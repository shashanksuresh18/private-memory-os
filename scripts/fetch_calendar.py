"""Fetch Google Calendar event METADATA only into vault/inbox/ as S2 pages.

Mirrors scripts/fetch_gmail.py: read-only OAuth, metadata-only, never the event
description/body. Window = today through +7 days. All calendar events are tier
S2 (meeting metadata is not public, but not MNPI). Event bodies are never read
or written — only title / time / attendees / location.

Usage:
    python scripts/fetch_calendar.py
    python scripts/fetch_calendar.py --limit 50 --days 7
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
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
SCOPES = ("https://www.googleapis.com/auth/calendar.readonly",)
# Every calendar event is S2 by policy — meeting metadata is sensitive but not
# MNPI. No subject-denylist S3 escalation here (unlike gmail): we never read the
# event body, so there is no field to scan for material non-public content.
CALENDAR_TIER = "S2"


def _env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing {name}")
    return value


def _credentials() -> Credentials:
    return Credentials(
        token=None,
        refresh_token=_env("CALENDAR_REFRESH_TOKEN"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=_env("CALENDAR_CLIENT_ID"),
        client_secret=_env("CALENDAR_CLIENT_SECRET"),
    )


def _service():
    return build("calendar", "v3", credentials=_credentials(), cache_discovery=False)


def _yaml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _safe_id(event_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", event_id).strip("._")
    if not safe:
        raise RuntimeError("Calendar event id produced an empty filename")
    return safe[:160]


def _when(node: dict[str, Any]) -> str:
    """Return an event start/end as a string. Timed events carry `dateTime`,
    all-day events carry `date`. Either way it is metadata, never the body."""
    return str(node.get("dateTime") or node.get("date") or "")


def _event_date(start: dict[str, Any]) -> str:
    """YYYY-MM-DD for the filename + `date:` field, from start.dateTime|date."""
    raw = _when(start)
    return raw[:10] if raw else "unknown"


def _attendees(event: dict[str, Any]) -> str:
    emails = [
        str(a.get("email", "")).strip()
        for a in (event.get("attendees") or [])
        if a.get("email")
    ]
    return ", ".join(emails) if emails else "none"


def _page(
    *, date: str, title: str, start: str, end: str, attendees: str, location: str
) -> str:
    """Frontmatter + a DERIVED one-line summary built only from metadata fields.

    `body: none` still holds — we never read or write the event's own
    description. The summary is synthesised from title/date/attendees/location
    so sparse calendar pages carry retrievable lexical tokens ('calendar',
    'meeting', 'meetings', plus the title/people/place) and survive the server's
    token-overlap relevance gate for natural meeting queries.
    """
    frontmatter = (
        "---\n"
        f"tier: {CALENDAR_TIER}\n"
        "source: calendar\n"
        f"date: {_yaml_string(date)}\n"
        f"title: {_yaml_string(title)}\n"
        f"start: {_yaml_string(start)}\n"
        f"end: {_yaml_string(end)}\n"
        f"attendees: {_yaml_string(attendees)}\n"
        f"location: {_yaml_string(location)}\n"
        "body: none\n"
        "---\n"
    )
    summary = (
        f"\nCalendar meeting entry. Upcoming meetings: {title} on {date} "
        f"from {start} to {end}. Attendees: {attendees}. Location: {location}.\n"
    )
    return frontmatter + summary


def fetch_events(limit: int = 50, days: int = 7, outbox: Path = OUTBOX) -> list[Path]:
    outbox.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    now = datetime.now(timezone.utc)
    time_min = now.replace(hour=0, minute=0, second=0, microsecond=0)
    time_max = time_min + timedelta(days=days + 1)

    service = _service()
    try:
        listing = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=time_min.isoformat(),
                timeMax=time_max.isoformat(),
                maxResults=min(limit, 50),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
    except (RefreshError, HttpError) as exc:
        print(f"calendar fetch failed: {exc.__class__.__name__}")
        return written

    for event in listing.get("items", [])[:limit]:
        event_id = event.get("id")
        if not event_id:
            continue
        start = event.get("start") or {}
        end = event.get("end") or {}
        event_date = _event_date(start)
        # timeMin already excludes anything before today; this is a belt-and-
        # suspenders guard for all-day events on a TZ boundary.
        if event_date != "unknown" and event_date < time_min.strftime("%Y-%m-%d"):
            continue

        filename = f"calendar_{event_date}_{_safe_id(event_id)}.md"
        path = outbox / filename
        path.write_text(
            _page(
                date=event_date,
                title=event.get("summary", "(no title)"),
                start=_when(start),
                end=_when(end),
                attendees=_attendees(event),
                location=event.get("location", "none") or "none",
            ),
            encoding="utf-8",
        )
        written.append(path)

    return written


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch Google Calendar event metadata only into vault/inbox."
    )
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--outbox", type=Path, default=OUTBOX)
    args = parser.parse_args()

    load_dotenv(ENV_PATH)
    paths = fetch_events(limit=args.limit, days=args.days, outbox=args.outbox)
    print(f"wrote {len(paths)} calendar metadata files")
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
