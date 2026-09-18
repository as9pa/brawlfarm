/** The settings frame: six sections in the nav, the one you are on marked, the title with
 * its one sentence, and a section id that is not one of the six saying so instead of
 * quietly moving you somewhere else. */
import { screen, within } from "@testing-library/react";
import { Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Settings } from "./Settings";
import { makeInstance, makeSettings } from "../test/fixtures";
import { jsonResponse, stubFetch } from "../test/http";
import { renderWithProviders } from "../test/renderWithProviders";

function stubApi(): void {
  stubFetch((url) => {
    if (url === "/api/settings") return jsonResponse(makeSettings());
    if (url === "/api/instances") return jsonResponse({ instances: [makeInstance()] });
    throw new Error(`unstubbed request: ${url}`);
  });
}

function mount(route: string) {
  return renderWithProviders(
    <Routes>
      <Route path="/settings/:section" element={<Settings />} />
    </Routes>,
    { route },
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Settings", () => {
  it("lists the six sections in order and marks the one you are on", async () => {
    stubApi();
    mount("/settings/instances");
    const nav = screen.getByRole("navigation", { name: "Settings sections" });
    expect(within(nav).getAllByRole("link").map((link) => link.textContent)).toEqual([
      "Instances",
      "Connection",
      "Behavior",
      "Notifications",
      "Data",
      "About",
    ]);
    // Schedule folded into Behavior, so its own link is gone.
    expect(within(nav).queryByRole("link", { name: "Schedule" })).not.toBeInTheDocument();
    expect(within(nav).getByRole("link", { name: "Instances" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(within(nav).getByRole("link", { name: "About" })).toHaveAttribute(
      "href",
      "/settings/about",
    );
    expect(await screen.findByRole("heading", { level: 1, name: "Instances" })).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByText("Which BlueStacks instances brawlfarm farms.")).toBeInTheDocument();
  });

  it("shows no saved caption until something has been saved", async () => {
    stubApi();
    mount("/settings/instances");
    expect(await screen.findByRole("heading", { level: 1, name: "Instances" })).toBeInTheDocument();
    expect(screen.queryByText(/^Saved \d\d:\d\d$/)).not.toBeInTheDocument();
  });

  it("says so when the section in the URL is not one of the six", () => {
    stubApi();
    mount("/settings/nope");
    expect(screen.getByText("unknown settings section")).toBeInTheDocument();
    // It does not quietly move you somewhere else, so the nav is still there to choose from.
    expect(screen.getByRole("navigation", { name: "Settings sections" })).toBeInTheDocument();
  });
});
