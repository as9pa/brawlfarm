/**
 * Cumulative trophy change, one line per instance, drawn by hand.
 *
 * There is no chart library here and there is not going to be one: this draws two rules
 * and a handful of polylines, and a dependency that renders its own DOM would also bring
 * its own focus behaviour, its own colours and its own animations, all three of which the
 * panel already decided.
 *
 * Only the paths and the two 1 px rules are SVG. Every piece of text is HTML positioned
 * over or beside the plot, because preserveAspectRatio="none" stretches the viewBox to the
 * panel's width and would stretch a <text> with it. The stroke survives that stretch
 * through vectorEffect="non-scaling-stroke".
 *
 * Nothing here animates. No draw-in, no transition on the crosshair, no easing, so there
 * is nothing for prefers-reduced-motion to turn off.
 *
 * The crosshair is reachable two ways and says the same thing both times: the pointer
 * moves it, and so do Left, Right, Home, End and Escape, with a polite live region
 * carrying the readout for a reader who cannot see the panel beside it.
 */
import { type KeyboardEvent, type MouseEvent, useState } from "react";

import type { StatsPoint, StatsRange, StatsSeries } from "../api/types";
import { Button } from "../components/ui/Button";
import { Segmented } from "../components/ui/Segmented";
import { Table, type Column } from "../components/ui/Table";
import { NOT_RECORDED } from "../lib/copy";
import { monthDay, num, signed } from "../lib/format";
import { type DayRow, rollUpDays } from "./days";
import { formatMoment } from "./format";

/** The chart or the same numbers as a table. The chart owns the vocabulary because it
 * owns both views; the page owns which one is showing, so a reload and a link keep it. */
export type StatsView = "chart" | "table";

export interface TrophyChartProps {
  series: StatsSeries[];
  /** Every selected instance, in the order the chips are in. The legend follows this, so
   * an instance with no games still appears and the legend matches the chips. */
  instances: string[];
  /** Which range is showing. Only the clock reads it: a range wider than today needs the
   * day on every stamp or the axis and the table lose which one they mean. */
  range: StatsRange;
  /** Which of the two views is showing. Controlled, because it lives in the URL. */
  view: StatsView;
  onView: (next: StatsView) => void;
}

export const CHART_LABEL = "Cumulative trophy change";
/** The unit, printed once on the y axis. The figures in that column are trophies and
 * nothing else, so the axis says so instead of leaving a column of bare numbers. */
export const CHART_UNIT = "trophies";

/** The panel heading: what the lines are, what they do to get there and over how long.
 * The svg keeps CHART_LABEL as its name, so a reader hears the chart named the way it
 * always was and a sighted reader gains the range the heading spells out. */
const CAPTIONS: Record<StatsRange, string> = {
  today: "Trophies, cumulative, today",
  "7d": "Trophies, cumulative, last 7 days",
  "30d": "Trophies, cumulative, last 30 days",
  all: "Trophies, cumulative, all time",
};

export function captionFor(range: StatsRange): string {
  return CAPTIONS[range];
}

/** The steps a person reads without doing arithmetic. A trophy total is a small integer
 * on one range and four figures on another, so the list spans both. */
const TICK_STEPS: readonly number[] = [1, 2, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000];

/** The round numbers inside the domain, descending, zero always among them: the smallest
 * step from TICK_STEPS that lands three, four or five of its multiples in [lo, hi]. The
 * domain always brackets zero, so zero is always one of those multiples. A range too
 * narrow for three round numbers keeps the one value the zero rule is drawn at. */
export function niceTicks(lo: number, hi: number): number[] {
  for (const step of TICK_STEPS) {
    const first = Math.ceil(lo / step);
    const last = Math.floor(hi / step);
    const count = last - first + 1;
    if (count < 3 || count > 5) continue;
    const values: number[] = [];
    for (let at = last; at >= first; at -= 1) values.push(at * step);
    return values;
  }
  return [0];
}

/** In series order, cycling. Every one of these exists in styles/theme.css; the proposal
 * named an "--info" tone, which does not. */
export const SERIES_COLORS: readonly string[] = [
  "var(--accent)",
  "var(--ok)",
  "var(--warn)",
  "var(--series-1)",
  "var(--series-2)",
  "var(--series-3)",
];

const PLOT_W = 640;
const PLOT_H = 180;
const PAD_Y = 10; // so a point at the very top or bottom is not half a stroke off the box
const VALUE_PAD = 0.05; // the brief's 5 %
const EMPTY = "No games in this range.";
/** How many dated stamps the x axis prints at most, the two ends included. */
const X_TICKS = 5;
/** The room a dated stamp needs on the x axis, in the coordinate space the paths are
 * drawn in. A candidate that does not clear its neighbour by this much is dropped rather
 * than nudged: three stamps drawn over each other say less than one. */
