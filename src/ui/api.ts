import { type Citation, type CitationAnchor } from "./types";

const ENGINE_URL = "http://127.0.0.1:7734/retrieve";
const API_ROOT = "http://127.0.0.1:7734";

export interface EngineResponse {
  citations: Citation[];
  // Extraction-layer fields — present only when the request set answer=true
  // and the engine produced an answer.
  answer?: string;
  answer_tier?: string;
  model_used?: string;
  redacted?: boolean;
  anchors?: CitationAnchor[];
}

export interface Stats {
  pages: number;
  chunks: number;
  tiers: Record<"S1" | "S2" | "S3", number>;
  meetings: number;
  graph_edges: number;
}

export interface PageSummary {
  page_path: string;
  tier: "S1" | "S2" | "S3";
  chunk_count: number;
  line_count: number;
  first_chunk?: Citation;
}

export interface CrmPerson {
  name: string;
  slug: string;
  company: string | null;
  role: string | null;
  tier: "S1" | "S2" | "S3";
  sealed: boolean;
}

export interface CrmCompany {
  name: string;
  slug: string;
  type: string | null;
  tier: "S1" | "S2" | "S3";
  sealed: boolean;
}

export interface CrmResponse {
  people: CrmPerson[];
  companies: CrmCompany[];
}

export interface HealthResponse {
  status: string;
  egress: string;
  cloudAllowed: boolean;
  gbrain?: Record<string, string>;
  s3_zero_egress_test?: string;
  audit_entries?: Array<{
    timestamp: string;
    tier: string;
    query_hash: string;
    model_used: string;
  }>;
}

function normalizeCitation(citation: Citation): Citation {
  const score = Number(citation.score || 0);
  return {
    ...citation,
    scores: citation.scores ?? { bm25: 0, vector: 0, rrf: score, rerank: 0 },
    atoms: citation.atoms ?? [],
    graph_refs: citation.graph_refs ?? [],
  };
}

export async function queryEngine(
  query: string,
  tier: string,
  k: number = 10,
): Promise<Citation[]> {
  // Surface failures to the caller so the UI can show a real error state.
  // Returning mock data here previously masked outages and rendered stale/fake
  // citations as if they belonged to the live query.
  let res: Response;
  try {
    res = await fetch(ENGINE_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, tier, k }),
    });
  } catch {
    throw new Error("Engine unreachable - start the local server (127.0.0.1:7734) and try again.");
  }
  if (!res.ok) throw new Error(`Search failed (HTTP ${res.status}).`);
  const data = await res.json();
  return (data.citations ?? []).map(normalizeCitation);
}

/**
 * Query the engine with the extraction answer layer enabled. Returns the full
 * response (citations + answer + anchors). Falls back to mock citations and no
 * answer when the engine is unreachable.
 */
export async function queryEngineWithAnswer(
  query: string,
  tier: string,
  k: number = 10,
): Promise<EngineResponse> {
  let res: Response;
  try {
    res = await fetch(ENGINE_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, tier, k, answer: true }),
    });
  } catch {
    throw new Error("Engine unreachable - start the local server (127.0.0.1:7734) and try again.");
  }
  if (!res.ok) throw new Error(`Search failed (HTTP ${res.status}).`);
  const data = await res.json();
  return {
    ...data,
    citations: (data.citations ?? []).map(normalizeCitation),
  };
}

export async function fetchStats(): Promise<Stats> {
  const res = await fetch(`${API_ROOT}/stats`);
  if (!res.ok) throw new Error(`stats failed: ${res.status}`);
  return res.json();
}

export async function fetchPages(tier?: string): Promise<PageSummary[]> {
  const qs = tier && tier !== "All" ? `?tier=${encodeURIComponent(tier)}` : "";
  const res = await fetch(`${API_ROOT}/pages${qs}`);
  if (!res.ok) throw new Error(`pages failed: ${res.status}`);
  const data = await res.json();
  return data.pages ?? [];
}

export async function fetchCrm(): Promise<CrmResponse> {
  const res = await fetch(`${API_ROOT}/crm`);
  if (!res.ok) throw new Error(`crm failed: ${res.status}`);
  return res.json();
}

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_ROOT}/health`);
  if (!res.ok) throw new Error(`health failed: ${res.status}`);
  return res.json();
}

export interface IngestResponse {
  filename: string;
  tier: "S1" | "S2" | "S3";
  chunks: number;
  status: string;
}

/**
 * Add a document to the vault via POST /ingest. Raw notes are structured into
 * markdown locally (gemma4-citadel, loopback only) and incrementally indexed;
 * S3 content never leaves the machine. Surfaces the server's plain-English
 * error message on failure.
 */
export async function addDocument(payload: {
  content: string;
  doc_type: string;
  tier: string;
  title?: string;
}): Promise<IngestResponse> {
  let res: Response;
  try {
    res = await fetch(`${API_ROOT}/ingest`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new Error("Engine unreachable - start the local server and try again.");
  }
  if (!res.ok) {
    let detail = `Add failed (HTTP ${res.status}).`;
    try {
      const data = await res.json();
      if (data?.detail) {
        detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
      }
    } catch {
      // keep the default detail
    }
    throw new Error(detail);
  }
  return res.json();
}
