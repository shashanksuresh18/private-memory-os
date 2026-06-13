# The Sovereign Citadel (Local-First AI Personal Operating System)

## Project Description
"Discrete Intelligence" AI Personal Operating System for a finance professional managing proprietary investment research and Material Non-Public Information (MNPI). Runs on a 32GB RAM Windows 11 laptop (target may migrate to mac later). Built on a "Hybrid Air-Gapped" architecture: absolute local-first data sovereignty + frontier cloud reasoning, gated by strict sensitivity classification + routing.

## Core Goal
Secure, persistent digital brain. Continuous memory. 24/7 background automation. Specialized financial-research skills. Zero exposure of confidential data to third-party cloud AI.

## Tri-Tiered Data Routing Policy (CRITICAL — NEVER VIOLATE)
- **Tier S3 (Confidential):** Private memos, MNPI, CRM notes. 100% local. Route: `extractive_local` (zero-LLM retrieval + exact text extraction) OR local Qwen2.5-32B (Q4_K_M, Ollama). Never touches cloud.
- **Tier S2 (Sensitive):** Passes local `openai/privacy-filter` (`opf`) DLP — PyTorch bidirectional token classifier, 1.5B params, 8 PII categories, runs on 127.0.0.1:8765. Sanitized skeleton MAY egress post-scrub to the configured cloud chat provider via the Sovereign Router's `/s2/v1/messages` path with prompt caching disabled.
- **Tier S1 (Public):** SEC filings, public market data. Routes to frontier models / MassGen multi-agent councils.
- **Default classification:** `unknown = S3`. Fail-closed always.

### Cloud Providers
- **S1/S2 cloud provider:** Nebius.
- **Model:** `deepseek-ai/DeepSeek-V3.2`.
- **Base URL:** `https://api.tokenfactory.nebius.com/v1/`.
- **Key env var:** `NEBIUS_API_KEY`.
- **S1:** unredacted public content only.
- **S2:** DLP-redacted content only; never original sensitive content.
- **S3:** never Nebius; local-only paths only.

### Locked Invariants (never amend without a security review)

- **S3-never-cloud.** No Tier S3 byte may leave the device. Applies to inference, embeddings, prompt cache, reranker calls, telemetry, crash reports, error envelopes. Any code path that handles S3 must show zero non-loopback DNS resolution during its execution window. Enforced by `tests/retrieval/test_no_egress_on_s3.py` (gating).

- **The retrieval ENGINE is ours, in Python.** `src/retrieval/` is the canonical surface. Hybrid RRF = BM25 (SQLite FTS5) + local nomic-embed vectors + optional atoms track + optional typed-edge graph track + local cross-encoder reranker. `gbrain` is an OPTIONAL, OFF-BY-DEFAULT sidecar — never the engine, never source of truth, never on the answer path. Do not patch gbrain internals to "fix" them; the goal is that our engine never invokes gbrain at all.

- **gbrain off-by-default for cloud.** `~/.gbrain/config.json` MUST keep `embedding_model | expansion_model | chat_model | rerank_model` set to `"none"` or to a `127.0.0.1`-prefixed local model. CI script `scripts/sidecar_off_check.py` rejects commits where any of those resolve non-loopback. `gbrain embed`, `gbrain extract atoms`, `gbrain extract facts`, `gbrain search --expansion`, `gbrain serve --http`, `gbrain dream`, and any cloud reranker (e.g. ZeroEntropy `zerank-2`) are PROHIBITED against any non-S1 source.

- **Atoms are pointers, never text.** The atoms table stores `(page_slug, chunk_id, byte_start, byte_end, label, confidence, tier, created_at)`. No `text` column. Resolver reads the current vault file at query time and returns the live byte slice. Audit log persists only the SHA-256 hash of resolved bytes, never the bytes themselves. Enforced by `tests/atoms/test_no_plaintext_persistence.py` (gating).

- **Final answers cite source text only.** The agent's answer must reopen the source span via `resolve(page_slug, byte_start, byte_end)` and quote from that. Never quote an atom row, a graph edge, a chunk embedding, or an RRF score line. Enforced by `tests/retrieval/test_citations_resolve_to_source.py` (gating).

- **Tier inheritance + most-restrictive composite.** Every atom inherits its source page's tier. Every graph edge carries `MAX(tier_src, tier_dst)` (most restrictive of its endpoints). Every fused/derived/cross-source result row carries the MAX tier of every contributing input. Re-tier on reclassification cascades to every downstream atom + edge + cached result. Enforced by `tests/retrieval/test_tier_integrity.py` (gating).

