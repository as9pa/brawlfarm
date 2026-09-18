/**
 * Plain names and screen buckets for the calibration page.
 *
 * A pure lookup module: no React, no Intl, no API call. The page shows anchors and tap
 * constants side by side, and both arrive as the raw identifier the bot uses, so every
 * word a reader sees is decided here.
 *
 * Nothing in this file is a coordinate or a threshold. The screen buckets exist to group
 * the page's rows, and a name this module has never seen keeps its humanised label and
 * shows up under the All filter, so a template dropped into the packaged folder later is
 * never silently hidden from every view.
 */
import { sentence } from "../lib/copy";

/** Which of the game's three screens a row belongs to. */
export type ScreenKey = "menu" | "brawlers" | "match";

export type ScreenFilter = ScreenKey | "all";

export const SCREEN_OPTIONS: readonly { value: ScreenFilter; label: string }[] = [
  { value: "menu", label: "Menu" },
  { value: "brawlers", label: "Brawlers" },
  { value: "match", label: "Match" },
  { value: "all", label: "All" },
];

/** The packaged templates in brawlfarm/core/templates. "matchmaking" reads as "Players
 * found" because that is the crop its anchor matches; the file and its threshold are
 * owner territory and unchanged. */
const TEMPLATES: Record<string, { label: string; screen: ScreenKey }> = {
  play: { label: "Play button", screen: "menu" },
  playagain: { label: "Play again button", screen: "menu" },
  proceed: { label: "Proceed button", screen: "menu" },
  exit: { label: "Exit button", screen: "menu" },
  close_x: { label: "Close X", screen: "menu" },
  skin_popup: { label: "Skin popup", screen: "menu" },
  other_device: { label: "Playing on another device notice", screen: "menu" },
  reload: { label: "Reload button", screen: "menu" },
  trio_showdown: { label: "Trio Showdown", screen: "brawlers" },
  trophy_screen: { label: "Trophy screen", screen: "brawlers" },
  trophy_brawler: { label: "Brawler trophy screen", screen: "brawlers" },
  matchmaking: { label: "Players found", screen: "match" },
  teams_left: { label: "Teams left counter", screen: "match" },
};

/** Tap constants bucket by prefix rather than by name: config.py holds about fifty and
 * they are owner territory, so a name added there should land somewhere sensible without
 * an edit here. The array order is the precedence, first match wins. */
const TAP_PREFIXES: readonly [RegExp, ScreenKey][] = [
  [/^BRAWLERS?_/, "brawlers"],
  [/^(?:ATTACK_POINT|SUPER_BUTTON|MOVE_ORIGIN|INGAME_MODAL_OK_BUTTON)$/, "match"],
  [/^DROP_/, "match"],
];

/** The tap constants the prefix rules do not claim, listed rather than defaulted: a rule
 * that swept up everything left over could not tell a menu tap from a name nobody has
 * taught the page, and screenOf owes its caller that difference. Read off the names
 * config.py exposes as taps, so a new one is unknown until it is added here. */
const MENU_TAPS: ReadonlySet<string> = new Set([
  "BUSH_SELF_POS",
  "CHOOSE_BRAWLER_CENTER_CARD",
  "CHOOSE_BRAWLER_CONFIRM",
  "CLOSE_X_BUTTON",
  "CONTINUE_BUTTON",
  "DAILY_STREAK_CLAIM",
  "DND_MUTES_CONFIRM",
  "DND_MUTE_FRIENDS_24H",
  "DND_MUTE_FRIENDS_24H_RADIO",
  "DND_MUTE_RECENT_30D",
  "DND_MUTE_RECENT_30D_RADIO",
  "DND_TEAMUP_CLOSE_X",
  "DND_TEAMUP_GEAR",
  "DND_TEAM_SLOT",
  "EXIT_BUTTON",
  "HOME_BUTTON",
  "INVITE_MUTE_BUTTON",
  "INVITE_REJECT_BUTTON",
  "MENU_BURGER",
  "MODE_BANNER",
  "PLAY_AGAIN_BUTTON",
  "PLAY_BUTTON",
  "PROCEED_BUTTON",
  "QUESTS_BUTTON",
  "QUESTS_CLOSE_BUTTON",
  "QUESTS_MEGA_CARD",
  "QUEST_PROGRESS_BAND0",
  "QUEST_REROLL_BUTTON",
  "QUEST_TITLE_BAND0",
  "RELOAD_BUTTON",
  "SAFE_DISMISS_POINT",
  "SAFE_HOLD_POINT",
  "SCID_CLOSE_X",
  "SCID_GEAR",
  "SCID_LOG_OUT",
  "SCID_SWITCH_ACCOUNT",
  "SETTINGS_SUPERCELL_ID_BTN",
  "SIDE_MENU_SETTINGS",
  "SIDE_MENU_SUPERCELL_ID",
]);

/** The names the humaniser gets wrong, either because the words are not English or
 * because the reader needs the thing named, not the variable. */
const CONSTANT_LABELS: Record<string, string> = {
  CLOSE_X_BUTTON: "Close X button",
  SAFE_DISMISS_POINT: "Safe place to tap",
  MOVE_ORIGIN: "Joystick centre",
  MATCH_THRESHOLD: "Match confidence",
  IN_MATCH_THRESHOLD: "In-match confidence",
  MATCHMAKING_THRESHOLD: "Players found confidence",
};

/** What the frame's own state word means to a reader. */
const SCREEN_STATE_LABELS: Record<string, string> = {
  disconnect: "Disconnected",
  menu: "Main menu",
  matchmaking: "Finding players",
  results: "Results screen",
  in_match: "In a match",
  trophy_screen: "Trophy screen",
  popup: "A pop-up",
  unknown: "Unknown screen",
};

/** Underscores to spaces, sentence case: enough to keep a raw identifier off the screen
 * whichever case it arrived in. */
function humanise(name: string): string {
  return sentence(name.split("_").join(" ").toLowerCase());
}

export function anchorLabel(name: string): string {
  return TEMPLATES[name]?.label ?? humanise(name);
}

export function constantLabel(name: string): string {
  return CONSTANT_LABELS[name] ?? humanise(name);
}

/** The screen a row belongs to, or null for a name that is in neither the template table,
 * the prefix rules nor the menu list. Null is "we do not know", not "menu". */
export function screenOf(name: string): ScreenKey | null {
  const template = TEMPLATES[name];
  if (template !== undefined) return template.screen;
  for (const [pattern, screen] of TAP_PREFIXES) {
    if (pattern.test(name)) return screen;
  }
  return MENU_TAPS.has(name) ? "menu" : null;
}

/** A name with no bucket passes the All filter alone, so it is visible somewhere. */
export function onScreen(name: string, filter: ScreenFilter): boolean {
  if (filter === "all") return true;
  return screenOf(name) === filter;
}

export function screenStateLabel(state: string): string {
  return SCREEN_STATE_LABELS[state] ?? humanise(state);
}
