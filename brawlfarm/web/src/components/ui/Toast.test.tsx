/** One toast visible at a time, a life the caller can lengthen, an Undo that both runs
 * the callback and closes the toast, and a hairline that holds still for a reader who
 * asked for less motion. */
import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Toaster } from "./Toast";
import { ApiError } from "../../api/client";
import { TOAST_MS, resetToasts, toast } from "../../lib/toast";

/** jsdom ships no matchMedia at all, so each branch has to be stubbed in. */
function stubReducedMotion(reduce: boolean): void {
  vi.stubGlobal("matchMedia", (query: string) => ({ matches: reduce, media: query }));
}

function drainBar(container: HTMLElement): HTMLElement {
  const bar = container.querySelector<HTMLElement>("[data-drain]");
  if (bar === null) throw new Error("the toast has no drain bar");
  return bar;
}

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  resetToasts();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
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

  it("says why an undo failed rather than leaving the rejection unhandled", async () => {
    // Real timers: userEvent awaits testing-library's async wrapper, and the rejection has
    // to settle before the replacement toast can be looked for.
    vi.useRealTimers();
    const logged = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const undo = vi.fn(() => Promise.reject(new ApiError(503, "adb did not answer")));
    render(<Toaster />);
    act(() => {
      toast("Stopping Pie64 after this match", { undo });
    });
    await userEvent.click(screen.getByRole("button", { name: "Undo" }));
    expect(await screen.findByText("adb did not answer")).toBeInTheDocument();
    expect(logged).toHaveBeenCalledTimes(1);
  });

  it("falls back to its own wording when the undo failed for some other reason", async () => {
    vi.useRealTimers();
    const logged = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const undo = vi.fn(() => Promise.reject(new Error("boom")));
    render(<Toaster />);
    act(() => {
      toast("Stopping Pie64 after this match", { undo });
    });
    await userEvent.click(screen.getByRole("button", { name: "Undo" }));
    expect(await screen.findByText("Undo failed")).toBeInTheDocument();
    expect(logged).toHaveBeenCalledTimes(1);
  });

  it("reports an undo that threw exactly as it reports one that rejected", async () => {
    // An undo is usually async, but not always: a handler that reads the cache and
    // throws on the way to its request fails before a promise ever exists, and that has
    // to reach the reader rather than the browser's console.
    vi.useRealTimers();
    const logged = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const undo = vi.fn(() => {
      throw new ApiError(503, "adb did not answer");
    });
    render(<Toaster />);
    act(() => {
      toast("Stopping Pie64 after this match", { undo });
    });
    await userEvent.click(screen.getByRole("button", { name: "Undo" }));
    expect(await screen.findByText("adb did not answer")).toBeInTheDocument();
    expect(logged).toHaveBeenCalledTimes(1);
  });

  it("falls back to its own wording when an undo throws something else", async () => {
    vi.useRealTimers();
    const logged = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const undo = vi.fn(() => {
      throw new Error("boom");
    });
    render(<Toaster />);
    act(() => {
      toast("Stopping Pie64 after this match", { undo });
    });
    await userEvent.click(screen.getByRole("button", { name: "Undo" }));
    expect(await screen.findByText("Undo failed")).toBeInTheDocument();
    expect(logged).toHaveBeenCalledTimes(1);
  });

  it("hands the hairline a transition to sweep across the toast's life", async () => {
    stubReducedMotion(false);
    const { container } = render(<Toaster />);
    act(() => {
      toast("Plan saved");
    });
    const bar = drainBar(container);
    // The first paint is the full width with nothing to animate, so the browser has a
    // value to sweep from once the transition arrives.
    expect(bar.style.width).toBe("100%");
    expect(bar.style.transition).toBe("");
    // jsdom runs requestAnimationFrame off a timer, so the frames the drain waits for only
    // come round when the clock does.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(50);
    });
    expect(bar.style.width).toBe("0%");
    expect(bar.style.transition).toBe(`width ${String(TOAST_MS)}ms linear`);
  });

  it("holds the hairline still for a reader who asked for less motion", async () => {
    stubReducedMotion(true);
    const { container } = render(<Toaster />);
    act(() => {
      toast("Plan saved");
    });
    const bar = drainBar(container);
    expect(bar.style.width).toBe("100%");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(50);
    });
    expect(bar.style.width).toBe("100%");
    expect(bar.style.transition).toBe("");
  });

  it.each([
    ["info", "bg-accent"],
    ["ok", "bg-ok"],
    ["bad", "bg-bad"],
  ] as const)("colours the hairline for a %s toast", (tone, expected) => {
    const { container } = render(<Toaster />);
    act(() => {
      toast("Plan saved", { tone });
    });
    expect(drainBar(container)).toHaveClass(expected);
  });

  it.each([
    ["ok", "text-ok"],
    ["bad", "text-bad"],
  ] as const)("colours the %s icon to match the hairline", (tone, expected) => {
    const { container } = render(<Toaster />);
    act(() => {
      toast("Plan saved", { tone });
    });
    const icon = container.querySelector("svg");
    expect(icon).not.toBeNull();
    expect(icon).toHaveClass(expected);
  });

  it("calls a bad toast out rather than announcing it politely", () => {
    render(<Toaster />);
    act(() => {
      toast("That did not go through. Try again.", { tone: "bad" });
    });
    const strip = screen.getByRole("alert");
    expect(strip).toHaveTextContent("That did not go through. Try again.");
    expect(strip).not.toHaveAttribute("aria-live");
  });

  it("offers Retry on a bad toast, runs it once and closes", () => {
    const retry = vi.fn();
    render(<Toaster />);
    act(() => {
      toast("That did not go through. Try again.", { tone: "bad", retry });
    });
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(retry).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("That did not go through. Try again.")).not.toBeInTheDocument();
  });

  it("offers no action on a bad toast with nothing to retry", () => {
    render(<Toaster />);
    act(() => {
      toast("That did not go through. Try again.", { tone: "bad" });
    });
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("still offers Undo on an ok toast", () => {
    render(<Toaster />);
    act(() => {
      toast("Stopping Pie64 after this match", { tone: "ok", undo: vi.fn() });
    });
    expect(screen.getByRole("button", { name: "Undo" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument();
  });

  it("keeps Undo and drops Retry when a caller offers both", () => {
    const logged = vi.spyOn(console, "error").mockImplementation(() => undefined);
    render(<Toaster />);
    act(() => {
      toast("Stopping Pie64 after this match", { undo: vi.fn(), retry: vi.fn() });
    });
    expect(screen.getByRole("button", { name: "Undo" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument();
    expect(logged).toHaveBeenCalledTimes(1);
    expect(String(logged.mock.calls[0][0])).toContain("retry");
  });

  it("says why a retry failed in one toast that does not offer another retry", async () => {
    vi.useRealTimers();
    const logged = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const retry = vi.fn(() => Promise.reject(new ApiError(503, "adb did not answer")));
    const { container } = render(<Toaster />);
    act(() => {
      toast("That did not go through. Try again.", { tone: "bad", retry });
    });
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("adb did not answer")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument();
    // One follow-up, not one per rejection path: a second toast would be waiting behind
    // this one with its own drain bar.
    expect(container.querySelectorAll("[data-drain]")).toHaveLength(1);
    expect(logged).toHaveBeenCalledTimes(1);
  });

  it("reports a retry that threw exactly as it reports one that rejected", async () => {
    vi.useRealTimers();
    const logged = vi.spyOn(console, "error").mockImplementation(() => undefined);
    const retry = vi.fn(() => {
      throw new ApiError(503, "adb did not answer");
    });
    render(<Toaster />);
    act(() => {
      toast("That did not go through. Try again.", { tone: "bad", retry });
    });
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("adb did not answer")).toBeInTheDocument();
    expect(logged).toHaveBeenCalledTimes(1);
  });

  it("renders nothing at all when the queue is empty", () => {
    const { container } = render(<Toaster />);
    expect(container).toBeEmptyDOMElement();
  });
});
