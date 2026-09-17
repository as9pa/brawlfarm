/** The alerts drawer's frame: a modal dialog that traps focus, closes on Escape and
 * closes when the scrim is clicked. */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Button } from "./Button";
import { Drawer } from "./Drawer";

describe("Drawer", () => {
  it("renders nothing while closed", () => {
    const { container } = render(
      <Drawer open={false} onClose={vi.fn()} title="Alerts">
        <p>rows</p>
      </Drawer>,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("is a modal dialog named by its title, with its actions in the header", () => {
    render(
      <Drawer open onClose={vi.fn()} title="Alerts" actions={<Button variant="quiet">Dismiss all</Button>}>
        <p>rows</p>
      </Drawer>,
    );
    const dialog = screen.getByRole("dialog", { name: "Alerts" });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(screen.getByRole("button", { name: "Dismiss all" })).toBeInTheDocument();
  });

  it("closes on Escape", async () => {
    const onClose = vi.fn();
    render(
      <Drawer open onClose={onClose} title="Alerts">
        <p>rows</p>
      </Drawer>,
    );
    await userEvent.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("keeps Tab inside the panel", async () => {
    render(
      <Drawer open onClose={vi.fn()} title="Alerts">
        <Button variant="quiet">Dismiss</Button>
      </Drawer>,
    );
    const close = screen.getByRole("button", { name: "Close" });
    const dismiss = screen.getByRole("button", { name: "Dismiss" });
    // The header, Close included, comes before the children in the DOM, so Tab reaches
    // Close first and wraps from Dismiss back to it.
    await userEvent.tab();
    expect(close).toHaveFocus();
    await userEvent.tab();
    expect(dismiss).toHaveFocus();
    await userEvent.tab();
    expect(close).toHaveFocus();
  });

  it("leaves focus alone when the caller re-renders with a fresh onClose", () => {
    const panel = (
      <Drawer open onClose={() => undefined} title="Alerts">
        <Button variant="quiet">Dismiss</Button>
      </Drawer>
    );
    const { rerender } = render(panel);
    screen.getByRole("button", { name: "Dismiss" }).focus();
    // A caller that builds onClose inline hands over a new function every render. That must
    // not re-run the focus effect, whose cleanup returns focus to whatever opened the panel.
    rerender(
      <Drawer open onClose={() => undefined} title="Alerts">
        <Button variant="quiet">Dismiss</Button>
      </Drawer>,
    );
    expect(screen.getByRole("button", { name: "Dismiss" })).toHaveFocus();
  });
});
