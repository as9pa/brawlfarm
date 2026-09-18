# Panel PR 7: Calibration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The Calibration page explains itself in plain words, draws a readable overlay, names every anchor and status in words, and shows the packaged thresholds with where each value came from, without one line changing under `brawlfarm/core` and without one new API field.

**Architecture:** One new module `brawlfarm/web/src/calibration/names.ts` is the single source of the plain name and the screen bucket for every template and every tap constant. `FrameOverlay` stops drawing SVG text and grows an HTML label layer plus a `screen` filter and a `highlight` pair. `AnchorTable` becomes the "What it looks for" table. `OverridesTable.tsx` is renamed `ThresholdsTable.tsx` and always lists the thresholds. `Calibration.tsx` owns the two Segmented controls, the two readout chips and the `highlight` state.

**Tech Stack:** React 19 and TypeScript under `pnpm`, vitest plus Testing Library, Python 3.13 under `uv` for the gate only.

**Spec:** the panel critique, items `cal-jargon`, `cal-overlay-clutter`, `cal-overrides-equal`, `cal-last-seen`, `cal-observe-switch`. Layout target: `W_calibration()` in the critique builder.

**Branch:** `panel/calibration`, cut from the merge of PR 3. Worktree `.claude/worktrees/phase-10`.

## Global Constraints

- No em-dashes and no emoji anywhere: prose, code, comments, tests, commit messages, pull request body.
- Never write the word bsutil or any legacy tag anywhere.
- Nothing under `brawlfarm/core` may change. Not a constant, not a template, not a threshold, not a comment. `CONTRIBUTING.md` puts never-tap logic, the 1600x900 assertion, the tap coordinates, the OCR needles and the templates behind an owner-approved calibration pull request, and this is not one.
- API changes only if a task names the endpoint and the change is additive and backward compatible. **No task in this plan changes the API.** See "Why no API field is needed" below; if an implementer thinks one is needed, stop and report rather than adding it.
- `worker`, `supervisor` and `tick` never appear in a string a person reads. Code, comments and the API keep their own names.
- Owner rulings that bind every task:
  - Calibration stays a top-level page in the rail.
  - The page opens with the plain intro in Task 2, verbatim.
  - Controls are named by outcome: "Where it taps", "What it looks for", "Both", "Record frames", "Record while I play". The words Taps, Anchors, Drift, Constant and Observe leave the labels.
  - A screen filter reduces overlay clutter; labels appear on hover or focus; crosshairs only by default.
  - The anchor table shows Name in words, Match as a percentage, Status as a word (Found, Not on this screen, Missing) and Last seen as an age.
  - The Overrides table becomes a Thresholds table that shows the packaged values with a Source column, so an empty override state is never an empty panel.
  - The Recorder and Observe cards keep their plain sentences and their caps. They are the best copy on the page. Only the one-line cap note is added.
- The implementer must not invent wording. Every string is given here before and after. If a string turns up that this plan does not list, leave it and report it.
- Per `CLAUDE.md`, code review is on: every task gets a spec-compliance and code-quality review pass on **sonnet** before it counts as complete, and the branch gets a whole-branch review on **sonnet** before its pull request opens. Findings are fixed by an implementer, then re-reviewed once.
- Conventional commit subjects with a scope (`feat(scope):`, `fix(scope):`, `refactor(scope):`, `test(scope):`). Every commit message ends with the trailers:

```
Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01E1U94d3i2jWe3tvmSRjcki
```

## The gate command block

Every task ends by running this, in this order, from the worktree root:

```
pnpm --dir brawlfarm/web typecheck
pnpm --dir brawlfarm/web test
uv run pytest -q -p no:cacheprovider
uv run ruff check .
uv run ruff format --check .
uv run python tools/scrub_check.py
```

`tools/scrub_check.py` must print `0 hit(s)`. A live pass is required for the branch (see the close-out): the page only shows scores while an instance is up.

## Blocking dependencies

This PR lands after PR 1, PR 2 and PR 3 and must not redo their work. Read the merge base before editing:

