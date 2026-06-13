"""Local cross-encoder reranker. P1 step 5 of the hybrid pipeline.

Two implementations behind a single `Reranker` protocol:

- `CrossEncoderReranker`: `BAAI/bge-reranker-base` via sentence-transformers
  CrossEncoder, FP32 on CPU. Weights are required to be present in the
  Hugging Face cache; the loader runs with `local_files_only=True` so no
  network fetch can happen on the S3 path. Constructor raises if the model
  is not cached.

- `DeterministicReranker`: token-overlap scorer, network-free, used in tests
  and the deterministic-acceptance path. No model load, no allocations
  beyond the input list.

`rerank(reranker, query, candidates, k_out)` is the call-site helper used
by `engine.retrieve` between `rrf_merge` and source-span reopen.

S3 invariant: the reranker call MUST NOT open any non-loopback socket.
Enforced structurally (no HTTP client constructed in this module) and
verified by `tests/retrieval/test_no_egress_on_s3.py` under socket monkeypatch.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Protocol, Sequence, Tuple


@dataclass(frozen=True)
class RerankCandidate:
    chunk_id: int
    text: str


class Reranker(Protocol):
    name: str

    def score(self, query: str, candidates: Sequence[RerankCandidate]) -> List[float]: ...


class DeterministicReranker:
    """Network-free token-overlap reranker.

    Score = |query_tokens ∩ candidate_tokens| / sqrt(|query_tokens| * |candidate_tokens|).
    Stable across runs; same inputs -> same score.
    """

    name = "deterministic"

    def score(self, query: str, candidates: Sequence[RerankCandidate]) -> List[float]:
        q = set(query.lower().split())
        out: List[float] = []
        for c in candidates:
            t = set(c.text.lower().split())
            if not q or not t:
                out.append(0.0)
                continue
            overlap = len(q & t)
            denom = (len(q) * len(t)) ** 0.5
            out.append(overlap / denom)
        return out


class CrossEncoderReranker:
    """Local cross-encoder via sentence-transformers, FP32 CPU.

    Default model: `BAAI/bge-reranker-base`. The model MUST already be
    present in the Hugging Face cache; we open it with `local_files_only=True`
    so a missing cache fails loudly rather than reaching the network.

    Loaded once, cached at module level via `_get_cross_encoder`.
    """

    name = "bge-reranker-base"
    DEFAULT_MODEL = "BAAI/bge-reranker-base"

    def __init__(self, model_name: str = DEFAULT_MODEL, device: str = "cpu") -> None:
        self.model_name = model_name
        self.device = device
        # Force offline mode at the transformers / hub layer for defense
        # in depth. The S3 path must never touch hf.co.
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        self._model = _get_cross_encoder(model_name, device)

    def score(self, query: str, candidates: Sequence[RerankCandidate]) -> List[float]:
        if not candidates:
            return []
        pairs = [[query, c.text] for c in candidates]
        raw = self._model.predict(pairs, show_progress_bar=False, batch_size=16)
        try:
            return [float(x) for x in raw]
        except TypeError:
            return [float(raw)]


_CROSS_ENCODER_CACHE: dict[Tuple[str, str], object] = {}


def _get_cross_encoder(model_name: str, device: str):
    key = (model_name, device)
    if key in _CROSS_ENCODER_CACHE:
        return _CROSS_ENCODER_CACHE[key]
    from sentence_transformers import CrossEncoder  # local import; heavy

    model = CrossEncoder(
        model_name,
        device=device,
        local_files_only=True,
    )
    _CROSS_ENCODER_CACHE[key] = model
    return model


def rerank(
    reranker: Reranker,
    query: str,
    candidates: Sequence[RerankCandidate],
    k_out: int = 10,
) -> List[Tuple[int, float]]:
    """Rerank `candidates`; return top-`k_out` as (chunk_id, score) ordered
    best-first. Deterministic when the underlying scorer is deterministic.
    """
    if not candidates:
        return []
    scores = reranker.score(query, candidates)
    if len(scores) != len(candidates):
        raise RuntimeError(
            f"reranker returned {len(scores)} scores for {len(candidates)} candidates"
        )
    paired = list(zip((c.chunk_id for c in candidates), scores))
    paired.sort(key=lambda x: x[1], reverse=True)
    return paired[:k_out]
