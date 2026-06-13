# massgen/MassGen

Audit generated: 2026-05-27T23:58:06.282214+00:00
Local clone: `repos-audit\massgen__MassGen`

## GitHub Metrics (Scrapling probe)

- **stars_abbrev:** 1k
- **stars_exact:** 1,039
- **forks:** 160
- **open_issues:** 1
- **open_prs:** 1
- **last_commit_utc:** 2026-05-27T19:02:51Z
- **description:** 🚀 MassGen is an open-source multi-agent scaling system that runs in your terminal, autonomously orchestrating frontier models and agents to collaborate, reason, and produce high-quality results. | Join us on Discord: discord.massgen.ai - massgen/Mass

## Git Snapshot

- branch: `main`
- head:   `20f70efb02930a54803e8d917072c7bdda8cf9cd`
- last commit: 2026-05-28 03:02:30 +0800 20f70ef HenryQi
- contributors in shallow clone: 1
- top contributors (shallow):
    1	HenryQi <henryluo811@gmail.com>

## License

Apache License | Version 2.0, January 2004 | http://www.apache.org/licenses/

## Languages (by total bytes — top 10)

- `.gif`: 524,656,179 bytes
- `.mp4`: 40,198,538 bytes
- `.map`: 31,822,295 bytes
- `.png`: 17,253,420 bytes
- `.py`: 17,032,313 bytes
- `.js`: 14,754,420 bytes
- `.md`: 5,045,088 bytes
- `.pdf`: 2,867,404 bytes
- `.html`: 1,650,010 bytes
- `.tsx`: 1,214,947 bytes

## Dependencies

### `pyproject_dependencies_sample`
- datasets
- openai
- xai-sdk
- anthropic
- elevenlabs
- cerebras-cloud-sdk
- lmstudio
- wcwidth
- google-genai
- python-dotenv
- PyYAML
- rich
- questionary
- requests
- typing-extensions
- claude-agent-sdk
- loguru
- mcp
- aiohttp
- nest-asyncio
- fastmcp
- sphinx-rtd-theme
- sphinx-book-theme
- pillow
- ag2
- pyautogen
- google-cloud-aiplatform
- pytest
- langchain-openai
- langgraph
- langchain-core
- agentscope
- smolagents[litellm]
- python-docx
- openpyxl
- python-pptx
- opencv-python
- pypdf2
- mem0ai
- reportlab
### `pkg_name`
```
massgen
```
### `requirements_txt_sample`
- datasets==3.2.0
- openai==2.2.0
- xai-sdk==1.6.1
- anthropic>=0.61.0
- nest-asyncio==1.6.0
- wcwidth>=0.2.5
- google-genai>=1.27.0
- python-dotenv>=1.0.0
- PyYAML>=6.0
- rich==14.1.0
- textual>=0.47.0
- cerebras-cloud-sdk==1.46.0
- lmstudio==1.4.1
- requests>=2.31.0
- typing-extensions>=4.0.0
- claude-agent-sdk>=0.0.22
- loguru>=0.7.0
- mcp>=1.12.0
- fastmcp>=2.12.3,<3.0.0
- aiohttp>=3.8.0
- websockets>=11.0.0
- pydub>=0.25.1
- dspy>=2.4.0
- sphinx>=7.0.0
- sphinx-rtd-theme>=2.0.0
- myst-parser>=2.0.0
- sphinx-copybutton>=0.5.0
- sphinx-autobuild>=2021.3.14
- sphinxcontrib-mermaid>=0.9.0
- sphinx-autodoc-typehints>=1.24.0
- sphinx-autoapi>=3.0.0
- sphinx-design>=0.5.0
- sphinx-tabs>=3.4.0
- sphinx-togglebutton>=0.3.0
- sphinx-inline-tabs>=2023.4.21
- sphinxcontrib-lunrsearch>=0.4

## README — first 80 lines

