/** Settings > Behavior: six plain switches, seven more behind Advanced, and every one of
 * them writing its own field. */
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
    expect(await screen.findByRole("switch", { name: "Win-rate aware" })).toBeInTheDocument();
    expect(screen.getAllByRole("switch")).toHaveLength(6); // Advanced is still collapsed
    for (const [name, sentence] of [
      ["Win-rate aware", "Prefer brawlers that win more in the current step."],
      ["Opportunity cost", "Skip brawlers whose next tier is far off."],
      ["Gas aware", "Move away from the gas earlier."],
      ["Bush hide", "Hide in bushes when the map allows."],
      ["Close game on stop", "Close Brawl Stars when the instance stops."],
      ["DND at start", "Turn on Do Not Disturb when the instance starts."],
    ]) {
      expect(screen.getByRole("switch", { name })).toBeInTheDocument();
      expect(screen.getByText(sentence)).toBeInTheDocument();
    }
    expect(screen.getByText("Applies the next time an instance starts.")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("switch", { name: "Gas aware" }));
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    expect(puts(calls)[0].behavior.gas_aware).toBe(false);
    // Only that one field moved: the whole document went, unchanged everywhere else.
    expect(puts(calls)[0].behavior.winrate_aware).toBe(true);
    expect(puts(calls)[0].advanced).toEqual(makeSettings().advanced);
    expect(current().behavior.gas_aware).toBe(false);
    expect(toastMessages()).toEqual(["Settings saved"]);
  });

  it("keeps the seven advanced switches behind Show, and writes the advanced section", async () => {
    const { calls } = server();
    mount();
    expect(await screen.findByRole("switch", { name: "Win-rate aware" })).toBeInTheDocument();
    expect(screen.getByText("Advanced")).toBeInTheDocument();
    expect(screen.queryByRole("switch", { name: "Fast input" })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Show" }));
    expect(screen.getAllByRole("switch")).toHaveLength(13);
    for (const [name, sentence] of [
      ["Fast input", "Send taps through the faster adb path."],
      ["Raw capture", "Read frames without re-encoding them."],
      ["Gray matching", "Match templates in grayscale."],
      ["Phase classify", "Work out the match phase from the screen."],
      ["Ability buttons", "Use the gadget and super buttons."],
      ["Recalibration tripwire", "Warn when a detector looks season-blind."],
      ["DND off on stop", "Turn Do Not Disturb back off when the instance stops."],
    ]) {
      expect(screen.getByRole("switch", { name })).toBeInTheDocument();
      expect(screen.getByText(sentence)).toBeInTheDocument();
    }

    await userEvent.click(screen.getByRole("switch", { name: "Gray matching" }));
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    expect(puts(calls)[0].advanced.gray_match).toBe(false);

    await userEvent.click(screen.getByRole("button", { name: "Hide" }));
    expect(screen.queryByRole("switch", { name: "Gray matching" })).not.toBeInTheDocument();
  });

  it("puts the API's message under the row it named", async () => {
    const { calls } = server({
      putStatus: 422,
      putDetail: "behavior.bush_hide: Input should be a valid boolean",
    });
    mount();
    expect(await screen.findByRole("switch", { name: "Bush hide" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("switch", { name: "Bush hide" }));
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    expect(
      await screen.findByText("bush_hide: Input should be a valid boolean"),
    ).toBeInTheDocument();
    expect(toastMessages()).toEqual([]);
  });
});
