"""Edge extractor invariants.

- Wikilink + markdown-link parsing produces deduped (src, dst, type) triples.
- Frontmatter typed-field map fires only for known fields.
- composite_tier rule: MAX(S3, S1) == S3.
- Edges inherit the most-restrictive composite at extraction time.
"""

from __future__ import annotations

import pytest

from src.memory.graph.extractor import (
    Edge,
    edge_tier,
    extract_edges,
    extract_edges_from_text,
    extract_frontmatter_edges,
)


def test_composite_tier_most_restrictive() -> None:
    assert edge_tier("S1", "S1") == "S1"
    assert edge_tier("S1", "S2") == "S2"
    assert edge_tier("S2", "S1") == "S2"
    assert edge_tier("S3", "S1") == "S3"
    assert edge_tier("S1", "S3") == "S3"
    assert edge_tier("S2", "S3") == "S3"
    with pytest.raises(ValueError):
        edge_tier("S1", "S5")


def test_extract_wikilinks_and_markdown_links() -> None:
    body = (
        "Alice met [[people/wonderland-capital]] last week. "
        "See the [Acme Q3 release](companies/acme-corp.md) for context. "
        "Cross-team [[meetings/2026-04-03|Q2 review]].\n"
    )
    edges = extract_edges_from_text(body)
    dst_types = {(d, t) for d, t, _kind, _conf in edges}
    assert ("people/wonderland-capital", "mentions") in dst_types
    assert ("companies/acme-corp", "mentions") in dst_types
    assert ("meetings/2026-04-03", "mentions") in dst_types


def test_frontmatter_typed_fields_fire() -> None:
    source = (
        "---\n"
        "tier: S3\n"
        "attendees:\n"
        "  - people/alice-chen\n"
        "  - Bob Garcia\n"
        "company: companies/wonderland-capital\n"
        "related: companies/acme-corp\n"
        "---\n"
        "# Body\n\nFiller text.\n"
    )
    edges = extract_frontmatter_edges(source)
    # tuple shape: (dst, edge_type, source_kind, confidence)
    by_type: dict[str, list[str]] = {}
    for dst, etype, _k, _c in edges:
        by_type.setdefault(etype, []).append(dst)
    assert "attended" in by_type
    assert "people/alice-chen" in by_type["attended"]
    # Bare-name fallback slugifies under the dir_hint.
    assert any(d.startswith("people/") for d in by_type["attended"])
    assert "works_at" in by_type
    assert "companies/wonderland-capital" in by_type["works_at"]
    assert "related_to" in by_type
    assert "companies/acme-corp" in by_type["related_to"]


def test_extract_edges_carries_composite_tier() -> None:
    source = (
        "---\n"
        "tier: S3\n"
        "company: companies/wonderland-capital\n"
        "---\n"
        "# Memo\n\nSee [[companies/acme-corp|Acme]].\n"
    )
    page_tiers = {
        "companies/wonderland-capital": "S1",
        "companies/acme-corp": "S1",
    }
    edges = extract_edges(
        src_page="memos/2026-q3-deal-review",
        src_tier="S3",
        source_text=source,
        page_tiers=page_tiers,
    )
    assert edges, "expected at least one edge"
    for e in edges:
        # S3 (src) joined with S1 (dst) -> S3 composite.
        assert e.tier == "S3", f"edge {e} should carry S3 composite"


def test_extract_edges_dedupes_repeats() -> None:
    source = (
        "---\ntier: S1\n---\n"
        "# Doc\n\n"
        "First mention [[people/alice-chen]]. Then again [[people/alice-chen|Alice]]."
    )
    edges = extract_edges(
        src_page="memos/dup", src_tier="S1", source_text=source,
        page_tiers={"people/alice-chen": "S1"},
    )
    keys = {(e.src_page, e.dst_page, e.edge_type) for e in edges}
    assert len(keys) == len(edges)
