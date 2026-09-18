# Panel PR 4: Instance page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The instance page reads as one page ordered by job instead of five stacked panels: a two-row header, a live screen that says when it is working, a feed that groups by day and announces itself, a farm plan that explains a rejected value where it was typed, and a schedule bar a person can read.

**Architecture:** No new route, no routing state, no tabs. `instance/Instance.tsx` keeps owning the layout and the header; the five panels keep their props except where a task names a new one. One new component (`components/ui/PanelSkeleton.tsx`) and one new module (`lib/feedDays.ts`), so `Feed.tsx` keeps its append and mirror logic untouched. `components/ui/Thumb.tsx` gains two optional props and stays identical for its Fleet callers.

**Tech Stack:** React 19 and TypeScript under `pnpm`, vitest plus Testing Library, Python 3.13 under `uv` for the gate only.

**Spec:** the panel critique, items `inst-five-panels`, `inst-header-clutter`, `inst-restart-no-confirm`, `inst-screenshot-two-words`, `inst-live-refresh`, `inst-pending-blank`, `inst-figures-live`, `feed-no-grouping`, `feed-follow`, `feed-live-region`, `feed-height`, `plan-goal-silent`, `plan-saved-toast`, `plan-fallback-field`, `plan-roster-list`, `plan-maxed-help`, `sched-bar-unreadable`, `sched-run-for`, `sched-timezone`, plus the two PR 1 deferred: an undo toast when the schedule override is cleared, and the goal field described by its unit.

**Branch:** `panel/instance`, cut from `main` after PR 1 and PR 2 land. Worktree `.claude/worktrees/phase-10`.

## Global Constraints

- No em-dashes and no emoji anywhere: prose, code, comments, tests, commit messages, pull request body.
- Never write the word bsutil or any legacy tag anywhere.
- Nothing under `brawlfarm/core` changes.
- API changes only if a task names the endpoint and keeps them additive. No task here names one, so this pull request is web-only. If a task needs a field the API does not send, stop and report it.
- The implementer must not invent wording. Every user-facing string is given here. A string this plan does not list stays as it is and is reported.
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

`tools/scrub_check.py` must print `0 hit(s)`.

## Verification: the live pass is required

This pull request changes the page the farm loop reports into, so the gate alone does not close it. Before the pull request opens, on this PC with instance Pie64 on port 5555:

- [ ] Park the instance with a stop override, open `/instances/Pie64` with the feed visible, then start a session through the API, not through the page.
- [ ] Confirm the feed appends live, shows a `Today` divider, puts `Interrupt` before an interrupt line, and that turning Follow off raises `Jump to latest`, which re-arms Follow when pressed.
- [ ] Confirm the session figures move while the session runs, that the accessibility tree shows the figures region as `aria-live="polite"`, and that the heading becomes `Last session` when the instance stops.
- [ ] Confirm the live screen shows the refreshing label while a capture is in flight and the caption reads the age and the clock time.
- [ ] Confirm the schedule bar draws hour labels and the legend and the now line sits where the clock says.
- [ ] Write the outcome in the pull request body. A failure here blocks the merge even with a green gate.

## Blocking dependencies

- **Blocked on PR 1 and PR 2.** This plan uses PR 1's `lib/copy.ts` (`count`, `NOT_SET`, `QUEUE_EMPTY`, `ELLIPSIS`) and PR 1's Schedule strings (`Paused until 05:23`, `Running until 07:00`, the `Resume schedule` accessible name, the rewritten `EMPTY` and redraw toast). It uses PR 2's `Button` variants (`primary`, `secondary`, `quiet`, `danger`), PR 2's `Field` `error` and `help` props with the `-msg` id and `aria-describedby`, PR 2's `Toast` tones and `retry`, and PR 2's `lib/format.ts` helpers `num`, `signed`, `clock`, `dateTime`.
- **Do not redo PR 1 or PR 2 work.** The override chip text, the card action labels, the `none` sentinels, the mode names and the feed sentence wording are done. If a string here disagrees with the branch, the branch wins and the difference is reported.
- Task 1 lands first: Tasks 2, 5, 7 and 8 use `PanelSkeleton`. Tasks 3 to 8 are independent of each other.

