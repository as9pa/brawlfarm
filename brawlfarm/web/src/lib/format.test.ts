/** Signed trophy deltas and the singular nouns the feed sentences need. */
import { describe, expect, it } from "vitest";

import { plural, signed } from "./format";

describe("signed", () => {
  it("puts a plus on a gain and leaves a plain zero alone", () => {
    expect(signed(86)).toBe("+86");
    expect(signed(-12)).toBe("-12");
    expect(signed(0)).toBe("0");
    expect(signed(-0)).toBe("0");
  });
});

describe("plural", () => {
  it("drops the s at one", () => {
    expect(plural(1, "game")).toBe("1 game");
    expect(plural(3, "game")).toBe("3 games");
    expect(plural(0, "skin")).toBe("0 skins");
  });
});
