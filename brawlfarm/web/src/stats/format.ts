/**
 * The one clock format the stats panel reads by, so the chart axis, the crosshair, the
 * Table view and the recent games list all say the same thing.
 *
 * Today is one day long, so hh:mm alone is unambiguous there and stays. Every other range
 * spans days, where hh:mm alone lost the day: the axis read "11:53 ... 16:53" across a
 * week and the recent list looked unsorted. The day itself is the kit's one short date,
 * so "Sep 10, 08:03" here reads the same way the feed's day divider does.
 */
import type { StatsRange } from "../api/types";
import { monthDay } from "../lib/format";
import { hhmm } from "../lib/time";

/** "HH:MM" on today, "MMM D, HH:MM" on every wider range. An unparseable stamp is "",
 * the same thing hhmm answers, so a bad row draws an empty cell and not "Invalid Date". */
export function formatMoment(iso: string, range: StatsRange): string {
  if (range === "today") return hhmm(iso);
  const day = monthDay(iso);
  if (day === "") return "";
  return `${day}, ${hhmm(iso)}`;
}
