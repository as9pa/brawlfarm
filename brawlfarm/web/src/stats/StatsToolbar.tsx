/**
 * The row above everything: which range, which instances, and the export.
 *
 * The ranges are the phase 4 Segmented shape rather than a new component, so the "one of
 * these is selected" relationship and the radio group's keyboard come with them. The
 * chips are buttons with aria-pressed, because "which of these are on" is a different
 * question from "which one of these", and at least one always stays on: a selection of
 * nothing would silently mean every instance to the API, which is not what the last click
 * asked for.
 *
 * Export CSV is an anchor with download, not a fetch: the browser's own download is the
 * feedback, so there is no toast and no pending state to draw.
 *
 * One configured instance is a label rather than a chip: a filter with one option is not a
 * filter, and a control that cannot change anything should not look pressable.
 */
import type { StatsRange } from "../api/types";
import { buttonClass } from "../components/ui/Button";
import { Segmented } from "../components/ui/Segmented";

export interface StatsToolbarProps {
  range: StatsRange;
  /** Every configured instance, in config.toml order: one chip each. */
  instances: string[];
  selected: string[];
  onRange: (next: StatsRange) => void;
  onInstances: (next: string[]) => void;
  csvHref: string;
}

export const RANGE_LABELS: Record<StatsRange, string> = {
  today: "Today",
  "7d": "7 days",
  "30d": "30 days",
  all: "All",
};

const RANGE_OPTIONS: readonly { value: StatsRange; label: string }[] = [
  { value: "today", label: RANGE_LABELS.today },
  { value: "7d", label: RANGE_LABELS["7d"] },
  { value: "30d", label: RANGE_LABELS["30d"] },
  { value: "all", label: RANGE_LABELS.all },
];

export function StatsToolbar({
  range,
  instances,
  selected,
  onRange,
  onInstances,
  csvHref,
}: StatsToolbarProps) {
  const toggle = (name: string) => {
    const on = selected.includes(name);
    // The last chip on says why through its own aria-disabled and title, so the click is
    // dropped here rather than explained nowhere.
    if (on && selected.length === 1) return;
    const next = on ? selected.filter((n) => n !== name) : [...selected, name];
    onInstances(instances.filter((n) => next.includes(n)));
  };

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Segmented label="Range" value={range} options={RANGE_OPTIONS} onChange={onRange} />

      <div className="order-last flex w-full flex-wrap gap-1 min-[900px]:order-none min-[900px]:w-auto">
        {instances.length === 1 ? (
          <span
            data-testid="instance-label"
            className="t-figure inline-flex h-6 items-center px-2 text-[12px] text-muted"
          >
            {instances[0]}
          </span>
        ) : (
          instances.map((name) => {
            const on = selected.includes(name);
            const last = on && selected.length === 1;
            return (
              <button
                key={name}
                type="button"
                aria-pressed={on}
                // aria-disabled, not disabled: the reason is only worth carrying if the
                // chip can still be reached by keyboard and read out.
                aria-disabled={last || undefined}
                title={last ? "Keep at least one" : undefined}
                onClick={() => toggle(name)}
                className={`h-6 rounded-[6px] border border-line px-2 font-mono text-[12px] transition-colors duration-[120ms] aria-disabled:cursor-not-allowed aria-disabled:opacity-50 ${
                  on ? "bg-panel-2 text-text" : "bg-panel text-muted hover:text-text"
                }`}
              >
                {name}
              </button>
            );
          })
        )}
      </div>

      {/* Not a Button: it stays an anchor so the browser's own download is the feedback. */}
      <a href={csvHref} download className={`ml-auto ${buttonClass("secondary", "sm")}`}>
        Export CSV
      </a>
    </div>
  );
}
