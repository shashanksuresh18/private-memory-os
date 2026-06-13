import type { Scores } from "../../types";
import { ConfBar } from "./conf-bar";
import { cn } from "./utils";

const rows: Array<{ key: keyof Scores; label: string; final?: boolean }> = [
  { key: "bm25", label: "BM25" },
  { key: "vector", label: "Vector" },
  { key: "rrf", label: "RRF" },
  { key: "rerank", label: "Rerank", final: true },
];

export function ScoreBreakdown({ scores, className }: { scores: Scores; className?: string }) {
  if (scores.rerank === 0) {
    return (
      <div className={cn("inline-flex items-center gap-2", className)} title="Lexical · Semantic · Fused · Re-ranked">
        <span className="font-mono text-[10.5px] uppercase text-fg-3">RRF</span>
        <ConfBar value={scores.rrf} />
      </div>
    );
  }

  return (
    <div className={cn("grid gap-1 min-w-0", className)} title="Lexical · Semantic · Fused · Re-ranked">
      {rows.map((row) => {
        const value = scores[row.key];
        return (
          <div key={row.key} className="grid grid-cols-[48px_minmax(0,1fr)_34px] items-center gap-2 font-mono text-[10.5px] text-fg-2">
            <span className={row.final ? "font-semibold text-fg" : "text-fg-3"}>{row.label}</span>
            <span className="h-1.5 rounded-full bg-panel-2 border border-line overflow-hidden">
              <span className={cn("block h-full", row.final ? "bg-evidence-primary" : "bg-accent")} style={{ width: `${Math.max(0, Math.min(1, value)) * 100}%` }} />
            </span>
            <span className={row.final ? "font-semibold text-fg" : ""}>{value.toFixed(2)}</span>
          </div>
        );
      })}
    </div>
  );
}
