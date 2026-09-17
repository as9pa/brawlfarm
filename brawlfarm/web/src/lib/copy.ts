/**
 * The panel's glossary: the one place a shared noun is written. A count, a mode name, a
 * window size or an empty-state phrase is spelled here once and imported everywhere else,
 * so the same thing never appears under two names on two pages; `worker`, `supervisor` and
 * `tick` are process names and never appear in a string a person reads.
 */

const NUMBER = new Intl.NumberFormat("en-US");

export const ELLIPSIS = "…";
export const APOSTROPHE = "’";

export const NO_GAMES_YET = "No games yet";
export const QUEUE_EMPTY = "Queue is empty";
export const NOT_SET = "Not set";
export const NOT_YET = "Not yet";
export const NOT_STARTED = "Not started";
export const NOT_RECORDED = "Not recorded";
export const NO_BRAWLER_YET = "No brawler selected yet";

export const REQUIRED_WIDTH = 1600;
export const REQUIRED_HEIGHT = 900;

/** The game's own spelling of every mode the farm plays. */
export const MODE_NAMES: Record<string, string> = {
  soloShowdown: "Solo Showdown",
  duoShowdown: "Duo Showdown",
  trioShowdown: "Trio Showdown",
  gemGrab: "Gem Grab",
  brawlBall: "Brawl Ball",
  heist: "Heist",
  bounty: "Bounty",
  hotZone: "Hot Zone",
  knockout: "Knockout",
  ranked: "Ranked",
};

export function count(n: number): string {
  return NUMBER.format(n);
}

/** Upper-cases the first character and leaves the rest. Used by the feed fallback only. */
export function sentence(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** A mode the game added after this list was written still reads as words, not camelCase. */
export function modeName(raw: string | null): string {
  if (!raw) return NOT_RECORDED;
  if (raw in MODE_NAMES) return MODE_NAMES[raw];
  return raw
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .split(/[\s_]+/)
    .map(sentence)
    .join(" ");
}

/** A size in words, so a person never has to read "1600x900". Empty when either side is
 * missing, which lets a caller fall back to its own wording. */
export function sizeWords(w: unknown, h: unknown): string {
  if (!Number.isFinite(w) || !Number.isFinite(h)) return "";
  return `${String(w)} by ${String(h)}`;
}

export const REQUIRED_SIZE = sizeWords(REQUIRED_WIDTH, REQUIRED_HEIGHT);
