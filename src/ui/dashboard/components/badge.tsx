import * as React from "react";
import { cn } from "./utils";

export function Badge({ tone, className, children }: {
  tone?: "evidence" | "danger" | "warn";
  className?: string;
  children: React.ReactNode;
}) {
  const cls =
    tone === "evidence" ? "text-evidence-primary bg-evidence-primary/10 border-evidence-primary/30"
    : tone === "danger" ? "text-evidence-missing bg-evidence-missing/10 border-evidence-missing/30"
    : tone === "warn" ? "text-evidence-weak bg-evidence-weak/15 border-evidence-weak/30"
    : "text-fg-2 bg-panel-2 border-line";
  return (
    <span className={cn("inline-flex items-center h-[18px] px-1.5 rounded-xs border font-mono text-[10.5px] font-medium uppercase whitespace-nowrap", cls, className)} style={{ letterSpacing: "0.08em" }}>
      {children}
    </span>
  );
}
