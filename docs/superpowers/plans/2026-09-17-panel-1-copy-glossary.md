# Panel PR 1: Copy and Glossary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every user-facing string in the panel reads as a sentence a person wrote: no `worker`, `supervisor` or `tick`, no `none`, no `True`, no `key=value`, no raw enum, numbers through `Intl`, and one glossary module as the single source of the shared nouns.

**Architecture:** One new module `brawlfarm/web/src/lib/copy.ts` holds the glossary (nouns, empty-state prose, mode names, the required display size, the number formatter). Every screen imports named exports from it instead of writing the noun again. No other new file except two test files. `lib/feedText.ts` keeps its `feedText(record)` signature, so `lib/feedMirrors.ts` and its tests are untouched structurally.

**Tech Stack:** React 19 and TypeScript under `pnpm`, vitest plus Testing Library, Python 3.13 under `uv` for the gate only.

**Spec:** the panel critique, items `fleet-alert-strip-repr`, `fleet-restart-means-start`, `inst-session-none`, `feed-fallback-repr`, `feed-worker-word`, `plan-none-values`, `sched-override-copy`, `stats-mode-enum`, `copy-casing`, `copy-errors-fix`, `copy-ellipsis`, `copy-1600`.

**Branch:** `panel/copy-glossary`, cut from `main` at 67be0e7. Worktree `.claude/worktrees/phase-10`.

## Global Constraints

- No em-dashes and no emoji anywhere: prose, code, comments, tests, commit messages, pull request body.
- Never write the word bsutil or any legacy tag anywhere.
- This pull request changes copy and formatting only. No layout, no new components, no behaviour change, nothing under `brawlfarm/core`, and nothing in the Python package unless a server string is the only source of a user-facing sentence; where that happens the task says so and the change is limited to that one string.
- Owner rulings that bind every task:
  - `worker`, `supervisor` and `tick` leave every user-facing string. The instance name and `brawlfarm` are the only actors. Logs, code, comments and the API keep their own names.
  - The Fleet alert strip shows one plain sentence with an action, never raw fields (`score=0.456`, `recovered=True`).
  - A recovered wrong mode is described as "Pie64 picked the wrong mode and switched back".
  - Enums are mapped to names: `trioShowdown` becomes `Trio Showdown`.
  - `none` and `True` are never rendered. Empty values are muted prose: "No games yet", "Queue is empty", "Not set".
  - `Restart` on a stopped card reads `Start`.
  - Sentence case everywhere except table headers and the rail eyebrow.
  - Every error string names the next step.
  - In-progress labels end with an ellipsis character.
  - Numbers are formatted with `Intl` (110,738), and the 1600x900 sentence is written in words where a user reads it.
- The implementer must not invent wording. Every string is given here before and after. If a string turns up that this plan does not list, leave it and report it.
- Per `CLAUDE.md`, code review is on: every task gets a spec-compliance and code-quality review pass on **sonnet** before it counts as complete, and the branch gets a whole-branch review on **sonnet** before its pull request opens. Findings are fixed by an implementer, then re-reviewed once.
- Conventional commit subjects with a scope (`feat(scope):`, `fix(scope):`, `docs(scope):`, `test(scope):`, `refactor(scope):`). Every commit message ends with the trailers:

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

`tools/scrub_check.py` must print `0 hit(s)`. No live pass is required: nothing here touches the farm loop.

## Strings that come from the API, not the web bundle

Listed so no task tries to fix them in the web layer and no task edits Python:

- `brawlfarm/api/alerts.py:66` builds `Alert.detail` by joining `key=value` pairs. That text is the leak behind `fleet-alert-strip-repr`. Task 2 stops the Fleet strip rendering it and reads `alert.kind` instead. The server string itself stays, and `app/AlertsDrawer.tsx:79` keeps showing it, which is the raw-fields view for the owner. Rendering alerts through `feedText` for real needs `fields` added to the `Alert` payload on both sides: a model change, not a copy change. Out of scope; note it in the pull request body.
- `ApiError.detail` (server prose) reaches `lib/toast.ts`, `components/ui/Thumb.tsx` and `components/ui/ErrorBlock.tsx`. Task 6 stops `Thumb` printing it raw. `failureMessage` keeps preferring it, because the server sentences such as "The panel cannot reach brawlfarm. Is it still running?" are the good ones.
- `fleet/InstanceCard.tsx:67` renders the server retry note ("BlueStacks window not found. Retrying in 4 min."). Already a sentence. Leave it.
- `bad_resolution` feed fields carry only `got`. Item `copy-1600` asks for the required size in the event fields; emitting it is a `brawlfarm/core` change and is out of scope. Task 3 takes the value from one exported constant in `copy.ts` and reads `fields.need` if a later core version sends it.

