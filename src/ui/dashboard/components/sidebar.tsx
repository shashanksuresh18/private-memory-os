"use client";

// REFERENCE-ONLY (React migration path). Not loaded by the vanilla runtime.
// Nav uses plain <a href> (no Next Link); active route is the plain `pathname`
// prop (no Next usePathname). Icons come from the local inline-SVG ./icon, not
// an external icon library. See ./README.md.
import { Icon, type IconName } from "./icon";
import { cn } from "./utils";
import { Button } from "./button";
import type { Stats } from "../../api";

const WORKSPACE: NavSpec[] = [
  { href: "/command-centre", icon: "grid", label: "Command Centre" },
  { href: "/compare", icon: "columns", label: "Compare", badge: "CLOUD" },
  { href: "/graph", icon: "share", label: "Graph" },
  { href: "/vault", icon: "folder", label: "Evidence Vault", countKey: "chunks" },
  { href: "/memo", icon: "file", label: "Memos", countKey: "meetings" },
  { href: "/crm", icon: "users", label: "Relationships", countKey: "graph_edges" },
];

const SYSTEM: NavSpec[] = [
  { href: "/audit", icon: "shield", label: "Privacy & Routing" },
  { href: "/gbrain", icon: "refresh", label: "GBrain Sync", badge: "SIDECAR" },
  { href: "/connectors", icon: "plug", label: "Connectors" },
  { href: "/settings", icon: "settings", label: "Settings" },
];

interface NavSpec { href: string; icon: IconName; label: string; count?: string; countKey?: keyof Pick<Stats, "chunks" | "meetings" | "graph_edges">; badge?: string; }

export function Sidebar({ pathname = "/command-centre", onNavigate, stats }: {
  pathname?: string;
  // When provided, nav items behave as in-app view switches (no full reload).
  onNavigate?: (href: string) => void;
  stats?: Stats | null;
}) {
  return (
    <nav className="flex flex-col w-[232px] shrink-0 h-full bg-panel-2 border-r border-line p-2.5 gap-1">
      <div className="flex items-center gap-2.5 px-1.5 pb-3">
        <div className="w-[26px] h-[26px] rounded-md grid place-items-center bg-gradient-to-b from-[#1B1B21] to-[#0F0F12] border border-line-2 shadow-sm">
          <svg width="14" height="14" viewBox="0 0 20 20" fill="none">
            <rect x="3" y="4.5" width="14" height="2" rx="1" fill="#F4F4F5"/>
            <rect x="3" y="9" width="8" height="2" rx="1" fill="#34D399"/>
            <rect x="3" y="13.5" width="14" height="2" rx="1" fill="#F4F4F5"/>
          </svg>
        </div>
        <div className="text-sm font-semibold tracking-tight text-fg">
          aleph<span className="text-emerald-400">.</span>
        </div>
        <span className="ml-auto font-mono text-[10px] text-fg-3">v0.18</span>
      </div>

      <Button variant="default" className="w-full justify-between mb-2 px-2.5">
        <span className="inline-flex items-center gap-2">
          <span className="block w-4 h-4 rounded-xs bg-gradient-to-br from-sky-400 to-indigo-500" />
          <span className="font-medium">Synthetic Demo Workspace</span>
        </span>
        <Icon name="chevron-down" size={12} />
      </Button>

      <a
        href="/add"
        onClick={onNavigate ? (event) => { event.preventDefault(); onNavigate("/add"); } : undefined}
        className={cn("sidebar-add", pathname.startsWith("/add") ? "sidebar-add--active" : "")}
      >
        <Icon name="file" size={14} />
        <span>Add Document</span>
      </a>

      <NavGroup label="Workspace">
        {WORKSPACE.map((i) => (
          <NavItem
            key={i.href}
            {...i}
            count={i.countKey && stats ? formatCount(stats[i.countKey]) : i.count}
            active={pathname.startsWith(i.href)}
            onNavigate={onNavigate}
          />
        ))}
      </NavGroup>

      <NavGroup label="System">
        {SYSTEM.map((i) => <NavItem key={i.href} {...i} active={pathname.startsWith(i.href)} onNavigate={onNavigate} />)}
      </NavGroup>

      <div className="mt-auto pt-2.5 px-2 border-t border-line flex items-center gap-2">
        <span className="w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_0_3px_rgba(16,185,129,0.18)] animate-pulse" />
        <div className="text-xs text-fg-2">
          <div className="text-fg-1 font-medium">Engine - local - armed</div>
          <div className="font-mono text-[10.5px] text-fg-3">cloud=blocked - vault=S1</div>
        </div>
      </div>
    </nav>
  );
}

function formatCount(value: number) {
  if (value >= 1000) {
    return `${(value / 1000).toFixed(value >= 10000 ? 1 : 2).replace(/\.0+$/, "")}k`;
  }
  return String(value);
}

function NavGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <div className="px-1.5 pt-2.5 pb-1 font-mono text-[10px] uppercase text-fg-3" style={{ letterSpacing: "0.08em" }}>{label}</div>
      {children}
    </div>
  );
}

function NavItem({
  href, icon, label, count, badge, active, onNavigate,
}: NavSpec & { active?: boolean; onNavigate?: (href: string) => void }) {
  return (
    <a
      href={href}
      onClick={onNavigate ? (event) => { event.preventDefault(); onNavigate(href); } : undefined}
      className={cn(
        "flex items-center gap-2.5 px-2 py-1.5 rounded-sm text-sm transition-colors duration-fast",
        active
          ? "bg-accent-soft text-fg"
          : "text-fg-2 hover:bg-[color:var(--hover)] hover:text-fg-1",
      )}
    >
      <Icon name={icon} size={13} className={active ? "text-indigo-400" : "text-fg-3"} />
      <span className="flex-1">{label}</span>
      {count ? <span className="font-mono text-[10.5px] text-fg-3">{count}</span> : null}
      {badge ? (
        <span className="font-mono text-[9px] px-1 h-3.5 inline-flex items-center rounded-xs bg-evidence-generated/15 text-evidence-generated border border-evidence-generated/30">
          {badge}
        </span>
      ) : null}
    </a>
  );
}
