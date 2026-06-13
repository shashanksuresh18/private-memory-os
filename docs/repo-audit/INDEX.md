# Sovereign Citadel — Repo Audit Index

Generated: 2026-05-28 (Scrapling + shallow clone + pattern scan)

## Verdict Matrix

Risk tiers from: stars vs commits, license validity, MNPI hot-path role,
supply-chain signals (telemetry, eval/exec, curl|bash, hardcoded API keys, AWS keys),
single-maintainer bus-factor.

| Repo | Stars | Commits | License | Risk | MNPI role | Verdict |
|---|---:|---:|---|:--:|---|---|
| `D4Vinci/Scrapling` | 54.5k | 1,444 | BSD-3 ✓ | LOW | tooling only | **OK** — supply-chain scraper. |
| `OpenBMB/EdgeClaw` | 1.2k | 24,491 | MIT ✓ | HIGH | local OS / agent loops | 10,236 files, 42 curl\|sh, 125 eval/exec, 931 URLs, 39 telemetry. **Zero-egress VM only.** |
| `OpenBMB/ClawXRouter` | 174 | 72 | MIT claimed, **no LICENSE in repo** | HIGH | **MNPI hot path** (tier router) | Legal gap. Fork to your org, add LICENSE, pin SHA before wiring. |
| ~~`privacyshield-ai/privacy-firewall`~~ | 237 | 19 | **MIT template UNFILLED** | DROP | n/a | Chrome extension, architecture mismatch. **REPLACED by `openai/privacy-filter`.** |
| `openai/privacy-filter` (`opf`) | 2,285 | 3 | **Apache 2.0 ✓** | LOW | **Tier S2 DLP** (NEW) | 1.5B-param bidirectional token classifier, 128k context, 8 PII categories, CPU/GPU. 45 files, 0 telemetry, 0 curl\|sh, 0 AWS keys. Clean Torch+safetensors+tiktoken stack. **APPROVED.** |
| `tinyhumansai/openhuman` | 28.8k | 2,442 | GPL-3 ✓ | MED | persistent memory + ingest | **121 telemetry hits**, 19 api-key literals, 12 curl\|sh. Isolated microservice over net API to bound GPLv3 contagion. |
| `garrytan/gbrain` | 19.4k | 268 | MIT ✓ | MED | memo schema + mutex | 7 curl\|sh, 88 eval/exec, 12 telemetry, 8 api-key literals. Pin SHA. |
| `affaan-m/ECC` | 195,900 | 1,994 | MIT ✓ | MED | wrapper / token-opt | Star count inflated. AWS key literal in clone. **Strip credentials + telemetry, compile manually (never npx).** |
| `massgen/MassGen` | 1.0k | 3,916 | Apache 2 ✓ | MED | S1 multi-agent council | 15 curl\|sh, 22 eval/exec, 11 shell=True, 6 telemetry, AWS key literal. S1-only blast radius. |
| `safishamsi/graphify` | 54.9k | 560 | MIT ✓ | LOW | knowledge graph | Installed globally (v0.8.21). 2 curl\|sh, 4 telemetry — review. |
| ~~`jlevere/obsidian-mcp-plugin`~~ | 12 | 155 | MIT ✓ | DROP | n/a | 12 stars, 10mo stale. **REPLACED by `@bitbonsai/mcpvault`.** |
| `@bitbonsai/mcpvault` | 1.3k | 180 | MIT (pkg.json) ✓ | LOW | **MCP egress** (NEW) | CHANGELOG, SECURITY.md, AGENTS.md, vitest. v0.11.2 on npm. `.base` + `.canvas` support, `list_all_tags`, dotted folder safety. **APPROVED.** |

## Decisions (locked 2026-05-28)

### S2 Firewall
- **Approved:** `openai/privacy-filter` (Apache 2.0, PyTorch, `opf` CLI, on-prem, fine-tunable, 8 PII categories)
- **Rejected:** `privacyshield-ai/privacy-firewall` (Chrome extension misclassified as server-side DLP; unfilled LICENSE template)
- **Folder:** `src/firewall/opf/` (renamed from `src/firewall/ner-onnx/`)

### MCP Vault Bridge
- **Approved:** `@bitbonsai/mcpvault` (npm, v0.11.2, native `.base`/`.canvas`)
- **Rejected:** `jlevere/obsidian-mcp-plugin` (12 stars, 10mo stale, bus factor 1)
- **Folder:** `src/mcp/vault-bridge/`

