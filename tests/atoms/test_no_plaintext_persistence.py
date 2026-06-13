"""Atoms = pointers, never text (LOCKED gating invariant).

Three layered assertions:

1. SCHEMA — atoms / entities / entity_aliases tables contain no `text*`
   column. PRAGMA table_info scrape, not just a regex over schema.sql.

2. RUNTIME — after ingesting a page that contains uniquely identifiable
   strings (an email + a deal codename + a USD amount), the `atoms.db`
   raw bytes do NOT contain any of those substrings.

3. AUDIT LOG — after resolving each atom via the resolver and calling
   `append_atom_event`, the `audit/atoms.jsonl` file does NOT contain any
   of those substrings. SHA-256 of resolved bytes IS present and matches
   a recomputation.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from src.memory.atoms import (
    append_atom_event,
    db as atomsdb,
    extract_atoms,
    resolver,
    verify_audit_chain,
)
from src.memory.atoms.audit import scan_for_plaintext
from src.memory.atoms.extractor import persist_atoms


CANARY_EMAIL = "ada.lovelace@example.invalid"
CANARY_CODENAME = "ProjectQuokka"
CANARY_AMOUNT = "$427.5M"


def _make_synthetic_page(vault: Path) -> tuple[Path, str]:
    page_path = vault / "p.md"
    body = (
        "---\ntier: S3\n---\n"
        "# Synthetic Memo\n\n"
        f"Contact: {CANARY_EMAIL}. Deal: {CANARY_CODENAME}. Size: {CANARY_AMOUNT}.\n"
    )
    page_path.write_bytes(body.encode("utf-8"))
    return page_path, body


@pytest.mark.gating
def test_schema_has_no_text_column(tmp_path: Path) -> None:
    db_path = tmp_path / "atoms.db"
    conn = atomsdb.connect(db_path)
    try:
        for table in ("atoms", "entities", "entity_aliases", "atom_entity"):
            rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
            assert rows, f"missing table {table}"
            for r in rows:
                col_name = r["name"].lower()
                assert "text" not in col_name, (
                    f"forbidden text-like column in {table}: {col_name}"
                )
    finally:
        conn.close()


@pytest.mark.gating
def test_atoms_db_contains_no_plaintext(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    page_path, body = _make_synthetic_page(vault)
    db_path = tmp_path / "atoms.db"

    conn = atomsdb.connect(db_path)
    try:
        atoms = extract_atoms(
            page_slug="p",
            page_source_bytes=body.encode("utf-8"),
            chunks=[(None, body, 0)],
            tier="S3",
            codename_terms=[CANARY_CODENAME],
        )
        # Sanity: we extracted at least the three canaries.
        labels = {a.label for a in atoms}
        assert "EMAIL" in labels
        assert "USD_AMOUNT" in labels
        assert "CODENAME" in labels
        persist_atoms(conn, atoms)
    finally:
        conn.close()

    raw_db = db_path.read_bytes()
    for canary in (CANARY_EMAIL, CANARY_CODENAME, CANARY_AMOUNT):
        assert canary.encode("utf-8") not in raw_db, (
            f"plaintext canary {canary!r} found in atoms.db bytes"
        )


@pytest.mark.gating
def test_audit_log_persists_only_hashes(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    page_path, body = _make_synthetic_page(vault)
    db_path = tmp_path / "atoms.db"
    audit_path = tmp_path / "audit" / "atoms.jsonl"

    conn = atomsdb.connect(db_path)
    try:
        atoms = extract_atoms(
            page_slug="p",
            page_source_bytes=body.encode("utf-8"),
            chunks=[(None, body, 0)],
            tier="S3",
            codename_terms=[CANARY_CODENAME],
        )
        ids = persist_atoms(conn, atoms)
        assert ids
        for aid in ids:
            row = conn.execute(
                "SELECT page_slug, byte_start, byte_end, tier FROM atoms WHERE atom_id=?",
                (aid,),
            ).fetchone()
            resolved = resolver.resolve_atom(conn, vault, aid).encode("utf-8")
            append_atom_event(
                audit_path,
                atom_id=aid,
                page_slug=row["page_slug"],
                byte_start=int(row["byte_start"]),
                byte_end=int(row["byte_end"]),
                tier=row["tier"],
                peer="test-suite",
                resolved_bytes=resolved,
            )
    finally:
        conn.close()

    # Audit log must not contain the canary substrings.
    found = scan_for_plaintext(audit_path, [CANARY_EMAIL, CANARY_CODENAME, CANARY_AMOUNT])
    assert not found, f"plaintext canaries leaked into audit log: {found}"

    # And the canary's SHA-256 hash MUST appear at least once (proves we
    # really did persist the hash, not nothing).
    canary_hash = hashlib.sha256(CANARY_EMAIL.encode("utf-8")).hexdigest()
    assert canary_hash in audit_path.read_text(encoding="utf-8")

    # Hash chain intact.
    assert verify_audit_chain(audit_path) == []


@pytest.mark.gating
def test_resolver_reads_live_source(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    page_path, body = _make_synthetic_page(vault)
    db_path = tmp_path / "atoms.db"

    conn = atomsdb.connect(db_path)
    try:
        atoms = extract_atoms(
            page_slug="p",
            page_source_bytes=body.encode("utf-8"),
            chunks=[(None, body, 0)],
            tier="S3",
        )
        ids = persist_atoms(conn, atoms)
        for aid in ids:
            row = conn.execute(
                "SELECT byte_start, byte_end FROM atoms WHERE atom_id=?", (aid,),
            ).fetchone()
            live = resolver.resolve_atom(conn, vault, aid)
            raw_slice = body.encode("utf-8")[int(row["byte_start"]):int(row["byte_end"])].decode("utf-8")
            assert live == raw_slice
    finally:
        conn.close()
