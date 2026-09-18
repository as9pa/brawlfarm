# Panel PR 6: Settings and setup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Settings reads as six sections a person can scan, with every switch named after what it does, one Danger zone holding the three irreversible actions, and a setup wizard that accepts a typed path, checks off every step it passed and says why the Start switch is missing.

**Architecture:** No new screens. `settings/Schedule.tsx` disappears into `settings/Behavior.tsx`; the three destructive actions gather in one Danger zone at the end of `settings/Data.tsx`; `settings/Instances.tsx` loses its Remove button to that zone. Two additive surface changes: `onEnter` on `Field`, and `GET /api/settings/defaults` so the Advanced Reset link resets to the Python model defaults rather than a second copy of them in TypeScript. `useSetupState.ts` grows one lifted display-pass flag so the rail can check Display.

**Tech Stack:** React 19 and TypeScript under `pnpm`, vitest plus Testing Library, Python 3.13 under `uv`.

**Spec:** the panel critique, items `sched-settings-page`, `set-danger-cues`, `set-confirm-word`, `set-adb-path-clipped`, `set-behavior-jargon`, `set-notifications`, `set-instances-table`, `set-theme-in-about`, `set-saved-caption`, `set-data-path`, `set-behavior-advanced-reset`, `setup-typed-path`, `setup-rail-checks`, `setup-answers-chip`, `setup-done-start`. Layout target: `W_settings()` and `W_setup()` in the critique builder.

**Branch:** `panel/settings-setup`, cut from the tip of the PR 2 branch (this plan assumes PR 1 and PR 2 are merged). Worktree `.claude/worktrees/phase-10`.

## Global Constraints

- No em-dashes and no emoji anywhere: prose, code, comments, tests, commit messages, pull request body.
- Never write the word bsutil or any legacy tag anywhere.
- Nothing under `brawlfarm/core` changes.
- API changes only where a task names the endpoint and keeps them additive. Task 3 adds `GET /api/settings/defaults`. No existing route changes shape. `POST /api/settings/reset` already exists and is reused as is.
- `worker`, `supervisor` and `tick` never appear in a string a person reads.
- Owner rulings that bind every task:
  - About stays About. There is no Appearance section. The theme picker moves to the top of About under a `Theme` heading.
  - One Danger zone, at the end of Settings, in Data: Remove instance (per instance), Delete data (per instance), Reset all settings. Red danger buttons, one sentence each.
  - The Instances table row keeps Edit only.
  - The type-the-word dialogs stay. The word moves out of the placeholder and into the label: `Type Pie64 to confirm`.
  - Behavior switches are named by outcome: Prefer brawlers that win, Skip far-off tiers, Leave the gas early, Hide in bushes, Close the game on stop, Do Not Disturb on start. The flag name is gone from the label.
  - Every Advanced switch gets a second help line saying what happens when it is off, there is a Reset to defaults link with an undo toast, and a Changed tag sits beside any switch that differs from its default.
  - The Schedule settings page becomes a paragraph plus switch inside Behavior. Decided from the code: `settings/Schedule.tsx` is 44 lines and holds exactly one `SettingRow` over `scheduler.default_enabled` and nothing else, so the section earns nothing and the page goes.
  - Saved state is an inline caption naming the section, not a toast fired from three places.
  - Notifications orders its fields by use and gives each a real placeholder.
  - The ADB path field shows the whole path (wrapping mono text, never clipped).
  - The data path is visible and copyable.
  - The wizard accepts a typed adb path with a Check button and Enter, the rail checks every step that passed, the display card names the required size in words and where to set it in BlueStacks, and the Done step says why the Start switch is hidden when there are no instances.
- The implementer must not invent wording. Every string is given here before and after. If a string turns up that this plan does not list, leave it and report it.
- Per `CLAUDE.md`, code review is on: every task gets a spec-compliance and code-quality review pass on **sonnet** before it counts as complete, and the branch gets a whole-branch review on **sonnet** before its pull request opens. Findings are fixed by an implementer, then re-reviewed once.
- Conventional commit subjects with a scope. Every commit message ends with the trailers:

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

