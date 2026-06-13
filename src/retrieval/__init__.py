"""Sovereign Citadel retrieval engine — local hybrid RRF.

Canonical surface. Engine is ours, in Python. gbrain is a sidecar and never
appears on the answer path.

Offset unit invariant: BYTE offsets throughout (chunker emit -> DB store ->
source-span reopen). Never char offsets. Never token offsets.
"""

from .engine import retrieve, ingest

__all__ = ["retrieve", "ingest"]
