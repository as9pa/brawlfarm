/** The feed's day dividers: what a day is called and where the dividers land in a list
 * that runs past midnight. */
import { describe, expect, it } from "vitest";

import { dayLabel, withDays } from "./feedDays";

const NOW = "2026-09-17T09:30:00";

describe("dayLabel", () => {
  it("names today and yesterday, and dates anything older", () => {
    expect(dayLabel("2026-09-17T00:05:00", NOW)).toBe("Today");
    expect(dayLabel("2026-09-16T23:59:00", NOW)).toBe("Yesterday");
    expect(dayLabel("2026-09-15T12:00:00", NOW)).toBe("Sep 15");
  });
});

describe("withDays", () => {
  it("opens a same-day list with one divider", () => {
    const rows = [{ ts: "2026-09-17T08:00:00" }, { ts: "2026-09-17T09:00:00" }];
    expect(withDays(rows, NOW)).toEqual([
      { kind: "day", label: "Today" },
      { kind: "row", record: rows[0] },
      { kind: "row", record: rows[1] },
    ]);
  });

  it("starts a new divider at every change of day, in order", () => {
    const rows = [
      { ts: "2026-09-16T23:50:00" },
      { ts: "2026-09-17T00:10:00" },
      { ts: "2026-09-17T00:20:00" },
    ];
    expect(withDays(rows, NOW).map((item) => (item.kind === "day" ? item.label : "row"))).toEqual([
      "Yesterday",
      "row",
      "Today",
      "row",
      "row",
    ]);
  });

  it("answers an empty list with no dividers", () => {
    expect(withDays([], NOW)).toEqual([]);
  });
});
