/** The settings frame: six sections in the nav, the one you are on marked, the title with
 * its one sentence, and a section id that is not one of the six saying so instead of
 * quietly moving you somewhere else. */
import { fireEvent, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Settings } from "./Settings";
import type { AppSettings } from "../api/types";
import { makeInstance, makeSettings } from "../test/fixtures";
import { jsonResponse, stubFetch } from "../test/http";
import { renderWithProviders } from "../test/renderWithProviders";

function stubApi(): void {
  let stored = makeSettings();
  stubFetch((url, init) => {
    if (url === "/api/instances") return jsonResponse({ instances: [makeInstance()] });
    if (url === "/api/settings/defaults") return jsonResponse(makeSettings());
    if (url !== "/api/settings") throw new Error(`unstubbed request: ${url}`);
    if (init?.method !== "PUT") return jsonResponse(stored);
    stored = JSON.parse(String(init.body)) as AppSettings;
    return jsonResponse(stored);
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
    expect(screen.queryByText(/saved \d\d:\d\d$/)).not.toBeInTheDocument();
  });

  it("names the section in the saved caption and announces it politely", async () => {
    stubApi();
    mount("/settings/behavior");
    await userEvent.click(await screen.findByRole("switch", { name: "Leave the gas early" }));
    const caption = await screen.findByText(/^Behavior saved \d\d:\d\d$/);
    expect(caption).toHaveClass("text-[12px]", "text-muted");
    expect(caption.closest("[aria-live]")).toHaveAttribute("aria-live", "polite");
  });

  it("shows the caption only on the section that saved", async () => {
    stubApi();
    mount("/settings/behavior");
    await userEvent.click(await screen.findByRole("switch", { name: "Leave the gas early" }));
    expect(await screen.findByText(/^Behavior saved \d\d:\d\d$/)).toBeInTheDocument();

    // One hook serves all six sections, so Behavior's save must not be read back as the
    // save of whichever section the reader walks into next.
    await userEvent.click(screen.getByRole("link", { name: "Notifications" }));
    expect(
      await screen.findByRole("heading", { level: 1, name: "Notifications" }),
    ).toBeInTheDocument();
    expect(screen.queryByText(/saved \d\d:\d\d$/)).not.toBeInTheDocument();

    // Coming back is not a new save, and the caption is still true, so it is still there.
    await userEvent.click(screen.getByRole("link", { name: "Behavior" }));
    expect(await screen.findByText(/^Behavior saved \d\d:\d\d$/)).toBeInTheDocument();

    // A save in another section takes the caption over, under that section's name.
    await userEvent.click(screen.getByRole("link", { name: "Notifications" }));
    const topic = await screen.findByLabelText("ntfy topic");
    fireEvent.change(topic, { target: { value: "brawlfarm-home" } });
    fireEvent.blur(topic);
    expect(await screen.findByText(/^Notifications saved \d\d:\d\d$/)).toBeInTheDocument();
    expect(screen.queryByText(/^Behavior saved \d\d:\d\d$/)).not.toBeInTheDocument();
  });

  it("says so when the section in the URL is not one of the six", () => {
    stubApi();
    mount("/settings/nope");
    expect(screen.getByText("unknown settings section")).toBeInTheDocument();
    // It does not quietly move you somewhere else, so the nav is still there to choose from.
    expect(screen.getByRole("navigation", { name: "Settings sections" })).toBeInTheDocument();
  });
});
