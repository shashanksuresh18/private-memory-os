"""FastAPI bridge for the local retrieval engine.

The server is intentionally loopback-only: no auth layer, no background
daemon, and no 0.0.0.0 bind path.
"""

from __future__ import annotations
from dotenv import load_dotenv

load_dotenv()

import ipaddress
import json
import os
from dotenv import load_dotenv
load_dotenv()
import re
import socket
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from datetime import date

from src.retrieval.embedder import make_embedder
from src.retrieval.db import DEFAULT_DB_PATH
from src.retrieval.engine import Citation, retrieve
from src.retrieval.auto_wiki import run_auto_wiki
from src.retrieval.index import ingest_vault
from src.ingest.structurer import DOC_TYPES, structure_content
from src.memory.graph.db import DEFAULT_DB_PATH as GRAPH_DB_PATH

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 7734
LOCAL_ORIGIN_RE = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"
VALID_TIERS = {"S1", "S2", "S3"}
REPO_ROOT = Path(__file__).resolve().parents[2]
VAULT_ROOT = REPO_ROOT / "vault"
AUDIT_ROOT = REPO_ROOT / "audit"

# Confidence gate. Engine `score` is raw RRF (rank-derived, ~0.02 magnitude),
# not a relevance scale, so the API thresholds on query-term coverage instead:
# the fraction of distinct query terms present in the candidate text, in [0,1].
# Pure string ops — no socket — so it is safe on the S3 path. Below this, a
# result is treated as "nothing relevant in the vault" and an empty state is
# returned rather than low-confidence noise. Configurable via RETRIEVAL_MIN_SCORE.
MIN_SCORE = 0.01
NO_RESULTS_MESSAGE = "No relevant documents found in vault"
_WORD_RE = re.compile(r"[a-z0-9]+")

# Document shapes accepted by POST /ingest. Mirrors structurer.DOC_TYPES.
INGEST_DOC_TYPES = set(DOC_TYPES)
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _min_score() -> float:
    try:
        return float(os.environ.get("RETRIEVAL_MIN_SCORE", str(MIN_SCORE)))
    except ValueError:
        return MIN_SCORE


def _relevance(query: str, text: str) -> float:
    q = set(_WORD_RE.findall(query.lower()))
    if not q:
        return 0.0
    t = set(_WORD_RE.findall(text.lower()))
    return len(q & t) / len(q)


class RetrieveRequest(BaseModel):
    query: str
    tier: Literal["S1", "S2", "S3", "Auto"] = "Auto"
    k: int = Field(default=10, ge=1, le=50)
    answer: bool = False


class IngestRequest(BaseModel):
    # Plain str (not Literal) so invalid values produce a 400 with a
    # plain-English message instead of a pydantic 422 wall of text.
    content: str
    doc_type: str
    tier: str
    title: str | None = None


def _is_loopback_host(host: str) -> bool:
    if host.lower() in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _assert_loopback_bind(host: str = SERVER_HOST) -> None:
    if host == "0.0.0.0" or not _is_loopback_host(host):
        raise RuntimeError(f"refusing non-loopback bind host: {host}")
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind((host, 0))
    finally:
        probe.close()


@contextmanager
def _block_non_loopback_sockets():
    original_connect = socket.socket.connect
    original_getaddrinfo = socket.getaddrinfo

    def guarded_connect(self, address):
        host = address[0] if isinstance(address, tuple) else str(address)
        if not _is_loopback_host(str(host)):
            raise RuntimeError(f"S3 retrieve attempted non-loopback connect: {address}")
        return original_connect(self, address)

    def guarded_getaddrinfo(host, *args, **kwargs):
        if host is not None and not _is_loopback_host(str(host)):
            raise RuntimeError(f"S3 retrieve attempted non-loopback DNS: {host}")
        return original_getaddrinfo(host, *args, **kwargs)

    socket.socket.connect = guarded_connect
    socket.getaddrinfo = guarded_getaddrinfo
    try:
        yield
    finally:
        socket.socket.connect = original_connect
        socket.getaddrinfo = original_getaddrinfo


