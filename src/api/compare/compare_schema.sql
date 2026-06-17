-- Compare / Council vote history. HASH-ONLY: the user's prompt and every model
-- response are stored only as SHA-256 hashes, never as plaintext. This keeps a
-- useful scoreboard / audit trail without persisting any (possibly sensitive)
-- content to disk on an MNPI laptop -- mirrors the atoms-audit hash-only rule.
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS compare_history (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    comp_id          TEXT    NOT NULL,
    ts               REAL    NOT NULL,          -- epoch seconds
    prompt_sha256    TEXT    NOT NULL,          -- hash of the prompt; never the prompt
    blind            INTEGER NOT NULL,          -- 0 / 1
    models_json      TEXT    NOT NULL,          -- JSON array of model ids in the comparison
    winner_model_id  TEXT,                      -- model id, or 'tie', or NULL
    panes_json       TEXT    NOT NULL,          -- per-pane metadata (hash-only, see history_db.py)
    created_at       TEXT    NOT NULL           -- ISO 8601
);

CREATE INDEX IF NOT EXISTS idx_compare_history_created ON compare_history(created_at);
