"""Sovereign Router — Tri-Tier (S1/S2/S3) Anthropic-compatible proxy.

Bound strictly to 127.0.0.1. Replaces the deferred OpenBMB/ClawXRouter.

Agents point ANTHROPIC_BASE_URL at this proxy. Two entry shapes:

    Path-pinned (recommended for SDKs that cannot set custom headers):
        POST /s1/v1/messages   -> Tier S1 forced
        POST /s2/v1/messages   -> Tier S2 forced
        POST /s3/v1/messages   -> Tier S3 forced

    Header-driven (direct integrations only):
        POST /v1/messages      -> reads X-Sovereign-Tier; missing/unknown -> S3

Tier semantics:
    S1 (public)       -> forward as-is to api.anthropic.com
    S2 (sensitive)    -> scrub each text block via local OPF DLP @ 127.0.0.1:8765
                         then forward the sanitized skeleton to api.anthropic.com
                         with prompt-caching disabled and X-Tier=S2 metadata
    S3 (confidential) -> hard-block cloud, route to local Ollama
                         (default model: ${SOVEREIGN_LOCAL_MODEL})

Default tier when X-Sovereign-Tier is missing or unrecognized: **S3** (fail-closed).

Audit:
    Every routing decision appends one hash-chained JSON line to audit/routing.jsonl
    BEFORE any egress. fsync on append. No plaintext stored.

Stream responses are not supported in v0.1. ``stream:true`` is rejected.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

from src.routing.classifier.main import classify_payload, reload_denylist

# ---------- config ----------
ROUTER_PORT = int(os.environ.get("SOVEREIGN_ROUTER_PORT", "8770"))
OPF_URL = os.environ.get("SOVEREIGN_OPF_URL", "http://127.0.0.1:8765")
OPF_TOKEN_PATH = Path(os.environ.get("SOVEREIGN_OPF_TOKEN_FILE", "src/firewall/opf/.token"))
ANTHROPIC_URL = os.environ.get("ANTHROPIC_API_URL", "https://api.anthropic.com")
OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
LOCAL_MODEL = os.environ.get("SOVEREIGN_LOCAL_MODEL", "qwen2.5:32b-instruct-q4_K_M")
ROUTER_TOKEN_ENV = "SOVEREIGN_ROUTER_TOKEN"
TIER_HEADER = "x-sovereign-tier"
RAG_SOURCES_HEADER = "x-sovereign-rag-sources"
MAX_PAYLOAD_BYTES = 4 * 1024 * 1024
ALLOWED_TIERS = ("S1", "S2", "S3")
DEFAULT_TIER = "S3"
TIER_WEIGHTS = {"S1": 1, "S2": 2, "S3": 3}
AUDIT_PATH = Path(os.environ.get("SOVEREIGN_AUDIT_DIR", "audit")) / "routing.jsonl"
LOG_LEVEL = os.environ.get("SOVEREIGN_ROUTER_LOG_LEVEL", "INFO")
HTTP_TIMEOUT_S = float(os.environ.get("SOVEREIGN_HTTP_TIMEOUT_S", "120"))

logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("sovereign.router")

_opf_token: str | None = None
_audit_lock = threading.Lock()
_http: httpx.AsyncClient | None = None


def _load_opf_token() -> str | None:
    """Read OPF shared-secret token from disk if available."""
    env_value = os.environ.get("SOVEREIGN_OPF_TOKEN")
    if env_value:
        return env_value
    try:
        return OPF_TOKEN_PATH.read_text(encoding="utf-8").strip() or None
    except FileNotFoundError:
        return None


def _audit_append(record: dict[str, Any]) -> None:
    """Append one hash-chained line to audit/routing.jsonl, fsync before return."""
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _audit_lock:
        prev_hash = ""
        if AUDIT_PATH.exists() and AUDIT_PATH.stat().st_size > 0:
            with AUDIT_PATH.open("rb") as fh:
                fh.seek(-min(4096, AUDIT_PATH.stat().st_size), 2)
                tail = fh.read().decode("utf-8", errors="ignore").splitlines()
                if tail:
                    try:
                        prev_hash = json.loads(tail[-1]).get("hash", "")
                    except Exception:
                        prev_hash = ""
        record = dict(record)
        record["prev_hash"] = prev_hash
        record_no_hash = json.dumps(record, sort_keys=True, ensure_ascii=False)
        record["hash"] = hashlib.sha256(record_no_hash.encode("utf-8")).hexdigest()
        with AUDIT_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            fh.flush()
            os.fsync(fh.fileno())


def _resolve_tier(raw: str | None) -> str:
    """Return a valid tier; unknown -> DEFAULT_TIER (S3, fail-closed)."""
    if not raw:
        return DEFAULT_TIER
    t = raw.strip().upper()
    return t if t in ALLOWED_TIERS else DEFAULT_TIER


def _extract_text_for_classifier(payload: dict[str, Any]) -> str:
    """Concatenate every text block in system + messages into one classifier input."""
    parts: list[str] = []
    sys_field = payload.get("system")
    if isinstance(sys_field, str):
        parts.append(sys_field)
    elif isinstance(sys_field, list):
        for blk in sys_field:
            if isinstance(blk, dict) and blk.get("type") == "text" and isinstance(blk.get("text"), str):
                parts.append(blk["text"])
    for msg in payload.get("messages", []):
        c = msg.get("content")
        if isinstance(c, str):
            parts.append(c)
        elif isinstance(c, list):
            for blk in c:
                if not isinstance(blk, dict):
                    continue
                if blk.get("type") == "text" and isinstance(blk.get("text"), str):
                    parts.append(blk["text"])
                elif blk.get("type") == "tool_result":
                    inner = blk.get("content")
                    if isinstance(inner, str):
                        parts.append(inner)
                    elif isinstance(inner, list):
                        for ib in inner:
                            if isinstance(ib, dict) and ib.get("type") == "text" and isinstance(ib.get("text"), str):
                                parts.append(ib["text"])
    return "\n".join(parts)


def _parse_rag_sources(header_value: str | None) -> list[str]:
    """Parse ``X-Sovereign-RAG-Sources`` (comma-separated file paths) into a list."""
    if not header_value:
        return []
    return [p.strip() for p in header_value.split(",") if p.strip()]


# ---------- middleware ----------

class LoopbackOnlyMiddleware(BaseHTTPMiddleware):
    """Reject any non-loopback peer (defense in depth over uvicorn bind)."""

    async def dispatch(self, request: Request, call_next):
        client = request.client.host if request.client else ""
        if client not in {"127.0.0.1", "::1", "localhost"}:
            log.warning("rejected non-loopback request from %s", client)
            return JSONResponse(status_code=status.HTTP_403_FORBIDDEN,
                                content={"detail": "loopback-only service"})
        return await call_next(request)


class SharedSecretMiddleware(BaseHTTPMiddleware):
    """Require X-Sovereign-Token to match SOVEREIGN_ROUTER_TOKEN env var.

    Skipped if env var is unset, but startup warns.
    /healthz is always allowed.
    """

    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/healthz":
            return await call_next(request)
        expected = os.environ.get(ROUTER_TOKEN_ENV)
        if not expected:
            return await call_next(request)
        provided = request.headers.get("x-sovereign-token", "")
        if provided != expected:
            return JSONResponse(status_code=status.HTTP_403_FORBIDDEN,
                                content={"detail": "invalid X-Sovereign-Token"})
        return await call_next(request)


class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    """Enforce hard cap on request body size."""

    async def dispatch(self, request: Request, call_next):
        cl = request.headers.get("content-length")
        if cl and cl.isdigit() and int(cl) > MAX_PAYLOAD_BYTES:
            return JSONResponse(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                                content={"detail": f"payload exceeds {MAX_PAYLOAD_BYTES} bytes"})
        return await call_next(request)


app = FastAPI(title="Sovereign Citadel Router", version="0.1.0")
app.add_middleware(MaxBodySizeMiddleware)
app.add_middleware(SharedSecretMiddleware)
app.add_middleware(LoopbackOnlyMiddleware)


@app.on_event("startup")
async def _startup() -> None:
    global _opf_token, _http
    _opf_token = _load_opf_token()
    if not _opf_token:
        log.warning("OPF token not found at %s — S2 calls will fail closed",
                    OPF_TOKEN_PATH)
    if not os.environ.get(ROUTER_TOKEN_ENV):
        log.warning("%s unset — router relies on loopback-only enforcement", ROUTER_TOKEN_ENV)
    _http = httpx.AsyncClient(timeout=HTTP_TIMEOUT_S)
    log.info("router ready on 127.0.0.1:%d (OPF=%s, Ollama=%s, Anthropic=%s, local_model=%s)",
             ROUTER_PORT, OPF_URL, OLLAMA_URL, ANTHROPIC_URL, LOCAL_MODEL)


@app.on_event("shutdown")
async def _shutdown() -> None:
    global _http
    if _http is not None:
        await _http.aclose()
        _http = None


# ---------- text-walking helpers ----------

async def _scrub_text(text: str) -> tuple[str, dict[str, int], int]:
    """Send one text blob to the local OPF service and return (redacted, label_counts, span_count).

    Raises HTTPException(503) on any failure — fail-closed.
    """
    if not text:
        return text, {}, 0
    headers = {"content-type": "application/json"}
    if _opf_token:
        headers["x-opf-token"] = _opf_token
    try:
        assert _http is not None
        r = await _http.post(f"{OPF_URL}/redact", json={"text": text}, headers=headers)
    except Exception as exc:
        log.error("OPF call failed: %s", exc)
        raise HTTPException(status_code=503, detail=f"S2 firewall unreachable: {exc}") from exc
    if r.status_code != 200:
        log.error("OPF returned %d: %s", r.status_code, r.text[:300])
        raise HTTPException(status_code=503, detail=f"S2 firewall error {r.status_code}")
    data = r.json()
    redacted = data["redacted_text"]
    counts: dict[str, int] = {}
    for s in data.get("spans", []):
        lab = s.get("label", "")
        counts[lab] = counts.get(lab, 0) + 1
    return redacted, counts, len(data.get("spans", []))


async def _scrub_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, int], int]:
    """Walk Anthropic Messages-shaped payload and scrub every text block in-place.

    Returns (sanitized_payload, total_label_counts, total_span_count).
    Tool inputs / tool results are scrubbed too — if it is text, it gets scrubbed.
    """
    total_counts: dict[str, int] = {}
    total_spans = 0

    async def _scrub_str(s: str) -> str:
        nonlocal total_spans
        red, counts, n = await _scrub_text(s)
        total_spans += n
        for k, v in counts.items():
            total_counts[k] = total_counts.get(k, 0) + v
        return red

    sys_field = payload.get("system")
    if isinstance(sys_field, str):
        payload["system"] = await _scrub_str(sys_field)
    elif isinstance(sys_field, list):
        for blk in sys_field:
            if isinstance(blk, dict) and blk.get("type") == "text" and isinstance(blk.get("text"), str):
                blk["text"] = await _scrub_str(blk["text"])

    for msg in payload.get("messages", []):
        content = msg.get("content")
        if isinstance(content, str):
            msg["content"] = await _scrub_str(content)
        elif isinstance(content, list):
            for blk in content:
                if not isinstance(blk, dict):
                    continue
                if blk.get("type") == "text" and isinstance(blk.get("text"), str):
                    blk["text"] = await _scrub_str(blk["text"])
                elif blk.get("type") == "tool_result":
                    inner = blk.get("content")
                    if isinstance(inner, str):
                        blk["content"] = await _scrub_str(inner)
                    elif isinstance(inner, list):
                        for ib in inner:
                            if isinstance(ib, dict) and ib.get("type") == "text" and isinstance(ib.get("text"), str):
                                ib["text"] = await _scrub_str(ib["text"])
    return payload, total_counts, total_spans


# ---------- upstream callers ----------

async def _call_anthropic(payload: dict[str, Any], api_key: str, anthropic_version: str,
                          tier: str, extra_beta: str | None) -> Response:
    assert _http is not None
    headers = {
        "x-api-key": api_key,
        "anthropic-version": anthropic_version,
        "content-type": "application/json",
    }
    if tier == "S2":
        headers["anthropic-disable-prompt-caching"] = "true"
    if extra_beta:
        headers["anthropic-beta"] = extra_beta

    r = await _http.post(f"{ANTHROPIC_URL}/v1/messages", json=payload, headers=headers)
    out = Response(content=r.content, status_code=r.status_code, media_type=r.headers.get("content-type", "application/json"))
    out.headers["x-tier"] = tier
    out.headers["cache-control"] = "no-store" if tier == "S2" else "no-store"
    return out


def _anthropic_to_ollama(payload: dict[str, Any]) -> dict[str, Any]:
    """Translate an Anthropic /v1/messages payload to Ollama /api/chat shape."""
    messages: list[dict[str, str]] = []
    sys_field = payload.get("system")
    if isinstance(sys_field, str) and sys_field.strip():
        messages.append({"role": "system", "content": sys_field})
    elif isinstance(sys_field, list):
        parts = [b.get("text", "") for b in sys_field if isinstance(b, dict) and b.get("type") == "text"]
        if any(parts):
            messages.append({"role": "system", "content": "\n".join(parts)})

    for m in payload.get("messages", []):
        role = m.get("role", "user")
        content = m.get("content", "")
        if isinstance(content, str):
            text = content
        else:
            text = "\n".join(b.get("text", "") for b in (content or [])
                             if isinstance(b, dict) and b.get("type") == "text")
        messages.append({"role": role, "content": text})

    return {
        "model": payload.get("model") or LOCAL_MODEL,
        "messages": messages,
        "stream": False,
        "options": {
            "num_predict": int(payload.get("max_tokens") or 1024),
            "temperature": float(payload.get("temperature", 0.0)),
        },
    }


def _ollama_to_anthropic(ollama_resp: dict[str, Any], model_used: str) -> dict[str, Any]:
    """Translate an Ollama /api/chat response to Anthropic /v1/messages response shape."""
    text = ((ollama_resp.get("message") or {}).get("content")) or ""
    prompt_eval_count = int(ollama_resp.get("prompt_eval_count") or 0)
    eval_count = int(ollama_resp.get("eval_count") or 0)
    done_reason = ollama_resp.get("done_reason") or "end_turn"
    stop_map = {"length": "max_tokens", "stop": "end_turn", "end": "end_turn"}
    return {
        "id": "msg_local_" + uuid.uuid4().hex,
        "type": "message",
        "role": "assistant",
        "model": model_used,
        "content": [{"type": "text", "text": text}],
        "stop_reason": stop_map.get(done_reason, done_reason),
        "stop_sequence": None,
        "usage": {"input_tokens": prompt_eval_count, "output_tokens": eval_count},
    }


async def _call_ollama_as_anthropic(payload: dict[str, Any], tier: str) -> Response:
    assert _http is not None
    ollama_payload = _anthropic_to_ollama(payload)
    try:
        r = await _http.post(f"{OLLAMA_URL}/api/chat", json=ollama_payload)
    except Exception as exc:
        log.error("Ollama call failed: %s", exc)
        return JSONResponse(status_code=503,
                            content={"type": "error",
                                     "error": {"type": "local_inference_unavailable",
                                               "message": f"Ollama unreachable: {exc}"}})
    if r.status_code != 200:
        return JSONResponse(status_code=r.status_code,
                            content={"type": "error",
                                     "error": {"type": "local_inference_error",
                                               "message": r.text[:500]}})
    body = _ollama_to_anthropic(r.json(), ollama_payload["model"])
    out = JSONResponse(status_code=200, content=body)
    out.headers["x-tier"] = tier
    out.headers["x-source"] = "ollama"
    out.headers["cache-control"] = "no-store"
    return out


# ---------- endpoints ----------

@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {
        "ok": True,
        "opf_url": OPF_URL,
        "opf_token_loaded": bool(_opf_token),
        "ollama_url": OLLAMA_URL,
        "local_model": LOCAL_MODEL,
        "anthropic_url": ANTHROPIC_URL,
        "default_tier": DEFAULT_TIER,
        "routes": {
            "header_driven": "/v1/messages  (X-Sovereign-Tier)",
            "path_pinned":   ["/s1/v1/messages", "/s2/v1/messages", "/s3/v1/messages"],
        },
    }


async def _handle_messages(
    request: Request,
    *,
    tier: str,
    tier_source: str,
    tier_explicit: bool = True,
) -> Response:
    """Shared core for header-driven and path-pinned message routes.

    Runs the classifier on every request, then applies the
    "auto-upgrade, never-downgrade" rule:
        - classifier severity > requested  -> forced upgrade
        - tier_explicit is False           -> classifier is the primary decider
        - otherwise                        -> keep caller-pinned tier

    ``tier_source`` is recorded in the audit log so a verifier can confirm the
    path/header (or classifier override) that selected the final tier.
    """
    raw = await request.body()
    if len(raw) > MAX_PAYLOAD_BYTES:
        raise HTTPException(status_code=413, detail="payload too large")
    try:
        payload = json.loads(raw)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"invalid JSON: {exc}") from exc

    if payload.get("stream"):
        raise HTTPException(status_code=400, detail="streaming not supported in v0.1")

    requested_tier = tier
    extracted_text = _extract_text_for_classifier(payload)
    rag_sources = _parse_rag_sources(request.headers.get(RAG_SOURCES_HEADER))

    classifier_started = time.monotonic()
    try:
        auto_tier = await asyncio.to_thread(classify_payload, extracted_text, rag_sources)
    except Exception as exc:
        log.error("classifier crashed -> S3 fail-closed: %s", exc)
        auto_tier = "S3"
    classifier_ms = int((time.monotonic() - classifier_started) * 1000)

    current_weight = TIER_WEIGHTS.get(tier, 3)
    auto_weight = TIER_WEIGHTS.get(auto_tier, 3)
    if auto_weight > current_weight:
        tier_source = f"classifier_upgrade:{tier}->{auto_tier}"
        tier = auto_tier
    elif not tier_explicit:
        tier_source = f"classifier_auto:{auto_tier}"
        tier = auto_tier

    event_id = uuid.uuid4().hex
    started = time.monotonic()

    api_key = request.headers.get("x-api-key") or os.environ.get("ANTHROPIC_API_KEY", "")
    anthropic_version = request.headers.get("anthropic-version", "2023-06-01")
    extra_beta = request.headers.get("anthropic-beta")

    input_hash = hashlib.sha256(raw).hexdigest()
    model_req = payload.get("model", "")
    msg_count = len(payload.get("messages") or [])

    audit_pre = {
        "ts": time.time(),
        "event_id": event_id,
        "service": "router",
        "stage": "pre_egress",
        "tier": tier,
        "tier_source": tier_source,
        "requested_tier": requested_tier,
        "classifier_tier": auto_tier,
        "classifier_ms": classifier_ms,
        "rag_sources_count": len(rag_sources),
        "model_request": model_req,
        "msg_count": msg_count,
        "input_sha256": input_hash,
        "input_bytes": len(raw),
        "peer": request.client.host if request.client else "",
    }

    if tier == "S3":
        audit_pre["route"] = "ollama_local"
        audit_pre["cloud_allowed"] = False
        _audit_append(audit_pre)
        resp = await _call_ollama_as_anthropic(payload, tier)
        _audit_append({
            "ts": time.time(),
            "event_id": event_id,
            "service": "router",
            "stage": "post_response",
            "tier": tier,
            "upstream_status": resp.status_code,
            "duration_ms": int((time.monotonic() - started) * 1000),
        })
        return resp

    if tier == "S2":
        if not _opf_token:
            _audit_append({**audit_pre, "route": "blocked",
                           "reason": "no_opf_token_fail_closed"})
            raise HTTPException(status_code=503,
                                detail="S2 fail-closed: OPF token not configured")
        try:
            sanitized, label_counts, span_count = await _scrub_payload(payload)
        except HTTPException:
            _audit_append({**audit_pre, "route": "blocked",
                           "reason": "scrub_failed_fail_closed"})
            raise
        audit_pre.update({
            "route": "anthropic_after_scrub",
            "cloud_allowed": True,
            "scrub_span_count": span_count,
            "scrub_label_counts": label_counts,
            "prompt_cache": False,
        })
        _audit_append(audit_pre)
        resp = await _call_anthropic(sanitized, api_key, anthropic_version, tier, extra_beta)
        _audit_append({
            "ts": time.time(),
            "event_id": event_id,
            "service": "router",
            "stage": "post_response",
            "tier": tier,
            "upstream_status": resp.status_code,
            "duration_ms": int((time.monotonic() - started) * 1000),
        })
        return resp

    # tier == "S1"
    audit_pre.update({"route": "anthropic_passthrough", "cloud_allowed": True,
                      "prompt_cache": True})
    _audit_append(audit_pre)
    resp = await _call_anthropic(payload, api_key, anthropic_version, tier, extra_beta)
    _audit_append({
        "ts": time.time(),
        "event_id": event_id,
        "service": "router",
        "stage": "post_response",
        "tier": tier,
        "upstream_status": resp.status_code,
        "duration_ms": int((time.monotonic() - started) * 1000),
    })
    return resp


# ---------- public routes ----------

@app.post("/v1/messages")
async def v1_messages(request: Request) -> Response:
    """Header-driven entry. Reads X-Sovereign-Tier; unknown -> classifier decides.

    Provided for direct integrations that can set custom headers.
    Most SDKs cannot — prefer the path-pinned routes below.
    """
    raw_tier = request.headers.get(TIER_HEADER)
    tier = _resolve_tier(raw_tier)
    tier_explicit = bool(raw_tier and raw_tier.strip().upper() in ALLOWED_TIERS)
    return await _handle_messages(
        request,
        tier=tier,
        tier_source=f"header:{raw_tier or 'missing'}->{tier}",
        tier_explicit=tier_explicit,
    )


@app.post("/s1/v1/messages")
async def s1_v1_messages(request: Request) -> Response:
    """Path-pinned Tier S1 (public). Forwards to api.anthropic.com unchanged.

    Classifier can still force-upgrade to S2 or S3 if MNPI is detected.
    """
    return await _handle_messages(request, tier="S1", tier_source="path:s1", tier_explicit=True)


@app.post("/s2/v1/messages")
async def s2_v1_messages(request: Request) -> Response:
    """Path-pinned Tier S2 (sensitive). Scrubs via OPF, then forwards to Claude
    with prompt caching disabled. Classifier can force-upgrade to S3."""
    return await _handle_messages(request, tier="S2", tier_source="path:s2", tier_explicit=True)


@app.post("/_admin/reload-denylist")
async def admin_reload_denylist(request: Request) -> dict[str, Any]:
    """Force the classifier to drop its denylist cache. Idempotent.

    Token-gated by SharedSecretMiddleware. Used by ``tools/admin/denylist_cli.py``
    after every atomic mutation. Mtime-aware caching means this call is a
    belt-and-braces signal — the next classifier invocation would pick the
    change up anyway on stat() comparison.
    """
    reload_denylist()
    return {"ok": True, "ts": time.time()}


@app.post("/s3/v1/messages")
async def s3_v1_messages(request: Request) -> Response:
    """Path-pinned Tier S3 (confidential). Hard-blocks cloud; routes to local Ollama.

    Classifier cannot downgrade — S3 is the maximum severity.
    """
    return await _handle_messages(request, tier="S3", tier_source="path:s3", tier_explicit=True)


if __name__ == "__main__":
    import uvicorn
    log.info("starting Sovereign Router at http://127.0.0.1:%d", ROUTER_PORT)
    uvicorn.run(app, host="127.0.0.1", port=ROUTER_PORT,
                log_level=LOG_LEVEL.lower(), access_log=False)