/** The panel's only button. A disabled control still says why: disabledReason becomes
 * the title, so "Stop" on a stopped instance explains itself instead of just greying. */
import type { MouseEvent, ReactNode } from "react";

export interface ButtonProps {
  variant?: "primary" | "secondary" | "quiet" | "danger";
  size?: "sm" | "md";
  disabled?: boolean;
  disabledReason?: string;
  onClick?: (event: MouseEvent<HTMLButtonElement>) => void;
  children: ReactNode;
  type?: "button" | "submit";
  /** For a control whose visible text is shorter than its meaning, such as a count. */
  "aria-label"?: string;
  /** A disclosure button says whether what it opens is open, and which element that is. */
  "aria-expanded"?: boolean;
  "aria-controls"?: string;
}

const VARIANTS: Record<NonNullable<ButtonProps["variant"]>, string> = {
  primary: "bg-accent text-accent-ink hover:brightness-110",
  secondary: "border border-line bg-panel-2 text-text hover:border-accent",
  quiet: "text-accent hover:underline",
  danger: "bg-bad text-text hover:brightness-110",
};

const SIZES: Record<NonNullable<ButtonProps["size"]>, string> = {
  sm: "h-7 px-2 text-[12px]",
  md: "h-8 px-3 text-[13px]",
};

export function Button({
  variant = "secondary",
  size = "md",
  disabled = false,
  disabledReason,
  onClick,
  children,
  type = "button",
  "aria-label": ariaLabel,
  "aria-expanded": ariaExpanded,
  "aria-controls": ariaControls,
}: ButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled}
      title={disabled ? disabledReason : undefined}
      aria-label={ariaLabel}
      aria-expanded={ariaExpanded}
      aria-controls={ariaControls}
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 rounded-[6px] font-medium transition-[background-color,border-color,color] duration-[120ms] disabled:cursor-not-allowed disabled:opacity-50 ${SIZES[size]} ${VARIANTS[variant]}`}
    >
      {children}
    </button>
  );
}
