import * as React from 'react';
import { type PaneState } from './useCompare';

interface Props {
  pane: PaneState;
  blind: boolean;
  revealed: boolean;
  canVote: boolean;
  decided: boolean;
  isWinner: boolean;
  onVote: () => void;
  onRetry: () => void;
}

function metric(pane: PaneState): string {
  const bits: string[] = [];
  if (pane.latency_ms != null) bits.push(`${(pane.latency_ms / 1000).toFixed(2)}s`);
  const out = pane.completion_tokens;
  if (out != null) bits.push(`~${out} tok`);
  return bits.join(' · ');
}

export function ComparePane({ pane, blind, revealed, canVote, decided, isWinner, onVote, onRetry }: Props) {
  const showName = !blind || revealed;
  const title = showName ? pane.info.model_label ?? pane.label : pane.label;
  const failed = pane.status === 'error' || pane.status === 'timeout';

  const cls = ['compare-pane'];
  if (decided && isWinner) cls.push('compare-pane--winner');
  else if (decided) cls.push('compare-pane--loser');
  if (failed) cls.push('compare-pane--failed');

  return (
    <article className={cls.join(' ')} aria-label={title}>
      <header className="compare-pane__head">
        <div className="compare-pane__title">
          <span className="compare-pane__name">{title}</span>
          <span className="cloud-badge" title="Sent to an external cloud provider">CLOUD</span>
          {decided && isWinner ? <span className="compare-pane__crown" aria-label="winner">★</span> : null}
        </div>
        <span className={`pane-status pane-status--${pane.status}`}>
          {pane.status === 'loading'
            ? 'Generating…'
            : pane.status === 'ready'
              ? 'Done'
              : pane.status === 'timeout'
                ? 'Timed out'
                : pane.status === 'error'
                  ? 'Error'
                  : 'Queued'}
        </span>
      </header>

      {pane.status === 'ready' && metric(pane) ? (
        <div className="compare-pane__metrics">{metric(pane)}</div>
      ) : null}

      <div className="compare-pane__body">
        {pane.status === 'loading' ? (
          <div className="compare-skeleton" aria-busy="true" aria-label="Generating">
            <span className="skeleton-line" />
            <span className="skeleton-line" />
            <span className="skeleton-line skeleton-line--short" />
          </div>
        ) : failed ? (
          <div className="compare-pane__error">
            <p>{pane.error ?? (pane.status === 'timeout' ? 'The model took too long.' : 'The model failed.')}</p>
            <button type="button" className="compare-btn" onClick={onRetry}>
              Retry
            </button>
          </div>
        ) : pane.status === 'ready' ? (
          <div className="compare-pane__text">{pane.text || '(empty response)'}</div>
        ) : (
          <div className="compare-pane__text compare-pane__text--muted">Waiting…</div>
        )}
      </div>

      {pane.rounds.length > 0 ? (
        <div className="compare-pane__rounds">
          {pane.rounds.map((rd) => (
            <div key={rd.round} className="compare-round">
              <div className="compare-round__head">
                <span>Round {rd.round}</span>
                {rd.status === 'ready' && rd.latency_ms != null ? (
                  <span className="compare-round__meta">{(rd.latency_ms / 1000).toFixed(2)}s</span>
                ) : null}
              </div>
              {rd.status === 'ready' ? (
                <div className="compare-pane__text">{rd.text || '(empty)'}</div>
              ) : (
                <div className="compare-pane__text compare-pane__text--muted">{rd.error ?? 'failed'}</div>
              )}
            </div>
          ))}
        </div>
      ) : null}

      <footer className="compare-pane__foot">
        <button
          type="button"
          className="compare-btn compare-btn--vote"
          disabled={!canVote || decided}
          onClick={onVote}
          title={canVote ? 'Pick this answer as the winner' : 'Vote once all panes have finished'}
        >
          {decided && isWinner ? 'Winner' : 'Vote'}
        </button>
      </footer>
    </article>
  );
}
