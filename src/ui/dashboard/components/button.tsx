import * as React from "react";
import { cn } from "./utils";

export type ButtonVariant = "default" | "primary" | "ghost" | "danger" | "outline";
export type ButtonSize = "sm" | "md" | "lg" | "icon";

const variants: Record<ButtonVariant, string> = {
  default: "bg-panel-2 text-fg-1 border border-line hover:bg-[color:var(--hover)] hover:border-line-2 active:translate-y-px",
  primary: "bg-accent text-accent-fg shadow-sm hover:bg-[color-mix(in_srgb,var(--accent)_90%,white)] active:translate-y-px",
  ghost: "text-fg-2 hover:bg-[color:var(--hover)] hover:text-fg-1",
  danger: "text-evidence-missing hover:bg-tier-s3-soft hover:border-[color-mix(in_srgb,var(--tier-s3)_30%,transparent)] border border-transparent",
  outline: "border border-line-2 text-fg-1 hover:bg-[color:var(--hover)]",
};

const sizes: Record<ButtonSize, string> = {
  sm: "h-7 px-2.5 text-xs",
  md: "h-8 px-3 text-sm",
  lg: "h-9 px-3.5 text-md",
  icon: "h-8 w-8 p-0",
};

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

export const Btn = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", size = "md", ...props }, ref) => (
    <button
      ref={ref}
      className={cn(
        "inline-flex items-center justify-center gap-1.5 rounded-md text-sm font-medium tracking-snug transition-colors duration-fast ease-out-soft focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-bg disabled:pointer-events-none disabled:opacity-50 select-none",
        variants[variant],
        sizes[size],
        className,
      )}
      {...props}
    />
  )
);
Btn.displayName = "Btn";

export const Button = Btn;
