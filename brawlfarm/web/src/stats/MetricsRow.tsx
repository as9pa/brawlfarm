/**
 * Six figures on one line: the value at 18 px and its label at 11 px muted under it,
 * separated by a 1 px rule. No tiles, no big numbers, no sparkline. The row is the
 * summary, so it is the one thing on the page that is always readable at a glance.
 *
 * Nothing here truncates. A cell keeps a floor of 104 px and the row wraps under it, so a
 * phone gets two or three columns of readable figures rather than six cells of "37...".
 *
 * Two placeholders stand in for numbers that would be a lie: "After 30 min" while the
 * range is too short for a rate to mean anything, and "Not yet" when there is nothing at
 * all to average.
 *
 * No value breaks between its number and its unit: "1 h 51 min" over two lines reads as two
 * figures. That is whitespace-nowrap here rather than a non-breaking space in hoursText,
 * which other screens share.
 */
import type { StatsSummary } from "../api/types";
import { NOT_YET } from "../lib/copy";
import { num, signed } from "../lib/format";
import { hoursText } from "../lib/time";

export interface MetricsRowProps {
  summary: StatsSummary;
}

const TOO_SHORT = "After 30 min";

function trophyTone(trophies: number): string {
  if (trophies > 0) return "text-accent";
  if (trophies < 0) return "text-bad";
  return "text-muted";
}

function rateText(summary: StatsSummary): string {
  if (summary.trophies_per_hour !== null) return num(summary.trophies_per_hour);
  return summary.games > 0 ? TOO_SHORT : NOT_YET;
}

function Figure({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div
      data-testid={`metric-${label}`}
      className="flex min-w-[104px] flex-1 flex-col gap-0.5 border-l border-line px-3 first:border-l-0 first:pl-0"
    >
      <span
        data-testid="metric-value"
        className={`t-figure whitespace-nowrap text-[18px] ${tone ?? "text-text"}`}
      >
        {value}
      </span>
      <span data-label="" className="text-[11px] text-muted">
        {label}
      </span>
    </div>
  );
}

export function MetricsRow({ summary }: MetricsRowProps) {
  return (
    <div className="flex flex-wrap items-start rounded-[10px] border border-line bg-panel px-3 py-2">
      <Figure label="Games" value={num(summary.games)} />
      <Figure
        label="Trophies"
        value={signed(summary.trophies)}
        tone={trophyTone(summary.trophies)}
      />
      <Figure label="Trophies per hour" value={rateText(summary)} />
      <Figure
        label="Average rank"
        value={summary.avg_rank === null ? NOT_YET : summary.avg_rank.toFixed(1)}
      />
      <Figure
        label="Top-4 rate"
        value={summary.top4_rate === null ? NOT_YET : `${Math.round(summary.top4_rate)}%`}
      />
      <Figure label="Time farmed" value={hoursText(summary.hours_farmed)} />
    </div>
  );
}
