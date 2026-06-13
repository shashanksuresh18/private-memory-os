"""Graph expansion — the 5th RRF track.

Given seed chunk_ids, expand to sibling chunk_ids reachable via 1-N
typed edges. Returns a ranked list ordered by edge confidence × proximity
decay. Tier-correct: every returned chunk is filtered to the requested
tier (the edge's composite tier acts as the gate).
"""

from __future__ import annotations

import sqlite3
from typing import List, Sequence, Tuple


def _page_slugs_for_chunks(retrieval_conn: sqlite3.Connection,
                           chunk_ids: Sequence[int]) -> dict[int, str]:
    if not chunk_ids:
        return {}
    placeholders = ",".join("?" * len(chunk_ids))
    rows = retrieval_conn.execute(
        f"SELECT c.chunk_id, p.page_slug FROM chunks c "
        f"JOIN pages p ON c.page_id = p.page_id "
        f"WHERE c.chunk_id IN ({placeholders})",
        list(chunk_ids),
    ).fetchall()
    return {int(r["chunk_id"]): r["page_slug"] for r in rows}


def _walk(graph_conn: sqlite3.Connection, seed_pages: Sequence[str],
          depth: int, direction: str, tier: str) -> List[Tuple[str, float]]:
    """BFS over the edges table. Returns `(page_slug, score)` ranked
    best-first. Score = confidence ** depth so deeper hops decay.

    Peers reachable via graph edges are ALWAYS emitted, even when they
    happen to also be in `seed_pages` (e.g. via a low-ranked vec hit). The
    graph track's job is to promote linked pages; suppressing them because
    a different track happened to surface them would defeat the purpose.
    `seed_pages` is excluded from emission only as the walk's origin — we
    don't yield "this page links to itself" trivial results.
    """
    if not seed_pages or depth < 1:
        return []
    if direction not in ("in", "out", "both"):
        raise ValueError(f"direction must be in/out/both, got {direction!r}")

    seeds_set: set[str] = set(seed_pages)
    emitted: set[str] = set()
    frontier_seen: set[str] = set(seed_pages)
    frontier: List[Tuple[str, float]] = [(p, 1.0) for p in seed_pages]
    out: List[Tuple[str, float]] = []

    for _ in range(depth):
        if not frontier:
            break
        next_frontier: List[Tuple[str, float]] = []
        for slug, score in frontier:
            rows = []
            if direction in ("out", "both"):
                rows.extend(graph_conn.execute(
                    "SELECT dst_page AS peer, confidence FROM edges "
                    "WHERE src_page=? AND tier=?",
                    (slug, tier),
                ).fetchall())
            if direction in ("in", "both"):
                rows.extend(graph_conn.execute(
                    "SELECT src_page AS peer, confidence FROM edges "
                    "WHERE dst_page=? AND tier=?",
                    (slug, tier),
                ).fetchall())
            for r in rows:
                peer = r["peer"]
                if peer == slug:
                    continue
                new_score = score * float(r["confidence"])
                if peer not in emitted:
                    emitted.add(peer)
                    out.append((peer, new_score))
                if peer not in frontier_seen:
                    frontier_seen.add(peer)
                    next_frontier.append((peer, new_score))
        frontier = next_frontier

    out.sort(key=lambda x: x[1], reverse=True)
    return out


def expand(retrieval_conn: sqlite3.Connection,
           graph_conn: sqlite3.Connection,
           chunk_ids: Sequence[int],
           tier: str,
           depth: int = 1,
           direction: str = "both",
           k: int = 50) -> List[Tuple[int, float]]:
    """Expand seed chunks via the typed-edge graph; return up to `k`
    chunk_ids ranked by edge score.

    Tier gating: only edges whose composite tier matches `tier` are
    traversed. Returned chunks are themselves filtered to `tier` in the
    retrieval DB.
    """
    if not chunk_ids:
        return []
    seed_slugs = list(set(_page_slugs_for_chunks(retrieval_conn, chunk_ids).values()))
    if not seed_slugs:
        return []
    page_scores = _walk(graph_conn, seed_slugs, depth=depth,
                        direction=direction, tier=tier)
    if not page_scores:
        return []
    slug_score = {slug: s for slug, s in page_scores}
    placeholders = ",".join("?" * len(slug_score))
    rows = retrieval_conn.execute(
        f"SELECT c.chunk_id, p.page_slug FROM chunks c "
        f"JOIN pages p ON c.page_id = p.page_id "
        f"WHERE p.page_slug IN ({placeholders}) AND c.tier = ?",
        list(slug_score.keys()) + [tier],
    ).fetchall()
    scored: List[Tuple[int, float]] = []
    for r in rows:
        scored.append((int(r["chunk_id"]), float(slug_score[r["page_slug"]])))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:k]
