"""Start the Obsidian vault bridge: watch vault/ and incrementally ingest
changed markdown into the canonical retrieval DB. Runs until Ctrl+C.

Production embedder is selected via RETRIEVAL_EMBEDDER (.env sets `ollama` so
new chunks land in the same nomic-embed-text space as the canonical index).
"""

from __future__ import annotations

import importlib.util
import logging
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VAULT = ROOT / "vault"

# Running `python scripts/start_vault_bridge.py` puts scripts/ on sys.path, not
# the repo root, so the bridge's `from src.retrieval ...` imports fail. Prepend
# the repo root so `src` is importable regardless of the launch cwd.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_bridge():
    # server.py lives under src/mcp/vault-bridge/ — the hyphen makes it
    # non-importable as a dotted module, so load it from its file path.
    server_path = ROOT / "src" / "mcp" / "vault-bridge" / "server.py"
    spec = importlib.util.spec_from_file_location("vault_bridge_server", server_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # Load .env so RETRIEVAL_EMBEDDER=ollama (and OLLAMA_* / paths) take effect,
    # matching the API server. Best-effort: no hard dependency on python-dotenv.
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
    except Exception:  # noqa: BLE001
        pass

    bridge = _load_bridge()
    observer = bridge.build_observer(VAULT)
    observer.start()
    print("Vault bridge running — watching vault/")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\nVault bridge stopped.")
    observer.join()


if __name__ == "__main__":
    main()
