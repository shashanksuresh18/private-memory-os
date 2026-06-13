"""Tests for the extraction-only answer layer (src/retrieval/answer.py).

Covers tier resolution, tier-violation guards, S2 local redaction, the S3
zero-egress invariant, deterministic anchor format, hardcoded system prompt,
and the API `answer=` toggle (default off = unchanged behaviour).
"""

from __future__ import annotations

import ipaddress
import re
import shutil
import socket
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.retrieval import answer as ans
from src.retrieval.answer import (
    SYSTEM_PROMPT,
    AnswerResult,
    CitationAnchor,
    CloudProviderUnavailable,
    TierViolationError,
    answer,
    answer_s1,
    answer_s2,
    answer_s3,
    build_context,
    make_anchor,
    redact_pii,
    resolve_answer_tier,
)
from src.retrieval.engine import Citation


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cite(tier: str, text: str = "verbatim source sentence.",
          page_path: str = "vault/memos/x.md",
          line_start: int = 12, line_end: int = 14) -> Citation:
    return Citation(
        chunk_id=1, page_slug="x", page_path=page_path, tier=tier,
        byte_start=0, byte_end=len(text.encode("utf-8")),
        line_start=line_start, line_end=line_end, score=0.5, text=text,
    )


_LOOPBACK = {"127.0.0.1", "::1", "localhost"}


def _is_loopback_host(host: str) -> bool:
    if host.lower() in _LOOPBACK:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


_ANCHOR_RE = re.compile(r"^\[.+:L\d+(?:-\d+)?\]$")


class _FakeNebiusResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {
            "choices": [{
                "message": {
                    "content": "mocked answer text",
                },
            }],
        }


# ---------------------------------------------------------------------------
# Tier resolution
# ---------------------------------------------------------------------------

def test_tier_resolution_most_restrictive():
    assert resolve_answer_tier([_cite("S1"), _cite("S2"), _cite("S3")]) == "S3"
    assert resolve_answer_tier([_cite("S1"), _cite("S2")]) == "S2"
    assert resolve_answer_tier([_cite("S1")]) == "S1"
    assert resolve_answer_tier([]) == "S3"  # fail-closed


# ---------------------------------------------------------------------------
# S1 tier-violation guards
# ---------------------------------------------------------------------------

def test_s1_raises_on_s3_citation():
    with pytest.raises(TierViolationError):
        answer_s1("q", [_cite("S1"), _cite("S3")])


def test_s1_raises_on_s2_citation():
    with pytest.raises(TierViolationError):
        answer_s1("q", [_cite("S2")])


def test_s1_raises_when_no_nebius_key(monkeypatch):
    calls: list[dict] = []

    def fake_post(**kwargs):
        calls.append(kwargs)
        return _FakeNebiusResponse()

    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    monkeypatch.setattr(ans.requests, "post", fake_post)

    with pytest.raises(CloudProviderUnavailable):
        answer_s1("q", [_cite("S1")])

    assert calls == []


def test_s2_raises_on_s3_citation():
    with pytest.raises(TierViolationError):
        answer_s2("q", [_cite("S3")])


# ---------------------------------------------------------------------------
# S3 zero egress
# ---------------------------------------------------------------------------

def test_s3_no_egress(monkeypatch):
    seen: list[tuple] = []
    original_connect = socket.socket.connect
    original_getaddrinfo = socket.getaddrinfo

    def guarded_connect(self, address):
        seen.append(("connect", address))
        host = address[0] if isinstance(address, tuple) else str(address)
        if not _is_loopback_host(str(host)):
            raise RuntimeError(f"non-loopback connect: {address}")
        return original_connect(self, address)

    def guarded_getaddrinfo(host, *args, **kwargs):
        seen.append(("getaddrinfo", host))
        if host is not None and not _is_loopback_host(str(host)):
            raise RuntimeError(f"non-loopback getaddrinfo: {host}")
        return original_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)

    # Ollama may or may not be running; either way must not egress.
    result = answer_s3("what is confidential?", [_cite("S3")])
    assert isinstance(result, AnswerResult)
    assert result.tier == "S3"

    non_loopback = [
        addr for kind, addr in seen
        if kind == "connect" and not _is_loopback_host(
            str(addr[0] if isinstance(addr, tuple) else addr)
        )
    ]
    assert not non_loopback, f"S3 answer egressed: {non_loopback}"


# ---------------------------------------------------------------------------
# S2 redaction
# ---------------------------------------------------------------------------

