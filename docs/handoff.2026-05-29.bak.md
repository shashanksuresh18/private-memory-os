# Sovereign Citadel — Session Handoff

Generated 2026-05-29. Fresh session reading this should be able to continue with zero prior context. Cross-references: `CLAUDE.md` (architecture + locked invariants), `config/tiers.yaml` (routing), `config/budgets.yaml` (RAM + cost), `docs/tech-debt-phase2.md` (deferred items B1-B10), `docs/crm-graph.md` (sidecar gbrain graph snapshot), `docs/repo-audit/INDEX.md` (supply-chain audit).

This handoff supersedes the prior `docs/handoff.md` that mis-scoped P0 as "close the gbrain hole." The new contract: **gbrain is a passive sidecar; the retrieval engine is ours, built in Python.** Do not patch gbrain internals.

---

## 1. Current State

### Done (live + verified)

| Layer | File | Lines | Evidence |
|---|---|---:|---|
| Tier-S2 OPF DLP service | `src/firewall/opf/main.py` | 276 | FastAPI on 127.0.0.1:8765, `X-OPF-Token` shared secret, hash-chained audit, AST + smoke pass |
| Sovereign Router | `src/routing/sovereign_router.py` | 629 | Header + path-pinned tier routes (S1/S2/S3), auto-upgrade never-downgrade, classifier wired, AST + import + extractor unit smoke pass |
| Tier classifier (3-gate) | `src/routing/classifier/main.py` | 295 | Evidence-taint → rules → local Ollama LLM, fail-closed S3, 35/35 pytest pass, 96% cov, 1 integration skipped (model not pulled) |
| Hash-chain verifier | `src/routing/audit-log/verify_chain.py` | 217 | 5-scenario test pass: tamper detect, anomaly detect, strict mode, empty dir, missing dir |
| Denylist admin CLI | `tools/admin/denylist_cli.py` | ~280 | Atomic write, hash-chained audit, no plaintext term in log, 8 e2e tests green |
| Security baseline | `scripts/security_baseline.ps1` | 200 | BitLocker + OneDrive + NotContentIndexed + SHA pin; passed `-SkipBitLocker -Baseline`; admin re-run still pending |
| Supply-chain audit | `docs/repo-audit/INDEX.md` + 11 clones | — | Decisions locked: drop `jlevere/obsidian-mcp-plugin`, `privacyshield-ai/privacy-firewall`; adopt `bitbonsai/mcpvault`, `openai/privacy-filter` |
| Project-root forks | `privacy-filter/` (f7f00ca, Apache 2.0) | — | LIVE — imported by OPF service. `ClawXRouter/` deferred (LICENSE absent) |
| Dashboard mockup | `src/ui/dashboard/{index.html,styles.css,app.js}` | 548 | Klarna one-screen, static, mock data inline |
| Vault seeds | `vault/{people,companies,meetings,memos,concepts}/` | 8 .md | 3 person, 2 company, 1 meeting, 1 memo, 1 concept template |
| gbrain SIDECAR install | `~/.gbrain/brain.pglite` + `bun 1.3.14` + `gbrain 0.41.26.0` | — | Source `citadel` registered, 8 pages / 16 chunks / 17 typed edges synced. **Inspection only. Not on the answer path.** |

### In progress (this turn = discover + plan only; no code shipped)

- Re-scoped P0 from "fix gbrain config" to **"build our own Python hybrid RRF engine."** No code yet.
- Vault is its own git repo under `vault/.git` (separate from project root). gbrain reads its working tree.

### Untouched

- **Our retrieval engine itself.** Does not exist. Empty placeholder dirs at `src/memory/{openhuman,sqlite,tokenjuice}/` and `src/models/{ollama,quant-eval}/` (zero code).
- No chunker, no FTS5 index, no vector store, no RRF fuser, no reranker, no atoms table, no graph track in our Python.
- BitLocker confirmation (admin PowerShell needed).
- OneDrive Known Folder Move audit (vault still under `~/Desktop`).
- `bitbonsai/mcpvault` — approved replacement, not wired.
- Ollama not installed; `nomic-embed-text` (embedder), `bge-reranker-v2-m3` or `bge-reranker-base` (reranker), and the S3 chat model (`qwen2.5:14b-q4_K_M` or similar) not pulled.
- Windows Task Scheduler wrapper for hourly `verify_chain.py`.
- `src/crm.deprecated/` Python+SQLite CRM (rollback only).
- `MassGen`, `EdgeClaw`, `tinyhumansai/openhuman`, `affaan-m/ECC` cloned to `repos-audit/`, never wired.

---

## 2. Discovery Results (file:line evidence — no assumptions)

### A. THIS repo's language census (verified)

`find src/ -type f -not -path '*__pycache__*' -not -path '*deprecated*'`:

