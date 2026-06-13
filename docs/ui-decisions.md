# UI Decisions — Sovereign Citadel
**Date:** 2026-05-30  
**Status:** Approved — Claude Code works from this document  
**Source design:** Aleph (claude.ai/design)  
**Do not deviate from this spec without updating this file first.**

---

## 1. What we are building

A local-first query interface for the Sovereign Citadel retrieval engine.  
One screen does the core job: type a query, see ranked citations with tier 
badges and fusion scores, click a citation to see the source byte slice.  
Everything else is chrome around that loop.

---

## 2. Adopt as-is (copy from Aleph files, zero changes)

| Component | Aleph file | Notes |
|---|---|---|
| TierBadge | tier-badge.tsx | Remap colors only (see §6) |
| KindBadge | kind-badge.tsx | primary = vault doc, generated = atom |
| EvidencePin | evidence-pin.tsx | Wire to Citation.line_start/end |
| ConfBar | conf-bar.tsx | Shows final fused score |
| SafetyBar | safety-bar.tsx | cloudAllowed: false hardcoded, keep |
| Audit log pattern | audit screen | Maps to hash-chained audit entries |
| Evidence Vault table | vault screen | Tier-filterable source inventory |
| CommandPalette | command-palette.tsx | Primary search entry point |
| Settings screen | settings screen | Routing policy toggles |
| Token system | colors_and_type.css | Remap 3 tier tokens only |
| Btn, Input, Badge, Icon, Kbd, Card, Stat, Sidebar, TopBar | primitives | Use verbatim |

---

## 3. Adapt (copy then modify)

### 3a. EvidenceRef → Citation
Aleph's EvidenceRef is lossy for our engine.  
Extend it with these fields before wiring any component:

```typescript
// src/ui/types.ts — extend EvidenceRef with:
interface Scores {
  bm25:   number   // raw BM25 rank score
  vector: number   // cosine similarity
  rrf:    number   // RRF fused score
  rerank: number   // cross-encoder score (0 if reranker skipped)
}

interface AtomRef {
  atom_id:    number
  label:      string
  confidence: number
  tier:       'S1' | 'S2' | 'S3'
  byte_start: number
  byte_end:   number
}

interface Citation {
  chunk_id:    number
  page_path:   string
  tier:        'S1' | 'S2' | 'S3'
  byte_start:  number
  byte_end:    number
  line_start:  number
  line_end:    number
  score:       number
  text:        string
  scores:      Scores
  atoms:       AtomRef[]
  graph_refs:  string[]
}
```

This is the canonical result shape. Every UI component reads from this.  
Source of truth: `src/retrieval/engine.py` → `Citation` dataclass.

### 3b. Memo Viewer → Citation Viewer
Repurpose the citation sidebar from Memo Viewer.  
Change: it must be query-result-centric, not memo-centric.  
Keep: pin → evidence card pattern, quote display, KindBadge, ConfBar.  
Remove: memo prose area, claim list.

### 3c. CommandPalette → Search Entry
Wire to real `retrieve()` call via local API.  
Input: query string + tier selector (S1/S2/S3 or Auto).  
Output: ranked Citation list → feeds Search Results view.  
Keep: keyboard nav, ⌘K trigger, overlay pattern.

### 3d. Tier colors
Remap these 3 tokens in `colors_and_type.css` only:

```css
--tier-s1: /* sky blue  — public */
--tier-s2: /* amber     — sensitive */
--tier-s3: /* rose/red  — sealed, confidential, most prominent */
```

Do not change any other color tokens.  
Keep emerald exclusively for primary-evidence (never a tier color).

---

## 4. Ignore completely (do not port)

| Screen / Component | Reason |
|---|---|
| Relationship Queue | CRM layer, not retrieval |
| GBrain Sync screen | External sidecar, not our engine |
| Email connector groups | Not ingesting mail |
| Concept covers | Marketing, not product UI |
| ScreenStub | Dev scaffolding only |

---

## 5. Build from scratch (nothing exists in Aleph)

These are greenfield. Build in Aleph visual language using the token system.

### 5a. Search Results View
Primary screen. Does not exist in Aleph.

```typescript
// Layout: query bar (top) → tier filter → ranked result list
// Each row = ResultCard:
{
  rank:       number
  citation:   Citation      // the extended shape from §3a
  tier_badge: TierBadge
  score_bar:  ScoreBreakdown
  preview:    string        // first 200 chars of citation.text
}
```

### 5b. ScoreBreakdown Component
Does not exist. Replaces single ConfBar for result cards.

```typescript
// Shows 4 bars or a horizontal breakdown:
{ bm25: number, vector: number, rrf: number, rerank: number }
// Final fused score = rerank if available, else rrf
// Collapse to single ConfBar if reranker was skipped
```

### 5c. Atom Inspector
Does not exist. Triggered from a result card.

```
AtomChip (inline) → expands to:
  - atom_id, label, confidence, tier badge
  - byte_start / byte_end (human readable: "lines 12–14")
  - "Resolve to source" button → opens Citation Viewer at that span
```

### 5d. Knowledge Graph View
Does not exist. Lowest priority — build last.

```
Nodes = pages (colored by tier)
Edges = typed relationships (attended/works_at/invested_in etc.)
Click node → open Evidence Vault filtered to that page
Tier gate: S3 nodes only visible in S3 query context
Use: graphify-out/graph.json (already generated)
```

---

## 6. Font fix (do before anything else)

Aleph imports Geist from Google Fonts — a network call on every load.  
This is the only cloud call in the entire design.  
**Self-host the .woff2 files before wiring any UI.**

```
1. Download Geist from github.com/vercel/geist-font
2. Place in src/ui/dashboard/fonts/
3. Replace @import in colors_and_type.css with @font-face pointing to 
   local path
4. Verify: load UI with network disconnected — font must render correctly
```

---

## 7. What Claude Code must NOT do

- Do not add any authentication layer
- Do not add any external API call (including fonts from CDN)
- Do not collapse tier into a visual indicator that is ever hidden
- Do not merge S2/S3 results into the same view without explicit tier filter
- Do not use the old static mock data from Aleph result sets —
  all data comes from the real retrieve() call
- Do not start a background daemon or scheduled task
- Do not add copy/export button on any S3 content

---

## 8. Local API contract

Claude Code will need a thin local server to bridge UI → Python engine.  
Before building the server, confirm:
- Port: localhost only, no 0.0.0.0 bind
- No auth (local only)
- Every response includes tier field
- S3 requests: server must assert zero non-loopback sockets during handling

This is a separate task. Do not build UI components that assume the 
server exists yet — use the deterministic mock embedder pattern from 
tests/ for now.

---

## 9. Build order

1. Font fix (§6)
2. Extend types — src/ui/types.ts (§3a)
3. Adopt Aleph components as-is (§2)
4. Search Results View + ResultCard (§5a)
5. ScoreBreakdown Component (§5b)
6. Citation Viewer (§3b)
7. AtomChip + Atom Inspector (§5c)
8. Wire CommandPalette to mock engine (§3c)
9. Knowledge Graph View (§5d) — last
10. Local API server — separate session

Do not skip steps or reorder. Each step's output is the next step's input.
