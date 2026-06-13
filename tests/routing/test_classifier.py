"""Sovereign Tier-Classifier — golden corpus + fail-closed + integration suite.

Run unit tests (default — gate 3 is mocked):
    pytest tests/routing/test_classifier.py

Run live integration (hits Ollama on 127.0.0.1:11434):
    pytest -m integration tests/routing/test_classifier.py

Run with coverage:
    pytest --cov=src.routing.classifier --cov-report=term-missing \
        tests/routing/test_classifier.py
"""
from __future__ import annotations

import json

import httpx
import pytest

from src.routing.classifier import main as cm


# ---------- fixtures ----------

@pytest.fixture
def isolated_denylist(tmp_path, monkeypatch):
    """Point the classifier at a fresh, test-controlled denylist tree."""
    d = tmp_path / "denylist"
    d.mkdir()
    (d / "codenames.txt").write_text("\n".join([
        "# test fixture",
        "project orion",
        "atlas acquisition",
    ]) + "\n", encoding="utf-8")
    (d / "tickers.txt").write_text("\n".join([
        "# test fixture",
        "AAPL",
        "XYZ",
    ]) + "\n", encoding="utf-8")
    (d / "markers.txt").write_text("\n".join([
        "# test fixture",
        "mnpi",
        "draft memo",
        "under nda",
    ]) + "\n", encoding="utf-8")
    monkeypatch.setattr(cm, "DENYLIST_DIR", d)
    cm.reload_denylist()
    yield d
    cm.reload_denylist()


@pytest.fixture
def stub_gate3(monkeypatch):
    """Replace gate 3 with a deterministic stub. Set state['return'] per test."""
    state = {"return": "S1"}

    def _stub(_text):
        return state["return"]

    monkeypatch.setattr(cm, "_gate3_local_llm", _stub)
    return state


def _fake_ollama_client(*, status: int = 200, content_obj=None, raise_exc=None):
    """Return a context-manager class that mocks ``httpx.Client``.

    ``content_obj`` is the JSON dict the model's ``message.content`` field
    should encode. If ``raise_exc`` is set, the ``.post`` call raises it.
    """
    class _Resp:
        status_code = status
        text = "" if content_obj is not None else "boom"

        def json(self):
            return {"message": {"content": json.dumps(content_obj) if content_obj is not None else "garbage"}}

    class _Client:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, *a, **k):
            if raise_exc is not None:
                raise raise_exc
            return _Resp()

    return _Client


# ---------- (1) Golden Corpus ----------

@pytest.mark.parametrize(
    ("gate3_return", "text", "expected"),
    [
        ("S1", "What is the WACC formula?", "S1"),
        ("S1", "Email Alice at alice@example.com about the Q4 numbers.", "S2"),
        ("S1", "The Project Orion timeline is accelerating.", "S3"),
        ("S1", "Execute the trade on AAPL.", "S3"),
    ],
    ids=["s1_public", "s2_pii_gate2", "s3_codename_gate2", "s3_ticker_gate2"],
)
def test_golden_corpus(isolated_denylist, stub_gate3, gate3_return, text, expected):
    stub_gate3["return"] = gate3_return
    assert cm.classify_payload(text) == expected


def test_ticker_whole_word_boundary(isolated_denylist, stub_gate3):
    """\\b boundary: 'AAPL' inside 'rainAAPLfall' must NOT match."""
    stub_gate3["return"] = "S1"
    assert cm.classify_payload("Considering AAPL position") == "S3"
    assert cm.classify_payload("rainAAPLfall thoughts") == "S1"


def test_codename_substring_match(isolated_denylist, stub_gate3):
    """Codenames use substring match (case-folded), so 'Project Orion' in any sentence hits."""
    stub_gate3["return"] = "S1"
    assert cm.classify_payload("status update for project orion") == "S3"
    assert cm.classify_payload("STATUS: Project Orion Q3 burn") == "S3"


# ---------- (2) Evidence Tainting (Gate 1) ----------

def test_gate1_short_circuits_without_invoking_gates_2_or_3(isolated_denylist, monkeypatch):
    gate2_called = {"v": False}
    gate3_called = {"v": False}

    def _g2_spy(_t):
        gate2_called["v"] = True
        return None

    def _g3_spy(_t):
        gate3_called["v"] = True
        return "S1"

    monkeypatch.setattr(cm, "_gate2_rules", _g2_spy)
    monkeypatch.setattr(cm, "_gate3_local_llm", _g3_spy)

    r = cm.classify_payload(
        "Summarize this paragraph.",
        context_metadata=["vault/memos/q4_strategy.md"],
    )
    assert r == "S3"
    assert gate2_called["v"] is False, "gate 2 must not be invoked on S3 evidence taint"
    assert gate3_called["v"] is False, "gate 3 must not be invoked on S3 evidence taint"


@pytest.mark.parametrize(
    ("sources", "expected"),
    [
        (["vault/crm/alice.md"], "S3"),
        (["vault/memos/q4.md"], "S3"),
        (["vault/people/x.md"], "S3"),
        (["vault/companies/y.md"], "S3"),
        (["vault/meetings/2026-04.md"], "S3"),
        ([r"C:\Users\u\vault\memos\x.md"], "S3"),
        (["vault/public/news.md"], "S1"),
        ([], "S1"),
    ],
    ids=["crm", "memos", "people", "companies", "meetings", "windows_path", "public_only", "empty_list"],
)
def test_gate1_path_matrix(isolated_denylist, stub_gate3, sources, expected):
    stub_gate3["return"] = "S1"
    assert cm.classify_payload("benign", context_metadata=sources) == expected


