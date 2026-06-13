"""Sovereign Citadel Deny-list Admin CLI.

Atomic mutation gateway for ``src/routing/classifier/denylist/{codenames,tickers,markers}.txt``.

Every mutation:
    1. Validates the term.
    2. Reads the current file, checks for duplicate/missing.
    3. Writes the new contents to ``<file>.tmp``, fsyncs, then atomically
       ``os.replace``s onto the live path.
    4. Appends a hash-chained record to ``audit/denylist_mutations.jsonl``.
    5. Best-effort POSTs ``/_admin/reload-denylist`` on the running router so
       any cached in-process classifier picks the change up immediately.
       Even without the POST, classifier auto-invalidates via mtime check
       on the next call, so the CLI never fails because the router is down.

Audit records never write the term in plaintext — only its SHA-256 hash and
length, so the audit log itself cannot become an MNPI leak.

Usage
-----
    python -m tools.admin.denylist_cli add tickers ACME
    python -m tools.admin.denylist_cli add codenames "Project Orion"
    python -m tools.admin.denylist_cli remove markers "embargoed"
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import platform
import socket
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Iterable

VALID_LISTS = ("codenames", "tickers", "markers")

DENYLIST_DIR = Path(os.environ.get(
    "SOVEREIGN_CLASSIFIER_DENYLIST_DIR",
    "src/routing/classifier/denylist",
))
AUDIT_PATH = Path(os.environ.get(
    "SOVEREIGN_AUDIT_DIR", "audit",
)) / "denylist_mutations.jsonl"
ROUTER_URL = os.environ.get("SOVEREIGN_ROUTER_URL", "http://127.0.0.1:8770")
ROUTER_TOKEN_PATH = Path(os.environ.get(
    "SOVEREIGN_ROUTER_TOKEN_FILE", "src/routing/.token",
))

MIN_TERM_LEN = 2
MAX_TERM_LEN = 200

_audit_lock = threading.Lock()


# ---------- validation ----------

def _validate_list_name(name: str) -> str:
    if name not in VALID_LISTS:
        raise SystemExit(f"error: list must be one of {VALID_LISTS}, got {name!r}")
    return name


def _validate_term(term: str) -> str:
    term = term.strip()
    if not term:
        raise SystemExit("error: term is empty after stripping whitespace")
    if len(term) < MIN_TERM_LEN:
        raise SystemExit(f"error: term shorter than {MIN_TERM_LEN} chars")
    if len(term) > MAX_TERM_LEN:
        raise SystemExit(f"error: term longer than {MAX_TERM_LEN} chars")
    for ch in term:
        if ord(ch) < 0x20 and ch not in (" ",):
            raise SystemExit("error: term contains control characters")
        if ch in ("\n", "\r", "\t", "\x00"):
            raise SystemExit("error: term contains newline/tab/null")
    return term


# ---------- file IO (atomic) ----------

def _read_file_lines(path: Path) -> tuple[list[str], list[str]]:
    """Return (all_lines_preserved, normalized_terms_lowercased).

    The first list preserves comments + blank lines so atomic writes don't
    destroy operator-authored sections. The second list is the matching set
    for duplicate/missing checks.
    """
    if not path.exists():
        return [], []
    all_lines = path.read_text(encoding="utf-8").splitlines()
    terms: list[str] = []
    for ln in all_lines:
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        terms.append(s.casefold())
    return all_lines, terms


def _atomic_write(path: Path, content: str) -> None:
    """Write ``content`` to ``path`` atomically: tmp -> fsync -> os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path_str = tempfile.mkstemp(
        prefix=path.name + ".",
        suffix=".tmp",
        dir=str(path.parent),
    )
    tmp_path = Path(tmp_path_str)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        finally:
            raise


def _sha256_file(path: Path) -> str:
    if not path.exists():
        return ""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------- audit log (hash-chain) ----------

def _audit_append(record: dict) -> None:
    """Append one hash-chained JSON line to audit/denylist_mutations.jsonl."""
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _audit_lock:
        prev_hash = ""
        if AUDIT_PATH.exists() and AUDIT_PATH.stat().st_size > 0:
            with AUDIT_PATH.open("rb") as fh:
                fh.seek(-min(4096, AUDIT_PATH.stat().st_size), 2)
                tail = fh.read().decode("utf-8", errors="ignore").splitlines()
                if tail:
                    try:
                        prev_hash = json.loads(tail[-1]).get("hash", "")
                    except Exception:
                        prev_hash = ""
        record = dict(record)
        record["prev_hash"] = prev_hash
        record_no_hash = json.dumps(record, sort_keys=True, ensure_ascii=False)
        record["hash"] = hashlib.sha256(record_no_hash.encode("utf-8")).hexdigest()
        with AUDIT_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            fh.flush()
            os.fsync(fh.fileno())


# ---------- hot reload (best-effort) ----------

