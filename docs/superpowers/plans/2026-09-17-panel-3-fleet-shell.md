# Panel PR 3: Fleet and Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The shell says one thing once. One page title, one readable connection sentence, one alerts control with an accessible name, one alert on the Fleet strip and only when it needs a hand, one status line per card, and metric labels written in words.

**Architecture:** No new routes and no new state. New markup inside existing files only (a connection line in `app/TopBar.tsx`, a `SkeletonCard` in `fleet/Fleet.tsx`), one rewritten label table and one restructured card body in `fleet/InstanceCard.tsx`. Every string the user reads comes from PR 1's `lib/copy.ts` glossary or is given verbatim below. Buttons, toasts, the focus ring and the `t-figure` / `t-name` utilities come from PR 2; this pull request consumes that kit and adds nothing to it.

**Tech Stack:** React 19 and TypeScript under `pnpm`, vitest plus Testing Library, Python 3.13 under `uv` for the gate only.

**Spec:** the panel critique, items `shell-two-titles`, `shell-live-pill`, `shell-alerts-count`, `shell-rail-instances`, `shell-alerts-drawer`, `shell-drawer-scrim`, `fleet-status-three-places`, `fleet-port-unlabeled`, `fleet-metrics-formats`, `fleet-open-twice`, `fleet-stop-all-undo`, `fleet-loading-zero`, `fleet-totals-line`, `fleet-thumbnail-chip`, `fleet-alert-more`, `fleet-offline-copy`.

**Dropped from this plan:** `shell-theme-color`. PR 2 Task 2 already ships the `meta[name=theme-color]` pair that tracks the resolved theme in `brawlfarm/web/index.html` and `src/App.tsx`. Do not touch it. Confirm it is on the merge base and note it in the pull request body.

**Branch:** `panel/fleet-shell`, cut from the merge of PR 2. Worktree `.claude/worktrees/phase-10`.

## Global Constraints

- No em-dashes and no emoji anywhere: prose, code, comments, tests, commit messages, pull request body.
- Never write the word bsutil or any legacy tag anywhere.
- Nothing under `brawlfarm/core`.
- API changes only if a task names the endpoint, and then only additive. No task here changes the API. Where the panel wants a field the server does not send, the task says so and defers it.
- Owner rulings that bind every task:
  - One title per page. The top bar carries the breadcrumb or page name and is not an `h1`; the page body carries the `h1` exactly once.
  - The connection state is a readable line, not an 11 px pill.
  - The alerts control reads "Alerts" with a count badge and an accessible name "Alerts, 6 unread".
  - The drawer and its scrim are fixed to the viewport, body scroll is locked while it is open, and focus returns to the Alerts button on close.
  - Rail instance names are set in Archivo with a state chip, never a colour dot alone.
  - The Fleet alert strip stays but shows only alerts that need action (`offline`, `crash`, `bad_resolution`, `recalibrate`): one sentence with an action, never more than one alert, plus a link to the drawer carrying the count. Recovered interrupts (`wrong_mode`, `recover`) appear only in the drawer and the bell count.
  - Card status lives in one place: a state chip plus one status line. The ADB port is labelled or absent. Metric labels are words: Games today, Trophies today, This session, Break at.
  - A stopped card reads Start (PR 1 ships that label). Stop all gets the same undo toast as Stop. Restart gets a one-line confirm.
  - Loading renders skeleton cards and no totals line.
  - The offline card renders the server note as it is written.
  - Only the owner uses this panel, at this PC, at 1440 wide. Narrow-screen items are out of this pull request: do not touch the 820 px breakpoints.
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

`tools/scrub_check.py` must print `0 hit(s)`. No live pass is required: nothing here touches the farm loop.

## Blocking dependencies

