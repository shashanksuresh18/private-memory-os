import * as React from 'react';
import {
  debateRound,
  fetchCompareModels,
  rankJury,
  revealCompare,
  runPane,
  startCompare,
  synthesize,
  voteCompare,
  type CompareModel,
  type JuryScore,
  type PaneInfo,
  type StartResponse,
} from './compare-api';

// Client-side backstop timeout. The server enforces its own per-model budget
// (COMPARE_TIMEOUT_S, default 60s); this aborts a hung connection a little after
// that so a pane can never spin forever.
const CLIENT_TIMEOUT_MS = 75000;

export type PaneStatus = 'pending' | 'loading' | 'ready' | 'error' | 'timeout';
type LoadStatus = 'loading' | 'ready' | 'error';
type SynthStatus = 'idle' | 'loading' | 'ready' | 'error';

export interface RoundEntry {
  round: number;
  status: PaneStatus;
  text: string;
  latency_ms: number | null;
  completion_tokens: number | null;
  error: string | null;
}

export interface PaneState {
  pane_id: string;
  label: string;
  info: PaneInfo;
  status: PaneStatus;
  text: string;
  latency_ms: number | null;
  prompt_tokens: number | null;
  completion_tokens: number | null;
  error: string | null;
  rounds: RoundEntry[]; // debate turns AFTER the initial answer
}

type JuryStatus = 'idle' | 'running' | 'ready' | 'error';

export interface JuryCell {
  score: number;
  reason: string;
}

export interface JuryState {
  status: JuryStatus;
  // matrix[jurorPaneId][targetPaneId] = the score the juror gave that target.
  matrix: Record<string, Record<string, JuryCell>>;
  // means[targetPaneId] = mean score that target RECEIVED (null if unscored).
  means: Record<string, number | null>;
  winnerPaneId: string | null; // pane_id, "tie", or null (not yet run)
  errors: Record<string, string>; // jurorPaneId -> error, for jurors that failed
  error: string | null; // top-level jury error (e.g. too few answers)
}

const JURY_IDLE: JuryState = {
  status: 'idle',
  matrix: {},
  means: {},
  winnerPaneId: null,
  errors: {},
  error: null,
};

// Two means count as a tie when within this band, so a hair-thin lead is not
// reported as a decisive jury winner.
const JURY_TIE_EPSILON = 0.05;

interface AbortMeta {
  controller: AbortController;
  timedOut: boolean;
}

function paneInfo(info: PaneInfo): PaneInfo {
  return {
    pane_id: info.pane_id,
    label: info.label,
    model_id: info.model_id,
    provider: info.provider,
    model: info.model,
    model_label: info.model_label,
  };
}