## File Structure

- `brawlfarm/web/src/lib/copy.ts`: new. The glossary and the formatters. Task 1.
- `brawlfarm/web/src/lib/copy.test.ts`: new. Task 1.
- `brawlfarm/web/src/lib/words.guard.test.ts`: new. The banned-word guard. Task 7.
- `brawlfarm/web/src/fleet/AlertStrip.tsx`: `alertSentence`. Task 2.
- `brawlfarm/web/src/lib/feedText.ts`: the table and the two fallbacks. Task 3.
- `brawlfarm/web/src/instance/SessionPanel.tsx`, `instance/FarmPlan.tsx`, `fleet/InstanceCard.tsx`, `stats/RecentGames.tsx`, `lib/time.ts`: empty values, mode names, numbers. Task 4.
- `brawlfarm/web/src/instance/Schedule.tsx`, `fleet/InstanceCard.tsx`: override chip and card actions. Task 5.
- `brawlfarm/web/src/api/client.ts`, `lib/toast.ts`, `components/ui/Thumb.tsx`, `instance/Instance.tsx`, `lib/states.ts`, `stats/MetricsRow.tsx`, `settings/Behavior.tsx`, `settings/Connection.tsx`, `settings/Data.tsx`, `instance/Feed.tsx`, `calibration/ObserveCard.tsx`, `calibration/Calibration.tsx`, `setup/StepBlueStacks.tsx`, `setup/StepDisplay.tsx`: Task 6.

Two characters appear by name throughout: the ellipsis is U+2026 HORIZONTAL ELLIPSIS (one character, never three dots) and the apostrophe is U+2019 RIGHT SINGLE QUOTATION MARK. Write them in source as the literal characters.

---

### Task 1: The glossary module

**Files:**
- Create: `brawlfarm/web/src/lib/copy.ts`
- Create: `brawlfarm/web/src/lib/copy.test.ts`

**Interfaces:**
- Consumes: nothing.
- Produces, all named exports, all imported by later tasks:
  - `count(n: number): string` returns `new Intl.NumberFormat("en-US").format(n)`.
  - `modeName(raw: string | null): string` returns the map below, else the camelCase name split into capitalised words, else `NOT_RECORDED` for null or empty.
  - `MODE_NAMES: Record<string, string>` with `soloShowdown: "Solo Showdown"`, `duoShowdown: "Duo Showdown"`, `trioShowdown: "Trio Showdown"`, `gemGrab: "Gem Grab"`, `brawlBall: "Brawl Ball"`, `heist: "Heist"`, `bounty: "Bounty"`, `hotZone: "Hot Zone"`, `knockout: "Knockout"`, `ranked: "Ranked"`.
  - Empty-state prose: `NO_GAMES_YET = "No games yet"`, `QUEUE_EMPTY = "Queue is empty"`, `NOT_SET = "Not set"`, `NOT_YET = "Not yet"`, `NOT_STARTED = "Not started"`, `NOT_RECORDED = "Not recorded"`, `NO_BRAWLER_YET = "No brawler selected yet"`.
  - `REQUIRED_WIDTH = 1600`, `REQUIRED_HEIGHT = 900`, `sizeWords(w: unknown, h: unknown): string` returning `"1600 by 900"` and an empty string when either side is not a finite number.
  - `REQUIRED_SIZE = sizeWords(REQUIRED_WIDTH, REQUIRED_HEIGHT)`.
  - `ELLIPSIS` (U+2026) and `APOSTROPHE` (U+2019).
  - `sentence(text: string): string` upper-cases the first character and leaves the rest. Used by the feed fallback only.

