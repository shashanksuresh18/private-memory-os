"""Auto-wiki concept extraction for successful retrievals.

Runs after citations are already resolved. Production extraction uses the
loopback Ollama model `gemma4-citadel`; tests inject a deterministic extractor
so no network is needed.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable, Iterable

import httpx

from src.retrieval.answer import redact_pii
from src.retrieval.engine import Citation

OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
AUTO_WIKI_MODEL = os.environ.get("AUTO_WIKI_MODEL", "gemma4-citadel")
_TIER_RANK = {"S1": 1, "S2": 2, "S3": 3}


@dataclass(frozen=True)
class ExtractedConcept:
    name: str
    facts: list[str]


Extractor = Callable[[list[str]], list[ExtractedConcept]]


def concept_tier(citations: Iterable[Citation]) -> str:
    rank = 0
    for citation in citations:
        rank = max(rank, _TIER_RANK.get(citation.tier, 3))
    return {1: "S1", 2: "S2", 3: "S3"}.get(rank, "S3")


def _vault_root_for(citations: list[Citation], vault_root: Path | None) -> Path:
    if vault_root is not None:
        return vault_root
    for citation in citations:
        path = Path(citation.page_path).resolve()
        for parent in [path.parent, *path.parents]:
            if parent.name == "vault":
                return parent
    return Path(__file__).resolve().parents[2] / "vault"


def _slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "untitled-concept"


def _frontmatter_value(text: str, key: str) -> str | None:
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end == -1:
        return None
    for line in text[4:end].splitlines():
        if line.startswith(f"{key}:"):
            return line.split(":", 1)[1].strip().strip('"')
    return None


def _is_auto_wiki_file(path: Path) -> bool:
    if not path.exists():
        return True
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    return _frontmatter_value(text, "source") == "auto-wiki"


def _ollama_extract(texts: list[str]) -> list[ExtractedConcept]:
    prompt = (
        "Extract key entities and durable facts from these citation texts. "
        "Return ONLY JSON in this shape: "
        '{"concepts":[{"name":"Concept Name","facts":["fact one","fact two"]}]}. '
        "Do not invent facts. Keep facts short.\n\n"
    )
    for idx, text in enumerate(texts, start=1):
        prompt += f"## Citation {idx}\n{text}\n\n"

    payload = {
        "model": AUTO_WIKI_MODEL,
        "stream": False,
        "think": False,
        "options": {"temperature": 0.0, "num_predict": 512},
        "messages": [
            {"role": "system", "content": "You create local markdown wiki facts."},
            {"role": "user", "content": prompt},
        ],
    }
    response = httpx.post(
        f"{OLLAMA_URL.rstrip('/')}/api/chat",
        json=payload,
        timeout=httpx.Timeout(600.0, connect=10.0),
    )
    response.raise_for_status()
    content = ((response.json().get("message") or {}).get("content")) or ""
    return _parse_concepts(content)


def _parse_concepts(content: str) -> list[ExtractedConcept]:
    raw = content.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?", "", raw).strip()
        raw = re.sub(r"```$", "", raw).strip()
    data = json.loads(raw)
    concepts = data.get("concepts", [])
    out: list[ExtractedConcept] = []
    if not isinstance(concepts, list):
        return out
    for item in concepts:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        facts = item.get("facts") or []
        if not name or not isinstance(facts, list):
            continue
        clean_facts = [str(f).strip() for f in facts if str(f).strip()]
        if clean_facts:
            out.append(ExtractedConcept(name=name, facts=clean_facts))
    return out


def _texts_for_extraction(citations: list[Citation], tier: str) -> list[str]:
    texts = [c.text for c in citations[:3] if c.text.strip()]
    if tier == "S2":
        return [redact_pii(text) for text in texts]
    return texts


def _render(concept: ExtractedConcept, tier: str, sources: list[str],
            updated: str) -> str:
    facts = concept.facts
    if tier == "S2":
        facts = [redact_pii(fact) for fact in facts]
    source_lines = "\n".join(f"- {source}" for source in sources)
    fact_lines = "\n".join(f"- {fact}" for fact in facts)
    return (
        "---\n"
        f"tier: {tier}\n"
        "source: auto-wiki\n"
        f"updated: {updated}\n"
        "---\n"
        f"## {concept.name}\n"
        f"{fact_lines}\n"
        "## Sources\n"
        f"{source_lines}\n"
    )


def run_auto_wiki(citations: list[Citation], vault_root: Path | None = None,
                  extractor: Extractor | None = None,
                  updated: str | None = None) -> list[Path]:
    if not citations:
        return []

    tier = concept_tier(citations)
    texts = _texts_for_extraction(citations, tier)
    if not texts:
        return []
    extractor = extractor or _ollama_extract

    try:
        concepts = extractor(texts)
    except Exception:
        return []
    if not concepts:
        return []

    root = _vault_root_for(citations, vault_root)
    concepts_dir = root / "concepts"
    concepts_dir.mkdir(parents=True, exist_ok=True)
    sources = list(dict.fromkeys(c.page_path for c in citations[:3]))
    stamp = updated or date.today().isoformat()
    written: list[Path] = []

    for concept in concepts:
        path = concepts_dir / f"{_slug(concept.name)}.md"
        if not _is_auto_wiki_file(path):
            continue
        path.write_text(_render(concept, tier, sources, stamp), encoding="utf-8")
        written.append(path)
    return written


__all__ = [
    "ExtractedConcept",
    "concept_tier",
    "run_auto_wiki",
]
