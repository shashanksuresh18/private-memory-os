# Sovereign Citadel

Local-first research memory for finance professionals working with public data, sensitive notes, and confidential investment material.

## What it does

- Converts notes, PDFs, Word, Excel, PowerPoint, text, and markdown into indexed vault pages.
- Searches a local SQLite retrieval database using BM25, vectors, reranking, and citations.
- Routes answers by data tier: public, sensitive, or confidential.
- Keeps S3 confidential data on the machine, enforced by automated egress tests.

## Architecture

Sovereign Citadel stores documents in an Obsidian-style vault, converts them into markdown, indexes chunks into `retrieval.db`, serves retrieval through a local FastAPI API, and exposes a local React UI.

```text
vault/
  raw/s1/  public files
  raw/s2/  sensitive files
  raw/s3/  confidential files
    |
    v
ingest + conversion
    |
    v
retrieval.db
    |
    v
API 127.0.0.1:7734
    |
    v
UI 127.0.0.1:3003

Tier flow:
S1 public          -> cloud answers allowed through Nebius / DeepSeek-V3.2
S2 sensitive       -> DLP scrubbed before cloud answers
S3 confidential    -> local-only gemma4-citadel, never cloud
```

## Requirements

- Python 3.11+
- Node.js 18+
- Ollama local AI runtime
- 32GB RAM recommended
- 30GB free disk for model weights
- Windows 10/11

## Quick Start

1. Clone the repo.

```powershell
git clone https://github.com/shashanksuresh18/private-memory-os.git
cd private-memory-os
```

2. Run setup. This installs dependencies and pulls local models. Expect about 30 minutes on a first run.

```powershell
.\setup.bat
```

3. Copy the environment template and fill in keys.

```powershell
copy .env.example .env
notepad .env
```

4. Start the local API and UI.

```powershell
.\launch.bat
```

5. Open the UI.

```text
http://127.0.0.1:3003
```

## Environment Variables

| Variable | Required | Description |
|---|---:|---|
| `NEBIUS_API_KEY` | Yes for S1/S2 cloud answers | Nebius API key used for DeepSeek-V3.2 answers. |
| `NEBIUS_BASE_URL` | Yes for S1/S2 cloud answers | Nebius OpenAI-compatible base URL. |
| `GMAIL_CLIENT_ID` | Yes for Gmail sync | Google OAuth client ID. |
| `GMAIL_CLIENT_SECRET` | Yes for Gmail sync | Google OAuth client secret. |
| `GMAIL_REFRESH_TOKEN` | Yes for Gmail sync | Refresh token with Gmail read-only scope. |
| `GMAIL_ACCOUNTS_JSON` | Yes for Gmail sync | Gmail account configuration JSON. |
| `CALENDAR_CLIENT_ID` | Yes for Calendar sync | Google OAuth client ID for Calendar. |
| `CALENDAR_CLIENT_SECRET` | Yes for Calendar sync | Google OAuth client secret for Calendar. |
| `CALENDAR_REFRESH_TOKEN` | Yes for Calendar sync | Refresh token with Calendar read-only scope. |

## Adding Documents

1. UI: click **Add Document** in the sidebar and paste notes.
2. File drop: drag files into `vault\raw\s1\`, `vault\raw\s2\`, or `vault\raw\s3\`.
3. Auto-fetch: sync Gmail and Calendar metadata/content through the provided scripts.

Supported file drop formats:

```text
.pdf
.docx
.xlsx
.pptx
.txt
.md
```

## Data Tiers

| Tier | What it means | AI model used | Leaves machine? |
|---|---|---|---|
| S1 | Public data | DeepSeek-V3.2 | Yes, for answers only |
| S2 | Sensitive data | DeepSeek-V3.2 | DLP-scrubbed only |
| S3 | MNPI or confidential data | gemma4-citadel local | Never |

If the system is unsure, it fails closed to S3.

## Security

- S3 data never leaves the machine. This is covered by `tests/retrieval/test_no_egress_on_s3.py`.
- S2 data is DLP-scrubbed before any cloud egress.
- Local servers bind to `127.0.0.1` only.
- No telemetry or analytics.
- External model calls are limited to Nebius for S1 answers and DLP-scrubbed S2 answers.
- Document conversion uses local MarkItDown with plugins and LLM clients disabled.

## Project Structure

```text
src/api/              FastAPI server and local endpoints
src/retrieval/        Retrieval engine, indexing, embeddings, reranking, answers
src/ingest/           Document conversion and structured markdown generation
src/ui/               React, Vite, and TypeScript UI
scripts/              Gmail, Calendar, EDGAR, ingest, and setup helpers
tests/                Safety, retrieval, ingest, API, and routing tests
config/               Tier, budget, and scheduler configuration
docs/                 Setup notes, handoff, and project documentation
vault/raw/            Client drop folders by tier
vault/inbox/          Generated markdown pages, ignored by Git
```

## Running Tests

```powershell
python -m pytest tests/ -q
```

Expected:

```text
186 passed, 1 skipped
```

Run the S3 egress gate directly:

```powershell
python -m pytest tests/retrieval/test_no_egress_on_s3.py -q
```

Expected:

```text
12 passed
```

## Tech Stack

- Python and FastAPI for the API server
- React, Vite, and TypeScript for the UI
- SQLite with FTS5 for the retrieval database
- Ollama for local AI: `gemma4-citadel` and `nomic-embed-text`
- Nebius and DeepSeek-V3.2 for S1/S2 cloud answers
- watchdog for vault file watching
- MarkItDown for document conversion

## License

MIT
