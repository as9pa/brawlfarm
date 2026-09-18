/** Five rows, rank 1 at the top and ranks 5 to 10 summed into the last one, each with a
 * direct label rather than an axis. */
import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RankBars, rankRows } from "./RankBars";
import type { StatsRank } from "../api/types";
import { renderWithProviders } from "../test/renderWithProviders";

const ROWS: StatsRank[] = [
  { rank: 1, games: 12 },
  { rank: 2, games: 24 },
  { rank: 4, games: 14 },
];

/** Six thin ranks, which the panel reads as one row of four games. */
const TAIL: StatsRank[] = [
  { rank: 5, games: 1 },
  { rank: 6, games: 0 },
  { rank: 7, games: 2 },
  { rank: 8, games: 0 },
  { rank: 9, games: 0 },
  { rank: 10, games: 1 },
];

describe("RankBars", () => {
  it("is headed Rank distribution", () => {
    renderWithProviders(<RankBars rows={ROWS} />);
    expect(screen.getByRole("heading", { name: "Rank distribution" })).toBeInTheDocument();
  });

  it("draws five rows, ranks 1 to 4 and one for 5 to 10", () => {
    renderWithProviders(<RankBars rows={ROWS} />);
    const rows = screen.getAllByTestId("rank-row");
    expect(rows).toHaveLength(5);
    expect(rows.map((row) => within(row).getByTestId("rank-label").textContent)).toEqual([
      "1",
      "2",
      "3",
      "4",
      "5 to 10",
    ]);
  });

  it("labels each bar with its count and its whole-percent share", () => {
    renderWithProviders(<RankBars rows={ROWS} />);
    const rows = screen.getAllByTestId("rank-row");
    expect(within(rows[0]).getByTestId("rank-count")).toHaveTextContent("12 (24%)");
    expect(within(rows[1]).getByTestId("rank-count")).toHaveTextContent("24 (48%)");
    expect(within(rows[2]).getByTestId("rank-count")).toHaveTextContent("0 (0%)");
  });

  it("scales every bar to the total, so the bar and the percent share a basis", () => {
    renderWithProviders(<RankBars rows={ROWS} />);
    const rows = screen.getAllByTestId("rank-row");
    expect(within(rows[1]).getByTestId("rank-count")).toHaveTextContent("24 (48%)");
    expect(within(rows[1]).getByTestId("rank-bar")).toHaveStyle({ width: "48%" });
    expect(within(rows[0]).getByTestId("rank-bar")).toHaveStyle({ width: "24%" });
    expect(within(rows[2]).getByTestId("rank-bar")).toHaveStyle({ width: "0%" });
  });

  it("sums ranks 5 to 10 into one row", () => {
    renderWithProviders(<RankBars rows={TAIL} />);
    const rows = screen.getAllByTestId("rank-row");
    expect(rows).toHaveLength(5);
    expect(within(rows[4]).getByTestId("rank-label")).toHaveTextContent("5 to 10");
    // The label column is wide enough for the tail label and forbids the wrap outright,
    // so the bar beside it can never sit between two lines of text.
    expect(within(rows[4]).getByTestId("rank-label")).toHaveClass("whitespace-nowrap");
    expect(within(rows[4]).getByTestId("rank-count")).toHaveTextContent("4 (100%)");
  });

  it("mutes the 5 to 10 row when nobody finished there", () => {
    renderWithProviders(<RankBars rows={ROWS} />);
    const rows = screen.getAllByTestId("rank-row");
    expect(within(rows[4]).getByTestId("rank-label")).toHaveClass("text-muted");
    expect(within(rows[4]).getByTestId("rank-count")).toHaveClass("text-muted");
    expect(within(rows[0]).getByTestId("rank-count")).not.toHaveClass("text-muted");
  });

  it("draws five empty rows when nothing was ranked", () => {
    renderWithProviders(<RankBars rows={[]} />);
    expect(screen.getAllByTestId("rank-row")).toHaveLength(5);
    for (const row of screen.getAllByTestId("rank-row")) {
      expect(within(row).getByTestId("rank-count")).toHaveTextContent("0 (0%)");
    }
  });
});

describe("rankRows", () => {
  it("keeps ranks 1 to 4 and collapses the rest over the one shared total", () => {
    expect(rankRows(ROWS)).toEqual([
      { label: "1", games: 12, percent: 24 },
      { label: "2", games: 24, percent: 48 },
      { label: "3", games: 0, percent: 0 },
      { label: "4", games: 14, percent: 28 },
      { label: "5 to 10", games: 0, percent: 0 },
    ]);
  });
});
