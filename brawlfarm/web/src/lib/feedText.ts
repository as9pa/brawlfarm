/** The event-kind-to-sentence table. It exports feedText and the kinds it spells out;
 * everything else here is the table, kept out of the Feed component so that file stays
 * about scrolling. */
import type { FeedRecord } from "../api/types";
import { ELLIPSIS, REQUIRED_SIZE, count, sentence, sizeWords } from "./copy";
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
  start: "Started farming",
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

/** The fields the unlisted-kind fallback prints, in the order it prints them; score is
 * printed after them in its own words. */
const HUMAN_FIELDS = ["brawler", "reason", "target", "quest"] as const;

/** A value worth printing: a name or a number, never a flag or a nested object. */
function human(value: unknown): boolean {
  return typeof value === "string" || typeof value === "number";
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
      // The worker logs one recap when the session ends, not one per match: trophies is
      // the whole session's delta, and the "trophies" kind carries the running total. A
      // session whose end total never arrived writes trophies as null, and a delta nobody
      // measured is left out of the sentence rather than printed as zero.
      const games = num(f, "games");
      const delta = has(f, "trophies") ? `, ${signed(num(f, "trophies"))} trophies` : "";
      const skins = num(f, "skins");
      const tail = skins > 0 ? `, ${skins} ${skins === 1 ? "skin" : "skins"}` : "";
      return {
        text: `Session ended, ${games} ${games === 1 ? "game" : "games"}${delta}${tail}`,
        tone,
      };
    }
    case "trophies":
      return { text: `Trophies: ${count(num(f, "total"))}`, tone };
    case "farming":
      return { text: `Farming ${str(f, "brawler")}`, tone };
    case "select_brawler":
      return {
        text: `Brawler selected: ${str(f, "brawler")}${has(f, "goal") ? ` (goal ${str(f, "goal")})` : ""}`,
        tone,
      };
    case "quest_pick": {
      // One sentence per reason. The two reasons that picked nothing name the plan target
      // when the plan has one, and the lowest-trophy chain that runs when it does not.
      const reason = str(f, "reason");
      const using = has(f, "target") ? str(f, "target") : "the lowest-trophy pick";
      if (reason === "chosen") {
        return { text: `Quest pick: ${str(f, "quest")}, chose ${str(f, "brawler")}`, tone };
      }
      if (reason === "target_clears") {
        return { text: `Quest pick: ${str(f, "target")} already clears ${str(f, "quest")}`, tone };
      }
      if (reason === "unreadable") {
        // The screen the pick depends on was not read; the fallback is worth a warn dot.
        return { text: `Quest pick: quests screen not readable, using ${using}`, tone: "warn" };
      }
      return { text: `Quest pick: no owned brawler clears a quest, using ${using}`, tone };
    }
    case "rotate_brawler":
      return { text: `Rotated to ${str(f, "brawler")}: ${str(f, "reason")}`, tone };
    case "wrong_mode":
      return {
        text:
          f.recovered === true ? "Picked the wrong mode and switched back" : "Picked the wrong mode",
        tone,
      };
    case "skin_reward":
      return { text: `Skin reward: ${str(f, "skin")}`, tone };
    case "game_left_foreground":
      return { text: `Game left the foreground (${str(f, "pkg")})`, tone };
    case "disconnect":
      return { text: `Disconnected, reconnecting (${num(f, "count")})`, tone };
    case "recover":
      return {
        text: `Recovering from ${str(f, "reason")}, attempt ${num(f, "attempt")}${ELLIPSIS}`,
        tone,
      };
    case "recover_dismissed":
      return { text: `Recovery no longer needed: ${str(f, "reason")}`, tone };
    case "crash":
      return { text: `Crash: ${str(f, "err")}`, tone };
    case "adb_error":
      return {
        text: `ADB error: ${str(f, "err")}${has(f, "streak") ? ` (streak ${str(f, "streak")})` : ""}`,
        tone,
      };
    case "bad_resolution": {
      // Array.isArray widens an unknown to any[], so each pair is annotated back to
      // unknown and printed through sizeWords() like every other size in the panel. A
      // core version that starts sending the size it wants is honoured without an edit.
      const got: readonly unknown[] = Array.isArray(f.got) ? f.got : [];
      const need: readonly unknown[] = Array.isArray(f.need) ? f.need : [];
      const wanted = has(f, "need") ? sizeWords(need[0], need[1]) : REQUIRED_SIZE;
      return {
        text: `Wrong resolution: ${sizeWords(got[0], got[1])}. brawlfarm needs ${wanted}.`,
        tone,
      };
    }
    case "recalibrate":
      return { text: `Recalibration needed: ${str(f, "surface")}`, tone };
    case "stop":
      return {
        text: `Stopped farming: ${str(f, "reason")} (${count(num(f, "games"))} games, ${count(num(f, "minutes"))} min)`,
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
    const what = sentence(words(record.event.slice(0, -"_error".length)));
    return { text: `${what} failed: ${str(f, "err")}`, tone };
  }
  // Every kind with no sentence of its own: the event name as a sentence, then only the
  // fields a reader recognises. A boolean, an object or a key HUMAN_FIELDS does not name
  // is never printed, because the old key=value join leaked all three into the feed.
  const parts = HUMAN_FIELDS.filter((key) => human(f[key])).map((key) => str(f, key));
  if (human(f.score)) parts.push(`match ${Math.round(num(f, "score") * 100)}%`);
  const head = sentence(words(record.event));
  return { text: parts.length === 0 ? head : `${head}: ${parts.join(", ")}`, tone };
}

/** Every kind above, for the test that catches a kind losing its sentence to the fallback. */
export const HANDLED_KINDS: readonly string[] = [
  ...Object.keys(PLAIN),
  "phase",
  "games_logged",
  "recap",
  "trophies",
  "farming",
  "select_brawler",
  "quest_pick",
  "rotate_brawler",
  "wrong_mode",
  "skin_reward",
  "game_left_foreground",
  "disconnect",
  "recover",
  "recover_dismissed",
  "crash",
  "adb_error",
  "bad_resolution",
  "recalibrate",
  "stop",
  "game_closed",
  "account_maxed",
  "maxed_fallback_switch",
  "step",
];
