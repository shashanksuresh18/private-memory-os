"""One-shot: re-scrub the `from:` sender line in existing S2 inbox email pages.

Closes the legacy exposure where S2 `email_*.md` files written before the
`sender_for_tier` fix carry a RAW `from:` address that would egress to Nebius in
the page's first chunk. Touches ONLY S2 pages and ONLY the `from:` line; body is
already scrubbed at write time. Idempotent (re-running on an already-scrubbed
file is a no-op). Reversible via re-fetch or the pre-scrub backup snapshot.

Preserves each file's original newline style (these pages are CRLF).
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "fetch_gmail", ROOT / "scripts" / "fetch_gmail.py"
)
fetch_gmail = importlib.util.module_from_spec(_SPEC)
sys.modules["fetch_gmail"] = fetch_gmail
_SPEC.loader.exec_module(fetch_gmail)

INBOX = ROOT / "vault" / "inbox"


def _scrub_file(path: Path) -> bool:
    """Re-scrub the `from:` line of an S2 page. Returns True if the file changed."""
    # keepends=True preserves the per-line newline (\r\n here) on write-back.
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return False
    is_s2 = False
    from_idx = None
    for i in range(1, len(lines)):
        stripped = lines[i].strip()
        if stripped == "---":
            break
        if stripped == "tier: S2":
            is_s2 = True
        elif stripped.startswith("from: "):
            from_idx = i
    if not is_s2 or from_idx is None:
        return False

    line = lines[from_idx]
    newline = line[len(line.rstrip("\r\n")):]  # preserve "\r\n" / "\n" / ""
    raw_val = line.rstrip("\r\n")[len("from: "):]
    try:
        sender = json.loads(raw_val)  # value is a json.dumps()'d string
    except json.JSONDecodeError:
        sender = raw_val  # tolerate an unquoted legacy value
    scrubbed = fetch_gmail.scrub_text(sender)
    if scrubbed == sender:
        return False
    lines[from_idx] = "from: " + json.dumps(scrubbed, ensure_ascii=False) + newline
    path.write_text("".join(lines), encoding="utf-8", newline="")
    return True


def main() -> None:
    s2 = 0
    changed = 0
    for path in sorted(INBOX.glob("email_*.md")):
        lines = path.read_text(encoding="utf-8").splitlines()
        if not any(l.strip() == "tier: S2" for l in lines[:15]):
            continue
        s2 += 1
        if _scrub_file(path):
            changed += 1
            print(f"scrubbed from: in {path.name}")
    print(f"S2 files scanned: {s2}; from: lines rewritten: {changed}")


if __name__ == "__main__":
    main()
