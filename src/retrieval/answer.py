"""Extraction-only answer layer for the local retrieval engine.

Plugs INTO the existing routing model (S1 cloud / S2 redact-then-cloud / S3
local-only). It does NOT replace ``src/routing/sovereign_router.py`` — the
router is the user-facing proxy; this is the internal answer composer that the
retrieval API calls once citations have been resolved.

Hard invariants (mirrors CLAUDE.md locked rules):

* ``SYSTEM_PROMPT`` is hardcoded — never user-configurable. Every model call,
  cloud or local, sends it verbatim.
* S1 path requires every citation to be S1 (raises ``TierViolationError``).
* S2 path refuses any S3 citation, redacts PII locally, and NEVER sends the
  original citation text to the cloud — only the redacted skeleton.
* S3 path talks only to the loopback Ollama endpoint; zero external egress.
* ``answer()`` fails closed: unknown / empty tier resolves to S3.

The model is told to quote verbatim and never paraphrase. We do not trust the
model to invent citation anchors — anchors are derived deterministically from
the resolved citations, so a quote always maps back to a real source span.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

import httpx
import requests

from src.retrieval.engine import Citation

# ---------------------------------------------------------------------------
# Hardcoded system prompt — NEVER user-configurable.
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """Do not paraphrase or synthesise.
You are an extraction engine.
Answer the user query by quoting the exact verbatim
sentences from the provided context chunks.
You must append a citation anchor to every quote."""

# ---------------------------------------------------------------------------
# Endpoints / models
# ---------------------------------------------------------------------------

NEBIUS_BASE_URL = os.environ.get(
    "NEBIUS_BASE_URL",
    "https://api.tokenfactory.nebius.com/v1/",
)
NEBIUS_MODEL = os.environ.get(
    "NEBIUS_MODEL",
    "deepseek-ai/DeepSeek-V3.2",
)
OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
HTTP_TIMEOUT_S = 120.0
# Local CPU inference (gemma4) is slow; extraction answers are short, so cap the
# generation budget and give the read a wide ceiling so it never trips the
# default timeout mid-generation.
OLLAMA_READ_TIMEOUT_S = float(os.environ.get("OLLAMA_READ_TIMEOUT_S", "600"))
OLLAMA_NUM_PREDICT = int(os.environ.get("OLLAMA_NUM_PREDICT", "256"))

DEFAULT_S3_MODEL = os.environ.get("OLLAMA_S3_MODEL", "gemma4")

_TIER_RANK = {"S1": 1, "S2": 2, "S3": 3}
_VALID_TIERS = ("S1", "S2", "S3")


class TierViolationError(RuntimeError):
    """Raised when a citation's tier exceeds what an answer path may handle."""


class CloudProviderUnavailable(RuntimeError):
    """Raised when an allowed cloud path is requested without credentials."""


# ---------------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------------

@dataclass
class CitationAnchor:
    page_path: str
    line_start: int
    line_end: int
    anchor: str  # "[vault/people/alice.md:L12-14]"


@dataclass
class AnswerResult:
    answer: str
    tier: str            # S1 / S2 / S3
    model_used: str
    anchors: list[CitationAnchor] = field(default_factory=list)
    redacted: bool = False


# ---------------------------------------------------------------------------
# Anchors
# ---------------------------------------------------------------------------

def make_anchor(citation: Citation) -> CitationAnchor:
    """Build a deterministic citation anchor from a resolved citation.

    Single-line spans render ``[path:L8]``; multi-line spans render
    ``[path:L22-24]``.
    """
    if citation.line_start == citation.line_end:
        text = f"[{citation.page_path}:L{citation.line_start}]"
    else:
        text = f"[{citation.page_path}:L{citation.line_start}-{citation.line_end}]"
    return CitationAnchor(
        page_path=citation.page_path,
        line_start=citation.line_start,
        line_end=citation.line_end,
        anchor=text,
    )


def _anchors_for(citations: list[Citation]) -> list[CitationAnchor]:
    return [make_anchor(c) for c in citations]


# ---------------------------------------------------------------------------
# Function 1 — Tier resolver
# ---------------------------------------------------------------------------

def resolve_answer_tier(citations: list[Citation]) -> str:
    """Most restrictive tier across all citations. S3 > S2 > S1.

    Empty list -> S3 (fail-closed).
    """
    if not citations:
        return "S3"
    rank = 0
    for c in citations:
        rank = max(rank, _TIER_RANK.get(getattr(c, "tier", "S3"), 3))
    return {1: "S1", 2: "S2", 3: "S3"}[rank]