- [ ] **Step 1: Write the failing test** in `lib/copy.test.ts`: `count(110738)` is `"110,738"`; `modeName("trioShowdown")` is `"Trio Showdown"`; `modeName("someNewMode")` is `"Some New Mode"`; `modeName(null)` is `"Not recorded"`; `sizeWords(1280, 720)` is `"1280 by 720"`; `REQUIRED_SIZE` is `"1600 by 900"`; `sentence("dnd off failed")` is `"Dnd off failed"`. Assert `REQUIRED_SIZE` contains no `x` and `ELLIPSIS.length` is 1.
- [ ] **Step 2: Run it and confirm it fails.** `pnpm --dir brawlfarm/web test copy` cannot resolve `./copy`.
- [ ] **Step 3: Write `copy.ts`.** Module docstring: one paragraph saying this file is the only place a shared noun is written, and that `worker`, `supervisor` and `tick` are process names that never appear in a string a person reads.
- [ ] **Step 4: Gate.** Full gate block green.
- [ ] **Step 5: Review.** Sonnet spec-compliance and code-quality pass.

**Commit:** `feat(copy): add the panel glossary module`

---

### Task 2: The Fleet alert strip says one sentence with an action

Item `fleet-alert-strip-repr`.

**Files:**
- Modify: `brawlfarm/web/src/fleet/AlertStrip.tsx:28-34` (`alertSentence`)
- Modify: `brawlfarm/web/src/fleet/AlertStrip.test.tsx` (add cases inside the existing suite at line 39)

**Before** (`AlertStrip.tsx:28-34`): the `offline` branch, then a return of `alert.instance`, a space, `alert.title.toLowerCase()`, a colon and `alert.detail`.

**After:** keep the signature and the `offline` age, drop `alert.detail` entirely, switch on `alert.kind`. The six panel kinds are `offline`, `recover`, `wrong_mode`, `bad_resolution`, `crash`, `recalibrate` (`brawlfarm/core/notify.py:44` minus `stop`). Exact sentences, with `n` being `alert.instance` and `age` the existing `since()` result:

- `offline`: `${n} has been offline for ${age}. Check that the BlueStacks window is open, then press Retry now on its card.`
- `recover`: `${n} got stuck on a screen and is working its way back. Open it to watch.`
- `wrong_mode`: `${n} picked the wrong mode and switched back. Nothing to do.`
- `bad_resolution`: `${n} is not at ${REQUIRED_SIZE}. Set the BlueStacks display to ${REQUIRED_SIZE} and restart it.`
- `crash`: `${n} crashed. Press Restart on its card.`
- `recalibrate`: `${n} needs recalibration. Open Calibration and record a new session.`
- Any other kind: `${n}: ${alert.title.toLowerCase()}. Open Alerts for the details.`

- [ ] **Step 1: Write the failing tests.** One per kind above, plus: given a detail of `score=0.456, recovered=True`, the rendered strip contains neither an equals sign nor `True`.
- [ ] **Step 2: Run and confirm failure.**
- [ ] **Step 3: Implement**, importing `REQUIRED_SIZE` from `../lib/copy`. A comment above the map records that the raw fields stay visible in the drawer (`app/AlertsDrawer.tsx:79`) and that `brawlfarm/api/alerts.py:66` is still the source of that text.
- [ ] **Step 4: Gate. Step 5: Review.**

**Commit:** `fix(fleet): say one sentence in the alert strip instead of raw fields`

---

### Task 3: feedText loses the internal words, the key=value fallback and the hardcoded size

Items `feed-fallback-repr`, `feed-worker-word` (feed half), `copy-ellipsis` (feed half), `copy-1600`.

**Files:**
- Modify: `brawlfarm/web/src/lib/feedText.ts`
- Modify: `brawlfarm/web/src/lib/feedText.test.ts` (extend the existing `ROWS` table; do not start a second suite)

Exact changes, line references against 67be0e7:

