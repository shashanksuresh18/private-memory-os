"""Entity merge logic with hash-chained audit row.

Merging contact B (secondary) into contact A (primary):
    1. Pull non-empty fields from B that A does not have. Record the override map.
    2. UPDATE A with the union row.
    3. SET B.merged_into = A.id  (soft-delete; B becomes hidden from active view).
    4. Re-parent every interaction + source from B to A.
    5. Append a hash-chained row to `merges` so the merge has its own audit trail.

Hash chain rule for `merges`:
    record["hash"] = sha256(
        json.dumps(record_minus_hash_field, sort_keys=True, ensure_ascii=False)
    )
matches the audit-log convention used elsewhere in the system.
"""
from __future__ import annotations

import getpass
import hashlib
import json
import sqlite3
from typing import Optional

from .db import transaction
from .models import Contact, MergeRecord, _new_id, _now_iso
from .repository import get_contact


_MERGE_FIELDS = ("primary_email", "primary_phone", "company", "role", "notes")


def _operator_default() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return "unknown"


def _last_merge_hash(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "SELECT hash FROM merges ORDER BY merged_at DESC LIMIT 1;"
    ).fetchone()
    return row["hash"] if row else ""


def _canonical_hash(record: dict) -> str:
    record_no_hash = {k: v for k, v in record.items() if k != "hash"}
    canonical = json.dumps(record_no_hash, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def merge_contacts(
    conn: sqlite3.Connection,
    primary_id: str,
    secondary_id: str,
    *,
    reason: str = "",
    operator_id: Optional[str] = None,
) -> MergeRecord:
    """Merge ``secondary_id`` into ``primary_id``. Returns the new MergeRecord."""
    if primary_id == secondary_id:
        raise ValueError("primary_id and secondary_id must differ")

    primary = get_contact(conn, primary_id)
    secondary = get_contact(conn, secondary_id)
    if primary is None or secondary is None:
        raise LookupError("primary or secondary contact does not exist")
    if primary.merged_into is not None:
        raise ValueError(f"primary {primary_id} is itself merged into {primary.merged_into}")
    if secondary.merged_into is not None:
        raise ValueError(f"secondary {secondary_id} is already merged into {secondary.merged_into}")

    overrides: dict[str, list[Optional[str]]] = {}
    new_values: dict[str, Optional[str]] = {}
    for f in _MERGE_FIELDS:
        a = getattr(primary, f)
        b = getattr(secondary, f)
        if (a in (None, "")) and (b not in (None, "")):
            new_values[f] = b
            overrides[f] = [a, b]

    operator = operator_id or _operator_default()
    merge = {
        "id": _new_id(),
        "primary_contact_id": primary_id,
        "merged_contact_id": secondary_id,
        "operator_id": operator,
        "reason": reason or None,
        "fields_overridden": json.dumps(overrides, ensure_ascii=False) if overrides else None,
        "prev_hash": _last_merge_hash(conn),
        "merged_at": _now_iso(),
    }
    merge["hash"] = _canonical_hash(merge)

    with transaction(conn):
        if new_values:
            cols = ", ".join(f"{k} = ?" for k in new_values)
            conn.execute(
                f"UPDATE contacts SET {cols} WHERE id = ?;",
                (*new_values.values(), primary_id),
            )

        conn.execute(
            "UPDATE contacts SET merged_into = ? WHERE id = ?;",
            (primary_id, secondary_id),
        )
        conn.execute(
            "UPDATE interactions SET contact_id = ? WHERE contact_id = ?;",
            (primary_id, secondary_id),
        )
        conn.execute(
            "UPDATE sources SET contact_id = ? WHERE contact_id = ?;",
            (primary_id, secondary_id),
        )

        conn.execute(
            """
            INSERT INTO merges (id, primary_contact_id, merged_contact_id,
                                operator_id, reason, fields_overridden,
                                prev_hash, hash, merged_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                merge["id"], merge["primary_contact_id"], merge["merged_contact_id"],
                merge["operator_id"], merge["reason"], merge["fields_overridden"],
                merge["prev_hash"], merge["hash"], merge["merged_at"],
            ),
        )

    return MergeRecord.model_validate(merge)


def verify_merge_chain(conn: sqlite3.Connection) -> tuple[bool, int, Optional[int]]:
    """Recompute hashes for every row in `merges` table.

    Returns (chain_ok, rows_checked, broken_row_id_or_None).
    """
    rows = conn.execute("SELECT * FROM merges ORDER BY merged_at ASC;").fetchall()
    prev = ""
    for n, row in enumerate(rows, 1):
        rec = dict(row)
        claimed = rec.pop("hash")
        if rec.get("prev_hash", "") != prev:
            return False, n, n
        expected = _canonical_hash(rec)
        if claimed != expected:
            return False, n, n
        prev = claimed
    return True, len(rows), None
