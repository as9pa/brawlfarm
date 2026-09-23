/**
 * Where the farming finished: 1st to 4th, 1st at the top.
 *
 * Placements 1 to 4 always keep their own rows. Anything past 4th is summed into one
 * "Other" row, and that row is only drawn when it has games, because an empty tail says
 * nothing a four-row list does not. A head row is drawn at zero games and keeps its
 * full-width track, since a gap in a distribution is information; it goes muted rather
 * than missing. Bar width and printed percent are the same number over the same total,
 * the placed games, so a bar can never disagree with the text beside it, and each bar
 * carries its own placement and count, so there is no axis to read across and no colour
 * to interpret.
 */
import type { StatsPlacement } from "../api/types";
import { num, ordinal } from "../lib/format";

export interface PlacementBarsProps {
  rows: StatsPlacement[];
}

const HEAD_PLACEMENTS = [1, 2, 3, 4];

/** The first placement of the tail row, and the label that names it. */
const TAIL_FROM = 5;
const TAIL_LABEL = "Other";

/** The label column holds the widest label on one line and never wraps: a wrapped label
 * would leave the bar beside it sitting between two lines of text. Every row shares the
 * width, so the bars all start at the same place. */
const LABEL_CLASS = "t-figure w-[54px] shrink-0 text-right text-[12px] whitespace-nowrap";

interface PlacementRow {
  label: string;
  games: number;
  percent: number;
}

/** The rows as they are drawn, every percent taken over the placed games. */
export function placementRows(rows: StatsPlacement[]): PlacementRow[] {
  const counts = new Map(rows.map((row) => [row.placement, row.games]));
  const total = rows.reduce((sum, row) => sum + row.games, 0);
  const tail = rows.reduce(
    (sum, row) => (row.placement >= TAIL_FROM ? sum + row.games : sum),
    0,
  );
  const share = (games: number) => (total === 0 ? 0 : Math.round((games / total) * 100));

  const head = HEAD_PLACEMENTS.map((placement) => {
    const games = counts.get(placement) ?? 0;
    return { label: ordinal(placement), games, percent: share(games) };
  });
  return tail > 0 ? [...head, { label: TAIL_LABEL, games: tail, percent: share(tail) }] : head;
}

export function PlacementBars({ rows }: PlacementBarsProps) {
  return (
    <section className="flex flex-col gap-2 rounded-[10px] border border-line bg-panel p-3">
      <h2 className="text-[13px] font-semibold">Placement</h2>
      <ul className="flex flex-col gap-1.5">
        {placementRows(rows).map((row) => {
          const tone = row.games === 0 ? "text-muted" : "text-text";
          return (
            <li
              key={row.label}
              data-testid="placement-row"
              className="flex items-center gap-2"
            >
              <span
                data-testid="placement-label"
                className={`${LABEL_CLASS} ${tone}`}
              >
                {row.label}
              </span>
              <span className="h-[4px] min-w-0 flex-1 rounded-[2px] bg-panel-2">
                <span
                  data-testid="placement-bar"
                  className="block h-full rounded-[2px] bg-accent"
                  style={{ width: `${row.percent}%` }}
                />
              </span>
              <span
                data-testid="placement-count"
                className={`t-figure w-[80px] shrink-0 text-[11px] ${tone}`}
              >
                {num(row.games)} ({row.percent}%)
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