| Where | Before | After |
| --- | --- | --- |
| `:27` `PLAIN.start` | `Worker started` | `Started farming` |
| `:90` `trophies` | `Trophies: 41120` | `Trophies: 41,120`, via `count(num(f, "total"))` |
| `:118` `wrong_mode` recovered | `Wrong mode detected, switched back` | `Picked the wrong mode and switched back` |
| `:118` `wrong_mode` not recovered | `Wrong mode detected` | `Picked the wrong mode` |
| `:131` `recover` | `Recovering: <reason>, attempt 2` | `Recovering from <reason>, attempt 2` plus U+2026 |
| `:133` `recover_dismissed` | `Recovery dismissed: <reason>` | `Recovery no longer needed: <reason>` |
| `:143-148` `bad_resolution` | `Wrong resolution: 1280 x 720, need 1600 x 900` | `Wrong resolution: 1280 by 720. brawlfarm needs 1600 by 900.` |
| `:155-158` `stop` | `Worker stopped: <reason> (12 games, 34 min)` | `Stopped farming: <reason> (12 games, 34 min)`, both numbers through `count()` |
| `:180-183` the `*_error` fallback | `dnd off failed: <err>` | `Dnd off failed: <err>`, via `sentence(words(kind))` |
| `:184-190` the default fallback | `shiny new: brawler=TARA, recovered=True` | see below |

For `bad_resolution` the got pair goes through `sizeWords(got[0], got[1])`, and the needed size is `has(f, "need") ? sizeWords(need[0], need[1]) : REQUIRED_SIZE`, so a later core version that sends the field is honoured without another edit.

New default fallback, replacing the `Object.entries` join: print `sentence(words(record.event))`, then only the human fields that are present, in this fixed order, comma separated after a colon: `brawler`, `reason`, `target`, `quest`, and `score` rendered as `match 46%` (`Math.round(num(f, "score") * 100)`). Booleans, objects and every other key are dropped. No fields present means the sentence is the event name alone. Add a comment saying a boolean or an unknown key is never printed, because that was the leak.

`start` and `stop` deliberately do not name the instance: `feedText(record)` has no instance in scope, and widening the signature would touch `lib/feedMirrors.ts` and its tests, which is not a copy change. The feed already sits inside one instance page.

- [ ] **Step 1: Write the failing tests.** Update every affected `ROWS` row to its new expected sentence; that table already covers every event kind, so it is the snapshot of `feedText` across every kind. Add rows: a `bad_resolution` carrying `need: [1600, 900]`; an unknown kind `{ event: "shiny_new", fields: { brawler: "TARA", recovered: true, score: 0.4567 } }` expecting `Shiny new: TARA, match 46%`; the same kind with no fields expecting `Shiny new`; a `foo_error` expecting `Foo failed: boom`.
- [ ] **Step 2: Add the coverage test** in the same file: export `HANDLED_KINDS: readonly string[]` from `feedText.ts` (the `PLAIN` keys plus every `case` label) and assert every kind in the test's own `API_KINDS` array is in it. Seed `API_KINDS` from the kinds already present in `ROWS`. A comment says a kind the API adds must be added to `API_KINDS` by hand, because that list lives in Python.
- [ ] **Step 3: Run and confirm failure. Step 4: Implement. Step 5: Gate. Step 6: Review.**

**Commit:** `fix(feed): write feed lines as sentences, not field dumps`

---

### Task 4: No sentinels, mapped modes and formatted numbers

Items `inst-session-none`, `plan-none-values`, `stats-mode-enum`.

**Files:**
- Modify: `brawlfarm/web/src/instance/SessionPanel.tsx:17-53,105-120`
- Modify: `brawlfarm/web/src/instance/FarmPlan.tsx:246-262,314-340`
- Modify: `brawlfarm/web/src/fleet/InstanceCard.tsx:215-218`
- Modify: `brawlfarm/web/src/stats/RecentGames.tsx:30-88`
- Modify: `brawlfarm/web/src/lib/time.ts` (add one formatter)
- Modify: `instance/SessionPanel.test.tsx`, `instance/FarmPlan.test.tsx`, `fleet/InstanceCard.test.tsx`, `stats/RecentGames.test.tsx`, `lib/time.test.ts`

Strings:

