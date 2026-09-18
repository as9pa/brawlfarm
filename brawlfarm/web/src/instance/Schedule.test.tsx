/** Today's sessions and the three things the reader can do to them: switch the schedule
 * off, run for a few hours now, and ask for a redraw. */
import { act, fireEvent, renderHook, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Schedule } from "./Schedule";
import { resetToasts, useToasts } from "../lib/toast";
import { makeSchedule } from "../test/fixtures";
import { type FetchCall, jsonResponse, stubFetch } from "../test/http";
import { renderWithProviders } from "../test/renderWithProviders";

const SCHEDULE = "/api/instances/Pie64/schedule";
const START = "/api/instances/Pie64/start";

function toastMessages(): string[] {
  return renderHook(() => useToasts()).result.current.map((item) => item.message);
}

/** api<T>() sends a GET as fetch(path, {}), so a missing method means GET. */
function matching(calls: FetchCall[], method: string, url: string): FetchCall[] {
  return calls.filter((call) => call.url === url && (call.init?.method ?? "GET") === method);
}

function countOf(calls: FetchCall[], method: string, url: string): number {
  return matching(calls, method, url).length;
}

function lastBody(calls: FetchCall[], method: string, url: string): unknown {
  const call = matching(calls, method, url).at(-1);
  return call === undefined ? undefined : JSON.parse(String(call.init?.body));
}

function mount(body = makeSchedule()): FetchCall[] {
  return stubFetch((url) => {
    if (url === SCHEDULE) return jsonResponse(body);
    if (url === START) return jsonResponse({ ok: true }, 202);
    throw new Error(`unstubbed request: ${url}`);
  }).calls;
}

afterEach(() => {
  resetToasts();
  vi.unstubAllGlobals();
});

