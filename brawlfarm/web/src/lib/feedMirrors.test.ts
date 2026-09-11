/** The narration mirror: which step record only repeats a sentence the feed already
 * showed, and which one is the sole record of its moment. */
import { describe, expect, it } from "vitest";

import type { FeedRecord } from "../api/types";
import { makeFeedRecord } from "../test/fixtures";
import { collapseMirrors } from "./feedMirrors";

/** The worker's own event for the launch milestone: "Brawl Stars opened". */
function launch(ts: string, seq: number): FeedRecord {
  return makeFeedRecord({ ts, seq, event: "launch_game", category: "other", fields: { method: "monkey" } });
}

/** The step record datalog mirrors that milestone into, same sentence. */
function mirror(ts: string, seq: number, fields: Record<string, unknown> = {}): FeedRecord {
  return makeFeedRecord({
    ts,
    seq,
    event: "step",
    category: "other",
    fields: { step: "launch", label: "Brawl Stars opened", status: "ok", ...fields },
  });
}

function seqs(records: FeedRecord[]): number[] {
  return records.map((record) => record.seq);
}

describe("collapseMirrors", () => {
  it("hides a step whose sentence an event said a second earlier", () => {
    const kept = collapseMirrors([launch("2026-09-11T19:05:40", 1), mirror("2026-09-11T19:05:41", 2)]);
    expect(seqs(kept)).toEqual([1]);
  });

  it("shows a step whose sentence was said three seconds earlier", () => {
    const kept = collapseMirrors([launch("2026-09-11T19:05:40", 1), mirror("2026-09-11T19:05:43", 2)]);
    expect(seqs(kept)).toEqual([1, 2]);
  });

  it("hides a step that arrives before the event it mirrors", () => {
    const kept = collapseMirrors([mirror("2026-09-11T19:05:40", 1), launch("2026-09-11T19:05:41", 2)]);
    expect(seqs(kept)).toEqual([2]);
  });

  it("compares the rendered sentence, not the event", () => {
    const select = makeFeedRecord({
      ts: "2026-09-11T19:05:40",
      seq: 1,
      event: "select_brawler",
      category: "matches",
      fields: { brawler: "TARA", planned: true },
    });
    const label = { step: "brawler", label: "Brawler selected: TARA", status: "ok" };
    const other = { step: "brawler", label: "Brawler selected: SHELLY", status: "ok" };
    expect(seqs(collapseMirrors([select, mirror("2026-09-11T19:05:40", 2, label)]))).toEqual([1]);
    expect(seqs(collapseMirrors([select, mirror("2026-09-11T19:05:40", 2, other)]))).toEqual([1, 2]);
  });

  it("always shows a step that failed", () => {
    const kept = collapseMirrors([
      launch("2026-09-11T19:05:40", 1),
      mirror("2026-09-11T19:05:41", 2, { status: "error" }),
    ]);
    expect(seqs(kept)).toEqual([1, 2]);
  });

  it("shows a step no event repeats", () => {
    // The claim event reads "Daily streak claimed"; the step's label does not.
    const claim = makeFeedRecord({
      ts: "2026-09-11T19:05:40",
      seq: 1,
      event: "daily_streak_claim",
      category: "interrupts",
      fields: {},
    });
    const step = mirror("2026-09-11T19:05:40", 2, { step: "daily_reward", label: "Daily reward claimed" });
    expect(seqs(collapseMirrors([claim, step]))).toEqual([1, 2]);
    expect(seqs(collapseMirrors([step]))).toEqual([2]);
  });

  it("leaves its input alone", () => {
    const records = [launch("2026-09-11T19:05:40", 1), mirror("2026-09-11T19:05:41", 2)];
    const before = structuredClone(records);
    collapseMirrors(records);
    expect(records).toEqual(before);
  });
});
