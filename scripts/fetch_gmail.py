from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


ROOT = Path(__file__).resolve().parents[1]
# Run-as-script: put repo root on the path so `import src...` resolves
# regardless of the caller's cwd.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
ENV_PATH = ROOT / ".env"
OUTBOX = ROOT / "vault" / "inbox"
SCOPES = ("https://www.googleapis.com/auth/gmail.readonly",)
METADATA_HEADERS = ("From", "Subject", "Date")
DENYLIST_DIR = Path(
    os.environ.get(
        "CITADEL_DENYLIST_DIR",
        str(ROOT / "src" / "routing" / "classifier" / "denylist"),
    )
)
S3_SUBJECT_DENYLIST = (
    "acquisition",
    "merger",
    "MNPI",
    "board",
    "material",
    "non-public",
    "confidential deal",
)

# ---------- DLP scrub patterns (Tier S2) ----------
# Mirrors the classifier's PII regexes (src/routing/classifier/main.py) plus
# UK/US postal + UK phone shapes. Used to sanitise S2 bodies BEFORE any write.
RE_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
RE_PHONE_US = re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
# UK: +44 / 0044 / leading 0, then 9-10 digits with optional spaces.
RE_PHONE_UK = re.compile(r"(?:\+?44\s?|\b0)(?:\d\s?){9,10}\d\b")
# UK postcode: e.g. SW1A 1AA, EC1A 1BB, M1 1AE.
RE_POSTAL_UK = re.compile(
    r"\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b", re.IGNORECASE
)
# US ZIP / ZIP+4.
RE_POSTAL_US = re.compile(r"\b\d{5}(?:-\d{4})?\b")

# Common-name denylist seed. Extend at runtime via a `names.txt` in DENYLIST_DIR
# (one name per line, '#' comments ignored). Whole-word, case-insensitive.
NAME_DENYLIST = (
    "John Smith",
    "Jane Doe",
    "Alice",
    "Bob",
)


@dataclass(frozen=True)
class GmailAccount:
    email: str
    refresh_token: str


def _env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing {name}")
    return value


def _accounts() -> list[GmailAccount]:
    raw = os.environ.get("GMAIL_ACCOUNTS_JSON")
    if raw:
        parsed = json.loads(raw)
        if not isinstance(parsed, list) or not parsed:
            raise RuntimeError("GMAIL_ACCOUNTS_JSON must be a non-empty JSON array")
        accounts: list[GmailAccount] = []
        for idx, item in enumerate(parsed):
            if not isinstance(item, dict):
                raise RuntimeError(f"GMAIL_ACCOUNTS_JSON[{idx}] must be an object")
            email = str(item.get("email") or item.get("account") or "me")
            refresh_token = item.get("refresh_token") or item.get("refreshToken")
            if not refresh_token:
                raise RuntimeError(f"GMAIL_ACCOUNTS_JSON[{idx}] is missing refresh_token")
            accounts.append(GmailAccount(email=email, refresh_token=str(refresh_token)))
        return accounts

    return [GmailAccount(email="me", refresh_token=_env("GMAIL_REFRESH_TOKEN"))]


def _credentials(refresh_token: str) -> Credentials:
    return Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=_env("GMAIL_CLIENT_ID"),
        client_secret=_env("GMAIL_CLIENT_SECRET"),
    )


def _service(refresh_token: str):
    creds = _credentials(refresh_token)
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _headers(message: dict[str, Any]) -> dict[str, str]:
    payload = message.get("payload") or {}
    headers = payload.get("headers") or []
    out: dict[str, str] = {}
    for header in headers:
        name = str(header.get("name", "")).lower()
        if name in {"from", "subject", "date"}:
            out[name] = str(header.get("value", ""))
    return out


# ---------- denylist (shared with the classifier) ----------

def _read_terms(path: Path) -> frozenset[str]:
    if not path.exists():
        return frozenset()
    out: set[str] = set()
    for ln in path.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        out.add(ln)
    return frozenset(out)


def _s3_denylist_terms() -> frozenset[str]:
    """Codenames + markers + tickers — any hit forces S3 (fail-closed)."""
    return (
        _read_terms(DENYLIST_DIR / "codenames.txt")
        | _read_terms(DENYLIST_DIR / "markers.txt")
        | _read_terms(DENYLIST_DIR / "tickers.txt")
    )


def _name_terms() -> frozenset[str]:
    return frozenset(NAME_DENYLIST) | _read_terms(DENYLIST_DIR / "names.txt")


def classify_tier(subject: str) -> str:
    subject_lower = subject.lower()
    for term in S3_SUBJECT_DENYLIST:
        if term.lower() in subject_lower:
            return "S3"
    return "S2"


