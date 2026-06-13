# jlevere/obsidian-mcp-plugin

Audit generated: 2026-05-27T23:58:06.050142+00:00
Local clone: `repos-audit\jlevere__obsidian-mcp-plugin`

## GitHub Metrics (Scrapling probe)

- **stars_abbrev:** 12
- **stars_exact:** 12
- **forks:** 2
- **open_issues:** 6
- **open_prs:** 0
- **last_commit_utc:** 2025-07-02T17:43:23Z
- **description:** Allow an LLM to interact with your notes in Obsidian via MCP - jlevere/obsidian-mcp-plugin

## Git Snapshot

- branch: `main`
- head:   `4a73b187ecdf26ee900fdeb6fb9969157a175b62`
- last commit: 2026-05-23 23:57:12 -0500 4a73b18 jlevere
- contributors in shallow clone: 1
- top contributors (shallow):
    1	jlevere <71566629+jlevere@users.noreply.github.com>

## License

MIT License | Copyright Jack Leverett and Josh Merrill (c) 2023

## Languages (by total bytes — top 10)

- `.png`: 240,782 bytes
- `.yaml`: 221,723 bytes
- `.ts`: 99,425 bytes
- `.md`: 15,096 bytes
- `.json`: 6,496 bytes
- `.yml`: 1,886 bytes
- `.lock`: 1,558 bytes
- `(noext)`: 1,270 bytes
- `.nix`: 718 bytes

## Dependencies

### `npm_name`
```
obsidian-mcp-plugin
```
### `npm_version`
```
0.0.10
```
### `npm_dependencies_sample`
- ('@dmitryrechkin/json-schema-to-zod', '^1.0.1')
- ('ajv', '^8.20.0')
- ('diff', '^9.0.0')
- ('express', '^5.2.1')
- ('zod', '^4.4.3')
### `npm_dev_dependencies_sample`
- ('@esbuild-plugins/tsconfig-paths', '^0.1.2')
- ('@eslint/js', '^10.0.1')
- ('@jest/globals', '^30.4.1')
- ('@modelcontextprotocol/inspector', '^0.21.2')
- ('@modelcontextprotocol/sdk', '^1.29.0')
- ('@types/express', '^5.0.6')
- ('@types/jest', '^30.0.0')
- ('@types/node', '^22.19.19')
- ('builtin-modules', '^5.2.0')
- ('esbuild', '^0.28.0')
- ('eslint', '^10.4.0')
- ('eslint-config-prettier', '^10.1.8')
- ('jest', '^30.4.2')
- ('jiti', '^2.7.0')
- ('obsidian', '^1.12.3')
- ('prettier', '^3.8.3')
- ('tailwindcss', '^4.3.0')
- ('ts-jest', '^29.4.11')
- ('tslib', '^2.8.1')
- ('tsx', '^4.22.3')
### `npm_scripts`
- dev
- build
- build:dev
- test
- lint
- preversion
- postversion
- postpublish
- inspect
- package
- format:write
- format

## README — first 80 lines

```
# Vault MCP

<div align="center">

[![Validate](https://github.com/jlevere/obsidian-mcp-plugin/actions/workflows/validate.yml/badge.svg)](https://github.com/jlevere/obsidian-mcp-plugin/actions/workflows/validate.yml)
[![GitHub release](https://img.shields.io/github/v/release/jlevere/obsidian-mcp-plugin)](https://github.com/jlevere/obsidian-mcp-plugin/releases)
[![Downloads](https://img.shields.io/github/downloads/jlevere/obsidian-mcp-plugin/total)](https://github.com/jlevere/obsidian-mcp-plugin/releases)

This Obsidian plugin embeds an MCP ([Model Context Protocol](https://modelcontextprotocol.io/introduction)) server directly within Obsidian, providing a streamlined
way for applications to interact with your vault.

*Desktop Only*

[Installation](#installation) •
[Features](#features) •
[Usage](#usage) •
[Development](#development) •
[Schema Guide](#schemas)
[Notes](#notes)

![obsidian-settings](./docs/obsidian-settings.png)

</div>

## Features

- **Embedded MCP Server:** Hosts the MCP server within Obsidian itself as a plugin, simplifying setup and improving performance
- **Vault Access via MCP:** Exposes your vault through standardized tools
- **Structured Data Support:** Define custom schemas for structured note creation and validation
- **File Operations:**
  - Read and write files
  - Fuzzy search across your vault
  - Navigate vault structure programmatically
  - Structured data storage and access
- **Configurable:** Customize server settings, tool availability, and authentication
- **Optional Authentication:** Secure your server with optional Bearer token authentication.

![tool-selection](./docs/obsidian-settings-tools.png)

![auth-settings](./docs/obsidian-settings-auth.png)

## Background

Vault MCP started as a small component of a larger project that needed an alternative to traditional RAG methods. It needed something LLMs could use to reliably retrieve and update structured, human-readable data, without relying on unpredictable vector databases or embedding fuzziness.

Existing Obsidian MCP servers weren't a great fit. They were REST-heavy, complex, and not well-suited for language models to interact with naturally. So this plugin was spun off to solve that: a lightweight interface for working with Obsidian vaults in a way that's natural for LLMs and transparent for humans.

## Installation

### Community Plugins (Recommended)

1. Open Obsidian Settings > Community Plugins
2. Search for "Vault MCP"
3. Click Install, then Enable
4. Configure settings as needed

### Manual Installation

1. Download the latest release zip
2. Extract to `<vault>/.obsidian/plugins/`
3. Enable in Obsidian settings

## Usage

### Basic Setup

1. Enable the plugin in Obsidian's Community Plugins section
2. Open plugin settings to configure:
  - **Server Port** (default: `3000`)
  - **Binding Host** (default: 127.0.0.1; use 0.0.0.0 for LAN access)
3. **(Optional) Enable Authentication:**
   - Toggle **Enable Authentication**
   - Copy the provided **Auth Token**
   - Include the token in HTTP headers: `Authorization: Bearer <your_token>`
4. Click Restart Server to apply changes

### Connection Methods

The plugin currently only supports Server-Sent Events (SSE) and StreamHTTP connections. For applications that require stdio connections (like Claude Desktop), you'll need to use a proxy. You can follow [Cloudflare's guide](https://developers.cloudflare.com/agents/guides/test-remote-mcp-server/#connect-your-remote-mcp-server-to-claude-desktop-via-a-local-proxy) on setting up a local proxy using [`mcp-remote`](https://www.npmjs.com/package/mcp-remote).

```
