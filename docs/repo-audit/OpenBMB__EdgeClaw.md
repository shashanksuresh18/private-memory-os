# OpenBMB/EdgeClaw

Audit generated: 2026-05-27T23:58:07.163112+00:00
Local clone: `repos-audit\OpenBMB__EdgeClaw`

## GitHub Metrics (Scrapling probe)

- **stars_abbrev:** 1.2k
- **stars_exact:** 1,207
- **forks:** 72
- **open_issues:** 1
- **open_prs:** 1
- **description:** EdgeClaw: Edge-Cloud Collaborative Personal AI Assistant based on OpenClaw - OpenBMB/EdgeClaw

## Git Snapshot

- branch: `main`
- head:   `5e461861b370f5677d2eb6b35499764632989279`
- last commit: 2026-04-15 17:25:34 +0800 5e46186 请输入用户名
- contributors in shallow clone: 1
- top contributors (shallow):
    1	请输入用户名 <liyishanthu@gmail.com>

## License

MIT License | Copyright (c) 2025 Peter Steinberger

## Languages (by total bytes — top 10)

- `.ts`: 56,366,013 bytes
- `.png`: 17,651,023 bytes
- `.js`: 10,300,618 bytes
- `.md`: 7,075,493 bytes
- `.swift`: 3,713,289 bytes
- `.json`: 3,310,507 bytes
- `.jsonl`: 2,301,400 bytes
- `.icns`: 1,884,490 bytes
- `.jpg`: 1,604,117 bytes
- `.kt`: 978,228 bytes

## Dependencies

### `pyproject_dependencies_sample`
### `npm_name`
```
openclaw
```
### `npm_version`
```
2026.4.1
```
### `npm_dependencies_sample`
- ('@agentclientprotocol/sdk', '0.17.1')
- ('@anthropic-ai/vertex-sdk', '^0.14.4')
- ('@clack/prompts', '^1.1.0')
- ('@homebridge/ciao', '^1.3.6')
- ('@line/bot-sdk', '^10.6.0')
- ('@lydell/node-pty', '1.2.0-beta.3')
- ('@mariozechner/pi-agent-core', '0.64.0')
- ('@mariozechner/pi-ai', '0.64.0')
- ('@mariozechner/pi-coding-agent', '0.64.0')
- ('@mariozechner/pi-tui', '0.64.0')
- ('@matrix-org/matrix-sdk-crypto-wasm', '18.0.0')
- ('@modelcontextprotocol/sdk', '1.29.0')
- ('@mozilla/readability', '^0.6.0')
- ('@sinclair/typebox', '0.34.49')
- ('ajv', '^8.18.0')
- ('chalk', '^5.6.2')
- ('chokidar', '^5.0.0')
- ('cli-highlight', '^2.1.11')
- ('commander', '^14.0.3')
- ('croner', '^10.0.1')
- ('dotenv', '^17.3.1')
- ('express', '^5.2.1')
- ('file-type', '22.0.0')
- ('gaxios', '7.1.4')
- ('hono', '4.12.9')
- ('ipaddr.js', '^2.3.0')
- ('jiti', '^2.6.1')
- ('json5', '^2.2.3')
- ('jszip', '^3.10.1')
- ('linkedom', '^0.18.12')
- ('long', '^5.3.2')
- ('markdown-it', '^14.1.1')
- ('matrix-js-sdk', '41.3.0-rc.0')
- ('node-edge-tts', '^1.2.10')
- ('osc-progress', '^0.3.0')
- ('pdfjs-dist', '^5.6.205')
- ('playwright-core', '1.58.2')
- ('qrcode-terminal', '^0.12.0')
- ('sharp', '^0.34.5')
- ('sqlite-vec', '0.1.9')
### `npm_dev_dependencies_sample`
- ('@grammyjs/types', '^3.25.0')
- ('@lit-labs/signals', '^0.2.0')
- ('@lit/context', '^1.1.6')
- ('@types/express', '^5.0.6')
- ('@types/markdown-it', '^14.1.2')
- ('@types/node', '^25.5.0')
- ('@types/qrcode-terminal', '^0.12.2')
- ('@types/ws', '^8.18.1')
- ('@typescript/native-preview', '7.0.0-dev.20260331.1')
- ('@vitest/coverage-v8', '^4.1.2')
- ('jscpd', '4.0.8')
- ('jsdom', '^29.0.1')
- ('lit', '^3.3.2')
- ('oxfmt', '0.43.0')
- ('oxlint', '^1.58.0')
- ('oxlint-tsgolint', '^0.18.1')
- ('semver', '7.7.4')
- ('signal-utils', '0.21.1')
- ('tsdown', '0.21.7')
- ('tsx', '^4.21.0')
### `npm_scripts`
- android:assemble
- android:assemble:third-party
- android:bundle:release
- android:format
- android:install
- android:install:third-party
- android:lint
- android:lint:android
- android:run
- android:run:third-party
- android:test
- android:test:integration
- android:test:third-party
- audit:seams
- build
- build:docker
- build:plugin-sdk:dts
- build:strict-smoke
- canon:check
- canon:check:json

