/** The /instances/:name frame: which row of the fleet it picks, what its header says
 * about that instance, and what each of its controls calls. */
import { renderHook, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { Instance } from "./Instance";
import { resetToasts, useToasts } from "../lib/toast";
import { closeEvents, setEventSourceFactory } from "../live/useEvents";
import { makeInstance, makePlan, makeSchedule } from "../test/fixtures";
import { type FetchCall, jpegResponse, jsonResponse, stubFetch } from "../test/http";
import { renderWithProviders } from "../test/renderWithProviders";

beforeAll(() => {
  Object.defineProperty(URL, "createObjectURL", { value: vi.fn(() => "blob:shot"), writable: true });
  Object.defineProperty(URL, "revokeObjectURL", { value: vi.fn(), writable: true });
});

/** jsdom has no EventSource and the page's feed opens the stream the moment it mounts.
 * What arrives on that stream is App.test.tsx's and Feed.test.tsx's business, so this
 * page gets one that never speaks. */
function silentStream(): EventSource {
  return {
    addEventListener: () => {},
    removeEventListener: () => {},
    close: () => {},
  } as unknown as EventSource;
}

beforeEach(() => {
  setEventSourceFactory(silentStream);
});

afterEach(() => {
  closeEvents();
  setEventSourceFactory(null);
  resetToasts();
  vi.unstubAllGlobals();
});

function toasts() {
  return renderHook(() => useToasts()).result.current;
}

/** The feed has its own tests; on this page it only has to render without asking for
 * anything the other stubs would have to answer. */
const EMPTY_FEED = () => jsonResponse({ session: null, records: [] });

/** The farm plan panel reads its own plan the moment the page mounts, and has its own
 * tests too; here it only has to be served a body of the right shape. */
const PLAN = () => jsonResponse(makePlan());

/** Every request the page makes: the fleet list, the screenshot, today's stats, this
 * session's feed, the farm plan, the schedule, and the three controls, each of which the
 * API answers 202 Accepted. */
function stubPage(instances: ReturnType<typeof makeInstance>[]): FetchCall[] {
  return stubFetch((url) => {
    if (url === "/api/instances") return jsonResponse({ instances });
    if (url.endsWith("preview.jpg")) return jpegResponse();
    // Only summary.avg_placement is read, so the rest of the stats body is left out.
    if (url.startsWith("/api/stats")) {
      return jsonResponse({ range: "today", instances: ["Pie64"], summary: { avg_placement: 3.4 } });
    }
    if (url.startsWith("/api/instances/Pie64/feed")) return EMPTY_FEED();
    if (url === "/api/instances/Pie64/plan") return PLAN();
    if (url === "/api/instances/Pie64/schedule") return jsonResponse(makeSchedule());
    return jsonResponse({ ok: true }, 202);
  }).calls;
}

/** The same page, except that every control fails with the API's own sentence. */
function stubFailingPage(detail: string): FetchCall[] {
  return stubFetch((url) => {
    if (url === "/api/instances") {
      return jsonResponse({ instances: [makeInstance({ name: "Pie64", state: "farming" })] });
    }
    if (url.endsWith("preview.jpg")) return jpegResponse();
    if (url.startsWith("/api/stats")) {
      return jsonResponse({ range: "today", instances: ["Pie64"], summary: { avg_placement: 3.4 } });
    }
    if (url.startsWith("/api/instances/Pie64/feed")) return EMPTY_FEED();
    if (url === "/api/instances/Pie64/plan") return PLAN();
    if (url === "/api/instances/Pie64/schedule") return jsonResponse(makeSchedule());
    return jsonResponse({ detail }, 503);
  }).calls;
}

/** api<T>() sends a GET as fetch(path, {}), so a missing method means GET. */
function scheduleGets(calls: FetchCall[]): number {
  return calls.filter(
    (call) =>
      call.url === "/api/instances/Pie64/schedule" && (call.init?.method ?? "GET") === "GET",
  ).length;
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
  it("announces a loading panel while the fleet is loading", () => {
    stubFetch(() => new Promise<Response>(() => {}));
    mountPage();
    expect(screen.getByRole("status", { name: "Loading Pie64" })).toHaveAttribute(
      "aria-busy",
      "true",
    );
  });

  it("reports an unknown instance with the API's own words", async () => {
    stubPage([makeInstance({ name: "Pie64_1" })]);
    mountPage();
    expect(
      await screen.findByText("No instance by that name. Open Fleet to pick one."),
    ).toBeInTheDocument();
  });

  it("heads the page with the name, state and phase, and labels every token below", async () => {
    stubPage([
      makeInstance({
        name: "Pie64",
        adb_port: 5555,
        state: "farming",
        phase: "playing",
        player_tag: "#2P0YLQ9",
      }),
    ]);
    const { container } = mountPage();
    expect(await screen.findByRole("heading", { level: 1, name: "Pie64" })).toBeInTheDocument();
    expect(screen.getByText("Farming")).toBeInTheDocument();
    expect(screen.getByText("Playing")).toBeInTheDocument();
    // Every value in the second row carries its own label, so no bare number is left to
    // guess at.
    expect(screen.getByText("Player tag")).toBeInTheDocument();
    expect(screen.getByText("#2P0YLQ9")).toHaveAttribute("data-private");
    expect(screen.getByText("ADB port")).toBeInTheDocument();
    expect(screen.getByText("5555")).toBeInTheDocument();
    expect(screen.getByText("Data folder")).toBeInTheDocument();
    expect(screen.getByText("instances/Pie64")).toBeInTheDocument();
    // The shell's breadcrumb already reads Fleet / Pie64, so the header does not say it
    // a second time.
    const header = container.querySelector("header") as HTMLElement;
    expect(within(header).queryByRole("link", { name: "Fleet" })).not.toBeInTheDocument();
  });

  it("leaves the whole player tag group out when there is no tag", async () => {
    stubPage([makeInstance({ name: "Pie64", player_tag: "" })]);
    mountPage();
    await screen.findByRole("heading", { level: 1, name: "Pie64" });
    expect(screen.queryByText("Player tag")).not.toBeInTheDocument();
  });

  it("opens the screenshot from a button rather than a link", async () => {
    stubPage([makeInstance({ name: "Pie64", state: "farming" })]);
    const open = vi.fn();
    vi.stubGlobal("open", open);
    mountPage();
    expect(screen.queryByRole("link", { name: "Screenshot" })).not.toBeInTheDocument();
    await userEvent.click(await screen.findByRole("button", { name: "Screenshot" }));
    expect(open).toHaveBeenCalledWith(
      "/api/instances/Pie64/screenshot.png",
      "_blank",
      "noopener",
    );
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

  it("asks for the schedule again once a control has settled", async () => {
    // Nothing on the schedule route is pushed over the event stream, so a Stop that has
    // just written a stop override would otherwise leave the panel showing yesterday's
    // answer until the page was reloaded.
    const calls = stubPage([makeInstance({ name: "Pie64", state: "farming" })]);
    mountPage();
    await screen.findByRole("button", { name: "Stop" });
    await waitFor(() => {
      expect(scheduleGets(calls)).toBe(1);
    });

    await userEvent.click(screen.getByRole("button", { name: "Stop" }));
    await waitFor(() => {
      expect(calls.map((call) => call.url)).toContain("/api/instances/Pie64/stop");
    });
    await waitFor(() => {
      expect(scheduleGets(calls)).toBe(2);
    });
  });

  it("asks before it restarts, and sends nothing when the question is cancelled", async () => {
    const calls = stubPage([makeInstance({ name: "Pie64", state: "farming" })]);
    mountPage();
    await userEvent.click(await screen.findByRole("button", { name: "Restart" }));
    const dialog = await screen.findByRole("dialog", { name: "Restart Pie64?" });
    expect(dialog).toHaveTextContent("The current match is abandoned.");
    expect(calls.map((call) => call.url)).not.toContain("/api/instances/Pie64/restart");

    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(calls.map((call) => call.url)).not.toContain("/api/instances/Pie64/restart");
    expect(toasts()).toHaveLength(0);
  });

  it("restarts the instance once the question is confirmed, and only then says so", async () => {
    const calls = stubPage([makeInstance({ name: "Pie64", state: "farming" })]);
    mountPage();
    await userEvent.click(await screen.findByRole("button", { name: "Restart" }));
    const dialog = await screen.findByRole("dialog", { name: "Restart Pie64?" });
    await userEvent.click(within(dialog).getByRole("button", { name: "Restart" }));
    await waitFor(() => {
      const restarts = calls.filter((call) => call.url === "/api/instances/Pie64/restart");
      expect(restarts).toHaveLength(1);
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
    expect(stop).toHaveAttribute("title", "Already stopped");
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

  it("orders the panels by job: watch, then read, then the numbers and the plans", async () => {
    stubPage([makeInstance({ name: "Pie64", state: "farming" })]);
    const { container } = mountPage();
    await screen.findByRole("heading", { level: 1, name: "Pie64" });
    await waitFor(() => {
      const headings = screen
        .getAllByRole("heading", { level: 2 })
        .map((heading) => heading.textContent);
      expect(headings).toEqual(["Live screen", "Feed", "Session", "Farm plan", "Schedule"]);
    });
    // One DOM order at both widths, so the tab order and the reading order agree.
    for (const id of ["watch", "session", "plan", "schedule"]) {
      expect(container.querySelectorAll(`#${id}`)).toHaveLength(1);
    }
  });

  it("offers a jump bar that reaches the four panels the page can scroll past", async () => {
    stubPage([makeInstance({ name: "Pie64", state: "farming" })]);
    mountPage();
    const bar = await screen.findByRole("navigation", { name: "Jump to a panel" });
    const links = within(bar).getAllByRole("link");
    expect(links.map((link) => link.textContent)).toEqual([
      "Watch",
      "Session",
      "Plan",
      "Schedule",
    ]);
    expect(links.map((link) => link.getAttribute("href"))).toEqual([
      "#watch",
      "#session",
      "#plan",
      "#schedule",
    ]);
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
    const dialog = await screen.findByRole("dialog", { name: "Restart Pie64?" });
    await userEvent.click(within(dialog).getByRole("button", { name: "Restart" }));
    await waitFor(() => {
      expect(toasts()[0]?.message).toBe("BlueStacks did not come back");
    });
    expect(calls.map((call) => call.url)).toContain("/api/instances/Pie64/restart");
    expect(toasts()).toHaveLength(1);
  });
});
