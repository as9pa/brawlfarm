/** The one screen that writes the worker's own configuration: what each control saves,
 * when it saves it, and what it puts back when the save fails. */
import { act, fireEvent, renderHook, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { FarmPlan } from "./FarmPlan";
import { resetToasts, useToasts } from "../lib/toast";
import { makePlan } from "../test/fixtures";
import { type FetchCall, jsonResponse, stubFetch } from "../test/http";
import { renderWithProviders } from "../test/renderWithProviders";

const PLAN = "/api/instances/Pie64/plan";

function toastMessages(): string[] {
  return renderHook(() => useToasts()).result.current.map((item) => item.message);
}

/** Every plan body this panel has sent, parsed. */
function puts(calls: FetchCall[]): unknown[] {
  return calls
    .filter((call) => call.url === PLAN && call.init?.method === "PUT")
    .map((call) => JSON.parse(String(call.init?.body)));
}

/** Serve `body` on GET and echo the PUT back merged over it, which is what task 7's
 * route does: the same enriched shape, with the four stored keys replaced. */
function mount(body = makePlan(), putStatus = 200): FetchCall[] {
  return stubFetch((url, init) => {
    if (url !== PLAN) throw new Error(`unstubbed request: ${url}`);
    if (init?.method !== "PUT") return jsonResponse(body);
    return putStatus === 200
      ? jsonResponse({ ...body, ...JSON.parse(String(init.body)) })
      : jsonResponse({ detail: "adb did not answer" }, putStatus);
  }).calls;
}

/** A response the test hands over when it chooses, so one save can be caught in flight
 * while the next control is touched. */
function deferred(): { promise: Promise<Response>; resolve: (response: Response) => void } {
  let resolve!: (response: Response) => void;
  const promise = new Promise<Response>((settle) => {
    resolve = settle;
  });
  return { promise, resolve };
}

afterEach(() => {
  resetToasts();
  vi.unstubAllGlobals();
});

describe("FarmPlan", () => {
  it("switching to prestige saves the whole plan and offers the start end", async () => {
    const calls = mount();
    renderWithProviders(<FarmPlan name="Pie64" />);
    await userEvent.click(await screen.findByRole("radio", { name: "Prestige" }));
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    expect(puts(calls)[0]).toEqual({
      mode: "prestige",
      prestige_start: "highest",
      goal_trophies: 1000,
      maxed_fallback: null,
    });
    expect(toastMessages()).toEqual(["Plan saved"]);
    expect(screen.getByText(/^Saved \d\d:\d\d$/)).toBeInTheDocument();
    expect(await screen.findByRole("radio", { name: "Lowest" })).toBeInTheDocument();
    expect(screen.getByText("Goal 1000, the prestige threshold")).toBeInTheDocument();
  });

  it("shows the goal for ladder and hides the prestige caption", async () => {
    mount();
    renderWithProviders(<FarmPlan name="Pie64" />);
    expect(await screen.findByLabelText("Goal")).toHaveValue(1000);
    expect(screen.queryByText("Goal 1000, the prestige threshold")).not.toBeInTheDocument();
  });

  it("caps the progress bar at 100 per cent and names it for a screen reader", async () => {
    mount(makePlan({ current: { brawler: "SPIKE", trophies: 1400, goal: 1000 } }));
    renderWithProviders(<FarmPlan name="Pie64" />);
    const bar = await screen.findByRole("progressbar", { name: "Progress to goal" });
    expect(bar.style.width).toBe("100%");
    expect(bar).toHaveAttribute("aria-valuemin", "0");
    expect(bar).toHaveAttribute("aria-valuemax", "100");
    expect(bar).toHaveAttribute("aria-valuenow", "100");
  });

  it("lists the queue with its trophies and can show the whole roster", async () => {
    mount();
    renderWithProviders(<FarmPlan name="Pie64" />);
    expect(await screen.findByText("TARA")).toBeInTheDocument();
    expect(screen.queryByTestId("plan-roster")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Show all brawlers" }));
    const rows = screen.getByTestId("plan-roster").querySelectorAll("li");
    expect([...rows].map((li) => li.textContent)).toEqual(["NORI812", "SHELLY615", "TARA540"]);
  });

  it("explains a missing roster in the words the reader can act on", async () => {
    mount(makePlan({ roster: null, queue: [], roster_status: "no_token" }));
    const first = renderWithProviders(<FarmPlan name="Pie64" />);
    expect(
      await screen.findByText("Add a Brawl Stars API token in Settings to see the roster."),
    ).toBeInTheDocument();
    first.unmount();

    mount(makePlan({ roster: null, queue: [], roster_status: "no_tag" }));
    const second = renderWithProviders(<FarmPlan name="Pie64" />);
    expect(
      await screen.findByText("Set this instance's player tag in Settings to see the roster."),
    ).toBeInTheDocument();
    second.unmount();

    mount(makePlan({ roster: null, queue: [], roster_status: "unavailable" }));
    const third = renderWithProviders(<FarmPlan name="Pie64" />);
    expect(await screen.findByText("Roster unavailable right now.")).toBeInTheDocument();
    third.unmount();

    mount(makePlan({ roster_status: "unavailable" }));
    renderWithProviders(<FarmPlan name="Pie64" />);
    expect(
      await screen.findByText("Roster unavailable right now; showing the last known list."),
    ).toBeInTheDocument();
  });

  it("offers the roster to the fallback box only once the switch is on", async () => {
    const calls = mount();
    renderWithProviders(<FarmPlan name="Pie64" />);
    const toggle = await screen.findByRole("switch", { name: "Maxed fallback" });
    expect(screen.queryByLabelText("Fallback brawler")).not.toBeInTheDocument();
    await userEvent.click(toggle);
    const box = await screen.findByLabelText("Fallback brawler");
    const list = document.getElementById(box.getAttribute("list") ?? "");
    expect(
      [...(list?.querySelectorAll("option") ?? [])].map((option) => option.getAttribute("value")),
    ).toEqual(["NORI", "SHELLY", "TARA"]);
    expect(puts(calls)).toHaveLength(0); // showing the box is not a change
  });

  it("puts the previous values back when the save fails", async () => {
    const calls = mount(makePlan(), 503);
    renderWithProviders(<FarmPlan name="Pie64" />);
    await userEvent.click(await screen.findByRole("radio", { name: "Prestige" }));
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    expect(await screen.findByText("adb did not answer")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByRole("radio", { name: "Ladder" })).toHaveAttribute("aria-checked", "true");
    });
    expect(toastMessages()).toEqual([]);
  });

  it("rolls a failed save back to the settled plan, not to an unconfirmed one", async () => {
    const body = makePlan();
    const first = deferred();
    let sent = 0;
    const { calls } = stubFetch((url, init) => {
      if (url !== PLAN) throw new Error(`unstubbed request: ${url}`);
      if (init?.method !== "PUT") return jsonResponse(body);
      sent += 1;
      return sent === 1 ? first.promise : jsonResponse({ detail: "adb did not answer" }, 503);
    });
    renderWithProviders(<FarmPlan name="Pie64" />);
    await userEvent.click(await screen.findByRole("radio", { name: "Prestige" }));
    await userEvent.click(await screen.findByRole("radio", { name: "Lowest" }));
    expect(puts(calls)).toHaveLength(1); // the second save waits for the first to settle

    // The API recomputes the queue for the new mode, so the plan it confirms is one the
    // optimistic cache could not have guessed.
    first.resolve(jsonResponse({ ...body, mode: "prestige", queue: ["SHELLY"] }));
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(2);
    });
    expect(await screen.findByText("adb did not answer")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByRole("radio", { name: "Highest" })).toHaveAttribute(
        "aria-checked",
        "true",
      );
    });
    expect(screen.getByRole("radio", { name: "Prestige" })).toHaveAttribute("aria-checked", "true");
    expect(screen.getByText("SHELLY")).toBeInTheDocument();
    expect(screen.queryByText("TARA")).not.toBeInTheDocument();
  });
});