`tools/scrub_check.py` must print `0 hit(s)`. Nothing here touches the farm loop, so no live farm pass is required; the wizard walk in the acceptance section stands in for it.

## Blocking dependencies

- PR 1 (`lib/copy.ts`): the required-display-size constant and the ellipsis (U+2026) and apostrophe (U+2019) characters come from there. Grep `brawlfarm/web/src/lib/copy.ts` for the exported size constant and import it; never write a second `1600` literal into a user-facing string. PR 1 already removed `worker` from the Behavior and Connection strings and fixed the Data apostrophe: do not redo those edits, and if a `worker` string is still present, stop and report rather than patching it here.
- PR 2 (kit): `Button` has a `danger` variant, `Switch` has visible disabled and focus states, `Field` has `error` and `help` props, `Toast` has tones and an action slot. Every task below uses those props and adds none of them.

## File Structure

- `brawlfarm/web/src/components/ui/Field.tsx`, `components/ui/ConfirmDialog.tsx`: Task 1.
- `brawlfarm/web/src/settings/Behavior.tsx`, `settings/SettingsNav.tsx`, `settings/Settings.tsx`; delete `settings/Schedule.tsx` and `settings/Schedule.test.tsx`: Task 2.
- `brawlfarm/web/src/settings/Behavior.tsx`, `brawlfarm/api/settings_routes.py`: Task 3.
- `brawlfarm/web/src/settings/Data.tsx`, `settings/Instances.tsx`: Task 4.
- `brawlfarm/web/src/settings/Connection.tsx`, `settings/Data.tsx`, `settings/Instances.tsx`: Task 5.
- `brawlfarm/web/src/settings/Settings.tsx`, `settings/SettingsNav.tsx`, `settings/useSettingsPatch.ts`, `settings/About.tsx`: Task 6.
- `brawlfarm/web/src/settings/Notifications.tsx`: Task 7.
- `brawlfarm/web/src/setup/StepBlueStacks.tsx`, `setup/useSetupState.ts`, `setup/StepDisplay.tsx`, `setup/StepInstances.tsx`, `setup/StepDone.tsx`: Task 8.

---

### Task 1: The dialog names the word, and a field can answer Enter

**Files:** `brawlfarm/web/src/components/ui/ConfirmDialog.tsx:69,84-91`, `components/ui/Field.tsx:14-28`, plus their test files.

Item `set-confirm-word`. Today the word to type is the placeholder and the disabled reason, and the visible label says `Type to confirm`, so the reminder vanishes as soon as anyone types.

- Before: a Field labelled `Type to confirm` with `placeholder={word}`.
- After: the label is built from the `word` prop and reads `Type Pie64 to confirm`, with no `placeholder` prop at all. The `disabledReason` stays `Type <word> to confirm`.
- The match becomes case-insensitive on the trimmed value: compare `typed.trim().toLowerCase()` with `word.trim().toLowerCase()`. Rewrite the docstring paragraph that justifies case sensitivity: the dialog is already scoped to one named instance by its caller, so the typed text is a confirmation, not a folder identifier, and refusing `pie64` buys nothing. Drop the sentence about case-sensitive disks.

Field API after the change: every existing prop unchanged, plus one optional

```ts
  /** Fired on Enter in the input. The caller decides what Enter means. */
  onEnter?: () => void;
```

wired through `onKeyDown`: when the key is Enter, prevent the default and call `onEnter`. Undefined by default, so every existing caller is untouched.

Steps:
- [ ] Edit `ConfirmDialog.tsx`: label, no placeholder, case-insensitive compare, new docstring paragraph.
- [ ] Add `onEnter` to `FieldProps` and the input.
- [ ] Extend `ConfirmDialog.test.tsx`: the text `Type Pie64 to confirm` is still visible after typing `Pie`; `pie64` enables confirm; before that the confirm button is disabled and its reason names the word.
- [ ] Extend `Field.test.tsx`: Enter calls `onEnter` once; a field without `onEnter` does not throw on Enter.
- [ ] Run the gate block.