describe("Schedule", () => {
  it("turns the schedule off and says so", async () => {
    const calls = mount();
    renderWithProviders(<Schedule name="Pie64" />);
    await userEvent.click(await screen.findByRole("switch", { name: "Schedule on" }));
    await waitFor(() => {
      expect(countOf(calls, "PUT", SCHEDULE)).toBe(1);
    });
    expect(lastBody(calls, "PUT", SCHEDULE)).toEqual({ enabled: false });
    expect(toastMessages()).toEqual(["Schedule off"]);
  });

  it("runs for a number of hours from the row", async () => {
    const calls = mount();
    renderWithProviders(<Schedule name="Pie64" />);
    const hours = await screen.findByLabelText("Run for");
    expect(hours).toHaveAttribute("step", "0.5");
    await userEvent.clear(hours);
    await userEvent.type(hours, "3");
    await userEvent.click(screen.getByRole("button", { name: "Start" }));
    await waitFor(() => {
      expect(countOf(calls, "POST", START)).toBe(1);
    });
    expect(lastBody(calls, "POST", START)).toEqual({ hours: 3 });
    expect(toastMessages()).toEqual(["Running Pie64 for 3 h"]);
  });

  it("keeps Start out of reach below the half hour the field asks for", async () => {
    const calls = mount();
    renderWithProviders(<Schedule name="Pie64" />);
    const hours = await screen.findByLabelText("Run for");
    expect(hours).toHaveAttribute("min", "0.5");

    // fireEvent rather than userEvent: typing "0.3" a character at a time goes through
    // "0." , which a number input does not hold, so the box would never see the value
    // this case is about.
    fireEvent.change(hours, { target: { value: "0.3" } });
    expect(screen.getByRole("button", { name: "Start" })).toBeDisabled();

    fireEvent.change(hours, { target: { value: "0.5" } });
    expect(screen.getByRole("button", { name: "Start" })).toBeEnabled();
    await userEvent.click(screen.getByRole("button", { name: "Start" }));
    await waitFor(() => {
      expect(countOf(calls, "POST", START)).toBe(1);
    });
    expect(lastBody(calls, "POST", START)).toEqual({ hours: 0.5 });
  });

  it("speaks the API's own sentence when Start fails, and says nothing else", async () => {
    stubFetch((url) => {
      if (url === SCHEDULE) return jsonResponse(makeSchedule());
      if (url === START) return jsonResponse({ detail: "adb did not answer" }, 503);
      throw new Error(`unstubbed request: ${url}`);
    });
    renderWithProviders(<Schedule name="Pie64" />);
    await userEvent.click(await screen.findByRole("button", { name: "Start" }));
    // The success toast never fires, so the failure is the only line on screen.
    await waitFor(() => {
      expect(toastMessages()).toEqual(["adb did not answer"]);
    });
  });

  it("sends one write for two quick clicks on the switch", async () => {
    const calls = mount();
    renderWithProviders(<Schedule name="Pie64" />);
    const toggle = await screen.findByRole("switch", { name: "Schedule on" });
    expect(toggle).toHaveAttribute("aria-checked", "true");

    // fireEvent rather than userEvent: the second click has to land while the first
    // write is still in flight, which is the whole case.
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-checked", "false"); // it moved under the finger
    expect(toggle).toBeDisabled();

    fireEvent.click(toggle);
    await waitFor(() => {
      expect(countOf(calls, "PUT", SCHEDULE)).toBe(1);
    });
    expect(lastBody(calls, "PUT", SCHEDULE)).toEqual({ enabled: false });
    expect(toastMessages()).toEqual(["Schedule off"]);
  });

  it("puts the switch back when the write is refused", async () => {
    stubFetch((url, init) => {
      if (url !== SCHEDULE) throw new Error(`unstubbed request: ${url}`);
      if (init?.method !== "PUT") return jsonResponse(makeSchedule());
      return jsonResponse({ detail: "adb did not answer" }, 503);
    });
    renderWithProviders(<Schedule name="Pie64" />);
    const toggle = await screen.findByRole("switch", { name: "Schedule on" });
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-checked", "false"); // it moved straight away

    await waitFor(() => {
      expect(toastMessages()).toEqual(["adb did not answer"]);
    });
    expect(toggle).toHaveAttribute("aria-checked", "true"); // and went back
    expect(toggle).toBeEnabled();
  });

  it("shows an override and clears it", async () => {
    const calls = mount(
      makeSchedule({
        override: { mode: "stop", until: "2026-09-11T18:00:00", set_at: "2026-09-11T12:00:00" },
      }),
    );
    renderWithProviders(<Schedule name="Pie64" />);
    const chip = await screen.findByText("Paused until 18:00");
    expect(chip).toBeInTheDocument();
    expect(chip.textContent).not.toMatch(/\bstop\b|override/i);
    // An icon button: its aria-label is the only accessible name it has.
    await userEvent.click(screen.getByRole("button", { name: "Resume schedule" }));
    await waitFor(() => {
      expect(countOf(calls, "PUT", SCHEDULE)).toBe(1);
    });
    expect(lastBody(calls, "PUT", SCHEDULE)).toEqual({ clear_override: true });
    // The chip going away is the confirmation, so nothing is announced.
    expect(toastMessages()).toEqual([]);
  });

  it("names a run override by what it is doing", async () => {
    mount(
      makeSchedule({
        override: { mode: "run", until: "2026-09-11T07:00:00", set_at: "2026-09-11T06:00:00" },
      }),
    );
    renderWithProviders(<Schedule name="Pie64" />);
    const chip = await screen.findByText("Running until 07:00");
    expect(chip).toBeInTheDocument();
    expect(chip.textContent).not.toMatch(/\brun\b|override/i);
    expect(screen.getByRole("button", { name: "Resume schedule" })).toBeInTheDocument();
  });

  it("says so when the day has not been drawn", async () => {
    mount(makeSchedule({ sessions: [], plan_date: null }));
    renderWithProviders(<Schedule name="Pie64" />);
    expect(
      await screen.findByText(
        "No sessions drawn yet. brawlfarm draws today’s sessions within a minute.",
      ),
    ).toBeInTheDocument();
  });
  it("groups the bar under one sentence that says what the day holds", async () => {
    mount();
    renderWithProviders(<Schedule name="Pie64" />);
    const figure = await screen.findByTestId("schedule-figure");
    expect(figure).toHaveAttribute("role", "group");
    expect(figure).toHaveAttribute(
      "aria-label",
      "Midnight to midnight. 3 sessions drawn, 1 running now.",
    );
    // Not an image: role="img" would prune the blocks inside it.
    expect(screen.getByTestId("schedule-bar")).not.toHaveAttribute("role");
    expect(screen.getByTestId("schedule-now")).toBeInTheDocument();
  });

  it("keeps every block's span in the accessibility tree on a wide window", async () => {
    mount();
    renderWithProviders(<Schedule name="Pie64" />);
    // The text list beside it is display none on a desk, so these spans are the only
    // per-session wording a screen reader has there.
    const bar = await screen.findByTestId("schedule-bar");
    for (const span of ["09:00 to 11:00", "13:30 to 15:00", "19:00 to 20:30"]) {
      expect(within(bar).getByText(span)).toHaveClass("sr-only");
    }
  });

  it("labels every block with its span and prints the hours under the bar", async () => {
    mount();
    renderWithProviders(<Schedule name="Pie64" />);
    const bar = await screen.findByTestId("schedule-bar");
    const titles = [...bar.querySelectorAll("[title]")].map((el) =>
      el.getAttribute("title"),
    );
    expect(titles).toEqual(["09:00 to 11:00", "13:30 to 15:00", "19:00 to 20:30"]);
    // The same span again for a reader who cannot see the block.
    expect(bar.textContent).toContain("13:30 to 15:00");
    for (const hour of ["0", "6", "12", "18", "24"]) {
      expect(screen.getByTestId(`schedule-hour-${hour}`)).toHaveTextContent(hour);
    }
  });

  it("names the four bar states and says the times are local", async () => {
    mount();
    renderWithProviders(<Schedule name="Pie64" />);
    const legend = await screen.findByTestId("schedule-legend");
    expect([...legend.querySelectorAll("li")].map((li) => li.textContent)).toEqual([
      "Past",
      "Running now",
      "Later today",
      "Now",
    ]);
    expect(screen.getByText("Times are local.")).toBeInTheDocument();
  });

  it("lists the sessions as text for a narrow window", async () => {
    mount();
    renderWithProviders(<Schedule name="Pie64" />);
    const list = await screen.findByTestId("schedule-list");
    expect(list.className).toContain("min-[1100px]:hidden");
    expect([...list.querySelectorAll("li")].map((li) => li.textContent)).toEqual([
      "09:00 to 11:00Past",
      "13:30 to 15:00Running now",
      "19:00 to 20:30Later today",
    ]);
  });

  it("explains Run for and holds Start back outside half an hour to 12 hours", async () => {
    mount();
    renderWithProviders(<Schedule name="Pie64" />);
    const hours = await screen.findByLabelText("Run for");
    expect(hours).toHaveAttribute("max", "12");
    expect(hours).toHaveAttribute("inputmode", "decimal");
    expect(
      screen.getByText("Starts now and ignores the schedule for this long."),
    ).toBeInTheDocument();

    fireEvent.change(hours, { target: { value: "13" } });
    expect(screen.getByRole("alert")).toHaveTextContent("Half an hour to 12 hours");
    expect(screen.getByRole("button", { name: "Start" })).toBeDisabled();

    fireEvent.change(hours, { target: { value: "12" } });
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByRole("button", { name: "Start" })).toBeEnabled();
  });

  it("says nothing about the range for an empty box and still holds Start back", async () => {
    mount();
    renderWithProviders(<Schedule name="Pie64" />);
    const hours = await screen.findByLabelText("Run for");

    fireEvent.change(hours, { target: { value: "" } });
    // An empty box is not a wrong number, so it is told nothing.
    expect(screen.queryByText("Half an hour to 12 hours")).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
    expect(hours).not.toHaveAttribute("aria-invalid");

    const start = screen.getByRole("button", { name: "Start" });
    expect(start).toBeDisabled();
    expect(start).toHaveAttribute("title", "Enter a number of hours");
  });

  it("sends one start for two quick clicks, because Start waits for its own write", async () => {
    let release: () => void = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    const calls = stubFetch(async (url) => {
      if (url === SCHEDULE) return jsonResponse(makeSchedule());
      if (url === START) {
        await gate;
        return jsonResponse({ ok: true }, 202);
      }
      throw new Error(`unstubbed request: ${url}`);
    }).calls;
    renderWithProviders(<Schedule name="Pie64" />);
    const start = await screen.findByRole("button", { name: "Start" });

    // fireEvent rather than userEvent: the second click has to land while the first
    // request is still in flight, which is the whole case.
    fireEvent.click(start);
    await waitFor(() => {
      expect(start).toBeDisabled();
    });
    fireEvent.click(start);
    release();
    await waitFor(() => {
      expect(start).toBeEnabled();
    });
    expect(countOf(calls, "POST", START)).toBe(1);
  });

  it("sends one draw for two quick clicks on Draw new sessions", async () => {
    let release: () => void = () => {};
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    const calls = stubFetch(async (url, init) => {
      if (url !== SCHEDULE) throw new Error(`unstubbed request: ${url}`);
      if (init?.method !== "PUT") return jsonResponse(makeSchedule());
      await gate;
      return jsonResponse(makeSchedule());
    }).calls;
    renderWithProviders(<Schedule name="Pie64" />);
    const draw = await screen.findByRole("button", { name: "Draw new sessions" });

    fireEvent.click(draw);
    await waitFor(() => {
      expect(draw).toBeDisabled();
    });
    fireEvent.click(draw);
    release();
    await waitFor(() => {
      expect(draw).toBeEnabled();
    });
    expect(countOf(calls, "PUT", SCHEDULE)).toBe(1);
  });
});

