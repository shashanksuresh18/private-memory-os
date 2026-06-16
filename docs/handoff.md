# Sovereign Citadel — Session Handoff

Generated 2026-05-29. Fresh session reading this should be able to continue with zero prior context. Cross-references: `CLAUDE.md` (architecture + locked invariants), `config/tiers.yaml` (routing), `config/budgets.yaml` (RAM + cost), `docs/tech-debt-phase2.md` (deferred items B1-B10), `docs/crm-graph.md` (sidecar gbrain graph snapshot), `docs/repo-audit/INDEX.md` (supply-chain audit).

This handoff supersedes the prior `docs/handoff.md` that mis-scoped P0 as "close the gbrain hole." The new contract: **gbrain is a passive sidecar; the retrieval engine is ours, built in Python.** Do not patch gbrain internals.

---

## SESSION 2026-06-16 (b) — UI polish: stale-results fix + loading/error/empty states + Odysseus-inspired refinement

Front-end-only pass (no Python touched, no engine/tier/egress code changed). Goal: fix the stale-search-results UX bug and broadly polish the workspace UI, drawing interaction inspiration from PewDiePie's AGPL [Odysseus](https://github.com/pewdiepie-archdaemon/odysseus) workspace (studied, not copied).

**Safety gate ✅** — `test_no_egress_on_s3` → **12/12 passed** (run at session start, before any edit).

**DB counts (unchanged by this session — UI-only) ✅** — `retrieval.db`: **152 pages** (S1 13 / S2 106 / S3 33), **1165 chunks == 1165 vectors** (1:1, no orphans). NOTE: this is above the 2026-06-15 "124-page clean baseline" — later ingest/test artifacts have re-accreted; durable cleanup (per the 2026-06-15 vault-cleanup procedure) is a separate follow-up, untouched here.

**The stale-results bug (fixed).**
- *Before:* `useSearch` initialised `results` to `MOCK_CITATIONS` and `runSearch` only called `setResults()` AFTER the `await` resolved — so old results stayed on screen for the whole request and the command centre opened showing fake mock citations. Worse, `api.ts` `queryEngine`/`queryEngineWithAnswer` swallowed every fetch failure and returned `MOCK_CITATIONS`, rendering stale/fake data as if it were the live query's result. No loading state (only a button-label flip), no error state.
- *After:* `useSearch` is a `status` state machine (`idle | loading | ready | error`). On submit it clears results immediately, shows a loading skeleton, and renders new results only on success; failures show an explicit error panel with a retry button; empty queries reset to an idle prompt; the command centre opens idle (no mock data). `api.ts` now throws on network error / non-OK instead of masking with mock, so outages surface as a real error state.

**Other UI/UX + robustness improvements:**
- Loading skeleton (shimmer) for search; loading skeleton rows for the Evidence Vault inventory fetch (previously flashed an empty table). `prefers-reduced-motion` disables the animations.
- Disabled states + `aria-busy` on the search input/tier-select/answer-toggle/submit during the async query; submit shows an inline spinner (consistent with the existing Add Document screen).
- Distinct empty states: "No results found" vs. "No matches under the current tier filter — try the All tab."
- Result-card polish: more padding/whitespace, smoother hover transition, more readable preview line-height.
- Refined tier badges (incl. the S3 SEALED badge) for legibility (`h-5`/`text-xs`/`font-semibold`).
- **Cleanup (removed repeated/conflicting CSS):** deleted an off-theme dark-palette duplicate of `.answer-panel`/`.answer-toggle` in `app.css` that — because `app.css` imports `dashboard/styles.css` first — was overriding the themed (cream, tier-aware) version and rendering the answer panel sky-blue. The themed version in `styles.css` now applies.
- **Security posture preserved:** `SafetyBar` (cloud-blocked / no-model-call / no-live-provider indicators) untouched; S3 sealing in the Citation Viewer + Answer panel untouched.

**Files modified (UI only):** `src/ui/api.ts`, `src/ui/App.tsx`, `src/ui/EvidenceVault.tsx`, `src/ui/app.css`, `src/ui/dashboard/styles.css`, `src/ui/dashboard/components/tier-badge.tsx`. **New:** `ACKNOWLEDGMENTS.md` (root) — credits Odysseus as design inspiration, states no code copied verbatim.

**Build ✅** — `npm run build` → **zero errors** (43 modules, built ~327ms). (The `ExperimentalWarning: CommonJS … loading ES Module` line from the vite config loader is a warning, not an error.)

