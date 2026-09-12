/** Settings > Schedule: one switch, and what it writes. */
import { renderHook, screen, waitFor } from "@testing-library/react";
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
    { route: "/settings/schedule" },
  );
}

function puts(calls: FetchCall[]): AppSettings[] {
  return calls
    .filter((call) => call.init?.method === "PUT")
    .map((call) => JSON.parse(String(call.init?.body)) as AppSettings);
}

function toastMessages(): string[] {
  return renderHook(() => useToasts()).result.current.map((item) => item.message);
}

afterEach(() => {
  resetToasts();
  vi.unstubAllGlobals();
});

describe("Settings > Schedule", () => {
  it("writes scheduler.default_enabled and says what it means", async () => {
    const { calls, current } = server();
    mount();
    const toggle = await screen.findByRole("switch", { name: "Schedule on by default" });
    expect(toggle).toHaveAttribute("aria-checked", "true");
    expect(
      screen.getByText(
        "New instances follow the anti-ban schedule unless you turn it off per instance.",
      ),
    ).toBeInTheDocument();

    await userEvent.click(toggle);
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    expect(puts(calls)[0].scheduler.default_enabled).toBe(false);
    expect(current().scheduler.default_enabled).toBe(false);
    expect(toastMessages()).toEqual(["Settings saved"]);
  });

  it("puts the API's message under the row", async () => {
    const { calls } = server({
      putStatus: 422,
      putDetail: "scheduler.default_enabled: Input should be a valid boolean",
    });
    mount();
    const toggle = await screen.findByRole("switch", { name: "Schedule on by default" });
    await userEvent.click(toggle);
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    expect(
      await screen.findByText("default_enabled: Input should be a valid boolean"),
    ).toBeInTheDocument();
  });
});
