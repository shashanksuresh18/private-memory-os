# Graph extraction — port plan (P4 prerequisite)

**Source:** `repos-audit/garrytan__gbrain/src/core/link-extraction.ts` (READ-ONLY clone, 935 lines).
**Verdict:** Link/frontmatter extraction is **100% local-deterministic. Zero LLM calls in the extraction path.**

## Evidence

| Line | Finding |
|---|---|
| 1-15 | JSDoc: "All functions are PURE (no DB access). The DB lives in the engine." |
| 46  | `DIR_PATTERN` — alternation of directory prefixes (`people|companies|meetings|concepts|...`). String constant, no I/O. |
| 58-61 | `ENTITY_REF_RE` — `\[([^\]]+)\]\((?:\.\.\/)*(${DIR_PATTERN}\/[^)\s]+?)(?:\.md)?\)`. Regex only. |
| 71-74 | `WIKILINK_RE` — `\[\[(${DIR_PATTERN}\/[^|\]#]+?)(?:#[^|\]]*?)?(?:\|([^\]]+?))?\]\]`. Regex only. |
| 88-91 | `QUALIFIED_WIKILINK_RE` — `\[\[([a-z0-9-]{1,32}):(${DIR_PATTERN}\/...)...\]\]`. Regex only. |
| 99-127 | `stripCodeBlocks` — pure char scan over the markdown source. No I/O. |
| 150 | `CODE_REF_REGEX` — `\b((?:src\|lib\|...)\/[\w./-]+\.(?:ts\|py\|...))(?::(\d+))?\b`. Regex only. |
| 493 | `PARTNER_ROLE_RE` — verb regex for inference heuristic. Regex only. |
| 649-655 | Comment: "batch mode (gbrain extract) — pg_trgm only, NO search fallback ... avoids N-thousand OpenAI embedding calls + Anthropic Haiku expansion calls ... keeps the backfill deterministic." |

Grep over `(llm\|anthropic\|openai\|api\|client\.chat\|gateway\|embed\|model)`:

```
493:const PARTNER_ROLE_RE = /\b(?:partner at|partner of|venture partner|VC partner|...)\b/i;
544:  // about VC topics naturally contain "venture capital" in their text, but
649: * fallback. On a 46K-page brain this avoids N-thousand OpenAI embedding
```

All three matches are in regex literals or comments — none are call sites. Confirmed: extraction is pure regex + (optionally) `pg_trgm` slug resolution.

## What we port (Python)

The Sovereign Citadel engine never touches gbrain's DB, so we port the regex shapes only and adapt to our `pages`/`chunks` schema.

| Element | gbrain shape | Sovereign Citadel port |
|---|---|---|
| Directory whitelist | `DIR_PATTERN` constant string | `DIR_PATTERN = "(?:people\|companies\|meetings\|memos\|concepts\|inbox)"` — matches our gbrain-base vault layout |
| Markdown entity ref | `[Name](dir/slug)` | Same regex, byte-aware (we operate on bytes for UTF-8 safety) |
| Obsidian wikilink | `[[dir/slug\|Display]]` | Same regex |
| Source-qualified wikilink | `[[source-id:dir/slug]]` | DROPPED — single-source by default; can add later if multi-source lands |
| Frontmatter typed fields | `FRONTMATTER_LINK_MAP` array of `{fields, type, direction, dirHint}` | Python list of dataclasses; same field types (`attendees`/`audience`/`company`/etc.) |
| Slug resolver | `pg_trgm` + per-run cache | DROPPED for P4 — we resolve via exact slug match; fuzzy resolution is future work |
| Verb-based inference | `inferLinkType()` heuristic regexes | Subset port: `attended`, `works_at`, `mentioned_in` — the three classes that fire on synthetic data |

## What we DROP (out of scope for P4)

- **Code references** (`CODE_REF_REGEX`) — tied to gbrain's TS-aware schema; we have no code pages.
- **Source-qualified wikilinks** — multi-source is a v2 concern.
- **Partner-role inference** (`PARTNER_ROLE_RE`) — domain-specific; can add per use case.
- **`pg_trgm` fuzzy resolver** — requires a Postgres install; we are SQLite-only.

## Composite-tier rule (load-bearing)

`edge.tier = MAX(tier_src, tier_dst)` where MAX is most-restrictive (`S3 > S2 > S1`). Enforced at the extractor: every emitted edge looks up both endpoint pages' tiers and stores the composite. This means an S3 memo linking to an S1 public page produces an S3 edge — the S3-never-cloud invariant follows by construction whenever the graph track joins fused results.

## Python implementation footprint

```
src/memory/graph/
  schema.sql      edges(src_page, dst_page, edge_type, confidence, tier)
  db.py           connect + reset
  extractor.py    Python port of regex set + FRONTMATTER_LINK_MAP
  expand.py       expand(chunk_ids, depth=1, direction='both') -> chunk_ids
```

Wired as the 5th RRF track inside `src/retrieval/engine.py`, behind a `enable_graph` flag (default `True` for `S1`, default `False` for `S2`/`S3`). Independent re-implementation keeps us offline even if gbrain regresses.

## Verification posture

`tests/retrieval/test_tier_integrity.py` extended to assert:

1. `composite_tier(S3, S1) == S3` — most-restrictive composite.
2. A query against an S3 page that references an S1 page returns rows tagged `tier=S3`, never `S1`.
3. The graph track never opens a non-loopback socket (covered by the existing `test_no_egress_on_s3` socket fence).
