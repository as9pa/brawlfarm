/** The one button: four looks, a disabled reason that reaches the user as a tooltip. */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Button } from "./Button";
import type { ButtonProps } from "./Button";

/** Each variant with the one class that tells it apart from the other three. */
const LOOKS: [NonNullable<ButtonProps["variant"]>, string][] = [
  ["primary", "bg-accent"],
  ["secondary", "border-line"],
  ["quiet", "text-accent"],
  ["danger", "bg-bad"],
];

describe("Button", () => {
  it("calls onClick and defaults to type button so it never submits a form", async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Stop</Button>);
    const button = screen.getByRole("button", { name: "Stop" });
    expect(button).toHaveAttribute("type", "button");
    await userEvent.click(button);
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it.each(LOOKS)("renders the %s variant with %s", (variant, className) => {
    render(<Button variant={variant}>Save</Button>);
    expect(screen.getByRole("button", { name: "Save" })).toHaveClass(className);
  });

  it("falls back to secondary so an unstyled call is an outline, not an accent", () => {
    render(<Button>Save</Button>);
    expect(screen.getByRole("button", { name: "Save" })).toHaveClass("border-line");
  });

  it("explains why it is disabled and does not fire", async () => {
    const onClick = vi.fn();
    render(
      <Button disabled disabledReason="Not running" onClick={onClick}>
        Stop
      </Button>,
    );
    const button = screen.getByRole("button", { name: "Stop" });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute("title", "Not running");
    await userEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
  });

  it("takes an accessible name over its visible text", () => {
    render(<Button aria-label="Alerts, 6 unread">Alerts</Button>);
    expect(screen.getByRole("button", { name: "Alerts, 6 unread" })).toBeInTheDocument();
  });

  it("says what a disclosure button opens and whether it is open", () => {
    render(
      <Button aria-expanded aria-controls="plan-roster">
        Hide all brawlers
      </Button>,
    );
    const button = screen.getByRole("button", { name: "Hide all brawlers" });
    expect(button).toHaveAttribute("aria-expanded", "true");
    expect(button).toHaveAttribute("aria-controls", "plan-roster");
  });
});
