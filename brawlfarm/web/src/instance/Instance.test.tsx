/** The /instances/:name frame: which row of the fleet it picks, what its header says
 * about that instance, and what each of its controls calls. */
import { renderHook, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { Instance } from "./Instance";
import { resetToasts, useToasts } from "../lib/toast";
import { makeInstance } from "../test/fixtures";
import { type FetchCall, jsonResponse, pngResponse, stubFetch } from "../test/http";
import { renderWithProviders } from "../test/renderWithProviders";

beforeAll(() => {
  Object.defineProperty(URL, "createObjectURL", { value: vi.fn(() => "blob:shot"), writable: true });
  Object.defineProperty(URL, "revokeObjectURL", { value: vi.fn(), writable: true });
});

afterEach(() => {
  resetToasts();
  vi.unstubAllGlobals();
});

function toasts() {
  return renderHook(() => useToasts()).result.current;
}

/** Every request the page makes: the fleet list, the screenshot, and the three controls,
 * each of which the API answers 202 Accepted. */
function stubPage(instances: ReturnType<typeof makeInstance>[]): FetchCall[] {
  return stubFetch((url) => {
    if (url === "/api/instances") return jsonResponse({ instances });
    if (url.endsWith("screenshot.png")) return pngResponse();
    return jsonResponse({ ok: true }, 202);
  }).calls;
}

/** The same page, except that every control fails with the API's own sentence. */
function stubFailingPage(detail: string): FetchCall[] {
  return stubFetch((url) => {
    if (url === "/api/instances") {
      return jsonResponse({ instances: [makeInstance({ name: "Pie64", state: "farming" })] });
    }
    if (url.endsWith("screenshot.png")) return pngResponse();
    return jsonResponse({ detail }, 503);
  }).calls;
}

function mountPage() {
  return renderWithProviders(
    <Routes>
      <Route path="/instances/:name" element={<Instance />} />
    </Routes>,
    { route: "/instances/Pie64" },
  );
}

describe("Instance", () => {
  it("renders nothing but the shell while the fleet is loading", () => {
    stubFetch(() => new Promise<Response>(() => {}));
    const { container } = mountPage();
    expect(container.textContent).toBe("");
  });

  it("reports an unknown instance with the API's own words", async () => {
    stubPage([makeInstance({ name: "Pie64_1" })]);
    mountPage();
    expect(await screen.findByText("unknown instance")).toBeInTheDocument();
  });

  it("heads the page with the name, state, port, tag, phase and a screenshot link", async () => {
    stubPage([
      makeInstance({
        name: "Pie64",
        adb_port: 5555,
        state: "farming",
        phase: "playing",
        player_tag: "#2P0YLQ9",
      }),
    ]);
    mountPage();
    expect(await screen.findByRole("heading", { level: 1, name: "Pie64" })).toBeInTheDocument();
    expect(screen.getByText("Farming")).toBeInTheDocument();
    expect(screen.getByText("5555")).toBeInTheDocument();
    expect(screen.getByText("playing")).toBeInTheDocument();
    expect(screen.getByText("#2P0YLQ9")).toHaveAttribute("data-private");
    const shot = screen.getByRole("link", { name: "Screenshot" });
    expect(shot).toHaveAttribute("href", "/api/instances/Pie64/screenshot.png");
    expect(shot).toHaveAttribute("target", "_blank");
    expect(shot).toHaveAttribute("rel", "noreferrer");
  });

  it("stops after this match and offers an undo that starts again", async () => {
    const calls = stubPage([makeInstance({ name: "Pie64", state: "farming" })]);
    mountPage();
    await userEvent.click(await screen.findByRole("button", { name: "Stop" }));
    await waitFor(() => {
      expect(calls.map((call) => call.url)).toContain("/api/instances/Pie64/stop");
    });
    expect(toasts()[0].message).toBe("Stopping Pie64 after this match");
    await toasts()[0].undo?.();
    await waitFor(() => {
      expect(calls.map((call) => call.url)).toContain("/api/instances/Pie64/start");
    });
  });

  it("restarts the instance and only then says so", async () => {
    const calls = stubPage([makeInstance({ name: "Pie64", state: "farming" })]);
    mountPage();
    await userEvent.click(await screen.findByRole("button", { name: "Restart" }));
    await waitFor(() => {
      expect(calls.map((call) => call.url)).toContain("/api/instances/Pie64/restart");
    });
    await waitFor(() => {
      expect(toasts()[0]?.message).toBe("Restarting Pie64");
    });
  });

  it("disables Stop on a stopped instance and says why", async () => {
    stubPage([makeInstance({ name: "Pie64", state: "stopped" })]);
    mountPage();
    const stop = await screen.findByRole("button", { name: "Stop" });
    expect(stop).toBeDisabled();
    expect(stop).toHaveAttribute("title", "Not running");
    expect(screen.queryByRole("button", { name: "Retry now" })).not.toBeInTheDocument();
  });

  it("offers Retry now only while the instance is offline", async () => {
    const calls = stubPage([makeInstance({ name: "Pie64", state: "offline" })]);
    mountPage();
    await userEvent.click(await screen.findByRole("button", { name: "Retry now" }));
    await waitFor(() => {
      expect(calls.map((call) => call.url)).toContain("/api/instances/Pie64/retry");
    });
    expect(toasts()[0].message).toBe("Retrying Pie64 now");
  });

  it("speaks the API's own sentence when a control fails, and says nothing else", async () => {
    stubFailingPage("adb did not answer");
    mountPage();
    await userEvent.click(await screen.findByRole("button", { name: "Stop" }));
    await waitFor(() => {
      expect(toasts()[0]?.message).toBe("adb did not answer");
    });
    // The success toast never fires, so the failure is the only line on screen.
    expect(toasts()).toHaveLength(1);
  });

  it("says nothing but the failure when Restart is refused", async () => {
    const calls = stubFailingPage("BlueStacks did not come back");
    mountPage();
    await userEvent.click(await screen.findByRole("button", { name: "Restart" }));
    await waitFor(() => {
      expect(toasts()[0]?.message).toBe("BlueStacks did not come back");
    });
    expect(calls.map((call) => call.url)).toContain("/api/instances/Pie64/restart");
    expect(toasts()).toHaveLength(1);
  });
});