## README — first 80 lines

```
<div align="center">

<img src="./assets/EdgeClaw-logo.png" alt="EdgeClaw Logo" width="200">

### Secure · Cost-Effective · Efficient

Edge-Cloud Collaborative AI Agent  
**EdgeClaw**: Bringing the Claude Code Experience to OpenClaw

【**[中文](./readme_zh.md)** | English】

👋 Join our community for discussion and support!

<a href="./assets/feishu-group.png"><img src="./assets/feishu-logo.png" width="16" height="16"> Feishu</a> &nbsp;|&nbsp; <a href="https://discord.com/invite/pC3N7ezpw"><img src="./assets/discord-logo.png" width="16" height="16"> Discord</a>

</div>

---

**What's New** 🔥

- **[2026.04.03]** 🚀 Three Claude Code-liked features released: 🔧 [ClawXTool](./extensions/clawxtool/) launches an 8-in-1 tool suite (including security analysis, secret scanning, git worktrees, etc.), 🔍 [ClawXSkill](./extensions/clawxskill/) releases an intelligent discovery engine (supporting skill search and model judge), and 🧠 [ClawXContext](./extensions/openbmb-clawxcontext/) introduces smooth context compaction and dynamic reinjection for long sessions.
- **[2026.04.02]** 🚀 Released three Claude Code-liked features optimized for OpenClaw — 🤖 [ClawXKairos](./extensions/clawxkairos/) (Self-Driven Agent Loop), 🛡️ [ClawXGovernor](./extensions/clawxgovernor/) (Tool Governance), and 📦 [ClawXSandbox](./extensions/ClawXSandbox/) (Claude Code-Style Sandbox)
- **[2026.04.01]** 🎉 EdgeClaw 2.0 is officially open-sourced, featuring a brand-new memory engine and cost-saving router — bringing the Claude Code experience to OpenClaw!
- **[2026.04.01]** 🎉 [ClawXMemory](https://github.com/OpenBMB/ClawXMemory) released — inspired by Claude Code's memory mechanism, it delivers a smoother experience for OpenClaw scenarios with multi-layered structured long-term memory and proactive reasoning!
- **[2026.03.25]** 🎉 [ClawXRouter](https://github.com/OpenBMB/clawxrouter) released — 5-tier cost-saving routing + three-tier privacy collaboration + visual Dashboard
- **[2026.03.13]** 🎉 EdgeClaw adds Cost-Aware Collaboration: automatically determines task complexity and matches the most economical cloud model
- **[2026.02.12]** 🎉 EdgeClaw is officially open-sourced — an Edge-Cloud Collaborative AI Agent

---

## 💡 About EdgeClaw

EdgeClaw is an **Edge-Cloud Collaborative AI Agent** jointly developed by [THUNLP (Tsinghua University)](https://nlp.csai.tsinghua.edu.cn), [Renmin University of China](http://ai.ruc.edu.cn/), [AI9Stars](https://github.com/AI9Stars), [ModelBest](https://modelbest.cn/en), and [OpenBMB](https://www.openbmb.cn/home), built on top of [OpenClaw](https://github.com/openclaw/openclaw).

### OpenClaw vs Claude Code vs EdgeClaw

|                                  | OpenClaw |     Claude Code      |                 **EdgeClaw**                  |
| -------------------------------- | :------: | :------------------: | :-------------------------------------------: |
| Cross-session project knowledge  |    ✗     |          ✓           |                     **✓**                     |
| Persistent user preference       |    ✗     |          ✓           |                     **✓**                     |
| Multi-layered structured memory  |    ✗     |          ✓           |                     **✓**                     |
| Memory integration strategy      |  Recall  |    On-demand read    |            **Proactive reasoning**            |
| Continuous memory consolidation  |    ✗     | Auto-Dream (backend) | **Auto-consolidation on idle & topic switch** |
| Cost-aware routing               |    ✗     |          ✗           |             **58% cost savings**              |
| Three-tier privacy collaboration |    ✗     |          ✗           |                 **S1/S2/S3**                  |
| Context working set management   |    ✗     |          ✓           |                     **✓**                     |
| Tool risk governance & audit     |    ✗     |          ✓           |                     **✓**                     |
| Self-driven agent loop           |    ✗     |          ✓           |                     **✓**                     |
| Sandboxed execution              |    ✗     |          ✓           |                     **✓**                     |
| Intelligent skill discovery      |    ✗     |          ✗           |                     **✓**                     |
| Built-in security tool suite     |    ✗     |          △           |                     **✓**                     |
| Virtual pet companion            |    ✗     |          ✓           |                     **✓**                     |
| Visual Dashboard                 |    ✗     |          ✗           |                     **✓**                     |

### ✨ Highlights at a Glance

**🌟 Claude Code-Liked Features**

- **🤖 Self-Driven Loop** — [ClawXKairos](./extensions/clawxkairos/): Tick scheduling + Sleep tool + background command automation + async sub-agents, enabling the agent to work autonomously and continuously
- **🛡️ Tool Governance** — [ClawXGovernor](./extensions/clawxgovernor/): Three hook middlewares — context tail-window trimming, tool call risk interception & audit, session note incremental append. Deeply optimized for OpenClaw scenarios, **saving 85% tokens over 30 rounds of calls**
- **📦 Sandbox Execution** — [ClawXSandbox](./extensions/ClawXSandbox/): Fully isolated local execution environment based on system-level sandboxing (bwrap / sandbox-exec). Focused on being **lightweight, fast, and zero-dependency**, completely eliminating all Docker overhead.
- **🔧 Unified Tool Suite** — [ClawXTool](./extensions/clawxtool/): 8-in-1 plugin providing 13 tools, covering **security audit** (bash security analysis, secret scanning), **workflow** (git worktree management, structured task tracking), **development assistance** (cron parsing, notebook editing), and **agent interaction** (memory age annotations, interactive user questions).
- **🔍 Skill Discovery** — [ClawXSkill](./extensions/clawxskill/): Automatically discovers and indexes agent skills across the workspace using BM25 keyword search, optional embedding-based semantic search, and LLM model judge for intelligent skill matching.
- **🧠 Memory Engine** — [ClawXMemory](./extensions/openbmb-clawxmemory/): A structured long-term memory engine built for OpenClaw. Building on the ideas behind Claude Code's memory mechanism, it further introduces multi-layered structured memory and model-driven memory retrieval. _(v0.1.5)_
- **📝 Context Engine** — [ClawXContext](./extensions/openbmb-clawxcontext/): OpenClaw context engine focused on long-session stability, smooth context compaction, and dynamic reinjection.
- **🐾 Virtual Pet Companion** — [ClawXBuddy](./extensions/clawxbuddy/): An adorable ASCII virtual pet companion with idle animations, rarity traits, and interactive commands to keep you company.

**🔥 Other Core Features**

- **💰 Cost-Saving Router** — [ClawXRouter](https://github.com/openbmb/clawxrouter): LLM-as-Judge automatically determines complexity, routing 60–80% of requests to cheaper models. Real-world PinchBench testing shows **58% cost savings** with scores **6.3% higher**.
- **🔒 Three-Tier Privacy** — S1 direct cloud / S2 desensitized forwarding / S3 fully local processing — sensitive data never leaves the device.
- **🚀 Zero Configuration** — `pnpm build && node openclaw.mjs gateway run`, auto-generates config on first launch, just fill in your API Key.
- **📊 Dual Dashboard** — ClawXRouter routing config hot-reload + ClawXMemory memory canvas visualization.

---

## 🎬 Demo

<div align="center">
```
