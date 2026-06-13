import { cn, confTone } from "./utils";

export function ConfBar({ value, className }: { value: number; className?: string }) {
  const tone = confTone(value);
  const fillClass =
    tone === "evidence-primary" ? "bg-evidence-primary"
    : tone === "evidence-weak" ? "bg-evidence-weak"
    : "bg-evidence-missing";

  return (
    <span className={cn("inline-flex items-center gap-1.5 font-mono text-xs text-fg-2 tnum", className)}>
      <span className="inline-block w-12 h-1 rounded-full bg-panel-2 border border-line overflow-hidden">
        <span className={cn("block h-full", fillClass)} style={{ width: `${Math.max(0, Math.min(1, value)) * 100}%` }} />
      </span>
      {value.toFixed(2)}
    </span>
  );
}
