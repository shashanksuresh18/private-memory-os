"""Retrieval engine orchestrator. Public surface: `ingest` + `retrieve`.

CLI:
    python -m src.retrieval.engine ingest <vault_path> [--db <path>]
    python -m src.retrieval.engine search "<query>" --tier S1|S2|S3 [--k 5]
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List

from . import db as dbmod
from .embedder import Embedder, HashEmbedder
from .index import ingest_vault
from .reranker import (
    CrossEncoderReranker,
    DeterministicReranker,
    RerankCandidate,
    Reranker,
    rerank as rerank_candidates,
)
from .search import bm25_search, rrf_merge, vector_search

from src.memory.graph import db as graphdb
from src.memory.graph.expand import expand as graph_expand_fn

_VALID_TIERS = {"S1", "S2", "S3"}
DEFAULT_RRF_K_IN = 50
DEFAULT_GRAPH_PER_TIER = {"S1": True, "S2": False, "S3": False}
DEFAULT_GRAPH_DEPTH = 1
DEFAULT_GRAPH_K = 20


@dataclass
class Citation:
    chunk_id: int
    page_slug: str
    page_path: str
    tier: str
    byte_start: int
    byte_end: int
    line_start: int
    line_end: int
    score: float
    text: str


def resolve(page_path: str, byte_start: int, byte_end: int) -> str:
    """Reopen the source file and return the live byte slice as UTF-8.

    Stored ``page_path`` is repo-root-relative (see ``index.repo_relative_path``);
    anchor it to ``REPO_ROOT`` so reopen is cwd-independent. Absolute paths
    (outside-repo / legacy rows) are opened as-is.
    """
    p = Path(page_path)
    if not p.is_absolute():
        p = dbmod.REPO_ROOT / p
    raw = p.read_bytes()
    return raw[byte_start:byte_end].decode("utf-8")


def ingest(vault_path: str | Path, db_path: str | Path | None = None,
           embedder: Embedder | None = None) -> dict:
    return ingest_vault(vault_path, db_path=db_path, embedder=embedder)


def retrieve(query: str, tier: str, k: int = 10,
             db_path: str | Path | None = None,
             embedder: Embedder | None = None,
             reranker: Reranker | None = None,
             k_in: int = DEFAULT_RRF_K_IN,
             enable_graph: bool | None = None,
             graph_db_path: str | Path | None = None,
             graph_depth: int = DEFAULT_GRAPH_DEPTH) -> List[Citation]:
    """Hybrid retrieval pipeline:

        BM25 + vector + [optional graph] -> RRF fuse (top k_in)
                                         -> [optional] cross-encoder rerank
                                         -> top k -> source-span reopen via resolve()

    `enable_graph=None` defers to `DEFAULT_GRAPH_PER_TIER` (ON for S1, OFF
    for S2/S3). When ON, graph expansion uses the union of BM25 + vector
    top-results as seeds, walks the typed-edge graph at `tier`, and joins
    as a 3rd RRF track.
    """
    if tier not in _VALID_TIERS:
        raise ValueError(f"invalid tier {tier!r}; must be one of {_VALID_TIERS}")
    if embedder is None:
        embedder = HashEmbedder()
    if enable_graph is None:
        enable_graph = DEFAULT_GRAPH_PER_TIER[tier]
    conn = dbmod.connect(db_path)
    try:
        bm25 = bm25_search(conn, query, tier, k=k_in)
        vecs = vector_search(conn, query, tier, embedder, k=k_in)
        tracks = [bm25, vecs]

        if enable_graph:
            seeds = list({cid for cid, _ in bm25} | {cid for cid, _ in vecs})
            gconn = graphdb.connect(graph_db_path)
            try:
                graph_hits = graph_expand_fn(
                    retrieval_conn=conn,
                    graph_conn=gconn,
                    chunk_ids=seeds,
                    tier=tier,
                    depth=graph_depth,
                    direction="both",
                    k=DEFAULT_GRAPH_K,
                )
            finally:
                gconn.close()
            if graph_hits:
                tracks.append(graph_hits)

        fuse_top = k_in if reranker is not None else k
        fused = rrf_merge(tracks, top=fuse_top)
        if not fused:
            return []
        ids = [cid for cid, _ in fused]
        placeholders = ",".join("?" * len(ids))
        rows = conn.execute(
            f"SELECT c.chunk_id, c.chunk_start_byte, c.chunk_end_byte, "
            f"c.line_start, c.line_end, c.tier, c.text, "
            f"p.page_slug, p.page_path "
            f"FROM chunks c JOIN pages p ON c.page_id = p.page_id "
            f"WHERE c.chunk_id IN ({placeholders})",
            ids,
        ).fetchall()
        row_by_id = {int(r["chunk_id"]): r for r in rows}
        score_by_id = dict(fused)

        if reranker is not None:
            cands = [
                RerankCandidate(chunk_id=int(r["chunk_id"]), text=r["text"])
                for cid in ids
                for r in [row_by_id.get(cid)]
                if r is not None
            ]
            reranked = rerank_candidates(reranker, query, cands, k_out=k)
            ids = [cid for cid, _ in reranked]
            score_by_id = dict(reranked)

        out: List[Citation] = []
        for cid in ids:
            r = row_by_id.get(cid)
            if r is None:
                continue
            out.append(Citation(
                chunk_id=cid,
                page_slug=r["page_slug"],
                page_path=r["page_path"],
                tier=r["tier"],
                byte_start=int(r["chunk_start_byte"]),
                byte_end=int(r["chunk_end_byte"]),
                line_start=int(r["line_start"]),
                line_end=int(r["line_end"]),
                score=float(score_by_id[cid]),
                text=resolve(r["page_path"], int(r["chunk_start_byte"]), int(r["chunk_end_byte"])),
            ))
        return out
    finally:
        conn.close()


def _build_reranker(name: str) -> Reranker | None:
    if name == "none":
        return None
    if name == "deterministic":
        return DeterministicReranker()
    if name == "bge":
        return CrossEncoderReranker()
    raise ValueError(f"unknown reranker {name!r}")


def _main(argv: List[str]) -> int:
    p = argparse.ArgumentParser(prog="src.retrieval.engine")
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("ingest")
    pi.add_argument("vault_path")
    pi.add_argument("--db", default=None)

    ps = sub.add_parser("search")
    ps.add_argument("query")
    ps.add_argument("--tier", required=True, choices=sorted(_VALID_TIERS))
    ps.add_argument("--k", type=int, default=10)
    ps.add_argument("--k-in", type=int, default=DEFAULT_RRF_K_IN, dest="k_in")
    ps.add_argument("--rerank", choices=("none", "deterministic", "bge"), default="none")
    ps.add_argument("--db", default=None)
    ps.add_argument("--graph-db", default=None, dest="graph_db")
    ps.add_argument("--enable-graph", choices=("auto", "on", "off"), default="auto",
                    dest="enable_graph")
    ps.add_argument("--graph-depth", type=int, default=DEFAULT_GRAPH_DEPTH, dest="graph_depth")

    args = p.parse_args(argv)
    if args.cmd == "ingest":
        stats = ingest(args.vault_path, db_path=args.db)
        print(json.dumps(stats))
        return 0
    if args.cmd == "search":
        eg = None if args.enable_graph == "auto" else (args.enable_graph == "on")
        results = retrieve(
            args.query, tier=args.tier, k=args.k, db_path=args.db,
            reranker=_build_reranker(args.rerank), k_in=args.k_in,
            enable_graph=eg, graph_db_path=args.graph_db,
            graph_depth=args.graph_depth,
        )
        print(json.dumps([asdict(c) for c in results], ensure_ascii=False, indent=2))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
