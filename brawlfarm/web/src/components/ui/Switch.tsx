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

export function Switch({
  checked,
  onChange,
  label,
  disabled = false,
  describedBy,
}: SwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-describedby={describedBy}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className="inline-flex items-center gap-2 rounded-[6px] text-[12px] text-muted disabled:cursor-not-allowed disabled:opacity-50"
    >
      <span
        aria-hidden="true"
        className={`relative h-4 w-7 shrink-0 rounded-full border border-line transition-colors duration-[120ms] ${checked ? "bg-accent" : "bg-panel-2"}`}
      >
        <span
          className={`absolute top-0.5 h-2.5 w-2.5 rounded-full transition-[left] duration-[120ms] ${checked ? "left-3.5 bg-accent-ink" : "left-0.5 bg-muted"}`}
        />
      </span>
      {label}
    </button>
  );
}
