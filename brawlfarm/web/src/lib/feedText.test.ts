/** Every event kind the core writes, one row per sentence, plus the two fallbacks for a
 * kind this table has never seen. */
import { describe, expect, it } from "vitest";

import type { FeedRecord } from "../api/types";
import { makeFeedRecord } from "../test/fixtures";
import { HANDLED_KINDS, feedText } from "./feedText";

type Row = [string, Partial<FeedRecord>, string, string];

const M = "matches";
const I = "interrupts";
const E = "errors";
const O = "other";

const ROWS: Row[] = [
  ["phase playing", { event: "phase", category: M, fields: { to: "playing" } }, "Playing", "ok"],
  ["phase queuing", { event: "phase", category: M, fields: { to: "queuing" } }, "Queuing for Showdown", "ok"],
  ["phase at_menu", { event: "phase", category: M, fields: { to: "at_menu" } }, "At the menu", "ok"],
  ["phase returning", { event: "phase", category: M, fields: { to: "returning" } }, "Returning to the menu", "ok"],
  ["phase unknown", { event: "phase", category: M, fields: { to: "results" } }, "Phase results", "ok"],
  ["games_logged one", { event: "games_logged", category: M, fields: { count: 1 } }, "Logged 1 game", "ok"],
  ["games_logged many", { event: "games_logged", category: M, fields: { count: 3 } }, "Logged 3 games", "ok"],
  ["recap plain", { event: "recap", category: M, fields: { trophies: 86, games: 12, skins: 0 } }, "Session ended, 12 games, +86 trophies", "ok"],
  ["recap one game", { event: "recap", category: M, fields: { trophies: 8, games: 1, skins: 0 } }, "Session ended, 1 game, +8 trophies", "ok"],
  ["recap negative", { event: "recap", category: M, fields: { trophies: -12, games: 4, skins: 0 } }, "Session ended, 4 games, -12 trophies", "ok"],
  ["recap without a delta", { event: "recap", category: M, fields: { trophies: null, games: 4, skins: 0 } }, "Session ended, 4 games", "ok"],
  ["recap with skins", { event: "recap", category: M, fields: { trophies: 20, games: 4, skins: 1 } }, "Session ended, 4 games, +20 trophies, 1 skin", "ok"],
  ["recap with skins plural", { event: "recap", category: M, fields: { trophies: 20, games: 4, skins: 2 } }, "Session ended, 4 games, +20 trophies, 2 skins", "ok"],
  ["trophies", { event: "trophies", category: M, fields: { total: 41120 } }, "Trophies: 41,120", "ok"],
  ["farming", { event: "farming", category: M, fields: { brawler: "NORI" } }, "Farming NORI", "ok"],
  ["select_brawler", { event: "select_brawler", category: M, fields: { brawler: "TARA", planned: true } }, "Brawler selected: TARA", "ok"],
  ["select_brawler with goal", { event: "select_brawler", category: M, fields: { brawler: "TARA", goal: 700 } }, "Brawler selected: TARA (goal 700)", "ok"],
  ["quest_pick chosen", { event: "quest_pick", category: M, fields: { reason: "chosen", brawler: "TARA", quest: "Win 4 games as TARA", target: null } }, "Quest pick: Win 4 games as TARA, chose TARA", "ok"],
  ["quest_pick target_clears", { event: "quest_pick", category: M, fields: { reason: "target_clears", brawler: "NORI", quest: "Win 4 games as NORI", target: "NORI" } }, "Quest pick: NORI already clears Win 4 games as NORI", "ok"],
  ["quest_pick no_candidate", { event: "quest_pick", category: M, fields: { reason: "no_candidate", brawler: null, quest: null, target: "NORI" } }, "Quest pick: no owned brawler clears a quest, using NORI", "ok"],
  ["quest_pick no_candidate without a target", { event: "quest_pick", category: M, fields: { reason: "no_candidate", brawler: null, quest: null, target: null } }, "Quest pick: no owned brawler clears a quest, using the lowest-trophy pick", "ok"],
  ["quest_pick unreadable", { event: "quest_pick", category: M, fields: { reason: "unreadable", brawler: null, quest: null, target: "NORI" } }, "Quest pick: quests screen not readable, using NORI", "warn"],
  ["quest_pick unreadable without a target", { event: "quest_pick", category: M, fields: { reason: "unreadable", brawler: null, quest: null, target: null } }, "Quest pick: quests screen not readable, using the lowest-trophy pick", "warn"],
  ["rotate_brawler", { event: "rotate_brawler", category: M, fields: { brawler: "SHELLY", reason: "absolute_floor" } }, "Rotated to SHELLY: absolute_floor", "ok"],
  ["reselect_brawler", { event: "reselect_brawler", category: I, fields: {} }, "Reselecting the brawler", "warn"],
  ["wrong_mode recovered", { event: "wrong_mode", category: I, fields: { score: 0.9, recovered: true } }, "Picked the wrong mode and switched back", "warn"],
  ["wrong_mode stuck", { event: "wrong_mode", category: I, fields: { score: 0.9, recovered: false } }, "Picked the wrong mode", "warn"],
  ["popup_close", { event: "popup_close", category: I, fields: {} }, "Popup closed", "warn"],
  ["team_invite_decline", { event: "team_invite_decline", category: I, fields: {} }, "Team invite declined", "warn"],
  ["daily_streak_claim", { event: "daily_streak_claim", category: I, fields: {} }, "Daily streak claimed", "warn"],
  ["ceremony_cleared", { event: "ceremony_cleared", category: I, fields: { kind: "rank_up" } }, "Ceremony cleared", "warn"],
  ["skin_reward", { event: "skin_reward", category: I, fields: { skin: "Bandita Shelly", rarity: "rare" } }, "Skin reward: Bandita Shelly", "warn"],
  ["ingame_modal_cleared", { event: "ingame_modal_cleared", category: I, fields: {} }, "In-game dialog closed", "warn"],
  ["gas_relocate", { event: "gas_relocate", category: I, fields: { target: "north", n: 2 } }, "Moved away from the gas", "warn"],
  ["bush_hide", { event: "bush_hide", category: I, fields: { target: "east" } }, "Hiding in a bush", "warn"],
  ["game_left_foreground", { event: "game_left_foreground", category: I, fields: { pkg: "com.android.settings" } }, "Game left the foreground (com.android.settings)", "warn"],
  ["disconnect", { event: "disconnect", category: I, fields: { count: 2, other_device: false } }, "Disconnected, reconnecting (2)", "warn"],
  ["recover", { event: "recover", category: I, fields: { reason: "stuck_menu", attempt: 1 } }, "Recovering from stuck_menu, attempt 1…", "warn"],
  ["recover_dismissed", { event: "recover_dismissed", category: I, fields: { reason: "stuck_menu" } }, "Recovery no longer needed: stuck_menu", "warn"],
  ["crash", { event: "crash", category: E, fields: { err: "adb did not answer" } }, "Crash: adb did not answer", "bad"],
  ["adb_error", { event: "adb_error", category: E, fields: { err: "device offline" } }, "ADB error: device offline", "bad"],
  ["adb_error with streak", { event: "adb_error", category: E, fields: { err: "device offline", streak: 3 } }, "ADB error: device offline (streak 3)", "bad"],
  ["bad_resolution", { event: "bad_resolution", category: E, fields: { got: [1920, 1080] } }, "Wrong resolution: 1920 by 1080. brawlfarm needs 1600 by 900.", "bad"],
  ["bad_resolution with a need", { event: "bad_resolution", category: E, fields: { got: [1920, 1080], need: [1600, 900] } }, "Wrong resolution: 1920 by 1080. brawlfarm needs 1600 by 900.", "bad"],
  ["bad_resolution with a malformed pair", { event: "bad_resolution", category: E, fields: { got: ["wide"] } }, "Wrong resolution. brawlfarm needs 1600 by 900.", "bad"],
  ["recalibrate", { event: "recalibrate", category: E, fields: { surface: "menu", detail: "drifted" } }, "Recalibration needed: menu", "bad"],
  ["other _error", { event: "select_brawler_error", category: E, fields: { err: "no brawler row" } }, "Select brawler failed: no brawler row", "bad"],
  ["quest_pick_error", { event: "quest_pick_error", category: E, fields: { err: "HTTP 503" } }, "Quest pick failed: HTTP 503", "bad"],
  ["api_error", { event: "api_error", category: E, fields: { where: "trophies", err: "HTTP 503" } }, "API failed: HTTP 503", "bad"],
  ["dnd_off_error", { event: "dnd_off_error", category: E, fields: { err: "no panel" } }, "DND off failed: no panel", "bad"],
  ["unlisted _error", { event: "foo_error", category: E, fields: { err: "boom" } }, "Foo failed: boom", "bad"],
  ["start", { event: "start", category: O, fields: { max_games: 40, max_minutes: 90 } }, "Started farming", "idle"],
  ["stop", { event: "stop", category: O, fields: { reason: "panel", games: 12, minutes: 47 } }, "Stopped farming: panel (12 games, 47 min)", "idle"],
  ["launch_game", { event: "launch_game", category: O, fields: { method: "monkey" } }, "Brawl Stars opened", "idle"],
  ["game_closed", { event: "game_closed", category: O, fields: { reason: "stop" } }, "Brawl Stars closed: stop", "idle"],
  ["dnd", { event: "dnd", category: O, fields: { ok: true } }, "DND enabled", "idle"],
  ["dnd_off", { event: "dnd_off", category: O, fields: { ok: true } }, "DND disabled", "idle"],
  ["mega_quest", { event: "mega_quest", category: O, fields: { activated: true } }, "Mega quest activated", "idle"],
  ["account_maxed", { event: "account_maxed", category: O, fields: { goal: 1000 } }, "Every brawler is at the goal (1000)", "idle"],
  ["maxed_fallback_switch", { event: "maxed_fallback_switch", category: O, fields: { fallback: "SHELLY" } }, "Switched to the maxed fallback SHELLY", "idle"],
  ["step ok", { event: "step", category: O, fields: { step: 2, label: "Daily streak claimed", status: "ok" } }, "Daily streak claimed", "idle"],
  ["step error", { event: "step", category: O, fields: { step: 3, label: "Brawler selected", status: "error" } }, "Brawler selected", "bad"],
  ["unknown with human fields", { event: "gas_edges_v2", category: O, fields: { edges: 4, n: 1 } }, "Gas edges v2", "idle"],
  ["unknown without fields", { event: "something_new", category: O, fields: {} }, "Something new", "idle"],
  ["unknown with the fallback's own fields", { event: "shiny_new", category: O, fields: { brawler: "TARA", recovered: true, score: 0.4567 } }, "Shiny new: TARA, match 46%", "idle"],
  ["unknown with no fields", { event: "shiny_new", category: O, fields: {} }, "Shiny new", "idle"],
];