/** Move the fake clock on with React's own work inside act, so a timer that fires and the
 * request it sends both settle before the next assertion. */
async function tick(ms: number): Promise<void> {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

describe("Schedule redraw", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    resetToasts();
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("asks again 2 s and 10 s later, because the draw happens on the supervisor tick", async () => {
    const calls = mount();
    renderWithProviders(<Schedule name="Pie64" />);
    // fireEvent rather than userEvent: userEvent awaits testing-library's async wrapper,
    // which drains the queue with a real setTimeout that fake timers never run. The
    // panel's own fetch settles on the fake clock, so it needs a tick of its own.
    await tick(0);
    expect(screen.getByRole("button", { name: "Draw new sessions" })).toBeInTheDocument();
    expect(countOf(calls, "GET", SCHEDULE)).toBe(1);

    fireEvent.click(screen.getByRole("button", { name: "Draw new sessions" }));
    await tick(0);
    expect(lastBody(calls, "PUT", SCHEDULE)).toEqual({ redraw: true });
    expect(toastMessages()).toEqual([
      "Redrawing today… new sessions appear within a minute.",
    ]);
    // Every patch invalidates the key, so the PUT has already asked once by itself. The
    // two timers are what this test is about, so count from there.
    const asked = countOf(calls, "GET", SCHEDULE);

    await tick(2000);
    expect(countOf(calls, "GET", SCHEDULE)).toBe(asked + 1);
    await tick(8000);
    expect(countOf(calls, "GET", SCHEDULE)).toBe(asked + 2);
  });

  it("asks again every 15 s, because nothing on this route arrives over the stream", async () => {
    const calls = mount();
    renderWithProviders(<Schedule name="Pie64" />);
    await tick(0);
    expect(countOf(calls, "GET", SCHEDULE)).toBe(1);

    await tick(14_999);
    expect(countOf(calls, "GET", SCHEDULE)).toBe(1);
    await tick(1);
    expect(countOf(calls, "GET", SCHEDULE)).toBe(2);
    await tick(15_000);
    expect(countOf(calls, "GET", SCHEDULE)).toBe(3);
  });
});
