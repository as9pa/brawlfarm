/** Settings > Connection: the adb path with the chip from one scan, and the masked token. */
import { fireEvent, renderHook, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Settings } from "./Settings";
import type { AppSettings, ConnectionCheck, ScanResponse } from "../api/types";
import { resetToasts, useToasts } from "../lib/toast";
import { makeConnection, makeSettings } from "../test/fixtures";
import { type FetchCall, jsonResponse, stubFetch } from "../test/http";
import { renderWithProviders } from "../test/renderWithProviders";

const FOUND: ScanResponse = {
  adb_path: "C:\\Program Files\\BlueStacks_nxt\\HD-Adb.exe",
  adb_found: true,
  conf_found: true,
  instances: [],
};

const MISSING: ScanResponse = {
  adb_path: null,
  adb_found: false,
  conf_found: false,
  instances: [],
};

/** A placeholder path long enough to run past the box, with no user name in it. */
const LONG_PATH =
  "D:\\programs\\emulators\\bluestacks\\portable-install\\engine\\bin\\HD-Adb.exe";

function server(
  options: {
    scan?: ScanResponse;
    putStatus?: number;
    putDetail?: string;
    doc?: AppSettings;
    check?: ConnectionCheck;
  } = {},
) {
  let stored = options.doc ?? makeSettings();
  const { calls } = stubFetch((url, init) => {
    if (url === "/api/setup/scan") return jsonResponse(options.scan ?? FOUND);
    if (url === "/api/connection/check") return jsonResponse(options.check ?? makeConnection());
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

  it("says Not found when the scan came back without adb, and what to do next", async () => {
    server({ scan: MISSING });
    mount();
    expect(await screen.findByText("Not found")).toBeInTheDocument();
    expect(screen.queryByText("Found")).not.toBeInTheDocument();
    expect(
      screen.getByText("Install BlueStacks, or type the path to HD-Adb.exe above."),
    ).toBeInTheDocument();
  });

  it("shows the whole adb path, wrapped rather than clipped", async () => {
    server({ doc: makeSettings({ connection: { adb_path: LONG_PATH, brawl_api_token: "" } }) });
    mount();
    const box = await screen.findByLabelText("ADB path");
    // The whole path is in the DOM, the box fills its row, and it stays mono and wraps.
    await waitFor(() => {
      expect(box).toHaveValue(LONG_PATH);
    });
    expect(box).toHaveClass("w-full", "font-mono");
    expect(box.closest("[class*='break-all']")).not.toBeNull();
  });

  it("chips the scan while it is still running", async () => {
    server();
    mount();
    // The scan shells out to adb and can take seconds, so the first paint says so.
    expect(screen.getByText("Scanning…")).toBeInTheDocument();
    expect(screen.getByText("Asking adb for devices")).toBeInTheDocument();
    expect(await screen.findByText("Found")).toBeInTheDocument();
    expect(screen.queryByText("Scanning…")).not.toBeInTheDocument();
  });

  it("checks the saved token, and waits for a save before it offers to", async () => {
    const { calls } = server({ check: makeConnection({ status: "rejected" }) });
    mount();
    const box = await screen.findByLabelText("ADB path");
    expect(
      screen.getByText("Uses the saved token and player tag."),
    ).toBeInTheDocument();

    // A form with something typed into it has nothing saved to check yet.
    fireEvent.change(box, { target: { value: "D:/portable/adb.exe" } });
    const check = screen.getByRole("button", { name: "Check connection" });
    expect(check).toBeDisabled();
    expect(check).toHaveAttribute("title", "Save first");

    fireEvent.blur(box);
    await waitFor(() => {
      expect(check).toBeEnabled();
    });

    await userEvent.click(check);
    await waitFor(() => {
      expect(calls.filter((call) => call.url === "/api/connection/check")).toHaveLength(1);
    });
    // The route reads what is on disk, so the answer is about the saved token.
    expect(
      await screen.findByText(/The Brawl Stars API rejected the token/),
    ).toBeInTheDocument();
    expect(toastMessages()).toEqual(["Settings saved"]);
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
