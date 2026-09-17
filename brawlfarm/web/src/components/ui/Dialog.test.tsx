/** The centred modal: named by its own heading, focus trapped inside it, Escape and the
 * backdrop close it, and a click on the panel does not. */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Button } from "./Button";
import { Dialog } from "./Dialog";

function backdrop(): HTMLElement {
  return screen.getByRole("dialog").previousElementSibling as HTMLElement;
}

describe("Dialog", () => {
  it("renders nothing while closed", () => {
    const { container } = render(
      <Dialog open={false} onClose={vi.fn()} title="Remove Pie64_3?">
        <p>body</p>
      </Dialog>,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("is a modal dialog labelled by the heading it shows", () => {
    render(
      <Dialog open onClose={vi.fn()} title="Remove Pie64_3?" actions={<Button>Remove</Button>}>
        <p>Its data folder stays on disk. Type the name to confirm.</p>
      </Dialog>,
    );
    const dialog = screen.getByRole("dialog", { name: "Remove Pie64_3?" });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    // aria-labelledby rather than aria-label: the title is already on screen, so there is
    // one string to keep right instead of two that can drift apart.
    expect(dialog.getAttribute("aria-labelledby")).toBe(
      screen.getByRole("heading", { name: "Remove Pie64_3?" }).id,
    );
    expect(screen.getByRole("button", { name: "Remove" })).toBeInTheDocument();
  });

  it("closes on Escape", async () => {
    const onClose = vi.fn();
    render(
      <Dialog open onClose={onClose} title="Remove Pie64_3?">
        <p>body</p>
      </Dialog>,
    );
    await userEvent.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("closes on the backdrop and stays open for a click inside", async () => {
    const onClose = vi.fn();
    render(
      <Dialog open onClose={onClose} title="Remove Pie64_3?" actions={<Button>Remove</Button>}>
        <p>body</p>
      </Dialog>,
    );
    await userEvent.click(screen.getByText("body"));
    expect(onClose).not.toHaveBeenCalled();
    await userEvent.click(backdrop());
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("keeps Tab inside the panel", async () => {
    render(
      <Dialog
        open
        onClose={vi.fn()}
        title="Remove Pie64_3?"
        actions={
          <>
            <Button variant="quiet">Cancel</Button>
            <Button variant="primary">Remove</Button>
          </>
        }
      >
        <p>body</p>
      </Dialog>,
    );
    const cancel = screen.getByRole("button", { name: "Cancel" });
    const remove = screen.getByRole("button", { name: "Remove" });
    await userEvent.tab();
    expect(cancel).toHaveFocus();
    await userEvent.tab();
    expect(remove).toHaveFocus();
    await userEvent.tab();
    expect(cancel).toHaveFocus();
  });
});
