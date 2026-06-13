-- Sovereign Citadel retrieval engine schema.
-- Offset unit: BYTE. Tier-on-every-row. Most-restrictive composite at query time.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS pages (
    page_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    page_slug    TEXT    NOT NULL UNIQUE,
    page_path    TEXT    NOT NULL,
    tier         TEXT    NOT NULL CHECK (tier IN ('S1','S2','S3')),
    sha256       TEXT    NOT NULL,
    ingested_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    page_id           INTEGER NOT NULL REFERENCES pages(page_id) ON DELETE CASCADE,
    chunk_index       INTEGER NOT NULL,
    chunk_start_byte  INTEGER NOT NULL,
    chunk_end_byte    INTEGER NOT NULL,
    line_start        INTEGER NOT NULL,
    line_end          INTEGER NOT NULL,
    tier              TEXT    NOT NULL CHECK (tier IN ('S1','S2','S3')),
    text              TEXT    NOT NULL,
    UNIQUE (page_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_chunks_page ON chunks(page_id);
CREATE INDEX IF NOT EXISTS idx_chunks_tier ON chunks(tier);

-- FTS5 virtual table mirrors chunks.text for BM25 ranking.
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    text,
    content='chunks',
    content_rowid='chunk_id',
    tokenize='porter unicode61'
);

CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
    INSERT INTO chunks_fts(rowid, text) VALUES (new.chunk_id, new.text);
END;

CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, text) VALUES('delete', old.chunk_id, old.text);
END;

-- Vector storage. BLOB float32 packed. sqlite-vec extension may shadow this
-- via a separate vec0 virtual table loaded at runtime, but BLOB is the
-- always-available fallback and the canonical source of truth.
CREATE TABLE IF NOT EXISTS vectors (
    chunk_id   INTEGER PRIMARY KEY REFERENCES chunks(chunk_id) ON DELETE CASCADE,
    dim        INTEGER NOT NULL,
    embedding  BLOB    NOT NULL
);
