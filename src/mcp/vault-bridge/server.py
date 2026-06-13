"""Local Obsidian vault bridge — watches `vault/` and triggers incremental
ingest of changed markdown into the canonical retrieval DB.

This is a *local* bridge, not a network MCP endpoint: it binds no socket and
opens no port. It is strictly a filesystem observer running on the host, so
there is no remote attack surface (loopback-only by construction). All embedding
goes through the same loopback Ollama / hash embedder the engine already uses;
S3 tier policy is inherited unchanged from `src.retrieval.index` (refuse-ingest
on missing tier, derived pages skipped, byte-offset citations preserved).

Design notes:
  - Reacts to created + modified `.md` events only (NOT deleted — a deletion is
    an operator action handled out-of-band; we never auto-purge the index).
  - Per-file 2s debounce: Obsidian writes on nearly every keystroke, so we wait
    for the writes to settle before paying for an embed.
  - Per-file ingest only. NEVER a full `reset=True` reindex (that would drop the
    whole DB and re-embed ~800 chunks). A changed page is deleted by slug — the
    `ON DELETE CASCADE` + FTS delete trigger clean its chunks/vectors/FTS rows —
    then re-inserted fresh, so modified pages are refreshed (plain incremental
    ingest would skip them because the slug already exists).
  - Skips `vault/archive/` and `vault/raw/` (lifecycle staging, never indexed)
    and `email_*.md` / `calendar_*.md` (owned by the fetch scripts, which run
    their own incremental ingest).
"""

from __future__ import annotations

import hashlib
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from src.retrieval import db as dbmod
from src.retrieval.chunker import chunk_markdown
from src.retrieval.embedder import Embedder, make_embedder
from src.retrieval.embedder import pack_vector
from src.retrieval.index import (
    TierMissingError,
    is_derived,
    parse_tier,
    repo_relative_path,
)

LOGGER = logging.getLogger("vault_bridge")

DEBOUNCE_SECONDS = 2.0

# Directories under vault/ that are never part of the knowledge base (mirrors
# src.retrieval.index._NON_INDEXED_DIRS). A change anywhere inside them is ignored.
_SKIP_DIRS = {"archive", "raw"}

# Filename prefixes owned by the fetch scripts (gmail / calendar). Those scripts
# run their own incremental ingest post-fetch, so the watcher must not double-handle.
_SKIP_PREFIXES = ("email_", "calendar_")


def is_watched(vault_path: Path, file_path: Path) -> bool:
    """True if `file_path` is a vault markdown page the bridge should ingest.

    Filters: must be a `.md` file inside `vault_path`, not under a skip dir, and
    not a fetch-script-managed `email_*` / `calendar_*` page.
    """
    if file_path.suffix.lower() != ".md":
        return False
    try:
        rel = file_path.relative_to(vault_path)
    except ValueError:
        return False
    if rel.parts and rel.parts[0] in _SKIP_DIRS:
        return False
    if file_path.name.startswith(_SKIP_PREFIXES):
        return False
    return True


def ingest_file(
    vault_path: Path | str,
    file_path: Path | str,
    db_path: Path | str | None = None,
    embedder: Embedder | None = None,
) -> int | None:
    """Incrementally (re)ingest a single markdown page into the retrieval DB.

    Deletes any existing rows for the page slug first (cascade clears chunks +
    vectors, the AFTER DELETE trigger clears FTS), then re-inserts page, chunks,
    and vectors. This refreshes modified pages — plain `ingest_vault(incremental=
    True)` would skip them because the slug already exists.

    Returns the number of chunks ingested, or `None` if the page was skipped
    (derived synthesis artefact) or refused (missing/invalid tier — fail-closed,
    logged, never crashes the watcher).
    """
    vault_path = Path(vault_path)
    file_path = Path(file_path)
    rel = file_path.relative_to(vault_path)
    slug = rel.with_suffix("").as_posix()

    source_text = file_path.read_bytes().decode("utf-8")
    if is_derived(source_text):
        return None
    try:
        tier = parse_tier(source_text, file_path)
    except TierMissingError as exc:
        LOGGER.warning("skipped vault/%s (refused): %s", rel.as_posix(), exc)
        return None

    if embedder is None:
        embedder = make_embedder()

    conn = dbmod.connect(db_path)
    try:
        # FK cascade must be on for the page delete to clear chunks/vectors.
        conn.execute("PRAGMA foreign_keys = ON")
        # Delete-then-insert so a modified page is refreshed, not duplicated.
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

    LOGGER.info("ingested vault/%s → +%d chunks", rel.as_posix(), len(chunks))
    return len(chunks)


class VaultBridgeHandler(FileSystemEventHandler):
    """Debounced watchdog handler that ingests changed vault markdown.

    `ingest_fn(path)` is injectable so tests can assert dispatch + debounce
    without touching the DB or an embedder; it defaults to `ingest_file` bound
    to the given vault/db/embedder.
    """

    def __init__(
        self,
        vault_path: Path | str,
        db_path: Path | str | None = None,
        embedder: Embedder | None = None,
        debounce: float = DEBOUNCE_SECONDS,
        ingest_fn: Callable[[Path], object] | None = None,
    ) -> None:
        self.vault_path = Path(vault_path)
        self.debounce = debounce
        if ingest_fn is not None:
            self._ingest = ingest_fn
        else:
            self._ingest = lambda p: ingest_file(
                self.vault_path, p, db_path=db_path, embedder=embedder
            )
        self._timers: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    # watchdog dispatches both creation and modification here.
    def on_created(self, event: FileSystemEvent) -> None:
        self._handle(event)

    def on_modified(self, event: FileSystemEvent) -> None:
        self._handle(event)

    def _handle(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        path = Path(event.src_path)
        if not is_watched(self.vault_path, path):
            return
        self._schedule(str(path))

    def _schedule(self, path_str: str) -> None:
        # Reset the per-file timer on every event so a burst of rapid saves
        # collapses into a single ingest `debounce` seconds after the last write.
        with self._lock:
            existing = self._timers.get(path_str)
            if existing is not None:
                existing.cancel()
            timer = threading.Timer(self.debounce, self._fire, args=(path_str,))
            timer.daemon = True
            self._timers[path_str] = timer
            timer.start()

    def _fire(self, path_str: str) -> None:
        with self._lock:
            self._timers.pop(path_str, None)
        try:
            self._ingest(Path(path_str))
        except Exception:  # noqa: BLE001 — a watcher must never die on one file
            LOGGER.exception("ingest failed for %s", path_str)


def build_observer(
    vault_path: Path | str,
    db_path: Path | str | None = None,
    embedder: Embedder | None = None,
    debounce: float = DEBOUNCE_SECONDS,
) -> Observer:
    """Construct (but do not start) a watchdog Observer for `vault_path`."""
    vault_path = Path(vault_path)
    handler = VaultBridgeHandler(
        vault_path, db_path=db_path, embedder=embedder, debounce=debounce
    )
    observer = Observer()
    observer.schedule(handler, str(vault_path), recursive=True)
    return observer
