"""Verify Sovereign Citadel stack repos exist + are alive (Scrapling-based)."""
import json
import sys
import time
from datetime import datetime, timezone

from scrapling.fetchers import Fetcher

REPOS = [
    ("D4Vinci/Scrapling",                       "https://github.com/D4Vinci/Scrapling"),
    ("OpenBMB/EdgeClaw",                        "https://github.com/OpenBMB/EdgeClaw"),
    ("OpenBMB/ClawXRouter",                     "https://github.com/OpenBMB/ClawXRouter"),
    ("privacyshield-ai/privacy-firewall",       "https://github.com/privacyshield-ai/privacy-firewall"),
    ("tinyhumansai/openhuman",                  "https://github.com/tinyhumansai/openhuman"),
    ("garrytan/gbrain",                         "https://github.com/garrytan/gbrain"),
    ("affaan-m/ECC",                            "https://github.com/affaan-m/ECC"),
    ("massgen/MassGen",                         "https://github.com/massgen/MassGen"),
    ("safishamsi/graphify",                     "https://github.com/safishamsi/graphify"),
    ("jlevere/obsidian-mcp-plugin",             "https://github.com/jlevere/obsidian-mcp-plugin"),
    ("bitbonsai/mcpvault",                      "https://github.com/bitbonsai/mcpvault"),
    ("openai/privacy-filter",                   "https://github.com/openai/privacy-filter"),
]


def _first_attr(page, selector: str, attr: str) -> str:
    els = page.css(selector)
    if not els:
        return ""
    try:
        return (els[0].attrib.get(attr, "") or "").strip()
    except Exception:
        return ""


def _first_text(page, selector: str) -> str:
    els = page.css(selector)
    if not els:
        return ""
    try:
        return (els[0].text or "").strip()
    except Exception:
        return ""


def probe(name: str, url: str) -> dict:
    try:
        r = Fetcher.get(url, follow_redirects=True, stealthy_headers=True, timeout=20)
    except Exception as e:
        return {"name": name, "url": url, "status": "ERROR", "error": str(e)[:200]}

    status = r.status
    if status >= 400:
        return {"name": name, "url": url, "status": status, "exists": False}

    desc = (_first_attr(r, 'meta[name="description"]', "content")
            or _first_attr(r, 'meta[property="og:description"]', "content"))

    title = _first_text(r, "title")

    stars = _first_text(r, '#repo-stars-counter-star')
    if not stars:
        stars = _first_text(r, 'a[href$="/stargazers"] strong')

    forks = _first_text(r, '#repo-network-counter')

    last_commit = (_first_attr(r, 'relative-time', "datetime")
                   or _first_attr(r, 'time-ago', "datetime"))

    primary_lang = _first_text(r, '[itemprop="programmingLanguage"]')

    license_name = _first_text(r, 'a[href$="#license-ov-file"]')

    body = ""
    try:
        body = r.body.decode("utf-8", errors="ignore") if hasattr(r, "body") else ""
    except Exception:
        body = ""
    archived = "This repository has been archived" in body or "Public archive" in body

    return {
        "name": name,
        "url": url,
        "status": status,
        "exists": True,
        "title": title[:120],
        "description": desc[:200],
        "stars": stars,
        "forks": forks,
        "last_commit_utc": last_commit,
        "language": primary_lang,
        "license": license_name,
        "archived": archived,
    }


def main() -> int:
    results = []
    for name, url in REPOS:
        sys.stderr.write(f"probing {name} ...\n")
        sys.stderr.flush()
        results.append(probe(name, url))
        time.sleep(1.0)

    out = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "repos": results,
    }
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
