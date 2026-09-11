/** A labelled input with an optional unit suffix. `step` is here because the schedule's
 * "Run for" field counts in half hours; everything else leaves it alone. */
export interface FieldProps {
  label: string;
  id: string;
  value: string;
  onChange: (v: string) => void;
  type?: "text" | "number";
  suffix?: string;
  min?: number;
  step?: number;
  disabled?: boolean;
  placeholder?: string;
  list?: string;
}

export function Field({
  label,
  id,
  value,
  onChange,
  type = "text",
  suffix,
  min,
  step,
  disabled = false,
  placeholder,
  list,
}: FieldProps) {
  return (
    <div className="flex items-center gap-2">
      <label htmlFor={id} className="text-[12px] text-muted">
        {label}
      </label>
      <input
        id={id}
        type={type}
        value={value}
        min={min}
        step={step}
        list={list}
        disabled={disabled}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
        className="h-8 w-24 rounded-[6px] border border-line bg-panel-2 px-2 font-mono text-[13px] tabular-nums text-text disabled:cursor-not-allowed disabled:opacity-50"
      />
      {suffix !== undefined && <span className="text-[12px] text-muted">{suffix}</span>}
    </div>
  );
}
