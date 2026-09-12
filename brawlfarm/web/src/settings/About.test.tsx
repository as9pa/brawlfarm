/** Settings > About: the theme as three cards in a radio group, the running version, the
 * three links and the attribution line. */
import { renderHook, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Settings } from "./Settings";
import type { AppSettings } from "../api/types";
import { resetToasts, useToasts } from "../lib/toast";
import { makeSettings } from "../test/fixtures";
import { type FetchCall, jsonResponse, stubFetch } from "../test/http";
import { renderWithProviders } from "../test/renderWithProviders";

function server(options: { putStatus?: number; putDetail?: string } = {}) {
  let stored = makeSettings();
  const { calls } = stubFetch((url, init) => {
    if (url === "/api/health") {
      return jsonResponse({
        version: "1.0.0",
        home: "C:/data/brawlfarm",
        instances: 1,
        uptime_s: 12.5,
      });
    }
    if (url !== "/api/settings") throw new Error(`unstubbed request: ${url}`);
    if (init?.method !== "PUT") return jsonResponse(stored);
    if (options.putStatus !== undefined) {
      return jsonResponse({ detail: options.putDetail }, options.putStatus);
    }
    stored = JSON.parse(String(init.body)) as AppSettings;
    return jsonResponse(stored);
  });
  return { calls, current: () => stored };
}

function mount() {
  return renderWithProviders(
    <Routes>
      <Route path="/settings/:section" element={<Settings />} />
    </Routes>,
    { route: "/settings/about" },
  );
}

function puts(calls: FetchCall[]): AppSettings[] {
  return calls
    .filter((call) => call.url === "/api/settings" && call.init?.method === "PUT")
    .map((call) => JSON.parse(String(call.init?.body)) as AppSettings);
}

function toastMessages(): string[] {
  return renderHook(() => useToasts()).result.current.map((item) => item.message);
}

afterEach(() => {
  resetToasts();
  vi.unstubAllGlobals();
});

describe("Settings > About", () => {
  it("offers the three themes as one radio group and writes the one that is picked", async () => {
    const { calls, current } = server();
    mount();
    const group = await screen.findByRole("radiogroup", { name: "Theme" });
    expect(within(group).getAllByRole("radio").map((radio) => radio.textContent)).toEqual([
      "SystemFollows Windows.",
      "LightAlways light.",
      "DarkAlways dark.",
    ]);
    expect(within(group).getByRole("radio", { name: /System/ })).toHaveAttribute(
      "aria-checked",
      "true",
    );

    await userEvent.click(within(group).getByRole("radio", { name: /Dark/ }));
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    expect(puts(calls)[0].app.theme).toBe("dark");
    expect(current().app.theme).toBe("dark");
    expect(toastMessages()).toEqual(["Settings saved"]);
    await waitFor(() => {
      expect(within(group).getByRole("radio", { name: /Dark/ })).toHaveAttribute(
        "aria-checked",
        "true",
      );
    });
  });

  it("shows the running version, the three links and the attribution", async () => {
    server();
    mount();
    expect(await screen.findByText("brawlfarm 1.0.0")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "GitHub" })).toHaveAttribute(
      "href",
      "https://github.com/as9pa/brawlfarm",
    );
    expect(screen.getByRole("link", { name: "Setup guide" })).toHaveAttribute(
      "href",
      "https://github.com/as9pa/brawlfarm#requirements",
    );
    expect(screen.getByRole("link", { name: "Safety rails" })).toHaveAttribute(
      "href",
      "https://github.com/as9pa/brawlfarm#safety-rails",
    );
    expect(
      screen.getByText(
        "brawlfarm is not affiliated with or endorsed by Supercell. Brawl Stars and its art belong to Supercell. MIT licensed.",
      ),
    ).toBeInTheDocument();
    // The home folder is on the health payload but belongs to the Data section's tooltip.
    expect(screen.queryByText(/C:\/data\/brawlfarm/)).not.toBeInTheDocument();
  });

  it("puts a refused theme under the group that wrote it", async () => {
    const { calls } = server({
      putStatus: 422,
      putDetail: "app.theme: Input should be 'system', 'dark' or 'light'",
    });
    mount();
    const group = await screen.findByRole("radiogroup", { name: "Theme" });
    await userEvent.click(within(group).getByRole("radio", { name: /Light/ }));
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    expect(
      await screen.findByText("theme: Input should be 'system', 'dark' or 'light'"),
    ).toBeInTheDocument();
    // Nothing was stored, so nothing claims it was.
    expect(toastMessages()).toEqual([]);
    expect(within(group).getByRole("radio", { name: /System/ })).toHaveAttribute(
      "aria-checked",
      "true",
    );
  });
});
