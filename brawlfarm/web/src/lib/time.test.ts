/** The clock strings the screens print: ages, wall-clock times and durations. */
import { describe, expect, it } from "vitest";

import { age, dayTime, duration, hhmm, hhmmss, hoursText, since } from "./time";

const NOW = Date.parse("2026-09-11T20:00:00");

describe("since and age", () => {
  it("counts seconds, then minutes, then hours", () => {
    expect(since(NOW - 8_000, NOW)).toBe("8 s");
    expect(since(NOW - 59_000, NOW)).toBe("59 s");
    expect(since(NOW - 60_000, NOW)).toBe("1 min");
    expect(since(NOW - 3 * 60_000, NOW)).toBe("3 min");
    expect(since(NOW - 3_600_000, NOW)).toBe("1 h");
    expect(since(NOW - 2 * 3_600_000, NOW)).toBe("2 h");
  });

  it("never counts backwards from a clock that ran ahead", () => {
    expect(since(NOW + 5_000, NOW)).toBe("0 s");
  });

  it("adds ago", () => {
    expect(age(NOW - 8_000, NOW)).toBe("8 s ago");
    expect(age(NOW - 3 * 60_000, NOW)).toBe("3 min ago");
    expect(age(NOW - 2 * 3_600_000, NOW)).toBe("2 h ago");
  });
});

describe("hhmm and hhmmss", () => {
  it("prints local wall-clock time", () => {
    expect(hhmm("2026-09-11T20:18:00")).toBe("20:18");
    expect(hhmm("2026-09-11T09:05:00")).toBe("09:05");
    expect(hhmmss("2026-09-11T19:05:40")).toBe("19:05:40");
  });

  it("prints nothing for a stamp it cannot parse", () => {
    expect(hhmm("not a time")).toBe("");
    expect(hhmmss("")).toBe("");
  });
});

describe("duration and hoursText", () => {
  it("prints minutes under an hour and h plus min above", () => {
    expect(duration(0)).toBe("0 min");
    expect(duration(0.4)).toBe("0 min");
    expect(duration(4)).toBe("4 min");
    expect(duration(59)).toBe("59 min");
    expect(duration(60)).toBe("1 h 0 min");
    expect(duration(72)).toBe("1 h 12 min");
    expect(duration(-5)).toBe("0 min");
  });

  it("turns a fractional hour count into the same shape", () => {
    expect(hoursText(3.6667)).toBe("3 h 40 min");
    expect(hoursText(0.5)).toBe("30 min");
    expect(hoursText(0)).toBe("0 min");
  });
});

describe("dayTime", () => {
  it("carries the day in front of the wall-clock time", () => {
    expect(dayTime("2026-09-17T05:25:00")).toBe("Sep 17, 05:25");
    expect(dayTime("2026-09-11T14:15:40")).toBe("Sep 11, 14:15");
  });

  it("answers the empty string for a stamp it cannot read, the same as hhmm", () => {
    expect(dayTime("not a date")).toBe("");
  });
});