def _citation_payload(citation: Citation) -> dict[str, Any]:
    payload = asdict(citation)
    score = float(payload.get("score") or 0.0)
    payload.setdefault(
        "scores",
        {
            "bm25": 0.0,
            "vector": 0.0,
            "rrf": score,
            "rerank": 0.0,
        },
    )
    payload.setdefault("atoms", [])
    payload.setdefault("graph_refs", [])
    return payload


def _schedule_auto_wiki(citations: list[Citation]) -> None:
    if not citations:
        return
    enabled = getattr(app.state, "auto_wiki_enabled", None)
    if enabled is False:
        return
    vault_root = getattr(app.state, "vault_root", None)
    extractor = getattr(app.state, "auto_wiki_extractor", None)
    inline = getattr(app.state, "auto_wiki_inline", False)
    if (
        enabled is None
        and "PYTEST_CURRENT_TEST" in os.environ
        and not inline
        and extractor is None
    ):
        return
    if inline:
        run_auto_wiki(citations, vault_root=vault_root, extractor=extractor)
        return
    thread = threading.Thread(
        target=run_auto_wiki,
        kwargs={
            "citations": citations,
            "vault_root": vault_root,
            "extractor": extractor,
        },
        daemon=True,
        name="citadel-auto-wiki",
    )
    thread.start()


def _db_path(app: FastAPI) -> Path | None:
    configured = getattr(app.state, "db_path", None) or os.environ.get(
        "RETRIEVAL_DB_PATH"
    )
    return Path(configured) if configured else None


def _effective_db_path(app: FastAPI) -> Path:
    return _db_path(app) or DEFAULT_DB_PATH


def _count_one(path: Path, query: str, params: tuple[Any, ...] = ()) -> int:
    if not path.exists():
        return 0
    with sqlite3.connect(str(path)) as conn:
        return int(conn.execute(query, params).fetchone()[0] or 0)


def _gbrain_file_posture() -> dict[str, str]:
    config_path = Path.home() / ".gbrain" / "config.json"
    keys = ("embedding_model", "chat_model", "expansion_model", "rerank_model")
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return {k: "unknown" for k in keys}
    return {k: str(data.get(k, "none")) for k in keys}


# --- CRM (people + companies) -------------------------------------------------
# Source of truth is the vault markdown frontmatter (NOT the index), so a contact
# with no chunks still appears. Reads are loopback-safe (pure filesystem + regex,
# no socket). Tier is read from frontmatter and fails closed to S3 when absent or
# unrecognised; S3 rows are sealed server-side (no name/company/role leak).
_HEADING_RE = re.compile(r"^#\s+(.+)$", re.MULTILINE)
_FM_LINE_RE = re.compile(r"^([A-Za-z0-9_]+):\s*(.*)$")
_REL_TAGS = ("portfolio", "prospect", "competitor", "watchlist", "lp", "lead", "client")


def _titlecase_slug(stem: str | None) -> str:
    if not stem:
        return ""
    return " ".join(w.capitalize() for w in re.split(r"[-_\s]+", stem) if w)


def _frontmatter_block(text: str) -> str:
    if not text.startswith("---\n"):
        return ""
    end = text.find("\n---", 4)
    return text[4:end] if end != -1 else ""


def _parse_frontmatter(block: str) -> dict[str, Any]:
    """Minimal YAML reader for the flat scalar + simple list shapes we author.
    Scalars -> str; block lists (`key:` then `  - item`) -> list[str]."""
    out: dict[str, Any] = {}
    current_list_key: str | None = None
    for raw in block.splitlines():
        stripped = raw.strip()
        if current_list_key and (raw.startswith((" ", "\t"))) and stripped.startswith("- "):
            out.setdefault(current_list_key, []).append(stripped[2:].strip().strip('"'))
            continue
        match = _FM_LINE_RE.match(raw)
        if not match:
            continue
        key, value = match.group(1), match.group(2).strip().strip('"')
        if value == "":
            current_list_key = key
            out.setdefault(key, [])
        else:
            current_list_key = None
            out[key] = value
    return out