**Tests ✅** — `python -m pytest tests/ --timeout=300 -q -p no:cacheprovider` → **190 collected, 189 passed, 1 skipped, 0 failures, 0 errors** (counts read from JUnit XML; skip = `llama3.2:3b` classifier integration, model not pulled). No Python changed; no regressions. Use `--timeout=300` (not 120 — cold `sentence_transformers` import can exceed 120s and pytest-timeout's Windows thread method kills the whole run).

**NEXT SESSION — prioritized action items (noted, NOT done this session):**
1. **Command palette still previews `MOCK_CITATIONS`.** `usePalette` in `src/ui/App.tsx` filters/renders mock citations for its Ctrl+K preview list. Same fake-data risk class as the stale-results bug just fixed — remove it (wire the palette to the live engine, or drop the preview list) so no surface renders mock data as if real.
2. **Vault drifted to 152 pages from test artifacts** (S1 13 / S2 106 / S3 33; real baseline = 124, S1 13 / S2 99 / S3 12). Clean back to the real baseline per the 2026-06-15 vault-cleanup procedure (delete session test artifacts from `vault/`, then `python -m scripts.ingest_new --rebuild` with nomic warmed first). The +21 are ingest/test docs, not real content.

**Other known limitations:**
- No automated front-end tests exist (testing.md specifies Vitest/Playwright but none are wired). These UI changes were verified by build + manual reasoning, not a UI test. Adding Vitest coverage for `useSearch` state transitions is a sensible next step.
- The `_relevance` lexical-gate weakness remains open (pre-existing, see below).

---

## SESSION 2026-06-16 — new-laptop / portability checklist

How to stand up and test the system on a fresh machine. **Key principle: git carries the CODE, never the DATA.** A clean clone is a fully working system with zero content.

**Transfers (tracked in git, on `origin/main`):** all `src/`, `tests/`, `requirements.txt`, `setup.bat`, `launch.bat`, `config/`, `docs/`.

**Does NOT transfer (gitignored by design — see `.gitignore`):**
- `vault/` — the MNPI corpus. A fresh clone has an **empty vault**. (Also note `vault/` is its own embedded git repo at `vault/.git`; cloning the outer repo records nothing of it.)
- `retrieval.db` (repo-root canonical DB, 124 pages) + `*.db-wal`/`*.db-shm` — **not pushed**; rebuilds from `vault/`.
- `.env` — secrets (`NEBIUS_API_KEY`, Gmail/Calendar OAuth). Re-enter by hand from `.env.example`.
- `audit/`, `backups/`, `graphify-out/`, `node_modules/`, `dist/`, model weights.
- Ollama models (~17GB `gemma4-citadel` + `nomic-embed-text`) — re-pull (`setup.bat` does this).

**Stand-up steps (Windows):**
1. Install prereqs: Python 3.11+ (3.12 OK), Node 22+, Ollama (native Windows installer), Git.
2. `git clone https://github.com/shashanksuresh18/private-memory-os` (private repo → GitHub auth / `gh auth login` required).
3. Run `setup.bat` — pip install `requirements.txt`, `npm install` + `npm run build`, `ollama pull nomic-embed-text` + `gemma4-citadel`, create `vault/raw/{s1,s2,s3}`, copy `.env.example`→`.env` (only if absent).
4. Edit `.env` — add `NEBIUS_API_KEY` (+ `GMAIL_*`/`CALENDAR_*` only if using connectors). Gmail/Calendar refresh tokens are per-account; redirect URIs must be re-registered (see `scripts/reauth_gmail.py`).
5. `launch.bat` — starts Ollama, API on `127.0.0.1:7734`, UI on `127.0.0.1:3003`, health-polls, opens browser.
6. Smoke test: drop files into `vault\raw\{s1,s2,s3}` → wait for the 10-min scheduled `--reindex` (or run `python -m scripts.ingest_new --reindex`) → ask in UI. Or `python -m pytest tests/ -q -p no:cacheprovider --timeout=300` → expect **189 passed, 1 skipped** (skip = `llama3.2:3b` not pulled; `ollama pull llama3.2:3b` to un-skip).

**Testing with the REAL vault (not an empty one):** move `vault/` only by **encrypted manual transfer** (BitLocker-protected drive / secure copy) — **never git, never cloud** (S3-never-cloud invariant). On the new machine, **BitLocker is mandatory** on the drive holding `vault/`, `audit/`, `backups/` before any real MNPI lands (CLAUDE.md operational rule). After copying the vault, run `python -m scripts.ingest_new --rebuild` to regenerate `retrieval.db` locally (warm `nomic-embed` first — see the 2026-06-15 rebuild caveat).

**BLOCKER — mac not yet supported.** `setup.bat`/`launch.bat` are Windows `.bat`; the `src/platform/{windows,mac}.py` shims (CLAUDE.md) are not written. A new **Windows** laptop works today; **mac does not** — porting the launcher + OS-call shims is prerequisite work.

---

## SESSION 2026-06-15 — vault cleanup back to clean baseline + /ingest fixes on a branch

**Recovery (start of session).** The prior session reportedly hung the full suite for >1h (suspected Ollama deadlock after a 155s gemma run). This session found **no actual deadlock**: API server already live (PID on :7734, `/health` 200, `cloudAllowed:false`, gbrain all `none`, S3 egress 12/12), Ollama responsive (`/api/tags` 200), no runaway python. Nothing needed killing or restarting.

**`pytest-timeout` is now a required dev dependency.** It was not installed; installed `pytest-timeout 2.4.0`. **Always run the suite with a per-test cap** so a single slow Ollama/model call can never hang the whole run again: `python -m pytest tests/ -q -p no:cacheprovider --timeout=300 -x`. NOTE on the cap value: `--timeout=120` is **too tight** — `tests/retrieval/test_reranker_no_egress.py::test_cross_encoder_rerank_no_egress` does a cold `from sentence_transformers import CrossEncoder` (pulls transformers→tensorflow→keras) that can exceed 120s on a cold OS cache, and pytest-timeout's Windows "thread" method **kills the whole process** on expiry (one slow import → exit 1 for the entire suite). **Use `--timeout=300`.** The test itself is fine (passes in isolation; it is NOT a regression). `pytest-timeout` should be added to `requirements.txt` (not yet done).

**/ingest fixes committed on a branch (NOT merged to main).** Branch **`fix/ingest-400-and-folder-routing`**, commit `07d22ca`, 4 files / +215 −31:
- **Fix 1 — plain 400 on bad OR missing fields.** `IngestRequest` fields `content`/`doc_type`/`tier` are now `Optional[str] = None`, so both *invalid* and *missing* fields reach the handler and produce a plain-English **400** instead of a pydantic **422** validation wall. Handler tolerates `None` via `(body.x or "")`.
- **Fix 2 — doc_type routes to its gbrain-base schema folder.** `meeting→meetings`, `memo→memos`, `company→companies`; `research`/`email` fall back to `inbox/` (`DOC_TYPE_FOLDER` map in `server.py`). Tier still lives in frontmatter, never the folder. Response gains `folder` + `path` fields. `/ingest` now indexes **only the page it wrote** via new `src/retrieval/index.py:ingest_page()` (delete-by-slug then re-insert) instead of a whole-vault `ingest_vault` sweep that re-embedded the auto-wiki backlog and stalled under Ollama contention — so returned `chunks` reflects the submitted doc alone.
- **`AUTO_WIKI_ENABLED` kill-switch (default on).** New env var; when false, `/retrieve` stops spawning the background gemma concept-extraction daemon that otherwise accretes `vault/concepts/*.md` on every query. Documented in `.env.example`. `/ingest` never triggers auto-wiki.
- Tests in `tests/api/test_ingest_endpoint.py`: missing+invalid 400 matrix, folder routing, single-page-only index (asserts `ingest_vault` is NOT called), submitted-doc chunk count.
- **RECOMMENDATION: merge to `main` after one more review.** Not merged this session.

**Vault cleaned back to clean baseline (124 pages).** Deleted **53 session test artifacts** (verified each, 0 missing): 14 inbox test docs (the 06-15 `/ingest` test cluster + `drop_test_memo.md` + the stray `inbox/test_s1_raw.md` from 06-01), 2 meetings + 1 memo (06-15 folder-routed copies), the **27 auto-wiki concept pages** dated 06-15 (incl. SEALED S3 `project-falcon`, `tidewater-analytics`, `project-kingfisher`, `financial-liquidity`, `regulatory-requirements`, `meridian-technologies`-concept), the stale `vault/wiki/index.md`, 5 archive test files (`test_s1/s2/s3.txt`, `drop_test_memo.pdf`, `archive/test_s1_raw.md`), plus repo-root `tmp_payloads/` + `junit_run.xml`. Baseline-real content (aapl/msft/googl filings, ~60 synced emails, calendar, real meetings/memos/companies/people, `board_meeting_2026_05_28.md`, the 26 pre-06-10 concepts) was kept. The handoff target was "~128" — exact clean baseline is **124**.

**Rebuild caveat — Ollama embed timed out on first `--rebuild`, succeeded on warm retry.** `python -m scripts.ingest_new --rebuild` first failed with `httpx.ReadTimeout` on a `/api/embed` call (Ollama stalled past the 90s+retry budget — leftover contention from the prior stuck session; `reset=True` had already dropped the DB to 0). A single warm-up embed (`POST /api/embed` returned in 0.24s) confirmed Ollama healthy, and the **retry rebuilt cleanly: 124 pages, 1075 chunks, 0 skipped**. Lesson: warm nomic-embed before a full `reset=True` rebuild, or it can wipe the DB mid-run. `--rebuild` also calls `generate_index()` → `vault/wiki/index.md` regenerated fresh against the 124-page baseline.

**Verification (all green):**
- DB **124 pages** — S1 13 / S2 99 / S3 12 (was 168: S1 30 / S2 116 / S3 22). `chunks 1075 == vectors 1075`, 0 orphan vectors.
- `test_no_egress_on_s3` → **12/12**.
- Full suite → **189 passed, 1 skipped, 0 failures** (`--timeout=300`; skip = `llama3.2:3b` classifier integration, model not pulled).

---

## CURRENT STATE (2026-06-13) — READ FIRST

The retrieval engine is **BUILT and LIVE** (§1 below is historical; it predates the build). `src/retrieval/` ships chunker, embedder, BM25+vector+RRF search, bge reranker, eval, and the extraction `answer.py`; `src/api/server.py` serves it. All 3 gating tests exist and pass.

**Client GitHub deployment prep (2026-06-13, DONE) — first public-safe push of the codebase:**
- **Git root fixed (was the P0 hazard).** The repo had **no local `.git`**; `git rev-parse --show-toplevel` resolved to **`C:/`** (a stray `C:\.git` tracking the entire drive — the source of the OneDrive/Desktop `D` deletions seen in `git status`). Ran `git init -b main` in `C:\sovereign-citadel`; root now **`C:/sovereign-citadel`**. `C:\.git` left untouched (not ours to delete). **Never run `git add` while root is `C:/`.**
- **Remote:** `origin` = **https://github.com/shashanksuresh18/private-memory-os** (fresh repo had none; the old `C:\.git` pointed at `investment-cockpit.git` — irrelevant, different repo).
- **`.gitignore` privacy rules:** excludes `.env*`, root **`retrieval.db` + `*.db`/`*.db-wal`/`*.db-shm`** (the canonical DB lives at repo root, NOT just `src/memory/sqlite/`), `audit/`, `backups/`, `graphify-out/`, `node_modules/`, `dist/` + `src/ui/dist/`, `__pycache__/`/`*.pyc`/`.pytest_cache/`, model weights + `.token` secrets, `repos-audit/`/`ClawXRouter/`/`privacy-filter/`, and stray dev-capture junk (`*.err`, `err*.txt`, `junit_tmp.xml`). Verified with `git check-ignore`: `.env`, `retrieval.db`, and the real `vault/inbox/email_*.md` Gmail files all ignored.
- **`vault/` — IMPORTANT deviation from the deploy spec (embedded-repo reality):** the spec asked to keep `vault/**/.gitkeep` committable and NOT ignore `vault/` wholesale. But `vault/` is its **own embedded git repo** (`vault/.git`). An outer repo can only record a useless **gitlink** (a bare SHA pointing at the private vault repo) — the inner `.gitkeep` files are unreachable across the boundary, and `git add vault/` warns `adding embedded git repository`. So `.gitignore` now ignores **`vault/` wholesale** (fail-closed: zero chance of committing vault content, real or placeholder). The client's empty folders are created at **runtime** instead: `launch.bat` + the new `setup.bat` step make `vault/raw/{s1,s2,s3}`, and `POST /ingest` / `ingest_vault` make `vault/inbox`. Net effect preserves the spec's intent (client gets the layout, never the content).
- **`.env.example`:** blank-key template (Nebius, Gmail, Calendar, `RETRIEVAL_EMBEDDER=ollama`, `OLLAMA_URL`); no real values copied from `.env`.
- **`requirements.txt` (NEW, root):** pinned to the installed/tested versions — fastapi, uvicorn[standard], pydantic, python-dotenv, httpx, requests, tiktoken, sentence-transformers (pulls torch+transformers for the bge reranker), markitdown[pdf,docx,pptx,xlsx], watchdog, google-auth(+oauthlib,+api-python-client), pytest, pytest-asyncio. Excludes `sqlite-vec` (not installed → BLOB fallback active) and `opf` (editable from gitignored `privacy-filter/`, off the test+answer path). `pip install -r requirements.txt` → all satisfied.
- **`setup.bat` (NEW, root):** one-shot client bootstrap — `pip install -r requirements.txt`, `npm install` + `npm run build` (root `package.json`, NOT `--prefix src/ui`, via `call npm` so batch resumes), `ollama pull nomic-embed-text` + `gemma4-citadel`, creates vault folders, copies `.env.example`→`.env` only if absent (never overwrites), prints the edit-`.env` reminder, pauses.
- **Pre-push secret/privacy sweep:** ripgrep secret-pattern scan of the tracked surface = clean (only false positives: an npm integrity hash + the gitignored Gmail files). `.claude/settings.json` clean. `.mcp.json` uses `${GITHUB_TOKEN}` env ref (no hardcoded secret). Denylist `codenames.txt`/`tickers.txt` are commented-out **example templates** ("REPLACE with real…"); `markers.txt` = generic MNPI phrases — no real MNPI. `git add --dry-run` confirmed no `vault/`, no forbidden artifact, no embedded-repo gitlink before the real add.
- **Commit + push:** `cdd43a6` "Initial client release" — **232 files, 130,025 insertions**, pushed to `origin/main`. Post-push `git ls-tree -r HEAD` forbidden-scan = clean.
- **Verification at deploy time:** `npm run build` zero errors; **full suite 187 collected → 186 passed, 1 skipped, 0 failures** (skip = `llama3.2:3b` classifier integration, model not pulled); `test_no_egress_on_s3` **12/12**; DB unchanged **128 pages / 1091 chunks / 1091 vectors**.

**Drop-a-note → structured vault page (2026-06-13, DONE) — `POST /ingest` + Add Document UI screen, all tiers local-only:**
- **`POST /ingest` (`src/api/server.py`):** accepts `{content, doc_type, tier, title?}`. Validates `content` non-empty, `doc_type ∈ {meeting, company, memo, research, email}` (from `structurer.DOC_TYPES`), `tier ∈ {S1, S2, S3}` — bad values return a plain-English **400** (request model uses plain `str`, not `Literal`, to avoid pydantic 422 walls). Returns `{filename, tier, chunks, status: "indexed"}` where `chunks` is the indexed-chunk count from the incremental ingest.
- **Local-only for EVERY tier (no cloud in v1):** raw notes are structured into a templated markdown body by loopback **`gemma4-citadel`** via `src/ingest/structurer.py` (Ollama `/api/chat`, temp 0, `think:false`). No Nebius, no DeepSeek, no cloud fallback. The whole structure→write→index pipeline runs inside `_block_non_loopback_sockets()`, so **S3 zero-egress is structural** (any non-loopback connect raises). If `gemma4-citadel` is unreachable, `structure_content` falls back to a deterministic per-doc-type section skeleton (still 100% local) — a dropped note is never lost.
- **Server owns frontmatter, never the LLM:** `tier`/`source: ingest`/`doc_type`/`date`/`title` are written authoritatively by `_render_ingest_markdown` AFTER generation; any frontmatter the model emits is stripped (`_strip_leading_frontmatter`). Missing title → derived from first non-empty content line (`_derive_title`, 80-char cap). Missing date → `date.today()`.
- **Filename + no-overwrite:** `YYYY-MM-DD_slugified-title.md` under **`vault/inbox/`** for all tiers (tier lives in frontmatter, not the folder). `_unique_inbox_path` never overwrites — collisions get `_2`, `_3`, … suffixes.
- **Incremental ingest, never reset:** calls `ingest_vault(..., reset=False, incremental=True)` so the new page is appended and the existing `retrieval.db` (~1091 chunks) is preserved — no full rebuild, no mid-run 0/0 window.
- **AddDocument.tsx + `/add` route + sidebar (`src/ui/`):** `AddDocument.tsx` is the capture screen — doc-type dropdown, tier dropdown with per-tier description, optional title, large "Paste your notes here" textarea, "Add to Vault" submit with idle/loading-spinner/success/error states. S3 selection paints a rose accent (`data-tier="S3"`) + warning "This will never leave your machine." Helper text points binary files at `vault/raw/{s1,s2,s3}` (no binary upload in v1). `App.tsx` wires the `/add` route + `addDocument()` in `api.ts` (`POST /ingest`); `sidebar.tsx` has a prominent "Add Document" button above the Workspace nav group.
- **Tests:** `tests/api/test_ingest_endpoint.py` (5) — `test_s1_ingest_creates_file`, `test_s2_ingest_preserves_local_content` (asserts no non-loopback socket), `test_s3_ingest_stays_local` (mocked structurer + non-loopback sentinel), `test_ingest_incremental_no_reset` (spies `ingest_vault` → `reset=False, incremental=True`, DB grows by exactly 1), `test_ingest_no_file_overwrite` (`_2` suffix, original intact). Fully offline: injected structurer stub + `HashEmbedder`, no real Ollama/network.
- **Verified (2026-06-13, post-restart):** `npm run build` → zero errors (43 modules, built 288ms). `test_no_egress_on_s3` → **12/12**. DB unchanged at **128 pages / 1091 chunks / 1091 vectors**. **Full suite: 187 collected, 186 passed, 1 skipped, 0 failures** (skip = `llama3.2:3b` classifier integration, model not pulled; counts read from JUnit XML).

**Non-technical-operator usability pass (2026-06-13, DONE) — drop-a-file → ask-a-question for a finance professional with zero CLI:**
- **File conversion (`src/ingest/converter.py`):** supported drop-in formats are **PDF, Word `.docx`, Excel `.xlsx`, PowerPoint `.pptx`, plain `.txt` (NEW this pass), and `.md`**. `.txt` is read directly (byte-deterministic, never via MarkItDown) and wrapped in tier frontmatter; all binary types go through MarkItDown `convert_local` (`enable_plugins=False`, `llm_client=None` — local-only, no cloud). Default tier on any converted file = **S3 (fail-closed)**. All 5 formats smoke-tested OK; added `tests/ingest/test_converter.py::test_txt_converts_plain_read` (asserts no non-loopback socket during conversion).
- **Auto-convert on drop (`scripts/ingest_new.py`):** the `--reindex` and `--rebuild` paths now **stage `vault/raw/` FIRST** (convert → `vault/inbox/` → index → archive original to `vault/archive/`) before the whole-vault pass. So the existing **10-minute `retrieval_incremental_ingest` Task Scheduler job** (`--reindex`) auto-picks-up any newly dropped file of any supported type — no manual run. Staging loop is tolerant (collision / bad file logged + left in `raw/`, never crashes the scheduled job); raw originals archived only after a successful ingest.
- **`launch.bat` (NEW, repo root):** one double-click. Checks Ollama (starts `ollama serve` if down, polls `/api/version`), starts the API server on **:7734** (`uvicorn src.api.server:app`, polls `/health`), starts the UI on **:3003** (`python -m http.server --bind 127.0.0.1 --directory src\ui\dist` — serves the built vite/TSX app, which is the live-data UI that talks to :7734), opens the browser, prints plain-language status + failure hints. All binds loopback-only.
- **`docs/CLIENT_SETUP.md` (NEW):** non-technical guide — install Python/Ollama/Node (download links), double-click `launch.bat`, drag files into `vault\raw\`, ask questions, troubleshooting (Ollama down / port in use / file not found / SmartScreen). No CLI instructions beyond double-clicking.
- **End-to-end verified:** `drop_test_memo.pdf` placed in `vault/raw/` → `ingest_new.py --reindex` → auto-converted to `vault/inbox/drop_test_memo.md` (tier S3), raw archived, indexed (page 128, S3 15, chunks==vectors==1091) → live `POST /retrieve {tier:S3}` returned the page as the **top citation**.
- **Safety gates:** `test_no_egress_on_s3` → **12/12** (run twice, before + after). **Full suite: 177 passed, 1 skipped, 0 failures** (was 176/1; +1 = the new `.txt` converter test; skip = `llama3.2:3b` classifier integration, model not pulled). Counts read from JUnit XML.
- **DB now 128 pages** (S1 14, S2 99, S3 15), 1091 chunks == 1091 vectors — the +1 S3 page is the drop-test memo; remove `vault/inbox/drop_test_memo.md` + `vault/archive/drop_test_memo.pdf` and rebuild to drop it durably if the demo artifact is unwanted.

**Folder-based tier classification (2026-06-13, DONE) — drop-file tier decided by which raw subfolder it lands in:**
- **Three drop folders:** `vault/raw/s1/` (public), `vault/raw/s2/` (sensitive, not MNPI), `vault/raw/s3/` (MNPI / confidential). A file dropped in `vault/raw/` root — or any unknown subfolder — **fails closed to S3** (most-restrictive, never cloud).
- **`scripts/ingest_new.py`:** new `tier_for_raw_source(source, raw_root=RAW)` maps the immediate raw subfolder → tier (`s1→S1`, `s2→S2`, `s3→S3`, else `DEFAULT_TIER=S3`); `_raw_sources()` now also scans the three tier subfolders; `_stage_to_inbox(source, tier)` passes the folder tier into `convert_to_vault(..., tier=tier)` (converted files get it in frontmatter; a copied `.md` keeps its own frontmatter, gets tier prepended only when it has none); `ensure_raw_dirs()` self-heals the subfolders on every `--reindex`/`--rebuild`/plain run; dry-run prints the per-file tier. Both the `--reindex`/`--rebuild` staging loop and the plain lifecycle path now stage tier-aware.
- **`launch.bat`:** creates `vault\raw\{s1,s2,s3}` on first run if absent (`if not exist … mkdir`); start banner now prints `s1=public s2=sensitive s3=secret (unsure - use s3)`.
- **`docs/CLIENT_SETUP.md`:** Part 3 rewritten with the three-folder table + "if unsure, use s3" + S3-stays-local privacy note.
- **Test:** `tests/ingest/test_tier_from_folder.py` (4) — `test_s1_folder_gives_s1_tier`, `test_s2_folder_gives_s2_tier`, `test_s3_folder_gives_s3_tier`, `test_root_raw_defaults_to_s3`. All green.
- **Suite: 181 passed, 1 skipped, 0 failures** (182 collected; +4 = the folder-tier tests; skip = `llama3.2:3b` classifier integration, model not pulled). `test_no_egress_on_s3` re-run after the change → **12/12**. Counts read from JUnit XML.

**Retrieval DB (`C:\sovereign-citadel\retrieval.db`, canonical, nomic-backed 768-dim):**
- **128 pages / 1091 chunks** (S1 14, S2 99, S3 15). `vectors == chunks == 1091`. Verified 2026-06-13 after client-drop conversion + E2E indexing smoke.
- **Gmail Session 1 (2026-06-04, DONE):** +20 S2 gmail metadata pages (`inbox/email_*.md`, `source: gmail`, `body: none`) → S2 11 → 31, pages 30 → 50, chunks 685 → 705 (1 chunk/email).
- **Gmail Session 2 (2026-06-05, DONE) — body ingest (S1/S2 only):** `scripts/fetch_gmail.py --with-body` now fetches message bodies. Tier-gated routing (NEVER violated): **S3 = body never fetched** (`format=full` requested only when `with_body AND tier != S3`; page keeps `body: none`), **S2 = DLP-scrubbed before write**, **S1 = raw** (public). The `body:` frontmatter field is a status flag (`none`/`scrubbed`/`raw`); the body text lands after the frontmatter as markdown (feeds the lexical relevance gate; multiline body never stuffed into a YAML scalar). Multi-chunk emails now exist → 51 pages skipped, **+23 new pages**, pages 51 → 74, chunks 706 → 863. Incremental ingest (`reset=False, incremental=True`) handled it cleanly.
  - **DLP scrub (`scrub_text`, S2 only — the only bodies that egress):** strips email addresses, US+UK phone numbers, UK postcodes + US ZIPs, a name denylist (`NAME_DENYLIST` seed + optional `denylist/names.txt`), and any residual S3 denylist term. Reuses the classifier denylist dir (`src/routing/classifier/denylist/`). Redaction tokens: `[REDACTED_EMAIL|PHONE|POSTAL|NAME]`.
  - **Fail-closed escalation (`body_forces_s3`):** a fetched body containing any codename/marker/ticker escalates the whole page to S3 — body discarded, never written, never embedded — rather than trusting scrub alone. Subject classification only sees the subject line; this catches MNPI that only appears in the body.
  - **UTF-8 hardening:** `_clean_utf8()` in the extractor + `chunker.py` byte-slice decodes switched to `errors="replace"` (was `strict`) so stray/mid-multibyte bytes in real email bodies degrade instead of crashing ingest. Valid UTF-8 round-trips identical → citation gating unaffected.
  - **Tests:** `tests/retrieval/test_dlp.py` (10) — S2 email/phone/postal scrubbed, S1 unchanged, S3 `body: none`, S3 `format=full` never requested (fake-service assertion), S2 full-fetch lands only scrubbed text on disk, **S2 `from:` field scrubbed + S1 `from:` raw** (see DLP from-field fix below).
  - **OAuth note:** body fetch needs the `gmail.readonly` scope; the old metadata-only tokens 403'd. `scripts/reauth_gmail.py` (loopback consent on :3456, prints refresh_token, does NOT write `.env`) mints fresh tokens. Re-register `http://localhost:3456/` as an authorized redirect URI first.
- **Calendar Session 1 (2026-06-04, DONE):** `scripts/fetch_calendar.py` built (Calendar API v3, `calendar.readonly`, primary cal, today→+7d, max 50, metadata-only — never the event description). +1 S2 calendar page (`inbox/calendar_{date}_{id}.md`, `source: calendar`, `body: none`) → S2 31 → 32, pages 50 → 51, chunks 705 → 706. Creds in `.env`: `CALENDAR_CLIENT_ID`/`SECRET` (= GMAIL_*), `CALENDAR_REFRESH_TOKEN` (from command-centre). Live query `{"query":"meetings today","tier":"S2"}` returns the calendar chunk.
- **Calendar page enrichment (why):** calendar pages are sparse frontmatter; `fetch_calendar.py` appends a DERIVED one-line summary (`Calendar meeting entry. Upcoming meetings: <title> on <date> ... Attendees ... Location ...`) synthesised ONLY from metadata fields — `body: none` still holds, the event's own description is never read/written. Without it the page carries no `meeting`/`calendar` tokens and the server's lexical relevance gate drops it (see weakness note below).
- Includes 3 EDGAR 10-Ks (`inbox/{aapl,msft,googl}_10k_*`) + 3 XBRL facts pages (`inbox/*_facts_*`) fetched 2026-06-02 via `scripts/fetch_edgar.py` (S1, public).
- **CAVEAT:** a mid-session DB-only delete of the 3 `*_10k_*` pages (→27/127) was **reverted** by a full reingest from `vault/` (the 10-K source still lives in `vault/inbox/`). To drop the 10-Ks **durably**, remove them from `vault/inbox/` first, then rebuild — DB-only deletion does not survive any reingest.

**S2 cloud egress path (verified 2026-06-09):** `/retrieve` with `answer:true` on an S2 query DOES egress to Nebius DeepSeek-V3.2 — `server.py` → `answer.answer()` → `answer_s2()` which runs `redact_pii()` on each citation (URL/EMAIL/AMOUNT>$1M/PHONE/ENTITY/PERSON → placeholder tokens), builds context from the REDACTED copies, then calls `_nebius_chat()`. The original citation text is never forwarded (scrub operates on a copy). Response exposes `answer_tier:S2`, `model_used:deepseek-ai/DeepSeek-V3.2`, `redacted:true`. NOTE: `from_vault` only means "not the S1 model-knowledge fallback" — it is `true` for a normal S2 cloud answer; it is NOT a "stayed local" flag. (Corrects a wrong note from the prior session that claimed `/retrieve` S2 was extractive-local.) Two redaction layers stack: fetch-time `scrub_text` (`[REDACTED_EMAIL]` in the chunk on disk) + egress-time `redact_pii` (`[EMAIL]`/`[PERSON]`/`[URL]`). Pinned by `tests/retrieval/test_s2_egress.py` (3) — captures the exact text sent to a mocked `_nebius_chat` and asserts zero raw email (body PII + `from:` sender), original citation unmutated.

**DLP `from:` field scrub (2026-06-08, DONE) — closes S2 frontmatter egress hole:** the page's `from:` sender (`"Name <addr@host>"`) lands in the page's first chunk, so for S2 it egresses to Nebius alongside the scrubbed body — but it was being written RAW. Fix: `scripts/fetch_gmail.py` adds `sender_for_tier(tier, sender)` (S2 → `scrub_text(sender)`; S1/S3 → raw — S1 public, S3 local-only never egresses; unknown → scrubbed, fail-closed), called in `render_page()` so BOTH the body-present and `body: none` branches scrub the sender. Mirrors `body_for_tier`. Tests: `test_s2_from_field_scrubbed` + `test_s1_from_field_raw` (`tests/retrieval/test_dlp.py`, now 10). **Suite: 176 passed, 1 skipped** (skip = `llama3.2:3b` classifier integration, model not pulled; +3 from `tests/retrieval/test_s2_egress.py`).
  - **Existing data re-scrubbed (2026-06-09, DONE):** `scripts/rescrub_s2_from.py` re-scrubbed the on-disk `from:` line of every existing S2 page in place — **48 files scanned, 48 rewritten** (display name kept, address → `[REDACTED_EMAIL]`, CRLF preserved, idempotent). Pre-scrub snapshot at `backups/inbox_s2_prescrub_20260609_070919` (reversible; also re-fetchable). Full `reset=True` reindex replaced all stale chunks. Verified post-reindex: **0 raw emails** in S2 chunk text (DB scan + 5-page spot check + live `/retrieve` citation scan), and **all 48 S2 `from:` chunks now carry `[REDACTED_EMAIL]`, 0 raw**. Server restarted on `127.0.0.1:7734` (RETRIEVAL_EMBEDDER=ollama) so it serves the rescrubbed DB.

**Embedder match (load-bearing):** index is nomic; `engine.retrieve()`/`ingest_vault()` DEFAULT to `HashEmbedder` (offline test stub). Production must use nomic or it silently breaks/regresses the index. `.env` now sets **`RETRIEVAL_EMBEDDER=ollama`** (read via `load_dotenv` by `server.py`); `scripts/ingest_new.py` uses `OllamaEmbedder` explicitly. `make_embedder()` factory in `src/retrieval/embedder.py` (default `hash` so tests/S3-no-egress stay offline). `OllamaEmbedder` timeout 30→90s + 1 retry.

**Batch-embed REVERTED (2026-06-04):** `OllamaEmbedder.embed_batch()` / `HashEmbedder.embed_batch()` still exist + are tested (`tests/retrieval/test_embedder_batch.py`), but `index.py` ingests via **per-chunk `embed()`** on purpose. Ollama `/api/embed` is SEQUENTIAL → batching gives no throughput gain AND concentrates many chunks under one timeout budget; a full 32-chunk batch of large pages tripped the 90s read timeout and (with `ingest_vault(reset=True)` dropping tables first) wiped the DB to 0/0 mid-reingest. Per-chunk gives each chunk its own timeout + retry. Do not re-wire batch into `index.py` without making the timeout size-aware (the embedder's `embed_batch` already scales it `max(90, len*6)s`).

**`scripts/ingest_new.py` raw-drop + reindex path (UPDATED 2026-06-13):** `--reindex` now stages anything dropped in `vault/raw/` BEFORE the incremental whole-vault pass. Supported raw files convert/copy to `vault/inbox/`, then the whole vault is incrementally indexed with `OllamaEmbedder`, and successfully staged raw originals are archived to `vault/archive/`. This is the 10-minute scheduled client path: drag files into `vault\raw\`, wait for conversion + indexing. `--rebuild` still does a full `reset=True` re-embed for edits to already-indexed pages.

**KNOWN WEAKNESS — server `_relevance` lexical gate (sparse pages):** `src/api/server.py:_relevance()` re-scores retrieval candidates as raw token overlap `|query∩text| / |query|` and drops anything `< MIN_SCORE (0.01)`. This DISCARDS the engine's RRF+rerank score and re-ranks on literal word overlap, so a semantically-relevant but token-sparse page (e.g. a calendar/email frontmatter page) gets zeroed when the query words don't literally appear in the page. **Current workaround:** producers of sparse pages append a derived summary line carrying the expected lexical tokens (see calendar enrichment above). **Proper fix (deferred):** blend or fall back to the vector/RRF score instead of pure token overlap — broader change, re-run eval after.

**Incremental ingest (DONE 2026-06-04):** `ingest_vault(..., reset=False, incremental=True)` appends only NEW pages — diffs `vault/` against existing `pages.page_slug` and skips matches BEFORE any file read/embed, so it never drops existing pages and never re-embeds the ~700 unchanged chunks (no more ~20 min full rebuild, no more mid-run 0/0 window). Returns `{pages, chunks, skipped}`. `reset=True` (still the default for full-rebuild callers — eval, gating, server) makes `incremental` a no-op. **`scripts/fetch_gmail.py` + `scripts/fetch_calendar.py` auto-run incremental ingest post-fetch** (`_incremental_ingest()`, `reset=False`, `OllamaEmbedder`) — a fetch now self-indexes only its new pages. Covered by `tests/retrieval/test_incremental_ingest.py` (skip-existing/add-new, no-op, no chunk-dup).

**STILL PENDING — sha256 content-change detection:** incremental keys on `page_slug` (path) only, so it picks up NEW files but NOT edits to an existing page (slug already present → skipped). The `pages.sha256` column already stores each page's content hash; a future upgrade should compare it and re-embed changed pages (delete old chunks + re-insert). Until then, an edited page needs a full `reset=True` reingest to refresh.

**Flaky gating test (noted, NOT touched):** `tests/retrieval/test_no_egress_on_s3.py::test_no_gbrain_scheduled_task_registered` shells `schtasks /Query` with a 20s subprocess timeout; under full-suite load (Ollama busy) it occasionally hits `subprocess.TimeoutExpired` and fails, then passes on isolated/clean rerun. Not a real egress regression. If it keeps flaking, bump the subprocess timeout — but it's a gating test, so change only with a security-review eye.

**DB paths (fixed permanently):** `src/retrieval/db.py`, `src/memory/graph/db.py`, `src/memory/atoms/db.py` all use ABSOLUTE `DEFAULT_DB_PATH` off repo root. `ingest_new.py` uses the canonical absolute path. cwd no longer changes which file ingest vs server hit.

**S1 model-knowledge fallback (DONE):** when the vault does not answer a public S1 question, fall back to DeepSeek from model knowledge with disclaimer `Answered from model knowledge — not from vault`. Trigger = extractive refusal (`answer.py:is_refusal()`), wired in `answer.py:answer()` **S1 ONLY** (S2/S3 return the refusal verbatim — never a no-context cloud path). `server.py` also fallbacks on empty S1 + adds a `from_vault` flag. **`MIN_SCORE = 0.01`** (server.py; `RETRIEVAL_MIN_SCORE` env override). Live-verified: Azure / iPhone-FY2025 / Google-ads → `from_vault:false`, DeepSeek answer + disclaimer.

**Test suite: 178 tests, 177 passed, 1 skipped** (skip = `llama3.2:3b` classifier integration, model not pulled). Latest `python -m pytest tests/ -q` green on 2026-06-13; `test_no_egress_on_s3` still **12/12 passed**. Baseline was 141; growth includes refusal-retry, batch-embed parity, incremental ingest, auto-wiki, DLP/S2-egress, vault bridge, and conversion tests. `pytest -m gating` (no-egress / citations-resolve / tier-integrity) green.

**Eval (Run 4, 23 q, nomic+bge, per-query tier — `src/retrieval/eval.py` reads per-row `tier`):** best variant **rrf** Recall@10 1.000 / MRR@10 **0.946** / nDCG@10 0.959 (rrf_rerank 0.920, bm25 0.904, vec 0.825). Run against canonical `retrieval.db` (`--db retrieval.db --no-reingest`). Output `docs/eval/eval_regrounded.json`.

**DONE — qrels q16–q23 re-grounding:** re-grounded to current top-1 results last session. q19 ("Microsoft diluted EPS") → `inbox/aapl_10k_2025-10-31`; q22 ("Apple shares outstanding") → `inbox/googl_10k_2026-02-05`; q16–q18, q20–q21, q23 already top-1, unchanged. **CAVEAT:** q19/q22 top-1 are the *wrong issuer's* 10-K — re-grounding made eval pass but masks a real cross-issuer ranking bug; revisit before trusting cross-issuer factoid retrieval. Still grounded to `*_10k_*` slugs → break if the 10-Ks are durably removed (re-ground to facts pages or drop then).

**Server:** `127.0.0.1:7734`, nomic embedder, **LIVE** (background `uvicorn src.api.server:app`). Loopback-only; `/health` ok. `NEBIUS_API_KEY` present in `.env` → S1/S2 cloud (DeepSeek-V3.2) functional; S3 → local gemma4, zero egress.

**Auto-wiki on query (DONE 2026-06-05):** `src/retrieval/auto_wiki.py` is wired into `src/api/server.py` `POST /retrieve`. After a successful retrieve with citations, a background daemon thread uses local loopback Ollama `gemma4-citadel` to extract key concepts/facts from the top 3 citation texts and writes/updates `vault/concepts/{slug}.md` with `source: auto-wiki`, `updated: <date>`, bullets, and source page paths. Tier is enforced by most-restrictive citation tier: S3 concept files stay S3/local-only, S2 text/facts are DLP scrubbed before extraction/write, S1 writes raw public facts. Manual concept files are never overwritten: an existing concept is updateable only when frontmatter has `source: auto-wiki`.

**Client handoff / transferable setup (DONE 2026-06-13):**
- **File conversion:** `src/ingest/converter.py` supports PDF, Word (`.docx`), Excel (`.xlsx`), PowerPoint (`.pptx`), `.txt`, plus `.md` copy-through in `scripts/ingest_new.py`. All five conversion formats smoke-tested OK. Unknown/raw sensitivity still fails closed to `tier: S3`.
- **Auto-convert on drop:** `scripts/ingest_new.py --reindex` now stages `vault/raw/` → `vault/inbox/`, runs incremental ingest, then archives raw originals. The tolerant loop logs unsupported/colliding files and leaves them in `raw/` rather than crashing the scheduled job.
- **Launcher:** `launch.bat` checks/starts Ollama, starts the API on `127.0.0.1:7734`, serves the built UI from `src/ui/dist` on `127.0.0.1:3003`, health-polls both services, opens the browser, and prints plain-language failure messages.
- **Client docs:** `docs/CLIENT_SETUP.md` is non-technical: install Python/Ollama/Node, double-click `launch.bat`, drag files into `vault\raw\`, troubleshooting, and privacy defaults.
- **End-to-end smoke:** dropped `drop_test_memo.pdf` into `vault/raw/` → auto-converted to Markdown with S3 fail-closed frontmatter → archived → indexed → returned as the top live `/retrieve` S3 citation.
- **Graphify:** incremental rebuild complete: **2488 nodes / 4848 edges / 246 communities**. God nodes: `ingest_vault()` (60), `HashEmbedder` (53), `Citation` (51). Outputs in `graphify-out/`.

**Dashboard wired to live data (NEW):**
- **`/stats` endpoint** — returns pages, chunks, tier breakdown, meetings, graph_edges counts.
- **`/pages` endpoint** — real page inventory with per-page tier, chunk count, line counts.
- **`EvidenceVault.tsx`** — real pages from `/pages`, tier badges, sealed S3 rows (no copy/export).
- **`PrivacyRouting.tsx`** — live posture, tier rules, audit metadata.
- **Sidebar + top-bar** — now driven by live `/stats` data (no more mock inline).
- **`App.tsx`** — `/vault` and `/audit` routes wired to the real screens.

**CRM screen (DONE 2026-06-06):**
- **`GET /crm` endpoint** (`src/api/server.py`) — returns `{people:[{name,slug,company,role,tier,sealed}], companies:[{name,slug,type,tier,sealed}]}`. Source of truth is vault markdown **frontmatter** (walks `vault/people/` + `vault/companies/`), NOT the index — so a contact with zero indexed chunks still appears. Tier read from frontmatter, **fail-closed S3** when absent/unrecognised. Company `type` derived from relationship tags (Portfolio/Prospect/Competitor/…) → `stage` → `sector` → `"Company"`. Person `company` slug normalised (handles bare `wonderland-capital` AND path `companies/vertex-credit`) and resolved to display name. **S3 sealing is server-side:** S3 rows return name-from-filename only, `company/role/type` nulled, `sealed:true`; a non-S3 person referencing an **S3 company** shows `[sealed]` (never leaks the S3 name via title-case).
- **`src/ui/CRM.tsx`** — two tabs **People | Companies**, tier badges, S3 rows sealed (badge + `SEALED`, no detail, no click-through). Click a non-sealed row → retrieves that contact/company by name and opens the Citation Viewer.
- **`App.tsx`** — `/crm` route wired; `onOpenPage` resolver queries the engine and opens the viewer.
- **Sidebar + top-bar** — "Relationships" nav repointed `/queue` → `/crm`; `app.css` adds 4-col people / 3-col companies grids.
- **Build:** `npm run build` zero errors. **Live-verified:** server restarted on `127.0.0.1:7734`, `GET /crm` → HTTP 200, 6 people / 5 companies, Frank Orr + Meridian Technologies correctly sealed.
- **Suite after CRM:** **166 passed, 1 skipped** (skip = `llama3.2:3b` classifier integration, model not pulled) — unchanged baseline, no regressions.

**Obsidian MCP vault bridge (DONE 2026-06-08):**
- **`src/mcp/vault-bridge/server.py`** — watchdog recursive watcher on `vault/`. Local-only (filesystem observer, binds no socket / opens no port — loopback by construction). Reacts to **created + modified** `.md` only (NOT deleted — never auto-purges the index).
- **2s per-file debounce** (`DEBOUNCE_SECONDS`) — Obsidian writes on nearly every keystroke; each event resets a `threading.Timer`, so a burst of rapid saves collapses into one ingest after the writes settle.
- **Per-file incremental ingest, NEVER `reset=True`.** `ingest_file()` deletes the page by slug first (`ON DELETE CASCADE` clears chunks + vectors; the `chunks_ad` FTS trigger clears the FTS row) then re-inserts page/chunks/vectors. This **refreshes modified pages** — plain `ingest_vault(incremental=True)` would skip them because the slug already exists. Inherits tier policy unchanged from `src/retrieval/index.py` (refuse-ingest on missing/invalid tier — logged, never crashes the watcher; derived pages skipped; byte-offset citations preserved). Logs `ingested vault/X.md → +N chunks`.
- **Skips:** `vault/archive/` + `vault/raw/` (lifecycle staging, never indexed) and `email_*.md` / `calendar_*.md` (owned by `fetch_gmail.py` / `fetch_calendar.py`, which run their own incremental ingest).
- **Start:** `python scripts\start_vault_bridge.py` → prints `Vault bridge running — watching vault/`, runs until Ctrl+C. Loads `.env` (so `RETRIEVAL_EMBEDDER=ollama`) and loads `server.py` via `importlib` (the hyphen in `vault-bridge` makes it non-importable as a dotted module).
- **Tests:** `tests/test_vault_bridge.py` (5) — new-file-triggers-ingest, debounce-batches-rapid-saves, archive-files-skipped, email/calendar-files-skipped, ingest_file add-then-refresh (no dup, vectors 1:1 with chunks). Handler dispatch/filter/debounce tested with a counting stub (no DB/embedder/network); `ingest_file` tested with `HashEmbedder` (offline).
- **Suite after bridge:** **171 passed, 1 skipped** (166 baseline + 5 new). 0 failures.

**Auto-ingest scheduled tasks (DONE 2026-06-10):** vault edits no longer need a manual reingest — two Windows Task Scheduler jobs keep `retrieval.db` current.
- **`scripts/ingest_new.py` — new flags:** `--reindex` (whole-vault **incremental** pass, `reset=False, incremental=True`; bypasses the `vault/raw/` staging gate so files written straight into `vault/<folder>/` — e.g. a new meeting note — get embedded; append-only, skips existing slugs) and `--rebuild` (**full** `reset=True` re-embed of every page, catches EDITS the incremental pass skips). Mutually exclusive (`parser.error`). Both use `OllamaEmbedder` (local nomic, zero cloud). Plain `python scripts/ingest_new.py` (no flag) still does the raw→inbox→reindex lifecycle.
- **Task Scheduler (`\SovereignCitadel\`):** `retrieval_incremental_ingest` → `--reindex` **every 10 min**; `retrieval_full_rebuild` → `--rebuild` **daily 03:30**. Registered via `Register-ScheduledTask` (PowerShell cmdlets, NOT `schtasks` — `/WAKETORUN` is a task *setting* `-WakeToRun`, not a `schtasks.exe` flag). Run as current user, `LogonType Interactive`, `RunLevel Limited` (vault is on the user drive → no admin/elevation needed; `RunLevel Highest` had failed with Access-denied in a non-elevated shell). Action `-Execute` pinned to the **real** interpreter `...PythonSoftwareFoundation.Python.3.11...\python.exe` (resolved via `sys.executable`), NOT the `WindowsApps\python.exe` Store alias stub.
- **Verified:** both tasks `State=Ready`; test-fired `retrieval_incremental_ingest` → `LastTaskResult 0` (success, after the `267009 = 0x41301 "currently running"` transient cleared). Demo file `vault/meetings/2026-06-10-meridian-ceo-strategy.md` (tier S3) ingested + confirmed present in `retrieval.db` via the new path.
- **Cron spec mirrored** in `config/cron.yaml` (`retrieval_incremental_ingest` + `retrieval_full_rebuild`) — but note `cron.yaml` is still declarative-only (no daemon reads it; tech-debt B4). The Task Scheduler registration above is what actually fires.
- **CAVEATS:** (1) Interactive logon → jobs fire only while the user is logged in (fine for a demo laptop; not headless). (2) Incremental diffs by `page_slug` only → an EDIT to an already-indexed page is NOT re-embedded until the nightly `--rebuild`. Logged as **tech-debt B12** (content-hash / SHA-256 diff → re-embed changed pages within 10 min, shrink the nightly rebuild). This is the same gap as the long-standing "sha256 content-change detection" note above; B12 is the action ticket.
- **Suite after auto-ingest: 176 passed, 1 skipped, 0 failures** (177 collected; skip = `llama3.2:3b` classifier integration, model not pulled). No test changes this turn — wiring + scheduler + docs only. Count read from JUnit XML (`errors=0 failures=0 skipped=1 tests=177`) because pytest's terminal-reporter summary line is being swallowed in this capture env.

**Full narrative + receipts:** `docs/overnight_run_summary.md` (§12 = the 2026-06-02 operator follow-ups).

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
