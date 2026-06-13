"""S3 rerank path must not egress.

Two cases:

1. DeterministicReranker — pure-Python, structurally no network. Asserted
   under the same socket monkeypatch as test_no_egress_on_s3.

2. CrossEncoderReranker — bge-reranker-base from local HF cache. Loaded
   BEFORE the socket fence (model construction may touch filesystem,
   tokenizer fixtures; we permit that, since the fence is about the actual
   rerank inference path). After the fence is armed, run rerank() and
   assert no non-loopback connect happened.

Both cases use a synthetic S3 vault.
"""

from __future__ import annotations

import ipaddress
import os
import socket
from pathlib import Path

import pytest

from src.retrieval.engine import retrieve
from src.retrieval.index import ingest_vault
from src.retrieval.reranker import (
    CrossEncoderReranker,
    DeterministicReranker,
)


_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


def _is_loopback_host(host: str) -> bool:
    if host.lower() in _LOOPBACK_HOSTS:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class EgressBlocked(RuntimeError):
    pass


@pytest.fixture
def fenced_socket(monkeypatch):
    original_connect = socket.socket.connect
    original_getaddrinfo = socket.getaddrinfo
    seen: list[tuple] = []

    def guarded_connect(self, address):
        seen.append(("connect", address))
        host = address[0] if isinstance(address, tuple) else str(address)
        if not _is_loopback_host(str(host)):
            raise EgressBlocked(f"non-loopback connect: {address}")
        return original_connect(self, address)

    def guarded_getaddrinfo(host, *args, **kwargs):
        seen.append(("getaddrinfo", host))
        if host is not None and not _is_loopback_host(str(host)):
            raise EgressBlocked(f"non-loopback getaddrinfo: {host}")
        return original_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)
    return seen


def _make_s3_vault(root: Path) -> Path:
    vault = root / "vault"
    vault.mkdir()
    pages = {
        "alpha.md": (
            "---\ntier: S3\n---\n"
            "# Alpha\n\nWonderland Capital initiated a position in Acme Corp.\n"
        ),
        "bravo.md": (
            "---\ntier: S3\n---\n"
            "# Bravo\n\nOmega Industries reported synthetic deal metrics last week.\n"
        ),
        "charlie.md": (
            "---\ntier: S3\n---\n"
            "# Charlie\n\nWonderland Capital exited the synthetic Acme Corp trade.\n"
        ),
    }
    for name, body in pages.items():
        (vault / name).write_bytes(body.encode("utf-8"))
    return vault


@pytest.mark.gating
def test_deterministic_rerank_no_egress(tmp_path: Path, fenced_socket) -> None:
    vault = _make_s3_vault(tmp_path)
    db_path = tmp_path / "retrieval.db"
    ingest_vault(vault, db_path=db_path)

    reranker = DeterministicReranker()
    results = retrieve(
        "Wonderland Capital Acme Corp position",
        tier="S3", k=3, db_path=db_path, reranker=reranker, k_in=10,
    )
    assert results, "expected reranked S3 hits"
    for c in results:
        assert c.tier == "S3"

    non_loopback = [
        addr for kind, addr in fenced_socket
        if kind == "connect" and not _is_loopback_host(
            str(addr[0] if isinstance(addr, tuple) else addr)
        )
    ]
    assert not non_loopback, f"non-loopback connects during S3 rerank: {non_loopback}"


@pytest.mark.gating
def test_cross_encoder_rerank_no_egress(tmp_path: Path, monkeypatch) -> None:
    # Load model first (filesystem + tokenizer init), THEN arm the fence.
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    try:
        reranker = CrossEncoderReranker()
    except Exception as e:  # pragma: no cover - environment dependent
        pytest.skip(f"bge-reranker-base unavailable locally: {e}")

    vault = _make_s3_vault(tmp_path)
    db_path = tmp_path / "retrieval.db"
    ingest_vault(vault, db_path=db_path)

    # Arm the fence AFTER model load — model construction may legitimately
    # touch loopback filesystem-bridge sockets on some platforms; the
    # invariant we test is the rerank inference path.
    original_connect = socket.socket.connect
    original_getaddrinfo = socket.getaddrinfo
    seen: list[tuple] = []

    def guarded_connect(self, address):
        seen.append(("connect", address))
        host = address[0] if isinstance(address, tuple) else str(address)
        if not _is_loopback_host(str(host)):
            raise EgressBlocked(f"non-loopback connect: {address}")
        return original_connect(self, address)

    def guarded_getaddrinfo(host, *args, **kwargs):
        seen.append(("getaddrinfo", host))
        if host is not None and not _is_loopback_host(str(host)):
            raise EgressBlocked(f"non-loopback getaddrinfo: {host}")
        return original_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)

    results = retrieve(
        "Wonderland Capital Acme Corp position",
        tier="S3", k=3, db_path=db_path, reranker=reranker, k_in=10,
    )
    assert results, "expected reranked S3 hits"
    for c in results:
        assert c.tier == "S3"

    non_loopback = [
        addr for kind, addr in seen
        if kind == "connect" and not _is_loopback_host(
            str(addr[0] if isinstance(addr, tuple) else addr)
        )
    ]
    assert not non_loopback, f"non-loopback connects during S3 BGE rerank: {non_loopback}"
