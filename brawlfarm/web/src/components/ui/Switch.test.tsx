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

  /** The classes of the track and the thumb for one combination of the two booleans. */
  function look(checked: boolean, disabled: boolean) {
    const { container } = render(
      <Switch checked={checked} onChange={vi.fn()} label="Follow" disabled={disabled} />,
    );
    const control = container.querySelector("button") as HTMLButtonElement;
    const track = control.querySelector("span") as HTMLSpanElement;
    const thumb = track.querySelector("span") as HTMLSpanElement;
    return { control: control.className, track: track.className, thumb: thumb.className };
  }

  it("paints the enabled switch with the accent and offers the hover border", () => {
    const on = look(true, false);
    const off = look(false, false);
    expect(on.track).toContain("bg-accent");
    expect(on.thumb).toContain("bg-accent-ink");
    expect(on.thumb).toContain("left-3.5");
    expect(off.track).toContain("bg-panel-2");
    expect(off.thumb).toContain("left-0.5");
    expect(on.track).toContain("hover:border-muted");
    expect(off.track).toContain("hover:border-muted");
  });

  it("greys the disabled switch out in both positions instead of dimming it", () => {
    const on = look(true, true);
    const off = look(false, true);
    expect(on.track).toContain("bg-idle");
    expect(off.track).toContain("bg-idle");
    expect(on.thumb).toContain("bg-muted");
    expect(off.thumb).toContain("bg-muted");
    expect(on.track).not.toContain("hover:border-muted");
    expect(on.control).not.toContain("opacity-50");
    expect(on.control).toContain("disabled:cursor-not-allowed");
    expect(on.control).toContain("text-muted");
  });

  it("still reads as on while disabled: grey, but the thumb stays to the right", () => {
    expect(look(true, true).thumb).toContain("left-3.5");
    expect(look(false, true).thumb).toContain("left-0.5");
  });

  it("tells all four states apart", () => {
    expect(look(true, true).track).not.toBe(look(true, false).track);
    expect(look(false, true).track).not.toBe(look(false, false).track);
    expect(look(true, true).thumb).not.toBe(look(false, true).thumb);
  });
});