- **Gating tests are non-bypassable.** A change to the engine, atoms table, graph extractor, reranker, or tier-routing seam ships only when all three gating tests pass: `test_no_egress_on_s3`, `test_citations_resolve_to_source`, `test_tier_integrity`. `pytest -m gating` runs all three. CI / pre-merge hook required (Phase 2 debt — `docs/tech-debt-phase2.md` B11).

- **gbrain egress is disabled on BOTH planes — file (`~/.gbrain/config.json`) AND DB (`gbrain config set`, stored in `brain.pglite`). The DB plane is authoritative; a future session must verify the DB plane, not just the file.**

## Technical Stack

### 1. Orchestration & Privacy Routing
- `OpenBMB/EdgeClaw` — local OS, 24/7 agent loops (`ClawXKairos`), sandboxed exec (`ClawXSandbox`). **HIGH-RISK: runs only in zero-egress VM/sandbox.**
- `OpenBMB/ClawXRouter` — Tri-Tier gatekeeper, token-cost optimizer. **Fork to private GH org + add missing LICENSE file before wiring.**
- `openai/privacy-filter` (`opf`) — Apache 2.0, PyTorch bidirectional token classifier. ~1.5B params (50M active), 128k context, 8 PII categories. Local CPU/GPU. **Tier S2 DLP.** Replaces deprecated `privacyshield-ai/privacy-firewall` (which was a Chrome extension — architecture mismatch).

### 2. Persistent Memory & Knowledge (Karpathy-Inspired Vault)
- `tinyhumansai/openhuman` — auto-fetch loops, "obsidian-wiki" workflow, TokenJuice compression, SQLite + Obsidian vault. **GPLv3 + 121 telemetry hits → runs only as isolated microservice over network API boundary; outbound traffic blocked except whitelisted endpoints.**
- `safishamsi/graphify` — deterministic knowledge graphs from raw folders (installed globally via `uv tool install graphifyy`).
- `@bitbonsai/mcpvault` (npm) — MCP bridge for local Obsidian vault. Native `.base` + `.canvas` support, `list_all_tags`, dotted folder safety. Has SECURITY.md + AGENTS.md + vitest tests. **Replaces deprecated `jlevere/obsidian-mcp-plugin`** (12 stars, 10mo stale, single maintainer).
- `garrytan/gbrain` (conceptual) — "compiled truth above the line / append-only timeline below the line" markdown structure for memos. Audit-trail integrity.

### 3. Agent Performance & Financial Research
- `affaan-m/ECC` — Agentic Operator System (installed globally via Claude plugin). Cost optimization, cross-session learning, financial skills (`investor-materials`, `market-research`). **HIGH-RISK: star count inflated (~196k), AWS key literal found in clone. Strip telemetry + hardcoded credentials, compile manually rather than `npx`. Treat as hostile until line-by-line audited.**
- `massgen/MassGen` — multi-agent orchestration for S1 public research (Bull / Bear / Skeptic councils). S1-only (public data) limits blast radius.

## Project Folder Layout
```
src/routing/{classifier,policies,audit-log}     # ClawXRouter
src/firewall/{opf,denylist,embeddings}          # openai/privacy-filter (opf CLI) + denylist + S3 corpus similarity gate
src/memory/{openhuman,sqlite,tokenjuice}        # persistent memory
src/agents/{edgeclaw,kairos,sandbox,massgen}    # agent runtimes
src/models/{ollama,quant-eval}                  # local LLMs + numeric correctness benchmarks
src/mcp/vault-bridge                            # mcpvault + obsidian-mcp-plugin
vault/{people,companies,meetings,memos,inbox,concepts}  # gbrain-base schema; tier via metadata, not folder
config/                                         # tiers.yaml, budgets.yaml, cron.yaml
audit/                                          # immutable egress log (GBRAIN_AUDIT_DIR)
backups/                                        # vault snapshots
tests/{routing,firewall,numeric,e2e}            # gating tests
```
Note: `graphify` + `ECC` installed globally — no `src/graph/` or `src/ecc/` in repo. `graphify-out/` is created in project root on `/graphify` invocation.

