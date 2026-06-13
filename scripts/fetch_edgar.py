"""Fetch real SEC EDGAR filings into ``vault/raw/`` as S1 (public) markdown.

EDGAR is public data, so cloud fetch is allowed here — this is the ONLY
network-touching ingest path and it is S1-only by construction. Every request
carries a descriptive User-Agent and respects SEC's 10 req/sec fair-access rate
limit (``time.sleep(0.12)``).

Outputs (never overwritten):
    vault/raw/{ticker}_10k_{filing_date}.md      latest 10-K, MarkItDown -> md
    vault/raw/{ticker}_facts_{today}.md          XBRL company-facts summary

Conversion of the downloaded 10-K HTML goes through the project's locked
MarkItDown wrapper (``src.ingest.converter.to_markdown``): ``enable_plugins=
False``, no ``llm_client``, ``convert_local()`` only. The remote file is
downloaded to a temp ``.html`` first, then converted locally.

CLI:
    python scripts/fetch_edgar.py --ticker AAPL
    python scripts/fetch_edgar.py --tickers AAPL MSFT GOOGL
    python scripts/fetch_edgar.py --tickers AAPL MSFT GOOGL --facts
    python scripts/fetch_edgar.py --facts --ticker AAPL
"""

from __future__ import annotations

import argparse
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

import httpx

# Run as a script: put the repo root (parent of scripts/) on the path.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.ingest.converter import to_markdown  # noqa: E402

RAW = _REPO_ROOT / "vault" / "raw"

# SEC requires a descriptive User-Agent identifying the requester. Accept is
# adjusted per-call (JSON for the APIs, HTML for the filing document itself).
HEADERS = {
    "User-Agent": "Sovereign-Citadel research@example.com",
    "Accept": "application/json",
}
RATE_LIMIT_S = 0.12  # SEC fair-access: <= 10 requests/second.
TIMEOUT_S = 30.0

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
ARCHIVE_DOC_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}"

# The frontmatter the locked converter prepends; we strip it and substitute a
# richer S1 block so we never double-stack frontmatter.
_CONVERTER_PREFIX = "---\ntier: S1\n---\n\n"


def clean_sec_markdown(md: str) -> str:
    """Drop inline-XBRL noise from a MarkItDown-converted SEC filing.

    The primary 10-K document is iXBRL: the readable report is wrapped around a
    large block of hidden machine-readable context tags (e.g. long runs like
    ``0000320193us-gaap:CommonStockMember2024-09-29...`` with no whitespace).
    MarkItDown emits those as enormous near-whitespace-free lines plus empty
    table skeletons. Indexing them produces hundreds of junk chunks that bury
    the real prose and balloon embed time, so we strip them line-wise. Pure text
    removal keeps the result UTF-8 byte-clean for the chunker's offset round-trip.
    """
    kept: list[str] = []
    for line in md.splitlines():
        s = line.strip()
        if not s:
            kept.append("")
            continue
        # Empty markdown table skeleton rows: only pipes, dashes, spaces.
        if set(s) <= set("|- "):
            continue
        # Long, near-whitespace-free runs are concatenated XBRL context tags.
        if len(s) > 200 and (s.count(" ") / len(s)) < 0.02:
            continue
        kept.append(line)
    # Collapse 3+ blank lines down to a single blank separator.
    out: list[str] = []
    blanks = 0
    for ln in kept:
        if ln == "":
            blanks += 1
            if blanks <= 1:
                out.append(ln)
        else:
            blanks = 0
            out.append(ln)
    return "\n".join(out).strip() + "\n"


def _get(url: str, accept: str = "application/json") -> httpx.Response:
    """GET with SEC headers, rate limit, 30s timeout, one 429 retry."""
    headers = dict(HEADERS)
    headers["Accept"] = accept
    time.sleep(RATE_LIMIT_S)
    resp = httpx.get(url, headers=headers, timeout=TIMEOUT_S, follow_redirects=True)
    if resp.status_code == 429:
        time.sleep(5)
        resp = httpx.get(url, headers=headers, timeout=TIMEOUT_S, follow_redirects=True)
    resp.raise_for_status()
    return resp


