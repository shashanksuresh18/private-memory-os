"""Bus-factor + risk metrics via Scrapling.

For each repo, hits:
  - GitHub repo home page (stars, last commit, language, license, archived)
  - /graphs/contributors page (contributor count)
  - /issues (open issue count)
  - /releases (latest release tag + date)
"""
import json
import re
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


def _fetch(url: str):
    try:
        return Fetcher.get(url, follow_redirects=True, stealthy_headers=True, timeout=20)
    except Exception as e:
        return e


def probe_repo(name: str, url: str) -> dict:
    home = _fetch(url)
    if isinstance(home, Exception) or home.status >= 400:
        status = "ERROR" if isinstance(home, Exception) else home.status
        return {"name": name, "url": url, "status": status, "exists": False}

    body = home.body.decode("utf-8", errors="ignore") if hasattr(home, "body") else ""
    archived = "This repository has been archived" in body or "Public archive" in body

    stars = _first_text(home, '#repo-stars-counter-star') or _first_attr(home, '#repo-stars-counter-star', "title")
    stars_exact = _first_attr(home, '#repo-stars-counter-star', "title")
    forks = _first_text(home, '#repo-network-counter') or _first_attr(home, '#repo-network-counter', "title")
    last_commit = _first_attr(home, 'relative-time', "datetime")
    desc = (_first_attr(home, 'meta[name="description"]', "content")
            or _first_attr(home, 'meta[property="og:description"]', "content"))
    license_name = _first_text(home, 'a[href$="#license-ov-file"]')
    title = _first_text(home, "title")

    open_issues = _first_text(home, '#issues-repo-tab-count') or _first_attr(home, '#issues-repo-tab-count', "title")
    open_prs    = _first_text(home, '#pull-requests-repo-tab-count') or _first_attr(home, '#pull-requests-repo-tab-count', "title")

    contributors = ""
    contrib_url = url.rstrip("/") + "/graphs/contributors"
    contrib_page = _fetch(contrib_url)
    if not isinstance(contrib_page, Exception) and contrib_page.status == 200:
        cbody = contrib_page.body.decode("utf-8", errors="ignore") if hasattr(contrib_page, "body") else ""
        m = re.search(r'data-target="contributors-list\.totalContributors"[^>]*>\s*([0-9,]+)', cbody)
        if m:
            contributors = m.group(1)
        else:
            m = re.search(r'([\d,]+)\s*contributors?\b', cbody, re.I)
            if m:
                contributors = m.group(1)

    releases_count = ""
    latest_release = ""
    rel_url = url.rstrip("/") + "/releases"
    rel_page = _fetch(rel_url)
    if not isinstance(rel_page, Exception) and rel_page.status == 200:
        rcount_node = rel_page.css('a[href$="/releases"] .Counter')
        if rcount_node:
            releases_count = (rcount_node[0].text or "").strip()
        latest_tag = rel_page.css('h2 a, .release-header a')
        if latest_tag:
            latest_release = (latest_tag[0].text or "").strip()[:60]

    primary_lang = ""
    lang_nodes = home.css('[itemprop="programmingLanguage"]')
    if lang_nodes:
        primary_lang = (lang_nodes[0].text or "").strip()

    install_hint = ""
    for needle in ("pip install ", "npm install ", "npx ", "go install ", "cargo install ", "uv tool install ", "brew install "):
        idx = body.find(needle)
        if idx >= 0:
            install_hint = body[idx:idx + 120].split("\n", 1)[0].strip()
            break

    return {
        "name": name,
        "url": url,
        "status": home.status,
        "exists": True,
        "archived": archived,
        "title": title[:120],
        "description": desc[:250],
        "stars_abbrev": stars,
        "stars_exact": stars_exact,
        "forks": forks,
        "open_issues": open_issues,
        "open_prs": open_prs,
        "contributors": contributors,
        "releases_count": releases_count,
        "latest_release": latest_release,
        "last_commit_utc": last_commit,
        "language": primary_lang,
        "license": license_name,
        "install_hint": install_hint,
    }


def main() -> int:
    results = []
    for name, url in REPOS:
        sys.stderr.write(f"probing {name} ...\n")
        sys.stderr.flush()
        results.append(probe_repo(name, url))
        time.sleep(1.5)

    out = {"generated_utc": datetime.now(timezone.utc).isoformat(), "repos": results}
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
