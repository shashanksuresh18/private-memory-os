"""Eval runner — compares retrieval variants on a qrels file.

Variants
--------
- `bm25_only`   : FTS5 BM25 only.
- `vec_only`    : nomic-embed-text vector cosine only.
- `rrf`         : RRF over BM25 + vector (no reranker).
- `rrf_rerank`  : RRF top k_in then bge-reranker-base cross-encoder.

Metrics @ k = 10
----------------
- Recall@10  : |relevant_pages ∩ retrieved_pages[:10]| / |relevant_pages|
- MRR@10     : 1 / rank_of_first_relevant, 0 if none in top 10
- nDCG@10    : binary relevance, log2 discount, normalized by ideal DCG

The unit of relevance is `page_slug` (qrels annotate at the page level).
Chunk hits are mapped up to page hits before scoring; deduplication keeps
the first occurrence of each page in retrieved order.

JSON envelope
-------------
schema_version 1. Top level: {schema_version, qrels_path, vault_path,
db_path, embedder, k, k_in, variants: {<name>: {macro: {...}, per_query:
[...]}}}

Usage
-----
    python -m src.retrieval.eval \\
        --qrels tests/eval/qrels.jsonl \\
        --vault tests/retrieval/synthetic_public_vault \\
        --db src/memory/sqlite/eval.db \\
        --embedder ollama \\
        --variants bm25_only,vec_only,rrf,rrf_rerank
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

from . import db as dbmod
from .embedder import Embedder, HashEmbedder, OllamaEmbedder
from .engine import resolve
from .index import ingest_vault
from .reranker import (
    CrossEncoderReranker,
    DeterministicReranker,
    RerankCandidate,
    Reranker,
    rerank as rerank_helper,
)
from .search import bm25_search, rrf_merge, vector_search


# ---------------------------------------------------------------------------
# Variant runners — each returns the ranked page_slug list (deduped, top-k).
# ---------------------------------------------------------------------------

def _hydrate_pages(conn: sqlite3.Connection, chunk_ids: Sequence[int]) -> Dict[int, Tuple[str, str, int, int]]:
    if not chunk_ids:
        return {}
    placeholders = ",".join("?" * len(chunk_ids))
    rows = conn.execute(
        f"SELECT c.chunk_id, p.page_slug, p.page_path, c.chunk_start_byte, c.chunk_end_byte, c.text "
        f"FROM chunks c JOIN pages p ON c.page_id = p.page_id "
        f"WHERE c.chunk_id IN ({placeholders})",
        list(chunk_ids),
    ).fetchall()
    return {int(r["chunk_id"]): r for r in rows}


def _dedupe_to_pages(ordered_chunk_ids: Sequence[int],
                     conn: sqlite3.Connection, k: int) -> List[str]:
    hydrated = _hydrate_pages(conn, ordered_chunk_ids)
    seen: set[str] = set()
    pages: List[str] = []
    for cid in ordered_chunk_ids:
        row = hydrated.get(cid)
        if row is None:
            continue
        slug = row["page_slug"]
        if slug in seen:
            continue
        seen.add(slug)
        pages.append(slug)
        if len(pages) >= k:
            break
    return pages


def run_bm25_only(conn, query: str, tier: str, embedder, reranker,
                  k: int, k_in: int) -> List[str]:
    ranked = bm25_search(conn, query, tier, k=k_in)
    return _dedupe_to_pages([cid for cid, _ in ranked], conn, k)


def run_vec_only(conn, query: str, tier: str, embedder, reranker,
                 k: int, k_in: int) -> List[str]:
    ranked = vector_search(conn, query, tier, embedder, k=k_in)
    return _dedupe_to_pages([cid for cid, _ in ranked], conn, k)


def run_rrf(conn, query: str, tier: str, embedder, reranker,
            k: int, k_in: int) -> List[str]:
    bm = bm25_search(conn, query, tier, k=k_in)
    vc = vector_search(conn, query, tier, embedder, k=k_in)
    fused = rrf_merge([bm, vc], top=k_in)
    return _dedupe_to_pages([cid for cid, _ in fused], conn, k)


def run_rrf_rerank(conn, query: str, tier: str, embedder, reranker,
                   k: int, k_in: int) -> List[str]:
    bm = bm25_search(conn, query, tier, k=k_in)
    vc = vector_search(conn, query, tier, embedder, k=k_in)
    fused = rrf_merge([bm, vc], top=k_in)
    fused_ids = [cid for cid, _ in fused]
    hydrated = _hydrate_pages(conn, fused_ids)
    cands = [
        RerankCandidate(chunk_id=cid, text=hydrated[cid]["text"])
        for cid in fused_ids if cid in hydrated
    ]
    reranked = rerank_helper(reranker, query, cands, k_out=k_in)
    return _dedupe_to_pages([cid for cid, _ in reranked], conn, k)


VARIANT_FNS = {
    "bm25_only": run_bm25_only,
    "vec_only": run_vec_only,
    "rrf": run_rrf,
    "rrf_rerank": run_rrf_rerank,
}


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def recall_at_k(retrieved: Sequence[str], relevant: Sequence[str], k: int) -> float:
    rel = set(relevant)
    if not rel:
        return 0.0
    hit = sum(1 for s in retrieved[:k] if s in rel)
    return hit / len(rel)


def mrr_at_k(retrieved: Sequence[str], relevant: Sequence[str], k: int) -> float:
    rel = set(relevant)
    for i, s in enumerate(retrieved[:k], start=1):
        if s in rel:
            return 1.0 / i
    return 0.0


def ndcg_at_k(retrieved: Sequence[str], relevant: Sequence[str], k: int) -> float:
    rel = set(relevant)
    dcg = 0.0
    for i, s in enumerate(retrieved[:k], start=1):
        if s in rel:
            dcg += 1.0 / math.log2(i + 1)
    ideal_n = min(len(rel), k)
    if ideal_n == 0:
        return 0.0
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_n + 1))
    return dcg / idcg if idcg > 0 else 0.0


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

@dataclass
class QRel:
    qid: str
    query: str
    relevant: List[str]
    style: str | None = None
    tier: str | None = None


def load_qrels(path: Path) -> List[QRel]:
    out: List[QRel] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        d = json.loads(line)
        out.append(QRel(qid=d["qid"], query=d["query"],
                        relevant=list(d["relevant"]),
                        style=d.get("style"),
                        tier=d.get("tier")))
    return out


def _make_embedder(name: str) -> Embedder:
    if name == "hash":
        return HashEmbedder()
    if name == "ollama":
        return OllamaEmbedder()
    raise ValueError(f"unknown embedder {name!r}")


def _make_reranker(name: str) -> Reranker:
    if name == "deterministic":
        return DeterministicReranker()
    if name == "bge":
        return CrossEncoderReranker()
    raise ValueError(f"unknown reranker {name!r}")


def run_eval(qrels_path: Path, vault_path: Path, db_path: Path,
             embedder_name: str, reranker_name: str,
             variants: Sequence[str], tier: str, k: int, k_in: int,
             reingest: bool) -> dict:
    qrels = load_qrels(qrels_path)
    embedder = _make_embedder(embedder_name)
    reranker = _make_reranker(reranker_name) if "rrf_rerank" in variants else None

    if reingest:
        ingest_vault(vault_path, db_path=db_path, embedder=embedder)

    conn = dbmod.connect(db_path)
    try:
        result_variants: Dict[str, dict] = {}
        for vname in variants:
            fn = VARIANT_FNS[vname]
            per_query = []
            for qr in qrels:
                # Tier gate in search.py is an EXACT match, so each query must
                # run at its own tier. qrels that omit `tier` fall back to the
                # global `--tier` (preserves single-tier qrels behaviour).
                q_tier = qr.tier or tier
                pages = fn(conn, qr.query, q_tier, embedder, reranker, k=k, k_in=k_in)
                per_query.append({
                    "qid": qr.qid,
                    "query": qr.query,
                    "tier": q_tier,
                    "style": qr.style,
                    "relevant": qr.relevant,
                    "retrieved": pages,
                    "recall_at_10": recall_at_k(pages, qr.relevant, k),
                    "mrr_at_10": mrr_at_k(pages, qr.relevant, k),
                    "ndcg_at_10": ndcg_at_k(pages, qr.relevant, k),
                })
            n = len(per_query)
            macro = {
                "recall_at_10": sum(q["recall_at_10"] for q in per_query) / n,
                "mrr_at_10":    sum(q["mrr_at_10"]    for q in per_query) / n,
                "ndcg_at_10":   sum(q["ndcg_at_10"]   for q in per_query) / n,
            }
            result_variants[vname] = {"macro": macro, "per_query": per_query}

        return {
            "schema_version": 1,
            "qrels_path": str(qrels_path),
            "vault_path": str(vault_path),
            "db_path": str(db_path),
            "embedder": embedder_name,
            "reranker": reranker_name if reranker is not None else None,
            "tier": tier,
            "k": k,
            "k_in": k_in,
            "n_queries": len(qrels),
            "variants": result_variants,
        }
    finally:
        conn.close()


def _main(argv: List[str]) -> int:
    p = argparse.ArgumentParser(prog="src.retrieval.eval")
    p.add_argument("--qrels", required=True)
    p.add_argument("--vault", required=True)
    p.add_argument("--db", default="src/memory/sqlite/eval.db")
    p.add_argument("--embedder", choices=("hash", "ollama"), default="ollama")
    p.add_argument("--reranker", choices=("deterministic", "bge"), default="bge")
    p.add_argument("--variants", default="bm25_only,vec_only,rrf,rrf_rerank")
    p.add_argument("--tier", default="S1")
    p.add_argument("--k", type=int, default=10)
    p.add_argument("--k-in", type=int, default=50, dest="k_in")
    p.add_argument("--no-reingest", action="store_true")
    p.add_argument("--out", default="-")
    args = p.parse_args(argv)

    variants = [v.strip() for v in args.variants.split(",") if v.strip()]
    for v in variants:
        if v not in VARIANT_FNS:
            raise SystemExit(f"unknown variant {v!r}; choose from {sorted(VARIANT_FNS)}")

    result = run_eval(
        qrels_path=Path(args.qrels),
        vault_path=Path(args.vault),
        db_path=Path(args.db),
        embedder_name=args.embedder,
        reranker_name=args.reranker,
        variants=variants,
        tier=args.tier,
        k=args.k,
        k_in=args.k_in,
        reingest=not args.no_reingest,
    )
    body = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out == "-":
        print(body)
    else:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(body, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
