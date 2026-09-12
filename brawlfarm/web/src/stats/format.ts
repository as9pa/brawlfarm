/**
 * The one clock format the stats panel reads by, so the chart axis, the crosshair, the
 * Table view and the recent games list all say the same thing.
 *
 * Today is one day long, so hh:mm alone is unambiguous there and stays. Every other range
 * spans days, where hh:mm alone lost the day: the axis read "11:53 ... 16:53" across a
 * week and the recent list looked unsorted. The month name and the order of the parts are
 * the browser's, not ours, so "Sep 10, 08:03" is what an English reader gets and the
 * locale decides for everyone else.
 */
import type { StatsRange } from "../api/types";
import { hhmm } from "../lib/time";

const DAY_AND_TIME = new Intl.DateTimeFormat(undefined, {
  month: "short",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

/** "HH:MM" on today, "MMM D, HH:MM" on every wider range. An unparseable stamp is "",
 * the same thing hhmm answers, so a bad row draws an empty cell and not "Invalid Date". */
export function formatMoment(iso: string, range: StatsRange): string {
  if (range === "today") return hhmm(iso);
  const at = new Date(iso);
  if (Number.isNaN(at.getTime())) return "";
  return DAY_AND_TIME.format(at);
}