```
.py    7 files  · 1467 lines total (largest: sovereign_router.py 629, classifier/main.py 295, opf/main.py 276)
.html  1 file   · 68 lines
.css   1 file   · 266 lines
.js    1 file   · 214 lines
.ps1   2 files  · 76 lines  (launcher scripts only)
.txt   5 files  · denylists + requirements
.db    1 file   · src/memory/sqlite/crm.db (orphan from earlier smoke test, 143 lines of dump)
```

**Verdict: our project is Python (server-side) + vanilla HTML/CSS/JS (dashboard). Zero TypeScript. Zero Rust. Zero Go.**

### B. Retrieval primitives in OUR src/ (`grep` over fts5|bm25|MATCH|websearch_to_tsquery|reciprocal_rank|rrf|hybrid_search|vector_store|reranker|cross_encoder|hnsw|pgvector|sqlite_vec|sqlite_vss|nomic_embed`)

**One hit, and it's a budget reservation, not code:**

- `config/budgets.yaml:19` — `embedding_engine_gb: 1 # nomic-embed-text`

**Verdict: zero retrieval primitives in our codebase.** The engine has not been built. P0 must build it.

### C. Local-model wiring already in OUR src/

We already call Ollama in two places — the patterns from these are reusable for the embedder client:

- `src/routing/classifier/main.py:43` — `OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")`
- `src/routing/classifier/main.py:220` — `r = client.post(f"{OLLAMA_URL}/api/chat", json=payload)` (gate 3 LLM tie-break)
- `src/routing/sovereign_router.py:57` — same `OLLAMA_URL` constant
- `src/routing/sovereign_router.py:381` — `_call_ollama_as_anthropic()` Tier-S3 chat path

**Verdict: Ollama is already a load-bearing local-only seam in our code. nomic-embed will land via `POST http://127.0.0.1:11434/api/embed` from the same `httpx.Client` pattern.**

### D. Cloud-egress sites in OUR src/ (would touch network)

The ONLY cloud-touching code in our Python is the Sovereign Router's S1 + S2 path:

- `src/routing/sovereign_router.py:16` — docstring: `S1 (public) -> forward as-is to api.anthropic.com`
- `src/routing/sovereign_router.py:18` — `S2 (sensitive) -> forward sanitized skeleton to api.anthropic.com`
- `src/routing/sovereign_router.py:56` — `ANTHROPIC_URL = os.environ.get("ANTHROPIC_API_URL", "https://api.anthropic.com")`
- `src/routing/sovereign_router.py:590` — `/s1/v1/messages` handler

**S3 paths never touch this URL.** The router's `_call_ollama_as_anthropic()` is the only path that S3 takes, and it goes to `127.0.0.1:11434`. Verified by re-reading the dispatch logic in `_handle_messages` at lines 470-540.

### E. Ownership verdict on `src/core/*.ts`

| Path | Exists? | Owner | Action |
|---|---|---|---|
| `src/core/search/rerank.ts` | YES, at `repos-audit/garrytan__gbrain/src/core/search/rerank.ts` | gbrain fork | **DO NOT MODIFY.** Our engine never calls it. |
| `src/core/ai/gateway.ts` | YES, at `repos-audit/garrytan__gbrain/src/core/ai/gateway.ts` | gbrain fork | DO NOT MODIFY. |
| Any other `src/core/*.ts` | YES — 100+ files at `repos-audit/garrytan__gbrain/src/core/` (6.8MB tree) | gbrain fork | DO NOT MODIFY. |
| `src/core/` at OUR project root | **DOES NOT EXIST** (verified by `[ -d src/core ] && echo EXISTS \|\| echo MISSING`) | — | If a future file is named `src/core/*.ts`, it is gbrain's. Our retrieval will live at `src/retrieval/` (Python). |

**Rule of thumb: any `.ts` file in this workspace belongs to a fork inside `repos-audit/` or `ClawXRouter/` or `privacy-filter/`. None of them are on our answer path. Our code is Python.**

### F. ZeroEntropy wiring + S2/S3 fireability

- **In OUR src/:** zero matches. ZE has never been referenced from our code.
- **In gbrain fork:** ZE is the **upstream default** embedding model. Evidence:
  - `repos-audit/garrytan__gbrain/src/core/ai/defaults.ts:20` — `DEFAULT_EMBEDDING_MODEL = 'zeroentropyai:zembed-1'`
  - `repos-audit/garrytan__gbrain/src/core/ai/dims.ts:57-65` — flexible-dim allowlist for `zembed-1` model
  - `repos-audit/garrytan__gbrain/src/cli.ts:1716-1719` — env passthrough for `ZEROENTROPY_API_KEY`
- **Our active sidecar config** (`~/.gbrain/config.json`):
  ```json
  "embedding_model": "openai:text-embedding-3-large",
  "embedding_dimensions": 1536,
  "expansion_model": "openai:gpt-5.2",
  "chat_model": "openai:gpt-5.2"
  ```
