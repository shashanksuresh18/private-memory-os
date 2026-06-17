# Acknowledgments

The Sovereign Citadel is built on the work of the open-source community. This
file credits projects whose ideas, patterns, or code informed this one.

## Design Inspiration

This project's workspace UI and interaction polish were informed in part by
[Odysseus](https://github.com/pewdiepie-archdaemon/odysseus), an AGPL-licensed
self-hosted AI workspace.

Specifically, Odysseus's operational, work-focused dashboard aesthetic informed
our approach to:

- Search-flow states — clearing stale results on submit, showing a loading
  skeleton while a query runs, and surfacing explicit error and empty states
  instead of leaving prior results on screen.
- Workspace-style density and visual hierarchy between query, answer, sources,
  and metadata.
- Consistent loading and disabled states for asynchronous actions.

No Odysseus source code was copied verbatim. The interaction and visual patterns
were studied and reimplemented from scratch in this project's existing
React / Vite / TypeScript stack, against our own cream-themed design tokens.

### Compare / Council Mode

The Multi-Model Compare / Council feature (`src/api/compare/`, `src/ui/compare/`)
is directly inspired by Odysseus's **Compare** feature
(`routes/compare_routes.py`, `static/js/compare/{index,stream,vote,scoreboard}.js`).
The following ideas were studied and adapted:

- sending one prompt to multiple models and showing one pane per model
- running model calls independently / in parallel
- blind comparison with neutral labels (`Model A`, `Model B`) and server-side
  mapping so identities cannot leak before reveal
- voting for a winner / tie, then revealing the model names
- a wins/losses/ties scoreboard aggregated from vote history
- per-pane latency, token counts, and timeout/error handling
- an optional synthesis ("council") step over the completed responses

These were reimplemented cleanly in our stack: a provider-agnostic FastAPI
backend that exposes only configured **cloud** providers, DLP-scrubs every
outbound prompt, and persists **hash-only** vote history; and a React/Vite/TS
front end using our own components and design tokens. No Odysseus code was
copied verbatim. Odysseus is AGPL-licensed; this is an independent
reimplementation, credited here.

## Components & Libraries

See `CLAUDE.md` ("Trusted Components & Swaps") for the full supply-chain audit
trail of the upstream projects this system integrates or draws from.
