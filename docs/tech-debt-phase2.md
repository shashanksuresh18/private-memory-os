# Technical Debt — Phase 2 (post-MVP)

Logged 2026-05-28. Boot-gate explicitly overridden by operator to unblock 1-Week MVP build.
Re-enable before any real MNPI lands in vault/.

## Security Findings Not Yet Resolved

### B1. BitLocker on system drive — UNVERIFIED
- `Get-BitLockerVolume` requires admin; current session non-elevated.
- Action: re-run `scripts/security_baseline.ps1` (no `-SkipBitLocker`) from an elevated PowerShell.
- Acceptance: exit 0 without flag.

### B2. OneDrive Known Folder Move — UNVERIFIED
- Project lives under `~/Desktop`. If KFM is enabled for Desktop, the entire repo (including `vault/`, `audit/`, `backups/`) is syncing to Microsoft cloud right now.
- Action: Settings -> OneDrive -> Backup -> Manage backup. Confirm Desktop OFF.
- Alternative: move repo to `C:\sovereign-citadel\` (outside any synced root).

### B3. Windows Search content-index exclusion at OS level
- `NotContentIndexed` attribute set on `vault/`, `audit/`, `backups/` (recursive). File-attribute alone is not always honored on Win 11 builds.
- Action: Settings -> Search -> Searching Windows -> Excluded folders -> add absolute paths.

### B4. Hourly cron / Task Scheduler wrapper for `verify_chain.py`
- `config/cron.yaml` references the job; no Windows Task Scheduler registration yet.
- Action: build `scripts/install_audit_cron.ps1` to register a SYSTEM-context scheduled task.

### B5. Tier-classifier admin CLI + operator-confirm queue for first S2 egress
- Classifier currently auto-decides without operator approval on first-time S2 patterns.
- Action: build `tools/admin/classifier_cli.py` with confirm-queue and audit log.

### B6. OPF service integration test (live POST against FastAPI app)
- Unit tests cover gates in isolation; no end-to-end "real request hits real OPF" test.
- Action: `tests/firewall/test_opf_integration.py` with FastAPI TestClient.

### B7. Live BitLocker telemetry / drift watcher
- Baseline runs at boot. No watcher catches *runtime* disable.
- Action: Phase 2 background daemon polling BitLocker + OneDrive state every 30 minutes.

### B8. Real model SHAs pinned for Ollama
- `config/cron.yaml` references `src/models/ollama/SHAS.txt`; file does not exist.
- Action: pull intended models, capture sha256 of GGUF blobs, commit pin file.

### B9. Python CRM (`src/crm.deprecated/`) decision finalization
- Renamed from `src/crm/` on 2026-05-28 when we pivoted to `garrytan/gbrain` as the CRM substrate. Smoke-tested but never wired to UI.
- Action options before v1:
  - DELETE `src/crm.deprecated/` entirely once gbrain CRM workflows are exercised and confirmed.
  - OR keep as the fallback path if gbrain proves too heavy on Windows + we need a pure-Python CRM after all.
- Decision deadline: end of MVP week. No third option.

### B10. gbrain bootstrap not yet run on this host
- `scripts/install_gbrain.ps1` is written but Bun + gbrain are not yet installed on the Windows host. Vault templates land regardless.
- Action: run `powershell -ExecutionPolicy Bypass -File scripts/install_gbrain.ps1` from project root.
- Acceptance: `gbrain doctor` exits 0; `gbrain search "Alice"` returns the seed `vault/people/_template.md` page.

### B12. Content-hash diff for incremental ingest
- `scripts/ingest_new.py --reindex` (cron `retrieval_incremental_ingest`, every 10 min) diffs the vault by `page_slug` existence only, NOT content. A NEW file is embedded within 10 min, but an EDIT to an already-indexed page is skipped until the nightly `--rebuild` full re-embed (cron `retrieval_full_rebuild`, 03:30).
- Action: make incremental ingest store + compare a per-page content hash (SHA-256 of source bytes) and re-embed any page whose hash changed. Lets edits land within 10 min and lets us drop / shrink the nightly full rebuild.
- Acceptance: edit an existing vault page → within one incremental cycle, search returns the new text; unchanged pages still skipped (no full re-embed).

## Reactivation Checklist (before first MNPI)

- [ ] B1 BitLocker passes elevated baseline
- [ ] B2 OneDrive KFM confirmed OFF or repo relocated
- [ ] B3 Windows Search exclude folders added
- [ ] B4 Audit cron registered + verified for 24 hours
- [ ] B5 Operator-confirm queue live + 1 round of staged S2 dry-runs
- [ ] B6 OPF integration test green in CI
- [ ] B7 Drift watcher logged 24 hours of healthy state
- [ ] B8 Ollama model SHAs pinned + re-verified
