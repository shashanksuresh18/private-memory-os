# tinyhumansai/openhuman

Audit generated: 2026-05-27T23:58:07.649209+00:00
Local clone: `repos-audit\tinyhumansai__openhuman`

## GitHub Metrics (Scrapling probe)

- **stars_abbrev:** 28.8k
- **stars_exact:** 28,807
- **forks:** 2.7k
- **open_issues:** 92
- **open_prs:** 71
- **last_commit_utc:** 2026-05-27T16:47:46Z
- **description:** Your Personal AI super intelligence. Private, Simple and extremely powerful. - tinyhumansai/openhuman

## Git Snapshot

- branch: `main`
- head:   `d8696c1c1f4b99647c6eac56c81df6b08c46df37`
- last commit: 2026-05-28 01:14:44 +0530 d8696c1 Cyrus Gray
- contributors in shallow clone: 1
- top contributors (shallow):
    1	Cyrus Gray <144336577+graycyrus@users.noreply.github.com>

## License

GNU GENERAL PUBLIC LICENSE | Version 3, 29 June 2007

## Languages (by total bytes — top 10)

- `.rs`: 19,964,399 bytes
- `.json`: 11,029,899 bytes
- `.ts`: 6,979,111 bytes
- `.png`: 5,398,524 bytes
- `.tsx`: 4,447,967 bytes
- `.md`: 1,658,162 bytes
- `.gif`: 1,589,884 bytes
- `.yaml`: 880,437 bytes
- `.lock`: 623,153 bytes
- `.sh`: 477,940 bytes

## Dependencies

### `npm_name`
```
openhuman-repo
```
### `npm_version`
```
None
```
### `npm_dependencies_sample`
- ('@rive-app/react-canvas', '^4.28.6')
- ('@tauri-apps/api', '2.10.1')
### `npm_dev_dependencies_sample`
- ('husky', '^9.1.7')
- ('tsx', '^4.20.3')
- ('ws', '^8.20.0')
### `npm_scripts`
- build
- compile
- dev
- dev:app
- dev:app:win
- dev:staging
- dev:cef
- format
- format:check
- knip
- knip:production
- lint
- lint:fix
- prepare
- postinstall
- tauri
- test
- test:coverage
- test:rust
- test:rust:e2e
### `cargo_toml_head`
```
[package]
name = "openhuman"
version = "0.57.0"
edition = "2021"
description = "OpenHuman core business logic and RPC server"
autobins = false

[[bin]]
name = "openhuman-core"
path = "src/main.rs"

[[bin]]
name = "slack-backfill"
path = "src/bin/slack_backfill.rs"

[[bin]]
name = "gmail-backfill-3d"
path = "src/bin/gmail_backfill_3d.rs"

[[bin]]
name = "memory-tree-init-smoke"
path = "src/bin/memory_tree_init_smoke.rs"

[[bin]]
name = "inference-probe"
```

## README — first 80 lines

