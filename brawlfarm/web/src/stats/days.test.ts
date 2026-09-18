/** The day roll-up: one row per local calendar day, the net of each day read off the
 * running total, and a series that sat out a day carrying its last total forward. */
import { describe, expect, it } from "vitest";

import { rollUpDays } from "./days";
import type { StatsSeries } from "../api/types";

/** Two instances over three local days. The stamps from the API carry no timezone and
 * mean local already, so 23:30 and 00:30 are two days whatever the machine is set to.
 * Pie64_1 has no game at all on the 13th. */
const SERIES: StatsSeries[] = [
  {
    instance: "Pie64",
    points: [
      { t: "2026-09-12T21:00:00", cum: 12 },
      { t: "2026-09-12T23:30:00", cum: 20 },
      { t: "2026-09-13T00:30:00", cum: 30 },
      { t: "2026-09-14T10:00:00", cum: 25 },
    ],
  },
  {
    instance: "Pie64_1",
    points: [
      { t: "2026-09-12T22:00:00", cum: -3 },
      { t: "2026-09-14T09:00:00", cum: 7 },
    ],
  },
];

describe("rollUpDays", () => {
  it("returns one row per day, ascending, with the games on each", () => {
    expect(rollUpDays(SERIES).map((row) => [row.date, row.games])).toEqual([
      ["2026-09-12", 3],
      ["2026-09-13", 1],
      ["2026-09-14", 2],
    ]);
  });

  it("reads the net off the running total, not off the games", () => {
    const rows = rollUpDays(SERIES);
    expect(rows[1].net).toBe(rows[1].cum - rows[0].cum);
    expect(rows[1].net).toBe(10);
  });

  it("sums the last total of every series on the last day", () => {
    const rows = rollUpDays(SERIES);
    expect(rows[rows.length - 1].cum).toBe(25 + 7);
  });

  it("carries a series with no game that day forward at its last total", () => {
    // Pie64_1 played nothing on the 13th, so its own -3 is still in that day total.
    expect(rollUpDays(SERIES)[1].cum).toBe(30 - 3);
  });

  it("answers nothing for no series and for series with no points", () => {
    expect(rollUpDays([])).toEqual([]);
    expect(rollUpDays([{ instance: "Pie64", points: [] }])).toEqual([]);
  });

  it("gives a single point one row whose net is its own total", () => {
    expect(
      rollUpDays([{ instance: "Pie64", points: [{ t: "2026-09-12T21:00:00", cum: 12 }] }]),
    ).toEqual([{ date: "2026-09-12", games: 1, net: 12, cum: 12 }]);
  });
});
