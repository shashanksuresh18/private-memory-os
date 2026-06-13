"""Tests for POST /ingest (drop-a-note -> structured vault page).

All tests are fully offline: the local gemma4-citadel structurer is replaced by
an injected stub (`app.state.ingest_structurer`) and the embedder is patched to
the in-process `HashEmbedder`, so no real Ollama and no real network are
required. S3 locality is asserted with a non-loopback socket sentinel.
"""

from __future__ import annotations

import socket
import sqlite3
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api import server
from src.retrieval.embedder import HashEmbedder
from src.retrieval.index import ingest_vault


def _seed_vault(tmp_path: Path) -> tuple[Path, Path]:
    """A tmp vault with one indexed page so the DB exists and the incremental
    pass has a baseline of existing slugs to skip."""
    vault = tmp_path / "vault"
    (vault / "inbox").mkdir(parents=True)
    (vault / "inbox" / "seed.md").write_text(
        "---\ntier: S1\n---\n\n# Seed\nPublic seed page about EDGAR filings.\n",
        encoding="utf-8",
    )
    db = tmp_path / "retrieval.db"
    ingest_vault(vault, db_path=db)  # HashEmbedder default, reset=True
    return vault, db


@contextmanager
def _forbid_nonloopback():
    """Record + reject any non-loopback socket connect for the duration.

    Nothing in the offline path opens a socket (hash embedder + injected
    structurer), so `seen["nonloopback"]` must stay empty — proving the endpoint
    never reaches out to the cloud.
    """
    seen: dict[str, list[str]] = {"nonloopback": []}
    real_connect = socket.socket.connect
    loopback = {"127.0.0.1", "::1", "localhost"}

    def guard(self, address):
        host = address[0] if isinstance(address, tuple) else str(address)
        if str(host) not in loopback:
            seen["nonloopback"].append(str(host))
            raise AssertionError(f"non-loopback connect attempted: {host}")
        return real_connect(self, address)

    socket.socket.connect = guard
    try:
        yield seen
    finally:
        socket.socket.connect = real_connect


@pytest.fixture
def make_client(tmp_path, monkeypatch):
    """Factory: build a TestClient bound to a fresh tmp vault/db with a given
    structurer stub. Embedder is forced to HashEmbedder (offline)."""
    monkeypatch.setattr(server, "make_embedder", lambda: HashEmbedder())

    def _make(structurer):
        vault, db = _seed_vault(tmp_path)
        server.app.state.db_path = db
        server.app.state.vault_root = vault
        server.app.state.ingest_structurer = structurer
        return TestClient(server.app), vault, db

    yield _make

    for attr in ("db_path", "vault_root", "ingest_structurer"):
        if hasattr(server.app.state, attr):
            delattr(server.app.state, attr)


def _frontmatter(text: str) -> str:
    return text.split("---", 2)[1] if text.startswith("---") else ""


def test_s1_ingest_creates_file(make_client):
    client, vault, _ = make_client(lambda content, doc_type: "## Findings\n\n" + content)

    res = client.post(
        "/ingest",
        json={
            "content": "EDGAR public filing summary for the quarter.",
            "doc_type": "research",
            "tier": "S1",
            "title": "Public filing",
        },
    )

    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "indexed"
    assert body["tier"] == "S1"
    assert body["chunks"] >= 1

    out = vault / "inbox" / body["filename"]
    assert out.exists(), "markdown file must be written to vault/inbox/"
    assert "tier: S1" in _frontmatter(out.read_text(encoding="utf-8"))


def test_s2_ingest_preserves_local_content(make_client):
    marker = "Acme Q3 pipeline discussion, internal only."
    client, vault, _ = make_client(lambda content, doc_type: "## Discussion\n\n" + content)

    with _forbid_nonloopback() as seen:
        res = client.post(
            "/ingest",
            json={"content": marker, "doc_type": "meeting", "tier": "S2", "title": "Acme sync"},
        )

    assert res.status_code == 200
    assert seen["nonloopback"] == [], "S2 ingest must make no cloud call"

    out = vault / "inbox" / res.json()["filename"]
    text = out.read_text(encoding="utf-8")
    assert "tier: S2" in _frontmatter(text)
    # S2 is stored locally as provided/generated (DLP applies only before any
    # FUTURE cloud egress, not before local vault storage).
    assert marker in text


def test_s3_ingest_stays_local(make_client):
    # Mocked local conversion: the structurer stub stands in for gemma4-citadel.
    client, vault, _ = make_client(lambda content, doc_type: "## Summary\n\n" + content)

    with _forbid_nonloopback() as seen:
        res = client.post(
            "/ingest",
            json={
                "content": "Board memo: deal codename Orchid, MNPI, do not distribute.",
                "doc_type": "memo",
                "tier": "S3",
                "title": "Board memo",
            },
        )

    assert res.status_code == 200
    assert seen["nonloopback"] == [], "S3 must never reach a non-loopback address"

    out = vault / "inbox" / res.json()["filename"]
    assert "tier: S3" in _frontmatter(out.read_text(encoding="utf-8"))


def test_ingest_incremental_no_reset(make_client, monkeypatch):
    client, _, db = make_client(lambda content, doc_type: "## Notes\n\n" + content)

    calls: dict[str, object] = {}
    real_ingest = server.ingest_vault

    def spy(*args, **kwargs):
        calls["reset"] = kwargs.get("reset")
        calls["incremental"] = kwargs.get("incremental")
        return real_ingest(*args, **kwargs)

    monkeypatch.setattr(server, "ingest_vault", spy)

    before = sqlite3.connect(str(db)).execute("SELECT COUNT(*) FROM pages").fetchone()[0]

    res = client.post(
        "/ingest",
        json={"content": "A short note.", "doc_type": "memo", "tier": "S1", "title": "Note"},
    )

    assert res.status_code == 200
    assert calls["reset"] is False, "ingest must run incrementally, never reset"
    assert calls["incremental"] is True

    after = sqlite3.connect(str(db)).execute("SELECT COUNT(*) FROM pages").fetchone()[0]
    # Existing DB preserved (not cleared/rebuilt): exactly one page added.
    assert after == before + 1


def test_ingest_no_file_overwrite(make_client):
    client, vault, _ = make_client(lambda content, doc_type: "## Notes\n\n" + content)

    r1 = client.post(
        "/ingest",
        json={"content": "first version content", "doc_type": "memo", "tier": "S1", "title": "Duplicate Title"},
    )
    r2 = client.post(
        "/ingest",
        json={"content": "second version content", "doc_type": "memo", "tier": "S1", "title": "Duplicate Title"},
    )

    assert r1.status_code == 200 and r2.status_code == 200
    f1, f2 = r1.json()["filename"], r2.json()["filename"]

    assert f1 != f2
    assert f2.endswith("_2.md"), "collision must add a _2 suffix"

    # Original is intact, not overwritten by the second ingest.
    assert "first version content" in (vault / "inbox" / f1).read_text(encoding="utf-8")
    assert "second version content" in (vault / "inbox" / f2).read_text(encoding="utf-8")
