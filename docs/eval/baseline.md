# Retrieval Eval — Baseline (2026-05-29, hardened qrels)

First committed baseline for the Sovereign Citadel retrieval engine.
Subsequent changes (P3 atoms, P4 graph track, reranker swaps) must beat or
match this baseline. Regressions of more than 5pp on Recall@10 or MRR@10
are non-mergeable per the P2 gating rule.

**Revision history**

- v1 (this file) — 2026-05-29 — first commit. Hardened qrels (14 queries
  rewritten as strict paraphrases stripping target-page vocabulary).
- v0 (superseded, see git history) — 2026-05-29 — initial qrels;
  metrics saturated because exact-keyword queries reused source phrasing.

## Run config

| Field        | Value |
|---           |---|
| Date         | 2026-05-29 |
| qrels        | `tests/eval/qrels.jsonl` — 25 queries; styles: 11 `paraphrase-hard`, 9 `paraphrase`, 1 `multi-page-hard`, 4 other (1 multi-page, originals retained) |
| corpus       | `tests/retrieval/synthetic_public_vault/` — 20 markdown pages, all Tier S1 |
| embedder     | Ollama `nomic-embed-text` (768d, local 127.0.0.1:11434) |
| reranker     | `BAAI/bge-reranker-base` (sentence-transformers CrossEncoder, FP32 CPU, local HF cache, `local_files_only=True`) |
| k            | 10 (results per query) |
| k_in         | 50 (candidates fed to RRF / reranker) |
| tier         | S1 |
| variants     | bm25_only, vec_only, rrf, rrf_rerank |
| egress       | none — all components loopback or pure-local |

## Macro results (mean over 25 queries)

| Variant      | Recall@10 | MRR@10 | nDCG@10 |
|---           |---:|---:|---:|
| `bm25_only`  | 1.0000 | 0.9333 | 0.9473 |
| `vec_only`   | 1.0000 | 0.9257 | 0.9438 |
| `rrf`        | 1.0000 | **1.0000** | **1.0000** |
| `rrf_rerank` | 1.0000 | 0.9800 | 0.9852 |

## Acceptance gates (per P2 spec)

| Gate                                       | Threshold | Observed                              | Status |
|---                                          |---|---                                    |---|
| RRF beats BM25-only on Recall@10            | ≥ +10pp | +0.00pp (1.0000 vs 1.0000)            | ⛔ CEILING |
| Reranker beats RRF on MRR@10                | > 0     | −0.0200 (0.9800 vs 1.0000)            | ⛔ REGRESS |

## Read on the numbers

### Headline: RRF demonstrates real value over lexical-only on MRR/nDCG

The hardened paraphrase pressure exposed real ranking differentiation:

| Variant      | MRR@10 delta vs BM25 |
|---           |---:|
| `bm25_only`  | — |
| `vec_only`   | −0.0076 |
| `rrf`        | **+0.0667** |
| `rrf_rerank` | +0.0467 |

This is the value the architecture promised: lexical and semantic tracks
are complementary, and RRF fusion captures both. Hardened qrels surfaced
the gradient that v0 (saturated baseline) masked.

### Where BM25 lost the rank-1 hit (paraphrase wins)

Three queries where BM25 misranks but every variant with the semantic
track recovers to MRR=1.0:

| qid | style | query | BM25 MRR | vec / rrf / rerank MRR |
|---|---|---|---:|---:|
| q04 | paraphrase | "buying back stock through an investment bank intermediary" | 0.500 | 1.0 |
| q09 | paraphrase-hard | "institutional marketing tour supporting pricing of a first-time share issuance" | 0.333 | 1.0 |
| q16 | paraphrase-hard | "shortened post-trade clearing window for cash equities adopted in 2024" | 0.500 | 1.0 |

Vocabulary the queries deliberately avoid: "buyback", "Rule 10b-18",
"S-1", "roadshow", "bookrunners", "T+1", "settlement cycle". BM25 falls to
secondary hits that share surface n-grams (e.g., "etf_structure_primer"
for q04 because both pages discuss "shares" and "investment"). The
semantic track recovers the conceptual match.

### Where the reranker regresses (q15 — note for future tuning)

q15 (paraphrase-hard): *"execution venue routing that must respect the
best displayed bid or ask across competing markets"* — relevant page is
`market_structure_primer`.

| Variant | Top-5 retrieved |
|---|---|
| `rrf`        | `market_structure_primer`, exchange_listing_standards, ipo_process_overview, tender_offer_mechanics, share_buyback_mechanics |
| `rrf_rerank` | tender_offer_mechanics, `market_structure_primer`, exchange_listing_standards, share_buyback_mechanics, ipo_process_overview |

The bge cross-encoder promoted `tender_offer_mechanics` over the correct
page. Likely cause: tender-offer text matches "bid" and "competing
shareholders" semantics more strongly than market-structure text matches
"execution venue routing" without the keyword "Regulation NMS" present.
This is documented but NOT tuned around — a known limitation of FP32
bge-reranker-base on financial-domain queries. Future evals will track
whether a larger reranker, domain fine-tune, or different prompt template
recovers.

### Why Recall@10 stays at 1.0 (corpus geometry, not wiring)

The corpus is 20 pages. k=10 captures half the corpus. Any variant whose
top-10 includes the target hits Recall@10=1.0. Every variant in this
baseline places the target somewhere in the top-3 even when it misses
rank-1, so Recall@10 cannot fall below 1.0.

To break the Recall ceiling requires Option 2 (corpus expansion to ~80-100
pages), which is explicitly out of scope per operator decision. Leaving
the ceiling visible in this baseline document so future readers don't
mistake it for a passed gate.

## Per-query mix (hardened set)

| Style              | Count | What it tests |
|---|---:|---|
| `paraphrase-hard`  | 11 | Vocabulary stripped at the stem; tests semantic generalization |
| `paraphrase`       | 9 | Loose paraphrase retained from v0 (already worked) |
| `exact-keyword`    | 0 | All v0 exact-keyword queries rewritten |
| `multi-page`       | 1 | Tests multi-document retrieval |
| `multi-page-hard`  | 1 | Multi-document + paraphrase pressure (q20) |

## How to reproduce

```powershell
python -m src.retrieval.eval `
    --qrels tests/eval/qrels.jsonl `
    --vault tests/retrieval/synthetic_public_vault `
    --db src/memory/sqlite/eval.db `
    --embedder ollama --reranker bge `
    --variants bm25_only,vec_only,rrf,rrf_rerank `
    --tier S1 --k 10 --k-in 50 `
    --out docs/eval/baseline.json
```

`docs/eval/baseline.json` is the machine-readable source of truth.
`schema_version: 1`. Per-query results inline.

## Outcome summary

**Wiring proven correct.** RRF gives a clean +6.7pp MRR@10 lift over
BM25-only on the hardened set. The spec's Recall@10 gate cannot be reached
without corpus expansion (operator decision: not now). The reranker
regression on q15 is logged for future eval cycles.

P2 deliverables (eval harness + qrels + baseline numbers committed) are
present and reproducible. Baseline is non-saturated on the MRR and nDCG
axes the architecture actually moves.
