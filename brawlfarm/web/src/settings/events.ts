/**
 * The seven alert kinds as Settings names them, in the order the section lists them.
 *
 * Deliberately not `lib/states.ts`'s ALERT_KIND_LABELS: that map names an alert that has
 * already happened ("Recover", "Recalibrate") and has no entry for `stop`, while this one
 * names a thing to be told about ("Recovery", "Recalibration needed", "Stopped"). Unifying
 * them would make one of the two read wrong. The kinds themselves are
 * `brawlfarm/core/notify.py`'s ALERT_KINDS, which is a set: the order lives here.
 */
export const NOTIFY_EVENT_LABELS: readonly { kind: string; label: string }[] = [
  { kind: "crash", label: "Crash" },
  { kind: "recover", label: "Recovery" },
  { kind: "offline", label: "Instance offline" },
  { kind: "wrong_mode", label: "Wrong mode" },
  { kind: "recalibrate", label: "Recalibration needed" },
  { kind: "stop", label: "Stopped" },
  { kind: "bad_resolution", label: "Wrong resolution" },
];