# ---------------------------------------------------------------------------
# Function 2 — Context builder
# ---------------------------------------------------------------------------

def build_context(citations: list[Citation]) -> str:
    """Format citations as numbered context blocks.

        [1] vault/people/alice-liddell.md L12-14
        "exact text from citation.text"

        [2] vault/memos/project-orchid.md L41-58
        "exact text from citation.text"
    """
    blocks: list[str] = []
    for i, c in enumerate(citations, start=1):
        if c.line_start == c.line_end:
            span = f"L{c.line_start}"
        else:
            span = f"L{c.line_start}-{c.line_end}"
        blocks.append(f"[{i}] {c.page_path} {span}\n\"{c.text}\"")
    return "\n\n".join(blocks)


def _user_prompt(query: str, context: str) -> str:
    return f"Query: {query}\n\nContext chunks:\n{context}"


# ---------------------------------------------------------------------------
# Model transports (monkeypatchable seams — tests never hit real network)
# ---------------------------------------------------------------------------

def _nebius_chat(model: str, user_content: str,
                 system_prompt: str = SYSTEM_PROMPT) -> str:
    """Call Nebius' OpenAI-compatible chat completions endpoint.

    ``system_prompt`` defaults to the hardcoded extraction ``SYSTEM_PROMPT``
    (never mutated). The S1 no-vault fallback passes its own public-knowledge
    prompt instead — the extraction prompt would be wrong with no context.
    """
    api_key = os.environ.get("NEBIUS_API_KEY", "")
    if not api_key:
        raise CloudProviderUnavailable(
            "NEBIUS_API_KEY not set - cannot answer S1/S2 query via cloud"
        )
    response = requests.post(
        NEBIUS_BASE_URL.rstrip("/") + "/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_content,
                },
            ],
            "temperature": 0,
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def _ollama_chat(model: str, system_prompt: str, user_content: str) -> str:
    """Call the loopback Ollama chat endpoint. Returns the assistant text.

    Loopback only (127.0.0.1:11434). Never egresses.
    """
    payload = {
        "model": model,
        "stream": False,
        # gemma4 is a reasoning model; without this every token is spent on the
        # hidden "thinking" channel and `content` comes back empty. Extraction
        # needs the answer, not the reasoning, so thinking is disabled.
        "think": False,
        "options": {"temperature": 0.0, "num_predict": OLLAMA_NUM_PREDICT},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    }
    timeout = httpx.Timeout(OLLAMA_READ_TIMEOUT_S, connect=10.0)
    r = httpx.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=timeout)
    r.raise_for_status()
    body = r.json()
    return ((body.get("message") or {}).get("content")) or ""


# ---------------------------------------------------------------------------
# S2 local DLP redaction (ClawXRouter regex set, ported to Python)
# ---------------------------------------------------------------------------

# Magnitude suffixes for the ">$1M" amount gate.
_AMOUNT_SUFFIX = {"": 1, "k": 1e3, "m": 1e6, "b": 1e9, "t": 1e12,
                  "thousand": 1e3, "million": 1e6, "billion": 1e9, "trillion": 1e12}
_AMOUNT_THRESHOLD = 1_000_000

_RE_URL = re.compile(r"https?://\S+")
# ClawXRouter utils.ts opt-in email rule, ported verbatim.
_RE_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# classifier/main.py RE_PHONE, ported verbatim.
_RE_PHONE = re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
# $<num><suffix>; suffix optional. Magnitude filtered in code (>$1M only).
_RE_AMOUNT = re.compile(
    r"\$\s?(\d[\d,]*(?:\.\d+)?)(?:\s?(k|m|b|t|thousand|million|billion|trillion))?\b",
    re.IGNORECASE,
)
# Two-or-more capitalised words -> person name heuristic.
_RE_PERSON = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b")


def _amount_value(num: str, suffix: str) -> float:
    try:
        base = float(num.replace(",", ""))
    except ValueError:
        return 0.0
    return base * _AMOUNT_SUFFIX.get(suffix.lower(), 1)


