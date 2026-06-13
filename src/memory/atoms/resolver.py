"""Live-source resolver for atom spans.

Reads the page file from the vault at query time and returns the byte
slice as UTF-8. No caching, no in-memory text persistence. If the source
file has shifted since insertion (e.g., re-tier or edit), the resolver
returns whatever is at the recorded byte range NOW.

Callers that need the original-time bytes must rely on the audit log's
SHA-256 hash, not on the resolver's output.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Mapping


def resolve_span(vault_root: Path | str, page_slug: str,
                 byte_start: int, byte_end: int) -> str:
    """Reopen `vault_root / (page_slug + '.md')`, slice bytes, decode UTF-8."""
    root = Path(vault_root)
    # The page_slug is a posix-style relative path without extension.
    page_path = root / f"{page_slug}.md"
    raw = page_path.read_bytes()
    if not (0 <= byte_start < byte_end <= len(raw)):
        raise ValueError(
            f"span [{byte_start},{byte_end}) out of range for "
            f"{page_path} (len={len(raw)})"
        )
    return raw[byte_start:byte_end].decode("utf-8")


def resolve_atom(conn: sqlite3.Connection, vault_root: Path | str,
                 atom_id: int) -> str:
    row = conn.execute(
        "SELECT page_slug, byte_start, byte_end FROM atoms WHERE atom_id=?",
        (atom_id,),
    ).fetchone()
    if row is None:
        raise KeyError(f"atom_id {atom_id} not found")
    return resolve_span(
        vault_root,
        row["page_slug"],
        int(row["byte_start"]),
        int(row["byte_end"]),
    )


def resolve_many(conn: sqlite3.Connection, vault_root: Path | str,
                 atom_ids: list[int]) -> Mapping[int, str]:
    return {aid: resolve_atom(conn, vault_root, aid) for aid in atom_ids}
