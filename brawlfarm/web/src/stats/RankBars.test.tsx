/** Ten rows, rank 1 at the top, including the ranks nobody finished at, each with a
 * direct label rather than an axis. */
import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RankBars } from "./RankBars";
import type { StatsRank } from "../api/types";
import { renderWithProviders } from "../test/renderWithProviders";

const ROWS: StatsRank[] = [
  { rank: 1, games: 12 },
  { rank: 2, games: 24 },
  { rank: 4, games: 14 },
];

describe("RankBars", () => {
  it("is headed Rank distribution", () => {
    renderWithProviders(<RankBars rows={ROWS} />);
    expect(screen.getByRole("heading", { name: "Rank distribution" })).toBeInTheDocument();
  });

  it("draws ten rows from 1 to 10, including the empty ones", () => {
    renderWithProviders(<RankBars rows={ROWS} />);
    const rows = screen.getAllByTestId("rank-row");
    expect(rows).toHaveLength(10);
    expect(rows.map((row) => within(row).getByTestId("rank-label").textContent)).toEqual([
      "1",
      "2",
      "3",
      "4",
      "5",
      "6",
      "7",
      "8",
      "9",
      "10",
    ]);
  });

  it("labels each bar with its count and its whole-percent share", () => {
    renderWithProviders(<RankBars rows={ROWS} />);
    const rows = screen.getAllByTestId("rank-row");
    expect(within(rows[0]).getByTestId("rank-count")).toHaveTextContent("12 (24%)");
    expect(within(rows[1]).getByTestId("rank-count")).toHaveTextContent("24 (48%)");
    expect(within(rows[2]).getByTestId("rank-count")).toHaveTextContent("0 (0%)");
  });

  it("scales every bar to the largest count", () => {
    renderWithProviders(<RankBars rows={ROWS} />);
    const rows = screen.getAllByTestId("rank-row");
    expect(within(rows[1]).getByTestId("rank-bar")).toHaveStyle({ width: "100%" });
    expect(within(rows[0]).getByTestId("rank-bar")).toHaveStyle({ width: "50%" });
    expect(within(rows[2]).getByTestId("rank-bar")).toHaveStyle({ width: "0%" });
  });

  it("draws ten empty rows when nothing was ranked", () => {
    renderWithProviders(<RankBars rows={[]} />);
    expect(screen.getAllByTestId("rank-row")).toHaveLength(10);
    for (const row of screen.getAllByTestId("rank-row")) {
      expect(within(row).getByTestId("rank-count")).toHaveTextContent("0 (0%)");
    }
  });
});
