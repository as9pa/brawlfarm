/** Step 2: the table of what BlueStacks has, testing a row, adding a port by hand, and
 * what Continue writes. */
import { renderHook, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Setup } from "./Setup";
import type { AppSettings, ScanResponse } from "../api/types";
import { resetToasts, useToasts } from "../lib/toast";
import { makeSettings } from "../test/fixtures";
import { type FetchCall, jsonResponse, stubFetch } from "../test/http";
import { renderWithProviders } from "../test/renderWithProviders";

const SCAN = "/api/setup/scan";
const TEST = "/api/setup/test";

const TWO: ScanResponse = {
  adb_path: "adb.exe",
  adb_found: true,
  conf_found: true,
  instances: [
    {
      name: "Pie64",
      display_name: "Nougat 64",
      adb_port: 5555,
      width: 1600,
      height: 900,
      dpi: 240,
      online: true,
    },
    {
      name: "Pie64_3",
      display_name: "Nougat 64 3",
      adb_port: 5585,
      width: null,
      height: null,
      dpi: null,
      online: false,
    },
  ],
};

const NONE: ScanResponse = {
  adb_path: "adb.exe",
  adb_found: true,
  conf_found: false,
  instances: [],
};

/** A settings document that lands the wizard on step 2: an adb path, and no fleet yet. */
function server(options: { scan?: ScanResponse; test?: { ok: boolean; detail: string } } = {}) {
  let stored = makeSettings({ instances: [] });
  const { calls } = stubFetch((url, init) => {
    if (url === SCAN) return jsonResponse(options.scan ?? TWO);
    if (url === TEST) {
      return jsonResponse(options.test ?? { ok: true, detail: "127.0.0.1:5555 answered" });
    }
    // Continue lands on step 3, which checks every instance it was handed.
    if (url === "/api/setup/display-check") {
      return jsonResponse({
        ok: true,
        width: 1600,
        height: 900,
        dpi: 240,
        detail: "1600x900 at 240 dpi",
        hint: "",
        expected: { width: 1600, height: 900, dpi: 240 },
      });
    }
    if (url !== "/api/settings") throw new Error(`unstubbed request: ${url}`);
    if (init?.method !== "PUT") return jsonResponse(stored);
    stored = JSON.parse(String(init.body)) as AppSettings;
    return jsonResponse(stored);
  });
  return { calls, current: () => stored };
}

function bodies(calls: FetchCall[], url: string): unknown[] {
  return calls
    .filter((call) => call.url === url)
    .map((call) => JSON.parse(String(call.init?.body)) as unknown);
}

function puts(calls: FetchCall[]): AppSettings[] {
  return calls
    .filter((call) => call.url === "/api/settings" && call.init?.method === "PUT")
    .map((call) => JSON.parse(String(call.init?.body)) as AppSettings);
}

function toastMessages(): string[] {
  return renderHook(() => useToasts()).result.current.map((item) => item.message);
}

/** The <tr> an instance sits in, found by its checkbox: a hand-added row is named after
 * its port, so its name appears in two cells and getByText would be ambiguous. */
function row(name: string): HTMLElement {
  const cell = screen.getByRole("checkbox", { name }).closest("tr");
  if (cell === null) throw new Error(`no row for ${name}`);
  return cell;
}

afterEach(() => {
  resetToasts();
  vi.unstubAllGlobals();
});