def _notify_router() -> tuple[bool, str]:
    """POST /_admin/reload-denylist on the running router. Never blocks mutation."""
    token = ""
    if ROUTER_TOKEN_PATH.exists():
        token = ROUTER_TOKEN_PATH.read_text(encoding="utf-8").strip()
    headers = {"x-sovereign-token": token} if token else {}
    try:
        import httpx  # local import — cli works without httpx if router is down
        r = httpx.post(f"{ROUTER_URL}/_admin/reload-denylist", headers=headers, timeout=2.5)
        return (r.status_code == 200, f"{r.status_code} {r.text[:120]}")
    except Exception as exc:
        return (False, f"{type(exc).__name__}: {exc}")


# ---------- commands ----------

def _operator_id() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return os.environ.get("USERNAME") or os.environ.get("USER") or "unknown"


def _build_file_content(lines: list[str], terms_normalized: list[str]) -> str:
    """Reconstruct file content from preserved lines + the new terms set.

    Comments / blank lines from the original are kept in place. The mutation
    operates only on plain term lines. A new term is appended at the end of
    the file. A removed term is filtered out.
    """
    return "\n".join(lines) + ("\n" if lines and not lines[-1].endswith("\n") else "")


def _do_add(list_name: str, term: str) -> int:
    list_name = _validate_list_name(list_name)
    term = _validate_term(term)
    target = DENYLIST_DIR / f"{list_name}.txt"

    all_lines, terms = _read_file_lines(target)
    if term.casefold() in terms:
        print(f"noop: {term!r} already present in {list_name}.txt", file=sys.stderr)
        return 1

    before_hash = _sha256_file(target)
    before_size = len(terms)

    new_lines = list(all_lines)
    if new_lines and new_lines[-1].strip():
        new_lines.append("")
    new_lines.append(term)
    content = "\n".join(new_lines).rstrip() + "\n"
    _atomic_write(target, content)

    after_hash = _sha256_file(target)
    after_size = before_size + 1

    record = _make_record("add", list_name, term, before_hash, after_hash,
                          before_size, after_size)
    _audit_append(record)
    print(f"added {term!r} to {list_name}.txt  (terms: {before_size} -> {after_size})")
    _print_reload_status()
    return 0


def _do_remove(list_name: str, term: str) -> int:
    list_name = _validate_list_name(list_name)
    term = _validate_term(term)
    target = DENYLIST_DIR / f"{list_name}.txt"

    all_lines, terms = _read_file_lines(target)
    if term.casefold() not in terms:
        print(f"noop: {term!r} not present in {list_name}.txt", file=sys.stderr)
        return 1

    before_hash = _sha256_file(target)
    before_size = len(terms)

    new_lines = [ln for ln in all_lines if ln.strip().casefold() != term.casefold()]
    content = "\n".join(new_lines).rstrip() + "\n" if new_lines else ""
    _atomic_write(target, content)

    after_hash = _sha256_file(target)
    after_size = before_size - 1

    record = _make_record("remove", list_name, term, before_hash, after_hash,
                          before_size, after_size)
    _audit_append(record)
    print(f"removed {term!r} from {list_name}.txt  (terms: {before_size} -> {after_size})")
    _print_reload_status()
    return 0


def _make_record(action: str, list_name: str, term: str,
                 before_hash: str, after_hash: str,
                 before_size: int, after_size: int) -> dict:
    term_sha = hashlib.sha256(term.encode("utf-8")).hexdigest()
    return {
        "ts": time.time(),
        "ts_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "event_id": uuid.uuid4().hex,
        "service": "denylist_admin",
        "action": action,
        "list_name": list_name,
        "term_sha256": term_sha,
        "term_length": len(term),
        "operator_id": _operator_id(),
        "host": socket.gethostname(),
        "platform": platform.system(),
        "list_file_sha256_before": before_hash,
        "list_file_sha256_after": after_hash,
        "list_size_before": before_size,
        "list_size_after": after_size,
    }


def _print_reload_status() -> None:
    ok, detail = _notify_router()
    if ok:
        print("router notified: /_admin/reload-denylist OK")
    else:
        print(f"router not notified (best-effort, file change still picked up by mtime cache): {detail}",
              file=sys.stderr)


# ---------- entry ----------

def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="denylist_cli",
        description="Atomic, audited admin tool for the Sovereign Citadel deny-lists.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    add_p = sub.add_parser("add", help="add a term to a deny-list")
    add_p.add_argument("list_name", choices=VALID_LISTS)
    add_p.add_argument("term")

    rm_p = sub.add_parser("remove", help="remove a term from a deny-list")
    rm_p.add_argument("list_name", choices=VALID_LISTS)
    rm_p.add_argument("term")

    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.cmd == "add":
        return _do_add(args.list_name, args.term)
    if args.cmd == "remove":
        return _do_remove(args.list_name, args.term)
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
