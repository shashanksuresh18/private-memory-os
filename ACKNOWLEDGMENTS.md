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

## Components & Libraries

See `CLAUDE.md` ("Trusted Components & Swaps") for the full supply-chain audit
trail of the upstream projects this system integrates or draws from.