def get_cik(ticker: str) -> str:
    """Resolve a ticker to its zero-padded 10-digit CIK via SEC's ticker map."""
    data = _get(TICKERS_URL).json()
    want = ticker.strip().upper()
    for row in data.values():
        if str(row.get("ticker", "")).upper() == want:
            return str(row["cik_str"]).zfill(10)
    raise ValueError(f"ticker not found in SEC ticker map: {ticker}")


def _write_no_overwrite(path: Path, content: str) -> Path | None:
    """Write content unless the file already exists. Returns path or None."""
    RAW.mkdir(parents=True, exist_ok=True)
    if path.exists():
        print(f"  skip (exists): {path.name}")
        return None
    path.write_text(content, encoding="utf-8")
    print(f"  wrote: {path.name} ({path.stat().st_size} bytes)")
    return path


def fetch_10k(ticker: str, limit: int = 1) -> list[Path]:
    """Download the latest ``limit`` 10-K filings for a ticker into vault/raw/."""
    ticker_l = ticker.strip().lower()
    written: list[Path] = []
    try:
        cik = get_cik(ticker)
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        print(f"[{ticker}] CIK lookup failed: {exc}")
        return written

    try:
        subs = _get(SUBMISSIONS_URL.format(cik=cik)).json()
    except httpx.HTTPError as exc:
        print(f"[{ticker}] submissions fetch failed: {exc}")
        return written

    recent = subs.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accns = recent.get("accessionNumber", [])
    docs = recent.get("primaryDocument", [])
    dates = recent.get("filingDate", [])

    found = 0
    for i, form in enumerate(forms):
        if form != "10-K":
            continue
        if found >= limit:
            break
        accn = accns[i]
        primary = docs[i]
        fdate = dates[i]
        if not primary or not primary.lower().endswith((".htm", ".html")):
            print(f"[{ticker}] 10-K {accn}: no HTML primary doc, skipping")
            continue
        acc_nodash = accn.replace("-", "")
        url = ARCHIVE_DOC_URL.format(cik=int(cik), acc=acc_nodash, doc=primary)
        out = RAW / f"{ticker_l}_10k_{fdate}.md"
        if out.exists():
            print(f"  skip (exists): {out.name}")
            found += 1
            continue
        try:
            doc = _get(url, accept="text/html")
        except httpx.HTTPError as exc:
            print(f"[{ticker}] 10-K doc download failed ({url}): {exc}")
            continue

        # Download to a temp .html, then convert locally (locked MarkItDown).
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td) / "filing.html"
            tmp.write_bytes(doc.content)
            try:
                converted = to_markdown(tmp, tier="S1")
            except Exception as exc:  # noqa: BLE001 - skip unconvertible filing
                print(f"[{ticker}] MarkItDown convert failed: {exc}")
                continue

        body = converted[len(_CONVERTER_PREFIX):] if converted.startswith(
            _CONVERTER_PREFIX) else converted
        body = clean_sec_markdown(body)
        frontmatter = (
            "---\n"
            "tier: S1\n"
            "source: SEC EDGAR 10-K\n"
            f"ticker: {ticker.upper()}\n"
            f"filing_date: {fdate}\n"
            "---\n\n"
        )
        result = _write_no_overwrite(out, frontmatter + body)
        if result is not None:
            written.append(result)
        found += 1

    if found == 0:
        print(f"[{ticker}] no 10-K filing found in recent submissions")
    return written


def _series_rows(facts: dict, concept: str, unit: str, last: int) -> list[tuple[str, float]]:
    """Return [(end_date, value)] for the last `last` entries of a us-gaap concept."""
    node = facts.get("facts", {}).get("us-gaap", {}).get(concept)
    if not node:
        return []
    units = node.get("units", {}).get(unit, [])
    # Sort by period end, keep the most recent `last`.
    rows = sorted(
        ((u.get("end", ""), u.get("val")) for u in units if u.get("val") is not None),
        key=lambda r: r[0],
    )
    # Dedupe by end-date keeping the last occurrence (latest amendment).
    by_end: dict[str, float] = {}
    for end, val in rows:
        by_end[end] = val
    ordered = sorted(by_end.items(), key=lambda r: r[0])
    return ordered[-last:]


