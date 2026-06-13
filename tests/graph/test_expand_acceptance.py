"""P4 acceptance + tier-integrity gating.

The acceptance query: tokens that appear ONLY in Alice's body text. The
Wonderland and Acme pages contain Alice's slug in frontmatter (so they
appear in the graph), but BM25 + vector cannot find them from the query
because they don't share Alice-body vocabulary. With graph expansion ON,
the engine walks Alice -> Wonderland and Alice -> Acme via the typed
frontmatter edges and surfaces both pages alongside Alice in the result.

The composite-tier case: an S3 page links to an S1 page; every emitted
edge carries `tier = MAX(S3, S1) = S3`, so an S3-tier query that joins
through the graph does not leak S1 rows into the answer path.
"""

from __future__ import annotations

import re
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.memory.atoms import db as atomsdb  # noqa: F401  (parity import; not used)
from src.memory.graph import db as graphdb
from src.memory.graph.extractor import extract_edges, persist_edges
from src.retrieval import db as retdb
from src.retrieval.embedder import OllamaEmbedder
from src.retrieval.engine import retrieve
from src.retrieval.index import ingest_vault


def _ollama_or_skip() -> OllamaEmbedder:
    import httpx
    try:
        with httpx.Client(timeout=2.0) as c:
            r = c.get("http://127.0.0.1:11434/api/tags")
            r.raise_for_status()
            names = [m["name"] for m in r.json().get("models", [])]
    except Exception as e:
        pytest.skip(f"Ollama not reachable: {e}")
    if not any(n.startswith("nomic-embed-text") for n in names):
        pytest.skip(f"nomic-embed-text not pulled; got models={names}")
    return OllamaEmbedder()


SYNTHETIC_PUBLIC_VAULT = Path(__file__).resolve().parents[1] / "retrieval" / "synthetic_public_vault"


def _write_page(vault: Path, rel: str, body: str) -> Path:
    p = vault / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(body.encode("utf-8"))
    return p


def _copy_public_vault(vault: Path) -> int:
    """Copy the 20-page synthetic_public_vault into `vault` flat. Returns
    the count of pages copied."""
    count = 0
    for src in SYNTHETIC_PUBLIC_VAULT.glob("*.md"):
        shutil.copy2(src, vault / src.name)
        count += 1
    return count


def _build_synthetic_corpus(vault: Path, tier: str = "S1") -> dict[str, Path]:
    """Alice + Wonderland + Acme. Acceptance query tokens
    ('hybrid retrieval engines reranking') appear ONLY in Alice's body.
    Wonderland and Acme reference Alice via frontmatter edges only; their
    body vocabulary is distinct.
    """
    pages = {}
    pages["people/alice-chen"] = _write_page(
        vault, "people/alice-chen.md",
        f"---\n"
        f"tier: {tier}\n"
        f"name: Alice Chen\n"
        f"---\n"
        f"# Alice Chen\n\n"
        f"Alice's research focuses on hybrid retrieval engines. She\n"
        f"publishes on cross-encoder reranking and reciprocal rank fusion.\n"
    )
    pages["companies/wonderland-capital-private"] = _write_page(
        vault, "companies/wonderland-capital-private.md",
        f"---\n"
        f"tier: {tier}\n"
        f"founded:\n"
        f"  - people/alice-chen\n"
        f"---\n"
        f"# Wonderland Capital Private\n\n"
        f"Mid-cap industrials investment firm. Maintains coverage on public\n"
        f"US equities and small caps. Filed annual ADV brochure with SEC.\n"
    )
    pages["companies/acme-corp"] = _write_page(
        vault, "companies/acme-corp.md",
        f"---\n"
        f"tier: {tier}\n"
        f"audience:\n"
        f"  - people/alice-chen\n"
        f"---\n"
        f"# Acme Corp\n\n"
        f"Acme Corp manufactures industrial components. Quarterly earnings\n"
        f"are filed with the SEC on Form 10-Q.\n"
    )
    return pages


def _build_graph(vault: Path, retrieval_db: Path, graph_db: Path,
                 page_tier_override: dict[str, str] | None = None) -> None:
    """Extract edges from every page in the vault and persist."""
    retconn = retdb.connect(retrieval_db)
    try:
        page_tiers = {}
        for row in retconn.execute("SELECT page_slug, tier FROM pages").fetchall():
            page_tiers[row["page_slug"]] = row["tier"]
        if page_tier_override:
            page_tiers.update(page_tier_override)

        gconn = graphdb.connect(graph_db)
        try:
            for slug, tier in page_tiers.items():
                page_path = next((p for p in vault.rglob("*.md")
                                  if p.stem == slug.split("/")[-1]
                                  and p.parent.name == slug.split("/")[0]),
                                 None)
                if page_path is None:
                    continue
                source_text = page_path.read_bytes().decode("utf-8")
                edges = extract_edges(slug, tier, source_text, page_tiers)
                persist_edges(gconn, edges)
        finally:
            gconn.close()
    finally:
        retconn.close()


