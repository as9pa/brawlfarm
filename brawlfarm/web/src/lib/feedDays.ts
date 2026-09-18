/** The feed's day dividers. A session that runs overnight writes "19:05:40" twice with a
 * day between them, so the list says which day each run of lines belongs to before the
 * clock stamps start again. Pure: the caller passes the moment it calls "now". */
import { monthDay } from "./format";
import { dayStart } from "./schedule";

export type FeedDay<T> = { kind: "day"; label: string } | { kind: "row"; record: T };

/** Midnight of the day before `at`, through the Date constructor rather than a subtraction
 * of 24 hours, which is the wrong length on the two days a year the clocks move. */
function yesterdayStart(at: number): number {
  const d = new Date(at);
  return new Date(d.getFullYear(), d.getMonth(), d.getDate() - 1).getTime();
}

/** What to call the calendar day `iso` falls in, read from `nowIso`. */
export function dayLabel(iso: string, nowIso: string): string {
  const day = dayStart(iso);
  const today = dayStart(nowIso);
  if (day === today) return "Today";
  if (day === yesterdayStart(today)) return "Yesterday";
  return monthDay(iso);
}

/** The list with one divider in front of every run of rows from the same local day,
 * including in front of the first row. The rows keep their order and their identity. */
export function withDays<T extends { ts: string }>(records: T[], nowIso: string): FeedDay<T>[] {
  const out: FeedDay<T>[] = [];
  let day: number | null = null;
  for (const record of records) {
    const start = dayStart(record.ts);
    if (start !== day) {
      out.push({ kind: "day", label: dayLabel(record.ts, nowIso) });
      day = start;
    }
    out.push({ kind: "row", record });
  }
  return out;
}