**Commit:** `feat(kit): name the confirm word in the label and let a field answer Enter`

---

### Task 2: Behavior switches say what they do, and Schedule folds in

**Files:** `brawlfarm/web/src/settings/Behavior.tsx:62-68,129`, `settings/SettingsNav.tsx:40-44`, `settings/Settings.tsx:44,56-58`, `settings/Behavior.test.tsx`, `settings/Settings.test.tsx`; delete `settings/Schedule.tsx` and `settings/Schedule.test.tsx`.

Items `set-behavior-jargon` (the basic list only; Advanced is Task 3) and `sched-settings-page`.

BASIC rows, before to after, settings keys unchanged:

| key | before label | after label | after description |
| --- | --- | --- | --- |
| winrate_aware | Win-rate aware | Prefer brawlers that win | Picks the brawler with the best win rate in the current step. |
| opportunity_cost | Opportunity cost | Skip far-off tiers | Skips brawlers whose next tier is more than a session away. |
| gas_aware | Gas aware | Leave the gas early | Moves away from the gas one ring sooner. |
| bush_hide | Bush hide | Hide in bushes | Hides in bushes when the map allows. |
| close_game_on_stop | Close game on stop | Close the game on stop | Closes Brawl Stars when the instance stops. |
| dnd_at_start | DND at start | Do Not Disturb on start | Turns on Do Not Disturb when the instance starts. |

The Switch `label` prop keeps taking the same string as the row title, so the accessible name moves with the visible one.

The Schedule row renders last in the basic block as its own `SettingRow`, not through the `behavior()` helper, because it writes `scheduler.default_enabled` rather than a behavior key:

- Title: Schedule
- Description: New instances follow the schedule: two to four sessions a day at random times, 1 to 3 h each, never the same hours two days running. Change the hours for one instance on its own page.
- Error: `fieldError(fieldErrors, "scheduler.default_enabled")`
- Switch label: Schedule on by default

Before writing that description, read the scheduler module under `brawlfarm/core` (read only) and confirm the session count, the length range and the no-repeat-hours claim. Keep the parts that match the code, drop the parts that do not, and report the difference. Do not invent a number.

Nav and routing:
- `SETTINGS_SECTIONS` in `SettingsNav.tsx`: remove the `schedule` entry. The `behavior` description becomes: How an instance plays, and the schedule new instances start with.
- `Settings.tsx`: remove the `schedule` case. The URL `/settings/schedule` then falls through to the existing unrecognised-section `ErrorBlock`; change nothing else there.
- Delete `settings/Schedule.tsx` and `settings/Schedule.test.tsx`. Afterwards grep for Schedule under `settings/` and confirm only `instance/Schedule.tsx` remains: that is a different component and is not touched.

Steps:
- [ ] Rename the six basic rows.
- [ ] Verify the schedule sentence against the scheduler code, then add the Schedule row.
- [ ] Drop the nav entry, the route case and the two files.
- [ ] Extend `Behavior.test.tsx`: the six new labels render; Win-rate aware, Gas aware and DND at start are absent; toggling Schedule patches `scheduler.default_enabled`.
- [ ] Extend `Settings.test.tsx`: the nav lists six sections and no Schedule link.
- [ ] Run the gate block.

**Commit:** `feat(settings): name behavior switches by outcome and fold Schedule into Behavior`

---

### Task 3: Advanced says what off costs, flags what changed, and can go back

**Files:** `brawlfarm/web/src/settings/Behavior.tsx:71-88,89-132`, `brawlfarm/api/settings_routes.py` (new route after `read_settings`), the existing settings-routes pytest module (grep tests for api/settings), `settings/Behavior.test.tsx`.

Item `set-behavior-advanced-reset` plus the Advanced half of `set-behavior-jargon`.

The defaults are the pydantic model defaults in `brawlfarm/settings.py`, which `POST /api/settings/reset` already leans on. Do not copy them into TypeScript. Add one read-only route:

