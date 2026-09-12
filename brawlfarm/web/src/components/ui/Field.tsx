/**
 * A labelled input with an optional unit suffix. `step` is here because the schedule's
 * "Run for" field counts in half hours; everything else leaves it alone.
 *
 * type="password" is the Brawl Stars token and nothing else. The input is masked,
 * autocomplete is off so no browser offers to remember it, it carries data-private so the
 * screenshot pass blurs it, and a trailing button reveals it. Revealing is component state
 * and nothing more: the token is never logged, never stored outside the query cache and
 * the PUT body, and never rendered unmasked by default.
 */
import { Eye, EyeOff } from "lucide-react";
import { useState } from "react";

export interface FieldProps {
  label: string;
  id: string;
  value: string;
  onChange: (v: string) => void;
  type?: "text" | "number" | "password";
  /** "control" is the phase 4 width (w-24); "full" fills its row. */
  width?: "control" | "full";
  suffix?: string;
  min?: number;
  step?: number;
  disabled?: boolean;
  placeholder?: string;
  list?: string;
}

const WIDTHS: Record<NonNullable<FieldProps["width"]>, string> = {
  control: "w-24",
  full: "w-full",
};

export function Field({
  label,
  id,
  value,
  onChange,
  type = "text",
  width = "control",
  suffix,
  min,
  step,
  disabled = false,
  placeholder,
  list,
}: FieldProps) {
  const [revealed, setRevealed] = useState(false);
  const masked = type === "password";

  return (
    <div className={`flex items-center gap-2 ${width === "full" ? "w-full" : ""}`}>
      <label htmlFor={id} className="text-[12px] text-muted">
        {label}
      </label>
      <input
        id={id}
        type={masked && !revealed ? "password" : masked ? "text" : type}
        value={value}
        min={min}
        step={step}
        list={list}
        disabled={disabled}
        placeholder={placeholder}
        autoComplete={masked ? "off" : undefined}
        data-private={masked ? "" : undefined}
        onChange={(event) => onChange(event.target.value)}
        className={`h-8 rounded-[6px] border border-line bg-panel-2 px-2 font-mono text-[13px] tabular-nums text-text disabled:cursor-not-allowed disabled:opacity-50 ${WIDTHS[width]}`}
      />
      {masked && (
        <button
          type="button"
          aria-label={revealed ? "Hide" : "Show"}
          onClick={() => setRevealed((on) => !on)}
          className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-[6px] border border-line bg-panel-2 text-muted transition-colors duration-[120ms] hover:text-text"
        >
          {revealed ? (
            <EyeOff size={16} strokeWidth={1.6} aria-hidden="true" />
          ) : (
            <Eye size={16} strokeWidth={1.6} aria-hidden="true" />
          )}
        </button>
      )}
      {suffix !== undefined && <span className="text-[12px] text-muted">{suffix}</span>}
    </div>
  );
}
