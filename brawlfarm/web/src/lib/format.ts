/**
 * Number and time formatting: signed deltas, grouped figures, clock strings, and nouns
 * that agree with their count.
 *
 * Every formatter is built once at module scope and pinned to en-US. These run in table
 * cells and chart tooltips, so one per row is a cost the panel pays on every repaint, and
 * a figure that groups with a dot on one machine and a comma on the next is not a shared
 * house style. There is one formatter per shape and no second one: `num`, `dateTime` and
 * `monthDay` are the copy and time modules' own formatters under the names the kit uses.
 */

export { count as num } from "./copy";
export { dayTime as dateTime, monthDay } from "./time";

/** "exceptZero" is the whole point: a gain gets its plus, a loss keeps its minus, and
 * zero stays a bare "0" rather than a "+0" that reads as a gain of nothing. */
const SIGNED = new Intl.NumberFormat("en-US", { signDisplay: "exceptZero" });

/** The h23 cycle is named rather than left to en-US, which would otherwise write midnight
 * as 24:00 under a bare hour12: false. */
const CLOCK = new Intl.DateTimeFormat("en-US", {
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

/** The same sign rule held to one decimal, for averages: "+11.7", "-3.6". */
const SIGNED_ONE = new Intl.NumberFormat("en-US", {
  signDisplay: "exceptZero",
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

export function signed(n: number): string {
  return SIGNED.format(n);
}

export function signedOne(n: number): string {
  return SIGNED_ONE.format(n);
}

/** A finishing place as it is said: 1st, 2nd, 3rd, 4th, 11th, 12th, 13th, 21st. */
export function ordinal(n: number): string {
  const teen = n % 100;
  if (teen >= 11 && teen <= 13) return `${n}th`;
  const suffix = ["th", "st", "nd", "rd"][n % 10] ?? "th";
  return `${n}${suffix}`;
}

/** Local wall-clock time; the API's stamps have no timezone and mean local already. An
 * unreadable stamp answers the empty string rather than throwing, the same as time.ts. */
export function clock(iso: string): string {
  const at = new Date(iso);
  if (Number.isNaN(at.getTime())) return "";
  return CLOCK.format(at);
}

export function plural(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? "" : "s"}`;
}
