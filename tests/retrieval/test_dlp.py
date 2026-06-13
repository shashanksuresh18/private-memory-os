"""Tier S2 DLP scrub + S3 body-never-fetched guarantees for fetch_gmail.

Locked invariants exercised here:
- S3 emails: metadata only, forever. Body never fetched (no `format=full`
  request issued) and the page keeps `body: none`.
- S2 emails: body fetched, DLP-scrubbed (email/phone/postal/names/S3 terms)
  BEFORE any write. Raw S2 body never lands on disk.
- S1 emails: public data, body written as-is.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location(
    "fetch_gmail", ROOT / "scripts" / "fetch_gmail.py"
)
fetch_gmail = importlib.util.module_from_spec(_SPEC)
# Register before exec so dataclass() can resolve the module's __dict__.
sys.modules["fetch_gmail"] = fetch_gmail
_SPEC.loader.exec_module(fetch_gmail)


# ---------- scrub: S2 ----------

def test_s2_body_scrubbed():
    raw = "Reach me at alice.jones@example.com about the report."
    out = fetch_gmail.body_for_tier("S2", raw)
    assert "alice.jones@example.com" not in out
    assert "@example.com" not in out
    assert "[REDACTED_EMAIL]" in out


def test_s2_phone_scrubbed():
    raw = "Call me on +44 7700 900123 or 555-123-4567 tomorrow."
    out = fetch_gmail.body_for_tier("S2", raw)
    assert "900123" not in out
    assert "555-123-4567" not in out
    assert "[REDACTED_PHONE]" in out


def test_s2_postal_scrubbed():
    raw = "Office at SW1A 1AA, mail to 90210."
    out = fetch_gmail.body_for_tier("S2", raw)
    assert "SW1A 1AA" not in out
    assert "90210" not in out
    assert "[REDACTED_POSTAL]" in out


# ---------- from: field (egresses in the page's first chunk) ----------

def test_s2_from_field_scrubbed():
    """The `from:` sender lands in the S2 chunk that egresses to the cloud, so
    the raw address must be redacted there exactly like body content."""
    sender = '"LinkedIn Job Alerts <jobalerts-noreply@linkedin.com>"'
    page = fetch_gmail.render_page(
        tier="S2", date="d", sender=sender, subject="job alert", body=None,
    )
    assert "jobalerts-noreply@linkedin.com" not in page
    assert "@linkedin.com" not in page
    assert "[REDACTED_EMAIL]" in page
    # Direct helper contract.
    out = fetch_gmail.sender_for_tier("S2", sender)
    assert "jobalerts-noreply@linkedin.com" not in out
    assert "[REDACTED_EMAIL]" in out


def test_s1_from_field_raw():
    sender = '"Apple IR <ir@apple.com>"'
    assert fetch_gmail.sender_for_tier("S1", sender) == sender
    page = fetch_gmail.render_page(
        tier="S1", date="d", sender=sender, subject="public", body="public data",
    )
    assert "ir@apple.com" in page  # public, never scrubbed


# ---------- S1 ----------

def test_s1_body_unchanged():
    raw = "Apple reported revenue of $383B. Contact ir@apple.com."
    out = fetch_gmail.body_for_tier("S1", raw)
    assert out == raw  # public data, never scrubbed


# ---------- S3 ----------

def test_s3_body_for_tier_is_none():
    assert fetch_gmail.body_for_tier("S3", "anything secret") is None


def test_s3_render_keeps_body_none():
    page = fetch_gmail.render_page(
        tier="S3", date="d", sender="s", subject="acquisition talks",
        body=None,
    )
    assert "body: none" in page
    assert "tier: S3" in page


class _FakeExec:
    def __init__(self, value):
        self._value = value

    def execute(self):
        return self._value


class _FakeMessages:
    """Records every .get() call so the test can assert no S3 full fetch."""

    def __init__(self, listing, by_id, calls):
        self._listing = listing
        self._by_id = by_id
        self._calls = calls

    def list(self, **_kwargs):
        return _FakeExec(self._listing)

    def get(self, *, userId, id, **kwargs):  # noqa: N803 (Gmail API kwarg)
        self._calls.append({"id": id, "format": kwargs.get("format")})
        return _FakeExec(self._by_id[id][kwargs.get("format", "metadata")])


class _FakeUsers:
    def __init__(self, messages):
        self._messages = messages

    def messages(self):
        return self._messages


class _FakeService:
    def __init__(self, messages):
        self._users = _FakeUsers(messages)

    def users(self):
        return self._users


def test_s3_body_never_fetched(tmp_path, monkeypatch):
    """An S3-classified email must never trigger a `format=full` request."""
    calls: list[dict] = []
    # Subject "acquisition" -> S3 by classify_tier denylist.
    meta = {
        "payload": {
            "headers": [
                {"name": "Subject", "value": "Project acquisition update"},
                {"name": "From", "value": "boss@firm.com"},
                {"name": "Date", "value": "Wed, 03 Jun 2026 00:00:00 +0000"},
            ]
        }
    }
    by_id = {"m1": {"metadata": meta}}
    messages = _FakeMessages({"messages": [{"id": "m1"}]}, by_id, calls)
    service = _FakeService(messages)

    monkeypatch.setattr(fetch_gmail, "_accounts",
                        lambda: [fetch_gmail.GmailAccount("me", "tok")])
    monkeypatch.setattr(fetch_gmail, "_service", lambda _t: service)

    written = fetch_gmail.fetch(limit=1, outbox=tmp_path, with_body=True)

    assert len(written) == 1
    text = written[0].read_text(encoding="utf-8")
    assert "tier: S3" in text
    assert "body: none" in text
    # The crux: only the metadata get fired; no full body fetch for S3.
    assert calls == [{"id": "m1", "format": "metadata"}]
    assert all(c["format"] != "full" for c in calls)


def test_s2_full_fetch_scrubbed_to_disk(tmp_path, monkeypatch):
    """An S2 email fetches full body, but only the scrubbed text hits disk."""
    calls: list[dict] = []
    meta = {
        "payload": {
            "headers": [
                {"name": "Subject", "value": "lunch plans"},
                {"name": "From", "value": "pal@firm.com"},
                {"name": "Date", "value": "Wed, 03 Jun 2026 00:00:00 +0000"},
            ]
        }
    }
    import base64

    raw_body = "Ping me at secret.person@example.com or 555-987-6543."
    encoded = base64.urlsafe_b64encode(raw_body.encode()).decode()
    full = {"payload": {"mimeType": "text/plain", "body": {"data": encoded}}}
    by_id = {"m2": {"metadata": meta, "full": full}}
    messages = _FakeMessages({"messages": [{"id": "m2"}]}, by_id, calls)
    service = _FakeService(messages)

    monkeypatch.setattr(fetch_gmail, "_accounts",
                        lambda: [fetch_gmail.GmailAccount("me", "tok")])
    monkeypatch.setattr(fetch_gmail, "_service", lambda _t: service)

    written = fetch_gmail.fetch(limit=1, outbox=tmp_path, with_body=True)
    text = written[0].read_text(encoding="utf-8")

    assert "tier: S2" in text
    assert "body: scrubbed" in text
    assert "secret.person@example.com" not in text
    assert "555-987-6543" not in text
    assert "[REDACTED_EMAIL]" in text
    assert {"id": "m2", "format": "full"} in calls
