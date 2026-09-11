/** The toast queue: one at a time, a longer life when an Undo is offered, and a store
 * that a component can subscribe to. */
import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  TOAST_MS,
  TOAST_UNDO_MS,
  dismissToast,
  resetToasts,
  subscribeToasts,
  toast,
  useToasts,
} from "./toast";

afterEach(() => {
  resetToasts();
  vi.restoreAllMocks();
});

describe("toast", () => {
  it("queues messages in order and reports them to a subscriber", () => {
    const { result } = renderHook(() => useToasts());
    act(() => {
      toast("Started Pie64");
      toast("Restarting Pie64");
    });
    expect(result.current.map((item) => item.message)).toEqual([
      "Started Pie64",
      "Restarting Pie64",
    ]);
  });

  it("lives 4 s normally and 6 s when it offers an undo", () => {
    const { result } = renderHook(() => useToasts());
    act(() => {
      toast("Plan saved");
      toast("Stopping Pie64 after this match", { undo: vi.fn() });
      toast("Redrawing today; new sessions appear after the next tick", { durationMs: 9000 });
    });
    expect(result.current.map((item) => item.durationMs)).toEqual([TOAST_MS, TOAST_UNDO_MS, 9000]);
  });

  it("notifies the subscribers after one that throws", () => {
    const reported = vi.spyOn(console, "error").mockImplementation(() => {});
    const seen: string[] = [];
    const offFirst = subscribeToasts(() => {
      throw new Error("a subscriber that throws");
    });
    const offSecond = subscribeToasts(() => seen.push("second"));
    try {
      toast("Started Pie64");
    } finally {
      // Without this the throwing listener would outlive a regression and fail the
      // next case too, hiding which one actually broke.
      offFirst();
      offSecond();
    }
    expect(seen).toEqual(["second"]);
    expect(reported).toHaveBeenCalledTimes(1);
  });

  it("dismisses by id and ignores an id it has already dropped", () => {
    const { result } = renderHook(() => useToasts());
    let id = 0;
    act(() => {
      id = toast("Alerts dismissed");
    });
    expect(result.current).toHaveLength(1);
    act(() => {
      dismissToast(id);
      dismissToast(id);
    });
    expect(result.current).toEqual([]);
  });
});
