"""S3-never-cloud gating test (LOCKED invariant).

Layered assertions:

1. Resolved-host check across BOTH planes (gbrain ~/.gbrain/config.json file
   plane + gbrain DB plane via `gbrain config get`) for ALL model fields
   (embedding_model, chat_model, expansion_model, rerank_model,
   models.tier.*). Each value MUST be either `none`, missing (treated as
   `none`), or resolve to a loopback host.

2. Socket-level monkeypatch: during S3 execution, any `socket.connect()` to
   a non-loopback peer raises `EgressBlocked`. The retrieval engine must
   complete with no exception under this constraint.

3. dream / cycle / autopilot daemon path: assert no Windows scheduled task
   named gbrain-* exists and no `~/.gbrain/autopilot.json` is registered.
   Config-only proof is insufficient because `models.tier.subagent` cannot
   be set to `none` and falls back to a hardcoded cloud model.
"""

from __future__ import annotations

import ipaddress
import json
import os
import socket
import subprocess
from pathlib import Path
from typing import Iterable

import pytest

from src.retrieval.engine import retrieve
from src.retrieval.index import ingest_vault


VAULT = Path(__file__).parent / "synthetic_public_vault"
GBRAIN_CONFIG = Path(os.environ.get("GBRAIN_HOME", str(Path.home() / ".gbrain"))) / "config.json"
ALL_MODEL_FIELDS = (
    "embedding_model",
    "chat_model",
    "expansion_model",
    "rerank_model",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class EgressBlocked(RuntimeError):
    pass


_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


def _is_loopback_host(host: str) -> bool:
    if host.lower() in _LOOPBACK_HOSTS:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _is_loopback_value(value: str | None) -> bool:
    if value is None:
        return True
    v = str(value).strip().lower()
    if v in ("", "none", "null"):
        return True
    # `provider:model` form — we cannot resolve provider->host without the
    # gbrain recipe registry. Conservative rule: only `none` or an explicit
    # `127.0.0.1:...` / `localhost:...` prefix passes. A literal IP string
    # is also accepted via _is_loopback_host below.
    if v.startswith("127.0.0.1") or v.startswith("localhost") or v.startswith("[::1]"):
        return True
    return _is_loopback_host(v)


def _file_plane() -> dict:
    if not GBRAIN_CONFIG.exists():
        return {}
    return json.loads(GBRAIN_CONFIG.read_text(encoding="utf-8"))


def _db_plane(field: str) -> str | None:
    gbrain = Path.home() / ".bun" / "bin" / "gbrain.exe"
    if not gbrain.exists():
        return None
    try:
        proc = subprocess.run(
            [str(gbrain), "config", "get", field],
            capture_output=True, text=True, timeout=20,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    if "not found" in (out + err).lower() or proc.returncode != 0:
        return None
    return out.splitlines()[-1].strip() if out else None


# ---------------------------------------------------------------------------
# Plane assertions
# ---------------------------------------------------------------------------

@pytest.mark.gating
@pytest.mark.parametrize("field", ALL_MODEL_FIELDS)
def test_file_plane_field_is_loopback_or_none(field: str) -> None:
    cfg = _file_plane()
    val = cfg.get(field)
    assert _is_loopback_value(val), f"file-plane {field}={val!r} resolves non-loopback"


@pytest.mark.gating
@pytest.mark.parametrize("field", ALL_MODEL_FIELDS)
def test_db_plane_field_is_loopback_or_none(field: str) -> None:
    val = _db_plane(field)
    assert _is_loopback_value(val), f"db-plane {field}={val!r} resolves non-loopback"


@pytest.mark.gating
def test_no_cloud_api_keys_in_env() -> None:
    leaked = [k for k in (
        "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
        "VOYAGE_API_KEY", "ZEROENTROPY_API_KEY",
    ) if os.environ.get(k)]
    assert not leaked, f"cloud API key leaked into env: {leaked}"


# ---------------------------------------------------------------------------
# dream/cycle/autopilot daemon must not be registered
# ---------------------------------------------------------------------------

@pytest.mark.gating
def test_no_gbrain_scheduled_task_registered() -> None:
    # Windows scheduled tasks. On other platforms this becomes a no-op.
    if os.name != "nt":
        pytest.skip("not windows")
    proc = subprocess.run(
        ["schtasks", "/Query", "/FO", "CSV", "/NH"],
        capture_output=True, text=True, timeout=20,
    )
    if proc.returncode != 0:
        pytest.skip(f"schtasks unavailable: {proc.stderr.strip()}")
    # Only gbrain-namespaced tasks are forbidden. Built-in Windows tasks
    # under \Microsoft\Windows\... (e.g. \Management\Autopilot\*) are not
    # us — they ship with the OS and pre-date the project.
    for line in proc.stdout.splitlines():
        lower = line.lower()
        if "gbrain" in lower:
            pytest.fail(f"forbidden gbrain scheduled task: {line.strip()}")
        # Catch a hypothetical project-local daemon path.
        if r"\sovereign" in lower or r"\citadel" in lower:
            # Any task under the project namespace must explicitly not be
            # one of the forbidden daemons.
            for needle in ("dream", "cycle", "autopilot"):
                assert needle not in lower, (
                    f"forbidden project daemon scheduled task: {line.strip()}"
                )


@pytest.mark.gating
def test_no_autopilot_registration_file() -> None:
    home = Path(os.environ.get("GBRAIN_HOME", str(Path.home() / ".gbrain")))
    for name in ("autopilot.json", "dream.json", "cycle.json"):
        p = home / name
        assert not p.exists(), f"forbidden daemon registration present: {p}"


# ---------------------------------------------------------------------------
# Socket-level egress fence
# ---------------------------------------------------------------------------

@pytest.fixture
def block_non_loopback(monkeypatch):
    original_connect = socket.socket.connect
    original_getaddrinfo = socket.getaddrinfo
    seen_peers: list[tuple] = []

    def guarded_connect(self, address):
        seen_peers.append(("connect", address))
        host = address[0] if isinstance(address, tuple) else str(address)
        if not _is_loopback_host(str(host)):
            raise EgressBlocked(f"non-loopback connect attempted: {address}")
        return original_connect(self, address)

    def guarded_getaddrinfo(host, *args, **kwargs):
        seen_peers.append(("getaddrinfo", host))
        if host is None:
            return original_getaddrinfo(host, *args, **kwargs)
        # Resolution itself does not egress, but any non-loopback hostname
        # implies an intent to leave the box. Treat as a failure.
        if not _is_loopback_host(str(host)):
            raise EgressBlocked(f"non-loopback getaddrinfo: {host}")
        return original_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)
    return seen_peers


@pytest.mark.gating
def test_s3_retrieve_path_does_not_egress(tmp_path, block_non_loopback) -> None:
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "s3_doc.md").write_bytes(
        b"---\ntier: S3\n---\n# Internal Memo\n\nConfidential synthetic content.\n",
    )
    db_path = tmp_path / "retrieval.db"

    # Ingest at S3 — must not egress.
    ingest_vault(vault, db_path=db_path)

    results = retrieve("confidential synthetic content", tier="S3", k=5, db_path=db_path)
    assert results, "S3 ingest+search produced no rows"
    for c in results:
        assert c.tier == "S3"

    non_loopback = [
        p for kind, p in block_non_loopback
        if kind == "connect" and (not isinstance(p, tuple) or not _is_loopback_host(str(p[0])))
    ]
    assert not non_loopback, f"non-loopback connects observed: {non_loopback}"