- **Can ZE fire on S2/S3?** Only if we explicitly run a gbrain phase that opens the gateway (`gbrain embed`, `gbrain search --expansion`, `gbrain dream`, `gbrain extract atoms`, `gbrain extract facts`, etc.). None of those are on our answer path. Today's exposure: gbrain config currently routes embeddings to **OpenAI** (cloud), and `gbrain search --expansion` would invoke gpt-5.2 (cloud). Both are off until somebody types the command. **None has been run.** The off-by-default switch (P0 §3 below) hardens this so the commands fail closed.

### G. Char offsets in chunks (source-span reopen)

- **In OUR src/:** chunks don't exist yet. We get to design the schema; emit `chunk_start_byte_offset INTEGER NOT NULL, chunk_end_byte_offset INTEGER NOT NULL` from day one.
- **In gbrain fork's `content_chunks` table** (`repos-audit/garrytan__gbrain/src/schema.sql:257-296`): columns are `id, page_id, chunk_index, chunk_text, embedding, embedding_image, symbol_name, language, search_vector` — **no offset columns.** Only `byte_offset` hit anywhere in the fork is `src/core/claw-test/transcript-capture.ts:9,21,63` (unrelated transcript-replay format).
- **Verdict:** since gbrain is a sidecar, this is moot for our answer path. **Our own chunker MUST emit char/byte offsets per chunk.** Source-span reopen depends on it. Flag it as a P0 schema invariant.

### H. Existing chunkers / FTS / vector store dirs in our repo

Empty placeholder directories from earlier scaffold:

- `src/memory/openhuman/.gitkeep` — empty
- `src/memory/sqlite/.gitkeep` — empty (plus orphan `crm.db` from prior smoke test)
- `src/memory/tokenjuice/.gitkeep` — empty
- `src/models/ollama/.gitkeep` — empty
- `src/models/quant-eval/.gitkeep` — empty
- `src/mcp/vault-bridge/.gitkeep` — empty
- `src/firewall/embeddings/.gitkeep` — empty (S3 corpus similarity index, future)

**Recommendation: build the engine under `src/retrieval/` (new dir). Reserve `src/memory/sqlite/` for the FTS5 + atoms + graph DBs.**

---

## 3. Phase Plan (P0 → P4 — discovery-driven, value-ordered)

All phases are Python (Bun + gbrain stay in their lane as sidecar). Engine entry point: `src/retrieval/engine.py`.

### P0 — Build our own local hybrid RRF retrieval engine

- **Goal:** the trusted S3 core. Answer-path retrieval = ours, 100% local, byte-deterministic.
- **Pipeline:** ingest → chunk (with byte offsets) → FTS5 BM25 index + nomic-embed vectors → RRF fuse → return `(chunk_id, page_slug, byte_start, byte_end, score)` tuples. **No reranker yet, no atoms yet, no graph yet.** Just the two-track RRF.
- **Files (all NEW):**
  - `src/retrieval/__init__.py` — public surface (`retrieve(query, tier, k=20)`).
  - `src/retrieval/schema.sql` — `pages`, `chunks` (with `chunk_start_byte`, `chunk_end_byte`, `tier`, `page_path`), `chunks_fts` (SQLite FTS5 virtual table), `vectors` (BLOB column of nomic-embed float32 packed, or sqlite-vec virtual table if available).
  - `src/retrieval/db.py` — connection + init from `schema.sql`. SQLite WAL mode, FK on.
  - `src/retrieval/chunker.py` — recursive markdown chunker (heading-aware, ~512 tokens), emits `(text, byte_start, byte_end)` triples.
  - `src/retrieval/embedder.py` — `embed(text) -> bytes` calls `POST http://127.0.0.1:11434/api/embed` (model `nomic-embed-text`). Reuse the `httpx` pattern from `src/routing/classifier/main.py:220`.
  - `src/retrieval/index.py` — `ingest(vault_path)` walks markdown files, chunks, embeds, persists to FTS5 + vectors. Tier of each chunk = tier of source page frontmatter (default S3 if absent).
  - `src/retrieval/search.py` — `bm25_search(query, k)` + `vector_search(query, k)` + `rrf_merge(*ranked_lists, k_const=60)` → fused top-N.
  - `src/retrieval/engine.py` — orchestrator: ingest CLI, search CLI, tier gate, fail-closed.
  - `tests/retrieval/test_chunker_offsets.py` — gating test #2 below.
  - `tests/retrieval/test_no_egress_on_s3.py` — gating test #1 below.
  - `tests/retrieval/test_tier_integrity.py` — gating test #3 below.
