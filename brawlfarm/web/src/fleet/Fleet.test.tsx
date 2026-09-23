/** The page around the cards: the count, the skeletons before the first response, the two
 * fleet-wide controls with their gates, the labelled totals row, the undo behind Stop all
 * and the sentence that tells a new user what to do next. */
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderHook } from "@testing-library/react";

import { Fleet } from "./Fleet";
import { resetToasts, useToasts } from "../lib/toast";
import { makeAlert, makeInstance } from "../test/fixtures";
import { jpegResponse, jsonResponse, stubFetch } from "../test/http";
import { renderWithProviders } from "../test/renderWithProviders";

function toastMessages(): string[] {
  return renderHook(() => useToasts()).result.current.map((item) => item.message);
}

function toastItems() {
  return renderHook(() => useToasts()).result.current;
}

/** The totals row read back as label/value pairs, and an empty list when the row is not
 * there at all. Scoped to the dl: "Games today" is a card metric label as well. */
function totalPairs(container: HTMLElement): string[][] {
  return [...container.querySelectorAll("dl > div")].map((pair) => [
    pair.querySelector("dt")?.textContent ?? "",
    pair.querySelector("dd")?.textContent ?? "",
  ]);
}

const FLEET = [
  makeInstance({ name: "Pie64", adb_port: 5555, state: "farming", today: { games: 12, trophies: 86 } }),
  makeInstance({ name: "Pie64_1", adb_port: 5565, state: "stopped", today: { games: 4, trophies: -12 } }),
  makeInstance({ name: "Pie64_3", adb_port: 5585, state: "offline", today: { games: 0, trophies: 0 } }),
];

function stubFleet(instances = FLEET, alerts: ReturnType<typeof makeAlert>[] = []) {
  return stubFetch((url) => {
    if (url === "/api/instances") return jsonResponse({ instances });
    if (url === "/api/alerts") return jsonResponse({ alerts, unread: alerts.length });
    if (url.startsWith("/api/stats")) {
      return jsonResponse({
        range: "today",
        instances: instances.map((inst) => inst.name),
        summary: {
          games: 16,
          trophies: 74,
          trophies_per_hour: null,
          avg_placement: 3.4,
          win_rate: null,
          hours_farmed: 3.6667,
        },
      });
    }
    if (url.endsWith("preview.jpg")) return jpegResponse();
    return jsonResponse({ ok: true });
  });
}

afterEach(() => {
  resetToasts();
  vi.unstubAllGlobals();
});