- **Blocked on PR 1 and PR 2.** PR 1 owns `lib/copy.ts` (`count`, `modeName`, the `NO_*` constants, `REQUIRED_SIZE`), `AlertStrip.alertSentence` by kind, and the Start label on a stopped card. PR 2 owns the `Button` variants `primary`, `secondary`, `quiet`, `danger`, `Toast` tones with `retry`, `Field`, the focus ring, the skip link, the theme-color metas, `lib/format.ts` (`num`, `signed`, `clock`, `dateTime`) and the `t-figure` / `t-name` utilities. Read the merge base before every task and reuse those exports. Never write a second formatter, a second alert sentence or a second Start label.
- PR 1 also edits `lib/states.ts` (phase label casing) and `fleet/InstanceCard.tsx` (empty values, card actions). Task 7 rewrites regions of both: rebase first, read those two files, then write.
- Order matters twice: **Task 1 before Task 2** (Task 1 removes the bar `h1`, Task 2 rebuilds the bar's right side) and **Task 5 before Task 6** (Task 5 changes the strip's props, Task 6 changes who passes them). Tasks 3, 4 and 7 are independent.

## File Structure

- `brawlfarm/web/src/app/TopBar.tsx`: breadcrumb, connection line, Alerts control. Tasks 1 and 2.
- `brawlfarm/web/src/fleet/Fleet.tsx`, `stats/Stats.tsx`, `calibration/Calibration.tsx`, `settings/Settings.tsx`, `instance/Instance.tsx`: one `h1` per page. Task 1.
- `brawlfarm/web/src/app/AlertsDrawer.tsx`, `components/ui/Drawer.tsx`: scroll lock, count in the title, dated rows, skeleton, confirm on Dismiss all. Task 3.
- `brawlfarm/web/src/app/Rail.tsx`: instance names and state chips. Task 4.
- `brawlfarm/web/src/fleet/AlertStrip.tsx`: actionable kinds only, the count link. Task 5.
- `brawlfarm/web/src/fleet/Fleet.tsx`: totals row, skeletons, Stop all undo. Task 6.
- `brawlfarm/web/src/fleet/InstanceCard.tsx`, `lib/states.ts`, `components/ui/Thumb.tsx`: card anatomy. Task 7.
- Tests: `app/TopBar.test.tsx`, `app/AlertsDrawer.test.tsx`, `app/Rail.test.tsx`, `fleet/AlertStrip.test.tsx`, `fleet/Fleet.test.tsx`, `fleet/InstanceCard.test.tsx`. All six exist; extend them, do not add new files.

## What the server does and does not send

- `brawlfarm/api/instances.py:50-67` `view_to_dict` sends `name`, `adb_port`, `state`, `health`, `pid`, `heartbeat_age_s`, `phase`, `desired`, `desired_reason`, `until`, `games_played`, `farm_brawler`, `note`. **There is no `retry_at` field.** So `fleet-offline-copy` is honoured by rendering `inst.note` as the sentence and deleting the client's second copy of it. `retryMinutes` survives only where the fourth metric needs a number (Task 7), and adding `retry_at` is listed as deferred additive work in the pull request body.
- There is no endpoint that restores a dismissed alert: `src/api/alerts.ts` exposes `listAlerts`, `dismissAlert` and `dismissAllAlerts` only. An undo for Dismiss all would need a new endpoint, which this plan may not add, so Task 3 uses a one-line confirm and defers the undo.
- `components/ui/Drawer.tsx:29` is already `fixed inset-0 z-40` with an absolute scrim inside it, and `useFocusTrap.ts:33,59` already captures the opener and returns focus on close. The remaining half of `shell-drawer-scrim` is the body scroll lock, so Task 3 does that and does not re-fix what is already fixed.

---

### Task 1: One page title, and the bar carries the breadcrumb

