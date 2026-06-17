"""Compare / Council HTTP routes (cloud-only, normal chat feature).

Mounted under ``/api/compare`` on the main loopback server. SEPARATE from the
retrieval engine: no S1/S2/S3 tier routing, no `_block_non_loopback_sockets`
fence (this is intentionally a cloud feature, gated by the user explicitly
choosing cloud models). Every outbound prompt -- and every response forwarded to
the synthesis model -- is DLP-scrubbed with the existing ``redact_pii`` first.

Parallelism: each ``/run`` call handles ONE pane. The frontend fires one ``/run``
per pane concurrently; FastAPI executes these sync handlers in its threadpool, so
the model calls run in parallel with no asyncio plumbing. A failing or slow pane
never blocks the others (partial failure is per-pane).
"""

from __future__ import annotations

import json
import re

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.retrieval.answer import redact_pii

from . import history_db, sessions
from .providers import (
    COMPARE_SYSTEM_PROMPT,
    DEFAULT_TIMEOUT_S,
    available_models,
    get_provider,
    is_model_available,
    model_by_id,
)

router = APIRouter(prefix="/api/compare", tags=["compare"])

# Synthesis ("Council") instruction. The chosen model is NOT blind -- the user
# picks it explicitly -- so its name may be shown.
COUNCIL_SYSTEM_PROMPT = (
    "You are a council moderator. You are given a question and several candidate "
    "answers from different AI models. Produce a synthesis using EXACTLY these "
    "markdown sections, in this order:\n"
    "## Consensus\n## Disagreements\n## Strongest answer\n## Gaps & uncertainty\n"
    "## Model-by-model summary\n"
    "Be concise and specific. Do not invent agreement that is not there."
)

# Debate ("round table"): a model is shown the other participants' latest
# answers and must engage with them directly. {label} is the model's own
# neutral pane label (identity stays hidden in blind mode).
DEBATE_SYSTEM_PROMPT = (
    "You are {label} in a multi-model debate about the user's question. You have "
    "already given an answer; you are now shown the other participants' latest "
    "answers. Respond concisely using EXACTLY these markdown sections:\n"
    "## Agree\n## Disagree\n## Refined answer\n"
    "Engage with the other participants' specific claims -- name the points you "
    "agree on, the points you dispute and why, then give your updated answer."
)

# Jury ("model-as-judge"): a model scores the OTHER participants' answers. Karpathy
# llm-council Stage 2. Candidates are shown under neutral labels only (identity is
# never sent -- enforced server-side in /rank), so scores cannot be biased by which
# brand produced an answer. The juror does NOT score itself. Output is strict JSON
# so the scores can be aggregated without parsing prose.
JURY_SYSTEM_PROMPT = (
    "You are {label}, an impartial judge on a panel scoring OTHER AI models' "
    "answers to the user's question. You are shown the question and several "
    "candidate answers, each under a neutral label. Score EACH candidate from 1 "
    "to 10 (10 = best) on accuracy, completeness, and clarity. Judge the answer's "
    "substance, not its length or style, and do not reward verbosity. Reply with "
    "ONLY a JSON object -- no prose, no markdown fences -- in exactly this shape:\n"
    '{{"scores": [{{"label": "<participant label>", "score": <1-10>, '
    '"reason": "<one short sentence>"}}]}}'
)


# --- Request models (plain optional fields -> plain 400s, not 422 walls) -----

class StartRequest(BaseModel):
    prompt: str | None = None
    model_ids: list[str] | None = None
    blind: bool = False


class RunRequest(BaseModel):
    comp_id: str | None = None
    pane_id: str | None = None
    timeout_s: float | None = None


class CompIdRequest(BaseModel):
    comp_id: str | None = None


class VotePane(BaseModel):
    pane_id: str | None = None
    status: str | None = None
    latency_ms: int | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    text: str | None = None  # hashed then discarded; never stored


class VoteRequest(BaseModel):
    comp_id: str | None = None
    winner: str | None = None  # pane_id or "tie"
    panes: list[VotePane] | None = None


class SynthResponse(BaseModel):
    label: str | None = None
    text: str | None = None


class SynthesizeRequest(BaseModel):
    comp_id: str | None = None
    synth_model_id: str | None = None
    responses: list[SynthResponse] | None = None


class DebatePeer(BaseModel):
    label: str | None = None
    text: str | None = None