def test_s2_redaction_strips_pii(monkeypatch):
    sent: dict[str, object] = {}

    def fake_post(url, *, headers, json, timeout):
        sent["url"] = url
        sent["headers"] = headers
        sent["json"] = json
        sent["user"] = json["messages"][1]["content"]
        return _FakeNebiusResponse()

    monkeypatch.setenv("NEBIUS_API_KEY", "test-key")
    monkeypatch.setattr(ans.requests, "post", fake_post)

    original = "John Smith agreed to $2.4B deal at smith@corp.com"
    result = answer_s2("summarise", [_cite("S2", text=original)])

    # Redacted skeleton reached the cloud.
    assert "[PERSON]" in sent["user"]
    assert "[AMOUNT]" in sent["user"]
    assert "[EMAIL]" in sent["user"]
    # Original PII NEVER sent.
    assert "John Smith" not in sent["user"]
    assert "$2.4B" not in sent["user"]
    assert "smith@corp.com" not in sent["user"]

    assert result.redacted is True
    assert result.tier == "S2"
    # Assert the request hit the *configured* Nebius endpoint, not a hardcoded
    # vendor literal — NEBIUS_BASE_URL is environment-driven (.env may point at
    # studio vs tokenfactory), so pinning a literal makes this test env-fragile.
    assert sent["url"] == ans.NEBIUS_BASE_URL.rstrip("/") + "/chat/completions"
    assert sent["json"]["messages"][0]["content"] == SYSTEM_PROMPT

    # Direct redactor check on the exact spec example.
    assert redact_pii(original, entity_terms=[]) == \
        "[PERSON] agreed to [AMOUNT] deal at [EMAIL]"


def test_s2_amount_threshold_keeps_small_amounts():
    # Only amounts > $1M are stripped.
    assert "[AMOUNT]" not in redact_pii("paid $500K fee", entity_terms=[])
    assert redact_pii("paid $2,400,000 fee", entity_terms=[]) == "paid [AMOUNT] fee"


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

def test_answer_routes_correctly(monkeypatch):
    calls: list[str] = []

    def make_fake(tier):
        def _fake(query, citations):
            calls.append(tier)
            return AnswerResult(answer="x", tier=tier, model_used="fake")
        return _fake

    monkeypatch.setattr(ans, "answer_s1", make_fake("S1"))
    monkeypatch.setattr(ans, "answer_s2", make_fake("S2"))
    monkeypatch.setattr(ans, "answer_s3", make_fake("S3"))

    answer("q", [_cite("S3")])
    answer("q", [_cite("S2")])
    answer("q", [_cite("S1")])
    assert calls == ["S3", "S2", "S1"]


# ---------------------------------------------------------------------------
# Refusal-retry: S1 falls back to model knowledge; S2/S3 never do
# ---------------------------------------------------------------------------

_REFUSAL_TEXT = "There is no information in the provided context."


def _patch_extractors(monkeypatch, text: str):
    """Make all three tier extractors return `text` for the resolved tier."""
    def make(tier):
        def _fake(query, citations):
            return AnswerResult(answer=text, tier=tier, model_used="extract")
        return _fake
    monkeypatch.setattr(ans, "answer_s1", make("S1"))
    monkeypatch.setattr(ans, "answer_s2", make("S2"))
    monkeypatch.setattr(ans, "answer_s3", make("S3"))


def _patch_fallback(monkeypatch):
    calls: list[str] = []

    def _fake_fallback(query, model=None):
        calls.append(query)
        return AnswerResult(answer="FALLBACK", tier="S1", model_used="cloud")
    monkeypatch.setattr(ans, "answer_s1_public_fallback", _fake_fallback)
    return calls


def test_s1_refusal_triggers_fallback(monkeypatch):
    _patch_extractors(monkeypatch, _REFUSAL_TEXT)
    calls = _patch_fallback(monkeypatch)

    result = answer("q", [_cite("S1")])

    assert calls == ["q"], "S1 refusal must call the public fallback"
    assert result.answer == "FALLBACK"


def test_s2_refusal_no_fallback(monkeypatch):
    _patch_extractors(monkeypatch, _REFUSAL_TEXT)
    calls = _patch_fallback(monkeypatch)

    result = answer("q", [_cite("S2")])

    assert calls == [], "S2 must NEVER fall back to cloud knowledge"
    assert result.answer == _REFUSAL_TEXT


