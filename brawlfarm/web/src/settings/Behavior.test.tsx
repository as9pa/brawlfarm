/** Settings > Behavior: six plain switches, the schedule new instances start with, seven
 * more behind Advanced that also say what off costs and whether they have been moved off
 * their default, and every one of them writing its own field. */
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

function server(
  options: { putStatus?: number; putDetail?: string; defaults?: AppSettings | null } = {},
) {
  let stored = makeSettings();
  const { calls } = stubFetch((url, init) => {
    if (url === "/api/settings/defaults") {
      // null stands for the defaults document that never arrives.
      if (options.defaults === null) return jsonResponse({ detail: "nope" }, 500);
      return jsonResponse(options.defaults ?? makeSettings());
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
    { route: "/settings/behavior" },
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

describe("Settings > Behavior", () => {
  it("shows the six rows with one plain sentence each, and writes the one that is flipped", async () => {
    const { calls, current } = server();
    mount();
    expect(
      await screen.findByRole("switch", { name: "Prefer brawlers that win" }),
    ).toBeInTheDocument();
    // The six behavior rows plus the schedule default; Advanced is still collapsed.
    expect(screen.getAllByRole("switch")).toHaveLength(7);
    for (const [name, sentence] of [
      ["Prefer brawlers that win", "Picks the brawler with the best win rate in the current step."],
      ["Skip far-off tiers", "Skips brawlers whose next tier is more than a session away."],
      ["Leave the gas early", "Moves away from the gas one ring sooner."],
      ["Hide in bushes", "Hides in bushes when the map allows."],
      ["Close the game on stop", "Closes Brawl Stars when the instance stops."],
      ["Do Not Disturb on start", "Turns on Do Not Disturb when the instance starts."],
    ]) {
      expect(screen.getByRole("switch", { name })).toBeInTheDocument();
      expect(screen.getByText(sentence)).toBeInTheDocument();
    }
    expect(screen.getByText("Applies the next time an instance starts.")).toBeInTheDocument();
    for (const gone of ["Win-rate aware", "Gas aware", "DND at start"]) {
      expect(screen.queryByRole("switch", { name: gone })).not.toBeInTheDocument();
    }

    await userEvent.click(screen.getByRole("switch", { name: "Leave the gas early" }));
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    expect(puts(calls)[0].behavior.gas_aware).toBe(false);
    // Only that one field moved: the whole document went, unchanged everywhere else.
    expect(puts(calls)[0].behavior.winrate_aware).toBe(true);
    expect(puts(calls)[0].advanced).toEqual(makeSettings().advanced);
    expect(current().behavior.gas_aware).toBe(false);
    // The frame names the section in its saved caption, so the save is silent here.
    expect(toastMessages()).toEqual([]);
  });

  it("turns the schedule new instances start with on and off", async () => {
    const { calls, current } = server();
    mount();
    expect(
      await screen.findByRole("switch", { name: "Schedule on by default" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Schedule")).toBeInTheDocument();
    expect(screen.getByText(/^Sessions run 30 minutes to 2 hours/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("switch", { name: "Schedule on by default" }));
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    expect(puts(calls)[0].scheduler.default_enabled).toBe(false);
    expect(current().scheduler.default_enabled).toBe(false);
  });

  it("keeps the seven advanced switches behind Show, and writes the advanced section", async () => {
    const { calls } = server();
    mount();
    expect(
      await screen.findByRole("switch", { name: "Prefer brawlers that win" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Advanced")).toBeInTheDocument();
    expect(screen.queryByRole("switch", { name: "Fast input" })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Show" }));
    expect(screen.getAllByRole("switch")).toHaveLength(14);
    for (const [name, help, off] of [
      [
        "Faster taps",
        "Send taps through the faster adb path.",
        "Off: taps go through the slower path.",
      ],
      [
        "Raw frames",
        "Read frames without re-encoding them.",
        "Off: frames are re-encoded before they are read.",
      ],
      ["Grayscale matching", "Match templates in grayscale.", "Off: templates match in color."],
      [
        "Match phase detection",
        "Work out the match phase from the screen.",
        "Off: the match phase is worked out from timing instead of the screen.",
      ],
      [
        "Use abilities",
        "Use the gadget and super buttons.",
        "Off: the gadget and super buttons are left alone.",
      ],
      [
        "Warn when the season changed the screens",
        "Warn when the screens stop matching what brawlfarm expects.",
        "Off: no warning when a season changes the screens.",
      ],
      [
        "Do Not Disturb off on stop",
        "Turn Do Not Disturb back off when the instance stops.",
        "Off: Do Not Disturb stays on after the instance stops.",
      ],
    ]) {
      expect(screen.getByRole("switch", { name })).toBeInTheDocument();
      expect(screen.getByText(help)).toBeInTheDocument();
      expect(screen.getByText(off)).toBeInTheDocument();
    }

    await userEvent.click(screen.getByRole("switch", { name: "Grayscale matching" }));
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    expect(puts(calls)[0].advanced.gray_match).toBe(false);

    await userEvent.click(screen.getByRole("button", { name: "Hide" }));
    expect(screen.queryByRole("switch", { name: "Grayscale matching" })).not.toBeInTheDocument();
  });

  it("says whether Advanced is open, and asks for the defaults once", async () => {
    const { calls } = server();
    mount();
    expect(
      await screen.findByRole("switch", { name: "Prefer brawlers that win" }),
    ).toBeInTheDocument();
    const show = screen.getByRole("button", { name: "Show" });
    expect(show).toHaveAttribute("aria-expanded", "false");
    expect(show).toHaveAttribute("aria-controls", "settings-advanced");

    await userEvent.click(show);
    const hide = screen.getByRole("button", { name: "Hide" });
    expect(hide).toHaveAttribute("aria-expanded", "true");
    expect(hide).toHaveAttribute("aria-controls", "settings-advanced");
    expect(document.getElementById("settings-advanced")).not.toBeNull();

    await userEvent.click(hide);
    await userEvent.click(screen.getByRole("button", { name: "Show" }));
    expect(calls.filter((call) => call.url === "/api/settings/defaults")).toHaveLength(1);
  });

  it("tags the advanced switches that are not at their default and puts them back", async () => {
    const defaults = makeSettings();
    defaults.advanced.gray_match = false;
    defaults.behavior.gas_aware = false; // a basic row that differs is still not tagged
    const { calls, current } = server({ defaults });
    mount();
    expect(
      await screen.findByRole("switch", { name: "Prefer brawlers that win" }),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Show" }));
    await waitFor(() => {
      expect(screen.getAllByText("Changed")).toHaveLength(1);
    });

    await userEvent.click(screen.getByRole("button", { name: "Reset to defaults" }));
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    expect(puts(calls)[0].advanced).toEqual(defaults.advanced);
    // Only the advanced section moved, whatever else the defaults document differs on.
    expect(puts(calls)[0].behavior).toEqual(makeSettings().behavior);
    expect(current().advanced.gray_match).toBe(false);
    // One note for the write, not the generic one stacked under this one.
    await vi.waitFor(() => {
      expect(toastMessages()).toEqual(["Advanced switches back to defaults"]);
    });

    const undo = renderHook(() => useToasts()).result.current.at(-1)?.undo;
    expect(undo).toBeDefined();
    // Awaited, so the undo's own write and anything it wanted to say have both happened.
    await undo?.();
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(2);
    });
    expect(puts(calls)[1].advanced).toEqual(makeSettings().advanced);
    expect(current().advanced.gray_match).toBe(true);
    // The undo is the same one write, so it raises no second note either.
    expect(toastMessages()).toEqual(["Advanced switches back to defaults"]);
  });

  it("offers no way back when advanced is already at the defaults", async () => {
    server();
    mount();
    expect(
      await screen.findByRole("switch", { name: "Prefer brawlers that win" }),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Show" }));
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Reset to defaults" })).toBeDisabled();
    });
    expect(screen.getByRole("button", { name: "Reset to defaults" })).toHaveAttribute(
      "title",
      "Already at the defaults",
    );
    expect(screen.queryByText("Changed")).not.toBeInTheDocument();
  });

  it("says nothing at all when the defaults document does not arrive", async () => {
    const { calls } = server({ defaults: null });
    mount();
    expect(
      await screen.findByRole("switch", { name: "Prefer brawlers that win" }),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Show" }));
    expect(screen.getByRole("switch", { name: "Faster taps" })).toBeInTheDocument();
    await waitFor(() => {
      expect(calls.some((call) => call.url === "/api/settings/defaults")).toBe(true);
    });
    expect(screen.queryByRole("button", { name: "Reset to defaults" })).not.toBeInTheDocument();
    expect(screen.queryByText("Changed")).not.toBeInTheDocument();
    expect(toastMessages()).toEqual([]);
  });

  it("puts the API's message under the row it named", async () => {
    const { calls } = server({
      putStatus: 422,
      putDetail: "behavior.bush_hide: Input should be a valid boolean",
    });
    mount();
    expect(await screen.findByRole("switch", { name: "Hide in bushes" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("switch", { name: "Hide in bushes" }));
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    expect(
      await screen.findByText("bush_hide: Input should be a valid boolean"),
    ).toBeInTheDocument();
    expect(toastMessages()).toEqual([]);
  });
});
