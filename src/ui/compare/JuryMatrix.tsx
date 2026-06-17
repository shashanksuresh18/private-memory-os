import * as React from 'react';
import { type JuryState, type PaneState } from './useCompare';

interface Props {
  panes: PaneState[];
  jury: JuryState;
}

function fmt(n: number | null | undefined): string {
  return n == null ? '—' : n.toFixed(1);
}

// Deference matrix: rows = jurors, columns = the answer being scored, cells = the
// score the row's model gave the column's answer. The diagonal is blank (a juror
// never scores itself). The footer row is each answer's mean RECEIVED score, which
// is what decides the jury winner.
export function JuryMatrix({ panes, jury }: Props) {
  const name = (p: PaneState) => p.info.model_label ?? p.label;

  return (
    <div className="jury-matrix">
      <table className="compare-score jury-table">
        <thead>
          <tr>
            <th className="jury-corner">Juror ↓ / Answer →</th>
            {panes.map((t) => (
              <th key={t.pane_id}>{name(t)}</th>
            ))}
            <th>Gave</th>
          </tr>
        </thead>
        <tbody>
          {panes.map((juror) => {
            const row = jury.matrix[juror.pane_id] ?? {};
            const given = panes
              .filter((t) => t.pane_id !== juror.pane_id && row[t.pane_id])
              .map((t) => row[t.pane_id].score);
            const gaveAvg = given.length ? given.reduce((a, b) => a + b, 0) / given.length : null;
            const err = jury.errors[juror.pane_id];
            return (
              <tr key={juror.pane_id} className={err ? 'jury-row--failed' : undefined}>
                <th scope="row" title={err ?? undefined}>
                  {name(juror)}
                  {err ? <span className="jury-failed-tag"> failed</span> : null}
                </th>
                {panes.map((t) => {
                  if (t.pane_id === juror.pane_id) {
                    return (
                      <td key={t.pane_id} className="jury-self">
                        —
                      </td>
                    );
                  }
                  const cell = row[t.pane_id];
                  return (
                    <td key={t.pane_id} title={cell?.reason || undefined}>
                      {cell ? cell.score.toFixed(0) : err ? '·' : '–'}
                    </td>
                  );
                })}
                <td>{fmt(gaveAvg)}</td>
              </tr>
            );
          })}
        </tbody>
        <tfoot>
          <tr>
            <th scope="row">Received avg</th>
            {panes.map((t) => {
              const win = jury.winnerPaneId === t.pane_id;
              return (
                <td key={t.pane_id} className={win ? 'jury-winner-cell' : undefined}>
                  <strong>{fmt(jury.means[t.pane_id])}</strong>
                </td>
              );
            })}
            <td />
          </tr>
        </tfoot>
      </table>
    </div>
  );
}