```python
@router.get("/api/settings/defaults")
async def read_settings_defaults() -> dict:
    """Every section at its model default, with no instances. Read only: nothing is saved
    and nothing is applied, so the panel can show what a switch would go back to."""
    return S.AppSettings().model_dump(mode="json")
```

The web side fetches it once when Advanced first expands and holds it in component state. If that fetch fails, the Changed tags and the Reset link are not rendered and no error is shown: neither is load bearing.

ADVANCED rows, before to after. The second help line is new on every row.

| key | before label | after label | second help line |
| --- | --- | --- | --- |
| fast_input | Fast input | Faster taps | Off: taps go through the slower path. |
| raw_cap | Raw capture | Raw frames | Off: frames are re-encoded before they are read. |
| gray_match | Gray matching | Grayscale matching | Off: templates match in colour. |
| phase_classify | Phase classify | Match phase detection | Off: the match phase is worked out from timing instead of the screen. |
| ability_buttons | Ability buttons | Use abilities | Off: the gadget and super buttons are left alone. |
| recalib_tripwire | Recalibration tripwire | Warn when the season changed the screens | Off: no warning when a season changes the screens. |
| dnd_off_on_stop | DND off on stop | Do Not Disturb off on stop | Off: Do Not Disturb stays on after the instance stops. |

Two first help lines also change, because they carry the jargon the item flags. `recalib_tripwire` becomes: Warn when the screens stop matching what brawlfarm expects. `dnd_off_on_stop` becomes: Turn Do Not Disturb back off when the instance stops. The other five keep the help line they have.

The two lines render as one description node (first line, a `<br />`, second line) so `SettingRow` and its `aria-describedby` wiring are unchanged.

- Changed tag: beside the row title, when the stored value differs from the same key in the defaults document, render a `Chip` with tone idle reading Changed. Basic rows get no tag.
- Reset to defaults: a `Button` with variant text reading Reset to defaults at the end of the expanded block. It writes every advanced key back to the defaults document in one `saveSetting` call, then raises a toast reading "Advanced switches back to defaults" with the action Undo, which restores the snapshot taken before the patch in one `saveSetting` call. Disabled with `disabledReason="Already at the defaults"` when nothing differs.
- `aria-expanded` goes on the Show / Hide button, with `aria-controls` pointing at the id of the Advanced block.

Steps:
- [ ] Add the route, plus a pytest asserting 200, an empty instances list, and an advanced section equal to the model default.
- [ ] Rename the seven rows and add the off lines.
- [ ] Fetch the defaults on first expand; render Changed; add the Reset link with its undo toast; add `aria-expanded` and `aria-controls`.
- [ ] Extend `Behavior.test.tsx`: an off line shows for each Advanced row; a switch differing from the mocked defaults shows Changed and a matching one does not; Reset patches every advanced key and the toast Undo restores the prior values; Show toggles `aria-expanded`.
- [ ] Run the gate block.

**Commit:** `feat(settings): advanced switches say what off costs and can go back to defaults`

---

### Task 4: One Danger zone at the end of Settings

**Files:** `brawlfarm/web/src/settings/Data.tsx:76-125`, `settings/Instances.tsx:350-361,393-400`, `settings/Data.test.tsx`, `settings/Instances.test.tsx`.

Item `set-danger-cues`. Today Remove is an accent text button identical to Edit, Delete data is an accent link on a plain row, and only Reset gets a red box.

Instances: delete the Remove button (`Instances.tsx:359-361`), its removing state and its `ConfirmDialog` block (393-400). The row keeps Cancel and Save while editing, and Edit otherwise. Move the removal call, the `PUT /api/settings` with that instance filtered out, into `Data.tsx` with its behaviour unchanged, including the 409 path whose detail reads "Stop Pie64 before removing it". That detail renders as the error line on the zone row, not as a toast.

Data, after Open data folder, one section that replaces both the per-instance delete list and the red Reset box:

```
Danger zone
These cannot be undone.
  Remove Pie32 from the fleet     Its data folder stays on disk.                                            [Remove]
  Delete the data for Pie32       Status, farm plan, schedule, games and past sessions. The instance stays.  [Delete data]
  Reset all settings              Instances and their data folders stay.                                     [Reset]
```

