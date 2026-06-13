# Sovereign Citadel — Setup Guide

Your private research brain. It reads your documents and answers questions
about them on **your own laptop**. Confidential material never leaves the
machine.

You only ever need to do two things: **install three programs once**, then
**double-click `launch.bat`** whenever you want to use it.

---

## Part 1 — Install three programs (one time only)

Install these in order. Click each link, download, run the installer, accept
the defaults. Restart the laptop after all three are installed.

| # | Program | Download link | Notes |
|---|---------|---------------|-------|
| 1 | **Python** | https://www.python.org/downloads/ | On the **first** installer screen, tick the box **"Add python.exe to PATH"** before clicking Install. This box matters — don't skip it. |
| 2 | **Ollama** | https://ollama.com/download | This is the local AI engine. Just install it; the launcher starts it for you. |
| 3 | **Node.js** | https://nodejs.org/ | Pick the **LTS** (green) button. Only needed if your technical contact asks you to rebuild the screen; the app runs without it day-to-day. |

That's it. You never open these programs yourself — `launch.bat` does it.

---

## Part 2 — Start the app

1. Open the **`sovereign-citadel`** folder.
2. Double-click **`launch.bat`**.
3. A black window appears and shows progress: `[1/4] … [2/4] … [3/4] … [4/4]`.
4. Your web browser opens automatically to the app.

The first launch can take a minute while the AI engine wakes up. That's
normal. Leave the two minimized windows on the taskbar (named "Citadel API"
and "Citadel UI") **open** while you work — they are the brain and the screen.
You can close the black window once the browser has opened.

To stop everything: close the two "Citadel" windows on the taskbar.

---

## Part 3 — Add your documents

1. Inside the `sovereign-citadel` folder, open the **`vault`** folder, then the
   **`raw`** folder.
2. **Drop each file into the folder that matches how confidential it is.**
   Inside `vault\raw\` there are three folders:

   | Folder | Put here | Examples |
   |--------|----------|----------|
   | **`vault\raw\s1\`** | **Public** material — already public, safe for a cloud model | Public reports, SEC filings, news articles |
   | **`vault\raw\s2\`** | **Sensitive** but not secret — internal, no MNPI | Meeting notes, internal documents |
   | **`vault\raw\s3\`** | **Confidential** — anything secret or market-moving | Board memos, deal documents, anything confidential |

   **If you are not sure, use `s3`.** It is the safest choice — those files are
   answered entirely on your laptop and never leave it.
3. Supported file types (any folder):
   - PDF (`.pdf`)
   - Word (`.docx`)
   - Excel (`.xlsx`)
   - PowerPoint (`.pptx`)
   - Plain text (`.txt`)
   - Markdown (`.md`)
4. Wait. Every 10 minutes the system automatically converts and reads new
   files. Within about 10 minutes they become searchable. There is nothing to
   click — just drop and wait.

> **Privacy default:** if you drop a file straight into `vault\raw\` (not into
> one of the three folders), it is treated as **most-confidential (S3)** —
> answered entirely on your laptop and never sent anywhere. The system always
> fails safe: unsure means confidential.

---

## Part 4 — Ask questions

1. In the app, type your question in the question box (for example,
   *"What was Meridian's Q3 revenue?"*).
2. Press **Enter** or click **Ask**.
3. The answer appears with the **source passages** it came from, so you can
   verify every claim against your own documents.

Answers about confidential documents are produced locally. Public questions
(SEC filings, market data) may use a cloud model for a fuller answer, clearly
labelled when they do.

---

## Troubleshooting

Each problem below is something you can fix yourself without typing commands.

### "The browser opened but the page is blank or says it can't connect"
The brain needs a few more seconds. Wait 30 seconds and refresh the page (F5).
If still blank, close everything and double-click `launch.bat` again.

### The black window says **"Ollama did not start"**
Ollama isn't installed, or didn't finish installing. Re-install it from
https://ollama.com/download, restart the laptop, then double-click
`launch.bat` again.

### The black window says **"port already in use"** or **"port 3003"**
The app is already running from an earlier double-click. Look on your taskbar
for the two minimized "Citadel" windows — the app is probably already open in
a browser tab. If unsure: close the two "Citadel" windows, wait ten seconds,
and double-click `launch.bat` once more.

### "I added a file but can't find it when I search"
- Give it up to 10 minutes — indexing runs on a timer.
- Check the file is one of the supported types in Part 3.
- Make sure you dropped it in **`vault\raw\`**, not somewhere else.

### "Windows warns me about running launch.bat"
The first time, Windows may ask if you trust the file. Choose **More info →
Run anyway**. It is a local script that only starts the app on your machine.

### Nothing here helped
Close the two "Citadel" taskbar windows, restart the laptop, and double-click
`launch.bat` again. A restart clears almost every stuck state. If it still
fails, send your technical contact a photo of the black window's error text.

---

## What's running (for your technical contact)

- **Ollama** — local model host on `127.0.0.1:11434` (nomic-embed-text for
  indexing, gemma4-citadel for confidential answers).
- **API server** — `127.0.0.1:7734` (FastAPI, loopback-only, fail-closed
  tier routing).
- **UI server** — `127.0.0.1:3003` (serves the built app from
  `src/ui/dist`).
- **Auto-ingest** — Windows Task Scheduler job `retrieval_incremental_ingest`
  runs `python scripts/ingest_new.py --reindex` every 10 minutes; that pass
  now also stages anything dropped in `vault/raw/` (convert → inbox → index →
  archive). Nightly `retrieval_full_rebuild` at 03:30 re-embeds edited pages.
- All confidential (S3) paths are local-only; verified by
  `tests/retrieval/test_no_egress_on_s3.py`.
