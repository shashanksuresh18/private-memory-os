export type Tier = "S1" | "S2" | "S3";

export interface Scores {
  bm25: number;
  vector: number;
  rrf: number;
  rerank: number;
}

export interface AtomRef {
  atom_id: number;
  label: string;
  confidence: number;
  tier: Tier;
  byte_start: number;
  byte_end: number;
}

export interface CitationAnchor {
  page_path: string;
  line_start: number;
  line_end: number;
  anchor: string; // "[vault/people/alice.md:L12-14]"
}

export interface Citation {
  chunk_id: number;
  page_path: string;
  tier: Tier;
  byte_start: number;
  byte_end: number;
  line_start: number;
  line_end: number;
  score: number;
  text: string;
  scores: Scores;
  atoms: AtomRef[];
  graph_refs: string[];
}

// Canonical result shape. Source of truth: src/retrieval/engine.py -> Citation dataclass.
// types.js (the vanilla runtime's source of truth) MUST stay identical in shape:
// 5 entries covering S1, S2, S3; every entry carries >=1 atom and >=1 graph_ref so
// the UI never falls back to a "No atoms" / "No graph references" placeholder.
export const MOCK_CITATIONS: Citation[] = [
  {
    chunk_id: 1001,
    page_path: "vault/companies/northstar-semiconductors.md",
    tier: "S1",
    byte_start: 120,
    byte_end: 612,
    line_start: 8,
    line_end: 18,
    score: 0.89,
    text:
      "Public filings describe Northstar Semiconductors as expanding gross margin through mix shift, lower foundry commitments, and a narrower product roadmap for industrial customers.",
    scores: { bm25: 0.73, vector: 0.61, rrf: 0.81, rerank: 0.89 },
    atoms: [
      {
        atom_id: 511,
        label: "gross margin expansion",
        confidence: 0.7,
        tier: "S1",
        byte_start: 180,
        byte_end: 204,
      },
    ],
    graph_refs: [
      "vault/companies/northstar-semiconductors.md",
      "vault/concepts/gross-margin.md",
    ],
  },
  {
    chunk_id: 1002,
    page_path: "vault/meetings/2026-05-12-vertex-credit-call.md",
    tier: "S2",
    byte_start: 820,
    byte_end: 1388,
    line_start: 22,
    line_end: 37,
    score: 0.84,
    text:
      "The lender call flagged covenant headroom as adequate under the base case, but management sensitivity tables showed pressure if renewal bookings slip by more than eight percent.",
    scores: { bm25: 0.68, vector: 0.77, rrf: 0.8, rerank: 0.84 },
    atoms: [
      {
        atom_id: 501,
        label: "covenant headroom",
        confidence: 0.82,
        tier: "S2",
        byte_start: 858,
        byte_end: 876,
      },
    ],
    graph_refs: [
      "vault/companies/vertex-systems.md",
      "vault/people/dana-liu.md",
    ],
  },
  {
    chunk_id: 1003,
    page_path: "vault/memos/project-orchid-pre-read.md",
    tier: "S3",
    byte_start: 2048,
    byte_end: 2796,
    line_start: 41,
    line_end: 58,
    score: 0.92,
    text:
      "The sealed pre-read records a confidential downside case, including customer concentration concerns and a still-private financing discussion that must remain local only.",
    scores: { bm25: 0.71, vector: 0.86, rrf: 0.88, rerank: 0.92 },
    atoms: [
      {
        atom_id: 502,
        label: "private financing discussion",
        confidence: 0.91,
        tier: "S3",
        byte_start: 2192,
        byte_end: 2220,
      },
    ],
    graph_refs: ["vault/companies/orchid-systems.md", "vault/people/mira-kapoor.md"],
  },
  {
    chunk_id: 1004,
    page_path: "vault/companies/atlas-grid-public-notes.md",
    tier: "S1",
    byte_start: 64,
    byte_end: 488,
    line_start: 5,
    line_end: 14,
    score: 0.76,
    text:
      "Atlas Grid's public investor day emphasized regulated asset growth, grid modernization spend, and a capital plan funded mostly through retained cash flow.",
    scores: { bm25: 0.64, vector: 0.58, rrf: 0.76, rerank: 0 },
    atoms: [
      {
        atom_id: 512,
        label: "regulated asset growth",
        confidence: 0.66,
        tier: "S1",
        byte_start: 96,
        byte_end: 118,
      },
    ],
    graph_refs: [
      "vault/companies/atlas-grid.md",
      "vault/concepts/rate-base.md",
    ],
  },
  {
    chunk_id: 1005,
    page_path: "vault/meetings/2026-05-18-sable-risk-review.md",
    tier: "S2",
    byte_start: 1504,
    byte_end: 1996,
    line_start: 31,
    line_end: 45,
    score: 0.79,
    text:
      "Risk review notes identify supplier fragility, a narrow integration window, and a dependency on two customer renewals that should be monitored before committee.",
    scores: { bm25: 0.6, vector: 0.74, rrf: 0.79, rerank: 0 },
    atoms: [
      {
        atom_id: 513,
        label: "customer renewal dependency",
        confidence: 0.78,
        tier: "S2",
        byte_start: 1600,
        byte_end: 1628,
      },
    ],
    graph_refs: [
      "vault/companies/sable-industries.md",
      "vault/people/tom-reyes.md",
    ],
  },
];