/** One keystroke on a controlled field. fireEvent rather than userEvent: userEvent awaits
 * testing-library's async wrapper, which drains the queue with a real setTimeout that fake
 * timers never run (the same trap as Toast.test.tsx). */
function keystroke(field: HTMLElement, value: string): void {
  fireEvent.change(field, { target: { value } });
}

/** Move the fake clock on with React's own work inside act, so a debounce that fires and
 * the PUT it sends both settle before the next assertion. */
async function tick(ms: number): Promise<void> {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

describe("FarmPlan goal debounce", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    resetToasts();
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("sends one PUT 500 ms after the last keystroke, and none for a bad value", async () => {
    const calls = mount();
    renderWithProviders(<FarmPlan name="Pie64" />);
    // The plan's fetch settles on the fake clock, so it needs a tick of its own.
    await tick(0);
    const goal = screen.getByLabelText("Goal");

    keystroke(goal, "8");
    keystroke(goal, "85");
    keystroke(goal, "850");
    expect(puts(calls)).toHaveLength(0); // still typing
    await tick(499);
    expect(puts(calls)).toHaveLength(0);
    await tick(1);
    expect(puts(calls)).toHaveLength(1);
    expect(puts(calls)[0]).toEqual({
      mode: "ladder",
      prestige_start: "highest",
      goal_trophies: 850,
      maxed_fallback: null,
    });

    keystroke(goal, "-4");
    await tick(1000);
    expect(puts(calls)).toHaveLength(1); // an integer >= 0 or nothing is sent
  });
});

