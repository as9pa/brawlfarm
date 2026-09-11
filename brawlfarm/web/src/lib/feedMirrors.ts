/**
 * The narration mirror, hidden from the rendered feed.
 *
 * The worker logs a milestone as its own event and datalog mirrors the first one of each
 * into a "step" record whose label is the same sentence (the contract block at the top of
 * core/datalog.py), so the reader sees the moment twice. Both records are real lines of
 * the session file, so nothing is dropped from the cache and no count changes: this only
 * decides which records Feed draws.
 */
import type { FeedRecord } from "../api/types";
import { feedText } from "./feedText";

/** How far apart the pair may sit and still be the same moment. Datalog writes the mirror
 * in the same call as the event, so the real gap is milliseconds; the window is loose
 * enough for a slow write and tight enough that the same sentence later still shows. */
const WINDOW_MS = 2000;

function stamp(record: FeedRecord): number {
  return new Date(record.ts).getTime();
}

/** Index of the first stamp in an ascending list that is not before `value`. */
function lowerBound(sorted: number[], value: number): number {
  let lo = 0;
  let hi = sorted.length;
  while (lo < hi) {
    const mid = Math.floor((lo + hi) / 2);
    if (sorted[mid] < value) lo = mid + 1;
    else hi = mid;
  }
  return lo;
}

/**
 * A step record the feed has already said in other words: same rendered sentence as a
 * non-step record within the window. A step that failed is never one of these, because
 * its own status is the only place the failure appears.
 */
function isMirror(record: FeedRecord, said: Map<string, number[]>): boolean {
  const fields = record.fields ?? {};
  if (record.event !== "step" || fields.status !== "ok") return false;
  const at = stamp(record);
  if (Number.isNaN(at)) return false;
  const times = said.get(feedText(record).text);
  if (times === undefined) return false;
  const first = lowerBound(times, at - WINDOW_MS);
  return first < times.length && times[first] <= at + WINDOW_MS;
}

/**
 * The records to draw: every line except a step record that only repeats a neighbouring
 * event's sentence. A new array, built in one pass plus a sort per distinct sentence, so
 * a full 500-line list costs nothing a render notices.
 */
export function collapseMirrors(records: FeedRecord[]): FeedRecord[] {
  const said = new Map<string, number[]>();
  for (const record of records) {
    if (record.event === "step") continue;
    const at = stamp(record);
    if (Number.isNaN(at)) continue;
    const text = feedText(record).text;
    const times = said.get(text);
    if (times === undefined) said.set(text, [at]);
    else times.push(at);
  }
  for (const times of said.values()) times.sort((a, b) => a - b);
  return records.filter((record) => !isMirror(record, said));
}
