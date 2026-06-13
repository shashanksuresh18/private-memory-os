"""SQLite connection + schema bootstrap for the retrieval engine."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent / "schema.sql"
# Repo root, resolved from this file so cwd never matters. Anchors both the
# canonical DB path and stored page_path normalization (index.py) + reopen
# (engine.resolve). On this host = C:\sovereign-citadel.
REPO_ROOT = Path(__file__).resolve().parents[2]
# Canonical retrieval DB — repo-root/retrieval.db, resolved from this file so
# cwd never matters and both the ingest path (index.py) and the API server
# (server.py) land on the SAME file. On this host = C:\sovereign-citadel\retrieval.db.
DEFAULT_DB_PATH = REPO_ROOT / "retrieval.db"


def _try_load_vec(conn: sqlite3.Connection) -> bool:
    try:
        conn.enable_load_extension(True)
    except sqlite3.NotSupportedError:
        return False
    try:
        import sqlite_vec  # type: ignore

        sqlite_vec.load(conn)
        return True
    except Exception:
        return False
    finally:
        try:
            conn.enable_load_extension(False)
        except sqlite3.NotSupportedError:
            pass


VEC_EXTENSION_LOADED: dict[str, bool] = {}


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    VEC_EXTENSION_LOADED[str(path)] = _try_load_vec(conn)
    return conn


def reset(db_path: Path | str | None = None) -> None:
    path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
    for suffix in ("", "-wal", "-shm"):
        p = path.with_name(path.name + suffix) if suffix else path
        if p.exists():
            p.unlink()