def test_gate1_mixed_evidence_any_s3_taints_query(isolated_denylist, stub_gate3):
    stub_gate3["return"] = "S1"
    assert cm.classify_payload(
        "plain",
        context_metadata=["vault/public/news.md", "vault/memos/x.md"],
    ) == "S3"


def test_gate1_ignores_non_strings(isolated_denylist, stub_gate3):
    stub_gate3["return"] = "S1"
    assert cm.classify_payload(
        "plain",
        context_metadata=[None, 42, "vault/crm/x.md", {"oops": True}],
    ) == "S3"


# ---------- (3) Fail-Closed Resiliency ----------

@pytest.mark.parametrize(
    "bad",
    ["", None, "\x00\x01\x02", "   ", 12345, [], {}],
    ids=["empty", "none", "ctrl_only", "whitespace_only", "int", "list", "dict"],
)
def test_anomalous_input_defaults_s3(isolated_denylist, stub_gate3, bad):
    stub_gate3["return"] = "S1"
    assert cm.classify_payload(bad) == "S3"


def test_gate3_timeout_fails_closed(isolated_denylist, monkeypatch):
    monkeypatch.setattr(cm.httpx, "Client",
                        _fake_ollama_client(raise_exc=httpx.TimeoutException("simulated timeout")))
    assert cm.classify_payload("benign question with no patterns") == "S3"


def test_gate3_connect_error_fails_closed(isolated_denylist, monkeypatch):
    monkeypatch.setattr(cm.httpx, "Client",
                        _fake_ollama_client(raise_exc=httpx.ConnectError("refused")))
    assert cm.classify_payload("benign question with no patterns") == "S3"


def test_gate3_http_503_fails_closed(isolated_denylist, monkeypatch):
    monkeypatch.setattr(cm.httpx, "Client", _fake_ollama_client(status=503))
    assert cm.classify_payload("benign question with no patterns") == "S3"


def test_gate3_invalid_json_fails_closed(isolated_denylist, monkeypatch):
    """Model returns content that is not parseable JSON."""
    monkeypatch.setattr(cm.httpx, "Client", _fake_ollama_client(status=200, content_obj=None))
    assert cm.classify_payload("benign question with no patterns") == "S3"


def test_gate3_unknown_tier_value_fails_closed(isolated_denylist, monkeypatch):
    monkeypatch.setattr(cm.httpx, "Client",
                        _fake_ollama_client(content_obj={"tier": "S4", "reasoning": "n/a"}))
    assert cm.classify_payload("benign question with no patterns") == "S3"


def test_gate3_missing_tier_field_fails_closed(isolated_denylist, monkeypatch):
    monkeypatch.setattr(cm.httpx, "Client",
                        _fake_ollama_client(content_obj={"reasoning": "no tier"}))
    assert cm.classify_payload("benign question with no patterns") == "S3"


def test_gate3_returns_lowercase_tier_normalized(isolated_denylist, monkeypatch):
    """Lowercase 'S2' from the model should still normalize correctly."""
    monkeypatch.setattr(cm.httpx, "Client",
                        _fake_ollama_client(content_obj={"tier": "s2", "reasoning": "case test"}))
    assert cm.classify_payload("benign question with no patterns") == "S2"


# ---------- (4) Max-Severity Composition (gate 2 + gate 3) ----------

def test_g2_s2_g3_s1_combined_to_s2(isolated_denylist, stub_gate3):
    """PII alone -> gate 2 says S2; gate 3 says S1; final must be S2 (max severity)."""
    stub_gate3["return"] = "S1"
    assert cm.classify_payload("Email Alice at alice@example.com about it.") == "S2"


def test_g2_s2_g3_s3_combined_to_s3(isolated_denylist, stub_gate3):
    """PII + implicit MNPI: gate 2 says S2, gate 3 says S3, final must be S3."""
    stub_gate3["return"] = "S3"
    assert cm.classify_payload("Email Alice at alice@example.com about it.") == "S3"


def test_g2_none_g3_s2_combined_to_s2(isolated_denylist, stub_gate3):
    """No rule hit, gate 3 says S2 -> final S2."""
    stub_gate3["return"] = "S2"
    assert cm.classify_payload("benign with no patterns") == "S2"


def test_g2_s3_short_circuits_skipping_gate3(isolated_denylist, monkeypatch):
    gate3_called = {"v": False}

    def _g3_spy(_t):
        gate3_called["v"] = True
        return "S1"

    monkeypatch.setattr(cm, "_gate3_local_llm", _g3_spy)
    assert cm.classify_payload("Project Orion update") == "S3"
    assert gate3_called["v"] is False, "gate 3 must not be invoked when gate 2 short-circuits to S3"


# ---------- (5) Live Integration ----------

@pytest.mark.integration
def test_live_ollama_classification():
    """Live hit on Ollama. Skipped if endpoint is unreachable or model missing."""
    try:
        with httpx.Client(timeout=1.0) as c:
            r = c.get(f"{cm.OLLAMA_URL}/api/tags")
            if r.status_code != 200:
                pytest.skip(f"Ollama tags endpoint returned {r.status_code}")
            tags = [t.get("name", "") for t in r.json().get("models", [])]
    except Exception as exc:
        pytest.skip(f"Ollama not reachable on {cm.OLLAMA_URL}: {exc}")

    if not any(cm.CLASSIFIER_MODEL in t for t in tags):
        pytest.skip(f"model {cm.CLASSIFIER_MODEL} not present in Ollama")

    result = cm.classify_payload("What is the formula for weighted average cost of capital?")
    assert result in cm.VALID_TIERS