## File Structure

- `brawlfarm/web/src/components/ui/PanelSkeleton.tsx`: new. Task 1.
- `brawlfarm/web/src/instance/Instance.tsx`: header rows, Restart confirm, jump bar, column order. Tasks 2 and 3.
- `brawlfarm/web/src/instance/LiveScreen.tsx`, `components/ui/Thumb.tsx`: in-flight state and the clock caption. Task 4.
- `brawlfarm/web/src/lib/feedDays.ts`: new, plus `instance/Feed.tsx`. Task 5.
- `brawlfarm/web/src/instance/SessionPanel.tsx`: live region and the stopped heading. Task 6.
- `brawlfarm/web/src/instance/FarmPlan.tsx`: goal validation, Saved caption, fallback check, roster list, help lines. Task 7.
- `brawlfarm/web/src/instance/Schedule.tsx`, `lib/schedule.ts`, `styles/theme.css`: bar labels, legend, Run for row, local caption, undo. Task 8.

---

### Task 1: One loading skeleton instead of four empty divs

Item `inst-pending-blank`.

**Files:** create `components/ui/PanelSkeleton.tsx` and `PanelSkeleton.test.tsx`; modify `instance/Instance.tsx:156`, `instance/Feed.tsx:134`, `instance/FarmPlan.tsx` (the `query.isPending` branch returning an empty `section`), `instance/Schedule.tsx:102-104`.

**Interfaces:**
- Produces `PanelSkeleton({ label, rows = 3 }: { label: string; rows?: number })`. The panel shell (`rounded-[10px] border border-line bg-panel p-3`) with `aria-busy="true"`, `role="status"`, an `sr-only` span reading `Loading {label}`, and `rows` bars at `h-3 rounded-[3px] bg-panel-2`. Pulse only under `motion-safe:animate-pulse`.
- Call sites: `Instance.tsx` uses `label={name} rows={6}`; `Feed` uses `label="the feed" rows={5}`; `FarmPlan` uses `label="the farm plan" rows={6}`; `Schedule` uses `label="the schedule" rows={3}`.
- Out of scope: `stats/Stats.tsx` and `calibration/Calibration.tsx`, which the item also names. They belong to their own pull requests; list them as a deferred sweep in the pull request body.

- [ ] **Step 1: Write the failing tests.** `PanelSkeleton.test.tsx`: `aria-busy="true"`, an accessible name containing `Loading the feed`, and `rows` bars rendered. Extend `Instance.test.tsx:107` ("renders nothing but the shell while the fleet is loading") to assert the skeleton is announced instead of an empty div, renaming the case to `announces a loading panel while the fleet is loading`.
- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement and wire the four call sites.**
- [ ] **Step 4: Run the gate.**

**Acceptance:** no `return <div />` and no empty `<section />` left in the four files; every loading state has an accessible `Loading` name; nothing changes once data lands.

**Commit:** `feat(instance): one announced loading skeleton for the page panels`

---

### Task 2: A two-row header, a quiet Screenshot and a Restart that asks

Items `inst-header-clutter`, `inst-restart-no-confirm`, `inst-screenshot-two-words`.

**Files:** modify `instance/Instance.tsx:68-137` (the `Header` component) and `instance/Instance.test.tsx:119-141,176-187,218-227`. Read only: `components/ui/ConfirmDialog.tsx` (props `open`, `title`, `confirmLabel`, `tone: "bad"`, `onConfirm`, `onClose`; body as children).

**Interfaces:** `Header` keeps `{ inst, onDone }` and gains one state, `const [confirmRestart, setConfirmRestart] = useState(false)`.

**Layout after the change,** two rows inside the existing `<header>`:

- Row one: the `Fleet` breadcrumb link (unchanged), the `h2` name, `StateChip`, `phaseLabel(inst.phase)` as the status phrase, then `ml-auto` and the actions in order: `Stop` as `variant="secondary"`, `Restart` as `variant="secondary"`, `Screenshot` as `variant="quiet"`, and the `Retry now` branch unchanged.
- Row two: one `flex flex-wrap gap-x-4 gap-y-1` at `text-[12px] text-muted`, each value preceded by its own sans label: `Player tag {inst.player_tag}` (keeps `data-private`, whole group omitted when the tag is empty), `ADB port {inst.adb_port}`, `Data folder instances/{inst.name}`. Values keep `font-mono`; the port keeps `tabular-nums`.
- `Screenshot` stops being the bare `<a>` at lines 86-93. It becomes `<Button variant="quiet" size="sm">` calling `window.open(screenshotUrl(inst.name), "_blank", "noopener")`, so the header has one control shape. `LiveScreen`'s `Full size` link is untouched and stays an anchor.

**Strings:** the labels are `Player tag`, `ADB port`, `Data folder`. The dialog title is `Restart {name}?`, its body `The current match is abandoned.`, its confirm label `Restart`. No type-the-word confirm. The success toast stays `Restarting {name}` and gains `{ tone: "info" }` explicitly, so the call site shows the tone was considered.

**Behaviour:** `Restart` only opens the dialog. `onConfirm` runs exactly the existing call, `void run(settled(restartInstance(inst.name)), () => toast(...))`, then closes. `Stop` keeps its undo toast and its `disabledReason` as PR 1 left it.

- [ ] **Step 1: Write the failing tests.** The header shows the three labels with their values; `Screenshot` is a button, not a link, and pressing it calls `window.open` with the screenshot URL (spy on `window.open`); pressing `Restart` sends no request until the dialog is confirmed; the dialog is named `Restart Pie64?` and says `The current match is abandoned.`; cancelling sends nothing; confirming calls `restartInstance` once and then toasts.
- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement.** Keep `NOT_RUNNING`, `settled` and `run` exactly as they are.
- [ ] **Step 4: Run the gate.**

**Acceptance:** two header rows at 1600 px, wrapping without overlap at 400 px; every token in row two carries a label; `Restart` cannot fire in one click; the existing Stop, undo, Retry and failure tests pass with no change beyond the header queries.

**Commit:** `feat(instance): a two-row header and a Restart that asks first`

---

### Task 3: Two columns ordered by job, and a sticky jump bar below 1100 px

Item `inst-five-panels`. **The item's own `?tab=` proposal is overruled by the owner: no tabs, no routing state, no scroll memory.**

**Files:** modify `instance/Instance.tsx:167-187` and `instance/Instance.test.tsx`.

**Interfaces:** no props change. `Instance` renders, inside the existing `flex flex-col gap-4`:

1. `<Header />` unchanged.
2. A jump bar, `<nav aria-label="Jump to a panel">`, shown only below 1100 px (`min-[1100px]:hidden`), `sticky top-0 z-10` with the panel background and a bottom hairline. Four plain `<a href="#id">` anchors, these labels and targets: `Watch` to `#watch`, `Plan` to `#plan`, `Schedule` to `#schedule`, `Session` to `#session`. The browser does the scrolling and the keyboard reaches them for free: no JavaScript, no active-state tracking, no scroll listener.
3. The grid, unchanged at `grid grid-cols-1 gap-4 min-[1100px]:grid-cols-[3fr_2fr]`. Left column: `LiveScreen` then `Feed`. Right column: `SessionPanel`, then `FarmPlan`, then `Schedule`. That reorder is the change; today the right column is FarmPlan, Schedule, SessionPanel.
4. Anchor targets: wrap `LiveScreen` in `<div id="watch" className="scroll-mt-12">`, `FarmPlan` in `#plan`, `Schedule` in `#schedule`, `SessionPanel` in `#session`. `scroll-mt-12` keeps the sticky bar off the heading it just jumped to. Wrap rather than push an `id` prop into four components.
5. **One DOM order serves both widths.** The owner's stacked order is Watch, Plan, Schedule, Session, while the desktop right column puts Session first. Do not reorder with CSS: a visual order tab order does not follow is worse than the compromise. Keep the DOM as LiveScreen, Feed, SessionPanel, FarmPlan, Schedule at both widths and say so in the commit body and the pull request body, so the owner can rule again.