**Files:**
- Modify: `brawlfarm/web/src/app/TopBar.tsx` (`pageTitle` lines 32-37, the `h1` at lines 47-49)
- Modify: `brawlfarm/web/src/fleet/Fleet.tsx` (the `h2` and its stale comment at lines 118-122; leave the empty-state `h1` at line 96 as it is)
- Modify: `brawlfarm/web/src/stats/Stats.tsx`, `calibration/Calibration.tsx`, `settings/Settings.tsx`, `instance/Instance.tsx`: the page heading element only
- Test: `app/TopBar.test.tsx` (`pageTitle` suite line 22, "shows the page title and the connection pill" line 34), `fleet/Fleet.test.tsx` (line 53)

**Interfaces after the change:**
- `pageTitle(pathname: string): string` keeps its signature and returns a breadcrumb on an instance path: `/instances/Pie64` gives `Fleet / Pie64`. Every other return is unchanged (`Fleet`, `Stats`, `Calibration`, `Settings`, `brawlfarm`).
- The bar renders that string inside `<nav aria-label="Breadcrumb">` as `<span className="truncate text-[13px] text-muted">`, not an `h1` and not at 20 px. The instance segment carries `t-name`.
- Every page body owns exactly one `h1`: each page's existing `h2` becomes `h1` with the same text and classes, and the "An h2: the top bar already carries this page's h1" comment is deleted, not reworded.

- [ ] **Step 1: Write the failing tests.** `pageTitle("/instances/Pie64")` is `Fleet / Pie64`; `TopBar` exposes no `heading` role at all; Fleet renders exactly one level-1 heading named `Fleet`; the same one-`h1` assertion for Stats, Calibration and Settings.
- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement, bar first, then page by page, type-checking after the bar.**
- [ ] **Step 4: Check the outline by hand:** no page shows the same words twice, every page has one level-1 heading.
- [ ] **Step 5: Run the gate.**

**Acceptance:** one level-1 heading per page, no heading in the top bar, `Fleet / Pie64` on an instance page, no page lost its title.

**Commit:** `fix(shell): one title per page and a breadcrumb in the bar`

---

### Task 2: A readable connection line and a named Alerts control

**Files:**
- Modify: `brawlfarm/web/src/app/TopBar.tsx` (`CONNECTION_PILL` lines 26-30, the pill markup lines 51-58, the Alerts `Button` lines 60-69)
- Read first: `brawlfarm/web/src/live/useEvents.ts` lines 82-88, for what `useConnection` actually exposes
- Test: `app/TopBar.test.tsx` (lines 33-63)

**Interfaces after the change:**
- `CONNECTION_PILL` is renamed `CONNECTION_STATE: Record<Connection, { label: string; line: string | null; tone: Tone }>`:
  - `live`: label `Live`, line `null`, tone `ok`
  - `reconnecting`: label `Reconnecting`, line `Reconnecting. Figures may be up to 30 s old.`, tone `warn`
  - `connecting`: label `Connecting`, line `Connecting to brawlfarm. Figures may be up to 30 s old.`, tone `idle`
- `TopBar` returns a wrapper `div` holding the 52 px `header` row and, when `line !== null`, one full-width row under it: `<p role="status" aria-live="polite" className="border-b border-line bg-panel-2 px-4 py-1.5 text-[13px] text-text">`. When `line === null` the bar keeps a quiet `Live` label at `text-[13px] text-muted` with the existing `TONE_DOT` dot and renders no second row. The 52 px bar height and the Shell grid are untouched.
- The Alerts control keeps `Button variant="quiet" size="sm"` and gains `aria-label={alertsLabel(unread)}`. Export `alertsLabel(unread: number): string`: `0` gives `Alerts, no unread`, `1` gives `Alerts, 1 unread`, `6` gives `Alerts, 6 unread`, `120` gives `Alerts, 120 unread`. The visible badge caps at `99+` while the label always says the true number.
- Do not add a retry countdown: `useConnection` returns the state only, and a countdown would need a new field out of `useEvents`. Note it as deferred in the commit body.

