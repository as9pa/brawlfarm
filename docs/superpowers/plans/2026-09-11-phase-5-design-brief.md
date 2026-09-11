# Phase 5 design brief: Setup wizard and Settings

This is the binding design for the phase 5 implementation plan. Plan writers copy its
values verbatim; they do not re-decide anything here. Facts about the existing API and the
existing web code come from `phase5-explore-contracts.md` in the session scratchpad, every
line of which was re-read against the source before this brief was written; the spec is
`docs/superpowers/specs/2026-09-10-brawlfarm-design.md` (section 8 is the UI, section 9 the
safety rails, section 10 hygiene, section 11 testing). The phase 4 brief next to this file
is the template and the inheritance: its tokens, state vocabulary, copy rules, API client
conventions and test conventions carry into phase 5 unchanged. The owner accepted all 21
proposal items (ids listed at the end) with no notes, then answered the follow-up page on
2026-09-11; those answers are written below as decided.

## 1. Outcome

`brawlfarm` has a first-run path and a settings screen. `/setup` is a five-step wizard
(BlueStacks, Instances, Display, Stats, Done) rendered outside the shell that takes a new
user from "BlueStacks installed" to "first instance farming" without editing a file, saving
after every step. `/settings/:section` has seven sections (Instances, Connection, Behavior,
Schedule, Notifications, Data, About) that save on change with a "Saved HH:MM" caption and
never show a Save button. Five small API additions back them: a notifications test, a
settings reset, an open-data-folder call, a delete-instance-data call, and one corrected
copy string. Two one-line bugs are fixed on the way: the wizard persists the discovered adb
path (the phase 3 deferred item) and a blank API token stops being sticky.

## 2. What phase 5 inherits unchanged (decided)

- Tokens, fonts, type scale, radii, motion and the focus ring: sections 2 and 3 of the
  phase 4 brief, already shipped in `brawlfarm/web/src/styles/theme.css`. No new token, no
  new font, no new icon library. Icons stay `lucide-react` at 16 px, `strokeWidth={1.6}`.
- The state vocabulary in `lib/states.ts` (seven states, phase captions, alert kind chips,
  tones) is not edited. The notification event list in Settings uses its own label map
  (section 9); do not "unify" the two, they name different things.
- Copy rules: no em-dashes, no emoji, no exclamation marks, state is a word plus a colour,
  and copy says what happened, what went wrong and how to fix it.
- `api/client.ts` (`ApiError`, `errorFrom`, `NETWORK_DETAIL`), `api/queries.ts`
  (`queryKeys`, `createQueryClient` with `staleTime: 5000, retry: 1`), `lib/toast.ts`
  (`toast`, `failureMessage`, `TOAST_MS`) and `lib/time.ts` (`hhmm`) are used as they are.
- The phase 4 components keep their props exactly: `Button`, `StateChip`, `Chip`, `Switch`,
  `Segmented`, `Toast`/`Toaster`, `Drawer`, `ErrorBlock`, `Thumb`. `Field` grows two
  optional props and nothing else (section 5).
- Test conventions: vitest plus `@testing-library/react`, with `stubFetch`, `jsonResponse`
  and `renderWithProviders` from `web/src/test/`; pytest with `make_client`,
  `build_settings` and `FakeWorld` from `tests/apihelpers.py`, and setup tests monkeypatch
  `discover.find_adb`, `discover.scan`, `discover.probe_port` and `checks.display_check`
  rather than spawning adb.
- Fleet, Instance, Rail, TopBar and AlertsDrawer are not redesigned. Exactly three edits
  reach them: the Fleet empty state (section 7), the rail's "soon" tag on Settings (gone;
  Stats keeps its), and `pageTitle` (section 3). Stats stays the phase 4 placeholder
  "Stats arrive in phase 6."
- `config.toml` stays the single source of truth, written by the API and never by the UI.
  `GET /api/settings` keeps returning the whole document including the token in full: the
  API is loopback-only, and the Settings screen is what masks it.

## 3. Routes and layout (decided)

| Route | Renders |
| --- | --- |
| `/setup` | `setup/Setup.tsx`, outside `Shell`, no rail, no top bar |
| `/settings` | `<Navigate to="/settings/instances" replace />` |
| `/settings/:section` | `settings/Settings.tsx` inside `Shell` |

- `App.tsx` splits its `<Routes>` in two so the wizard escapes the shell:
  `<Route path="/setup" element={<Setup />} />` beside `<Route path="*" element={<ShellRoutes />} />`,
  where `ShellRoutes` is the existing `<Shell>` wrapping today's routes plus the two
  settings routes. The theme bootstrap and the live handlers stay in `Panel` above both, so
  the wizard follows the theme and the event stream is opened once.
- Wizard layout: full window on `--ground`; the wordmark (the 10 px gold square plus
  "brawlfarm", copied from `Rail`) fixed top-left at 16 px; content a centred column
  720 px wide; the step rail a vertical list of five numbered steps to the left of the
  column at >= 1000 px, and a horizontal row of five numbers above the column below that.
- Settings layout: the shell rail stays. Inside the content, a second-level left nav
  200 px wide (`settings/SettingsNav.tsx`, `NavLink` per section so `aria-current` is
  free), then the section: title 20 px, one muted description line, then the rows. Under
  820 px the second-level nav becomes a horizontal scrolling row above the section.
- `TopBar.pageTitle` changes from an exact-match lookup to: instance prefix first (as
  today), then `pathname.startsWith("/settings")` returns "Settings", then the existing
  map. The rail keeps `to="/settings"`, so `NavLink` without `end` stays active across
  every section.
