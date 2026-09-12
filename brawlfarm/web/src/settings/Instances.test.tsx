/** Settings > Instances: the fleet as config.toml holds it, joined with the supervisor's
 * live view, edited in place, and refusing where the reader can see it. */
import { act, fireEvent, renderHook, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Settings } from "./Settings";
import type { AppSettings, ScanResponse } from "../api/types";
import { resetToasts, useToasts } from "../lib/toast";
import { makeInstance, makeSettings } from "../test/fixtures";
import { type FetchCall, jsonResponse, stubFetch } from "../test/http";
import { renderWithProviders } from "../test/renderWithProviders";

const FLEET = makeSettings({
  instances: [
    { name: "Pie64", adb_port: 5555, player_tag: "#2P0YLQ9" },
    { name: "Pie64_1", adb_port: 5565, player_tag: "" },
    { name: "Pie64_3", adb_port: 5585, player_tag: "" },
  ],
});

const NO_SCAN: ScanResponse = {
  adb_path: "C:/adb.exe",
  adb_found: true,
  conf_found: true,
  instances: [],
};

/** The settings route with a memory, the instances list, and the setup scan. Pie64_3 has no
 * view on purpose: the supervisor has not derived one for it yet. */
function server(
  options: { doc?: AppSettings; putStatus?: number; putDetail?: string; scan?: ScanResponse } = {},
) {
  let stored = options.doc ?? FLEET;
  const { calls } = stubFetch((url, init) => {
    if (url === "/api/instances") {
      return jsonResponse({
        instances: [
          makeInstance({ name: "Pie64", state: "farming" }),
          makeInstance({ name: "Pie64_1", adb_port: 5565, state: "offline", player_tag: "" }),
        ],
      });
    }
    if (url === "/api/setup/scan") return jsonResponse(options.scan ?? NO_SCAN);
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
    { route: "/settings/instances" },
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

/** The data rows, header excluded. */
async function rows(): Promise<HTMLElement[]> {
  await screen.findByRole("row", { name: /instances\/Pie64_1/ });
  return screen.getAllByRole("row").slice(1);
}

afterEach(() => {
  resetToasts();
  vi.unstubAllGlobals();
});

describe("Settings > Instances", () => {
  it("shows every instance with its port, its tag, its folder and its status", async () => {
    server();
    mount();
    const [pie64, pie64_1, pie64_3] = await rows();

    const cells = within(pie64_1).getAllByRole("cell");
    expect(cells[0]).toHaveTextContent("Pie64_1");
    expect(cells[1]).toHaveTextContent("5565");
    // Relative to the home folder, never an absolute path: that path names a user.
    expect(cells[3]).toHaveTextContent("instances/Pie64_1");
    expect(within(pie64_1).getByText("Offline")).toBeInTheDocument();
    expect(within(pie64).getByText("Farming")).toBeInTheDocument();
    // The supervisor has no view for Pie64_3 yet, and an invented state would be a lie.
    expect(within(pie64_3).getByText("No status yet")).toBeInTheDocument();

    const tag = within(pie64).getByDisplayValue("#2P0YLQ9");
    expect(tag).toHaveAttribute("id", "instance-tag-Pie64");
    // The screenshot pass blurs it before the shot.
    expect(within(pie64).getAllByRole("cell")[2].querySelector("[data-private]")).not.toBeNull();
  });

  it("says what to do when there are no instances yet", async () => {
    server({ doc: makeSettings({ instances: [] }) });
    mount();
    expect(
      await screen.findByText("No instances yet. Add one or scan for BlueStacks."),
    ).toBeInTheDocument();
  });

  it("edits a row in place and saves all three fields", async () => {
    const { calls, current } = server();
    mount();
    const [, pie64_1] = await rows();
    await userEvent.click(within(pie64_1).getByRole("button", { name: "Edit" }));

    const form = screen.getAllByRole("row")[2];
    await userEvent.clear(within(form).getByLabelText("ADB port"));
    await userEvent.type(within(form).getByLabelText("ADB port"), "5575");
    await userEvent.type(within(form).getByLabelText("Player tag"), "2P0YLQ9");
    await userEvent.click(within(form).getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    expect(puts(calls)[0].instances[1]).toEqual({
      name: "Pie64_1",
      adb_port: 5575,
      player_tag: "2P0YLQ9", // the model puts the # back and upper-cases it
    });
    expect(current().instances[1].adb_port).toBe(5575);
    expect(toastMessages()).toEqual(["Settings saved"]);
    await waitFor(() => {
      expect(screen.queryByRole("button", { name: "Save" })).not.toBeInTheDocument();
    });
  });

  it("adds an instance through the same form, as a new last row", async () => {
    const { calls } = server();
    mount();
    await rows();
    await userEvent.click(screen.getByRole("button", { name: "Add instance" }));

    const form = screen.getAllByRole("row")[4];
    await userEvent.type(within(form).getByLabelText("Name"), "Pie64_5");
    await userEvent.type(within(form).getByLabelText("ADB port"), "5595");
    await userEvent.click(within(form).getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    expect(puts(calls)[0].instances).toHaveLength(4);
    expect(puts(calls)[0].instances[3]).toEqual({
      name: "Pie64_5",
      adb_port: 5595,
      player_tag: "",
    });
  });

  it("removes an instance only once its name is typed", async () => {
    const { calls } = server();
    mount();
    const [, , pie64_3] = await rows();
    await userEvent.click(within(pie64_3).getByRole("button", { name: "Remove" }));

    const dialog = screen.getByRole("dialog", { name: "Remove Pie64_3?" });
    expect(
      within(dialog).getByText("Its data folder stays on disk. Type the name to confirm."),
    ).toBeInTheDocument();
    const confirm = within(dialog).getByRole("button", { name: "Remove" });
    expect(confirm).toBeDisabled();
    await userEvent.type(within(dialog).getByLabelText("Type to confirm"), "Pie64_3");
    await userEvent.click(confirm);

    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    expect(puts(calls)[0].instances.map((inst) => inst.name)).toEqual(["Pie64", "Pie64_1"]);
    expect(toastMessages()).toEqual(["Settings saved"]);
  });

  it("shows the API's refusal in the row it names", async () => {
    server({ putStatus: 409, putDetail: "Stop Pie64_3 before removing it" });
    mount();
    const [, , pie64_3] = await rows();
    await userEvent.click(within(pie64_3).getByRole("button", { name: "Remove" }));
    const dialog = screen.getByRole("dialog", { name: "Remove Pie64_3?" });
    await userEvent.type(within(dialog).getByLabelText("Type to confirm"), "Pie64_3");
    await userEvent.click(within(dialog).getByRole("button", { name: "Remove" }));

    // The API's own sentence, in the row, not a toast that scrolls away.
    expect(await screen.findByText("Stop Pie64_3 before removing it")).toBeInTheDocument();
    expect(
      within(screen.getAllByRole("row")[3]).getByText("Stop Pie64_3 before removing it"),
    ).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(toastMessages()).toEqual([]);
  });

  it("puts a bad tag's message under the tag field", async () => {
    server({
      putStatus: 422,
      putDetail:
        "instances.1.player_tag: player tag must be # followed by letters from 0289PYLQGRJCUV",
    });
    mount();
    const [, pie64_1] = await rows();
    await userEvent.click(within(pie64_1).getByRole("button", { name: "Edit" }));
    const form = screen.getAllByRole("row")[2];
    await userEvent.type(within(form).getByLabelText("Player tag"), "nope");
    await userEvent.click(within(form).getByRole("button", { name: "Save" }));

    expect(
      await screen.findByText(
        "player_tag: player tag must be # followed by letters from 0289PYLQGRJCUV",
      ),
    ).toBeInTheDocument();
    // A validation message is not a refusal: nothing goes in the row's 409 line.
    expect(toastMessages()).toEqual([]);
  });

  it("puts a bad port's message under the port box and leaves the row open", async () => {
    server({ putStatus: 422, putDetail: "instances.0.adb_port: Input should be a valid integer" });
    mount();
    const [pie64] = await rows();
    await userEvent.click(within(pie64).getByRole("button", { name: "Edit" }));
    const form = screen.getAllByRole("row")[1];
    await userEvent.clear(within(form).getByLabelText("ADB port"));
    await userEvent.click(within(form).getByRole("button", { name: "Save" }));

    const message = await screen.findByText("adb_port: Input should be a valid integer");
    expect(within(screen.getAllByRole("row")[1]).getAllByRole("cell")[1]).toContainElement(message);
    // The form stays open, because the value the API refused is the one being fixed.
    expect(screen.getByRole("button", { name: "Save" })).toBeInTheDocument();
    expect(toastMessages()).toEqual([]);
  });

  it("puts a bad name's message under the name box of the row being added", async () => {
    server({ putStatus: 422, putDetail: "instances.3.name: instance name must not be blank" });
    mount();
    await rows();
    await userEvent.click(screen.getByRole("button", { name: "Add instance" }));

    const form = screen.getAllByRole("row")[4];
    await userEvent.type(within(form).getByLabelText("ADB port"), "5595");
    await userEvent.click(within(form).getByRole("button", { name: "Save" }));

    // The new row is saved onto the end, so instances.3 is the row the reader is looking at.
    const message = await screen.findByText("name: instance name must not be blank");
    expect(within(screen.getAllByRole("row")[4]).getAllByRole("cell")[0]).toContainElement(message);
    expect(toastMessages()).toEqual([]);
  });

  it("adds what a scan found, and says so when it found nothing new", async () => {
    const first = server({
      scan: {
        ...NO_SCAN,
        instances: [
          // Already configured, so it is not offered again.
          {
            name: "Pie64",
            display_name: "Pie64",
            adb_port: 5555,
            width: 1600,
            height: 900,
            dpi: 240,
            online: true,
          },
          {
            name: "Pie64_5",
            display_name: "Pie 5",
            adb_port: 5595,
            width: 1600,
            height: 900,
            dpi: 240,
            online: true,
          },
        ],
      },
    });
    const view = mount();
    await rows();
    await userEvent.click(screen.getByRole("button", { name: "Scan again" }));
    await waitFor(() => {
      expect(puts(first.calls)).toHaveLength(1);
    });
    expect(puts(first.calls)[0].instances.map((inst) => inst.name)).toEqual([
      "Pie64",
      "Pie64_1",
      "Pie64_3",
      "Pie64_5",
    ]);
    expect(toastMessages()).toEqual(["Added 1 instance"]);
    view.unmount();
    resetToasts();
    vi.unstubAllGlobals();

    const second = server();
    mount();
    await rows();
    await userEvent.click(screen.getByRole("button", { name: "Scan again" }));
    await waitFor(() => {
      expect(toastMessages()).toEqual(["No new instances found"]);
    });
    expect(puts(second.calls)).toHaveLength(0);
  });
});

/** One keystroke on a controlled field. fireEvent rather than userEvent: userEvent awaits
 * testing-library's async wrapper, which drains the queue with a real setTimeout that fake
 * timers never run. */
function keystroke(field: HTMLElement, value: string): void {
  fireEvent.change(field, { target: { value } });
}

/** Move the fake clock on with React's own work inside act, so a debounce that fires and the
 * PUT it sends both settle before the next assertion. */
async function tick(ms: number): Promise<void> {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

describe("Settings > Instances tag debounce", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    resetToasts();
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("saves the tag 500 ms after the last keystroke, and at once on blur", async () => {
    const { calls } = server();
    mount();
    await tick(0); // the settings and instances fetches settle on the fake clock

    const tag = screen.getByLabelText("Player tag for Pie64_1");
    keystroke(tag, "2P0");
    keystroke(tag, "2P0Y");
    keystroke(tag, "2P0YLQ9");
    expect(puts(calls)).toHaveLength(0); // still typing
    await tick(499);
    expect(puts(calls)).toHaveLength(0);
    await tick(1);
    expect(puts(calls)).toHaveLength(1);
    expect(puts(calls)[0].instances[1].player_tag).toBe("2P0YLQ9");

    keystroke(tag, "2P0YLQ90");
    fireEvent.blur(tag);
    await tick(0);
    // Leaving the box does not wait out the rest of the debounce.
    expect(puts(calls)).toHaveLength(2);
    expect(puts(calls)[1].instances[1].player_tag).toBe("2P0YLQ90");
  });
});
