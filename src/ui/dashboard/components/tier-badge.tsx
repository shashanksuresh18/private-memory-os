import * as React from "react";
import { cn } from "./utils";
import type { Tier } from "../../types";

export type EvidenceKind = "PRIMARY" | "GENERATED";

const tierTokens: Record<Tier, { text: string; bg: string; border: string; label: string }> = {
  S1: { text: "text-tier-s1", bg: "bg-tier-s1-soft", border: "border-tier-s1/30", label: "S1 - PUBLIC" },
  S2: { text: "text-tier-s2", bg: "bg-tier-s2-soft", border: "border-tier-s2/30", label: "S2 - SENSITIVE" },
  S3: { text: "text-tier-s3", bg: "bg-tier-s3-soft", border: "border-tier-s3/30", label: "S3 - SEALED" },
};

export function TierBadge({ tier, dot = true, label, className }: {
  tier: Tier;
  dot?: boolean;
  label?: string;
  className?: string;
}) {
  const t = tierTokens[tier];
  return (
    <span className={cn(
      "inline-flex items-center gap-1 h-[18px] px-1.5 rounded-xs font-mono text-[10.5px] font-medium uppercase whitespace-nowrap border",
      t.text, t.bg, t.border, className,
    )} style={{ letterSpacing: "0.08em" }}>
      {dot ? <span className="block w-1.5 h-1.5 rounded-full bg-current" /> : null}
      {label ?? t.label}
    </span>
  );
}

export function KindBadge({ kind, className }: { kind: EvidenceKind; className?: string }) {
  const isPrimary = kind === "PRIMARY";
  return (
    <span className={cn(
      "inline-flex items-center gap-1 h-[18px] px-1.5 rounded-xs font-mono text-[10.5px] font-medium uppercase whitespace-nowrap border",
      isPrimary
        ? "text-evidence-primary bg-evidence-primary/10 border-evidence-primary/30"
        : "text-evidence-generated bg-evidence-generated/10 border-evidence-generated/30",
      className,
    )} style={{ letterSpacing: "0.08em" }}>
      <span className="block w-1.5 h-1.5 rounded-full bg-current" />
      {kind}
    </span>
  );
}
