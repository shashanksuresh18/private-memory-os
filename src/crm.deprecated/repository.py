"""CRM CRUD repository over SQLite.

Functions return Pydantic models (or lists of them). All writes use
parameterized SQL — no string concat.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Iterable, Optional

from .db import connect, transaction
from .models import Contact, Interaction, MergeRecord, Source


# ---------- contacts ----------

def upsert_contact(conn: sqlite3.Connection, contact: Contact) -> Contact:
    """Insert or update a contact by ``id``. Does not move ``merged_into``.

    To merge two contacts, call ``merges.merge_contacts`` — it is the only
    code path allowed to set ``merged_into``.
    """
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO contacts (id, display_name, primary_email, primary_phone,
                                  company, role, tier, notes,
                                  created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                display_name  = excluded.display_name,
                primary_email = excluded.primary_email,
                primary_phone = excluded.primary_phone,
                company       = excluded.company,
                role          = excluded.role,
                tier          = excluded.tier,
                notes         = excluded.notes;
            """,
            (
                contact.id, contact.display_name, contact.primary_email, contact.primary_phone,
                contact.company, contact.role, contact.tier, contact.notes,
                contact.created_at, contact.updated_at,
            ),
        )
    return get_contact(conn, contact.id) or contact


def get_contact(conn: sqlite3.Connection, contact_id: str) -> Optional[Contact]:
    row = conn.execute("SELECT * FROM contacts WHERE id = ?;", (contact_id,)).fetchone()
    return Contact.model_validate(dict(row)) if row else None


def find_contact_by_email(conn: sqlite3.Connection, email: str) -> Optional[Contact]:
    row = conn.execute(
        "SELECT * FROM active_contacts WHERE primary_email = ? LIMIT 1;",
        (email,),
    ).fetchone()
    return Contact.model_validate(dict(row)) if row else None


def list_active_contacts(
    conn: sqlite3.Connection,
    *,
    limit: int = 100,
    offset: int = 0,
    search: Optional[str] = None,
) -> list[Contact]:
    """Return active (non-merged) contacts. ``search`` does a case-insensitive
    LIKE on display_name, primary_email, and company."""
    if search:
        like = f"%{search}%"
        rows = conn.execute(
            """
            SELECT * FROM active_contacts
            WHERE display_name  LIKE ? COLLATE NOCASE
               OR primary_email LIKE ? COLLATE NOCASE
               OR company       LIKE ? COLLATE NOCASE
            ORDER BY display_name COLLATE NOCASE
            LIMIT ? OFFSET ?;
            """,
            (like, like, like, limit, offset),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM active_contacts "
            "ORDER BY display_name COLLATE NOCASE LIMIT ? OFFSET ?;",
            (limit, offset),
        ).fetchall()
    return [Contact.model_validate(dict(r)) for r in rows]


def find_duplicate_candidates(conn: sqlite3.Connection, contact: Contact) -> list[Contact]:
    """Heuristic dedupe: same email OR same phone OR same display_name (case-folded)."""
    conditions: list[str] = []
    params: list[object] = []
    if contact.primary_email:
        conditions.append("primary_email = ?")
        params.append(contact.primary_email)
    if contact.primary_phone:
        conditions.append("primary_phone = ?")
        params.append(contact.primary_phone)
    conditions.append("LOWER(display_name) = LOWER(?)")
    params.append(contact.display_name)

    sql = (
        "SELECT * FROM active_contacts WHERE id != ? AND ("
        + " OR ".join(conditions)
        + ") ORDER BY updated_at DESC LIMIT 25;"
    )
    rows = conn.execute(sql, [contact.id, *params]).fetchall()
    return [Contact.model_validate(dict(r)) for r in rows]


# ---------- sources ----------

def add_source(conn: sqlite3.Connection, source: Source) -> Source:
    """Insert a source row. Raises sqlite3.IntegrityError on duplicate
    (source_type, source_external_id) — let caller decide policy."""
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO sources (id, contact_id, source_type, source_external_id,
                                 raw_blob, tier, captured_at)
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (
                source.id, source.contact_id, source.source_type, source.source_external_id,
                source.raw_blob, source.tier, source.captured_at,
            ),
        )
    return source


def list_sources_for(conn: sqlite3.Connection, contact_id: str) -> list[Source]:
    rows = conn.execute(
        "SELECT * FROM sources WHERE contact_id = ? ORDER BY captured_at DESC;",
        (contact_id,),
    ).fetchall()
    return [Source.model_validate(dict(r)) for r in rows]


# ---------- interactions ----------

def log_interaction(conn: sqlite3.Connection, interaction: Interaction) -> Interaction:
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO interactions (id, contact_id, interaction_type, ts,
                                      summary, body, source_id, tier, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                interaction.id, interaction.contact_id, interaction.interaction_type,
                interaction.ts, interaction.summary, interaction.body,
                interaction.source_id, interaction.tier, interaction.created_at,
            ),
        )
    return interaction


def list_interactions_for(
    conn: sqlite3.Connection,
    contact_id: str,
    *,
    limit: int = 50,
) -> list[Interaction]:
    rows = conn.execute(
        """
        SELECT * FROM interactions
        WHERE contact_id = ?
        ORDER BY ts DESC
        LIMIT ?;
        """,
        (contact_id, limit),
    ).fetchall()
    return [Interaction.model_validate(dict(r)) for r in rows]


def recent_interactions(conn: sqlite3.Connection, *, limit: int = 50) -> list[Interaction]:
    rows = conn.execute(
        "SELECT * FROM interactions ORDER BY ts DESC LIMIT ?;",
        (limit,),
    ).fetchall()
    return [Interaction.model_validate(dict(r)) for r in rows]


# ---------- merges (read-only here; writes live in merges.py) ----------

def list_merges(conn: sqlite3.Connection, *, limit: int = 100) -> list[MergeRecord]:
    rows = conn.execute(
        "SELECT * FROM merges ORDER BY merged_at DESC LIMIT ?;", (limit,),
    ).fetchall()
    return [MergeRecord.model_validate(dict(r)) for r in rows]


def merges_for(conn: sqlite3.Connection, contact_id: str) -> list[MergeRecord]:
    rows = conn.execute(
        """
        SELECT * FROM merges
        WHERE primary_contact_id = ? OR merged_contact_id = ?
        ORDER BY merged_at DESC;
        """,
        (contact_id, contact_id),
    ).fetchall()
    return [MergeRecord.model_validate(dict(r)) for r in rows]


# ---------- counts (for dashboard tiles) ----------

def counts(conn: sqlite3.Connection) -> dict:
    """Aggregate stats for UI tiles."""
    def scalar(sql: str, *params) -> int:
        return int(conn.execute(sql, params).fetchone()[0])

    return {
        "contacts_active": scalar("SELECT COUNT(*) FROM active_contacts;"),
        "contacts_total":  scalar("SELECT COUNT(*) FROM contacts;"),
        "interactions":    scalar("SELECT COUNT(*) FROM interactions;"),
        "merges":          scalar("SELECT COUNT(*) FROM merges;"),
        "sources":         scalar("SELECT COUNT(*) FROM sources;"),
    }
