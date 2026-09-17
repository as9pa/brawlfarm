/** The page around the cards: the count, the two fleet-wide controls, the totals line and
 * the sentence that tells a new user what to do next. */
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
          avg_rank: 3.4,
          top4_rate: null,
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
    renderWithProviders(<Fleet />);
    expect(await screen.findByText("3 instances")).toBeInTheDocument();
    // One farming, one stopped, one offline; 12 + 4 + 0 games and 86 - 12 + 0 trophies
    // from the cards, and 3.6667 hours from the stats route.
    expect(
      await screen.findByText(
        "1 farming · 16 games today · +74 trophies today · 3 h 40 min farmed",
      ),
    ).toBeInTheDocument();
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

  it("says starting and stopping one instance in the singular", async () => {
    const { calls } = stubFleet([FLEET[0]]);
    renderWithProviders(<Fleet />);
    await userEvent.click(await screen.findByRole("button", { name: "Start all" }));
    await vi.waitFor(() => {
      expect(toastMessages()).toContain("Starting 1 instance");
    });
    expect(calls.filter((call) => call.url.endsWith("/start"))).toHaveLength(1);

    await userEvent.click(screen.getByRole("button", { name: "Stop all" }));
    await vi.waitFor(() => {
      expect(toastMessages()).toContain("Stopping 1 instance after its match");
    });
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
          avg_rank: null,
          top4_rate: null,
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