def _first_concept(facts: dict, concepts: list[str], unit: str, last: int):
    for c in concepts:
        rows = _series_rows(facts, c, unit, last)
        if rows:
            return c, rows
    return None, []


def fetch_company_facts(ticker: str) -> Path | None:
    """Fetch XBRL company-facts and write a compact S1 markdown summary."""
    ticker_l = ticker.strip().lower()
    try:
        cik = get_cik(ticker)
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        print(f"[{ticker}] CIK lookup failed: {exc}")
        return None
    try:
        facts = _get(COMPANYFACTS_URL.format(cik=cik)).json()
    except httpx.HTTPError as exc:
        print(f"[{ticker}] companyfacts fetch failed: {exc}")
        return None

    rev_concept, rev_rows = _first_concept(
        facts,
        [
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "Revenues",
        ],
        "USD",
        8,
    )
    _, eps_rows = _first_concept(facts, ["EarningsPerShareBasic"], "USD/shares", 8)
    _, shares_rows = _first_concept(
        facts, ["CommonStockSharesOutstanding"], "shares", 1
    )

    today = date.today().isoformat()
    lines = [
        "---",
        "tier: S1",
        "source: SEC EDGAR XBRL company facts",
        f"ticker: {ticker.upper()}",
        "derived: false",
        f"retrieved: {today}",
        "---",
        "",
        f"# {ticker.upper()} — SEC XBRL Company Facts",
        "",
        f"CIK: {cik}",
        "",
    ]

    lines.append(f"## Revenue ({rev_concept or 'n/a'}) — last 8 periods")
    lines.append("")
    if rev_rows:
        lines.append("| Period end | Value (USD) |")
        lines.append("|---|---:|")
        for end, val in rev_rows:
            lines.append(f"| {end} | {val:,.0f} |")
    else:
        lines.append("_No revenue data available._")
    lines.append("")

    lines.append("## EarningsPerShareBasic — last 8 periods")
    lines.append("")
    if eps_rows:
        lines.append("| Period end | EPS (USD) |")
        lines.append("|---|---:|")
        for end, val in eps_rows:
            lines.append(f"| {end} | {val} |")
    else:
        lines.append("_No EPS data available._")
    lines.append("")

    lines.append("## CommonStockSharesOutstanding — latest")
    lines.append("")
    if shares_rows:
        end, val = shares_rows[-1]
        lines.append("| As of | Shares |")
        lines.append("|---|---:|")
        lines.append(f"| {end} | {val:,.0f} |")
    else:
        lines.append("_No shares-outstanding data available._")
    lines.append("")

    out = RAW / f"{ticker_l}_facts_{today}.md"
    return _write_no_overwrite(out, "\n".join(lines).rstrip() + "\n")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Fetch SEC EDGAR filings into vault/raw/")
    p.add_argument("--ticker", help="single ticker, e.g. AAPL")
    p.add_argument("--tickers", nargs="+", help="multiple tickers")
    p.add_argument("--facts", action="store_true",
                   help="also fetch XBRL company-facts summary")
    p.add_argument("--limit", type=int, default=1, help="number of 10-Ks per ticker")
    args = p.parse_args(argv)

    tickers: list[str] = []
    if args.tickers:
        tickers.extend(args.tickers)
    if args.ticker:
        tickers.append(args.ticker)
    if not tickers:
        p.error("provide --ticker or --tickers")

    # Dedupe preserving order.
    seen: set[str] = set()
    tickers = [t for t in tickers if not (t.upper() in seen or seen.add(t.upper()))]

    written: list[Path] = []
    for t in tickers:
        print(f"== {t.upper()} ==")
        try:
            written.extend(fetch_10k(t, limit=args.limit))
        except Exception as exc:  # noqa: BLE001 - one ticker must not kill the run
            print(f"[{t}] 10-K fetch crashed: {exc}")
        if args.facts:
            try:
                fp = fetch_company_facts(t)
                if fp is not None:
                    written.append(fp)
            except Exception as exc:  # noqa: BLE001
                print(f"[{t}] facts fetch crashed: {exc}")

    print(f"\nDone. {len(written)} file(s) written to {RAW}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