- **PR 1 (copy glossary)** created `brawlfarm/web/src/lib/copy.ts`, replaced `Calibration.tsx`'s `HINT` with the short intro "What brawlfarm sees.", and rewrote the `ObserveCard.tsx` strings (the old `OBSERVE_BLOCKED_MESSAGE` said "farming worker"; PR 1 fixed that). Task 2 **replaces the PR 1 intro string in place, in `lib/copy.ts`**. Do not add a second intro constant, and do not touch the Observe sentences beyond adding the cap note. PR 1 also shipped `lib/words.guard.test.ts`, the banned-word guard; every string this plan adds must pass it.
- **PR 2 (kit)** shipped the four `Button` variants, the four `Switch` states, the `Segmented` focus ring, and `lib/format.ts` with module-scope `Intl` helpers `num`, `signed`, `clock`, `dateTime`, plus the `t-figure` and `t-name` text roles. Use `format.ts` for every number and clock here and construct no new formatter. Use `t-figure` for the Match percentage and the threshold values and `t-name` for the instance chips; that is part of the page-adoption sweep PR 2 deferred.
- **PR 3 (one h1 per page)** turned `Calibration.tsx:116`'s `h2` into the page `h1`. Task 2 edits the paragraph under it and leaves the heading element alone. The two section headings inside the page (`Anchors` at `Calibration.tsx:220`, `Overrides` at `OverridesTable.tsx:92`) stay `h2`.

## Why no API field is needed

Both values the owner ruling worried about are already reachable, so no route changes and the "or drop the column with a note" branch never fires:

- **Last seen.** `GET /api/instances/{name}/calibration/scores` returns `at`, the frame's own mtime, at `brawlfarm/api/calibration.py:262`. `AnchorTable.tsx:40-53` already remembers the last response in which each anchor was found, in a ref, and prints `hh:mm` from a local `clock()`. Task 4 keeps the ref and changes what it stores from a formatted string to the response's epoch milliseconds, then renders `age()` from `lib/time.ts` with an absolute `title`. No field is missing; the hand-rolled clock is the whole bug.
- **Packaged thresholds.** `GET /api/calibration` already returns, per constant, `name`, `group`, `value`, `default` and `source` (`"calibration.toml"` or `"package"`), and per template `source` (`"package"` or `"override"`), `width`, `height` and `threshold`, at `brawlfarm/api/calibration.py:138-178`. `group_of` at `brawlfarm/core/calibration.py:57` already labels every `*_THRESHOLD` name `"threshold"`. Task 5 needs nothing more.
- **The screen a point belongs to** is the one thing the API does not carry, and it must not be added: deriving it server-side would put a second copy of the screen taxonomy next to `brawlfarm/core`. It lives in the web layer, in `names.ts`, tested. `tests/test_api_calibration.py` stays green untouched and is the regression guard that no route moved.

## File Structure

- `brawlfarm/web/src/calibration/names.ts`: new. Plain names and screen buckets. Task 1.
- `brawlfarm/web/src/calibration/names.test.ts`: new. Task 1.
- `brawlfarm/web/src/lib/copy.ts`: the intro string, replaced in place. Task 2.
- `brawlfarm/web/src/calibration/Calibration.tsx`: intro, the two Segmented controls, the readout chips, `highlight` state, section heading. Tasks 2, 3, 4, 5.
- `brawlfarm/web/src/calibration/FrameOverlay.tsx`: crosshairs, HTML label layer, screen filter, highlight. Task 3.
- `brawlfarm/web/src/calibration/AnchorTable.tsx`: the four columns. Task 4.
- `brawlfarm/web/src/calibration/AnchorTable.test.tsx`: new. Task 4.
- `brawlfarm/web/src/calibration/OverridesTable.tsx` renamed to `ThresholdsTable.tsx` with `git mv`, plus a new `ThresholdsTable.test.tsx`. Task 5.
- `brawlfarm/web/src/calibration/RecorderCard.tsx`, `ObserveCard.tsx`: the cap note. Task 6.
- Extended: `Calibration.test.tsx`, `FrameOverlay.test.tsx`, `RecorderCard.test.tsx`, `ObserveCard.test.tsx`.

The apostrophe in any new string is U+2019 RIGHT SINGLE QUOTATION MARK and any ellipsis is U+2026, written as the literal character.

---

### Task 1: One module for the plain names and the screen buckets

**Files:**
- Create: `brawlfarm/web/src/calibration/names.ts`
- Test: `brawlfarm/web/src/calibration/names.test.ts`

