/** The schedule bar's geometry: where a session sits in the day, what state it is in,
 * and what happens to one that crosses midnight or belongs to yesterday. */
import { describe, expect, it } from "vitest";

import { makeSchedule } from "../test/fixtures";
import { timeline } from "./schedule";

const NOW = "2026-09-11T14:15:00";

describe("timeline", () => {
  it("places a day of three sessions against the wall clock", () => {
    // 09:00 to 11:00 is done, 13:30 to 15:00 is running, 19:00 to 20:30 is still to come.
    const t = timeline(makeSchedule(), NOW);
    expect(t.blocks).toHaveLength(3);

    expect(t.blocks[0].leftPct).toBeCloseTo(37.5, 6); // 09:00 of 24 h
    expect(t.blocks[0].widthPct).toBeCloseTo(8.333333, 5); // two hours
    expect(t.blocks[0].state).toBe("past");

    expect(t.blocks[1].leftPct).toBeCloseTo(56.25, 6); // 13:30
    expect(t.blocks[1].widthPct).toBeCloseTo(6.25, 6); // ninety minutes
    expect(t.blocks[1].state).toBe("active");

    expect(t.blocks[2].leftPct).toBeCloseTo(79.166666, 5); // 19:00
    expect(t.blocks[2].widthPct).toBeCloseTo(6.25, 6);
    expect(t.blocks[2].state).toBe("future");

    expect(t.nowPct).toBeCloseTo(59.375, 6); // 14:15
    expect(t.ticks).toEqual([
      { hour: 0, leftPct: 0 },
      { hour: 6, leftPct: 25 },
      { hour: 12, leftPct: 50 },
      { hour: 18, leftPct: 75 },
      { hour: 24, leftPct: 100 },
    ]);
  });

  it("clips a session that runs past midnight to the end of the day", () => {
    const t = timeline(
      makeSchedule({
        sessions: [{ start: "2026-09-11T22:00:00", end: "2026-09-12T01:00:00" }],
      }),
      NOW,
    );
    expect(t.blocks[0].leftPct).toBeCloseTo(91.666666, 5);
    expect(t.blocks[0].widthPct).toBeCloseTo(8.333333, 5);
    expect(t.blocks[0].state).toBe("future");
  });

  it("drops a session with no width and an undrawn day has no blocks", () => {
    const t = timeline(
      makeSchedule({
        sessions: [
          { start: "2026-09-11T10:00:00", end: "2026-09-11T10:00:00" },
          { start: "2026-09-10T22:00:00", end: "2026-09-10T23:00:00" },
        ],
      }),
      NOW,
    );
    expect(t.blocks).toHaveLength(0);
    expect(timeline(makeSchedule({ sessions: [] }), NOW).blocks).toHaveLength(0);
  });

  it("labels a block with the session's own wall-clock span", () => {
    const t = timeline(
      makeSchedule({
        sessions: [{ start: "2026-09-11T14:00:00", end: "2026-09-11T15:30:00" }],
      }),
      NOW,
    );
    expect(t.blocks[0].label).toBe("14:00 to 15:30");
  });

  it("labels a clipped session with its real end, not with midnight", () => {
    const t = timeline(
      makeSchedule({
        sessions: [{ start: "2026-09-11T22:00:00", end: "2026-09-12T01:00:00" }],
      }),
      NOW,
    );
    expect(t.blocks[0].widthPct).toBeCloseTo(8.333333, 5);
    expect(t.blocks[0].label).toBe("22:00 to 01:00");
  });

  it("describes the span, the count and whether one is running", () => {
    expect(timeline(makeSchedule(), NOW).description).toBe(
      "Midnight to midnight. 3 sessions drawn, 1 running now.",
    );
    expect(
      timeline(
        makeSchedule({
          sessions: [{ start: "2026-09-11T19:00:00", end: "2026-09-11T20:30:00" }],
        }),
        NOW,
      ).description,
    ).toBe("Midnight to midnight. 1 session drawn, 0 running now.");
  });
});
