// REFERENCE-ONLY (React migration path). Not loaded by the vanilla runtime
// (index.html + app.js + styles.css). See ./README.md. Logic lives in app.js.
import { Icon } from "./icon";
import { TierBadge } from "./tier-badge";
import { Button } from "./button";
import type { Tier } from "../../types";

export interface Posture {
  cloudAllowed: false;
  modelCallUsed: false;
  liveProviderUsed: false;
  generatedMemoFilteredCount: number;
  vaultId: string;
  vaultTier: Tier;
  sessionId: string;
}

export function SafetyBar({ posture, onOpenAudit }: { posture: Posture; onOpenAudit?: () => void }) {
  return (
    <div
      className="grid items-center gap-3.5 rounded-lg p-3 px-4"
      style={{
        gridTemplateColumns: "auto 1fr auto",
        border: "1px solid color-mix(in srgb, var(--evidence-primary) 32%, transparent)",
        background: "linear-gradient(180deg, color-mix(in srgb, var(--evidence-primary) 4%, transparent), transparent 60%) var(--panel)",
        boxShadow: "var(--shadow-sm)",
      }}
    >
      <div className="flex items-center gap-2.5">
        <div className="w-[26px] h-[26px] rounded-md grid place-items-center bg-evidence-primary/15 text-evidence-primary border border-evidence-primary/30">
          <Icon name="shield" size={14} />
        </div>
        <div>
          <div className="text-md font-semibold text-fg">Engine - local - extractive</div>
          <div className="text-xs text-fg-2">vault/{posture.vaultId} - no model call - no live provider</div>
        </div>
      </div>

      <div className="flex gap-4 font-mono text-xs text-fg-2">
        <Kv k="cloud" v="blocked" ok />
        <Kv k="model_call" v="false" ok />
        <Kv k="live_provider" v="false" ok />
        <Kv k="filtered" v={String(posture.generatedMemoFilteredCount)} />
      </div>

      <div className="flex gap-2 items-center">
        <TierBadge tier={posture.vaultTier} label={`${posture.vaultTier} - SYNTHETIC`} />
        <Button onClick={onOpenAudit}>Routing audit</Button>
      </div>
    </div>
  );
}

function Kv({ k, v, ok }: { k: string; v: string; ok?: boolean }) {
  return (
    <span className={ok ? "text-evidence-primary" : ""}>
      <span className="text-fg-3">{k}</span> {v}
    </span>
  );
}
