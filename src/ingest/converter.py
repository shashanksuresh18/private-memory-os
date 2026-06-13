"""Local-only pre-ingest conversion to vault markdown.

MarkItDown is configured without plugins or LLM clients. Callers are
responsible for validating untrusted paths before passing them here.
"""

from __future__ import annotations

from pathlib import Path

from markitdown import MarkItDown

_md = MarkItDown(enable_plugins=False)
_md.llm_client = None
_md.enable_plugins = False

SUPPORTED = {".pdf", ".docx", ".pptx", ".xlsx", ".html", ".csv", ".txt"}
DEFAULT_TIER = "S3"


def to_markdown(path: Path, tier: str | None = None) -> str:
    """Convert a supported local file to markdown with tier frontmatter."""
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED:
        raise ValueError(f"Unsupported: {path.suffix}")
    if suffix == ".txt":
        # Plain text needs no converter: read directly so the output is
        # byte-deterministic and never depends on MarkItDown's txt handling.
        body = path.read_text(encoding="utf-8", errors="replace")
    else:
        body = _md.convert_local(str(path)).text_content
    effective_tier = tier or DEFAULT_TIER
    frontmatter = f"---\ntier: {effective_tier}\n---\n\n"
    return frontmatter + body


def convert_to_vault(
    source: Path,
    vault_inbox: Path,
    tier: str | None = None,
) -> Path:
    """Convert source file into vault inbox as markdown without overwriting."""
    out = vault_inbox / (source.stem + ".md")
    if out.exists():
        raise FileExistsError(
            f"Vault file exists: {out}. "
            f"Delete manually to re-convert."
        )
    md = to_markdown(source, tier)
    out.write_text(md, encoding="utf-8")
    return out

