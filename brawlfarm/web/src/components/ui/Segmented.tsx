/** A radio group that looks like chips. Radio semantics rather than buttons, so the
 * "one of these is selected" relationship survives in a screen reader, and the radio
 * group's keyboard comes with them: one tab stop, arrows between the options. */
import { type KeyboardEvent, useRef } from "react";

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

/** Which way each arrow moves along the group. The group is drawn as a row, so Left and
 * Right are the obvious pair, and Up and Down are the ones a screen reader user is told
 * to try; both ends wrap. */
const ARROW_STEP: Record<string, number> = {
  ArrowLeft: -1,
  ArrowUp: -1,
  ArrowRight: 1,
  ArrowDown: 1,
};

export function Segmented({ value, options, onChange, label }: SegmentedProps) {
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
    if (step === undefined) return;
    event.preventDefault();
    const to = at < 0 ? 0 : (at + step + options.length) % options.length;
    onChange(options[to].value);
    group.current?.querySelectorAll<HTMLButtonElement>('[role="radio"]')[to]?.focus();
  };

  return (
    <div
      ref={group}
      role="radiogroup"
      aria-label={label}
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
            className={`h-6 rounded-[4px] px-2 text-[12px] transition-colors duration-[120ms] ${selected ? "bg-accent text-accent-ink" : "text-muted hover:text-text"}`}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
