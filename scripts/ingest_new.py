"""Vault ingest lifecycle: raw -> inbox -> index -> archive.

Karpathy-style capture loop, tier-safe:

  1. Convert / copy every source in ``vault/raw/`` into ``vault/inbox/`` markdown
     (binary types via MarkItDown; ``.md`` copied as-is). Never overwrites.
  2. Re-index the whole vault into ``retrieval.db``.
  3. Regenerate ``vault/wiki/index.md`` (derived=true, never a citation).
  4. Move processed raw originals into ``vault/archive/``.

Usage:
    python scripts/ingest_new.py
    python scripts/ingest_new.py --dry-run
"""

from __future__ import annotations

import argparse
import re
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# Run as a script: put the repo root (parent of scripts/) on the path.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.ingest.converter import DEFAULT_TIER, SUPPORTED, convert_to_vault  # noqa: E402
from src.retrieval.db import DEFAULT_DB_PATH  # noqa: E402
from src.retrieval.embedder import OllamaEmbedder  # noqa: E402
from src.retrieval.index import ingest_vault  # noqa: E402

VAULT = Path("vault")
RAW = VAULT / "raw"
INBOX = VAULT / "inbox"
ARCHIVE = VAULT / "archive"
WIKI = VAULT / "wiki"

# Folder-based tier classification: a file's sensitivity is decided by which
# raw subfolder it was dropped in. Anything in vault/raw/ root (or an unknown
# subfolder) fails closed to S3 — the most-restrictive tier, never cloud.
_TIER_SUBDIRS = {"s1": "S1", "s2": "S2", "s3": "S3"}
# Canonical absolute path from src/retrieval/db.py — resolves to repo-root/
# retrieval.db regardless of the caller's working directory, so ingest and the
# API server (server.py) always land on the SAME DB file.
DB_PATH = str(DEFAULT_DB_PATH)

_FRONTMATTER_RE = re.compile(r"^---\r?\n.*?\r?\n---\r?\n", re.DOTALL)
_H2_RE = re.compile(r"(?m)^##\s+(.+?)\s*$")

_TIER_ORDER = ("S1", "S2", "S3")
_TIER_LABEL = {"S1": "S1 — Public", "S2": "S2 — Sensitive", "S3": "S3 — Sealed"}


def ensure_raw_dirs() -> None:
    """Create vault/raw/ and its s1/s2/s3 tier subfolders if absent.

    Mirrors launch.bat so the CLI is self-healing on a fresh checkout.
    """
    for sub in _TIER_SUBDIRS:
        (RAW / sub).mkdir(parents=True, exist_ok=True)


def tier_for_raw_source(source: Path, raw_root: Path = RAW) -> str:
    """Tier from the raw subfolder a source sits in (fail-closed S3).

    vault/raw/s1/* -> S1, s2/* -> S2, s3/* -> S3. A file directly in
    vault/raw/ — or in any other subfolder — defaults to S3, the
    most-restrictive tier (never cloud). Unknown sensitivity fails closed.
    """
    try:
        rel = source.resolve().relative_to(raw_root.resolve())
    except ValueError:
        return DEFAULT_TIER  # outside the raw tree entirely -> fail closed
    if len(rel.parts) >= 2:
        return _TIER_SUBDIRS.get(rel.parts[0].lower(), DEFAULT_TIER)
    return DEFAULT_TIER


def _raw_sources() -> list[Path]:
    """Files dropped in vault/raw/ and its s1/s2/s3 tier subfolders.

    Top-level files in raw/ plus the immediate files in raw/{s1,s2,s3}/.
    Any other subdir is ignored (its files never get auto-staged).
    """
    if not RAW.exists():
        return []
    sources = [p for p in RAW.iterdir() if p.is_file()]
    for sub in _TIER_SUBDIRS:
        sub_dir = RAW / sub
        if sub_dir.is_dir():
            sources.extend(p for p in sub_dir.iterdir() if p.is_file())
    return sorted(sources)