@pytest.mark.gating
def test_alice_query_surfaces_wonderland_acme_via_graph(tmp_path: Path) -> None:
    embedder = _ollama_or_skip()
    vault = tmp_path / "vault"
    vault.mkdir()
    pubcount = _copy_public_vault(vault)
    assert pubcount >= 18, f"expected the 20-page public vault, got {pubcount}"
    _build_synthetic_corpus(vault, tier="S1")
    db = tmp_path / "retrieval.db"
    graph_db = tmp_path / "graph.db"

    ingest_vault(vault, db_path=db, embedder=embedder)
    _build_graph(vault, db, graph_db)

    # Verify: Wonderland and Acme pages contain ZERO mentions of "hybrid" / "retrieval" / "reranking".
    won = (vault / "companies" / "wonderland-capital-private.md").read_text(encoding="utf-8")
    acme = (vault / "companies" / "acme-corp.md").read_text(encoding="utf-8")
    for forbidden in ("hybrid", "retrieval", "reranking"):
        assert forbidden not in won.lower()
        assert forbidden not in acme.lower()

    query = "hybrid retrieval engines reranking"

    no_graph = retrieve(
        query, tier="S1", k=10, db_path=db, embedder=embedder,
        graph_db_path=graph_db, enable_graph=False,
    )
    no_graph_pages = [c.page_slug for c in no_graph]
    assert "people/alice-chen" in no_graph_pages, no_graph_pages
    assert "companies/wonderland-capital-private" not in no_graph_pages, no_graph_pages
    assert "companies/acme-corp" not in no_graph_pages, no_graph_pages

    with_graph = retrieve(
        query, tier="S1", k=10, db_path=db, embedder=embedder,
        graph_db_path=graph_db, enable_graph=True,
    )
    with_graph_pages = {c.page_slug for c in with_graph}
    assert "people/alice-chen" in with_graph_pages
    assert "companies/wonderland-capital-private" in with_graph_pages, with_graph_pages
    assert "companies/acme-corp" in with_graph_pages, with_graph_pages


@pytest.mark.gating
def test_composite_tier_no_s1_leak_into_s3_answer(tmp_path: Path) -> None:
    """S3 memo links to S1 public pages. Every edge composes to S3 at the
    extractor. An S3 query joining through the graph must return zero S1
    chunks — the composite-tier rule is the structural defense."""
    vault = tmp_path / "vault"
    vault.mkdir()

    # Public S1 pages.
    _write_page(vault, "companies/wonderland-capital.md",
                "---\ntier: S1\n---\n# Wonderland Capital\n\n"
                "Mid-cap industrials investment firm.\n")
    _write_page(vault, "companies/acme-corp.md",
                "---\ntier: S1\n---\n# Acme Corp\n\n"
                "Industrial components manufacturer.\n")

    # S3 confidential memo links both S1 pages.
    _write_page(vault, "memos/2026-q3-deal-review.md",
                "---\n"
                "tier: S3\n"
                "company: companies/wonderland-capital\n"
                "related: companies/acme-corp\n"
                "---\n"
                "# Q3 Deal Review (CONFIDENTIAL)\n\n"
                "Wonderland Capital is preparing to acquire Acme Corp at\n"
                "a synthetic deal valuation of nine hundred million dollars.\n")

    db = tmp_path / "retrieval.db"
    graph_db = tmp_path / "graph.db"
    ingest_vault(vault, db_path=db)
    _build_graph(vault, db, graph_db)

    # Inspect persisted edges: every edge from the S3 memo carries S3.
    gconn = graphdb.connect(graph_db)
    try:
        rows = gconn.execute(
            "SELECT src_page, dst_page, edge_type, tier FROM edges "
            "WHERE src_page=?",
            ("memos/2026-q3-deal-review",),
        ).fetchall()
        assert rows, "expected edges out of the S3 memo"
        for r in rows:
            assert r["tier"] == "S3", (
                f"edge {r['src_page']} -> {r['dst_page']} ({r['edge_type']}) "
                f"should be S3 composite, got {r['tier']}"
            )
    finally:
        gconn.close()

    # S1 query with graph on: only the S1 pages surface, S3 memo cannot leak.
    s1_results = retrieve(
        "Wonderland Capital", tier="S1", k=10, db_path=db,
        graph_db_path=graph_db, enable_graph=True,
    )
    for c in s1_results:
        assert c.tier == "S1"
    assert any(c.page_slug == "companies/wonderland-capital" for c in s1_results)

    # S3 query with graph on: only the S3 memo, never the S1 children
    # via the answer-path retrieval (graph track gated to tier='S3' only).
    s3_results = retrieve(
        "Wonderland Capital acquisition", tier="S3", k=10, db_path=db,
        graph_db_path=graph_db, enable_graph=True,
    )
    for c in s3_results:
        assert c.tier == "S3", (
            f"S3 query returned non-S3 row: {c.page_slug} tier={c.tier}"
        )
