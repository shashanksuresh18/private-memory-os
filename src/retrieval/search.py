"""Hybrid retrieval: FTS5 BM25 + vector cosine, fused via RRF.

Tier gate: results are filtered to the requested tier set BEFORE fusion.
A query at tier S3 returns only rows where chunks.tier == 'S3'. (Locked
invariant — per-row tier on chunks; composite-tier only matters when
graph/atoms tracks join, which P0 does not.)
"""

from __future__ import annotations

import re
import sqlite3
from typing import List, Sequence, Tuple

from .embedder import Embedder, cosine, unpack_vector

RRF_K = 60


def _fts_query(query: str) -> str:
    # Sanitize query for FTS5: keep word chars only (drop apostrophes and
    # punctuation that FTS5 would treat as operators), OR-join terms.
    tokens = re.findall(r"\w+", query.lower())
    if not tokens:
        return '""'
    return " OR ".join(tokens)


def bm25_search(
    conn: sqlite3.Connection,
    query: str,
    tier: str,
    k: int = 50,
) -> List[Tuple[int, float]]:
    """Return list of (chunk_id, bm25_score) ordered by best score first.

    SQLite FTS5 `bm25()` returns SMALLER == better. We negate so callers can
    treat as a normal descending score.
    """
    sql = (
        "SELECT c.chunk_id, bm25(chunks_fts) AS score "
        "FROM chunks_fts "
        "JOIN chunks c ON c.chunk_id = chunks_fts.rowid "
        "WHERE chunks_fts MATCH ? AND c.tier = ? "
        "ORDER BY score ASC LIMIT ?"
    )
    rows = conn.execute(sql, (_fts_query(query), tier, k)).fetchall()
    return [(int(r["chunk_id"]), -float(r["score"])) for r in rows]


def vector_search(
    conn: sqlite3.Connection,
    query: str,
    tier: str,
    embedder: Embedder,
    k: int = 50,
) -> List[Tuple[int, float]]:
    """Return list of (chunk_id, cosine_score). BLOB fallback path —
    cosine computed in Python; correct on any platform.
    """
    qv = embedder.embed(query)
    rows = conn.execute(
        "SELECT v.chunk_id, v.embedding FROM vectors v "
        "JOIN chunks c ON c.chunk_id = v.chunk_id WHERE c.tier = ?",
        (tier,),
    ).fetchall()
    scored: List[Tuple[int, float]] = []
    for r in rows:
        vec = unpack_vector(r["embedding"])
        if len(vec) != len(qv):
            continue
        scored.append((int(r["chunk_id"]), cosine(qv, vec)))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:k]


def rrf_merge(
    ranked_lists: Sequence[Sequence[Tuple[int, float]]],
    k_const: int = RRF_K,
    top: int = 10,
) -> List[Tuple[int, float]]:
    """Reciprocal Rank Fusion. `ranked_lists[i]` is a list ordered best-first.

    Score per id = sum over lists of 1 / (k_const + rank), 1-indexed rank.
    """
    scores: dict[int, float] = {}
    for lst in ranked_lists:
        for rank, (cid, _s) in enumerate(lst, start=1):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k_const + rank)
    fused = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return fused[:top]
