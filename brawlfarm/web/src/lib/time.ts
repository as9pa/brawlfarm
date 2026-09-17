/**
 * Clock strings. Pure functions over a millisecond stamp or an ISO string, so the tests
 * pin them without a fake clock and the components pass Date.now() in.
 */

const MINUTE_S = 60;
const HOUR_S = 3600;

/** "8 s", "3 min", "2 h": how long ago something happened, without the word "ago". */
export function since(fromMs: number, nowMs: number): string {
  const seconds = Math.max(0, Math.round((nowMs - fromMs) / 1000));
  if (seconds < MINUTE_S) return `${seconds} s`;
  if (seconds < HOUR_S) return `${Math.floor(seconds / MINUTE_S)} min`;
  return `${Math.floor(seconds / HOUR_S)} h`;
}

export function age(fromMs: number, nowMs: number): string {
  return `${since(fromMs, nowMs)} ago`;
}

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

/** Local wall-clock time; the API's stamps have no timezone and mean local already. */
export function hhmm(iso: string): string {
  const at = new Date(iso);
  if (Number.isNaN(at.getTime())) return "";
  return `${pad(at.getHours())}:${pad(at.getMinutes())}`;
}

const DAY = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric" });

/** "Sep 17, 05:25": the same wall clock as hhmm with the day in front, for a caption that
 * can still be on screen the morning after the moment it describes. */
export function dayTime(iso: string): string {
  const at = new Date(iso);
  if (Number.isNaN(at.getTime())) return "";
  return `${DAY.format(at)}, ${hhmm(iso)}`;
}

export function hhmmss(iso: string): string {
  const at = new Date(iso);
  if (Number.isNaN(at.getTime())) return "";
  return `${pad(at.getHours())}:${pad(at.getMinutes())}:${pad(at.getSeconds())}`;
}

export function duration(minutes: number): string {
  const total = Math.max(0, Math.floor(minutes));
  if (total < 60) return `${total} min`;
  return `${Math.floor(total / 60)} h ${total % 60} min`;
}

export function hoursText(h: number): string {
  return duration(Math.round(h * 60));
}
