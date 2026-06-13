# Retrieval Eval — Real-Vault Baseline

**DB:** `retrieval.db` (repo root, canonical)
**Qrels:** `tests/eval/qrels_real.jsonl`
**Tier gate:** exact match (`WHERE c.tier = ?`) — each query run at its own tier, results aggregated.

---

## Run 2 — nomic-embed + bge reranker (2026-06-02) — CURRENT

**Embedder:** `ollama` (nomic-embed-text, 768-dim — verified cosine 1.000 vs stored vectors;
HashEmbedder cosine -0.058, i.e. index is no longer hash).
**Reranker:** `bge` (BAAI/bge-reranker-base, FP32 CPU, `local_files_only=True`, pre-downloaded to HF cache).
**Qrels:** 15 questions (10 factoid q01-q10 + 5 hard paraphrase q11-q15).
**Run mode:** `reset=True` re-ingest of `vault/`, then eval `reingest=False`.

### Vault size (post-reingest)

| Metric | Value |
|---|---:|
| Pages | 24 |
| Chunks | 112 |
| Chunks S1 / S2 / S3 | 29 / 59 / 24 |

Vault grew between sessions (now includes Northstar, Meridian, Vertex peer/diligence docs +
inbox-converted sources) — real distractors now present.

### Baseline table — all 15 questions

| Variant      | Recall@10 | MRR@10 | nDCG@10 |
|--------------|----------:|-------:|--------:|
| bm25_only    | 1.000     | 0.917  | 0.937   |
| vec_only     | 1.000     | 0.906  | 0.929   |
| rrf          | 1.000     | 0.900  | 0.926   |
| rrf_rerank   | 1.000     | 1.000  | 1.000   |

### Hard-paraphrase subset (q11-q15) — the semantic-search probe

| Variant      | Recall@10 | MRR@10 | nDCG@10 |
|--------------|----------:|-------:|--------:|
| bm25_only    | 1.000     | 0.750  | 0.812   |
| vec_only     | 1.000     | 1.000  | 1.000   |
| rrf          | 1.000     | 0.800  | 0.852   |
| rrf_rerank   | 1.000     | 1.000  | 1.000   |

### Interpretation

- **Is rrf_rerank better than rrf? YES — the real reranker test passes.** MRR 1.000 vs 0.900,
  nDCG 1.000 vs 0.926 across all 15. The bge cross-encoder reorders the RRF candidate set so the
  relevant page is always rank-1. This is the first run where the reranker measurably earns its place
  (Run 1 used the deterministic stub on a saturated corpus and showed no lift).
- **nomic semantic search proven.** On hard paraphrases (no lexical overlap with source),
  vec_only MRR = **1.000** vs bm25_only **0.750**. Vectors retrieve "takeover price Meridian deal" →
  board_meeting, "credit agreement headroom pressure" → vertex-credit-call, etc. — none of which
  share keywords with the source. Per the prior prediction, the hash embedder would have scored these
  < 0.5; nomic scores them perfectly. All 5 paraphrase top-1 hits correct under vec_only and rrf_rerank.
- **Does rrf beat bm25? No, not on its own here.** rrf MRR (0.900) is slightly BELOW bm25 (0.917)
  on all-15 and below vec (1.000) on paraphrases — fusing bm25's weaker paraphrase ranking dilutes
  vec_only's perfect order. The reranker on top recovers it to 1.000. So value comes from
  (vectors on paraphrases) + (reranker on the fused set), not from RRF fusion alone.
- **Recall@10 > 0.8? Yes (1.000) — but still saturated.** Each query has exactly one relevant page;
  with 24 pages and a tier gate, the target reliably lands in top-10. Recall no longer discriminates;
  MRR/nDCG now do (and show real separation). More distractors than Run 1 (24 vs 11 pages) make it
  more credible, but Recall is still a ceiling.

### nomic vs hash difference (Run 1 → Run 2)

| Metric (all questions)        | Run 1 hash | Run 2 nomic |
|-------------------------------|-----------:|------------:|
| vec_only MRR@10               | 0.883      | 0.906       |
| rrf_rerank MRR@10             | 1.000*     | 1.000       |
| paraphrase vec_only MRR@10    | n/a        | 1.000       |

*Run 1 reranker was the deterministic stub on a saturated 11-page corpus — lift was unmeasurable.
The decisive change: hash bag-of-words cannot resolve zero-overlap paraphrases; nomic does.

---

## Run 1 — HashEmbedder + deterministic reranker (2026-06-01) — superseded

10 factoid questions, 11-page vault, index built with offline HashEmbedder.

| Variant      | Recall@10 | MRR@10 | nDCG@10 |
|--------------|----------:|-------:|--------:|
| bm25_only    | 1.000     | 1.000  | 1.000   |
| vec_only     | 1.000     | 0.883  | 0.913   |
| rrf          | 1.000     | 1.000  | 1.000   |
| rrf_rerank   | 1.000     | 1.000  | 1.000   |

All variants saturated; benchmark could not discriminate. vec_only worse (hash = bag-of-words).
Reranker effect unmeasurable. Recommendation at the time: re-ingest with nomic, add hard paraphrases.

---

## Scale recommendation (updated)

**Engine quality: confirmed healthy. Reranker confirmed value-adding. Cleared to scale the corpus —
with the benchmark hardened in parallel.**

What Run 2 establishes:
1. The production index is now nomic-backed (768-dim), not the hash stub.
2. Semantic retrieval works: zero-overlap paraphrases resolve to the correct page (vec MRR 1.000).
3. The bge reranker lifts MRR/nDCG to 1.000 over RRF's 0.900/0.926 — it pays for itself.
4. bge runs offline (`local_files_only=True`, weights pinned in `config/sha_manifest.json`) — no
   query-time egress, S3-safe.

Remaining caveat before declaring "scale-proven":
- **Recall@10 is still saturated (1.000).** One relevant page per query. To measure recall at scale,
  the qrels need multi-relevant-page queries and a corpus large enough that the relevant set does not
  trivially fit in top-10. Grow qrels alongside the vault. Until then, trust MRR/nDCG, not Recall, as
  the discriminating signal.