- Section ids in nav order: `instances`, `connection`, `behavior`, `schedule`,
  `notifications`, `data`, `about`. An unknown `:section` renders `ErrorBlock` with the
  detail "unknown settings section".

## 4. Settings data layer: `useSettingsPatch` (decided)

`web/src/settings/useSettingsPatch.ts`. One hook, used by every settings section and by
every wizard step, so there is exactly one way a setting reaches disk.

```ts
export interface SettingsPatch {
  settings: AppSettings | undefined;
  patch: (mutate: (draft: AppSettings) => void) => Promise<void>;
  savedAt: string | null;                  // "19:04", hhmm of the last successful PUT
  fieldErrors: Record<string, string>;     // keyed by the API's dotted loc
  sectionErrors: string[];                 // anything the mapper could not place
  pending: boolean;
}
export function useSettingsPatch(): SettingsPatch;
```

- `patch` does GET `/api/settings` fresh (never the cached copy), applies `mutate` to a
  structured clone of the response, PUTs the whole document, writes the response into
  `queryKeys.settings()` with `setQueryData`, invalidates `queryKeys.settings()` and, when
  the draft touched `instances`, `queryKeys.instances()`.
- Patches queue: a module-level promise chain means a second `patch` starts only after the
  first resolves, so two quick switch flips never race and no PUT overlaps another PUT.
- On success `savedAt` becomes `hhmm(new Date().toISOString())` and `fieldErrors` clears.
  Each section renders the caption "Saved 19:04" (muted, 11 px) beside its title.
- On an `ApiError` with status 422, `settingsFieldErrors(error.detail)` fills `fieldErrors`
  and `sectionErrors`, and the cached document is left as it was. On 409 the detail goes to
  the caller (the Instances row renders it inline, section 8). On any other failure the
  section shows `ErrorBlock` with the error.
- No Save buttons anywhere. Switches, radios and checkboxes write on change; text and
  number fields write 500 ms after the last keystroke (the same debounce the phase 4 farm
  plan goal uses) and immediately on blur.

The mapper is pure and lives in the same file:

```ts
/** settings._explain joins pydantic errors as "loc: msg; loc: msg" in one string. Split on
 * "; " then the first ": "; a piece that does not split lands in `rest`. */
export function settingsFieldErrors(detail: string): {
  fields: Record<string, string>;
  rest: string[];
};
```

A field renders its error as `${loc.split(".").pop()}: ${msg}`, so
`"connection.adb_path: file not found"` shows under the ADB path field as
"adb_path: file not found". `rest` renders as lines under the section title.

## 5. Foundations: new components (props are the contract)

`components/ui/`:

- `useFocusTrap(open: boolean, ref: RefObject<HTMLElement | null>, onClose: () => void)`
  in `components/ui/useFocusTrap.ts`: the trap lifted out of `Drawer.tsx` verbatim (focus
  in on open, Tab cycles, Escape closes through a ref so an inline `onClose` does not
  re-run the effect, focus returns to the opener). `Drawer` then calls it and keeps its
  props and behaviour byte-for-byte; its existing tests must pass unchanged.
- `Dialog` props `{ open: boolean; onClose: () => void; title: string; children: ReactNode; actions?: ReactNode }`.
  Centred, 480 px wide, `--panel` on a `--scrim` backdrop, radius 10 px, `role="dialog"`
  with `aria-modal="true"` and `aria-labelledby` pointing at the title. Uses
  `useFocusTrap`. A click on the backdrop closes it; a click inside does not.
- `ConfirmDialog` props `{ open; onClose; title: string; body: ReactNode; word: string; confirmLabel: string; tone: "bad"; onConfirm: () => void | Promise<void> }`.
  Wraps `Dialog`: the body, then a mono `Field` labelled "Type to confirm" with
  `placeholder` = `word`, then actions Cancel (text) and the confirm button (primary, bad
  tone) disabled with `disabledReason` "Type ${word} to confirm" until the trimmed typed
  value equals `word` exactly, case sensitive. The typed value resets whenever `open`
  turns false.
- `Table` props:

  ```ts
  export interface Column<Row> {
    key: string;
    label: string;
    mono?: boolean;
    width?: string;                    // a CSS grid track, e.g. "120px"
    render?: (row: Row) => ReactNode;  // a status chip column is an ordinary render
  }
  export interface TableProps<Row> {
    columns: readonly Column<Row>[];
    rows: readonly Row[];
    rowKey: (row: Row) => string;
    empty: ReactNode;
  }
  ```

  A real `<table>` with `<th scope="col">`; a column with no `label` still gets a
  `<th class="sr-only">` so screen readers are not handed a blank header. `mono` puts
  `font-mono tabular-nums` on the cell. `empty` renders in one full-width cell when `rows`
  is empty. Row hover is `--panel-2`, borders are the 1 px `--line`.