def body_forces_s3(text: str) -> bool:
    """True if a fetched body contains an MNPI codename/marker/ticker.

    Defence-in-depth: subject classification only sees the subject line; a body
    that carries S3 signal must escalate the whole page to S3 (body never
    written, never embedded) rather than relying on scrub alone. Fail-closed.
    """
    if not text:
        return False
    folded = text.casefold()
    for term in _s3_denylist_terms():
        if re.search(rf"\b{re.escape(term.casefold())}\b", folded):
            return True
    return False


def scrub_text(text: str) -> str:
    """Strip PII + S3 denylist terms from an S2 body before it is written.

    Removes: email addresses, US/UK phone numbers, US/UK postal codes,
    denylisted names, and any residual S3 denylist term. S2 bodies are the only
    bodies that egress (DLP-redacted), so this is the load-bearing gate.
    """
    if not text:
        return text
    out = text
    out = RE_EMAIL.sub("[REDACTED_EMAIL]", out)
    out = RE_PHONE_UK.sub("[REDACTED_PHONE]", out)
    out = RE_PHONE_US.sub("[REDACTED_PHONE]", out)
    out = RE_POSTAL_UK.sub("[REDACTED_POSTAL]", out)
    out = RE_POSTAL_US.sub("[REDACTED_POSTAL]", out)
    for term in _name_terms():
        out = re.sub(rf"(?i)\b{re.escape(term)}\b", "[REDACTED_NAME]", out)
    # Belt-and-suspenders: any S3 term that survived escalation gets nuked.
    for term in _s3_denylist_terms():
        out = re.sub(rf"(?i)\b{re.escape(term)}\b", "[REDACTED]", out)
    return out


def sender_for_tier(tier: str, sender: str) -> str:
    """Return the `from:` value to write for a tier.

    The `from:` field lands in the page's first chunk, so for S2 it egresses to
    the cloud alongside the scrubbed body. Scrub it the same way: strip the raw
    address (and any other PII) so only a redacted skeleton leaves the device.
    S1 -> raw (public). S3 -> raw (local-only, never egresses; full fidelity).
    unknown -> scrubbed (fail-closed).
    """
    if tier in ("S1", "S3"):
        return sender
    return scrub_text(sender or "")


def body_for_tier(tier: str, raw_body: str | None) -> str | None:
    """Return the body text to write for a tier, or None to write `body: none`.

    S3 -> None (never written, never fetched upstream).
    S2 -> DLP-scrubbed.
    S1 -> raw (public data).
    unknown -> None (fail-closed).
    """
    if tier == "S1":
        return raw_body
    if tier == "S2":
        return scrub_text(raw_body or "")
    return None  # S3 + anything unexpected


# ---------- body extraction ----------

def _clean_utf8(text: str) -> str:
    """Drop anything that can't round-trip through UTF-8 (lone surrogates, stray
    bytes) so the chunker's byte-offset slicing never hits a decode error."""
    return text.encode("utf-8", errors="replace").decode("utf-8", errors="replace")


def _decode_b64url(data: str) -> str:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad).decode("utf-8", errors="replace")


def extract_plaintext(payload: dict[str, Any]) -> str:
    """Walk a Gmail message payload and return the text/plain body.

    Prefers text/plain; falls back to a crude tag-strip of text/html if no
    plain part exists. Returns '' when no textual body is present.
    """
    if not payload:
        return ""
    mime = str(payload.get("mimeType", ""))
    body = payload.get("body") or {}
    data = body.get("data")
    if mime == "text/plain" and data:
        return _clean_utf8(_decode_b64url(data))
    parts = payload.get("parts") or []
    # First pass: any text/plain anywhere in the tree.
    for part in parts:
        text = extract_plaintext(part)
        if text:
            return text
    # Fallback: strip tags from a top-level text/html body.
    if mime == "text/html" and data:
        return _clean_utf8(re.sub(r"<[^>]+>", " ", _decode_b64url(data)))
    return ""


def _yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _safe_id(message_id: str, account: str) -> str:
    base = f"{account}_{message_id}" if account != "me" else message_id
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", base).strip("._")
    if not safe:
        raise RuntimeError("Gmail message id produced an empty filename")
    return safe[:180]


def _frontmatter(*, tier: str, date: str, sender: str, subject: str,
                 body_status: str = "none") -> str:
    return (
        "---\n"
        f"tier: {tier}\n"
        "source: gmail\n"
        f"date: {_yaml_string(date)}\n"
        f"from: {_yaml_string(sender)}\n"
        f"subject: {_yaml_string(subject)}\n"
        f"body: {body_status}\n"
        "---\n"
    )


