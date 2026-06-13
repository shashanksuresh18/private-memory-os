"""CRM database lifecycle. Initializes SQLite from schema.sql + tunes pragmas.

Default DB path: ``src/memory/sqlite/crm.db``. Override via the
``SOVEREIGN_CRM_DB`` env var.
"""
from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

DEFAULT_DB = Path(os.environ.get(
    "SOVEREIGN_CRM_DB",
    "src/memory/sqlite/crm.db",
))
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def init_db(path: Path | str | None = None) -> Path:
    """Create the SQLite file (if needed) and apply schema.sql idempotently.

    Returns the resolved absolute path of the database file.
    """
    db_path = Path(path) if path else DEFAULT_DB
    db_path.parent.mkdir(parents=True, exist_ok=True)

    ddl = SCHEMA_PATH.read_text(encoding="utf-8")
    with sqlite3.connect(db_path) as conn:
        conn.executescript(ddl)
        conn.commit()
    return db_path.resolve()


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    """Return a SQLite connection with row-as-dict + foreign keys + WAL mode."""
    db_path = Path(path) if path else DEFAULT_DB
    if not db_path.exists():
        init_db(db_path)
    conn = sqlite3.connect(db_path, isolation_level=None, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Begin/commit/rollback wrapper. Use for multi-statement writes."""
    conn.execute("BEGIN IMMEDIATE;")
    try:
        yield conn
        conn.execute("COMMIT;")
    except Exception:
        conn.execute("ROLLBACK;")
        raise


if __name__ == "__main__":
    path = init_db()
    print(f"crm.db ready -> {path}")
