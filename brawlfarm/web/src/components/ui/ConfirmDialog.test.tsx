/** The typed-name gate: the confirm button will not fire until the word is typed exactly,
 * it says what to type while it is disabled, and the box forgets what was typed when the
 * dialog closes, so a second open never starts already armed. */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ConfirmDialog } from "./ConfirmDialog";

function remove(open: boolean, onConfirm: () => void, onClose: () => void) {
  return (
    <ConfirmDialog
      open={open}
      onClose={onClose}
      title="Remove Pie64_3?"
      body="Its data folder stays on disk. Type the name to confirm."
      word="Pie64_3"
      confirmLabel="Remove"
      tone="bad"
      onConfirm={onConfirm}
    />
  );
}

describe("ConfirmDialog", () => {
  it("stays disabled, and says what to type, until the word matches exactly", async () => {
    const onConfirm = vi.fn();
    render(remove(true, onConfirm, vi.fn()));
    const confirm = screen.getByRole("button", { name: "Remove" });
    const box = screen.getByLabelText("Type to confirm");
    expect(confirm).toBeDisabled();
    expect(confirm).toHaveAttribute("title", "Type Pie64_3 to confirm");
    expect(box).toHaveAttribute("placeholder", "Pie64_3");
    expect(
      screen.getByText(
        "Its data folder stays on disk. Type the name to confirm.",
      ),
    ).toBeInTheDocument();

    await userEvent.type(box, "pie64_3");
    // Case sensitive on purpose: on a case-sensitive disk those are two different folders,
    // and a confirmation that accepts either is not a confirmation.
    expect(confirm).toBeDisabled();
    await userEvent.clear(box);
    await userEvent.type(box, "  Pie64_3  ");
    expect(confirm).toBeEnabled(); // the trimmed value is what is compared
    await userEvent.click(confirm);
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("cancels without confirming", async () => {
    const onConfirm = vi.fn();
    const onClose = vi.fn();
    render(remove(true, onConfirm, onClose));
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("forgets the typed word when it closes", async () => {
    const onConfirm = vi.fn();
    const { rerender } = render(remove(true, onConfirm, vi.fn()));
    await userEvent.type(screen.getByLabelText("Type to confirm"), "Pie64_3");
    expect(screen.getByRole("button", { name: "Remove" })).toBeEnabled();

    rerender(remove(false, onConfirm, vi.fn()));
    rerender(remove(true, onConfirm, vi.fn()));
    expect(screen.getByLabelText("Type to confirm")).toHaveValue("");
    expect(screen.getByRole("button", { name: "Remove" })).toBeDisabled();
  });

  it("confirms on the button alone when there is no word to type", async () => {
    const onConfirm = vi.fn();
    render(
      <ConfirmDialog
        open
        onClose={vi.fn()}
        title="Dismiss all alerts?"
        body="They leave the drawer and the bell count. Nothing is un-dismissed."
        confirmLabel="Dismiss all"
        tone="bad"
        onConfirm={onConfirm}
      />,
    );
    const confirm = screen.getByRole("button", { name: "Dismiss all" });
    expect(confirm).toBeEnabled();
    expect(screen.queryByLabelText("Type to confirm")).not.toBeInTheDocument();
    await userEvent.click(confirm);
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });
});
