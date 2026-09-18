/**
 * Where the farming finished: five rows, rank 1 at the top.
 *
 * Ranks 1 to 4 keep their own rows. Ranks 5 to 10 are summed into one, because six
 * near-empty bars set the height of the panel beside this one without saying anything the
 * single tail row does not. A row is drawn at zero games and keeps its full-width track,
 * since a gap in a distribution is information; it goes muted rather than missing. Bar
 * width and printed percent are the same number over the same total, so a bar can never
 * disagree with the text beside it, and each bar carries its own rank and count, so there
 * is no axis to read across and no colour to interpret.
 */
import type { StatsRank } from "../api/types";
import { num } from "../lib/format";

export interface RankBarsProps {
  rows: StatsRank[];
}

const HEAD_RANKS = [1, 2, 3, 4];

/** The first rank of the tail row, and the label that names it. The two are written out
 * together because nothing derives one from the other. */
const TAIL_FROM = 5;
const TAIL_LABEL = "5 to 10";

/** The label column holds the tail label on one line and never wraps: "5 to 10" is seven
 * characters at the 12 px mono size, near 50 px, and a wrapped label would leave the bar
 * beside it sitting between two lines of text. Every row shares the width, so the bars
 * all start at the same place. */
const LABEL_CLASS = "t-figure w-[54px] shrink-0 text-right text-[12px] whitespace-nowrap";

interface RankRow {
  label: string;
  games: number;
  percent: number;
}

/** The five rows as they are drawn, every percent taken over the one shared total. */
export function rankRows(rows: StatsRank[]): RankRow[] {
  const counts = new Map(rows.map((row) => [row.rank, row.games]));
  const total = rows.reduce((sum, row) => sum + row.games, 0);
  const tail = rows.reduce(
    (sum, row) => (row.rank >= TAIL_FROM ? sum + row.games : sum),
    0,
  );
  const share = (games: number) => (total === 0 ? 0 : Math.round((games / total) * 100));

  return [
    ...HEAD_RANKS.map((rank) => {
      const games = counts.get(rank) ?? 0;
      return { label: String(rank), games, percent: share(games) };
    }),
    { label: TAIL_LABEL, games: tail, percent: share(tail) },
  ];
}

export function RankBars({ rows }: RankBarsProps) {
  return (
    <section className="flex flex-col gap-2 rounded-[10px] border border-line bg-panel p-3">
      <h2 className="text-[13px] font-semibold">Rank distribution</h2>
      <ul className="flex flex-col gap-1.5">
        {rankRows(rows).map((row) => {
          const tone = row.games === 0 ? "text-muted" : "text-text";
          return (
            <li
              key={row.label}
              data-testid="rank-row"
              className="flex items-center gap-2"
            >
              <span
                data-testid="rank-label"
                className={`${LABEL_CLASS} ${tone}`}
              >
                {row.label}
              </span>
              <span className="h-[4px] min-w-0 flex-1 rounded-[2px] bg-panel-2">
                <span
                  data-testid="rank-bar"
                  className="block h-full rounded-[2px] bg-accent"
                  style={{ width: `${row.percent}%` }}
                />
              </span>
              <span
                data-testid="rank-count"
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