- [ ] **Step 1: Write the failing tests.** `alertsLabel` at 0, 1, 6 and 120; reconnecting renders the exact sentence with `role="status"`; a live connection renders no second row and shows `Live`; `getByRole("button", { name: "Alerts, 6 unread" })` finds the control; 120 unread shows `99+` with the label still saying 120.
- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the gate.**

**Acceptance:** the 11 px pill is gone; reconnecting says so in a sentence readable from across the desk; the alerts control has one accessible name that agrees with its badge.

**Commit:** `fix(shell): a readable connection line and an accessible Alerts name`

---

### Task 3: The alerts drawer: dates, a skeleton, a locked page and a confirm

**Files:**
- Modify: `brawlfarm/web/src/components/ui/Drawer.tsx` (the early return line 25, the panel lines 28-37)
- Modify: `brawlfarm/web/src/app/AlertsDrawer.tsx` (`useQuery` line 25, `onDismissAll` lines 42-49, `title` line 56, `actions` lines 57-64, the empty copy lines 67-70, the row lines 73-88)
- Test: `app/AlertsDrawer.test.tsx` (lines 47-128)

**Interfaces after the change:**
- `Drawer` gains no props. Inside it one `useEffect` locks body scroll while `open`: capture `document.body.style.overflow`, set it to `hidden`, restore the captured value in the cleanup. Restore the captured value, never a hard-coded `""`, or a second modal unlocks the page behind the first.
- `AlertsDrawer` reads `isPending` from the same `useQuery` and renders three states in this order: pending gives three skeleton rows (`<li aria-hidden="true">` with `animate-pulse` bones and no text); resolved and empty keeps today's sentence exactly as it reads now; resolved and non-empty gives the list.
- The drawer title becomes `Alerts, {n}` when `alerts.length > 0` and stays `Alerts` at zero. `Drawer` passes `title` into `aria-label`, so this is the accessible name too.
- Each row's time becomes relative with an absolute `title`: visible text from `since(Date.parse(alert.ts), Date.now())` in PR 1's unit wording, and `title={dateTime(alert.ts)}` from PR 2's `lib/format.ts`. Rows group under two `text-[11px] uppercase tracking-wide text-muted` subheadings, `Today` and `Earlier`, decided by local calendar day. An empty group renders nothing.
- `Dismiss all` opens `ConfirmDialog` (`components/ui/ConfirmDialog.tsx`, props `open`, `onClose`, `onConfirm`, `title`, `confirmLabel`, `tone`) with title `Dismiss all alerts?`, body `They leave the drawer and the bell count. Nothing is un-dismissed.`, confirm label `Dismiss all`, tone `bad`. On confirm the existing call and its `Alerts dismissed` toast run unchanged.
- No undo here: there is no restore endpoint. Say so in the commit body and list the additive endpoint as deferred.

- [ ] **Step 1: Write the failing tests.** Body overflow is `hidden` while open and back to its previous value after close; a pending query shows skeleton rows and no empty copy; the resolved empty case still shows the sentence; the title reads `Alerts, 3`; a row from yesterday sits under `Earlier` and carries a dated `title`; `Dismiss all` asks first and only calls the API after the confirm.
- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement `Drawer` first, then the drawer body.**
- [ ] **Step 4: Confirm by hand** that opening the drawer on the Stats page does not scroll the page behind it and that Escape returns focus to the Alerts button.
- [ ] **Step 5: Run the gate.**

**Acceptance:** no flash of empty copy before the list; yesterday's crash reads as yesterday's; the page behind the drawer does not scroll; Dismiss all cannot happen on one stray click.

**Commit:** `fix(shell): dated alert rows, a drawer skeleton and a locked page behind it`

---

### Task 4: Rail instance names in words with a state chip

**Files:**
- Modify: `brawlfarm/web/src/app/Rail.tsx` (`linkClass` lines 20-24, the instance list lines 56-76)
- Test: `app/Rail.test.tsx` ("gives every instance a dot in its state's tone", line 43)

