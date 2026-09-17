/** The whole tree: the four routes, the theme bootstrap, and the live handlers that turn
 * server-sent events into cache updates. */
import { act, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { closeAlertsDrawer } from "./lib/alertsDrawer";
import { closeEvents, setEventSourceFactory } from "./live/useEvents";
import { resetToasts } from "./lib/toast";
import { jpegResponse, jsonResponse, stubFetch } from "./test/http";
import { makeAlert, makeConnection, makeInstance, makeSettings, makeStats } from "./test/fixtures";

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
      return jsonResponse(
        makeSettings({
          app: { port: 8765, theme },
          connection: { adb_path: "adb.exe", brawl_api_token: "never-render-me" },
        }),
      );
    }
    if (url === "/api/instances") return jsonResponse({ instances: [makeInstance()] });
    if (url === "/api/alerts") return jsonResponse({ alerts: [makeAlert()], unread: 1 });
    if (url.endsWith("preview.jpg")) return jpegResponse();
    if (url === "/api/setup/scan") {
      return jsonResponse({ adb_path: "adb.exe", adb_found: true, conf_found: true, instances: [] });
    }
    if (url === "/api/connection/check") return jsonResponse(makeConnection());
    if (url.startsWith("/api/stats")) return jsonResponse(makeStats());
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
    // where it lives: the rail entry inside the Sections landmark, the card by the
    // name its stretched link carries.
    expect(
      await within(screen.getByRole("navigation", { name: "Sections" })).findByRole("link", {
        name: "Pie64",
      }),
    ).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "Open Pie64" })).toBeInTheDocument();
  });

  it("gives the page one h1 and leaves the top bar without one", async () => {
    // Two level-one headings saying the same word is a screen reader reading the page
    // name twice and a document outline with no top. The bar carries a breadcrumb
    // instead, so the page's own heading is the only h1 on screen.
    stubApi();
    render(<App />);
    expect(await screen.findByRole("link", { name: "Open Pie64" })).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 1 }).map((h) => h.textContent)).toEqual([
      "Fleet",
    ]);
  });

  it("renders the Stats page at /stats", async () => {
    // "Stats" is on screen three times here: the rail link, the bar's breadcrumb and the
    // page heading under it, so only a role query can pick out the one that matters.
    stubApi();
    window.history.pushState({}, "", "/stats");
    render(<App />);
    expect(await screen.findByRole("heading", { level: 1, name: "Stats" })).toBeInTheDocument();
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

  it("puts a skip link first and points it at the main region", async () => {
    stubApi();
    render(<App />);
    expect(await screen.findByRole("link", { name: "Open Pie64" })).toBeInTheDocument();
    const skip = screen.getByRole("link", { name: "Skip to content" });
    // First in the DOM is first in the tab order, which is the only thing that makes a
    // skip link worth having.
    expect(document.querySelectorAll("a[href], button, [tabindex]")[0]).toBe(skip);
    expect(skip).toHaveAttribute("href", "#main-content");
    const main = document.getElementById("main-content");
    expect(main?.tagName).toBe("MAIN");
    // Without the tabindex the link moves the scroll position and leaves focus behind.
    expect(main).toHaveAttribute("tabindex", "-1");
  });

  it("writes no theme-color override when the computed ground colour is empty", async () => {
    // jsdom has no stylesheet behind --ground, so there is no colour to write and the
    // effect must not leave an empty meta behind for the browser chrome to read.
    stubApi("dark");
    render(<App />);
    await waitFor(() => {
      expect(document.documentElement.dataset.theme).toBe("dark");
    });
    expect(document.head.querySelector('meta[name="theme-color"]:not([media])')).toBeNull();
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

  it("sends /settings to the first section and keeps one title across them", async () => {
    stubApi();
    window.history.pushState({}, "", "/settings");
    render(<App />);
    expect(await screen.findByRole("heading", { level: 1, name: "Instances" })).toBeInTheDocument();
    expect(window.location.pathname).toBe("/settings/instances");
    // Every section is one page as far as the bar's breadcrumb is concerned.
    expect(screen.getByRole("navigation", { name: "Breadcrumb" })).toHaveTextContent("Settings");
  });

  it("puts the wizard on its own page, outside the shell", async () => {
    stubApi();
    window.history.pushState({}, "", "/setup");
    render(<App />);
    // The wizard's step rail, which no other page has. This document already names an adb
    // path and an instance, so the wizard opens further along than step 1.
    expect(await screen.findByRole("button", { name: "BlueStacks" })).toBeInTheDocument();
    // No rail, no top bar, no alerts drawer: there is no fleet to frame yet.
    expect(screen.queryByRole("link", { name: "Fleet" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Alerts/ })).not.toBeInTheDocument();
    window.history.pushState({}, "", "/");
  });
});
