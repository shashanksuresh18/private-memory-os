"""Sovereign Citadel local CRM (SQLite-backed)."""
from .db import connect, init_db, transaction
from .merges import merge_contacts, verify_merge_chain
from .models import Contact, Interaction, MergeRecord, Source
from .repository import (
    add_source,
    counts,
    find_contact_by_email,
    find_duplicate_candidates,
    get_contact,
    list_active_contacts,
    list_interactions_for,
    list_merges,
    list_sources_for,
    log_interaction,
    merges_for,
    recent_interactions,
    upsert_contact,
)

__all__ = [
    "Contact", "Interaction", "MergeRecord", "Source",
    "init_db", "connect", "transaction",
    "upsert_contact", "get_contact", "find_contact_by_email",
    "list_active_contacts", "find_duplicate_candidates",
    "add_source", "list_sources_for",
    "log_interaction", "list_interactions_for", "recent_interactions",
    "merge_contacts", "verify_merge_chain",
    "list_merges", "merges_for", "counts",
]