def render_page(*, tier: str, date: str, sender: str, subject: str,
                body: str | None) -> str:
    """Build the vault page. Body (when present) lands after the frontmatter as
    markdown content; the `body:` field becomes a status flag (none/scrubbed/raw).
    """
    sender = sender_for_tier(tier, sender)
    if body is None or not body.strip():
        return _frontmatter(
            tier=tier, date=date, sender=sender, subject=subject,
            body_status="none",
        )
    status = "raw" if tier == "S1" else "scrubbed"
    fm = _frontmatter(
        tier=tier, date=date, sender=sender, subject=subject, body_status=status,
    )
    return f"{fm}\n{body.strip()}\n"


def fetch(limit: int = 20, outbox: Path = OUTBOX, with_body: bool = False) -> list[Path]:
    outbox.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for account in _accounts():
        remaining = limit - len(written)
        if remaining <= 0:
            break
        service = _service(account.refresh_token)
        try:
            listing = (
                service.users()
                .messages()
                .list(userId="me", maxResults=remaining)
                .execute()
            )
        except (RefreshError, HttpError) as exc:
            print(f"skipped account {account.email}: {exc.__class__.__name__}")
            continue

        for item in listing.get("messages", [])[:remaining]:
            message_id = item["id"]
            try:
                message = (
                    service.users()
                    .messages()
                    .get(
                        userId="me",
                        id=message_id,
                        format="metadata",
                        metadataHeaders=list(METADATA_HEADERS),
                    )
                    .execute()
                )
            except (RefreshError, HttpError) as exc:
                print(f"skipped message {message_id}: {exc.__class__.__name__}")
                continue
            headers = _headers(message)
            subject = headers.get("subject", "")
            tier = classify_tier(subject)

            body: str | None = None
            # S3 INVARIANT: never fetch the body of an S3 email. The full
            # message is only requested when with_body AND tier is not S3.
            if with_body and tier != "S3":
                try:
                    full = (
                        service.users()
                        .messages()
                        .get(userId="me", id=message_id, format="full")
                        .execute()
                    )
                    raw_body = extract_plaintext(full.get("payload") or {})
                except (RefreshError, HttpError) as exc:
                    print(f"body skipped {message_id}: {exc.__class__.__name__}")
                    raw_body = ""
                # Fail-closed: a body carrying S3 signal escalates to S3 and is
                # discarded (never written, never embedded).
                if body_forces_s3(raw_body):
                    tier = "S3"
                    body = None
                else:
                    body = body_for_tier(tier, raw_body)

            filename = f"email_{_safe_id(message_id, account.email)}.md"
            path = outbox / filename
            path.write_text(
                render_page(
                    tier=tier,
                    date=headers.get("date", ""),
                    sender=headers.get("from", ""),
                    subject=subject,
                    body=body,
                ),
                encoding="utf-8",
            )
            written.append(path)

    return written


# Back-compat alias (Session 1 callers).
def fetch_metadata(limit: int = 20, outbox: Path = OUTBOX) -> list[Path]:
    return fetch(limit=limit, outbox=outbox, with_body=False)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch Gmail into vault/inbox. Metadata-only by default; "
        "--with-body fetches + DLP-scrubs S1/S2 bodies (S3 stays metadata-only)."
    )
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--outbox", type=Path, default=OUTBOX)
    parser.add_argument(
        "--with-body",
        action="store_true",
        help="Fetch body for S1/S2 emails (scrubbed for S2). S3 never fetched.",
    )
    args = parser.parse_args()

    load_dotenv(ENV_PATH)
    paths = fetch(limit=args.limit, outbox=args.outbox, with_body=args.with_body)
    print(f"wrote {len(paths)} gmail files")
    if paths:
        _incremental_ingest()


def _incremental_ingest() -> None:
    """Append the newly fetched pages to retrieval.db without dropping or
    re-embedding the existing index (reset=False, incremental=True)."""
    from src.retrieval.db import DEFAULT_DB_PATH
    from src.retrieval.embedder import OllamaEmbedder
    from src.retrieval.index import ingest_vault

    stats = ingest_vault(
        ROOT / "vault",
        str(DEFAULT_DB_PATH),
        embedder=OllamaEmbedder(),
        reset=False,
        incremental=True,
    )
    print(
        f"incremental ingest: +{stats['pages']} pages, "
        f"+{stats['chunks']} chunks, {stats['skipped']} skipped"
    )


if __name__ == "__main__":
    main()