- `SessionPanel.tsx`: the `Figures` key `"Avg rank today"` becomes `"Avg rank"` in the type, in `figuresOf` and in `figuresOfLast`, and the doc comment above `figuresOfLast` loses its sentence about keeping the word today.
- `SessionPanel.tsx:45`: `avgRank === null ? "none"` becomes `avgRank === null ? NO_GAMES_YET`; the same for `last.avg_rank` in `figuresOfLast`.
- `SessionPanel.tsx:43`: `start === null || last === null ? "0"` becomes the same test returning `NOT_YET`.
- `SessionPanel.tsx`: every `String(...)` count becomes `count(...)`: `games_played`, `disconnect_count`, `interrupts`, `last.games`, `last.disconnects`, `last.interrupts`.
- `SessionPanel.tsx:108-110`: `Session ended {hhmm(endedAt)}` becomes `Session ended {dayTime(endedAt)}`, where `dayTime` is a new export in `lib/time.ts` giving `Sep 17, 05:25` (an `Intl.DateTimeFormat("en-US", { month: "short", day: "numeric" })` prefix plus the existing `hhmm`).
- `SessionPanel.tsx:115-116`: a prose value must not be mono. Have `figuresOf` and `figuresOfLast` return `{ value, prose }` per figure, and render the `dd` with `font-mono text-[15px] tabular-nums` when `prose` is false and `text-[13px] text-muted` when it is true. No structural change to the grid.
- `FarmPlan.tsx:316`: `{plan.current.brawler ?? "none"}` becomes `{plan.current.brawler ?? NO_BRAWLER_YET}`, and that span drops `font-mono` when the brawler is null.
- `FarmPlan.tsx:318`: `{plan.current.trophies === null ? "none" : plan.current.trophies} / {goal}` becomes `{plan.current.trophies === null ? NOT_YET : count(plan.current.trophies)} / {count(goal)}`.
- `FarmPlan.tsx:337-338`: the queue-empty `none` becomes `{QUEUE_EMPTY}`.
- `FarmPlan.tsx:248`: `Goal 1000, the prestige threshold` keeps its wording with the number through `count()`, reading the prestige constant the component already has if there is one, otherwise the literal 1000 formatted.
- `InstanceCard.tsx:217`: `sessionMinutes === null ? "none" : duration(sessionMinutes)` becomes `sessionMinutes === null ? NOT_STARTED : duration(sessionMinutes)`.
- `RecentGames.tsx`: the local `NONE` constant (the word `none`) is deleted and `NOT_RECORDED` from `copy.ts` replaces every use. The `mode` column renders `muted(modeName(row.mode))`. `instance` and `map` keep `muted(...)`. `trophy_change` gains a zero case before the `signed` call: `0` renders as `0` in `text-muted`, `null` still renders `NOT_RECORDED` muted, everything else keeps `signed()` and the `recent-trophies` test id. Table header labels are unchanged: headers are the one place that is not sentence case.

Deferred on purpose, to be stated in the pull request body: the `aria-describedby` from the goal input to its `trophies` suffix (`plan-none-values`) is an accessibility attribute on `components/ui/Field.tsx`, not copy, and belongs to the accessibility pull request.

- [ ] **Step 1: Write the failing tests** in the four existing suites: a stopped card shows `Not started`; a session with no ranked games shows `No games yet` and not `none`; a session missing one trophy end shows `Not yet`; a plan with a null current brawler shows `No brawler selected yet`; `110738 / 1000` renders as `110,738 / 1,000`; an empty queue shows `Queue is empty`; a game with `mode: "trioShowdown"` renders `Trio Showdown`; `trophy_change: 0` renders `0` and not `+0`; `trophy_change: null` renders `Not recorded`. Add `dayTime` cases to `lib/time.test.ts`.
- [ ] **Step 2: Run and confirm failure. Step 3: Implement. Step 4: Gate. Step 5: Review.**

**Commit:** `fix(panel): replace none and unformatted numbers with prose and Intl`

---

### Task 5: The override chip and the card actions say what they do

Items `sched-override-copy` (copy half), `fleet-restart-means-start`.

**Files:**
- Modify: `brawlfarm/web/src/instance/Schedule.tsx:24,159-176,204`
- Modify: `brawlfarm/web/src/fleet/InstanceCard.tsx:222-234`
- Modify: `instance/Schedule.test.tsx`, `fleet/InstanceCard.test.tsx`