**Out of scope:** the item also asks for a 160 px live-screen strip on phones. The owner rulings do not ask for it and `Thumb` owns the frame size, so it is deferred and named in the pull request body.

- [ ] **Step 1: Write the failing tests.** The panel headings appear in the document order Live screen, Feed, Session, Farm plan, Schedule; a nav named `Jump to a panel` holds four links whose `href` values are `#watch`, `#plan`, `#schedule`, `#session`; each target id exists exactly once.
- [ ] **Step 2: Run them and confirm they fail. Step 3: Implement. Step 4: Run the gate,** then check the browser at 1600 px and at 400 px.

**Acceptance:** two columns at 1600 px in the job order; one column with a working sticky four-link bar below 1100 px; no `useState`, no `useSearchParams` and no scroll listener added to this file.

**Commit:** `feat(instance): order the page by job and add a jump bar under 1100 px`

---

### Task 4: The live screen says when it is working, and stamps the clock

Item `inst-live-refresh`.

**Files:** modify `components/ui/Thumb.tsx` (props at line 36, caption at line 142), `instance/LiveScreen.tsx:17-45`, `components/ui/Thumb.test.tsx`, `instance/LiveScreen.test.tsx`.

**Interfaces:**
- `Thumb` gains two optional props, both additive, both defaulting to today's behaviour so every Fleet call site is untouched:
  - `onBusyChange?: (busy: boolean) => void`, called `true` when a capture request starts and `false` when it settles either way. Guard against repeating the same value so a caller's `setState` does not rerender on every poll.
  - `showClock?: boolean`, default `false`. When true the caption renders `{age(takenAt, now)} ({clock(takenAt)})` using PR 2's `clock`; when false the caption is exactly what it is today. Either way the caption element gains `title={clock(takenAt)}`.
- `LiveScreen` holds `const [busy, setBusy] = useState(false)`, passes `onBusyChange={setBusy}` and `showClock`, and its `Refresh` button becomes `disabled={busy}` with the label `Refreshing` plus the single character U+2026 while busy, `Refresh` otherwise. No spinner glyph: the label change plus the disabled state is the in-flight signal and it costs no icon.
- The frame wrapper's `max-w-[760px]` becomes `w-full`, so the frame fills the left column; the grid already caps the column.

**Failure mode to respect:** `onBusyChange` is called from inside `Thumb`'s fetch effect. Calling it on a render path would loop. Call it only inside the async body, never during render and never in a cleanup that runs after unmount.

- [ ] **Step 1: Write the failing tests.** `Thumb.test.tsx`: `onBusyChange` fires `true` then `false` around one fetch and never twice with the same value; with `showClock` the caption holds both the age and a clock time; without it the caption text is unchanged; the caption always carries a `title`. `LiveScreen.test.tsx`: while a capture is in flight the control is named with the refreshing label and disabled, and it returns to `Refresh` and enabled afterwards.
- [ ] **Step 2: Run them and confirm they fail. Step 3: Implement `Thumb` first, then `LiveScreen`. Step 4: Run the gate,** then confirm no Fleet card rendering changed with `pnpm --dir brawlfarm/web test fleet`.

**Acceptance:** `Refresh` cannot be pressed twice into the same in-flight capture; the caption reads age and clock on the instance page and age alone on a Fleet card; `Thumb`'s polling, its 304 handling and the `refreshKey` contract are unchanged.

**Commit:** `feat(instance): show a capture in flight and stamp the frame with the clock`

---

### Task 5: The feed groups by day, announces itself and offers a way back to now

