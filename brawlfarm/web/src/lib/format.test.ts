/**
 * Signed trophy deltas, grouped figures, clock strings and the singular nouns the feed
 * sentences need.
 *
 * The locale is pinned rather than inferred: every formatter in format.ts names en-US, so
 * these assertions hold on a machine whose own locale groups with a dot or writes the day
 * first. The timezone is the host's, which is why the clock cases use a stamp with no
 * zone: the API writes local wall clock and the formatter reads it back as local wall
 * clock.
 */
import { describe, expect, it } from "vitest";

import { clock, dateTime, monthDay, num, ordinal, plural, signed, signedOne } from "./format";

describe("num", () => {
  it("groups the thousands and leaves zero and a negative readable", () => {
    expect(num(12345)).toBe("12,345");
    expect(num(0)).toBe("0");
    expect(num(-1234567)).toBe("-1,234,567");
  });
});

describe("monthDay", () => {
  it("writes the short month and the day, and nothing for a bad stamp", () => {
    expect(monthDay("2026-09-15T12:00:00")).toBe("Sep 15");
    expect(monthDay("not a stamp")).toBe("");
  });
});

describe("signed", () => {
  it("puts a plus on a gain and leaves a plain zero alone", () => {
    expect(signed(86)).toBe("+86");
    expect(signed(-12)).toBe("-12");
    expect(signed(0)).toBe("0");
    expect(signed(-0)).toBe("0");
  });

  it("groups a four-figure delta the same way num does", () => {
    expect(signed(1250)).toBe("+1,250");
    expect(signed(-1250)).toBe("-1,250");
  });
});

describe("clock", () => {
  it("writes a 24-hour wall clock with both fields padded", () => {
    expect(clock("2026-09-17T05:25:00")).toBe("05:25");
    expect(clock("2026-09-17T20:18:00")).toBe("20:18");
    // Midnight is 00, never 24: the h23 cycle is named rather than left to the locale.
    expect(clock("2026-09-17T00:07:00")).toBe("00:07");
  });

  it("answers the empty string for a stamp it cannot read", () => {
    expect(clock("not a time")).toBe("");
    expect(clock("")).toBe("");
  });
});

describe("dateTime", () => {
  it("puts the day in front of the same wall clock", () => {
    expect(dateTime("2026-09-17T05:25:00")).toBe("Sep 17, 05:25");
  });

  it("answers the empty string for a stamp it cannot read", () => {
    expect(dateTime("not a time")).toBe("");
  });
});

describe("plural", () => {
  it("drops the s at one", () => {
    expect(plural(1, "game")).toBe("1 game");
    expect(plural(3, "game")).toBe("3 games");
    expect(plural(0, "skin")).toBe("0 skins");
  });

  it("signs an average to one decimal and leaves zero unsigned", () => {
    expect(signedOne(11.74)).toBe("+11.7");
    expect(signedOne(-3.6)).toBe("-3.6");
    expect(signedOne(0)).toBe("0.0");
  });

  it("names a placement as an ordinal", () => {
    expect([1, 2, 3, 4, 5, 10, 11, 12, 13, 21, 22, 23].map(ordinal)).toEqual([
      "1st", "2nd", "3rd", "4th", "5th", "10th", "11th", "12th", "13th", "21st", "22nd", "23rd",
    ]);
  });
});
