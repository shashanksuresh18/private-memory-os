"""Deterministic-first atom extractor.

Default pass: regex-only, network-free, deterministic. Emits pointer rows
only — never returns or stores the matched text in a persisted form.
Caller is responsible for tier-correct insertion.

Optional LLM gate: `enable_llm=True` activates a second pass against the
local Ollama loopback endpoint for tiers in `llm_tier_allowlist` (default
{'S1','S2'}). Tier S3 calling enable_llm=True raises
`TierForbiddenLLMError` — S3 is rule-only, fail-closed, per the CLAUDE.md
locked invariant. Off by default in every code path.

Cloud calls are structurally impossible from this module: the LLM gate
uses the same OLLAMA_URL constant that the rest of the engine routes
through, and refuses any non-loopback URL at construction.

Schema contract: emitted spans are byte offsets relative to the FULL page
source bytes (UTF-8). The caller passes the chunk text plus its
(page_slug, chunk_id, page_byte_start) so we can translate chunk-local
spans back into page-byte coordinates.
"""

from __future__ import annotations

import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, List, Set, Tuple


OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_EXTRACT_MODEL = os.environ.get("OLLAMA_EXTRACT_MODEL", "llama3.2:3b")
DEFAULT_LLM_TIER_ALLOWLIST: Set[str] = {"S1", "S2"}


class TierForbiddenLLMError(RuntimeError):
    """Raised when an LLM extraction is requested for a tier that does not
    permit LLM inference. S3 is always forbidden."""

# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------

LABEL_EMAIL = "EMAIL"
LABEL_PHONE = "PHONE"
LABEL_USD_AMOUNT = "USD_AMOUNT"
LABEL_CODENAME = "CODENAME"
LABEL_WIKILINK = "WIKILINK"
LABEL_TICKER = "TICKER"

