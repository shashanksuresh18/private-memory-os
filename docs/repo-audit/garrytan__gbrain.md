# garrytan/gbrain

Audit generated: 2026-05-27T23:58:05.939573+00:00
Local clone: `repos-audit\garrytan__gbrain`

## GitHub Metrics (Scrapling probe)

- **stars_abbrev:** 19.4k
- **stars_exact:** 19,400
- **forks:** 2.7k
- **open_issues:** 317
- **open_prs:** 360
- **description:** Garry's Opinionated OpenClaw/Hermes Agent Brain. Contribute to garrytan/gbrain development by creating an account on GitHub.

## Git Snapshot

- branch: `master`
- head:   `42d99b6fca3b5270f664dd61b8b1e3091e493760`
- last commit: 2026-05-27 08:52:36 -0700 42d99b6 Garry Tan
- contributors in shallow clone: 1
- top contributors (shallow):
    1	Garry Tan <garrytan@gmail.com>

## License

MIT License | Copyright (c) 2026 Garry Tan

## Languages (by total bytes — top 10)

- `.wasm`: 62,958,982 bytes
- `.ts`: 16,995,079 bytes
- `.md`: 6,811,628 bytes
- `.txt`: 650,430 bytes
- `.jsonl`: 261,937 bytes
- `.sh`: 248,582 bytes
- `.js`: 232,916 bytes
- `.png`: 225,424 bytes
- `.mjs`: 188,144 bytes
- `.wav`: 175,760 bytes

## Dependencies

### `npm_name`
```
gbrain
```
### `npm_version`
```
0.41.26.0
```
### `npm_dependencies_sample`
- ('@ai-sdk/anthropic', '^3.0.71')
- ('@ai-sdk/google', '^3.0.64')
- ('@ai-sdk/openai', '^3.0.53')
- ('@ai-sdk/openai-compatible', '^2.0.41')
- ('@anthropic-ai/sdk', '^0.30.0')
- ('@aws-sdk/client-s3', '^3.1028.0')
- ('@dqbd/tiktoken', '^1.0.22')
- ('@electric-sql/pglite', '0.4.3')
- ('@jsquash/avif', '^2.1.1')
- ('@jsquash/png', '^3.1.1')
- ('@modelcontextprotocol/sdk', '1.29.0')
- ('ai', '^6.0.168')
- ('chokidar', '^4.0.3')
- ('cookie-parser', '^1.4.7')
- ('cors', '^2.8.5')
- ('eventsource-parser', '^3.0.8')
- ('exifr', '^7.1.3')
- ('express', '^5.1.0')
- ('express-rate-limit', '^7.5.0')
- ('gray-matter', '^4.0.3')
- ('heic-decode', '^2.1.0')
- ('js-yaml', '^3.14.2')
- ('marked', '^18.0.0')
- ('openai', '^4.0.0')
- ('pgvector', '^0.2.0')
- ('postgres', '^3.4.0')
- ('tree-sitter-wasms', '0.1.13')
- ('web-tree-sitter', '0.22.6')
- ('zod', '^4.3.6')
### `npm_dev_dependencies_sample`
- ('@types/bun', 'latest')
- ('@types/cookie-parser', '^1.4.7')
- ('@types/cors', '^2.8.19')
- ('@types/express', '^5.0.6')
- ('@types/js-yaml', '^3.12.10')
- ('bun-types', '^1.3.13')
- ('fast-check', '^4.8.0')
- ('typescript', '^5.6.0')
### `npm_scripts`
- dev
- build
- build:all
- build:admin
- build:admin-embedded
- build:schema
- build:llms
- build:pglite-snapshot
- test
- test:full
- verify
- check:source-config-leak
- check:no-pii-agent-voice
- check:synthetic-corpus-privacy
- check:system-of-record
- check:admin-scope-drift
- check:cli-exec
- check:all
- check:gateway-routed
- check:worker-pool-atomicity

## README — first 80 lines

