"""Per-clone audit. Extracts README head, license, deps, languages, contributor count."""
import json
import re
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone

REPOS_DIR = Path("repos-audit")
OUT_DIR = Path("docs/repo-audit")
BUS_FACTOR_JSON = Path("audit/bus_factor.json")
REPO_VERIFY_JSON = Path("audit/repo_verify.json")


def read_first_lines(path: Path, max_lines: int = 80) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""
    lines = text.splitlines()[:max_lines]
    return "\n".join(lines)


def find_first(root: Path, names: list[str]) -> Path | None:
    for n in names:
        for p in root.rglob(n):
            if ".git" in p.parts:
                continue
            return p
    return None


def git_stat(root: Path) -> dict:
    def run(args):
        try:
            return subprocess.run(
                ["git", "-C", str(root)] + args,
                capture_output=True, text=True, timeout=15, encoding="utf-8", errors="ignore",
            ).stdout.strip()
        except Exception:
            return ""
    last_commit  = run(["log", "-1", "--format=%ci %h %an"])
    head_commit  = run(["rev-parse", "HEAD"])
    branch       = run(["rev-parse", "--abbrev-ref", "HEAD"])
    contrib_hist = run(["shortlog", "-s", "-n", "-e", "HEAD"])
    contributors_in_clone = len([l for l in contrib_hist.splitlines() if l.strip()])
    return {
        "last_commit": last_commit,
        "head_sha": head_commit,
        "branch": branch,
        "contributors_in_clone": contributors_in_clone,
        "contributor_histogram_top10": contrib_hist.splitlines()[:10],
    }


def detect_deps(root: Path) -> dict:
    out: dict = {}

    py = root / "pyproject.toml"
    if py.exists():
        text = py.read_text(encoding="utf-8", errors="ignore")
        deps = re.findall(r'^\s*"([a-zA-Z0-9_\-.\[\]]+)\s*(?:[<>=!~].*)?"\s*,?\s*$', text, re.M)
        out["pyproject_dependencies_sample"] = deps[:40]
        m = re.search(r'name\s*=\s*"([^"]+)"', text)
        if m: out["pkg_name"] = m.group(1)

    req = root / "requirements.txt"
    if req.exists():
        deps = [l.strip() for l in req.read_text(encoding="utf-8", errors="ignore").splitlines()
                if l.strip() and not l.strip().startswith("#")]
        out["requirements_txt_sample"] = deps[:40]

    pj = root / "package.json"
    if pj.exists():
        try:
            pkg = json.loads(pj.read_text(encoding="utf-8", errors="ignore"))
            out["npm_name"] = pkg.get("name")
            out["npm_version"] = pkg.get("version")
            out["npm_dependencies_sample"] = list((pkg.get("dependencies") or {}).items())[:40]
            out["npm_dev_dependencies_sample"] = list((pkg.get("devDependencies") or {}).items())[:20]
            out["npm_scripts"] = list((pkg.get("scripts") or {}).keys())[:20]
        except Exception as e:
            out["package_json_parse_error"] = str(e)

    gm = root / "go.mod"
    if gm.exists():
        out["go_mod_head"] = "\n".join(gm.read_text(encoding="utf-8", errors="ignore").splitlines()[:25])

    cg = root / "Cargo.toml"
    if cg.exists():
        out["cargo_toml_head"] = "\n".join(cg.read_text(encoding="utf-8", errors="ignore").splitlines()[:25])

    return out


def detect_license(root: Path) -> str:
    for name in ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING", "COPYING.md"):
        p = root / name
        if p.exists():
            head = p.read_text(encoding="utf-8", errors="ignore").splitlines()[:3]
            return " | ".join(line.strip() for line in head if line.strip())[:200]
    return ""


def language_breakdown(root: Path) -> list[tuple[str, int]]:
    exts: dict[str, int] = {}
    for p in root.rglob("*"):
        if not p.is_file() or ".git" in p.parts:
            continue
        try:
            ext = p.suffix.lower() or "(noext)"
            exts[ext] = exts.get(ext, 0) + p.stat().st_size
        except Exception:
            pass
    return sorted(exts.items(), key=lambda kv: -kv[1])[:10]