- `Field` grows two optional props and nothing else, so every phase 4 call site renders
  identically: `type?: "text" | "number" | "password"` and
  `width?: "control" | "full"` (default `"control"`, today's `w-24`). With
  `type="password"` the input renders as a password field with `autoComplete="off"`, and a
  trailing icon button toggles it to text; the button's accessible name is "Show" when the
  value is hidden and "Hide" when it is visible (lucide `Eye` / `EyeOff`). Revealing is
  component state only: the value is never logged, never written anywhere but the query
  cache and the request body.
- `settings/SettingRow.tsx` props `{ title: string; description: string; error?: string; children: ReactNode }`:
  the title (13 px), the sentence (12 px muted), the control to the right, the error line
  (12 px, `--bad`) under both. Every Behavior, Schedule, Connection and Notifications row
  uses it, which is what makes "one plain sentence per setting" a structure rather than a
  habit.

## 6. API additions (Python, decided)

All loopback-only through the existing middleware. No auth, no CORS. `LIVE_STATES` moves
from `brawlfarm/api/settings_routes.py` to `brawlfarm/api/deps.py` unchanged, because two
routers now need it; `settings_routes.py` imports it from there.

**a. Display copy.** `brawlfarm/setup/checks.py` `DISPLAY_HINT` becomes exactly:

```
"Set the display to 1600 x 900 and pixel density 240 in BlueStacks: Settings, Display, "
"then restart the instance."
```

The owner confirmed the BlueStacks path is Settings, Display, and that resolution and
pixel density are the only two options there. `tests/test_setup_checks.py` asserts
`"Settings, Display" in result.hint` instead of `"Settings > Display"`;
`tests/test_api_setup_routes.py` compares against the constant and needs no change.

**b. `notify.send_test`.** New pure function in `brawlfarm/core/notify.py`:

```python
def send_test(*, webhook_url: str, ntfy_server: str, ntfy_topic: str,
              healthchecks_url: str) -> dict[str, bool]:
```

It posts to the values it was handed and touches none of the module's configured state:
no `_overrides`, no `configure()`, no `configured()`, no cooldown. It reuses `_send_discord`
and `_send_ntfy` with title "brawlfarm test" and message
"This is a test alert from brawlfarm." and, for healthchecks, one GET of the ping URL.
The returned dict has a key only for a channel whose value is non-empty, in the order
`webhook`, `ntfy`, `healthchecks`; a channel that raises counts as `False`, never as an
exception. `requests` is imported lazily as the module already does.

**c. `POST /api/notifications/test`** in a new `brawlfarm/api/notify_routes.py`, registered
in `app.py` after `settings_routes`. No body. Reads `sup.settings.notifications`, calls
`send_test` through `asyncio.to_thread`, and returns
`{"sent": [names that returned True], "failed": [names that returned False]}`. With no
channel configured it returns `{"sent": [], "failed": []}`; the UI does not call it in that
case. Always 200. Never logs a URL or a topic.

**d. `POST /api/settings/reset`** in `settings_routes.py`. Builds
`S.AppSettings(instances=list(sup.settings.instances))`, so every other section returns to
its model default and the instances list survives untouched. Then `S.save`,
`sup.apply_settings`, `sup.poke()`, and returns `new.model_dump(mode="json")` (200). No
409 is reachable: nothing is removed.

**e. `POST /api/settings/open-data-folder`** in `settings_routes.py`. 204. On Windows,
`await asyncio.to_thread(os.startfile, str(get_home(request)))`. Anywhere else, 501 with
detail "Only on Windows" (guarded on `sys.platform != "win32"`, before touching `os`). An
`OSError` from `startfile` becomes 500 with detail "could not open the data folder"; the
path is not put in the message.

**f. `DELETE /api/instances/{name}/data`** in `brawlfarm/api/instances.py`. 204.
`resolve_instance` supplies the 404 "unknown instance" for an unknown or unmatchable name.
409 with detail `f"Stop {name} before deleting its data"` when that instance's view state
is in `LIVE_STATES`. Then `target = S.instance_dir(home, inst.name).resolve()` and
`root = (Path(home) / "instances").resolve()`; when `not target.is_relative_to(root)` the
answer is 400 "refusing to delete outside the data folder". A missing folder is 204 (the
call is idempotent). Otherwise `shutil.rmtree(target)` through `asyncio.to_thread`; an
`OSError` becomes 409 with detail `f"could not delete {name}'s data; a file is still in use"`.
The instance stays in `config.toml`: this deletes the folder, not the instance.

**g. Sticky token.** `brawlfarm/supervisor/loop.py:87` becomes

```python
config.API_TOKEN = settings.connection.brawl_api_token or os.environ.get("BRAWL_API_TOKEN", "")
```

so clearing the token in Settings clears the applied one instead of keeping the last
non-blank value forever, while `BRAWL_API_TOKEN` stays the developer override the spec
promises. `os` is already imported. One test: apply settings with a token, apply settings
with a blank token, assert `config.API_TOKEN == ""` with the environment variable unset.

Everything else in the API stays as it is. `POST /api/setup/scan|test|display-check`,
`GET|PUT /api/settings` and every instance route keep their current shapes.

## 7. Setup wizard (decided)

Files: `web/src/setup/Setup.tsx`, `StepRail.tsx`, `useSetupState.ts`,
`StepBlueStacks.tsx`, `StepInstances.tsx`, `StepDisplay.tsx`, `StepStats.tsx`,
`StepDone.tsx`, and `web/src/api/setup.ts`.

One route, five steps held in component state; refreshing lands on the derived step. Every
step writes through `useSettingsPatch`, so the API stays whole-document and the wizard is
what finally persists `connection.adb_path`.

`useSetupState.ts` derives step completion from the settings document and the last scan:

| Step | Id | Done when |
| --- | --- | --- |
| 1 BlueStacks | `bluestacks` | the last scan returned `adb_found: true` and `connection.adb_path` equals that scan's `adb_path` (the step writes it, so this converges on the first pass) |
| 2 Instances | `instances` | `settings.instances` is non-empty |
| 3 Display | `display` | never persisted; it re-runs on every visit |
| 4 Stats | `stats` | `connection.brawl_api_token` is non-empty, or any selected instance has a `player_tag`, or the step was skipped this visit (a ref, not saved) |
| 5 Done | `done` | the summary; reaching it is the only meaning |

Landing step: the first of BlueStacks, Instances that is not done, otherwise Display.
Display is never skipped because nothing about it is stored. Stats and Done are reached
only by walking forward. In the step rail a done step carries a lucide `Check`, the current
one is accent, later ones are muted; a step is clickable when its index is at or below the
current one, so you can go back and cannot skip forward.

**Step 1 BlueStacks.** Runs `POST /api/setup/scan` on entry (a mutation, not a cached
query). While it runs: an idle `Chip` "Scanning" and the muted line "Asking adb for
devices". On `adb_found`, the path in mono with an ok `Chip` "Found", and the step patches
`connection.adb_path` to the returned path, which raises the toast "Saved to config.toml".
On failure, a full-width `Field` "Where is BlueStacks installed" (placeholder
`C:\Program Files\BlueStacks_nxt\HD-Adb.exe`) whose value is sent as the scan body's
`adb_path`, plus the line "brawlfarm needs HD-Adb.exe from the BlueStacks folder." Buttons:
"Scan again" (quiet), "Continue" (primary, disabled with reason "Find HD-Adb.exe first").

**Step 2 Instances.** `Table` over the scan's `instances`: checkbox, "Name" (mono),
"Display name", "ADB port" (mono), "Status", and a "Test" text button per row. Status chips
are ok "Answers", bad "No answer", idle "Testing", idle "Not tested"; the row starts from
the scan's `online` flag and "Test" replaces it with `POST /api/setup/test`. Under the
table: "Scan again" (quiet) and "Add a port" (text) revealing a number `Field` "ADB port"
with an "Add" button, which appends a row named after the port. The line "Enable ADB in
BlueStacks: Settings, Advanced, Android Debug Bridge." sits below. There is no tag column
here: tags are asked on step 4. Continue patches `instances` to the ticked rows
(`{name, adb_port, player_tag: ""}`) and is disabled with reason "Select at least one
instance". Buttons: "Back", "Continue".

**Step 3 Display.** One card per selected instance calling `POST /api/setup/display-check`
with that instance's port. Card: the name in mono, a chip (ok "Correct", bad "Wrong size",
idle "Checking"), a mono line `${width} x ${height}, pixel density ${dpi}` from the
response, falling back to the response's `detail` when any of the three is null, and on
failure the response's `hint` rendered verbatim (so the sentence has one source, the
Python constant) and a "Recheck" quiet button. Nothing is saved by this step. Buttons:
"Back", "Continue" (disabled with reason "Fix the display first" until every card is ok).

