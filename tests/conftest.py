"""Collection guards shared by the whole test tree.

The ``gating`` CI workflow (``.github/workflows/gate.yml``) installs a deliberately
small dependency set and runs ``pytest -m gating``. To discover which tests carry
the ``gating`` marker pytest must IMPORT every module under ``tests/`` first, so a
module that imports a dependency the gating job does not install raises
``ModuleNotFoundError`` at collection time and aborts the entire run -- even though
that module holds no gating tests.

The gating tests import the retrieval engine, whose import chain needs
``markitdown`` + ``python-dotenv``; the gating job installs those. Everything else
that a non-gating test drags in (the API stack, the Google client stack, the vault
watcher) is skip-collected here when absent. With the full dependency set installed
(local dev, the non-gating CI lanes) all of this is a no-op, so ``pytest``,
``pytest tests/api``, etc. behave exactly as before. No gating test depends on any
of the skipped modules, so nothing load-bearing is ever skipped.

Set ``CITADEL_FORCE_MINIMAL_DEPS=1`` to force the API-stack skip path locally (used
to verify this guard mirrors the gating runner).
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent


def _missing(module: str) -> bool:
    """True when ``module`` cannot be imported in this environment."""
    try:
        return importlib.util.find_spec(module) is None
    except ModuleNotFoundError:
        # find_spec raises (not returns None) when a parent package is absent,
        # e.g. "google.auth" when "google" itself is not installed.
        return True


# Non-gating test modules (path relative to tests/) that import a heavy optional
# dependency -- sometimes via a dynamically loaded script, so a source scan would
# not see it. Each is skip-collected only when its dependency is genuinely absent.
_OPTIONAL_DEP_MODULES = {
    "test_vault_bridge.py": "watchdog",      # dynamically loads src/mcp/vault-bridge/server.py
    "retrieval/test_dlp.py": "google.auth",  # dynamically loads scripts/fetch_gmail.py
}

# The API-stack modules import fastapi/requests directly, so a cheap source scan
# catches them (and any future sibling) without an explicit list.
_HAVE_API_STACK = (
    os.environ.get("CITADEL_FORCE_MINIMAL_DEPS") != "1"
    and not _missing("fastapi")
    and not _missing("requests")
)


def pytest_ignore_collect(collection_path, config):
    """Skip-collect test modules whose (optional) dependencies are unavailable.

    Returning ``True`` drops the path; ``None`` leaves default behaviour intact.
    """
    if collection_path.suffix != ".py":
        return None

    try:
        rel = collection_path.resolve().relative_to(_TESTS_DIR).as_posix()
    except ValueError:
        return None

    dep = _OPTIONAL_DEP_MODULES.get(rel)
    if dep is not None and _missing(dep):
        return True

    if not _HAVE_API_STACK:
        try:
            source = collection_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None
        if "fastapi" in source or "import requests" in source:
            return True

    return None