def render_md(slug: str, root: Path, bus: dict, gitinfo: dict, deps: dict, license_str: str, langs: list, readme_head: str) -> str:
    lines = []
    lines.append(f"# {slug.replace('__', '/')}")
    lines.append("")
    lines.append(f"Audit generated: {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"Local clone: `{root}`")
    lines.append("")
    lines.append("## GitHub Metrics (Scrapling probe)")
    lines.append("")
    for k in ("stars_abbrev", "stars_exact", "forks", "open_issues", "open_prs",
              "contributors", "releases_count", "latest_release", "last_commit_utc",
              "language", "license", "archived", "description"):
        if bus.get(k):
            lines.append(f"- **{k}:** {bus[k]}")
    lines.append("")
    lines.append("## Git Snapshot")
    lines.append("")
    lines.append(f"- branch: `{gitinfo.get('branch')}`")
    lines.append(f"- head:   `{gitinfo.get('head_sha')}`")
    lines.append(f"- last commit: {gitinfo.get('last_commit')}")
    lines.append(f"- contributors in shallow clone: {gitinfo.get('contributors_in_clone')}")
    if gitinfo.get("contributor_histogram_top10"):
        lines.append("- top contributors (shallow):")
        for c in gitinfo["contributor_histogram_top10"]:
            lines.append(f"    {c}")
    lines.append("")
    lines.append("## License")
    lines.append("")
    lines.append(license_str or "_(no LICENSE file found)_")
    lines.append("")
    lines.append("## Languages (by total bytes — top 10)")
    lines.append("")
    for ext, sz in langs:
        lines.append(f"- `{ext}`: {sz:,} bytes")
    lines.append("")
    lines.append("## Dependencies")
    lines.append("")
    if not deps:
        lines.append("_(no dependency manifest detected)_")
    else:
        for k, v in deps.items():
            lines.append(f"### `{k}`")
            if isinstance(v, list):
                for item in v:
                    lines.append(f"- {item}")
            else:
                lines.append("```")
                lines.append(str(v))
                lines.append("```")
        lines.append("")
    lines.append("## README — first 80 lines")
    lines.append("")
    lines.append("```")
    lines.append(readme_head or "_(no README found)_")
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    bus_data = {r["name"].replace("/", "__"): r for r in json.loads(BUS_FACTOR_JSON.read_text(encoding="utf-8"))["repos"]} if BUS_FACTOR_JSON.exists() else {}
    verify_data = {r["name"].replace("/", "__"): r for r in json.loads(REPO_VERIFY_JSON.read_text(encoding="utf-8"))["repos"]} if REPO_VERIFY_JSON.exists() else {}

    if not REPOS_DIR.exists():
        print(f"missing {REPOS_DIR}", file=sys.stderr)
        return 1

    written = []
    for d in sorted(REPOS_DIR.iterdir()):
        if not d.is_dir():
            continue
        if not (d / ".git").exists():
            print(f"skip {d.name} (not a git clone)", file=sys.stderr)
            continue

        slug = d.name
        readme = find_first(d, ["README.md", "readme.md", "README.rst", "README", "README.txt"])
        readme_head = read_first_lines(readme, 80) if readme else ""
        gitinfo = git_stat(d)
        deps = detect_deps(d)
        license_str = detect_license(d)
        langs = language_breakdown(d)
        bus = bus_data.get(slug, verify_data.get(slug, {}))

        md = render_md(slug, d, bus, gitinfo, deps, license_str, langs, readme_head)
        out_path = OUT_DIR / f"{slug}.md"
        out_path.write_text(md, encoding="utf-8")
        written.append((slug, str(out_path), gitinfo.get("contributors_in_clone"), license_str[:40] if license_str else ""))
        print(f"WROTE {out_path}  contributors={gitinfo.get('contributors_in_clone')}  license={license_str[:40]}", file=sys.stderr)

    summary = OUT_DIR / "INDEX.md"
    lines = ["# Repo Audit Index", "", f"Generated: {datetime.now(timezone.utc).isoformat()}", "",
             "| repo | contributors (shallow) | license | report |", "|---|---|---|---|"]
    for slug, path, contribs, lic in written:
        lines.append(f"| {slug.replace('__','/')} | {contribs} | {lic} | [{slug}.md]({slug}.md) |")
    summary.write_text("\n".join(lines), encoding="utf-8")
    print(f"INDEX written -> {summary}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
