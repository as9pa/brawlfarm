/** The calibration page's vocabulary: the thirteen packaged templates, every tap constant
 * config.py exposes, the labels the humaniser gets wrong, and the screen a frame was in. */
import { describe, expect, it } from "vitest";

import {
  SCREEN_OPTIONS,
  anchorLabel,
  constantLabel,
  onScreen,
  screenOf,
  screenStateLabel,
} from "./names";
import type { ScreenKey } from "./names";

/** The packaged templates, verified against brawlfarm/core/templates/*.png. */
const TEMPLATES: [string, string, ScreenKey][] = [
  ["play", "Play button", "menu"],
  ["playagain", "Play again button", "menu"],
  ["proceed", "Proceed button", "menu"],
  ["exit", "Exit button", "menu"],
  ["close_x", "Close X", "menu"],
  ["skin_popup", "Skin popup", "menu"],
  ["other_device", "Playing on another device notice", "menu"],
  ["reload", "Reload button", "menu"],
  ["trio_showdown", "Trio Showdown", "brawlers"],
  ["trophy_screen", "Trophy screen", "brawlers"],
  ["trophy_brawler", "Brawler trophy screen", "brawlers"],
  ["matchmaking", "Players found", "match"],
  ["teams_left", "Teams left counter", "match"],
];

/** Every name calibration.group_of calls a tap, with the bucket the prefix rules and the
 * menu list owe it. Kept as a flat table so a constant added to config.py shows up here as
 * a failure rather than as a name the page quietly drops. */
const TAPS: [string, ScreenKey][] = [
  ["BRAWLERS_BUTTON", "brawlers"],
  ["BRAWLER_FIRST_CARD", "brawlers"],
  ["BRAWLER_HEART_TOGGLE", "brawlers"],
  ["BRAWLER_QUEST_TOGGLE", "brawlers"],
  ["BRAWLER_SEARCH_FIELD", "brawlers"],
  ["BRAWLER_SELECT_BUTTON", "brawlers"],
  ["BRAWLER_SORT_LABEL", "brawlers"],
  ["ATTACK_POINT", "match"],
  ["SUPER_BUTTON", "match"],
  ["MOVE_ORIGIN", "match"],
  ["INGAME_MODAL_OK_BUTTON", "match"],
  ["BUSH_SELF_POS", "match"],
  ["CHOOSE_BRAWLER_CENTER_CARD", "menu"],
  ["CHOOSE_BRAWLER_CONFIRM", "menu"],
  ["CLOSE_X_BUTTON", "menu"],
  ["CONTINUE_BUTTON", "menu"],
  ["DAILY_STREAK_CLAIM", "menu"],
  ["DND_MUTES_CONFIRM", "menu"],
  ["DND_MUTE_FRIENDS_24H", "menu"],
  ["DND_MUTE_FRIENDS_24H_RADIO", "menu"],
  ["DND_MUTE_RECENT_30D", "menu"],
  ["DND_MUTE_RECENT_30D_RADIO", "menu"],
  ["DND_TEAMUP_CLOSE_X", "menu"],
  ["DND_TEAMUP_GEAR", "menu"],
  ["DND_TEAM_SLOT", "menu"],
  ["EXIT_BUTTON", "menu"],
  ["HOME_BUTTON", "menu"],
  ["INVITE_MUTE_BUTTON", "menu"],
  ["INVITE_REJECT_BUTTON", "menu"],
  ["MENU_BURGER", "menu"],
  ["MODE_BANNER", "menu"],
  ["PLAY_AGAIN_BUTTON", "menu"],
  ["PLAY_BUTTON", "menu"],
  ["PROCEED_BUTTON", "menu"],
  ["QUESTS_BUTTON", "menu"],
  ["QUESTS_CLOSE_BUTTON", "menu"],
  ["QUESTS_MEGA_CARD", "menu"],
  ["QUEST_PROGRESS_BAND0", "menu"],
  ["QUEST_REROLL_BUTTON", "menu"],
  ["QUEST_TITLE_BAND0", "menu"],
  ["RELOAD_BUTTON", "menu"],
  ["SAFE_DISMISS_POINT", "menu"],
  ["SAFE_HOLD_POINT", "menu"],
  ["SCID_CLOSE_X", "menu"],
  ["SCID_GEAR", "menu"],
  ["SCID_LOG_OUT", "menu"],
  ["SCID_SWITCH_ACCOUNT", "menu"],
  ["SETTINGS_SUPERCELL_ID_BTN", "menu"],
  ["SIDE_MENU_SETTINGS", "menu"],
  ["SIDE_MENU_SUPERCELL_ID", "menu"],
];