describe("Setup step 2: Instances", () => {
  it("lists what the scan found, with its columns and the status it starts from", async () => {
    server();
    renderWithProviders(<Setup />, { route: "/setup" });
    // By heading, because the step rail beside it carries the same word as a button.
    expect(await screen.findByRole("heading", { name: "Instances" })).toBeInTheDocument();
    expect(
      screen.getByText("Pick the BlueStacks instances brawlfarm should farm."),
    ).toBeInTheDocument();
    expect(await screen.findByText("Pie64")).toBeInTheDocument();

    const headers = screen.getAllByRole("columnheader").map((cell) => cell.textContent);
    expect(headers).toEqual(["select", "Name", "Display name", "ADB port", "Status", "test"]);
    expect(within(row("Pie64")).getByText("Nougat 64")).toBeInTheDocument();
    expect(within(row("Pie64")).getByText("5555")).toBeInTheDocument();
    // The scan said this one answers, so it starts at Answers; the other was not probed
    // by the scan and has not been tested here either.
    expect(within(row("Pie64")).getByText("Answers")).toBeInTheDocument();
    expect(within(row("Pie64_3")).getByText("Not tested")).toBeInTheDocument();
    expect(
      screen.getByText("Enable ADB in BlueStacks: Settings, Advanced, Android Debug Bridge."),
    ).toBeInTheDocument();
    // No tag column here: tags are asked on step 4.
    expect(screen.queryByText("Player tag")).not.toBeInTheDocument();
  });

  it("tests one row and says what happened, with that row's own port", async () => {
    const { calls } = server({ test: { ok: false, detail: "127.0.0.1:5585: no answer" } });
    renderWithProviders(<Setup />, { route: "/setup" });
    expect(await screen.findByText("Pie64_3")).toBeInTheDocument();

    await userEvent.click(within(row("Pie64_3")).getByRole("button", { name: "Test" }));
    await waitFor(() => {
      expect(bodies(calls, TEST)).toEqual([{ adb_port: 5585 }]);
    });
    expect(await within(row("Pie64_3")).findByText("No answer")).toBeInTheDocument();
    expect(
      within(row("Pie64_3")).getByText("No answer on 5585. Is the instance running?"),
    ).toBeInTheDocument();
    // The other row is untouched by its neighbour's probe.
    expect(within(row("Pie64")).getByText("Answers")).toBeInTheDocument();
  });

  it("adds a port by hand and lets it be picked", async () => {
    const { calls } = server({ scan: NONE });
    renderWithProviders(<Setup />, { route: "/setup" });
    expect(
      await screen.findByText(
        "No instances found. Start a BlueStacks instance, enable ADB, then Scan again.",
      ),
    ).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Add a port" }));
    await userEvent.type(screen.getByLabelText("ADB port"), "5605");
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    expect(await screen.findByRole("checkbox", { name: "5605" })).toBeInTheDocument();
    expect(within(row("5605")).getByText("Not tested")).toBeInTheDocument();

    await userEvent.click(within(row("5605")).getByRole("checkbox"));
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    // Named after the port, which is the only thing known about it.
    expect(puts(calls)[0].instances).toEqual([{ name: "5605", adb_port: 5605, player_tag: "" }]);
  });

  it("keeps Continue shut until a row is ticked, then writes the ticked rows", async () => {
    const { calls, current } = server();
    renderWithProviders(<Setup />, { route: "/setup" });
    expect(await screen.findByText("Pie64")).toBeInTheDocument();
    const forward = screen.getByRole("button", { name: "Continue" });
    expect(forward).toBeDisabled();
    expect(forward).toHaveAttribute("title", "Select at least one instance");

    await userEvent.click(within(row("Pie64")).getByRole("checkbox"));
    await userEvent.click(within(row("Pie64_3")).getByRole("checkbox"));
    expect(forward).toBeEnabled();
    await userEvent.click(forward);
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    expect(puts(calls)[0].instances).toEqual([
      { name: "Pie64", adb_port: 5555, player_tag: "" },
      { name: "Pie64_3", adb_port: 5585, player_tag: "" },
    ]);
    expect(current().instances).toHaveLength(2);
    await waitFor(() => {
      expect(toastMessages()).toEqual(["Saved to config.toml"]);
    });
    // And it moved on: step 3 is on screen.
    expect(await screen.findByRole("heading", { name: "Display" })).toBeInTheDocument();
  });

  it("re-scans on demand and goes back a step", async () => {
    const { calls } = server();
    renderWithProviders(<Setup />, { route: "/setup" });
    expect(await screen.findByText("Pie64")).toBeInTheDocument();
    expect(calls.filter((call) => call.url === SCAN)).toHaveLength(1);

    await userEvent.click(screen.getByRole("button", { name: "Scan again" }));
    await waitFor(() => {
      expect(calls.filter((call) => call.url === SCAN)).toHaveLength(2);
    });

    await userEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(
      await screen.findByText("brawlfarm talks to BlueStacks through adb."),
    ).toBeInTheDocument();
  });
});