def _stage_to_inbox(source: Path, tier: str | None = None) -> Path:
    """Convert (binary) or copy (.md) one raw source into the inbox.

    ``tier`` is the folder-derived sensitivity (see tier_for_raw_source).
    Converted files get it written into their frontmatter. A copied ``.md``
    keeps its own frontmatter; if it has none, tier frontmatter is prepended
    so a folder drop still classifies (fail-closed S3 when tier is None).

    Never overwrites an existing inbox file (FileExistsError, mirroring
    converter.convert_to_vault).
    """
    suffix = source.suffix.lower()
    if suffix in SUPPORTED:
        return convert_to_vault(source, INBOX, tier=tier)
    if suffix == ".md":
        out = INBOX / source.name
        if out.exists():
            raise FileExistsError(
                f"Vault file exists: {out}. Delete manually to re-stage."
            )
        text = source.read_text(encoding="utf-8", errors="replace")
        if not text.lstrip().startswith("---"):
            effective = tier or DEFAULT_TIER
            text = f"---\ntier: {effective}\n---\n\n" + text
        out.write_text(text, encoding="utf-8")
        return out
    raise ValueError(f"Unsupported raw source: {source.name}")


def _archive(source: Path) -> Path:
    """Move a processed raw original into vault/archive/ (never overwrites)."""
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    dest = ARCHIVE / source.name
    if dest.exists():
        raise FileExistsError(f"Archive file exists: {dest}. Refusing to overwrite.")
    shutil.move(str(source), str(dest))
    return dest


def _topics(page_path: str) -> str:
    """First 3 H2 headings, else first 50 chars of the first paragraph."""
    try:
        text = Path(page_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    body = _FRONTMATTER_RE.sub("", text, count=1)
    heads = [h.strip() for h in _H2_RE.findall(body)][:3]
    if heads:
        return ", ".join(heads)
    for para in re.split(r"\r?\n\s*\r?\n", body):
        p = para.strip()
        if p and not p.startswith("#"):
            return p[:50]
    return ""


def _pages_by_tier(db_path: str) -> dict[str, list[tuple[str, str]]]:
    """Return {tier: [(slug, page_path), ...]} from the retrieval DB."""
    out: dict[str, list[tuple[str, str]]] = {t: [] for t in _TIER_ORDER}
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT page_slug, page_path, tier FROM pages ORDER BY tier, page_slug"
        ).fetchall()
    finally:
        conn.close()
    for slug, page_path, tier in rows:
        if tier in out:
            out[tier].append((slug, page_path))
    return out


def generate_index(db_path: str = DB_PATH) -> Path:
    """Write vault/wiki/index.md from the current DB. derived=true -> never cited.

    S3 entries are slug + _(SEALED)_ only: no topics, no content preview.
    """
    WIKI.mkdir(parents=True, exist_ok=True)
    by_tier = _pages_by_tier(db_path)
    now = datetime.now(timezone.utc).isoformat()

    lines = [
        "---",
        "tier: S1",
        "derived: true",
        f"generated_at: {now}",
        "---",
        "",
        "# Vault Index",
        "_Auto-generated. Do not edit manually._",
        "",
    ]
    for tier in _TIER_ORDER:
        entries = by_tier[tier]
        lines.append(f"## {_TIER_LABEL[tier]} ({len(entries)} pages)")
        for slug, page_path in entries:
            if tier == "S3":
                lines.append(f"- [[{slug}]] _(SEALED)_")
            else:
                lines.append(f"- [[{slug}]]")
                topics = _topics(page_path)
                if topics:
                    lines.append(f"  topics: {topics}")
        lines.append("")

    index_path = WIKI / "index.md"
    index_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return index_path


