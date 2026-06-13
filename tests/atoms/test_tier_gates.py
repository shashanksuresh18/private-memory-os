"""Tier gates around the atom extractor.

- S3 + enable_llm=True must raise (rule-only, fail-closed).
- S3 in the allowlist must raise even if the page is not S3 (the
  allowlist itself is malformed).
- composite_tier returns MAX(tier) — most restrictive of the inputs.
- retier_page cascades to atoms and to entities derived from those atoms.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.memory.atoms import (
    Atom,
    TierForbiddenLLMError,
    composite_tier,
    db as atomsdb,
    extract_atoms,
    retier_page,
)
from src.memory.atoms.extractor import persist_atoms


@pytest.mark.gating
def test_s3_with_enable_llm_raises() -> None:
    body = "---\ntier: S3\n---\n# H\n\nbody\n"
    with pytest.raises(TierForbiddenLLMError):
        extract_atoms(
            page_slug="p",
            page_source_bytes=body.encode("utf-8"),
            chunks=[(None, body, 0)],
            tier="S3",
            enable_llm=True,
        )


@pytest.mark.gating
def test_s3_in_allowlist_raises_even_on_s1_page() -> None:
    body = "---\ntier: S1\n---\n# H\n\nbody\n"
    with pytest.raises(TierForbiddenLLMError):
        extract_atoms(
            page_slug="p",
            page_source_bytes=body.encode("utf-8"),
            chunks=[(None, body, 0)],
            tier="S1",
            enable_llm=True,
            llm_tier_allowlist={"S1", "S2", "S3"},
        )


@pytest.mark.gating
def test_llm_default_off_does_not_raise() -> None:
    body = "---\ntier: S3\n---\n# H\n\nbody\n"
    # Default enable_llm=False: S3 must not raise.
    atoms = extract_atoms(
        page_slug="p",
        page_source_bytes=body.encode("utf-8"),
        chunks=[(None, body, 0)],
        tier="S3",
    )
    assert isinstance(atoms, list)


def test_composite_tier_most_restrictive() -> None:
    assert composite_tier("S1") == "S1"
    assert composite_tier("S1", "S2") == "S2"
    assert composite_tier("S2", "S3", "S1") == "S3"
    assert composite_tier("S3", "S3") == "S3"
    with pytest.raises(ValueError):
        composite_tier()


@pytest.mark.gating
def test_retier_page_cascades_to_atoms_and_entities(tmp_path: Path) -> None:
    db_path = tmp_path / "atoms.db"
    conn = atomsdb.connect(db_path)
    try:
        now = datetime.now(timezone.utc).isoformat()
        # Two atoms, both on page "p", labelled ENTITY, both linked to one entity.
        a1 = Atom(None, "p", None, 10, 30, "ENTITY", 0.9, "S2", now)
        a2 = Atom(None, "p", None, 40, 60, "ENTITY", 0.9, "S2", now)
        ids = persist_atoms(conn, [a1, a2])

        conn.execute(
            "INSERT INTO entities(canonical_label, aliases_json, tier, created_at) "
            "VALUES (?,?,?,?)",
            ("Wonderland Capital", "[]", "S2", now),
        )
        eid = conn.execute("SELECT entity_id FROM entities").fetchone()["entity_id"]
        for aid in ids:
            conn.execute(
                "INSERT INTO atom_entity(atom_id, entity_id, confidence) VALUES (?,?,?)",
                (aid, eid, 0.9),
            )
        conn.commit()

        summary = retier_page(conn, "p", "S3")
        assert summary == {"atoms_updated": 2, "entities_updated": 1}

        atom_tiers = [r["tier"] for r in conn.execute(
            "SELECT tier FROM atoms WHERE page_slug=?", ("p",)
        ).fetchall()]
        assert atom_tiers == ["S3", "S3"]

        ent_tier = conn.execute(
            "SELECT tier FROM entities WHERE entity_id=?", (eid,),
        ).fetchone()["tier"]
        assert ent_tier == "S3"
    finally:
        conn.close()