def _load_entity_terms() -> list[str]:
    """Company / codename terms from the classifier denylist (longest first).

    Reused as the S2 ``[ENTITY]`` redaction set so a proprietary codename never
    egresses even after PII scrub.
    """
    base = os.environ.get(
        "SOVEREIGN_CLASSIFIER_DENYLIST_DIR",
        os.path.join(os.path.dirname(os.path.dirname(__file__)),
                     "routing", "classifier", "denylist"),
    )
    terms: list[str] = []
    for name in ("codenames.txt", "markers.txt"):
        path = os.path.join(base, name)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line and not line.startswith("#"):
                    terms.append(line)
    # Longest first so multi-word entities win over their substrings.
    return sorted(set(terms), key=len, reverse=True)


def redact_pii(text: str, entity_terms: list[str] | None = None) -> str:
    """Replace PII / sensitive entities with placeholders.

    Order matters: URL -> EMAIL -> AMOUNT(>$1M) -> PHONE -> ENTITY -> PERSON.
    """
    if entity_terms is None:
        entity_terms = _load_entity_terms()

    out = _RE_URL.sub("[URL]", text)
    out = _RE_EMAIL.sub("[EMAIL]", out)

    def _amount_sub(m: re.Match) -> str:
        if _amount_value(m.group(1), m.group(2) or "") >= _AMOUNT_THRESHOLD:
            return "[AMOUNT]"
        return m.group(0)

    out = _RE_AMOUNT.sub(_amount_sub, out)
    out = _RE_PHONE.sub("[PHONE]", out)

    for term in entity_terms:
        out = re.sub(re.escape(term), "[ENTITY]", out, flags=re.IGNORECASE)

    out = _RE_PERSON.sub("[PERSON]", out)
    return out


# ---------------------------------------------------------------------------
# Function 3 — S1 path (cloud)
# ---------------------------------------------------------------------------

def answer_s1(query: str, citations: list[Citation],
              model: str | None = None) -> AnswerResult:
    """S1 path - Nebius cloud (DeepSeek-V3.2).

    All citations must be S1. Raises TierViolationError for any S2/S3
    citation. Raises CloudProviderUnavailable if NEBIUS_API_KEY is not set.
    """
    for c in citations:
        if c.tier != "S1":
            raise TierViolationError(
                f"S1 path received {c.tier} citation: {c.page_path}"
            )
    resolved_model = model or NEBIUS_MODEL
    context = build_context(citations)
    text = _nebius_chat(resolved_model, f"{context}\n\nQuery: {query}")
    return AnswerResult(
        answer=text,
        tier="S1",
        model_used=resolved_model,
        anchors=_anchors_for(citations),
        redacted=False,
    )


# ---------------------------------------------------------------------------
# S1 no-vault fallback — public-markets question not covered by the vault.
# ---------------------------------------------------------------------------

# Public-knowledge prompt for the S1 fallback ONLY. Distinct from the hardcoded
# extraction SYSTEM_PROMPT (which must never change). Used when S1 retrieval
# finds nothing relevant, so there is no context to quote.
PUBLIC_FALLBACK_PROMPT = (
    "Answer from your knowledge. This is a public market question. "
    "Cite your knowledge source."
)

FALLBACK_DISCLAIMER = "Answered from model knowledge — not from vault"

# Extraction refusals — the hardcoded SYSTEM_PROMPT makes the model say one of
# these when the vault context does not contain the answer. On the S1 (public)
# path a refusal triggers a model-knowledge fallback; S2/S3 keep the refusal.
_REFUSAL_PHRASES = (
    "no information",
    "not in the provided context",
    "cannot find",
    "not mentioned",
    "no verbatim sentences",
    "does not contain",
    "no relevant",
)


def is_refusal(answer: str) -> bool:
    """True if an extractive answer is a 'not found in context' refusal."""
    a = (answer or "").lower()
    return any(p in a for p in _REFUSAL_PHRASES)


def answer_s1_public_fallback(query: str, model: str | None = None) -> AnswerResult:
    """S1-only: answer a public question from model knowledge, no vault context.

    Egress to Nebius is permitted on the S1 (public) path. NEVER reachable from
    S2/S3 — the caller gates this to resolved S1 with no relevant citations.
    """
    resolved_model = model or NEBIUS_MODEL
    text = _nebius_chat(resolved_model, f"Question: {query}",
                        system_prompt=PUBLIC_FALLBACK_PROMPT)
    return AnswerResult(
        answer=f"{FALLBACK_DISCLAIMER}\n\n{text}",
        tier="S1",
        model_used=resolved_model,
        anchors=[],
        redacted=False,
    )