- **Acceptance check:** `python -m src.retrieval.engine ingest vault/` produces an SQLite DB at `src/memory/sqlite/retrieval.db` with non-zero chunks AND non-NULL `(chunk_start_byte, chunk_end_byte)`. `python -m src.retrieval.engine search "Wonderland Capital" --tier S3 --k 5` returns 5 results, each pointing into a real `vault/*.md` byte range that reopens to the indexed text byte-identical.
- **Gating test:** `tests/retrieval/test_no_egress_on_s3.py` runs `engine.retrieve(query, tier='S3')` inside a network-blocked context (`monkeypatch` `socket.socket.connect` to raise on any non-loopback host) and asserts (a) no exception, (b) results returned, (c) zero non-loopback DNS calls captured.

### P1 — Local cross-encoder reranker on the RRF output

- **Goal:** Step 5 of target pipeline. Re-score top-N from P0 with a local cross-encoder. No cloud.
- **Candidate models** (must run on 32GB CPU, ideally MPS-able when we port to mac):
  - `BAAI/bge-reranker-base` (~280MB, fast, FP16 OK on CPU)
  - `BAAI/bge-reranker-v2-m3` (~570MB, multilingual)
- **Wiring:** transformers + `sentence-transformers` CrossEncoder, OR run via `llama.cpp` GGUF as embedding endpoint. **Decision needed** (open question #1 below).
- **Files:**
  - `src/retrieval/reranker.py` — `rerank(query, candidates, k_in=50, k_out=10) -> list[dict]`. Loaded once at startup, cached.
  - `src/retrieval/engine.py` — call reranker between RRF and span reopen.
  - `tests/retrieval/test_reranker_local_only.py` — asserts reranker never opens a socket.
- **Acceptance check:** P0's top-10 reorders deterministically; manual eyeball shows MNPI-relevant chunks float up. Latency measured (target: <500ms for k_in=50 on CPU; if it blows past 2s, drop to `bge-reranker-base` or quantize).
- **Gating test:** same `no_egress_on_S3` test extended to cover the reranker call.

### P2 — Eval benchmark (truth set so P1+ are measured not vibed)

- **Goal:** real questions + expected source-file citations + Recall@10, MRR@10, nDCG@10 numbers.
- **Files:**
  - `tests/eval/qrels.jsonl` — 25 hand-curated queries with expected `page_slug` list (lifted from the seed corpus + synthetic-but-realistic MNPI shapes per the privacy rule in CLAUDE.md).
  - `src/retrieval/eval.py` — runner: `python -m src.retrieval.eval --qrels tests/eval/qrels.jsonl --variants bm25_only,vec_only,rrf,rrf_rerank`. Emits JSON envelope with `schema_version: 1`, per-variant metrics, per-query top-K.
  - `docs/eval/baseline.md` — first numbers committed; every P3+ change must beat or tie.
- **Acceptance check:** RRF beats BM25-only on Recall@10 by >=10pp on the qrels set. Reranker beats RRF on MRR@10. Numbers go in `docs/eval/baseline.md`.
- **Gating test:** part of `pytest -m gating` — refuses to merge if Recall@10 regresses by >5pp vs `docs/eval/baseline.md`.

### P3 — Tier-aware atoms (pointer-only) + local entity/alias table

- **Goal:** atoms = `(page_slug, chunk_id, byte_start, byte_end, label, confidence, tier, created_at)`. No `text` column. Resolver returns live source slice.
- **Files:**
  - `src/memory/atoms/schema.sql` — atoms table + entities table (canonical id + aliases array as JSON) + entity_alias table for fast lookup. Tier on every row.
  - `src/memory/atoms/extractor.py` — deterministic-first regex pass over each chunk (emails, phone, $X.YM, deal codenames from `src/routing/classifier/denylist/`), optional local-LLM gate (Ollama Llama 3.2 3B) for semantic atoms — **off by default**; only fires when `--enable-llm-extract` flag AND tier in `{S1, S2}` (S3 is rule-only, fail-closed).
  - `src/memory/atoms/resolver.py` — `resolve(atom_id) -> str` reads `vault/<page_slug>.md` and slices `[byte_start:byte_end]`. Always from the live file; no cached text.
  - `src/memory/atoms/audit.py` — append-only `audit/atoms.jsonl`, hash-chained, records `atom_id`, `sha256(resolved_text)`, `tier`, peer, ts. **Never the text itself.**
  - `tests/atoms/test_no_plaintext_persistence.py` — gating test (see §5 of CLAUDE.md additions).
- **Acceptance check:** atoms DB has 0 `text*` columns. `audit/atoms.jsonl` greps clean for any substring of resolved chunks. Resolver byte-equal to manual slice.
- **Gating test:** `test_citations_resolve_to_source` (gating #2 in CLAUDE.md).

### P4 — Typed-edge knowledge graph as a 5th retrieval track

- **Goal:** graph_expansion(seed_chunks) returns sibling chunks reachable via 1-2 typed edges. Edges = `(src_page, dst_page, edge_type, confidence, tier)`. Tier of edge = MAX(tier_src, tier_dst) (most-restrictive).
- **Extraction:** mirror gbrain's deterministic local approach. Verify before relying:
  - frontmatter fields (`attendees`, `audience`, `company`) → typed edges via static map.
  - markdown wikilinks `[Name](people/slug)` + Obsidian `[[people/slug|Name]]` → `mentions` edges with verb-inference heuristics.
  - **Must be 100% local-deterministic.** No LLM in the extraction path. Verified by reading `repos-audit/garrytan__gbrain/src/core/link-extraction.ts` and porting the regex set (the gbrain code itself is local-deterministic — confirm + port). Independent re-implementation in Python keeps our engine offline.
- **Files:**
  - `src/memory/graph/schema.sql` — edges table with composite tier column.
  - `src/memory/graph/extractor.py` — Python port of gbrain's frontmatter + wikilink + verb-inference regexes.
  - `src/memory/graph/expand.py` — `expand(chunk_ids, depth=1, direction='both') -> list[chunk_id]` then merge as RRF track #5.
  - `src/retrieval/engine.py` — wire graph track behind a flag (default ON for S1, opt-in for S2/S3).
- **Acceptance check:** seed an Alice query, top-10 includes Wonderland + Acme via graph expansion when they were missed by BM25+vector alone.
- **Gating test:** `test_tier_integrity` (gating #3 in CLAUDE.md) — assert no S1 atom or edge leaks into an S3 result row; assert composite-tier rule fires when an S3 page links to an S1 page (result row = S3).

---

## 4. Cloud-Call Inventory + Off-By-Default Switch

Every cloud path in this workspace, who can fire it, what the switch is:

| Caller | Cloud target | Trigger | Off-by-default switch (what to add in P0) |
|---|---|---|---|
| `src/routing/sovereign_router.py:_call_anthropic` | api.anthropic.com | S1 or S2 inbound HTTP only | Already tier-gated. S3 cannot reach this code path. No change. |
| gbrain `embed --stale` (sidecar) | api.openai.com (current config) OR api.zeroentropy.dev (upstream default) | Operator types the command | Set `~/.gbrain/config.json` → `embedding_model: "none"`. Add startup check: refuse to run if non-loopback model resolved. Documented as "gbrain off-by-default for cloud" locked rule. |
| gbrain `extract atoms` (sidecar) | anthropic Haiku via gateway | Operator types | Set `chat_model: "none"` in same config. Same refuse-startup gate. |
| gbrain `extract facts` (sidecar) | anthropic Haiku | Operator types | Same as above. |
| gbrain `search --expansion` (sidecar) | gpt-5.2 expansion model | Operator types `--expansion` flag | Set `expansion_model: "none"`. Refuse-flag gate. |
| gbrain `serve --http` (sidecar) | n/a outbound; opens HTTP server | Operator types | Add `tests/sidecar/test_gbrain_serve_off.py` asserting service file absent + port 3131 closed. |
| gbrain `dream` (cycle synthesis) | multi-LLM via gateway | Operator types OR autopilot daemon registered | Don't register autopilot. Add `gbrain_off_check.py` script that fails CI if `~/.gbrain/config.json` has a non-loopback chat_model. |
| gbrain `models doctor` 1-token probes | All configured providers | Operator runs it | Acceptable IF all providers resolve loopback. With `embedding_model: none, chat_model: none, expansion_model: none`, doctor cannot reach any cloud. |
| `src/retrieval/embedder.py` (P0, not yet built) | 127.0.0.1:11434/api/embed | Every ingest | Loopback only. No switch needed. |
| `src/retrieval/reranker.py` (P1, not yet built) | local model load + inference | Every search | Loopback or in-process. No switch needed. |
| `src/memory/atoms/extractor.py` (P3) optional LLM gate | 127.0.0.1:11434/api/chat | `--enable-llm-extract` flag AND tier in {S1,S2} | Flag default OFF + tier gate. |

**The single hardening artifact P0 ships:** `scripts/sidecar_off_check.py` — runs in CI + pre-commit. **Spec (resolved-host based, NOT model-name based):** the script MUST enumerate every model field across both planes (file `~/.gbrain/config.json` AND DB `brain.pglite`), resolve each declared `provider:model` through the gbrain recipe registry to its `base_url`, parse the host, and fail the build if any host is non-loopback (`127.0.0.1`, `::1`, `localhost`) OR not the literal `none`. **Why model-name strings are insufficient:** `assertEmbeddingEnabled()` (`embedding-dim-check.ts:66`) only checks the `embedding_disabled` sentinel, not `model === "none"`; a future operator typo like `gbrain config set embedding_model openai:text-embedding-3-large` bypasses every model-name allowlist. Resolved-host is the only invariant that cannot be string-spoofed. `tests/retrieval/test_no_egress_on_s3.py` MUST mirror the same resolved-host assertion across BOTH planes and ALL fields (`embedding_model | chat_model | expansion_model | rerank_model | models.tier.{utility,reasoning,deep,subagent}`), AND must monkeypatch `socket.socket.connect` to raise on any non-loopback peer during S3 execution to catch the resolved-host bypass case (DNS rebinding, IP literal, host header trick).

**Addendum (2026-05-29 — corrected post-incident):**

- **Incident truth:** `gbrain embed --stale` on 2026-05-29 *actually fired to OpenAI* (got 429s). Root cause: DB plane held `chat_model | expansion_model | embedding_model` pointing at OpenAI while the file plane was being edited toward `none`. The DB plane is what gbrain reads at runtime for `chat_model | expansion_model`; the embed path reached the live `embedding_model` resolution and fired.
- **Per-field plane authority** (load-bearing — both planes must be hardened for all fields):
  - `embedding_model` — **file-plane authoritative**. Sizes schema at init; DB-plane writes via `gbrain config set` are silent no-ops.
  - `chat_model`, `expansion_model`, tier defaults (`models.tier.*`) — **DB-plane authoritative**. File-plane values fall through.
  - `models.tier.subagent` — cannot be set to `none`; gbrain hardcoded-falls-back to `anthropic:claude-sonnet-4-6` with stderr warning. Subagent leak is non-zero if any future code invokes `gbrain dream | cycle | autopilot`. All three are off the answer path today and MUST remain off.
- **Dry-run is NOT egress proof.** `gbrain embed --stale --dry-run` is plan-mode by design (`embed.ts:123,157,169` all short-circuit on `dryRun`). It skips `preflightDimMismatch`, `assertEmbeddingEnabled`, AND `validateEmbeddingCreds`. It enumerates stale chunks without touching network. The egress invariant is proven by the *non-dry* path: with `embedding_model = "none"`, `validateEmbeddingCreds()` → `diagnoseEmbedding()` returns `no_model_configured` → throws `EmbeddingCredentialError` before any HTTP call. That throw is the structural fail-closed proof; dry-run silence is not.
- **OpenAI API key purged 2026-05-29.** The credential persisting from the incident lived at three sites: `~/.bashrc:1` `export OPENAI_API_KEY=...`, Windows User env, current shell env. All three scrubbed. `gbrain config show` no longer reports `openai_api_key`. The credential cannot be auto-reloaded; recovery = regenerate at platform.openai.com.
- **Standing gates** (cannot regress):
  - Both planes resolve `embedding_model | chat_model | expansion_model | rerank_model` to `none` or loopback.
  - No `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `VOYAGE_API_KEY` / `ZEROENTROPY_API_KEY` in shell profile, OS env, or any future config plane until an explicit operator decision re-introduces one with a documented tier scope.
  - `scripts/sidecar_off_check.py` resolved-host assertion fires on commit AND in `gbrain doctor`.

---

## 5. Next Action (single first step for next session)

**Discover gbrain's link-extraction regex set (confirm it's LLM-free) BEFORE writing P0 code.** This is the only piece of P0+P4 design that depends on a fork we don't control. Read the actual code:

```bash
sed -n '1,200p' repos-audit/garrytan__gbrain/src/core/link-extraction.ts
```

Look for: `extractEntityRefs`, `extractPageLinks`, `inferLinkType` regex shapes, `FRONTMATTER_LINK_MAP` constant. Verify zero LLM calls in the path. Write a one-page port plan into `docs/graph-extraction-port.md`. Then start P0 (`src/retrieval/schema.sql`).

Reason this is the very first step: P0 + P4 share the page schema (compiled-truth above the line, append-only timeline below, frontmatter taxonomy). Locking the graph extractor's deterministic surface now means we don't redesign `pages.frontmatter_links` later.

---

## 6. Open Decisions

### LOCKED (operator decision, 2026-05-29 — do not amend without security review)

| # | Decision | LOCKED value | Notes |
|---|---|---|---|
| 2 | SQLite vector storage | **`sqlite-vec` extension with raw BLOB float32 fallback** | Try `db.load_extension('vec0')` at startup; if load fails (no shared lib for this platform), fall back to BLOB column + cosine-in-Python. Schema accommodates both; runtime path switches via a single bool flag. |
| 3 | Chunker target | **512 tokens per chunk, 64-token overlap, heading-aware splits at H1/H2 boundaries** | Tokenizer for counting: `tiktoken` `cl100k_base` (matches OpenAI/Anthropic tokenizer; locally vendored, no cloud). |
| 4 | nomic-embed dimensions | **768 (full default, no Matryoshka truncation)** | Storage: 768 × 4 bytes = ~3KB per chunk vector. Acceptable at vault scale. |

### Still open

| # | Decision | Default if no answer | Why it matters |
|---|---|---|---|
| 1 | Local reranker model: `bge-reranker-base` (280MB, 2-class), `bge-reranker-v2-m3` (570MB, multilingual), or skip and rely on RRF order? | `bge-reranker-base` via `sentence-transformers` CrossEncoder (FP32 CPU). | Blocks P1 file scaffold. |
| 5 | Tier on absent-frontmatter pages: default S3 (current rule) or refuse-ingest? | **Refuse-ingest with loud error.** Forces explicit tier on every page. Catches forgotten metadata before it lives in the index as S3-by-accident. | Tier integrity. |
| 6 | Fork gbrain to your private GH org for SHA pinning, or keep audit clone read-only? | Keep audit clone read-only since gbrain stays a sidecar. Pin commit SHA in `config/sha_manifest.json` to prevent silent upstream drift. | Supply-chain. |
| 7 | Vault relocation off `~/Desktop` to `C:\sovereign-citadel\`? | Yes, before any real MNPI lands. Sweeps tech-debt B2. | KFM exposure. |
| 8 | Delete `src/crm.deprecated/` Python+SQLite CRM (since gbrain sidecar + our P0 engine cover the use cases)? | Keep until P0 + P3 ship green; delete after P3 acceptance test passes. | Rollback option. |

---

## 7. LOCKED Rules To Add To CLAUDE.md (operator does this)

Insert under the existing `## Tri-Tiered Data Routing Policy (CRITICAL — NEVER VIOLATE)` section, **right after line 12** (the "Default classification: unknown = S3" bullet). New block:

```markdown
### Locked Invariants (never amend without a security review)

- **S3-never-cloud.** No Tier S3 byte may leave the device. Applies to inference, embeddings, prompt cache, reranker calls, telemetry, crash reports, error envelopes. Any code path that handles S3 must show zero non-loopback DNS resolution during its execution window. Enforced by `tests/retrieval/test_no_egress_on_s3.py` (gating).

- **The retrieval ENGINE is ours, in Python.** `src/retrieval/` is the canonical surface. Hybrid RRF = BM25 (SQLite FTS5) + local nomic-embed vectors + optional atoms track + optional typed-edge graph track + local cross-encoder reranker. `gbrain` is an OPTIONAL, OFF-BY-DEFAULT sidecar — never the engine, never source of truth, never on the answer path. Do not patch gbrain internals to "fix" them; the goal is that our engine never invokes gbrain at all.

- **gbrain off-by-default for cloud.** `~/.gbrain/config.json` MUST keep `embedding_model | expansion_model | chat_model | rerank_model` set to `"none"` or to a `127.0.0.1`-prefixed local model. CI script `scripts/sidecar_off_check.py` rejects commits where any of those resolve non-loopback. `gbrain embed`, `gbrain extract atoms`, `gbrain extract facts`, `gbrain search --expansion`, `gbrain serve --http`, `gbrain dream`, and any cloud reranker (e.g. ZeroEntropy `zerank-2`) are PROHIBITED against any non-S1 source.

- **Atoms are pointers, never text.** The atoms table stores `(page_slug, chunk_id, byte_start, byte_end, label, confidence, tier, created_at)`. No `text` column. Resolver reads the current vault file at query time and returns the live byte slice. Audit log persists only the SHA-256 hash of resolved bytes, never the bytes themselves. Enforced by `tests/atoms/test_no_plaintext_persistence.py` (gating).

- **Final answers cite source text only.** The agent's answer must reopen the source span via `resolve(page_slug, byte_start, byte_end)` and quote from that. Never quote an atom row, a graph edge, a chunk embedding, or an RRF score line. Enforced by `tests/retrieval/test_citations_resolve_to_source.py` (gating).

- **Tier inheritance + most-restrictive composite.** Every atom inherits its source page's tier. Every graph edge carries `MAX(tier_src, tier_dst)` (most restrictive of its endpoints). Every fused/derived/cross-source result row carries the MAX tier of every contributing input. Re-tier on reclassification cascades to every downstream atom + edge + cached result. Enforced by `tests/retrieval/test_tier_integrity.py` (gating).

- **Gating tests are non-bypassable.** A change to the engine, atoms table, graph extractor, reranker, or tier-routing seam ships only when all three gating tests pass: `test_no_egress_on_s3`, `test_citations_resolve_to_source`, `test_tier_integrity`. `pytest -m gating` runs all three. CI / pre-merge hook required (Phase 2 debt — `docs/tech-debt-phase2.md` B11).
```

Once those 7 bullets are in CLAUDE.md, the contract is load-bearing across sessions and the engine code can be written against it.

---

## 8. Quick-Reference Paths

```
~/.gbrain/                              gbrain SIDECAR DB + config (off-by-default)
~/.bun/bin/bun.exe                      bun (sidecar runtime only)
vault/                                  brain source (own git repo, system of record)
vault/people|companies|meetings|memos|concepts/

src/retrieval/                          [P0, TO BUILD]  our hybrid RRF engine
src/memory/sqlite/                      [P0]            retrieval.db + atoms.db + graph.db
src/memory/atoms/                       [P3, TO BUILD]
src/memory/graph/                       [P4, TO BUILD]
src/firewall/opf/                       Tier S2 DLP service (live)
src/routing/                            Sovereign Router + classifier + verifier (live)
tools/admin/denylist_cli.py             audited mutation gateway (live)

config/tiers.yaml                       routing policy
config/budgets.yaml                     RAM + cost budgets
config/cron.yaml                        Task Scheduler jobs (not yet registered)
config/sha_manifest.json                supply-chain pins

scripts/security_baseline.ps1           boot-gate
scripts/install_gbrain.ps1              sidecar bootstrap
scripts/sidecar_off_check.py            [P0, TO BUILD]  CI guard against gbrain cloud config

tests/retrieval/                        [P0-P4]         gating tests
tests/atoms/                            [P3]
tests/eval/qrels.jsonl                  [P2]            truth set
docs/eval/baseline.md                   [P2]            committed metrics

repos-audit/garrytan__gbrain/           READ-ONLY audit clone (sidecar source)
ClawXRouter/                            user fork, DEFERRED per Option 4
privacy-filter/                         user fork of openai/privacy-filter, LIVE (OPF)
src/crm.deprecated/                     soft-deleted Python CRM (rollback only)
```

---

## 9. Step Receipts (this turn)

1. Discover OUR repo's language + retrieval state — ✅ done. 7 .py files, 1 .html, 1 .css, 1 .js; zero retrieval primitives; one budget mention of nomic-embed-text in `config/budgets.yaml:19`.
2. Determine ownership + language of `src/core/*.ts` files — ✅ done. `src/core/` does not exist in our repo; every `src/core/*.ts` is in `repos-audit/garrytan__gbrain/src/core/` (gbrain fork). Do not modify.
3. Locate ZeroEntropy wiring + fireability — ✅ done. Only in gbrain fork. Cannot fire on S2/S3 unless an operator types a gbrain cloud command AND BOTH planes resolve to it. Currently both planes resolve to `none` for `embedding_model | chat_model | expansion_model`; resolved-host hardening per §4 spec still required.
4. Check chunk offsets — ✅ done. Gbrain has none. We will emit them from day one in our chunker; flagged as P0 invariant.
5. Produce phased plan — ✅ done. P0 hybrid RRF, P1 reranker, P2 eval bench, P3 atoms, P4 graph track.
6. Cloud-call inventory + off-by-default switch — ✅ done. Single artifact: `scripts/sidecar_off_check.py` (resolved-host spec, see §4) + CLAUDE.md locked rules.
7. No installs, no builds, no deletes this turn — ✅ confirmed.

## 9.1 Receipts (2026-05-29 post-incident addendum, this session)

1. Verified live gbrain state — DB plane (`gbrain config get`): `embedding_model` = key not found (file-plane authoritative; resolves to `none`); `chat_model` = `none`; `expansion_model` = `none`; `rerank_model` = key not found. File plane (`~/.gbrain/config.json`): all four = `none`. No model field resolves to a cloud provider.
2. Re-classified the 2026-05-29 incident — the embed **actually fired to OpenAI** (429s observed). Root cause: DB plane (authoritative for `chat_model | expansion_model`) held cloud values during the file-plane edit. §4 addendum extended to record incident truth and per-field plane split.
3. Classified `gbrain embed --stale --dry-run` behaviour — plan-mode by design (`embed.ts:123,157,169`); skips dim preflight, `assertEmbeddingEnabled`, and `validateEmbeddingCreds`. Cannot be used as the egress proof. The non-dry path is the real fail-closed gate: with `embedding_model = "none"`, `validateEmbeddingCreds()` throws `EmbeddingCredentialError` before any HTTP. §4 addendum records this.
4. Purged the leftover `OPENAI_API_KEY` from all three sites — `~/.bashrc:1` (export replaced with audit comment), Windows User env (`SetEnvironmentVariable($null, 'User')` → `CONFIRMED_EMPTY`), current shell env (`unset`). `gbrain config show` no longer reports `openai_api_key`. Credential cannot be auto-reloaded.
5. Re-specced the P0 hardening artifact — `scripts/sidecar_off_check.py` and `tests/retrieval/test_no_egress_on_s3.py` MUST assert on **resolved host** (loopback or `none`) across BOTH planes and ALL model fields. Model-name string allowlists are insufficient because `assertEmbeddingEnabled()` only checks the `embedding_disabled` sentinel, not `model === "none"`; a future operator typo bypasses string allowlists but cannot bypass a resolved-host check. §4 addendum extended with the spec.
6. No code shipped this session — discover + patch + purge only. P0 build deferred to operator confirmation.

End of handoff.
