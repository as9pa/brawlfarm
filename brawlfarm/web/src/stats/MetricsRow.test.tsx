/** Six figures on one line: their labels, their formatting, and the two placeholders that
 * stand in for a number that would be a lie. */
import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MetricsRow } from "./MetricsRow";
import type { StatsPlacement, StatsSummary } from "../api/types";
import { renderWithProviders } from "../test/renderWithProviders";

function summary(overrides: Partial<StatsSummary> = {}): StatsSummary {
  return {
    games: 4,
    trophies: 37,
    trophies_per_hour: 24.7,
    avg_placement: 3.3,
    win_rate: 75,
    hours_farmed: 1.53,
    trophies_by_placement: [],
    ...overrides,
  };
}

/** Twelve placed games, enough for the placement figures to read at full strength. */
const PLACED: StatsPlacement[] = [
  { placement: 1, games: 9 },
  { placement: 3, games: 3 },
];

function figure(label: string): HTMLElement {
  return screen.getByTestId(`metric-${label}`);
}

describe("MetricsRow", () => {
  it("shows the six labels in order", () => {
    renderWithProviders(<MetricsRow summary={summary()} placements={PLACED} />);
    // The value spans are metric-value, which the label testids would otherwise match.
    const labels = screen.getAllByTestId(/^metric-(?!value$)/).map((node) => {
      const caption = node.querySelector("[data-label]");
      return caption?.textContent ?? "";
    });
    expect(labels).toEqual([
      "Games",
      "Trophies",
      "Trophies per hour",
      "Average placement",
      "Win rate",
      "Time farmed",
    ]);
  });

  it("formats every figure", () => {
    renderWithProviders(<MetricsRow summary={summary()} placements={PLACED} />);
    expect(within(figure("Games")).getByTestId("metric-value")).toHaveTextContent("4");
    expect(within(figure("Trophies")).getByTestId("metric-value")).toHaveTextContent("+37");
    expect(within(figure("Trophies per hour")).getByTestId("metric-value")).toHaveTextContent(
      "24.7",
    );
    expect(within(figure("Average placement")).getByTestId("metric-value")).toHaveTextContent("3.3");
    expect(within(figure("Win rate")).getByTestId("metric-value")).toHaveTextContent("75%");
    expect(within(figure("Time farmed")).getByTestId("metric-value")).toHaveTextContent(
      "1 h 32 min",
    );
  });

  it("reads time farmed in hours and minutes", () => {
    renderWithProviders(<MetricsRow placements={PLACED} summary={summary({ hours_farmed: 1.85 })} />);
    expect(within(figure("Time farmed")).getByTestId("metric-value")).toHaveTextContent(
      "1 h 51 min",
    );
  });

  it("groups a five-figure game count", () => {
    renderWithProviders(<MetricsRow placements={PLACED} summary={summary({ games: 110738 })} />);
    expect(within(figure("Games")).getByTestId("metric-value")).toHaveTextContent("110,738");
  });

  it("tints the trophy figure by its sign", () => {
    const { unmount } = renderWithProviders(<MetricsRow summary={summary()} placements={PLACED} />);
    expect(within(figure("Trophies")).getByTestId("metric-value")).toHaveClass("text-accent");
    unmount();
    const second = renderWithProviders(<MetricsRow placements={PLACED} summary={summary({ trophies: -12 })} />);
    expect(within(figure("Trophies")).getByTestId("metric-value")).toHaveClass("text-bad");
    expect(within(figure("Trophies")).getByTestId("metric-value")).toHaveTextContent("-12");
    second.unmount();
    renderWithProviders(<MetricsRow placements={PLACED} summary={summary({ trophies: 0 })} />);
    expect(within(figure("Trophies")).getByTestId("metric-value")).toHaveClass("text-muted");
  });

  it("says After 30 min when the rate is null and games were played", () => {
    renderWithProviders(<MetricsRow placements={PLACED} summary={summary({ trophies_per_hour: null })} />);
    expect(within(figure("Trophies per hour")).getByTestId("metric-value")).toHaveTextContent(
      "After 30 min",
    );
  });

  it("says none when there are no games at all", () => {
    renderWithProviders(
      <MetricsRow
        placements={[]}
        summary={summary({
          games: 0,
          trophies: 0,
          trophies_per_hour: null,
          avg_placement: null,
          win_rate: null,
          hours_farmed: 0,
        })}
      />,
    );
    expect(within(figure("Trophies per hour")).getByTestId("metric-value")).toHaveTextContent(
      "Not yet",
    );
    expect(within(figure("Average placement")).getByTestId("metric-value")).toHaveTextContent(
      "Not yet",
    );
    expect(within(figure("Win rate")).getByTestId("metric-value")).toHaveTextContent("Not yet");
  });

  it("notes that the win rate counts first place only", () => {
    renderWithProviders(<MetricsRow summary={summary()} placements={PLACED} />);
    expect(figure("Win rate").querySelector("[data-note]")).toHaveTextContent("first place");
    expect(figure("Average placement").querySelector("[data-note]")).toBeNull();
  });

  it("says 0% for a win rate of zero", () => {
    renderWithProviders(<MetricsRow summary={summary({ win_rate: 0 })} placements={PLACED} />);
    expect(within(figure("Win rate")).getByTestId("metric-value")).toHaveTextContent("0%");
  });

  it("mutes the placement figures under ten placed games", () => {
    const { unmount } = renderWithProviders(
      <MetricsRow summary={summary()} placements={PLACED} />,
    );
    expect(within(figure("Win rate")).getByTestId("metric-value")).not.toHaveClass("text-muted");
    expect(within(figure("Average placement")).getByTestId("metric-value")).not.toHaveClass(
      "text-muted",
    );
    unmount();
    renderWithProviders(
      <MetricsRow summary={summary()} placements={[{ placement: 2, games: 9 }]} />,
    );
    expect(within(figure("Win rate")).getByTestId("metric-value")).toHaveClass("text-muted");
    expect(within(figure("Average placement")).getByTestId("metric-value")).toHaveClass(
      "text-muted",
    );
    expect(within(figure("Games")).getByTestId("metric-value")).not.toHaveClass("text-muted");
  });

  it("wraps at phone width rather than truncating any cell", () => {
    renderWithProviders(<MetricsRow summary={summary()} placements={PLACED} />);
    const cells = screen.getAllByTestId(/^metric-(?!value$)/);
    expect(cells).toHaveLength(6);
    for (const cell of cells) {
      expect(cell.className).toContain("min-w-[");
      expect(cell.querySelectorAll('[class*="truncate"]')).toHaveLength(0);
      expect(cell.querySelectorAll('[class*="overflow-hidden"]')).toHaveLength(0);
    }
  });

  it("gives every number tabular figures and keeps its unit on the same line", () => {
    renderWithProviders(<MetricsRow summary={summary()} placements={PLACED} />);
    for (const node of screen.getAllByTestId("metric-value")) {
      expect(node).toHaveClass("t-figure");
      expect(node).toHaveClass("whitespace-nowrap");
    }
  });
});