### High-Risk Containment
- `EdgeClaw`, `openhuman`, `ECC` run inside **zero-egress sandbox** (Hyper-V VM or Docker network with `iptables` outbound-deny default + whitelist: Anthropic API endpoint for S1 only, local Make.com webhook).
- `openhuman` runs as **isolated microservice over network API boundary** to bound GPLv3 contagion (prevents your proprietary financial routing logic from becoming open-source).
- `ECC` cloned, telemetry stripped, AWS-key-literal removed, compiled manually. **Never `npx`-installed.**

### Legal Gaps
- `OpenBMB/ClawXRouter`: no LICENSE in repo → fork to your private GH org, add `LICENSE` from `OpenBMB/OpenClaw` parent, pin SHA in `src/routing/policies/SHAS.txt`.

## Required User Actions (cannot run on your behalf — need GH creds)

```bash
export GH_ORG="YOUR_ORG_NAME_HERE"

# 1. Fork + LICENSE-patch ClawXRouter
gh repo fork OpenBMB/ClawXRouter --org $GH_ORG --clone
cd ClawXRouter
curl -s https://raw.githubusercontent.com/OpenBMB/OpenClaw/main/LICENSE > LICENSE
git add LICENSE && git commit -m "chore: add missing MIT license for compliance"
git push origin main
cd ..

# 2. Fork S2 firewall
gh repo fork openai/privacy-filter --org $GH_ORG --clone

# 3. Record pinned SHAs for SHAS.txt
git -C repos-audit/OpenBMB__ClawXRouter rev-parse HEAD
git -C repos-audit/openai__privacy-filter rev-parse HEAD
git -C repos-audit/bitbonsai__mcpvault rev-parse HEAD
```

## Per-Repo Reports

| Repo | Report |
|---|---|
| D4Vinci/Scrapling | [D4Vinci__Scrapling.md](D4Vinci__Scrapling.md) |
| OpenBMB/EdgeClaw | [OpenBMB__EdgeClaw.md](OpenBMB__EdgeClaw.md) |
| OpenBMB/ClawXRouter | [OpenBMB__ClawXRouter.md](OpenBMB__ClawXRouter.md) |
| ~~privacyshield-ai/privacy-firewall~~ | [privacyshield-ai__privacy-firewall.md](privacyshield-ai__privacy-firewall.md) |
| **openai/privacy-filter** | [openai__privacy-filter.md](openai__privacy-filter.md) |
| tinyhumansai/openhuman | [tinyhumansai__openhuman.md](tinyhumansai__openhuman.md) |
| garrytan/gbrain | [garrytan__gbrain.md](garrytan__gbrain.md) |
| affaan-m/ECC | [affaan-m__ECC.md](affaan-m__ECC.md) |
| massgen/MassGen | [massgen__MassGen.md](massgen__MassGen.md) |
| safishamsi/graphify | [safishamsi__graphify.md](safishamsi__graphify.md) |
| ~~jlevere/obsidian-mcp-plugin~~ | [jlevere__obsidian-mcp-plugin.md](jlevere__obsidian-mcp-plugin.md) |
| **@bitbonsai/mcpvault** | [bitbonsai__mcpvault.md](bitbonsai__mcpvault.md) |

## Scan Methodology

- HTTP probe: Scrapling Fetcher with stealth headers
- Bus-factor: stars, commits, contributors via HTML
- Shallow clone (`--depth 1`) into `repos-audit/`
- Static pattern scan over `.py .ts .js .tsx .jsx .sh .toml .json .md .yml .yaml`
  patterns: `curl_pipe_sh`, `eval_exec`, `shell_true`, `hardcoded_url`, `telemetry`, `aws_key`, `api_key_literal`
- Counts include docs/examples — order-of-magnitude triage, not vuln proof

Raw data: `audit/repo_verify.json`, `audit/bus_factor.json`, `audit/security_scan.txt`.

## Reproduction

```bash
# Refresh metrics
"$SCRAPLING_PY" scripts/bus_factor.py > audit/bus_factor.json
# Re-clone any missing
bash scripts/clone_all.sh
# Regenerate per-repo audits (script overwrites this INDEX header — manually re-append the verdict matrix)
"$SCRAPLING_PY" scripts/audit_clones.py
```
