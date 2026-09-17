/** The chart: one path per series that has points, a legend that matches the chips, a
 * crosshair the keyboard can reach, a live region saying the same thing, a Table view of
 * the same numbers, and no motion anywhere. */
import { fireEvent, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { TrophyChart } from "./TrophyChart";
import type { StatsRange, StatsSeries } from "../api/types";
import { renderWithProviders } from "../test/renderWithProviders";

const SERIES: StatsSeries[] = [
  {
    instance: "Pie64",
    points: [
      { t: "2026-09-12T21:00:00", cum: 12 },
      { t: "2026-09-12T21:30:00", cum: 8 },
      { t: "2026-09-12T22:00:00", cum: 25 },
    ],
  },
  {
    instance: "Pie64_1",
    points: [
      { t: "2026-09-12T21:30:00", cum: -3 },
      { t: "2026-09-12T22:00:00", cum: 12 },
    ],
  },
  { instance: "Pie64_3", points: [] },
];

const INSTANCES = ["Pie64", "Pie64_1", "Pie64_3"];

function mount(series = SERIES, instances = INSTANCES, range: StatsRange = "today") {
  return renderWithProviders(
    <TrophyChart series={series} instances={instances} range={range} />,
  );
}

function plot(): HTMLElement {
  return screen.getByRole("img", { name: "Cumulative trophy change" });
}

describe("TrophyChart", () => {
  it("draws one path per series that has points", () => {
    const { container } = mount();
    expect(container.querySelectorAll("[data-series-path]")).toHaveLength(2);
  });

  it("gives every selected instance a legend entry, points or not", () => {
    mount();
    const legend = screen.getByTestId("chart-legend");
    expect(within(legend).getAllByTestId("legend-entry").map((n) => n.textContent)).toEqual([
      "Pie64",
      "Pie64_1",
      "Pie64_3",
    ]);
  });

  it("puts an end label on every series that has points", () => {
    const { container } = mount();
    expect(
      Array.from(container.querySelectorAll("[data-end-label]")).map((n) => n.textContent),
    ).toEqual(["Pie64", "Pie64_1"]);
  });

  it("is one tab stop, labelled, and keeps its stroke when the viewBox stretches", () => {
    const { container } = mount();
    expect(plot()).toHaveAttribute("tabindex", "0");
    expect(plot()).toHaveAttribute("viewBox", "0 0 640 180");
    expect(plot()).toHaveAttribute("preserveAspectRatio", "none");
    for (const path of container.querySelectorAll("[data-series-path]")) {
      expect(path).toHaveAttribute("vector-effect", "non-scaling-stroke");
    }
  });

  it("moves the crosshair with Left and Right and clears it with Escape", async () => {
    mount();
    plot().focus();
    expect(screen.queryByTestId("chart-readout")).toBeNull();
    await userEvent.keyboard("{ArrowRight}");
    expect(screen.getByTestId("chart-readout")).toHaveTextContent("21:00");
    await userEvent.keyboard("{ArrowRight}");
    expect(screen.getByTestId("chart-readout")).toHaveTextContent("21:30");
    await userEvent.keyboard("{ArrowLeft}");
    expect(screen.getByTestId("chart-readout")).toHaveTextContent("21:00");
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByTestId("chart-readout")).toBeNull();
  });

  it("jumps to the ends with Home and End", async () => {
    mount();
    plot().focus();
    await userEvent.keyboard("{End}");
    expect(screen.getByTestId("chart-readout")).toHaveTextContent("22:00");
    await userEvent.keyboard("{Home}");
    expect(screen.getByTestId("chart-readout")).toHaveTextContent("21:00");
  });

  it("draws the crosshair rule only while there is a crosshair", async () => {
    const { container } = mount();
    expect(container.querySelector("[data-crosshair]")).toBeNull();
    plot().focus();
    await userEvent.keyboard("{End}");
    expect(container.querySelector("[data-crosshair]")).not.toBeNull();
  });

  it("announces the same readout in a polite live region", async () => {
    mount();
    plot().focus();
    await userEvent.keyboard("{End}");
    const live = screen.getByTestId("chart-live");
    expect(live).toHaveAttribute("aria-live", "polite");
    expect(live).toHaveTextContent("22:00, Pie64: 25, Pie64_1: 12, Pie64_3: Not recorded");
  });

  it("reads Not recorded for a series with no point yet at that moment", async () => {
    mount();
    plot().focus();
    await userEvent.keyboard("{Home}");
    expect(screen.getByTestId("chart-readout")).toHaveTextContent("Pie64_1");
    expect(screen.getByTestId("chart-readout")).toHaveTextContent("Not recorded");
  });

  it("swaps to a table of the same points and back, with the toggle reading Table both ways", async () => {
    mount();
    const toggle = screen.getByRole("button", { name: "Table" });
    expect(plot()).toBeInTheDocument();
    await userEvent.click(toggle);
    expect(screen.queryByRole("img", { name: "Cumulative trophy change" })).toBeNull();
    const table = screen.getByRole("table");
    expect(within(table).getAllByRole("columnheader").map((n) => n.textContent)).toEqual([
      "Time",
      "Pie64",
      "Pie64_1",
      "Pie64_3",
    ]);
    expect(within(table).getAllByRole("row")).toHaveLength(4); // header plus three moments
    expect(screen.getByRole("button", { name: "Table" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Table" }));
    expect(plot()).toBeInTheDocument();
  });

  it("has no transition and no animation on any element", () => {
    const { container } = mount();
    expect(container.querySelectorAll('[class*="transition"]')).toHaveLength(0);
    expect(container.querySelectorAll('[class*="animate"]')).toHaveLength(0);
    expect(container.querySelectorAll('[class*="duration-"]')).toHaveLength(0);
    for (const node of container.querySelectorAll<HTMLElement>("*")) {
      expect(node.style.transition).toBe("");
      expect(node.style.animation).toBe("");
    }
  });

  it("moves the crosshair on a pointer move and drops it on leave", () => {
    mount();
    const svg = plot();
    Object.defineProperty(svg, "clientWidth", { value: 640, configurable: true });
    fireEvent.mouseMove(svg, { clientX: 0 });
    expect(screen.getByTestId("chart-readout")).toBeInTheDocument();
    fireEvent.mouseLeave(svg);
    expect(screen.queryByTestId("chart-readout")).toBeNull();
  });

  it("draws nothing but the legend when no series has a point", () => {
    const { container } = mount([{ instance: "Pie64", points: [] }], ["Pie64"]);
    expect(container.querySelectorAll("[data-series-path]")).toHaveLength(0);
    expect(screen.getAllByTestId("legend-entry")).toHaveLength(1);
    expect(screen.getByTestId("chart-empty")).toHaveTextContent("No games in this range.");
  });

  it("drops a y-axis label that would overprint the zero one", () => {
    // Every game lost trophies, so the top of the domain is the zero rule itself and the
    // label for the maximum would sit exactly on the zero label.
    mount(
      [
        {
          instance: "Pie64",
          points: [
            { t: "2026-09-12T21:00:00", cum: -3 },
            { t: "2026-09-12T22:00:00", cum: -5 },
          ],
        },
      ],
      ["Pie64"],
    );
    const axis = screen.getByTestId("chart-axis");
    expect(Array.from(axis.children).map((node) => node.textContent)).toEqual(["0", "-5"]);
  });

  it("says whether the table view is the one showing", async () => {
    const user = userEvent.setup();
    mount();
    const toggle = screen.getByRole("button", { name: "Table" });
    expect(toggle).toHaveAttribute("aria-pressed", "false");
    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-pressed", "true");
    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-pressed", "false");
  });

  it("carries the day on a range wider than today and drops it on today", async () => {
    const user = userEvent.setup();
    const { unmount } = mount(SERIES, INSTANCES, "7d");
    await user.click(screen.getByRole("button", { name: "Table" }));
    expect(screen.getAllByRole("row")[1]).toHaveTextContent("Sep 12, 21:00");
    unmount();
    mount();
    await user.click(screen.getByRole("button", { name: "Table" }));
    expect(screen.getAllByRole("row")[1]).toHaveTextContent("21:00");
    expect(screen.getAllByRole("row")[1]).not.toHaveTextContent("Sep");
  });
});
