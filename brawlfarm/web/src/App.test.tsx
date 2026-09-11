/** The whole tree: the four routes, the theme bootstrap, and the live handlers that turn
 * server-sent events into cache updates. */
import { act, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { closeAlertsDrawer } from "./lib/alertsDrawer";
import { closeEvents, setEventSourceFactory } from "./live/useEvents";
import { resetToasts } from "./lib/toast";
import { jsonResponse, pngResponse, stubFetch } from "./test/http";
import { makeAlert, makeInstance } from "./test/fixtures";

class FakeEventSource {
  static last: FakeEventSource | null = null;

  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  private readonly listeners = new Map<string, Set<(event: Event) => void>>();

  constructor(readonly url: string) {
    FakeEventSource.last = this;
  }

  addEventListener(kind: string, listener: (event: Event) => void): void {
    const set = this.listeners.get(kind) ?? new Set<(event: Event) => void>();
    set.add(listener);
    this.listeners.set(kind, set);
  }

  removeEventListener(kind: string, listener: (event: Event) => void): void {
    this.listeners.get(kind)?.delete(listener);
  }

  close(): void {}

  connect(): void {
    this.onopen?.();
  }

  emit(kind: string, data: unknown, id: number): void {
    const event = new MessageEvent(kind, { data: JSON.stringify(data), lastEventId: String(id) });
    for (const listener of [...(this.listeners.get(kind) ?? [])]) listener(event);
  }
}

function stubApi(theme: "system" | "dark" | "light" = "system"): { calls: { url: string }[] } {
  return stubFetch((url) => {
    if (url === "/api/settings") {
      return jsonResponse({
        app: { port: 8765, theme },
        connection: { adb_path: "adb.exe", brawl_api_token: "never-render-me" },
      });
    }
    if (url === "/api/instances") return jsonResponse({ instances: [makeInstance()] });
    if (url === "/api/alerts") return jsonResponse({ alerts: [makeAlert()], unread: 1 });
    if (url.endsWith("screenshot.png")) return pngResponse();
    throw new Error(`unstubbed request: ${url}`);
  });
}

beforeEach(() => {
  FakeEventSource.last = null;
  setEventSourceFactory((url) => new FakeEventSource(url) as unknown as EventSource);
  window.history.pushState({}, "", "/");
});

afterEach(() => {
  closeEvents();
  setEventSourceFactory(null);
  closeAlertsDrawer();
  resetToasts();
  resetTheme();
  vi.unstubAllGlobals();
});

function resetTheme(): void {
  delete document.documentElement.dataset.theme;
}

describe("App", () => {
  it("mounts the shell and the Fleet route", async () => {
    stubApi();
    render(<App />);
    expect(screen.getByText("brawlfarm")).toBeInTheDocument();
    // The rail and the Fleet card both link to the same instance, so each is asked for
    // where it lives: the rail entry inside the navigation landmark, the card by the
    // name its stretched link carries.
    expect(
      await within(screen.getByRole("navigation")).findByRole("link", { name: "Pie64" }),
    ).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "Open Pie64" })).toBeInTheDocument();
  });

  it("renders the two placeholder pages with their copy", async () => {
    stubApi();
    window.history.pushState({}, "", "/stats");
    render(<App />);
    expect(await screen.findByText("Stats arrive in phase 6.")).toBeInTheDocument();
  });

  it("applies the stored theme and never renders the API token", async () => {
    stubApi("light");
    render(<App />);
    await waitFor(() => {
      expect(document.documentElement.dataset.theme).toBe("light");
    });
    expect(document.body.innerHTML).not.toContain("never-render-me");
  });

  it("leaves the theme to the operating system when the setting says system", async () => {
    stubApi("system");
    render(<App />);
    await waitFor(() => {
      expect(document.documentElement.dataset.theme).toBeUndefined();
    });
  });

  it("refetches the instances when an instance event arrives", async () => {
    vi.useFakeTimers();
    const { calls } = stubApi();
    render(<App />);
    await vi.waitFor(() => {
      expect(calls.filter((call) => call.url === "/api/instances")).toHaveLength(1);
    });
    act(() => {
      FakeEventSource.last?.connect();
      FakeEventSource.last?.emit("instance", { name: "Pie64", state: "stopping" }, 1);
      FakeEventSource.last?.emit("instance", { name: "Pie64", state: "stopped" }, 2);
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(250);
    });
    expect(calls.filter((call) => call.url === "/api/instances")).toHaveLength(2);
    vi.useRealTimers();
  });

  it("refetches the alerts when an alert event arrives", async () => {
    const { calls } = stubApi();
    render(<App />);
    // The unread badge is the proof that the first response landed, not merely that the
    // request went out: react-query folds an invalidation into a first fetch that is
    // still in flight, so emitting before the badge paints would test nothing.
    expect(await screen.findByText("1")).toBeInTheDocument();
    act(() => {
      FakeEventSource.last?.connect();
      FakeEventSource.last?.emit("alert", { id: 1, kind: "crash" }, 1);
    });
    await vi.waitFor(() => {
      expect(calls.filter((call) => call.url === "/api/alerts").length).toBeGreaterThan(1);
    });
  });
});
