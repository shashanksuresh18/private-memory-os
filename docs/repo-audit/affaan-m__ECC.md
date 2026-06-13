# affaan-m/ECC

Audit generated: 2026-05-27T23:58:05.488468+00:00
Local clone: `repos-audit\affaan-m__ECC`

## GitHub Metrics (Scrapling probe)

- **stars_abbrev:** 196k
- **stars_exact:** 195,906
- **forks:** 30.1k
- **open_issues:** 13
- **open_prs:** 16
- **last_commit_utc:** 2026-04-05T20:20:57Z
- **description:** The agent harness performance optimization system. Skills, instincts, memory, security, and research-first development for Claude Code, Codex, Opencode, Cursor and beyond. - affaan-m/ECC

## Git Snapshot

- branch: `main`
- head:   `928076cc08cbb31e8549cea2883b4f51811de1c8`
- last commit: 2026-05-25 14:19:03 -0400 928076c Affaan Mustafa
- contributors in shallow clone: 1
- top contributors (shallow):
    1	Affaan Mustafa <affaan@dcube.ai>

## License

MIT License | Copyright (c) 2026 Affaan Mustafa

## Languages (by total bytes — top 10)

- `.png`: 20,770,315 bytes
- `.md`: 13,605,908 bytes
- `.js`: 3,662,236 bytes
- `.rs`: 1,870,968 bytes
- `.jpeg`: 958,091 bytes
- `.mp4`: 516,057 bytes
- `.json`: 473,874 bytes
- `.py`: 335,437 bytes
- `.sh`: 190,286 bytes
- `.lock`: 163,110 bytes

## Dependencies

### `pyproject_dependencies_sample`
- anthropic
- openai
- pytest
- pytest-asyncio
- pytest-cov
- pytest-mock
- ruff
- mypy
### `pkg_name`
```
llm-abstraction
```
### `npm_name`
```
ecc-universal
```
### `npm_version`
```
2.0.0-rc.1
```
### `npm_dependencies_sample`
- ('@iarna/toml', '^2.2.5')
- ('ajv', '^8.18.0')
- ('sql.js', '^1.14.1')
### `npm_dev_dependencies_sample`
- ('@eslint/js', '^9.39.2')
- ('@opencode-ai/plugin', '^1.0.0')
- ('@types/node', '25.7.0')
- ('c8', '^11.0.0')
- ('eslint', '^9.39.2')
- ('globals', '^17.4.0')
- ('markdownlint-cli', '^0.48.0')
- ('typescript', '^6.0.3')
### `npm_scripts`
- postinstall
- catalog:check
- catalog:sync
- command-registry:generate
- command-registry:write
- command-registry:check
- lint
- harness:adapters
- harness:audit
- observability:ready
- operator:dashboard
- preview-pack:smoke
- release:approval-gate
- release:video-suite
- platform:audit
- discussion:audit
- security:ioc-scan
- security:advisory-sources
- claw
- orchestrate:status

## README — first 80 lines