Items `feed-no-grouping`, `feed-follow`, `feed-live-region`, `feed-height`.

**Files:** create `lib/feedDays.ts` and `lib/feedDays.test.ts`; modify `instance/Feed.tsx:112-163` and `instance/Feed.test.tsx`.

**Interfaces:**
- `lib/feedDays.ts` exports `dayLabel(iso: string, nowIso: string): string` returning `Today`, `Yesterday` or a short date such as `Sep 15` through PR 2's `lib/format.ts`, and `withDays<T extends { ts: string }>(records: T[], nowIso: string): ({ kind: "day"; label: string } | { kind: "row"; record: T })[]`, inserting one divider whenever the local calendar day of `ts` changes, including before the first row. Pure, no clock of its own: the caller passes `nowIso`. Reuse the local-midnight arithmetic already written as `dayStart` in `lib/schedule.ts` by exporting it from there rather than writing a second copy.
- `Feed` renders `withDays(shown, new Date().toISOString())`. A divider is `<li role="presentation" className="pt-2 text-[11px] text-muted">{label}</li>`; rows are unchanged except as listed here.
- The scroll container gains `role="log" aria-live="polite" aria-relevant="additions"`, and `max-h-[420px]` becomes `max-h-[min(60vh,640px)]`. Keep `data-testid="feed-list"`, the `ref` and the `onScroll` handler exactly as they are.
- Each row's time span gains `title={dateTime(record.ts)}` from PR 2's helper.
- A tone word precedes the sentence when `line.tone` is `warn` or `bad`: `<b className="font-semibold">Interrupt</b>` for `warn` and `<b>Error</b>` for `bad`, with one space before `line.text`. Nothing for `ok` and `idle`. The tone dot stays and stays `aria-hidden`.
- The jump pill: when `follow` is `false` and the list has at least one row, render `Button variant="secondary" size="sm"` labelled `Jump to latest` in a `sticky bottom-0` wrapper inside the scroll container. Pressing it sets `follow` to `true`, which the existing effect at line 107 already turns into a scroll to the bottom. Do not add a second scrolling path.
- The `Follow` switch gains `describedBy` pointing at a muted help line reading `Scrolling up turns this off.`, with the id `${name}-follow-help`. That is the missing explanation the audit names at line 129.

**Failure mode to respect:** `role="log"` with `aria-live="polite"` over a list that appends a line a second will talk over itself. `aria-relevant="additions"` is what holds it to new lines, so it is not optional. If the live pass shows the narration is still too chatty, the fallback is to move the live region to the newest row alone; write that in the pull request body rather than changing the plan silently.

- [ ] **Step 1: Write the failing tests.** `feedDays.test.ts`: a same-day list gets one `Today` divider; a list crossing midnight gets two dividers in order; `dayLabel` gives `Today`, `Yesterday` and a date. `Feed.test.tsx`: the list carries `role="log"`, `aria-live="polite"` and `aria-relevant="additions"`; an interrupt row renders `Interrupt` before its sentence and an error row renders `Error`; a time span carries a `title` with the full stamp; scrolling up raises a control named `Jump to latest`, absent while Follow is on, and pressing it re-arms Follow. Extend the existing case at line 185 rather than replacing it.
- [ ] **Step 2: Run them and confirm they fail. Step 3: Implement `feedDays.ts` first, then the component. Step 4: Run the gate.**

**Acceptance:** `appendRecord`, `feedKey`, `collapseMirrors` and the four chips are untouched; the feed height follows the viewport; an interrupt is readable without colour; Follow is explained.

**Commit:** `feat(feed): day dividers, a log role, tone words and a jump back to latest`

---

### Task 6: The session figures announce themselves and say when they are history

Item `inst-figures-live`.

**Files:** modify `instance/SessionPanel.tsx:103-120` and `instance/SessionPanel.test.tsx`.

**Interfaces:** props unchanged. Two changes in the returned markup:

