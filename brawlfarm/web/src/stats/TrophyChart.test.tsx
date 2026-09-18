/** The chart: one path per series that has points, a legend that matches the chips, a
 * crosshair the keyboard can reach, a live region saying the same thing, a Table view of
 * the same numbers, and no motion anywhere. */
import { fireEvent, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { niceTicks, type StatsView, TrophyChart } from "./TrophyChart";
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

/** One instance, one game a day, `count` days running from Sep 1. */
function daily(count: number): StatsSeries[] {
  return [
    {
      instance: "Pie64",
      points: Array.from({ length: count }, (_, i) => ({
        t: `2026-09-${String(i + 1).padStart(2, "0")}T21:00:00`,
        cum: i + 1,
      })),
    },
  ];
}

/** The view is the page's to own, so every case says which one it is looking at and
 * reads onView to see what the chart asked for. */
let onView = vi.fn();

beforeEach(() => {
  onView = vi.fn();
});

function mount(
  series = SERIES,
  instances = INSTANCES,
  range: StatsRange = "today",
  view: StatsView = "chart",
) {
  return renderWithProviders(
    <TrophyChart
      series={series}
      instances={instances}
      range={range}
      view={view}
      onView={onView}
    />,
  );
}

function plot(): HTMLElement {
  return screen.getByRole("img", { name: "Cumulative trophy change" });
}

/** Five moments inside two hours, three of them bunched together: the middle stamps land
 * on top of each other unless the axis drops the ones that do not fit. */
const CLUSTER: StatsSeries[] = [
  {
    instance: "Pie64",
    points: [
      { t: "2026-09-11T15:00:00", cum: 4 },
      { t: "2026-09-11T15:57:00", cum: 9 },
      { t: "2026-09-11T16:16:00", cum: 14 },
      { t: "2026-09-11T16:45:00", cum: 11 },
      { t: "2026-09-11T16:50:00", cum: 18 },
    ],
  },
];

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

  it("calls onView with the other view when the segmented control is used", async () => {
    mount();
    expect(plot()).toBeInTheDocument();
    await userEvent.click(screen.getByRole("radio", { name: "Table" }));
    expect(onView).toHaveBeenCalledWith("table");
    // Controlled: the chart asks and the page answers, so nothing swapped on its own.
    expect(plot()).toBeInTheDocument();
  });

  it("has no transition and no animation on anything it draws", () => {
    const { container } = mount();
    // The View control is the kit's Segmented and keeps the kit's 120 ms colour fade.
    // Everything the chart draws itself still stands perfectly still.
    for (const node of container.querySelectorAll<HTMLElement>("*")) {
      if (node.closest('[role="radiogroup"]') !== null) continue;
      expect(node.getAttribute("class") ?? "").not.toMatch(/transition|animate|duration-/);
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

  it("never draws two ticks closer than the label height", () => {
    // Every game lost trophies, so the domain runs from the worst total up to the zero
    // rule itself, and the round ticks in between still have to be readable apart.
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
    const tops = Array.from(axis.querySelectorAll<HTMLElement>("[data-tick]")).map(
      (node) => (Number.parseFloat(node.style.top) / 100) * 180,
    );
    expect(tops).toHaveLength(niceTicks(-5, 0).length);
    for (let i = 1; i < tops.length; i += 1) {
      expect(tops[i] - tops[i - 1]).toBeGreaterThanOrEqual(12);
    }
  });

  it("picks round ticks that always include zero", () => {
    expect(niceTicks(-3, 78)).toEqual([75, 50, 25, 0]);
    for (const [lo, hi] of [
      [-3, 78],
      [0, 25],
      [-40, 0],
      [-5, 0],
    ] as const) {
      expect(niceTicks(lo, hi)).toContain(0);
    }
  });

  it("names what it plots in the panel heading, per range", () => {
    const wide = mount(SERIES, INSTANCES, "7d");
    expect(
      screen.getByRole("heading", { name: "Trophies, cumulative, last 7 days" }),
    ).toBeInTheDocument();
    wide.unmount();
    mount();
    expect(
      screen.getByRole("heading", { name: "Trophies, cumulative, today" }),
    ).toBeInTheDocument();
  });

  it("says the unit once, under the lowest y tick", () => {
    mount();
    expect(screen.getAllByText("trophies")).toHaveLength(1);
    const axis = screen.getByTestId("chart-axis");
    expect(within(axis).getByText("trophies")).toBeInTheDocument();
  });

  it("dates the x axis and never prints one label twice", () => {
    mount(SERIES, INSTANCES, "7d");
    const labels = Array.from(screen.getByTestId("chart-x-axis").children).map(
      (node) => node.textContent,
    );
    expect(labels.length).toBeGreaterThanOrEqual(2);
    expect(labels[0]).toContain("Sep");
    expect(new Set(labels).size).toBe(labels.length);
  });

  it("drops an x label rather than printing it over its neighbour", () => {
    mount(CLUSTER, ["Pie64"], "7d");
    // Read back where each label sits, in the coordinate space the paths are drawn in.
    const at = Array.from(
      screen.getByTestId("chart-x-axis").querySelectorAll<HTMLElement>("span"),
    ).map((node) => (Number.parseFloat(node.style.left) / 100) * 640);
    expect(at.length).toBeGreaterThanOrEqual(2);
    expect(at[0]).toBe(0);
    expect(at[at.length - 1]).toBe(640);
    for (let i = 1; i < at.length; i += 1) {
      expect(at[i] - at[i - 1]).toBeGreaterThanOrEqual(120);
    }
  });

  it("draws one gridline per y tick", () => {
    const { container } = mount();
    expect(container.querySelectorAll("[data-gridline]")).toHaveLength(
      niceTicks(-3, 25).length,
    );
  });

  it("leaves the end label off a chart of one series", () => {
    const one = mount([SERIES[0]], ["Pie64"]);
    expect(one.container.querySelectorAll("[data-end-label]")).toHaveLength(0);
    one.unmount();
    const two = mount(SERIES.slice(0, 2), ["Pie64", "Pie64_1"]);
    expect(two.container.querySelectorAll("[data-end-label]")).toHaveLength(2);
  });

  it("renders the table when view is table", () => {
    mount(SERIES, INSTANCES, "today", "table");
    expect(screen.queryByRole("img", { name: "Cumulative trophy change" })).toBeNull();
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Table" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
  });

  it("is one row a day, and names no instance in its headers", () => {
    mount(SERIES, INSTANCES, "7d", "table");
    const table = screen.getByRole("table");
    const headers = within(table)
      .getAllByRole("columnheader")
      .map((n) => n.textContent);
    expect(headers).toEqual(["Date", "Games", "Net trophies", "Cumulative"]);
    for (const name of INSTANCES) expect(headers).not.toContain(name);
    // Three moments over one day, so one row, and the day reads as the short date.
    expect(within(table).getAllByRole("row")).toHaveLength(2);
    expect(within(table).getAllByRole("row")[1]).toHaveTextContent("Sep 12");
  });

  it("caps the table at fourteen days and expands in place", async () => {
    mount(daily(30), ["Pie64"], "30d", "table");
    expect(within(screen.getByRole("table")).getAllByRole("row")).toHaveLength(15);
    await userEvent.click(screen.getByRole("button", { name: "Show all 30 days" }));
    expect(within(screen.getByRole("table")).getAllByRole("row")).toHaveLength(31);
    await userEvent.click(screen.getByRole("button", { name: "Show 14 days" }));
    expect(within(screen.getByRole("table")).getAllByRole("row")).toHaveLength(15);
  });

  it("leads with the newest day and caps to the newest fourteen", () => {
    mount(daily(20), ["Pie64"], "30d", "table");
    const rows = within(screen.getByRole("table")).getAllByRole("row");
    expect(rows).toHaveLength(15);
    expect(rows[1]).toHaveTextContent("Sep 20");
    expect(rows[14]).toHaveTextContent("Sep 7");
  });

  it("shows no expander when the range fits under the cap", () => {
    mount(daily(13), ["Pie64"], "30d", "table");
    expect(within(screen.getByRole("table")).getAllByRole("row")).toHaveLength(14);
    expect(screen.queryByRole("button", { name: /Show/ })).toBeNull();
  });

  it("carries the day on a range wider than today and drops it on today", async () => {
    const wide = mount(SERIES, INSTANCES, "7d");
    plot().focus();
    await userEvent.keyboard("{Home}");
    expect(screen.getByTestId("chart-readout")).toHaveTextContent("Sep 12, 21:00");
    wide.unmount();
    mount();
    plot().focus();
    await userEvent.keyboard("{Home}");
    expect(screen.getByTestId("chart-readout")).toHaveTextContent("21:00");
    expect(screen.getByTestId("chart-readout")).not.toHaveTextContent("Sep");
  });
});
