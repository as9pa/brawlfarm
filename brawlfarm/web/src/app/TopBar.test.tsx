/** The top bar: which page you are on, whether the stream is live, and how many alerts
 * are waiting. */
import { renderHook, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { TopBar, alertsLabel, pageTitle } from "./TopBar";
import { closeAlertsDrawer, useAlertsDrawerOpen } from "../lib/alertsDrawer";
import type { Connection } from "../live/useEvents";
import { jsonResponse, stubFetch } from "../test/http";
import { makeAlert } from "../test/fixtures";
import { renderWithProviders } from "../test/renderWithProviders";

// The stream is module state, so the connection is stubbed rather than driven: these
// tests are about what the bar says, not about how the stream gets there.
const live = vi.hoisted(() => ({ connection: "connecting" as Connection }));

vi.mock("../live/useEvents", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../live/useEvents")>()),
  useConnection: () => live.connection,
}));

function alertsDrawerIsOpen(): boolean {
  return renderHook(() => useAlertsDrawerOpen()).result.current;
}

afterEach(() => {
  live.connection = "connecting";
  closeAlertsDrawer();
  vi.unstubAllGlobals();
});

describe("pageTitle", () => {
  it("names the four sections and uses the instance name on its own page", () => {
    expect(pageTitle("/")).toBe("Fleet");
    expect(pageTitle("/stats")).toBe("Stats");
    expect(pageTitle("/calibration")).toBe("Calibration");
    expect(pageTitle("/settings")).toBe("Settings");
    expect(pageTitle("/settings/notifications")).toBe("Settings");
    expect(pageTitle("/instances/Pie64_1")).toBe("Fleet / Pie64_1");
  });
});

describe("alertsLabel", () => {
  it("names the control by the true unread count, capped badge or not", () => {
    expect(alertsLabel(0)).toBe("Alerts, no unread");
    expect(alertsLabel(1)).toBe("Alerts, 1 unread");
    expect(alertsLabel(6)).toBe("Alerts, 6 unread");
    expect(alertsLabel(120)).toBe("Alerts, 120 unread");
  });
});

describe("TopBar", () => {
  it("shows the breadcrumb and the connection pill, and no heading of its own", async () => {
    stubFetch(() => jsonResponse({ alerts: [], unread: 0 }));
    renderWithProviders(<TopBar />, { route: "/instances/Pie64" });
    expect(screen.getByRole("navigation", { name: "Breadcrumb" })).toHaveTextContent(
      "Fleet / Pie64",
    );
    // The page under the bar owns the one h1, so the bar itself is no heading at all.
    expect(screen.queryAllByRole("heading")).toHaveLength(0);
    // Nothing has subscribed to the stream in this test, so it is still connecting.
    expect(screen.getByText("Connecting")).toBeInTheDocument();
    expect(screen.getByText("Connecting").closest("[data-tone]")).toHaveAttribute(
      "data-tone",
      "idle",
    );
  });

  it("says in a sentence that it is reconnecting and what that costs", async () => {
    live.connection = "reconnecting";
    stubFetch(() => jsonResponse({ alerts: [], unread: 0 }));
    renderWithProviders(<TopBar />);
    const line = screen.getByRole("status");
    expect(line).toHaveTextContent("Reconnecting. Figures may be up to 30 s old.");
    expect(line).toHaveAttribute("aria-live", "polite");
  });

  it("keeps a quiet Live label and no second row once the stream is live", async () => {
    live.connection = "live";
    stubFetch(() => jsonResponse({ alerts: [], unread: 0 }));
    renderWithProviders(<TopBar />);
    expect(screen.getByText("Live")).toBeInTheDocument();
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("names the Alerts control by its unread count", async () => {
    stubFetch(() => jsonResponse({ alerts: [], unread: 6 }));
    renderWithProviders(<TopBar />);
    expect(await screen.findByRole("button", { name: "Alerts, 6 unread" })).toBeInTheDocument();
  });

  it("caps the badge at 99+ while the name still says the true count", async () => {
    stubFetch(() => jsonResponse({ alerts: [], unread: 120 }));
    renderWithProviders(<TopBar />);
    expect(await screen.findByText("99+")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Alerts, 120 unread" })).toBeInTheDocument();
  });

  it("badges the Alerts button with the unread count and hides it at zero", async () => {
    stubFetch(() => jsonResponse({ alerts: [makeAlert(), makeAlert({ id: 2 })], unread: 2 }));
    const { client } = renderWithProviders(<TopBar />);
    expect(await screen.findByText("2")).toBeInTheDocument();
    client.setQueryData(["alerts"], { alerts: [], unread: 0 });
    await vi.waitFor(() => {
      expect(screen.queryByText("2")).not.toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: /Alerts/ })).toBeInTheDocument();
  });

  it("opens the drawer store when Alerts is clicked", async () => {
    stubFetch(() => jsonResponse({ alerts: [], unread: 0 }));
    renderWithProviders(<TopBar />);
    expect(alertsDrawerIsOpen()).toBe(false);
    await userEvent.click(screen.getByRole("button", { name: /Alerts/ }));
    expect(alertsDrawerIsOpen()).toBe(true);
  });
});
