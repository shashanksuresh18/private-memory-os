"""Batch-embed parity. HashEmbedder only — no Ollama / no network."""

from __future__ import annotations

from src.retrieval.embedder import HashEmbedder


def test_batch_matches_single():
    """embed_batch must return vectors bit-identical to per-text embed()."""
    emb = HashEmbedder()
    texts = ["a", "b", "c"]

    batched = emb.embed_batch(texts)
    singles = [emb.embed(t) for t in texts]

    assert batched == singles


def test_batch_empty():
    """Empty input -> empty output, no error."""
    assert HashEmbedder().embed_batch([]) == []


def test_batch_preserves_order_and_dim():
    """Order is preserved across a batch larger than one slice; dim fixed."""
    emb = HashEmbedder()
    texts = [f"chunk number {i}" for i in range(40)]  # > EMBED_BATCH_SIZE (32)

    batched = emb.embed_batch(texts)

    assert len(batched) == len(texts)
    assert all(len(v) == emb.dim for v in batched)
    assert batched == [emb.embed(t) for t in texts]
