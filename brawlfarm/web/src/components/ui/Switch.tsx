/** A real button[role=switch]: the keyboard, the screen reader and the pointer all get
 * the same control, and the visible label is its accessible name. */
export interface SwitchProps {
  checked: boolean;
  onChange: (next: boolean) => void;
  label: string;
  disabled?: boolean;
  /** The id of a help line rendered next to the switch, read out after the label. */
  describedBy?: string;
}

/** The one focus ring, restated on the control so it survives an ancestor that sets
 * outline-none. theme.css carries the same rule as the fallback. */
const FOCUS_RING =
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent";

/** The four looks, keyed by `${checked}-${disabled}`. A disabled switch goes grey in both
 * positions, so being off limits is its own signal rather than a dimming of the accent,
 * and the hover border is offered on the enabled control only. */
const TONES: Record<`${boolean}-${boolean}`, { track: string; thumb: string }> = {
  "true-false": { track: "bg-accent hover:border-muted", thumb: "bg-accent-ink" },
  "false-false": { track: "bg-panel-2 hover:border-muted", thumb: "bg-muted" },
  "true-true": { track: "bg-idle", thumb: "bg-muted" },
  "false-true": { track: "bg-idle", thumb: "bg-muted" },
};

export function Switch({
  checked,
  onChange,
  label,
  disabled = false,
  describedBy,
}: SwitchProps) {
  const tone = TONES[`${checked}-${disabled}`];

  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-describedby={describedBy}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={`inline-flex items-center gap-2 rounded-[6px] text-[12px] text-muted disabled:cursor-not-allowed ${FOCUS_RING}`}
    >
      <span
        aria-hidden="true"
        className={`relative h-4 w-7 shrink-0 rounded-full border border-line transition-colors duration-[120ms] ${tone.track}`}
      >
        <span
          className={`absolute top-0.5 h-2.5 w-2.5 rounded-full transition-[left] duration-[120ms] ${checked ? "left-3.5" : "left-0.5"} ${tone.thumb}`}
        />
      </span>
      {label}
    </button>
  );
}
