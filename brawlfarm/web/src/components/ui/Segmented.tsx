/** A radio group that looks like chips. Radio semantics rather than buttons, so the
 * "one of these is selected" relationship survives in a screen reader, and the radio
 * group's keyboard comes with them: one tab stop, arrows between the options, and Home
 * and End to the two ends. */
import { type KeyboardEvent, useRef } from "react";

/** Generic over the option values, so a caller whose values are a union gets that union
 * back in onChange rather than a bare string it has to assert its way out of. */
export interface SegmentedProps<T extends string> {
  value: T;
  options: readonly { value: T; label: string }[];
  onChange: (next: T) => void;
  label: string;
  /** The id of a note rendered beside the group, read out after the label. */
  describedBy?: string;
}

/** Which way each arrow moves along the group. The group is drawn as a row, so Left and
 * Right are the obvious pair, and Up and Down are the ones a screen reader user is told
 * to try; both ends wrap. Home and End are not in here: they land on an end rather than
 * stepping, so they have no direction to hold. */
const ARROW_STEP: Record<string, number> = {
  ArrowLeft: -1,
  ArrowUp: -1,
  ArrowRight: 1,
  ArrowDown: 1,
};

/** The one focus ring, restated on the control so it survives an ancestor that sets
 * outline-none. theme.css carries the same rule as the fallback. */
const FOCUS_RING =
  "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent";

export function Segmented<T extends string>({
  value,
  options,
  onChange,
  label,
  describedBy,
}: SegmentedProps<T>) {
  const group = useRef<HTMLDivElement>(null);
  // A value that matches nothing still has to leave one tab stop behind, or the group
  // drops out of the tab order entirely.
  const at = options.findIndex((option) => option.value === value);
  const tabStop = at < 0 ? 0 : at;

  /** Selection follows focus, which is what a radio group does: the arrow key both moves
   * and chooses. The focus call reads the buttons from the DOM rather than waiting for
   * the re-render, so the key press lands on one frame. */
  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const step = ARROW_STEP[event.key];
    let to: number;
    if (event.key === "Home") to = 0;
    else if (event.key === "End") to = options.length - 1;
    else if (step !== undefined) to = at < 0 ? 0 : (at + step + options.length) % options.length;
    else return;
    event.preventDefault();
    onChange(options[to].value);
    group.current?.querySelectorAll<HTMLButtonElement>('[role="radio"]')[to]?.focus();
  };

  return (
    <div
      ref={group}
      role="radiogroup"
      aria-label={label}
      aria-describedby={describedBy}
      onKeyDown={onKeyDown}
      className="inline-flex gap-0.5 rounded-[6px] border border-line bg-panel p-0.5"
    >
      {options.map((option, index) => {
        const selected = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={selected}
            tabIndex={index === tabStop ? 0 : -1}
            onClick={() => onChange(option.value)}
            className={`h-6 rounded-[4px] px-2 text-[12px] transition-colors duration-[120ms] ${selected ? "bg-accent text-accent-ink" : "text-muted hover:text-text"} ${FOCUS_RING}`}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
