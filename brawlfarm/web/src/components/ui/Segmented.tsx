/** A radio group that looks like chips. Radio semantics rather than buttons, so the
 * "one of these is selected" relationship survives in a screen reader. */
export interface SegmentedOption {
  value: string;
  label: string;
}

export interface SegmentedProps {
  value: string;
  options: SegmentedOption[];
  onChange: (next: string) => void;
  label: string;
}

export function Segmented({ value, options, onChange, label }: SegmentedProps) {
  return (
    <div
      role="radiogroup"
      aria-label={label}
      className="inline-flex gap-0.5 rounded-[6px] border border-line bg-panel p-0.5"
    >
      {options.map((option) => {
        const selected = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => onChange(option.value)}
            className={`h-6 rounded-[4px] px-2 text-[12px] transition-colors duration-[120ms] ${selected ? "bg-accent text-accent-ink" : "text-muted hover:text-text"}`}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
