/** The filter chips are a radio group, so a screen reader keeps the "one of these is
 * selected" relationship and gets the keyboard that goes with it: the group is a single
 * tab stop, the arrows move the selection along it, wrapping at both ends, and Home and
 * End land on the two ends. */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { Segmented } from "./Segmented";

const OPTIONS = [
  { value: "all", label: "All" },
  { value: "matches", label: "Matches" },
  { value: "errors", label: "Errors" },
];

/** Segmented is controlled, so the arrow keys only visibly move when a parent feeds the
 * new value back in. */
function Controlled({ start }: { start: string }) {
  const [value, setValue] = useState(start);
  return <Segmented value={value} options={OPTIONS} onChange={setValue} label="Feed filter" />;
}

function checked(): string | null {
  const on = screen.getAllByRole("radio").find((r) => r.getAttribute("aria-checked") === "true");
  return on?.textContent ?? null;
}

describe("Segmented", () => {
  it("marks the pressed option and reports the one that was clicked", async () => {
    const onChange = vi.fn();
    render(<Segmented value="all" options={OPTIONS} onChange={onChange} label="Feed filter" />);
    expect(screen.getByRole("radiogroup", { name: "Feed filter" })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "All" })).toHaveAttribute("aria-checked", "true");
    expect(screen.getByRole("radio", { name: "Errors" })).toHaveAttribute("aria-checked", "false");
    await userEvent.click(screen.getByRole("radio", { name: "Errors" }));
    expect(onChange).toHaveBeenCalledWith("errors");
  });

  it("is one tab stop: only the selected option is tabbable", () => {
    render(<Segmented value="matches" options={OPTIONS} onChange={vi.fn()} label="Feed filter" />);
    expect(screen.getByRole("radio", { name: "All" })).toHaveAttribute("tabindex", "-1");
    expect(screen.getByRole("radio", { name: "Matches" })).toHaveAttribute("tabindex", "0");
    expect(screen.getByRole("radio", { name: "Errors" })).toHaveAttribute("tabindex", "-1");
  });

  it("leaves the first option tabbable when the value matches nothing", () => {
    render(<Segmented value="gone" options={OPTIONS} onChange={vi.fn()} label="Feed filter" />);
    expect(screen.getByRole("radio", { name: "All" })).toHaveAttribute("tabindex", "0");
  });

  it("moves and selects with the arrows, wrapping at both ends", async () => {
    render(<Controlled start="all" />);
    screen.getByRole("radio", { name: "All" }).focus();

    await userEvent.keyboard("{ArrowRight}");
    expect(checked()).toBe("Matches");
    expect(screen.getByRole("radio", { name: "Matches" })).toHaveFocus();

    await userEvent.keyboard("{ArrowRight}{ArrowRight}");
    expect(checked()).toBe("All");

    await userEvent.keyboard("{ArrowLeft}");
    expect(checked()).toBe("Errors");
    expect(screen.getByRole("radio", { name: "Errors" })).toHaveFocus();

    await userEvent.keyboard("{ArrowDown}");
    expect(checked()).toBe("All");
    await userEvent.keyboard("{ArrowUp}");
    expect(checked()).toBe("Errors");
  });

  it("goes to the two ends with Home and End", async () => {
    render(<Controlled start="matches" />);
    screen.getByRole("radio", { name: "Matches" }).focus();
    await userEvent.keyboard("{End}");
    expect(checked()).toBe("Errors");
    await userEvent.keyboard("{Home}");
    expect(checked()).toBe("All");
  });

  it("leaves other keys to the browser", async () => {
    const onChange = vi.fn();
    render(<Segmented value="all" options={OPTIONS} onChange={onChange} label="Feed filter" />);
    screen.getByRole("radio", { name: "All" }).focus();
    await userEvent.keyboard("{PageDown}");
    expect(onChange).not.toHaveBeenCalled();
  });
});
