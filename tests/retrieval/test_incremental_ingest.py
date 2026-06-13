"""Incremental ingest: skip pages already in the DB, embed only new files.

HashEmbedder only — deterministic, no Ollama / no network.
"""

from __future__ import annotations

import sqlite3

from src.retrieval.embedder import HashEmbedder
from src.retrieval.index import ingest_vault

PAGE = "---\ntier: S1\n---\n\n# {title}\n\nBody text for {title}.\n"


def _page_slugs(db_path) -> set[str]:
    conn = sqlite3.connect(db_path)
    try:
        return {r[0] for r in conn.execute("SELECT page_slug FROM pages")}
    finally:
        conn.close()


def _write(vault, name, title):
    (vault / f"{name}.md").write_text(PAGE.format(title=title), encoding="utf-8")


def test_incremental_skips_existing_adds_new(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    db_path = str(tmp_path / "r.db")
    emb = HashEmbedder()

    _write(vault, "alpha", "Alpha")
    _write(vault, "beta", "Beta")

    # Full build of the first two pages.
    first = ingest_vault(vault, db_path=db_path, embedder=emb, reset=True)
    assert first["pages"] == 2
    assert _page_slugs(db_path) == {"alpha", "beta"}

    # Add one new page, run incremental: only the new page is added, the two
    # existing pages are skipped (never dropped, never re-embedded).
    _write(vault, "gamma", "Gamma")
    inc = ingest_vault(
        vault, db_path=db_path, embedder=emb, reset=False, incremental=True
    )
    assert inc["pages"] == 1          # only gamma embedded
    assert inc["skipped"] == 2        # alpha + beta left as-is
    assert _page_slugs(db_path) == {"alpha", "beta", "gamma"}


def test_incremental_noop_when_nothing_new(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    db_path = str(tmp_path / "r.db")
    emb = HashEmbedder()

    _write(vault, "alpha", "Alpha")
    ingest_vault(vault, db_path=db_path, embedder=emb, reset=True)

    inc = ingest_vault(
        vault, db_path=db_path, embedder=emb, reset=False, incremental=True
    )
    assert inc["pages"] == 0
    assert inc["skipped"] == 1
    assert _page_slugs(db_path) == {"alpha"}


def test_incremental_does_not_duplicate_chunks(tmp_path):
    """Re-running incremental must not double-insert chunks for an existing page."""
    vault = tmp_path / "vault"
    vault.mkdir()
    db_path = str(tmp_path / "r.db")
    emb = HashEmbedder()

    _write(vault, "alpha", "Alpha")
    ingest_vault(vault, db_path=db_path, embedder=emb, reset=True)

    conn = sqlite3.connect(db_path)
    before = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    conn.close()

    ingest_vault(vault, db_path=db_path, embedder=emb, reset=False, incremental=True)

    conn = sqlite3.connect(db_path)
    after = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    conn.close()
    assert after == before