const X_LABEL_GAP = 120;
/** How many day rows the table shows before it asks. Two weeks is a screen of rows and
 * the width of the range most of the panel is read at. */
const DAY_CAP = 14;
/** The line box at 11 px type, the gap the end labels are nudged by. Two y-axis labels
 * closer together than this would overprint each other. */
const LABEL_H = 12;

/** The same three tones the brawler table reads a net by, so a day and a brawler agree
 * on what a gain looks like. */
function netTone(net: number): string {
  if (net > 0) return "text-accent";
  if (net < 0) return "text-bad";
  return "text-muted";
}

function colorFor(index: number): string {
  return SERIES_COLORS[index % SERIES_COLORS.length];
}

function msOf(point: StatsPoint): number {
  return new Date(point.t).getTime();
}

/** The value this series had at `moment`, stepping: the last point at or before it, or
 * null when the instance had not logged a game yet. */
function valueAt(points: StatsPoint[], moment: number): number | null {
  let found: number | null = null;
  for (const point of points) {
    if (msOf(point) > moment) break;
    found = point.cum;
  }
  return found;
}

export function TrophyChart({ series, instances, range, view, onView }: TrophyChartProps) {
  /** The panel's one clock format: the recent games table reads the same way, so the
   * crosshair, the ends and the table all agree on what a stamp looks like. */
  const clock = (iso: string): string => formatMoment(iso, range);
  const [hover, setHover] = useState<number | null>(null);
  // View-only and deliberately not in the URL: the range and the view are what a link
  // carries, and how far one table is unrolled is not worth a history entry.
  const [showAll, setShowAll] = useState(false);
  const [cursor, setCursor] = useState<number | null>(null);
  const active = hover ?? cursor;

  // The legend follows the chips, so an instance the API sent no entry for still shows.
  const ordered: StatsSeries[] = instances.map(
    (name) => series.find((s) => s.instance === name) ?? { instance: name, points: [] },
  );
  const drawn = ordered.filter((s) => s.points.length > 0);

  const moments = Array.from(new Set(ordered.flatMap((s) => s.points.map(msOf)))).sort(
    (a, b) => a - b,
  );

  const values = drawn.flatMap((s) => s.points.map((p) => p.cum));
  // Zero is always in the domain, because the rule at zero is what the lines are read
  // against. A flat series gets a span of 1 rather than a division by zero.
  const rawLo = Math.min(0, ...values);
  const rawHi = Math.max(0, ...values);
  const span = rawHi - rawLo || 1;
  const lo = rawLo - span * VALUE_PAD;
  const hi = rawHi + span * VALUE_PAD;
  const firstMs = moments[0] ?? 0;
  const lastMs = moments[moments.length - 1] ?? 0;
  const timeSpan = lastMs - firstMs;

  const xFor = (ms: number): number =>
    timeSpan === 0 ? PLOT_W / 2 : ((ms - firstMs) / timeSpan) * PLOT_W;
  const yFor = (value: number): number =>
    PAD_Y + ((hi - value) / (hi - lo)) * (PLOT_H - PAD_Y * 2);
  const topPercent = (y: number): string => `${(y / PLOT_H) * 100}%`;

  /** The y axis: round numbers inside the real domain rather than its two ragged
   * extremes, so every gridline is a figure a point can be read against. Three to five
   * multiples of one step are always further apart than a label height. */
  const ticks = niceTicks(rawLo, rawHi);

  /** The x axis: the two ends always, and as many of the X_TICKS evenly spaced moments
   * between as fit. A candidate is placed only where it clears the last placed label and
   * the far end by X_LABEL_GAP, so an hour of games bunched together drops labels instead
   * of printing them over each other. Two neighbours that format the same are one label,
   * so a range whose ends fall on one day does not print that day twice. */
  const xTicks: { ms: number; text: string }[] = [];
  const placeLabel = (ms: number): void => {
    const text = clock(new Date(ms).toISOString());
    const previous = xTicks[xTicks.length - 1];
    if (previous === undefined || previous.text !== text) xTicks.push({ ms, text });
  };
  if (moments.length > 0) {
    placeLabel(firstMs);
    const lastX = xFor(lastMs);
    for (let i = 1; i < X_TICKS - 1; i += 1) {
      const ms = moments[Math.round((i * (moments.length - 1)) / (X_TICKS - 1))];
      const at = xFor(ms);
      const kept = xFor(xTicks[xTicks.length - 1].ms);
      if (at - kept >= X_LABEL_GAP && lastX - at >= X_LABEL_GAP) placeLabel(ms);
    }
    if (lastMs !== firstMs) placeLabel(lastMs);
  }

  const pathOf = (points: StatsPoint[]): string =>
    points
      .map(
        (p, i) => `${i === 0 ? "M" : "L"}${xFor(msOf(p)).toFixed(2)},${yFor(p.cum).toFixed(2)}`,
      )
      .join(" ");

  /** The end labels, nudged down in turn so two instances that finish on the same number
   * are both readable. 12 px is the line box at 11 px type. Sorted by y first, so the
   * nudge only ever pushes a label away from the one above it. */
  const placed: { name: string; color: string; y: number }[] = [];
  for (const label of ordered
    .map((s, index) => ({
      name: s.instance,
      color: colorFor(index),
      y: s.points.length === 0 ? null : yFor(s.points[s.points.length - 1].cum),
    }))
    .filter((label): label is { name: string; color: string; y: number } => label.y !== null)
    .sort((a, b) => a.y - b.y)) {
    const above = placed[placed.length - 1];
    placed.push({
      ...label,
      y: above === undefined ? label.y : Math.max(label.y, above.y + LABEL_H),
    });
  }
  // A single series is already named by the legend, so an end label would name it twice.
  const endLabels = drawn.length > 1 ? placed : [];

  const readout =
    active === null
      ? null
      : {
          time: clock(new Date(moments[active]).toISOString()),
          lines: ordered.map((s) => {
            const value = valueAt(s.points, moments[active]);
            return { name: s.instance, text: value === null ? NOT_RECORDED : String(value) };
          }),
        };
  const liveText =
    readout === null
      ? ""
      : `${readout.time}, ${readout.lines.map((l) => `${l.name}: ${l.text}`).join(", ")}`;

  const onKeyDown = (event: KeyboardEvent<SVGSVGElement>) => {
    if (moments.length === 0) return;
    const last = moments.length - 1;
    let next: number | null | undefined;
    if (event.key === "ArrowRight") next = Math.min(last, (cursor ?? -1) + 1);
    else if (event.key === "ArrowLeft") next = Math.max(0, (cursor ?? 1) - 1);
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = last;
    else if (event.key === "Escape") next = null;
    if (next === undefined) return;
    event.preventDefault();
    setHover(null);
    setCursor(next);
  };

  const onMouseMove = (event: MouseEvent<SVGSVGElement>) => {
    if (moments.length === 0) return;
    const box = event.currentTarget.getBoundingClientRect();
    const width = box.width || event.currentTarget.clientWidth || PLOT_W;
    const ratio = Math.min(1, Math.max(0, (event.clientX - box.left) / width));
    setHover(Math.round(ratio * (moments.length - 1)));
  };

  /** One row a day, not one a game: a 30-day range was hundreds of rows of a running
   * total with no net and no count. The selection is named by the toolbar and the legend,
   * so no column names an instance either. */
  // Newest day first, because that is the day the panel is opened to read, and the cap
  // keeps the newest DAY_CAP of them rather than the fortnight the range opens on.
  const dayRows = rollUpDays(ordered).reverse();
  const shown = showAll ? dayRows : dayRows.slice(0, DAY_CAP);
  const columns: Column<DayRow>[] = [
    {
      key: "date",
      label: "Date",
      width: "120px",
      // At local midnight, because a bare YYYY-MM-DD parses as UTC and would read as the
      // day before on every machine west of it.
      render: (row) => <span className="t-figure">{monthDay(`${row.date}T00:00:00`)}</span>,
    },
    {
      key: "games",
      label: "Games",
      width: "80px",
      render: (row) => <span className="t-figure">{num(row.games)}</span>,
    },
    {
      key: "net",
      label: "Net trophies",
      width: "120px",
      render: (row) => (
        <span className={`t-figure ${netTone(row.net)}`}>{signed(row.net)}</span>
      ),
    },
    {
      key: "cum",
      label: "Cumulative",
      width: "120px",
      render: (row) => <span className="t-figure">{num(row.cum)}</span>,
    },
  ];

  return (
    <section className="flex flex-col gap-2 rounded-[10px] border border-line bg-panel p-3">
      <div className="flex items-center gap-3">
        <h2 className="text-[13px] font-semibold">{captionFor(range)}</h2>
        <div data-testid="chart-legend" className="flex flex-wrap items-center gap-3">
          {ordered.map((s, index) => (
            <span
              key={s.instance}
              data-testid="legend-entry"
              className="inline-flex items-center gap-1.5 text-[11px] text-muted"
            >
              <span
                aria-hidden="true"
                className="h-2 w-2 rounded-full"
                style={{ background: colorFor(index) }}
              />
              {s.instance}
            </span>
          ))}
        </div>
        <div className="ml-auto">
          <Segmented
            label="View"
            value={view}
            options={[
              { value: "chart", label: "Chart" },
              { value: "table", label: "Table" },
            ]}
            onChange={onView}
          />
        </div>
      </div>

      {view === "table" ? (
        <>
          <Table
            columns={columns}
            rows={shown}
            rowKey={(row) => row.date}
            empty={EMPTY}
            headers="sentence"
            minWidth="440px"
          />
          {dayRows.length > DAY_CAP ? (
            <div>
              <Button variant="quiet" size="sm" onClick={() => setShowAll((open) => !open)}>
                {showAll ? `Show ${num(DAY_CAP)} days` : `Show all ${num(dayRows.length)} days`}
              </Button>
            </div>
          ) : null}
        </>
      ) : moments.length === 0 ? (
        <p data-testid="chart-empty" className="h-[180px] text-[13px] text-muted">
          {EMPTY}
        </p>
      ) : (
        <>
          <div className="flex gap-2">
            <div data-testid="chart-axis" className="flex w-[44px] shrink-0 flex-col items-end">
              <div className="relative w-full" style={{ height: `${PLOT_H}px` }}>
                {ticks.map((tick) => (
                  <span
                    key={tick}
                    data-tick=""
                    className="t-figure absolute right-0 -translate-y-1/2 text-[11px] text-muted"
                    style={{ top: topPercent(yFor(tick)) }}
                  >
                    {num(tick)}
                  </span>
                ))}
              </div>
              <span className="text-[11px] text-muted">{CHART_UNIT}</span>
            </div>

            <div className="relative min-w-0 flex-1 pr-[72px]" style={{ height: `${PLOT_H}px` }}>
              <svg
                role="img"
                aria-label={CHART_LABEL}
                tabIndex={0}
                viewBox={`0 0 ${PLOT_W} ${PLOT_H}`}
                preserveAspectRatio="none"
                onKeyDown={onKeyDown}
                onMouseMove={onMouseMove}
                onMouseLeave={() => setHover(null)}
                className="block h-full w-full focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
              >
                {ticks.map((tick) => (
                  <line
                    key={tick}
                    data-gridline=""
                    x1={0}
                    x2={PLOT_W}
                    y1={yFor(tick)}
                    y2={yFor(tick)}
                    stroke="var(--line)"
                    strokeWidth={1}
                    vectorEffect="non-scaling-stroke"
                    className="opacity-40"
                  />
                ))}
                {/* After the gridlines, so the rule the lines are read against wins. */}
                <line
                  x1={0}
                  x2={PLOT_W}
                  y1={yFor(0)}
                  y2={yFor(0)}
                  stroke="var(--line)"
                  strokeWidth={1}
                  vectorEffect="non-scaling-stroke"
                />
                {active === null ? null : (
                  <line
                    data-crosshair=""
                    x1={xFor(moments[active])}
                    x2={xFor(moments[active])}
                    y1={0}
                    y2={PLOT_H}
                    stroke="var(--line)"
                    strokeWidth={1}
                    vectorEffect="non-scaling-stroke"
                  />
                )}
                {ordered.map((s, index) =>
                  s.points.length === 0 ? null : (
                    <path
                      key={s.instance}
                      data-series-path=""
                      d={pathOf(s.points)}
                      fill="none"
                      stroke={colorFor(index)}
                      strokeWidth={1.5}
                      strokeLinejoin="round"
                      strokeLinecap="round"
                      vectorEffect="non-scaling-stroke"
                    />
                  ),
                )}
              </svg>

              {endLabels.map((label) => (
                <span
                  key={label.name}
                  data-end-label=""
                  className="absolute right-0 w-[68px] -translate-y-1/2 truncate pl-1 text-[11px]"
                  style={{ top: topPercent(label.y), color: label.color }}
                >
                  {label.name}
                </span>
              ))}
            </div>
          </div>

          <div
            data-testid="chart-x-axis"
            className="relative ml-[52px] mr-[72px] h-[14px] text-[11px] text-muted"
          >
            {xTicks.map((tick) => (
              <span
                key={tick.ms}
                className="t-figure absolute whitespace-nowrap"
                style={{ left: `${(xFor(tick.ms) / PLOT_W) * 100}%` }}
              >
                {tick.text}
              </span>
            ))}
          </div>

          {readout === null ? null : (
            <div
              data-testid="chart-readout"
              className="rounded-[6px] border border-line bg-panel-2 px-2 py-1 text-[11px]"
            >
              <span className="font-mono tabular-nums text-muted">{readout.time}</span>
              {readout.lines.map((line) => (
                <span key={line.name} className="ml-3 font-mono tabular-nums">
                  {line.name}: {line.text}
                </span>
              ))}
            </div>
          )}
        </>
      )}

      <span data-testid="chart-live" aria-live="polite" className="sr-only">
        {liveText}
      </span>
    </section>
  );
}
