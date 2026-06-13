export type ClassValue = string | false | null | undefined;

export function cn(...inputs: ClassValue[]) {
  return inputs.filter(Boolean).join(" ");
}

export function confTone(c: number): "evidence-primary" | "evidence-weak" | "evidence-missing" {
  if (c >= 0.7) return "evidence-primary";
  if (c >= 0.45) return "evidence-weak";
  return "evidence-missing";
}
