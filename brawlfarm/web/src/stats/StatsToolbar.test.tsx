/** The toolbar: four range radios with a radio group's keyboard, one chip per configured
 * instance that cannot all be turned off, and an export link carrying the current query. */
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { StatsToolbar } from "./StatsToolbar";
import { statsCsvHref } from "../api/stats";
import { buttonClass } from "../components/ui/Button";
import { renderWithProviders } from "../test/renderWithProviders";

function mount(overrides: Partial<Parameters<typeof StatsToolbar>[0]> = {}) {
  // The two mocks are written after the spread, so they keep their Mock type: a
  // Partial<Props> spread over them would widen both back to plain callbacks.
  const props = {
    range: "7d" as const,
    instances: ["Pie64", "Pie64_1"],
    selected: ["Pie64", "Pie64_1"],
    csvHref: statsCsvHref("7d", []),
    ...overrides,
    onRange: vi.fn(),
    onInstances: vi.fn(),
  };
  renderWithProviders(<StatsToolbar {...props} />);
  return props;
}

describe("StatsToolbar", () => {
  it("shows the four ranges as one radio group", () => {
    mount();
    const group = screen.getByRole("radiogroup", { name: "Range" });
    expect(
      Array.from(group.querySelectorAll('[role="radio"]')).map((n) => n.textContent),
    ).toEqual(["Today", "7 days", "30 days", "All"]);
    expect(screen.getByRole("radio", { name: "7 days" })).toHaveAttribute("aria-checked", "true");
  });

  it("moves between the ranges with Left and Right", async () => {
    const props = mount();
    await userEvent.click(screen.getByRole("radio", { name: "7 days" }));
    props.onRange.mockClear();
    await userEvent.keyboard("{ArrowRight}");
    expect(props.onRange).toHaveBeenCalledWith("30d");
    props.onRange.mockClear();
    await userEvent.keyboard("{ArrowLeft}");
    expect(props.onRange).toHaveBeenCalledWith("today");
  });

  it("jumps to the first and the last range with Home and End", async () => {
    const props = mount();
    await userEvent.click(screen.getByRole("radio", { name: "7 days" }));
    props.onRange.mockClear();
    await userEvent.keyboard("{End}");
    expect(props.onRange).toHaveBeenCalledWith("all");
    props.onRange.mockClear();
    await userEvent.keyboard("{Home}");
    expect(props.onRange).toHaveBeenCalledWith("today");
  });

  it("toggles one instance chip", async () => {
    const props = mount();
    await userEvent.click(screen.getByRole("button", { name: "Pie64_1" }));
    expect(props.onInstances).toHaveBeenCalledWith(["Pie64"]);
  });

  it("turns a chip back on", async () => {
    const props = mount({ selected: ["Pie64"] });
    expect(screen.getByRole("button", { name: "Pie64_1" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    await userEvent.click(screen.getByRole("button", { name: "Pie64_1" }));
    expect(props.onInstances).toHaveBeenCalledWith(["Pie64", "Pie64_1"]);
  });

  it("disables the last enabled chip and says why", async () => {
    const props = mount({ selected: ["Pie64"] });
    const chip = screen.getByRole("button", { name: "Pie64" });
    expect(chip).toHaveAttribute("aria-disabled", "true");
    expect(chip).toHaveAttribute("title", "Keep at least one");
    await userEvent.click(chip);
    expect(props.onInstances).not.toHaveBeenCalled();
  });

  it("renders one instance as a label, not a chip", () => {
    mount({ instances: ["Pie64"], selected: ["Pie64"] });
    const label = screen.getByTestId("instance-label");
    expect(label).toHaveTextContent("Pie64");
    // An instance name is a name, not a figure: t-name, never t-figure.
    expect(label).toHaveClass("t-name");
    expect(label).not.toHaveClass("t-figure");
    expect(screen.queryByRole("button", { name: "Pie64" })).toBeNull();
  });

  it("exports the current query as a download link", () => {
    mount({ range: "30d", csvHref: statsCsvHref("30d", ["Pie64"]) });
    const link = screen.getByRole("link", { name: "Export CSV" });
    expect(link).toHaveAttribute("href", "/api/stats/export.csv?range=30d&instances=Pie64");
    expect(link).toHaveAttribute("download");
    expect(link).toHaveClass("ml-auto", buttonClass("secondary", "sm"));
  });
});