## Development Instructions for Claude
- **Always respect S1/S2/S3 boundaries.** Never route S3 content to cloud, even indirectly via embeddings, prompt caches, or scrubbed skeletons that retain semantic MNPI.
- **Obsidian = human-readable layer.** All memory systems prioritize Obsidian markdown as source of truth.
- **Prefer open-source local-first integration** over proprietary cloud dependencies.
- **Fail closed.** Unknown sensitivity → S3. Classifier error → S3. Firewall miss → S3.
- **gbrain memo structure:** Compiled truth above `---`, append-only timeline below. Never rewrite history below the line.
- **Vault writes go through gbrain `withMutation` skeleton** (per-pack `O_CREAT|O_EXCL` atomic lock, 10s TTL). No direct file writes from agents.
- **Numeric work:** symbolic Python (deterministic) for math. LLM narrates only.
- **Egress audit log:** every cloud-bound payload logged to `audit/` *before* network call. Append-only. Hash-chained.
- **MarkItDown:** `enable_plugins=False` always. No `llm_client`. No `az-*` endpoints. Only `convert_local()`. Install `markitdown[pdf,docx,pptx,xlsx]` only. SHA pinned in `config/sha_manifest.json`.

## Operational Rules
- Local APIs bind `127.0.0.1` only.
- Host: Windows 11, 32GB RAM. 24/7 loops via Task Scheduler with `/WAKETORUN`; disable sleep with `powercfg /change standby-timeout-ac 0` for the daemon profile.
- Ollama via native Windows installer (preferred over WSL2 for direct GPU access). Models pinned by SHA in `src/models/ollama/`.
- Vault directory MUST be outside `%USERPROFILE%\OneDrive`, `%USERPROFILE%\Documents` (if synced), Desktop. **BitLocker mandatory** on the drive holding `vault/`, `audit/`, `backups/`.
- Disable Windows Search indexing for `vault/` via Indexing Options → exclude folder, and `attrib +I` on the directory.
- Plan to keep Windows host portable to mac later: abstract OS calls behind `src/platform/{windows,mac}.py` shims when written.

## Commands
- `/review` — full code review on staged changes
- `/fix-issue` — diagnose and fix a reported issue
- `/graphify` — rebuild deterministic knowledge graph over project files

## Trusted Components & Swaps (decisions from 2026-05-28 supply-chain audit)
- **Vault Egress (MCP):** `@bitbonsai/mcpvault` (npm). Replaces `jlevere/obsidian-mcp-plugin` (stale, 12 stars, bus factor 1).
- **Tier S2 Redaction:** `openai/privacy-filter` (`opf`, Apache 2.0, PyTorch, 1.5B params, 128k context, 8 PII categories). Replaces `privacyshield-ai/privacy-firewall` (Chrome extension — architecture mismatch + unfilled MIT template).
- **CRM / Knowledge Brain:** `garrytan/gbrain` (Bun + TypeScript, PGLite local default, Postgres-native scale-out). Replaces our `src/crm/` Python+SQLite stack (renamed `src/crm.deprecated/`). Vault layout `vault/{people,companies,meetings,memos,concepts,inbox}` matches gbrain-base schema-pack byte-for-byte. Page = markdown + YAML frontmatter; compiled-truth above the line, append-only timeline below. Aliases on frontmatter dedupe contacts; `gbrain pages purge-deleted` plus phantom-redirect replace the hash-chained `merges.py` table.
- **Untrusted Infrastructure (HIGH-RISK):** `OpenBMB/EdgeClaw`, `tinyhumansai/openhuman`, `affaan-m/ECC`. Must execute in zero-egress sandbox / VM / container with `iptables` outbound-deny default + whitelist (Nebius API for S1 and DLP-redacted S2 only, local Make.com webhook). `openhuman` runs as isolated microservice over network API boundary to bound GPLv3 contagion. `ECC` stripped of hardcoded credentials + telemetry + compiled manually (never via `npx`).
- **Legal gaps to close before wiring:** `OpenBMB/ClawXRouter` has no LICENSE in repo root → fork to private org + copy LICENSE from `OpenBMB/OpenClaw`. SHA pin in `src/routing/policies/SHAS.txt` after audit.
- **Approved as-is:** `D4Vinci/Scrapling` (BSD-3, tooling only), `safishamsi/graphify` (MIT, installed globally), `massgen/MassGen` (S1-only blast radius), `garrytan/gbrain` (conceptual schema, no runtime hot-path).

## Important Paths
- **Canonical retrieval DB = `C:\sovereign-citadel\retrieval.db`** (repo-root/retrieval.db). Single source of truth resolved by `src/retrieval/db.py:DEFAULT_DB_PATH`; both ingest (`index.py`) and the API server (`server.py`) land here. Override only via `RETRIEVAL_DB_PATH` env or explicit `db_path=`.
- `src/` — application source
- `vault/` — Obsidian root (gitignored, contains MNPI)
- `audit/` — immutable egress log (gitignored)
- `backups/` — vault snapshots (gitignored)
- `docs/` — architecture.md, threat-model.md, runbook.md
- `tests/` — gating tests
- `.claude/` — Claude Code config
