"use client";

import * as React from "react";
import type { AtomRef } from "../../types";
import { TierBadge } from "./tier-badge";
import { ConfBar } from "./conf-bar";
import { Button } from "./button";
import { cn } from "./utils";

export function AtomChip({ atom, lineStart, lineEnd, onResolve, className }: {
  atom: AtomRef;
  lineStart?: number;
  lineEnd?: number;
  onResolve?: (atom: AtomRef) => void;
  className?: string;
}) {
  const [open, setOpen] = React.useState(false);

  return (
    <span className={cn("inline-flex flex-col gap-2 align-top", className)}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-1.5 rounded-sm border border-line bg-panel-2 px-2 py-1 text-xs text-fg-1 hover:border-line-2"
      >
        <span className="font-medium">{atom.label}</span>
        <TierBadge tier={atom.tier} dot={false} label={atom.tier} />
        <ConfBar value={atom.confidence} />
      </button>

      {open ? (
        <AtomInspector atom={atom} lineStart={lineStart} lineEnd={lineEnd} onResolve={onResolve} />
      ) : null}
    </span>
  );
}

export function AtomInspector({ atom, lineStart, lineEnd, onResolve }: {
  atom: AtomRef;
  lineStart?: number;
  lineEnd?: number;
  onResolve?: (atom: AtomRef) => void;
}) {
  const lines = lineStart && lineEnd ? `Lines ${lineStart}-${lineEnd}` : `Bytes ${atom.byte_start}-${atom.byte_end}`;
  return (
    <div className="w-[280px] rounded-md border border-line bg-panel p-3 shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="font-mono text-[10.5px] text-fg-3">atom_id {atom.atom_id}</div>
          <div className="mt-1 text-sm font-semibold text-fg">{atom.label}</div>
        </div>
        <TierBadge tier={atom.tier} />
      </div>

      <div className="mt-3 flex items-center justify-between gap-3">
        <span className="font-mono text-xs text-fg-3">{lines}</span>
        <ConfBar value={atom.confidence} />
      </div>

      <div className="mt-3 flex items-center justify-between gap-2">
        {atom.tier === "S3" ? (
          <span className="font-mono text-[10.5px] uppercase text-tier-s3">Sealed — resolve only</span>
        ) : <span />}
        <Button size="sm" variant="outline" onClick={() => onResolve?.(atom)}>Resolve to source</Button>
      </div>
    </div>
  );
}
