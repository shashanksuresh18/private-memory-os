import { cn } from "./utils";

export function Stat({ label, value, sub, tone, className }: {
  label: string;
  value: string;
  sub: string;
  tone?: "ok" | "warn";
  className?: string;
}) {
  return (
    <div className={cn("bg-panel border border-line rounded-md p-3.5", className)}>
      <div className="eyebrow mb-1.5">{label}</div>
      <div className="flex items-baseline gap-2">
        <div className={cn("text-[26px] font-semibold tracking-tight", tone === "ok" ? "text-evidence-primary" : tone === "warn" ? "text-evidence-weak" : "text-fg")}>{value}</div>
        <div className="font-mono text-xs text-fg-3">{sub}</div>
      </div>
    </div>
  );
}