**Interfaces after the change:**
- The instance name renders as `<span className="t-name truncate text-[13px]">`, PR 2's utility, Archivo at the nav size. Mono stays for ports and tags elsewhere; nothing in the rail is mono.
- The colour dot is replaced by `<StateChip state={inst.state} />` at the existing 10 px chip scale, so the state carries a text label and does not rest on colour alone. Drop the `stateTone` and `TONE_DOT` imports from this file once nothing else uses them, and leave `lib/states.ts` alone.
- The `Instances` eyebrow keeps its uppercase treatment: it is the documented exception in PR 1's casing rule.

- [ ] **Step 1: Write the failing tests.** Each rail instance link's accessible name contains both the instance name and its state label ("Pie64", "Stopped"); no element in the instance list carries a `font-mono` class; the existing active-link test still passes.
- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the gate.**

**Acceptance:** a rail entry reads as a name and a state, not a dot; nothing in the rail is mono; the 820 px behaviour is untouched.

**Commit:** `fix(shell): rail instance names in words with a state chip`

---

### Task 5: The Fleet strip shows one alert that needs a hand

**Files:**
- Modify: `brawlfarm/web/src/fleet/AlertStrip.tsx` (props lines 22-26, the `unread > 1` control lines 78-84)
- Modify: `brawlfarm/web/src/fleet/Fleet.tsx` (`newest` line 45, the strip render lines 125-127)
- Test: `fleet/AlertStrip.test.tsx` (lines 39-91), `fleet/Fleet.test.tsx` ("shows the newest alert above the grid", line 130)

**Interfaces after the change:**
- New in `AlertStrip.tsx`: a module-scope `const ACTION_KINDS = new Set(["offline", "crash", "bad_resolution", "recalibrate"])` and `export function stripAlert(alerts: Alert[]): Alert | undefined`, returning the newest alert whose `kind` is in `ACTION_KINDS`. `Fleet` calls `stripAlert(alerts?.alerts ?? [])` instead of reading `alerts.alerts[0]`, so a recovered `wrong_mode` never reaches the strip and is left to the drawer and the bell.
- `AlertStripProps` keeps `alert` and `onOpen` and replaces `unread: number` with `total: number`, the full unread count from the same query. The strip still renders one alert and one sentence.
- The count control reads `All 6 alerts`, built from PR 1's `count(total, "alert")`, and renders only when `total > 1`. It stays a `Button variant="quiet" size="sm"` calling `onOpen`, the same action as the bell, so the two controls agree.
- `alertSentence` is PR 1's and is not touched. `Retry now` stays on an offline alert; `Dismiss` stays.

- [ ] **Step 1: Write the failing tests.** `stripAlert` picks the newest actionable alert and skips `wrong_mode` and `recover`; an all-recovered list gives `undefined`; the strip renders no count control at `total: 1`; at `total: 6` it reads `All 6 alerts` and calls `onOpen`; Fleet renders no strip when the only alert is a recovered wrong mode, while the bell count still says 1.
- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement `stripAlert` first, then the prop rename.**
- [ ] **Step 4: Run the gate.**

**Acceptance:** the strip appears only when something needs the owner; one alert, one sentence, one action, one link with the count; recovered interrupts are drawer-only.

**Commit:** `feat(fleet): the alert strip shows one alert that needs a hand`

---

### Task 6: The Fleet page: a totals row, skeletons, and a reversible Stop all

**Files:**
- Modify: `brawlfarm/web/src/fleet/Fleet.tsx` (`onStartAll` lines 62-69, `onStopAll` lines 71-82, the header lines 116-130, the grid lines 129-133, the totals `p` lines 141-143)
- Test: `fleet/Fleet.test.tsx` (lines 52-159)

