"""S2 cloud-egress DLP guarantees for the answer composer.

The S2 answer path (`answer.answer_s2`) is the ONLY place a Tier-S2 citation
leaves the device: it redacts each citation locally, then forwards the redacted
skeleton to Nebius (DeepSeek). These tests pin the load-bearing invariant —
NOTHING that reaches the cloud transport (`_nebius_chat`) may contain a raw
email address — by capturing the exact text sent to the (mocked) cloud. No real
network is touched.

Worst-case framing: the citation text here carries RAW addresses (as if the
upstream fetch-time scrub had never run), so the test proves `answer_s2`'s own
`redact_pii` pass is sufficient on its own.
"""

from __future__ import annotations

import re

import src.retrieval.answer as answer_mod
from src.retrieval.engine import Citation

_RE_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _citation(text: str, tier: str = "S2") -> Citation:
    return Citation(
        chunk_id=1,
        page_slug="inbox/email_test",
        page_path="vault/inbox/email_test.md",
        tier=tier,
        byte_start=0,
        byte_end=len(text.encode("utf-8")),
        line_start=1,
        line_end=text.count("\n") + 1,
        score=1.0,
        text=text,
    )


def _capture_egress(monkeypatch) -> dict:
    """Replace the cloud transport with a capture stub; return the capture dict."""
    captured: dict = {}

    def _fake_nebius(model, user_content, system_prompt=answer_mod.SYSTEM_PROMPT):
        captured["model"] = model
        captured["content"] = user_content
        captured["system"] = system_prompt
        return "OK"

    monkeypatch.setattr(answer_mod, "_nebius_chat", _fake_nebius)
    monkeypatch.setenv("NEBIUS_API_KEY", "test-key")  # never used (transport mocked)
    return captured


def test_s2_answer_uses_scrubbed_text(monkeypatch):
    """No raw email address may reach the cloud transport."""
    captured = _capture_egress(monkeypatch)
    raw_email = "alice.jones@example.com"
    cit = _citation(f"Reach the analyst at {raw_email} about the report.")

    result = answer_mod.answer_s2("who is the analyst", [cit])

    egressed = captured["content"]
    assert raw_email not in egressed
    assert "@example.com" not in egressed
    assert not _RE_EMAIL.search(egressed), f"raw email leaked to cloud: {egressed!r}"
    assert "[EMAIL]" in egressed  # proof the scrub actually fired
    # The result is flagged redacted and routed to DeepSeek.
    assert result.redacted is True
    assert result.tier == "S2"
    assert captured["model"] == answer_mod.NEBIUS_MODEL


def test_s2_from_field_not_in_egress(monkeypatch):
    """The frontmatter `from:` sender address must not egress to the cloud."""
    captured = _capture_egress(monkeypatch)
    from_email = "jobalerts-noreply@linkedin.com"
    text = (
        "---\n"
        "tier: S2\n"
        f'from: "LinkedIn Job Alerts <{from_email}>"\n'
        "body: scrubbed\n"
        "---\n"
        "Your job alert for London roles."
    )
    cit = _citation(text)

    answer_mod.answer_s2("job alerts London", [cit])

    egressed = captured["content"]
    assert from_email not in egressed
    assert "@linkedin.com" not in egressed
    assert not _RE_EMAIL.search(egressed)


def test_s2_original_citation_text_not_mutated(monkeypatch):
    """Scrubbing must operate on a copy — the caller's citation stays intact."""
    _capture_egress(monkeypatch)
    raw_email = "bob@firm.com"
    cit = _citation(f"Contact {raw_email} now.")

    answer_mod.answer_s2("contact", [cit])

    assert raw_email in cit.text  # original untouched; only the egressed copy scrubbed
