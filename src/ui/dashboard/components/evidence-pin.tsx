import { cn } from "./utils";

export type PinKind = "primary" | "generated" | "weak" | "gap";

const tokens: Record<PinKind, { text: string; bg: string; border: string }> = {
  primary: { text: "text-evidence-primary", bg: "bg-evidence-primary/15", border: "border-evidence-primary/40" },
  generated: { text: "text-evidence-generated", bg: "bg-evidence-generated/15", border: "border-evidence-generated/40" },
  weak: { text: "text-evidence-weak", bg: "bg-evidence-weak/15", border: "border-evidence-weak/40" },
  gap: { text: "text-evidence-missing", bg: "bg-evidence-missing/15", border: "border-evidence-missing/40" },
};

export function EvidencePin({ n, kind = "primary", className, onClick }: {
  n: number | string;
  kind?: PinKind;
  className?: string;
  onClick?: () => void;
}) {
  const t = tokens[kind];
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "inline-flex items-center justify-center min-w-[16px] h-4 px-1 ml-0.5 rounded-[3px] border font-mono text-[10px] font-semibold cursor-pointer align-middle",
        t.text, t.bg, t.border, className,
      )}
      style={{ verticalAlign: "1px" }}
      aria-label={`Open evidence ${n}`}
    >
      {n}
    </button>
  );
}