def _dry_run(sources: list[Path]) -> None:
    print(f"[dry-run] {len(sources)} raw source(s) found:")
    for s in sources:
        suffix = s.suffix.lower()
        tier = tier_for_raw_source(s)
        if suffix in SUPPORTED:
            action = f"convert -> {INBOX / (s.stem + '.md')}"
        elif suffix == ".md":
            action = f"copy -> {INBOX / s.name}"
        else:
            action = "SKIP (unsupported)"
        print(f"  {s.name} [{tier}]: {action}; archive -> {ARCHIVE / s.name}")
    print("[dry-run] no files written, no ingest, index.md untouched")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Vault ingest lifecycle")
    parser.add_argument("--dry-run", action="store_true",
                        help="show what would be processed; make no changes")
    parser.add_argument("--reindex", action="store_true",
                        help="skip the raw/ staging gate; incrementally re-index "
                             "the whole vault into retrieval.db (embeds only NEW "
                             "page_slugs, skips existing). Used by the cron "
                             "auto-ingest job. Local Ollama only, zero cloud.")
    parser.add_argument("--rebuild", action="store_true",
                        help="full reset=True rebuild: drop + re-embed EVERY vault "
                             "page. Catches edits to already-indexed pages that "
                             "--reindex skips. Used by the nightly cron job. "
                             "Local Ollama only, zero cloud.")
    args = parser.parse_args(argv)

    if args.reindex and args.rebuild:
        parser.error("--reindex and --rebuild are mutually exclusive")

    if args.reindex or args.rebuild:
        # Stage anything dropped in vault/raw/ FIRST, so the 10-minute
        # scheduled --reindex job picks up drag-and-drop sources (PDF, Word,
        # Excel, PowerPoint, txt, md) without a manual run. Tier is decided by
        # the raw subfolder (s1/s2/s3); root drops fail closed to S3. Tolerant
        # loop: a collision or bad file is logged and left in raw/ for the
        # operator; it must never crash the scheduled job.
        ensure_raw_dirs()
        staged: list[Path] = []
        for source in _raw_sources():
            suffix = source.suffix.lower()
            if suffix not in SUPPORTED and suffix != ".md":
                print(f"skip unsupported: {source.name}")
                continue
            try:
                _stage_to_inbox(source, tier_for_raw_source(source))
                staged.append(source)
            except (FileExistsError, ValueError, OSError) as exc:
                print(f"skip {source.name}: {exc}")

        # --reindex: whole-vault incremental pass -- picks up files written
        #   straight into vault/<folder>/ (e.g. a new meeting note) that never
        #   passed through vault/raw/. Append-only, never re-embeds existing.
        # --rebuild: full reset -- drops and re-embeds every page so EDITS to
        #   already-indexed pages get re-indexed.
        rebuild = args.rebuild
        stats = ingest_vault(
            Path(VAULT), DB_PATH, embedder=OllamaEmbedder(),
            reset=rebuild, incremental=not rebuild,
        )
        generate_index(DB_PATH)

        # Archive raw originals only after a successful ingest pass.
        for source in staged:
            try:
                _archive(source)
            except FileExistsError as exc:
                print(f"archive skipped for {source.name}: {exc}")

        label = "rebuild" if rebuild else "reindex"
        print(f"{label}: {stats['pages']} new pages, "
              f"{stats['chunks']} chunks, {stats['skipped']} skipped, "
              f"{len(staged)} raw file(s) staged")
        return 0

    ensure_raw_dirs()
    sources = _raw_sources()
    if not sources:
        print("Nothing to process")
        return 0

    if args.dry_run:
        _dry_run(sources)
        return 0

    # 1. Stage every supported source into the inbox, tier from its folder.
    staged: list[Path] = []
    for source in sources:
        if source.suffix.lower() in SUPPORTED or source.suffix.lower() == ".md":
            _stage_to_inbox(source, tier_for_raw_source(source))
            staged.append(source)
        else:
            print(f"skip unsupported: {source.name}")

    # 2. Re-index the whole vault. The canonical retrieval.db is nomic-backed
    #    (768-dim nomic-embed-text); ingest with the same embedder so we never
    #    silently regress the production index to the offline hash stub.
    stats = ingest_vault(Path(VAULT), DB_PATH, embedder=OllamaEmbedder())

    # 3. Regenerate the derived index.
    generate_index(DB_PATH)

    # 4. Archive the processed raw originals.
    for source in staged:
        _archive(source)

    print(f"{len(staged)} files converted, {stats['pages']} pages indexed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
