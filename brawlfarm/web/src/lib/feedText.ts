/** The event-kind-to-sentence table. Its one export is feedText; everything else here is
 * the table, kept out of the Feed component so that file stays about scrolling. */
import type { FeedRecord } from "../api/types";
import { signed } from "./format";
import { type Tone, feedTone } from "./states";

type Fields = Record<string, unknown>;

const PHASES: Record<string, string> = {
  playing: "Playing",
  queuing: "Queuing for Showdown",
  at_menu: "At the menu",
  returning: "Returning to the menu",
};

/** Kinds whose whole meaning is the kind itself; the fields add nothing a reader wants. */
const PLAIN: Record<string, string> = {
  reselect_brawler: "Reselecting the brawler",
  popup_close: "Popup closed",
  team_invite_decline: "Team invite declined",
  daily_streak_claim: "Daily streak claimed",
  ceremony_cleared: "Ceremony cleared",
  ingame_modal_cleared: "In-game dialog closed",
  gas_relocate: "Moved away from the gas",
  bush_hide: "Hiding in a bush",
  start: "Worker started",
  launch_game: "Brawl Stars opened",
  dnd: "DND enabled",
  dnd_off: "DND disabled",
  mega_quest: "Mega quest activated",
};

/** The one coercion every printed value goes through: a field the worker did not write
 * leaves a gap in the sentence rather than the word "undefined". */
function show(value: unknown): string {
  return value === null || value === undefined ? "" : String(value);
}

function str(fields: Fields, key: string): string {
  return show(fields[key]);
}

function num(fields: Fields, key: string): number {
  const value = Number(fields[key]);
  return Number.isFinite(value) ? value : 0;
}

function has(fields: Fields, key: string): boolean {
  return fields[key] !== null && fields[key] !== undefined;
}

function words(event: string): string {
  return event.replaceAll("_", " ");
}

/**
 * One line of the worker's session narration as a sentence a person can read, plus the
 * colour of its dot. The core adds event kinds faster than this table does, so anything
 * unlisted degrades to the kind with its fields spelled out rather than disappearing.
 */
export function feedText(record: FeedRecord): { text: string; tone: Tone } {
  const f: Fields = record.fields ?? {};
  // The chip a line sits under decides its dot colour; lib/states.ts owns that mapping.
  const tone = feedTone(record.category);
  const plain = PLAIN[record.event];
  if (plain !== undefined) return { text: plain, tone };

  switch (record.event) {
    case "phase": {
      const to = str(f, "to");
      return { text: PHASES[to] ?? `Phase ${to}`, tone };
    }
    case "games_logged": {
      const n = num(f, "count");
      return { text: `Logged ${n} ${n === 1 ? "game" : "games"}`, tone };
    }
    case "recap": {
      // recap.trophies is the session delta; the "trophies" kind carries the total.
      const skins = num(f, "skins");
      const tail = skins > 0 ? `, ${skins} ${skins === 1 ? "skin" : "skins"}` : "";
      return { text: `Match ended, ${signed(num(f, "trophies"))} trophies${tail}`, tone };
    }
    case "trophies":
      return { text: `Trophies: ${num(f, "total")}`, tone };
    case "farming":
      return { text: `Farming ${str(f, "brawler")}`, tone };
    case "select_brawler":
      return {
        text: `Brawler selected: ${str(f, "brawler")}${has(f, "goal") ? ` (goal ${str(f, "goal")})` : ""}`,
        tone,
      };
    case "rotate_brawler":
      return { text: `Rotated to ${str(f, "brawler")}: ${str(f, "reason")}`, tone };
    case "wrong_mode":
      return {
        text: f.recovered === true ? "Wrong mode detected, switched back" : "Wrong mode detected",
        tone,
      };
    case "skin_reward":
      return { text: `Skin reward: ${str(f, "skin")}`, tone };
    case "game_left_foreground":
      return { text: `Game left the foreground (${str(f, "pkg")})`, tone };
    case "disconnect":
      return { text: `Disconnected, reconnecting (${num(f, "count")})`, tone };
    case "recover":
      return { text: `Recovering: ${str(f, "reason")}, attempt ${num(f, "attempt")}`, tone };
    case "recover_dismissed":
      return { text: `Recovery dismissed: ${str(f, "reason")}`, tone };
    case "crash":
      return { text: `Crash: ${str(f, "err")}`, tone };
    case "adb_error":
      return {
        text: `ADB error: ${str(f, "err")}${has(f, "streak") ? ` (streak ${str(f, "streak")})` : ""}`,
        tone,
      };
    case "bad_resolution": {
      // Array.isArray widens an unknown to any[], so the pair is annotated back to
      // unknown and printed through show() like every other field in the table.
      const got: readonly unknown[] = Array.isArray(f.got) ? f.got : [];
      return {
        text: `Wrong resolution: ${show(got[0])} x ${show(got[1])}, need 1600 x 900`,
        tone,
      };
    }
    case "recalibrate":
      return { text: `Recalibration needed: ${str(f, "surface")}`, tone };
    case "stop":
      return {
        text: `Worker stopped: ${str(f, "reason")} (${num(f, "games")} games, ${num(f, "minutes")} min)`,
        tone,
      };
    case "game_closed":
      return { text: `Brawl Stars closed: ${str(f, "reason")}`, tone };
    case "account_maxed":
      return { text: `Every brawler is at the goal (${num(f, "goal")})`, tone };
    case "maxed_fallback_switch":
      return { text: `Switched to the maxed fallback ${str(f, "fallback")}`, tone };
    case "step":
      // The narration mirror, whose label is already a sentence. Its own status wins
      // over the category, because step always classifies as "other".
      return { text: str(f, "label"), tone: f.status === "error" ? "bad" : tone };
    default:
      break;
  }

  // Every remaining *_error kind: api_error, farmplan_error, dnd_off_error, and the ones
  // the core has not added yet.
  if (record.event.endsWith("_error")) {
    const what = words(record.event.slice(0, -"_error".length));
    return { text: `${what} failed: ${str(f, "err")}`, tone };
  }
  const rest = Object.entries(f)
    .filter(([, v]) => v !== null && v !== undefined)
    .map(([k, v]) => `${k}=${String(v)}`)
    .join(", ");
  return { text: rest === "" ? words(record.event) : `${words(record.event)}: ${rest}`, tone };
}
