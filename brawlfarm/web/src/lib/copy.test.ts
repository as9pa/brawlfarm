/** The glossary: grouped counts, mode names, window sizes and the empty-state words. */
import { describe, expect, it } from "vitest";

import { ELLIPSIS, REQUIRED_SIZE, count, modeName, sentence, sizeWords } from "./copy";

describe("count", () => {
  it("groups thousands", () => {
    expect(count(110738)).toBe("110,738");
  });
});

describe("modeName", () => {
  it("spells a known mode the way the game does", () => {
    expect(modeName("trioShowdown")).toBe("Trio Showdown");
  });

  it("splits a mode it has never seen into capitalised words", () => {
    expect(modeName("someNewMode")).toBe("Some New Mode");
  });

  it("says nothing was recorded rather than leaving a gap", () => {
    expect(modeName(null)).toBe("Not recorded");
    expect(modeName("")).toBe("Not recorded");
  });
});

describe("sizeWords", () => {
  it("writes a size as words", () => {
    expect(sizeWords(1280, 720)).toBe("1280 by 720");
  });

  it("is empty when either side is not a finite number", () => {
    expect(sizeWords(1600, null)).toBe("");
    expect(sizeWords("1600", 900)).toBe("");
    expect(sizeWords(1600, Number.NaN)).toBe("");
  });
});

describe("REQUIRED_SIZE", () => {
  it("is the window size the farm needs, with no x in it", () => {
    expect(REQUIRED_SIZE).toBe("1600 by 900");
    expect(REQUIRED_SIZE).not.toContain("x");
  });
});

describe("sentence", () => {
  it("upper-cases the first character and leaves the rest", () => {
    expect(sentence("dnd off failed")).toBe("Dnd off failed");
  });
});

describe("ELLIPSIS", () => {
  it("is one character, not three dots", () => {
    expect(ELLIPSIS.length).toBe(1);
  });
});
