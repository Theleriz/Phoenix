import type { ButtonHTMLAttributes } from "react";

export type ButtonVariant = "primary" | "secondary" | "text-button";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  full?: boolean;
}

/** Both apps already use the same `primary`/`secondary`/`text-button` + `full` class vocabulary. */
export function Button({ variant = "primary", full, className, ...rest }: ButtonProps) {
  const classes = [variant, full && "full", className].filter(Boolean).join(" ");
  return <button {...rest} className={classes} />;
}
