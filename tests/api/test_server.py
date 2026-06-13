from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api import server
from src.retrieval.index import ingest_vault

SYNTHETIC_PUBLIC_VAULT = Path(__file__).resolve().parents[1] / "retrieval" / "synthetic_public_vault"


@pytest.fixture
def client(tmp_path):
    vault = tmp_path / "vault"
    shutil.copytree(SYNTHETIC_PUBLIC_VAULT, vault)
    db_path = tmp_path / "retrieval.db"
    ingest_vault(vault, db_path=db_path)
    server.app.state.db_path = db_path
    with TestClient(server.app) as c:
        yield c
    if hasattr(server.app.state, "db_path"):
        delattr(server.app.state, "db_path")


def test_health_returns_ok(client):
    res = client.get("/health")

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert body["egress"] == "local-only"
    assert body["cloudAllowed"] is False
    assert body["gbrain"]["embedding_model"] in {"none", "unknown"}
    assert body["gbrain"]["chat_model"] in {"none", "unknown"}


def test_retrieve_s1_returns_citations(client):
    res = client.post(
        "/retrieve",
        json={"query": "EDGAR public filing workflow", "tier": "S1", "k": 5},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["query_tier"] == "S1"
    assert body["citations"]
    assert body["citations"][0]["tier"] == "S1"
    assert "EDGAR" in body["citations"][0]["text"]


def test_auto_tier_resolves_s3(client):
    res = client.post(
        "/retrieve",
        json={"query": "EDGAR public filing workflow", "tier": "Auto", "k": 5},
    )

    assert res.status_code == 200
    assert res.json()["query_tier"] == "S3"


def test_low_score_returns_empty_state(client):
    # A query whose terms appear in no document scores below MIN_SCORE on the
    # coverage gate, so the server returns an empty citation list (HTTP 200).
    res = client.post(
        "/retrieve",
        json={"query": "zxqwv plugh xyzzy nonexistent", "tier": "S1", "k": 5},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["citations"] == []
    assert body["query_tier"] == "S1"


def test_empty_state_message_present(client):
    res = client.post(
        "/retrieve",
        json={"query": "zxqwv plugh xyzzy nonexistent", "tier": "S1", "k": 5},
    )

    body = res.json()
    assert body["citations"] == []
    assert body["message"] == "No relevant documents found in vault"


def test_mock_fallback_only_on_unreachable_server(client):
    # The server never substitutes mock/placeholder data: a no-match query
    # yields a real empty state (with message), and a real match yields only
    # vault-sourced citations. The mock fallback is a client-side concern that
    # fires solely when the fetch itself throws (server unreachable).
    empty = client.post(
        "/retrieve",
        json={"query": "zxqwv plugh xyzzy nonexistent", "tier": "S1", "k": 5},
    ).json()
    assert empty["citations"] == []
    assert "message" in empty

    hit = client.post(
        "/retrieve",
        json={"query": "EDGAR public filing workflow", "tier": "S1", "k": 5},
    ).json()
    assert hit["citations"], "real query must return vault citations"
    # No mock page_path (the dashboard's MOCK_CITATIONS) ever comes from the API.
    mock_markers = ("northstar-semiconductors", "project-orchid", "vertex-credit-call")
    for c in hit["citations"]:
        assert not any(m in c["page_path"] for m in mock_markers)
    assert "message" not in hit


def test_no_0000_bind():
    assert server.SERVER_HOST == "127.0.0.1"
    with pytest.raises(RuntimeError, match="refusing non-loopback bind"):
        server._assert_loopback_bind("0.0.0.0")


def test_cors_blocks_external_origin(client):
    res = client.post(
        "/retrieve",
        headers={"Origin": "https://evil.com"},
        json={"query": "EDGAR public filing workflow", "tier": "S1", "k": 5},
    )

    assert res.status_code == 403
    assert "access-control-allow-origin" not in {
        k.lower(): v for k, v in res.headers.items()
    }
