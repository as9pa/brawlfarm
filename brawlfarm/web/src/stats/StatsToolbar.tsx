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
 */
import type { StatsRange } from "../api/types";
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
    if (on && selected.length === 1) return; // the last chip stays on
    const next = on ? selected.filter((n) => n !== name) : [...selected, name];
    onInstances(instances.filter((n) => next.includes(n)));
  };

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Segmented label="Range" value={range} options={RANGE_OPTIONS} onChange={onRange} />

      <div className="order-last flex w-full flex-wrap gap-1 min-[900px]:order-none min-[900px]:w-auto">
        {instances.map((name) => {
          const on = selected.includes(name);
          return (
            <button
              key={name}
              type="button"
              aria-pressed={on}
              onClick={() => toggle(name)}
              className={`h-6 rounded-[6px] border border-line px-2 font-mono text-[12px] transition-colors duration-[120ms] ${
                on ? "bg-panel-2 text-text" : "bg-panel text-muted hover:text-text"
              }`}
            >
              {name}
            </button>
          );
        })}
      </div>

      <a
        href={csvHref}
        download
        className="ml-auto inline-flex h-6 items-center rounded-[6px] border border-line px-2 text-[12px] text-muted transition-colors duration-[120ms] hover:text-text"
      >
        Export CSV
      </a>
    </div>
  );
}
