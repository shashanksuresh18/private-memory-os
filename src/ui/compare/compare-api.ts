// Fetch client for Compare / Council mode (cloud-only, normal chat feature).
// Same base + error conventions as ../api.ts: throw on unreachable / non-OK and
// surface the server's plain-English `detail`. Never silent-fallback.

const API_ROOT = 'http://127.0.0.1:7734';
const BASE = `${API_ROOT}/api/compare`;

export interface CompareModel {
  id: string;
  provider: string;
  model: string;
  label: string;
  kind: string;
}

export interface PaneInfo {
  pane_id: string;
  label: string;
  model_id: string | null;
  provider: string | null;
  model: string | null;
  model_label: string | null;
}

export interface StartResponse {
  comp_id: string;
  blind: boolean;
  panes: PaneInfo[];
}

export type RunStatus = 'ok' | 'error' | 'timeout';

export interface RunResponse extends PaneInfo {
  status: RunStatus;
  text: string;
  latency_ms: number;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  error: string | null;
}

export interface RevealResponse {
  comp_id: string;
  revealed: boolean;
  panes: PaneInfo[];
}

export interface DebateResponse extends PaneInfo {
  status: RunStatus;
  text: string;
  latency_ms: number;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  round: number;
  error: string | null;
}

export interface VoteResponse {
  comp_id: string;
  winner: string;
  winner_model_id: string | null;
  panes: PaneInfo[];
}

export interface JuryScore {
  label: string; // the neutral label of the SCORED peer (e.g. "Model B")
  score: number;
  reason: string;
}

export interface RankResponse extends PaneInfo {
  status: RunStatus;
  scores: JuryScore[];
  latency_ms: number;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  error: string | null;
}

export interface SynthesizeResponse {
  synthesis: string;
  model_id: string;
  model: string;
  provider: string;
  latency_ms: number;
}

export interface ScoreRow {
  model_id: string;
  wins: number;
  losses: number;
  ties: number;
  games: number;
  win_pct: number;
}

export interface HistoryEntry {
  comp_id: string;
  blind: boolean;
  models: string[];
  winner_model_id: string | null;
  created_at: string;
}

export interface HistoryResponse {
  history: HistoryEntry[];
  scoreboard: ScoreRow[];
}

export interface VotePanePayload {
  pane_id: string;
  status?: string;
  latency_ms?: number;
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  text?: string;
}

async function readError(res: Response, fallback: string): Promise<string> {
  try {
    const data = await res.json();
    if (data?.detail) {
      return typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
    }
  } catch {
    // keep fallback
  }
  return fallback;
}

async function postJSON<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal,
    });
  } catch (err) {
    if ((err as Error)?.name === 'AbortError') throw err;
    throw new Error('Compare server unreachable - start the local server (127.0.0.1:7734) and try again.');
  }
  if (!res.ok) throw new Error(await readError(res, `Request failed (HTTP ${res.status}).`));
  return res.json() as Promise<T>;
}

export async function fetchCompareModels(): Promise<CompareModel[]> {
  const res = await fetch(`${BASE}/models`);
  if (!res.ok) throw new Error(`models failed: ${res.status}`);
  const data = await res.json();
  return data.models ?? [];
}

export function startCompare(prompt: string, modelIds: string[], blind: boolean): Promise<StartResponse> {
  return postJSON<StartResponse>('/start', { prompt, model_ids: modelIds, blind });
}

export function runPane(compId: string, paneId: string, signal?: AbortSignal): Promise<RunResponse> {
  return postJSON<RunResponse>('/run', { comp_id: compId, pane_id: paneId }, signal);
}

export function revealCompare(compId: string): Promise<RevealResponse> {
  return postJSON<RevealResponse>('/reveal', { comp_id: compId });
}

export function debateRound(
  compId: string,
  paneId: string,
  peers: Array<{ label: string; text: string }>,
  round: number,
): Promise<DebateResponse> {
  return postJSON<DebateResponse>('/debate', { comp_id: compId, pane_id: paneId, peers, round });
}

export function voteCompare(compId: string, winner: string, panes: VotePanePayload[]): Promise<VoteResponse> {
  return postJSON<VoteResponse>('/vote', { comp_id: compId, winner, panes });
}

// One juror scores its peers. Peers are passed by pane_id (NOT label/name) — the
// server resolves each to its neutral session label, so the jury never sees a
// model's identity, even outside blind mode.
export function rankJury(
  compId: string,
  paneId: string,
  peers: Array<{ pane_id: string; text: string }>,
): Promise<RankResponse> {
  return postJSON<RankResponse>('/rank', { comp_id: compId, pane_id: paneId, peers });
}

export function synthesize(
  compId: string,
  synthModelId: string,
  responses: Array<{ label: string; text: string }>,
): Promise<SynthesizeResponse> {
  return postJSON<SynthesizeResponse>('/synthesize', {
    comp_id: compId,
    synth_model_id: synthModelId,
    responses,
  });
}

export async function fetchCompareHistory(): Promise<HistoryResponse> {
  const res = await fetch(`${BASE}/history`);
  if (!res.ok) throw new Error(`history failed: ${res.status}`);
  return res.json();
}
