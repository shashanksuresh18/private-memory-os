"""Collection guards shared by the whole test tree.

The ``gating`` CI workflow (``.github/workflows/gate.yml``) installs a
deliberately minimal dependency set -- ``pytest tiktoken httpx`` -- and runs
``pytest -m gating``. To discover which tests carry the ``gating`` marker pytest
must IMPORT every module under ``tests/`` first, so a module that imports the API
stack (``fastapi`` / ``requests``) raises ``ModuleNotFoundError`` at collection
time and fails the entire run -- even though it holds no gating tests.

When that stack is absent we skip-collect exactly those modules. With the full
dependency set installed (local dev, the non-gating CI lanes) this is a no-op:
``pytest``, ``pytest tests/api``, etc. behave exactly as before. None of the
gating tests import the API stack, so nothing load-bearing is ever skipped.

Set ``CITADEL_FORCE_MINIMAL_DEPS=1`` to exercise the skip path locally (used to
verify this guard mirrors the gating runner).
"""

from __future__ import annotations

import importlib.util
import os

_API_STACK = ("fastapi", "requests")
_HAVE_API_STACK = (
    os.environ.get("CITADEL_FORCE_MINIMAL_DEPS") != "1"
    and all(importlib.util.find_spec(m) is not None for m in _API_STACK)
)


def pytest_ignore_collect(collection_path, config):
    """Skip API-stack test modules when fastapi/requests are not installed.

    Returning ``True`` drops the path from collection; ``None`` leaves the
    default behaviour untouched.
    """
    if _HAVE_API_STACK or collection_path.suffix != ".py":
        return None
    try:
        source = collection_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    # A module that imports the API stack cannot be collected without it.
    if "fastapi" in source or "import requests" in source:
        return True
    return None