/** A pending debounce belongs to the box it was typed into. When that box goes away the
 * write goes with it, so the worker never holds a setting the panel has stopped showing. */
describe("FarmPlan pending writes", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    resetToasts();
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("switching Maxed fallback off cancels a name that was still pending", async () => {
    const calls = mount();
    renderWithProviders(<FarmPlan name="Pie64" />);
    await tick(0);

    fireEvent.click(screen.getByRole("switch", { name: "Maxed fallback" }));
    keystroke(screen.getByLabelText("Fallback brawler"), "TARA");
    await tick(400);
    fireEvent.click(screen.getByRole("switch", { name: "Maxed fallback" }));
    await tick(600);

    expect(puts(calls)).toEqual([]); // the plan held no name, so the switch wrote nothing
    expect(screen.queryByLabelText("Fallback brawler")).not.toBeInTheDocument();
  });

  it("switching Maxed fallback off still clears the name the plan holds", async () => {
    const calls = mount(makePlan({ maxed_fallback: "NORI" }));
    renderWithProviders(<FarmPlan name="Pie64" />);
    await tick(0);

    keystroke(screen.getByLabelText("Fallback brawler"), "TARA");
    await tick(400);
    fireEvent.click(screen.getByRole("switch", { name: "Maxed fallback" }));
    await tick(600);

    expect(puts(calls)).toEqual([
      { mode: "ladder", prestige_start: "highest", goal_trophies: 1000, maxed_fallback: null },
    ]);
  });

  it("switching to prestige cancels a goal that was still pending", async () => {
    const calls = mount();
    renderWithProviders(<FarmPlan name="Pie64" />);
    await tick(0);

    keystroke(screen.getByLabelText("Goal"), "850");
    await tick(400);
    fireEvent.click(screen.getByRole("radio", { name: "Prestige" }));
    await tick(600);

    // The body is always the four stored keys, so goal_trophies is there: what matters is
    // that it is the plan's own 1000 and not the 850 typed into a box that is now gone.
    expect(puts(calls)).toEqual([
      { mode: "prestige", prestige_start: "highest", goal_trophies: 1000, maxed_fallback: null },
    ]);
  });

  it("puts back only the field whose save failed", async () => {
    mount(makePlan({ maxed_fallback: "NORI" }), 503);
    renderWithProviders(<FarmPlan name="Pie64" />);
    await tick(0);

    keystroke(screen.getByLabelText("Goal"), "850");
    await tick(400);
    keystroke(screen.getByLabelText("Fallback brawler"), "TARA");
    await tick(150); // the goal's 500 ms is up; the fallback still has 350 ms to run

    expect(screen.getByText("adb did not answer")).toBeInTheDocument();
    expect(screen.getByLabelText("Goal")).toHaveValue(1000);
    expect(screen.getByLabelText("Fallback brawler")).toHaveValue("TARA");
  });
});
