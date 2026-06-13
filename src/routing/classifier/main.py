"""Sovereign Tier-Classifier — 3-Gate Pipeline.

Public surface
--------------
    classify_payload(text: str, context_metadata: list[str] | None = None) -> str

Returns exactly one of ``"S1"``, ``"S2"``, ``"S3"``. On any failure, ambiguity,
or unknown output, returns ``"S3"`` (fail-closed).

Gates (sequential)
------------------
    1. Evidence taint (RAG poison pill)  — 0ms
       If any path in ``context_metadata`` matches a restricted vault directory
       (vault/crm, vault/memos, vault/people, vault/companies, vault/meetings),
       short-circuit to S3.
    2. Deterministic rule engine          — 0ms
       Case-folded substring/word-boundary match against deny-lists
       (codenames, restricted tickers, MNPI markers) and regex PII patterns.
       S3 short-circuit if a codename, marker, or restricted ticker hits.
       S2 escalation if PII regex hits.
    3. Semantic local LLM                  — ~1-2s
       Forwards text to a local 3B-class model via Ollama with a
       JSON-only sensitivity prompt. Failure -> S3 (fail-closed).

Final tier is the max severity of gate 2 and gate 3 (S3 > S2 > S1).
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
from pathlib import Path
from typing import Iterable

import httpx

DEFAULT_TIER = "S3"
VALID_TIERS = ("S1", "S2", "S3")
_TIER_RANK = {"S1": 1, "S2": 2, "S3": 3}

OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
CLASSIFIER_MODEL = os.environ.get("SOVEREIGN_CLASSIFIER_MODEL", "llama3.2:3b")
CLASSIFIER_TIMEOUT_S = float(os.environ.get("SOVEREIGN_CLASSIFIER_TIMEOUT_S", "3.0"))
MAX_LLM_INPUT_CHARS = int(os.environ.get("SOVEREIGN_CLASSIFIER_MAX_CHARS", "8000"))

DENYLIST_DIR = Path(os.environ.get(
    "SOVEREIGN_CLASSIFIER_DENYLIST_DIR",
    str(Path(__file__).parent / "denylist"),
))

# Gate 1: any context_metadata entry matching this regex taints the whole query.
S3_VAULT_PATTERN = re.compile(
    r"(?:^|[/\\])vault[/\\](?:crm|memos|people|companies|meetings)(?:[/\\]|$)",
    re.IGNORECASE,
)

# Gate 2 PII regex (S2 escalation patterns).
RE_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
RE_PHONE = re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
RE_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
RE_CREDIT_CARD = re.compile(r"\b(?:\d[ -]*?){13,16}\b")
RE_IBAN = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")

LLM_SYSTEM_PROMPT = (
    "You are the Sovereign Citadel data-sensitivity classifier for a "
    "finance professional handling Material Non-Public Information (MNPI).\n"
    "Classify the user-provided text into exactly ONE tier:\n"
    "S1: Public market data, SEC filings, published news, general questions.\n"
    "S2: Sensitive but not non-public — contains PII (names, emails, phones, "
    "internal notes) without MNPI.\n"
    "S3: Material Non-Public Information — undisclosed deal flow, draft memos, "
    "codenames, position sizes, earnings prior to release, insider context.\n"
    "Rules:\n"
    "- Fail closed. If unsure between S2 and S3, return S3.\n"
    "- If unsure between S1 and S2, return S2.\n"
    'Output ONLY valid JSON: {"tier": "S1|S2|S3", "reasoning": "<one short '
    'sentence>"}. No prose, no markdown fences.'
)

log = logging.getLogger("sovereign.classifier")


_DENYLIST_FILES = ("codenames.txt", "tickers.txt", "markers.txt")
_DENYLIST_CACHE: tuple[
    tuple[float, ...],
    tuple[frozenset[str], frozenset[str], frozenset[str]],
] | None = None
_DENYLIST_LOCK = threading.Lock()


def _denylist_mtimes() -> tuple[float, ...]:
    """Tuple of (mtime, size) per file — invalidates cache if any changes."""
    out: list[float] = []
    for name in _DENYLIST_FILES:
        p = DENYLIST_DIR / name
        if p.exists():
            st = p.stat()
            out.append(st.st_mtime)
            out.append(float(st.st_size))
        else:
            out.append(0.0)
            out.append(0.0)
    return tuple(out)


def _read_terms(path: Path) -> frozenset[str]:
    if not path.exists():
        return frozenset()
    out: set[str] = set()
    for ln in path.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        out.add(ln.casefold())
    return frozenset(out)


def _load_denylist() -> tuple[frozenset[str], frozenset[str], frozenset[str]]:
    """Return (codenames, tickers, markers). Auto-invalidates on file mtime/size change.

    The mtime-aware cache means atomic writes by the admin CLI propagate to the
    next classifier call without any explicit reload step.
    """
    global _DENYLIST_CACHE
    current_key = _denylist_mtimes()
    cached = _DENYLIST_CACHE
    if cached is not None and cached[0] == current_key:
        return cached[1]
    with _DENYLIST_LOCK:
        cached = _DENYLIST_CACHE
        if cached is not None and cached[0] == current_key:
            return cached[1]
        triple = (
            _read_terms(DENYLIST_DIR / "codenames.txt"),
            _read_terms(DENYLIST_DIR / "tickers.txt"),
            _read_terms(DENYLIST_DIR / "markers.txt"),
        )
        _DENYLIST_CACHE = (current_key, triple)
        log.info("denylist reloaded: %d codenames, %d tickers, %d markers",
                 len(triple[0]), len(triple[1]), len(triple[2]))
        return triple


def reload_denylist() -> None:
    """Force the next classify call to re-read disk regardless of mtime.

    Useful for tests and explicit admin signal paths. Mtime-aware caching
    handles routine edits transparently.
    """
    global _DENYLIST_CACHE
    with _DENYLIST_LOCK:
        _DENYLIST_CACHE = None


# ---------- Gate 1 ----------

def _gate1_evidence_taint(context_metadata: Iterable[str] | None) -> str | None:
    """Return ``"S3"`` if any source path matches the restricted vault dirs."""
    if not context_metadata:
        return None
    for src in context_metadata:
        if not isinstance(src, str):
            continue
        if S3_VAULT_PATTERN.search(src):
            log.info("gate1: S3 evidence taint from source=%s", src)
            return "S3"
    return None


# ---------- Gate 2 ----------

def _gate2_rules(text: str) -> str | None:
    """Return ``"S3"`` for codename/marker/ticker hits, ``"S2"`` for PII, else None."""
    codenames, tickers, markers = _load_denylist()
    folded = text.casefold()

    for term in codenames | markers:
        if term in folded:
            log.info("gate2: S3 codename/marker hit -> %r", term)
            return "S3"
    for tkr in tickers:
        if re.search(rf"\b{re.escape(tkr)}\b", folded):
            log.info("gate2: S3 restricted ticker hit -> %r", tkr)
            return "S3"

    for name, pat in (
        ("ssn", RE_SSN),
        ("phone", RE_PHONE),
        ("email", RE_EMAIL),
        ("credit_card", RE_CREDIT_CARD),
        ("iban", RE_IBAN),
    ):
        if pat.search(text):
            log.info("gate2: S2 PII pattern hit -> %s", name)
            return "S2"

    return None


# ---------- Gate 3 ----------

def _gate3_local_llm(text: str) -> str:
    """Send ``text`` to the local Ollama 3B model. Fail-closed to S3."""
    truncated = text[:MAX_LLM_INPUT_CHARS]
    payload = {
        "model": CLASSIFIER_MODEL,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.0, "num_predict": 256},
        "messages": [
            {"role": "system", "content": LLM_SYSTEM_PROMPT},
            {"role": "user", "content": truncated},
        ],
    }

    try:
        with httpx.Client(timeout=CLASSIFIER_TIMEOUT_S) as client:
            r = client.post(f"{OLLAMA_URL}/api/chat", json=payload)
    except Exception as exc:
        log.error("gate3 fail-closed: transport error (%s: %s)",
                  type(exc).__name__, exc)
        return DEFAULT_TIER

    if r.status_code != 200:
        log.error("gate3 fail-closed: ollama returned %d (%s)",
                  r.status_code, r.text[:200])
        return DEFAULT_TIER

    try:
        body = r.json()
        raw_content = ((body.get("message") or {}).get("content") or "").strip()
        parsed = json.loads(raw_content)
        tier = str(parsed.get("tier", "")).strip().upper()
        reasoning = str(parsed.get("reasoning", ""))[:200]
    except Exception as exc:
        log.error("gate3 fail-closed: invalid JSON from local LLM (%s: %s)",
                  type(exc).__name__, exc)
        return DEFAULT_TIER

    if tier not in VALID_TIERS:
        log.warning("gate3 fail-closed: unrecognized tier %r", tier)
        return DEFAULT_TIER

    log.info("gate3: %s (%s)", tier, reasoning)
    return tier


# ---------- public API ----------

def classify_payload(
    text: str,
    context_metadata: list[str] | None = None,
) -> str:
    """Classify a payload into S1, S2, or S3.

    Args:
        text: Raw user prompt or message content to be classified.
        context_metadata: Optional list of source identifiers attached to a
            RAG query (file paths, URLs, vault tags). If any entry matches a
            restricted vault directory, the entire query becomes S3.

    Returns:
        Exactly one of ``"S1"``, ``"S2"``, or ``"S3"``. ``"S3"`` is the
        fail-closed default for any unexpected input or runtime failure.
    """
    if not isinstance(text, str) or not text:
        log.warning("classifier: non-string or empty text -> %s", DEFAULT_TIER)
        return DEFAULT_TIER
    if not text.strip():
        log.warning("classifier: whitespace-only text -> %s", DEFAULT_TIER)
        return DEFAULT_TIER
    if not any(ch.isprintable() or ch == "\n" for ch in text):
        log.warning("classifier: no printable content -> %s", DEFAULT_TIER)
        return DEFAULT_TIER

    if _gate1_evidence_taint(context_metadata) == "S3":
        return "S3"

    g2 = _gate2_rules(text)
    if g2 == "S3":
        return "S3"

    g3 = _gate3_local_llm(text)
    if g3 == "S3":
        return "S3"

    candidates = [t for t in (g2 or "S1", g3) if t in VALID_TIERS]
    if not candidates:
        return DEFAULT_TIER
    return max(candidates, key=_TIER_RANK.__getitem__)


__all__ = ["classify_payload", "reload_denylist", "DEFAULT_TIER", "VALID_TIERS"]
