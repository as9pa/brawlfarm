/** One toast visible at a time, a life the caller can lengthen, and an Undo that both
 * runs the callback and closes the toast. */
import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Toaster } from "./Toast";
import { resetToasts, toast } from "../../lib/toast";

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  resetToasts();
  vi.useRealTimers();
});

describe("Toaster", () => {
  it("shows one message at a time and moves on when the first expires", () => {
    render(<Toaster />);
    act(() => {
      toast("Started Pie64");
      toast("Restarting Pie64");
    });
    expect(screen.getByText("Started Pie64")).toBeInTheDocument();
    expect(screen.queryByText("Restarting Pie64")).not.toBeInTheDocument();
    act(() => {
      vi.advanceTimersByTime(4000);
    });
    expect(screen.queryByText("Started Pie64")).not.toBeInTheDocument();
    expect(screen.getByText("Restarting Pie64")).toBeInTheDocument();
  });

  it("keeps an undoable toast up for 6 s and runs the undo when clicked", () => {
    const undo = vi.fn();
    render(<Toaster />);
    act(() => {
      toast("Stopping Pie64 after this match", { undo });
    });
    act(() => {
      vi.advanceTimersByTime(4000);
    });
    expect(screen.getByText("Stopping Pie64 after this match")).toBeInTheDocument();
    // fireEvent rather than userEvent: userEvent awaits testing-library's async wrapper,
    // which drains the queue with a real setTimeout that fake timers never run.
    fireEvent.click(screen.getByRole("button", { name: "Undo" }));
    expect(undo).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("Stopping Pie64 after this match")).not.toBeInTheDocument();
  });

  it("announces politely and offers no Undo when there is nothing to undo", () => {
    render(<Toaster />);
    act(() => {
      toast("Plan saved");
    });
    expect(screen.getByText("Plan saved").closest("[aria-live]")).toHaveAttribute(
      "aria-live",
      "polite",
    );
    expect(screen.queryByRole("button", { name: "Undo" })).not.toBeInTheDocument();
  });

  it("renders nothing at all when the queue is empty", () => {
    const { container } = render(<Toaster />);
    expect(container).toBeEmptyDOMElement();
  });
});
