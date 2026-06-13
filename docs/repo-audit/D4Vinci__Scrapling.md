# D4Vinci/Scrapling

Audit generated: 2026-05-27T23:58:05.725744+00:00
Local clone: `repos-audit\D4Vinci__Scrapling`

## GitHub Metrics (Scrapling probe)

- **stars_abbrev:** 54.5k
- **stars_exact:** 54,523
- **forks:** 5.2k
- **open_issues:** 8
- **open_prs:** 4
- **last_commit_utc:** 2026-05-11T02:00:00Z
- **description:** 🕷️ An adaptive Web Scraping framework that handles everything from a single request to a full-scale crawl! - D4Vinci/Scrapling

## Git Snapshot

- branch: `main`
- head:   `b31dc50a063418307c6572cf01a1a9d14ccda8fc`
- last commit: 2026-05-27 04:10:38 +0300 b31dc50 Karim shoair
- contributors in shallow clone: 1
- top contributors (shallow):
    1	Karim shoair <D4Vinci@users.noreply.github.com>

## License

BSD 3-Clause License | Copyright (c) 2024, Karim shoair

## Languages (by total bytes — top 10)

- `.png`: 1,544,429 bytes
- `.py`: 971,699 bytes
- `.md`: 961,547 bytes
- `.ico`: 267,230 bytes
- `.svg`: 245,830 bytes
- `.zip`: 90,018 bytes
- `.yml`: 20,165 bytes
- `.jpg`: 18,340 bytes
- `.toml`: 11,913 bytes
- `(noext)`: 4,850 bytes

## Dependencies

### `pyproject_dependencies_sample`
- web-scraping
- scraping
- automation
- browser-automation
- data-extraction
- html-parsing
- undetectable
- playwright
- selenium-alternative
- web-crawler
- browser
- crawling
- headless
- scraper
- chrome
- lxml
- cssselect
- orjson
- tld
- w3lib
- typing_extensions
- click
- curl_cffi
- playwright
- patchright
- browserforge
- apify-fingerprint-datapoints
- msgspec
- anyio
- protego
- mcp
- markdownify
- scrapling[fetchers]
- markdownify
- scrapling[fetchers]
### `pkg_name`
```
scrapling
```

## README — first 80 lines

