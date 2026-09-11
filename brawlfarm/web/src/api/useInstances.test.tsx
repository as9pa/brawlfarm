/** The instances query every screen shares: one key, one fetcher, and a 15 s poll that
 * stops while the tab is hidden. */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { INSTANCES_POLL_MS, useInstances } from "./useInstances";
import { makeInstance } from "../test/fixtures";
import { jsonResponse, stubFetch } from "../test/http";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

/** One client per test, so a cached list never leaks into the next case. */
function withClient() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

describe("useInstances", () => {
  it("reads the fleet through the shared instances key", async () => {
    const { calls } = stubFetch(() => jsonResponse({ instances: [makeInstance()] }));
    const { result } = renderHook(() => useInstances(), { wrapper: withClient() });
    await waitFor(() => {
      expect(result.current.data?.map((inst) => inst.name)).toEqual(["Pie64"]);
    });
    expect(calls[0].url).toBe("/api/instances");
  });

  it("asks again every 15 s while the tab is visible", async () => {
    vi.useFakeTimers();
    const { calls } = stubFetch(() => jsonResponse({ instances: [] }));
    renderHook(() => useInstances(), { wrapper: withClient() });
    await vi.waitFor(() => {
      expect(calls).toHaveLength(1);
    });
    expect(INSTANCES_POLL_MS).toBe(15000);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(INSTANCES_POLL_MS);
    });
    expect(calls).toHaveLength(2);
  });
});
