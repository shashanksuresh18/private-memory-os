-- Sovereign Citadel — Local CRM schema (SQLite)
-- Owned by src/crm/db.py. Read by src/crm/repository.py + src/crm/merges.py.
-- Tier defaults: contacts = S2 (PII), interactions/sources = S2.
-- All hard-delete is forbidden. Soft-merge writes the secondary's
-- merged_into pointer and a hash-chained row in `merges`.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA synchronous = NORMAL;

CREATE TABLE IF NOT EXISTS contacts (
    id              TEXT PRIMARY KEY,                       -- uuid4 hex
    display_name    TEXT NOT NULL,
    primary_email   TEXT,
    primary_phone   TEXT,
    company         TEXT,
    role            TEXT,
    tier            TEXT NOT NULL DEFAULT 'S2'
                    CHECK (tier IN ('S1','S2','S3')),
    notes           TEXT,
    merged_into     TEXT REFERENCES contacts(id),           -- NULL = active
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_contacts_email        ON contacts(primary_email);
CREATE INDEX IF NOT EXISTS idx_contacts_phone        ON contacts(primary_phone);
CREATE INDEX IF NOT EXISTS idx_contacts_display_name ON contacts(display_name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_contacts_active       ON contacts(merged_into);
CREATE INDEX IF NOT EXISTS idx_contacts_company      ON contacts(company COLLATE NOCASE);

CREATE TABLE IF NOT EXISTS sources (
    id                  TEXT PRIMARY KEY,                   -- uuid4 hex
    contact_id          TEXT NOT NULL REFERENCES contacts(id),
    source_type         TEXT NOT NULL,                      -- gmail|linkedin|iphone|manual|...
    source_external_id  TEXT,                               -- provider's id; nullable for manual
    raw_blob            TEXT,                               -- JSON-as-text
    tier                TEXT NOT NULL DEFAULT 'S2'
                        CHECK (tier IN ('S1','S2','S3')),
    captured_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE (source_type, source_external_id)
);

CREATE INDEX IF NOT EXISTS idx_sources_contact ON sources(contact_id);
CREATE INDEX IF NOT EXISTS idx_sources_type    ON sources(source_type);

CREATE TABLE IF NOT EXISTS interactions (
    id                TEXT PRIMARY KEY,                     -- uuid4 hex
    contact_id        TEXT NOT NULL REFERENCES contacts(id),
    interaction_type  TEXT NOT NULL,                        -- email|call|meeting|note|message
    ts                TEXT NOT NULL,                        -- ISO-8601 UTC
    summary           TEXT,
    body              TEXT,
    source_id         TEXT REFERENCES sources(id),
    tier              TEXT NOT NULL DEFAULT 'S2'
                      CHECK (tier IN ('S1','S2','S3')),
    created_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_interactions_contact_ts ON interactions(contact_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_interactions_type       ON interactions(interaction_type);
CREATE INDEX IF NOT EXISTS idx_interactions_ts         ON interactions(ts DESC);

CREATE TABLE IF NOT EXISTS merges (
    id                  TEXT PRIMARY KEY,                   -- uuid4 hex
    primary_contact_id  TEXT NOT NULL REFERENCES contacts(id),
    merged_contact_id   TEXT NOT NULL REFERENCES contacts(id),
    operator_id         TEXT NOT NULL,
    reason              TEXT,
    fields_overridden   TEXT,                               -- JSON: {field:[old,new]}
    prev_hash           TEXT NOT NULL DEFAULT '',
    hash                TEXT NOT NULL,
    merged_at           TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_merges_primary  ON merges(primary_contact_id);
CREATE INDEX IF NOT EXISTS idx_merges_merged   ON merges(merged_contact_id);
CREATE INDEX IF NOT EXISTS idx_merges_ts       ON merges(merged_at DESC);

-- Touch updated_at on every contact write.
CREATE TRIGGER IF NOT EXISTS contacts_touch_updated_at
AFTER UPDATE ON contacts FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE contacts SET updated_at = strftime('%Y-%m-%dT%H:%M:%fZ','now')
    WHERE id = OLD.id;
END;

-- View: active contacts only (anything not merged away).
CREATE VIEW IF NOT EXISTS active_contacts AS
SELECT * FROM contacts WHERE merged_into IS NULL;