**Interfaces after the change:**
- Loading: while `instances === undefined` and `error === null`, the page renders the header with a muted `Loading fleet` where the instance count goes, a grid of three `SkeletonCard` elements, no totals row and no strip. `SkeletonCard` is a local function component in this file: the card frame, an `aspect-video` bone, a name bone and four metric bones, all `aria-hidden="true"` with `animate-pulse`. Never render `0 instances` or a row of zeros before the first response.
- The totals `p` becomes a `dl` above the grid, rendered only when `fleet.length >= 2`, with four pairs: `Farming` / `{farming} of {fleet.length}`, `Games today` / `{num(games)}`, `Trophies today` / `{signed(trophies)}`, `Farmed` / `{hoursText(hours)}`. `dt` at `text-[11px] text-muted`, `dd` with PR 2's `t-figure`. `num` and `signed` come from `lib/format.ts`. No mono, no middle dots.
- `Start all` and `Stop all` render only when `fleet.length >= 2`. `Stop all` is `disabled` with `disabledReason="Nothing is running"` when no instance is running; `Start all` is `disabled` with `disabledReason="Everything is running"` when all are. Read `InstanceCard`'s existing definition of running on the merge base and reuse it; lift it into `lib/states.ts` only if it is already duplicated there.
- `onStopAll` gains the undo the single Stop already has: capture the names that were running before the call and pass `undo` to the toast so it starts exactly those again, with `tone: "ok"` from PR 2. Follow `InstanceCard`'s Stop undo discipline verbatim, including the failure path through `failureMessage`. The toast text is unchanged. A failed undo raises one follow-up toast with `tone: "bad"` and no further action.

- [ ] **Step 1: Write the failing tests.** An undefined query renders skeletons, no totals and no `0 instances`; a one-instance fleet renders no totals row and neither all-control; a two-instance fleet renders the four labelled totals; `Stop all` is disabled when nothing runs; Stop all offers Undo and the undo starts exactly the instances that were running; a rejecting undo says why once.
- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement in this order: skeletons, totals row, control gating, undo.**
- [ ] **Step 4: Run the gate.**

**Acceptance:** nothing numeric appears before the first response; totals are labelled and appear only when they mean something; the larger blast-radius action is at least as reversible as the smaller one.

**Commit:** `feat(fleet): skeletons while loading, a labelled totals row and an undo for Stop all`

---

### Task 7: Card anatomy: one status line, labelled metrics, one way in

**Files:**
- Modify: `brawlfarm/web/src/fleet/InstanceCard.tsx` (`NEXT_LABELS` lines 57-65, `nextValue` lines 84-91, `Metric` lines 93-101, `OfflineBlock` lines 103-116, the name row lines 198-210, the metric grid lines 212-221, the footer lines 223-249)
- Modify: `brawlfarm/web/src/lib/states.ts` (`PHASE_LABELS` lines 32-37, `phaseLabel` lines 96-99)
- Modify: `brawlfarm/web/src/components/ui/Thumb.tsx` (the age stamp lines 116-135)
- Test: `fleet/InstanceCard.test.tsx` (lines 57-255)

**Interfaces after the change:**
- Status in one place. The name row becomes: the stretched `Link` on the name with `t-name`, then `<StateChip state={inst.state} />`, then one muted status line at `text-[12px] text-muted` joining the phase fragment and the frame age with `", "`, for example `queuing, frame 2 s ago`. The port leaves the card: it lives in the instance header as `ADB port 5555` and in Settings where it is edited. Nothing sits on the image any more: remove the corner age stamp from `Thumb.tsx` and keep the `overlay` prop for the offline case only.
- `phaseLabel` never returns a raw token: an unknown phase returns `""` and the status line then shows the age alone. If PR 1 already set `PHASE_LABELS` to sentence case, change only the fallback.
- Metrics. `Metric` gains no props; its label is always words and its value carries `t-figure`. The four are `Games today` / `num(inst.today.games)`, `Trophies today` / `signed(inst.today.trophies)`, `This session` or `Last session` / `duration(sessionMinutes)` with PR 1's empty-value prose, and a fourth that names what it counts down to. Replace `NEXT_LABELS` and `nextValue` with `nextMetric(inst: InstancePayload): { label: string; value: string }`:
  - `farming`, `starting`, `reconnecting`: label `Break at`, value `hhmm(inst.until)`
  - `stopping`: label `Stops`, value `After this match`
  - `scheduled_break`, `stopped`: label `Next session`, value `hhmm(inst.until)`
  - `offline`: label `Retry in`, value `{retryMinutes(inst.note)} min`, or PR 1's empty-value prose when the note carries no number
  A clock time stays `05:25` and a duration stays `1 min`; the label is what says which is which. When `inst.until` is null, use PR 1's empty-value prose, never `none`.
