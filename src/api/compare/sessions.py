"""In-memory store for active Compare sessions.

A session holds the prompt, the blind flag, the pane->model mapping, and the
reveal/vote state. The mapping is kept SERVER-SIDE so that in blind mode the
real model identity never reaches the browser until the user reveals or votes
(Odysseus's anti-de-anonymisation rule). Sessions are ephemeral: lost on
restart, capped, and oldest-evicted. Durable record-keeping is the hash-only
history DB, not this store.
"""

from __future__ import annotations

import random
import secrets
import string
import threading
from dataclasses import dataclass, field

# Cap resident sessions so a long-running server cannot grow unbounded.
_MAX_SESSIONS = 200


@dataclass
class Pane:
    pane_id: str
    model_id: str
    label: str  # neutral blind label, e.g. "Model A"


@dataclass
class CompareSession:
    comp_id: str
    prompt: str
    blind: bool
    panes: list[Pane]
    revealed: bool = False
    voted_winner: str | None = None  # pane_id or "tie"

    def pane(self, pane_id: str) -> Pane | None:
        for p in self.panes:
            if p.pane_id == pane_id:
                return p
        return None


_SESSIONS: "dict[str, CompareSession]" = {}
_LOCK = threading.Lock()


def _labels(n: int) -> list[str]:
    # "Model A", "Model B", ... "Model Z", then "Model AA" (rare).
    out: list[str] = []
    for i in range(n):
        if i < 26:
            out.append(f"Model {string.ascii_uppercase[i]}")
        else:
            out.append(f"Model {string.ascii_uppercase[i // 26 - 1]}{string.ascii_uppercase[i % 26]}")
    return out


def create_session(prompt: str, model_ids: list[str], blind: bool) -> CompareSession:
    """Build a session. In blind mode the model->pane assignment is shuffled so
    the neutral label order is independent of the order the user picked models,
    and the real ids are withheld until reveal/vote."""
    ids = list(model_ids)
    if blind:
        random.shuffle(ids)
    labels = _labels(len(ids))
    panes = [
        Pane(pane_id=f"p{i}", model_id=mid, label=labels[i])
        for i, mid in enumerate(ids)
    ]
    comp_id = secrets.token_hex(8)
    session = CompareSession(comp_id=comp_id, prompt=prompt, blind=blind, panes=panes)
    with _LOCK:
        if len(_SESSIONS) >= _MAX_SESSIONS:
            # Evict oldest (dict preserves insertion order).
            oldest = next(iter(_SESSIONS))
            _SESSIONS.pop(oldest, None)
        _SESSIONS[comp_id] = session
    return session


def get_session(comp_id: str) -> CompareSession | None:
    with _LOCK:
        return _SESSIONS.get(comp_id)


def reveal(comp_id: str) -> CompareSession | None:
    with _LOCK:
        session = _SESSIONS.get(comp_id)
        if session is not None:
            session.revealed = True
        return session


def record_vote(comp_id: str, winner: str) -> CompareSession | None:
    """Record a vote ('tie' or a pane_id) and reveal. Returns the session, or
    None if the comp_id is unknown / the pane_id is invalid."""
    with _LOCK:
        session = _SESSIONS.get(comp_id)
        if session is None:
            return None
        if winner != "tie" and session.pane(winner) is None:
            return None
        session.voted_winner = winner
        session.revealed = True
        return session


def drop_session(comp_id: str) -> None:
    with _LOCK:
        _SESSIONS.pop(comp_id, None)
