/**
 * The trophy series, rolled up into one row per local calendar day.
 *
 * The API sends one point per game, each carrying the running total for its instance over
 * the whole range, so the net of a day is the difference between the totals at its two
 * ends and not a sum of anything. Reading it that way means a day never disagrees with the
 * cumulative column beside it, and the first day, whose previous total is zero, nets
 * exactly what it has.
 *
 * A series with no game on a day is not a series that lost everything: it carries its last
 * known total forward, so the total for the fleet stays the sum of where every instance
 * stood at the end of that day.
 *
 * No React, no Intl and no date arithmetic beyond reading the local calendar day off a
 * stamp: the formatting is the job of whoever draws the row.
 */
import type { StatsSeries } from "../api/types";

export interface DayRow {
  /** The local calendar day, as YYYY-MM-DD, which sorts as it reads. */
  date: string;
  games: number;
  net: number;
  cum: number;
}

/** The local calendar day of a stamp. Built by hand rather than with Intl, because this
 * is a sort key and a row key, not something a person reads. */
function dayOf(at: Date): string {
  const month = String(at.getMonth() + 1).padStart(2, "0");
  const day = String(at.getDate()).padStart(2, "0");
  return `${at.getFullYear()}-${month}-${day}`;
}

export function rollUpDays(series: StatsSeries[]): DayRow[] {
  const games = new Map<string, number>();
  /** Per series, the last total of each day it played, by the stamp on the point rather
   * than by its place in the list, so an unsorted series rolls up the same way. */
  const lastOf: Map<string, { at: number; cum: number }>[] = [];

  for (const one of series) {
    const perDay = new Map<string, { at: number; cum: number }>();
    for (const point of one.points) {
      const at = new Date(point.t);
      const ms = at.getTime();
      if (Number.isNaN(ms)) continue;
      const day = dayOf(at);
      const kept = perDay.get(day);
      if (kept === undefined || ms >= kept.at) perDay.set(day, { at: ms, cum: point.cum });
      games.set(day, (games.get(day) ?? 0) + 1);
    }
    lastOf.push(perDay);
  }

  // A series that has not played yet stands at zero, which is what its own totals count
  // from, so the fleet total on the first day is the first day of it.
  const standing = lastOf.map(() => 0);
  const rows: DayRow[] = [];
  let previous = 0;
  for (const day of Array.from(games.keys()).sort()) {
    lastOf.forEach((perDay, index) => {
      const last = perDay.get(day);
      if (last !== undefined) standing[index] = last.cum;
    });
    const cum = standing.reduce((total, one) => total + one, 0);
    rows.push({ date: day, games: games.get(day) ?? 0, net: cum - previous, cum });
    previous = cum;
  }
  return rows;
}