```
**Language:** English | [Português (Brasil)](docs/pt-BR/README.md) | [简体中文](README.zh-CN.md) | [繁體中文](docs/zh-TW/README.md) | [日本語](docs/ja-JP/README.md) | [한국어](docs/ko-KR/README.md) | [Türkçe](docs/tr/README.md) | [Русский](docs/ru/README.md) | [Tiếng Việt](docs/vi-VN/README.md) | [ไทย](docs/th/README.md) | [Deutsch](docs/de-DE/README.md)

# ECC

![ECC - the harness-native operator system for agentic work](assets/hero.png)

[![Stars](https://img.shields.io/github/stars/affaan-m/ECC?style=flat)](https://github.com/affaan-m/ECC/stargazers)
[![Forks](https://img.shields.io/github/forks/affaan-m/ECC?style=flat)](https://github.com/affaan-m/ECC/network/members)
[![Contributors](https://img.shields.io/github/contributors/affaan-m/ECC?style=flat)](https://github.com/affaan-m/ECC/graphs/contributors)
[![npm ecc-universal](https://img.shields.io/npm/dw/ecc-universal?label=ecc-universal%20weekly%20downloads&logo=npm)](https://www.npmjs.com/package/ecc-universal)
[![npm ecc-agentshield](https://img.shields.io/npm/dw/ecc-agentshield?label=ecc-agentshield%20weekly%20downloads&logo=npm)](https://www.npmjs.com/package/ecc-agentshield)
[![GitHub App Install](https://img.shields.io/badge/GitHub%20App-150%20installs-2ea44f?logo=github)](https://github.com/marketplace/ecc-tools)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Shell](https://img.shields.io/badge/-Shell-4EAA25?logo=gnu-bash&logoColor=white)
![TypeScript](https://img.shields.io/badge/-TypeScript-3178C6?logo=typescript&logoColor=white)
![Python](https://img.shields.io/badge/-Python-3776AB?logo=python&logoColor=white)
![Go](https://img.shields.io/badge/-Go-00ADD8?logo=go&logoColor=white)
![Java](https://img.shields.io/badge/-Java-ED8B00?logo=openjdk&logoColor=white)
![Perl](https://img.shields.io/badge/-Perl-39457E?logo=perl&logoColor=white)
![Markdown](https://img.shields.io/badge/-Markdown-000000?logo=markdown&logoColor=white)

> **182K+ stars** | **28K+ forks** | **170+ contributors** | **12+ language ecosystems** | **Anthropic Hackathon Winner**

---

<div align="center">

**Language / 语言 / 語言 / Dil / Язык / Ngôn ngữ**

[**English**](README.md) | [Português (Brasil)](docs/pt-BR/README.md) | [简体中文](README.zh-CN.md) | [繁體中文](docs/zh-TW/README.md) | [日本語](docs/ja-JP/README.md) | [한국어](docs/ko-KR/README.md)
 | [Türkçe](docs/tr/README.md) | [Русский](docs/ru/README.md) | [Tiếng Việt](docs/vi-VN/README.md) | [ไทย](docs/th/README.md) | [Deutsch](docs/de-DE/README.md)

</div>

---

**The harness-native operator system for agentic work. From an Anthropic hackathon winner.**

Not just configs. A complete system: skills, instincts, memory optimization, continuous learning, security scanning, and research-first development. Production-ready agents, skills, hooks, rules, MCP configurations, and legacy command shims evolved over 10+ months of intensive daily use building real products.

Works across **Claude Code**, **Codex**, **Cursor**, **OpenCode**, **Gemini**, **Zed**, **GitHub Copilot**, and other AI agent harnesses.

ECC v2.0.0-rc.1 adds the public Hermes operator story on top of that reusable layer: start with the [Hermes setup guide](docs/HERMES-SETUP.md), then review the [rc.1 release notes](docs/releases/2.0.0-rc.1/release-notes.md) and [cross-harness architecture](docs/architecture/cross-harness.md).

---

<table>
<tr>
<td width="25%" align="center">
  <a href="https://ecc.tools/pricing">
    <strong> ECC Pro</strong><br />
    <sub>Private repos · GitHub App · $19/seat/mo</sub>
  </a>
</td>
<td width="25%" align="center">
  <a href="https://github.com/sponsors/affaan-m">
    <strong> Sponsor</strong><br />
    <sub>Fund the OSS · From $5/mo</sub>
  </a>
</td>
<td width="25%" align="center">
  <a href="https://github.com/affaan-m/ECC/discussions">
    <strong>Community</strong>
    <br />
    <sub>Discussions · Q&amp;A · Show & Tell</sub>
  </a>
</td>
<td width="25%" align="center">
  <a href="https://github.com/apps/ecc-tools">
    <strong> GitHub App</strong><br />
    <sub>Install · PR audits · Free tier</sub>
  </a>
</td>
</tr>
</table>

<sub>**OSS stays free.** This repo is MIT-licensed forever. ECC Pro is the hosted GitHub App for private repos. <a href="https://github.com/sponsors/affaan-m">Sponsors</a> and <a href="https://ecc.tools/pricing">Pro subscribers</a> fund the work — that's why a single maintainer ships weekly across 7 harnesses.</sub>

---

```