```
# GBrain

**Search gives you raw pages. GBrain gives you the answer.** It's the brain layer your AI agent has been missing — the only one that does synthesis, graph traversal, and gap analysis in one box.

I'm Garry Tan, President and CEO of Y Combinator. I built GBrain to run my own AI agents. It's the production brain behind my OpenClaw and Hermes deployments: **146,646 pages, 24,585 people, 5,339 companies**, 66 cron jobs running autonomously. My agent ingests meetings, emails, tweets, voice calls, and original ideas while I sleep. It enriches every person and company it encounters. It fixes its own citations and consolidates memory overnight. I wake up smarter than when I went to bed — and so will you.

**And now it works as a company brain too.** Each person on the team gets their own slice of the brain, scoped by login. When you query, you only see what you're allowed to see — never another person's notes, never another team's data. We fuzz-tested this across every way you can read the brain (search, list, lookup, multi-source reads) and got zero leaks. Drop GBrain in as your team's shared institutional memory — the [company-brain](https://www.ycombinator.com/rfs#company-brain) shape YC just put on its Request for Startups. If you're building in that space, you might as well build on this. **[Tutorial: set up GBrain as your company brain →](docs/tutorials/company-brain.md)**

Lots of personal-knowledge systems give you keyword matching and grep in a box. GBrain does that, and adds two things nobody else ships together:

- **A synthesis layer that gives you the actual answer.** Synthesized, well-cited prose across people, companies, deals, and ideas. Not "here are 10 chunks that mention your query"; an actual answer with citations and an explicit note on what the brain doesn't know yet. The gap analysis is the part that changes how you use the brain.
- **A self-wiring knowledge graph.** Every page write extracts entity refs and creates typed edges (`attended`, `works_at`, `invested_in`, `founded`, `advises`) with zero LLM calls. Ask "who works at Acme AI?" or "what did Bob invest in this quarter?" and get answers vector search alone can't reach. Benchmarked: **P@5 49.1%, R@5 97.9%** on a 240-page Opus-generated rich-prose corpus, **+31.4 points P@5** over its graph-disabled variant and over ripgrep-BM25 + vector-only RAG by a similar margin. Full BrainBench scorecards live in the sibling [gbrain-evals](https://github.com/garrytan/gbrain-evals) repo.

The point of building a 100K-page brain is to use it as a strategic moat. To never lose context. To query what's in your own head without re-reading it. The brain layer is what makes the moat usable. The 24/7 dream cycle is what keeps it sharp. Both run on your hardware, your DB, your keys.

It's easier to ship a daemon that runs 24/7 to ingest, enrich, and consolidate than it is to keep an agent in chat working hard. GBrain is that daemon, generalized. Install in 30 minutes. Your agent does the work. As my personal agent gets smarter, so does yours.

> **~30 minutes to a fully working brain.** Database ready in 2 seconds (PGLite, no server). You just answer questions about API keys.

> **LLMs:** fetch [`llms.txt`](llms.txt) for the documentation map, or [`llms-full.txt`](llms-full.txt) for the same map with core docs inlined in one fetch. **Agents:** start with [`AGENTS.md`](AGENTS.md) (or [`CLAUDE.md`](CLAUDE.md) if you're Claude Code).

## What this looks like

Say you have a meeting with Alice tomorrow. You want to walk in remembering what she works on, when you last talked, and what's still open between you. Here's what you'd type, and what you'd get back.

**You ask:**

> "What do I need to know before my meeting with Alice tomorrow?"

**Most personal-knowledge tools give you back a list of pages.** Something like:

```
1. people/alice — Alice runs engineering at Acme...
2. meetings/2026-03-15-alice-q1 — Q1 product review with Alice...
3. meetings/2026-01-08-acme-kickoff — Kickoff meeting with Acme team...
4. customers/acme — Acme is a series-B fintech we work with...
5. notes/2026-04-22 — Quick chat with Alice about pricing...
```

Five pages you now have to open and read yourself to actually prepare. The tool found the right material, but it didn't do the work.

**GBrain gives you back the answer, with sources:**

```
Alice runs engineering at Acme (a series-B fintech). You last spoke
on April 22 in a quick pricing chat. Three things are still open
from that conversation:

1. She owes you the security review for the new tier
   (deadline was May 1; no update since).
2. You committed to pricing for a 500-seat tier
   (you sent it April 25; no response yet).
3. She mentioned they're hiring a CISO; you said you'd intro
   someone from your network.

Heads up: nothing's been added to the brain about Alice or Acme
since April 22, six weeks ago. She may have replied through email
or Slack DM, channels the brain doesn't see. Worth asking her to
catch up before assuming any of this is still current.
```

Every claim has a source page behind it. The "heads up" at the end tells you what the brain doesn't know yet, so you can ask Alice about it directly instead of being surprised. The brain just did your meeting prep.

This is the difference between a search engine and a brain. Search finds the pages. The brain reads them for you and writes the answer.

## Install

GBrain is designed to be installed and operated by an AI agent. The fastest path is to have your agent do it for you. The CLI and MCP paths below are for people who want to wire it up themselves.

### Have your agent install it (recommended)

If you don't already have an AI agent platform running, start with one of these. Both are designed to read GBrain's install protocol and execute it:

- **[OpenClaw](https://github.com/openclawagents/openclaw)** — deploy [AlphaClaw on Render](https://render.com/deploy?repo=https://github.com/chrysb/alphaclaw) (one click, 8GB+ RAM)
- **[Hermes](https://github.com/openclawagents/hermes)** — deploy on [Railway](https://github.com/praveen-ks-2001/hermes-agent-template) (one click)

Then paste this into your agent:

```
Retrieve and follow the instructions at:
```
