"use client";

// REFERENCE-ONLY (React migration path). Not loaded by the vanilla runtime.
// Active-route tracking is via the plain `pathname` prop (no Next usePathname);
// the live app tracks the active view in app.js. See ./README.md.
import { Icon } from "./icon";
import { Button } from "./button";
import { TierBadge } from "./tier-badge";
import type { Stats } from "../../api";

const TITLES: Record<string, { t: string; trail: (stats?: Stats | null) => string }> = {
  "/command-centre": { t: "Command Centre", trail: () => "Overview - today" },
  "/vault": { t: "Evidence Vault", trail: (stats) => `${stats?.pages ?? 0} pages - ${formatNumber(stats?.chunks ?? 0)} chunks` },
  "/memo": { t: "Memos", trail: (stats) => `${stats?.meetings ?? 0} meeting notes` },
  "/crm": { t: "Relationships", trail: () => "People & companies" },
  "/audit": { t: "Privacy & Routing", trail: () => "Live local posture" },
  "/gbrain": { t: "GBrain Sync", trail: () => "Sidecar - one-way export" },
  "/connectors": { t: "Connectors", trail: () => "No active connectors" },
  "/settings": { t: "Settings", trail: () => "Workspace config" },
};

export function TopBar({ onOpenPalette, pathname = "/command-centre", stats }: { onOpenPalette?: () => void; pathname?: string; stats?: Stats | null }) {
  const key = Object.keys(TITLES).find(k => pathname.startsWith(k)) ?? "/command-centre";
  const { t } = TITLES[key];
  const trail = TITLES[key].trail(stats);

  return (
    <header className="flex items-center gap-3 h-12 shrink-0 px-4 bg-panel border-b border-line">
      <div className="flex items-baseline gap-2.5 min-w-0">
        <div className="text-md font-semibold text-fg tracking-snug whitespace-nowrap">{t}</div>
        <div className="font-mono text-xs text-fg-3 truncate">{trail}</div>
      </div>

      <div className="flex-1" />

      <button
        onClick={onOpenPalette}
        className="inline-flex items-center gap-2.5 h-[30px] px-2.5 rounded-md bg-panel-2 border border-line text-sm hover:bg-[color:var(--hover)] hover:border-line-2 transition-colors duration-fast"
      >
        <Icon name="search" size={13} className="text-fg-3" />
        <span className="text-fg-3 font-normal">Search vault, memos, contacts...</span>
        <kbd className="font-mono text-[10.5px] text-fg-3 ml-1">Ctrl K</kbd>
      </button>

      <div className="w-px h-5 bg-line" />

      <TierBadge tier="S1" label="S1 - SYNTHETIC" />

      <Button variant="ghost" size="icon" aria-label="Settings">
        <Icon name="settings" size={13} />
      </Button>
    </header>
  );
}

function formatNumber(value: number) {
  return new Intl.NumberFormat().format(value);
}
