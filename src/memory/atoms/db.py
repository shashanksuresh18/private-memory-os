"""SQLite connection + schema bootstrap for the atoms layer."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent / "schema.sql"
# Absolute, resolved from this file so cwd never changes which DB is used.
# parents[3] == repo root (src/memory/atoms/db.py -> atoms/memory/src/<root>).
DEFAULT_DB_PATH = Path(__file__).resolve().parents[3] / "src" / "memory" / "sqlite" / "atoms.db"


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    return conn


def reset(db_path: Path | str | None = None) -> None:
    path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
    for suffix in ("", "-wal", "-shm"):
        p = path.with_name(path.name + suffix) if suffix else path
        if p.exists():
            p.unlink()
