/**
 * The last twenty games the workers logged, newest first.
 *
 * The API already orders them, so this never sorts: the list is a log, and a log that
 * reorders itself is a different thing. A null mode, map, brawler or rank reads
 * "Not recorded" rather than blank, so an empty cell always means the column is empty and
 * never that something failed to render.
 */
import type { StatsGame, StatsRange } from "../api/types";
import { BrawlerIcon } from "../components/ui/BrawlerIcon";
import { Table, type Column } from "../components/ui/Table";
import { modeName, NOT_RECORDED } from "../lib/copy";
import { signed } from "../lib/format";
import { formatMoment } from "./format";

export interface RecentGamesProps {
  rows: StatsGame[];
  /** Which range is showing. A list of days that says only hh:mm reads as if it were
   * unsorted, so anything wider than today carries the day too. */
  range: StatsRange;
}

const EMPTY = "No games in this range.";

function trophyTone(change: number): string {
  if (change > 0) return "text-accent";
  if (change < 0) return "text-bad";
  return "text-muted";
}

function muted(value: string | null) {
  return value === null || value === "" ? (
    <span className="text-muted">{NOT_RECORDED}</span>
  ) : (
    value
  );
}

/** Built per render rather than once at module level, because the Time column reads the
 * range. Everything else in it is constant. */
function columnsFor(range: StatsRange): Column<StatsGame>[] {
  return [
    {
      key: "t",
      label: "Time",
      mono: true,
      width: range === "today" ? "70px" : "120px",
      render: (row) => formatMoment(row.t, range),
    },
    {
      key: "instance",
      label: "Instance",
      mono: true,
      width: "110px",
      render: (row) => muted(row.instance),
    },
    {
      key: "brawler",
      label: "Brawler",
      render: (row) => (
        <span className="flex items-center gap-2">
          <BrawlerIcon name={row.brawler} />
          <span className="font-mono">{muted(row.brawler)}</span>
        </span>
      ),
    },
    { key: "mode", label: "Mode", render: (row) => muted(modeName(row.mode)) },
    { key: "map", label: "Map", render: (row) => muted(row.map) },
    {
      key: "rank",
      label: "Rank",
      mono: true,
      width: "60px",
      render: (row) =>
        row.rank === null ? (
          <span className="text-muted">{NOT_RECORDED}</span>
        ) : (
          String(row.rank)
        ),
    },
    {
      key: "trophy_change",
      label: "Trophies",
      mono: true,
      width: "80px",
      render: (row) => {
        if (row.trophy_change === null) return <span className="text-muted">{NOT_RECORDED}</span>;
        // A game that moved no trophies is a fact, not a gain: "+0" claims otherwise.
        if (row.trophy_change === 0) return <span className="text-muted">0</span>;
        return (
          <span data-testid="recent-trophies" className={trophyTone(row.trophy_change)}>
            {signed(row.trophy_change)}
          </span>
        );
      },
    },
  ];
}

export function RecentGames({ rows, range }: RecentGamesProps) {
  return (
    <section className="flex flex-col gap-2 rounded-[10px] border border-line bg-panel p-3">
      <h2 className="text-[13px] font-semibold">Recent games</h2>
      <Table
        columns={columnsFor(range)}
        rows={rows}
        rowKey={(row) => `${row.instance ?? ""}-${row.t}-${row.brawler ?? ""}`}
        empty={EMPTY}
      />
    </section>
  );
}
