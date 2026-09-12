/** Settings > Data: open the folder, delete one instance's folder, reset everything. */
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

const OPEN = "/api/settings/open-data-folder";
const RESET = "/api/settings/reset";
const DELETE_DATA = "/api/instances/Pie64/data";

const FLEET = makeSettings({
  instances: [
    { name: "Pie64", adb_port: 5555, player_tag: "#2P0YLQ9" },
    { name: "Pie64_3", adb_port: 5585, player_tag: "" },
  ],
});

function server(
  options: {
    openStatus?: number;
    openDetail?: string;
    deleteStatus?: number;
    deleteDetail?: string;
  } = {},
) {
  let stored = FLEET;
  const { calls } = stubFetch((url, init) => {
    if (url === "/api/health") {
      return jsonResponse({
        version: "1.0.0",
        home: "C:/data/brawlfarm",
        instances: 2,
        uptime_s: 12.5,
      });
    }
    if (url === OPEN) {
      if (options.openStatus !== undefined) {
        return jsonResponse({ detail: options.openDetail }, options.openStatus);
      }
      return jsonResponse(null, 204);
    }
    if (url === RESET) {
      // What settings_routes.py does: every section back to its model default, the
      // instances list carried over untouched.
      stored = { ...makeSettings(), instances: stored.instances };
      return jsonResponse(stored);
    }
    if (url === DELETE_DATA) {
      if (options.deleteStatus !== undefined) {
        return jsonResponse({ detail: options.deleteDetail }, options.deleteStatus);
      }
      return jsonResponse(null, 204);
    }
    if (url === "/api/instances") return jsonResponse({ instances: [] });
    if (url !== "/api/settings") throw new Error(`unstubbed request: ${url}`);
    if (init?.method !== "PUT") return jsonResponse(stored);
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
    { route: "/settings/data" },
  );
}

function hits(calls: FetchCall[], url: string): FetchCall[] {
  return calls.filter((call) => call.url === url);
}

function toastMessages(): string[] {
  return renderHook(() => useToasts()).result.current.map((item) => item.message);
}

/** Open a typed-name dialog, type the word, press the confirm button. */
async function confirmWith(word: string, confirmLabel: string) {
  const dialog = await screen.findByRole("dialog");
  const confirm = within(dialog).getByRole("button", { name: confirmLabel });
  expect(confirm).toBeDisabled();
  await userEvent.type(within(dialog).getByLabelText("Type to confirm"), word);
  expect(confirm).toBeEnabled();
  await userEvent.click(confirm);
}

afterEach(() => {
  resetToasts();
  vi.unstubAllGlobals();
});

describe("Settings > Data", () => {
  it("opens the data folder, with the home path only in the button's tooltip", async () => {
    const { calls } = server();
    mount();
    const button = await screen.findByRole("button", { name: "Open data folder" });
    await waitFor(() => {
      expect(screen.getByTitle("C:/data/brawlfarm")).toBeInTheDocument();
    });
    // In the tooltip and nowhere else: a path with a user name in it must not be in the
    // page's text, where a screenshot would catch it.
    expect(screen.queryByText("C:/data/brawlfarm")).not.toBeInTheDocument();
    expect(screen.getByTitle("C:/data/brawlfarm")).toHaveAttribute("data-private");

    await userEvent.click(button);
    await waitFor(() => {
      expect(hits(calls, OPEN)).toHaveLength(1);
    });
    expect(hits(calls, OPEN)[0].init?.method).toBe("POST");
    expect(toastMessages()).toEqual([]);
  });

  it("toasts the 501 when brawlfarm is not running on Windows", async () => {
    server({ openStatus: 501, openDetail: "Only on Windows" });
    mount();
    await userEvent.click(await screen.findByRole("button", { name: "Open data folder" }));
    await waitFor(() => {
      expect(toastMessages()).toEqual(["Only on Windows"]);
    });
  });

  it("deletes one instance's folder once its name has been typed", async () => {
    const { calls } = server();
    mount();
    expect(await screen.findByText("Delete one instance's data")).toBeInTheDocument();
    expect(screen.getByText("instances/Pie64")).toBeInTheDocument();
    expect(screen.getByText("instances/Pie64_3")).toBeInTheDocument();

    const row = screen.getByText("instances/Pie64").closest("li");
    expect(row).not.toBeNull();
    await userEvent.click(within(row as HTMLElement).getByRole("button", { name: "Delete data" }));
    expect(await screen.findByText("Delete Pie64's data?")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Its folder instances/Pie64 and everything in it goes: status, farm plan, schedule, games.csv and past sessions. The instance stays in your fleet.",
      ),
    ).toBeInTheDocument();

    await confirmWith("Pie64", "Delete data");
    await waitFor(() => {
      expect(hits(calls, DELETE_DATA)).toHaveLength(1);
    });
    expect(hits(calls, DELETE_DATA)[0].init?.method).toBe("DELETE");
    // The instance is still in the fleet: only its folder went.
    expect(screen.getByText("instances/Pie64")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });

  it("puts the API's refusal inline in the row it belongs to", async () => {
    const { calls } = server({
      deleteStatus: 409,
      deleteDetail: "Stop Pie64 before deleting its data",
    });
    mount();
    const row = (await screen.findByText("instances/Pie64")).closest("li");
    await userEvent.click(within(row as HTMLElement).getByRole("button", { name: "Delete data" }));
    await confirmWith("Pie64", "Delete data");
    await waitFor(() => {
      expect(hits(calls, DELETE_DATA)).toHaveLength(1);
    });
    const failed = (await screen.findByText("Stop Pie64 before deleting its data")).closest("li");
    expect(failed).toBe(row);
    expect(toastMessages()).toEqual([]);
  });

  it("resets every other setting once the word has been typed", async () => {
    const { calls } = server();
    mount();
    expect(await screen.findByText("Reset all settings")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Your instances and their data folders stay. Every other setting goes back to its default.",
      ),
    ).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Reset" }));
    expect(await screen.findByText("Reset all settings?")).toBeInTheDocument();
    await confirmWith("reset", "Reset");
    await waitFor(() => {
      expect(hits(calls, RESET)).toHaveLength(1);
    });
    expect(hits(calls, RESET)[0].init?.method).toBe("POST");
    await waitFor(() => {
      expect(toastMessages()).toEqual(["Settings reset"]);
    });
    // The answer went into the cache, so the two instances are still listed: a reset keeps
    // them and their folders.
    expect(screen.getByText("instances/Pie64")).toBeInTheDocument();
    expect(screen.getByText("instances/Pie64_3")).toBeInTheDocument();
  });
});
