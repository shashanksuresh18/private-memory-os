"""Hash-only persistence + scoreboard for Compare / Council votes.

This module NEVER receives prompt or response plaintext: callers pass pre-hashed
panes. The only content-derived values written are SHA-256 hashes, so nothing
sensitive lands on disk (`compare_history.db` is gitignored by the `*.db` rule).
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent / "compare_schema.sql"
# Repo root, resolved from this file so cwd never matters:
# history_db.py -> compare -> api -> src -> <repo root>.
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB_PATH = REPO_ROOT / "compare_history.db"


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    return conn


def record_vote(
    *,
    comp_id: str,
    prompt_sha256: str,
    blind: bool,
    model_ids: list[str],
    winner_model_id: str | None,
    panes: list[dict],
    db_path: Path | str | None = None,
) -> int:
    """Append one voted comparison. ``panes`` must already be hash-only:
    each item carries ``model_id, latency_ms, prompt_tokens, completion_tokens,
    status, response_sha256`` -- no response text. Returns the new row id."""
    now = time.time()
    conn = connect(db_path)
    try:
        cur = conn.execute(
            """
            INSERT INTO compare_history
                (comp_id, ts, prompt_sha256, blind, models_json,
                 winner_model_id, panes_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                comp_id,
                now,
                prompt_sha256,
                1 if blind else 0,
                json.dumps(model_ids),
                winner_model_id,
                json.dumps(panes),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def list_history(limit: int = 50, db_path: Path | str | None = None) -> list[dict]:
    conn = connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT comp_id, ts, prompt_sha256, blind, models_json,
                   winner_model_id, panes_json, created_at
            FROM compare_history
            ORDER BY id DESC
            LIMIT ?
            """,
            (int(limit),),
        ).fetchall()
    finally:
        conn.close()
    out: list[dict] = []
    for r in rows:
        out.append(
            {
                "comp_id": r["comp_id"],
                "ts": r["ts"],
                "prompt_sha256": r["prompt_sha256"],
                "blind": bool(r["blind"]),
                "models": json.loads(r["models_json"]),
                "winner_model_id": r["winner_model_id"],
                "panes": json.loads(r["panes_json"]),
                "created_at": r["created_at"],
            }
        )
    return out


def scoreboard(db_path: Path | str | None = None) -> list[dict]:
    """Aggregate wins/losses/ties/games + win% per model id across all votes."""
    history = list_history(limit=100000, db_path=db_path)
    stats: dict[str, dict] = {}

    def _row(model_id: str) -> dict:
        return stats.setdefault(
            model_id,
            {"model_id": model_id, "wins": 0, "losses": 0, "ties": 0, "games": 0},
        )

    for entry in history:
        winner = entry["winner_model_id"]
        for model_id in entry["models"]:
            s = _row(model_id)
            s["games"] += 1
            if winner == "tie" or winner is None:
                s["ties"] += 1
            elif winner == model_id:
                s["wins"] += 1
            else:
                s["losses"] += 1

    board = list(stats.values())
    for s in board:
        s["win_pct"] = round(100 * s["wins"] / s["games"], 1) if s["games"] else 0.0
    board.sort(key=lambda s: (s["win_pct"], s["wins"]), reverse=True)
    return board