**Step 4 Stats.** Title "Stats (optional)". The masked `Field` "Brawl Stars API token"
first, then one mono `Field` per selected instance labelled with the instance name,
placeholder "#TAG". Copy above: "A token and your player tags let brawlfarm show
per-brawler stats. Farming works without them." Below: "Create a key at
developer.brawlstars.com and allow this machine's IP address." with the domain linked to
`https://developer.brawlstars.com`. The token patches `connection.brawl_api_token`; each
tag patches that instance's `player_tag` (the model upper-cases it and prepends `#`, and a
bad tag returns 422 that the mapper puts under that field). A "Skip for now" text button
marks the step skipped for this visit and moves on. Buttons: "Back", "Continue". A prompt
on the Stats page when a tag is missing or the key stops working is phase 6, not this
brief.

**Step 5 Done.** Heading "Setup complete." Four summary lines: `Instances: ${n}` with the
names in mono; `adb: ${path}` in mono; "Token: set" or "Token: skipped"; "Player tags:
${k} of ${n} set" or "Player tags: none". Then a `Switch` "Start ${first} now" (the first
selected instance) defaulting on, then the line "Each step already saved to config.toml, so
you can close this and come back." Button "Open Fleet" (primary): when the switch is on it
posts `/api/instances/${first}/start` and then navigates to `/`; when it is off it just
navigates. A failed start raises `toast(failureMessage(error))` and still navigates.

**Entry points.** Nothing auto-redirects. When `GET /api/settings` returns no instances,
Fleet's empty state becomes the heading "No instances yet." and the body "Open setup to
find your BlueStacks instances." with an "Open setup" primary button linking to `/setup`
(replacing the phase 4 config.toml sentence in `fleet/Fleet.tsx`). Settings > Connection
carries "Run setup again" (quiet) linking to `/setup`. The rail's Settings link loses its
"soon" tag.

## 8. Settings sections (decided)

Files: `settings/Settings.tsx`, `SettingsNav.tsx`, `SettingRow.tsx`, `useSettingsPatch.ts`,
`Instances.tsx`, `Connection.tsx`, `Behavior.tsx`, `Schedule.tsx`, `Notifications.tsx`,
`Data.tsx`, `About.tsx`, `events.ts`.

