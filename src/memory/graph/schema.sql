-- Typed-edge graph track schema (P4).
-- One row per (src_page, dst_page, edge_type) tuple. Composite tier =
-- MAX(tier_src, tier_dst) computed at insert time.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS edges (
    edge_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    src_page       TEXT    NOT NULL,
    dst_page       TEXT    NOT NULL,
    edge_type      TEXT    NOT NULL,
    confidence     REAL    NOT NULL,
    tier           TEXT    NOT NULL CHECK (tier IN ('S1','S2','S3')),
    source_kind    TEXT    NOT NULL,        -- 'frontmatter' | 'wikilink' | 'markdown_link'
    created_at     TEXT    NOT NULL,
    UNIQUE (src_page, dst_page, edge_type)
);

CREATE INDEX IF NOT EXISTS idx_edges_src  ON edges(src_page);
CREATE INDEX IF NOT EXISTS idx_edges_dst  ON edges(dst_page);
CREATE INDEX IF NOT EXISTS idx_edges_tier ON edges(tier);
CREATE INDEX IF NOT EXISTS idx_edges_type ON edges(edge_type);
