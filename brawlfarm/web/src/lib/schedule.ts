/**
 * The schedule bar's arithmetic, kept out of the component so a block that looks wrong
 * can be argued about with numbers. One pure function over a payload and a stamp: no
 * clock, no DOM, no React.
 */
import type { SchedulePayload } from "../api/types";
import { count } from "./copy";
import { plural } from "./format";
import { hhmm } from "./time";

export type BlockState = "past" | "active" | "future";
/** `label` is the block's wall-clock span, "14:00 to 15:30", so colour never has to
 * carry it on its own. */
export type Block = {
  leftPct: number;
  widthPct: number;
  state: BlockState;
  label: string;
};
export type Tick = { hour: number; leftPct: number };
/** `description` is the whole bar in one sentence; the component prints it and never
 * assembles it, so the wording is testable without React. */
export type Timeline = {
  blocks: Block[];
  nowPct: number;
  ticks: Tick[];
  description: string;
};

const DAY_MS = 24 * 60 * 60 * 1000;
const TICK_HOURS = [0, 6, 12, 18, 24];
// The bar is always the whole calendar day, said in words rather than as 00:00 to 24:00.
const DAY_SPAN = "Midnight to midnight.";

/**
 * Midnight of the local calendar day `iso` falls in. The API writes its stamps with no
 * zone offset, which JavaScript reads as local time, so this stays in one zone
 * throughout and never has to think about UTC.
 */
function dayStart(iso: string): number {
  const d = new Date(iso);
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

function clamp(pct: number): number {
  return Math.max(0, Math.min(100, pct));
}

/**
 * The schedule bar's geometry: one block per session as a percentage of the day the
 * payload's `now` sits in, the now line, and the four-hourly ticks. A session that runs
 * past midnight is clipped to the end of the day, and one that falls entirely outside it
 * (a stale payload from yesterday) is dropped rather than drawn at zero width.
 */
export function timeline(payload: SchedulePayload, nowIso: string): Timeline {
  const start = dayStart(payload.now);
  const now = new Date(nowIso).getTime();
  const pct = (ms: number): number => ((ms - start) / DAY_MS) * 100;

  const blocks: Block[] = [];
  for (const session of payload.sessions) {
    const from = new Date(session.start).getTime();
    const to = new Date(session.end).getTime();
    if (!Number.isFinite(from) || !Number.isFinite(to) || to <= from) continue;
    const left = clamp(pct(from));
    const right = clamp(pct(to));
    if (right <= left) continue;
    blocks.push({
      leftPct: left,
      widthPct: right - left,
      state: now >= to ? "past" : now >= from ? "active" : "future",
      // From the session's own stamps rather than the clipped percentages: a block cut
      // off at midnight still states the end it really has.
      label: `${hhmm(session.start)} to ${hhmm(session.end)}`,
    });
  }
  const running = blocks.filter((block) => block.state === "active").length;
  return {
    blocks,
    nowPct: clamp(pct(now)),
    ticks: TICK_HOURS.map((hour) => ({ hour, leftPct: (hour / 24) * 100 })),
    description: `${DAY_SPAN} ${plural(blocks.length, "session")} drawn, ${count(running)} running now.`,
  };
}