**Read first:** `brawlfarm/web/src/api/calibration.ts:15-58` for `ConstantGroup`, `CalibrationConstant` and `Anchor`; `brawlfarm/api/calibration.py:34-42` for `EXPECTED_BY_PHASE`, which is where the template-to-phase truth already lives.

**Interfaces:**

```
export type ScreenKey = "menu" | "brawlers" | "match";
export type ScreenFilter = ScreenKey | "all";
export const SCREEN_OPTIONS: readonly { value: ScreenFilter; label: string }[];
export function anchorLabel(name: string): string;
export function constantLabel(name: string): string;
export function screenOf(name: string): ScreenKey | null;
export function onScreen(name: string, filter: ScreenFilter): boolean;
```

`SCREEN_OPTIONS` is exactly `Menu`, `Brawlers`, `Match`, `All`, in that order. `screenOf` returns `null` for a name the module does not know; `onScreen` returns `true` for an unknown name only when the filter is `all`, so a template added to the packaged folder later is never silently hidden from every view. `anchorLabel` and `constantLabel` fall back to a humaniser for an unknown name: split on `_`, lowercase, capitalise the first word, so `teams_left` becomes `Teams left` and `PLAY_BUTTON` becomes `Play button`. No `Intl` here and no React import: this is a pure lookup module.

**The template table** (the thirteen packaged names, verified against `brawlfarm/core/templates/*.png`):

| name | label | screen |
| --- | --- | --- |
| `play` | Play button | menu |
| `playagain` | Play again button | menu |
| `proceed` | Proceed button | menu |
| `exit` | Exit button | menu |
| `close_x` | Close X | menu |
| `skin_popup` | Skin popup | menu |
| `other_device` | Playing on another device notice | menu |
| `reload` | Reload button | menu |
| `trio_showdown` | Trio Showdown | brawlers |
| `trophy_screen` | Trophy screen | brawlers |
| `trophy_brawler` | Brawler trophy screen | brawlers |
| `matchmaking` | Players found | match |
| `teams_left` | Teams left counter | match |

`matchmaking` is labelled "Players found" because that is the crop the current anchor matches. Do not change its threshold or its file; only the word on screen.

**The tap table** is by prefix, not by name, because `brawlfarm/core/config.py` holds about sixty of them and they are owner territory: `BRAWLER_*` and `BRAWLERS_*` are `brawlers`; `ATTACK_POINT`, `SUPER_BUTTON`, `MOVE_ORIGIN`, `INGAME_MODAL_OK_BUTTON` and any `DROP_*` are `match`; every other known name is `menu`. Write the prefix rules as an ordered array of `[RegExp, ScreenKey]` with a comment saying the order is the precedence, and give `constantLabel` a small explicit override map for the names the humaniser gets wrong: `CLOSE_X_BUTTON` to "Close X button", `SAFE_DISMISS_POINT` to "Safe place to tap", `MOVE_ORIGIN` to "Joystick centre".

- [ ] **Step 1: Write the failing tests** in `names.test.ts`: every one of the thirteen template names above maps to its exact label and screen; `screenOf("BRAWLER_FIRST_CARD")` is `brawlers`; `screenOf("ATTACK_POINT")` is `match`; `screenOf("PLAY_BUTTON")` is `menu`; `screenOf("SOMETHING_NEW")` is `null`; `onScreen("SOMETHING_NEW", "menu")` is `false` and `onScreen("SOMETHING_NEW", "all")` is `true`; `anchorLabel("brand_new_thing")` is `"Brand new thing"`.
- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement `names.ts`.**
- [ ] **Step 4: Run the gate.**

**Acceptance:** the module is pure, the thirteen packaged names are covered, an unknown name degrades to a humanised label under the All filter only, and no other file imports it yet.

**Commit:** `feat(calibration): plain names and screen buckets for anchors and taps`

---

### Task 2: The page explains itself, and the controls are named by outcome

**Files:**
- Modify: `brawlfarm/web/src/lib/copy.ts` (the Calibration intro string PR 1 added)
- Modify: `brawlfarm/web/src/calibration/Calibration.tsx` (`HINT` at 40-41, `SHOW_OPTIONS` at 51-55, `noFrameYet` at 57-59, `header` at 114-119, `toolbar` at 132-163, the readout at 218-226)
- Test: `brawlfarm/web/src/calibration/Calibration.test.tsx`