- The `<dl>` becomes the live region: `aria-live="polite"` and `aria-atomic="false"`. The item asks for the Trophies `dd` alone; the owner ruling is the figures region, and the region is the `dl`, so the ruling wins. Write one comment saying the ruling overrode the item, so a reviewer reading the critique does not file it again.
- The heading text becomes a function of `live`: `Session` while the instance is running, `Last session` when it is frozen. The `Session ended {hhmm(endedAt)}` caption stays exactly as it is, including its `endedAt === null` guard.

- [ ] **Step 1: Write the failing tests.** A live panel is headed `Session`, a frozen one `Last session`; the figures list carries `aria-live="polite"`; the seeded cold-load case at line 101 still shows its caption and now reads `Last session`.
- [ ] **Step 2: Run them and confirm they fail. Step 3: Implement.** Do not touch `figuresOf`, `figuresOfLast`, `FROZEN`, the `lastLive` ref or the `endedAt` effect: that logic is the hard-won part of this file. **Step 4: Run the gate.**

**Acceptance:** the six figures, their labels and the freeze behaviour are identical; the heading changes only with `live`; a screen reader hears a changed figure, not the whole panel.

**Commit:** `feat(instance): announce the session figures and name a finished session`

---

### Task 7: The farm plan explains a rejected value where it was typed

Items `plan-goal-silent`, `plan-saved-toast`, `plan-fallback-field`, `plan-roster-list`, `plan-maxed-help`, plus PR 1's deferred goal unit wiring.

**Files:** modify `instance/FarmPlan.tsx` (`run` around line 115, the save toast at 123, `onGoal` at 168-178, `onFallback` at 180-195, the Saved caption at 216, the Prestige note and Goal `Field` at 246-259, the `Maxed fallback` switch at 261, the fallback `Field` at 277-289, the roster block at 356-372) and `instance/FarmPlan.test.tsx`.

**Interfaces:**
- `run(patch)` gains a second argument, `label: string`, the human name of what was saved. It sets `savedAt` and a new `const [savedField, setSavedField] = useState<string | null>(null)` instead of firing a toast. Callers pass `"Goal"`, `"Fallback"`, `"Mode"`, `"Start with"`, `"Pick quest brawlers"`. The inline caption becomes `{savedField} saved {hhmm(savedAt)}`, for example `Goal saved 05:22`.
- **The `Plan saved` toast is removed for field saves.** A mode switch keeps one toast, `Plan set to Ladder` or `Plan set to Prestige`, with `tone: "ok"`. Nothing else here toasts on success. Failures keep going through `setFailure` and the existing `ErrorBlock`.
- Two new local validation states, each cleared by a successful save of its own field: `goalError` and `fallbackError`, both `string | null`. Do not widen the shared `failure` state: the audit's finding at lines 96, 121 and 136 is that one shared error is already too coarse.
- Goal: `onGoal` keeps its debounce and its `/^\d+$/` gate, and now sets `goalError` to `Whole numbers only` when the trimmed value is non-empty and does not match, and to `null` when it does. An invalid value is still not saved. The `Field` gets `error={goalError ?? undefined}` and, when there is no error, `help="Whole numbers, in trophies."`, so PR 2's `aria-describedby` gives the input its unit. `suffix="trophies"` stays. That discharges PR 1's deferred item through the PR 2 prop instead of a hand-rolled `aria-describedby`.
- Fallback: the placeholder becomes `Shelly` followed by U+2026. When the debounce fires with a non-empty trimmed value that no roster entry matches case-insensitively, set `fallbackError` to `Not in your roster` and do not save. An empty value still saves `null` as it does today. The `Field` gets `error={fallbackError ?? undefined}`.
- `Maxed fallback` switch gains `describedBy={fallbackHelpId}` and a help line built the way `questHelpId` already is: `When the target brawler is at max rank, farm this one instead.`
- Prestige note: the static line becomes `Goal 1000, the prestige threshold. Prestige ignores your goal and the quest-aware pick.`, given an id and wired to the mode `Segmented` through `describedBy`, matching what the quest switch already does. That is the owner's "Prestige explains what it ignores".
- Roster block: the toggle keeps `Show all brawlers` / `Hide all brawlers` and gains `aria-expanded={showAll}` and `aria-controls="plan-roster"`, matching the existing `data-testid`. When open, the list gets a header row (`Brawler`, `Trophies`) as a `role="presentation"` line in the same grid, a search input labelled `Search brawlers` filtering case-insensitively on the name, a cap of 12 rows, and a `Show all {count}` button under the cap that lifts it for the rest of the session. The list sits in a `max-h-[320px] overflow-y-auto` box with `content-visibility: auto` on the rows. **No virtualisation library.** Trophies go through PR 1's `count`.