- Remove and Delete data repeat per instance, in settings instance order. The old "Delete one instance data" heading and its list go.
- Every button is a `Button` with variant danger (PR 2). No per-row red box and no accent-override wrapper on these three; the zone itself is one container with `border border-bad rounded-[10px] p-3`.
- Both dialogs stay `ConfirmDialog` with tone bad and, after Task 1, read "Type Pie32 to confirm". Reset keeps its existing non-typed confirm dialog, its wording (title "Reset all settings?", confirm "Reset") and its "Settings reset" toast.
- `data-private` stays on anything printing a path or an instance folder.

Steps:
- [ ] Move remove-instance from Instances into Data, with its 409 handling and its row error line.
- [ ] Build the Danger zone, fold the delete list into it, drop the old Reset box.
- [ ] Extend `Instances.test.tsx`: no Remove control in a row; Edit still there.
- [ ] Extend `Data.test.tsx`: the three actions sit under Danger zone; each button carries the danger variant; Remove and Delete data each require the typed instance name; a 409 from Remove shows its sentence on the row.
- [ ] Run the gate block.

**Commit:** `feat(settings): gather the three irreversible actions in one danger zone`

---

### Task 5: Paths you can read and copy, and a table header a person understands

**Files:** `brawlfarm/web/src/settings/Connection.tsx:37-49,88-117`, `settings/Data.tsx:78-86`, `settings/Instances.tsx:222-260,313,377-381`, plus the three test files.

Items `set-adb-path-clipped`, `set-data-path`, `set-instances-table`.

Connection:
- The adb path Field gets `width="full"` and the input wraps (`break-all`) so the whole path shows on two lines instead of clipping at the box edge. It stays mono.
- While the mount scan runs, show a `Chip` with tone idle reading Scanning plus the ellipsis character, beside the text "Asking adb for devices", matching `StepBlueStacks.tsx:82-93`.
- The Not found chip gains a next step under it: Not found. Install BlueStacks, or type the path to HD-Adb.exe above.
- A Check token button beside the API token field, calling the existing connection check route. Grep `brawlfarm/api/connection.py` for a route that validates the token without side effects and reuse it. If there is none, skip this bullet and report it: do not add an endpoint in this task.

Data: under Open data folder, print the home path from the health payload in a mono block with `data-private`, plus a Copy button beside it. Copy calls `navigator.clipboard.writeText` and raises the toast "Path copied"; a rejected promise raises an error-tone toast reading "Could not copy the path. Select it and copy by hand." Tests stub the clipboard with `vi.stubGlobal`.

Instances: the header ADB port becomes Port with `title="The adb port BlueStacks listens on"`; the player tag placeholder becomes a real example tag plus the ellipsis character instead of the word TAG; under the Scan again and Add a port buttons, a help line reading "Scan again finds running BlueStacks instances."; the save error paragraph is wrapped in `aria-live="polite"`.

Steps:
- [ ] Connection: full-width wrapping path, scanning chip, not-found next step, token check or the report.
- [ ] Data: mono path plus Copy.
- [ ] Instances: header, placeholder, help line, aria-live.
- [ ] Extend the three suites: the long path is present in full in the DOM; the scanning chip appears before the scan resolves; the not-found sentence renders; Copy writes the path and toasts; the header reads Port; the help line renders.
- [ ] Run the gate block.

**Commit:** `fix(settings): show the whole adb path, make the data path copyable, explain the scan`

---

### Task 6: One saved caption that names its section, and Theme at the top of About

**Files:** `brawlfarm/web/src/settings/Settings.tsx:56-68`, `settings/SettingsNav.tsx`, `settings/useSettingsPatch.ts:52-56`, `settings/Instances.tsx` (its local success toast), `settings/Data.tsx`, `settings/About.tsx`, `settings/useSettingsPatch.test.tsx`, `settings/Settings.test.tsx`, `settings/About.test.tsx`.