class DebateRequest(BaseModel):
    comp_id: str | None = None
    pane_id: str | None = None
    round: int = 2
    peers: list[DebatePeer] | None = None


class RankPeer(BaseModel):
    # A candidate to score. The juror is given the peer's TEXT but never a
    # client-supplied label -- /rank resolves the neutral label from the session
    # by pane_id, so model identity can never reach a juror.
    pane_id: str | None = None
    text: str | None = None


class RankRequest(BaseModel):
    comp_id: str | None = None
    pane_id: str | None = None
    peers: list[RankPeer] | None = None


# --- Helpers ----------------------------------------------------------------

def _compare_db(request: Request):
    """Test-injectable history DB path (set via app.state.compare_db_path)."""
    return getattr(request.app.state, "compare_db_path", None)


def _parse_scores(text: str, allowed: set[str]) -> list[dict]:
    """Parse a jury reply into ``[{label, score, reason}]``.

    Tolerant of the ways models wrap JSON: strips a ```json ... ``` fence and
    narrows to the outermost ``{...}`` before parsing. Keeps only labels that were
    actually shown to this juror (so a hallucinated label or a self-score is
    dropped), clamps each score to 1..10, and de-dupes by label (first wins).
    Raises ``ValueError`` when nothing usable is found so the caller can mark the
    juror as failed without poisoning the aggregate.
    """
    raw = (text or "").strip()
    if not raw:
        raise ValueError("empty reply")
    fence = re.search(r"```(?:json)?\s*(.*?)```", raw, re.DOTALL)
    if fence:
        raw = fence.group(1).strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON object found")
    try:
        obj = json.loads(raw[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError(str(exc)) from exc
    rows = obj.get("scores") if isinstance(obj, dict) else None
    if not isinstance(rows, list):
        raise ValueError("missing 'scores' array")
    out: list[dict] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        label = str(row.get("label", "")).strip()
        if label not in allowed or label in seen:
            continue
        try:
            score = float(row.get("score"))
        except (TypeError, ValueError):
            continue
        score = max(1.0, min(10.0, score))
        reason = str(row.get("reason", "")).strip()[:280]
        out.append({"label": label, "score": score, "reason": reason})
        seen.add(label)
    if not out:
        raise ValueError("no valid scores for shown participants")
    return out


def _pane_public(session: sessions.CompareSession, pane: sessions.Pane) -> dict:
    """Public view of a pane. Model identity is withheld while blind and not yet
    revealed -- only the neutral label leaks to the client."""
    show = (not session.blind) or session.revealed
    reg = model_by_id(pane.model_id) or {}
    return {
        "pane_id": pane.pane_id,
        "label": pane.label,
        "model_id": pane.model_id if show else None,
        "provider": reg.get("provider") if show else None,
        "model": reg.get("model") if show else None,
        "model_label": reg.get("label") if show else None,
    }


# --- Endpoints --------------------------------------------------------------

@router.get("/models")
def list_models() -> dict:
    """Configured cloud models only. Unconfigured providers never appear, so
    they cannot be selected."""
    return {"models": available_models()}


@router.post("/start")
def start(body: StartRequest) -> dict:
    prompt = (body.prompt or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt is required")
    model_ids = body.model_ids or []
    if len(model_ids) < 2:
        raise HTTPException(status_code=400, detail="select at least 2 models to compare")
    for mid in model_ids:
        if not is_model_available(mid):
            raise HTTPException(
                status_code=400,
                detail=f"model not available (unknown or provider not configured): {mid}",
            )
    session = sessions.create_session(prompt, model_ids, body.blind)
    return {
        "comp_id": session.comp_id,
        "blind": session.blind,
        "panes": [_pane_public(session, p) for p in session.panes],
    }


@router.post("/run")
def run(body: RunRequest) -> dict:
    session = sessions.get_session(body.comp_id or "")
    if session is None:
        raise HTTPException(status_code=404, detail="unknown comparison session")
    pane = session.pane(body.pane_id or "")
    if pane is None:
        raise HTTPException(status_code=404, detail="unknown pane")

    reg = model_by_id(pane.model_id)
    provider = get_provider(reg["provider"]) if reg else None
    public = _pane_public(session, pane)

    if reg is None or provider is None or not provider.is_configured():
        return {**public, "status": "error", "text": "", "latency_ms": 0,
                "error": "model unavailable"}

    # DLP scrub before the prompt leaves the device.
    safe_prompt = redact_pii(session.prompt)
    timeout_s = body.timeout_s if body.timeout_s and body.timeout_s > 0 else DEFAULT_TIMEOUT_S
    result = provider.chat(reg["model"], safe_prompt, COMPARE_SYSTEM_PROMPT, timeout_s)

    return {
        **public,
        "status": result.status,
        "text": result.text,
        "latency_ms": result.latency_ms,
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
        "error": result.error,
    }


@router.post("/reveal")
def reveal(body: CompIdRequest) -> dict:
    session = sessions.reveal(body.comp_id or "")
    if session is None:
        raise HTTPException(status_code=404, detail="unknown comparison session")
    return {
        "comp_id": session.comp_id,
        "revealed": True,
        "panes": [_pane_public(session, p) for p in session.panes],
    }


@router.post("/vote")
def vote(body: VoteRequest, request: Request) -> dict:
    winner = (body.winner or "").strip()
    if not winner:
        raise HTTPException(status_code=400, detail="winner is required (a pane_id or 'tie')")
    session = sessions.record_vote(body.comp_id or "", winner)
    if session is None:
        raise HTTPException(status_code=400, detail="unknown session or invalid winner")

    if winner == "tie":
        winner_model_id: str | None = "tie"
    else:
        won = session.pane(winner)
        winner_model_id = won.model_id if won else None

    # Build hash-only pane rows. Any response text supplied is hashed here and
    # immediately discarded -- it is never persisted.
    by_id = {p.pane_id: p for p in session.panes}
    hist_panes: list[dict] = []
    for vp in (body.panes or []):
        pane = by_id.get(vp.pane_id or "")
        if pane is None:
            continue
        hist_panes.append({
            "model_id": pane.model_id,
            "status": vp.status,
            "latency_ms": vp.latency_ms,
            "prompt_tokens": vp.prompt_tokens,
            "completion_tokens": vp.completion_tokens,
            "response_sha256": history_db.sha256(vp.text or ""),
        })

    history_db.record_vote(
        comp_id=session.comp_id,
        prompt_sha256=history_db.sha256(session.prompt),
        blind=session.blind,
        model_ids=[p.model_id for p in session.panes],
        winner_model_id=winner_model_id,
        panes=hist_panes,
        db_path=_compare_db(request),
    )

    return {
        "comp_id": session.comp_id,
        "winner": winner,
        "winner_model_id": winner_model_id,
        "panes": [_pane_public(session, p) for p in session.panes],
    }


@router.post("/synthesize")
def synthesize(body: SynthesizeRequest) -> dict:
    synth_id = body.synth_model_id or ""
    if not is_model_available(synth_id):
        raise HTTPException(
            status_code=400,
            detail=f"synthesis model not available: {synth_id or '(none)'}",
        )
    responses = [r for r in (body.responses or []) if (r.text or "").strip()]
    if not responses:
        raise HTTPException(status_code=400, detail="no model responses to synthesize")

    reg = model_by_id(synth_id)
    provider = get_provider(reg["provider"])

    # Scrub each candidate answer before it is re-sent to the synthesis model.
    parts = []
    for i, r in enumerate(responses):
        label = r.label or f"Model {chr(65 + i)}"
        parts.append(f"### {label}\n{redact_pii(r.text or '')}")
    user_content = "Candidate answers:\n\n" + "\n\n".join(parts)

    result = provider.chat(reg["model"], user_content, COUNCIL_SYSTEM_PROMPT)
    if result.status != "ok":
        # Synthesis failed -- surface a clear error. The caller keeps every pane
        # output; nothing about the comparison is erased.
        raise HTTPException(
            status_code=500,
            detail=f"synthesis failed ({result.status}): {result.error or 'unknown error'}",
        )
    return {
        "synthesis": result.text,
        "model_id": synth_id,
        "model": reg["model"],
        "provider": reg["provider"],
        "latency_ms": result.latency_ms,
    }


@router.post("/debate")
def debate(body: DebateRequest) -> dict:
    """One debate turn for one pane: the model is shown the other participants'
    latest answers and responds with agree / disagree / refined. Same per-pane
    semantics as /run (status ok|error|timeout), so a slow or failing model in a
    round never blocks the others. DLP-scrubs the prompt and every peer answer
    before egress."""
    session = sessions.get_session(body.comp_id or "")
    if session is None:
        raise HTTPException(status_code=404, detail="unknown comparison session")
    pane = session.pane(body.pane_id or "")
    if pane is None:
        raise HTTPException(status_code=404, detail="unknown pane")

    reg = model_by_id(pane.model_id)
    provider = get_provider(reg["provider"]) if reg else None
    public = _pane_public(session, pane)
    if reg is None or provider is None or not provider.is_configured():
        return {**public, "status": "error", "text": "", "latency_ms": 0,
                "round": body.round, "error": "model unavailable"}

    peers = [p for p in (body.peers or []) if (p.text or "").strip()]
    peer_block = "\n\n".join(
        f"### {redact_pii(p.label or 'Participant')}\n{redact_pii(p.text or '')}"
        for p in peers
    )
    user_content = (
        f"The question was:\n{redact_pii(session.prompt)}\n\n"
        f"Other participants' latest answers:\n\n{peer_block}"
    )
    system = DEBATE_SYSTEM_PROMPT.format(label=pane.label)
    result = provider.chat(reg["model"], user_content, system)
    return {
        **public,
        "status": result.status,
        "text": result.text,
        "latency_ms": result.latency_ms,
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
        "round": body.round,
        "error": result.error,
    }


@router.post("/rank")
def rank(body: RankRequest) -> dict:
    """One juror turn for one pane: the model scores the OTHER participants'
    answers 1-10 (Karpathy llm-council Stage 2 -- model-as-judge).

    Anti-bias is enforced HERE, not trusted to the client: the request carries
    only peer ``pane_id``s, and this handler resolves each one to its neutral
    session label (``Model A`` ...). A juror therefore never sees a model name,
    even when the comparison is not blind. Same per-pane partial-failure contract
    as /debate -- a juror that errors, times out, or returns unparseable JSON
    yields ``status != "ok"`` with empty ``scores`` and never blocks the others.
    DLP-scrubs the prompt and every candidate answer before egress.
    """
    session = sessions.get_session(body.comp_id or "")
    if session is None:
        raise HTTPException(status_code=404, detail="unknown comparison session")
    pane = session.pane(body.pane_id or "")
    if pane is None:
        raise HTTPException(status_code=404, detail="unknown pane")

    reg = model_by_id(pane.model_id)
    provider = get_provider(reg["provider"]) if reg else None
    public = _pane_public(session, pane)
    if reg is None or provider is None or not provider.is_configured():
        return {**public, "status": "error", "scores": [], "latency_ms": 0,
                "error": "model unavailable"}

    # Resolve peers to (neutral_label, text), dropping unknown ids and self.
    resolved: list[tuple[str, str]] = []
    for p in (body.peers or []):
        text = (p.text or "").strip()
        peer_pane = session.pane(p.pane_id or "")
        if not text or peer_pane is None or peer_pane.pane_id == pane.pane_id:
            continue
        resolved.append((peer_pane.label, text))
    if not resolved:
        raise HTTPException(status_code=400, detail="need at least one peer answer to score")

    allowed = {label for label, _ in resolved}
    peer_block = "\n\n".join(
        f"### {redact_pii(label)}\n{redact_pii(text)}" for label, text in resolved
    )
    user_content = (
        f"The question was:\n{redact_pii(session.prompt)}\n\n"
        f"Candidate answers to score:\n\n{peer_block}"
    )
    system = JURY_SYSTEM_PROMPT.format(label=pane.label)
    result = provider.chat(reg["model"], user_content, system)
    if result.status != "ok":
        return {**public, "status": result.status, "scores": [],
                "latency_ms": result.latency_ms, "error": result.error}
    try:
        scores = _parse_scores(result.text, allowed)
    except ValueError as exc:
        return {**public, "status": "error", "scores": [],
                "latency_ms": result.latency_ms,
                "error": f"could not parse jury scores: {exc}"}
    return {
        **public,
        "status": "ok",
        "scores": scores,
        "latency_ms": result.latency_ms,
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
    }


@router.get("/history")
def history(request: Request) -> dict:
    db_path = _compare_db(request)
    return {
        "history": history_db.list_history(db_path=db_path),
        "scoreboard": history_db.scoreboard(db_path=db_path),
    }
