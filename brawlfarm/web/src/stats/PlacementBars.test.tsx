/** Four rows, 1st at the top, plus an "Other" row only when a placement past 4th has
 * games, each with a direct label rather than an axis. */
import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PlacementBars, placementRows } from "./PlacementBars";
import type { StatsPlacement } from "../api/types";
import { renderWithProviders } from "../test/renderWithProviders";

const ROWS: StatsPlacement[] = [
  { placement: 1, games: 12 },
  { placement: 2, games: 24 },
  { placement: 4, games: 14 },
];

/** Thin placements past 4th, which the panel reads as one row. */
const TAIL: StatsPlacement[] = [
  { placement: 1, games: 4 },
  { placement: 5, games: 1 },
  { placement: 7, games: 2 },
  { placement: 10, games: 1 },
];

describe("PlacementBars", () => {
  it("is headed Placement", () => {
    renderWithProviders(<PlacementBars rows={ROWS} />);
    expect(screen.getByRole("heading", { name: "Placement" })).toBeInTheDocument();
  });

  it("draws four rows, 1st to 4th, and no Other row when nothing finished past 4th", () => {
    renderWithProviders(<PlacementBars rows={ROWS} />);
    const rows = screen.getAllByTestId("placement-row");
    expect(rows.map((row) => within(row).getByTestId("placement-label").textContent)).toEqual([
      "1st",
      "2nd",
      "3rd",
      "4th",
    ]);
  });

  it("labels each bar with its count and its whole-percent share", () => {
    renderWithProviders(<PlacementBars rows={ROWS} />);
    const rows = screen.getAllByTestId("placement-row");
    expect(within(rows[0]).getByTestId("placement-count")).toHaveTextContent("12 (24%)");
    expect(within(rows[1]).getByTestId("placement-count")).toHaveTextContent("24 (48%)");
    expect(within(rows[2]).getByTestId("placement-count")).toHaveTextContent("0 (0%)");
  });

  it("draws each bar at the width of its printed percent", () => {
    renderWithProviders(<PlacementBars rows={ROWS} />);
    const rows = screen.getAllByTestId("placement-row");
    expect(within(rows[1]).getByTestId("placement-bar")).toHaveStyle({ width: "48%" });
    expect(within(rows[0]).getByTestId("placement-bar")).toHaveStyle({ width: "24%" });
    expect(within(rows[2]).getByTestId("placement-bar")).toHaveStyle({ width: "0%" });
  });

  it("sums every placement past 4th into one Other row over the placed games", () => {
    renderWithProviders(<PlacementBars rows={TAIL} />);
    const rows = screen.getAllByTestId("placement-row");
    expect(rows).toHaveLength(5);
    expect(within(rows[4]).getByTestId("placement-label")).toHaveTextContent("Other");
    expect(within(rows[4]).getByTestId("placement-label")).toHaveClass("whitespace-nowrap");
    expect(within(rows[4]).getByTestId("placement-count")).toHaveTextContent("4 (50%)");
    expect(within(rows[0]).getByTestId("placement-count")).toHaveTextContent("4 (50%)");
  });

  it("mutes a row with no games and leaves the others at full strength", () => {
    renderWithProviders(<PlacementBars rows={ROWS} />);
    const rows = screen.getAllByTestId("placement-row");
    expect(within(rows[2]).getByTestId("placement-label")).toHaveClass("text-muted");
    expect(within(rows[2]).getByTestId("placement-count")).toHaveClass("text-muted");
    expect(within(rows[0]).getByTestId("placement-count")).not.toHaveClass("text-muted");
  });

  it("still draws 1st to 4th at zero when there are no games", () => {
    renderWithProviders(<PlacementBars rows={[]} />);
    expect(screen.getAllByTestId("placement-row")).toHaveLength(4);
    for (const row of screen.getAllByTestId("placement-row")) {
      expect(within(row).getByTestId("placement-count")).toHaveTextContent("0 (0%)");
    }
  });
});

describe("placementRows", () => {
  it("keeps 1st to 4th and adds Other only when it has games", () => {
    expect(placementRows(ROWS)).toEqual([
      { label: "1st", games: 12, percent: 24 },
      { label: "2nd", games: 24, percent: 48 },
      { label: "3rd", games: 0, percent: 0 },
      { label: "4th", games: 14, percent: 28 },
    ]);
    expect(placementRows([...ROWS, { placement: 6, games: 0 }])).toHaveLength(4);
    expect(placementRows(TAIL)[4]).toEqual({ label: "Other", games: 4, percent: 50 });
  });
});
