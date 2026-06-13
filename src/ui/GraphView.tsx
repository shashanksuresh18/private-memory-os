import * as React from "react";
import rawGraph from "./graph-data.json";
import type { Tier } from "./types";
import "./graph-view.css";

// §6 Knowledge Graph View. Source: local vault graph SQLite export:
// `edges` relationships + retrieval `pages` tiers, committed as graph-data.json.
// Node ids are vault page_path values so clicks resolve to real vault pages.
// Plain SVG + a deterministic in-TS force layout — NO external graph library,
// NO CDN, so the offline build works.

export interface GraphNode {
  id: string;
  label: string;
  tier: Tier | null;
  group: string;
  source_file: string | null;
}
interface GraphLink {
  source: string;
  target: string;
  relation: string;
}

const data = rawGraph as { nodes: GraphNode[]; links: GraphLink[] };
const NODE_BY_ID = new Map(data.nodes.map((n) => [n.id, n] as const));

const TIER_RANK: Record<Tier, number> = { S1: 1, S2: 2, S3: 3 };
const TIER_COLOR: Record<Tier, string> = {
  S1: "var(--tier-s1)",
  S2: "var(--tier-s2)",
  S3: "var(--tier-s3)",
};

function nodeColor(tier: Tier | null): string {
  return tier ? TIER_COLOR[tier] : "var(--fg-3, #8a8a93)";
}

interface Pt { x: number; y: number; vx: number; vy: number; }

// Deterministic force-directed layout (seeded on a circle, no Math.random) so
// the same data always lays out identically.
function useLayout(width: number, height: number): Map<string, Pt> {
  return React.useMemo(() => {
    const pos = new Map<string, Pt>();
    const { nodes, links } = data;
    const radius = Math.min(width, height) * 0.36;
    nodes.forEach((n, i) => {
      const a = (i / Math.max(nodes.length, 1)) * Math.PI * 2;
      pos.set(n.id, { x: width / 2 + Math.cos(a) * radius, y: height / 2 + Math.sin(a) * radius, vx: 0, vy: 0 });
    });
    const edges = links.filter((l) => pos.has(l.source) && pos.has(l.target));
    const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));

    for (let it = 0; it < 320; it++) {
      for (let i = 0; i < nodes.length; i++) {
        const a = pos.get(nodes[i].id)!;
        for (let j = i + 1; j < nodes.length; j++) {
          const b = pos.get(nodes[j].id)!;
          const dx = a.x - b.x, dy = a.y - b.y;
          const d2 = dx * dx + dy * dy || 0.01;
          const d = Math.sqrt(d2);
          const f = 2000 / d2;
          const ux = dx / d, uy = dy / d;
          a.vx += ux * f; a.vy += uy * f;
          b.vx -= ux * f; b.vy -= uy * f;
        }
      }
      for (const l of edges) {
        const a = pos.get(l.source)!, b = pos.get(l.target)!;
        const dx = b.x - a.x, dy = b.y - a.y;
        const d = Math.sqrt(dx * dx + dy * dy) || 0.01;
        const f = (d - 96) * 0.02;
        const ux = dx / d, uy = dy / d;
        a.vx += ux * f; a.vy += uy * f;
        b.vx -= ux * f; b.vy -= uy * f;
      }
      for (const n of nodes) {
        const p = pos.get(n.id)!;
        p.vx += (width / 2 - p.x) * 0.001;
        p.vy += (height / 2 - p.y) * 0.001;
        p.vx *= 0.85; p.vy *= 0.85;
        p.x = clamp(p.x + clamp(p.vx, -8, 8), 28, width - 28);
        p.y = clamp(p.y + clamp(p.vy, -8, 8), 28, height - 28);
      }
    }
    return pos;
  }, [width, height]);
}

export function GraphView({ resolvedTier, onSelectNode }: {
  resolvedTier: Tier;
  onSelectNode: (node: GraphNode) => void;
}) {
  const width = 920, height = 600;
  const pos = useLayout(width, height);
  const [hover, setHover] = React.useState<string | null>(null);
  const contextRank = TIER_RANK[resolvedTier];

  // Tier gate: an S3 node is only fully visible (and clickable) in S3 context.
  const visible = (n: GraphNode) => !n.tier || TIER_RANK[n.tier] <= contextRank;
  // S3 labels are hidden whenever the tier context is S1/S2.
  const labelVisible = (n: GraphNode) => n.tier !== "S3" || resolvedTier === "S3";

  return (
    <section className="graph-view" aria-label="Knowledge graph view">
      <div className="graph-view__legend">
        <span className="swatch"><span className="dot" style={{ background: "var(--tier-s1)" }} /> S1 public</span>
        <span className="swatch"><span className="dot" style={{ background: "var(--tier-s2)" }} /> S2 sensitive</span>
        <span className="swatch"><span className="dot" style={{ background: "var(--tier-s3)" }} /> S3 sealed</span>
        <span className="swatch"><span className="dot" style={{ background: "var(--fg-3, #8a8a93)" }} /> untiered</span>
        <span className="graph-view__note">{data.nodes.length} nodes · {data.links.length} edges · click a node to retrieve its page</span>
      </div>

      <svg viewBox={`0 0 ${width} ${height}`} className="graph-view__svg" role="img" aria-label="Knowledge graph">
        {data.links.map((l, i) => {
          const a = pos.get(l.source), b = pos.get(l.target);
          if (!a || !b) return null;
          const na = NODE_BY_ID.get(l.source), nb = NODE_BY_ID.get(l.target);
          // Hide an edge if either endpoint is a tier-gated (hidden) node.
          if ((na && !visible(na)) || (nb && !visible(nb))) return null;
          const hot = hover != null && (l.source === hover || l.target === hover);
          return (
            <g key={i}>
              <line
                x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                stroke={hot ? "var(--fg-2, #b5b5bd)" : "var(--line, #2a2a31)"}
                strokeWidth={hot ? 1.6 : 1}
                opacity={hover != null && !hot ? 0.2 : 0.7}
              >
                <title>{l.relation}</title>
              </line>
              {hot ? (
                <text className="graph-edge-label" x={(a.x + b.x) / 2} y={(a.y + b.y) / 2 - 3}>{l.relation}</text>
              ) : null}
            </g>
          );
        })}

        {data.nodes.map((n) => {
          const p = pos.get(n.id);
          if (!p) return null;
          const vis = visible(n);
          const sealed = n.tier === "S3" && resolvedTier !== "S3";
          const hot = hover === n.id;
          const showLabel = labelVisible(n) && (hot || data.nodes.length <= 60);
          return (
            <g
              key={n.id}
              transform={`translate(${p.x},${p.y})`}
              style={{ cursor: vis ? "pointer" : "default" }}
              onMouseEnter={() => setHover(n.id)}
              onMouseLeave={() => setHover(null)}
              onClick={() => { if (vis) onSelectNode(n); }}
            >
              <circle
                r={hot ? 9 : 6}
                fill={nodeColor(n.tier)}
                opacity={vis ? 1 : 0.22}
                stroke={hot ? "var(--fg, #fff)" : "transparent"}
                strokeWidth={2}
              >
                <title>{`${n.label} · ${n.tier ?? "untiered"} · ${n.group}`}</title>
              </circle>
              {showLabel ? (
                <text className="graph-node-label" x={10} y={4}>
                  {n.label.length > 26 ? `${n.label.slice(0, 25)}…` : n.label}
                </text>
              ) : sealed ? (
                <text className="graph-node-label graph-node-label--sealed" x={10} y={4}>S3 · sealed</text>
              ) : null}
            </g>
          );
        })}
      </svg>
    </section>
  );
}