describe("feedText", () => {
  it.each(ROWS)("%s", (_label, overrides, expected, tone) => {
    const line = feedText(makeFeedRecord(overrides));
    expect(line.text).toBe(expected);
    expect(line.tone).toBe(tone);
  });

  it("covers every event name the brief's table names", () => {
    const events = ROWS.map(([, o]) => o.event);
    expect(events.filter((e) => e === undefined)).toHaveLength(0);
    expect(ROWS).toHaveLength(66);
    expect(new Set(events).size).toBe(44); // 39 named kinds plus the five fallback cases
  });
  // Every kind that has a sentence of its own above. The API's kind list lives in Python,
  // so a kind the core adds has to be added here by hand; the *_error kinds are left out
  // because they read through the suffix fallback rather than a case of their own.
  const API_KINDS: readonly string[] = [
    "phase",
    "games_logged",
    "recap",
    "trophies",
    "farming",
    "select_brawler",
    "quest_pick",
    "rotate_brawler",
    "reselect_brawler",
    "wrong_mode",
    "popup_close",
    "team_invite_decline",
    "daily_streak_claim",
    "ceremony_cleared",
    "skin_reward",
    "ingame_modal_cleared",
    "gas_relocate",
    "bush_hide",
    "game_left_foreground",
    "disconnect",
    "recover",
    "recover_dismissed",
    "crash",
    "adb_error",
    "bad_resolution",
    "recalibrate",
    "start",
    "stop",
    "launch_game",
    "game_closed",
    "dnd",
    "dnd_off",
    "mega_quest",
    "account_maxed",
    "maxed_fallback_switch",
    "step",
  ];

  it("spells out every kind the API writes", () => {
    expect(API_KINDS.filter((kind) => !HANDLED_KINDS.includes(kind))).toEqual([]);
  });
});
