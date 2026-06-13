from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from src.api import server
from src.retrieval.auto_wiki import ExtractedConcept, concept_tier, run_auto_wiki
from src.retrieval.engine import Citation
from src.retrieval.index import ingest_vault


def _citation(tmp_path: Path, tier: str = "S1", text: str = "Acme files public reports.") -> Citation:
    vault = tmp_path / "vault"
    page = vault / "inbox" / "source.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(f"---\ntier: {tier}\n---\n# Source\n\n{text}\n", encoding="utf-8")
    raw = page.read_bytes()
    return Citation(
        chunk_id=1,
        page_slug="inbox/source",
        page_path=str(page),
        tier=tier,
        byte_start=0,
        byte_end=len(raw),
        line_start=1,
        line_end=5,
        score=1.0,
        text=text,
    )


def test_concept_created_after_query(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    page = vault / "inbox" / "edgar.md"
    page.parent.mkdir(parents=True)
    page.write_text(
        "---\ntier: S1\n---\n# EDGAR\n\nEDGAR public filing workflow uses accession numbers.\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "retrieval.db"
    ingest_vault(vault, db_path=db_path)

    def fake_extractor(texts: list[str]) -> list[ExtractedConcept]:
        assert "EDGAR public filing workflow" in texts[0]
        return [
            ExtractedConcept(
                name="EDGAR Public Filing Workflow",
                facts=["EDGAR filing pages use accession numbers."],
            )
        ]

    server.app.state.db_path = db_path
    server.app.state.vault_root = vault
    server.app.state.auto_wiki_inline = True
    server.app.state.auto_wiki_extractor = fake_extractor
    try:
        with TestClient(server.app) as client:
            res = client.post(
                "/retrieve",
                json={"query": "EDGAR public filing workflow", "tier": "S1", "k": 3},
            )
        assert res.status_code == 200
        assert res.json()["citations"]
    finally:
        for key in ("db_path", "vault_root", "auto_wiki_inline", "auto_wiki_extractor"):
            if hasattr(server.app.state, key):
                delattr(server.app.state, key)

    concept = vault / "concepts" / "edgar-public-filing-workflow.md"
    assert concept.exists()
    text = concept.read_text(encoding="utf-8")
    assert "tier: S1" in text
    assert "source: auto-wiki" in text
    assert "- EDGAR filing pages use accession numbers." in text
    assert f"- {page}" in text


def test_s3_concept_stays_local(tmp_path: Path) -> None:
    citation = _citation(
        tmp_path,
        tier="S3",
        text="Project Orchid internal memo remains local only.",
    )

    written = run_auto_wiki(
        [citation],
        extractor=lambda texts: [
            ExtractedConcept(
                name="Project Orchid",
                facts=["Project Orchid is sourced from an internal memo."],
            )
        ],
        updated="2026-06-05",
    )

    assert len(written) == 1
    text = written[0].read_text(encoding="utf-8")
    assert "tier: S3" in text
    assert "source: auto-wiki" in text
    assert "Project Orchid is sourced from an internal memo." in text


def test_manual_concept_not_overwritten(tmp_path: Path) -> None:
    citation = _citation(
        tmp_path,
        tier="S2",
        text="Acme sensitive note from Jane Doe at jane@example.com.",
    )
    manual = tmp_path / "vault" / "concepts" / "acme.md"
    manual.parent.mkdir(parents=True, exist_ok=True)
    original = "---\ntier: S2\nsource: manual\n---\n## Acme\nKeep this.\n"
    manual.write_text(original, encoding="utf-8")

    written = run_auto_wiki(
        [citation],
        extractor=lambda texts: [
            ExtractedConcept(
                name="Acme",
                facts=["Jane Doe emailed jane@example.com about Acme."],
            )
        ],
        updated="2026-06-05",
    )

    assert written == []
    assert manual.read_text(encoding="utf-8") == original


def test_s2_concept_is_scrubbed_before_extract_and_write(tmp_path: Path) -> None:
    citation = _citation(
        tmp_path,
        tier="S2",
        text="Jane Doe emailed jane@example.com about Acme at 555-123-4567.",
    )

    def fake_extractor(texts: list[str]) -> list[ExtractedConcept]:
        joined = "\n".join(texts)
        assert "jane@example.com" not in joined
        assert "555-123-4567" not in joined
        return [
            ExtractedConcept(
                name="Acme Sensitive Note",
                facts=["Jane Doe sent jane@example.com a note."],
            )
        ]

    written = run_auto_wiki(
        [citation],
        extractor=fake_extractor,
        updated="2026-06-05",
    )

    text = written[0].read_text(encoding="utf-8")
    assert "tier: S2" in text
    assert "Jane Doe" not in text
    assert "jane@example.com" not in text
    assert "[EMAIL]" in text


def test_existing_auto_wiki_concept_is_updated(tmp_path: Path) -> None:
    citation = _citation(tmp_path, tier="S1", text="Acme has a public filing.")
    existing = tmp_path / "vault" / "concepts" / "acme.md"
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_text(
        "---\ntier: S1\nsource: auto-wiki\nupdated: 2026-01-01\n---\nold\n",
        encoding="utf-8",
    )

    written = run_auto_wiki(
        [citation],
        extractor=lambda texts: [
            ExtractedConcept(name="Acme", facts=["Acme has a public filing."])
        ],
        updated="2026-06-05",
    )

    assert written == [existing]
    text = existing.read_text(encoding="utf-8")
    assert "updated: 2026-06-05" in text
    assert "Acme has a public filing." in text
    assert "old" not in text


def test_no_citations_creates_nothing(tmp_path: Path) -> None:
    written = run_auto_wiki(
        [],
        vault_root=tmp_path / "vault",
        extractor=lambda texts: [ExtractedConcept(name="Nope", facts=["Nope"])],
    )

    assert written == []
    assert not (tmp_path / "vault" / "concepts").exists()


def test_sources_are_limited_to_top_three(tmp_path: Path) -> None:
    citations = [
        _citation(tmp_path / f"case{i}", tier="S1", text=f"Concept source {i}.")
        for i in range(4)
    ]

    written = run_auto_wiki(
        citations,
        extractor=lambda texts: [
            ExtractedConcept(name="Concept Source", facts=["Top three only."])
        ],
    )

    text = written[0].read_text(encoding="utf-8")
    assert citations[0].page_path in text
    assert citations[1].page_path in text
    assert citations[2].page_path in text
    assert citations[3].page_path not in text


def test_concept_tier_uses_most_restrictive_citation(tmp_path: Path) -> None:
    assert concept_tier([
        _citation(tmp_path / "s1", tier="S1"),
        _citation(tmp_path / "s2", tier="S2"),
    ]) == "S2"
    assert concept_tier([
        _citation(tmp_path / "s1b", tier="S1"),
        _citation(tmp_path / "s3", tier="S3"),
    ]) == "S3"
