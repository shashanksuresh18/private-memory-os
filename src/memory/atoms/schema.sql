-- Pointer-only atoms layer (P3).
-- Span store; no text column anywhere. Resolver reads the live vault file
-- at query time. Audit persists SHA-256 hashes only.
--
-- Tier-on-every-row. Atoms inherit tier from the source page. Cross-source
-- joins must compose tiers as MAX(tier_a, tier_b) at fusion time.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- The canonical span store. Every row is a pointer; no inline text.
CREATE TABLE IF NOT EXISTS atoms (
    atom_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    page_slug    TEXT    NOT NULL,
    chunk_id     INTEGER,                -- nullable: atom may pre-date chunk index
    byte_start   INTEGER NOT NULL,
    byte_end     INTEGER NOT NULL,
    label        TEXT    NOT NULL,       -- e.g. EMAIL, PHONE, USD_AMOUNT, CODENAME, ENTITY
    confidence   REAL    NOT NULL,       -- [0.0, 1.0]
    tier         TEXT    NOT NULL CHECK (tier IN ('S1','S2','S3')),
    created_at   TEXT    NOT NULL,
    CHECK (byte_end > byte_start)
);

CREATE INDEX IF NOT EXISTS idx_atoms_page  ON atoms(page_slug);
CREATE INDEX IF NOT EXISTS idx_atoms_label ON atoms(label);
CREATE INDEX IF NOT EXISTS idx_atoms_tier  ON atoms(tier);

-- Canonical entity registry. Aliases are JSON arrays of strings (e.g.
-- {"Wonderland Capital", "Wonderland Capital Partners", "WCP"}). The
-- canonical_label is what UIs display; aliases drive matching.
-- Tier on entities is the most-restrictive of any contributing source
-- page. `retier_page()` recomputes this on reclassification.
CREATE TABLE IF NOT EXISTS entities (
    entity_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_label  TEXT    NOT NULL UNIQUE,
    aliases_json     TEXT    NOT NULL DEFAULT '[]',
    tier             TEXT    NOT NULL CHECK (tier IN ('S1','S2','S3')),
    created_at       TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_entities_tier ON entities(tier);

-- Many-to-one alias-to-entity map for fast lookup. Aliases are
-- case-folded before insert; case-folding rule lives in extractor.py.
CREATE TABLE IF NOT EXISTS entity_aliases (
    alias        TEXT    NOT NULL,
    entity_id    INTEGER NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    PRIMARY KEY (alias, entity_id)
);

CREATE INDEX IF NOT EXISTS idx_entity_aliases_alias ON entity_aliases(alias);

-- Join: atoms labelled ENTITY can carry an entity_id pointer. Composite
-- key allows the same atom to point to multiple entity candidates with
-- per-link confidence.
CREATE TABLE IF NOT EXISTS atom_entity (
    atom_id     INTEGER NOT NULL REFERENCES atoms(atom_id)    ON DELETE CASCADE,
    entity_id   INTEGER NOT NULL REFERENCES entities(entity_id) ON DELETE CASCADE,
    confidence  REAL    NOT NULL,
    PRIMARY KEY (atom_id, entity_id)
);