describe("Fleet", () => {
  it("heads the page with the instance count and totals today", async () => {
    stubFleet();
    const { container } = renderWithProviders(<Fleet />);
    expect(await screen.findByText("3 instances")).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 1 }).map((h) => h.textContent)).toEqual([
      "Fleet",
    ]);
    // One farming, one stopped, one offline; 12 + 4 + 0 games and 86 - 12 + 0 trophies
    // from the cards, and 3.6667 hours from the stats route.
    await vi.waitFor(() => {
      expect(totalPairs(container)).toEqual([
        ["Farming", "1 of 3"],
        ["Games today", "16"],
        ["Trophies today", "+74"],
        ["Farmed", "3 h 40 min"],
      ]);
    });
  });

  it("shows skeleton cards, and nothing numeric, before the first response", () => {
    stubFetch(() => new Promise<Response>(() => undefined));
    const { container } = renderWithProviders(<Fleet />);
    expect(screen.getAllByTestId("fleet-skeleton-card")).toHaveLength(3);
    expect(screen.getByText("Loading fleet")).toBeInTheDocument();
    expect(screen.queryByText("0 instances")).toBeNull();
    expect(totalPairs(container)).toEqual([]);
  });

  it("labels the totals as soon as there are two instances to add up", async () => {
    stubFleet([FLEET[0], FLEET[1]]);
    const { container } = renderWithProviders(<Fleet />);
    await vi.waitFor(() => {
      expect(totalPairs(container)).toEqual([
        ["Farming", "1 of 2"],
        ["Games today", "16"],
        ["Trophies today", "+74"],
        ["Farmed", "3 h 40 min"],
      ]);
    });
  });

  it("counts one instance in the singular", async () => {
    stubFleet([FLEET[0]]);
    renderWithProviders(<Fleet />);
    expect(await screen.findByText("1 instance")).toBeInTheDocument();
  });

  it("starts and stops the whole fleet", async () => {
    const { calls } = stubFleet();
    renderWithProviders(<Fleet />);
    await userEvent.click(await screen.findByRole("button", { name: "Start all" }));
    await vi.waitFor(() => {
      expect(toastMessages()).toContain("Starting 3 instances");
    });
    expect(calls.filter((call) => call.url.endsWith("/start"))).toHaveLength(3);

    await userEvent.click(screen.getByRole("button", { name: "Stop all" }));
    await vi.waitFor(() => {
      expect(toastMessages()).toContain("Stopping 3 instances after their matches");
    });
    expect(calls.filter((call) => call.url.endsWith("/stop"))).toHaveLength(3);
  });

  it("hides the totals row and both all-controls for a single instance", async () => {
    stubFleet([FLEET[0]]);
    const { container } = renderWithProviders(<Fleet />);
    expect(await screen.findByText("1 instance")).toBeInTheDocument();
    expect(totalPairs(container)).toEqual([]);
    expect(screen.queryByRole("button", { name: "Start all" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Stop all" })).toBeNull();
  });

  it("says why Stop all is off when nothing is running", async () => {
    stubFleet([FLEET[1], makeInstance({ name: "Pie64_2", adb_port: 5575, state: "stopped" })]);
    renderWithProviders(<Fleet />);
    const stopAll = await screen.findByRole("button", { name: "Stop all" });
    expect(stopAll).toBeDisabled();
    expect(stopAll).toHaveAttribute("title", "Nothing is running");
    expect(screen.getByRole("button", { name: "Start all" })).toBeEnabled();
  });

  it("says why Start all is off when everything is running", async () => {
    stubFleet([FLEET[0], makeInstance({ name: "Pie64_2", adb_port: 5575, state: "starting" })]);
    renderWithProviders(<Fleet />);
    const startAll = await screen.findByRole("button", { name: "Start all" });
    expect(startAll).toBeDisabled();
    expect(startAll).toHaveAttribute("title", "Everything is running");
    expect(screen.getByRole("button", { name: "Stop all" })).toBeEnabled();
  });

  it("offers an undo after Stop all that starts exactly what was running", async () => {
    const { calls } = stubFleet();
    renderWithProviders(<Fleet />);
    await userEvent.click(await screen.findByRole("button", { name: "Stop all" }));
    await vi.waitFor(() => {
      expect(toastMessages()).toContain("Stopping 3 instances after their matches");
    });
    const undo = toastItems()[0]?.undo;
    expect(undo).toBeTypeOf("function");
    await undo?.();
    // Pie64 was the only one farming; the stopped and the offline card are left alone.
    expect(calls.filter((call) => call.url.endsWith("/start")).map((call) => call.url)).toEqual([
      "/api/instances/Pie64/start",
    ]);
  });

  it("says why a failed undo did not go through, once and with nothing to press", async () => {
    stubFetch((url) => {
      if (url.endsWith("/start")) return jsonResponse({ detail: "Pie64 is offline" }, 409);
      if (url === "/api/instances") return jsonResponse({ instances: FLEET });
      if (url === "/api/alerts") return jsonResponse({ alerts: [], unread: 0 });
      if (url.endsWith("preview.jpg")) return jpegResponse();
      if (url.endsWith("/stop")) return jsonResponse({ ok: true });
      return jsonResponse({
        range: "today",
        instances: [],
        summary: {
          games: 0,
          trophies: 0,
          trophies_per_hour: null,
          avg_placement: null,
          win_rate: null,
          hours_farmed: 0,
        },
      });
    });
    renderWithProviders(<Fleet />);
    await userEvent.click(await screen.findByRole("button", { name: "Stop all" }));
    await vi.waitFor(() => {
      expect(toastMessages()).toContain("Stopping 3 instances after their matches");
    });
    await toastItems()[0]?.undo?.();
    expect(toastMessages().filter((message) => message === "Pie64 is offline")).toHaveLength(1);
    const followUp = toastItems().at(-1);
    expect(followUp?.tone).toBe("bad");
    expect(followUp?.undo).toBeUndefined();
    expect(followUp?.retry).toBeUndefined();
  });

  it("says why Start all failed rather than claiming the fleet started", async () => {
    stubFetch((url) => {
      if (url.endsWith("/start")) return jsonResponse({ detail: "Pie64_3 is offline" }, 409);
      if (url === "/api/instances") return jsonResponse({ instances: FLEET });
      if (url === "/api/alerts") return jsonResponse({ alerts: [], unread: 0 });
      if (url.endsWith("preview.jpg")) return jpegResponse();
      return jsonResponse({
        range: "today",
        instances: [],
        summary: {
          games: 0,
          trophies: 0,
          trophies_per_hour: null,
          avg_placement: null,
          win_rate: null,
          hours_farmed: 0,
        },
      });
    });
    renderWithProviders(<Fleet />);
    await userEvent.click(await screen.findByRole("button", { name: "Start all" }));
    await vi.waitFor(() => {
      expect(toastMessages()).toContain("Pie64_3 is offline");
    });
    expect(toastMessages()).not.toContain("Starting 3 instances");
  });

  it("shows the newest alert above the grid", async () => {
    stubFleet(FLEET, [
      makeAlert({ id: 9, instance: "Pie64", kind: "crash", title: "Bot crashed", detail: "err=adb did not answer" }),
    ]);
    renderWithProviders(<Fleet />);
    expect(
      await screen.findByText("Pie64 crashed. Press Restart on its card."),
    ).toBeInTheDocument();
  });

  it("leaves an alert the bot handled itself to the drawer", async () => {
    stubFleet(FLEET, [makeAlert({ id: 9, instance: "Pie64", kind: "wrong_mode", title: "Wrong mode" })]);
    renderWithProviders(<Fleet />);
    expect(await screen.findByText("3 instances")).toBeInTheDocument();
    expect(
      screen.queryByText("Pie64 picked the wrong mode and switched back. Nothing to do."),
    ).toBeNull();
  });

  it("gives the strip's link every unread alert, not just the actionable ones", async () => {
    stubFleet(FLEET, [
      makeAlert({ id: 9, instance: "Pie64", kind: "crash", title: "Bot crashed", detail: "err=adb did not answer" }),
      makeAlert({ id: 8, instance: "Pie64", kind: "wrong_mode", title: "Wrong mode" }),
      makeAlert({ id: 7, instance: "Pie64_1", kind: "recover", title: "Recovering" }),
    ]);
    renderWithProviders(<Fleet />);
    expect(await screen.findByRole("button", { name: "All 3 alerts" })).toBeInTheDocument();
  });

  it("tells a new user what to do when there are no instances", async () => {
    stubFleet([]);
    renderWithProviders(<Fleet />);
    expect(await screen.findByText("No instances yet.")).toBeInTheDocument();
    expect(
      screen.getByText("Open setup to find your BlueStacks instances."),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open setup" })).toHaveAttribute("href", "/setup");
    expect(screen.queryByRole("button", { name: "Start all" })).not.toBeInTheDocument();
  });

  it("shows the API's own sentence when the list cannot be fetched", async () => {
    stubFetch((url) =>
      url === "/api/instances"
        ? jsonResponse({ detail: "adb did not answer" }, 503)
        : jsonResponse({ alerts: [], unread: 0, summary: { hours_farmed: 0 } }),
    );
    renderWithProviders(<Fleet />);
    expect(await screen.findByText("adb did not answer")).toBeInTheDocument();
  });
});
