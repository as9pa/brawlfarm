/**
 * The panel's word-and-colour vocabulary.
 *
 * Colour alone never carries meaning, so every mapping here comes in pairs: a word for
 * the reader and a tone for the dot beside it. The tone names match the theme's colour
 * tokens, and TONE_DOT / TONE_TEXT are the only place a tone becomes a class.
 */
import type { FeedCategory, InstanceState } from "../api/types";

export type Tone = "ok" | "warn" | "bad" | "idle";

const STATE_LABELS: Record<InstanceState, string> = {
  farming: "Farming",
  starting: "Starting",
  stopping: "Stopping after this match",
  stopped: "Stopped",
  scheduled_break: "Scheduled break",
  reconnecting: "Reconnecting",
  offline: "Offline",
};

const STATE_TONES: Record<InstanceState, Tone> = {
  farming: "ok",
  starting: "idle",
  stopping: "warn",
  stopped: "idle",
  scheduled_break: "idle",
  reconnecting: "warn",
  offline: "bad",
};

const PHASE_LABELS: Record<string, string> = {
  at_menu: "at menu",
  queuing: "queuing",
  playing: "playing",
  returning: "returning",
};

const ALERT_KIND_LABELS: Record<string, string> = {
  offline: "Offline",
  crash: "Crash",
  bad_resolution: "Wrong resolution",
  recover: "Recover",
  wrong_mode: "Wrong mode",
  recalibrate: "Recalibrate",
};

const ALERT_KIND_TONES: Record<string, Tone> = {
  offline: "bad",
  crash: "bad",
  bad_resolution: "bad",
  recover: "warn",
  wrong_mode: "warn",
  recalibrate: "warn",
};

const FEED_TONES: Record<FeedCategory, Tone> = {
  matches: "ok",
  interrupts: "warn",
  errors: "bad",
  other: "idle",
};

export const TONE_DOT: Record<Tone, string> = {
  ok: "bg-ok",
  warn: "bg-warn",
  bad: "bg-bad",
  idle: "bg-idle",
};

export const TONE_TEXT: Record<Tone, string> = {
  ok: "text-ok",
  warn: "text-warn",
  bad: "text-bad",
  idle: "text-idle",
};

export function stateLabel(state: InstanceState): string {
  return STATE_LABELS[state];
}

export function stateTone(state: InstanceState): Tone {
  return STATE_TONES[state];
}

/** The state to show for an instance the supervisor has not listed yet, or one whose state
 * is a word we do not have: neither is running, and "stopped" is the honest reading of
 * that. Falling through to the first key of the table would say "Scheduled break", which
 * claims a reason nobody gave. */
export function knownState(state: string | undefined): InstanceState {
  return state !== undefined && state in STATE_LABELS ? (state as InstanceState) : "stopped";
}

/** The worker writes its own phase strings; one it has not taught us is shown as it
 * arrived, because "no status yet" would be a lie. */
export function phaseLabel(phase: string | null): string {
  if (phase === null || phase === "") return "no status yet";
  return PHASE_LABELS[phase] ?? phase;
}

export function alertKindLabel(kind: string): string {
  return ALERT_KIND_LABELS[kind] ?? kind;
}

export function alertKindTone(kind: string): Tone {
  return ALERT_KIND_TONES[kind] ?? "idle";
}

export function feedTone(category: FeedCategory): Tone {
  return FEED_TONES[category];
}
