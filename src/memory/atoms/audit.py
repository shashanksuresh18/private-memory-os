"""Hash-only audit log for atom resolutions.

Append-only JSONL. Each record carries the SHA-256 of the resolved bytes,
the atom_id, page_slug, byte span, tier, peer label, and the previous
record's hash for chain integrity. **No record contains the resolved
bytes themselves, ever.**

Chain construction: each record's `entry_hash` is sha256 over the JSON
serialization of the record's payload concatenated with the prior
record's `entry_hash` (or 64 zero hexits at genesis). Tampering with any
record breaks the chain at and after the tampered row.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List


DEFAULT_AUDIT_PATH = Path("audit/atoms.jsonl")
GENESIS_HASH = "0" * 64


@dataclass(frozen=True)
class AtomAuditEntry:
    schema_version: int
    ts: str
    atom_id: int
    page_slug: str
    byte_start: int
    byte_end: int
    tier: str
    peer: str
    resolved_sha256: str
    prev_hash: str
    entry_hash: str


def _hash_payload(payload: dict, prev_hash: str) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)
    h = hashlib.sha256()
    h.update(body.encode("utf-8"))
    h.update(b"|")
    h.update(prev_hash.encode("ascii"))
    return h.hexdigest()


def _tail_hash(audit_path: Path) -> str:
    if not audit_path.exists():
        return GENESIS_HASH
    last_hash = GENESIS_HASH
    with audit_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            last_hash = json.loads(line)["entry_hash"]
    return last_hash


def append_atom_event(
    audit_path: Path | str,
    *,
    atom_id: int,
    page_slug: str,
    byte_start: int,
    byte_end: int,
    tier: str,
    peer: str,
    resolved_bytes: bytes,
) -> AtomAuditEntry:
    """Append one audit row. The `resolved_bytes` argument is hashed and
    DISCARDED — never persisted to the log.
    """
    path = Path(audit_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    resolved_sha = hashlib.sha256(resolved_bytes).hexdigest()
    prev = _tail_hash(path)
    payload = {
        "schema_version": 1,
        "ts": datetime.now(timezone.utc).isoformat(),
        "atom_id": atom_id,
        "page_slug": page_slug,
        "byte_start": byte_start,
        "byte_end": byte_end,
        "tier": tier,
        "peer": peer,
        "resolved_sha256": resolved_sha,
        "prev_hash": prev,
    }
    entry_hash = _hash_payload(payload, prev)
    entry = AtomAuditEntry(entry_hash=entry_hash, **payload)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())
    return entry


def verify_audit_chain(audit_path: Path | str) -> List[int]:
    """Verify the hash chain. Returns the list of 1-indexed row numbers
    whose `entry_hash` does not match the recomputed value, or whose
    `prev_hash` does not equal the prior row's `entry_hash`. Empty list
    means chain is intact.
    """
    path = Path(audit_path)
    if not path.exists():
        return []
    bad_rows: List[int] = []
    prev = GENESIS_HASH
    with path.open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("prev_hash") != prev:
                bad_rows.append(idx)
            payload = {k: row[k] for k in (
                "schema_version", "ts", "atom_id", "page_slug",
                "byte_start", "byte_end", "tier", "peer",
                "resolved_sha256", "prev_hash",
            )}
            recomputed = _hash_payload(payload, prev)
            if recomputed != row.get("entry_hash"):
                if idx not in bad_rows:
                    bad_rows.append(idx)
            prev = row["entry_hash"]
    return bad_rows


def scan_for_plaintext(audit_path: Path | str,
                       needles: Iterable[str]) -> List[str]:
    """Defense-in-depth scan: returns any needle that appears in the
    audit log's raw bytes. Used by the gating test.
    """
    path = Path(audit_path)
    if not path.exists():
        return []
    raw = path.read_bytes()
    found: List[str] = []
    for needle in needles:
        if not needle:
            continue
        if needle.encode("utf-8") in raw:
            found.append(needle)
    return found