- One way in. Delete the `Open` button from the footer. The footer holds Start or Stop (PR 1 owns which label) plus `Restart`, and the stretched link on the name is the only navigation. `Restart` now opens `ConfirmDialog` with title `Restart {name}?`, body `It stops now, not after this match, and starts again.`, confirm label `Restart`, tone `bad`; the existing call and toast run on confirm, unchanged.
- Offline copy. `OfflineBlock` renders `{note}` verbatim from the payload and keeps the `Open the instance, or {onRetry}.` line. It no longer authors `BlueStacks window not found.` and no longer builds a second sentence from the minute count. If `note` is empty, fall back to PR 1's empty-value prose, never to a blank card.

- [ ] **Step 1: Write the failing tests.** No `5555` anywhere on a card; one status line carrying the phase and the frame age, and no chip or stamp inside the image region; an unknown phase shows the age alone and never the raw token; the metric labels are exactly `Games today`, `Trophies today`, `This session` and the state-dependent fourth, asserted for `farming`, `stopping`, `stopped` and `offline`; no `Open` control; `Restart` asks first and calls the API only after the confirm; the offline block prints the server note byte for byte.
- [ ] **Step 2: Run them and confirm they fail.**
- [ ] **Step 3: Implement in this order: `nextMetric`, the status line plus the Thumb stamp removal, the footer, then `OfflineBlock`.** Update the existing `retryMinutes, breakCaption and nextValue` suite in place: `nextValue` is gone, so its cases move to `nextMetric`.
- [ ] **Step 4: Run the gate.**

**Acceptance:** a card states its status twice at most (chip plus status line) and never three times; every metric label is a phrase a person would say out loud; there is one way to open an instance; the offline sentence has one author, the server.

**Commit:** `feat(fleet): one status line, labelled metrics and one way into an instance`

---

## Verification and whole-branch close-out

- [ ] **Rebase on the merged PR 2 and re-run the gate** from the worktree root.
- [ ] **Whole-branch review on sonnet** before the pull request opens. Findings go to an implementer, then one re-review.
- [ ] **Captures with the playwright-cli skill,** browser session opened from the scratchpad, viewport 1440 wide, against a two-instance mock, in both themes:
  - Fleet loading (three skeleton cards, no totals, no `0 instances`).
  - Fleet resolved with two instances: strip, labelled totals row, two cards with one status line each and four labelled metrics.
  - Fleet with one card offline, showing the server note verbatim.
  - The top bar live, and reconnecting with the connection line under it.
  - The alerts drawer open over a long page (Stats), proving the scrim covers the full viewport and the page behind does not scroll.
  - The instance page bar showing `Fleet / Pie64` with one `h1` in the body.
- [ ] **Keyboard pass:** tab from PR 2's skip link through rail, bar, strip and one card; one ring style throughout; Escape from the drawer returns focus to the Alerts button.
- [ ] **Pull request body lists:** `shell-theme-color` already shipped by PR 2; deferred additive API work (`retry_at` on the instance payload, a restore endpoint behind an undo for Dismiss all, a reconnect countdown out of `useEvents`); and the narrow-screen items held back by the owner's single-PC ruling.