Items `set-saved-caption` and `set-theme-in-about`.

- `useSettingsPatch` stops raising the "Settings saved" toast on a successful field save and instead exposes `savedAt: string | null`, formatted by the existing `hhmm` helper. Failure toasts stay exactly as they are.
- `Settings.tsx` renders the caption beside the section subtitle, reading the section label from `SETTINGS_SECTIONS` (already the single source of the labels), so Behavior shows "Behavior saved 05:22" in muted 12 px text inside an `aria-live="polite"` wrapper. Nothing renders while `savedAt` is null.
- Remove the duplicated success toast from the Instances success handler and from the field-save path in `Data.tsx`. The destructive-action toasts in Data ("Settings reset" and the delete confirmation) are not field saves and stay.
- Remove the Saved caption from `SettingsNav.tsx`.
- The footer sentence pasted into both Connection and Behavior keeps one copy, in Behavior, reading: Applies to an instance the next time it starts. If PR 1 already rewrote that sentence, keep the PR 1 wording and only delete the duplicate.
- `About.tsx`: move the theme picker to the top of the component under an h3 reading Theme, above the version and links block. No section rename, no Appearance heading, nav label and description unchanged.

Steps:
- [ ] Move the saved signal from three toasts to one caption.
- [ ] Delete the duplicated footer sentence.
- [ ] Reorder About.
- [ ] Extend the suites: a successful save raises no toast and shows "Behavior saved 05:22" in a polite live region; Theme renders before the version string in the About DOM order.
- [ ] Run the gate block.

**Commit:** `fix(settings): one saved caption that names the section, theme at the top of About`

---

### Task 7: Notifications in the order people use it

**Files:** `brawlfarm/web/src/settings/Notifications.tsx:138-139,186-194`, `settings/Notifications.test.tsx`.

Item `set-notifications`.

- Field order: ntfy topic, Webhook URL, Healthchecks URL. Placeholders in that order, each ending with the ellipsis character: brawlfarm-alerts, then the Slack hooks URL prefix, then the hc-ping URL prefix.
- The test toast is built from the field labels, never the payload keys: one channel reads "Test sent to ntfy topic.", two read "Test sent to ntfy topic and Webhook URL.", three read "Test sent to ntfy topic, Webhook URL and Healthchecks URL." Join with commas and a final and.
- The seven event checkboxes become one column in this order: Crash, Instance offline, Wrong resolution, Recalibration needed, Wrong mode, Stopped, Recovery. Keep the existing labels where they already read that way; change only the order and the column count.

Steps:
- [ ] Reorder the fields and add the placeholders.
- [ ] Build the toast from labels.
- [ ] One column, severity order.
- [ ] Extend `Notifications.test.tsx`: the placeholders render; the toast names labels and never a key such as ntfy; the checkbox DOM order matches the list above.
- [ ] Run the gate block.

**Commit:** `fix(settings): order the notification fields by use and name channels by their labels`

---

### Task 8: The wizard accepts a typed path, checks what passed, and explains the missing switch

**Files:** `brawlfarm/web/src/setup/StepBlueStacks.tsx:96-125`, `setup/useSetupState.ts:105-127`, `setup/StepDisplay.tsx:62,71-73`, `setup/StepInstances.tsx:30-35`, `setup/StepDone.tsx:75-79,110-120`, and the five matching test files.

Items `setup-typed-path`, `setup-rail-checks`, `setup-answers-chip`, `setup-done-start`.

**Typed path.** `run(path)` already takes a candidate path, so no new fetch is needed. Add a Check button (variant quiet) beside the path field that calls `run(typed)`, and pass `onEnter` (Task 1) calling the same thing. Help line under the field: Press Enter or Check to test this path. Split the two failure cases that share one message today: when the request itself failed, the `ErrorBlock` shows the failure and the Continue disabled reason becomes "Check the path again"; when the check ran and found nothing, Continue keeps the reason "Find HD-Adb.exe first" and the Field shows the error "No HD-Adb.exe at that path." Scan again stays as it is.

