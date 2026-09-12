/** Six figures on one line: their labels, their formatting, and the two placeholders that
 * stand in for a number that would be a lie. */
import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MetricsRow } from "./MetricsRow";
import type { StatsSummary } from "../api/types";
import { renderWithProviders } from "../test/renderWithProviders";

function summary(overrides: Partial<StatsSummary> = {}): StatsSummary {
  return {
    games: 4,
    trophies: 37,
    trophies_per_hour: 24.7,
    avg_rank: 3.3,
    top4_rate: 75,
    hours_farmed: 1.53,
    ...overrides,
  };
}

function figure(label: string): HTMLElement {
  return screen.getByTestId(`metric-${label}`);
}

describe("MetricsRow", () => {
  it("shows the six labels in order", () => {
    renderWithProviders(<MetricsRow summary={summary()} />);
    // The value spans are metric-value, which the label testids would otherwise match.
    const labels = screen.getAllByTestId(/^metric-(?!value$)/).map((node) => {
      const caption = node.querySelector("[data-label]");
      return caption?.textContent ?? "";
    });
    expect(labels).toEqual([
      "games",
      "trophies",
      "trophies per hour",
      "average rank",
      "top-4 rate",
      "time farmed",
    ]);
  });

  it("formats every figure", () => {
    renderWithProviders(<MetricsRow summary={summary()} />);
    expect(within(figure("games")).getByTestId("metric-value")).toHaveTextContent("4");
    expect(within(figure("trophies")).getByTestId("metric-value")).toHaveTextContent("+37");
    expect(within(figure("trophies per hour")).getByTestId("metric-value")).toHaveTextContent(
      "24.7",
    );
    expect(within(figure("average rank")).getByTestId("metric-value")).toHaveTextContent("3.3");
    expect(within(figure("top-4 rate")).getByTestId("metric-value")).toHaveTextContent("75%");
    expect(within(figure("time farmed")).getByTestId("metric-value")).toHaveTextContent("1.53 h");
  });

  it("tints the trophy figure by its sign", () => {
    const { unmount } = renderWithProviders(<MetricsRow summary={summary()} />);
    expect(within(figure("trophies")).getByTestId("metric-value")).toHaveClass("text-accent");
    unmount();
    const second = renderWithProviders(<MetricsRow summary={summary({ trophies: -12 })} />);
    expect(within(figure("trophies")).getByTestId("metric-value")).toHaveClass("text-bad");
    expect(within(figure("trophies")).getByTestId("metric-value")).toHaveTextContent("-12");
    second.unmount();
    renderWithProviders(<MetricsRow summary={summary({ trophies: 0 })} />);
    expect(within(figure("trophies")).getByTestId("metric-value")).toHaveClass("text-muted");
  });

  it("says after 30 min when the rate is null and games were played", () => {
    renderWithProviders(<MetricsRow summary={summary({ trophies_per_hour: null })} />);
    expect(within(figure("trophies per hour")).getByTestId("metric-value")).toHaveTextContent(
      "after 30 min",
    );
  });

  it("says none when there are no games at all", () => {
    renderWithProviders(
      <MetricsRow
        summary={summary({
          games: 0,
          trophies: 0,
          trophies_per_hour: null,
          avg_rank: null,
          top4_rate: null,
          hours_farmed: 0,
        })}
      />,
    );
    expect(within(figure("trophies per hour")).getByTestId("metric-value")).toHaveTextContent(
      "none",
    );
    expect(within(figure("average rank")).getByTestId("metric-value")).toHaveTextContent("none");
    expect(within(figure("top-4 rate")).getByTestId("metric-value")).toHaveTextContent("none");
  });

  it("gives every number tabular figures", () => {
    renderWithProviders(<MetricsRow summary={summary()} />);
    for (const node of screen.getAllByTestId("metric-value")) {
      expect(node).toHaveClass("font-mono");
      expect(node).toHaveClass("tabular-nums");
    }
  });
});
