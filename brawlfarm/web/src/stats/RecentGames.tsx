/**
 * The last twenty games the workers logged, newest first.
 *
 * The API already orders them, so this never sorts: the list is a log, and a log that
 * reorders itself is a different thing. A null mode, map, brawler or rank reads "none"
 * rather than blank, so an empty cell always means the column is empty and never that
 * something failed to render.
 */
import type { StatsGame } from "../api/types";
import { BrawlerIcon } from "../components/ui/BrawlerIcon";
import { Table, type Column } from "../components/ui/Table";
import { signed } from "../lib/format";
import { hhmm } from "../lib/time";

export interface RecentGamesProps {
  rows: StatsGame[];
}

const NONE = "none";
const EMPTY = "No games in this range.";

function trophyTone(change: number): string {
  if (change > 0) return "text-accent";
  if (change < 0) return "text-bad";
  return "text-muted";
}

function muted(value: string | null) {
  return value === null || value === "" ? <span className="text-muted">{NONE}</span> : value;
}

const columns: Column<StatsGame>[] = [
  { key: "t", label: "Time", mono: true, width: "70px", render: (row) => hhmm(row.t) },
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
  { key: "mode", label: "Mode", render: (row) => muted(row.mode) },
  { key: "map", label: "Map", render: (row) => muted(row.map) },
  {
    key: "rank",
    label: "Rank",
    mono: true,
    width: "60px",
    render: (row) =>
      row.rank === null ? <span className="text-muted">{NONE}</span> : String(row.rank),
  },
  {
    key: "trophy_change",
    label: "Trophies",
    mono: true,
    width: "80px",
    render: (row) =>
      row.trophy_change === null ? (
        <span className="text-muted">{NONE}</span>
      ) : (
        <span data-testid="recent-trophies" className={trophyTone(row.trophy_change)}>
          {signed(row.trophy_change)}
        </span>
      ),
  },
];

export function RecentGames({ rows }: RecentGamesProps) {
  return (
    <section className="flex flex-col gap-2 rounded-[10px] border border-line bg-panel p-3">
      <h2 className="text-[13px] font-semibold">Recent games</h2>
      <Table
        columns={columns}
        rows={rows}
        rowKey={(row) => `${row.instance ?? ""}-${row.t}-${row.brawler ?? ""}`}
        empty={EMPTY}
      />
    </section>
  );
}
