"""Citations must reopen byte-identical to the indexed source span.

LOCKED rule: final answers cite source text only. The agent reopens
`vault/<page_slug>` and slices `[byte_start:byte_end]` — never the indexed
copy of the text. Without this, a re-classification of the source file
would not propagate to past answers.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.retrieval.engine import resolve, retrieve
from src.retrieval.index import ingest_vault


VAULT = Path(__file__).parent / "synthetic_public_vault"


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "retrieval.db"


@pytest.mark.gating
def test_citation_reopens_to_live_source_bytes(db_path: Path) -> None:
    ingest_vault(VAULT, db_path=db_path)
    results = retrieve("EDGAR public filing workflow", tier="S1", k=5, db_path=db_path)
    assert results
    for c in results:
        raw = Path(c.page_path).read_bytes()
        live_slice = raw[c.byte_start:c.byte_end].decode("utf-8")
        assert c.text == live_slice, f"resolve drift on {c.page_slug}"


@pytest.mark.gating
def test_resolve_function_reflects_live_file(tmp_path: Path, db_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    page = vault / "p.md"
    # Same-length replacement so byte offsets remain valid; the test
    # asserts resolve() reads the LIVE file, not a cached copy of the text.
    original = "---\ntier: S1\n---\n# H\n\nABCDEFG original.\n"
    page.write_bytes(original.encode("utf-8"))
    ingest_vault(vault, db_path=db_path)

    hits = retrieve("ABCDEFG original", tier="S1", k=5, db_path=db_path)
    assert hits
    c = hits[0]

    pre = resolve(c.page_path, c.byte_start, c.byte_end)
    assert "ABCDEFG" in pre and "original" in pre

    edited = original.replace("ABCDEFG", "ZYXWVUT")
    assert len(edited.encode("utf-8")) == len(original.encode("utf-8"))
    page.write_bytes(edited.encode("utf-8"))

    post = resolve(c.page_path, c.byte_start, c.byte_end)
    assert "ZYXWVUT" in post and "ABCDEFG" not in post
