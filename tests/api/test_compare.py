"""Compare / Council mode endpoint tests.

Compare is a cloud-only NORMAL chat feature, separate from the retrieval tier
engine. These tests mock every provider transport (no real network) and inject a
tmp history DB via ``app.state.compare_db_path``. They pin:

- the model registry exposes ONLY configured cloud providers
- start requires >= 2 available models
- partial failure: one pane errors, the others keep their output
- a timed-out transport yields a ``timeout`` status (not a hard failure)
- blind mode withholds model identity until reveal / vote
- vote reveals identities and writes a HASH-ONLY history row (no plaintext)
- the prompt is DLP-scrubbed before it reaches the cloud transport
- a synthesis failure surfaces an error WITHOUT erasing the comparison
"""

from __future__ import annotations

import glob
import os

import pytest
import requests
from fastapi.testclient import TestClient

import src.api.compare.providers as providers_mod
import src.retrieval.answer as answer_mod
from src.api import server


@pytest.fixture
def client(tmp_path, monkeypatch):
    """TestClient with only Nebius configured and a fresh tmp history DB.
    Tests opt into Anthropic/OpenAI by setting their keys via ``monkeypatch``."""
    monkeypatch.setenv("NEBIUS_API_KEY", "test-nebius")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    server.app.state.compare_db_path = str(tmp_path / "compare_history.db")
    c = TestClient(server.app)
    yield c, monkeypatch, tmp_path
    if hasattr(server.app.state, "compare_db_path"):
        del server.app.state.compare_db_path


def _nebius_stub(captured: dict | None = None, reply: str = "nebius answer", exc: Exception | None = None):
    def fake(model, user_content, system_prompt=answer_mod.SYSTEM_PROMPT):
        if captured is not None:
            captured["content"] = user_content
            captured["model"] = model
        if exc is not None:
            raise exc
        return reply

    return fake


# --- registry ---------------------------------------------------------------

def test_models_lists_only_configured_providers(client):
    c, monkeypatch, _ = client
    models = c.get("/api/compare/models").json()["models"]
    ids = [m["id"] for m in models]
    # Only Nebius is keyed -> every listed model is a Nebius model; the inert
    # Anthropic / OpenAI seams are absent.
    assert "deepseek-v3.2" in ids
    assert all(m["provider"] == "nebius" for m in models)
    assert "claude-opus-4-8" not in ids and "gpt-4o" not in ids

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic")
    ids2 = [m["id"] for m in c.get("/api/compare/models").json()["models"]]
    assert "deepseek-v3.2" in ids2 and "claude-opus-4-8" in ids2
    assert "gpt-4o" not in ids2  # OpenAI still unset
    for m in c.get("/api/compare/models").json()["models"]:
        assert m["kind"] == "cloud"


# --- start validation -------------------------------------------------------

def test_start_requires_at_least_two_models(client):
    c, _, _ = client
    r = c.post("/api/compare/start", json={"prompt": "hi", "model_ids": ["deepseek-v3.2"], "blind": False})
    assert r.status_code == 400
    assert "2 models" in r.json()["detail"]


def test_start_requires_prompt(client):
    c, _, _ = client
    r = c.post("/api/compare/start", json={"prompt": "  ", "model_ids": ["deepseek-v3.2", "deepseek-v3.2"]})
    assert r.status_code == 400


def test_start_rejects_unconfigured_model(client):
    c, _, _ = client  # anthropic NOT configured
    r = c.post(
        "/api/compare/start",
        json={"prompt": "hi", "model_ids": ["deepseek-v3.2", "claude-opus-4-8"]},
    )
    assert r.status_code == 400
    assert "not available" in r.json()["detail"]


# --- run: partial failure + timeout ----------------------------------------

def test_partial_failure_preserves_successful_outputs(client):
    c, monkeypatch, _ = client
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic")
    monkeypatch.setattr(answer_mod, "_nebius_chat", _nebius_stub(reply="good answer"))

    def boom(model, prompt, system, timeout_s):
        raise RuntimeError("provider exploded")

    monkeypatch.setattr(providers_mod, "_anthropic_chat", boom)

    start = c.post(
        "/api/compare/start",
        json={"prompt": "explain X", "model_ids": ["deepseek-v3.2", "claude-opus-4-8"], "blind": False},
    ).json()

    results = {}
    for pane in start["panes"]:
        res = c.post("/api/compare/run", json={"comp_id": start["comp_id"], "pane_id": pane["pane_id"]}).json()
        results[res["provider"]] = res

    assert results["nebius"]["status"] == "ok"
    assert results["nebius"]["text"] == "good answer"  # success preserved
    assert results["anthropic"]["status"] == "error"
    assert results["anthropic"]["error"]


