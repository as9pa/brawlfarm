/** The one button: three looks, a disabled reason that reaches the user as a tooltip. */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Button } from "./Button";

describe("Button", () => {
  it("calls onClick and defaults to type button so it never submits a form", async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Stop</Button>);
    const button = screen.getByRole("button", { name: "Stop" });
    expect(button).toHaveAttribute("type", "button");
    await userEvent.click(button);
    expect(onClick).toHaveBeenCalledTimes(1);
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
});
