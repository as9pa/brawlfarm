/** The last twenty games, newest first, with "none" where the API had nothing to say. */
import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RecentGames } from "./RecentGames";
import type { StatsGame } from "../api/types";
import { renderWithProviders } from "../test/renderWithProviders";

function game(overrides: Partial<StatsGame> = {}): StatsGame {
  return {
    instance: "Pie64",
    t: "2026-09-12T22:00:00",
    brawler: "NORI",
    rank: 1,
    trophy_change: 17,
    map: "Feast or Famine",
    mode: "soloShowdown",
    ...overrides,
  };
}

describe("RecentGames", () => {
  it("is headed Recent games and shows the seven columns", () => {
    renderWithProviders(<RecentGames rows={[game()]} />);
    expect(screen.getByRole("heading", { name: "Recent games" })).toBeInTheDocument();
    expect(screen.getAllByRole("columnheader").map((n) => n.textContent)).toEqual([
      "Time",
      "Instance",
      "Brawler",
      "Mode",
      "Map",
      "Rank",
      "Trophies",
    ]);
  });

  it("keeps the API's order, newest first, for twenty rows", () => {
    const rows = Array.from({ length: 20 }, (_, i) =>
      game({ t: `2026-09-12T22:${String(59 - i).padStart(2, "0")}:00`, rank: (i % 10) + 1 }),
    );
    renderWithProviders(<RecentGames rows={rows} />);
    const body = screen.getAllByRole("row").slice(1);
    expect(body).toHaveLength(20);
    expect(within(body[0]).getAllByRole("cell")[0]).toHaveTextContent("22:59");
    expect(within(body[19]).getAllByRole("cell")[0]).toHaveTextContent("22:40");
  });

  it("renders an icon beside every brawler name", () => {
    renderWithProviders(<RecentGames rows={[game(), game({ t: "2026-09-12T21:00:00" })]} />);
    expect(screen.getAllByTestId("brawler-icon")).toHaveLength(2);
  });

  it("says none for a null mode, a null map and a null brawler", () => {
    renderWithProviders(
      <RecentGames rows={[game({ mode: null, map: null, brawler: null, rank: null })]} />,
    );
    const cells = screen.getAllByRole("row")[1].querySelectorAll("td");
    expect(cells[2]).toHaveTextContent("none");
    expect(cells[3]).toHaveTextContent("none");
    expect(cells[4]).toHaveTextContent("none");
    expect(cells[5]).toHaveTextContent("none");
  });

  it("signs and tints the trophy change", () => {
    renderWithProviders(
      <RecentGames rows={[game({ trophy_change: -3, t: "2026-09-12T21:00:00" }), game()]} />,
    );
    const values = screen.getAllByTestId("recent-trophies");
    expect(values[0]).toHaveTextContent("-3");
    expect(values[0]).toHaveClass("text-bad");
    expect(values[1]).toHaveTextContent("+17");
    expect(values[1]).toHaveClass("text-accent");
  });

  it("says so when the range has no games", () => {
    renderWithProviders(<RecentGames rows={[]} />);
    expect(screen.getByText("No games in this range.")).toBeInTheDocument();
  });
});