# ---------------------------------------------------------------------------
# Function 4 — S2 path (redact then cloud)
# ---------------------------------------------------------------------------

def answer_s2(query: str, citations: list[Citation],
              model: str | None = None) -> AnswerResult:
    """Refuse any S3 citation. Redact PII locally, send only the redacted
    skeleton to the cloud. ``redacted`` is always True.
    """
    for c in citations:
        if c.tier == "S3":
            raise TierViolationError(
                f"answer_s2 received S3 citation {c.page_path!r}; S2 max"
            )

    entity_terms = _load_entity_terms()
    redacted_citations: list[Citation] = []
    for c in citations:
        scrubbed = redact_pii(c.text, entity_terms)
        # Copy so the original citation text is never mutated nor forwarded.
        rc = Citation(
            chunk_id=c.chunk_id, page_slug=c.page_slug, page_path=c.page_path,
            tier=c.tier, byte_start=c.byte_start, byte_end=c.byte_end,
            line_start=c.line_start, line_end=c.line_end, score=c.score,
            text=scrubbed,
        )
        redacted_citations.append(rc)

    resolved_model = model or NEBIUS_MODEL
    context = build_context(redacted_citations)
    text = _nebius_chat(resolved_model, f"{context}\n\nQuery: {query}")
    return AnswerResult(
        answer=text,
        tier="S2",
        model_used=resolved_model,
        anchors=_anchors_for(citations),
        redacted=True,
    )


# ---------------------------------------------------------------------------
# Function 5 — S3 path (local Ollama only)
# ---------------------------------------------------------------------------

_OLLAMA_UNAVAILABLE = (
    "Local model unavailable: S3 content cannot be answered without the "
    "loopback Ollama service. No cloud fallback is permitted."
)


def answer_s3(query: str, citations: list[Citation],
              model: str = DEFAULT_S3_MODEL) -> AnswerResult:
    """Calls http://127.0.0.1:11434/api/chat ONLY. Never any external API.

    If Ollama is not running, fails gracefully (no raise, no egress) with a
    notice so the S3 path can be exercised in environments without a model.
    """
    context = build_context(citations)
    try:
        text = _ollama_chat(model, SYSTEM_PROMPT, _user_prompt(query, context))
    except httpx.HTTPError:
        text = _OLLAMA_UNAVAILABLE
    return AnswerResult(
        answer=text,
        tier="S3",
        model_used=model,
        anchors=_anchors_for(citations),
        redacted=False,
    )


# ---------------------------------------------------------------------------
# Function 6 — Main entry point
# ---------------------------------------------------------------------------

def answer(query: str, citations: list[Citation],
           force_tier: str | None = None) -> AnswerResult:
    """Resolve the answer tier and route to the matching path.

    ``force_tier`` is a test-only override. Unknown / empty -> S3 (fail-closed).

    Dispatch resolves ``answer_s{1,2,3}`` through module globals at call time so
    the routing seam stays monkeypatchable in tests.
    """
    if not citations and force_tier is None:
        raise TierViolationError("no citations to answer from; fail-closed")

    tier = force_tier or resolve_answer_tier(citations)
    if tier == "S1":
        result = answer_s1(query, citations)
    elif tier == "S2":
        result = answer_s2(query, citations)
    else:
        result = answer_s3(query, citations)  # S3 + unknown -> fail-closed local

    # Refusal-retry: the vault did not actually answer (extraction returned a
    # 'not in context' refusal). On S1 (public) only, answer from model
    # knowledge with a disclaimer. S2/S3 NEVER take a no-context cloud path —
    # the refusal is returned verbatim.
    if tier == "S1" and is_refusal(result.answer):
        return answer_s1_public_fallback(query)
    return result


__all__ = [
    "SYSTEM_PROMPT",
    "CitationAnchor",
    "AnswerResult",
    "TierViolationError",
    "CloudProviderUnavailable",
    "resolve_answer_tier",
    "build_context",
    "redact_pii",
    "make_anchor",
    "answer_s1",
    "answer_s1_public_fallback",
    "answer_s2",
    "answer_s3",
    "answer",
    "is_refusal",
    "PUBLIC_FALLBACK_PROMPT",
    "FALLBACK_DISCLAIMER",
]
