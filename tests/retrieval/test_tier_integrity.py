"""Tier integrity gating test.

- A page with no `tier:` frontmatter is refused (LOCKED decision #5).
- A query at one tier never returns chunks from any other tier.
- Every chunk row carries the tier of its source page.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.retrieval import db as dbmod
from src.retrieval.engine import retrieve
from src.retrieval.index import TierMissingError, ingest_vault


VAULT = Path(__file__).parent / "synthetic_public_vault"


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "retrieval.db"


@pytest.mark.gating
def test_refuse_ingest_without_tier(tmp_path: Path, db_path: Path) -> None:
    bad = tmp_path / "vault"
    bad.mkdir()
    (bad / "no_frontmatter.md").write_bytes(b"# just a heading\n\nbody\n")
    with pytest.raises(TierMissingError):
        ingest_vault(bad, db_path=db_path)


@pytest.mark.gating
def test_refuse_ingest_with_invalid_tier(tmp_path: Path, db_path: Path) -> None:
    bad = tmp_path / "vault"
    bad.mkdir()
    (bad / "bad.md").write_bytes(b"---\ntier: S5\n---\n# h\n\nbody\n")
    with pytest.raises(TierMissingError):
        ingest_vault(bad, db_path=db_path)


@pytest.mark.gating
def test_query_tier_isolation(tmp_path: Path, db_path: Path) -> None:
    ingest_vault(VAULT, db_path=db_path)
    s1 = retrieve("Wonderland Capital investment philosophy", tier="S1", k=10, db_path=db_path)
    assert s1, "expected at least one S1 hit"
    for c in s1:
        assert c.tier == "S1"
    s3 = retrieve("Wonderland Capital investment philosophy", tier="S3", k=10, db_path=db_path)
    assert s3 == [], "no S3 chunks exist in synthetic vault; tier filter must return empty"


@pytest.mark.gating
def test_chunk_rows_carry_source_page_tier(tmp_path: Path, db_path: Path) -> None:
    ingest_vault(VAULT, db_path=db_path)
    conn = dbmod.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT c.tier AS ct, p.tier AS pt FROM chunks c "
            "JOIN pages p ON c.page_id = p.page_id"
        ).fetchall()
        assert rows
        for r in rows:
            assert r["ct"] == r["pt"]
    finally:
        conn.close()
