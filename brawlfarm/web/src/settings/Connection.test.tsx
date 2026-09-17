/** Settings > Connection: the adb path with the chip from one scan, and the masked token. */
import { fireEvent, renderHook, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Settings } from "./Settings";
import type { AppSettings, ScanResponse } from "../api/types";
import { resetToasts, useToasts } from "../lib/toast";
import { makeSettings } from "../test/fixtures";
import { type FetchCall, jsonResponse, stubFetch } from "../test/http";
import { renderWithProviders } from "../test/renderWithProviders";

const FOUND: ScanResponse = {
  adb_path: "C:\\Program Files\\BlueStacks_nxt\\HD-Adb.exe",
  adb_found: true,
  conf_found: true,
  instances: [],
};

function server(
  options: { scan?: ScanResponse; putStatus?: number; putDetail?: string } = {},
) {
  let stored = makeSettings();
  const { calls } = stubFetch((url, init) => {
    if (url === "/api/setup/scan") return jsonResponse(options.scan ?? FOUND);
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
    { route: "/settings/connection" },
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

describe("Settings > Connection", () => {
  it("chips what one scan found and saves the adb path on blur", async () => {
    const { calls, current } = server();
    mount();
    const box = await screen.findByLabelText("ADB path");
    expect(await screen.findByText("Found")).toBeInTheDocument();
    expect(
      screen.getByText("brawlfarm needs HD-Adb.exe from the BlueStacks folder."),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Run setup again" })).toHaveAttribute(
      "href",
      "/setup",
    );
    expect(screen.getByText("Applies the next time an instance starts.")).toBeInTheDocument();

    fireEvent.change(box, { target: { value: "D:/portable/adb.exe" } });
    fireEvent.blur(box);
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    expect(puts(calls)[0].connection.adb_path).toBe("D:/portable/adb.exe");
    expect(current().connection.adb_path).toBe("D:/portable/adb.exe");
    expect(toastMessages()).toEqual(["Settings saved"]);
    // The scan runs once when the section mounts, never again per keystroke: it shells out
    // to adb and can take seconds.
    expect(calls.filter((call) => call.url === "/api/setup/scan")).toHaveLength(1);
  });

  it("says Not found when the scan came back without adb", async () => {
    server({ scan: { adb_path: null, adb_found: false, conf_found: false, instances: [] } });
    mount();
    expect(await screen.findByText("Not found")).toBeInTheDocument();
    expect(screen.queryByText("Found")).not.toBeInTheDocument();
  });

  it("puts the API's message under the ADB path row", async () => {
    const { calls } = server({ putStatus: 422, putDetail: "connection.adb_path: file not found" });
    mount();
    const box = await screen.findByLabelText("ADB path");
    fireEvent.change(box, { target: { value: "D:/nope.exe" } });
    fireEvent.blur(box);
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    expect(await screen.findByText("adb_path: file not found")).toBeInTheDocument();
    // The box keeps what is being fixed rather than snapping back under the reader.
    expect(box).toHaveValue("D:/nope.exe");
    expect(toastMessages()).toEqual([]);
  });

  it("masks the token, offers Show, and saves it on blur", async () => {
    const { calls } = server();
    mount();
    const token = await screen.findByLabelText("Brawl Stars API token");
    expect(token).toHaveAttribute("type", "password");
    expect(token).toHaveAttribute("data-private");
    expect(
      screen.getByText(
        "Create a key at developer.brawlstars.com and allow this machine's IP address.",
      ),
    ).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Show" }));
    expect(token).toHaveAttribute("type", "text");

    fireEvent.change(token, { target: { value: "a-token-that-is-not-real" } });
    fireEvent.blur(token);
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    expect(puts(calls)[0].connection.brawl_api_token).toBe("a-token-that-is-not-real");
  });
});
