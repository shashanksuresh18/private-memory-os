"""Vault bridge: debounced incremental ingest of changed vault markdown.

Handler dispatch + filtering + debounce are tested with a counting stub (no DB,
no embedder, no network). `ingest_file` correctness is tested directly with the
deterministic HashEmbedder. No Ollama / no network anywhere.
"""

from __future__ import annotations

import importlib.util
import sqlite3
import threading
import time
from pathlib import Path
from types import SimpleNamespace

from src.retrieval.embedder import HashEmbedder

ROOT = Path(__file__).resolve().parents[1]


def _load_bridge():
    server_path = ROOT / "src" / "mcp" / "vault-bridge" / "server.py"
    spec = importlib.util.spec_from_file_location("vault_bridge_server", server_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bridge = _load_bridge()

PAGE = "---\ntier: S1\n---\n\n# {title}\n\nBody text for {title}.\n"


def _evt(path: Path, is_directory: bool = False):
    """Minimal stand-in for a watchdog FileSystemEvent."""
    return SimpleNamespace(src_path=str(path), is_directory=is_directory)


def _make_handler(vault: Path, debounce: float = 0.05):
    """Handler wired to a thread-safe counting stub instead of real ingest."""
    calls: list[Path] = []
    lock = threading.Lock()

    def stub(path: Path):
        with lock:
            calls.append(path)

    handler = bridge.VaultBridgeHandler(vault, debounce=debounce, ingest_fn=stub)
    return handler, calls


def test_new_file_triggers_ingest(tmp_path):
    vault = tmp_path / "vault"
    (vault / "people").mkdir(parents=True)
    page = vault / "people" / "alice.md"
    page.write_text(PAGE.format(title="Alice"), encoding="utf-8")

    handler, calls = _make_handler(vault)
    handler.on_created(_evt(page))

    time.sleep(0.2)  # > debounce
    assert calls == [page]


def test_debounce_batches_rapid_saves(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    page = vault / "memo.md"
    page.write_text(PAGE.format(title="Memo"), encoding="utf-8")

    handler, calls = _make_handler(vault, debounce=0.15)
    # Simulate Obsidian firing many modify events while typing.
    for _ in range(6):
        handler.on_modified(_evt(page))
        time.sleep(0.01)

    time.sleep(0.3)  # let the single debounced timer fire
    assert calls == [page]  # collapsed to ONE ingest


def test_archive_files_skipped(tmp_path):
    vault = tmp_path / "vault"
    (vault / "archive").mkdir(parents=True)
    page = vault / "archive" / "old.md"
    page.write_text(PAGE.format(title="Old"), encoding="utf-8")

    handler, calls = _make_handler(vault)
    handler.on_created(_evt(page))
    handler.on_modified(_evt(page))

    time.sleep(0.2)
    assert calls == []  # never ingested


def test_email_files_skipped(tmp_path):
    vault = tmp_path / "vault"
    (vault / "inbox").mkdir(parents=True)
    email = vault / "inbox" / "email_123.md"
    calendar = vault / "inbox" / "calendar_2026-06-06_abc.md"
    for p in (email, calendar):
        p.write_text(PAGE.format(title="Fetched"), encoding="utf-8")

    handler, calls = _make_handler(vault)
    handler.on_created(_evt(email))
    handler.on_modified(_evt(calendar))

    time.sleep(0.2)
    assert calls == []  # fetch-script-managed pages are not watcher's job


def test_ingest_file_adds_then_refreshes(tmp_path):
    """ingest_file inserts a new page, then a re-ingest refreshes (no dup)."""
    vault = tmp_path / "vault"
    (vault / "memos").mkdir(parents=True)
    page = vault / "memos" / "deal.md"
    page.write_text(PAGE.format(title="Deal"), encoding="utf-8")
    db_path = str(tmp_path / "r.db")
    emb = HashEmbedder()

    n = bridge.ingest_file(vault, page, db_path=db_path, embedder=emb)
    assert n and n >= 1

    conn = sqlite3.connect(db_path)
    pages = conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
    chunks_first = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    conn.close()
    assert pages == 1

    # Modify and re-ingest: still exactly one page, chunks replaced not doubled.
    page.write_text(PAGE.format(title="Deal v2 with more body text here."),
                    encoding="utf-8")
    bridge.ingest_file(vault, page, db_path=db_path, embedder=emb)

    conn = sqlite3.connect(db_path)
    pages = conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
    chunks_after = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    vectors = conn.execute("SELECT COUNT(*) FROM vectors").fetchone()[0]
    conn.close()
    assert pages == 1
    assert vectors == chunks_after  # vectors stay 1:1 with chunks (cascade clean)
    assert chunks_after >= 1
    assert chunks_first  # sanity
