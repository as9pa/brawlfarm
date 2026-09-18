/** Step 3: one card per instance, and the one sentence that says how to fix a wrong one. */
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Setup } from "./Setup";
import type { DisplayCheckResponse } from "../api/types";
import { makeSettings } from "../test/fixtures";
import { type FetchCall, jsonResponse, stubFetch } from "../test/http";
import { renderWithProviders } from "../test/renderWithProviders";

const CHECK = "/api/setup/display-check";
const EXPECTED = { width: 1600, height: 900, dpi: 240 };
const HINT =
  "Set the display to 1600 x 900 and pixel density 240 in BlueStacks: Settings, Display, " +
  "then restart the instance.";
const FIX = "In BlueStacks: Settings, Display, Custom, 1600 \u00d7 900.";
const WRONG_CHIP = "Wrong size, needs 1600 \u00d7 900";

const CORRECT: DisplayCheckResponse = {
  ok: true,
  width: 1600,
  height: 900,
  dpi: 240,
  detail: "1600x900 at 240 dpi",
  hint: HINT,
  expected: EXPECTED,
};

const WRONG: DisplayCheckResponse = {
  ok: false,
  width: 1920,
  height: 1080,
  dpi: 320,
  detail: "1920x1080 at 320 dpi",
  hint: HINT,
  expected: EXPECTED,
};

const UNKNOWN: DisplayCheckResponse = {
  ok: false,
  width: null,
  height: null,
  dpi: null,
  detail: "adb was not found; set its path in Connection",
  hint: HINT,
  expected: EXPECTED,
};

/** Two instances already in config.toml, so the wizard lands on step 3. `answers` is read
 * by port, and a port may answer differently the second time it is asked. */
function server(answers: Record<number, DisplayCheckResponse[]>) {
  const asked: Record<number, number> = {};
  const stored = makeSettings({
    instances: [
      { name: "Pie64", adb_port: 5555, player_tag: "" },
      { name: "Pie64_3", adb_port: 5585, player_tag: "" },
    ],
  });
  const { calls } = stubFetch((url, init) => {
    if (url === CHECK) {
      const port = (JSON.parse(String(init?.body)) as { adb_port: number }).adb_port;
      const queue = answers[port];
      const at = asked[port] ?? 0;
      asked[port] = at + 1;
      return jsonResponse(queue[Math.min(at, queue.length - 1)]);
    }
    if (url !== "/api/settings") throw new Error(`unstubbed request: ${url}`);
    return jsonResponse(stored);
  });
  return { calls };
}

/** The <article> an instance sits in. Async because the cards come from the settings
 * document, which is still in flight when the test starts looking. */
/** Two instances are already in config.toml, so the wizard lands on the last step; the
 * rail is how a returning owner gets back to step 3. */
async function landOnDisplay(): Promise<void> {
  renderWithProviders(<Setup />, { route: "/setup" });
  const rail = await screen.findByRole("button", { name: "Display" });
  await waitFor(() => {
    expect(rail).toBeEnabled();
  });
  await userEvent.click(rail);
}

async function card(name: string): Promise<HTMLElement> {
  const found = (await screen.findByText(name)).closest("article");
  if (found === null) throw new Error(`no card for ${name}`);
  return found;
}

function checks(calls: FetchCall[]): number[] {
  return calls
    .filter((call) => call.url === CHECK)
    .map((call) => (JSON.parse(String(call.init?.body)) as { adb_port: number }).adb_port);
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Setup step 3: Display", () => {
  it("checks every instance and says Correct when it is", async () => {
    const { calls } = server({ 5555: [CORRECT], 5585: [CORRECT] });
    await landOnDisplay();
    // By heading, because the step rail beside it carries the same word as a button.
    expect(await screen.findByRole("heading", { name: "Display" })).toBeInTheDocument();
    expect(
      screen.getByText("The farm reads the screen, so every instance has to be the same size."),
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(checks(calls).sort()).toEqual([5555, 5585]);
    });
    expect(await within(await card("Pie64")).findByText("Correct")).toBeInTheDocument();
    expect(
      within(await card("Pie64")).getByText("1600 \u00d7 900, pixel density 240"),
    ).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Continue" })).toBeEnabled();
    // A card that is right does not repeat the fix, and the API's own sentence, which
    // spells the size with a letter x, never reaches the screen.
    expect(screen.queryByText(FIX)).not.toBeInTheDocument();
    expect(screen.queryByText(HINT)).not.toBeInTheDocument();
  });

  it("shows what it measured and how to fix it when the size is wrong", async () => {
    server({ 5555: [CORRECT], 5585: [WRONG] });
    await landOnDisplay();
    expect(await within(await card("Pie64_3")).findByText(WRONG_CHIP)).toBeInTheDocument();
    expect(
      within(await card("Pie64_3")).getByText("1920 \u00d7 1080, pixel density 320"),
    ).toBeInTheDocument();
    expect(within(await card("Pie64_3")).getByText(FIX)).toBeInTheDocument();
  });

  it("falls back to the API's own sentence when nothing could be measured", async () => {
    server({ 5555: [UNKNOWN], 5585: [UNKNOWN] });
    await landOnDisplay();
    expect(
      await within(await card("Pie64")).findByText(
        "adb was not found; set its path in Connection",
      ),
    ).toBeInTheDocument();
    // The fix sentence names a size too, so this pins the measured line's own shape.
    expect(
      within(await card("Pie64")).queryByText(/^\d+ \u00d7 \d+, pixel density \d+$/),
    ).not.toBeInTheDocument();
    expect(within(await card("Pie64")).getByText(FIX)).toBeInTheDocument();
  });

  it("keeps Continue shut with its reason until Recheck finds every card correct", async () => {
    const { calls } = server({ 5555: [CORRECT], 5585: [WRONG, CORRECT] });
    await landOnDisplay();
    expect(await within(await card("Pie64_3")).findByText(WRONG_CHIP)).toBeInTheDocument();
    const forward = screen.getByRole("button", { name: "Continue" });
    expect(forward).toBeDisabled();
    expect(forward).toHaveAttribute("title", "Fix the display first");

    await userEvent.click(within(await card("Pie64_3")).getByRole("button", { name: "Recheck" }));
    await waitFor(() => {
      expect(checks(calls).filter((port) => port === 5585)).toHaveLength(2);
    });
    expect(await within(await card("Pie64_3")).findByText("Correct")).toBeInTheDocument();
    await waitFor(() => {
      expect(forward).toBeEnabled();
    });
    // Nothing was saved: this step stores nothing at all.
    expect(calls.filter((call) => call.init?.method === "PUT")).toHaveLength(0);
  });
});