**Read first:** `lib/copy.ts` on the merge base. PR 1 owns the intro. Change its value there and leave `Calibration.tsx` importing it; if PR 1 left the string inline as `HINT`, move it to `copy.ts` in this task and keep one definition.

**Strings, before and after:**

- Intro, before: `"What brawlfarm sees."` After, verbatim, one paragraph: `"This is what brawlfarm looks for on the screen. Green means it found the thing where it expects it. Nothing here changes settings; it helps you see why a step failed."`
- `SHOW_OPTIONS` labels, before `Taps` / `Anchors` / `Both`, after `Where it taps` / `What it looks for` / `Both`. **The `OverlayShow` union values stay `"taps" | "anchors" | "both"`.** They are state keys, not copy; renaming them would churn `FrameOverlay.test.tsx` for nothing.
- `Segmented label`, before `"Overlay"`, after `"Show"`. A second control, `Segmented label="Screen"`, takes `SCREEN_OPTIONS` from Task 1.
- `noFrameYet(name)`, before `"Start ${name} to see its frame. Scores appear after the first capture."`, after `"Start ${name} to see its screen. Matches appear once it sends the first picture."`
- The readout at 222-224, before one mono string joining `state` and `phaseLabel(phase)`, after two `Chip tone="idle"` elements under the frame, in the left column, reading `Screen: ${scores.data.state}` and `Step: ${phaseLabel(scores.data.phase)}`.
- Section heading at 220, before `Anchors`, after `What it looks for`.

**Component API after the change:** `Calibration` keeps its no-prop signature and gains `const [screen, setScreen] = useState<ScreenFilter>("all")`. The default is `"all"` and the filter never follows the detected screen on its own: an auto-moving filter would fight a reader who set it. Say that in a comment.

- [ ] **Step 1: Write the failing tests** in `Calibration.test.tsx`: the intro paragraph renders verbatim; the three Show labels render and `Taps` and `Anchors` render nowhere; the four Screen labels render; both chips render for a fixture with `state: "menu"` and `phase: "at_menu"`; the section heading is `What it looks for`.
- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Make the edits.** Wire `screen` into state only; `FrameOverlay` consumes it in Task 3, so pass nothing yet and leave a `// Task 3 wires this into the overlay.` marker you delete there.
- [ ] **Step 4: Run the gate.**

**Acceptance:** no user-visible string on the page names a file, a tap, an anchor, a capture or a worker; the Show control reads by outcome; the readout is two labelled chips; the heading count per page is unchanged from PR 3.

**Commit:** `feat(calibration): a plain intro, outcome-named controls and two readout chips`

---

### Task 3: Crosshairs only, labels on hover or focus, and the screen filter

**Files:**
- Modify: `brawlfarm/web/src/calibration/FrameOverlay.tsx` (the whole `<svg>` body, 43-96)
- Modify: `brawlfarm/web/src/calibration/Calibration.tsx` (the `frame()` callback at 165-182)
- Test: `brawlfarm/web/src/calibration/FrameOverlay.test.tsx`

**Read first:** `FrameOverlay.tsx:1-35`. The `viewBox` is the frame's own 1600x900 and `preserveAspectRatio="none"` is load-bearing; keep both. The file's safety promise is in its header comment: it is a picture, and no handler on it can move a coordinate. That promise must survive this task, so update the comment rather than delete it.

**Component API after the change:**

```
export interface FrameOverlayProps {
  instance: string;
  taps: CalibrationConstant[];
  anchors: Anchor[] | undefined;
  show: OverlayShow;
  screen: ScreenFilter;
  /** The one point whose label is shown regardless of hover, or null. */
  highlight: string | null;
  onHighlight: (name: string | null) => void;
  refreshMs: number | false;
}
```

**Structure after the change:** two stacked layers over `Thumb`.

