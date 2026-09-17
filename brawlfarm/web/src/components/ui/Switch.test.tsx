/** A real switch: screen readers get role and state, the keyboard gets it for free. */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Switch } from "./Switch";

describe("Switch", () => {
  it("reports its state and toggles the other way round", async () => {
    const onChange = vi.fn();
    render(<Switch checked={false} onChange={onChange} label="Follow" />);
    const control = screen.getByRole("switch", { name: "Follow" });
    expect(control).toHaveAttribute("aria-checked", "false");
    await userEvent.click(control);
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it("does not toggle while disabled", async () => {
    const onChange = vi.fn();
    render(<Switch checked onChange={onChange} label="Schedule on" disabled />);
    await userEvent.click(screen.getByRole("switch", { name: "Schedule on" }));
    expect(onChange).not.toHaveBeenCalled();
  });

  it("carries the shared focus ring", () => {
    render(<Switch checked={false} onChange={vi.fn()} label="Follow" />);
    expect(screen.getByRole("switch", { name: "Follow" }).className).toContain(
      "focus-visible:outline-accent",
    );
  });
});
