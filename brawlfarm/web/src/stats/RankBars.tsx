/**
 * Where the farming finished: ten rows, rank 1 at the top.
 *
 * Ranks with no games are drawn anyway, because a gap in a distribution is information
 * and a list that silently skips rank 7 reads as if rank 7 did not exist. Each bar
 * carries its own label at its end, so there is no axis to read across and no gridline to
 * draw.
 */
import type { StatsRank } from "../api/types";

export interface RankBarsProps {
  rows: StatsRank[];
}

const RANKS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];

export function RankBars({ rows }: RankBarsProps) {
  const counts = new Map(rows.map((row) => [row.rank, row.games]));
  const total = rows.reduce((sum, row) => sum + row.games, 0);
  const largest = rows.reduce((most, row) => Math.max(most, row.games), 0);

  return (
    <section className="flex flex-col gap-2 rounded-[10px] border border-line bg-panel p-3">
      <h2 className="text-[13px] font-semibold">Rank distribution</h2>
      <ul className="flex flex-col gap-1.5">
        {RANKS.map((rank) => {
          const games = counts.get(rank) ?? 0;
          const width = largest === 0 ? 0 : Math.round((games / largest) * 100);
          const percent = total === 0 ? 0 : Math.round((games / total) * 100);
          return (
            <li key={rank} data-testid="rank-row" className="flex items-center gap-2">
              <span
                data-testid="rank-label"
                className="w-[18px] shrink-0 text-right font-mono text-[12px] tabular-nums text-muted"
              >
                {rank}
              </span>
              <span className="h-[4px] min-w-0 flex-1 rounded-[2px] bg-panel-2">
                <span
                  data-testid="rank-bar"
                  className="block h-full rounded-[2px] bg-accent"
                  style={{ width: `${width}%` }}
                />
              </span>
              <span
                data-testid="rank-count"
                className="w-[80px] shrink-0 font-mono text-[11px] tabular-nums text-muted"
              >
                {games} ({percent}%)
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
