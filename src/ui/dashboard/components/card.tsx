import * as React from "react";
import { cn } from "./utils";

export function Card({ className, children }: { className?: string; children: React.ReactNode }) {
  return (
    <section className={cn("bg-panel border border-line rounded-lg shadow-sm overflow-hidden", className)}>
      {children}
    </section>
  );
}
