"""Pointer-only atoms layer (P3 scaffold).

Atoms are SPANS, never text. Each row references a live byte range in a
vault markdown file. The resolver reads the live file at query time and
returns the byte slice. The audit log persists SHA-256 hashes only.

Locked invariants (CLAUDE.md):
- Atoms table has NO `text` column.
- Audit persists only `sha256(resolved_bytes)`, never the bytes.
- Tier inherits from the source page; most-restrictive composite at the
  point of fusion with retrieval results.
- Deterministic regex extraction is the default; any LLM gate is opt-in,
  off-by-default, and forbidden on Tier S3.
"""

from .extractor import (
    Atom,
    ExtractedAtom,
    TierForbiddenLLMError,
    composite_tier,
    extract_atoms,
    extract_atoms_from_chunk,
    retier_page,
)
from .resolver import resolve_atom, resolve_span
from .audit import append_atom_event, verify_audit_chain

__all__ = [
    "Atom",
    "ExtractedAtom",
    "TierForbiddenLLMError",
    "composite_tier",
    "extract_atoms",
    "extract_atoms_from_chunk",
    "retier_page",
    "resolve_atom",
    "resolve_span",
    "append_atom_event",
    "verify_audit_chain",
]