**Rail checks.** In `useSetupState.ts`:
- `bluestacks` becomes true when `settings.connection.adb_path` is not empty, so a return visit shows a check instead of a numeral. Drop the `scan` dependency from that entry only.
- `display` stops being hardcoded false. Lift a `displayPassed` boolean into `useSetupState` with a setter handed to `StepDisplay` the way `setScan` is handed to `StepBlueStacks`, and read it for the display entry. It stays this-visit-only like `statsSkipped`, and the comment says so.
- The done entry becomes true when the current step is done.
- Landing: when the adb path is set and there is at least one instance, land on done rather than display. `StepDone` then needs a "Run the checks again" button that sets the step back to bluestacks. Update the landing docstring to say why.

**Display card.** The wrong-size chip reads Wrong size, needs 1600 x 900 using the multiplication sign U+00D7 rather than the letter x, and the measured line uses the same character. Under it, the fix sentence: In BlueStacks: Settings, Display, Custom, 1600 x 900 (same character), DPI 240. The required size text comes from the exported constant in `lib/copy.ts` (PR 1), not from a fresh literal.

**Instances chip.** The reachable-port chip reads Reachable instead of Answers. No answer stays.

**Done step.** Where the "Start Pie64 now" switch is hidden because there are no instances, render "Add an instance to start farming." with a link to `/settings/instances`. The footer that names config.toml becomes: Everything is saved as you go.

Steps:
- [ ] BlueStacks: Check button, Enter, split failure messages.
- [ ] `useSetupState`: the four done entries and the landing change, with the docstring.
- [ ] Display card, instances chip, Done step line and footer.
- [ ] Extend the suites: typing a path and pressing Enter enables Continue with no Scan again click; a rejected check shows its own message; `useSetupState.test.tsx` asserts the display entry turns true after the setter and that a configured install lands on done; the wrong-size chip names the required size; Reachable replaces Answers; the no-instance line renders in place of the switch.
- [ ] Run the gate block.

**Commit:** `feat(setup): accept a typed adb path, check every passed step, explain the hidden start switch`

---

## Acceptance criteria for the branch

- The gate block passes at every commit, with `0 hit(s)` from `tools/scrub_check.py`.
- A fresh-config wizard walk: point `BRAWLFARM_HOME` at an empty temp directory (the env var the data home reads; confirm with `grep -rn BRAWLFARM_HOME brawlfarm/core`), start the API and the panel against it, and walk BlueStacks through to Done. Typing the adb path and pressing Enter must unlock Continue with no Scan again click. Every step that passed carries a check in the rail. Reload the setup URL and confirm it lands on Done with Run the checks again.
- Every destructive flow still refuses to fire until the instance name is typed: Remove and Delete data, from the Danger zone, for two different instances. Reset all settings still asks its own confirm.
- No string a person reads contains worker, supervisor, tick, Win-rate aware, DND at start, Answers or ADB port.
- Captures at 1440 of each section (Instances, Connection, Behavior with Advanced expanded, Notifications, Data with the Danger zone, About) and of the BlueStacks, Display and Done steps, taken with the `playwright-cli` skill from the scratchpad, attached to the pull request.
- The pull request body lists: the deleted Schedule page, the new `GET /api/settings/defaults` route, the Remove button moving from Instances to Data, the return-visit landing change, and anything a task was told to report rather than fix.

## Risks and open questions

- The return-visit landing change (Task 8) is the only behaviour change a returning owner will feel: the wizard opens on Done instead of Display. If Done reads badly without a fresh display check, keep the landing on Display and check the rail entries only, and say so in the pull request body.
- The Schedule sentence in Task 2 asserts session counts and lengths the audit says are documented nowhere. It must be verified against the scheduler code before it ships.
- `Check token` in Task 5 depends on a token-validation route existing. If `brawlfarm/api/connection.py` has none, that bullet is dropped rather than turned into an API task.
- Making the confirm dialog case-insensitive (Task 1) reverses a documented decision. It is safe because the dialog is always scoped to one named instance by its caller, but it is the one item here an owner may want back.
