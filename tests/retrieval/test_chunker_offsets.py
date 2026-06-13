"""Chunker invariant tests.

Offsets are byte offsets over UTF-8. Round-trip reopen must be exact.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.retrieval.chunker import OVERLAP_TOKENS, chunk_markdown


VAULT = Path(__file__).parent / "synthetic_public_vault"


def _all_pages():
    return sorted(VAULT.rglob("*.md"))


@pytest.mark.parametrize("page", _all_pages(), ids=lambda p: p.name)
def test_offsets_reopen_byte_identical(page: Path) -> None:
    source_text = page.read_text(encoding="utf-8")
    source_bytes = source_text.encode("utf-8")
    chunks = chunk_markdown(source_text)
    assert chunks, f"no chunks produced for {page}"
    for ch in chunks:
        slice_bytes = source_bytes[ch.byte_start:ch.byte_end]
        assert slice_bytes.decode("utf-8") == ch.text, (
            f"byte slice != chunk text for {page} [{ch.byte_start},{ch.byte_end})"
        )


@pytest.mark.parametrize("page", _all_pages(), ids=lambda p: p.name)
def test_chunks_within_bounds(page: Path) -> None:
    source_text = page.read_text(encoding="utf-8")
    source_bytes = source_text.encode("utf-8")
    for ch in chunk_markdown(source_text):
        assert 0 <= ch.byte_start < ch.byte_end <= len(source_bytes)
        assert ch.line_start >= 1
        assert ch.line_end >= ch.line_start


def test_offsets_are_byte_not_char() -> None:
    text = "---\ntier: S1\n---\n# H\n\nemoji ééé next line.\n"
    chunks = chunk_markdown(text)
    src = text.encode("utf-8")
    for ch in chunks:
        # `é` is 2 bytes UTF-8; char offset would mis-slice. Byte slice must round-trip.
        assert src[ch.byte_start:ch.byte_end].decode("utf-8") == ch.text