```
<h1 align="center">OpenHuman</h1>

<p align="center">
 <img src="./gitbooks/.gitbook/assets/demo.png" alt="The Tet" />
</p>

<p align="center" style="display: inline-block">
	<a href="https://trendshift.io/repositories/23680" target="_blank" style="display: inline-block">
		<img src="https://trendshift.io/api/badge/repositories/23680" alt="tinyhumansai%2Fopenhuman | Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/>
	</a>
	<a href="https://www.producthunt.com/products/openhuman?embed=true&amp;utm_source=badge-top-post-badge&amp;utm_medium=badge&amp;utm_campaign=badge-openhuman" target="_blank" rel="noopener noreferrer">
		<img alt="OpenHuman - An open source AI harness built with the human in mind | Product Hunt" width="250" height="54" src="https://api.producthunt.com/widgets/embed-image/v1/top-post-badge.svg?post_id=1136902&amp;theme=light&amp;period=daily&amp;t=1778916022823">
		</a>
		<a href="https://www.producthunt.com/products/openhuman?embed=true&amp;utm_source=badge-top-post-badge&amp;utm_medium=badge&amp;utm_campaign=badge-openhuman" target="_blank" rel="noopener noreferrer">
			<img alt="OpenHuman - An open source AI harness built with the human in mind | Product Hunt" width="250" height="54" src="https://api.producthunt.com/widgets/embed-image/v1/top-post-badge.svg?post_id=1136902&amp;theme=light&amp;period=weekly&amp;t=1779351403565">
		</a>
</p>
<p align="center" style="display: inline-block">
 <a href="https://www.producthunt.com/products/openhuman?embed=true&amp;utm_source=badge-top-post-topic-badge&amp;utm_medium=badge&amp;utm_campaign=badge-openhuman" target="_blank" rel="noopener noreferrer">
  <img alt="OpenHuman - An open source AI harness built with the human in mind | Product Hunt" width="250" height="54" src="https://api.producthunt.com/widgets/embed-image/v1/top-post-topic-badge.svg?post_id=1136902&amp;theme=light&amp;period=weekly&amp;topic_id=268&amp;t=1779351808756">
  </a>
  <a href="https://www.producthunt.com/products/openhuman?embed=true&amp;utm_source=badge-top-post-topic-badge&amp;utm_medium=badge&amp;utm_campaign=badge-openhuman" target="_blank" rel="noopener noreferrer">
   <img alt="OpenHuman - An open source AI harness built with the human in mind | Product Hunt" width="250" height="54" src="https://api.producthunt.com/widgets/embed-image/v1/top-post-topic-badge.svg?post_id=1136902&amp;theme=light&amp;period=weekly&amp;topic_id=46&amp;t=1779351808756">
   </a>
 </p>


<p align="center">
 <strong>OpenHuman is your Personal AI super intelligence: local memory, managed services where needed, simple and powerful.</strong>
</p>


<p align="center">
 <a href="https://discord.tinyhumans.ai/">Discord</a> •
 <a href="https://www.reddit.com/r/tinyhumansai/">Reddit</a> •
 <a href="https://x.com/intent/follow?screen_name=tinyhumansai">X/Twitter</a> •
 <a href="https://tinyhumans.gitbook.io/openhuman/">Docs</a> •
 <a href="https://x.com/intent/follow?screen_name=senamakel">Follow @senamakel (Creator)</a>
</p>

<p align="center">
  🇺🇸 <a href="./README.md">English</a> | 🇨🇳 <a href="./README.zh-CN.md">简体中文</a> | 🇯🇵 <a href="./README.ja-JP.md">日本語</a> | 🇰🇷 <a href="./README.ko.md">한국어</a> | 🇩🇪 <a href="./README.de.md">Deutsch</a>
</p>


<p align="center">
 <img src="https://img.shields.io/badge/status-early%20beta-orange" alt="Early Beta" />
 <a href="https://github.com/tinyhumansai/openhuman/releases/latest"><img src="https://img.shields.io/github/v/release/tinyhumansai/openhuman?label=latest" alt="Latest Release" /></a>
 <a href="https://github.com/tinyhumansai/openhuman/stargazers"><img src="https://img.shields.io/github/stars/tinyhumansai/openhuman?style=flat" alt="GitHub Stars" /></a>
 <a href="./LICENSE"><img src="https://img.shields.io/github/license/tinyhumansai/openhuman" alt="License" /></a>
 <a href="./README.zh-CN.md"><img src="https://img.shields.io/badge/lang-简体中文-blue" alt="简体中文" /></a>
 <a href="./README.ja-JP.md"><img src="https://img.shields.io/badge/lang-日本語-blue" alt="日本語" /></a>
 <a href="./README.ko.md"><img src="https://img.shields.io/badge/lang-한국어-blue" alt="한국어" /></a>
 <a href="./README.de.md"><img src="https://img.shields.io/badge/lang-Deutsch-blue" alt="Deutsch" /></a>
</p>

> **Early Beta**: Under active development. Expect rough edges.

> **Local + managed services, upfront:** OpenHuman stores its Memory Tree, Obsidian-style Markdown vault, workspace config, and local runtime state on your machine. The default managed experience still uses OpenHuman-hosted services for account sign-in, model routing, web search proxying, and managed integration/OAuth flows through the Composio connector layer. Choose custom/local settings if you want to bring your own model, search, or Composio credentials; some real-time triggers and hosted features still require the managed backend.

# Install

Download installers from [tinyhumans.ai/openhuman](https://tinyhumans.ai/openhuman?utm_source=github&utm_medium=readme) or from the [GitHub Releases](https://github.com/tinyhumansai/openhuman/releases/latest) page. For terminal installs, the native package paths below are preferred — they ride your OS package-manager's signing chain.

## Recommended install (native packages)

These paths verify the artifact through your OS package manager's signing chain (Homebrew bottle hash, signed apt repo, MSI signature).

**macOS (Homebrew tap):**

```bash
brew tap tinyhumansai/core
brew install openhuman
```

**Linux (Debian/Ubuntu — signed apt repo):**

```bash
sudo apt-get install -y --no-install-recommends gnupg2 curl ca-certificates
curl -fsSL https://tinyhumansai.github.io/openhuman/apt/KEY.gpg \
```