**Failure mode to respect:** the goal field is debounced, so the error must not appear mid-keystroke on a value the user is still typing into validity. Set `goalError` on the debounce tick and on blur, never on every `onChange`. Say so in a comment: it is the difference between helpful and nagging.

- [ ] **Step 1: Write the failing tests.** Typing `1000.5` into Goal shows `Whole numbers only`, sends no request, and clears when the value becomes `1000`; a successful goal save shows `Goal saved` with a time and fires no toast; a mode switch still toasts; a fallback name absent from the roster shows `Not in your roster` and sends no request, while a roster name saves; the `Maxed fallback` switch has an accessible description naming max rank; the Prestige note says what Prestige ignores; the roster toggle carries `aria-expanded` and `aria-controls`; an open roster shows at most 12 rows plus a `Show all` control, and the search box filters. Keep every case in the existing 567-line suite passing; if one asserts the `Plan saved` toast, update that case and say so in the commit body.
- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement** in this order: the `run` label and the caption, then the two validation states, then the help lines, then the roster block. Each is separately testable; do not interleave.
- [ ] **Step 4: Run the gate.**

**Acceptance:** no value is rejected silently; one confirmation per save and it names the field; the fallback cannot save a name the roster does not have; the roster is reachable by keyboard and announced; the optimistic cache write, the rollback and the debounce cancels are behaviourally unchanged.

**Commit:** `feat(plan): inline validation, a named Saved caption and a readable roster`

---

### Task 8: A schedule bar a person can read

Items `sched-bar-unreadable`, `sched-run-for`, `sched-timezone`, plus PR 1's deferred override undo.

**Files:** modify `lib/schedule.ts` (the `Block` and `Timeline` types and `timeline`), `instance/Schedule.tsx:32-36,130-212`, `styles/theme.css` (one `.hatch` utility), `lib/schedule.test.ts`, `instance/Schedule.test.tsx`.

**Interfaces:**
- `lib/schedule.ts`: `Block` gains `label: string`, the block's wall-clock span such as `14:00 to 15:30`, built from the session's own `start` and `end` through `hhmm` **before** the clip to the end of the day, so a clipped block still states its real end. `Timeline` gains `description: string`, one sentence naming the span and the sessions, for example `Midnight to midnight. 3 sessions drawn, 1 running now.` The component renders that string and never assembles it, so the wording is testable without React.
- `Schedule.tsx` bar, keeping `data-testid="schedule-bar"` and `data-testid="schedule-now"`:
  - `BLOCK_TONE` carries shape as well as colour: `past` is `bg-idle opacity-40 hatch` (a repeating-linear-gradient utility added to `styles/theme.css` as `.hatch`), `active` is `bg-accent`, `future` is `border border-line bg-transparent`. Colour alone stops carrying the state.
  - Each block gets `title={block.label}` and an `sr-only` span with the same text.
  - Hour labels under the bar at 0, 6, 12, 18 and 24, positioned from the existing `bar.ticks` percentages, `text-[10px] text-muted tabular-nums`, `aria-hidden="true"` because `description` already says the span.
  - The bar container gets `role="img"` and `aria-label={bar.description}`.
  - A legend line under the labels: four items reading `Past`, `Running now`, `Later today`, `Now`, each with the same swatch shape as the thing it names. Sentence case, no emoji.
  - A muted caption under the legend: `Times are local.` Not the UTC offset the item suggests: only the owner uses this panel at this PC, so the offset is noise. Say that in the commit body.
  - Below 1100 px (`min-[1100px]:hidden`) the sessions also render as a plain text list, one `hh:mm to hh:mm` per line with its state word, from the same `bar.blocks`.
