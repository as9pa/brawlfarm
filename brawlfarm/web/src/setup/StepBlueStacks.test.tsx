/** Step 1 end to end, through the real frame: the scan on entry, what it says while it
 * runs, the path it writes, and the field it falls back to. */
import { renderHook, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Setup } from "./Setup";
import type { AppSettings, ScanResponse } from "../api/types";
import { resetToasts, useToasts } from "../lib/toast";
import { makeSettings } from "../test/fixtures";
import { type FetchCall, jsonResponse, stubFetch } from "../test/http";
import { renderWithProviders } from "../test/renderWithProviders";

const ADB = "C:\\Program Files\\BlueStacks_nxt\\HD-Adb.exe";
const SCAN = "/api/setup/scan";

const FOUND: ScanResponse = {
  adb_path: ADB,
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

/** A settings route with a memory and a scan route the test drives by hand, so the
 * "Scanning" state can be looked at before the answer lands. */
function server(scans: (ScanResponse | "hold")[]) {
  const blank = makeSettings({ instances: [] });
  blank.connection.adb_path = "";
  let stored = blank;
  let held: ((response: Response) => void) | null = null;
  let at = 0;
  const { calls } = stubFetch((url, init) => {
    if (url === SCAN) {
      const answer = scans[Math.min(at, scans.length - 1)];
      at += 1;
      if (answer === "hold") {
        return new Promise<Response>((resolve) => {
          held = resolve;
        });
      }
      return jsonResponse(answer);
    }
    if (url !== "/api/settings") throw new Error(`unstubbed request: ${url}`);
    if (init?.method !== "PUT") return jsonResponse(stored);
    stored = JSON.parse(String(init.body)) as AppSettings;
    return jsonResponse(stored);
  });
  return {
    calls,
    current: () => stored,
    release: (answer: ScanResponse) => held?.(jsonResponse(answer)),
  };
}

function scanBodies(calls: FetchCall[]): unknown[] {
  return calls
    .filter((call) => call.url === SCAN)
    .map((call) => JSON.parse(String(call.init?.body)) as unknown);
}

function toastMessages(): string[] {
  return renderHook(() => useToasts()).result.current.map((item) => item.message);
}

afterEach(() => {
  resetToasts();
  vi.unstubAllGlobals();
});

describe("Setup step 1: BlueStacks", () => {
  it("says what it is doing while the scan runs, then shows what it found", async () => {
    const { release } = server(["hold"]);
    renderWithProviders(<Setup />, { route: "/setup" });
    // By heading, because the step rail beside it carries the same word as a button.
    expect(await screen.findByRole("heading", { name: "BlueStacks" })).toBeInTheDocument();
    expect(screen.getByText("brawlfarm talks to BlueStacks through adb.")).toBeInTheDocument();
    expect(await screen.findByText("Scanning…")).toBeInTheDocument();
    expect(screen.getByText("Asking adb for devices")).toBeInTheDocument();

    release(FOUND);
    expect(await screen.findByText("Found")).toBeInTheDocument();
    expect(screen.getByText(ADB)).toBeInTheDocument();
    expect(screen.queryByText("Scanning…")).not.toBeInTheDocument();
  });

  it("writes the path it found to config.toml and opens Continue", async () => {
    const { calls, current } = server([FOUND]);
    renderWithProviders(<Setup />, { route: "/setup" });
    expect(await screen.findByText("Found")).toBeInTheDocument();
    await waitFor(() => {
      expect(current().connection.adb_path).toBe(ADB);
    });
    await waitFor(() => {
      expect(toastMessages()).toEqual(["Saved to config.toml"]);
    });
    expect(screen.getByRole("button", { name: "Continue" })).toBeEnabled();
    // The first scan is the configured one: no adb_path key until the reader types one.
    expect(scanBodies(calls)).toEqual([{}]);
  });

  it("keeps Continue shut while the path it found could not be saved", async () => {
    const blank = makeSettings({ instances: [] });
    blank.connection.adb_path = "";
    stubFetch((url, init) => {
      if (url === SCAN) return jsonResponse(FOUND);
      if (url !== "/api/settings") throw new Error(`unstubbed request: ${url}`);
      if (init?.method !== "PUT") return jsonResponse(blank);
      return jsonResponse({ detail: "config.toml is read only" }, 500);
    });
    renderWithProviders(<Setup />, { route: "/setup" });
    expect(await screen.findByText("config.toml is read only")).toBeInTheDocument();
    // Found, but not stored: walking on would carry a path the next step cannot read back.
    expect(screen.getByRole("button", { name: "Continue" })).toBeDisabled();
  });

  it("asks where BlueStacks is when no adb was found, and re-scans with what was typed", async () => {
    const { calls } = server([MISSING, FOUND]);
    renderWithProviders(<Setup />, { route: "/setup" });
    const box = await screen.findByLabelText("Where is BlueStacks installed");
    expect(box).toHaveAttribute("placeholder", ADB);
    expect(
      screen.getByText("brawlfarm needs HD-Adb.exe from the BlueStacks folder."),
    ).toBeInTheDocument();
    // Nothing has been typed yet, so the help line stands and no error blames a path.
    expect(screen.getByText("Press Enter or Check to test this path.")).toBeInTheDocument();
    expect(screen.queryByText("No HD-Adb.exe at that path.")).not.toBeInTheDocument();

    await userEvent.type(box, "D:\\portable\\adb.exe");
    await userEvent.click(screen.getByRole("button", { name: "Scan again" }));
    await waitFor(() => {
      expect(scanBodies(calls)).toHaveLength(2);
    });
    expect(scanBodies(calls)[1]).toEqual({ adb_path: "D:\\portable\\adb.exe" });
    expect(await screen.findByText("Found")).toBeInTheDocument();
  });

  it("checks the path that was typed on Enter, with no Scan again click", async () => {
    const { calls } = server([MISSING, FOUND]);
    renderWithProviders(<Setup />, { route: "/setup" });
    const box = await screen.findByLabelText("Where is BlueStacks installed");

    await userEvent.type(box, "D:\\portable\\adb.exe{Enter}");
    await waitFor(() => {
      expect(scanBodies(calls)).toHaveLength(2);
    });
    expect(scanBodies(calls)[1]).toEqual({ adb_path: "D:\\portable\\adb.exe" });
    expect(await screen.findByText("Found")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Continue" })).toBeEnabled();
  });

  it("blames the typed path when the check runs and finds nothing", async () => {
    const { calls } = server([MISSING, MISSING]);
    renderWithProviders(<Setup />, { route: "/setup" });
    const box = await screen.findByLabelText("Where is BlueStacks installed");

    await userEvent.type(box, "D:\\portable\\adb.exe");
    await userEvent.click(screen.getByRole("button", { name: "Check" }));
    await waitFor(() => {
      expect(scanBodies(calls)).toHaveLength(2);
    });
    expect(await screen.findByText("No HD-Adb.exe at that path.")).toBeInTheDocument();
    const forward = screen.getByRole("button", { name: "Continue" });
    expect(forward).toBeDisabled();
    expect(forward).toHaveAttribute("title", "Find HD-Adb.exe first");
  });

  it("says to check the path again when the check itself failed", async () => {
    const blank = makeSettings({ instances: [] });
    blank.connection.adb_path = "";
    stubFetch((url) => {
      if (url === SCAN) return jsonResponse({ detail: "adb did not answer" }, 500);
      if (url !== "/api/settings") throw new Error(`unstubbed request: ${url}`);
      return jsonResponse(blank);
    });
    renderWithProviders(<Setup />, { route: "/setup" });
    expect(await screen.findByText("adb did not answer")).toBeInTheDocument();
    const forward = screen.getByRole("button", { name: "Continue" });
    expect(forward).toBeDisabled();
    expect(forward).toHaveAttribute("title", "Check the path again");
    // A request that never answered has nothing to say about the path itself.
    expect(screen.queryByText("No HD-Adb.exe at that path.")).not.toBeInTheDocument();
  });

  it("keeps Continue shut, with the reason, until adb is found", async () => {
    server([MISSING]);
    renderWithProviders(<Setup />, { route: "/setup" });
    const forward = await screen.findByRole("button", { name: "Continue" });
    expect(forward).toBeDisabled();
    expect(forward).toHaveAttribute("title", "Find HD-Adb.exe first");
    expect(screen.queryByText("Found")).not.toBeInTheDocument();
    expect(toastMessages()).toEqual([]);
  });
});
