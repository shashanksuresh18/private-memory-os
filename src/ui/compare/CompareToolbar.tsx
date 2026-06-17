import * as React from 'react';
import { type CompareModel } from './compare-api';

interface Props {
  models: CompareModel[];
  modelsStatus: 'loading' | 'ready' | 'error';
  modelsError: string | null;
  selected: string[];
  onToggle: (id: string) => void;
  blind: boolean;
  onBlind: (v: boolean) => void;
  prompt: string;
  onPrompt: (v: string) => void;
  canRun: boolean;
  anyLoading: boolean;
  started: boolean;
  onRun: () => void;
  onStop: () => void;
  onReset: () => void;
}

export function CompareToolbar({
  models,
  modelsStatus,
  modelsError,
  selected,
  onToggle,
  blind,
  onBlind,
  prompt,
  onPrompt,
  canRun,
  anyLoading,
  started,
  onRun,
  onStop,
  onReset,
}: Props) {
  return (
    <section className="compare-toolbar" aria-label="Compare controls">
      <p className="compare-warning" role="note">
        CLOUD — prompts are DLP-scrubbed, then sent to external providers. Don't use confidential / MNPI content here.
      </p>

      <div className="compare-models" role="group" aria-label="Models">
        {modelsStatus === 'loading' ? (
          <span className="compare-muted">Loading models…</span>
        ) : modelsStatus === 'error' ? (
          <span className="compare-muted compare-muted--error">{modelsError}</span>
        ) : models.length === 0 ? (
          <span className="compare-muted">
            No cloud models configured. Add NEBIUS_API_KEY (or ANTHROPIC_API_KEY / OPENAI_API_KEY) to .env and restart.
          </span>
        ) : (
          models.map((m) => {
            const on = selected.includes(m.id);
            return (
              <button
                key={m.id}
                type="button"
                className={on ? 'model-chip model-chip--on' : 'model-chip'}
                aria-pressed={on}
                onClick={() => onToggle(m.id)}
                disabled={anyLoading}
              >
                <span className="model-chip__dot" />
                {m.label}
                <span className="model-chip__cloud">CLOUD</span>
              </button>
            );
          })
        )}
      </div>

      <textarea
        className="compare-prompt"
        value={prompt}
        onChange={(e) => onPrompt(e.target.value)}
        placeholder="Enter one prompt to send to every selected model…"
        rows={3}
        disabled={anyLoading}
      />

      <div className="compare-actions">
        <label className="compare-blind">
          <input type="checkbox" checked={blind} onChange={(e) => onBlind(e.target.checked)} disabled={anyLoading} />
          Blind mode
        </label>
        <span className="compare-actions__spacer" />
        {anyLoading ? (
          <button type="button" className="compare-btn" onClick={onStop}>
            Stop
          </button>
        ) : null}
        {started ? (
          <button type="button" className="compare-btn" onClick={onReset}>
            Reset
          </button>
        ) : null}
        <button type="button" className="compare-btn compare-btn--primary" onClick={onRun} disabled={!canRun || anyLoading}>
          {started ? 'Run again' : 'Compare'}
        </button>
      </div>

      {selected.length > 0 && selected.length < 2 ? (
        <p className="compare-hint">Select at least 2 models.</p>
      ) : null}
    </section>
  );
}