Strings:

- `Schedule.tsx:161-163`: `Override: stop until 05:23` becomes `Paused until 05:23`, and `Override: run until 07:00` becomes `Running until 07:00`, chosen on `payload.override.mode === "run"`. The chip tone logic is unchanged.
- `Schedule.tsx:168`: `aria-label="Clear override"` becomes `aria-label="Resume schedule"`.
- `Schedule.tsx:24` `EMPTY`: `No sessions drawn yet. The supervisor draws today on its next tick.` becomes `No sessions drawn yet. brawlfarm draws today` plus U+2019 plus `s sessions within a minute.`
- `Schedule.tsx:204` toast: `Redrawing today; new sessions appear after the next tick` becomes `Redrawing today` plus U+2026 plus ` new sessions appear within a minute.`
- `InstanceCard.tsx:228`: `disabledReason="Not running"` becomes `disabledReason="Already stopped"`.
- `InstanceCard.tsx:231-233`: the Restart button label becomes `{stoppable ? "Restart" : "Start"}`, reading the same `stoppable` boolean the Stop button already uses. Label only: the handler, the endpoint and the disabled state do not change.

Deferred on purpose, to be stated in the pull request body: an undo toast on clearing the override, and surfacing `desired_reason` in the Fleet card status line, are behaviour and layout, not copy.

- [ ] **Step 1: Write the failing tests:** a `stop` override renders `Paused until 05:23`; a `run` override renders `Running until 07:00`; neither rendering contains a bare mode word; the clear control is found by the accessible name `Resume schedule`; a stopped card shows a button named `Start` and none named `Restart`; a running card shows `Restart`; the disabled Stop button reason reads `Already stopped`.
- [ ] **Step 2: Run and confirm failure. Step 3: Implement. Step 4: Gate. Step 5: Review.**

**Commit:** `fix(schedule): name the override state and the card action plainly`

---

### Task 6: Sentence case, errors with a next step, ellipses and the last internal words

Items `copy-casing`, `copy-errors-fix`, `copy-ellipsis`, `feed-worker-word` (the rest).

**Files and strings**, each line is before then after:

- `api/client.ts:51`: `Request failed (HTTP 500)` becomes a `STATUS_MESSAGE` map above `errorFrom`, then `STATUS_MESSAGE[response.status] ?? generic`. Entries: `400: "That request was not valid. Check the values and try again."`, `401: "The panel is not signed in to brawlfarm. Check the API token in Settings."`, `403: "The panel is not allowed to do that. Check the API token in Settings."`, `404: "That is not there any more. Refresh the page."`, `409: "Something changed while you were editing. Refresh and try again."`, `422: "Some values were not accepted. Fix the fields listed and try again."`, `500: "brawlfarm hit an internal error. Check the panel log, then try again."`, `503: "brawlfarm is not ready yet. Wait a moment and try again."`. Generic: `Something went wrong (HTTP 418). Try again, and check the panel log if it keeps failing.`
- `api/client.ts:50`: `"Validation failed"` becomes `"Some values were not accepted. Fix the fields listed and try again."`
- `lib/toast.ts:31`: `"Request failed"` becomes `"That did not go through. Try again."`
- `components/ui/Thumb.tsx:130-135`: `Screenshot failed: <api detail>` becomes `No screenshot yet. Check that the instance is running.` The second line `Retrying in 15 s.` stays. The API detail is no longer printed.
- `instance/Instance.tsx:161`: `new ApiError(404, "unknown instance")` becomes `new ApiError(404, "No instance by that name. Open Fleet to pick one.")`
- `lib/states.ts:33-36`: phase words to sentence case: `at_menu: "At the menu"`, `queuing: "Queuing"`, `playing: "Playing"`, `returning: "Returning"`. The state labels at `:13-19` are already sentence case; leave them.
- `stats/MetricsRow.tsx`: every metric label to sentence case, brand names as the brand writes them. List each changed label in the commit body.
- `settings/Behavior.tsx:67`: `Close Brawl Stars when the worker stops.` becomes `Close Brawl Stars when the instance stops.`
- `settings/Behavior.tsx:68`: `Turn on Do Not Disturb when the worker starts.` becomes `Turn on Do Not Disturb when the instance starts.`
- `settings/Behavior.tsx:85`: `Turn Do Not Disturb back off when the worker stops.` becomes `Turn Do Not Disturb back off when the instance stops.`
- `settings/Behavior.tsx:129` and `settings/Connection.tsx:120`: `Applies to a worker the next time it starts.` becomes `Applies the next time an instance starts.`
- `instance/Feed.tsx:26`: `No lines yet. The feed fills as the worker plays.` becomes `No lines yet. The feed fills as the instance plays.`
- `calibration/Calibration.tsx:41`: `What the workers see. The page reads; calibration.toml and the templates folder write.` becomes the same sentence opening `What brawlfarm sees.`
- `calibration/ObserveCard.tsx:24`: `Stop this instance first. Recording your own play never starts on top of a farming worker.` becomes the same sentence ending `on top of a farming instance.`
- `calibration/ObserveCard.tsx:55`: `" Waiting for the worker to start."` becomes `" Waiting for the recording to start"` plus U+2026.
- `setup/StepBlueStacks.tsx:84`: `Scanning` becomes `Scanning` plus U+2026.
- `setup/StepDisplay.tsx:69`: `Checking` becomes `Checking` plus U+2026.
- `settings/Data.tsx:89`: the HTML entity in `Delete one instance&apos;s data` becomes the literal U+2019 character.

