/** Refetch intervals stop while the tab is hidden: a backgrounded panel must not keep
 * screenshotting a BlueStacks window. */
import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { useVisiblePolling } from "./useVisiblePolling";

function setVisibility(state: "visible" | "hidden"): void {
  Object.defineProperty(document, "visibilityState", { value: state, configurable: true });
  document.dispatchEvent(new Event("visibilitychange"));
}

afterEach(() => {
  Object.defineProperty(document, "visibilityState", { value: "visible", configurable: true });
});

describe("useVisiblePolling", () => {
  it("returns the interval while visible and false while hidden", () => {
    const { result } = renderHook(() => useVisiblePolling(15000));
    expect(result.current).toBe(15000);
    act(() => setVisibility("hidden"));
    expect(result.current).toBe(false);
    act(() => setVisibility("visible"));
    expect(result.current).toBe(15000);
  });
});
