/** Today's sessions and the three things the reader can do to them: switch the schedule
 * off, run for a few hours now, and ask for a redraw. */
import { act, fireEvent, renderHook, screen, waitFor } from "@testing-library/react";
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
    expect(screen.getByRole("button", { name: "Redraw today" })).toBeInTheDocument();
    expect(countOf(calls, "GET", SCHEDULE)).toBe(1);

    fireEvent.click(screen.getByRole("button", { name: "Redraw today" }));
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
