/** The per-brawler table: games descending by default, a click that sorts descending
 * first and then toggles, aria-sort following it, and an icon in front of every name. */
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { BrawlerTable } from "./BrawlerTable";
import type { StatsBrawler } from "../api/types";
import { renderWithProviders } from "../test/renderWithProviders";

const ROWS: StatsBrawler[] = [
  { name: "NORI", games: 3, net: 29, avg_rank: 2.7, top4_rate: 100 },
  { name: "SHELLY", games: 1, net: -8, avg_rank: 5, top4_rate: 0 },
  { name: "COLT", games: 3, net: 4, avg_rank: 4.5, top4_rate: 50 },
];

function names(): string[] {
  return screen
    .getAllByRole("row")
    .slice(1)
    .map((row) => within(row).getAllByRole("cell")[1].textContent ?? "");
}

describe("BrawlerTable", () => {
  it("shows the six columns", () => {
    renderWithProviders(<BrawlerTable rows={ROWS} />);
    expect(screen.getAllByRole("columnheader").map((n) => n.textContent)).toEqual([
      "icon",
      "Brawler",
      "Games",
      "Net",
      "Avg rank",
      "Top 4",
    ]);
  });

  it("starts games descending, with name ascending breaking the tie", () => {
    renderWithProviders(<BrawlerTable rows={ROWS} />);
    expect(names()).toEqual(["COLT", "NORI", "SHELLY"]);
    expect(screen.getByRole("columnheader", { name: /Games/ })).toHaveAttribute(
      "aria-sort",
      "descending",
    );
  });

  it("sorts a new column descending first, then toggles it", async () => {
    renderWithProviders(<BrawlerTable rows={ROWS} />);
    await userEvent.click(screen.getByRole("button", { name: /Net/ }));
    expect(names()).toEqual(["NORI", "COLT", "SHELLY"]);
    expect(screen.getByRole("columnheader", { name: /Net/ })).toHaveAttribute(
      "aria-sort",
      "descending",
    );
    await userEvent.click(screen.getByRole("button", { name: /Net/ }));
    expect(names()).toEqual(["SHELLY", "COLT", "NORI"]);
    expect(screen.getByRole("columnheader", { name: /Net/ })).toHaveAttribute(
      "aria-sort",
      "ascending",
    );
    expect(screen.getByRole("columnheader", { name: /Games/ })).toHaveAttribute(
      "aria-sort",
      "none",
    );
  });

  it("sorts by name too", async () => {
    renderWithProviders(<BrawlerTable rows={ROWS} />);
    await userEvent.click(screen.getByRole("button", { name: /Brawler/ }));
    expect(names()).toEqual(["SHELLY", "NORI", "COLT"]);
  });

  it("puts a null avg rank and a null top-4 rate last, whichever way it is sorted", async () => {
    renderWithProviders(
      <BrawlerTable
        rows={[
          { name: "NORI", games: 1, net: 3, avg_rank: null, top4_rate: null },
          { name: "COLT", games: 1, net: 3, avg_rank: 2, top4_rate: 50 },
        ]}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: /Avg rank/ }));
    expect(names()).toEqual(["COLT", "NORI"]);
    await userEvent.click(screen.getByRole("button", { name: /Avg rank/ }));
    expect(names()).toEqual(["COLT", "NORI"]);
  });

  it("tints the net figure by its sign and shows its sign", () => {
    renderWithProviders(<BrawlerTable rows={ROWS} />);
    const shelly = screen.getAllByRole("row").find((r) => r.textContent?.includes("SHELLY"));
    expect(within(shelly as HTMLElement).getByTestId("brawler-net")).toHaveTextContent("-8");
    expect(within(shelly as HTMLElement).getByTestId("brawler-net")).toHaveClass("text-bad");
  });

  it("gives every row an icon and the icon column no sort button", () => {
    renderWithProviders(<BrawlerTable rows={ROWS} />);
    expect(screen.getAllByTestId("brawler-icon")).toHaveLength(3);
    expect(
      within(screen.getByRole("columnheader", { name: "icon" })).queryByRole("button"),
    ).toBeNull();
  });

  it("says so when the range has no games", () => {
    renderWithProviders(<BrawlerTable rows={[]} />);
    expect(screen.getByText("No games in this range.")).toBeInTheDocument();
  });
});
