import * as React from 'react';
import { fetchCompareHistory, type ScoreRow } from './compare-api';

interface Props {
  open: boolean;
  onClose: () => void;
}

export function Scoreboard({ open, onClose }: Props) {
  const [status, setStatus] = React.useState<'loading' | 'ready' | 'error'>('loading');
  const [rows, setRows] = React.useState<ScoreRow[]>([]);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setStatus('loading');
    fetchCompareHistory()
      .then((res) => {
        if (cancelled) return;
        setRows(res.scoreboard ?? []);
        setStatus('ready');
      })
      .catch((err) => {
        if (cancelled) return;
        setError((err as Error).message);
        setStatus('error');
      });
    return () => {
      cancelled = true;
    };
  }, [open]);

  if (!open) return null;

  return (
    <div className="compare-modal" role="dialog" aria-modal="true" aria-label="Scoreboard">
      <div className="compare-modal__overlay" onClick={onClose} />
      <div className="compare-modal__panel">
        <header className="compare-modal__head">
          <h2>Scoreboard</h2>
          <button type="button" className="compare-btn" onClick={onClose}>
            Close
          </button>
        </header>
        {status === 'loading' ? (
          <p className="compare-muted">Loading…</p>
        ) : status === 'error' ? (
          <p className="compare-muted compare-muted--error">{error}</p>
        ) : rows.length === 0 ? (
          <p className="compare-muted">No votes recorded yet.</p>
        ) : (
          <table className="compare-score">
            <thead>
              <tr>
                <th>Model</th>
                <th>Win %</th>
                <th>W</th>
                <th>L</th>
                <th>T</th>
                <th>Games</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.model_id}>
                  <td className="compare-score__name">{r.model_id}</td>
                  <td>{r.win_pct}%</td>
                  <td>{r.wins}</td>
                  <td>{r.losses}</td>
                  <td>{r.ties}</td>
                  <td>{r.games}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