```
<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/logo-dark.png">
    <source media="(prefers-color-scheme: light)" srcset="assets/logo.png">
    <img src="assets/logo.png" alt="MassGen Logo" width="360" />
  </picture>
</p>

<div align="center">

[![PyPI](https://img.shields.io/pypi/v/massgen?style=flat-square&logo=pypi&logoColor=white&label=PyPI&color=3775A9)](https://pypi.org/project/massgen/)
[![Docs](https://img.shields.io/badge/docs-massgen.ai-blue?style=flat-square&logo=readthedocs&logoColor=white)](https://docs.massgen.ai)
[![GitHub Stars](https://img.shields.io/github/stars/Leezekun/MassGen?style=flat-square&logo=github&color=181717&logoColor=white)](https://github.com/Leezekun/MassGen)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Apache%202.0-green?style=flat-square)](LICENSE)

</div>

<div align="center">

[![Follow on X](https://img.shields.io/badge/FOLLOW%20ON%20X-000000?style=for-the-badge&logo=x&logoColor=white)](https://x.massgen.ai)
[![Follow on LinkedIn](https://img.shields.io/badge/FOLLOW%20ON%20LINKEDIN-0A66C2?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/company/massgen-ai)
[![Join our Discord](https://img.shields.io/badge/JOIN%20OUR%20DISCORD-5865F2?style=for-the-badge&logo=discord&logoColor=white)](https://discord.massgen.ai)

</div>

<h1 align="center">🚀 MassGen: Multi-Agent Scaling System for GenAI</h1>

<p align="center">
  <i>MassGen is a cutting-edge multi-agent system that leverages the power of collaborative AI to solve complex tasks.</i>
</p>

<p align="center">
  <a href="https://www.youtube.com/watch?v=5JofXWf_Ok8">
    <img src="docs/source/_static/images/readme.gif" alt="MassGen example" width="800">
  </a>
</p>

<p align="center">
  <i>Scaling AI with collaborative, continuously improving agents (4x speed)</i>
</p>

MassGen is a cutting-edge multi-agent framework that coordinates AI agents to solve complex tasks through redundancy and iterative refinement. Every agent tackles the full problem, observing, critiquing, and building on each other's work across cycles of refinement and restarts. When agents believe there is a strong enough answer, they vote, and the best collectively validated answer wins. This approach to parallel refinement and collective validation lays the groundwork for principled multi-agent scaling, where the system continuously improves its outputs by leveraging diverse agent perspectives and enforcing quality through consensus.

This project started with the "threads of thought" and "iterative refinement" ideas presented in [The Myth of Reasoning](https://docs.ag2.ai/latest/docs/blog/2025/04/16/Reasoning/), and extends the classic "multi-agent conversation" idea in [AG2](https://github.com/ag2ai/ag2). Here is a [video recording](https://www.youtube.com/watch?v=xM2Uguw1UsQ) of the background context introduction presented at the Berkeley Agentic AI Summit 2025.

<p align="center">
  <b>🧩 Use MassGen as a Skill:</b> <code>npx skills add massgen/skills --all</code> — then type invoke the skill in Claude Code, Cursor, Copilot, or 40+ other agents. <a href="https://github.com/massgen/skills">Learn more →</a>
</p>

<p align="center">
  <b>📚 For Contributors:</b> See <a href="https://massgen.github.io/Handbook/">MassGen Contributor Handbook</a> - Centralized policies and resources for development and research teams
</p>

---

## 📋 Table of Contents

<details open>
<summary><h3>✨ Key Features</h3></summary>

- [Cross-Model/Agent Synergy](#-key-features-1)
- [Parallel Processing](#-key-features-1)
- [Intelligence Sharing](#-key-features-1)
- [Consensus Building](#-key-features-1)
- [Live Visualization](#-key-features-1)
</details>

<details open>
<summary><h3>🆕 Latest Features</h3></summary>

- [v0.1.91 Features](#-latest-features-v0191)
</details>

<details open>
<summary><h3>🏗️ System Design</h3></summary>

- [System Architecture](#%EF%B8%8F-system-design-1)
- [Parallel Processing](#%EF%B8%8F-system-design-1)
- [Real-time Collaboration](#%EF%B8%8F-system-design-1)
```