1. The `<svg>` keeps `aria-hidden="true"` and `pointer-events-none`, and **draws no `<text>` at all**: for a tap, the circle and the two lines it already has, with `vectorEffect="non-scaling-stroke"` added to each so the strokes stay 2 CSS pixels at any width; for an anchor, the dashed or solid `rect`, likewise non-scaling. A tap or anchor whose name fails `onScreen(name, screen)` is not rendered.
2. A sibling `<div className="pointer-events-none absolute inset-0">` holds one `<span>` per rendered point, positioned with `left: ${(x / 1600) * 100}%` and `top: ${(y / 900) * 100}%`, class `pointer-events-auto` plus `text-[11px]`, holding `anchorLabel(name)` or `constantLabel(name)` and, for an anchor, its Match percentage. Each span is `opacity-0` and becomes `opacity-100` on `hover`, on `focus-visible` and when `highlight === name`. Give the layer `aria-hidden="true"` as well and make the spans **not** focusable: the accessible path to this information is the table in Task 4, which is real text in a real table. A focusable node inside an `aria-hidden` subtree is an accessibility defect, so do not add `tabIndex` here.
3. `onMouseEnter` on a span calls `onHighlight(name)` and `onMouseLeave` calls `onHighlight(null)`. Those are the only two handlers in the file. **No `onClick` anywhere, on any layer.** A click on this overlay must remain incapable of writing a coordinate.

`Calibration.tsx` holds `const [highlight, setHighlight] = useState<string | null>(null)` and passes `screen`, `highlight` and `setHighlight` down; Task 4 gives the table rows the same pair, which is what makes the table and the frame point at each other.

- [ ] **Step 1: Write the failing tests** in `FrameOverlay.test.tsx`: the rendered SVG contains zero `text` elements; with `screen="match"` a `BRAWLER_*` tap draws nothing and `ATTACK_POINT` draws one crosshair; with `screen="all"` both draw; a label span is present but hidden by default and visible when `highlight` names it; the `svg` still carries `aria-hidden="true"`; no `button` and no `a` exists inside the overlay.
- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement the two layers and the filter.**
- [ ] **Step 4: Check it by eye.** `pnpm --dir brawlfarm/web dev` with an instance running, at 1440 and again at 400. At 400 the labels are still 11 px and the crosshair strokes are still 2 px.
- [ ] **Step 5: Run the gate.**

**Acceptance:** no SVG text; crosshairs and boxes only; one label at a time, on hover or from `highlight`; the screen filter removes points from the DOM rather than hiding them; the overlay has no click handler and the header comment still says so.

**Commit:** `feat(calibration): crosshairs only, hover labels and a screen filter on the overlay`

---

### Task 4: The "What it looks for" table says it in words, a percentage and an age

**Files:**
- Modify: `brawlfarm/web/src/calibration/AnchorTable.tsx` (`status` at 24-28, `clock` at 30-37, the ref and `lastSeen` at 39-53, `columns` at 55-91)
- Modify: `brawlfarm/web/src/calibration/Calibration.tsx` (the `AnchorTable` call at 227-231)
- Create: `brawlfarm/web/src/calibration/AnchorTable.test.tsx`

**Read first:** `brawlfarm/web/src/lib/time.ts:17` (`age(fromMs, nowMs)`) and `lib/format.ts` from PR 2 (`clock(iso)`). Delete the local `clock()` in `AnchorTable.tsx` entirely; that duplication is the whole of `cal-last-seen`.

**Component API after the change:**

```
export interface AnchorTableProps {
  anchors: readonly Anchor[];
  at: string | undefined;
  empty: string;
  highlight: string | null;
  onHighlight: (name: string | null) => void;
}
```

**Columns after the change**, four, matching the wireframe: `Name`, `Match`, `Status`, `Last seen`. The `Threshold` column at 57-63 is removed; its number moves into the row `title` as `Needs 85%`, so nothing is lost. `Name` is `anchorLabel(row.name)`, not mono, not the raw name. `Match` is `${Math.round(row.score * 100)}%` with the `t-figure` role from PR 2; a score below zero clamps to `0%`, because TM_CCOEFF_NORMED bottoms out at -1 and the route passes that through. The clamp gets its own test.

**Status wording**, the only three values:

| condition | before | after | tone |
| --- | --- | --- | --- |
| `found` | `Found` | `Found` | `ok` |
| `!found && expected` | `Drift` | `Missing` | `bad` |
| `!found && !expected` | `Absent` | `Not on this screen` | `idle` |

