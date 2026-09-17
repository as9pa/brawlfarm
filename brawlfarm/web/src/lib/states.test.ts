/** The panel's word-and-colour vocabulary: every instance state, every phase caption and
 * every alert kind the API can send. */
import { describe, expect, it } from "vitest";

import type { InstanceState } from "../api/types";
import { alertKindLabel, alertKindTone, feedTone, phaseLabel, stateLabel, stateTone } from "./states";

const STATES: [InstanceState, string, string][] = [
  ["farming", "Farming", "ok"],
  ["starting", "Starting", "idle"],
  ["stopping", "Stopping after this match", "warn"],
  ["stopped", "Stopped", "idle"],
  ["scheduled_break", "Scheduled break", "idle"],
  ["reconnecting", "Reconnecting", "warn"],
  ["offline", "Offline", "bad"],
];

describe("stateLabel and stateTone", () => {
  it.each(STATES)("maps %s to its word and tone", (state, label, tone) => {
    expect(stateLabel(state)).toBe(label);
    expect(stateTone(state)).toBe(tone);
  });
});

describe("phaseLabel", () => {
  it("captions the four worker phases and says so when there is no status", () => {
    expect(phaseLabel("at_menu")).toBe("At the menu");
    expect(phaseLabel("queuing")).toBe("Queuing");
    expect(phaseLabel("playing")).toBe("Playing");
    expect(phaseLabel("returning")).toBe("Returning");
    expect(phaseLabel(null)).toBe("No status yet");
    expect(phaseLabel("")).toBe("No status yet");
  });

  it("shows a phase it does not know rather than pretending there is none", () => {
    expect(phaseLabel("shopping")).toBe("shopping");
  });
});

describe("alertKindLabel and alertKindTone", () => {
  it("names the six panel alert kinds", () => {
    expect([
      alertKindLabel("offline"),
      alertKindLabel("crash"),
      alertKindLabel("bad_resolution"),
      alertKindLabel("recover"),
      alertKindLabel("wrong_mode"),
      alertKindLabel("recalibrate"),
    ]).toEqual(["Offline", "Crash", "Wrong resolution", "Recover", "Wrong mode", "Recalibrate"]);
    expect([
      alertKindTone("offline"),
      alertKindTone("crash"),
      alertKindTone("bad_resolution"),
      alertKindTone("recover"),
      alertKindTone("wrong_mode"),
      alertKindTone("recalibrate"),
    ]).toEqual(["bad", "bad", "bad", "warn", "warn", "warn"]);
  });

  it("falls back to the kind text for anything the API adds later", () => {
    expect(alertKindLabel("brand_new")).toBe("brand_new");
    expect(alertKindTone("brand_new")).toBe("idle");
  });
});

describe("feedTone", () => {
  it("colours the four feed categories", () => {
    expect([feedTone("matches"), feedTone("interrupts"), feedTone("errors"), feedTone("other")]).toEqual([
      "ok",
      "warn",
      "bad",
      "idle",
    ]);
  });
});
