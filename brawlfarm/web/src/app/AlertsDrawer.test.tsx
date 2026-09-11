/** The drawer: newest first, one Dismiss per row, one Dismiss all in the header, and a
 * sentence when there is nothing to show. */
import { renderHook, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AlertsDrawer } from "./AlertsDrawer";
import { closeAlertsDrawer, openAlertsDrawer } from "../lib/alertsDrawer";
import { resetToasts, useToasts } from "../lib/toast";
import { jsonResponse, stubFetch } from "../test/http";
import { makeAlert } from "../test/fixtures";
import { renderWithProviders } from "../test/renderWithProviders";

function toastMessages(): string[] {
  return renderHook(() => useToasts()).result.current.map((item) => item.message);
}

beforeEach(() => {
  openAlertsDrawer();
});

afterEach(() => {
  closeAlertsDrawer();
  resetToasts();
  vi.unstubAllGlobals();
});

const ALERTS = [
  makeAlert({
    id: 9,
    ts: "2026-09-11T19:42:00",
    instance: "Pie64_1",
    kind: "offline",
    title: "Instance offline",
    detail: "misses=3",
  }),
  makeAlert({
    id: 8,
    ts: "2026-09-11T18:10:00",
    instance: "Pie64",
    kind: "crash",
    title: "Bot crashed",
    detail: "err=adb did not answer",
  }),
];

describe("AlertsDrawer", () => {
  it("lists the alerts newest first with kind, instance, time and detail", async () => {
    stubFetch(() => jsonResponse({ alerts: ALERTS, unread: 2 }));
    renderWithProviders(<AlertsDrawer />);
    const rows = await screen.findAllByRole("listitem");
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveTextContent("Offline");
    expect(rows[0]).toHaveTextContent("Pie64_1");
    expect(rows[0]).toHaveTextContent("19:42");
    expect(rows[0]).toHaveTextContent("misses=3");
    expect(rows[0].querySelector("[data-tone]")).toHaveAttribute("data-tone", "bad");
    expect(rows[1]).toHaveTextContent("Crash");
  });

  it("dismisses one row", async () => {
    const { calls } = stubFetch((url) =>
      url === "/api/alerts"
        ? jsonResponse({ alerts: ALERTS, unread: 2 })
        : new Response(null, { status: 204 }),
    );
    renderWithProviders(<AlertsDrawer />);
    const rows = await screen.findAllByRole("listitem");
    await userEvent.click(within(rows[0]).getByRole("button", { name: "Dismiss" }));
    await vi.waitFor(() => {
      expect(calls.map((call) => call.url)).toContain("/api/alerts/9/dismiss");
    });
  });

  it("dismisses all of them and says so", async () => {
    const { calls } = stubFetch((url) =>
      url === "/api/alerts"
        ? jsonResponse({ alerts: ALERTS, unread: 2 })
        : new Response(null, { status: 204 }),
    );
    renderWithProviders(<AlertsDrawer />);
    await userEvent.click(await screen.findByRole("button", { name: "Dismiss all" }));
    await vi.waitFor(() => {
      expect(calls.map((call) => call.url)).toContain("/api/alerts/dismiss-all");
    });
    expect(toastMessages()).toContain("Alerts dismissed");
  });

  it("says what the drawer is for when it is empty", async () => {
    stubFetch(() => jsonResponse({ alerts: [], unread: 0 }));
    renderWithProviders(<AlertsDrawer />);
    expect(
      await screen.findByText(
        "No alerts. Offline instances, crashes and wrong-mode recoveries show up here.",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Dismiss all" })).not.toBeInTheDocument();
  });
});
