"""Typed-edge graph track (P4).

Deterministic regex + frontmatter port of gbrain's link-extraction. ZERO LLM
calls in the extraction path. Edges carry MAX(tier_src, tier_dst) — most
restrictive composite — per CLAUDE.md locked invariant.

The graph is the 5th RRF track in `src/retrieval/engine.py`. Default ON for
S1, opt-in for S2/S3.
"""

from .extractor import (
    EXTRACTOR_VERSION,
    Edge,
    edge_tier,
    extract_edges,
    extract_edges_from_text,
    extract_frontmatter_edges,
)
from .expand import expand

__all__ = [
    "EXTRACTOR_VERSION",
    "Edge",
    "edge_tier",
    "extract_edges",
    "extract_edges_from_text",
    "extract_frontmatter_edges",
    "expand",
]
