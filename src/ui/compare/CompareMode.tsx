import * as React from 'react';
import { useCompare } from './useCompare';
import { CompareToolbar } from './CompareToolbar';
import { ComparePane } from './ComparePane';
import { JuryMatrix } from './JuryMatrix';
import { Scoreboard } from './Scoreboard';

export function CompareMode() {
  const c = useCompare();
  const [scoreboardOpen, setScoreboardOpen] = React.useState(false);

  const decided = c.winner !== null;
  const canVote = c.allSettled && !decided;
  const readyCount = c.panes.filter((p) => p.status === 'ready' && p.text.trim()).length;

  // Panes eligible to be judged by the jury: those with a completed latest answer
  // (initial run or a debate round). Must match runJury's actor filter.
  const juryActors = c.panes.filter(
    (p) => (p.rounds.length ? p.rounds[p.rounds.length - 1].text : p.text).trim().length > 0 &&
      (p.status === 'ready' || p.rounds.length > 0),
  );
  const juryRunning = c.jury.status === 'running';
  const juryWinnerName =
    c.jury.winnerPaneId && c.jury.winnerPaneId !== 'tie'
      ? (() => {
          const w = c.panes.find((p) => p.pane_id === c.jury.winnerPaneId);
          return w ? w.info.model_label ?? w.label : null;
        })()
      : null;

  return (
    <div className="compare-mode">
      <header className="compare-header">
        <div>
          <h1>Compare / Council</h1>
          <p className="compare-sub">Send one prompt to multiple cloud models, side by side.</p>
        </div>
        <button type="button" className="compare-btn" onClick={() => setScoreboardOpen(true)}>
          Scoreboard
        </button>
      </header>

      <CompareToolbar
        models={c.models}
        modelsStatus={c.modelsStatus}
        modelsError={c.modelsError}
        selected={c.selected}
        onToggle={c.toggleSelect}
        blind={c.blind}
        onBlind={c.setBlind}
        prompt={c.prompt}
        onPrompt={c.setPrompt}
        canRun={c.canRun}
        anyLoading={c.anyLoading}
        started={c.started}
        onRun={c.runAll}
        onStop={c.stopAll}
        onReset={c.reset}
      />

      {c.topError ? <p className="compare-error-bar">{c.topError}</p> : null}

      {!c.started ? (
        <div className="compare-empty">
          <p>Pick 2 or more models, enter a prompt, and hit Compare.</p>
          <p className="compare-muted">
            Each model answers the same prompt in its own pane. Turn on Blind mode to hide names until you vote.
          </p>
        </div>
      ) : (
        <>
          <section className="compare-grid" aria-label="Model responses">
            {c.panes.map((pane) => (
              <ComparePane
                key={pane.pane_id}
                pane={pane}
                blind={c.blindActive}
                revealed={c.revealed}
                canVote={canVote}
                decided={decided}
                isWinner={c.winner === pane.pane_id}
                onVote={() => c.vote(pane.pane_id)}
                onRetry={() => c.retryPane(pane.pane_id)}
              />
            ))}
          </section>

          <section className="compare-votebar" aria-label="Vote">
            {decided ? (
              <p className="compare-result">
                {c.winner === 'tie' ? 'You called it a tie.' : 'Winner recorded.'}
              </p>
            ) : (
              <>
                <button type="button" className="compare-btn" disabled={!canVote} onClick={() => c.vote('tie')}>
                  Tie
                </button>
                {c.blindActive && !c.revealed ? (
                  <button type="button" className="compare-btn" onClick={c.reveal}>
                    Reveal names
                  </button>
                ) : null}
              </>
            )}
          </section>

          <section className="compare-debate" aria-label="Debate">
            <div className="compare-debate__head">
              <div>
                <h2>Debate</h2>
                <p className="compare-muted">
                  Each model reads the others' answers, then states where it agrees, disagrees, and refines.
                </p>
              </div>
              <div className="compare-debate__controls">
                <label className="compare-muted">
                  Rounds
                  <select
                    value={c.debateRounds}
                    onChange={(e) => c.setDebateRounds(Number(e.target.value))}
                    disabled={c.debating}
                    aria-label="Debate rounds"
                  >
                    <option value={2}>2</option>
                    <option value={3}>3</option>
                  </select>
                </label>
                <button
                  type="button"
                  className="compare-btn"
                  onClick={c.runDebate}
                  disabled={readyCount < 2 || c.debating || c.anyLoading}
                >
                  {c.debating ? 'Debating…' : 'Debate'}
                </button>
              </div>
            </div>
            {c.debateError ? <p className="compare-error-bar">{c.debateError}</p> : null}
          </section>

          <section className="compare-jury" aria-label="Jury">
            <div className="compare-jury__head">
              <div>
                <h2>Jury</h2>
                <p className="compare-muted">
                  Each model anonymously scores the others' answers 1–10. The highest mean score wins and is
                  recorded to the scoreboard — no human vote needed.
                </p>
              </div>
              <button
                type="button"
                className="compare-btn compare-btn--primary"
                onClick={c.runJury}
                disabled={juryActors.length < 2 || juryRunning || c.anyLoading}
              >
                {juryRunning ? 'Scoring…' : 'Convene jury'}
              </button>
            </div>

            {c.jury.error ? <p className="compare-error-bar">{c.jury.error}</p> : null}

            {c.jury.status === 'ready' ? (
              <>
                <p className="compare-jury__verdict">
                  {c.jury.winnerPaneId === 'tie' || !juryWinnerName ? (
                    'Jury verdict: tie.'
                  ) : (
                    <>
                      Jury verdict: <strong>{juryWinnerName}</strong> wins.
                    </>
                  )}
                </p>
                <JuryMatrix panes={juryActors} jury={c.jury} />
              </>
            ) : null}
          </section>

          <section className="compare-synth" aria-label="Council synthesis">
            <div className="compare-synth__head">
              <h2>Council synthesis</h2>
              <div className="compare-synth__controls">
                <select
                  value={c.synthModelId}
                  onChange={(e) => c.setSynthModelId(e.target.value)}
                  disabled={c.synthesis.status === 'loading'}
                  aria-label="Synthesis model"
                >
                  {c.models.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.label}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  className="compare-btn compare-btn--primary"
                  onClick={c.runSynthesize}
                  disabled={readyCount < 1 || c.synthesis.status === 'loading'}
                >
                  {c.synthesis.status === 'loading' ? 'Synthesizing…' : 'Synthesize'}
                </button>
              </div>
            </div>
            {c.synthesis.status === 'error' ? (
              <p className="compare-error-bar">{c.synthesis.error}</p>
            ) : c.synthesis.status === 'ready' ? (
              <div className="compare-synth__text">{c.synthesis.text}</div>
            ) : c.synthesis.status === 'loading' ? (
              <div className="compare-skeleton">
                <span className="skeleton-line" />
                <span className="skeleton-line" />
              </div>
            ) : (
              <p className="compare-muted">
                Combine the panes into a consensus, disagreements, strongest answer, gaps, and a per-model summary.
              </p>
            )}
          </section>
        </>
      )}

      <Scoreboard open={scoreboardOpen} onClose={() => setScoreboardOpen(false)} />
    </div>
  );
}
