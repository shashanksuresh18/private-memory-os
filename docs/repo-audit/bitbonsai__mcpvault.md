# bitbonsai/mcpvault

Audit generated: 2026-05-27T23:58:05.601090+00:00
Local clone: `repos-audit\bitbonsai__mcpvault`

## GitHub Metrics (Scrapling probe)

- **stars_abbrev:** 1.3k
- **stars_exact:** 1,312
- **forks:** 105
- **open_issues:** 15
- **open_prs:** 8
- **description:** A lightweight Model Context Protocol (MCP) server for safe Obsidian vault access - bitbonsai/mcpvault

## Git Snapshot

- branch: `main`
- head:   `488a9076f84fdc8d5818c11eb4f8e2cdbfd74e8c`
- last commit: 2026-05-25 21:49:39 +0200 488a907 Mauricio Wolff
- contributors in shallow clone: 1
- top contributors (shallow):
    1	Mauricio Wolff <gh@bitbonsai.com>

## License

_(no LICENSE file found)_

## Languages (by total bytes — top 10)

- `.mp4`: 1,083,904 bytes
- `.astro`: 211,142 bytes
- `.ts`: 185,967 bytes
- `.json`: 136,534 bytes
- `.jpg`: 108,952 bytes
- `.md`: 106,674 bytes
- `.js`: 86,475 bytes
- `.lock`: 52,884 bytes
- `.png`: 41,021 bytes
- `.webp`: 34,312 bytes

## Dependencies

### `npm_name`
```
@bitbonsai/mcpvault
```
### `npm_version`
```
0.11.2
```
### `npm_dependencies_sample`
- ('@modelcontextprotocol/sdk', '^1.20.0')
- ('gray-matter', '^4.0.3')
- ('trash', '^10.1.1')
- ('yaml', '^2.8.3')
### `npm_dev_dependencies_sample`
- ('@types/node', '^25.3.3')
- ('tsx', '^4.20.6')
- ('typescript', '^6.0.2')
- ('vitest', '^4.0.15')
### `npm_scripts`
- start
- website
- build
- test
- test:watch
- prepublishOnly
- prepack
- publish:dry
- publish:beta
- publish:latest

## README — first 80 lines

```
<div align="center">
  <img width="256" height="256" alt="image" src="https://github.com/user-attachments/assets/1e21d898-811b-42c2-a810-bf921dde0f58" />
</div>

# MCPVault

A universal AI bridge for Obsidian vaults using the Model Context Protocol (MCP) standard. Connect any MCP-compatible AI assistant to your knowledge base - works with Claude, ChatGPT, and future AI tools. This server provides safe read/write access to your notes while preventing YAML frontmatter corruption.

<div align="center">
  
[https://mcpvault.org](https://mcpvault.org)

[Changelog](./CHANGELOG.md)

</div>

<div align="center">

[![GitHub Stars](https://img.shields.io/github/stars/bitbonsai/mcpvault?style=flat&logo=github&logoColor=white&color=9065ea&labelColor=262626)](https://github.com/bitbonsai/mcpvault)
[![npm version](https://img.shields.io/npm/v/%40bitbonsai%2Fmcpvault?style=flat&logo=npm&logoColor=white&color=9065ea&labelColor=262626)](https://www.npmjs.com/package/@bitbonsai/mcpvault)
[![npm downloads](https://img.shields.io/endpoint?url=https%3A%2F%2Fmcpvault.org%2Fapi%2Fdownloads.json&style=flat&logo=npm&logoColor=white&color=9065ea&labelColor=262626)](https://www.npmjs.com/package/@bitbonsai/mcpvault)
[![GitHub Sponsors](https://img.shields.io/github/sponsors/BitBonsai?style=flat&logo=github&logoColor=white&color=9065ea&labelColor=262626)](https://github.com/sponsors/bitbonsai)
[![Ko-Fi](https://img.shields.io/badge/Ko--fi-Support%20Me-9065ea?style=flat&logo=ko-fi&logoColor=white&labelColor=262626)](https://ko-fi.com/bitbonsai)
[![Liberapay](https://img.shields.io/badge/Liberapay-Weekly%20Support-9065ea?style=flat&logo=liberapay&logoColor=white&labelColor=262626)](https://liberapay.com/bitbonsai/)

</div>

## Universal Compatibility

Works with any MCP-compatible AI assistant including Claude Desktop, Claude Code, ChatGPT Desktop (Enterprise+), OpenCode, Gemini CLI, OpenAI Codex, IntelliJ IDEA 2025.1+, Cursor IDE, Windsurf IDE, and future AI platforms that adopt the MCP standard.

https://github.com/user-attachments/assets/657ac4c6-1cd2-4cc3-829f-fd095a32f71c

## Quick Start (5 minutes)

1. **Install Node.js runtime:**

   ```bash
   # Download from https://nodejs.org (v18.0.0 or later)
   # or use a package manager like nvm, brew, apt, etc.
   ```

2. **Test the server:**

   If using the published package:

   ```bash
   npx @modelcontextprotocol/inspector npx @bitbonsai/mcpvault@latest /path/to/your/vault
   ```

3. **Configure your AI client:**

   **Claude Desktop** - Copy this to `claude_desktop_config.json`:

   ```json
   {
     "mcpServers": {
       "obsidian": {
         "command": "npx",
         "args": ["@bitbonsai/mcpvault@latest", "/path/to/your/vault"]
       }
     }
   }
   ```

   **Claude Code** - Copy this to `~/.claude.json`:

   ```json
   {
     "mcpServers": {
       "obsidian": {
         "command": "npx",
         "args": ["@bitbonsai/mcpvault@latest", "/path/to/your/vault"],
         "env": {}
       }
     }
   }
   ```

   **OpenCode** - Copy this to `~/.config/opencode/opencode.json`
```