**Last seen:** keep the ref, change what it stores. On each effect run, for every found anchor, store `Date.parse(at)`, skipping when the parse is `NaN`. Render: a found anchor reads `just now`; a remembered moment reads `age(storedMs, Date.now())` with `title={clock(storedIso)}`; nothing remembered stays `never` with no title. `age()` already returns the relative wording, so no new formatter appears.

**The hover link:** each row gets `onMouseEnter={() => onHighlight(row.name)}`, `onMouseLeave={() => onHighlight(null)}` and a background when `highlight === row.name`. If `components/ui/Table.tsx` has no row-level hook, add one optional `onRowHover` and one optional `rowTone` prop to `Table` rather than forking the table; check `Table.tsx` first and say in the commit body which way you went.

- [ ] **Step 1: Write the failing tests** in `AnchorTable.test.tsx`: a found `play` anchor renders `Play button`, `97%`, `Found`, `just now`; an expected miss renders `Missing`; an unexpected miss renders `Not on this screen` and never `Absent` or `Drift`; a negative score renders `0%`; an anchor found in an earlier render and missing now renders an age with a `title`; one never found renders `never`; hovering a row calls `onHighlight` with the raw name, not the label.
- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Rewrite the columns and the ref.**
- [ ] **Step 4: Run the gate.**

**Acceptance:** four columns, plain names, a percentage, three status words, relative ages with absolute titles, no local clock helper, and hovering a row lights its point on the frame.

**Commit:** `feat(calibration): name, match percentage, status word and age in the anchor table`

---

### Task 5: Overrides becomes Thresholds, and is never an empty panel

**Files:**
- Rename with `git mv`: `brawlfarm/web/src/calibration/OverridesTable.tsx` to `brawlfarm/web/src/calibration/ThresholdsTable.tsx`
- Modify: the renamed file (`CHANGED_WARNING` at 22-23, `Row` at 25-31, `overrideRows` at 41-68, `COLUMNS` at 70-85, the section at 87-120)
- Modify: `brawlfarm/web/src/calibration/Calibration.tsx` (the import at 19 and the call at 235-239)
- Create: `brawlfarm/web/src/calibration/ThresholdsTable.test.tsx`

**Component API after the change:**

```
export interface ThresholdsTableProps {
  constants: readonly CalibrationConstant[];
  templates: readonly CalibrationTemplate[];
  file: { present: boolean; changed_since_start: boolean; problems: string[] };
}
export function thresholdRows(
  constants: readonly CalibrationConstant[],
  templates: readonly CalibrationTemplate[],
): Row[];
```

`Row` becomes `{ key: string; name: string; value: string; source: "package" | "file" | "templates"; note: string | null }`. The exported helper is renamed from `overrideRows` to `thresholdRows`; update its one caller and any test that imports it.

**Rows, in this order:** every constant with `group === "threshold"`, always, whether or not it is overridden; then every non-threshold constant whose `source !== "package"`; then every template whose `source === "override"`. So the panel has content on a clean install, which is the point of `cal-overrides-equal`.

**Columns, three:** `Setting`, `Value`, `Source`.

- `Setting` is `constantLabel(row.name)` from Task 1, extended there with the three threshold names: `MATCH_THRESHOLD` to "Match confidence", `IN_MATCH_THRESHOLD` to "In-match confidence", `MATCHMAKING_THRESHOLD` to "Players found confidence". Add those to the override map in `names.ts` as part of this task and extend `names.test.ts`.
- `Value` is one column, the value in use, printed through the existing `show()` helper so `0.85` never becomes `0.9`, with the `t-figure` role. The separate `Default` column at 72 is removed; where `default !== value` the row gets `note` reading `Packaged value 0.85` and renders it as muted text under the value. That is the fix for three rows reading `DEFAULT 0.85` beside `OVERRIDE 0.85`.
- `Source` renders a word plus a one-line legend under the table, not a raw API string. `"package"` renders muted `package`; `"file"` and `"templates"` both render a `Chip tone="idle"` reading `override`. The legend, verbatim: `"package means the value brawlfarm ships. override means you changed it in the calibration folder."` The raw `calibration/templates` string at 64 stops reaching the screen.
- `CHANGED_WARNING`, before `"calibration.toml changed. Instances started before that run the old values until restarted."`, after `"The calibration file changed. Instances started before that keep the old values until you restart them."`
- Heading at 92, before `Overrides`, after `Thresholds`, still an `h2`, with a muted caption `"packaged values, no overrides"` when every row is `package` and no caption otherwise.
- The `empty` prop stays as a defensive fallback, retexted to `"No thresholds reported."`, because with thresholds always listed an empty table now means the API returned nothing, not that nothing is overridden.
- Keep the `file.problems` and `changed_since_start` banners exactly as they are, including their tones and their `data-tone` attributes.