def test_timeout_produces_timeout_status(client):
    c, monkeypatch, _ = client
    monkeypatch.setattr(answer_mod, "_nebius_chat", _nebius_stub(exc=requests.Timeout("too slow")))
    start = c.post(
        "/api/compare/start",
        json={"prompt": "q", "model_ids": ["deepseek-v3.2", "deepseek-v3.2"], "blind": False},
    ).json()
    res = c.post("/api/compare/run", json={"comp_id": start["comp_id"], "pane_id": start["panes"][0]["pane_id"]}).json()
    assert res["status"] == "timeout"


# --- blind mode + reveal ----------------------------------------------------

def test_blind_hides_names_until_reveal(client):
    c, monkeypatch, _ = client
    monkeypatch.setattr(answer_mod, "_nebius_chat", _nebius_stub(reply="ans"))
    start = c.post(
        "/api/compare/start",
        json={"prompt": "q", "model_ids": ["deepseek-v3.2", "deepseek-v3.2"], "blind": True},
    ).json()

    assert start["blind"] is True
    for pane in start["panes"]:
        assert pane["model_id"] is None
        assert pane["model"] is None
        assert pane["label"].startswith("Model ")

    run = c.post("/api/compare/run", json={"comp_id": start["comp_id"], "pane_id": start["panes"][0]["pane_id"]}).json()
    assert run["status"] == "ok"
    assert run["model_id"] is None  # still blind during generation

    reveal = c.post("/api/compare/reveal", json={"comp_id": start["comp_id"]}).json()
    assert reveal["revealed"] is True
    assert all(p["model_id"] == "deepseek-v3.2" for p in reveal["panes"])


# --- vote reveals + hash-only history ---------------------------------------

def test_vote_reveals_and_writes_hash_only_history(client):
    c, monkeypatch, tmp_path = client
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-anthropic")  # two distinct models
    canary_prompt = "memo for alice@example.com about Project CANARY"
    canary_response = "RESPONSE-CANARY-9988"
    monkeypatch.setattr(answer_mod, "_nebius_chat", _nebius_stub(reply=canary_response))

    start = c.post(
        "/api/compare/start",
        json={"prompt": canary_prompt, "model_ids": ["deepseek-v3.2", "claude-opus-4-8"], "blind": True},
    ).json()
    panes = start["panes"]
    vote = c.post(
        "/api/compare/vote",
        json={
            "comp_id": start["comp_id"],
            "winner": panes[0]["pane_id"],
            "panes": [{"pane_id": p["pane_id"], "text": canary_response, "status": "ready"} for p in panes],
        },
    ).json()

    assert vote["winner_model_id"] in {"deepseek-v3.2", "claude-opus-4-8"}
    assert all(p["model_id"] is not None for p in vote["panes"])  # revealed by vote

    hist = c.get("/api/compare/history").json()
    assert len(hist["history"]) == 1
    board = {row["model_id"]: row for row in hist["scoreboard"]}
    assert board[vote["winner_model_id"]]["wins"] == 1
    loser = "claude-opus-4-8" if vote["winner_model_id"] == "deepseek-v3.2" else "deepseek-v3.2"
    assert board[loser]["losses"] == 1

    # Hash-only: no prompt / response plaintext anywhere on disk.
    blob = b""
    for path in glob.glob(str(tmp_path / "compare_history.db*")):
        with open(path, "rb") as fh:
            blob += fh.read()
    assert canary_response.encode() not in blob
    assert b"alice@example.com" not in blob
    assert b"Project CANARY" not in blob


# --- DLP scrub before egress ------------------------------------------------

def test_prompt_is_dlp_scrubbed_before_cloud(client):
    c, monkeypatch, _ = client
    captured: dict = {}
    monkeypatch.setattr(answer_mod, "_nebius_chat", _nebius_stub(captured=captured))
    start = c.post(
        "/api/compare/start",
        json={"prompt": "reach me at bob@firm.com now", "model_ids": ["deepseek-v3.2", "deepseek-v3.2"]},
    ).json()
    c.post("/api/compare/run", json={"comp_id": start["comp_id"], "pane_id": start["panes"][0]["pane_id"]})
    assert "bob@firm.com" not in captured["content"]
    assert "[EMAIL]" in captured["content"]


