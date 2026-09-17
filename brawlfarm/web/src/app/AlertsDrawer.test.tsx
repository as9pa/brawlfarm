/** The drawer: newest first under a day heading, one Dismiss per row, a Dismiss all that
 * asks first, a skeleton while the list loads, and a sentence when there is nothing to
 * show. */
import { renderHook, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AlertsDrawer } from "./AlertsDrawer";
import { closeAlertsDrawer, openAlertsDrawer } from "../lib/alertsDrawer";
import { dateTime } from "../lib/format";
import { resetToasts, useToasts } from "../lib/toast";
import { jsonResponse, stubFetch } from "../test/http";
import { makeAlert } from "../test/fixtures";
import { renderWithProviders } from "../test/renderWithProviders";

const EMPTY_SENTENCE =
  "No alerts. Offline instances, crashes and wrong-mode recoveries show up here.";

function toastMessages(): string[] {
  return renderHook(() => useToasts()).result.current.map(
    (item) => item.message,
  );
}

/** The API's stamps have no timezone and mean local already, so a fixture that has to land
 * on a particular calendar day is written the same way. */
function localStamp(at: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  const day = `${at.getFullYear()}-${pad(at.getMonth() + 1)}-${pad(at.getDate())}`;
  return `${day}T${pad(at.getHours())}:${pad(at.getMinutes())}:${pad(at.getSeconds())}`;
}

function daysAgo(days: number): string {
  const at = new Date();
  at.setDate(at.getDate() - days);
  return localStamp(at);
}

/** Opens the header's Dismiss all and answers the dialog it raises. Both buttons carry the
 * same label, so the confirm is reached through the dialog it sits in. */
async function confirmDismissAll() {
  await userEvent.click(
    await screen.findByRole("button", { name: "Dismiss all" }),
  );
  const dialog = screen.getByRole("dialog", { name: "Dismiss all alerts?" });
  await userEvent.click(
    within(dialog).getByRole("button", { name: "Dismiss all" }),
  );
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
    expect(rows[0]).toHaveTextContent("misses=3");
    expect(rows[0].querySelector("[data-tone]")).toHaveAttribute(
      "data-tone",
      "bad",
    );
    expect(rows[1]).toHaveTextContent("Crash");
    // Both are older than today, so the Today group has nothing to render.
    expect(screen.queryByText("Today")).not.toBeInTheDocument();
  });

  it("counts the alerts in its title", async () => {
    stubFetch(() =>
      jsonResponse({ alerts: [...ALERTS, makeAlert({ id: 7 })], unread: 3 }),
    );
    renderWithProviders(<AlertsDrawer />);
    expect(
      await screen.findByRole("dialog", { name: "Alerts, 3" }),
    ).toBeInTheDocument();
  });

  it("shows skeleton rows, and no empty copy, while the list is still loading", () => {
    stubFetch(() => new Promise<Response>(() => undefined));
    renderWithProviders(<AlertsDrawer />);
    expect(screen.getByTestId("alerts-skeleton")).toBeInTheDocument();
    expect(screen.queryByText(EMPTY_SENTENCE)).not.toBeInTheDocument();
    expect(screen.queryAllByRole("listitem")).toHaveLength(0);
  });

  it("groups the rows by day and keeps the exact stamp in a title", async () => {
    const today = localStamp(new Date());
    const yesterday = daysAgo(1);
    stubFetch(() =>
      jsonResponse({
        alerts: [
          makeAlert({ id: 9, ts: today }),
          makeAlert({ id: 8, ts: yesterday }),
        ],
        unread: 2,
      }),
    );
    renderWithProviders(<AlertsDrawer />);
    const rows = await screen.findAllByRole("listitem");
    expect(screen.getByText("Today")).toBeInTheDocument();
    expect(screen.getByText("Earlier")).toBeInTheDocument();
    // Yesterday's crash reads as a span of hours, with the dated stamp a hover away.
    const stamp = within(rows[1]).getByTitle(dateTime(yesterday));
    expect(stamp).toHaveTextContent(/^\d+ h$/);
    expect(within(rows[0]).getByTitle(dateTime(today))).toBeInTheDocument();
  });

  it("dismisses one row", async () => {
    const { calls } = stubFetch((url) =>
      url === "/api/alerts"
        ? jsonResponse({ alerts: ALERTS, unread: 2 })
        : new Response(null, { status: 204 }),
    );
    renderWithProviders(<AlertsDrawer />);
    const rows = await screen.findAllByRole("listitem");
    await userEvent.click(
      within(rows[0]).getByRole("button", { name: "Dismiss" }),
    );
    await vi.waitFor(() => {
      expect(calls.map((call) => call.url)).toContain("/api/alerts/9/dismiss");
    });
  });

  it("asks before it dismisses all of them", async () => {
    const { calls } = stubFetch((url) =>
      url === "/api/alerts"
        ? jsonResponse({ alerts: ALERTS, unread: 2 })
        : new Response(null, { status: 204 }),
    );
    renderWithProviders(<AlertsDrawer />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Dismiss all" }),
    );
    expect(
      screen.getByText(
        "They leave the drawer and the bell count. Nothing is un-dismissed.",
      ),
    ).toBeInTheDocument();
    expect(calls.map((call) => call.url)).not.toContain(
      "/api/alerts/dismiss-all",
    );
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(calls.map((call) => call.url)).not.toContain(
      "/api/alerts/dismiss-all",
    );
  });

  it("dismisses all of them and says so", async () => {
    const { calls } = stubFetch((url) =>
      url === "/api/alerts"
        ? jsonResponse({ alerts: ALERTS, unread: 2 })
        : new Response(null, { status: 204 }),
    );
    renderWithProviders(<AlertsDrawer />);
    await confirmDismissAll();
    await vi.waitFor(() => {
      expect(calls.map((call) => call.url)).toContain(
        "/api/alerts/dismiss-all",
      );
    });
    expect(toastMessages()).toContain("Alerts dismissed");
  });

  it("says why a dismiss was refused and leaves the row where it is", async () => {
    stubFetch((url) =>
      url === "/api/alerts"
        ? jsonResponse({ alerts: ALERTS, unread: 2 })
        : jsonResponse({ detail: "the alert store is gone" }, 500),
    );
    renderWithProviders(<AlertsDrawer />);
    const rows = await screen.findAllByRole("listitem");
    await userEvent.click(
      within(rows[0]).getByRole("button", { name: "Dismiss" }),
    );
    await vi.waitFor(() => {
      expect(toastMessages()).toEqual(["the alert store is gone"]);
    });
    // The row is only removed by a refetch, so a refused dismiss leaves it readable.
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
  });

  it("says why Dismiss all was refused", async () => {
    stubFetch((url) =>
      url === "/api/alerts"
        ? jsonResponse({ alerts: ALERTS, unread: 2 })
        : jsonResponse({ detail: "the alert store is gone" }, 500),
    );
    renderWithProviders(<AlertsDrawer />);
    await confirmDismissAll();
    await vi.waitFor(() => {
      expect(toastMessages()).toEqual(["the alert store is gone"]);
    });
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
  });

  it("says what the drawer is for when it is empty", async () => {
    stubFetch(() => jsonResponse({ alerts: [], unread: 0 }));
    renderWithProviders(<AlertsDrawer />);
    expect(await screen.findByText(EMPTY_SENTENCE)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Dismiss all" }),
    ).not.toBeInTheDocument();
  });
});