- [ ] **Step 1: Write the failing tests** in `ThresholdsTable.test.tsx`: three packaged thresholds render with `package` and no override chip; a threshold whose `default` differs renders the packaged-value note; an overridden timing constant renders with the `override` chip; a template override renders one row and the string `calibration/templates` renders nowhere; the legend renders; the heading is `Thresholds` and `Overrides` renders nowhere; `Default` is not a column header.
- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: `git mv`, then rewrite.** Commit the rename and the rewrite together so the diff reviews as one move.
- [ ] **Step 4: Run the gate.**

**Acceptance:** the panel shows the shipped thresholds on a clean install; one value column; Source is a word with a legend; no raw path or file name reaches a cell; no default-equals-override row.

**Commit:** `refactor(calibration): Thresholds table with one value column and a source legend`

---

### Task 6: The two switches say what they will use

**Files:**
- Modify: `brawlfarm/web/src/calibration/RecorderCard.tsx` (the message constants at 25-33)
- Modify: `brawlfarm/web/src/calibration/ObserveCard.tsx` (the off-state paragraph at 59-64 and the observing paragraph at 52-57)
- Test: `brawlfarm/web/src/calibration/RecorderCard.test.tsx`, `brawlfarm/web/src/calibration/ObserveCard.test.tsx`

**Read first:** both files on the merge base. `FRAME_CAP_MESSAGE`, `diskCapMessage` and `WRITE_ERROR_MESSAGE` are the best copy on the page and **do not change**. PR 1 already rewrote the Observe sentences; do not touch them either.

**The one new string,** exported once from `RecorderCard.tsx` and imported by `ObserveCard.tsx`:

```
export const RECORDING_CAP_NOTE =
  "Up to 2000 frames or 512 MB per session, in the calibration folder.";
```

It renders as a muted line under the switch in each card, in the off state and the on state both, so the reader learns the cap before flipping rather than when the cap message appears. In the Recorder card's off state it follows the existing sentence `"Off. Nothing has recorded here yet."` on its own line. In the Observe card it follows the existing off sentence and, when observing, follows the recording sentence. It is a note, not a warning: muted text, no `data-tone`, no icon.

- [ ] **Step 1: Write the failing tests:** each card renders the note in the off state and in the on state; the existing cap and error messages still render in their own states, byte for byte.
- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Add the constant and the two lines.**
- [ ] **Step 4: Run the gate.**

**Acceptance:** both switches carry the cap note in every state; no other string in either card changed.

**Commit:** `feat(calibration): say the recording cap before the switch is flipped`

---

## Whole-branch close-out

- [ ] Whole-branch review on sonnet. Fix findings with an implementer, then re-review once.
- [ ] Full gate green from the worktree root, `tools/scrub_check.py` printing `0 hit(s)`.
- [ ] **Live pass.** Start Pie64 on 5555, park it with a stop override, then open Calibration. Confirm matches arrive; confirm the two chips read the real screen and step; hover three table rows and watch the right crosshair light up; flip the Recorder switch on and off and confirm the note and the frame count. Captures at 1440 in both themes with an instance running, plus one at 400, for the pull request body. The page shows matches only while an instance is up, so a capture of a stopped fleet proves nothing.
- [ ] **`git diff main --stat` shows nothing under `brawlfarm/core` and nothing under `brawlfarm/api`.** If either appears, the branch is wrong, not the rule.
- [ ] The pull request body lists the five critique ids this PR closes (`cal-jargon`, `cal-overlay-clutter`, `cal-overrides-equal`, `cal-last-seen`, `cal-observe-switch`) and names the two deferred items: the screen filter does not follow the detected screen, and the tap screen buckets are prefix rules in the web layer, so a tap constant added to `brawlfarm/core` later shows under `All` only until someone adds it to `names.ts`.
