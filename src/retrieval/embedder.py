"""Local embedder. Ollama nomic-embed-text by default. Deterministic hash
embedder for tests and offline acceptance — no network at all.

Both paths return float32 numpy arrays of fixed dim. Storage is raw BLOB.
"""

from __future__ import annotations

import hashlib
import os
import struct
from typing import List, Protocol

import httpx

NOMIC_DIM = 768
HASH_DIM = 768
OLLAMA_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_EMBED_MODEL = os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text")


EMBED_BATCH_SIZE = 32


class Embedder(Protocol):
    dim: int

    def embed(self, text: str) -> List[float]: ...

    def embed_batch(self, texts: List[str]) -> List[List[float]]: ...


class HashEmbedder:
    """Deterministic, network-free embedder for tests and acceptance runs.

    Bag-of-words style hashing into `dim` buckets, then L2-normalized.
    Same input bytes -> bit-identical vector. Different inputs produce
    distinguishable vectors via SHA-256 token hashing.
    """

    def __init__(self, dim: int = HASH_DIM) -> None:
        self.dim = dim

    def embed(self, text: str) -> List[float]:
        vec = [0.0] * self.dim
        for token in text.lower().split():
            h = hashlib.sha256(token.encode("utf-8")).digest()
            for i in range(0, len(h), 4):
                bucket_word = int.from_bytes(h[i : i + 4], "big")
                bucket = bucket_word % self.dim
                sign = 1.0 if (bucket_word >> 31) & 1 else -1.0
                vec[bucket] += sign
        norm = sum(v * v for v in vec) ** 0.5
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Loop over embed() — no network, keeps interface parity with Ollama."""
        return [self.embed(t) for t in texts]


class OllamaEmbedder:
    """Calls 127.0.0.1:11434/api/embed for nomic-embed-text. Loopback only.

    Construction does not perform any network I/O. `embed()` raises on any
    non-loopback URL — this is a defense-in-depth check; URL is sourced from
    env which an operator controls.
    """

    def __init__(self, dim: int = NOMIC_DIM, url: str = OLLAMA_URL, model: str = OLLAMA_EMBED_MODEL) -> None:
        self.dim = dim
        self.url = url
        self.model = model
        if not (url.startswith("http://127.0.0.1") or url.startswith("http://localhost")):
            raise RuntimeError(f"OllamaEmbedder refuses non-loopback url: {url}")

    def _post_embed(self, value, read_timeout: float = 90.0):
        # CPU embedding of a 512-token chunk runs ~2-3s; a cold model load or
        # transient stall can spike well past that. Give a generous read budget
        # and retry once on a read timeout so a single slow call never aborts a
        # multi-hundred-chunk ingest. Still loopback-only — no egress widened.
        # `value` is a str (single) or list[str] (batch); Ollama /api/embed
        # returns `embeddings` as a list either way. Ollama embeds a batch
        # SEQUENTIALLY, so a 32-chunk batch needs ~32x a single call's budget —
        # the caller scales `read_timeout` by batch size to avoid a false abort.
        timeout = httpx.Timeout(read_timeout, connect=10.0)
        payload = {"model": self.model, "input": value}
        for attempt in range(2):
            try:
                with httpx.Client(timeout=timeout) as client:
                    r = client.post(f"{self.url}/api/embed", json=payload)
                    r.raise_for_status()
                    return r.json()
            except httpx.ReadTimeout:
                if attempt == 1:
                    raise

    def embed(self, text: str) -> List[float]:
        data = self._post_embed(text)
        vec = data["embeddings"][0] if "embeddings" in data else data["embedding"]
        if len(vec) != self.dim:
            raise RuntimeError(f"embedding dim mismatch: {len(vec)} != {self.dim}")
        return vec

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed many texts with one HTTP call per `EMBED_BATCH_SIZE` slice.

        Cuts per-chunk request overhead on a full reingest. Order of returned
        vectors matches `texts`. Loopback only — same /api/embed path as embed().
        """
        out: List[List[float]] = []
        for start in range(0, len(texts), EMBED_BATCH_SIZE):
            batch = texts[start : start + EMBED_BATCH_SIZE]
            # Ollama embeds the batch sequentially; budget ~6s/chunk over a 90s
            # floor so a full-size batch of large chunks never trips the timeout.
            read_timeout = max(90.0, len(batch) * 6.0)
            data = self._post_embed(batch, read_timeout=read_timeout)
            vecs = data["embeddings"]
            if len(vecs) != len(batch):
                raise RuntimeError(
                    f"batch size mismatch: {len(vecs)} != {len(batch)}"
                )
            for vec in vecs:
                if len(vec) != self.dim:
                    raise RuntimeError(
                        f"embedding dim mismatch: {len(vec)} != {self.dim}"
                    )
                out.append(vec)
        return out


def make_embedder(name: str | None = None) -> Embedder:
    """Resolve an embedder by name, falling back to the RETRIEVAL_EMBEDDER env.

    Default is ``hash`` (deterministic, network-free) so unit tests and the S3
    no-egress gating path never touch the network unless an operator opts in.
    Production ingest + the live API server set ``RETRIEVAL_EMBEDDER=ollama`` so
    queries hit the same nomic-embed-text space the canonical index was built in.
    """
    resolved = (name or os.environ.get("RETRIEVAL_EMBEDDER", "hash")).lower()
    if resolved in ("ollama", "nomic"):
        return OllamaEmbedder()
    if resolved == "hash":
        return HashEmbedder()
    raise ValueError(f"unknown embedder {resolved!r}")


def pack_vector(vec: List[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


def unpack_vector(blob: bytes) -> List[float]:
    n = len(blob) // 4
    return list(struct.unpack(f"{n}f", blob))


def cosine(a: List[float], b: List[float]) -> float:
    s = 0.0
    for x, y in zip(a, b):
        s += x * y
    return s
