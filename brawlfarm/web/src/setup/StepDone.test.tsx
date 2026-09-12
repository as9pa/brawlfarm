/** Step 5: what setup did, the one start it offers, and the way out. */
import { renderHook, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Setup } from "./Setup";
import type { AppSettings } from "../api/types";
import { resetToasts, useToasts } from "../lib/toast";
import { makeSettings } from "../test/fixtures";
import { type FetchCall, jsonResponse, stubFetch } from "../test/http";
import { renderWithProviders } from "../test/renderWithProviders";

const CHECK = "/api/setup/display-check";
const START = "/api/instances/Pie64/start";

const CORRECT = {
  ok: true,
  width: 1600,
  height: 900,
  dpi: 240,
  detail: "1600x900 at 240 dpi",
  hint: "",
  expected: { width: 1600, height: 900, dpi: 240 },
};

function server(
  settings: AppSettings,
  options: { startStatus?: number; startDetail?: string } = {},
) {
  const { calls } = stubFetch((url) => {
    if (url === CHECK) return jsonResponse(CORRECT);
    if (url === START) {
      if (options.startStatus !== undefined) {
        return jsonResponse({ detail: options.startDetail }, options.startStatus);
      }
      return jsonResponse({ ok: true }, 202);
    }
    if (url !== "/api/settings") throw new Error(`unstubbed request: ${url}`);
    return jsonResponse(settings);
  });
  return { calls };
}

function fleet(): AppSettings {
  const settings = makeSettings({
    instances: [
      { name: "Pie64", adb_port: 5555, player_tag: "#2P0YLQ9" },
      { name: "Pie64_3", adb_port: 5585, player_tag: "" },
    ],
  });
  settings.connection.adb_path = "adb.exe";
  settings.connection.brawl_api_token = "a-token-that-is-not-real";
  return settings;
}

function mount() {
  return renderWithProviders(
    <Routes>
      <Route path="/setup" element={<Setup />} />
      <Route path="/" element={<p>Fleet screen</p>} />
    </Routes>,
    { route: "/setup" },
  );
}

/** Land on step 3, then two Continues to step 5. */
async function walkToDone() {
  const forward = await screen.findByRole("button", { name: "Continue" });
  await waitFor(() => {
    expect(forward).toBeEnabled();
  });
  await userEvent.click(forward);
  expect(await screen.findByText("Stats (optional)")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Continue" }));
  expect(await screen.findByText("Setup complete.")).toBeInTheDocument();
}

function starts(calls: FetchCall[]): FetchCall[] {
  return calls.filter((call) => call.url === START);
}

function toastMessages(): string[] {
  return renderHook(() => useToasts()).result.current.map((item) => item.message);
}

afterEach(() => {
  resetToasts();
  vi.unstubAllGlobals();
});

describe("Setup step 5: Done", () => {
  it("summarises what setup did", async () => {
    server(fleet());
    mount();
    await walkToDone();

    const summary = screen.getByRole("list", { name: "Setup summary" });
    expect(within(summary).getAllByRole("listitem").map((item) => item.textContent)).toEqual([
      "Instances: 2 Pie64, Pie64_3",
      "adb: adb.exe",
      "Token: set",
      "Player tags: 1 of 2 set",
    ]);
    expect(
      screen.getByText(
        "Each step already saved to config.toml, so you can close this and come back.",
      ),
    ).toBeInTheDocument();
    // The token is summarised, never shown.
    expect(screen.queryByText(/a-token-that-is-not-real/)).not.toBeInTheDocument();
  });

  it("says skipped and none when neither was given", async () => {
    const bare = fleet();
    bare.connection.brawl_api_token = "";
    bare.instances = [
      { name: "Pie64", adb_port: 5555, player_tag: "" },
      { name: "Pie64_3", adb_port: 5585, player_tag: "" },
    ];
    server(bare);
    mount();
    await walkToDone();

    const summary = screen.getByRole("list", { name: "Setup summary" });
    expect(within(summary).getAllByRole("listitem").map((item) => item.textContent)).toEqual([
      "Instances: 2 Pie64, Pie64_3",
      "adb: adb.exe",
      "Token: skipped",
      "Player tags: none",
    ]);
  });

  it("starts the first instance and opens the fleet", async () => {
    const { calls } = server(fleet());
    mount();
    await walkToDone();

    const toggle = screen.getByRole("switch", { name: "Start Pie64 now" });
    expect(toggle).toHaveAttribute("aria-checked", "true");
    await userEvent.click(screen.getByRole("button", { name: "Open Fleet" }));
    await waitFor(() => {
      expect(starts(calls)).toHaveLength(1);
    });
    expect(starts(calls)[0].init?.method).toBe("POST");
    expect(await screen.findByText("Fleet screen")).toBeInTheDocument();
  });

  it("opens the fleet without starting when the switch is off", async () => {
    const { calls } = server(fleet());
    mount();
    await walkToDone();

    await userEvent.click(screen.getByRole("switch", { name: "Start Pie64 now" }));
    await userEvent.click(screen.getByRole("button", { name: "Open Fleet" }));
    expect(await screen.findByText("Fleet screen")).toBeInTheDocument();
    expect(starts(calls)).toHaveLength(0);
  });

  it("still opens the fleet when the start was refused, and says why", async () => {
    const { calls } = server(fleet(), {
      startStatus: 409,
      startDetail: "Pie64 is already running",
    });
    mount();
    await walkToDone();

    await userEvent.click(screen.getByRole("button", { name: "Open Fleet" }));
    await waitFor(() => {
      expect(starts(calls)).toHaveLength(1);
    });
    expect(await screen.findByText("Fleet screen")).toBeInTheDocument();
    await waitFor(() => {
      expect(toastMessages()).toEqual(["Pie64 is already running"]);
    });
  });
});