**Instances.** Header buttons "Add instance" (primary) and "Scan again" (quiet). `Table`
columns: "Name" (mono), "ADB port" (mono), "Player tag" (mono), "Data folder" (mono muted),
"Status", and a trailing actions column. The data folder cell shows the path relative to
the home folder, `instances/Pie64`, never an absolute path. Status joins
`settings.instances` with `useInstances()` by name and renders `StateChip`, or an idle
`Chip` "No status yet" when no view exists. The Player tag cell is an editable mono `Field`
written through `useSettingsPatch` on debounce and blur, so a tag never needs the edit row.
Row actions: "Edit" (text) turns the row into an inline form of three `Field`s (Name, ADB
port, Player tag) with "Save" (primary) and "Cancel" (text); "Remove" (text) opens the
typed-name `ConfirmDialog`. "Add instance" opens the same inline form as a new last row.
A 409 renders inline in that row, as the API's detail, until the next successful patch.

**Connection.** Two `SettingRow`s. "ADB path" with a full-width mono `Field` and a chip,
ok "Found" or bad "Not found", from a scan run once when the section mounts, plus a "Run
setup again" quiet button linking to `/setup`. "Brawl Stars API token" with the masked
`Field` and the line "Create a key at developer.brawlstars.com and allow this machine's IP
address." Section caption: "Applies to a worker the next time it starts."

**Behavior.** Six `SettingRow`s with a `Switch` each, then a collapsed "Advanced" group
(a text button reading "Show" or "Hide") with seven more. Titles, sentences and the
settings field each one writes are in section 9. Section caption: "Applies to a worker the
next time it starts."

**Schedule.** One `SettingRow`: `Switch` "Schedule on by default" writing
`scheduler.default_enabled`, sentence "New instances follow the anti-ban schedule unless
you turn it off per instance."

**Notifications.** Four full-width `Field`s in this order, each a `SettingRow` with its
sentence: ntfy topic, ntfy server, Webhook URL, Healthchecks URL. Then the heading "Send me"
and seven checkboxes over `notify.ALERT_KINDS`, writing `notifications.events`. Then a
"Send a test" quiet button: with no channel set it shows "Add a channel first" inline
beside the button and does not call the API; otherwise it posts
`/api/notifications/test` and toasts `Test sent to ${sent.join(", ")}` when `sent` is
non-empty and `Test failed for ${failed.join(", ")}` when `failed` is non-empty, firing the
sent toast first.

**Data.** Three groups. "Open data folder": a quiet button posting
`/api/settings/open-data-folder`; the home folder path appears only in that button's
`title` tooltip, nowhere else on the page; a 501 toasts its detail. "Delete one instance's
data": one row per instance with the name in mono, the relative folder `instances/Pie64`
muted, and a "Delete data" text button opening a typed-name `ConfirmDialog`. "Reset all
settings": a bad-toned card at the bottom of the section with its sentence and a "Reset"
quiet button opening a `ConfirmDialog` whose typed word is "reset".

**About.** Theme as three cards in a `role="radiogroup"` labelled "Theme": System, Light,
Dark, each with a radio and a one-line subtitle; picking one writes `app.theme` and the
phase 4 bootstrap applies it within the same render. Then the version line from
`GET /api/health` (`brawlfarm 0.1.0`), three links, and the attribution line. System is the
default, which is already the model default.

## 9. Copy (verbatim)

Every string the UI shows. The plan and the tests quote from here.

**Wizard chrome.** Wordmark "brawlfarm". Step rail labels: "BlueStacks", "Instances",
"Display", "Stats", "Done".

**Step 1.** Title "BlueStacks". Description "brawlfarm talks to BlueStacks through adb."
Scanning chip "Scanning", line "Asking adb for devices". Found chip "Found". Field label
"Where is BlueStacks installed". Line "brawlfarm needs HD-Adb.exe from the BlueStacks
folder." Buttons "Scan again", "Continue" (disabled reason "Find HD-Adb.exe first"). Toast
"Saved to config.toml".

**Step 2.** Title "Instances". Description "Pick the BlueStacks instances brawlfarm should
farm." Columns "Name", "Display name", "ADB port", "Status". Chips "Answers", "No answer",
"Testing", "Not tested". Buttons "Test", "Scan again", "Add a port", "Add", "Back",
"Continue" (disabled reason "Select at least one instance"). Field "ADB port". Line "Enable
ADB in BlueStacks: Settings, Advanced, Android Debug Bridge." Empty "No instances found.
Start a BlueStacks instance, enable ADB, then Scan again." Test failure "No answer on 5585.
Is the instance running?" (the real port).

**Step 3.** Title "Display". Description "The farm reads the screen, so every instance has
to be the same size." Chips "Correct", "Wrong size", "Checking". Measurement line
"1600 x 900, pixel density 240". Fix line, from the API's `hint` and from
`checks.DISPLAY_HINT`: "Set the display to 1600 x 900 and pixel density 240 in BlueStacks:
Settings, Display, then restart the instance." Buttons "Recheck", "Back", "Continue"
(disabled reason "Fix the display first").

**Step 4.** Title "Stats (optional)". Copy "A token and your player tags let brawlfarm show
per-brawler stats. Farming works without them." Field "Brawl Stars API token", tag field
placeholder "#TAG". Line "Create a key at developer.brawlstars.com and allow this machine's
IP address." Buttons "Skip for now", "Back", "Continue".

**Step 5.** Title "Done". Heading "Setup complete." Summary "Instances: 2", "adb: ", "Token:
set", "Token: skipped", "Player tags: 1 of 2 set", "Player tags: none". Switch "Start Pie64
now". Line "Each step already saved to config.toml, so you can close this and come back."
Button "Open Fleet".

**Fleet entry.** Heading "No instances yet." Body "Open setup to find your BlueStacks
instances." Button "Open setup".

