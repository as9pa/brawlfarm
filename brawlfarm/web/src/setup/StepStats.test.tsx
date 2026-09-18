/** Step 4: the optional token and one tag per instance, and the button that says no. */
import { fireEvent, renderHook, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Setup } from "./Setup";
import type { AppSettings } from "../api/types";
import { resetToasts, useToasts } from "../lib/toast";
import { makeSettings } from "../test/fixtures";
import { type FetchCall, jsonResponse, stubFetch } from "../test/http";
import { renderWithProviders } from "../test/renderWithProviders";

const CHECK = "/api/setup/display-check";

const CORRECT = {
  ok: true,
  width: 1600,
  height: 900,
  dpi: 240,
  detail: "1600x900 at 240 dpi",
  hint: "",
  expected: { width: 1600, height: 900, dpi: 240 },
};

function server(options: { putStatus?: number; putDetail?: string } = {}) {
  let stored = makeSettings({
    instances: [
      { name: "Pie64", adb_port: 5555, player_tag: "" },
      { name: "Pie64_3", adb_port: 5585, player_tag: "" },
    ],
  });
  stored.connection.brawl_api_token = "";
  const { calls } = stubFetch((url, init) => {
    if (url === CHECK) return jsonResponse(CORRECT);
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

function puts(calls: FetchCall[]): AppSettings[] {
  return calls
    .filter((call) => call.url === "/api/settings" && call.init?.method === "PUT")
    .map((call) => JSON.parse(String(call.init?.body)) as AppSettings);
}

function toastMessages(): string[] {
  return renderHook(() => useToasts()).result.current.map((item) => item.message);
}

/** A fleet already in config.toml lands the wizard on the last step; the rail is how a
 * returning owner gets back to step 4. */
async function walkToStats() {
  const rail = await screen.findByRole("button", { name: "Stats" });
  await waitFor(() => {
    expect(rail).toBeEnabled();
  });
  await userEvent.click(rail);
  expect(await screen.findByText("Stats (optional)")).toBeInTheDocument();
}

afterEach(() => {
  resetToasts();
  vi.unstubAllGlobals();
});

describe("Setup step 4: Stats", () => {
  it("asks for the token and one tag per instance, and links the key page", async () => {
    server();
    renderWithProviders(<Setup />, { route: "/setup" });
    await walkToStats();

    expect(
      screen.getByText(
        "A token and your player tags let brawlfarm show per-brawler stats. Farming works without them.",
      ),
    ).toBeInTheDocument();
    const token = screen.getByLabelText("Brawl Stars API token");
    expect(token).toHaveAttribute("type", "password");
    expect(token).toHaveAttribute("data-private");
    expect(screen.getByLabelText("Pie64")).toHaveAttribute("placeholder", "#TAG");
    expect(screen.getByLabelText("Pie64_3")).toHaveAttribute("placeholder", "#TAG");

    const line = screen.getByText(/Create a key at/);
    expect(line).toHaveTextContent(
      "Create a key at developer.brawlstars.com and allow this machine's IP address.",
    );
    expect(screen.getByRole("link", { name: "developer.brawlstars.com" })).toHaveAttribute(
      "href",
      "https://developer.brawlstars.com",
    );
  });

  it("saves the token and a tag on blur, one field at a time", async () => {
    const { calls, current } = server();
    renderWithProviders(<Setup />, { route: "/setup" });
    await walkToStats();

    const token = screen.getByLabelText("Brawl Stars API token");
    fireEvent.change(token, { target: { value: "a-token-that-is-not-real" } });
    fireEvent.blur(token);
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    expect(puts(calls)[0].connection.brawl_api_token).toBe("a-token-that-is-not-real");

    const tag = screen.getByLabelText("Pie64_3");
    fireEvent.change(tag, { target: { value: "#2P0YLQ9" } });
    fireEvent.blur(tag);
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(2);
    });
    // Only that instance's tag moved, and the token written a moment ago is still there.
    expect(puts(calls)[1].instances).toEqual([
      { name: "Pie64", adb_port: 5555, player_tag: "" },
      { name: "Pie64_3", adb_port: 5585, player_tag: "#2P0YLQ9" },
    ]);
    expect(puts(calls)[1].connection.brawl_api_token).toBe("a-token-that-is-not-real");
    expect(current().instances[1].player_tag).toBe("#2P0YLQ9");
    await waitFor(() => {
      expect(toastMessages()).toEqual(["Saved to config.toml", "Saved to config.toml"]);
    });
  });

  it("puts a refused tag under the field that carried it", async () => {
    const { calls } = server({
      putStatus: 422,
      putDetail: "instances.0.player_tag: tag must be 3 to 15 characters after the #",
    });
    renderWithProviders(<Setup />, { route: "/setup" });
    await walkToStats();

    const tag = screen.getByLabelText("Pie64");
    fireEvent.change(tag, { target: { value: "#X" } });
    fireEvent.blur(tag);
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    expect(
      await screen.findByText("player_tag: tag must be 3 to 15 characters after the #"),
    ).toBeInTheDocument();
    // The box keeps what is being fixed, and no toast claims it was saved.
    expect(tag).toHaveValue("#X");
    expect(toastMessages()).toEqual([]);
  });

  it("Skip for now moves on without writing anything", async () => {
    const { calls } = server();
    renderWithProviders(<Setup />, { route: "/setup" });
    await walkToStats();

    await userEvent.click(screen.getByRole("button", { name: "Skip for now" }));
    expect(await screen.findByText("Setup complete.")).toBeInTheDocument();
    expect(puts(calls)).toHaveLength(0);
    expect(toastMessages()).toEqual([]);
    // Skipped counts as finished, so the rail ticks it.
    expect(screen.getByRole("button", { name: "Stats" }).querySelector("svg")).not.toBeNull();
  });
});