Comments and identifiers keep `worker`, `supervisor` and `tick`. Only strings a person reads change.

- [ ] **Step 1: Write the failing tests.** In `api/client.test.ts` add one case per mapped status plus the generic. In `lib/toast.test.ts` assert the new fallback. In `components/ui/Thumb.test.tsx` assert an error with detail `boom` renders the new sentence and does not render `boom`. Extend the `settings`, `calibration` and `setup` suites where they already assert these labels; where they do not, add no suite, because the Task 7 guard covers them.
- [ ] **Step 2: Run and confirm failure. Step 3: Implement. Step 4: Gate. Step 5: Review.**

**Commit:** `fix(copy): sentence case, a next step in every error, ellipses on progress`

---

### Task 7: The guard test that keeps the words out

**Files:**
- Create: `brawlfarm/web/src/lib/words.guard.test.ts`

**Interfaces:** consumes the source tree on disk. Produces no exports.

- [ ] **Step 1: Write the test.** Walk `brawlfarm/web/src` recursively from `import.meta.dirname`, reading every `.ts` and `.tsx` file except `*.test.ts`, `*.test.tsx` and everything under `src/test/`. Strip line comments, block comments and JSDoc from each file. In what is left, fail on: the words `worker`, `supervisor` or `tick` inside a string literal or JSX text (case insensitive, whole word, so `setInterval` bodies and `AGE_TICK_MS` are untouched because they are not literals); the exact token `True`; the pattern `=0.`; and an interpolated `key=value` shape inside a template literal. Report every hit as `path:line: text` in one assertion message, so a failure names all of them at once.
- [ ] **Step 2: Run it before tasks 2 to 6 land** to confirm it catches the old strings, and record that count in the commit body. Then confirm it passes on the finished branch.
- [ ] **Step 3:** The allowlist array in the test must be empty. If a real string ever needs one of these words, the task that needs it edits this test in the same commit with a comment saying why.
- [ ] **Step 4: Gate. Step 5: Review.**

**Commit:** `test(copy): fail the build when internal words reach the screen`

---

## Acceptance criteria for the branch

1. The full gate block is green and `tools/scrub_check.py` prints `0 hit(s)`.
2. `pnpm --dir brawlfarm/web test` includes the new `copy` and `words.guard` suites and the extended `feedText` table, and `words.guard` passes with an empty allowlist.
3. No Python file is modified anywhere on the branch: `git diff --stat main -- "*.py"` is empty, and nothing under `brawlfarm/core` appears in the diff.
4. No em-dash and no emoji anywhere in the diff.
5. The pull request body lists the deferred items: the `Alert.fields` payload change, the `bad_resolution` `need` field from core, the Field `aria-describedby`, the override undo toast, and `desired_reason` on the Fleet card.
