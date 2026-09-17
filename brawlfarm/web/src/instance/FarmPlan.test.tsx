/** The one screen that writes the worker's own configuration: what each control saves,
 * when it saves it, and what it puts back when the save fails. */
import { act, fireEvent, renderHook, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { FarmPlan } from "./FarmPlan";
import { resetToasts, useToasts } from "../lib/toast";
import { makeConnection, makePlan, makeRosterBrawler } from "../test/fixtures";
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
 * route does: the same enriched shape, with the five stored keys replaced. */
function mount(body = makePlan(), putStatus = 200): FetchCall[] {
  return stubFetch((url, init) => {
    if (url === "/api/connection/check") return jsonResponse(makeConnection());
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
      quest_aware: false,
    });
    expect(toastMessages()).toEqual(["Plan saved"]);
    expect(screen.getByText(/^Saved \d\d:\d\d$/)).toBeInTheDocument();
    expect(await screen.findByRole("radio", { name: "Lowest" })).toBeInTheDocument();
    expect(screen.getByText("Goal 1,000, the prestige threshold")).toBeInTheDocument();
  });

  it("shows the goal for ladder and hides the prestige caption", async () => {
    mount();
    renderWithProviders(<FarmPlan name="Pie64" />);
    expect(await screen.findByLabelText("Goal")).toHaveValue(1000);
    expect(screen.queryByText("Goal 1,000, the prestige threshold")).not.toBeInTheDocument();
  });

  it("says so in words when there is no current brawler and no queue", async () => {
    mount(makePlan({ current: { brawler: null, trophies: null, goal: 1000 }, queue: [] }));
    renderWithProviders(<FarmPlan name="Pie64" />);
    expect(await screen.findByText("No brawler selected yet")).toBeInTheDocument();
    expect(screen.getByText("Queue is empty")).toBeInTheDocument();
    expect(screen.getByText("Not yet / 1,000")).toBeInTheDocument();
    expect(screen.queryByText("none")).not.toBeInTheDocument();
  });

  it("groups the thousands in the current trophies and the goal", async () => {
    mount(makePlan({ current: { brawler: "NORI", trophies: 110738, goal: 1000 } }));
    renderWithProviders(<FarmPlan name="Pie64" />);
    expect(await screen.findByText("110,738 / 1,000")).toBeInTheDocument();
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

  it("puts the Maxed fallback switch back on when clearing the name fails", async () => {
    const calls = mount(makePlan({ maxed_fallback: "NORI" }), 500);
    renderWithProviders(<FarmPlan name="Pie64" />);
    expect(await screen.findByLabelText("Fallback brawler")).toHaveValue("NORI");
    await userEvent.click(screen.getByRole("switch", { name: "Maxed fallback" }));
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    expect(puts(calls)[0]).toEqual({
      mode: "ladder",
      prestige_start: "highest",
      goal_trophies: 1000,
      maxed_fallback: null,
      quest_aware: false,
    });

    // The worker still has NORI, so the switch has to follow the cache back on.
    expect(await screen.findByText("adb did not answer")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByRole("switch", { name: "Maxed fallback" })).toHaveAttribute(
        "aria-checked",
        "true",
      );
    });
    expect(screen.getByLabelText("Fallback brawler")).toHaveValue("NORI");
    expect(toastMessages()).toEqual([]);
  });

  it("offers Pick quest brawlers under Maxed fallback, with its help line", async () => {
    mount();
    renderWithProviders(<FarmPlan name="Pie64" />);
    const switches = await screen.findAllByRole("switch");
    expect(switches.map((one) => one.textContent)).toEqual([
      "Maxed fallback",
      "Pick quest brawlers",
    ]);
    expect(switches[1]).toHaveAttribute("aria-checked", "false");
    // The help line is the switch's own description, not loose text sitting beside it.
    const help = document.getElementById(String(switches[1].getAttribute("aria-describedby")));
    expect(help).toHaveTextContent(
      "Applies at session start only. The instance reads the quests screen and picks an owned " +
        "brawler that clears a quest. Your plan target wins when it clears one; otherwise the " +
        "lowest-trophy candidate.",
    );
  });

  it("puts Pick quest brawlers back on when turning it off fails", async () => {
    const calls = mount(makePlan({ quest_aware: true }), 500);
    renderWithProviders(<FarmPlan name="Pie64" />);
    await userEvent.click(await screen.findByRole("switch", { name: "Pick quest brawlers" }));
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    expect(puts(calls)[0]).toEqual({
      mode: "ladder",
      prestige_start: "highest",
      goal_trophies: 1000,
      maxed_fallback: null,
      quest_aware: false,
    });

    // The cache is the source of truth after a failed save, so the switch goes back on.
    expect(await screen.findByText("adb did not answer")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByRole("switch", { name: "Pick quest brawlers" })).toHaveAttribute(
        "aria-checked",
        "true",
      );
    });
  });

  it("hides Pick quest brawlers in prestige mode without writing anything", async () => {
    const calls = mount(makePlan({ mode: "prestige", quest_aware: true }));
    renderWithProviders(<FarmPlan name="Pie64" />);
    expect(await screen.findByRole("switch", { name: "Maxed fallback" })).toBeInTheDocument();
    expect(screen.queryByRole("switch", { name: "Pick quest brawlers" })).toBeNull();
    expect(puts(calls)).toEqual([]); // hiding it is not a save

    // Ladder shows it again in the state the plan still holds.
    await userEvent.click(screen.getByRole("radio", { name: "Ladder" }));
    expect(await screen.findByRole("switch", { name: "Pick quest brawlers" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
  });

  it("puts an icon in front of the current brawler, every queue row and the full list", async () => {
    mount(
      makePlan({
        current: { brawler: "NORI", trophies: 820, goal: 1000 },
        queue: ["SHELLY", "COLT"],
        roster: [
          makeRosterBrawler({ id: 1, name: "NORI", trophies: 820 }),
          makeRosterBrawler({ id: 2, name: "SHELLY", trophies: 740 }),
        ],
      }),
    );
    renderWithProviders(<FarmPlan name="Pie64" />);

    await screen.findByText("SHELLY");
    // One for the current brawler, one per queue row.
    expect(screen.getAllByTestId("brawler-icon")).toHaveLength(3);

    await userEvent.click(screen.getByRole("button", { name: "Show all brawlers" }));
    // Plus one per roster row.
    expect(screen.getAllByTestId("brawler-icon")).toHaveLength(5);
  });

  it("says the token was rejected when the connection check says so", async () => {
    stubFetch((url) => {
      if (url === "/api/connection/check") {
        return jsonResponse(makeConnection({ status: "rejected" }));
      }
      if (url === PLAN) {
        return jsonResponse(makePlan({ roster: null, queue: [], roster_status: "unavailable" }));
      }
      throw new Error(`unstubbed request: ${url}`);
    });
    renderWithProviders(<FarmPlan name="Pie64" />);
    expect(
      await screen.findByText(
        /The Brawl Stars API rejected the token\. Check the token, and the IP address it was created for, in/,
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Settings, Connection" })).toHaveAttribute(
      "href",
      "/settings/connection",
    );
  });

  it("keeps the plain unavailable note when the connection check does not say rejected", async () => {
    stubFetch((url) => {
      if (url === "/api/connection/check") return jsonResponse(makeConnection({ status: "ok" }));
      if (url === PLAN) {
        return jsonResponse(makePlan({ roster: null, queue: [], roster_status: "unavailable" }));
      }
      throw new Error(`unstubbed request: ${url}`);
    });
    renderWithProviders(<FarmPlan name="Pie64" />);
    expect(await screen.findByText("Roster unavailable right now.")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Settings, Connection" })).toBeNull();
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
      quest_aware: false,
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

  it("Pick quest brawlers saves on the click, with no debounce to wait out", async () => {
    const calls = mount();
    renderWithProviders(<FarmPlan name="Pie64" />);
    await tick(0);

    fireEvent.click(screen.getByRole("switch", { name: "Pick quest brawlers" }));
    await tick(0); // no clock advanced: the PUT is already on its way
    expect(puts(calls)).toEqual([
      {
        mode: "ladder",
        prestige_start: "highest",
        goal_trophies: 1000,
        maxed_fallback: null,
        quest_aware: true,
      },
    ]);
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
      {
        mode: "ladder",
        prestige_start: "highest",
        goal_trophies: 1000,
        maxed_fallback: null,
        quest_aware: false,
      },
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

    // The body is always the five stored keys, so goal_trophies is there: what matters is
    // that it is the plan's own 1000 and not the 850 typed into a box that is now gone.
    expect(puts(calls)).toEqual([
      {
        mode: "prestige",
        prestige_start: "highest",
        goal_trophies: 1000,
        maxed_fallback: null,
        quest_aware: false,
      },
    ]);
  });

  it("drops a name typed while the save before it was in flight and failed", async () => {
    // The failure takes the box away. A debounce left running behind it would write the
    // newer name a moment later, and the panel would be holding a setting it has stopped
    // showing -- the same rule as switching the fallback off.
    const body = makePlan();
    const first = deferred();
    let sent = 0;
    const { calls } = stubFetch((url, init) => {
      if (url !== PLAN) throw new Error(`unstubbed request: ${url}`);
      if (init?.method !== "PUT") return jsonResponse(body);
      sent += 1;
      return sent === 1
        ? first.promise
        : jsonResponse({ ...body, ...JSON.parse(String(init.body)) });
    });
    renderWithProviders(<FarmPlan name="Pie64" />);
    await tick(0);

    fireEvent.click(screen.getByRole("switch", { name: "Maxed fallback" }));
    keystroke(screen.getByLabelText("Fallback brawler"), "TARA");
    await tick(500); // the debounce fired; the PUT is held open
    expect(puts(calls)).toHaveLength(1);

    keystroke(screen.getByLabelText("Fallback brawler"), "TARAB"); // a second debounce
    first.resolve(jsonResponse({ detail: "adb did not answer" }, 503));
    await tick(600);

    expect(puts(calls)).toEqual([
      {
        mode: "ladder",
        prestige_start: "highest",
        goal_trophies: 1000,
        maxed_fallback: "TARA",
        quest_aware: false,
      },
    ]);
    expect(screen.queryByLabelText("Fallback brawler")).not.toBeInTheDocument();
  });

  it("drops a goal typed while the save before it was in flight and failed", async () => {
    const body = makePlan();
    const first = deferred();
    let sent = 0;
    const { calls } = stubFetch((url, init) => {
      if (url !== PLAN) throw new Error(`unstubbed request: ${url}`);
      if (init?.method !== "PUT") return jsonResponse(body);
      sent += 1;
      return sent === 1
        ? first.promise
        : jsonResponse({ ...body, ...JSON.parse(String(init.body)) });
    });
    renderWithProviders(<FarmPlan name="Pie64" />);
    await tick(0);

    keystroke(screen.getByLabelText("Goal"), "850");
    await tick(500);
    expect(puts(calls)).toHaveLength(1);

    keystroke(screen.getByLabelText("Goal"), "860");
    first.resolve(jsonResponse({ detail: "adb did not answer" }, 503));
    await tick(600);

    expect(puts(calls)).toEqual([
      {
        mode: "ladder",
        prestige_start: "highest",
        goal_trophies: 850,
        maxed_fallback: null,
        quest_aware: false,
      },
    ]);
    expect(screen.getByLabelText("Goal")).toHaveValue(1000); // the plan's own value is back
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