# --- synthesis --------------------------------------------------------------

def test_synthesize_success(client):
    c, monkeypatch, _ = client
    monkeypatch.setattr(answer_mod, "_nebius_chat", _nebius_stub(reply="## Consensus\nAll agree."))
    r = c.post(
        "/api/compare/synthesize",
        json={
            "comp_id": "anything",
            "synth_model_id": "deepseek-v3.2",
            "responses": [{"label": "Model A", "text": "answer one"}, {"label": "Model B", "text": "answer two"}],
        },
    )
    assert r.status_code == 200
    assert "Consensus" in r.json()["synthesis"]


def test_synthesis_failure_does_not_erase_comparison(client):
    c, monkeypatch, _ = client
    # Run a pane successfully first.
    monkeypatch.setattr(answer_mod, "_nebius_chat", _nebius_stub(reply="kept answer"))
    start = c.post(
        "/api/compare/start",
        json={"prompt": "q", "model_ids": ["deepseek-v3.2", "deepseek-v3.2"], "blind": False},
    ).json()
    first = c.post("/api/compare/run", json={"comp_id": start["comp_id"], "pane_id": start["panes"][0]["pane_id"]}).json()
    assert first["status"] == "ok"

    # Now synthesis fails.
    monkeypatch.setattr(answer_mod, "_nebius_chat", _nebius_stub(exc=RuntimeError("synth down")))
    r = c.post(
        "/api/compare/synthesize",
        json={"comp_id": start["comp_id"], "synth_model_id": "deepseek-v3.2", "responses": [{"label": "A", "text": "x"}]},
    )
    assert r.status_code == 500
    assert "synthesis failed" in r.json()["detail"].lower()

    # The comparison is intact: the session still resolves and panes still run.
    monkeypatch.setattr(answer_mod, "_nebius_chat", _nebius_stub(reply="still works"))
    second = c.post(
        "/api/compare/run",
        json={"comp_id": start["comp_id"], "pane_id": start["panes"][1]["pane_id"]},
    ).json()
    assert second["status"] == "ok"
    assert second["text"] == "still works"


def test_debate_round_sees_scrubbed_peers(client):
    c, monkeypatch, _ = client
    captured: dict = {}
    monkeypatch.setattr(answer_mod, "_nebius_chat", _nebius_stub(captured=captured, reply="## Agree\nyes"))
    start = c.post(
        "/api/compare/start",
        json={"prompt": "q", "model_ids": ["deepseek-v3.2", "deepseek-v3.2"], "blind": False},
    ).json()
    res = c.post(
        "/api/compare/debate",
        json={
            "comp_id": start["comp_id"],
            "pane_id": start["panes"][0]["pane_id"],
            "round": 2,
            "peers": [{"label": "Model B", "text": "contact me at eve@corp.com about it"}],
        },
    ).json()
    assert res["status"] == "ok"
    assert res["round"] == 2
    # The peer answer is included in the debate context, DLP-scrubbed.
    assert "Model B" in captured["content"]
    assert "eve@corp.com" not in captured["content"]
    assert "[EMAIL]" in captured["content"]


# --- jury (/rank): model-as-judge ------------------------------------------

def _start_two(c, prompt="explain X", blind=False):
    return c.post(
        "/api/compare/start",
        json={"prompt": prompt, "model_ids": ["deepseek-v3.2", "deepseek-v3.2"], "blind": blind},
    ).json()


def test_rank_scores_peers(client):
    c, monkeypatch, _ = client
    monkeypatch.setattr(
        answer_mod,
        "_nebius_chat",
        _nebius_stub(reply='{"scores": [{"label": "Model B", "score": 8, "reason": "clear and correct"}]}'),
    )
    start = _start_two(c)
    juror, peer = start["panes"][0], start["panes"][1]
    res = c.post(
        "/api/compare/rank",
        json={"comp_id": start["comp_id"], "pane_id": juror["pane_id"],
              "peers": [{"pane_id": peer["pane_id"], "text": "the peer answer"}]},
    ).json()
    assert res["status"] == "ok"
    assert res["scores"] == [{"label": "Model B", "score": 8.0, "reason": "clear and correct"}]


