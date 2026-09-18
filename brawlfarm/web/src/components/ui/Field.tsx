/**
 * A labelled input with an optional unit suffix. `step` is here because the schedule's
 * "Run for" field counts in half hours; everything else leaves it alone.
 *
 * type="password" is the Brawl Stars token and nothing else. The input is masked,
 * autocomplete is off so no browser offers to remember it, it carries data-private so the
 * screenshot pass blurs it, and a trailing button reveals it. Revealing is component state
 * and nothing more: the token is never logged, never stored outside the query cache and
 * the PUT body, and never rendered unmasked by default.
 *
 * At most one message line sits under the control: `error` wins over `help` and they never
 * both show. The component owns aria-describedby, which points at that line and nothing
 * else, so a caller cannot add a second description; a field that needs one should say it
 * in `help`.
 */
import { Eye, EyeOff } from "lucide-react";
import { useState } from "react";

export interface FieldProps {
  label: string;
  id: string;
  value: string;
  onChange: (v: string) => void;
  /** Called when focus leaves the box, for a check that should wait until then. */
  onBlur?: () => void;
  type?: "text" | "number" | "password";
  /** "control" is the phase 4 width (w-24); "full" fills its row. */
  width?: "control" | "full";
  suffix?: string;
  min?: number;
  max?: number;
  step?: number;
  disabled?: boolean;
  placeholder?: string;
  list?: string;
  /** Shown under the control in red, announced, and it lifts the input border. */
  error?: string;
  /** Shown under the control in grey, and only when there is no `error`. */
  help?: string;
  inputMode?: "text" | "numeric" | "decimal";
  /** Masked fields default to false; an explicit value wins. */
  spellCheck?: boolean;
  /** Masked fields default to "off"; an explicit value wins. */
  autoComplete?: string;
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
  onBlur,
  type = "text",
  width = "control",
  suffix,
  min,
  max,
  step,
  disabled = false,
  placeholder,
  list,
  error,
  help,
  inputMode,
  spellCheck,
  autoComplete,
}: FieldProps) {
  const [revealed, setRevealed] = useState(false);
  const masked = type === "password";
  const message = error ?? help;
  const messageId = `${id}-msg`;

  return (
    <div className={`flex flex-col gap-1 ${width === "full" ? "w-full" : ""}`}>
      <div className="flex items-center gap-2">
        <label htmlFor={id} className="text-[12px] text-muted">
          {label}
        </label>
        <input
          id={id}
          type={masked && !revealed ? "password" : masked ? "text" : type}
          value={value}
          min={min}
          max={max}
          step={step}
          list={list}
          disabled={disabled}
          placeholder={placeholder}
          inputMode={inputMode}
          spellCheck={spellCheck ?? (masked ? false : undefined)}
          autoComplete={autoComplete ?? (masked ? "off" : undefined)}
          aria-describedby={message !== undefined ? messageId : undefined}
          aria-invalid={error !== undefined ? true : undefined}
          data-private={masked ? "" : undefined}
          onChange={(event) => onChange(event.target.value)}
          onBlur={onBlur}
          className={`h-8 rounded-[6px] border ${error !== undefined ? "border-bad" : "border-line"} bg-panel-2 px-2 font-mono text-[13px] tabular-nums text-text disabled:cursor-not-allowed disabled:opacity-50 ${WIDTHS[width]}`}
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
      {message !== undefined && (
        <p
          id={messageId}
          role={error !== undefined ? "alert" : undefined}
          className={`text-[12px] ${error !== undefined ? "text-bad" : "text-muted"}`}
        >
          {message}
        </p>
      )}
    </div>
  );
}
