/** Four tiles, 1st to 4th: a signed one-decimal average tinted by its sign, a game count
 * under it, and "Not yet" where nobody finished there. */
import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TrophiesByPlacement } from "./TrophiesByPlacement";
import type { StatsTrophiesByPlacement } from "../api/types";
import { renderWithProviders } from "../test/renderWithProviders";

const ROWS: StatsTrophiesByPlacement[] = [
  { placement: 1, games: 14, avg: 11.74 },
  { placement: 2, games: 9, avg: 0 },
  { placement: 3, games: 0, avg: null },
  { placement: 4, games: 3, avg: -3.6 },
];

function tiles(): HTMLElement[] {
  return screen.getAllByTestId("trophies-tile");
}

describe("TrophiesByPlacement", () => {
  it("is headed Trophies by placement and draws a tile for 1st to 4th", () => {
    renderWithProviders(<TrophiesByPlacement rows={ROWS} />);
    expect(screen.getByRole("heading", { name: "Trophies by placement" })).toBeInTheDocument();
    expect(tiles().map((tile) => tile.firstChild?.textContent)).toEqual([
      "1st",
      "2nd",
      "3rd",
      "4th",
    ]);
  });

  it("signs the average to one decimal and counts the games under it", () => {
    renderWithProviders(<TrophiesByPlacement rows={ROWS} />);
    const [first, second, , fourth] = tiles();
    expect(within(first).getByTestId("trophies-value")).toHaveTextContent("+11.7");
    expect(within(first).getByTestId("trophies-games")).toHaveTextContent("n = 14");
    expect(within(second).getByTestId("trophies-value")).toHaveTextContent("0.0");
    expect(within(fourth).getByTestId("trophies-value")).toHaveTextContent("-3.6");
  });

  it("tints a gain accent and a loss red, and mutes a value under five games", () => {
    renderWithProviders(
      <TrophiesByPlacement
        rows={[
          { placement: 1, games: 5, avg: 11.7 },
          { placement: 2, games: 6, avg: -2 },
          { placement: 3, games: 4, avg: 3 },
          { placement: 4, games: 4, avg: -3 },
        ]}
      />,
    );
    const values = screen.getAllByTestId("trophies-value");
    expect(values[0]).toHaveClass("text-accent");
    expect(values[1]).toHaveClass("text-bad");
    expect(values[2]).toHaveClass("text-muted");
    expect(values[3]).toHaveClass("text-muted");
    for (const value of values) expect(value).toHaveClass("t-figure");
  });

  it("says Not yet with no count line when there is no average", () => {
    renderWithProviders(<TrophiesByPlacement rows={ROWS} />);
    const third = tiles()[2];
    expect(within(third).getByTestId("trophies-value")).toHaveTextContent("Not yet");
    expect(within(third).queryByTestId("trophies-games")).toBeNull();
  });

  it("lays the tiles out four across, two across under 520 px", () => {
    renderWithProviders(<TrophiesByPlacement rows={ROWS} />);
    const grid = tiles()[0].parentElement as HTMLElement;
    expect(grid).toHaveClass("grid-cols-2");
    expect(grid).toHaveClass("min-[520px]:grid-cols-4");
  });
});
