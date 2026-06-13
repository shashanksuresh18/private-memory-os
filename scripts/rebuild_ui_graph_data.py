"""Rebuild the React graph view data from the local vault graph.

Source of truth:
- `edges` from the typed graph SQLite database
- `pages` from the retrieval SQLite database

The UI node id is the vault `page_path`, so graph clicks can resolve back to
real vault pages instead of graphify concept ids.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.memory.graph import db as graphdb
from src.memory.graph.extractor import extract_edges, persist_edges
from src.retrieval.index import ingest_vault

DEFAULT_VAULT = ROOT / "vault"
DEFAULT_RETRIEVAL_DB = ROOT / "src" / "memory" / "sqlite" / "retrieval.db"
DEFAULT_GRAPH_DB = ROOT / "src" / "memory" / "sqlite" / "graph.db"
DEFAULT_OUTPUT = ROOT / "src" / "ui" / "graph-data.json"
UI_RELATIONS = {"attended", "works_at", "invested_in", "founded"}


def _connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _pages(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT page_slug, page_path, tier FROM pages ORDER BY page_path"
    ).fetchall()


def rebuild_graph_db(vault: Path, retrieval_db: Path, graph_db: Path) -> int:
    """Re-index vault pages and repopulate graph edges locally."""
    ingest_vault(vault, db_path=retrieval_db, reset=True)
    graphdb.reset(graph_db)

    retconn = _connect(retrieval_db)
    try:
        pages = _pages(retconn)
        page_tiers = {row["page_slug"]: row["tier"] for row in pages}
        gconn = graphdb.connect(graph_db)
        try:
            inserted = 0
            for row in pages:
                page_path = Path(row["page_path"])
                if not page_path.exists():
                    continue
                source_text = page_path.read_text(encoding="utf-8")
                edges = extract_edges(
                    src_page=row["page_slug"],
                    src_tier=row["tier"],
                    source_text=source_text,
                    page_tiers=page_tiers,
                )
                inserted += persist_edges(gconn, edges)
            return inserted
        finally:
            gconn.close()
    finally:
        retconn.close()


def export_graph_data(retrieval_db: Path, graph_db: Path, output: Path) -> dict:
    retconn = _connect(retrieval_db)
    gconn = graphdb.connect(graph_db)
    try:
        pages = _pages(retconn)
        by_slug = {row["page_slug"]: row for row in pages}
        edges = gconn.execute(
            "SELECT src_page, dst_page, edge_type FROM edges "
            "ORDER BY src_page, dst_page, edge_type"
        ).fetchall()

        used_slugs: set[str] = set()
        links = []
        for edge in edges:
            if edge["edge_type"] not in UI_RELATIONS:
                continue
            src = by_slug.get(edge["src_page"])
            dst = by_slug.get(edge["dst_page"])
            if src is None or dst is None:
                continue
            used_slugs.add(edge["src_page"])
            used_slugs.add(edge["dst_page"])
            links.append({
                "source": src["page_path"],
                "target": dst["page_path"],
                "relation": edge["edge_type"],
            })

        nodes = []
        for slug in sorted(used_slugs, key=lambda s: by_slug[s]["page_path"]):
            page = by_slug[slug]
            page_path = page["page_path"]
            nodes.append({
                "id": page_path,
                "label": Path(page_path).stem.replace("-", " ").replace("_", " ").title(),
                "tier": page["tier"],
                "group": slug.split("/", 1)[0] if "/" in slug else "vault",
                "source_file": page_path,
            })

        payload = {
            "nodes": nodes,
            "links": links,
            "built_from": str(graph_db.relative_to(ROOT)),
        }
        output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return payload
    finally:
        gconn.close()
        retconn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault", type=Path, default=DEFAULT_VAULT)
    parser.add_argument("--retrieval-db", type=Path, default=DEFAULT_RETRIEVAL_DB)
    parser.add_argument("--graph-db", type=Path, default=DEFAULT_GRAPH_DB)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--no-rebuild-db", action="store_true")
    args = parser.parse_args()

    inserted = None
    if not args.no_rebuild_db:
        inserted = rebuild_graph_db(args.vault, args.retrieval_db, args.graph_db)
    payload = export_graph_data(args.retrieval_db, args.graph_db, args.output)
    print(json.dumps({
        "nodes": len(payload["nodes"]),
        "links": len(payload["links"]),
        "inserted_edges": inserted,
        "output": str(args.output),
    }, indent=2))


if __name__ == "__main__":
    main()
