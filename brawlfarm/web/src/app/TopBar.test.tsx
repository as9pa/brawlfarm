/** The top bar: which page you are on, whether the stream is live, and how many alerts
 * are waiting. */
import { renderHook, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { TopBar, pageTitle } from "./TopBar";
import { closeAlertsDrawer, useAlertsDrawerOpen } from "../lib/alertsDrawer";
import { jsonResponse, stubFetch } from "../test/http";
import { makeAlert } from "../test/fixtures";
import { renderWithProviders } from "../test/renderWithProviders";

function alertsDrawerIsOpen(): boolean {
  return renderHook(() => useAlertsDrawerOpen()).result.current;
}

afterEach(() => {
  closeAlertsDrawer();
  vi.unstubAllGlobals();
});

describe("pageTitle", () => {
  it("names the three sections and uses the instance name on its own page", () => {
    expect(pageTitle("/")).toBe("Fleet");
    expect(pageTitle("/stats")).toBe("Stats");
    expect(pageTitle("/settings")).toBe("Settings");
    expect(pageTitle("/settings/notifications")).toBe("Settings");
    expect(pageTitle("/instances/Pie64_1")).toBe("Pie64_1");
  });
});

describe("TopBar", () => {
  it("shows the page title and the connection pill", async () => {
    stubFetch(() => jsonResponse({ alerts: [], unread: 0 }));
    renderWithProviders(<TopBar />, { route: "/instances/Pie64" });
    expect(screen.getByRole("heading", { name: "Pie64" })).toBeInTheDocument();
    // Nothing has subscribed to the stream in this test, so it is still connecting.
    expect(screen.getByText("Connecting")).toBeInTheDocument();
    expect(screen.getByText("Connecting").closest("[data-tone]")).toHaveAttribute(
      "data-tone",
      "idle",
    );
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