def test_rank_resolves_neutral_label_and_scrubs(client):
    """The juror must see the session's neutral label (resolved server-side from
    pane_id, never a client string) and DLP-scrubbed peer text + prompt."""
    c, monkeypatch, _ = client
    captured: dict = {}
    monkeypatch.setattr(
        answer_mod,
        "_nebius_chat",
        _nebius_stub(captured=captured, reply='{"scores": [{"label": "Model A", "score": 7, "reason": "ok"}]}'),
    )
    start = _start_two(c, prompt="reach me at bob@firm.com")
    juror, peer = start["panes"][1], start["panes"][0]  # peer is pane 0 -> "Model A"
    res = c.post(
        "/api/compare/rank",
        json={"comp_id": start["comp_id"], "pane_id": juror["pane_id"],
              "peers": [{"pane_id": peer["pane_id"], "text": "mail eve@corp.com for detail"}]},
    ).json()
    assert res["status"] == "ok"
    assert res["scores"][0]["label"] == "Model A"  # server-resolved neutral label
    # Prompt + peer answer DLP-scrubbed before egress.
    assert "bob@firm.com" not in captured["content"]
    assert "eve@corp.com" not in captured["content"]
    assert "[EMAIL]" in captured["content"]
    assert "Model A" in captured["content"]


def test_rank_partial_failure_yields_error_status(client):
    c, monkeypatch, _ = client
    monkeypatch.setattr(answer_mod, "_nebius_chat", _nebius_stub(exc=RuntimeError("juror down")))
    start = _start_two(c)
    juror, peer = start["panes"][0], start["panes"][1]
    res = c.post(
        "/api/compare/rank",
        json={"comp_id": start["comp_id"], "pane_id": juror["pane_id"],
              "peers": [{"pane_id": peer["pane_id"], "text": "answer"}]},
    ).json()
    assert res["status"] == "error"
    assert res["scores"] == []
    assert res["error"]


def test_rank_unparseable_reply_is_error_not_crash(client):
    c, monkeypatch, _ = client
    monkeypatch.setattr(answer_mod, "_nebius_chat", _nebius_stub(reply="I think they were all pretty good honestly."))
    start = _start_two(c)
    juror, peer = start["panes"][0], start["panes"][1]
    res = c.post(
        "/api/compare/rank",
        json={"comp_id": start["comp_id"], "pane_id": juror["pane_id"],
              "peers": [{"pane_id": peer["pane_id"], "text": "answer"}]},
    ).json()
    assert res["status"] == "error"
    assert res["scores"] == []
    assert "could not parse" in res["error"]


def test_rank_drops_unknown_and_self_labels(client):
    """A juror that scores a label it was not shown (or itself) has those rows
    filtered; fenced JSON is tolerated."""
    c, monkeypatch, _ = client
    reply = (
        "```json\n"
        '{"scores": [{"label": "Model B", "score": 9, "reason": "good"}, '
        '{"label": "Model A", "score": 10, "reason": "self"}, '
        '{"label": "Model Z", "score": 1, "reason": "ghost"}]}\n'
        "```"
    )
    monkeypatch.setattr(answer_mod, "_nebius_chat", _nebius_stub(reply=reply))
    start = _start_two(c)
    juror, peer = start["panes"][0], start["panes"][1]  # juror = Model A, peer = Model B
    res = c.post(
        "/api/compare/rank",
        json={"comp_id": start["comp_id"], "pane_id": juror["pane_id"],
              "peers": [{"pane_id": peer["pane_id"], "text": "answer"}]},
    ).json()
    assert res["status"] == "ok"
    assert [s["label"] for s in res["scores"]] == ["Model B"]  # self + ghost dropped


def test_rank_requires_a_peer(client):
    c, monkeypatch, _ = client
    monkeypatch.setattr(answer_mod, "_nebius_chat", _nebius_stub(reply="{}"))
    start = _start_two(c)
    r = c.post(
        "/api/compare/rank",
        json={"comp_id": start["comp_id"], "pane_id": start["panes"][0]["pane_id"], "peers": []},
    )
    assert r.status_code == 400


def test_existing_health_endpoint_still_works(client):
    c, _, _ = client
    assert c.get("/health").json()["status"] == "ok"
