"""Tier S2 DLP service: local HTTP wrapper around openai/privacy-filter (opf).

Bound strictly to 127.0.0.1 — never expose to LAN. ClawXRouter calls this on
every S2-classified egress before the scrubbed skeleton is forwarded to Claude.

Pipeline contract:
    POST /redact { "text": "..." }
    -> 200 { "redacted_text": "...", "summary": {...}, "spans": [...], "warning": null }
    -> 503 if model checkpoint is not loaded
    -> 413 if payload exceeds MAX_PAYLOAD_BYTES
    -> 403 if request did not come from 127.0.0.1 or shared-secret header is wrong

Audit:
    Every request appends one hash-only JSON line to audit/opf.jsonl.
    No plaintext is written. Hash chain (prev_hash -> sha256(prev_hash || record))
    so a tampered line breaks verification.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from opf._api import OPF, RedactionResult

MAX_PAYLOAD_BYTES = 256 * 1024
ALLOWED_CATEGORIES = (
    "account_number",
    "private_address",
    "private_date",
    "private_email",
    "private_person",
    "private_phone",
    "private_url",
    "secret",
)
SHARED_SECRET_ENV = "SOVEREIGN_OPF_TOKEN"
AUDIT_PATH = Path(os.environ.get("SOVEREIGN_AUDIT_DIR", "audit")) / "opf.jsonl"
LOG_LEVEL = os.environ.get("SOVEREIGN_OPF_LOG_LEVEL", "INFO")

logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("sovereign.opf")

_redactor: OPF | None = None
_redactor_lock = threading.Lock()
_audit_lock = threading.Lock()


def _get_redactor() -> OPF:
    """Lazily build and cache the singleton OPF redactor.

    First call downloads or loads the checkpoint at ``OPF_CHECKPOINT`` or
    ``~/.opf/privacy_filter``. Subsequent calls reuse the warm instance.
    """
    global _redactor
    if _redactor is not None:
        return _redactor
    with _redactor_lock:
        if _redactor is None:
            device = os.environ.get("SOVEREIGN_OPF_DEVICE", "cpu")
            log.info("loading OPF checkpoint on device=%s ...", device)
            _redactor = OPF(
                device=device,
                output_mode="typed",
                decode_mode="viterbi",
                output_text_only=False,
            )
            _redactor.get_runtime()
            log.info("OPF runtime ready")
    return _redactor


def _audit_append(record: dict[str, Any]) -> None:
    """Append one hash-chained JSON line to the audit log.

    The record stores no plaintext. Only counts, hashes, and category labels.
    """
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


class LoopbackOnlyMiddleware(BaseHTTPMiddleware):
    """Reject any request whose peer is not 127.0.0.1 or ::1.

    Defense in depth: even if uvicorn is misconfigured to bind 0.0.0.0,
    every request is checked at the application layer.
    """

    async def dispatch(self, request: Request, call_next):
        client = request.client.host if request.client else ""
        if client not in {"127.0.0.1", "::1", "localhost"}:
            log.warning("rejected non-loopback request from %s", client)
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "loopback-only service"},
            )
        return await call_next(request)


class SharedSecretMiddleware(BaseHTTPMiddleware):
    """Require X-OPF-Token header to match SOVEREIGN_OPF_TOKEN env var.

    Skipped if env var is unset, but a startup warning is logged.
    """

    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/healthz":
            return await call_next(request)
        expected = os.environ.get(SHARED_SECRET_ENV)
        if not expected:
            return await call_next(request)
        provided = request.headers.get("x-opf-token", "")
        if provided != expected:
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "invalid X-OPF-Token"},
            )
        return await call_next(request)


class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    """Enforce a hard cap on request body size."""

    async def dispatch(self, request: Request, call_next):
        cl = request.headers.get("content-length")
        if cl and cl.isdigit() and int(cl) > MAX_PAYLOAD_BYTES:
            return JSONResponse(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                content={"detail": f"payload exceeds {MAX_PAYLOAD_BYTES} bytes"},
            )
        return await call_next(request)


app = FastAPI(title="Sovereign Citadel OPF DLP", version="0.1.0")
app.add_middleware(MaxBodySizeMiddleware)
app.add_middleware(SharedSecretMiddleware)
app.add_middleware(LoopbackOnlyMiddleware)


@app.on_event("startup")
def _warm_model() -> None:
    if not os.environ.get(SHARED_SECRET_ENV):
        log.warning(
            "%s is unset — service relies on loopback-only enforcement only",
            SHARED_SECRET_ENV,
        )
    try:
        _get_redactor()
    except Exception as exc:
        log.error("failed to warm OPF runtime at startup: %s", exc)


class RedactRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_PAYLOAD_BYTES)


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    """Liveness probe. Reports whether model is ready."""
    return {
        "ok": True,
        "model_ready": _redactor is not None,
        "categories": list(ALLOWED_CATEGORIES),
        "max_payload_bytes": MAX_PAYLOAD_BYTES,
    }


@app.post("/redact")
def redact(req: RedactRequest, request: Request) -> dict[str, Any]:
    """Scrub PII spans from ``text`` and return the sanitized skeleton.

    Response contains the redacted text plus per-span metadata (label, start,
    end, placeholder). No plaintext is written to the audit log — only counts,
    hashes, and category labels.
    """
    try:
        redactor = _get_redactor()
    except Exception as exc:
        log.exception("OPF runtime unavailable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"OPF runtime unavailable: {exc}",
        ) from exc

    event_id = uuid.uuid4().hex
    started = time.monotonic()
    result = redactor.redact(req.text)
    duration_ms = int((time.monotonic() - started) * 1000)

    if not isinstance(result, RedactionResult):
        raise HTTPException(status_code=500, detail="unexpected OPF result type")

    spans = [
        {
            "label": s.label,
            "start": s.start,
            "end": s.end,
            "placeholder": s.placeholder,
        }
        for s in result.detected_spans
    ]

    input_hash = hashlib.sha256(req.text.encode("utf-8")).hexdigest()
    output_hash = hashlib.sha256(result.redacted_text.encode("utf-8")).hexdigest()
    category_counts: dict[str, int] = {}
    for s in result.detected_spans:
        category_counts[s.label] = category_counts.get(s.label, 0) + 1

    _audit_append({
        "ts": time.time(),
        "event_id": event_id,
        "service": "opf",
        "tier": "S2",
        "input_sha256": input_hash,
        "input_bytes": len(req.text.encode("utf-8")),
        "output_sha256": output_hash,
        "output_bytes": len(result.redacted_text.encode("utf-8")),
        "span_count": len(spans),
        "categories": category_counts,
        "duration_ms": duration_ms,
        "warning": result.warning,
        "peer": request.client.host if request.client else "",
    })

    response = Response(
        content=json.dumps({
            "event_id": event_id,
            "redacted_text": result.redacted_text,
            "summary": result.summary,
            "spans": spans,
            "warning": result.warning,
            "duration_ms": duration_ms,
        }, ensure_ascii=False),
        media_type="application/json",
    )
    response.headers["cache-control"] = "no-store"
    response.headers["x-tier"] = "S2"
    return response


if __name__ == "__main__":
    import uvicorn
    host = "127.0.0.1"
    port = int(os.environ.get("SOVEREIGN_OPF_PORT", "8765"))
    log.info("starting Sovereign Citadel OPF DLP at http://%s:%d", host, port)
    uvicorn.run(app, host=host, port=port, log_level=LOG_LEVEL.lower(), access_log=False)