**Settings nav and titles.** "Instances" / "Which BlueStacks instances brawlfarm farms.";
"Connection" / "How brawlfarm reaches BlueStacks and the Brawl Stars API."; "Behavior" /
"How a worker plays."; "Schedule" / "The default for new instances."; "Notifications" /
"Where alerts go."; "Data" / "Files on this machine."; "About" / "Theme, version and
links." Save caption "Saved 19:04". Unknown section detail "unknown settings section".

**Settings > Instances.** Buttons "Add instance", "Scan again", "Edit", "Remove", "Save",
"Cancel". Columns "Name", "ADB port", "Player tag", "Data folder", "Status". Chip "No status
yet". Empty "No instances yet. Add one or scan for BlueStacks." Remove dialog title "Remove
Pie64_3?", body "Its data folder stays on disk. Type the name to confirm.", confirm label
"Remove". The 409 inline: "Stop Pie64_3 before removing it" (the API's detail, verbatim).

**Settings > Connection.** Rows "ADB path" and "Brawl Stars API token". Chips "Found",
"Not found". Button "Run setup again". Line "Create a key at developer.brawlstars.com and
allow this machine's IP address." Caption "Applies to a worker the next time it starts."

**Settings > Behavior.** `behavior.winrate_aware` "Win-rate aware" / "Prefer brawlers that
win more in the current step."; `opportunity_cost` "Opportunity cost" / "Skip brawlers
whose next tier is far off."; `gas_aware` "Gas aware" / "Move away from the gas earlier.";
`bush_hide` "Bush hide" / "Hide in bushes when the map allows."; `close_game_on_stop`
"Close game on stop" / "Close Brawl Stars when the worker stops."; `dnd_at_start` "DND at
start" / "Turn on Do Not Disturb when the worker starts." Group "Advanced" with "Show" /
"Hide" and `advanced.fast_input` "Fast input" / "Send taps through the faster adb path.";
`raw_cap` "Raw capture" / "Read frames without re-encoding them."; `gray_match` "Gray
matching" / "Match templates in grayscale."; `phase_classify` "Phase classify" / "Work out
the match phase from the screen."; `ability_buttons` "Ability buttons" / "Use the gadget
and super buttons."; `recalib_tripwire` "Recalibration tripwire" / "Warn when a detector
looks season-blind."; `dnd_off_on_stop` "DND off on stop" / "Turn Do Not Disturb back off
when the worker stops." Caption "Applies to a worker the next time it starts."

**Settings > Schedule.** Switch "Schedule on by default". Sentence "New instances follow the
anti-ban schedule unless you turn it off per instance."

**Settings > Notifications.** Field "ntfy topic" / "Free phone notifications. Install the
ntfy app, pick a topic name, type it here."; "ntfy server" / "Leave this unless you run
your own ntfy server."; "Webhook URL" / "A URL that receives each alert as a message, for
chat apps that offer incoming webhooks."; "Healthchecks URL" / "A check-in URL from
healthchecks.io; it warns you when brawlfarm stops checking in." Heading "Send me".
`settings/events.ts` `NOTIFY_EVENT_LABELS`, in this order: crash "Crash", recover
"Recovery", offline "Instance offline", wrong_mode "Wrong mode", recalibrate "Recalibration
needed", stop "Stopped", bad_resolution "Wrong resolution". Button "Send a test". Inline
"Add a channel first". Toasts "Test sent to ntfy" and "Test failed for webhook" (names
joined with ", ").

**Settings > Data.** Button "Open data folder". Heading "Delete one instance's data".
Button "Delete data". Dialog title "Delete Pie64's data?", body "Its folder
instances/Pie64 and everything in it goes: status, farm plan, schedule, games.csv and past
sessions. The instance stays in your fleet.", confirm label "Delete data". Card title
"Reset all settings", sentence "Your instances and their data folders stay. Every other
setting goes back to its default.", button "Reset", dialog title "Reset all settings?",
body the same sentence, confirm label "Reset", typed word "reset". Toast after a reset
"Settings reset". 501 detail "Only on Windows".

**Settings > About.** Heading "Theme"; cards "System" / "Follows Windows.", "Light" /
"Always light.", "Dark" / "Always dark." Version line "brawlfarm 0.1.0". Links "GitHub"
(`https://github.com/as9pa/brawlfarm`), "Setup guide" (the README's Requirements section
until `docs/setup.md` arrives in phase 7), "Safety rails" (the README's Safety rails
section). Attribution line: "brawlfarm is not affiliated with or endorsed by Supercell.
Brawl Stars and its art belong to Supercell. MIT licensed."

**Shared errors.** `ErrorBlock` behaviour is unchanged from phase 4: the API's `detail`
verbatim, FastAPI's validation list as `loc: msg` lines, "Request failed (HTTP ${status})"
otherwise, and "The panel cannot reach brawlfarm. Is it still running?" when fetch never
got an answer. `ConfirmDialog` disabled reason "Type ${word} to confirm". Masked field
buttons "Show" and "Hide".

## 10. States, empty and error strips (verbatim, binding)

These come from the accepted proposal and are what the screenshots and the tests pin.

- Wizard, scanning: the idle chip "Scanning" and the muted line "Asking adb for devices",
  with no spinner.
- Wizard, nothing found: "No instances found. Start a BlueStacks instance, enable ADB,
  then Scan again."
- Wizard, a port test failing: "No answer on 5585. Is the instance running?", with the row's
  real port.
- Wizard, display failing: the bad chip, the measured line, and the hint sentence.
- Wizard, saved: the toast "Saved to config.toml".
- Settings, empty instances table: "No instances yet. Add one or scan for BlueStacks."
- Settings, a validation error under a field: "adb_path: file not found", the mapped shape
  from section 4.
- Settings, the 409: the API's detail inline in the row.
- Settings, saved: the toast "Settings saved" with no undo, plus the per-section caption.
- The typed-name dialog, with the confirm button disabled until the name matches.
- A visible focus ring on every switch, every table checkbox, every dialog control.

## 11. Web types and API client additions

`api/types.ts`: `AppSettings` grows from the theme-only shape to the whole document, and
its comment is rewritten to say that the token reaches only the masked `Field`, and is
never logged, never stored outside the query cache, and never rendered unmasked by default.

```ts
export interface AppSettings {
  app: { port: number; theme: "system" | "dark" | "light" };
  connection: { adb_path: string; brawl_api_token: string };
  behavior: { winrate_aware: boolean; opportunity_cost: boolean; gas_aware: boolean;
              bush_hide: boolean; close_game_on_stop: boolean; dnd_at_start: boolean };
  advanced: { fast_input: boolean; raw_cap: boolean; gray_match: boolean;
              phase_classify: boolean; ability_buttons: boolean;
              recalib_tripwire: boolean; dnd_off_on_stop: boolean };
  scheduler: { default_enabled: boolean };
  notifications: { webhook_url: string; ntfy_topic: string; ntfy_server: string;
                   healthchecks_url: string; events: string[] };
  instances: { name: string; adb_port: number; player_tag: string }[];
}
export interface ScanResponse {
  adb_path: string | null; adb_found: boolean; conf_found: boolean;
  instances: { name: string; display_name: string; adb_port: number | null;
               width: number | null; height: number | null; dpi: number | null;
               online: boolean }[];
}
export interface PortTestResponse { ok: boolean; detail: string }
export interface DisplayCheckResponse {
  ok: boolean; width: number | null; height: number | null; dpi: number | null;
  detail: string; hint: string;
  expected: { width: number; height: number; dpi: number };
}
export interface NotifyTestResponse { sent: string[]; failed: string[] }
export interface Health { version: string; home: string; instances: number; uptime_s: number }
```

New client functions, each a thin wrapper over `api<T>()` in the existing per-resource
style: `api/settings.ts` gains `putSettings(doc)`, `resetSettings()`,
`openDataFolder()`, `testNotifications()`; `api/instances.ts` gains
`deleteInstanceData(name)`; new `api/setup.ts` has `scanSetup(adbPath?)`,
`testPort(port, adbPath?)`, `checkDisplay(port, adbPath?)`; new `api/health.ts` has
`getHealth()`. `queryKeys` gains `health: () => ["health"] as const`. The three setup
probes are mutations with local state, not cached queries: each one is a deliberate act,
and a stale cached scan would lie about what is plugged in.

## 12. Safety, hygiene and process constraints (Global Constraints for the plan)

- The safety rails of spec section 9 are absolute and untouched. The UI never sends a tap,
  never exposes a shop or purchase action, never bypasses the API. Navigation stays
  verify-then-act, bailing to the menu on a failed check so stale coordinates degrade to
  logged no-ops. The controller still asserts 1600 x 900 at startup and exits otherwise.
  Tap coordinates, OCR needles, HSV windows and the calibration block of
  `brawlfarm/core/config.py` are not edited. `controller.py`, `states.py`, `vision.py` and
  `farmplan.py` are not edited. The only file under `brawlfarm/core` that changes in phase
  5 is `notify.py`, and only to add `send_test`. The never-tap rail tests must pass
  unchanged.
- One worker per instance, ever. Workers are killed only by the PID read from that
  instance's `status.json`, never by name or command line. Nothing in this phase starts,
  stops or kills a process except the Done step's single `POST /api/instances/{name}/start`.
- No user-supplied string reaches a shell. Every adb call stays an argv list with
  `shell=False` and every serial is built from a validated integer port. Instance names are
  validated against `^[A-Za-z0-9_-]{1,32}$` before anything touches the filesystem, because
  they become folder names; `DELETE /api/instances/{name}/data` goes through
  `resolve_instance` and additionally refuses any resolved path that is not under
  `<home>/instances`.
- No `discord` import anywhere, in code, tests or fixtures.
- Loopback only, no auth, no CORS middleware; the Vite proxy handles dev. The four new
  routes sit behind the same middleware as the rest.
- The token is never logged, never written to a file by the web app, never rendered
  unmasked by default, and never put in a toast, an error message or a screenshot.
  Notification URLs and ntfy topics are never logged either.
- Scrub: `uv run python tools/scrub_check.py` prints `0 hit(s)` before every commit, and
  the commit is chained on its exit code
  (`uv run python tools/scrub_check.py && git commit ...`). No player tag, nickname, user
  path or token appears in code, tests, fixtures, screenshots or PR text. Fixtures use
  Pie64 / Pie64_1 / Pie64_3, ports 5555 / 5565 / 5585, and the made-up tag `#2P0YLQ9`.
  Screens and docs show a data folder as `instances/Pie64`, never as an absolute path.
- Copy: no em-dashes, no emoji, no exclamation marks; state is a word plus a colour.
- Every commit carries a conventional message plus these two trailer lines exactly:
  `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>` and
  `Claude-Session: https://claude.ai/code/session_01CQ1GimQ3uiR2sXPzfZLNWV`.
  `git config user.name` is `as9pa`.
- Green before every commit: `pnpm typecheck`, `pnpm test`, `pnpm build`,
  `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest -q`.
- The branch is `phase-5/setup-wizard-and-settings` from `main`; one PR; the PR carries
  screenshots of the real panel with the token field, any player tag and every thumbnail
  blurred (playwright-cli `eval` sets `filter: blur(14px)` on `[data-private]` before the
  shot; the masked `Field` input, the Instances table's tag column and the About home-folder
  tooltip carry `data-private`).

## 13. Tests

- vitest: `settingsFieldErrors` for a single error, several joined errors, an unparseable
  piece; `useSettingsPatch` for GET-merge-PUT, the queue under two quick changes, the 422
  mapping, the 409 passthrough, and the caption; `Dialog` for Escape, the focus trap and
  backdrop close; `ConfirmDialog` for the disabled confirm until the typed word matches
  exactly and for the reset on close; `Table` for the empty slot and a render column;
  `Field` for the password variant, the Show/Hide button name and `autocomplete="off"`;
  `Drawer`'s existing tests unchanged after the trap is extracted; `useSetupState` for each
  row of the step table and for the landing rule; one test per wizard step covering its
  disabled-Continue reason and what it patches; `StepDone` for both switch positions; per
  settings section, one test that the control writes the right field and one that renders
  its error; Notifications for the three toast paths including "Add a channel first";
  Data for both dialogs; About for the theme write; Fleet for the new empty state.
- pytest: `send_test` with a fake `requests` for all-sent, partly-failed, none-configured,
  and a raising channel, plus a test that it leaves `notify._overrides` untouched;
  `POST /api/notifications/test` for the payload shape and ordering;
  `POST /api/settings/reset` for defaults restored, instances kept, the file rewritten and
  `apply_settings` called; `POST /api/settings/open-data-folder` for 204 with a fake
  `startfile` and 501 off Windows; `DELETE /api/instances/{name}/data` for 204, the missing
  folder being 204, 404 unknown, 409 live, 409 on `OSError` and 400 for a path outside
  `<home>/instances`; the `DISPLAY_HINT` assertion updated in `tests/test_setup_checks.py`;
  the sticky-token test. A settings fixture joins `web/src/test/fixtures.ts`
  (`makeSettings`) so no test hand-writes the whole document.

## 14. Task list for the plan (8 tasks, this order)

1. **Foundations.** `useFocusTrap` extracted from `Drawer`, `Dialog`, `ConfirmDialog`,
   `Table`, the masked and full-width `Field` variants, `SettingRow`,
   `useSettingsPatch` with `settingsFieldErrors`, `makeSettings` in the test fixtures, and
   the `AppSettings` type grown to the whole document with its rewritten comment. Verify:
   `pnpm typecheck` and `pnpm test` green, `Drawer`'s existing tests untouched.
2. **API additions, Python.** `DISPLAY_HINT` and its test; `notify.send_test`;
   `POST /api/notifications/test` in `api/notify_routes.py`; `POST /api/settings/reset` and
   `POST /api/settings/open-data-folder`; `DELETE /api/instances/{name}/data`; `LIVE_STATES`
   moved to `api/deps.py`; the `loop.py:87` sticky-token fix. Verify: `uv run pytest -q`
   and `uv run ruff check .` green.
3. **Settings shell, nav and Instances.** The route split in `App.tsx`, `pageTitle`, the
   rail's "soon" tag, `Settings.tsx`, `SettingsNav.tsx`, the Instances table with Add,
   Edit, Remove, the inline tag field, Scan again and the 409 inline. Verify: remove a
   stopped instance in the real panel, and see the 409 on a farming one.
4. **Connection, Behavior, Schedule, About.** The two connection rows, the six behavior
   rows plus the collapsed seven, the schedule switch, the theme cards, version and links.
   Verify: flip the theme and watch the shell follow without a reload.
5. **Notifications and Data.** The four fields with their sentences, the seven event
   checkboxes, "Send a test" and its three outcomes; open data folder, delete one
   instance's data, reset all settings, both confirm dialogs. Verify: a test ntfy message
   arrives on the phone, and "Open data folder" opens Explorer.
6. **Wizard steps 1 to 3.** `Setup.tsx`, `StepRail`, `useSetupState`, `api/setup.ts`,
   BlueStacks, Instances and Display, including the adb path persisting into
   `connection.adb_path`. Verify: rename `config.toml` aside, start brawlfarm, and reach
   step 4 against the real BlueStacks.
7. **Wizard steps 4 and 5, and the entry points.** Stats with the token and per-instance
   tags, Done with its summary and start switch, the Fleet empty state, "Run setup again".
   Verify: finish the wizard and land on Fleet with the first instance starting.
8. **Finish.** Keyboard and focus pass over dialogs, tables and the step rail; reduced
   motion; phone width; light theme; README updated (the Requirements line says "pixel
   density 240", the API list gains the four new routes, a "Setup" paragraph points at
   `/setup`); `docs/PLAN.md` phase 5 row; blurred screenshots; PR body.

## 15. Accepted proposal ids (all 21, for traceability in task briefs)

wiz-flow, wiz-bluestacks, wiz-instances, wiz-display, wiz-token, wiz-done, wiz-entry,
set-nav, set-instances, set-remove-confirm, set-connection, set-behavior, set-schedule,
set-notifications, set-data, set-about, set-save, set-empty, found-dialog, found-table,
found-masked.