```
<!-- mcp-name: io.github.D4Vinci/Scrapling -->

<h1 align="center">
    <a href="https://scrapling.readthedocs.io">
        <picture>
          <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/D4Vinci/Scrapling/main/docs/assets/cover_dark.svg?sanitize=true">
          <img alt="Scrapling Poster" src="https://raw.githubusercontent.com/D4Vinci/Scrapling/main/docs/assets/cover_light.svg?sanitize=true">
        </picture>
    </a>
    <br>
    <small>Effortless Web Scraping for the Modern Web</small>
</h1>

<p align="center">
    <a href="https://trendshift.io/repositories/14244" target="_blank"><img src="https://trendshift.io/api/badge/repositories/14244" alt="D4Vinci%2FScrapling | Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/></a>
    <br/>
    <a href="https://github.com/D4Vinci/Scrapling/blob/main/docs/README_AR.md">العربيه</a> | <a href="https://github.com/D4Vinci/Scrapling/blob/main/docs/README_ES.md">Español</a> | <a href="https://github.com/D4Vinci/Scrapling/blob/main/docs/README_PT_BR.md">Português (Brasil)</a> | <a href="https://github.com/D4Vinci/Scrapling/blob/main/docs/README_FR.md">Français</a> | <a href="https://github.com/D4Vinci/Scrapling/blob/main/docs/README_DE.md">Deutsch</a> | <a href="https://github.com/D4Vinci/Scrapling/blob/main/docs/README_CN.md">简体中文</a> | <a href="https://github.com/D4Vinci/Scrapling/blob/main/docs/README_JP.md">日本語</a> |  <a href="https://github.com/D4Vinci/Scrapling/blob/main/docs/README_RU.md">Русский</a> | <a href="https://github.com/D4Vinci/Scrapling/blob/main/docs/README_KR.md">한국어</a>
    <br/>
    <a href="https://github.com/D4Vinci/Scrapling/actions/workflows/tests.yml" alt="Tests">
        <img alt="Tests" src="https://github.com/D4Vinci/Scrapling/actions/workflows/tests.yml/badge.svg"></a>
    <a href="https://badge.fury.io/py/Scrapling" alt="PyPI version">
        <img alt="PyPI version" src="https://badge.fury.io/py/Scrapling.svg"></a>
    <a href="https://clickpy.clickhouse.com/dashboard/scrapling" rel="nofollow"><img src="https://img.shields.io/pypi/dm/scrapling" alt="PyPI package downloads"></a>
    <a href="https://github.com/D4Vinci/Scrapling/tree/main/agent-skill" alt="AI Agent Skill directory">
        <img alt="Static Badge" src="https://img.shields.io/badge/Skill-black?style=flat&label=Agent&link=https%3A%2F%2Fgithub.com%2FD4Vinci%2FScrapling%2Ftree%2Fmain%2Fagent-skill"></a>
    <a href="https://clawhub.ai/D4Vinci/scrapling-official" alt="OpenClaw Skill">
        <img alt="OpenClaw Skill" src="https://img.shields.io/badge/Clawhub-darkred?style=flat&label=OpenClaw&link=https%3A%2F%2Fclawhub.ai%2FD4Vinci%2Fscrapling-official"></a>
    <br/>
    <a href="https://discord.gg/EMgGbDceNQ" alt="Discord" target="_blank">
      <img alt="Discord" src="https://img.shields.io/discord/1360786381042880532?style=social&logo=discord&link=https%3A%2F%2Fdiscord.gg%2FEMgGbDceNQ">
    </a>
    <a href="https://x.com/Scrapling_dev" alt="X (formerly Twitter)">
      <img alt="X (formerly Twitter) Follow" src="https://img.shields.io/twitter/follow/Scrapling_dev?style=social&logo=x&link=https%3A%2F%2Fx.com%2FScrapling_dev">
    </a>
    <br/>
    <a href="https://pypi.org/project/scrapling/" alt="Supported Python versions">
        <img alt="Supported Python versions" src="https://img.shields.io/pypi/pyversions/scrapling.svg"></a>
</p>

<p align="center">
    <a href="https://scrapling.readthedocs.io/en/latest/parsing/selection.html"><strong>Selection methods</strong></a>
    &middot;
    <a href="https://scrapling.readthedocs.io/en/latest/fetching/choosing.html"><strong>Fetchers</strong></a>
    &middot;
    <a href="https://scrapling.readthedocs.io/en/latest/spiders/architecture.html"><strong>Spiders</strong></a>
    &middot;
    <a href="https://scrapling.readthedocs.io/en/latest/spiders/proxy-blocking.html"><strong>Proxy Rotation</strong></a>
    &middot;
    <a href="https://scrapling.readthedocs.io/en/latest/cli/overview.html"><strong>CLI</strong></a>
    &middot;
    <a href="https://scrapling.readthedocs.io/en/latest/ai/mcp-server.html"><strong>MCP</strong></a>
</p>

Scrapling is an adaptive Web Scraping framework that handles everything from a single request to a full-scale crawl.

Its parser learns from website changes and automatically relocates your elements when pages update. Its fetchers bypass anti-bot systems like Cloudflare Turnstile out of the box. And its spider framework lets you scale up to concurrent, multi-session crawls with pause/resume and automatic proxy rotation - all in a few lines of Python. One library, zero compromises.

Blazing fast crawls with real-time stats and streaming. Built by Web Scrapers for Web Scrapers and regular users, there's something for everyone.

```python
from scrapling.fetchers import Fetcher, AsyncFetcher, StealthyFetcher, DynamicFetcher
StealthyFetcher.adaptive = True
p = StealthyFetcher.fetch('https://example.com', headless=True, network_idle=True)  # Fetch website under the radar!
products = p.css('.product', auto_save=True)                                        # Scrape data that survives website design changes!
products = p.css('.product', adaptive=True)                                         # Later, if the website structure changes, pass `adaptive=True` to find them!
```
Or scale up to full crawls
```python
from scrapling.spiders import Spider, Response

class MySpider(Spider):
  name = "demo"
  start_urls = ["https://example.com/"]

  async def parse(self, response: Response):
      for item in response.css('.product'):
          yield {"title": item.css('h2::text').get()}

MySpider().start()
```
```
