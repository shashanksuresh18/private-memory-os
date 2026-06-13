import * as React from "react";
import { cn } from "./utils";

export function Kbd({ className, children }: { className?: string; children: React.ReactNode }) {
  return (
    <kbd className={cn("inline-flex h-[18px] items-center rounded-xs border border-line bg-panel-2 px-1.5 font-mono text-[10.5px] text-fg-3", className)}>
      {children}
    </kbd>
  );
}
