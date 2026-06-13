"""Local-only structuring of raw notes into vault markdown.

Converts free-form notes into a templated markdown body using the loopback
Ollama model ``gemma4-citadel``. This path is local-only for EVERY tier in v1:
no Nebius, no DeepSeek, no cloud fallback. S3 content never leaves the machine
(the ``/ingest`` endpoint wraps the call in a non-loopback socket fence). The
server -- not the model -- is authoritative for frontmatter (tier / source /
date / title); the model only shapes the body.

If the local model is unreachable or returns nothing usable, the raw content is
wrapped in the doc-type's section skeleton deterministically (still 100% local,
still no cloud) so a dropped note is never lost.
"""

from __future__ import annotations

import os

import httpx

OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
STRUCTURE_MODEL = os.environ.get("INGEST_MODEL", "gemma4-citadel")

# The five document shapes the operator can capture. Kept in sync with the
# server's validation set and the AddDocument.tsx dropdown.
DOC_TYPES = ("meeting", "company", "memo", "research", "email")

# Per-type section skeletons. Used both to steer the local model and as the
# deterministic fallback wrapper when the model is unavailable.
_TEMPLATE_SECTIONS: dict[str, list[str]] = {
    "meeting": ["Attendees", "Discussion", "Decisions", "Action Items"],
    "company": ["Overview", "Key People", "Financials", "Notes"],
    "memo": ["Summary", "Background", "Analysis", "Recommendation"],
    "research": ["Thesis", "Key Findings", "Evidence", "Risks"],
    "email": ["Summary", "Key Points", "Follow-ups"],
}

_TYPE_LABEL: dict[str, str] = {
    "meeting": "meeting notes",
    "company": "company profile",
    "memo": "memo",
    "research": "research note",
    "email": "email thread summary",
}


def _skeleton(doc_type: str) -> list[str]:
    return _TEMPLATE_SECTIONS.get(doc_type, ["Summary", "Notes"])


def _fallback(content: str, doc_type: str) -> str:
    """Deterministic, network-free structuring used when the model is down.

    Wraps the raw notes under the doc-type's section headings. The first section
    carries the original text verbatim; the rest are left as empty stubs for the
    operator to fill. No content is lost and nothing leaves the machine.
    """
    sections = _skeleton(doc_type)
    body = content.strip()
    parts = [f"## {sections[0]}", "", body, ""]
    for heading in sections[1:]:
        parts.append(f"## {heading}")
        parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def _build_prompt(content: str, doc_type: str) -> str:
    sections = _skeleton(doc_type)
    heading_list = ", ".join(sections)
    return (
        f"You are formatting raw notes into a clean Markdown {_TYPE_LABEL[doc_type]}.\n"
        f"Use ONLY these top-level sections, as `## ` headings, in this order: "
        f"{heading_list}.\n"
        "Rules:\n"
        "- Do NOT invent facts; only reorganise what is in the notes.\n"
        "- Do NOT write YAML frontmatter, a title line, or a `# ` H1 heading.\n"
        "- Leave a section empty if the notes say nothing about it.\n"
        "- Output Markdown only, no commentary.\n\n"
        "Raw notes:\n"
        f"{content.strip()}\n"
    )


def _strip_leading_frontmatter(text: str) -> str:
    """Drop a leading ``---`` YAML block if the model emitted one.

    The server owns frontmatter, so any frontmatter the model produces is
    discarded to avoid a double block (which would break ``parse_tier``).
    """
    stripped = text.lstrip()
    if not stripped.startswith("---"):
        return text
    end = stripped.find("\n---", 3)
    if end == -1:
        return text
    after = stripped[end + 4 :]
    return after.lstrip("\n")


def _ollama_structure(content: str, doc_type: str) -> str:
    payload = {
        "model": STRUCTURE_MODEL,
        "stream": False,
        "think": False,
        "options": {"temperature": 0.0, "num_predict": 1024},
        "messages": [
            {
                "role": "system",
                "content": "You format raw notes into clean local Markdown. Local-only.",
            },
            {"role": "user", "content": _build_prompt(content, doc_type)},
        ],
    }
    response = httpx.post(
        f"{OLLAMA_URL.rstrip('/')}/api/chat",
        json=payload,
        timeout=httpx.Timeout(600.0, connect=10.0),
    )
    response.raise_for_status()
    return ((response.json().get("message") or {}).get("content")) or ""


def structure_content(content: str, doc_type: str) -> str:
    """Turn raw notes into a structured Markdown BODY (no frontmatter).

    Local-only via ``gemma4-citadel`` on loopback Ollama. Falls back to the
    deterministic section skeleton (no network) when the model is unreachable or
    returns nothing usable, so a captured note is never lost. The caller (the
    ``/ingest`` endpoint) prepends the authoritative frontmatter.
    """
    if doc_type not in DOC_TYPES:
        # Defensive: the server validates first, but never structure an unknown
        # shape with an invented template.
        raise ValueError(f"unsupported doc_type: {doc_type!r}")
    try:
        raw = _ollama_structure(content, doc_type)
    except Exception:
        return _fallback(content, doc_type)
    body = _strip_leading_frontmatter(raw).strip()
    if not body:
        return _fallback(content, doc_type)
    return body + "\n"


__all__ = ["DOC_TYPES", "structure_content"]