- `Run for` row becomes one sentence with the Start button: the `Field` keeps `label="Run for"` and `suffix="hours"` and gains `max={12}`, `inputMode="decimal"` and `help="Starts now and ignores the schedule for this long."`, plus `error="Half an hour to 12 hours"` whenever the parsed value is finite and outside `[0.5, 12]`. `runnable` becomes `Number.isFinite(parsed) && parsed >= 0.5 && parsed <= 12`. `Start` stays `variant="primary"` with its `disabledReason`. One new state, `const [busy, setBusy] = useState<null | "start" | "redraw">(null)`, disables each of the two buttons while its own request is in flight, so neither can double-submit.
- `Redraw today` becomes `Draw new sessions`. Its toast text is PR 1's; do not rewrite it.
- The override clear gains the undo PR 1 deferred. `patch({ clear_override: true }, null)` becomes a `tone: "ok"` toast reading `Schedule resumed` with an `undo` that writes the same override back from the payload the panel already holds (`payload.override.mode`, `payload.override.until`). **Read the API first:** `api/schedule.ts` and the PATCH body must already accept an override write with a mode and an until. If they do not, drop the undo, leave the toast with no action, and report it. Do not add or widen an endpoint.

**Failure modes to respect:** the undo writes state back to the server, so a wrong restore is a farm-loop effect, not a cosmetic one. If the stored `until` is already past by the time undo fires, skip the write and show a `tone: "bad"` toast reading `That pause has already expired.`; compare against `payload.now`, not the browser clock. Ordering also matters: gate the undo on `busy === null` so it cannot interleave with a start or a draw.

- [ ] **Step 1: Write the failing tests.** `schedule.test.ts`: a block carries a `14:00 to 15:30` label built from the unclipped session; a session clipped at midnight still labels its real end; `description` names the count and whether one is running. `Schedule.test.tsx`: the bar is an image whose accessible name holds the day span; hour labels 0, 6, 12, 18 and 24 render; each block has a title with its span; the legend names the four states; `Times are local.` renders; `Run for` shows the help sentence and the range error at 13 while `Start` stays out of reach; `Start` and `Draw new sessions` disable while pending; clearing an override toasts `Schedule resumed` with an undo that writes the override back exactly once; an expired override writes nothing. Keep all twelve existing cases passing.
- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement `lib/schedule.ts` first,** then the component.
- [ ] **Step 4: Run the gate,** then the bar items of the live pass.

**Acceptance:** the bar's state is readable without colour; every block states its span; the `Run for` row reads as a sentence with a bounded field; no control can double-submit; the override undo either works against the real API or is absent with a report saying why.

**Commit:** `feat(schedule): a labelled readable day bar and a bounded Run for row`

---

## Acceptance criteria for the branch

- All nineteen items in scope, plus the two PR 1 deferrals, are discharged or explicitly deferred in the pull request body with a reason.
- The gate block is green on the final commit, including `0 hit(s)`.
- The live pass on Pie64 is done and its outcome is written in the pull request body.
- No em-dash, no emoji, no legacy tag, nothing under `brawlfarm/core`, no API change.
- Deferred and named in the pull request body: the `Stats.tsx` and `Calibration.tsx` skeletons, the phone live-screen strip, the 422 field-mapping half of `plan-goal-silent` (it lives in `api/client.ts` and `ErrorBlock.tsx`, which belong to another pull request), and the one-DOM-order compromise from Task 3.
- Whole-branch review on sonnet, findings fixed by an implementer, re-reviewed once.