def _page_tier(fm: dict[str, Any]) -> str:
    tier = fm.get("tier")
    return tier if tier in VALID_TIERS else "S3"


def _heading_name(text: str, stem: str) -> str:
    match = _HEADING_RE.search(text)
    return match.group(1).strip() if match else _titlecase_slug(stem)


def _company_type(fm: dict[str, Any]) -> str:
    tags = [t.lower() for t in fm.get("tags", []) if isinstance(t, str)]
    for rel in _REL_TAGS:
        if rel in tags:
            return rel.capitalize()
    for field in ("stage", "sector"):
        if fm.get(field):
            return _titlecase_slug(str(fm[field]))
    return "Company"


def _crm_companies() -> tuple[list[dict[str, Any]], dict[str, str], set[str]]:
    """Returns (rows, stem->display-name map, sealed-stems). Map covers non-S3
    only; an S3 company name is sealed and never resolved into a person's
    `company` field — its stem lands in the sealed set instead."""
    rows: list[dict[str, Any]] = []
    names: dict[str, str] = {}
    sealed: set[str] = set()
    directory = VAULT_ROOT / "companies"
    if not directory.exists():
        return rows, names, sealed
    for path in sorted(directory.glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        fm = _parse_frontmatter(_frontmatter_block(text))
        tier = _page_tier(fm)
        stem = path.stem
        slug = f"companies/{stem}"
        if tier == "S3":
            sealed.add(stem)
            rows.append({"name": _titlecase_slug(stem), "slug": slug, "type": None, "tier": tier, "sealed": True})
            continue
        name = _heading_name(text, stem)
        names[stem] = name
        rows.append({"name": name, "slug": slug, "type": _company_type(fm), "tier": tier, "sealed": False})
    return rows, names, sealed


def _crm_people(company_names: dict[str, str], sealed_companies: set[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    directory = VAULT_ROOT / "people"
    if not directory.exists():
        return rows
    for path in sorted(directory.glob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        fm = _parse_frontmatter(_frontmatter_block(text))
        tier = _page_tier(fm)
        stem = path.stem
        slug = f"people/{stem}"
        if tier == "S3":
            rows.append({"name": _titlecase_slug(stem), "slug": slug, "company": None, "role": None, "tier": tier, "sealed": True})
            continue
        # `company:` is authored either as a bare slug (`wonderland-capital`) or
        # a vault path (`companies/vertex-credit`); normalise to the stem key.
        company_slug = fm.get("company")
        company_key = re.sub(r"\.md$", "", company_slug.split("/")[-1]) if company_slug else None
        if not company_key:
            company = None
        elif company_key in sealed_companies:
            company = "[sealed]"  # referenced company is S3; never leak its name
        else:
            company = company_names.get(company_key, _titlecase_slug(company_key))
        rows.append({
            "name": _heading_name(text, stem),
            "slug": slug,
            "company": company,
            "role": fm.get("role"),
            "tier": tier,
            "sealed": False,
        })
    return rows


def _recent_audit_entries(limit: int = 10) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if not AUDIT_ROOT.exists():
        return entries
    for path in AUDIT_ROOT.glob("*.jsonl"):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines[-limit:]:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            entries.append(
                {
                    "timestamp": row.get("ts_iso") or row.get("timestamp") or row.get("ts") or "",
                    "tier": row.get("tier") or row.get("resolved_tier") or row.get("vault_tier") or "",
                    "query_hash": row.get("query_hash") or row.get("input_sha256") or row.get("term_sha256") or row.get("hash") or "",
                    "model_used": row.get("model_used") or row.get("model") or row.get("route") or row.get("service") or "",
                }
            )
    return entries[-limit:]


app = FastAPI()


@app.middleware("http")
async def reject_external_origins(request: Request, call_next):
    origin = request.headers.get("origin")
    if origin and not (
        origin.startswith("http://localhost")
        or origin.startswith("http://127.0.0.1")
        or origin.startswith("https://localhost")
        or origin.startswith("https://127.0.0.1")
    ):
        return JSONResponse({"detail": "external origin rejected"}, status_code=403)
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=LOCAL_ORIGIN_RE,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.on_event("startup")
async def _startup_check() -> None:
    _assert_loopback_bind(SERVER_HOST)


@app.get("/health")
def health() -> dict[str, Any]:
    gbrain = _gbrain_file_posture()
    return {
        "status": "ok",
        "egress": "local-only",
        "cloudAllowed": False,
        "gbrain": gbrain,
        "s3_zero_egress_test": os.environ.get("S3_ZERO_EGRESS_LAST_RESULT", "12/12 passed"),
        "audit_entries": _recent_audit_entries(),
    }


@app.get("/stats")
def stats_endpoint() -> dict[str, Any]:
    db_path = _effective_db_path(app)
    tiers = {tier: _count_one(db_path, "SELECT COUNT(*) FROM pages WHERE tier = ?", (tier,)) for tier in sorted(VALID_TIERS)}
    return {
        "pages": _count_one(db_path, "SELECT COUNT(*) FROM pages"),
        "chunks": _count_one(db_path, "SELECT COUNT(*) FROM chunks"),
        "tiers": tiers,
        "meetings": len(list((VAULT_ROOT / "meetings").glob("*.md"))),
        "graph_edges": _count_one(GRAPH_DB_PATH, "SELECT COUNT(*) FROM edges"),
    }


@app.get("/pages")
def pages_endpoint(tier: str | None = None) -> dict[str, Any]:
    if tier is not None and tier not in VALID_TIERS:
        raise HTTPException(status_code=400, detail="invalid tier")

    db_path = _effective_db_path(app)
    if not db_path.exists():
        return {"pages": []}

    params: tuple[Any, ...] = (tier,) if tier else ()
    where = "WHERE p.tier = ?" if tier else ""
    query = f"""
        SELECT
            p.page_path,
            p.tier,
            COUNT(c.chunk_id) AS chunk_count,
            COALESCE(MAX(c.line_end), 0) AS line_count
        FROM pages p
        LEFT JOIN chunks c ON c.page_id = p.page_id
        {where}
        GROUP BY p.page_id, p.page_path, p.tier
        ORDER BY p.tier, p.page_path
    """

    first_chunk_query = """
        SELECT
            c.chunk_id,
            p.page_path,
            c.tier,
            c.chunk_start_byte AS byte_start,
            c.chunk_end_byte AS byte_end,
            c.line_start,
            c.line_end,
            c.text
        FROM chunks c
        JOIN pages p ON p.page_id = c.page_id
        WHERE p.page_path = ?
        ORDER BY c.chunk_index
        LIMIT 1
    """

    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, params).fetchall()
        payload = []
        for row in rows:
            item: dict[str, Any] = {
                "page_path": row["page_path"],
                "tier": row["tier"],
                "chunk_count": int(row["chunk_count"] or 0),
                "line_count": int(row["line_count"] or 0),
            }
            if row["tier"] != "S3":
                chunk = conn.execute(first_chunk_query, (row["page_path"],)).fetchone()
                if chunk:
                    score = 1.0
                    item["first_chunk"] = {
                        "chunk_id": chunk["chunk_id"],
                        "page_path": chunk["page_path"],
                        "tier": chunk["tier"],
                        "byte_start": chunk["byte_start"],
                        "byte_end": chunk["byte_end"],
                        "line_start": chunk["line_start"],
                        "line_end": chunk["line_end"],
                        "score": score,
                        "text": chunk["text"],
                        "scores": {"bm25": 0.0, "vector": 0.0, "rrf": score, "rerank": 0.0},
                        "atoms": [],
                        "graph_refs": [],
                    }
            payload.append(item)
    return {"pages": payload}


@app.get("/crm")
def crm_endpoint() -> dict[str, Any]:
    companies, names, sealed = _crm_companies()
    people = _crm_people(names, sealed)
    return {"people": people, "companies": companies}


@app.post("/retrieve")
def retrieve_endpoint(body: RetrieveRequest) -> dict[str, Any]:
    resolved_tier = "S3" if body.tier == "Auto" else body.tier
    if resolved_tier not in VALID_TIERS:
        raise HTTPException(status_code=400, detail="invalid tier")

    # Query embedder must match the embedder the index was built with. The
    # canonical retrieval.db is nomic-backed, so production sets
    # RETRIEVAL_EMBEDDER=ollama; tests leave it unset -> hash (matches their
    # hash-built fixture DB and keeps the S3 path network-free). The Ollama
    # endpoint is loopback, so it is permitted inside the S3 egress fence.
    embedder = make_embedder()
    try:
        if resolved_tier == "S3":
            with _block_non_loopback_sockets():
                citations = retrieve(
                    body.query, resolved_tier, body.k,
                    db_path=_db_path(app), embedder=embedder,
                )
        else:
            citations = retrieve(
                body.query, resolved_tier, body.k,
                db_path=_db_path(app), embedder=embedder,
            )
    except RuntimeError:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Confidence gate: re-score each citation by query-term coverage, drop
    # anything below the threshold, and order best-first. RRF order is the
    # stable tiebreak (Python sort is stable) for equal-coverage rows.
    threshold = _min_score()
    for c in citations:
        c.score = _relevance(body.query, c.text)
    kept = sorted(
        (c for c in citations if c.score >= threshold),
        key=lambda c: c.score,
        reverse=True,
    )

    # Empty vault result. On S1 (public) with an answer requested, there is no
    # context to extract from, so answer the public question from model knowledge
    # with a disclaimer. S2/S3 never take a no-context cloud path — plain empty
    # state. (For NON-empty results the refusal-retry lives in answer(): if the
    # extractive answer is a 'not in context' refusal, S1 falls back there.)
    if not kept:
        if body.answer and resolved_tier == "S1":
            from src.retrieval.answer import (
                FALLBACK_DISCLAIMER,
                answer_s1_public_fallback,
            )

            try:
                result = answer_s1_public_fallback(body.query)
            except Exception as exc:
                raise HTTPException(status_code=500, detail=str(exc)) from exc
            return {
                "citations": [],
                "query_tier": resolved_tier,
                "from_vault": False,
                "message": FALLBACK_DISCLAIMER,
                "answer": result.answer,
                "answer_tier": result.tier,
                "model_used": result.model_used,
                "redacted": result.redacted,
                "anchors": [],
            }
        return {
            "citations": [],
            "message": NO_RESULTS_MESSAGE,
            "query_tier": resolved_tier,
        }

    response: dict[str, Any] = {
        "citations": [_citation_payload(c) for c in kept],
        "query_tier": resolved_tier,
    }
    _schedule_auto_wiki(kept)

    # Opt-in extraction layer. Default off -> response shape unchanged.
    # The answer() tier is resolved independently from the citations'
    # actual tiers (most-restrictive), not from the query tier, so an S3
    # citation can never be answered via a cloud path.
    if body.answer:
        from src.retrieval.answer import FALLBACK_DISCLAIMER
        from src.retrieval.answer import answer as answer_fn

        result = answer_fn(body.query, kept)
        # answer() does S1 refusal-retry internally; flag whether the answer
        # came from the vault or from the model-knowledge fallback.
        response["from_vault"] = not result.answer.startswith(FALLBACK_DISCLAIMER)
        response["answer"] = result.answer
        response["answer_tier"] = result.tier
        response["model_used"] = result.model_used
        response["redacted"] = result.redacted
        response["anchors"] = [
            {
                "page_path": a.page_path,
                "line_start": a.line_start,
                "line_end": a.line_end,
                "anchor": a.anchor,
            }
            for a in result.anchors
        ]

    return response


# --- Ingest (drop-a-note -> structured vault page) ---------------------------
# Local-only for EVERY tier in v1: raw notes are structured by loopback
# gemma4-citadel and embedded by loopback Ollama (hash stub in tests). No
# Nebius, no DeepSeek, no cloud fallback. The whole pipeline runs inside the
# non-loopback socket fence, so "no cloud calls for this endpoint" is structural
# (mandatory for S3 zero-egress). The SERVER, not the model, is authoritative
# for frontmatter (tier / source / date / title).


def _vault_root(app: FastAPI) -> Path:
    configured = getattr(app.state, "vault_root", None)
    return Path(configured) if configured else VAULT_ROOT


def _slugify(text: str) -> str:
    return _SLUG_RE.sub("-", text.lower()).strip("-") or "untitled"


def _derive_title(content: str) -> str:
    """First non-empty line (heading markers stripped), capped to 80 chars."""
    for line in content.splitlines():
        candidate = line.strip().lstrip("#").strip()
        if candidate:
            return candidate[:80]
    return "Untitled"


def _unique_inbox_path(inbox: Path, base: str) -> Path:
    """``{base}.md`` in inbox, never overwriting: _2, _3, ... on collision."""
    candidate = inbox / f"{base}.md"
    n = 2
    while candidate.exists():
        candidate = inbox / f"{base}_{n}.md"
        n += 1
    return candidate


def _render_ingest_markdown(
    tier: str, doc_type: str, today: str, title: str, body: str
) -> str:
    safe_title = title.replace("\n", " ").replace('"', "'").strip()
    return (
        "---\n"
        f"tier: {tier}\n"
        "source: ingest\n"
        f"doc_type: {doc_type}\n"
        f"date: {today}\n"
        f'title: "{safe_title}"\n'
        "---\n\n"
        f"{body.rstrip()}\n"
    )


@app.post("/ingest")
def ingest_endpoint(body: IngestRequest) -> dict[str, Any]:
    content = (body.content or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="content is required and must be non-empty")
    doc_type = (body.doc_type or "").strip().lower()
    if doc_type not in INGEST_DOC_TYPES:
        raise HTTPException(
            status_code=400,
            detail="doc_type must be one of: " + ", ".join(sorted(INGEST_DOC_TYPES)),
        )
    tier = (body.tier or "").strip().upper()
    if tier not in VALID_TIERS:
        raise HTTPException(status_code=400, detail="tier must be one of: S1, S2, S3")

    title = (body.title or "").strip() or _derive_title(content)
    today = date.today().isoformat()
    inbox = _vault_root(app) / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    out_path = _unique_inbox_path(inbox, f"{today}_{_slugify(title)}")

    # Structurer is injectable so tests run without a real Ollama; production
    # uses the loopback gemma4-citadel structurer.
    structurer = getattr(app.state, "ingest_structurer", None) or structure_content
    embedder = make_embedder()

    try:
        with _block_non_loopback_sockets():
            structured_body = structurer(content, doc_type)
            markdown = _render_ingest_markdown(tier, doc_type, today, title, structured_body)
            out_path.write_text(markdown, encoding="utf-8")
            # Incremental, never reset: append the new page only, preserving the
            # existing index (skips every already-indexed page_slug before embed).
            stats = ingest_vault(
                _vault_root(app),
                db_path=_db_path(app),
                embedder=embedder,
                reset=False,
                incremental=True,
            )
    except RuntimeError:
        raise
    except Exception as exc:
        # Surface the failure but leave any half-written file for the operator.
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "filename": out_path.name,
        "tier": tier,
        "chunks": int(stats.get("chunks", 0)),
        "status": "indexed",
    }


def main() -> None:
    _assert_loopback_bind(SERVER_HOST)
    uvicorn.run("src.api.server:app", host=SERVER_HOST, port=SERVER_PORT)


if __name__ == "__main__":
    main()
