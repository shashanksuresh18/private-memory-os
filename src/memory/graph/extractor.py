"""Deterministic edge extractor.

Ports the regex shapes from gbrain's `src/core/link-extraction.ts` and the
frontmatter map. 100% local-deterministic. NO LLM in the extraction path.
NO network I/O. NO outside-loopback socket.

Composite-tier rule (CLAUDE.md locked invariant): every edge carries
`MAX(tier_src, tier_dst)` — most-restrictive of its endpoints.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable, List, Sequence, Tuple

EXTRACTOR_VERSION = "p4-port-v1"

# Directory whitelist mirrors gbrain DIR_PATTERN, scoped to the
# gbrain-base vault layout we use.
DIR_PATTERN = r"(?:people|companies|meetings|memos|concepts|inbox)"

# Markdown entity ref: [Name](path)
_ENTITY_REF_RE = re.compile(
    rf"\[([^\]]+)\]\((?:\.\.\/)*({DIR_PATTERN}\/[^)\s]+?)(?:\.md)?\)"
)

# Obsidian wikilink: [[path]] or [[path|Display]]
_WIKILINK_RE = re.compile(
    rf"\[\[({DIR_PATTERN}\/[^|\]#]+?)(?:#[^|\]]*?)?(?:\|([^\]]+?))?\]\]"
)
_WORKS_AT_RE = re.compile(
    r"\b(?:at|reports?\s+to|managing\s+partner|senior\s+analyst|ceo|cto|cfo|partner)\b",
    re.IGNORECASE,
)
_INVESTED_IN_RE = re.compile(
    r"\b(?:portfolio(?:\s+company)?\s+of|portfolio\s+support|series\s+[abc]\s+lead|investor|invested)\b",
    re.IGNORECASE,
)
_FOUNDED_RE = re.compile(r"\b(?:co-?founder|founder|founded)\b", re.IGNORECASE)

# Minimal YAML frontmatter parser (handles the shape we emit ourselves).
_FRONTMATTER_BLOCK_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
# Match a kv line as a SINGLE-LINE pattern (no multi-line backtracking).
_KV_WITH_VALUE_RE = re.compile(r"^(\w+)\s*:\s*(\S.*?)\s*$")
_KV_EMPTY_RE = re.compile(r"^(\w+)\s*:\s*$")
_LIST_LINE_RE = re.compile(r"^\s*-\s+(.+?)\s*$")


@dataclass(frozen=True)
class FrontmatterMap:
    """One row of FRONTMATTER_LINK_MAP. `fields` are the frontmatter keys
    we read; `edge_type` is the typed edge we emit when those keys point
    at directory-scoped slugs.
    """

    fields: Tuple[str, ...]
    edge_type: str
    dir_hint: str  # 'people' | 'companies' | 'meetings' | ''


# Subset of gbrain's FRONTMATTER_LINK_MAP that fires on our gbrain-base
# vault. Ordered for deterministic emission.
FRONTMATTER_LINK_MAP: List[FrontmatterMap] = [
    FrontmatterMap(("attendees",), "attended", "people"),
    FrontmatterMap(("company", "employer"), "works_at", "companies"),
    FrontmatterMap(("audience", "for"), "audience", "people"),
    FrontmatterMap(("related", "see_also"), "related_to", ""),
    FrontmatterMap(("invested_in", "portfolio"), "invested_in", "companies"),
    FrontmatterMap(("founded", "founder_of"), "founded", "companies"),
]


@dataclass(frozen=True)
class Edge:
    src_page: str
    dst_page: str
    edge_type: str
    confidence: float
    tier: str
    source_kind: str  # 'frontmatter' | 'wikilink' | 'markdown_link'


_TIER_ORDER = {"S1": 1, "S2": 2, "S3": 3}
_VALID_TIERS = set(_TIER_ORDER.keys())


def edge_tier(tier_src: str, tier_dst: str) -> str:
    """Most-restrictive composite. S3 > S2 > S1."""
    if tier_src not in _VALID_TIERS:
        raise ValueError(f"unknown tier_src {tier_src!r}")
    if tier_dst not in _VALID_TIERS:
        raise ValueError(f"unknown tier_dst {tier_dst!r}")
    return tier_src if _TIER_ORDER[tier_src] >= _TIER_ORDER[tier_dst] else tier_dst


def _parse_frontmatter(source_text: str) -> dict[str, list[str]]:
    """Tiny YAML reader for our page shape. Recognizes scalar values and
    `- item` bullet lists. Single-pass, line-by-line.
    """
    out: dict[str, list[str]] = {}
    m = _FRONTMATTER_BLOCK_RE.match(source_text)
    if not m:
        return out
    current_key: str | None = None
    for line in m.group(1).splitlines():
        empty_kv = _KV_EMPTY_RE.match(line)
        if empty_kv:
            current_key = empty_kv.group(1).strip()
            out.setdefault(current_key, [])
            continue
        kv = _KV_WITH_VALUE_RE.match(line)
        if kv:
            key = kv.group(1).strip()
            value = kv.group(2).strip().strip("'\"")
            out[key] = [value]
            current_key = None
            continue
        bullet = _LIST_LINE_RE.match(line)
        if bullet and current_key is not None:
            v = bullet.group(1).strip().strip("'\"")
            if v:
                out[current_key].append(v)
            continue
        # Anything else (blank line, prose) clears the open list context.
        current_key = None
    return out


def _is_slug(value: str) -> bool:
    """Lightweight check: `dir/something` shape."""
    return "/" in value and not value.startswith(("http://", "https://", "/"))


def _maybe_prefix_dir(value: str, dir_hint: str) -> str | None:
    """Frontmatter values may be bare names (`Alice`) or already-qualified
    slugs (`people/alice`). Bare names with a dir_hint get coerced.
    """
    if _is_slug(value):
        # Strip optional .md and any leading '../' fragments.
        clean = value.strip()
        if clean.endswith(".md"):
            clean = clean[:-3]
        return clean
    if not dir_hint:
        return None
    # Slugify the bare name conservatively: lowercase, non-alphanum -> '-'.
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not slug:
        return None
    return f"{dir_hint}/{slug}"


def extract_frontmatter_edges(source_text: str) -> List[Tuple[str, str, str, float]]:
    """Return `(dst_slug, edge_type, source_kind, confidence)` tuples
    extracted from the page frontmatter. Caller supplies src + tiers.
    """
    fm = _parse_frontmatter(source_text)
    out: List[Tuple[str, str, str, float]] = []
    for row in FRONTMATTER_LINK_MAP:
        for field in row.fields:
            values = fm.get(field, [])
            for v in values:
                dst = _maybe_prefix_dir(v, row.dir_hint)
                if dst is None:
                    continue
                out.append((dst, row.edge_type, "frontmatter", 0.97))
    return out


def extract_edges_from_text(body_text: str) -> List[Tuple[str, str, str, float]]:
    """Return `(dst_slug, edge_type, source_kind, confidence)` tuples
    extracted from the markdown body (wikilinks + markdown entity refs).
    `body_text` should be the page MINUS the frontmatter block.
    """
    out: List[Tuple[str, str, str, float]] = []
    for m in _ENTITY_REF_RE.finditer(body_text):
        dst = m.group(2).strip()
        if dst.endswith(".md"):
            dst = dst[:-3]
        edge_type = _infer_link_edge_type(body_text, m.start(), m.end(), dst)
        confidence = 0.95 if edge_type != "mentions" else 0.92
        out.append((dst, edge_type, "markdown_link", confidence))
    for m in _WIKILINK_RE.finditer(body_text):
        dst = m.group(1).strip()
        if dst.endswith(".md"):
            dst = dst[:-3]
        edge_type = _infer_link_edge_type(body_text, m.start(), m.end(), dst)
        out.append((dst, edge_type, "wikilink", 0.97))
    return out


def _infer_link_edge_type(body_text: str, start: int, end: int, dst: str) -> str:
    """Infer a CRM-style edge type from local prose around a markdown link.

    This is deliberately small and deterministic: it only upgrades links when
    nearby text contains unambiguous relationship phrases; otherwise the link
    stays a generic mention.
    """
    prefix = body_text[max(0, start - 64):start]
    window = body_text[max(0, start - 96):min(len(body_text), end + 96)]
    if dst.startswith("companies/"):
        if re.search(r"(?:portfolio(?:\s+company)?\s+of|invested\s+in|investor\s+in)\s*$", prefix, re.IGNORECASE):
            return "invested_in"
        if _FOUNDED_RE.search(prefix):
            return "founded"
        if _WORKS_AT_RE.search(window):
            return "works_at"
        if _INVESTED_IN_RE.search(window):
            return "invested_in"
    return "mentions"


def extract_edges(
    src_page: str,
    src_tier: str,
    source_text: str,
    page_tiers: dict[str, str],
) -> List[Edge]:
    """Drive both extractors over one page. `page_tiers` is a precomputed
    `slug -> tier` map for every page in the vault; unknown destinations
    fall back to S3 (fail-closed)."""
    if src_tier not in _VALID_TIERS:
        raise ValueError(f"unknown src_tier {src_tier!r}")
    body_text = source_text
    m = _FRONTMATTER_BLOCK_RE.match(source_text)
    if m:
        body_text = source_text[m.end():]

    candidates: List[Tuple[str, str, str, float]] = []
    candidates.extend(extract_frontmatter_edges(source_text))
    candidates.extend(extract_edges_from_text(body_text))

    edges: List[Edge] = []
    seen: set[Tuple[str, str, str]] = set()
    for dst, edge_type, source_kind, confidence in candidates:
        key = (src_page, dst, edge_type)
        if key in seen:
            continue
        seen.add(key)
        dst_tier = page_tiers.get(dst, "S3")
        edges.append(Edge(
            src_page=src_page,
            dst_page=dst,
            edge_type=edge_type,
            confidence=confidence,
            tier=edge_tier(src_tier, dst_tier),
            source_kind=source_kind,
        ))
    return edges


def persist_edges(conn: sqlite3.Connection, edges: Iterable[Edge]) -> int:
    """Insert edges with `INSERT OR IGNORE` to honor the (src,dst,type)
    uniqueness constraint. Returns count of rows actually written."""
    now = datetime.now(timezone.utc).isoformat()
    inserted = 0
    for e in edges:
        cur = conn.execute(
            "INSERT OR IGNORE INTO edges(src_page, dst_page, edge_type, "
            "confidence, tier, source_kind, created_at) VALUES (?,?,?,?,?,?,?)",
            (e.src_page, e.dst_page, e.edge_type, e.confidence,
             e.tier, e.source_kind, now),
        )
        if cur.rowcount > 0:
            inserted += 1
    conn.commit()
    return inserted
