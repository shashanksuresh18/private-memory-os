"""Ingest a vault of markdown files into the retrieval DB.

Tier policy (LOCKED decision #5): pages without an explicit `tier:` field in
YAML frontmatter are REFUSED with a loud error. No silent default.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List

from src.ingest.converter import SUPPORTED, convert_to_vault

from . import db as dbmod
from .chunker import chunk_markdown
from .embedder import Embedder, HashEmbedder, pack_vector

_FRONTMATTER_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
_TIER_RE = re.compile(r"(?m)^tier\s*:\s*(S[123])\s*$")
_DERIVED_RE = re.compile(r"(?m)^derived\s*:\s*true\s*$")
_VALID_TIERS = {"S1", "S2", "S3"}


def is_derived(source_text: str) -> bool:
    """True if frontmatter carries `derived: true`.

    Derived pages (e.g. the auto-generated `vault/wiki/index.md`) are synthesis
    artefacts, never source-of-truth, so they are skipped on ingest and can
    never surface as a citation.
    """
    m = _FRONTMATTER_RE.match(source_text)
    if not m:
        return False
    return bool(_DERIVED_RE.search(m.group(1)))


class TierMissingError(ValueError):
    """Raised when a page has no `tier:` field in frontmatter."""


def parse_tier(source_text: str, page_path: Path) -> str:
    m = _FRONTMATTER_RE.match(source_text)
    if not m:
        raise TierMissingError(
            f"{page_path}: missing YAML frontmatter; refuse-ingest (LOCKED decision #5)"
        )
    tier_match = _TIER_RE.search(m.group(1))
    if not tier_match:
        raise TierMissingError(
            f"{page_path}: frontmatter has no `tier:` field; refuse-ingest"
        )
    tier = tier_match.group(1)
    if tier not in _VALID_TIERS:
        raise TierMissingError(f"{page_path}: invalid tier {tier!r}")
    return tier


# Lifecycle staging dirs that are NOT the knowledge base: raw/ holds
# pre-conversion sources, archive/ holds processed originals. Neither is ever
# indexed — only curated/converted pages (inbox, people, companies, ...) are.
_NON_INDEXED_DIRS = {"raw", "archive"}


def _iter_markdown(vault_path: Path) -> Iterable[Path]:
    for p in sorted(vault_path.rglob("*.md")):
        if not p.is_file():
            continue
        rel_parts = p.relative_to(vault_path).parts
        if rel_parts and rel_parts[0] in _NON_INDEXED_DIRS:
            continue
        yield p


def _convert_inbox_sources(vault_path: Path) -> list[Path]:
    inbox = vault_path / "inbox"
    if not inbox.exists():
        return []
    converted: list[Path] = []
    for source in sorted(p for p in inbox.iterdir() if p.is_file()):
        if source.suffix.lower() in SUPPORTED:
            converted.append(convert_to_vault(source, inbox, tier=None))
    return converted


def _slug(vault_path: Path, page_path: Path) -> str:
    rel = page_path.relative_to(vault_path).with_suffix("")
    return rel.as_posix()


def repo_relative_path(vault_path: Path, page_path: Path) -> str:
    """Return ``page_path`` as a repo-root-relative string, e.g.
    ``vault\\inbox\\x.md``.

    Stored ``page_path`` MUST be repo-relative + portable: a file created
    manually (Obsidian / VS Code -> the vault bridge hands ``ingest_file`` an
    ABSOLUTE path) must land identically to a relative-vault ingest. Without this
    an absolute ``C:\\sovereign-citadel\\vault\\inbox\\x.md`` leaks into the DB,
    breaking portability and the planned mac migration.

    ``engine.resolve`` anchors a relative result back to ``REPO_ROOT`` at reopen
    time, so storage is cwd-independent. Files OUTSIDE the repo root (e.g. a
    tmp-dir vault in tests, or a relocated vault) are not repo-relative — they
    fall back to an absolute path, which ``resolve`` opens directly.
    ``vault_path`` is accepted for call-site symmetry but the anchor is the fixed
    repo root, not the vault parent.
    """
    abs_page = page_path.resolve()
    try:
        return str(abs_page.relative_to(dbmod.REPO_ROOT))
    except ValueError:
        return str(abs_page)


def ingest_page(
    vault_path: Path | str,
    file_path: Path | str,
    db_path: Path | str | None = None,
    embedder: Embedder | None = None,
) -> int | None:
    """Index exactly ONE markdown page into the retrieval DB and return its
    chunk count (or None if the page is derived / has no valid tier).

    Delete-by-slug then re-insert, so a re-submitted page is refreshed, not
    duplicated (the ``ON DELETE CASCADE`` + FTS delete trigger clear the old
    chunks/vectors/FTS rows). This is the surface ``POST /ingest`` uses: a
    drop-a-note write must index ONLY the page it just wrote, never sweep the
    whole vault — so the returned count reflects the submitted document alone
    (not any auto-wiki concept pages a prior query queued), and the call is
    bounded (no re-embedding the backlog, no hang under Ollama contention).
    Whole-vault catch-up for manually-added or auto-wiki pages stays the job of
    the scheduled ``ingest_new.py --reindex`` pass and the vault bridge.

    Mirrors the per-file logic in ``src/mcp/vault-bridge/server.py:ingest_file``
    (which should delegate here in a future cleanup — tech-debt).
    """
    vault_path = Path(vault_path)
    file_path = Path(file_path)
    slug = _slug(vault_path, file_path)

    source_text = file_path.read_bytes().decode("utf-8")
    if is_derived(source_text):
        return None
    try:
        tier = parse_tier(source_text, file_path)
    except TierMissingError:
        return None

    if embedder is None:
        embedder = HashEmbedder()

    conn = dbmod.connect(db_path)
    try:
        # FK cascade must be on for the page delete to clear chunks/vectors.
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("DELETE FROM pages WHERE page_slug = ?", (slug,))

        now = datetime.now(timezone.utc).isoformat()
        sha256 = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
        cur = conn.execute(
            "INSERT INTO pages(page_slug, page_path, tier, sha256, ingested_at) "
            "VALUES (?,?,?,?,?)",
            (slug, repo_relative_path(vault_path, file_path), tier, sha256, now),
        )
        page_id = cur.lastrowid

        chunks = chunk_markdown(source_text)
        for idx, ch in enumerate(chunks):
            cur = conn.execute(
                "INSERT INTO chunks(page_id, chunk_index, chunk_start_byte, "
                "chunk_end_byte, line_start, line_end, tier, text) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (page_id, idx, ch.byte_start, ch.byte_end,
                 ch.line_start, ch.line_end, tier, ch.text),
            )
            chunk_id = cur.lastrowid
            vec = embedder.embed(ch.text)
            conn.execute(
                "INSERT INTO vectors(chunk_id, dim, embedding) VALUES (?,?,?)",
                (chunk_id, len(vec), pack_vector(vec)),
            )
        conn.commit()
    finally:
        conn.close()
    return len(chunks)


def ingest_vault(
    vault_path: Path | str,
    db_path: Path | str | None = None,
    embedder: Embedder | None = None,
    reset: bool = True,
    incremental: bool = True,
) -> dict:
    """Ingest markdown pages from `vault_path` into the retrieval DB.

    Modes:
      - `reset=True` (default): drop + rebuild the whole index. Full re-embed.
      - `reset=False, incremental=True`: append-only. Skip any page whose
        `page_slug` already has a row in `pages`; embed only NEW files. This is
        the cheap path for a single fetched email/calendar event — it never
        drops existing pages and never re-embeds the ~700 unchanged chunks.
      - `reset=False, incremental=False`: legacy append that would duplicate
        existing pages; kept only for explicit callers, not recommended.

    `incremental` is a no-op when `reset=True` (the table is empty after reset).
    Returns added `pages` / `chunks` plus `skipped` (existing pages left as-is).
    """
    vault_path = Path(vault_path)
    if reset:
        dbmod.reset(db_path)
    conn = dbmod.connect(db_path)
    if embedder is None:
        embedder = HashEmbedder()

    _convert_inbox_sources(vault_path)

    # Incremental diff is by page_slug (vault-relative path, the stable key).
    existing_slugs: set[str] = set()
    if incremental and not reset:
        existing_slugs = {
            row[0] for row in conn.execute("SELECT page_slug FROM pages")
        }

    now = datetime.now(timezone.utc).isoformat()
    pages_count = 0
    chunks_count = 0
    skipped_count = 0
    refused: List[str] = []

    for page_path in _iter_markdown(vault_path):
        # Skip pages already in the index BEFORE any file read or embed — this
        # is what makes the incremental path cheap (no re-embedding 700 chunks).
        # `_slug` derives from the path alone, no disk I/O.
        slug = _slug(vault_path, page_path)
        if slug in existing_slugs:
            skipped_count += 1
            continue
        # Bytes-first read avoids Windows CRLF translation. The chunker
        # operates on `source_text.encode("utf-8")` which must equal the
        # file's on-disk byte sequence for resolve() to round-trip.
        source_text = page_path.read_bytes().decode("utf-8")
        # Derived pages (synthesis artefacts) are never indexed -> never cited.
        if is_derived(source_text):
            continue
        try:
            tier = parse_tier(source_text, page_path)
        except TierMissingError as e:
            refused.append(str(e))
            continue

        sha256 = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
        cur = conn.execute(
            "INSERT INTO pages(page_slug, page_path, tier, sha256, ingested_at) "
            "VALUES (?,?,?,?,?)",
            (slug, repo_relative_path(vault_path, page_path), tier, sha256, now),
        )
        page_id = cur.lastrowid
        pages_count += 1

        chunks = chunk_markdown(source_text)
        # Per-chunk embed() on purpose: Ollama /api/embed is SEQUENTIAL, so a
        # batched call gives no throughput gain and instead concentrates many
        # chunks under one timeout budget (a full batch of large chunks tripped
        # the read timeout and aborted a whole reingest). Per-chunk gives each
        # chunk its own timeout + retry. embed_batch() stays on the embedder
        # classes (tested) but is intentionally not used here.
        for idx, ch in enumerate(chunks):
            cur = conn.execute(
                "INSERT INTO chunks(page_id, chunk_index, chunk_start_byte, "
                "chunk_end_byte, line_start, line_end, tier, text) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (page_id, idx, ch.byte_start, ch.byte_end,
                 ch.line_start, ch.line_end, tier, ch.text),
            )
            chunk_id = cur.lastrowid
            vec = embedder.embed(ch.text)
            conn.execute(
                "INSERT INTO vectors(chunk_id, dim, embedding) VALUES (?,?,?)",
                (chunk_id, len(vec), pack_vector(vec)),
            )
            chunks_count += 1

    conn.commit()
    conn.close()
    if refused:
        raise TierMissingError(
            f"refused {len(refused)} page(s): " + "; ".join(refused)
        )
    return {"pages": pages_count, "chunks": chunks_count, "skipped": skipped_count}