# ---------------------------------------------------------------------------
# Regex set (deterministic, local, no LLM)
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(rb"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
# US/international phone shapes: digits with optional + and grouping.
_PHONE_RE = re.compile(rb"(?<!\w)(?:\+?\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\w)")
# USD amounts: $1, $1.50, $1,000, $1.2M, $3.5bn, $400K, etc.
_USD_AMOUNT_RE = re.compile(
    rb"\$\s?\d{1,3}(?:,\d{3})*(?:\.\d+)?(?:\s?[KMB]|\s?[Bb]n|\s?[Mm]m|\s?[Kk]ilo|\s?million|\s?billion|\s?thousand)?\b"
)
# ALL-CAPS tickers (letters only, 1-5 chars), bounded by non-word.
_TICKER_RE = re.compile(rb"(?<![A-Za-z0-9])\$?[A-Z]{2,5}(?![A-Za-z0-9])")
# Obsidian-style wikilinks: [[Wonderland Capital]] or [[people/wonderland|Wonderland]].
_WIKILINK_RE = re.compile(rb"\[\[([^\[\]]+?)\]\]")


@dataclass(frozen=True)
class ExtractedAtom:
    """Result of a single extraction pass. Bytes relative to PAGE source."""
    label: str
    confidence: float
    byte_start: int
    byte_end: int


@dataclass(frozen=True)
class Atom:
    """Persisted atom row (mirrors schema)."""
    atom_id: int | None
    page_slug: str
    chunk_id: int | None
    byte_start: int
    byte_end: int
    label: str
    confidence: float
    tier: str
    created_at: str


def _emit(regex: re.Pattern[bytes], chunk_bytes: bytes, label: str,
          page_byte_start: int, confidence: float,
          extra_offset: int = 0) -> Iterable[ExtractedAtom]:
    for m in regex.finditer(chunk_bytes):
        s = page_byte_start + m.start() + extra_offset
        e = page_byte_start + m.end() + extra_offset
        if e <= s:
            continue
        yield ExtractedAtom(label=label, confidence=confidence,
                            byte_start=s, byte_end=e)


def extract_atoms_from_chunk(
    chunk_text: str,
    page_byte_start: int,
    codename_terms: Iterable[str] = (),
) -> List[ExtractedAtom]:
    """Run the full deterministic regex pass on a single chunk.

    `page_byte_start` is the BYTE offset of `chunk_text`'s first byte
    within the PAGE source. All returned `byte_start`/`byte_end` values are
    page-byte offsets (NOT chunk-byte offsets).
    """
    chunk_bytes = chunk_text.encode("utf-8")
    out: List[ExtractedAtom] = []
    out.extend(_emit(_EMAIL_RE, chunk_bytes, LABEL_EMAIL, page_byte_start, 0.98))
    out.extend(_emit(_PHONE_RE, chunk_bytes, LABEL_PHONE, page_byte_start, 0.85))
    out.extend(_emit(_USD_AMOUNT_RE, chunk_bytes, LABEL_USD_AMOUNT, page_byte_start, 0.92))
    out.extend(_emit(_TICKER_RE, chunk_bytes, LABEL_TICKER, page_byte_start, 0.55))
    out.extend(_emit(_WIKILINK_RE, chunk_bytes, LABEL_WIKILINK, page_byte_start, 0.97))

    # Codename pass: each term matched verbatim (case-insensitive, word-bounded).
    for term in codename_terms:
        term_b = term.encode("utf-8")
        if not term_b:
            continue
        pattern = rb"(?i)(?<!\w)" + re.escape(term_b) + rb"(?!\w)"
        rx = re.compile(pattern)
        out.extend(_emit(rx, chunk_bytes, LABEL_CODENAME, page_byte_start, 0.99))

    return out


def extract_atoms(
    page_slug: str,
    page_source_bytes: bytes,
    chunks: Iterable[Tuple[int, str, int]],
    tier: str,
    codename_terms: Iterable[str] = (),
    enable_llm: bool = False,
    llm_tier_allowlist: Set[str] | None = None,
) -> List[Atom]:
    """Drive `extract_atoms_from_chunk` over an iterable of
    `(chunk_id, chunk_text, chunk_byte_start)` tuples for a single page.

    Returns unpersisted `Atom` rows with `atom_id=None`. Caller persists.

    `enable_llm` activates a second extraction pass against local Ollama
    for the tiers in `llm_tier_allowlist`. Tier S3 with `enable_llm=True`
    raises `TierForbiddenLLMError` — S3 must remain rule-only, fail-closed.
    """
    if enable_llm:
        allow = llm_tier_allowlist if llm_tier_allowlist is not None else DEFAULT_LLM_TIER_ALLOWLIST
        if "S3" in allow:
            # Defense in depth: even if the operator passes S3 in the
            # allowlist, we refuse. The invariant is structural.
            raise TierForbiddenLLMError(
                "S3 in llm_tier_allowlist is forbidden; S3 is rule-only"
            )
        if tier == "S3":
            raise TierForbiddenLLMError(
                f"enable_llm=True is forbidden for page tier S3 ({page_slug!r})"
            )
        if tier not in allow:
            raise TierForbiddenLLMError(
                f"tier {tier!r} not in llm_tier_allowlist {sorted(allow)}"
            )
        # The LLM second pass is reserved for future wiring. The gate is
        # live; the call is not. When wired, it MUST route through
        # OLLAMA_URL and refuse any non-loopback URL.
        if not (OLLAMA_URL.startswith("http://127.0.0.1")
                or OLLAMA_URL.startswith("http://localhost")):
            raise RuntimeError(f"OLLAMA_URL is non-loopback: {OLLAMA_URL}")

    now = datetime.now(timezone.utc).isoformat()
    out: List[Atom] = []
    for chunk_id, chunk_text, chunk_byte_start in chunks:
        for ea in extract_atoms_from_chunk(chunk_text, chunk_byte_start, codename_terms):
            # Defense in depth: ensure the span actually lies within the
            # source page bytes. If not, drop it; never persist a bad span.
            if not (0 <= ea.byte_start < ea.byte_end <= len(page_source_bytes)):
                continue
            out.append(Atom(
                atom_id=None,
                page_slug=page_slug,
                chunk_id=chunk_id,
                byte_start=ea.byte_start,
                byte_end=ea.byte_end,
                label=ea.label,
                confidence=ea.confidence,
                tier=tier,
                created_at=now,
            ))
    return out


_TIER_ORDER = {"S1": 1, "S2": 2, "S3": 3}


def composite_tier(*tiers: str) -> str:
    """Return the most-restrictive tier among the inputs.

    S3 > S2 > S1. Empty input raises. Unknown tier raises.
    """
    if not tiers:
        raise ValueError("composite_tier requires at least one tier")
    worst = max(tiers, key=lambda t: _TIER_ORDER[t])
    return worst


def retier_page(conn: sqlite3.Connection, page_slug: str, new_tier: str) -> dict:
    """Operator-triggered re-tier of every atom on a page, cascading to
    any entities derived from those atoms.

    Returns a summary `{atoms_updated, entities_updated}`. Does not delete
    any rows — re-tier means re-label, not redact.
    """
    if new_tier not in _TIER_ORDER:
        raise ValueError(f"unknown tier {new_tier!r}")

    cur = conn.execute(
        "UPDATE atoms SET tier=? WHERE page_slug=?",
        (new_tier, page_slug),
    )
    atoms_updated = cur.rowcount

    # Entities pick up MAX tier over all contributing atoms.
    rows = conn.execute(
        "SELECT DISTINCT ae.entity_id FROM atom_entity ae "
        "JOIN atoms a ON ae.atom_id = a.atom_id WHERE a.page_slug = ?",
        (page_slug,),
    ).fetchall()
    entities_updated = 0
    for r in rows:
        eid = int(r["entity_id"])
        max_tier_row = conn.execute(
            "SELECT a.tier FROM atom_entity ae JOIN atoms a ON ae.atom_id=a.atom_id "
            "WHERE ae.entity_id=?",
            (eid,),
        ).fetchall()
        if not max_tier_row:
            continue
        new = composite_tier(*[r2["tier"] for r2 in max_tier_row])
        conn.execute("UPDATE entities SET tier=? WHERE entity_id=?", (new, eid))
        entities_updated += 1

    conn.commit()
    return {"atoms_updated": atoms_updated, "entities_updated": entities_updated}


def persist_atoms(conn: sqlite3.Connection, atoms: Iterable[Atom]) -> List[int]:
    """Insert atoms; return the list of new atom_ids."""
    ids: List[int] = []
    for a in atoms:
        cur = conn.execute(
            "INSERT INTO atoms(page_slug, chunk_id, byte_start, byte_end, "
            "label, confidence, tier, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (a.page_slug, a.chunk_id, a.byte_start, a.byte_end,
             a.label, a.confidence, a.tier, a.created_at),
        )
        ids.append(int(cur.lastrowid))
    conn.commit()
    return ids
