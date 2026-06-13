"""Markdown chunker — heading-aware (H1/H2), 512 tokens, 64 overlap.

Offset unit invariant: BYTE offsets over the UTF-8 encoding of the source
file. The reopen path slices `source.encode('utf-8')[byte_start:byte_end]`
and decodes back to UTF-8 — round-trip is exact when offsets fall on UTF-8
code-point boundaries. The splitter guarantees this by only splitting on
ASCII boundaries (newlines and ASCII whitespace).

Tokenizer: tiktoken `cl100k_base`, vendored locally. No network.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

# Pin tiktoken to the in-repo vendored cl100k_base BPE ranks BEFORE importing
# tiktoken, so the S3 ingest/retrieve path can never reach
# openaipublic.blob.core.windows.net to download them. Forced (not setdefault)
# so an ambient TIKTOKEN_CACHE_DIR can't redirect us off the offline copy.
# S3-never-cloud locked invariant — enforced by test_no_egress_on_s3.
_VENDOR_TIKTOKEN_CACHE = Path(__file__).resolve().parent / "vendor" / "tiktoken_cache"
os.environ["TIKTOKEN_CACHE_DIR"] = str(_VENDOR_TIKTOKEN_CACHE)

import tiktoken

CHUNK_TOKENS = 512
OVERLAP_TOKENS = 64

_HEADING_RE = re.compile(rb"(?m)^(#{1,2})\s+[^\n]*")


@dataclass(frozen=True)
class Chunk:
    text: str
    byte_start: int
    byte_end: int
    line_start: int
    line_end: int

    def __post_init__(self) -> None:
        if self.byte_end <= self.byte_start:
            raise ValueError(f"empty span: [{self.byte_start},{self.byte_end})")
        if self.line_end < self.line_start:
            raise ValueError(f"line_end<line_start: {self.line_start},{self.line_end}")


def _tokenizer() -> tiktoken.Encoding:
    return tiktoken.get_encoding("cl100k_base")


def _line_at(source_bytes: bytes, byte_offset: int) -> int:
    return source_bytes.count(b"\n", 0, byte_offset) + 1


def _heading_offsets(source_bytes: bytes) -> List[int]:
    offsets = [0]
    for m in _HEADING_RE.finditer(source_bytes):
        if m.start() > 0:
            offsets.append(m.start())
    offsets.append(len(source_bytes))
    return offsets


def _split_section_by_tokens(
    source_bytes: bytes,
    start: int,
    end: int,
    enc: tiktoken.Encoding,
) -> Iterable[tuple[int, int]]:
    # errors="replace": token/heading byte offsets can land mid-multibyte char
    # (and ingested bodies may carry stray bytes) — degrade, never crash.
    section_text = source_bytes[start:end].decode("utf-8", errors="replace")
    token_ids = enc.encode(section_text)
    if not token_ids:
        return
    if len(token_ids) <= CHUNK_TOKENS:
        yield start, end
        return

    cursor_tok = 0
    while cursor_tok < len(token_ids):
        win_end_tok = min(cursor_tok + CHUNK_TOKENS, len(token_ids))
        prefix_bytes = enc.decode(token_ids[:cursor_tok]).encode("utf-8")
        chunk_bytes = enc.decode(token_ids[cursor_tok:win_end_tok]).encode("utf-8")
        b_start = start + len(prefix_bytes)
        b_end = b_start + len(chunk_bytes)
        if b_end > end:
            b_end = end
        yield b_start, b_end
        if win_end_tok >= len(token_ids):
            return
        cursor_tok = win_end_tok - OVERLAP_TOKENS


def chunk_markdown(source_text: str) -> List[Chunk]:
    """Yield Chunks for a markdown document.

    `source_text` must be UTF-8 decodable. Offsets are over the UTF-8 bytes
    of `source_text.encode('utf-8')`.
    """
    source_bytes = source_text.encode("utf-8")
    enc = _tokenizer()
    heading_offsets = _heading_offsets(source_bytes)

    chunks: List[Chunk] = []
    for i in range(len(heading_offsets) - 1):
        sec_start = heading_offsets[i]
        sec_end = heading_offsets[i + 1]
        if sec_end - sec_start == 0:
            continue
        for b_start, b_end in _split_section_by_tokens(source_bytes, sec_start, sec_end, enc):
            if b_end <= b_start:
                continue
            text_slice = source_bytes[b_start:b_end].decode("utf-8", errors="replace")
            chunks.append(
                Chunk(
                    text=text_slice,
                    byte_start=b_start,
                    byte_end=b_end,
                    line_start=_line_at(source_bytes, b_start),
                    line_end=_line_at(source_bytes, max(b_start, b_end - 1)),
                )
            )
    return chunks
