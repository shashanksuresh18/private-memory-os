import * as React from "react";
import { cn } from "./utils";

export type IconName =
  | "search" | "settings" | "shield" | "folder" | "file" | "users" | "grid"
  | "refresh" | "plug" | "chevron-down" | "share" | "columns";

const paths: Record<IconName, React.ReactNode> = {
  search: <path d="m21 21-4.3-4.3M10.8 18a7.2 7.2 0 1 1 0-14.4 7.2 7.2 0 0 1 0 14.4Z" />,
  settings: <path d="M12 15.2a3.2 3.2 0 1 0 0-6.4 3.2 3.2 0 0 0 0 6.4Zm8-3.2 2-1.4-2-3.5-2.3 1a8 8 0 0 0-1.6-.9L15.8 4h-4l-.3 3.2a8 8 0 0 0-1.6.9l-2.3-1-2 3.5 2 1.4a8 8 0 0 0 0 1.8l-2 1.4 2 3.5 2.3-1a8 8 0 0 0 1.6.9l.3 3.2h4l.3-3.2a8 8 0 0 0 1.6-.9l2.3 1 2-3.5-2-1.4a8 8 0 0 0 0-1.8Z" />,
  shield: <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10Zm-3-10 2 2 4-5" />,
  folder: <path d="M3 7h7l2 2h9v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z" />,
  file: <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6Zm0 0v6h6" />,
  users: <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm13 10v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8" />,
  grid: <path d="M4 4h6v6H4V4Zm10 0h6v6h-6V4ZM4 14h6v6H4v-6Zm10 0h6v6h-6v-6Z" />,
  refresh: <path d="M21 12a9 9 0 1 1-2.64-6.36M21 4v5h-5" />,
  plug: <path d="M9 2v6M15 2v6M6 8h12v3a6 6 0 0 1-12 0V8Zm6 9v5" />,
  "chevron-down": <path d="m6 9 6 6 6-6" />,
  share: <><circle cx="18" cy="5" r="3" /><circle cx="6" cy="12" r="3" /><circle cx="18" cy="19" r="3" /><path d="m8.6 13.5 6.8 4M15.4 6.5l-6.8 4" /></>,
  columns: <path d="M4 4h7v16H4V4Zm9 0h7v16h-7V4Z" />,
};

export function Icon({ name, size = 14, className }: { name: IconName; size?: number; className?: string }) {
  return (
    <svg className={cn("shrink-0", className)} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {paths[name]}
    </svg>
  );
}