const SCREEN_STATES: [string, string][] = [
  ["disconnect", "Disconnected"],
  ["menu", "Main menu"],
  ["matchmaking", "Finding players"],
  ["results", "Results screen"],
  ["in_match", "In a match"],
  ["trophy_screen", "Trophy screen"],
  ["popup", "A pop-up"],
  ["unknown", "Unknown screen"],
];

describe("SCREEN_OPTIONS", () => {
  it("offers Menu, Brawlers, Match and All in that order", () => {
    expect(SCREEN_OPTIONS).toEqual([
      { value: "menu", label: "Menu" },
      { value: "brawlers", label: "Brawlers" },
      { value: "match", label: "Match" },
      { value: "all", label: "All" },
    ]);
  });
});

describe("the packaged templates", () => {
  it.each(TEMPLATES)("%s reads as %s on the %s screen", (name, label, screen) => {
    expect(anchorLabel(name)).toBe(label);
    expect(screenOf(name)).toBe(screen);
  });

  it("covers every packaged template", () => {
    expect(TEMPLATES).toHaveLength(13);
  });
});

describe("the tap constants", () => {
  it.each(TAPS)("%s sits on the %s screen", (name, screen) => {
    expect(screenOf(name)).toBe(screen);
  });
});

describe("constantLabel", () => {
  it.each([
    ["CLOSE_X_BUTTON", "Close X button"],
    ["SAFE_DISMISS_POINT", "Safe place to tap"],
    ["MOVE_ORIGIN", "Joystick centre"],
    ["MATCH_THRESHOLD", "Match confidence"],
    ["IN_MATCH_THRESHOLD", "In-match confidence"],
    ["MATCHMAKING_THRESHOLD", "Players found confidence"],
  ])("%s reads as %s", (name, label) => {
    expect(constantLabel(name)).toBe(label);
  });

  it("humanises a name it does not know", () => {
    expect(constantLabel("PLAY_BUTTON")).toBe("Play button");
    expect(constantLabel("SOMETHING_NEW")).toBe("Something new");
  });
});

describe("anchorLabel", () => {
  it("humanises a template added to the folder later", () => {
    expect(anchorLabel("brand_new_thing")).toBe("Brand new thing");
  });
});

describe("screenOf", () => {
  it("has no bucket for a name it has never seen", () => {
    expect(screenOf("SOMETHING_NEW")).toBeNull();
    expect(screenOf("brand_new_thing")).toBeNull();
  });
});

describe("onScreen", () => {
  it("keeps a known name under its own filter and under All", () => {
    expect(onScreen("play", "menu")).toBe(true);
    expect(onScreen("play", "match")).toBe(false);
    expect(onScreen("play", "all")).toBe(true);
  });

  it("shows an unknown name under All alone, so nothing is hidden everywhere", () => {
    expect(onScreen("SOMETHING_NEW", "menu")).toBe(false);
    expect(onScreen("SOMETHING_NEW", "brawlers")).toBe(false);
    expect(onScreen("SOMETHING_NEW", "match")).toBe(false);
    expect(onScreen("SOMETHING_NEW", "all")).toBe(true);
  });
});

describe("screenStateLabel", () => {
  it.each(SCREEN_STATES)("%s reads as %s", (state, label) => {
    expect(screenStateLabel(state)).toBe(label);
  });

  it("humanises a state the worker added later", () => {
    expect(screenStateLabel("brawl_pass_offer")).toBe("Brawl pass offer");
  });
});