export function useCompare() {
  const [models, setModels] = React.useState<CompareModel[]>([]);
  const [modelsStatus, setModelsStatus] = React.useState<LoadStatus>('loading');
  const [modelsError, setModelsError] = React.useState<string | null>(null);

  const [selected, setSelected] = React.useState<string[]>([]);
  const [blind, setBlind] = React.useState(false);
  const [prompt, setPrompt] = React.useState('');

  const [compId, setCompId] = React.useState<string | null>(null);
  const [blindActive, setBlindActive] = React.useState(false);
  const [revealed, setRevealed] = React.useState(false);
  const [panes, setPanes] = React.useState<PaneState[]>([]);
  const [winner, setWinner] = React.useState<string | null>(null);
  const [topError, setTopError] = React.useState<string | null>(null);

  const [debateRounds, setDebateRounds] = React.useState(2);
  const [debating, setDebating] = React.useState(false);
  const [debateError, setDebateError] = React.useState<string | null>(null);

  const [synthModelId, setSynthModelId] = React.useState('');
  const [synthesisState, setSynthesis] = React.useState<{ status: SynthStatus; text: string; error: string | null }>({
    status: 'idle',
    text: '',
    error: null,
  });

  const [jury, setJury] = React.useState<JuryState>(JURY_IDLE);

  const abortRef = React.useRef<Map<string, AbortMeta>>(new Map());

  React.useEffect(() => {
    let cancelled = false;
    setModelsStatus('loading');
    fetchCompareModels()
      .then((ms) => {
        if (cancelled) return;
        setModels(ms);
        setModelsStatus('ready');
        setSynthModelId((cur) => cur || ms[0]?.id || '');
      })
      .catch((err) => {
        if (cancelled) return;
        setModelsError((err as Error).message);
        setModelsStatus('error');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const updatePane = React.useCallback((paneId: string, patch: Partial<PaneState>) => {
    setPanes((prev) => prev.map((p) => (p.pane_id === paneId ? { ...p, ...patch } : p)));
  }, []);

  // Merge revealed model identities back onto panes (used by reveal / vote / jury).
  const applyInfos = React.useCallback((infos: PaneInfo[]) => {
    setPanes((prev) =>
      prev.map((p) => {
        const info = infos.find((x) => x.pane_id === p.pane_id);
        return info ? { ...p, info } : p;
      }),
    );
  }, []);

  // Build the hash-only pane payload for /vote. Votes are cast on each pane's
  // LATEST position (final debate round if any, else the initial answer).
  const buildVotePanes = React.useCallback(
    () =>
      panes.map((p) => {
        const last = p.rounds.length ? p.rounds[p.rounds.length - 1] : null;
        return {
          pane_id: p.pane_id,
          status: last ? last.status : p.status,
          latency_ms: (last ? last.latency_ms : p.latency_ms) ?? undefined,
          prompt_tokens: p.prompt_tokens,
          completion_tokens: last ? last.completion_tokens : p.completion_tokens,
          text: last ? last.text : p.text,
        };
      }),
    [panes],
  );

  const runOne = React.useCallback(
    async (id: string, paneId: string) => {
      updatePane(paneId, { status: 'loading', error: null, text: '', rounds: [] });
      const controller = new AbortController();
      const meta: AbortMeta = { controller, timedOut: false };
      abortRef.current.set(paneId, meta);
      const timer = window.setTimeout(() => {
        meta.timedOut = true;
        controller.abort();
      }, CLIENT_TIMEOUT_MS);
      try {
        const res = await runPane(id, paneId, controller.signal);
        updatePane(paneId, {
          status: res.status === 'ok' ? 'ready' : res.status,
          text: res.text,
          latency_ms: res.latency_ms,
          prompt_tokens: res.prompt_tokens,
          completion_tokens: res.completion_tokens,
          error: res.error,
          info: paneInfo(res),
        });
      } catch (err) {
        const aborted = (err as Error)?.name === 'AbortError';
        if (aborted && meta.timedOut) {
          updatePane(paneId, { status: 'timeout', error: 'Timed out' });
        } else if (aborted) {
          updatePane(paneId, { status: 'error', error: 'Stopped' });
        } else {
          updatePane(paneId, { status: 'error', error: (err as Error).message });
        }
      } finally {
        window.clearTimeout(timer);
        abortRef.current.delete(paneId);
      }
    },
    [updatePane],
  );

  const runAll = React.useCallback(async () => {
    setTopError(null);
    if (selected.length < 2) {
      setTopError('Select at least 2 models to compare.');
      return;
    }
    if (!prompt.trim()) {
      setTopError('Enter a prompt.');
      return;
    }
    setWinner(null);
    setRevealed(false);
    setSynthesis({ status: 'idle', text: '', error: null });
    setJury(JURY_IDLE);
    let start: StartResponse;
    try {
      start = await startCompare(prompt.trim(), selected, blind);
    } catch (err) {
      setTopError((err as Error).message);
      return;
    }
    setCompId(start.comp_id);
    setBlindActive(start.blind);
    const initial: PaneState[] = start.panes.map((info) => ({
      pane_id: info.pane_id,
      label: info.label,
      info,
      status: 'loading',
      text: '',
      latency_ms: null,
      prompt_tokens: null,
      completion_tokens: null,
      error: null,
      rounds: [],
    }));
    setPanes(initial);
    // Fire every pane concurrently — independent loading / error / timeout.
    initial.forEach((p) => {
      void runOne(start.comp_id, p.pane_id);
    });
  }, [selected, prompt, blind, runOne]);

  const stopAll = React.useCallback(() => {
    abortRef.current.forEach((meta) => meta.controller.abort());
  }, []);

  const retryPane = React.useCallback(
    (paneId: string) => {
      if (compId) void runOne(compId, paneId);
    },
    [compId, runOne],
  );

  const reset = React.useCallback(() => {
    stopAll();
    setCompId(null);
    setBlindActive(false);
    setPanes([]);
    setWinner(null);
    setRevealed(false);
    setSynthesis({ status: 'idle', text: '', error: null });
    setJury(JURY_IDLE);
    setTopError(null);
  }, [stopAll]);

  const reveal = React.useCallback(async () => {
    if (!compId) return;
    try {
      const res = await revealCompare(compId);
      setRevealed(true);
      applyInfos(res.panes);
    } catch (err) {
      setTopError((err as Error).message);
    }
  }, [compId, applyInfos]);

  const vote = React.useCallback(
    async (winnerSel: string) => {
      if (!compId) return;
      try {
        const res = await voteCompare(compId, winnerSel, buildVotePanes());
        setWinner(res.winner);
        setRevealed(true);
        applyInfos(res.panes);
      } catch (err) {
        setTopError((err as Error).message);
      }
    },
    [compId, buildVotePanes, applyInfos],
  );

  const runSynthesize = React.useCallback(async () => {
    if (!compId) return;
    if (!synthModelId) {
      setSynthesis({ status: 'error', text: '', error: 'Pick a synthesis model.' });
      return;
    }
    const ready = panes.filter((p) => p.status === 'ready' && p.text.trim());
    if (ready.length < 1) {
      setSynthesis({ status: 'error', text: '', error: 'No completed responses to synthesize.' });
      return;
    }
    setSynthesis({ status: 'loading', text: '', error: null });
    const responses = ready.map((p) => ({ label: p.info.model_label ?? p.label, text: p.text }));
    try {
      const res = await synthesize(compId, synthModelId, responses);
      setSynthesis({ status: 'ready', text: res.synthesis, error: null });
    } catch (err) {
      // Synthesis failure must not erase pane outputs — only this panel errors.
      setSynthesis({ status: 'error', text: '', error: (err as Error).message });
    }
  }, [compId, synthModelId, panes]);

  const runDebate = React.useCallback(async () => {
    if (!compId) return;
    const endRound = Math.max(2, debateRounds);
    setDebating(true);
    setDebateError(null);
    const latest = (p: PaneState) => (p.rounds.length ? p.rounds[p.rounds.length - 1].text : p.text);
    const participates = (p: PaneState) =>
      latest(p).trim().length > 0 && (p.status === 'ready' || p.rounds.length > 0);
    // Local working copy so multi-round peers read the freshest answers even
    // before React re-renders.
    let working = panes.map((p) => ({ ...p, rounds: [...p.rounds] }));
    try {
      for (let r = 2; r <= endRound; r++) {
        const actors = working.filter(participates);
        if (actors.length < 2) {
          setDebateError('Need at least 2 completed answers to debate.');
          break;
        }
        const results = await Promise.all(
          actors.map(async (p) => {
            const peers = actors
              .filter((o) => o.pane_id !== p.pane_id)
              .map((o) => ({ label: o.info.model_label ?? o.label, text: latest(o) }));
            let entry: RoundEntry;
            try {
              const res = await debateRound(compId, p.pane_id, peers, r);
              entry = {
                round: r,
                status: res.status === 'ok' ? 'ready' : res.status,
                text: res.text,
                latency_ms: res.latency_ms,
                completion_tokens: res.completion_tokens,
                error: res.error,
              };
            } catch (err) {
              entry = {
                round: r,
                status: 'error',
                text: '',
                latency_ms: null,
                completion_tokens: null,
                error: (err as Error).message,
              };
            }
            return { pane_id: p.pane_id, entry };
          }),
        );
        working = working.map((p) => {
          const found = results.find((x) => x.pane_id === p.pane_id);
          return found ? { ...p, rounds: [...p.rounds, found.entry] } : p;
        });
        setPanes(working);
      }
    } finally {
      setDebating(false);
    }
  }, [compId, panes, debateRounds]);

  const runJury = React.useCallback(async () => {
    if (!compId) return;
    const latest = (p: PaneState) => (p.rounds.length ? p.rounds[p.rounds.length - 1].text : p.text);
    // Jurors are panes with a completed latest answer (initial or final debate
    // round). A pane both judges and is judged.
    const actors = panes.filter((p) => latest(p).trim().length > 0 && (p.status === 'ready' || p.rounds.length > 0));
    if (actors.length < 2) {
      setJury({ ...JURY_IDLE, status: 'error', error: 'Need at least 2 completed answers to convene the jury.' });
      return;
    }
    setJury({ ...JURY_IDLE, status: 'running' });

    const labelToPane = new Map(actors.map((p) => [p.label, p.pane_id]));
    // Each juror scores every OTHER actor, concurrently. A failing juror returns
    // empty scores and never blocks the panel (same contract as /run, /debate).
    const results = await Promise.all(
      actors.map(async (juror) => {
        const peers = actors
          .filter((o) => o.pane_id !== juror.pane_id)
          .map((o) => ({ pane_id: o.pane_id, text: latest(o) }));
        try {
          const res = await rankJury(compId, juror.pane_id, peers);
          if (res.status !== 'ok') {
            return { pane_id: juror.pane_id, scores: [] as JuryScore[], error: res.error ?? res.status };
          }
          return { pane_id: juror.pane_id, scores: res.scores, error: null as string | null };
        } catch (err) {
          return { pane_id: juror.pane_id, scores: [] as JuryScore[], error: (err as Error).message };
        }
      }),
    );

    const matrix: Record<string, Record<string, JuryCell>> = {};
    const errors: Record<string, string> = {};
    for (const r of results) {
      matrix[r.pane_id] = {};
      if (r.error) errors[r.pane_id] = r.error;
      for (const s of r.scores) {
        const targetPane = labelToPane.get(s.label);
        if (targetPane) matrix[r.pane_id][targetPane] = { score: s.score, reason: s.reason };
      }
    }

    // Mean score each actor RECEIVED (only jurors who actually scored it count).
    const means: Record<string, number | null> = {};
    for (const target of actors) {
      const received: number[] = [];
      for (const juror of actors) {
        if (juror.pane_id === target.pane_id) continue;
        const cell = matrix[juror.pane_id]?.[target.pane_id];
        if (cell) received.push(cell.score);
      }
      means[target.pane_id] = received.length ? received.reduce((a, b) => a + b, 0) / received.length : null;
    }

    // Winner = highest received mean; a near-tie at the top reports "tie".
    let best: string | null = null;
    let bestVal = -Infinity;
    let tied = false;
    for (const target of actors) {
      const m = means[target.pane_id];
      if (m == null) continue;
      if (m > bestVal + JURY_TIE_EPSILON) {
        bestVal = m;
        best = target.pane_id;
        tied = false;
      } else if (Math.abs(m - bestVal) <= JURY_TIE_EPSILON) {
        tied = true;
      }
    }
    const winnerPaneId = best == null ? null : tied ? 'tie' : best;
    setJury({ status: 'ready', matrix, means, winnerPaneId, errors, error: null });

    // Feed the scoreboard without a human click: record the jury's verdict
    // through the existing hash-only vote path (this also reveals identities).
    if (winnerPaneId) {
      try {
        const res = await voteCompare(compId, winnerPaneId, buildVotePanes());
        setWinner(res.winner);
        setRevealed(true);
        applyInfos(res.panes);
      } catch (err) {
        setJury((j) => ({ ...j, error: (err as Error).message }));
      }
    }
  }, [compId, panes, buildVotePanes, applyInfos]);

  const toggleSelect = React.useCallback((id: string) => {
    setSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  }, []);

  const anyLoading = panes.some((p) => p.status === 'loading');
  const started = compId !== null;
  const allSettled = panes.length > 0 && panes.every((p) => p.status !== 'loading');

  return {
    models,
    modelsStatus,
    modelsError,
    selected,
    toggleSelect,
    canRun: selected.length >= 2 && prompt.trim().length > 0,
    blind,
    setBlind,
    prompt,
    setPrompt,
    compId,
    blindActive,
    revealed,
    panes,
    started,
    anyLoading,
    allSettled,
    winner,
    topError,
    runAll,
    stopAll,
    retryPane,
    reset,
    reveal,
    vote,
    debateRounds,
    setDebateRounds,
    debating,
    debateError,
    runDebate,
    synthModelId,
    setSynthModelId,
    synthesis: synthesisState,
    runSynthesize,
    jury,
    runJury,
  };
}
