/**
 * Which brawlers did the farming, and how they did.
 *
 * Sort state is this component's, not the URL's: it is a way of reading one table rather
 * than a view worth linking to, and the range and the selection are already in the URL.
 * The first click on a column sorts it descending, because every column here is a "most
 * of" question; the second toggles. Ties break on name ascending, which is the order the
 * API already returns.
 *
 * A null average placement or win rate sorts last in both directions: a brawler with no
 * recorded placement is missing a number, not holding the worst one.
 */
import { useState } from "react";

import type { StatsBrawler } from "../api/types";
import { BrawlerIcon } from "../components/ui/BrawlerIcon";
import { Table, type Column } from "../components/ui/Table";
import { NOT_RECORDED } from "../lib/copy";
import { signed } from "../lib/format";

export interface BrawlerTableProps {
  rows: StatsBrawler[];
}

type SortKey = "name" | "games" | "net" | "avg_placement" | "win_rate";

const EMPTY = "No games in this range.";

function netTone(net: number): string {
  if (net > 0) return "text-accent";
  if (net < 0) return "text-bad";
  return "text-muted";
}

function compare(a: StatsBrawler, b: StatsBrawler, key: SortKey, dir: "asc" | "desc"): number {
  if (key === "name") {
    return dir === "asc" ? a.name.localeCompare(b.name) : b.name.localeCompare(a.name);
  }
  const left = a[key];
  const right = b[key];
  // A missing number is not a small one: it goes last whichever way the column points.
  if (left === null && right === null) return a.name.localeCompare(b.name);
  if (left === null) return 1;
  if (right === null) return -1;
  if (left !== right) return dir === "asc" ? left - right : right - left;
  return a.name.localeCompare(b.name);
}

export function BrawlerTable({ rows }: BrawlerTableProps) {
  const [sort, setSort] = useState<{ key: SortKey; dir: "asc" | "desc" }>({
    key: "games",
    dir: "desc",
  });

  const sorted = [...rows].sort((a, b) => compare(a, b, sort.key, sort.dir));

  const columns: Column<StatsBrawler>[] = [
    { key: "icon", label: "", width: "34px", render: (row) => <BrawlerIcon name={row.name} /> },
    { key: "name", label: "Brawler", mono: true, sortable: true, render: (row) => row.name },
    {
      key: "games",
      label: "Games",
      mono: true,
      sortable: true,
      render: (row) => String(row.games),
    },
    {
      key: "net",
      label: "Net",
      mono: true,
      sortable: true,
      render: (row) => (
        <span data-testid="brawler-net" className={netTone(row.net)}>
          {signed(row.net)}
        </span>
      ),
    },
    {
      key: "avg_placement",
      label: "Avg placement",
      mono: true,
      sortable: true,
      render: (row) =>
        row.avg_placement === null ? NOT_RECORDED : row.avg_placement.toFixed(1),
    },
    {
      key: "win_rate",
      label: "Wins",
      mono: true,
      sortable: true,
      render: (row) => (row.win_rate === null ? NOT_RECORDED : `${Math.round(row.win_rate)}%`),
    },
  ];

  return (
    <Table
      columns={columns}
      rows={sorted}
      rowKey={(row) => row.name}
      empty={EMPTY}
      sort={sort}
      onSort={(key) =>
        setSort((current) =>
          current.key === key
            ? { key: current.key, dir: current.dir === "desc" ? "asc" : "desc" }
            : { key: key as SortKey, dir: "desc" },
        )
      }
    />
  );
}