def test_s3_refusal_no_fallback(monkeypatch):
    _patch_extractors(monkeypatch, _REFUSAL_TEXT)
    calls = _patch_fallback(monkeypatch)

    result = answer("q", [_cite("S3")])

    assert calls == [], "S3 must NEVER fall back to cloud knowledge"
    assert result.answer == _REFUSAL_TEXT


def test_non_refusal_no_fallback(monkeypatch):
    _patch_extractors(monkeypatch, "iPhone net sales were $201 billion. [1]")
    calls = _patch_fallback(monkeypatch)

    result = answer("q", [_cite("S1")])

    assert calls == [], "a real extractive answer must not trigger fallback"
    assert result.answer.startswith("iPhone net sales")


# ---------------------------------------------------------------------------
# Hardcoded system prompt
# ---------------------------------------------------------------------------

def test_system_prompt_hardcoded(monkeypatch):
    seen_prompts: list[str] = []

    def fake_post(url, *, headers, json, timeout):
        seen_prompts.append(json["messages"][0]["content"])
        return _FakeNebiusResponse()

    def fake_ollama(model, system_prompt, user_content):
        seen_prompts.append(system_prompt)
        return "ok"

    monkeypatch.setenv("NEBIUS_API_KEY", "test-key")
    monkeypatch.setattr(ans.requests, "post", fake_post)
    monkeypatch.setattr(ans, "_ollama_chat", fake_ollama)

    answer_s1("q", [_cite("S1")])
    answer_s2("q", [_cite("S2")])
    answer_s3("q", [_cite("S3")])

    assert len(seen_prompts) == 3
    for p in seen_prompts:
        assert p == SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Anchor format
# ---------------------------------------------------------------------------

def test_citation_anchors_format():
    multi = make_anchor(_cite("S1", line_start=12, line_end=14))
    single = make_anchor(_cite("S1", line_start=8, line_end=8))
    assert multi.anchor == "[vault/memos/x.md:L12-14]"
    assert single.anchor == "[vault/memos/x.md:L8]"
    for a in (multi, single):
        assert _ANCHOR_RE.match(a.anchor), a.anchor
        assert isinstance(a, CitationAnchor)

    # Every anchor produced on an answer path matches the format.
    result = answer_s3("q", [_cite("S3", line_start=22, line_end=24),
                             _cite("S3", line_start=5, line_end=5)])
    assert result.anchors
    for a in result.anchors:
        assert _ANCHOR_RE.match(a.anchor), a.anchor


# ---------------------------------------------------------------------------
# Empty citations
# ---------------------------------------------------------------------------

def test_empty_citations_returns_s3():
    # answer([]) fails closed (no cloud). Tier resolver alone maps [] -> S3.
    assert resolve_answer_tier([]) == "S3"
    with pytest.raises(TierViolationError):
        answer("q", [])


# ---------------------------------------------------------------------------
# Build context
# ---------------------------------------------------------------------------

def test_build_context_numbered_blocks():
    ctx = build_context([
        _cite("S1", text="first.", page_path="vault/a.md", line_start=1, line_end=2),
        _cite("S2", text="second.", page_path="vault/b.md", line_start=4, line_end=4),
    ])
    assert "[1] vault/a.md L1-2" in ctx
    assert '"first."' in ctx
    assert "[2] vault/b.md L4" in ctx
    assert '"second."' in ctx


# ---------------------------------------------------------------------------
# API toggle — default off leaves existing behaviour unchanged
# ---------------------------------------------------------------------------

SYNTHETIC_PUBLIC_VAULT = (
    Path(__file__).resolve().parents[1] / "retrieval" / "synthetic_public_vault"
)


@pytest.fixture
def client(tmp_path):
    from src.api import server
    from src.retrieval.index import ingest_vault

    vault = tmp_path / "vault"
    shutil.copytree(SYNTHETIC_PUBLIC_VAULT, vault)
    db_path = tmp_path / "retrieval.db"
    ingest_vault(vault, db_path=db_path)
    server.app.state.db_path = db_path
    with TestClient(server.app) as c:
        yield c
    if hasattr(server.app.state, "db_path"):
        delattr(server.app.state, "db_path")


def test_answer_toggle_off_unchanged(client):
    res = client.post(
        "/retrieve",
        json={"query": "EDGAR public filing workflow", "tier": "S1", "k": 5},
    )
    assert res.status_code == 200
    body = res.json()
    # Existing shape: citations + query_tier, no answer fields.
    assert body["query_tier"] == "S1"
    assert body["citations"]
    assert "answer" not in body
    assert "answer_tier" not in body
    assert "anchors" not in body
