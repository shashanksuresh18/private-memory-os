import * as React from "react";
import { cn } from "./utils";

export const Input = React.forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement>
>(({ className, ...props }, ref) => (
  <input
    ref={ref}
    className={cn(
      "flex h-8 w-full rounded-md border border-line bg-panel-2 px-2.5 text-md text-fg",
      "placeholder:text-fg-4 outline-none transition-colors duration-fast",
      "hover:border-line-2 focus:border-[color:color-mix(in_srgb,var(--accent)_70%,var(--line-2))] focus:bg-panel focus:ring-2 focus:ring-accent/30",
      className
    )}
    {...props}
  />
));
Input.displayName = "Input";
