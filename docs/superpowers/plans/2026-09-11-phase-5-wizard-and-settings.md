# Phase 5: Setup wizard and Settings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give brawlfarm a first-run path and a settings screen: a five-step `/setup` wizard that takes a new user from "BlueStacks installed" to "first instance farming" without editing a file, and a seven-section `/settings/:section` screen that saves on change and never shows a Save button.

**Architecture:** One data layer, `settings/useSettingsPatch.ts`, is the only way a setting reaches disk: it re-reads `GET /api/settings`, mutates a structured clone, PUTs the whole document and writes the answer back into the query cache, with every patch queued on a module-level promise chain so two quick switch flips cannot race. Every wizard step and every settings section writes through it, which is what makes "saved after every step" a property of the code rather than a habit. Five small Python additions back the screens (a notifications test, a settings reset, an open-data-folder call, a delete-instance-data call and one corrected copy string), and two one-line bugs are fixed on the way: the wizard persists the discovered adb path, and a blank API token stops being sticky.

**Tech Stack:** Vite 7, React 19, TypeScript 5.9 (strict, `any` banned, `tsc --noEmit` is the lint), Tailwind v4 through `@tailwindcss/vite` with the tokens already in `src/styles/theme.css`, `react-router` 7 (declarative mode), `@tanstack/react-query` 5, `lucide-react` at 16 px with `strokeWidth={1.6}`. Tests: vitest 3 + `@testing-library/react` 16 + `@testing-library/user-event` 14 + jsdom 26. pnpm 10.17.1. Python 3.13 with uv, FastAPI, pydantic v2, pytest, ruff.

**Spec:** docs/superpowers/specs/2026-09-10-brawlfarm-design.md (section 8 the UI, section 9 the safety rails, section 10 hygiene, section 11 testing)

**Design brief (binding):** docs/superpowers/plans/2026-09-11-phase-5-design-brief.md. Every value, every route, every prop and every string in this plan is copied from it. Sections 9 and 10 of the brief are the copy the tests quote; nothing here re-decides anything it settles.

**Task order:** the brief's section 14 lists eight tasks. This plan keeps that order and splits three of them in two, because each of those carries more than one implementer can hold along with its tests. Brief task 1 (Foundations) becomes plan tasks 1 and 2; brief task 2 (API additions) becomes plan tasks 3 and 4; brief task 6 (wizard steps 1 to 3) becomes plan tasks 8 and 9. Brief tasks 3, 4, 5, 7 and 8 become plan tasks 5, 6, 7, 10 and 11 unchanged. Nothing moves across a boundary: each half is the front or the back of its brief task, in the brief's own order.

## Global Constraints

Copied verbatim from section 12 of the design brief. Every task's requirements implicitly include this section.

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

---


Two shell conventions for every task: commands are written for Git Bash on Windows with
forward slashes, web commands run as `pnpm --dir brawlfarm/web <script>` from the repo
root, and Python commands run from the repo root with `uv run`.

## File map

Everything phase 5 creates or modifies, across all eleven tasks.

Foundations, components and types:

```
brawlfarm/web/src/api/types.ts                    # AppSettings grown to the whole document; the five probe payloads  (task 1)
brawlfarm/web/src/test/fixtures.ts                # makeSettings                                                      (task 1)
brawlfarm/web/src/components/ui/useFocusTrap.ts   # the modal focus contract, lifted out of Drawer                    (task 1)
brawlfarm/web/src/components/ui/Drawer.tsx        # now calls useFocusTrap; props and behaviour unchanged             (task 1)
brawlfarm/web/src/components/ui/Dialog.tsx        # the centred 480 px modal                                          (task 1)
brawlfarm/web/src/components/ui/ConfirmDialog.tsx # Dialog plus the typed-name gate                                   (task 1)
brawlfarm/web/src/components/ui/Table.tsx         # Column<Row>, TableProps<Row>, the empty slot                      (task 1)
brawlfarm/web/src/components/ui/Field.tsx         # type="password" and width="full"                                  (task 1)
brawlfarm/web/src/settings/SettingRow.tsx         # title, sentence, control, error line                              (task 1)
brawlfarm/web/src/settings/useSettingsPatch.ts    # the one write path, the 422 mapper, saveSetting, fieldError        (task 2)
brawlfarm/web/src/api/settings.ts                 # putSettings (task 2); reset, open-data-folder, test (task 7)
brawlfarm/web/src/api/setup.ts                    # scanSetup, testPort, checkDisplay                                 (task 5)
brawlfarm/web/src/api/health.ts                   # getHealth                                                         (task 6)
brawlfarm/web/src/api/instances.ts                # deleteInstanceData                                                (task 7)
brawlfarm/web/src/api/queries.ts                  # queryKeys.health                                                  (task 6)
```

The settings screen:

```
brawlfarm/web/src/App.tsx                         # the route split: /setup outside Shell, the rest inside            (tasks 5, 8)
brawlfarm/web/src/app/TopBar.tsx                  # pageTitle answers Settings for every section                      (task 5)
brawlfarm/web/src/app/Rail.tsx                    # Settings loses its soon tag; Stats keeps its                      (task 5)
brawlfarm/web/src/settings/Settings.tsx           # the section frame, the save caption, the unknown-section error    (task 5)
brawlfarm/web/src/settings/SettingsNav.tsx        # the 200 px second-level nav, NavLink per section                  (task 5)
brawlfarm/web/src/settings/Instances.tsx          # the table, Add, Edit, Remove, the inline tag field, the 409       (task 5)
brawlfarm/web/src/settings/Connection.tsx         # adb path with its scan chip, the masked token                     (task 6)
brawlfarm/web/src/settings/Behavior.tsx           # six rows plus the collapsed Advanced seven                        (task 6)
brawlfarm/web/src/settings/Schedule.tsx           # one switch                                                        (task 6)
brawlfarm/web/src/settings/About.tsx              # the theme cards, the version line, the links, the attribution     (task 6)
brawlfarm/web/src/settings/Notifications.tsx      # four channels, seven events, Send a test                          (task 7)
brawlfarm/web/src/settings/events.ts              # NOTIFY_EVENT_LABELS, in the brief's order                         (task 7)
brawlfarm/web/src/settings/Data.tsx               # open the folder, delete an instance folder, reset everything      (task 7)
```

The setup wizard:

```
brawlfarm/web/src/setup/Setup.tsx                 # the full-window frame outside the shell                           (task 8)
brawlfarm/web/src/setup/StepRail.tsx              # five numbered steps, Check on the done ones                       (task 8)
brawlfarm/web/src/setup/useSetupState.ts          # the step table, the landing rule, the shared scan                 (task 8)
brawlfarm/web/src/setup/StepBlueStacks.tsx        # scan on entry, persist connection.adb_path                        (task 8)
brawlfarm/web/src/setup/StepInstances.tsx         # the scan table, per-row Test, Add a port                          (task 9)
brawlfarm/web/src/setup/StepDisplay.tsx           # one card per instance, the hint verbatim from the API             (task 9)
brawlfarm/web/src/setup/StepStats.tsx             # the token and one tag field per instance, Skip for now            (task 10)
brawlfarm/web/src/setup/StepDone.tsx              # the four summary lines and the start switch                       (task 10)
brawlfarm/web/src/fleet/Fleet.tsx                 # the empty state points at /setup                                  (task 10)
```

Vitest files sit next to the module they pin, named `<module>.test.ts` or `<module>.test.tsx`:

```
src/components/ui/Dialog.test.tsx (task 1)        src/components/ui/ConfirmDialog.test.tsx (task 1)
src/components/ui/Table.test.tsx (task 1)         src/components/ui/Field.test.tsx (task 1, modified)
src/components/ui/Drawer.test.tsx (task 1, left alone: it is the regression gate on the trap)
src/settings/SettingRow.test.tsx (task 1)         src/settings/useSettingsPatch.test.tsx (task 2)
src/app/Rail.test.tsx (task 5, modified)          src/App.test.tsx (tasks 5, 8, modified)
src/settings/Settings.test.tsx (task 5)           src/settings/Instances.test.tsx (task 5)
src/settings/Connection.test.tsx (task 6)         src/settings/Behavior.test.tsx (task 6)
src/settings/Schedule.test.tsx (task 6)           src/settings/About.test.tsx (task 6)
src/settings/Notifications.test.tsx (task 7)      src/settings/Data.test.tsx (task 7)
src/setup/useSetupState.test.tsx (task 8)         src/setup/StepBlueStacks.test.tsx (task 8)
src/setup/StepInstances.test.tsx (task 9)         src/setup/StepDisplay.test.tsx (task 9)
src/setup/StepStats.test.tsx (task 10)            src/setup/StepDone.test.tsx (task 10)
src/fleet/Fleet.test.tsx (task 10, modified)
```

Python and repository files:

```
brawlfarm/setup/checks.py              # DISPLAY_HINT, the one corrected sentence                                  (task 3)
brawlfarm/core/notify.py               # send_test; nothing else under brawlfarm/core changes                      (task 3)
brawlfarm/api/notify_routes.py         # POST /api/notifications/test                                              (task 3)
brawlfarm/api/app.py                   # include notify_routes.router after settings_routes                        (task 3)
brawlfarm/api/deps.py                  # LIVE_STATES moves here, unchanged                                         (task 4)
brawlfarm/api/settings_routes.py       # imports LIVE_STATES; POST reset; POST open-data-folder                     (task 4)
brawlfarm/api/instances.py             # DELETE /api/instances/{name}/data                                          (task 4)
brawlfarm/supervisor/loop.py           # the one-line sticky-token fix at line 87                                   (task 4)
tests/test_setup_checks.py             # the DISPLAY_HINT assertion                                                 (task 3)
tests/test_notify_send_test.py         # send_test: all sent, partly failed, none configured, a raising channel     (task 3)
tests/test_api_notifications.py        # the route's payload shape and ordering                                     (task 3)
tests/test_api_settings.py             # reset and open-data-folder                                                 (task 4)
tests/test_api_instances.py            # delete one instance's data: 204, 404, 409, 400, idempotent                 (task 4)
tests/test_supervisor_loop.py          # the sticky-token test                                                      (task 4)
README.md                              # the status line, the Requirements sentence, four API rows, a Setup line    (task 11)
docs/PLAN.md                           # the phase 5 row                                                            (task 11)
```

`brawlfarm/core/controller.py`, `core/states.py`, `core/vision.py`, `core/farmplan.py` and
the calibration block of `core/config.py` are not touched by any task. `.gitignore` and
`tools/scrub_check.py` need no change: `node_modules` and `dist` are already in the scrub
check's `SKIP_DIRS` and in `.gitignore`.

## Four decisions the brief left open, settled once here

These are the only places the brief did not hand over a value. They are settled here so no
task re-decides them, and every task that touches them cites this list.

1. **`Health` is a name collision.** `api/types.ts` already exports
   `export type Health = "healthy" | "stale" | "dead"` for `InstancePayload.health`. The
   brief's section 11 asks for an interface of the same name for `GET /api/health`. The new
   one is called `HealthResponse`, matching `ScanResponse`, `PortTestResponse`,
   `DisplayCheckResponse` and `NotifyTestResponse`; the instance-health type is not touched.
2. **Settings > Instances "Scan again"** runs `POST /api/setup/scan` and appends, in one
   patch, every discovered instance with a port that is not already in
   `settings.instances` by name. It toasts `Added ${plural(n, "instance")}` when it added
   any and `No new instances found` when it did not. These two strings are the only copy in
   phase 5 that is not quoted from brief section 9; the brief's own empty state ("No
   instances yet. Add one or scan for BlueStacks.") is what says the button adds rows.
3. **The About links.** Only the GitHub URL is given. "Setup guide" is
   `https://github.com/as9pa/brawlfarm#requirements` and "Safety rails" is
   `https://github.com/as9pa/brawlfarm#safety-rails`, which are the README anchors the
   brief names, until `docs/setup.md` arrives in phase 7.
4. **The wizard's landing step is derived from `config.toml`, not from the scan.** Brief
   section 7 gives one table and asks it two questions: what the rail may tick, and where
   the wizard opens. The two cannot share an answer. Its BlueStacks row is true only once a
   scan has come back and agreed with what is stored, and no scan has come back when the
   page mounts, so a single table would land every cold open on step 1 and make the
   "otherwise Display" branch dead. Task 8 splits them: the `done` table is exactly the
   brief's, scan and all, and it is what the rail ticks; the landing rule reads the stored
   document alone, which is BlueStacks when `connection.adb_path` is empty, Instances when
   it is set and `instances` is empty, and Display otherwise. Both of the brief's sentences
   then mean what they say, and nobody watches the wizard jump a step half a second after
   it appears.

One more note, recorded so a reviewer does not read it as a mistake: brief section 12 says
the About home-folder tooltip carries `data-private`, while section 8 puts the home folder
in the Data section's "Open data folder" tooltip and says it appears nowhere else. Section 8
wins: `data-private` goes on the Data section's button (task 7), and About carries no path
at all.

---

### Task 1: Foundations A. The settings document, the fixture, and five components

The front half of the brief's task 1. Everything the settings screen and the wizard stand
on except the write path, which is task 2: the payload types grown from "only app.theme" to
the whole document, a fixture so no later test hand-writes it, the focus trap lifted out of
`Drawer` so `Dialog` gets the same one, and the five components the brief's section 5 names
as contracts.

Nothing in this task calls the API. `Drawer.test.tsx` is not edited: it is the regression
gate proving the trap came out byte-for-byte.

Accepted proposal ids covered: `found-dialog`, `found-table`, `found-masked`.

**Files:**
- Modify: `brawlfarm/web/src/api/types.ts` (rewrite the `AppSettings` block and the module comment; append five payload interfaces)
- Modify: `brawlfarm/web/src/test/fixtures.ts` (add `makeSettings`)
- Create: `brawlfarm/web/src/components/ui/useFocusTrap.ts`
- Modify: `brawlfarm/web/src/components/ui/Drawer.tsx` (the trap moves out; props and markup unchanged)
- Create: `brawlfarm/web/src/components/ui/Dialog.tsx`
- Create: `brawlfarm/web/src/components/ui/ConfirmDialog.tsx`
- Create: `brawlfarm/web/src/components/ui/Table.tsx`
- Modify: `brawlfarm/web/src/components/ui/Field.tsx` (two optional props, and nothing else)
- Create: `brawlfarm/web/src/settings/SettingRow.tsx`
- Test: `brawlfarm/web/src/components/ui/Dialog.test.tsx` (create)
- Test: `brawlfarm/web/src/components/ui/ConfirmDialog.test.tsx` (create)
- Test: `brawlfarm/web/src/components/ui/Table.test.tsx` (create)
- Test: `brawlfarm/web/src/components/ui/Field.test.tsx` (modify: three tests appended)
- Test: `brawlfarm/web/src/settings/SettingRow.test.tsx` (create)

**Interfaces:**
- Consumes, from the phase 4 tree, unchanged: `Button` (`variant`, `size`, `disabled`,
  `disabledReason`, `onClick`, `children`, `type`), `Switch` (`checked`, `onChange`,
  `label`, `disabled`), `Chip` (`tone`, `children`), `Tone` and `TONE_DOT` from
  `lib/states.ts`, and the token names in `styles/theme.css`.
- Produces:
  - `api/types.ts`: `AppSettings` (the whole config.toml document), `ScanInstance`,
    `ScanResponse`, `PortTestResponse`, `DisplayCheckResponse`, `NotifyTestResponse`,
    `HealthResponse`
  - `test/fixtures.ts`: `makeSettings(overrides?: Partial<AppSettings>): AppSettings`
  - `components/ui/useFocusTrap.ts`:
    `useFocusTrap(open: boolean, ref: RefObject<HTMLElement | null>, onClose: () => void): void`
  - `components/ui/Dialog.tsx`: `DialogProps { open; onClose; title; children; actions? }`,
    `Dialog`
  - `components/ui/ConfirmDialog.tsx`:
    `ConfirmDialogProps { open; onClose; title; body; word; confirmLabel; tone: "bad"; onConfirm }`,
    `ConfirmDialog`
  - `components/ui/Table.tsx`: `Column<Row> { key; label; mono?; width?; render? }`,
    `TableProps<Row> { columns; rows; rowKey; empty }`, `Table`
  - `components/ui/Field.tsx`: `FieldProps` gains `type?: "text" | "number" | "password"`
    and `width?: "control" | "full"`
  - `settings/SettingRow.tsx`: `SettingRowProps { title; description; error?; children }`,
    `SettingRow`
- Consumed by: task 2 (`AppSettings`, `makeSettings`), tasks 5, 6, 7 (every component),
  tasks 8, 9, 10 (`Table`, `Field`, `ScanResponse`, `DisplayCheckResponse`, `makeSettings`).

- [ ] **Step 1: Branch, and grow the payload types**

```bash
cd <repo>
git switch -c phase-5/setup-wizard-and-settings
git config user.name   # must print as9pa
```

In `brawlfarm/web/src/api/types.ts`, replace the module comment at the top of the file:

```ts
/**
 * The API's payloads as TypeScript.
 *
 * Mirrors brawlfarm/api/*.py exactly: optional in Python means `| null` here, never `?`,
 * because the API always sends the key. The stats series is the only payload still left
 * out, and it arrives with the Stats page in phase 6.
 */
```

Replace the `AppSettings` block at the end of the file (the comment above it goes too):

```ts
/**
 * The whole config.toml document, as GET /api/settings serves it and PUT takes it back.
 *
 * connection.brawl_api_token is modelled because the document is whole: the API is
 * loopback-only and hands the token over in full, and masking it is the panel's job, not
 * the server's. It reaches exactly one control, the masked Field on Settings > Connection
 * and on the wizard's Stats step. It is never logged, never stored anywhere but the query
 * cache and the PUT body, never rendered unmasked by default, and never put into a toast,
 * an error message or a screenshot.
 */
export interface AppSettings {
  app: { port: number; theme: "system" | "dark" | "light" };
  connection: { adb_path: string; brawl_api_token: string };
  behavior: {
    winrate_aware: boolean;
    opportunity_cost: boolean;
    gas_aware: boolean;
    bush_hide: boolean;
    close_game_on_stop: boolean;
    dnd_at_start: boolean;
  };
  advanced: {
    fast_input: boolean;
    raw_cap: boolean;
    gray_match: boolean;
    phase_classify: boolean;
    ability_buttons: boolean;
    recalib_tripwire: boolean;
    dnd_off_on_stop: boolean;
  };
  scheduler: { default_enabled: boolean };
  notifications: {
    webhook_url: string;
    ntfy_topic: string;
    ntfy_server: string;
    healthchecks_url: string;
    events: string[];
  };
  instances: { name: string; adb_port: number; player_tag: string }[];
}

/** One row of POST /api/setup/scan: a BlueStacks instance as bluestacks.conf describes it,
 * with `online` from `adb devices`. `adb_port` is null when the conf line was unreadable,
 * which is what the wizard's "Add a port" field is for. */
export interface ScanInstance {
  name: string;
  display_name: string;
  adb_port: number | null;
  width: number | null;
  height: number | null;
  dpi: number | null;
  online: boolean;
}

export interface ScanResponse {
  adb_path: string | null;
  adb_found: boolean;
  conf_found: boolean;
  instances: ScanInstance[];
}

export interface PortTestResponse {
  ok: boolean;
  detail: string;
}

/** POST /api/setup/display-check. `hint` is checks.DISPLAY_HINT, rendered verbatim so the
 * sentence telling the user where to change the display has exactly one source. */
export interface DisplayCheckResponse {
  ok: boolean;
  width: number | null;
  height: number | null;
  dpi: number | null;
  detail: string;
  hint: string;
  expected: { width: number; height: number; dpi: number };
}

export interface NotifyTestResponse {
  sent: string[];
  failed: string[];
}

/** GET /api/health. Not called `Health`: that name is already this file's instance-health
 * union ("healthy" | "stale" | "dead"), and the two mean different things. */
export interface HealthResponse {
  version: string;
  home: string;
  instances: number;
  uptime_s: number;
}
```

- [ ] **Step 2: Add the settings fixture**

In `brawlfarm/web/src/test/fixtures.ts`, add `AppSettings` to the type import from
`../api/types`, then append this builder at the end of the file:

```ts
/** The whole settings document at its model defaults, with one instance. Every settings
 * and wizard test starts from here, so a field that changes shape breaks one file rather
 * than twenty. The defaults mirror brawlfarm/settings.py exactly, including the empty
 * token: a fixture that carried a real one would be a leak waiting to happen. */
export function makeSettings(overrides: Partial<AppSettings> = {}): AppSettings {
  return {
    app: { port: 8765, theme: "system" },
    connection: {
      adb_path: "C:\\Program Files\\BlueStacks_nxt\\HD-Adb.exe",
      brawl_api_token: "",
    },
    behavior: {
      winrate_aware: true,
      opportunity_cost: false,
      gas_aware: true,
      bush_hide: false,
      close_game_on_stop: true,
      dnd_at_start: true,
    },
    advanced: {
      fast_input: true,
      raw_cap: true,
      gray_match: true,
      phase_classify: true,
      ability_buttons: true,
      recalib_tripwire: true,
      dnd_off_on_stop: true,
    },
    scheduler: { default_enabled: true },
    notifications: {
      webhook_url: "",
      ntfy_topic: "",
      ntfy_server: "https://ntfy.sh",
      healthchecks_url: "",
      events: ["crash", "recover", "offline", "wrong_mode", "recalibrate"],
    },
    instances: [{ name: "Pie64", adb_port: 5555, player_tag: "#2P0YLQ9" }],
    ...overrides,
  };
}
```

- [ ] **Step 3: Write the failing tests**

Create `brawlfarm/web/src/components/ui/Dialog.test.tsx`:

```tsx
/** The centred modal: named by its own heading, focus trapped inside it, Escape and the
 * backdrop close it, and a click on the panel does not. */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Button } from "./Button";
import { Dialog } from "./Dialog";

function backdrop(): HTMLElement {
  return screen.getByRole("dialog").previousElementSibling as HTMLElement;
}

describe("Dialog", () => {
  it("renders nothing while closed", () => {
    const { container } = render(
      <Dialog open={false} onClose={vi.fn()} title="Remove Pie64_3?">
        <p>body</p>
      </Dialog>,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("is a modal dialog labelled by the heading it shows", () => {
    render(
      <Dialog open onClose={vi.fn()} title="Remove Pie64_3?" actions={<Button>Remove</Button>}>
        <p>Its data folder stays on disk. Type the name to confirm.</p>
      </Dialog>,
    );
    const dialog = screen.getByRole("dialog", { name: "Remove Pie64_3?" });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    // aria-labelledby rather than aria-label: the title is already on screen, so there is
    // one string to keep right instead of two that can drift apart.
    expect(dialog.getAttribute("aria-labelledby")).toBe(
      screen.getByRole("heading", { name: "Remove Pie64_3?" }).id,
    );
    expect(screen.getByRole("button", { name: "Remove" })).toBeInTheDocument();
  });

  it("closes on Escape", async () => {
    const onClose = vi.fn();
    render(
      <Dialog open onClose={onClose} title="Remove Pie64_3?">
        <p>body</p>
      </Dialog>,
    );
    await userEvent.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("closes on the backdrop and stays open for a click inside", async () => {
    const onClose = vi.fn();
    render(
      <Dialog open onClose={onClose} title="Remove Pie64_3?" actions={<Button>Remove</Button>}>
        <p>body</p>
      </Dialog>,
    );
    await userEvent.click(screen.getByText("body"));
    expect(onClose).not.toHaveBeenCalled();
    await userEvent.click(backdrop());
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("keeps Tab inside the panel", async () => {
    render(
      <Dialog
        open
        onClose={vi.fn()}
        title="Remove Pie64_3?"
        actions={
          <>
            <Button variant="text">Cancel</Button>
            <Button variant="primary">Remove</Button>
          </>
        }
      >
        <p>body</p>
      </Dialog>,
    );
    const cancel = screen.getByRole("button", { name: "Cancel" });
    const remove = screen.getByRole("button", { name: "Remove" });
    await userEvent.tab();
    expect(cancel).toHaveFocus();
    await userEvent.tab();
    expect(remove).toHaveFocus();
    await userEvent.tab();
    expect(cancel).toHaveFocus();
  });
});
```

Create `brawlfarm/web/src/components/ui/ConfirmDialog.test.tsx`:

```tsx
/** The typed-name gate: the confirm button will not fire until the word is typed exactly,
 * it says what to type while it is disabled, and the box forgets what was typed when the
 * dialog closes, so a second open never starts already armed. */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ConfirmDialog } from "./ConfirmDialog";

function remove(open: boolean, onConfirm: () => void, onClose: () => void) {
  return (
    <ConfirmDialog
      open={open}
      onClose={onClose}
      title="Remove Pie64_3?"
      body="Its data folder stays on disk. Type the name to confirm."
      word="Pie64_3"
      confirmLabel="Remove"
      tone="bad"
      onConfirm={onConfirm}
    />
  );
}

describe("ConfirmDialog", () => {
  it("stays disabled, and says what to type, until the word matches exactly", async () => {
    const onConfirm = vi.fn();
    render(remove(true, onConfirm, vi.fn()));
    const confirm = screen.getByRole("button", { name: "Remove" });
    const box = screen.getByLabelText("Type to confirm");
    expect(confirm).toBeDisabled();
    expect(confirm).toHaveAttribute("title", "Type Pie64_3 to confirm");
    expect(box).toHaveAttribute("placeholder", "Pie64_3");
    expect(
      screen.getByText("Its data folder stays on disk. Type the name to confirm."),
    ).toBeInTheDocument();

    await userEvent.type(box, "pie64_3");
    // Case sensitive on purpose: on a case-sensitive disk those are two different folders,
    // and a confirmation that accepts either is not a confirmation.
    expect(confirm).toBeDisabled();
    await userEvent.clear(box);
    await userEvent.type(box, "  Pie64_3  ");
    expect(confirm).toBeEnabled(); // the trimmed value is what is compared
    await userEvent.click(confirm);
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("cancels without confirming", async () => {
    const onConfirm = vi.fn();
    const onClose = vi.fn();
    render(remove(true, onConfirm, onClose));
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onClose).toHaveBeenCalledTimes(1);
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("forgets the typed word when it closes", async () => {
    const onConfirm = vi.fn();
    const { rerender } = render(remove(true, onConfirm, vi.fn()));
    await userEvent.type(screen.getByLabelText("Type to confirm"), "Pie64_3");
    expect(screen.getByRole("button", { name: "Remove" })).toBeEnabled();

    rerender(remove(false, onConfirm, vi.fn()));
    rerender(remove(true, onConfirm, vi.fn()));
    expect(screen.getByLabelText("Type to confirm")).toHaveValue("");
    expect(screen.getByRole("button", { name: "Remove" })).toBeDisabled();
  });
});
```

Create `brawlfarm/web/src/components/ui/Table.test.tsx`:

```tsx
/** The settings tables: real table semantics, one render function per column, a header the
 * actions column does not show but a screen reader still hears, and one full-width cell
 * when there is nothing to list. */
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { type Column, Table } from "./Table";

interface Row {
  name: string;
  port: number;
}

const ROWS: Row[] = [
  { name: "Pie64", port: 5555 },
  { name: "Pie64_3", port: 5585 },
];

const COLUMNS: readonly Column<Row>[] = [
  { key: "name", label: "Name", mono: true, render: (row) => row.name },
  { key: "port", label: "ADB port", mono: true, width: "120px", render: (row) => String(row.port) },
  {
    key: "actions",
    label: "",
    render: (row) => <button type="button">{`Remove ${row.name}`}</button>,
  },
];

describe("Table", () => {
  it("is a real table with one header per column", () => {
    render(<Table columns={COLUMNS} rows={ROWS} rowKey={(row) => row.name} empty="nothing" />);
    expect(screen.getAllByRole("columnheader").map((th) => th.textContent)).toEqual([
      "Name",
      "ADB port",
      "actions",
    ]);
    // A column with no visible label is still announced, by its key, rather than handing a
    // screen reader a blank header.
    expect(
      screen.getByRole("columnheader", { name: "actions" }).querySelector(".sr-only"),
    ).not.toBeNull();
    expect(screen.getAllByRole("row")).toHaveLength(3); // the header row plus two
  });

  it("renders every cell through its column and puts mono on the ones that ask", () => {
    render(<Table columns={COLUMNS} rows={ROWS} rowKey={(row) => row.name} empty="nothing" />);
    const row = screen.getByRole("row", { name: /Pie64_3/ });
    const cells = within(row).getAllByRole("cell");
    expect(cells.map((cell) => cell.textContent)).toEqual(["Pie64_3", "5585", "Remove Pie64_3"]);
    expect(cells[0].className).toContain("font-mono");
    expect(cells[2].className).not.toContain("font-mono");
    expect(within(row).getByRole("button", { name: "Remove Pie64_3" })).toBeInTheDocument();
  });

  it("shows the empty slot in one cell that spans the table", () => {
    render(
      <Table
        columns={COLUMNS}
        rows={[]}
        rowKey={(row) => row.name}
        empty="No instances yet. Add one or scan for BlueStacks."
      />,
    );
    const cell = screen.getByRole("cell");
    expect(cell).toHaveTextContent("No instances yet. Add one or scan for BlueStacks.");
    expect(cell).toHaveAttribute("colspan", "3");
  });
});
```

Create `brawlfarm/web/src/settings/SettingRow.test.tsx`:

```tsx
/** One setting: its name, the plain sentence under it, the control beside it, and the
 * API's own message when that control's last save was refused. */
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SettingRow } from "./SettingRow";
import { Switch } from "../components/ui/Switch";

describe("SettingRow", () => {
  it("shows the title, the sentence and the control", () => {
    render(
      <SettingRow title="Gas aware" description="Move away from the gas earlier.">
        <Switch checked onChange={vi.fn()} label="Gas aware" />
      </SettingRow>,
    );
    expect(screen.getByText("Move away from the gas earlier.")).toBeInTheDocument();
    // The words appear twice in the DOM and once on screen: the row prints the title, and
    // the switch keeps the same string as its accessible name with its own copy shrunk
    // away. Switch's props are phase 4's and do not change, so the row is what hides it.
    expect(screen.getAllByText("Gas aware").map((el) => el.tagName)).toEqual(["P", "BUTTON"]);
    expect(screen.getByRole("switch", { name: "Gas aware" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
  });

  it("prints the field error under both", () => {
    render(
      <SettingRow
        title="ADB path"
        description="Where HD-Adb.exe lives."
        error="adb_path: file not found"
      >
        <Switch checked={false} onChange={vi.fn()} label="ADB path" />
      </SettingRow>,
    );
    expect(screen.getByText("adb_path: file not found")).toBeInTheDocument();
  });

  it("shows no error line when there is no error", () => {
    const { container } = render(
      <SettingRow title="Bush hide" description="Hide in bushes when the map allows.">
        <Switch checked={false} onChange={vi.fn()} label="Bush hide" />
      </SettingRow>,
    );
    expect(container.querySelector(".text-bad")).toBeNull();
  });
});
```

Append three tests to `brawlfarm/web/src/components/ui/Field.test.tsx`, inside the existing
`describe("Field", ...)` block:

```tsx
  it("masks the token, keeps browsers out of it, and toggles with Show and Hide", async () => {
    render(
      <Field
        label="Brawl Stars API token"
        id="token"
        value="a-token-that-is-not-real"
        onChange={vi.fn()}
        type="password"
        width="full"
      />,
    );
    const input = screen.getByLabelText("Brawl Stars API token");
    expect(input).toHaveAttribute("type", "password");
    expect(input).toHaveAttribute("autocomplete", "off");
    // The screenshot pass blurs every [data-private] before the shot is taken.
    expect(input).toHaveAttribute("data-private");

    await userEvent.click(screen.getByRole("button", { name: "Show" }));
    expect(input).toHaveAttribute("type", "text");
    expect(screen.queryByRole("button", { name: "Show" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Hide" }));
    expect(input).toHaveAttribute("type", "password");
  });

  it("leaves an ordinary field alone: no mask, no reveal button, the control width", () => {
    render(<Field label="Goal" id="goal" value="1000" onChange={vi.fn()} type="number" />);
    const input = screen.getByLabelText("Goal");
    expect(input).toHaveAttribute("type", "number");
    expect(input).not.toHaveAttribute("data-private");
    expect(input).not.toHaveAttribute("autocomplete");
    expect(input.className).toContain("w-24");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("grows to the row when asked", () => {
    render(<Field label="ADB path" id="adb" value="C:/adb.exe" onChange={vi.fn()} width="full" />);
    const input = screen.getByLabelText("ADB path");
    expect(input.className).toContain("w-full");
    expect(input.className).not.toContain("w-24");
  });
```

- [ ] **Step 4: Run the five files to confirm they fail**

```bash
pnpm --dir brawlfarm/web test src/components/ui/Dialog.test.tsx src/components/ui/ConfirmDialog.test.tsx src/components/ui/Table.test.tsx src/components/ui/Field.test.tsx src/settings/SettingRow.test.tsx
```

Expected: FAIL. Dialog, ConfirmDialog, Table and SettingRow fail to collect at all
(`Failed to resolve import "./Dialog"`, and the same for the other three modules);
`Field.test.tsx` collects and its three new cases fail, the first with
`Unable to find a label with the text of: Brawl Stars API token` because `type="password"`
is not yet a value `FieldProps` allows.

- [ ] **Step 5: Lift the focus trap out of Drawer**

Create `brawlfarm/web/src/components/ui/useFocusTrap.ts`:

```ts
/**
 * The modal focus contract, in one place.
 *
 * Focus moves into the panel on open, Tab cycles inside it, Escape closes it, and focus
 * returns to whatever opened it. Written by hand rather than pulled from a library: the
 * panel has two modals and neither owes anything to a dependency.
 *
 * onClose is held in a ref so the effect depends on `open` alone. A caller that builds
 * onClose inline hands over a new function on every render, and re-running the effect
 * would fire its cleanup, which returns focus to the opener and so takes focus straight
 * back out of the panel that just opened.
 */
import { type RefObject, useEffect, useRef } from "react";

const FOCUSABLE =
  'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function useFocusTrap(
  open: boolean,
  ref: RefObject<HTMLElement | null>,
  onClose: () => void,
): void {
  const onCloseRef = useRef(onClose);

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  useEffect(() => {
    if (!open) return;
    const panel = ref.current;
    if (panel === null) return;
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    panel.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onCloseRef.current();
        return;
      }
      if (event.key !== "Tab") return;
      const focusable = [...panel.querySelectorAll<HTMLElement>(FOCUSABLE)];
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      opener?.focus();
    };
    // ref is the stable object useRef returns, so only `open` ever re-runs the trap.
  }, [open, ref]);
}
```

In `brawlfarm/web/src/components/ui/Drawer.tsx`, replace the imports, the `FOCUSABLE`
constant and both effects with the hook call. The file's module comment keeps its first
paragraph and loses the sentence about writing the trap by hand, which now lives in
`useFocusTrap.ts`; the returned markup is not touched.

```tsx
/**
 * A right-side modal panel.
 *
 * Focus moves into the panel on open, Tab cycles inside it, Escape closes it, and focus
 * returns to whatever opened it: useFocusTrap owns all four, and Dialog shares the same
 * hook, so the two modals cannot drift apart.
 */
import { type ReactNode, useRef } from "react";

import { Button } from "./Button";
import { useFocusTrap } from "./useFocusTrap";

export interface DrawerProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  actions?: ReactNode;
}

export function Drawer({ open, onClose, title, children, actions }: DrawerProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  useFocusTrap(open, panelRef, onClose);

  if (!open) return null;
```

Everything from `return (` to the end of the file stays exactly as it is.

- [ ] **Step 6: Write the four new components and the two Field props**

Create `brawlfarm/web/src/components/ui/Dialog.tsx`:

```tsx
/**
 * A centred modal.
 *
 * The same focus contract as Drawer, because it is literally the same hook. A click on the
 * backdrop closes it and a click on the panel does not, which is why the backdrop is the
 * panel's sibling rather than its parent: no click has to be stopped from propagating.
 */
import { type ReactNode, useId, useRef } from "react";

import { useFocusTrap } from "./useFocusTrap";

export interface DialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  actions?: ReactNode;
}

export function Dialog({ open, onClose, title, children, actions }: DialogProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const titleId = useId();
  useFocusTrap(open, panelRef, onClose);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div aria-hidden="true" className="absolute inset-0 bg-scrim" onClick={onClose} />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className="relative w-[480px] max-w-full rounded-[10px] border border-line bg-panel outline-none"
      >
        <h2 id={titleId} className="border-b border-line px-4 py-3 text-[15px] font-semibold">
          {title}
        </h2>
        <div className="px-4 py-3 text-[13px]">{children}</div>
        {actions !== undefined && (
          <div className="flex items-center justify-end gap-2 border-t border-line px-4 py-3">
            {actions}
          </div>
        )}
      </div>
    </div>
  );
}
```

Create `brawlfarm/web/src/components/ui/ConfirmDialog.tsx`:

```tsx
/**
 * A dialog that will not fire until the name is typed out.
 *
 * Removing an instance and deleting a data folder cannot be undone, so the confirm button
 * stays disabled, and says what to type, until the trimmed value equals `word` exactly.
 * Case sensitive: on a case-sensitive disk Pie64 and pie64 are two different folders.
 *
 * The bad tone is one custom property on a wrapper rather than a new Button variant.
 * theme.css declares its colours with `@theme inline`, so `bg-accent` compiles to
 * `background-color: var(--accent)`: pointing --accent at --bad for this one subtree turns
 * the fill, and the focus ring with it, red in both themes, and Button's props stay exactly
 * as phase 4 left them.
 */
import { type ReactNode, useEffect, useId, useState } from "react";

import { Button } from "./Button";
import { Dialog } from "./Dialog";
import { Field } from "./Field";

export interface ConfirmDialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  body: ReactNode;
  word: string;
  confirmLabel: string;
  tone: "bad";
  onConfirm: () => void | Promise<void>;
}

const TONE_ACCENT: Record<ConfirmDialogProps["tone"], string> = {
  bad: "[--accent:var(--bad)]",
};

export function ConfirmDialog({
  open,
  onClose,
  title,
  body,
  word,
  confirmLabel,
  tone,
  onConfirm,
}: ConfirmDialogProps) {
  const [typed, setTyped] = useState("");
  const boxId = useId();
  const matches = typed.trim() === word;

  // The next thing this dialog confirms is a different instance, so a closed dialog cannot
  // keep the last name: reopening it would find the button already armed.
  useEffect(() => {
    if (!open) setTyped("");
  }, [open]);

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={title}
      actions={
        <>
          <Button variant="text" onClick={onClose}>
            Cancel
          </Button>
          <span className={TONE_ACCENT[tone]}>
            <Button
              variant="primary"
              disabled={!matches}
              disabledReason={`Type ${word} to confirm`}
              onClick={() => {
                // The caller owns the failure: it is the one that knows whether a refusal
                // belongs in a toast, in a row, or under the section title.
                void onConfirm();
              }}
            >
              {confirmLabel}
            </Button>
          </span>
        </>
      }
    >
      <div className="space-y-3">
        <div>{body}</div>
        <Field
          label="Type to confirm"
          id={boxId}
          value={typed}
          onChange={setTyped}
          width="full"
          placeholder={word}
        />
      </div>
    </Dialog>
  );
}
```

Create `brawlfarm/web/src/components/ui/Table.tsx`:

```tsx
/**
 * The panel's one table.
 *
 * A real <table> with a <th scope="col"> per column, because both settings tables are
 * genuinely tabular and a grid of divs hands a screen reader a wall of unrelated text. A
 * column has no value accessor: `render` is how every cell gets its content, which is what
 * lets a status chip, an inline field and a row of buttons all be ordinary columns.
 *
 * A column whose label is empty still gets a header cell, named by its key and hidden with
 * sr-only on a span inside the cell rather than on the cell itself: sr-only is
 * position:absolute, and that would take the header out of the table's column flow.
 */
import type { ReactNode } from "react";

export interface Column<Row> {
  key: string;
  label: string;
  mono?: boolean;
  /** A CSS track for this column, e.g. "120px", written onto its <col>. */
  width?: string;
  render?: (row: Row) => ReactNode;
}

export interface TableProps<Row> {
  columns: readonly Column<Row>[];
  rows: readonly Row[];
  rowKey: (row: Row) => string;
  empty: ReactNode;
}

export function Table<Row>({ columns, rows, rowKey, empty }: TableProps<Row>) {
  return (
    <table className="w-full border-collapse text-[13px]">
      <colgroup>
        {columns.map((column) => (
          <col
            key={column.key}
            style={column.width === undefined ? undefined : { width: column.width }}
          />
        ))}
      </colgroup>
      <thead>
        <tr className="border-b border-line">
          {columns.map((column) => (
            <th
              key={column.key}
              scope="col"
              className="px-2 py-1.5 text-left text-[11px] font-medium uppercase tracking-wide text-muted"
            >
              {column.label === "" ? <span className="sr-only">{column.key}</span> : column.label}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.length === 0 ? (
          <tr>
            <td colSpan={columns.length} className="px-2 py-3 text-[13px] text-muted">
              {empty}
            </td>
          </tr>
        ) : (
          rows.map((row) => (
            <tr
              key={rowKey(row)}
              className="border-b border-line last:border-b-0 hover:bg-panel-2"
            >
              {columns.map((column) => (
                <td
                  key={column.key}
                  className={`px-2 py-1.5 align-middle ${column.mono === true ? "font-mono tabular-nums" : ""}`}
                >
                  {column.render === undefined ? null : column.render(row)}
                </td>
              ))}
            </tr>
          ))
        )}
      </tbody>
    </table>
  );
}
```

Replace `brawlfarm/web/src/components/ui/Field.tsx` entirely:

```tsx
/**
 * A labelled input with an optional unit suffix. `step` is here because the schedule's
 * "Run for" field counts in half hours; everything else leaves it alone.
 *
 * type="password" is the Brawl Stars token and nothing else. The input is masked,
 * autocomplete is off so no browser offers to remember it, it carries data-private so the
 * screenshot pass blurs it, and a trailing button reveals it. Revealing is component state
 * and nothing more: the token is never logged, never stored outside the query cache and
 * the PUT body, and never rendered unmasked by default.
 */
import { Eye, EyeOff } from "lucide-react";
import { useState } from "react";

export interface FieldProps {
  label: string;
  id: string;
  value: string;
  onChange: (v: string) => void;
  type?: "text" | "number" | "password";
  /** "control" is the phase 4 width (w-24); "full" fills its row. */
  width?: "control" | "full";
  suffix?: string;
  min?: number;
  step?: number;
  disabled?: boolean;
  placeholder?: string;
  list?: string;
}

const WIDTHS: Record<NonNullable<FieldProps["width"]>, string> = {
  control: "w-24",
  full: "w-full",
};

export function Field({
  label,
  id,
  value,
  onChange,
  type = "text",
  width = "control",
  suffix,
  min,
  step,
  disabled = false,
  placeholder,
  list,
}: FieldProps) {
  const [revealed, setRevealed] = useState(false);
  const masked = type === "password";

  return (
    <div className={`flex items-center gap-2 ${width === "full" ? "w-full" : ""}`}>
      <label htmlFor={id} className="text-[12px] text-muted">
        {label}
      </label>
      <input
        id={id}
        type={masked && !revealed ? "password" : masked ? "text" : type}
        value={value}
        min={min}
        step={step}
        list={list}
        disabled={disabled}
        placeholder={placeholder}
        autoComplete={masked ? "off" : undefined}
        data-private={masked ? "" : undefined}
        onChange={(event) => onChange(event.target.value)}
        className={`h-8 rounded-[6px] border border-line bg-panel-2 px-2 font-mono text-[13px] tabular-nums text-text disabled:cursor-not-allowed disabled:opacity-50 ${WIDTHS[width]}`}
      />
      {masked && (
        <button
          type="button"
          aria-label={revealed ? "Hide" : "Show"}
          onClick={() => setRevealed((on) => !on)}
          className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-[6px] border border-line bg-panel-2 text-muted transition-colors duration-[120ms] hover:text-text"
        >
          {revealed ? (
            <EyeOff size={16} strokeWidth={1.6} aria-hidden="true" />
          ) : (
            <Eye size={16} strokeWidth={1.6} aria-hidden="true" />
          )}
        </button>
      )}
      {suffix !== undefined && <span className="text-[12px] text-muted">{suffix}</span>}
    </div>
  );
}
```

Create `brawlfarm/web/src/settings/SettingRow.tsx`:

```tsx
/**
 * One setting: what it is called, one plain sentence saying what it does, the control that
 * changes it, and the API's own message when that control's last save was refused.
 *
 * Every Connection, Behavior, Schedule and Notifications row goes through here, which is
 * what turns "one plain sentence per setting" into a structure rather than a habit.
 *
 * Two arbitrary variants sit on the control column. Switch and Field each render their own
 * visible label, and that label is this row's title, so without them the reader would see
 * the same words twice: the switch's copy is shrunk to nothing and the field's label is
 * made screen-reader-only. Both stay in the accessibility tree as the control's name, which
 * is where they belong, and neither component's props change, which is what phase 4
 * promised.
 */
import type { ReactNode } from "react";

export interface SettingRowProps {
  title: string;
  description: string;
  error?: string;
  children: ReactNode;
}

export function SettingRow({ title, description, error, children }: SettingRowProps) {
  return (
    <div className="border-b border-line py-3 last:border-b-0">
      <div className="flex flex-wrap items-start gap-4">
        <div className="min-w-[220px] flex-1">
          <p className="text-[13px]">{title}</p>
          <p className="mt-0.5 text-[12px] text-muted">{description}</p>
        </div>
        <div className="w-[280px] max-w-full shrink-0 [&_[role=switch]]:gap-0 [&_[role=switch]]:text-[0px] [&_label]:sr-only">
          {children}
        </div>
      </div>
      {error !== undefined && <p className="mt-1 text-[12px] text-bad">{error}</p>}
    </div>
  );
}
```

- [ ] **Step 7: Run the five files, then everything**

```bash
pnpm --dir brawlfarm/web test src/components/ui/Dialog.test.tsx src/components/ui/ConfirmDialog.test.tsx src/components/ui/Table.test.tsx src/components/ui/Field.test.tsx src/settings/SettingRow.test.tsx src/components/ui/Drawer.test.tsx
pnpm --dir brawlfarm/web typecheck
pnpm --dir brawlfarm/web test
pnpm --dir brawlfarm/web build
```

Expected: the six files at 5, 3, 3, 5, 3 and 5 tests, all passing. `Drawer.test.tsx` is at
5 and was not edited: if any of its five fails, the trap did not come out intact and the
fix belongs in `useFocusTrap.ts`, not in the test. `tsc --noEmit` prints nothing. The whole
suite is 38 files and 297 tests (34 and 280 before this task, plus 4 files and 17 tests).
`vite build` writes `brawlfarm/web/dist/index.html`.

- [ ] **Step 8: Commit**

```bash
uv run python tools/scrub_check.py && git add brawlfarm/web/src && git commit -m "feat(web): the modal, table and field primitives the settings screen needs

useFocusTrap comes out of Drawer so Dialog can share it byte for byte;
Drawer's own tests are the gate and were not touched. Dialog is the
centred modal, ConfirmDialog is Dialog plus a typed-name gate that stays
disabled, and says what to type, until the trimmed value matches exactly.
Table is a real table whose cells are render functions, so a status chip
or an inline field is an ordinary column. Field grows two optional props
and nothing else: type=\"password\" for the Brawl Stars token, masked with
autocomplete off and data-private for the screenshot pass, and
width=\"full\" for the rows that fill their line. SettingRow is the shape
of one setting.

AppSettings grows from the theme-only shape to the whole config.toml
document, which is what the settings screen writes back, and makeSettings
joins the fixtures so no later test hand-writes it. The new GET
/api/health payload is HealthResponse, because Health is already this
file's instance-health union.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CQ1GimQ3uiR2sXPzfZLNWV"
```

Expected: the scrub prints `0 hit(s)` and the commit runs. The scrub is chained on its exit
code, never piped, so a hit stops the commit instead of scrolling past it.

---

### Task 2: Foundations B. The one write path, and the 422 mapper

The back half of the brief's task 1. `useSettingsPatch` is the only way a setting reaches
disk in phase 5: every settings section and every wizard step writes through it, so there is
exactly one place that knows the API has no PATCH, one place that queues writes, and one
place that turns a 422 into a message under the field that caused it.

Accepted proposal ids covered: `set-save`.

**Files:**
- Modify: `brawlfarm/web/src/api/settings.ts` (rewrite the comment; add `putSettings`)
- Create: `brawlfarm/web/src/settings/useSettingsPatch.ts`
- Test: `brawlfarm/web/src/settings/useSettingsPatch.test.tsx` (create)

**Interfaces:**
- Consumes: task 1's `AppSettings` and `makeSettings`; `api<T>()`, `ApiError` from
  `api/client.ts`; `queryKeys.settings()` and `queryKeys.instances()` from `api/queries.ts`;
  `hhmm` from `lib/time.ts`; `toast` from `lib/toast.ts`; `testQueryClient` from
  `test/renderWithProviders.tsx`; `stubFetch`, `jsonResponse`, `FetchCall` from `test/http.ts`.
- Produces:
  - `api/settings.ts`: `putSettings(doc: AppSettings): Promise<AppSettings>`
  - `settings/useSettingsPatch.ts`:
    ```ts
    export interface SettingsPatch {
      settings: AppSettings | undefined;
      patch: (mutate: (draft: AppSettings) => void) => Promise<void>;
      savedAt: string | null;
      fieldErrors: Record<string, string>;
      sectionErrors: string[];
      pending: boolean;
    }
    export function useSettingsPatch(): SettingsPatch;
    export function settingsFieldErrors(detail: string): {
      fields: Record<string, string>;
      rest: string[];
    };
    export function fieldError(errors: Record<string, string>, loc: string): string | undefined;
    export function saveSetting(
      patch: SettingsPatch["patch"],
      mutate: (draft: AppSettings) => void,
      onFailure: (error: unknown) => void,
    ): void;
    export function saveSettingAsync(
      patch: SettingsPatch["patch"],
      mutate: (draft: AppSettings) => void,
      onFailure: (error: unknown) => void,
    ): Promise<void>;
    export function useDebouncedSave(
      stored: string,
      save: (value: string) => Promise<void>,
    ): { value: string; onChange: (next: string) => void; onBlur: () => void };
    ```
  - The rejection contract every later task relies on: `patch` resolves when the document
    is on disk, and rejects with the `ApiError` on every failure, including the 422 it has
    already mapped into `fieldErrors`. `saveSetting` is the wrapper the sections use: it
    toasts `"Settings saved"` on success, swallows the 422 (already on screen under its
    field) and hands everything else, the 409 included, to `onFailure`. `saveSettingAsync`
    is that same wrapper with the promise kept, for the one caller that has to wait:
    `useDebouncedSave` only knows a save landed because it resolved.
- Consumed by: tasks 5, 6, 7 (every settings section), tasks 8, 9, 10 (every wizard step).

- [ ] **Step 1: Write the failing test**

Create `brawlfarm/web/src/settings/useSettingsPatch.test.tsx`:

```tsx
/** The one write path: it re-reads before it writes, it writes the whole document, two
 * quick changes queue instead of racing, a 422 lands under the field that caused it, and a
 * 409 reaches the caller with the API's own sentence. */
import { QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  fieldError,
  saveSetting,
  saveSettingAsync,
  settingsFieldErrors,
  useDebouncedSave,
  useSettingsPatch,
} from "./useSettingsPatch";
import { ApiError } from "../api/client";
import type { AppSettings } from "../api/types";
import { resetToasts, useToasts } from "../lib/toast";
import { makeSettings } from "../test/fixtures";
import { type FetchCall, jsonResponse, stubFetch } from "../test/http";
import { testQueryClient } from "../test/renderWithProviders";

const SETTINGS = "/api/settings";

/** A settings route that remembers: GET serves what is stored, PUT stores the body and
 * echoes it, which is exactly what brawlfarm/api/settings_routes.py does. */
function server(options: { putStatus?: number; putDetail?: string } = {}) {
  let stored = makeSettings();
  const { calls } = stubFetch((url, init) => {
    if (url !== SETTINGS) throw new Error(`unstubbed request: ${url}`);
    if (init?.method !== "PUT") return jsonResponse(stored);
    if (options.putStatus !== undefined) {
      return jsonResponse({ detail: options.putDetail }, options.putStatus);
    }
    stored = JSON.parse(String(init.body)) as AppSettings;
    return jsonResponse(stored);
  });
  return { calls, current: () => stored };
}

function mount() {
  const client = testQueryClient();
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return { client, ...renderHook(() => useSettingsPatch(), { wrapper }) };
}

/** Every settings document this panel has sent, parsed. */
function puts(calls: FetchCall[]): AppSettings[] {
  return calls
    .filter((call) => call.init?.method === "PUT")
    .map((call) => JSON.parse(String(call.init?.body)) as AppSettings);
}

/** Where in `calls` each PUT sits, so the GET in front of it can be checked. */
function putIndexes(calls: FetchCall[]): number[] {
  return calls.flatMap((call, index) => (call.init?.method === "PUT" ? [index] : []));
}

function toastMessages(): string[] {
  return renderHook(() => useToasts()).result.current.map((item) => item.message);
}

afterEach(() => {
  resetToasts();
  vi.unstubAllGlobals();
});

describe("settingsFieldErrors", () => {
  it("splits one error into its loc and its message", () => {
    expect(settingsFieldErrors("connection.adb_path: file not found")).toEqual({
      fields: { "connection.adb_path": "file not found" },
      rest: [],
    });
  });

  it("splits the joined list pydantic produces", () => {
    expect(
      settingsFieldErrors(
        "app.port: Input should be less than 65536; instances.0.player_tag: player tag must be # followed by letters from 0289PYLQGRJCUV",
      ),
    ).toEqual({
      fields: {
        "app.port": "Input should be less than 65536",
        "instances.0.player_tag":
          "player tag must be # followed by letters from 0289PYLQGRJCUV",
      },
      rest: [],
    });
  });

  it("keeps a piece it cannot split, rather than dropping it", () => {
    // A sentence the API grows later still has to reach the reader, under the section
    // title instead of under a field.
    expect(settingsFieldErrors("instance names must be unique; app.port: too big")).toEqual({
      fields: { "app.port": "too big" },
      rest: ["instance names must be unique"],
    });
    expect(settingsFieldErrors("")).toEqual({ fields: {}, rest: [] });
  });
});

describe("fieldError", () => {
  it("shows the last segment of the loc, and nothing at all for a field with no error", () => {
    const errors = { "connection.adb_path": "file not found" };
    expect(fieldError(errors, "connection.adb_path")).toBe("adb_path: file not found");
    expect(fieldError(errors, "connection.brawl_api_token")).toBeUndefined();
  });
});

describe("useSettingsPatch", () => {
  it("re-reads, mutates and puts the whole document back", async () => {
    const { calls, current } = server();
    const { result, client } = mount();
    await waitFor(() => {
      expect(result.current.settings).not.toBeUndefined();
    });

    await act(async () => {
      await result.current.patch((draft) => {
        draft.behavior.gas_aware = false;
      });
    });

    const sent = puts(calls);
    expect(sent).toHaveLength(1);
    expect(sent[0].behavior.gas_aware).toBe(false);
    // The whole document goes, not one key: the API has no PATCH, and a partial PUT would
    // drop every section it did not send.
    expect(sent[0].notifications.ntfy_server).toBe("https://ntfy.sh");
    expect(sent[0].instances).toEqual([{ name: "Pie64", adb_port: 5555, player_tag: "#2P0YLQ9" }]);
    // The read in front of the write is a fresh GET, never the cached copy.
    expect(calls[putIndexes(calls)[0] - 1].init?.method).toBeUndefined();
    expect(current().behavior.gas_aware).toBe(false);
    expect(client.getQueryData(["settings"])).toEqual(current());
    expect(result.current.savedAt).toMatch(/^\d\d:\d\d$/);
    expect(result.current.fieldErrors).toEqual({});
    expect(result.current.pending).toBe(false);
  });

  it("queues two quick changes so the second reads what the first stored", async () => {
    const { calls, current } = server();
    const { result } = mount();
    await waitFor(() => {
      expect(result.current.settings).not.toBeUndefined();
    });

    await act(async () => {
      const first = result.current.patch((draft) => {
        draft.behavior.gas_aware = false;
      });
      const second = result.current.patch((draft) => {
        draft.behavior.bush_hide = true;
      });
      await Promise.all([first, second]);
    });

    const sent = puts(calls);
    expect(sent).toHaveLength(2);
    // The second patch read the document the first one saved, so neither flip is lost.
    expect(sent[1].behavior.gas_aware).toBe(false);
    expect(sent[1].behavior.bush_hide).toBe(true);
    expect(current().behavior).toMatchObject({ gas_aware: false, bush_hide: true });
    // No PUT overlapped another: the second one has its own GET immediately in front of it.
    expect(calls[putIndexes(calls)[1] - 1].init?.method).toBeUndefined();
  });

  it("invalidates the instances list only when the document's instances changed", async () => {
    server();
    const { result, client } = mount();
    await waitFor(() => {
      expect(result.current.settings).not.toBeUndefined();
    });
    const invalidate = vi.spyOn(client, "invalidateQueries");

    await act(async () => {
      await result.current.patch((draft) => {
        draft.app.theme = "dark";
      });
    });
    expect(invalidate.mock.calls.map((call) => call[0]?.queryKey)).toEqual([["settings"]]);

    invalidate.mockClear();
    await act(async () => {
      await result.current.patch((draft) => {
        draft.instances.push({ name: "Pie64_3", adb_port: 5585, player_tag: "" });
      });
    });
    // A new instance has to reach the rail and the Fleet grid, not just this screen.
    expect(invalidate.mock.calls.map((call) => call[0]?.queryKey)).toEqual([
      ["settings"],
      ["instances"],
    ]);
  });

  it("puts a 422 under its own field and leaves the stored document alone", async () => {
    const { calls, current } = server({
      putStatus: 422,
      putDetail: "connection.adb_path: file not found; instances.0.player_tag: bad tag",
    });
    const { result, client } = mount();
    await waitFor(() => {
      expect(result.current.settings).not.toBeUndefined();
    });
    const before = client.getQueryData(["settings"]);

    await act(async () => {
      await expect(
        result.current.patch((draft) => {
          draft.connection.adb_path = "D:/nope.exe";
        }),
      ).rejects.toBeInstanceOf(ApiError);
    });

    expect(result.current.fieldErrors).toEqual({
      "connection.adb_path": "file not found",
      "instances.0.player_tag": "bad tag",
    });
    expect(result.current.sectionErrors).toEqual([]);
    expect(fieldError(result.current.fieldErrors, "connection.adb_path")).toBe(
      "adb_path: file not found",
    );
    // The cache is left exactly as it was: the reader keeps looking at what is on disk.
    expect(client.getQueryData(["settings"])).toEqual(before);
    expect(current().connection.adb_path).toBe(makeSettings().connection.adb_path);
    expect(puts(calls)).toHaveLength(1);
  });

  it("hands a 409 to the caller with the API's own sentence", async () => {
    server({ putStatus: 409, putDetail: "Stop Pie64_3 before removing it" });
    const { result } = mount();
    await waitFor(() => {
      expect(result.current.settings).not.toBeUndefined();
    });

    let caught: unknown;
    await act(async () => {
      await result.current
        .patch((draft) => {
          draft.instances = [];
        })
        .catch((error: unknown) => {
          caught = error;
        });
    });

    expect(caught).toBeInstanceOf(ApiError);
    expect((caught as ApiError).status).toBe(409);
    expect((caught as ApiError).detail).toBe("Stop Pie64_3 before removing it");
    // A refusal is not a validation error, so nothing goes under a field.
    expect(result.current.fieldErrors).toEqual({});
  });

  it("saveSetting toasts once the document is on disk, and is silent about a 422", async () => {
    server();
    const first = mount();
    await waitFor(() => {
      expect(first.result.current.settings).not.toBeUndefined();
    });
    const failures: unknown[] = [];
    saveSetting(
      first.result.current.patch,
      (draft) => {
        draft.scheduler.default_enabled = false;
      },
      (error: unknown) => failures.push(error),
    );
    await waitFor(() => {
      expect(toastMessages()).toEqual(["Settings saved"]);
    });
    expect(failures).toEqual([]);
    first.unmount();
    resetToasts();
    vi.unstubAllGlobals();

    server({ putStatus: 422, putDetail: "app.port: Input should be less than 65536" });
    const second = mount();
    await waitFor(() => {
      expect(second.result.current.settings).not.toBeUndefined();
    });
    saveSetting(
      second.result.current.patch,
      (draft) => {
        draft.app.port = 99999;
      },
      (error: unknown) => failures.push(error),
    );
    await waitFor(() => {
      expect(second.result.current.fieldErrors).toEqual({
        "app.port": "Input should be less than 65536",
      });
    });
    // The message is already under app.port; an ErrorBlock saying it again would be the
    // second copy, and no toast is raised for a value that was never stored.
    expect(failures).toEqual([]);
    expect(toastMessages()).toEqual([]);
  });

  it("saveSettingAsync resolves on a save that landed and rejects on one that did not", async () => {
    server({ putStatus: 422, putDetail: "app.port: Input should be less than 65536" });
    const view = mount();
    await waitFor(() => {
      expect(view.result.current.settings).not.toBeUndefined();
    });
    const settled: string[] = [];
    await act(async () => {
      await saveSettingAsync(
        view.result.current.patch,
        (draft) => {
          draft.app.port = 99999;
        },
        () => settled.push("failure"),
      ).then(
        () => settled.push("resolved"),
        () => settled.push("rejected"),
      );
    });
    // Rejected, so the debounce keeps the typed text; and onFailure was not called,
    // because the message is already under app.port.
    expect(settled).toEqual(["rejected"]);
    expect(toastMessages()).toEqual([]);
  });
});

describe("useDebouncedSave", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("saves once the typing stops, and at once on blur", async () => {
    const saved: string[] = [];
    const save = (value: string): Promise<void> => {
      saved.push(value);
      return Promise.resolve();
    };
    const { result } = renderHook(() => useDebouncedSave("1600", save));
    expect(result.current.value).toBe("1600");

    act(() => {
      result.current.onChange("9");
    });
    act(() => {
      result.current.onChange("90");
    });
    expect(result.current.value).toBe("90");
    await act(async () => {
      await vi.advanceTimersByTimeAsync(499);
    });
    expect(saved).toEqual([]);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1);
    });
    expect(saved).toEqual(["90"]);
    // Once the save lands the box shows what is on disk again, not what was typed: the
    // model may have normalised it on the way through.
    expect(result.current.value).toBe("1600");

    act(() => {
      result.current.onChange("900");
    });
    await act(async () => {
      result.current.onBlur();
      await vi.advanceTimersByTimeAsync(0);
    });
    // Leaving the box does not wait out the rest of the debounce.
    expect(saved).toEqual(["90", "900"]);
  });

  it("does nothing on a blur with nothing pending", () => {
    const saved: string[] = [];
    const { result } = renderHook(() =>
      useDebouncedSave("1600", (value) => {
        saved.push(value);
        return Promise.resolve();
      }),
    );
    act(() => {
      result.current.onBlur();
    });
    expect(saved).toEqual([]);
  });
});
```

- [ ] **Step 2: Run it to confirm it fails**

```bash
pnpm --dir brawlfarm/web test src/settings/useSettingsPatch.test.tsx
```

Expected: FAIL to collect, with
`Failed to resolve import "./useSettingsPatch" from "src/settings/useSettingsPatch.test.tsx"`.

- [ ] **Step 3: Add putSettings**

Replace `brawlfarm/web/src/api/settings.ts` entirely:

```ts
/**
 * The settings document.
 *
 * GET and PUT are both whole-document: the API has no PATCH, so every write goes through
 * settings/useSettingsPatch.ts, which reads, mutates a clone and puts the whole thing back.
 * The response carries connection.brawl_api_token in full because the API is loopback-only
 * and masking is the panel's job; exactly one masked Field ever renders it.
 */
import { api } from "./client";
import type { AppSettings } from "./types";

export function getSettings(): Promise<AppSettings> {
  return api<AppSettings>("/api/settings");
}

export function putSettings(doc: AppSettings): Promise<AppSettings> {
  return api<AppSettings>("/api/settings", { method: "PUT", body: JSON.stringify(doc) });
}
```

- [ ] **Step 4: Write the hook and its two pure helpers**

Create `brawlfarm/web/src/settings/useSettingsPatch.ts`:

```ts
/**
 * The one way a setting reaches disk.
 *
 * The API's settings route is whole-document, so every write is read-modify-write, and the
 * read is a fresh GET rather than the cached copy: the supervisor rewrites config.toml on
 * an apply and on a reset, and a stale cached section would be put straight back.
 *
 * Patches queue on a module-level chain rather than a per-hook one. Two sections can be on
 * screen at once (Instances and every inline tag field in it, or a wizard step and the
 * settings screen behind a reload), and two PUTs in flight against one file is exactly how
 * a flipped switch loses to the one before it.
 *
 * `patch` resolves when the document is on disk and rejects on every failure, including the
 * 422 it has already mapped: a 409 is the caller's to render inline, and anything else is
 * the caller's to put in an ErrorBlock. `saveSetting` is the wrapper the sections use.
 */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "../api/client";
import { queryKeys } from "../api/queries";
import { getSettings, putSettings } from "../api/settings";
import type { AppSettings } from "../api/types";
import { hhmm } from "../lib/time";
import { toast } from "../lib/toast";

export interface SettingsPatch {
  settings: AppSettings | undefined;
  patch: (mutate: (draft: AppSettings) => void) => Promise<void>;
  /** "19:04": the wall-clock time of the last successful PUT, or null before the first. */
  savedAt: string | null;
  /** Keyed by the API's dotted loc, e.g. "connection.adb_path". */
  fieldErrors: Record<string, string>;
  /** Anything the mapper could not place under a field. */
  sectionErrors: string[];
  pending: boolean;
}

/** The chain every patch joins, shared by every mounted section. */
let chain: Promise<void> = Promise.resolve();

/** Section 4 of the brief: a text or number field saves 500 ms after the last keystroke, and
 * immediately on blur. The same debounce the phase 4 farm-plan goal uses. */
const DEBOUNCE_MS = 500;

/**
 * settings._explain joins pydantic's errors as "loc: msg; loc: msg" in one string, and that
 * string is the 422's detail. Split on "; ", then on the first ": ", so a message that has
 * a colon of its own survives. A piece that does not split is not a field error and goes to
 * `rest`, which is how a sentence the API grows later still reaches the reader.
 */
export function settingsFieldErrors(detail: string): {
  fields: Record<string, string>;
  rest: string[];
} {
  const fields: Record<string, string> = {};
  const rest: string[] = [];
  for (const piece of detail.split("; ")) {
    const text = piece.trim();
    if (text === "") continue;
    const at = text.indexOf(": ");
    if (at <= 0) {
      rest.push(text);
      continue;
    }
    fields[text.slice(0, at)] = text.slice(at + 2);
  }
  return { fields, rest };
}

/** A field's error line as its row shows it: the last segment of the dotted loc and the
 * message, so "connection.adb_path: file not found" reads "adb_path: file not found" under
 * the ADB path field. */
export function fieldError(errors: Record<string, string>, loc: string): string | undefined {
  const msg = errors[loc];
  if (msg === undefined) return undefined;
  return `${loc.split(".").pop() ?? loc}: ${msg}`;
}

/** What every settings section does with a patch: toast once the document is on disk, and
 * hand anything else back so the section can show it. A 422 is deliberately swallowed here,
 * because the hook has already put each message under its own field. */
export function saveSettingAsync(
  patch: SettingsPatch["patch"],
  mutate: (draft: AppSettings) => void,
  onFailure: (error: unknown) => void,
): Promise<void> {
  return patch(mutate).then(
    () => {
      toast("Settings saved");
    },
    (error: unknown) => {
      if (!(error instanceof ApiError && error.status === 422)) onFailure(error);
      // Re-thrown so a caller that is waiting can tell a save that landed from one that
      // did not, even for the 422 this function has already dealt with.
      throw error;
    },
  );
}

/** The same thing for a switch or a card, which has nothing to wait for once the toast is
 * queued. */
export function saveSetting(
  patch: SettingsPatch["patch"],
  mutate: (draft: AppSettings) => void,
  onFailure: (error: unknown) => void,
): void {
  void saveSettingAsync(patch, mutate, onFailure).catch(() => undefined);
}

/**
 * One text or number field that saves itself.
 *
 * The typed text wins while the box is being typed in; once the save lands the box goes back
 * to showing what is on disk, which may not be what was typed (the model upper-cases a
 * player tag and puts its # back). A save that failed leaves the typed text alone, so
 * nothing the reader is still fixing is thrown away under them.
 *
 * `save` returns the patch promise and is expected to have reported its own failure already,
 * which is what saveSetting does.
 */
export function useDebouncedSave(
  stored: string,
  save: (value: string) => Promise<void>,
): { value: string; onChange: (next: string) => void; onBlur: () => void } {
  const [text, setText] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // A navigation away must not let a pending debounce write into a screen that is gone.
  useEffect(
    () => () => {
      if (timer.current !== null) clearTimeout(timer.current);
    },
    [],
  );

  const flush = (next: string): void => {
    timer.current = null;
    void save(next)
      .then(() => setText(null))
      .catch(() => undefined);
  };

  return {
    value: text ?? stored,
    onChange: (next: string) => {
      setText(next);
      if (timer.current !== null) clearTimeout(timer.current);
      timer.current = setTimeout(() => flush(next), DEBOUNCE_MS);
    },
    onBlur: () => {
      if (timer.current === null) return; // nothing was typed, so there is nothing to flush
      clearTimeout(timer.current);
      flush(text ?? stored);
    },
  };
}

export function useSettingsPatch(): SettingsPatch {
  const client = useQueryClient();
  const { data } = useQuery({ queryKey: queryKeys.settings(), queryFn: getSettings });
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [sectionErrors, setSectionErrors] = useState<string[]>([]);
  const [pending, setPending] = useState(false);

  const patch = useCallback(
    (mutate: (draft: AppSettings) => void): Promise<void> => {
      const run = async (): Promise<void> => {
        setPending(true);
        try {
          const fresh = await getSettings();
          const draft = structuredClone(fresh);
          mutate(draft);
          const touchedInstances =
            JSON.stringify(draft.instances) !== JSON.stringify(fresh.instances);
          const saved = await putSettings(draft);
          client.setQueryData(queryKeys.settings(), saved);
          void client.invalidateQueries({ queryKey: queryKeys.settings() });
          if (touchedInstances) {
            // A row added or removed here has to reach the rail and the Fleet grid too.
            void client.invalidateQueries({ queryKey: queryKeys.instances() });
          }
          setFieldErrors({});
          setSectionErrors([]);
          setSavedAt(hhmm(new Date().toISOString()));
        } catch (error) {
          if (error instanceof ApiError && error.status === 422) {
            const mapped = settingsFieldErrors(error.detail);
            setFieldErrors(mapped.fields);
            setSectionErrors(mapped.rest);
          }
          throw error;
        } finally {
          setPending(false);
        }
      };
      // The caller waits on its own place in the queue, so a rejection reaches exactly the
      // section that asked for the write; the chain itself swallows it, so one refusal
      // cannot stop every later save.
      const queued = chain.then(run);
      chain = queued.catch(() => undefined);
      return queued;
    },
    [client],
  );

  return { settings: data, patch, savedAt, fieldErrors, sectionErrors, pending };
}
```

- [ ] **Step 5: Run it to confirm it passes, then everything**

```bash
pnpm --dir brawlfarm/web test src/settings/useSettingsPatch.test.tsx
pnpm --dir brawlfarm/web typecheck
pnpm --dir brawlfarm/web test
pnpm --dir brawlfarm/web build
```

Expected: the file at 13 tests, all passing. `tsc --noEmit` prints nothing. The whole suite
is 39 files and 310 tests (38 and 297 after task 1). `vite build` writes
`brawlfarm/web/dist/index.html`.

- [ ] **Step 6: Commit**

```bash
uv run python tools/scrub_check.py && git add brawlfarm/web/src && git commit -m "feat(web): one write path for every setting

The settings route is whole-document, so useSettingsPatch reads fresh,
mutates a clone and puts the whole thing back, then writes the answer
into the query cache. The read is deliberately not the cached copy: the
supervisor rewrites config.toml on an apply and on a reset, and a stale
section would be put straight back on the next save.

Patches queue on a module-level chain, so two quick switch flips cannot
race and no PUT overlaps another. A 422 is mapped by loc, so
\"connection.adb_path: file not found\" shows as \"adb_path: file not
found\" under the ADB path field rather than as a wall of text, and a
piece the mapper cannot split still reaches the reader under the section
title. patch rejects on every failure, which is how a 409 gets to the row
that has to render it inline. useDebouncedSave is the other half of the
same rule: a text field saves 500 ms after the last keystroke and at once
on blur, and goes back to showing what is on disk once it lands, which is
why saveSettingAsync keeps the promise saveSetting throws away.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CQ1GimQ3uiR2sXPzfZLNWV"
```

Expected: `0 hit(s)`, then the commit.

---

### Task 3: Python A. The display sentence, notify.send_test, and the notifications test route

The front half of the brief's task 2. Three changes that stand alone: the one copy string
the wizard's Display step renders verbatim, a pure test-alert sender that touches none of
`notify`'s configured state, and the route the Settings screen's "Send a test" button calls.

This is the only task in phase 5 that touches `brawlfarm/core`, and it adds one function:
`send_test`. Nothing else in `notify.py` changes, and no other file under `brawlfarm/core`
is opened.

Accepted proposal ids covered: part of `wiz-display`, part of `set-notifications`.

**Files:**
- Modify: `brawlfarm/setup/checks.py` (the `DISPLAY_HINT` constant, found by that name)
- Modify: `brawlfarm/core/notify.py` (append `send_test` at the end of the file)
- Create: `brawlfarm/api/notify_routes.py`
- Modify: `brawlfarm/api/app.py` (add `notify_routes` to the `brawlfarm.api` import list; include its router after `settings_routes`)
- Modify: `tests/test_setup_checks.py` (one assertion)
- Test: `tests/test_notify_send_test.py` (create)
- Test: `tests/test_api_notifications.py` (create)

**Interfaces:**
- Consumes: `notify._send_discord(requests, url, title, message, png) -> bool` and
  `notify._send_ntfy(requests, server, topic, title, message, png) -> bool` exactly as they
  are; `get_sup(request)` from `api/deps.py`; `make_client` from `tests/apihelpers.py`.
- Produces:
  - `checks.DISPLAY_HINT` is now
    `"Set the display to 1600 x 900 and pixel density 240 in BlueStacks: Settings, Display, then restart the instance."`,
    which `POST /api/setup/display-check` already returns as `hint`
  - `notify.send_test(*, webhook_url: str, ntfy_server: str, ntfy_topic: str, healthchecks_url: str) -> dict[str, bool]`,
    with a key only for a channel whose value is non-empty, in the order `webhook`, `ntfy`,
    `healthchecks`
  - `POST /api/notifications/test -> {"sent": list[str], "failed": list[str]}`, always 200
- Consumed by: task 7 (`Notifications.tsx` calls the route), task 9 (`StepDisplay` renders
  the hint verbatim).

- [ ] **Step 1: Write the failing tests for send_test**

Create `tests/test_notify_send_test.py`:

```python
"""notify.send_test sends one alert to exactly the channels it is handed, reports each one
as a plain True or False, and leaves the module's own configured state untouched."""

from __future__ import annotations

import sys

import pytest

from brawlfarm.core import notify


class FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class FakeRequests:
    """Stands in for the requests module: records every call, answers with a status, and
    raises instead when the test handed it an exception."""

    def __init__(self, post=200, get=200) -> None:
        self._post, self._get = post, get
        self.posts: list[tuple[str, dict]] = []
        self.gets: list[str] = []

    def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        if isinstance(self._post, Exception):
            raise self._post
        return FakeResponse(self._post)

    def get(self, url, **kwargs):
        self.gets.append(url)
        if isinstance(self._get, Exception):
            raise self._get
        return FakeResponse(self._get)


def _install(monkeypatch, requests: FakeRequests) -> FakeRequests:
    """send_test imports requests lazily, so the fake only has to be in sys.modules."""
    monkeypatch.setitem(sys.modules, "requests", requests)
    return requests


@pytest.fixture()
def fake(monkeypatch) -> FakeRequests:
    return _install(monkeypatch, FakeRequests())


def test_every_configured_channel_is_reported(fake) -> None:
    result = notify.send_test(
        webhook_url="https://hook.invalid/abc",
        ntfy_server="https://ntfy.example/",
        ntfy_topic="brawlfarm-test",
        healthchecks_url="https://hc.invalid/ping",
    )
    assert result == {"webhook": True, "ntfy": True, "healthchecks": True}
    # The UI joins these names with ", " into one toast, so the order is part of the copy.
    assert list(result) == ["webhook", "ntfy", "healthchecks"]
    assert [url for url, _ in fake.posts] == [
        "https://hook.invalid/abc",
        "https://ntfy.example/brawlfarm-test",  # the trailing slash is stripped
    ]
    assert fake.gets == ["https://hc.invalid/ping"]
    assert fake.posts[0][1]["json"]["content"] == (
        "**brawlfarm test**\nThis is a test alert from brawlfarm."
    )
    assert fake.posts[1][1]["headers"]["Title"] == "brawlfarm test"
    assert fake.posts[1][1]["data"] == b"This is a test alert from brawlfarm."


def test_a_channel_that_does_not_answer_is_a_failure_not_an_exception(monkeypatch) -> None:
    _install(monkeypatch, FakeRequests(post=500, get=RuntimeError("name resolution failed")))
    result = notify.send_test(
        webhook_url="https://hook.invalid/abc",
        ntfy_server="https://ntfy.sh",
        ntfy_topic="brawlfarm-test",
        healthchecks_url="https://hc.invalid/ping",
    )
    # A test that explodes tells the user less than a test that says no.
    assert result == {"webhook": False, "ntfy": False, "healthchecks": False}


def test_an_unset_channel_gets_no_key_at_all(fake) -> None:
    assert notify.send_test(
        webhook_url="",
        ntfy_server="https://ntfy.sh",
        ntfy_topic="brawlfarm-test",
        healthchecks_url="",
    ) == {"ntfy": True}
    assert (
        notify.send_test(
            webhook_url="", ntfy_server="https://ntfy.sh", ntfy_topic="", healthchecks_url=""
        )
        == {}
    )
    # Whitespace is not a channel, so nothing is sent and nothing is claimed.
    assert (
        notify.send_test(
            webhook_url="   ", ntfy_server=" ", ntfy_topic="  ", healthchecks_url=" "
        )
        == {}
    )
    assert fake.posts == [("https://ntfy.sh/brawlfarm-test", fake.posts[0][1])]


def test_it_leaves_the_modules_own_settings_alone(fake) -> None:
    notify.configure(webhook_url="https://configured.invalid/z", events=["crash"])
    before = dict(notify._overrides)

    notify.send_test(
        webhook_url="https://typed.invalid/abc",
        ntfy_server="https://ntfy.sh",
        ntfy_topic="typed-topic",
        healthchecks_url="",
    )

    assert notify._overrides == before
    assert notify._webhook_url() == "https://configured.invalid/z"
    assert notify.enabled_events() == frozenset({"crash"})
    assert notify._last_alert == {}  # no per-kind cooldown was started
    # The test went where the screen said, not where the supervisor is configured.
    assert [url for url, _ in fake.posts] == [
        "https://typed.invalid/abc",
        "https://ntfy.sh/typed-topic",
    ]
```

- [ ] **Step 2: Write the failing tests for the route**

Create `tests/test_api_notifications.py`:

```python
"""POST /api/notifications/test: what is tested is what is saved, the answer is two lists of
channel names in a fixed order, and no URL or topic ever appears in it."""

from __future__ import annotations

from pathlib import Path

import pytest

from brawlfarm.core import notify
from tests.apihelpers import make_client


@pytest.fixture()
def api(tmp_path: Path):
    client, sup, home = make_client(tmp_path, ("alpha", "bravo"))
    try:
        yield client, sup, home
    finally:
        client.__exit__(None, None, None)


def test_it_splits_the_channels_into_sent_and_failed(api, monkeypatch) -> None:
    client, sup, _home = api
    sup.settings.notifications.webhook_url = "https://hook.invalid/abc"
    sup.settings.notifications.ntfy_topic = "brawlfarm-test"
    seen: dict[str, str] = {}

    def fake_send_test(*, webhook_url, ntfy_server, ntfy_topic, healthchecks_url):
        seen.update(
            webhook_url=webhook_url,
            ntfy_server=ntfy_server,
            ntfy_topic=ntfy_topic,
            healthchecks_url=healthchecks_url,
        )
        return {"webhook": False, "ntfy": True}

    monkeypatch.setattr(notify, "send_test", fake_send_test)
    r = client.post("/api/notifications/test")
    assert r.status_code == 200
    assert r.json() == {"sent": ["ntfy"], "failed": ["webhook"]}
    # The route reads the supervisor's own section, so the screen tests what is on disk.
    assert seen["webhook_url"] == "https://hook.invalid/abc"
    assert seen["ntfy_topic"] == "brawlfarm-test"
    assert seen["ntfy_server"] == "https://ntfy.sh"
    assert seen["healthchecks_url"] == ""


def test_no_channel_configured_is_two_empty_lists_and_still_a_200(api, monkeypatch) -> None:
    client, _sup, _home = api
    monkeypatch.setattr(notify, "send_test", lambda **kwargs: {})
    r = client.post("/api/notifications/test")
    assert r.status_code == 200
    assert r.json() == {"sent": [], "failed": []}


def test_it_keeps_the_channel_order_send_test_returned(api, monkeypatch) -> None:
    client, _sup, _home = api
    monkeypatch.setattr(
        notify,
        "send_test",
        lambda **kwargs: {"webhook": True, "ntfy": True, "healthchecks": True},
    )
    body = client.post("/api/notifications/test").json()
    assert body["sent"] == ["webhook", "ntfy", "healthchecks"]
    assert body["failed"] == []


def test_the_answer_never_carries_a_url_or_a_topic(api, monkeypatch) -> None:
    client, sup, _home = api
    sup.settings.notifications.webhook_url = "https://hook.invalid/not-in-the-answer"
    sup.settings.notifications.ntfy_topic = "not-in-the-answer-either"
    monkeypatch.setattr(notify, "send_test", lambda **kwargs: {"webhook": True, "ntfy": False})
    text = client.post("/api/notifications/test").text
    assert "not-in-the-answer" not in text
    assert text == '{"sent":["webhook"],"failed":["ntfy"]}'
```

- [ ] **Step 3: Update the display-hint assertion**

In `tests/test_setup_checks.py`, in
`test_display_check_explains_a_mismatch_and_where_to_fix_it`, replace the last line:

```python
    assert "Settings, Display" in result.hint
```

The line above it, `assert result.hint == checks.DISPLAY_HINT`, stays. Nothing in
`tests/test_api_setup_routes.py` changes: it compares against the constant.

- [ ] **Step 4: Run the three modules to confirm they fail**

```bash
cd <repo>
uv run pytest tests/test_notify_send_test.py tests/test_api_notifications.py tests/test_setup_checks.py -q
```

Expected: FAIL.
`tests/test_notify_send_test.py` fails with
`AttributeError: module 'brawlfarm.core.notify' has no attribute 'send_test'`;
`tests/test_api_notifications.py` fails the same way at `monkeypatch.setattr`, and its first
case would otherwise get a 405 on an unrouted path;
`tests/test_setup_checks.py` fails with
`AssertionError: assert 'Settings, Display' in 'In BlueStacks open Settings > Display, ...'`.

- [ ] **Step 5: Correct the display sentence**

In `brawlfarm/setup/checks.py`, replace the `DISPLAY_HINT` constant:

```python
DISPLAY_HINT = (
    "Set the display to 1600 x 900 and pixel density 240 in BlueStacks: Settings, Display, "
    "then restart the instance."
)
```

The BlueStacks path really is Settings, Display, and resolution and pixel density are the
only two options on it, so the sentence names what to set before where to set it.

- [ ] **Step 6: Add send_test to notify**

Append to the end of `brawlfarm/core/notify.py`, after `maybe_alert`:

```python
def send_test(
    *,
    webhook_url: str,
    ntfy_server: str,
    ntfy_topic: str,
    healthchecks_url: str,
) -> dict[str, bool]:
    """Send one test alert to exactly the channels the caller passed in.

    The control panel's "Send a test" button has four values on screen, and they are not
    necessarily the ones the supervisor is running with, so nothing here reads _overrides,
    calls configure(), consults configured() or touches the per-kind cooldown: a test the
    user asked for must never be swallowed as a repeat of something else.

    A channel whose value is empty gets no key at all, so the caller can tell "did not
    answer" from "was never set up". A channel that raises counts as False: a test that
    explodes tells the user less than a test that says no. requests is imported lazily, the
    same way the rest of this module does it.
    """
    title = "brawlfarm test"
    message = "This is a test alert from brawlfarm."
    webhook = webhook_url.strip()
    server = ntfy_server.strip().rstrip("/")
    topic = ntfy_topic.strip()
    ping = healthchecks_url.strip()
    results: dict[str, bool] = {}
    if not (webhook or topic or ping):
        return results
    try:
        import requests
    except Exception:  # without requests no channel can answer, and none is claimed to
        for name, value in (("webhook", webhook), ("ntfy", topic), ("healthchecks", ping)):
            if value:
                results[name] = False
        return results

    if webhook:
        results["webhook"] = _send_discord(requests, webhook, title, message, None)
    if topic:
        results["ntfy"] = _send_ntfy(requests, server, topic, title, message, None)
    if ping:
        try:
            response = requests.get(ping, timeout=5)
            results["healthchecks"] = int(getattr(response, "status_code", 0)) < 300
        except Exception:
            results["healthchecks"] = False
    return results
```

- [ ] **Step 7: Write the route and register it**

Create `brawlfarm/api/notify_routes.py`:

```python
"""POST /api/notifications/test: send one alert to the channels config.toml names, now.

The Settings screen's "Send a test" button. The route takes no body and reads the
supervisor's own [notifications] section instead, so what is tested is what is saved. It
calls notify.send_test, which touches none of that module's configured state and has no
cooldown, through asyncio.to_thread: three network calls on the event loop would stall the
supervisor task and the SSE stream behind them.

Always 200. A channel that did not answer is a name in `failed`, not an HTTP error, because
the panel wants to show three outcomes at once. No URL and no topic is logged or returned;
only the channel names are.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request

from brawlfarm.api.deps import get_sup
from brawlfarm.core import notify

router = APIRouter()


@router.post("/api/notifications/test")
async def test_notifications(request: Request) -> dict:
    """Fire one test alert per configured channel and say which of them answered."""
    n = get_sup(request).settings.notifications
    results = await asyncio.to_thread(
        notify.send_test,
        webhook_url=n.webhook_url,
        ntfy_server=n.ntfy_server,
        ntfy_topic=n.ntfy_topic,
        healthchecks_url=n.healthchecks_url,
    )
    return {
        "sent": [name for name, ok in results.items() if ok],
        "failed": [name for name, ok in results.items() if not ok],
    }
```

In `brawlfarm/api/app.py`, add `notify_routes` to the `from brawlfarm.api import (...)` list
(it sorts between `instances` and `plans`):

```python
from brawlfarm.api import (
    alerts,
    events,
    feed,
    instances,
    notify_routes,
    plans,
    roster,
    schedule,
    screens,
    settings_routes,
    setup_routes,
    stats,
)
```

and include its router immediately after `settings_routes`:

```python
    app.include_router(settings_routes.router)
    app.include_router(notify_routes.router)
    app.include_router(setup_routes.router)
```

- [ ] **Step 8: Run the three modules, then the whole suite**

```bash
uv run pytest tests/test_notify_send_test.py tests/test_api_notifications.py tests/test_setup_checks.py -v
uv run pytest -q
```

Expected: `test_notify_send_test.py` at 4 tests and `test_api_notifications.py` at 4, all
passing, and `test_setup_checks.py` green with its assertion updated. The whole suite is
605 tests (597 before this task, plus 8) with no warnings.

- [ ] **Step 9: Lint, scrub, commit**

```bash
uv run ruff format brawlfarm/setup/checks.py brawlfarm/core/notify.py brawlfarm/api/notify_routes.py brawlfarm/api/app.py tests/test_notify_send_test.py tests/test_api_notifications.py tests/test_setup_checks.py
uv run ruff check --fix brawlfarm tests
uv run ruff check . && uv run ruff format --check .
uv run python tools/scrub_check.py && git add brawlfarm/setup/checks.py brawlfarm/core/notify.py brawlfarm/api/notify_routes.py brawlfarm/api/app.py tests/test_notify_send_test.py tests/test_api_notifications.py tests/test_setup_checks.py && git commit -m "feat(api): a notifications test, and the display sentence the wizard reads out

DISPLAY_HINT now says what to set before where to set it, and names the
real BlueStacks path: Settings, Display. The wizard renders it verbatim
from the display-check response, so the sentence has exactly one source.

notify.send_test posts to the four values it is handed and to nothing
else: no _overrides, no configure(), no configured(), no cooldown. A
channel with an empty value gets no key, so the caller can tell a channel
that did not answer from one that was never set up, and a channel that
raises counts as False rather than as an exception. POST
/api/notifications/test reads the supervisor's own section, so what is
tested is what is saved, runs the three calls off the event loop, and
always answers 200 with two lists of channel names. No URL and no topic
is logged or returned.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CQ1GimQ3uiR2sXPzfZLNWV"
```

Expected: `All checks passed!`, every file already formatted, `0 hit(s)`, then the commit.

---

### Task 4: Python B. Reset, open the data folder, delete one instance's data, and the sticky token

The back half of the brief's task 2. Three routes the Data section needs, the one shared
constant they need with the settings route, and the one-line supervisor fix that makes
clearing the API token in Settings actually clear it.

Nothing under `brawlfarm/core` is opened in this task.

Accepted proposal ids covered: `set-data`.

**Files:**
- Modify: `brawlfarm/api/deps.py` (`LIVE_STATES` moves here from `settings_routes.py`, unchanged)
- Modify: `brawlfarm/api/settings_routes.py` (import `LIVE_STATES`; add `POST /api/settings/reset` and `POST /api/settings/open-data-folder`)
- Modify: `brawlfarm/api/instances.py` (add `DELETE /api/instances/{name}/data`)
- Modify: `brawlfarm/supervisor/loop.py` (line 87)
- Test: `tests/test_api_settings.py` (five tests appended)
- Test: `tests/test_api_instances.py` (six tests and one helper appended)
- Test: `tests/test_supervisor_loop.py` (one test appended)

**Interfaces:**
- Consumes: `resolve_instance`, `get_home`, `get_sup` from `api/deps.py`; `S.AppSettings`,
  `S.save`, `S.instance_dir`, `S.config_path`; `Supervisor.apply_settings`,
  `Supervisor.poke`, `Supervisor.views`; `FakeWorld`, `make_client` from
  `tests/apihelpers.py`.
- Produces:
  - `deps.LIVE_STATES: frozenset[InstanceState]` (`FARMING`, `STARTING`, `STOPPING`,
    `RECONNECTING`); `settings_routes.LIVE_STATES` is gone, and every importer takes it
    from `deps`
  - `POST /api/settings/reset -> 200` with the whole reset document
  - `POST /api/settings/open-data-folder -> 204`, `501 {"detail": "Only on Windows"}`,
    `500 {"detail": "could not open the data folder"}`
  - `DELETE /api/instances/{name}/data -> 204`, `404 "unknown instance"`,
    `409 "Stop {name} before deleting its data"`,
    `400 "refusing to delete outside the data folder"`,
    `409 "could not delete {name}'s data; a file is still in use"`
  - `Supervisor.apply_settings` now clears `config.API_TOKEN` when the setting is blank,
    falling back to `BRAWL_API_TOKEN` rather than to the last non-blank value
- Consumed by: task 7 (`Data.tsx` calls all three routes).

- [ ] **Step 1: Write the failing settings tests**

Append to `tests/test_api_settings.py`. Add `import os` and `import sys` to the module's
imports, then append these five tests at the end of the file:

```python
def test_reset_restores_every_default_and_keeps_the_instances(api) -> None:
    client, sup, home = api
    doc = client.get("/api/settings").json()
    doc["app"]["theme"] = "dark"
    doc["behavior"]["gas_aware"] = False
    doc["notifications"]["ntfy_topic"] = "brawlfarm-test"
    doc["instances"][0]["player_tag"] = "#2P0YLQ9"
    assert client.put("/api/settings", json=doc).status_code == 200

    r = client.post("/api/settings/reset")
    assert r.status_code == 200
    body = r.json()
    assert body["app"]["theme"] == "system"
    assert body["behavior"]["gas_aware"] is True
    assert body["notifications"]["ntfy_topic"] == ""
    # The one thing a reset must not touch is the fleet, tags and ports included.
    assert [i["name"] for i in body["instances"]] == ["alpha", "bravo"]
    assert body["instances"][0]["player_tag"] == "#2P0YLQ9"
    assert body["instances"][1]["adb_port"] == 5565
    assert sup.settings.app.theme == "system"
    assert sup.settings.notifications.ntfy_topic == ""
    # It was written, not only applied: a restart has to come back reset.
    text = S.config_path(home).read_text(encoding="utf-8")
    assert "brawlfarm-test" not in text
    assert "bravo" in text


def test_reset_works_while_an_instance_is_farming(tmp_path: Path) -> None:
    world = FakeWorld()
    world.alive.add(4242)
    _heartbeat(tmp_path, "bravo", 4242, world.now)
    client, sup, _home = make_client(tmp_path, ("alpha", "bravo"), world=world)
    try:
        assert next(v for v in sup.views() if v.name == "bravo").state == InstanceState.FARMING
        sup.settings.app.theme = "dark"
        r = client.post("/api/settings/reset")
        # Nothing is removed by a reset, so the 409 that guards PUT cannot happen here.
        assert r.status_code == 200
        assert r.json()["app"]["theme"] == "system"
        assert [i.name for i in sup.settings.instances] == ["alpha", "bravo"]
    finally:
        client.__exit__(None, None, None)


def test_open_data_folder_asks_windows_to_open_the_home_directory(api, monkeypatch) -> None:
    client, _sup, home = api
    opened: list[str] = []
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(os, "startfile", lambda path: opened.append(path), raising=False)
    r = client.post("/api/settings/open-data-folder")
    assert r.status_code == 204
    assert r.content == b""
    assert opened == [str(home)]


def test_open_data_folder_off_windows_says_so(api, monkeypatch) -> None:
    client, _sup, _home = api
    monkeypatch.setattr(sys, "platform", "linux")
    r = client.post("/api/settings/open-data-folder")
    assert r.status_code == 501
    assert r.json() == {"detail": "Only on Windows"}


def test_open_data_folder_reports_a_refusal_without_naming_the_path(api, monkeypatch) -> None:
    client, _sup, home = api

    def denied(path):
        raise OSError("access is denied")

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(os, "startfile", denied, raising=False)
    r = client.post("/api/settings/open-data-folder")
    assert r.status_code == 500
    assert r.json() == {"detail": "could not open the data folder"}
    # The home directory is a Windows user path; it never goes into an error message.
    assert str(home) not in r.text
```

- [ ] **Step 2: Write the failing delete-data tests**

Append to `tests/test_api_instances.py`. Add `from brawlfarm.supervisor import InstanceState`
to the module's imports, then append this helper and six tests at the end of the file:

```python
def _offline_client(tmp_path: Path):
    """alpha and bravo with no BlueStacks window, so the startup tick leaves them offline
    instead of starting them: everything in LIVE_STATES is refused by the delete route, and
    the default fixture's instances are STARTING the moment the lifespan tick has run."""
    world = FakeWorld()
    world.online[5555] = False
    world.online[5565] = False
    return make_client(tmp_path, ("alpha", "bravo"), world=world)


def test_deleting_data_removes_the_folder_and_keeps_the_instance(tmp_path: Path) -> None:
    client, sup, home = _offline_client(tmp_path)
    try:
        inst_dir = S.instance_dir(home, "alpha")
        (inst_dir / "sessions").mkdir(parents=True, exist_ok=True)
        (inst_dir / "games.csv").write_text("battleTime,trophyChange\n", encoding="utf-8")
        (inst_dir / "sessions" / "session-20260911-100000.jsonl").write_text(
            '{"ts": "2026-09-11T10:00:00", "kind": "start"}\n', encoding="utf-8"
        )
        S.instance_dir(home, "bravo").mkdir(parents=True, exist_ok=True)

        r = client.delete("/api/instances/alpha/data")
        assert r.status_code == 204
        assert r.content == b""
        assert not inst_dir.exists()
        assert S.instance_dir(home, "bravo").exists()  # only the one that was asked for
        # This deletes the folder, not the instance: it is still in the fleet and the file.
        assert [i.name for i in sup.settings.instances] == ["alpha", "bravo"]
        assert "alpha" in S.config_path(home).read_text(encoding="utf-8")
    finally:
        client.__exit__(None, None, None)


def test_deleting_data_twice_is_still_204(tmp_path: Path) -> None:
    client, _sup, home = _offline_client(tmp_path)
    try:
        S.instance_dir(home, "alpha").mkdir(parents=True, exist_ok=True)
        assert client.delete("/api/instances/alpha/data").status_code == 204
        # Idempotent: a folder that is already gone is the state the caller asked for.
        assert client.delete("/api/instances/alpha/data").status_code == 204
        assert not S.instance_dir(home, "alpha").exists()
    finally:
        client.__exit__(None, None, None)


def test_deleting_data_for_an_unknown_or_malformed_name_is_404(tmp_path: Path) -> None:
    client, _sup, _home = _offline_client(tmp_path)
    try:
        assert client.delete("/api/instances/charlie/data").status_code == 404
        r = client.delete("/api/instances/bad.name/data")
        assert r.status_code == 404
        assert r.json() == {"detail": "unknown instance"}
    finally:
        client.__exit__(None, None, None)


def test_deleting_data_refuses_while_the_worker_is_alive(tmp_path: Path) -> None:
    world = FakeWorld()
    world.alive.add(4242)
    _heartbeat(tmp_path, "bravo", 4242, world.now)
    client, sup, home = make_client(tmp_path, ("alpha", "bravo"), world=world)
    try:
        assert next(v for v in sup.views() if v.name == "bravo").state == InstanceState.FARMING
        r = client.delete("/api/instances/bravo/data")
        assert r.status_code == 409
        assert r.json() == {"detail": "Stop bravo before deleting its data"}
        # Deleting the files a live worker is writing would leave it logging into nothing.
        assert (S.instance_dir(home, "bravo") / "status.json").exists()
    finally:
        client.__exit__(None, None, None)


def test_deleting_data_refuses_a_target_outside_the_data_folder(tmp_path, monkeypatch) -> None:
    client, _sup, _home = _offline_client(tmp_path)
    try:
        elsewhere = Path(tmp_path) / "elsewhere" / "alpha"
        elsewhere.mkdir(parents=True, exist_ok=True)
        # The folder name comes out of config.toml, so a resolved path that left
        # <home>/instances is a refusal rather than a delete, whatever put it there.
        monkeypatch.setattr(instances.S, "instance_dir", lambda home, name: elsewhere)
        r = client.delete("/api/instances/alpha/data")
        assert r.status_code == 400
        assert r.json() == {"detail": "refusing to delete outside the data folder"}
        assert elsewhere.exists()
    finally:
        client.__exit__(None, None, None)


def test_a_file_still_in_use_is_a_409_naming_the_instance(tmp_path, monkeypatch) -> None:
    client, _sup, home = _offline_client(tmp_path)
    try:
        S.instance_dir(home, "alpha").mkdir(parents=True, exist_ok=True)

        def locked(path):
            raise OSError("the process cannot access the file because it is being used")

        monkeypatch.setattr(instances.shutil, "rmtree", locked)
        r = client.delete("/api/instances/alpha/data")
        assert r.status_code == 409
        assert r.json() == {"detail": "could not delete alpha's data; a file is still in use"}
        assert S.instance_dir(home, "alpha").exists()
    finally:
        client.__exit__(None, None, None)
```

- [ ] **Step 3: Write the failing sticky-token test**

In `tests/test_supervisor_loop.py`, add `config` to the core import so it reads
`from brawlfarm.core import config, scheduler, status`, then append at the end of the file:

```python
def test_clearing_the_token_clears_the_applied_one(tmp_path, world, monkeypatch) -> None:
    monkeypatch.delenv("BRAWL_API_TOKEN", raising=False)
    sup = make_sup(tmp_path, world, ("Pie64",))
    assert config.API_TOKEN == "tok"  # _settings() sets one, and __init__ applied it

    sup.settings.connection.brawl_api_token = ""
    sup.apply_settings(sup.settings)
    # Blank means blank. Before this, the last non-blank token stuck for the life of the
    # process, so clearing it in Settings changed nothing until a restart.
    assert config.API_TOKEN == ""

    monkeypatch.setenv("BRAWL_API_TOKEN", "from-the-environment")
    sup.apply_settings(sup.settings)
    # The environment override the spec promises is still the fallback, not the leftover.
    assert config.API_TOKEN == "from-the-environment"
```

- [ ] **Step 4: Run the three modules to confirm they fail**

```bash
cd <repo>
uv run pytest tests/test_api_settings.py tests/test_api_instances.py tests/test_supervisor_loop.py -q
```

Expected: FAIL. The settings tests get 405 on `POST /api/settings/reset` and
`POST /api/settings/open-data-folder` (the path exists for PUT and GET, not POST); the
instance tests fail at `import InstanceState` only if it was forgotten, and otherwise get
405 on `DELETE /api/instances/alpha/data`; `test_a_file_still_in_use_is_a_409_naming_the_instance`
fails first with `AttributeError: module 'brawlfarm.api.instances' has no attribute 'shutil'`;
the supervisor test fails with `assert 'tok' == ''`.

- [ ] **Step 5: Move LIVE_STATES into deps**

In `brawlfarm/api/deps.py`, add the import and the constant. The import line becomes
`from brawlfarm.supervisor import Supervisor` plus a second line, and the constant sits
above `get_sup`:

```python
from brawlfarm.supervisor import Supervisor
from brawlfarm.supervisor.state import InstanceState

# States that mean a worker process is running, or is about to be. Two routers need it now:
# PUT /api/settings refuses to drop a live instance, and DELETE /api/instances/{name}/data
# refuses to empty a live instance's folder out from under it.
LIVE_STATES = frozenset(
    {
        InstanceState.FARMING,
        InstanceState.STARTING,
        InstanceState.STOPPING,
        InstanceState.RECONNECTING,
    }
)
```

In `brawlfarm/api/settings_routes.py`, delete the `LIVE_STATES` block and the
`from brawlfarm.supervisor.state import InstanceState` line, and take the constant from
`deps` instead:

```python
from brawlfarm.api.deps import LIVE_STATES, get_home, get_sup
```

`write_settings` is otherwise untouched: it still reads `view.state in LIVE_STATES`.

- [ ] **Step 6: Add the two settings routes**

Still in `brawlfarm/api/settings_routes.py`. The import block grows three standard-library
imports and `Response`:

```python
import asyncio
import os
import sys

from fastapi import APIRouter, HTTPException, Request, Response
```

Append both routes at the end of the file, after `write_settings`:

```python
@router.post("/api/settings/reset")
async def reset_settings(request: Request) -> dict:
    """Every section back to its model default, with the instances list carried over.

    A reset that also emptied the fleet would be a factory reset of somebody's farm, and it
    would orphan every data folder behind it. Because nothing is removed, the 409 that
    guards PUT cannot happen here, and no instance has to be stopped first.
    """
    sup = get_sup(request)
    new = S.AppSettings(instances=list(sup.settings.instances))
    S.save(new, get_home(request))
    sup.apply_settings(new)
    sup.poke()
    return new.model_dump(mode="json")


@router.post("/api/settings/open-data-folder", status_code=204)
async def open_data_folder(request: Request) -> Response:
    """Open the data directory in Explorer.

    Windows only, and the guard is on sys.platform rather than on a try around os.startfile,
    because that attribute does not exist anywhere else. startfile can block on a busy shell,
    so it goes through a thread. The path is never put in the answer: the panel shows it in
    one tooltip and nowhere else, and it is a Windows user path.
    """
    if sys.platform != "win32":
        raise HTTPException(status_code=501, detail="Only on Windows")
    try:
        await asyncio.to_thread(os.startfile, str(get_home(request)))
    except OSError as exc:
        raise HTTPException(status_code=500, detail="could not open the data folder") from exc
    return Response(status_code=204)
```

- [ ] **Step 7: Add the delete-data route**

In `brawlfarm/api/instances.py`, grow the imports: `import asyncio` and `import shutil` at
the top of the standard-library block, `Response` on the fastapi line, and `LIVE_STATES` on
the deps line:

```python
import asyncio
import csv
import shutil
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from brawlfarm import settings as S
from brawlfarm.api.deps import LIVE_STATES, get_home, get_sup, resolve_instance
```

Append the route at the end of the file, after `retry_instance`:

```python
@router.delete("/api/instances/{name}/data", status_code=204)
async def delete_instance_data(request: Request, name: str) -> Response:
    """Delete this instance's data folder: status.json, farmplan.json, the schedule,
    games.csv and every past session.

    The instance itself stays in config.toml. That is the mirror image of PUT /api/settings
    dropping a row and leaving the folder behind, and between them the user can remove
    either half without the other.

    Three guards, in order. resolve_instance answers 404 both for a name that is not
    configured and for one that could never be a folder. A live worker is a 409, because
    deleting the files it is writing would leave it logging into nothing. And the resolved
    target has to still sit under <home>/instances: the folder name comes out of
    config.toml, so a path that has left the data directory is a refusal, not a delete.
    A folder that is already gone is a 204, so a second click is not an error.
    """
    inst, _dir = resolve_instance(request, name)
    home = get_home(request)
    view = next((v for v in get_sup(request).views() if v.name == inst.name), None)
    if view is not None and view.state in LIVE_STATES:
        raise HTTPException(status_code=409, detail=f"Stop {inst.name} before deleting its data")
    target = S.instance_dir(home, inst.name).resolve()
    root = (Path(home) / "instances").resolve()
    if not target.is_relative_to(root):
        raise HTTPException(status_code=400, detail="refusing to delete outside the data folder")
    if not target.exists():
        return Response(status_code=204)
    try:
        await asyncio.to_thread(shutil.rmtree, target)
    except OSError as exc:
        raise HTTPException(
            status_code=409,
            detail=f"could not delete {inst.name}'s data; a file is still in use",
        ) from exc
    return Response(status_code=204)
```

- [ ] **Step 8: Fix the sticky token**

In `brawlfarm/supervisor/loop.py`, in `apply_settings`, replace line 87:

```python
        # Blank means blank: a token cleared in Settings has to clear the applied one, not
        # leave the last non-blank value in place for the life of the process. The
        # environment stays the developer override the spec promises.
        config.API_TOKEN = settings.connection.brawl_api_token or os.environ.get(
            "BRAWL_API_TOKEN", ""
        )
```

`os` is already imported at the top of the file.

- [ ] **Step 9: Run the three modules, then the whole suite**

```bash
uv run pytest tests/test_api_settings.py tests/test_api_instances.py tests/test_supervisor_loop.py -v
uv run pytest -q
```

Expected: the three modules green, `test_api_settings.py` five tests longer and
`test_api_instances.py` six longer. The whole suite is 617 tests (605 after task 3, plus 12)
with no warnings. If anything else fails, it imported `LIVE_STATES` from
`settings_routes`; `grep -rn "LIVE_STATES" brawlfarm tests` finds every user, and today only
`settings_routes.py` has one.

- [ ] **Step 10: Lint, scrub, commit**

```bash
uv run ruff format brawlfarm/api/deps.py brawlfarm/api/settings_routes.py brawlfarm/api/instances.py brawlfarm/supervisor/loop.py tests/test_api_settings.py tests/test_api_instances.py tests/test_supervisor_loop.py
uv run ruff check --fix brawlfarm tests
uv run ruff check . && uv run ruff format --check .
uv run python tools/scrub_check.py && git add brawlfarm/api tests/test_api_settings.py tests/test_api_instances.py tests/test_supervisor_loop.py brawlfarm/supervisor/loop.py && git commit -m "feat(api): reset settings, open the data folder, delete one instance's data

Three routes the Data section needs. Reset rebuilds AppSettings from its
model defaults and carries the instances list over untouched, so a reset
is not a factory reset of somebody's farm; nothing is removed, so no 409
is reachable. Open-data-folder is Windows only, guarded on sys.platform
rather than on a missing attribute, and the path never reaches the answer
because it is a Windows user path. Delete-data empties the folder and
leaves the instance in config.toml: 404 for an unknown name, 409 while a
worker is alive, 400 for a resolved target that is not under
<home>/instances, 409 when a file is still locked, and 204 for a folder
that is already gone.

LIVE_STATES moves to api/deps.py, because two routers now refuse a live
instance rather than one.

fix(supervisor): a blank Brawl Stars token now clears the applied one
instead of leaving the last non-blank value in place for the life of the
process; BRAWL_API_TOKEN stays the developer override.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CQ1GimQ3uiR2sXPzfZLNWV"
```

Expected: `All checks passed!`, every file already formatted, `0 hit(s)`, then the commit.

---

### Task 5: The settings shell, its nav, and Settings > Instances

The brief's task 3. `/settings` becomes a real screen: the shell routes split so the wizard
can escape them later, a second-level nav, the section frame with its save caption, and the
first and largest section.

The `/setup` route itself is not added here, because `Setup.tsx` does not exist until task 8.
What this task does is the structural half: `ShellRoutes` comes out of `Panel` as its own
component, so task 8 only has to put one `<Routes>` around it and one sibling route beside
it.

Accepted proposal ids covered: `set-nav`, `set-instances`, `set-remove-confirm`, `set-empty`.

**Files:**
- Create: `brawlfarm/web/src/api/setup.ts`
- Create: `brawlfarm/web/src/settings/SettingsNav.tsx`
- Create: `brawlfarm/web/src/settings/Settings.tsx`
- Create: `brawlfarm/web/src/settings/Instances.tsx`
- Modify: `brawlfarm/web/src/App.tsx` (`ShellRoutes` extracted; the two settings routes added)
- Modify: `brawlfarm/web/src/app/TopBar.tsx` (`pageTitle` answers "Settings" for every section)
- Modify: `brawlfarm/web/src/app/Rail.tsx` (Settings loses its "soon" tag)
- Test: `brawlfarm/web/src/settings/Settings.test.tsx` (create)
- Test: `brawlfarm/web/src/settings/Instances.test.tsx` (create)
- Test: `brawlfarm/web/src/app/Rail.test.tsx` (modify: one assertion)
- Test: `brawlfarm/web/src/app/TopBar.test.tsx` (modify: one assertion)
- Test: `brawlfarm/web/src/App.test.tsx` (modify: the settings stub, one renamed test, one new test)

**Interfaces:**
- Consumes: task 1's `Table`, `Field`, `ConfirmDialog`; task 2's `useSettingsPatch`,
  `fieldError`, `SettingsPatch`; the phase 4 `Button`, `Chip`, `StateChip`, `ErrorBlock`,
  `useInstances`, `plural`, `toast`, `ApiError`.
- Produces:
  - `api/setup.ts`: `scanSetup(adbPath?: string): Promise<ScanResponse>`,
    `testPort(port: number, adbPath?: string): Promise<PortTestResponse>`,
    `checkDisplay(port: number, adbPath?: string): Promise<DisplayCheckResponse>`
  - `settings/SettingsNav.tsx`: `SectionId` (the seven ids), `SettingsSection`,
    `SETTINGS_SECTIONS: readonly SettingsSection[]`, `SettingsNav`
  - `settings/Settings.tsx`: `Settings`, and the section-view contract every section
    implements: `(props: { settingsPatch: SettingsPatch }) => ReactElement`
  - `settings/Instances.tsx`: `Instances`
  - `App.tsx`: `ShellRoutes`, the component task 8 puts beside `/setup`
  - `TopBar.pageTitle(pathname)` answers `"Settings"` for any path under `/settings`
- Consumed by: tasks 6 and 7 (they add their sections to `SECTION_VIEWS`), tasks 8 and 9
  (`api/setup.ts`), task 10 (the `/setup` links).

- [ ] **Step 1: Write the failing tests for the frame**

Create `brawlfarm/web/src/settings/Settings.test.tsx`:

```tsx
/** The settings frame: seven sections in the nav, the one you are on marked, the title with
 * its one sentence, and a section id that is not one of the seven saying so instead of
 * quietly moving you somewhere else. */
import { screen, within } from "@testing-library/react";
import { Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Settings } from "./Settings";
import { makeInstance, makeSettings } from "../test/fixtures";
import { jsonResponse, stubFetch } from "../test/http";
import { renderWithProviders } from "../test/renderWithProviders";

function stubApi(): void {
  stubFetch((url) => {
    if (url === "/api/settings") return jsonResponse(makeSettings());
    if (url === "/api/instances") return jsonResponse({ instances: [makeInstance()] });
    throw new Error(`unstubbed request: ${url}`);
  });
}

function mount(route: string) {
  return renderWithProviders(
    <Routes>
      <Route path="/settings/:section" element={<Settings />} />
    </Routes>,
    { route },
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Settings", () => {
  it("lists the seven sections in order and marks the one you are on", async () => {
    stubApi();
    mount("/settings/instances");
    const nav = screen.getByRole("navigation", { name: "Settings sections" });
    expect(within(nav).getAllByRole("link").map((link) => link.textContent)).toEqual([
      "Instances",
      "Connection",
      "Behavior",
      "Schedule",
      "Notifications",
      "Data",
      "About",
    ]);
    expect(within(nav).getByRole("link", { name: "Instances" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(within(nav).getByRole("link", { name: "About" })).toHaveAttribute(
      "href",
      "/settings/about",
    );
    expect(await screen.findByRole("heading", { level: 2, name: "Instances" })).toBeInTheDocument();
    expect(screen.getByText("Which BlueStacks instances brawlfarm farms.")).toBeInTheDocument();
  });

  it("shows no saved caption until something has been saved", async () => {
    stubApi();
    mount("/settings/instances");
    expect(await screen.findByRole("heading", { level: 2, name: "Instances" })).toBeInTheDocument();
    expect(screen.queryByText(/^Saved \d\d:\d\d$/)).not.toBeInTheDocument();
  });

  it("says so when the section in the URL is not one of the seven", () => {
    stubApi();
    mount("/settings/nope");
    expect(screen.getByText("unknown settings section")).toBeInTheDocument();
    // It does not quietly move you somewhere else, so the nav is still there to choose from.
    expect(screen.getByRole("navigation", { name: "Settings sections" })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Write the failing tests for Instances**

Create `brawlfarm/web/src/settings/Instances.test.tsx`:

```tsx
/** Settings > Instances: the fleet as config.toml holds it, joined with the supervisor's
 * live view, edited in place, and refusing where the reader can see it. */
import { act, fireEvent, renderHook, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Settings } from "./Settings";
import type { AppSettings, ScanResponse } from "../api/types";
import { resetToasts, useToasts } from "../lib/toast";
import { makeInstance, makeSettings } from "../test/fixtures";
import { type FetchCall, jsonResponse, stubFetch } from "../test/http";
import { renderWithProviders } from "../test/renderWithProviders";

const FLEET = makeSettings({
  instances: [
    { name: "Pie64", adb_port: 5555, player_tag: "#2P0YLQ9" },
    { name: "Pie64_1", adb_port: 5565, player_tag: "" },
    { name: "Pie64_3", adb_port: 5585, player_tag: "" },
  ],
});

const NO_SCAN: ScanResponse = {
  adb_path: "C:/adb.exe",
  adb_found: true,
  conf_found: true,
  instances: [],
};

/** The settings route with a memory, the instances list, and the setup scan. Pie64_3 has no
 * view on purpose: the supervisor has not derived one for it yet. */
function server(
  options: { doc?: AppSettings; putStatus?: number; putDetail?: string; scan?: ScanResponse } = {},
) {
  let stored = options.doc ?? FLEET;
  const { calls } = stubFetch((url, init) => {
    if (url === "/api/instances") {
      return jsonResponse({
        instances: [
          makeInstance({ name: "Pie64", state: "farming" }),
          makeInstance({ name: "Pie64_1", adb_port: 5565, state: "offline", player_tag: "" }),
        ],
      });
    }
    if (url === "/api/setup/scan") return jsonResponse(options.scan ?? NO_SCAN);
    if (url !== "/api/settings") throw new Error(`unstubbed request: ${url}`);
    if (init?.method !== "PUT") return jsonResponse(stored);
    if (options.putStatus !== undefined) {
      return jsonResponse({ detail: options.putDetail }, options.putStatus);
    }
    stored = JSON.parse(String(init.body)) as AppSettings;
    return jsonResponse(stored);
  });
  return { calls, current: () => stored };
}

function mount() {
  return renderWithProviders(
    <Routes>
      <Route path="/settings/:section" element={<Settings />} />
    </Routes>,
    { route: "/settings/instances" },
  );
}

function puts(calls: FetchCall[]): AppSettings[] {
  return calls
    .filter((call) => call.url === "/api/settings" && call.init?.method === "PUT")
    .map((call) => JSON.parse(String(call.init?.body)) as AppSettings);
}

function toastMessages(): string[] {
  return renderHook(() => useToasts()).result.current.map((item) => item.message);
}

/** The data rows, header excluded. */
async function rows(): Promise<HTMLElement[]> {
  await screen.findByRole("row", { name: /instances\/Pie64_1/ });
  return screen.getAllByRole("row").slice(1);
}

afterEach(() => {
  resetToasts();
  vi.unstubAllGlobals();
});

describe("Settings > Instances", () => {
  it("shows every instance with its port, its tag, its folder and its status", async () => {
    server();
    mount();
    const [pie64, pie64_1, pie64_3] = await rows();

    const cells = within(pie64_1).getAllByRole("cell");
    expect(cells[0]).toHaveTextContent("Pie64_1");
    expect(cells[1]).toHaveTextContent("5565");
    // Relative to the home folder, never an absolute path: that path names a user.
    expect(cells[3]).toHaveTextContent("instances/Pie64_1");
    expect(within(pie64_1).getByText("Offline")).toBeInTheDocument();
    expect(within(pie64).getByText("Farming")).toBeInTheDocument();
    // The supervisor has no view for Pie64_3 yet, and an invented state would be a lie.
    expect(within(pie64_3).getByText("No status yet")).toBeInTheDocument();

    const tag = within(pie64).getByDisplayValue("#2P0YLQ9");
    expect(tag).toHaveAttribute("id", "instance-tag-Pie64");
    // The screenshot pass blurs it before the shot.
    expect(within(pie64).getAllByRole("cell")[2].querySelector("[data-private]")).not.toBeNull();
  });

  it("says what to do when there are no instances yet", async () => {
    server({ doc: makeSettings({ instances: [] }) });
    mount();
    expect(
      await screen.findByText("No instances yet. Add one or scan for BlueStacks."),
    ).toBeInTheDocument();
  });

  it("edits a row in place and saves all three fields", async () => {
    const { calls, current } = server();
    mount();
    const [, pie64_1] = await rows();
    await userEvent.click(within(pie64_1).getByRole("button", { name: "Edit" }));

    const form = screen.getAllByRole("row")[2];
    await userEvent.clear(within(form).getByLabelText("ADB port"));
    await userEvent.type(within(form).getByLabelText("ADB port"), "5575");
    await userEvent.type(within(form).getByLabelText("Player tag"), "2P0YLQ9");
    await userEvent.click(within(form).getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    expect(puts(calls)[0].instances[1]).toEqual({
      name: "Pie64_1",
      adb_port: 5575,
      player_tag: "2P0YLQ9", // the model puts the # back and upper-cases it
    });
    expect(current().instances[1].adb_port).toBe(5575);
    expect(toastMessages()).toEqual(["Settings saved"]);
    await waitFor(() => {
      expect(screen.queryByRole("button", { name: "Save" })).not.toBeInTheDocument();
    });
  });

  it("adds an instance through the same form, as a new last row", async () => {
    const { calls } = server();
    mount();
    await rows();
    await userEvent.click(screen.getByRole("button", { name: "Add instance" }));

    const form = screen.getAllByRole("row")[4];
    await userEvent.type(within(form).getByLabelText("Name"), "Pie64_5");
    await userEvent.type(within(form).getByLabelText("ADB port"), "5595");
    await userEvent.click(within(form).getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    expect(puts(calls)[0].instances).toHaveLength(4);
    expect(puts(calls)[0].instances[3]).toEqual({
      name: "Pie64_5",
      adb_port: 5595,
      player_tag: "",
    });
  });

  it("removes an instance only once its name is typed", async () => {
    const { calls } = server();
    mount();
    const [, , pie64_3] = await rows();
    await userEvent.click(within(pie64_3).getByRole("button", { name: "Remove" }));

    const dialog = screen.getByRole("dialog", { name: "Remove Pie64_3?" });
    expect(
      within(dialog).getByText("Its data folder stays on disk. Type the name to confirm."),
    ).toBeInTheDocument();
    const confirm = within(dialog).getByRole("button", { name: "Remove" });
    expect(confirm).toBeDisabled();
    await userEvent.type(within(dialog).getByLabelText("Type to confirm"), "Pie64_3");
    await userEvent.click(confirm);

    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    expect(puts(calls)[0].instances.map((inst) => inst.name)).toEqual(["Pie64", "Pie64_1"]);
    expect(toastMessages()).toEqual(["Settings saved"]);
  });

  it("shows the API's refusal in the row it names", async () => {
    server({ putStatus: 409, putDetail: "Stop Pie64_3 before removing it" });
    mount();
    const [, , pie64_3] = await rows();
    await userEvent.click(within(pie64_3).getByRole("button", { name: "Remove" }));
    const dialog = screen.getByRole("dialog", { name: "Remove Pie64_3?" });
    await userEvent.type(within(dialog).getByLabelText("Type to confirm"), "Pie64_3");
    await userEvent.click(within(dialog).getByRole("button", { name: "Remove" }));

    // The API's own sentence, in the row, not a toast that scrolls away.
    expect(await screen.findByText("Stop Pie64_3 before removing it")).toBeInTheDocument();
    expect(
      within(screen.getAllByRole("row")[3]).getByText("Stop Pie64_3 before removing it"),
    ).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(toastMessages()).toEqual([]);
  });

  it("puts a bad tag's message under the tag field", async () => {
    server({
      putStatus: 422,
      putDetail:
        "instances.1.player_tag: player tag must be # followed by letters from 0289PYLQGRJCUV",
    });
    mount();
    const [, pie64_1] = await rows();
    await userEvent.click(within(pie64_1).getByRole("button", { name: "Edit" }));
    const form = screen.getAllByRole("row")[2];
    await userEvent.type(within(form).getByLabelText("Player tag"), "nope");
    await userEvent.click(within(form).getByRole("button", { name: "Save" }));

    expect(
      await screen.findByText(
        "player_tag: player tag must be # followed by letters from 0289PYLQGRJCUV",
      ),
    ).toBeInTheDocument();
    // A validation message is not a refusal: nothing goes in the row's 409 line.
    expect(toastMessages()).toEqual([]);
  });

  it("adds what a scan found, and says so when it found nothing new", async () => {
    const first = server({
      scan: {
        ...NO_SCAN,
        instances: [
          // Already configured, so it is not offered again.
          {
            name: "Pie64",
            display_name: "Pie64",
            adb_port: 5555,
            width: 1600,
            height: 900,
            dpi: 240,
            online: true,
          },
          {
            name: "Pie64_5",
            display_name: "Pie 5",
            adb_port: 5595,
            width: 1600,
            height: 900,
            dpi: 240,
            online: true,
          },
        ],
      },
    });
    const view = mount();
    await rows();
    await userEvent.click(screen.getByRole("button", { name: "Scan again" }));
    await waitFor(() => {
      expect(puts(first.calls)).toHaveLength(1);
    });
    expect(puts(first.calls)[0].instances.map((inst) => inst.name)).toEqual([
      "Pie64",
      "Pie64_1",
      "Pie64_3",
      "Pie64_5",
    ]);
    expect(toastMessages()).toEqual(["Added 1 instance"]);
    view.unmount();
    resetToasts();
    vi.unstubAllGlobals();

    const second = server();
    mount();
    await rows();
    await userEvent.click(screen.getByRole("button", { name: "Scan again" }));
    await waitFor(() => {
      expect(toastMessages()).toEqual(["No new instances found"]);
    });
    expect(puts(second.calls)).toHaveLength(0);
  });
});

/** One keystroke on a controlled field. fireEvent rather than userEvent: userEvent awaits
 * testing-library's async wrapper, which drains the queue with a real setTimeout that fake
 * timers never run. */
function keystroke(field: HTMLElement, value: string): void {
  fireEvent.change(field, { target: { value } });
}

/** Move the fake clock on with React's own work inside act, so a debounce that fires and the
 * PUT it sends both settle before the next assertion. */
async function tick(ms: number): Promise<void> {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

describe("Settings > Instances tag debounce", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    resetToasts();
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("saves the tag 500 ms after the last keystroke, and at once on blur", async () => {
    const { calls } = server();
    mount();
    await tick(0); // the settings and instances fetches settle on the fake clock

    const tag = screen.getByLabelText("Player tag for Pie64_1");
    keystroke(tag, "2P0");
    keystroke(tag, "2P0Y");
    keystroke(tag, "2P0YLQ9");
    expect(puts(calls)).toHaveLength(0); // still typing
    await tick(499);
    expect(puts(calls)).toHaveLength(0);
    await tick(1);
    expect(puts(calls)).toHaveLength(1);
    expect(puts(calls)[0].instances[1].player_tag).toBe("2P0YLQ9");

    keystroke(tag, "2P0YLQ90");
    fireEvent.blur(tag);
    await tick(0);
    // Leaving the box does not wait out the rest of the debounce.
    expect(puts(calls)).toHaveLength(2);
    expect(puts(calls)[1].instances[1].player_tag).toBe("2P0YLQ90");
  });
});
```

Note the tag field's label: it is `Player tag for Pie64_1`, not the column header, because
three of them are on screen at once and a screen reader hearing "Player tag" three times
cannot tell them apart. The label is hidden in the cell, so nothing shows twice.

- [ ] **Step 3: Update the three existing test files**

In `brawlfarm/web/src/app/Rail.test.tsx`, in
`test "shows the wordmark and tags the sections that are not built yet"`, replace the
Settings assertion:

```tsx
    expect(screen.getByRole("link", { name: "Settings" })).toHaveAttribute("href", "/settings");
```

and rename the test to `"shows the wordmark and tags the one section that is not built yet"`.
The Stats assertion stays exactly as it is.

In `brawlfarm/web/src/app/TopBar.test.tsx`, add one line to
`test "names the three sections and uses the instance name on its own page"`:

```tsx
    expect(pageTitle("/settings/notifications")).toBe("Settings");
```

In `brawlfarm/web/src/App.test.tsx`, add `makeSettings` to the fixtures import and serve the
whole document from the settings stub:

```tsx
function stubApi(theme: "system" | "dark" | "light" = "system"): { calls: { url: string }[] } {
  return stubFetch((url) => {
    if (url === "/api/settings") {
      return jsonResponse(
        makeSettings({
          app: { port: 8765, theme },
          connection: { adb_path: "adb.exe", brawl_api_token: "never-render-me" },
        }),
      );
    }
    if (url === "/api/instances") return jsonResponse({ instances: [makeInstance()] });
    if (url === "/api/alerts") return jsonResponse({ alerts: [makeAlert()], unread: 1 });
    if (url.endsWith("preview.jpg")) return jpegResponse();
    throw new Error(`unstubbed request: ${url}`);
  });
}
```

Rename `it("renders the two placeholder pages with their copy", ...)` to
`it("renders the stats placeholder with its copy", ...)`; its body does not change. Append
one test to the `describe("App", ...)` block:

```tsx
  it("sends /settings to the first section and keeps one title across them", async () => {
    stubApi();
    window.history.pushState({}, "", "/settings");
    render(<App />);
    expect(await screen.findByRole("heading", { level: 2, name: "Instances" })).toBeInTheDocument();
    expect(window.location.pathname).toBe("/settings/instances");
    // Every section is one page as far as the top bar is concerned.
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Settings");
  });
```

- [ ] **Step 4: Run the five files to confirm they fail**

```bash
pnpm --dir brawlfarm/web test src/settings/Settings.test.tsx src/settings/Instances.test.tsx src/app/Rail.test.tsx src/app/TopBar.test.tsx src/App.test.tsx
```

Expected: FAIL. `Settings.test.tsx` and `Instances.test.tsx` fail to collect
(`Failed to resolve import "./Settings"`); `Rail.test.tsx` fails with
`Unable to find an accessible element with the role "link" and name "Settings"` because the
rail still renders "Settings soon"; `TopBar.test.tsx` fails with
`expected 'brawlfarm' to be 'Settings'`; `App.test.tsx`'s new case fails with
`Unable to find an accessible element with the role "heading" and name "Instances"`.

- [ ] **Step 5: Write the setup client**

Create `brawlfarm/web/src/api/setup.ts`:

```ts
/**
 * The three setup probes.
 *
 * Each one is a mutation with local state, never a cached query: a probe is a deliberate act
 * and takes seconds, and a stale cached scan would lie about what is plugged in right now.
 * The optional adbPath is the path the user typed, which the API prefers over the configured
 * one, so the wizard's field works before anything has reached config.toml.
 */
import { api } from "./client";
import type { DisplayCheckResponse, PortTestResponse, ScanResponse } from "./types";

/** The body's adb_path key is only sent when there is one: the route forbids extra keys and
 * treats a missing one as "use what is configured". */
function withPath(body: Record<string, number>, adbPath: string | undefined): string {
  return JSON.stringify(adbPath === undefined ? body : { ...body, adb_path: adbPath });
}

export function scanSetup(adbPath?: string): Promise<ScanResponse> {
  return api<ScanResponse>("/api/setup/scan", { method: "POST", body: withPath({}, adbPath) });
}

export function testPort(port: number, adbPath?: string): Promise<PortTestResponse> {
  return api<PortTestResponse>("/api/setup/test", {
    method: "POST",
    body: withPath({ adb_port: port }, adbPath),
  });
}

export function checkDisplay(port: number, adbPath?: string): Promise<DisplayCheckResponse> {
  return api<DisplayCheckResponse>("/api/setup/display-check", {
    method: "POST",
    body: withPath({ adb_port: port }, adbPath),
  });
}
```

- [ ] **Step 6: Write the nav and the frame**

Create `brawlfarm/web/src/settings/SettingsNav.tsx`:

```tsx
/**
 * The second-level nav, and the table that names the seven sections.
 *
 * The table lives here rather than in Settings.tsx so the nav and the section heading read
 * the same labels and the same sentences from one place, and so the import only ever points
 * one way. NavLink rather than Link, so the section you are on gets aria-current="page"
 * without this component tracking the route itself.
 *
 * Under 820 px the column becomes a horizontal row that scrolls, which is the same move the
 * shell rail makes at the same width.
 */
import { NavLink } from "react-router";

export type SectionId =
  | "instances"
  | "connection"
  | "behavior"
  | "schedule"
  | "notifications"
  | "data"
  | "about";

export interface SettingsSection {
  id: SectionId;
  label: string;
  description: string;
}

export const SETTINGS_SECTIONS: readonly SettingsSection[] = [
  {
    id: "instances",
    label: "Instances",
    description: "Which BlueStacks instances brawlfarm farms.",
  },
  {
    id: "connection",
    label: "Connection",
    description: "How brawlfarm reaches BlueStacks and the Brawl Stars API.",
  },
  { id: "behavior", label: "Behavior", description: "How a worker plays." },
  { id: "schedule", label: "Schedule", description: "The default for new instances." },
  { id: "notifications", label: "Notifications", description: "Where alerts go." },
  { id: "data", label: "Data", description: "Files on this machine." },
  { id: "about", label: "About", description: "Theme, version and links." },
];

function linkClass(isActive: boolean): string {
  return `block rounded-[6px] border-l-2 px-2 py-1.5 text-[13px] whitespace-nowrap transition-colors duration-[120ms] ${
    isActive ? "border-accent bg-panel-2 text-text" : "border-transparent text-muted hover:text-text"
  }`;
}

export function SettingsNav() {
  return (
    <nav aria-label="Settings sections" className="shrink-0 min-[820px]:w-[200px]">
      <ul className="flex gap-1 overflow-x-auto min-[820px]:block min-[820px]:space-y-0.5">
        {SETTINGS_SECTIONS.map((section) => (
          <li key={section.id}>
            <NavLink to={`/settings/${section.id}`} className={({ isActive }) => linkClass(isActive)}>
              {section.label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
```

Create `brawlfarm/web/src/settings/Settings.tsx`:

```tsx
/**
 * The settings screen's frame.
 *
 * One route, /settings/:section: the second-level nav, then the section's title, the caption
 * saying when it last saved, its one plain sentence, anything the 422 mapper could not place
 * under a field, and the section itself. A section id that is not in the table is an
 * ErrorBlock rather than a redirect, because a mistyped URL that quietly moves you somewhere
 * else is how you end up changing the wrong setting.
 *
 * useSettingsPatch is called once here and handed down, so the caption, the field errors and
 * the write queue are the same ones the section on screen is using.
 */
import type { ReactElement } from "react";
import { useParams } from "react-router";

import { Instances } from "./Instances";
import { SETTINGS_SECTIONS, type SectionId, SettingsNav } from "./SettingsNav";
import { type SettingsPatch, useSettingsPatch } from "./useSettingsPatch";
import { ErrorBlock } from "../components/ui/ErrorBlock";

/** Every section takes the same one prop, so the table below can hold all seven. */
type SectionView = (props: { settingsPatch: SettingsPatch }) => ReactElement;

/** Partial while this branch is being built: tasks 6 and 7 fill the other six in, and the
 * last of them makes this a total Record so the compiler proves none is missing. */
const SECTION_VIEWS: Partial<Record<SectionId, SectionView>> = {
  instances: Instances,
};

const UNKNOWN_SECTION = new Error("unknown settings section");

export function Settings() {
  const { section } = useParams();
  const settingsPatch = useSettingsPatch();
  const known = SETTINGS_SECTIONS.find((entry) => entry.id === section);
  const View = known === undefined ? undefined : SECTION_VIEWS[known.id];

  return (
    <section className="flex flex-col gap-4 min-[820px]:flex-row">
      <SettingsNav />
      <div className="min-w-0 flex-1">
        {known === undefined ? (
          <ErrorBlock error={UNKNOWN_SECTION} />
        ) : (
          <>
            {/* An h2: the top bar already carries this page's h1, and it says Settings for
                every one of the seven. */}
            <header className="flex items-baseline gap-2">
              <h2 className="text-[20px] font-semibold tracking-tight">{known.label}</h2>
              {settingsPatch.savedAt !== null && (
                <span className="text-[11px] text-muted">{`Saved ${settingsPatch.savedAt}`}</span>
              )}
            </header>
            <p className="mt-1 text-[13px] text-muted">{known.description}</p>
            {settingsPatch.sectionErrors.map((line) => (
              <p key={line} className="mt-1 text-[12px] text-bad">
                {line}
              </p>
            ))}
            <div className="mt-4">
              {View === undefined ? null : <View settingsPatch={settingsPatch} />}
            </div>
          </>
        )}
      </div>
    </section>
  );
}
```

- [ ] **Step 7: Write the Instances section**

Create `brawlfarm/web/src/settings/Instances.tsx`:

```tsx
/**
 * Settings > Instances: the fleet as config.toml holds it.
 *
 * The table joins two sources on the name. settings.instances is what is on disk and what
 * this screen edits; useInstances() is the supervisor's live view, which an instance it has
 * not derived yet simply does not have, so that row says "No status yet" rather than
 * inventing a state.
 *
 * The player tag is editable in place, on a 500 ms debounce and at once on blur, because a
 * tag is the one field people come here to fix and opening an edit row for it is three
 * clicks too many. Everything else goes through the inline form, and Add opens the same form
 * as a new last row.
 *
 * A refusal is shown where it happened: a 409 is the API's own sentence in the row it names,
 * until the next save succeeds, and a 422 is already under its field through the mapper in
 * useSettingsPatch. Anything else is the section's ErrorBlock.
 */
import { useEffect, useRef, useState } from "react";

import { type SettingsPatch, fieldError } from "./useSettingsPatch";
import { ApiError } from "../api/client";
import { scanSetup } from "../api/setup";
import type { ScanInstance } from "../api/types";
import { useInstances } from "../api/useInstances";
import { Button } from "../components/ui/Button";
import { Chip } from "../components/ui/Chip";
import { ConfirmDialog } from "../components/ui/ConfirmDialog";
import { ErrorBlock } from "../components/ui/ErrorBlock";
import { Field } from "../components/ui/Field";
import { StateChip } from "../components/ui/StateChip";
import { type Column, Table } from "../components/ui/Table";
import { plural } from "../lib/format";
import { toast } from "../lib/toast";

/** The key of the row that does not exist yet. An instance name can never be empty. */
const NEW_ROW = "";
const DEBOUNCE_MS = 500;

interface Row {
  name: string;
}

interface Draft {
  name: string;
  adb_port: string;
  player_tag: string;
}

const BLANK: Draft = { name: "", adb_port: "", player_tag: "" };

export function Instances({ settingsPatch }: { settingsPatch: SettingsPatch }) {
  const { settings, patch, fieldErrors } = settingsPatch;
  const { data: views } = useInstances();
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState<Draft>(BLANK);
  const [rowErrors, setRowErrors] = useState<Record<string, string>>({});
  const [removing, setRemoving] = useState<string | null>(null);
  const [scanning, setScanning] = useState(false);
  const [failure, setFailure] = useState<unknown>(null);
  const [tagText, setTagText] = useState<Record<string, string>>({});
  const timers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  // A navigation away must not let a debounce fire a write into a screen that is gone.
  useEffect(() => {
    const pending = timers.current;
    return () => {
      for (const timer of Object.values(pending)) clearTimeout(timer);
    };
  }, []);

  const instances = settings?.instances ?? [];
  const rows: Row[] = [
    ...instances.map((inst) => ({ name: inst.name })),
    ...(editing === NEW_ROW ? [{ name: NEW_ROW }] : []),
  ];

  const succeeded = () => {
    setRowErrors({});
    setFailure(null);
    toast("Settings saved");
  };

  const failed = (key: string, error: unknown) => {
    if (error instanceof ApiError && error.status === 422) return; // already under its field
    if (error instanceof ApiError && error.status === 409) {
      setRowErrors((errors) => ({ ...errors, [key]: error.detail }));
      return;
    }
    setFailure(error);
  };

  const saveTag = (name: string, value: string) => {
    delete timers.current[name];
    void patch((document) => {
      const row = document.instances.find((inst) => inst.name === name);
      if (row !== undefined) row.player_tag = value;
    })
      .then(() => {
        succeeded();
        // The model upper-cases the tag and puts the # back, so the box goes back to showing
        // what is on disk rather than what was typed into it.
        setTagText((text) => {
          const next = { ...text };
          delete next[name];
          return next;
        });
      })
      .catch((error: unknown) => failed(name, error));
  };

  const onTagChange = (name: string, next: string) => {
    setTagText((text) => ({ ...text, [name]: next }));
    const running = timers.current[name];
    if (running !== undefined) clearTimeout(running);
    timers.current[name] = setTimeout(() => saveTag(name, next), DEBOUNCE_MS);
  };

  const onTagBlur = (name: string) => {
    const running = timers.current[name];
    if (running === undefined) return; // nothing was typed, so there is nothing to flush
    clearTimeout(running);
    saveTag(name, tagText[name] ?? "");
  };

  const startEdit = (name: string) => {
    const inst = instances.find((row) => row.name === name);
    setEditing(name);
    setDraft(
      inst === undefined
        ? BLANK
        : { name: inst.name, adb_port: String(inst.adb_port), player_tag: inst.player_tag },
    );
  };

  const cancelEdit = () => {
    setEditing(null);
    setDraft(BLANK);
  };

  const saveRow = () => {
    const original = editing;
    if (original === null) return;
    const port = Number(draft.adb_port);
    void patch((document) => {
      const row = {
        name: draft.name.trim(),
        // A blank or unparseable port goes as 0, which the API answers with a 422 naming
        // adb_port: the model is the validator here, not this form.
        adb_port: Number.isFinite(port) ? port : 0,
        player_tag: draft.player_tag.trim(),
      };
      const at = document.instances.findIndex((inst) => inst.name === original);
      if (at < 0) document.instances.push(row);
      else document.instances[at] = row;
    })
      .then(() => {
        succeeded();
        cancelEdit();
      })
      .catch((error: unknown) => failed(original, error));
  };

  const removeRow = (name: string) => {
    void patch((document) => {
      document.instances = document.instances.filter((inst) => inst.name !== name);
    })
      .then(() => {
        succeeded();
        setRemoving(null);
      })
      .catch((error: unknown) => {
        // The dialog closes either way: a refusal belongs in the row, in front of the reader.
        setRemoving(null);
        failed(name, error);
      });
  };

  const scanAgain = () => {
    setScanning(true);
    const known = new Set(instances.map((inst) => inst.name));
    void scanSetup()
      .then((scan) => {
        const found = scan.instances.filter(
          (row): row is ScanInstance & { adb_port: number } =>
            row.adb_port !== null && !known.has(row.name),
        );
        if (found.length === 0) {
          toast("No new instances found");
          return;
        }
        return patch((document) => {
          for (const row of found) {
            document.instances.push({ name: row.name, adb_port: row.adb_port, player_tag: "" });
          }
        }).then(() => {
          setRowErrors({});
          setFailure(null);
          toast(`Added ${plural(found.length, "instance")}`);
        });
      })
      .catch((error: unknown) => setFailure(error))
      .finally(() => setScanning(false));
  };

  const isEditing = (row: Row) => editing === row.name;
  /** The label is hidden in the cell, so it names the row rather than repeating the column:
   * three boxes called "Player tag" are three boxes a screen reader cannot tell apart. */
  const tagLabel = (name: string) => `Player tag for ${name}`;

  const columns: readonly Column<Row>[] = [
    {
      key: "name",
      label: "Name",
      mono: true,
      render: (row) => (
        <div>
          {isEditing(row) ? (
            <span className="[&_label]:sr-only">
              <Field
                label="Name"
                id={`instance-name-${row.name}`}
                value={draft.name}
                onChange={(value) => setDraft((current) => ({ ...current, name: value }))}
                width="full"
              />
            </span>
          ) : (
            row.name
          )}
          {rowErrors[row.name] !== undefined && (
            <p className="mt-1 font-sans text-[12px] whitespace-normal text-bad">
              {rowErrors[row.name]}
            </p>
          )}
        </div>
      ),
    },
    {
      key: "adb_port",
      label: "ADB port",
      mono: true,
      width: "140px",
      render: (row) =>
        isEditing(row) ? (
          <span className="[&_label]:sr-only">
            <Field
              label="ADB port"
              id={`instance-port-${row.name}`}
              value={draft.adb_port}
              onChange={(value) => setDraft((current) => ({ ...current, adb_port: value }))}
              type="number"
              width="full"
            />
          </span>
        ) : (
          String(instances.find((inst) => inst.name === row.name)?.adb_port ?? "")
        ),
    },
    {
      key: "player_tag",
      label: "Player tag",
      mono: true,
      width: "180px",
      render: (row) => {
        if (isEditing(row)) {
          return (
            <span data-private className="[&_label]:sr-only">
              <Field
                label="Player tag"
                id={`instance-draft-tag-${row.name}`}
                value={draft.player_tag}
                onChange={(value) => setDraft((current) => ({ ...current, player_tag: value }))}
                width="full"
              />
            </span>
          );
        }
        const at = instances.findIndex((inst) => inst.name === row.name);
        const stored = instances[at]?.player_tag ?? "";
        const message = fieldError(fieldErrors, `instances.${at}.player_tag`);
        return (
          <div onBlur={() => onTagBlur(row.name)}>
            <span data-private className="[&_label]:sr-only">
              <Field
                label={tagLabel(row.name)}
                id={`instance-tag-${row.name}`}
                value={tagText[row.name] ?? stored}
                onChange={(value) => onTagChange(row.name, value)}
                placeholder="#TAG"
                width="full"
              />
            </span>
            {message !== undefined && (
              <p className="mt-1 font-sans text-[12px] whitespace-normal text-bad">{message}</p>
            )}
          </div>
        );
      },
    },
    {
      key: "folder",
      label: "Data folder",
      mono: true,
      render: (row) =>
        row.name === NEW_ROW ? null : (
          // Relative to the home directory: an absolute path here would name a Windows user.
          <span className="text-muted">{`instances/${row.name}`}</span>
        ),
    },
    {
      key: "status",
      label: "Status",
      render: (row) => {
        if (row.name === NEW_ROW) return null;
        const view = (views ?? []).find((entry) => entry.name === row.name);
        return view === undefined ? (
          <Chip tone="idle">No status yet</Chip>
        ) : (
          <StateChip state={view.state} />
        );
      },
    },
    {
      key: "actions",
      label: "",
      render: (row) =>
        isEditing(row) ? (
          <div className="flex items-center gap-2">
            <Button variant="primary" size="sm" onClick={saveRow}>
              Save
            </Button>
            <Button variant="text" size="sm" onClick={cancelEdit}>
              Cancel
            </Button>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <Button variant="text" size="sm" onClick={() => startEdit(row.name)}>
              Edit
            </Button>
            <Button variant="text" size="sm" onClick={() => setRemoving(row.name)}>
              Remove
            </Button>
          </div>
        ),
    },
  ];

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Button variant="primary" size="sm" onClick={() => startEdit(NEW_ROW)}>
          Add instance
        </Button>
        <Button
          variant="quiet"
          size="sm"
          disabled={scanning}
          disabledReason="Scanning"
          onClick={scanAgain}
        >
          Scan again
        </Button>
      </div>

      {failure !== null && <ErrorBlock error={failure} />}

      <Table
        columns={columns}
        rows={rows}
        rowKey={(row) => row.name}
        empty="No instances yet. Add one or scan for BlueStacks."
      />

      <ConfirmDialog
        open={removing !== null}
        onClose={() => setRemoving(null)}
        title={`Remove ${removing ?? ""}?`}
        body="Its data folder stays on disk. Type the name to confirm."
        word={removing ?? ""}
        confirmLabel="Remove"
        tone="bad"
        onConfirm={() => {
          if (removing !== null) removeRow(removing);
        }}
      />
    </div>
  );
}
```

- [ ] **Step 8: Split the routes and retitle the page**

In `brawlfarm/web/src/App.tsx`, add `Navigate` to the react-router import and `Settings` to
the imports, then replace `Panel` with these two components:

```tsx
/** Everything that lives inside the shell. Task 8 puts the wizard's route beside it, which
 * is the only reason it is a component of its own rather than the body of Panel. */
function ShellRoutes() {
  return (
    <Shell>
      <Routes>
        <Route path="/" element={<Fleet />} />
        <Route path="/instances/:name" element={<Instance />} />
        <Route path="/stats" element={<Placeholder title="Stats" body="Stats arrive in phase 6." />} />
        <Route path="/settings" element={<Navigate to="/settings/instances" replace />} />
        <Route path="/settings/:section" element={<Settings />} />
      </Routes>
    </Shell>
  );
}

function Panel() {
  useThemeBootstrap();
  useLiveHandlers();

  return <ShellRoutes />;
}
```

The `Placeholder` import stays: Stats still uses it. The `/settings` placeholder is gone.

In `brawlfarm/web/src/app/TopBar.tsx`, replace `pageTitle`:

```tsx
export function pageTitle(pathname: string): string {
  if (pathname.startsWith(INSTANCE_PREFIX)) return pathname.slice(INSTANCE_PREFIX.length);
  // One title for all seven sections: /settings/data is still the Settings page.
  if (pathname.startsWith("/settings")) return "Settings";
  return SECTION_TITLES[pathname] ?? "brawlfarm";
}
```

`SECTION_TITLES` is not edited: its `/settings` entry is now unreachable and harmless, and
leaving it means one fewer file to re-read when Stats arrives.

In `brawlfarm/web/src/app/Rail.tsx`, the Settings entry loses its tag:

```tsx
const SECTIONS: { to: string; label: string; soon: boolean }[] = [
  { to: "/", label: "Fleet", soon: false },
  { to: "/stats", label: "Stats", soon: true },
  { to: "/settings", label: "Settings", soon: false },
];
```

Nothing else in `Rail.tsx` changes: `NavLink` has no `end` for `/settings`, so the rail entry
stays active across every section.

- [ ] **Step 9: Run the five files, then everything**

```bash
pnpm --dir brawlfarm/web test src/settings/Settings.test.tsx src/settings/Instances.test.tsx src/app/Rail.test.tsx src/app/TopBar.test.tsx src/App.test.tsx
pnpm --dir brawlfarm/web typecheck
pnpm --dir brawlfarm/web test
pnpm --dir brawlfarm/web build
```

Expected: `Settings.test.tsx` at 3, `Instances.test.tsx` at 9, `Rail.test.tsx` at 3,
`TopBar.test.tsx` at 4 and `App.test.tsx` at 8, all passing. `tsc --noEmit` prints nothing.
The whole suite is 41 files and 323 tests (39 and 310 after task 2). `vite build` writes
`brawlfarm/web/dist/index.html`.

- [ ] **Step 10: Look at it**

```bash
pnpm --dir brawlfarm/web build
uv run brawlfarm --no-browser
```

Open `http://127.0.0.1:8765/settings` and confirm: it lands on Instances, the top bar says
Settings, the rail's Settings entry has no "soon" and stays highlighted when you click
About, the table shows every instance with `instances/<name>` and a state chip, and typing
into a tag saves it with a "Settings saved" toast and a "Saved HH:MM" caption beside the
title.

- [ ] **Step 11: Commit**

```bash
uv run python tools/scrub_check.py && git add brawlfarm/web/src && git commit -m "feat(web): the settings screen, its nav, and the instances table

/settings redirects to its first section and /settings/:section renders
the rest; a section id that is not one of the seven says so instead of
redirecting, because a mistyped URL that quietly moves you is how you
change the wrong setting. The frame calls useSettingsPatch once and hands
it down, so the Saved HH:MM caption, the field errors and the write queue
are the ones the section is using. The rail's Settings entry loses its
soon tag and the top bar answers Settings for every section.

Instances joins config.toml with the supervisor's live view on the name,
shows the data folder relative to the home directory, and edits in place:
the player tag saves on a 500 ms debounce and at once on blur, everything
else goes through the inline form, Add opens that form as a new last row,
Remove needs the name typed out, and Scan again appends whatever the scan
found that is not configured yet. A 409 is the API's own sentence in the
row it names.

ShellRoutes comes out of Panel so task 8 can put the wizard beside it.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CQ1GimQ3uiR2sXPzfZLNWV"
```

Expected: `0 hit(s)`, then the commit.

---

### Task 6: Settings > Connection, Behavior, Schedule and About

The brief's task 4. Four sections, every one of them a stack of `SettingRow`s writing through
`useSettingsPatch`. No Save buttons anywhere: a switch writes on change, a text field writes
500 ms after the last keystroke and at once on blur.

Accepted proposal ids covered: `set-connection`, `set-behavior`, `set-schedule`, `set-about`.

**Files:**
- Create: `brawlfarm/web/src/api/health.ts`
- Modify: `brawlfarm/web/src/api/queries.ts` (add `health`)
- Create: `brawlfarm/web/src/settings/Connection.tsx`
- Create: `brawlfarm/web/src/settings/Behavior.tsx`
- Create: `brawlfarm/web/src/settings/Schedule.tsx`
- Create: `brawlfarm/web/src/settings/About.tsx`
- Modify: `brawlfarm/web/src/settings/Settings.tsx` (four entries in `SECTION_VIEWS`)
- Test: `brawlfarm/web/src/settings/Connection.test.tsx` (create)
- Test: `brawlfarm/web/src/settings/Behavior.test.tsx` (create)
- Test: `brawlfarm/web/src/settings/Schedule.test.tsx` (create)
- Test: `brawlfarm/web/src/settings/About.test.tsx` (create)

**Interfaces:**
- Consumes: task 1's `SettingRow` and `Field`; task 2's `useSettingsPatch`, `saveSetting`,
  `fieldError`, `useDebouncedSave`; task 5's `scanSetup` and the `SECTION_VIEWS` table; the
  phase 4 `Button`, `Chip`, `Switch`, `ErrorBlock`.
- Produces:
  - `api/health.ts`: `getHealth(): Promise<HealthResponse>`
  - `api/queries.ts`: `queryKeys.health: () => ["health"] as const`
  - `settings/Connection.tsx`: `Connection`
  - `settings/Behavior.tsx`: `Behavior`
  - `settings/Schedule.tsx`: `Schedule`
  - `settings/About.tsx`: `About`
- Consumed by: task 7 (`getHealth` again, for the Data section's tooltip; the same
  `queryKeys.health()` so one request serves both), task 11 (the keyboard pass over the
  theme radiogroup).

- [ ] **Step 1: Write the failing tests**

Create `brawlfarm/web/src/settings/Connection.test.tsx`:

```tsx
/** Settings > Connection: the adb path with the chip from one scan, and the masked token. */
import { fireEvent, renderHook, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Settings } from "./Settings";
import type { AppSettings, ScanResponse } from "../api/types";
import { resetToasts, useToasts } from "../lib/toast";
import { makeSettings } from "../test/fixtures";
import { type FetchCall, jsonResponse, stubFetch } from "../test/http";
import { renderWithProviders } from "../test/renderWithProviders";

const FOUND: ScanResponse = {
  adb_path: "C:\\Program Files\\BlueStacks_nxt\\HD-Adb.exe",
  adb_found: true,
  conf_found: true,
  instances: [],
};

function server(
  options: { scan?: ScanResponse; putStatus?: number; putDetail?: string } = {},
) {
  let stored = makeSettings();
  const { calls } = stubFetch((url, init) => {
    if (url === "/api/setup/scan") return jsonResponse(options.scan ?? FOUND);
    if (url !== "/api/settings") throw new Error(`unstubbed request: ${url}`);
    if (init?.method !== "PUT") return jsonResponse(stored);
    if (options.putStatus !== undefined) {
      return jsonResponse({ detail: options.putDetail }, options.putStatus);
    }
    stored = JSON.parse(String(init.body)) as AppSettings;
    return jsonResponse(stored);
  });
  return { calls, current: () => stored };
}

function mount() {
  return renderWithProviders(
    <Routes>
      <Route path="/settings/:section" element={<Settings />} />
    </Routes>,
    { route: "/settings/connection" },
  );
}

function puts(calls: FetchCall[]): AppSettings[] {
  return calls
    .filter((call) => call.url === "/api/settings" && call.init?.method === "PUT")
    .map((call) => JSON.parse(String(call.init?.body)) as AppSettings);
}

function toastMessages(): string[] {
  return renderHook(() => useToasts()).result.current.map((item) => item.message);
}

afterEach(() => {
  resetToasts();
  vi.unstubAllGlobals();
});

describe("Settings > Connection", () => {
  it("chips what one scan found and saves the adb path on blur", async () => {
    const { calls, current } = server();
    mount();
    const box = await screen.findByLabelText("ADB path");
    expect(await screen.findByText("Found")).toBeInTheDocument();
    expect(
      screen.getByText("brawlfarm needs HD-Adb.exe from the BlueStacks folder."),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Run setup again" })).toHaveAttribute(
      "href",
      "/setup",
    );
    expect(screen.getByText("Applies to a worker the next time it starts.")).toBeInTheDocument();

    fireEvent.change(box, { target: { value: "D:/portable/adb.exe" } });
    fireEvent.blur(box);
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    expect(puts(calls)[0].connection.adb_path).toBe("D:/portable/adb.exe");
    expect(current().connection.adb_path).toBe("D:/portable/adb.exe");
    expect(toastMessages()).toEqual(["Settings saved"]);
    // The scan runs once when the section mounts, never again per keystroke: it shells out
    // to adb and can take seconds.
    expect(calls.filter((call) => call.url === "/api/setup/scan")).toHaveLength(1);
  });

  it("says Not found when the scan came back without adb", async () => {
    server({ scan: { adb_path: null, adb_found: false, conf_found: false, instances: [] } });
    mount();
    expect(await screen.findByText("Not found")).toBeInTheDocument();
    expect(screen.queryByText("Found")).not.toBeInTheDocument();
  });

  it("puts the API's message under the ADB path row", async () => {
    const { calls } = server({ putStatus: 422, putDetail: "connection.adb_path: file not found" });
    mount();
    const box = await screen.findByLabelText("ADB path");
    fireEvent.change(box, { target: { value: "D:/nope.exe" } });
    fireEvent.blur(box);
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    expect(await screen.findByText("adb_path: file not found")).toBeInTheDocument();
    // The box keeps what is being fixed rather than snapping back under the reader.
    expect(box).toHaveValue("D:/nope.exe");
    expect(toastMessages()).toEqual([]);
  });

  it("masks the token, offers Show, and saves it on blur", async () => {
    const { calls } = server();
    mount();
    const token = await screen.findByLabelText("Brawl Stars API token");
    expect(token).toHaveAttribute("type", "password");
    expect(token).toHaveAttribute("data-private");
    expect(
      screen.getByText(
        "Create a key at developer.brawlstars.com and allow this machine's IP address.",
      ),
    ).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Show" }));
    expect(token).toHaveAttribute("type", "text");

    fireEvent.change(token, { target: { value: "a-token-that-is-not-real" } });
    fireEvent.blur(token);
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    expect(puts(calls)[0].connection.brawl_api_token).toBe("a-token-that-is-not-real");
  });
});
```

Create `brawlfarm/web/src/settings/Behavior.test.tsx`:

```tsx
/** Settings > Behavior: six plain switches, seven more behind Advanced, and every one of
 * them writing its own field. */
import { renderHook, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Settings } from "./Settings";
import type { AppSettings } from "../api/types";
import { resetToasts, useToasts } from "../lib/toast";
import { makeSettings } from "../test/fixtures";
import { type FetchCall, jsonResponse, stubFetch } from "../test/http";
import { renderWithProviders } from "../test/renderWithProviders";

function server(options: { putStatus?: number; putDetail?: string } = {}) {
  let stored = makeSettings();
  const { calls } = stubFetch((url, init) => {
    if (url !== "/api/settings") throw new Error(`unstubbed request: ${url}`);
    if (init?.method !== "PUT") return jsonResponse(stored);
    if (options.putStatus !== undefined) {
      return jsonResponse({ detail: options.putDetail }, options.putStatus);
    }
    stored = JSON.parse(String(init.body)) as AppSettings;
    return jsonResponse(stored);
  });
  return { calls, current: () => stored };
}

function mount() {
  return renderWithProviders(
    <Routes>
      <Route path="/settings/:section" element={<Settings />} />
    </Routes>,
    { route: "/settings/behavior" },
  );
}

function puts(calls: FetchCall[]): AppSettings[] {
  return calls
    .filter((call) => call.init?.method === "PUT")
    .map((call) => JSON.parse(String(call.init?.body)) as AppSettings);
}

function toastMessages(): string[] {
  return renderHook(() => useToasts()).result.current.map((item) => item.message);
}

afterEach(() => {
  resetToasts();
  vi.unstubAllGlobals();
});

describe("Settings > Behavior", () => {
  it("shows the six rows with one plain sentence each, and writes the one that is flipped", async () => {
    const { calls, current } = server();
    mount();
    expect(await screen.findByRole("switch", { name: "Win-rate aware" })).toBeInTheDocument();
    expect(screen.getAllByRole("switch")).toHaveLength(6); // Advanced is still collapsed
    for (const [name, sentence] of [
      ["Win-rate aware", "Prefer brawlers that win more in the current step."],
      ["Opportunity cost", "Skip brawlers whose next tier is far off."],
      ["Gas aware", "Move away from the gas earlier."],
      ["Bush hide", "Hide in bushes when the map allows."],
      ["Close game on stop", "Close Brawl Stars when the worker stops."],
      ["DND at start", "Turn on Do Not Disturb when the worker starts."],
    ]) {
      expect(screen.getByRole("switch", { name })).toBeInTheDocument();
      expect(screen.getByText(sentence)).toBeInTheDocument();
    }
    expect(screen.getByText("Applies to a worker the next time it starts.")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("switch", { name: "Gas aware" }));
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    expect(puts(calls)[0].behavior.gas_aware).toBe(false);
    // Only that one field moved: the whole document went, unchanged everywhere else.
    expect(puts(calls)[0].behavior.winrate_aware).toBe(true);
    expect(puts(calls)[0].advanced).toEqual(makeSettings().advanced);
    expect(current().behavior.gas_aware).toBe(false);
    expect(toastMessages()).toEqual(["Settings saved"]);
  });

  it("keeps the seven advanced switches behind Show, and writes the advanced section", async () => {
    const { calls } = server();
    mount();
    expect(await screen.findByRole("switch", { name: "Win-rate aware" })).toBeInTheDocument();
    expect(screen.getByText("Advanced")).toBeInTheDocument();
    expect(screen.queryByRole("switch", { name: "Fast input" })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Show" }));
    expect(screen.getAllByRole("switch")).toHaveLength(13);
    for (const [name, sentence] of [
      ["Fast input", "Send taps through the faster adb path."],
      ["Raw capture", "Read frames without re-encoding them."],
      ["Gray matching", "Match templates in grayscale."],
      ["Phase classify", "Work out the match phase from the screen."],
      ["Ability buttons", "Use the gadget and super buttons."],
      ["Recalibration tripwire", "Warn when a detector looks season-blind."],
      ["DND off on stop", "Turn Do Not Disturb back off when the worker stops."],
    ]) {
      expect(screen.getByRole("switch", { name })).toBeInTheDocument();
      expect(screen.getByText(sentence)).toBeInTheDocument();
    }

    await userEvent.click(screen.getByRole("switch", { name: "Gray matching" }));
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    expect(puts(calls)[0].advanced.gray_match).toBe(false);

    await userEvent.click(screen.getByRole("button", { name: "Hide" }));
    expect(screen.queryByRole("switch", { name: "Gray matching" })).not.toBeInTheDocument();
  });

  it("puts the API's message under the row it named", async () => {
    const { calls } = server({
      putStatus: 422,
      putDetail: "behavior.bush_hide: Input should be a valid boolean",
    });
    mount();
    expect(await screen.findByRole("switch", { name: "Bush hide" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("switch", { name: "Bush hide" }));
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    expect(
      await screen.findByText("bush_hide: Input should be a valid boolean"),
    ).toBeInTheDocument();
    expect(toastMessages()).toEqual([]);
  });
});
```

Create `brawlfarm/web/src/settings/Schedule.test.tsx`:

```tsx
/** Settings > Schedule: one switch, and what it writes. */
import { renderHook, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Settings } from "./Settings";
import type { AppSettings } from "../api/types";
import { resetToasts, useToasts } from "../lib/toast";
import { makeSettings } from "../test/fixtures";
import { type FetchCall, jsonResponse, stubFetch } from "../test/http";
import { renderWithProviders } from "../test/renderWithProviders";

function server(options: { putStatus?: number; putDetail?: string } = {}) {
  let stored = makeSettings();
  const { calls } = stubFetch((url, init) => {
    if (url !== "/api/settings") throw new Error(`unstubbed request: ${url}`);
    if (init?.method !== "PUT") return jsonResponse(stored);
    if (options.putStatus !== undefined) {
      return jsonResponse({ detail: options.putDetail }, options.putStatus);
    }
    stored = JSON.parse(String(init.body)) as AppSettings;
    return jsonResponse(stored);
  });
  return { calls, current: () => stored };
}

function mount() {
  return renderWithProviders(
    <Routes>
      <Route path="/settings/:section" element={<Settings />} />
    </Routes>,
    { route: "/settings/schedule" },
  );
}

function puts(calls: FetchCall[]): AppSettings[] {
  return calls
    .filter((call) => call.init?.method === "PUT")
    .map((call) => JSON.parse(String(call.init?.body)) as AppSettings);
}

function toastMessages(): string[] {
  return renderHook(() => useToasts()).result.current.map((item) => item.message);
}

afterEach(() => {
  resetToasts();
  vi.unstubAllGlobals();
});

describe("Settings > Schedule", () => {
  it("writes scheduler.default_enabled and says what it means", async () => {
    const { calls, current } = server();
    mount();
    const toggle = await screen.findByRole("switch", { name: "Schedule on by default" });
    expect(toggle).toHaveAttribute("aria-checked", "true");
    expect(
      screen.getByText(
        "New instances follow the anti-ban schedule unless you turn it off per instance.",
      ),
    ).toBeInTheDocument();

    await userEvent.click(toggle);
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    expect(puts(calls)[0].scheduler.default_enabled).toBe(false);
    expect(current().scheduler.default_enabled).toBe(false);
    expect(toastMessages()).toEqual(["Settings saved"]);
  });

  it("puts the API's message under the row", async () => {
    const { calls } = server({
      putStatus: 422,
      putDetail: "scheduler.default_enabled: Input should be a valid boolean",
    });
    mount();
    const toggle = await screen.findByRole("switch", { name: "Schedule on by default" });
    await userEvent.click(toggle);
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    expect(
      await screen.findByText("default_enabled: Input should be a valid boolean"),
    ).toBeInTheDocument();
  });
});
```

Create `brawlfarm/web/src/settings/About.test.tsx`:

```tsx
/** Settings > About: the theme as three cards in a radio group, the running version, the
 * three links and the attribution line. */
import { renderHook, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Settings } from "./Settings";
import type { AppSettings } from "../api/types";
import { resetToasts, useToasts } from "../lib/toast";
import { makeSettings } from "../test/fixtures";
import { type FetchCall, jsonResponse, stubFetch } from "../test/http";
import { renderWithProviders } from "../test/renderWithProviders";

function server(options: { putStatus?: number; putDetail?: string } = {}) {
  let stored = makeSettings();
  const { calls } = stubFetch((url, init) => {
    if (url === "/api/health") {
      return jsonResponse({
        version: "0.1.0",
        home: "C:/data/brawlfarm",
        instances: 1,
        uptime_s: 12.5,
      });
    }
    if (url !== "/api/settings") throw new Error(`unstubbed request: ${url}`);
    if (init?.method !== "PUT") return jsonResponse(stored);
    if (options.putStatus !== undefined) {
      return jsonResponse({ detail: options.putDetail }, options.putStatus);
    }
    stored = JSON.parse(String(init.body)) as AppSettings;
    return jsonResponse(stored);
  });
  return { calls, current: () => stored };
}

function mount() {
  return renderWithProviders(
    <Routes>
      <Route path="/settings/:section" element={<Settings />} />
    </Routes>,
    { route: "/settings/about" },
  );
}

function puts(calls: FetchCall[]): AppSettings[] {
  return calls
    .filter((call) => call.url === "/api/settings" && call.init?.method === "PUT")
    .map((call) => JSON.parse(String(call.init?.body)) as AppSettings);
}

function toastMessages(): string[] {
  return renderHook(() => useToasts()).result.current.map((item) => item.message);
}

afterEach(() => {
  resetToasts();
  vi.unstubAllGlobals();
});

describe("Settings > About", () => {
  it("offers the three themes as one radio group and writes the one that is picked", async () => {
    const { calls, current } = server();
    mount();
    const group = await screen.findByRole("radiogroup", { name: "Theme" });
    expect(within(group).getAllByRole("radio").map((radio) => radio.textContent)).toEqual([
      "SystemFollows Windows.",
      "LightAlways light.",
      "DarkAlways dark.",
    ]);
    expect(within(group).getByRole("radio", { name: /System/ })).toHaveAttribute(
      "aria-checked",
      "true",
    );

    await userEvent.click(within(group).getByRole("radio", { name: /Dark/ }));
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    expect(puts(calls)[0].app.theme).toBe("dark");
    expect(current().app.theme).toBe("dark");
    expect(toastMessages()).toEqual(["Settings saved"]);
    await waitFor(() => {
      expect(within(group).getByRole("radio", { name: /Dark/ })).toHaveAttribute(
        "aria-checked",
        "true",
      );
    });
  });

  it("shows the running version, the three links and the attribution", async () => {
    server();
    mount();
    expect(await screen.findByText("brawlfarm 0.1.0")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "GitHub" })).toHaveAttribute(
      "href",
      "https://github.com/as9pa/brawlfarm",
    );
    expect(screen.getByRole("link", { name: "Setup guide" })).toHaveAttribute(
      "href",
      "https://github.com/as9pa/brawlfarm#requirements",
    );
    expect(screen.getByRole("link", { name: "Safety rails" })).toHaveAttribute(
      "href",
      "https://github.com/as9pa/brawlfarm#safety-rails",
    );
    expect(
      screen.getByText(
        "brawlfarm is not affiliated with or endorsed by Supercell. Brawl Stars and its art belong to Supercell. MIT licensed.",
      ),
    ).toBeInTheDocument();
    // The home folder is on the health payload but belongs to the Data section's tooltip.
    expect(screen.queryByText(/C:\/data\/brawlfarm/)).not.toBeInTheDocument();
  });

  it("puts a refused theme under the group that wrote it", async () => {
    const { calls } = server({
      putStatus: 422,
      putDetail: "app.theme: Input should be 'system', 'dark' or 'light'",
    });
    mount();
    const group = await screen.findByRole("radiogroup", { name: "Theme" });
    await userEvent.click(within(group).getByRole("radio", { name: /Light/ }));
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    expect(
      await screen.findByText("theme: Input should be 'system', 'dark' or 'light'"),
    ).toBeInTheDocument();
    // Nothing was stored, so nothing claims it was.
    expect(toastMessages()).toEqual([]);
    expect(within(group).getByRole("radio", { name: /System/ })).toHaveAttribute(
      "aria-checked",
      "true",
    );
  });
});
```

- [ ] **Step 2: Run the four files to confirm they fail**

```bash
pnpm --dir brawlfarm/web test src/settings/Connection.test.tsx src/settings/Behavior.test.tsx src/settings/Schedule.test.tsx src/settings/About.test.tsx
```

Expected: FAIL. All four collect (they import `./Settings`, which exists) and every case
fails at its first `findBy`, because `SECTION_VIEWS` has no entry for these four ids and the
frame renders the title with nothing under it: `Unable to find a label with the text of: ADB
path`, `Unable to find an accessible element with the role "switch"`, and
`Unable to find an accessible element with the role "radiogroup" and name "Theme"`.

- [ ] **Step 3: Add the health client and its query key**

Create `brawlfarm/web/src/api/health.ts`:

```ts
/** GET /api/health: which version is running, where its data lives, how many instances it
 * manages and how long this process has been up. About shows the version; Data puts the
 * home folder in one tooltip and nowhere else. */
import { api } from "./client";
import type { HealthResponse } from "./types";

export function getHealth(): Promise<HealthResponse> {
  return api<HealthResponse>("/api/health");
}
```

In `brawlfarm/web/src/api/queries.ts`, add one key to `queryKeys`, after `settings`:

```ts
  settings: () => ["settings"] as const,
  /** Version and home folder. About and Data both read it, so one request serves both. */
  health: () => ["health"] as const,
```

- [ ] **Step 4: Write Connection**

Create `brawlfarm/web/src/settings/Connection.tsx`. Both fields are debounced, so they use
task 2's `saveSettingAsync` rather than `saveSetting`: `useDebouncedSave` only learns that a
save landed because the promise resolved.

```tsx
/**
 * Settings > Connection: how brawlfarm reaches BlueStacks and the Brawl Stars API.
 *
 * The adb path carries a chip from one scan run when the section mounts. One, not one per
 * keystroke: the scan shells out to adb and can take seconds, and a cached one would lie
 * about what is installed right now. A scan that failed outright leaves the chip off rather
 * than guessing, because "Not found" would be a claim about adb that the panel cannot make
 * when it could not reach its own server.
 *
 * Both fields save 500 ms after the last keystroke and at once on blur. Neither has a Save
 * button, and neither ever logs what was typed: the token reaches the masked Field, the PUT
 * body and nothing else.
 */
import { useEffect, useState } from "react";
import { Link } from "react-router";

import { SettingRow } from "./SettingRow";
import {
  type SettingsPatch,
  fieldError,
  saveSettingAsync,
  useDebouncedSave,
} from "./useSettingsPatch";
import { scanSetup } from "../api/setup";
import type { ScanResponse } from "../api/types";
import { Chip } from "../components/ui/Chip";
import { ErrorBlock } from "../components/ui/ErrorBlock";
import { Field } from "../components/ui/Field";

const TOKEN_LINE = "Create a key at developer.brawlstars.com and allow this machine's IP address.";

export function Connection({ settingsPatch }: { settingsPatch: SettingsPatch }) {
  const { settings, patch, fieldErrors } = settingsPatch;
  const [scan, setScan] = useState<ScanResponse | null>(null);
  const [failure, setFailure] = useState<unknown>(null);

  useEffect(() => {
    let alive = true;
    void scanSetup()
      .then((found) => {
        if (alive) setScan(found);
      })
      .catch(() => {
        if (alive) setScan(null);
      });
    return () => {
      alive = false;
    };
  }, []);

  const adbPath = useDebouncedSave(settings?.connection.adb_path ?? "", (value) =>
    saveSettingAsync(
      patch,
      (document) => {
        document.connection.adb_path = value;
      },
      setFailure,
    ),
  );
  const token = useDebouncedSave(settings?.connection.brawl_api_token ?? "", (value) =>
    saveSettingAsync(
      patch,
      (document) => {
        document.connection.brawl_api_token = value;
      },
      setFailure,
    ),
  );

  return (
    <div>
      {failure !== null && <ErrorBlock error={failure} />}

      <SettingRow
        title="ADB path"
        description="brawlfarm needs HD-Adb.exe from the BlueStacks folder."
        error={fieldError(fieldErrors, "connection.adb_path")}
      >
        <div className="space-y-2" onBlur={adbPath.onBlur}>
          <Field
            label="ADB path"
            id="connection-adb-path"
            value={adbPath.value}
            onChange={adbPath.onChange}
            width="full"
          />
          <div className="flex items-center gap-2">
            {scan !== null && (
              <Chip tone={scan.adb_found ? "ok" : "bad"}>
                {scan.adb_found ? "Found" : "Not found"}
              </Chip>
            )}
            <Link
              to="/setup"
              className="inline-flex h-8 items-center rounded-[6px] border border-line bg-panel-2 px-3 text-[13px] font-medium text-text transition-colors duration-[120ms] hover:border-accent"
            >
              Run setup again
            </Link>
          </div>
        </div>
      </SettingRow>

      <SettingRow
        title="Brawl Stars API token"
        description={TOKEN_LINE}
        error={fieldError(fieldErrors, "connection.brawl_api_token")}
      >
        <div onBlur={token.onBlur}>
          <Field
            label="Brawl Stars API token"
            id="connection-token"
            value={token.value}
            onChange={token.onChange}
            type="password"
            width="full"
          />
        </div>
      </SettingRow>

      <p className="mt-3 text-[12px] text-muted">Applies to a worker the next time it starts.</p>
    </div>
  );
}
```

"Run setup again" is a `Link` styled like a quiet `Button` rather than a `Button` with an
`onClick` that navigates: it goes somewhere, so it is a link, and middle-clicking it should
open a tab.

- [ ] **Step 5: Write Behavior and Schedule**

Create `brawlfarm/web/src/settings/Behavior.tsx`:

```tsx
/**
 * Settings > Behavior: how a worker plays.
 *
 * Thirteen switches over two sections of the settings document, six of them plain and seven
 * behind Advanced, which starts collapsed because they are performance and safety switches
 * that are on for a reason.
 *
 * Each row is built by one of the two helpers below rather than by a literal table, so the
 * key is checked against the settings type at compile time and the dotted loc the API sends
 * a 422 under is derived from it instead of typed out twice.
 */
import { useState } from "react";

import { SettingRow } from "./SettingRow";
import { type SettingsPatch, fieldError, saveSetting } from "./useSettingsPatch";
import type { AppSettings } from "../api/types";
import { Button } from "../components/ui/Button";
import { ErrorBlock } from "../components/ui/ErrorBlock";
import { Switch } from "../components/ui/Switch";

interface Toggle {
  /** The API's dotted loc, which is also the key a 422 for this row arrives under. */
  loc: string;
  title: string;
  description: string;
  read: (settings: AppSettings) => boolean;
  write: (settings: AppSettings, next: boolean) => void;
}

function behavior<K extends keyof AppSettings["behavior"]>(
  key: K,
  title: string,
  description: string,
): Toggle {
  return {
    loc: `behavior.${key}`,
    title,
    description,
    read: (settings) => settings.behavior[key],
    write: (settings, next) => {
      settings.behavior[key] = next;
    },
  };
}

function advanced<K extends keyof AppSettings["advanced"]>(
  key: K,
  title: string,
  description: string,
): Toggle {
  return {
    loc: `advanced.${key}`,
    title,
    description,
    read: (settings) => settings.advanced[key],
    write: (settings, next) => {
      settings.advanced[key] = next;
    },
  };
}

const BASIC: readonly Toggle[] = [
  behavior("winrate_aware", "Win-rate aware", "Prefer brawlers that win more in the current step."),
  behavior("opportunity_cost", "Opportunity cost", "Skip brawlers whose next tier is far off."),
  behavior("gas_aware", "Gas aware", "Move away from the gas earlier."),
  behavior("bush_hide", "Bush hide", "Hide in bushes when the map allows."),
  behavior("close_game_on_stop", "Close game on stop", "Close Brawl Stars when the worker stops."),
  behavior("dnd_at_start", "DND at start", "Turn on Do Not Disturb when the worker starts."),
];

const ADVANCED: readonly Toggle[] = [
  advanced("fast_input", "Fast input", "Send taps through the faster adb path."),
  advanced("raw_cap", "Raw capture", "Read frames without re-encoding them."),
  advanced("gray_match", "Gray matching", "Match templates in grayscale."),
  advanced("phase_classify", "Phase classify", "Work out the match phase from the screen."),
  advanced("ability_buttons", "Ability buttons", "Use the gadget and super buttons."),
  advanced(
    "recalib_tripwire",
    "Recalibration tripwire",
    "Warn when a detector looks season-blind.",
  ),
  advanced(
    "dnd_off_on_stop",
    "DND off on stop",
    "Turn Do Not Disturb back off when the worker stops.",
  ),
];

export function Behavior({ settingsPatch }: { settingsPatch: SettingsPatch }) {
  const { settings, patch, fieldErrors } = settingsPatch;
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [failure, setFailure] = useState<unknown>(null);

  if (settings === undefined) return null;

  const rows = (list: readonly Toggle[]) =>
    list.map((row) => (
      <SettingRow
        key={row.loc}
        title={row.title}
        description={row.description}
        error={fieldError(fieldErrors, row.loc)}
      >
        <Switch
          checked={row.read(settings)}
          onChange={(next) =>
            saveSetting(patch, (document) => row.write(document, next), setFailure)
          }
          label={row.title}
        />
      </SettingRow>
    ));

  return (
    <div>
      {failure !== null && <ErrorBlock error={failure} />}
      <div>{rows(BASIC)}</div>

      <div className="mt-4">
        <div className="flex items-center gap-2">
          <h3 className="text-[13px] font-semibold">Advanced</h3>
          <Button variant="text" size="sm" onClick={() => setShowAdvanced((on) => !on)}>
            {showAdvanced ? "Hide" : "Show"}
          </Button>
        </div>
        {showAdvanced && <div className="mt-2">{rows(ADVANCED)}</div>}
      </div>

      <p className="mt-4 text-[12px] text-muted">Applies to a worker the next time it starts.</p>
    </div>
  );
}
```

Create `brawlfarm/web/src/settings/Schedule.tsx`:

```tsx
/**
 * Settings > Schedule: the default for new instances.
 *
 * One switch. Per-instance schedules live on the Instance page, where the timeline is: this
 * is only what a freshly added instance starts out with.
 */
import { useState } from "react";

import { SettingRow } from "./SettingRow";
import { type SettingsPatch, fieldError, saveSetting } from "./useSettingsPatch";
import { ErrorBlock } from "../components/ui/ErrorBlock";
import { Switch } from "../components/ui/Switch";

export function Schedule({ settingsPatch }: { settingsPatch: SettingsPatch }) {
  const { settings, patch, fieldErrors } = settingsPatch;
  const [failure, setFailure] = useState<unknown>(null);

  if (settings === undefined) return null;

  return (
    <div>
      {failure !== null && <ErrorBlock error={failure} />}
      <SettingRow
        title="Schedule on by default"
        description="New instances follow the anti-ban schedule unless you turn it off per instance."
        error={fieldError(fieldErrors, "scheduler.default_enabled")}
      >
        <Switch
          checked={settings.scheduler.default_enabled}
          onChange={(next) =>
            saveSetting(
              patch,
              (document) => {
                document.scheduler.default_enabled = next;
              },
              setFailure,
            )
          }
          label="Schedule on by default"
        />
      </SettingRow>
    </div>
  );
}
```

- [ ] **Step 6: Write About**

Create `brawlfarm/web/src/settings/About.tsx`:

```tsx
/**
 * Settings > About: theme, version and links.
 *
 * The theme is a radio group of three cards rather than a Segmented, because each option
 * carries a sentence and Segmented is a row of chips. It keeps Segmented's keyboard, though:
 * one tab stop into the group, arrows between the options, and selection follows focus,
 * which is what a radio group does everywhere else.
 *
 * Picking one writes app.theme, and useSettingsPatch puts the answer straight into the
 * ["settings"] cache, which is the same query App.tsx's theme bootstrap reads: the shell
 * changes colour without a reload and without this component touching the document element.
 */
import { useQuery } from "@tanstack/react-query";
import { type KeyboardEvent, useRef, useState } from "react";

import { type SettingsPatch, fieldError, saveSetting } from "./useSettingsPatch";
import { getHealth } from "../api/health";
import { queryKeys } from "../api/queries";
import type { AppSettings } from "../api/types";
import { ErrorBlock } from "../components/ui/ErrorBlock";

type Theme = AppSettings["app"]["theme"];

const THEMES: readonly { value: Theme; label: string; subtitle: string }[] = [
  { value: "system", label: "System", subtitle: "Follows Windows." },
  { value: "light", label: "Light", subtitle: "Always light." },
  { value: "dark", label: "Dark", subtitle: "Always dark." },
];

const LINKS: readonly { label: string; href: string }[] = [
  { label: "GitHub", href: "https://github.com/as9pa/brawlfarm" },
  // The README's own sections, until docs/setup.md arrives in phase 7.
  { label: "Setup guide", href: "https://github.com/as9pa/brawlfarm#requirements" },
  { label: "Safety rails", href: "https://github.com/as9pa/brawlfarm#safety-rails" },
];

const ATTRIBUTION =
  "brawlfarm is not affiliated with or endorsed by Supercell. Brawl Stars and its art " +
  "belong to Supercell. MIT licensed.";

/** Which way each arrow moves along the group; both ends wrap. */
const ARROW_STEP: Record<string, number> = {
  ArrowLeft: -1,
  ArrowUp: -1,
  ArrowRight: 1,
  ArrowDown: 1,
};

export function About({ settingsPatch }: { settingsPatch: SettingsPatch }) {
  const { settings, patch, fieldErrors } = settingsPatch;
  const [failure, setFailure] = useState<unknown>(null);
  const group = useRef<HTMLDivElement>(null);
  const { data: health } = useQuery({ queryKey: queryKeys.health(), queryFn: getHealth });

  if (settings === undefined) return null;

  const theme = settings.app.theme;
  const at = THEMES.findIndex((entry) => entry.value === theme);
  const tabStop = at < 0 ? 0 : at;

  const choose = (next: Theme) => {
    saveSetting(
      patch,
      (document) => {
        document.app.theme = next;
      },
      setFailure,
    );
  };

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const step = ARROW_STEP[event.key];
    if (step === undefined) return;
    event.preventDefault();
    const to = (tabStop + step + THEMES.length) % THEMES.length;
    choose(THEMES[to].value);
    // Read from the DOM rather than waiting for the re-render, so the key press lands on
    // one frame.
    group.current?.querySelectorAll<HTMLButtonElement>('[role="radio"]')[to]?.focus();
  };

  return (
    <div className="space-y-4">
      {failure !== null && <ErrorBlock error={failure} />}

      <div>
        <h3 className="text-[13px] font-semibold">Theme</h3>
        <div
          ref={group}
          role="radiogroup"
          aria-label="Theme"
          onKeyDown={onKeyDown}
          className="mt-2 grid gap-2 min-[640px]:grid-cols-3"
        >
          {THEMES.map((entry, index) => {
            const selected = entry.value === theme;
            return (
              <button
                key={entry.value}
                type="button"
                role="radio"
                aria-checked={selected}
                tabIndex={index === tabStop ? 0 : -1}
                onClick={() => choose(entry.value)}
                className={`rounded-[10px] border p-3 text-left transition-colors duration-[120ms] ${
                  selected ? "border-accent bg-panel-2" : "border-line bg-panel hover:border-accent"
                }`}
              >
                <span className="block text-[13px]">{entry.label}</span>
                <span className="block text-[12px] text-muted">{entry.subtitle}</span>
              </button>
            );
          })}
        </div>
        {fieldError(fieldErrors, "app.theme") !== undefined && (
          <p className="mt-1 text-[12px] text-bad">{fieldError(fieldErrors, "app.theme")}</p>
        )}
      </div>

      {health !== undefined && (
        <p className="font-mono text-[12px] tabular-nums text-muted">{`brawlfarm ${health.version}`}</p>
      )}

      <ul className="flex flex-wrap gap-3">
        {LINKS.map((link) => (
          <li key={link.label}>
            <a
              href={link.href}
              target="_blank"
              rel="noreferrer"
              className="text-[13px] text-accent hover:underline"
            >
              {link.label}
            </a>
          </li>
        ))}
      </ul>

      <p className="text-[12px] text-muted">{ATTRIBUTION}</p>
    </div>
  );
}
```

- [ ] **Step 7: Put the four sections in the table**

In `brawlfarm/web/src/settings/Settings.tsx`, import the four and add them to
`SECTION_VIEWS`:

```tsx
import { About } from "./About";
import { Behavior } from "./Behavior";
import { Connection } from "./Connection";
import { Instances } from "./Instances";
import { Schedule } from "./Schedule";
```

```tsx
/** Partial while this branch is being built: task 7 fills Notifications and Data in and
 * makes this a total Record, so the compiler proves none is missing. */
const SECTION_VIEWS: Partial<Record<SectionId, SectionView>> = {
  instances: Instances,
  connection: Connection,
  behavior: Behavior,
  schedule: Schedule,
  about: About,
};
```

- [ ] **Step 8: Run the four files, then everything**

```bash
pnpm --dir brawlfarm/web test src/settings/Connection.test.tsx src/settings/Behavior.test.tsx src/settings/Schedule.test.tsx src/settings/About.test.tsx
pnpm --dir brawlfarm/web typecheck
pnpm --dir brawlfarm/web test
pnpm --dir brawlfarm/web build
```

Expected: `Connection.test.tsx` at 4, `Behavior.test.tsx` at 3, `Schedule.test.tsx` at 2 and
`About.test.tsx` at 3, all passing. `tsc --noEmit` prints nothing. The whole suite is 45
files and 335 tests (41 and 323 after task 5). `vite build` writes
`brawlfarm/web/dist/index.html`.

- [ ] **Step 9: Look at it**

```bash
pnpm --dir brawlfarm/web build
uv run brawlfarm --no-browser
```

Open `http://127.0.0.1:8765/settings/about` and pick Dark, then Light, then System: the whole
shell follows within the same render, with no reload and no flash, and the caption beside the
title moves to the current minute. Then open `/settings/connection` and confirm the chip says
Found against the real BlueStacks install, and that the token field shows dots until Show is
pressed.

- [ ] **Step 10: Commit**

```bash
uv run python tools/scrub_check.py && git add brawlfarm/web/src && git commit -m "feat(web): the connection, behavior, schedule and about settings

Connection is two rows: the adb path with a chip from one scan run when
the section mounts, and the masked Brawl Stars token. Both save 500 ms
after the last keystroke and at once on blur, and neither has a Save
button. Behavior is six switches plus seven behind a collapsed Advanced
group, each row built from a key checked against the settings type so the
dotted loc a 422 arrives under is derived rather than typed out twice.
Schedule is the one default for new instances. About offers the theme as
three cards in a real radio group with arrow keys, and the write lands in
the same query the shell's theme bootstrap reads, so the colours follow
without a reload.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CQ1GimQ3uiR2sXPzfZLNWV"
```

Expected: `0 hit(s)`, then the commit.

---

### Task 7: Settings > Notifications and Data

The brief's task 5, and the last of the settings sections: `SECTION_VIEWS` becomes a total
`Record` at the end of this task, so from here on the compiler proves no section is missing.

The three destructive calls of the whole phase live here, and all three are behind a
typed-name `ConfirmDialog`: delete one instance's data folder, and reset every setting. The
open-folder button is the only place the home path is allowed on screen, and it is in a
tooltip so it cannot land in a screenshot.

Accepted proposal ids covered: `set-notifications`, `set-data`.

**Files:**
- Modify: `brawlfarm/web/src/api/settings.ts` (add `resetSettings`, `openDataFolder`, `testNotifications`)
- Modify: `brawlfarm/web/src/api/instances.ts` (add `deleteInstanceData`)
- Create: `brawlfarm/web/src/settings/events.ts`
- Create: `brawlfarm/web/src/settings/Notifications.tsx`
- Create: `brawlfarm/web/src/settings/Data.tsx`
- Modify: `brawlfarm/web/src/settings/Settings.tsx` (`SECTION_VIEWS` becomes total)
- Test: `brawlfarm/web/src/settings/Notifications.test.tsx` (create)
- Test: `brawlfarm/web/src/settings/Data.test.tsx` (create)

**Interfaces:**
- Consumes: task 1's `SettingRow` and `ConfirmDialog`; task 2's `useSettingsPatch`,
  `saveSetting`, `saveSettingAsync`, `fieldError`, `useDebouncedSave`; task 4's four Python
  routes; task 6's `getHealth` and `queryKeys.health()`; the phase 4 `Button`, `ErrorBlock`,
  `Field`, `toast`, `failureMessage`, `queryKeys.instances()`.
- Produces:
  - `api/settings.ts`: `resetSettings(): Promise<AppSettings>`, `openDataFolder(): Promise<void>`,
    `testNotifications(): Promise<NotifyTestResponse>`
  - `api/instances.ts`: `deleteInstanceData(name: string): Promise<void>`
  - `settings/events.ts`: `NOTIFY_EVENT_LABELS: readonly { kind: string; label: string }[]`
  - `settings/Notifications.tsx`: `Notifications`
  - `settings/Data.tsx`: `Data`
- Consumed by: nothing later. This is the last settings task; tasks 8 to 10 are the wizard.

- [ ] **Step 1: Write the failing tests**

Create `brawlfarm/web/src/settings/Notifications.test.tsx`:

```tsx
/** Settings > Notifications: four channels, seven events and one test send. */
import { fireEvent, renderHook, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Settings } from "./Settings";
import type { AppSettings } from "../api/types";
import { resetToasts, useToasts } from "../lib/toast";
import { makeSettings } from "../test/fixtures";
import { type FetchCall, jsonResponse, stubFetch } from "../test/http";
import { renderWithProviders } from "../test/renderWithProviders";

const TEST_ROUTE = "/api/notifications/test";

function server(
  options: {
    settings?: AppSettings;
    sent?: string[];
    failed?: string[];
    testStatus?: number;
    testDetail?: string;
    putStatus?: number;
    putDetail?: string;
  } = {},
) {
  let stored = options.settings ?? makeSettings();
  const { calls } = stubFetch((url, init) => {
    if (url === TEST_ROUTE) {
      if (options.testStatus !== undefined) {
        return jsonResponse({ detail: options.testDetail }, options.testStatus);
      }
      return jsonResponse({ sent: options.sent ?? [], failed: options.failed ?? [] });
    }
    if (url !== "/api/settings") throw new Error(`unstubbed request: ${url}`);
    if (init?.method !== "PUT") return jsonResponse(stored);
    if (options.putStatus !== undefined) {
      return jsonResponse({ detail: options.putDetail }, options.putStatus);
    }
    stored = JSON.parse(String(init.body)) as AppSettings;
    return jsonResponse(stored);
  });
  return { calls, current: () => stored };
}

function mount() {
  return renderWithProviders(
    <Routes>
      <Route path="/settings/:section" element={<Settings />} />
    </Routes>,
    { route: "/settings/notifications" },
  );
}

function puts(calls: FetchCall[]): AppSettings[] {
  return calls
    .filter((call) => call.url === "/api/settings" && call.init?.method === "PUT")
    .map((call) => JSON.parse(String(call.init?.body)) as AppSettings);
}

function toastMessages(): string[] {
  return renderHook(() => useToasts()).result.current.map((item) => item.message);
}

afterEach(() => {
  resetToasts();
  vi.unstubAllGlobals();
});

describe("Settings > Notifications", () => {
  it("lists the four channels in order with their sentences, and saves one on blur", async () => {
    const { calls, current } = server();
    mount();
    const topic = await screen.findByLabelText("ntfy topic");
    expect(
      screen.getByText(
        "Free phone notifications. Install the ntfy app, pick a topic name, type it here.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("ntfy server")).toHaveValue("https://ntfy.sh");
    expect(
      screen.getByText("Leave this unless you run your own ntfy server."),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Webhook URL")).toBeInTheDocument();
    expect(
      screen.getByText(
        "A URL that receives each alert as a message, for chat apps that offer incoming webhooks.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Healthchecks URL")).toBeInTheDocument();
    expect(
      screen.getByText(
        "A check-in URL from healthchecks.io; it warns you when brawlfarm stops checking in.",
      ),
    ).toBeInTheDocument();

    fireEvent.change(topic, { target: { value: "brawlfarm-home" } });
    fireEvent.blur(topic);
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    expect(puts(calls)[0].notifications.ntfy_topic).toBe("brawlfarm-home");
    expect(current().notifications.ntfy_topic).toBe("brawlfarm-home");
    expect(toastMessages()).toEqual(["Settings saved"]);
  });

  it("keeps the event list in the brief's order however it is ticked", async () => {
    const { calls } = server();
    mount();
    expect(await screen.findByText("Send me")).toBeInTheDocument();
    const boxes = screen.getAllByRole("checkbox");
    expect(boxes.map((box) => box.getAttribute("aria-label") ?? "")).toEqual([
      "Crash",
      "Recovery",
      "Instance offline",
      "Wrong mode",
      "Recalibration needed",
      "Stopped",
      "Wrong resolution",
    ]);
    // The fixture's default five are on; Stopped and Wrong resolution are not.
    expect(screen.getByRole("checkbox", { name: "Crash" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Stopped" })).not.toBeChecked();

    await userEvent.click(screen.getByRole("checkbox", { name: "Stopped" }));
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    // Stored in the list's own order, not in the order they were clicked, so the file on
    // disk reads the same whatever route got it there.
    expect(puts(calls)[0].notifications.events).toEqual([
      "crash",
      "recover",
      "offline",
      "wrong_mode",
      "recalibrate",
      "stop",
    ]);

    await userEvent.click(screen.getByRole("checkbox", { name: "Crash" }));
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(2);
    });
    expect(puts(calls)[1].notifications.events).toEqual([
      "recover",
      "offline",
      "wrong_mode",
      "recalibrate",
      "stop",
    ]);
  });

  it("will not send a test with no channel set, and says what to add first", async () => {
    // The fixture is the model default: no topic, no webhook, no healthchecks URL.
    const { calls } = server();
    mount();
    const button = await screen.findByRole("button", { name: "Send a test" });
    expect(button).toBeDisabled();
    expect(screen.getByText("Add a channel first")).toBeInTheDocument();

    await userEvent.click(button);
    expect(calls.filter((call) => call.url === TEST_ROUTE)).toHaveLength(0);
    expect(toastMessages()).toEqual([]);
  });

  it("puts a refused channel under the row that carried it", async () => {
    const { calls } = server({
      putStatus: 422,
      putDetail: "notifications.ntfy_topic: topic may not contain a slash",
    });
    mount();
    const topic = await screen.findByLabelText("ntfy topic");
    fireEvent.change(topic, { target: { value: "home/phone" } });
    fireEvent.blur(topic);
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    expect(
      await screen.findByText("ntfy_topic: topic may not contain a slash"),
    ).toBeInTheDocument();
    // The box keeps what is being fixed, and no toast claims it was saved.
    expect(topic).toHaveValue("home/phone");
    expect(toastMessages()).toEqual([]);
  });

  it("toasts what was sent and what failed, sent first", async () => {
    const withChannel = makeSettings();
    withChannel.notifications.ntfy_topic = "brawlfarm-home";
    const { calls } = server({ settings: withChannel, sent: ["ntfy"], failed: ["webhook"] });
    mount();
    const button = await screen.findByRole("button", { name: "Send a test" });
    expect(button).toBeEnabled();
    expect(screen.queryByText("Add a channel first")).not.toBeInTheDocument();

    await userEvent.click(button);
    await waitFor(() => {
      expect(calls.filter((call) => call.url === TEST_ROUTE)).toHaveLength(1);
    });
    expect(calls.find((call) => call.url === TEST_ROUTE)?.init?.method).toBe("POST");
    await waitFor(() => {
      expect(toastMessages()).toEqual(["Test sent to ntfy", "Test failed for webhook"]);
    });
    // Nothing was saved: a test send writes no settings.
    expect(puts(calls)).toHaveLength(0);
  });
});
```

Task 1's `makeSettings` mirrors `brawlfarm/settings.py`, so its `notifications` block is the
model default: topic `""`, server `"https://ntfy.sh"`, no webhook, no healthchecks URL, and
`events` the five kinds `crash, recover, offline, wrong_mode, recalibrate`. That is why the
third case can use the fixture as it comes to get the no-channel state, and the fourth sets a
topic on its own copy.

Create `brawlfarm/web/src/settings/Data.test.tsx`:

```tsx
/** Settings > Data: open the folder, delete one instance's folder, reset everything. */
import { renderHook, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Settings } from "./Settings";
import type { AppSettings } from "../api/types";
import { resetToasts, useToasts } from "../lib/toast";
import { makeSettings } from "../test/fixtures";
import { type FetchCall, jsonResponse, stubFetch } from "../test/http";
import { renderWithProviders } from "../test/renderWithProviders";

const OPEN = "/api/settings/open-data-folder";
const RESET = "/api/settings/reset";
const DELETE_DATA = "/api/instances/Pie64/data";

const FLEET = makeSettings({
  instances: [
    { name: "Pie64", adb_port: 5555, player_tag: "#2P0YLQ9" },
    { name: "Pie64_3", adb_port: 5585, player_tag: "" },
  ],
});

function server(
  options: {
    openStatus?: number;
    openDetail?: string;
    deleteStatus?: number;
    deleteDetail?: string;
  } = {},
) {
  let stored = FLEET;
  const { calls } = stubFetch((url, init) => {
    if (url === "/api/health") {
      return jsonResponse({
        version: "0.1.0",
        home: "C:/data/brawlfarm",
        instances: 2,
        uptime_s: 12.5,
      });
    }
    if (url === OPEN) {
      if (options.openStatus !== undefined) {
        return jsonResponse({ detail: options.openDetail }, options.openStatus);
      }
      return jsonResponse(null, 204);
    }
    if (url === RESET) {
      // What settings_routes.py does: every section back to its model default, the
      // instances list carried over untouched.
      stored = { ...makeSettings(), instances: stored.instances };
      return jsonResponse(stored);
    }
    if (url === DELETE_DATA) {
      if (options.deleteStatus !== undefined) {
        return jsonResponse({ detail: options.deleteDetail }, options.deleteStatus);
      }
      return jsonResponse(null, 204);
    }
    if (url === "/api/instances") return jsonResponse({ instances: [] });
    if (url !== "/api/settings") throw new Error(`unstubbed request: ${url}`);
    if (init?.method !== "PUT") return jsonResponse(stored);
    stored = JSON.parse(String(init.body)) as AppSettings;
    return jsonResponse(stored);
  });
  return { calls, current: () => stored };
}

function mount() {
  return renderWithProviders(
    <Routes>
      <Route path="/settings/:section" element={<Settings />} />
    </Routes>,
    { route: "/settings/data" },
  );
}

function hits(calls: FetchCall[], url: string): FetchCall[] {
  return calls.filter((call) => call.url === url);
}

function toastMessages(): string[] {
  return renderHook(() => useToasts()).result.current.map((item) => item.message);
}

/** Open a typed-name dialog, type the word, press the confirm button. */
async function confirmWith(word: string, confirmLabel: string) {
  const dialog = await screen.findByRole("dialog");
  const confirm = within(dialog).getByRole("button", { name: confirmLabel });
  expect(confirm).toBeDisabled();
  await userEvent.type(within(dialog).getByLabelText("Type to confirm"), word);
  expect(confirm).toBeEnabled();
  await userEvent.click(confirm);
}

afterEach(() => {
  resetToasts();
  vi.unstubAllGlobals();
});

describe("Settings > Data", () => {
  it("opens the data folder, with the home path only in the button's tooltip", async () => {
    const { calls } = server();
    mount();
    const button = await screen.findByRole("button", { name: "Open data folder" });
    await waitFor(() => {
      expect(screen.getByTitle("C:/data/brawlfarm")).toBeInTheDocument();
    });
    // In the tooltip and nowhere else: a path with a user name in it must not be in the
    // page's text, where a screenshot would catch it.
    expect(screen.queryByText("C:/data/brawlfarm")).not.toBeInTheDocument();
    expect(screen.getByTitle("C:/data/brawlfarm")).toHaveAttribute("data-private");

    await userEvent.click(button);
    await waitFor(() => {
      expect(hits(calls, OPEN)).toHaveLength(1);
    });
    expect(hits(calls, OPEN)[0].init?.method).toBe("POST");
    expect(toastMessages()).toEqual([]);
  });

  it("toasts the 501 when brawlfarm is not running on Windows", async () => {
    server({ openStatus: 501, openDetail: "Only on Windows" });
    mount();
    await userEvent.click(await screen.findByRole("button", { name: "Open data folder" }));
    await waitFor(() => {
      expect(toastMessages()).toEqual(["Only on Windows"]);
    });
  });

  it("deletes one instance's folder once its name has been typed", async () => {
    const { calls } = server();
    mount();
    expect(await screen.findByText("Delete one instance's data")).toBeInTheDocument();
    expect(screen.getByText("instances/Pie64")).toBeInTheDocument();
    expect(screen.getByText("instances/Pie64_3")).toBeInTheDocument();

    const row = screen.getByText("instances/Pie64").closest("li");
    expect(row).not.toBeNull();
    await userEvent.click(within(row as HTMLElement).getByRole("button", { name: "Delete data" }));
    expect(await screen.findByText("Delete Pie64's data?")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Its folder instances/Pie64 and everything in it goes: status, farm plan, schedule, games.csv and past sessions. The instance stays in your fleet.",
      ),
    ).toBeInTheDocument();

    await confirmWith("Pie64", "Delete data");
    await waitFor(() => {
      expect(hits(calls, DELETE_DATA)).toHaveLength(1);
    });
    expect(hits(calls, DELETE_DATA)[0].init?.method).toBe("DELETE");
    // The instance is still in the fleet: only its folder went.
    expect(screen.getByText("instances/Pie64")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });

  it("puts the API's refusal inline in the row it belongs to", async () => {
    const { calls } = server({
      deleteStatus: 409,
      deleteDetail: "Stop Pie64 before deleting its data",
    });
    mount();
    const row = (await screen.findByText("instances/Pie64")).closest("li");
    await userEvent.click(within(row as HTMLElement).getByRole("button", { name: "Delete data" }));
    await confirmWith("Pie64", "Delete data");
    await waitFor(() => {
      expect(hits(calls, DELETE_DATA)).toHaveLength(1);
    });
    const failed = (await screen.findByText("Stop Pie64 before deleting its data")).closest("li");
    expect(failed).toBe(row);
    expect(toastMessages()).toEqual([]);
  });

  it("resets every other setting once the word has been typed", async () => {
    const { calls } = server();
    mount();
    expect(await screen.findByText("Reset all settings")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Your instances and their data folders stay. Every other setting goes back to its default.",
      ),
    ).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Reset" }));
    expect(await screen.findByText("Reset all settings?")).toBeInTheDocument();
    await confirmWith("reset", "Reset");
    await waitFor(() => {
      expect(hits(calls, RESET)).toHaveLength(1);
    });
    expect(hits(calls, RESET)[0].init?.method).toBe("POST");
    await waitFor(() => {
      expect(toastMessages()).toEqual(["Settings reset"]);
    });
    // The answer went into the cache, so the two instances are still listed: a reset keeps
    // them and their folders.
    expect(screen.getByText("instances/Pie64")).toBeInTheDocument();
    expect(screen.getByText("instances/Pie64_3")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run both files to confirm they fail**

```bash
pnpm --dir brawlfarm/web test src/settings/Notifications.test.tsx src/settings/Data.test.tsx
```

Expected: FAIL, 10 cases. `SECTION_VIEWS` has no `notifications` or `data` entry, so the frame
renders the title and nothing else: `Unable to find a label with the text of: ntfy topic` and
`Unable to find an accessible element with the role "button" and name "Open data folder"`.

- [ ] **Step 3: Add the four client calls**

Append to `brawlfarm/web/src/api/settings.ts`:

```ts
/** POST /api/settings/reset. Returns the document it wrote: every section back to its model
 * default, with the instances list carried over untouched. */
export function resetSettings(): Promise<AppSettings> {
  return api<AppSettings>("/api/settings/reset", { method: "POST" });
}

/** POST /api/settings/open-data-folder. 204 on Windows; 501 "Only on Windows" anywhere
 * else, which the caller toasts. The path itself never crosses the wire. */
export function openDataFolder(): Promise<void> {
  return api<void>("/api/settings/open-data-folder", { method: "POST" });
}

/** POST /api/notifications/test. The body is the server's own list of channel names that
 * answered and channel names that did not; nothing here sees a URL or a topic. */
export function testNotifications(): Promise<NotifyTestResponse> {
  return api<NotifyTestResponse>("/api/notifications/test", { method: "POST" });
}
```

and widen its type import:

```ts
import type { AppSettings, NotifyTestResponse } from "./types";
```

Append to `brawlfarm/web/src/api/instances.ts`:

```ts
/** DELETE /api/instances/{name}/data. 204. This removes the instance's folder under the
 * data home, not the instance: it stays in config.toml and in the fleet, with nothing in
 * its folder. 409 when it is still running, which the caller shows in the row. */
export function deleteInstanceData(name: string): Promise<void> {
  return api<void>(`/api/instances/${name}/data`, { method: "DELETE" });
}
```

- [ ] **Step 4: Write the event label map**

Create `brawlfarm/web/src/settings/events.ts`:

```ts
/**
 * The seven alert kinds as Settings names them, in the order the section lists them.
 *
 * Deliberately not `lib/states.ts`'s ALERT_KIND_LABELS: that map names an alert that has
 * already happened ("Recover", "Recalibrate") and has no entry for `stop`, while this one
 * names a thing to be told about ("Recovery", "Recalibration needed", "Stopped"). Unifying
 * them would make one of the two read wrong. The kinds themselves are
 * `brawlfarm/core/notify.py`'s ALERT_KINDS, which is a set: the order lives here.
 */
export const NOTIFY_EVENT_LABELS: readonly { kind: string; label: string }[] = [
  { kind: "crash", label: "Crash" },
  { kind: "recover", label: "Recovery" },
  { kind: "offline", label: "Instance offline" },
  { kind: "wrong_mode", label: "Wrong mode" },
  { kind: "recalibrate", label: "Recalibration needed" },
  { kind: "stop", label: "Stopped" },
  { kind: "bad_resolution", label: "Wrong resolution" },
];
```

- [ ] **Step 5: Write Notifications**

Create `brawlfarm/web/src/settings/Notifications.tsx`:

```tsx
/**
 * Settings > Notifications: where alerts go.
 *
 * Four channels, seven events and one test send. Each channel row is its own component
 * rather than four copies of the same eight lines, which is also what keeps useDebouncedSave
 * to one call per component instead of a hook inside a loop.
 *
 * The event list is written back in NOTIFY_EVENT_LABELS' order rather than in the order the
 * boxes were ticked, so config.toml reads the same however it got there and a diff between
 * two machines is about what is on, not about what was clicked first.
 *
 * Neither a URL nor a topic is ever logged or toasted: the test result names channels
 * ("ntfy", "webhook"), never their addresses.
 */
import { useState } from "react";

import { NOTIFY_EVENT_LABELS } from "./events";
import { SettingRow } from "./SettingRow";
import {
  type SettingsPatch,
  fieldError,
  saveSetting,
  saveSettingAsync,
  useDebouncedSave,
} from "./useSettingsPatch";
import { testNotifications } from "../api/settings";
import type { AppSettings } from "../api/types";
import { Button } from "../components/ui/Button";
import { ErrorBlock } from "../components/ui/ErrorBlock";
import { Field } from "../components/ui/Field";
import { failureMessage, toast } from "../lib/toast";

type ChannelField = "ntfy_topic" | "ntfy_server" | "webhook_url" | "healthchecks_url";

const CHANNELS: readonly { field: ChannelField; label: string; description: string }[] = [
  {
    field: "ntfy_topic",
    label: "ntfy topic",
    description:
      "Free phone notifications. Install the ntfy app, pick a topic name, type it here.",
  },
  {
    field: "ntfy_server",
    label: "ntfy server",
    description: "Leave this unless you run your own ntfy server.",
  },
  {
    field: "webhook_url",
    label: "Webhook URL",
    description:
      "A URL that receives each alert as a message, for chat apps that offer incoming webhooks.",
  },
  {
    field: "healthchecks_url",
    label: "Healthchecks URL",
    description:
      "A check-in URL from healthchecks.io; it warns you when brawlfarm stops checking in.",
  },
];

function ChannelRow({
  settingsPatch,
  field,
  label,
  description,
  onFailure,
}: {
  settingsPatch: SettingsPatch;
  field: ChannelField;
  label: string;
  description: string;
  onFailure: (error: unknown) => void;
}) {
  const { settings, patch, fieldErrors } = settingsPatch;
  const box = useDebouncedSave(settings?.notifications[field] ?? "", (value) =>
    saveSettingAsync(
      patch,
      (document) => {
        document.notifications[field] = value;
      },
      onFailure,
    ),
  );
  return (
    <SettingRow
      title={label}
      description={description}
      error={fieldError(fieldErrors, `notifications.${field}`)}
    >
      <div onBlur={box.onBlur}>
        <Field
          label={label}
          id={`notifications-${field}`}
          value={box.value}
          onChange={box.onChange}
          width="full"
        />
      </div>
    </SettingRow>
  );
}

export function Notifications({ settingsPatch }: { settingsPatch: SettingsPatch }) {
  const { settings, patch } = settingsPatch;
  const [failure, setFailure] = useState<unknown>(null);
  const [sending, setSending] = useState(false);

  if (settings === undefined) return null;

  const on = new Set(settings.notifications.events);
  const hasChannel =
    settings.notifications.ntfy_topic !== "" ||
    settings.notifications.webhook_url !== "" ||
    settings.notifications.healthchecks_url !== "";

  const toggleEvent = (kind: string, next: boolean) => {
    const wanted = new Set(on);
    if (next) wanted.add(kind);
    else wanted.delete(kind);
    saveSetting(
      patch,
      (document: AppSettings) => {
        document.notifications.events = NOTIFY_EVENT_LABELS.filter((event) =>
          wanted.has(event.kind),
        ).map((event) => event.kind);
      },
      setFailure,
    );
  };

  const sendTest = () => {
    setSending(true);
    void testNotifications()
      .then(
        (result) => {
          // Sent first: the good news is the answer to "did that work", and the failures
          // read as the exception to it.
          if (result.sent.length > 0) toast(`Test sent to ${result.sent.join(", ")}`);
          if (result.failed.length > 0) toast(`Test failed for ${result.failed.join(", ")}`);
        },
        (error: unknown) => {
          toast(failureMessage(error));
        },
      )
      .finally(() => setSending(false));
  };

  return (
    <div>
      {failure !== null && <ErrorBlock error={failure} />}

      <div>
        {CHANNELS.map((channel) => (
          <ChannelRow
            key={channel.field}
            settingsPatch={settingsPatch}
            field={channel.field}
            label={channel.label}
            description={channel.description}
            onFailure={setFailure}
          />
        ))}
      </div>

      <div className="mt-4">
        <h3 className="text-[13px] font-semibold">Send me</h3>
        <ul className="mt-2 grid gap-1.5 min-[640px]:grid-cols-2">
          {NOTIFY_EVENT_LABELS.map((event) => (
            <li key={event.kind}>
              <label className="inline-flex items-center gap-2 text-[13px]">
                <input
                  type="checkbox"
                  aria-label={event.label}
                  checked={on.has(event.kind)}
                  onChange={(change) => toggleEvent(event.kind, change.target.checked)}
                  className="h-3.5 w-3.5 accent-[var(--accent)]"
                />
                {event.label}
              </label>
            </li>
          ))}
        </ul>
      </div>

      <div className="mt-4 flex items-center gap-2">
        <Button
          variant="quiet"
          disabled={!hasChannel || sending}
          disabledReason={hasChannel ? undefined : "Add a channel first"}
          onClick={sendTest}
        >
          Send a test
        </Button>
        {!hasChannel && <span className="text-[12px] text-muted">Add a channel first</span>}
      </div>
    </div>
  );
}
```

The checkbox carries an explicit `aria-label` as well as its visible text: the text is inside
the same `<label>`, so it is already the accessible name, and the attribute is what lets the
test read the seven names off the list in order without walking the DOM.

- [ ] **Step 6: Write Data**

Create `brawlfarm/web/src/settings/Data.tsx`:

```tsx
/**
 * Settings > Data: files on this machine.
 *
 * The home folder is a real path with a user name in it, so it appears in exactly one place:
 * the title of the open-folder button. Not in a heading, not in a caption, not in an error.
 * A screenshot of this page is therefore safe to paste into an issue.
 *
 * Both destructive acts go through a typed-name ConfirmDialog: the instance's own name for
 * its folder, the word "reset" for the settings. Deleting a folder does not delete the
 * instance, and a reset keeps every instance and every folder: only the other sections go
 * back to their defaults.
 */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { type SettingsPatch } from "./useSettingsPatch";
import { getHealth } from "../api/health";
import { deleteInstanceData } from "../api/instances";
import { queryKeys } from "../api/queries";
import { openDataFolder, resetSettings } from "../api/settings";
import { Button } from "../components/ui/Button";
import { ConfirmDialog } from "../components/ui/ConfirmDialog";
import { failureMessage, toast } from "../lib/toast";

const RESET_SENTENCE =
  "Your instances and their data folders stay. Every other setting goes back to its default.";

export function Data({ settingsPatch }: { settingsPatch: SettingsPatch }) {
  const { settings } = settingsPatch;
  const client = useQueryClient();
  const { data: health } = useQuery({ queryKey: queryKeys.health(), queryFn: getHealth });
  const [deleting, setDeleting] = useState<string | null>(null);
  const [resetting, setResetting] = useState(false);
  /** Keyed by instance name: a refusal belongs beside the row it refused. */
  const [rowErrors, setRowErrors] = useState<Record<string, string>>({});

  if (settings === undefined) return null;

  const openFolder = () => {
    void openDataFolder().catch((error: unknown) => {
      toast(failureMessage(error));
    });
  };

  const deleteData = (name: string) => {
    setRowErrors((errors) =>
      Object.fromEntries(Object.entries(errors).filter(([key]) => key !== name)),
    );
    void deleteInstanceData(name).then(
      () => {
        setDeleting(null);
        void client.invalidateQueries({ queryKey: queryKeys.instances() });
      },
      (error: unknown) => {
        setDeleting(null);
        setRowErrors((errors) => ({ ...errors, [name]: failureMessage(error) }));
      },
    );
  };

  const reset = () => {
    void resetSettings().then(
      (next) => {
        setResetting(false);
        client.setQueryData(queryKeys.settings(), next);
        void client.invalidateQueries({ queryKey: queryKeys.instances() });
        toast("Settings reset");
      },
      (error: unknown) => {
        setResetting(false);
        toast(failureMessage(error));
      },
    );
  };

  return (
    <div className="space-y-5">
      <div>
        {/* The title is on a wrapper rather than on Button, so Button's props stay exactly
            as phase 4 left them. data-private is what the screenshot pass blurs. */}
        <span title={health?.home} data-private>
          <Button variant="quiet" onClick={openFolder}>
            Open data folder
          </Button>
        </span>
      </div>

      <div>
        <h3 className="text-[13px] font-semibold">Delete one instance&apos;s data</h3>
        <ul className="mt-2">
          {settings.instances.map((instance) => (
            <li
              key={instance.name}
              className="flex flex-wrap items-center gap-3 border-b border-line py-2 last:border-b-0"
            >
              <span className="font-mono text-[13px]">{instance.name}</span>
              <span className="text-[12px] text-muted">{`instances/${instance.name}`}</span>
              <span className="ml-auto">
                <Button variant="text" size="sm" onClick={() => setDeleting(instance.name)}>
                  Delete data
                </Button>
              </span>
              {rowErrors[instance.name] !== undefined && (
                <p className="w-full text-[12px] text-bad">{rowErrors[instance.name]}</p>
              )}
            </li>
          ))}
        </ul>
      </div>

      <div className="rounded-[10px] border border-bad bg-panel p-3">
        <h3 className="text-[13px] font-semibold">Reset all settings</h3>
        <p className="mt-0.5 text-[12px] text-muted">{RESET_SENTENCE}</p>
        <div className="mt-2">
          <Button variant="quiet" onClick={() => setResetting(true)}>
            Reset
          </Button>
        </div>
      </div>

      <ConfirmDialog
        open={deleting !== null}
        onClose={() => setDeleting(null)}
        title={`Delete ${deleting ?? ""}'s data?`}
        body={`Its folder instances/${deleting ?? ""} and everything in it goes: status, farm plan, schedule, games.csv and past sessions. The instance stays in your fleet.`}
        word={deleting ?? ""}
        confirmLabel="Delete data"
        tone="bad"
        onConfirm={() => {
          if (deleting !== null) deleteData(deleting);
        }}
      />

      <ConfirmDialog
        open={resetting}
        onClose={() => setResetting(false)}
        title="Reset all settings?"
        body={RESET_SENTENCE}
        word="reset"
        confirmLabel="Reset"
        tone="bad"
        onConfirm={reset}
      />
    </div>
  );
}
```

`border-bad` is the existing `--bad` token used as a border colour, which Tailwind v4's
`@theme inline` already generates from `styles/theme.css`; no new token is added.

- [ ] **Step 7: Close the section table**

In `brawlfarm/web/src/settings/Settings.tsx`, add the last two imports and drop the
`Partial`:

```tsx
import { About } from "./About";
import { Behavior } from "./Behavior";
import { Connection } from "./Connection";
import { Data } from "./Data";
import { Instances } from "./Instances";
import { Notifications } from "./Notifications";
import { Schedule } from "./Schedule";
```

```tsx
/** Total, not Partial: every id in SETTINGS_SECTIONS has a view, and the compiler is what
 * says so. Adding a section to the nav without writing it now fails typecheck. */
const SECTION_VIEWS: Record<SectionId, SectionView> = {
  instances: Instances,
  connection: Connection,
  behavior: Behavior,
  schedule: Schedule,
  notifications: Notifications,
  data: Data,
  about: About,
};
```

- [ ] **Step 8: Run both files, then everything**

```bash
pnpm --dir brawlfarm/web test src/settings/Notifications.test.tsx src/settings/Data.test.tsx
pnpm --dir brawlfarm/web typecheck
pnpm --dir brawlfarm/web test
pnpm --dir brawlfarm/web build
```

Expected: `Notifications.test.tsx` at 5 and `Data.test.tsx` at 5, all passing. `tsc --noEmit`
prints nothing. The whole suite is 47 files and 345 tests (45 and 335 after task 6). `vite
build` writes `brawlfarm/web/dist/index.html`.

- [ ] **Step 9: Look at it, and send one real notification**

```bash
pnpm --dir brawlfarm/web build
uv run brawlfarm --no-browser
```

Open `http://127.0.0.1:8765/settings/notifications`, put a real ntfy topic in (any name; the
free ntfy app subscribes to it), wait for the "Settings saved" toast, then press Send a test:
the phone gets "brawlfarm test / This is a test alert from brawlfarm." and the panel toasts
`Test sent to ntfy`. Clear the topic again afterwards so nothing personal is left in
`config.toml`.

Then open `/settings/data`, hover Open data folder and confirm the path is only in the
tooltip, press it and confirm Explorer opens the data home. Open the delete dialog for an
instance and press Escape without typing: nothing is deleted, and reopening it finds the box
empty again.

- [ ] **Step 10: Commit**

```bash
uv run python tools/scrub_check.py && git add brawlfarm/web/src && git commit -m "feat(web): the notifications and data settings

Notifications is four channel rows, seven event checkboxes and one test
send. The event list is written back in its own order rather than in the
order the boxes were ticked, so config.toml reads the same however it got
there. With no channel set the test button is disabled and says what to
add first, so the route is never called with nothing to send to. No URL
and no topic reaches a log or a toast: the result names channels.

Data keeps the home folder in exactly one place, the open-folder button's
tooltip, so a screenshot of the page cannot leak a user name. Deleting an
instance's folder and resetting the settings both go through a typed-name
dialog, and the API's refusal lands in the row it refused rather than in a
toast that has already scrolled away. SECTION_VIEWS is a total Record from
here on, so a section in the nav without a view fails typecheck.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CQ1GimQ3uiR2sXPzfZLNWV"
```

Expected: `0 hit(s)`, then the commit.

---

### Task 8: The wizard frame, the step rail, and step 1

The first half of the brief's task 6. One route, five steps in component state, and the
first step made real. The other four render nothing until tasks 9 and 10 fill them in, which
is why `STEP_VIEWS` starts `Partial` exactly as `SECTION_VIEWS` did.

`/setup` is the one route that escapes the `Shell`: no rail, no top bar, no alerts drawer.
Someone on this page has no fleet yet, so a fleet chrome around it would be a shell with
nothing in it.

Accepted proposal ids covered: `wiz-flow`, `wiz-bluestacks`.

**Files:**
- Create: `brawlfarm/web/src/setup/useSetupState.ts`
- Create: `brawlfarm/web/src/setup/StepRail.tsx`
- Create: `brawlfarm/web/src/setup/Setup.tsx`
- Create: `brawlfarm/web/src/setup/StepBlueStacks.tsx`
- Modify: `brawlfarm/web/src/App.tsx` (`/setup` beside `ShellRoutes`)
- Test: `brawlfarm/web/src/setup/useSetupState.test.tsx` (create)
- Test: `brawlfarm/web/src/setup/StepRail.test.tsx` (create)
- Test: `brawlfarm/web/src/setup/StepBlueStacks.test.tsx` (create)
- Test: `brawlfarm/web/src/App.test.tsx` (modify: one test appended)

**Interfaces:**
- Consumes: task 2's `useSettingsPatch` and `SettingsPatch`; task 5's `scanSetup` and
  `ShellRoutes`; task 1's `Field`; the phase 4 `Button`, `Chip`, `ErrorBlock`, `toast`,
  `ApiError`.
- Produces:
  - `setup/useSetupState.ts`: `StepId` (`"bluestacks" | "instances" | "display" | "stats" | "done"`),
    `SetupStep { id: StepId; label: string }`, `SETUP_STEPS: readonly SetupStep[]`,
    `SetupState`, `StepProps { setup: SetupState }` (the one prop every step takes),
    `useSetupState(settingsPatch: SettingsPatch): SetupState`,
    `saveStep(patch, mutate, onFailure): void`,
    `saveStepAsync(patch, mutate, onFailure): Promise<void>`
  - `setup/StepRail.tsx`: `StepRailProps { index; done; onGo }`, `StepRail`
  - `setup/Setup.tsx`: `Setup`
  - `setup/StepBlueStacks.tsx`: `StepBlueStacks`
- Consumed by: task 9 (`StepInstances`, `StepDisplay`), task 10 (`StepStats`, `StepDone`,
  and the two links into `/setup`).

`SetupState` in full, because tasks 9 and 10 are written against it:

```ts
export interface SetupState {
  /** The step on screen. Always a real id: "bluestacks" until the document arrives. */
  step: StepId;
  /** Its position in SETUP_STEPS, which is what the rail compares against. */
  index: number;
  /** False until GET /api/settings has answered; the frame shows nothing before that. */
  ready: boolean;
  done: Record<StepId, boolean>;
  go: (id: StepId) => void;
  next: () => void;
  back: () => void;
  /** The last scan. Step 1 runs it; steps 2 and 3 read the ports out of it. */
  scan: ScanResponse | null;
  setScan: (scan: ScanResponse | null) => void;
  /** Step 4's "Skip for now": true for this visit only, never written to disk. */
  skipStats: () => void;
  settingsPatch: SettingsPatch;
}
```

`StepProps` lives in `useSetupState.ts` rather than in `Setup.tsx`, even though `Setup.tsx` is
where the contract is used: `Setup.tsx` imports every step, so a step importing a type back
out of it would be a module cycle, and `verbatimModuleSyntax` keeps the empty import that
makes the cycle real at runtime.

- [ ] **Step 1: Write the failing tests for the state**

Create `brawlfarm/web/src/setup/useSetupState.test.tsx`:

```tsx
/** Where the wizard opens, what the rail may tick, and how walking forward and back
 * behaves. */
import { QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useSetupState } from "./useSetupState";
import type { AppSettings, ScanResponse } from "../api/types";
import { useSettingsPatch } from "../settings/useSettingsPatch";
import { makeSettings } from "../test/fixtures";
import { jsonResponse, stubFetch } from "../test/http";
import { testQueryClient } from "../test/renderWithProviders";

const ADB = "C:\\Program Files\\BlueStacks_nxt\\HD-Adb.exe";

function found(adbPath: string): ScanResponse {
  return { adb_path: adbPath, adb_found: true, conf_found: true, instances: [] };
}

function mount(settings: AppSettings) {
  stubFetch((url) => {
    if (url !== "/api/settings") throw new Error(`unstubbed request: ${url}`);
    return jsonResponse(settings);
  });
  const client = testQueryClient();
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return renderHook(
    () => {
      const settingsPatch = useSettingsPatch();
      return useSetupState(settingsPatch);
    },
    { wrapper },
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useSetupState", () => {
  it("opens on BlueStacks when config.toml names no adb path", async () => {
    const blank = makeSettings({ instances: [] });
    blank.connection.adb_path = "";
    const { result } = mount(blank);
    await waitFor(() => {
      expect(result.current.ready).toBe(true);
    });
    expect(result.current.step).toBe("bluestacks");
    expect(result.current.index).toBe(0);
    expect(result.current.done.instances).toBe(false);
  });

  it("opens on Instances with a path but no fleet, and on Display once there is one", async () => {
    const noFleet = makeSettings({ instances: [] });
    const first = mount(noFleet);
    await waitFor(() => {
      expect(first.result.current.ready).toBe(true);
    });
    expect(first.result.current.step).toBe("instances");
    first.unmount();
    vi.unstubAllGlobals();

    const withFleet = mount(makeSettings());
    await waitFor(() => {
      expect(withFleet.result.current.ready).toBe(true);
    });
    expect(withFleet.result.current.step).toBe("display");
    expect(withFleet.result.current.index).toBe(2);
    // Nothing about the display is stored, so it is never already done.
    expect(withFleet.result.current.done.display).toBe(false);
    expect(withFleet.result.current.done.instances).toBe(true);
  });

  it("ticks BlueStacks only when the last scan agrees with what is stored", async () => {
    const settings = makeSettings();
    settings.connection.adb_path = ADB;
    const { result } = mount(settings);
    await waitFor(() => {
      expect(result.current.ready).toBe(true);
    });
    expect(result.current.done.bluestacks).toBe(false);

    act(() => {
      result.current.setScan(found("D:\\portable\\adb.exe"));
    });
    // A scan that found a different adb has not been accepted yet: the step has to write
    // it before the rail may tick it.
    expect(result.current.done.bluestacks).toBe(false);

    act(() => {
      result.current.setScan(found(ADB));
    });
    expect(result.current.done.bluestacks).toBe(true);
  });

  it("walks forward and back, and counts Stats done once it has been skipped", async () => {
    const settings = makeSettings();
    settings.connection.brawl_api_token = "";
    settings.instances = [{ name: "Pie64", adb_port: 5555, player_tag: "" }];
    const { result } = mount(settings);
    await waitFor(() => {
      expect(result.current.ready).toBe(true);
    });
    expect(result.current.step).toBe("display");
    expect(result.current.done.stats).toBe(false);

    act(() => {
      result.current.next();
    });
    expect(result.current.step).toBe("stats");
    act(() => {
      result.current.skipStats();
    });
    expect(result.current.done.stats).toBe(true);

    act(() => {
      result.current.next();
    });
    expect(result.current.step).toBe("done");
    expect(result.current.index).toBe(4);
    // The last step has nowhere further to go.
    act(() => {
      result.current.next();
    });
    expect(result.current.step).toBe("done");

    act(() => {
      result.current.back();
    });
    expect(result.current.step).toBe("stats");
    act(() => {
      result.current.go("bluestacks");
    });
    expect(result.current.step).toBe("bluestacks");
    act(() => {
      result.current.back();
    });
    expect(result.current.step).toBe("bluestacks");
  });
});
```

Create `brawlfarm/web/src/setup/StepRail.test.tsx`:

```tsx
/** The five steps down the side: where you are, what is finished, and what you may not
 * skip to. */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { StepRail } from "./StepRail";
import type { StepId } from "./useSetupState";

const NONE: Record<StepId, boolean> = {
  bluestacks: false,
  instances: false,
  display: false,
  stats: false,
  done: false,
};

describe("StepRail", () => {
  it("names the five steps in order", () => {
    render(<StepRail index={0} done={NONE} onGo={() => undefined} />);
    expect(screen.getAllByRole("button").map((button) => button.textContent)).toEqual([
      "BlueStacks",
      "Instances",
      "Display",
      "Stats",
      "Done",
    ]);
  });

  it("marks the step you are on and checks the ones already finished", () => {
    render(
      <StepRail index={2} done={{ ...NONE, bluestacks: true, instances: true }} onGo={() => undefined} />,
    );
    expect(screen.getByRole("button", { name: "Display" })).toHaveAttribute(
      "aria-current",
      "step",
    );
    expect(screen.getByRole("button", { name: "BlueStacks" })).not.toHaveAttribute(
      "aria-current",
    );
    // The check is decoration: the name a screen reader reads is still the label.
    const rail = screen.getByRole("list");
    expect(rail.querySelectorAll("svg[aria-hidden='true']")).toHaveLength(2);
  });

  it("lets you go back but not skip forward", async () => {
    const gone: StepId[] = [];
    render(<StepRail index={2} done={NONE} onGo={(id) => gone.push(id)} />);
    expect(screen.getByRole("button", { name: "Stats" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Done" })).toBeDisabled();

    await userEvent.click(screen.getByRole("button", { name: "Stats" }));
    expect(gone).toEqual([]);

    await userEvent.click(screen.getByRole("button", { name: "BlueStacks" }));
    expect(gone).toEqual(["bluestacks"]);
  });
});
```

`StepRail` takes plain props rather than the whole `SetupState`, so this file needs no query
client, no router and no fetch stub: it is the one piece of the wizard that is pure.

Create `brawlfarm/web/src/setup/StepBlueStacks.test.tsx`:

```tsx
/** Step 1 end to end, through the real frame: the scan on entry, what it says while it
 * runs, the path it writes, and the field it falls back to. */
import { renderHook, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Setup } from "./Setup";
import type { AppSettings, ScanResponse } from "../api/types";
import { resetToasts, useToasts } from "../lib/toast";
import { makeSettings } from "../test/fixtures";
import { type FetchCall, jsonResponse, stubFetch } from "../test/http";
import { renderWithProviders } from "../test/renderWithProviders";

const ADB = "C:\\Program Files\\BlueStacks_nxt\\HD-Adb.exe";
const SCAN = "/api/setup/scan";

const FOUND: ScanResponse = {
  adb_path: ADB,
  adb_found: true,
  conf_found: true,
  instances: [],
};

const MISSING: ScanResponse = {
  adb_path: null,
  adb_found: false,
  conf_found: false,
  instances: [],
};

/** A settings route with a memory and a scan route the test drives by hand, so the
 * "Scanning" state can be looked at before the answer lands. */
function server(scans: (ScanResponse | "hold")[]) {
  const blank = makeSettings({ instances: [] });
  blank.connection.adb_path = "";
  let stored = blank;
  let held: ((response: Response) => void) | null = null;
  let at = 0;
  const { calls } = stubFetch((url, init) => {
    if (url === SCAN) {
      const answer = scans[Math.min(at, scans.length - 1)];
      at += 1;
      if (answer === "hold") {
        return new Promise<Response>((resolve) => {
          held = resolve;
        });
      }
      return jsonResponse(answer);
    }
    if (url !== "/api/settings") throw new Error(`unstubbed request: ${url}`);
    if (init?.method !== "PUT") return jsonResponse(stored);
    stored = JSON.parse(String(init.body)) as AppSettings;
    return jsonResponse(stored);
  });
  return {
    calls,
    current: () => stored,
    release: (answer: ScanResponse) => held?.(jsonResponse(answer)),
  };
}

function scanBodies(calls: FetchCall[]): unknown[] {
  return calls
    .filter((call) => call.url === SCAN)
    .map((call) => JSON.parse(String(call.init?.body)) as unknown);
}

function toastMessages(): string[] {
  return renderHook(() => useToasts()).result.current.map((item) => item.message);
}

afterEach(() => {
  resetToasts();
  vi.unstubAllGlobals();
});

describe("Setup step 1: BlueStacks", () => {
  it("says what it is doing while the scan runs, then shows what it found", async () => {
    const { release } = server(["hold"]);
    renderWithProviders(<Setup />, { route: "/setup" });
    expect(await screen.findByText("BlueStacks")).toBeInTheDocument();
    expect(screen.getByText("brawlfarm talks to BlueStacks through adb.")).toBeInTheDocument();
    expect(await screen.findByText("Scanning")).toBeInTheDocument();
    expect(screen.getByText("Asking adb for devices")).toBeInTheDocument();

    release(FOUND);
    expect(await screen.findByText("Found")).toBeInTheDocument();
    expect(screen.getByText(ADB)).toBeInTheDocument();
    expect(screen.queryByText("Scanning")).not.toBeInTheDocument();
  });

  it("writes the path it found to config.toml and opens Continue", async () => {
    const { calls, current } = server([FOUND]);
    renderWithProviders(<Setup />, { route: "/setup" });
    expect(await screen.findByText("Found")).toBeInTheDocument();
    await waitFor(() => {
      expect(current().connection.adb_path).toBe(ADB);
    });
    await waitFor(() => {
      expect(toastMessages()).toEqual(["Saved to config.toml"]);
    });
    expect(screen.getByRole("button", { name: "Continue" })).toBeEnabled();
    // The first scan is the configured one: no adb_path key until the reader types one.
    expect(scanBodies(calls)).toEqual([{}]);
  });

  it("asks where BlueStacks is when no adb was found, and re-scans with what was typed", async () => {
    const { calls } = server([MISSING, FOUND]);
    renderWithProviders(<Setup />, { route: "/setup" });
    const box = await screen.findByLabelText("Where is BlueStacks installed");
    expect(box).toHaveAttribute("placeholder", ADB);
    expect(
      screen.getByText("brawlfarm needs HD-Adb.exe from the BlueStacks folder."),
    ).toBeInTheDocument();

    await userEvent.type(box, "D:\\portable\\adb.exe");
    await userEvent.click(screen.getByRole("button", { name: "Scan again" }));
    await waitFor(() => {
      expect(scanBodies(calls)).toHaveLength(2);
    });
    expect(scanBodies(calls)[1]).toEqual({ adb_path: "D:\\portable\\adb.exe" });
    expect(await screen.findByText("Found")).toBeInTheDocument();
  });

  it("keeps Continue shut, with the reason, until adb is found", async () => {
    server([MISSING]);
    renderWithProviders(<Setup />, { route: "/setup" });
    const forward = await screen.findByRole("button", { name: "Continue" });
    expect(forward).toBeDisabled();
    expect(forward).toHaveAttribute("title", "Find HD-Adb.exe first");
    expect(screen.queryByText("Found")).not.toBeInTheDocument();
    expect(toastMessages()).toEqual([]);
  });
});
```

Append one case to `brawlfarm/web/src/App.test.tsx`, inside its existing top-level
`describe`:

```tsx
  it("puts the wizard on its own page, outside the shell", async () => {
    stubApi();
    window.history.pushState({}, "", "/setup");
    render(<App />);
    expect(await screen.findByText("BlueStacks")).toBeInTheDocument();
    // No rail, no top bar, no alerts drawer: there is no fleet to frame yet.
    expect(screen.queryByRole("link", { name: "Fleet" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Alerts/ })).not.toBeInTheDocument();
    window.history.pushState({}, "", "/");
  });
```

`stubApi` is the file's existing helper; it answers `/api/settings` and `/api/instances`.
Add one line to it so the wizard's scan has an answer, right before its `throw`:

```tsx
    if (url === "/api/setup/scan") {
      return jsonResponse({ adb_path: "adb.exe", adb_found: true, conf_found: true, instances: [] });
    }
```

The `pushState` back to `/` at the end matters: `App` mounts a `BrowserRouter`, and jsdom's
location is shared by every case in the file.

- [ ] **Step 2: Run the four files to confirm they fail**

```bash
pnpm --dir brawlfarm/web test src/setup/useSetupState.test.tsx src/setup/StepRail.test.tsx src/setup/StepBlueStacks.test.tsx src/App.test.tsx
```

Expected: FAIL. The three setup files fail to collect at all, with
`Failed to resolve import "./useSetupState"`, `"./StepRail"` and `"./Setup"`; `App.test.tsx`
collects and fails its new case with `Unable to find an element with the text: BlueStacks`,
because `/setup` matches no route yet.

- [ ] **Step 3: Write the state**

Create `brawlfarm/web/src/setup/useSetupState.ts`:

```ts
/**
 * The wizard's five steps, where it opens, and the one save every step shares.
 *
 * The steps live in component state rather than in the URL. There is one route, and a
 * half-finished setup is not a place worth linking to or going back to with the browser's
 * Back button, which here means "leave the wizard", not "undo step 3".
 *
 * Where it opens is derived from what is on disk, not from the scan: the scan has not
 * answered when the wizard mounts, and a wizard that jumped a step half a second after it
 * appeared would be worse than one that always starts at the top. The done table below is
 * the other question, what the rail may tick, and that one does wait for the scan.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ApiError } from "../api/client";
import type { AppSettings, ScanResponse } from "../api/types";
import type { SettingsPatch } from "../settings/useSettingsPatch";
import { toast } from "../lib/toast";

export type StepId = "bluestacks" | "instances" | "display" | "stats" | "done";

export interface SetupStep {
  id: StepId;
  label: string;
}

export const SETUP_STEPS: readonly SetupStep[] = [
  { id: "bluestacks", label: "BlueStacks" },
  { id: "instances", label: "Instances" },
  { id: "display", label: "Display" },
  { id: "stats", label: "Stats" },
  { id: "done", label: "Done" },
];

export interface SetupState {
  step: StepId;
  index: number;
  ready: boolean;
  done: Record<StepId, boolean>;
  go: (id: StepId) => void;
  next: () => void;
  back: () => void;
  scan: ScanResponse | null;
  setScan: (scan: ScanResponse | null) => void;
  skipStats: () => void;
  settingsPatch: SettingsPatch;
}

/** Every step takes the same one prop, and the frame is typed against it. It is declared
 * here and not in Setup.tsx because Setup.tsx imports the steps. */
export interface StepProps {
  setup: SetupState;
}

/**
 * The wizard's save, and the reason the wizard does not call Settings' saveSetting: the
 * toast is "Saved to config.toml" here, because on this page the reader has not been
 * anywhere called Settings and the reassurance they need is that it is already on disk.
 * A 422 is swallowed for the same reason it is there: useSettingsPatch has already put the
 * message under the field that caused it.
 */
export function saveStepAsync(
  patch: SettingsPatch["patch"],
  mutate: (draft: AppSettings) => void,
  onFailure: (error: unknown) => void,
): Promise<void> {
  return patch(mutate).then(
    () => {
      toast("Saved to config.toml");
    },
    (error: unknown) => {
      if (!(error instanceof ApiError && error.status === 422)) onFailure(error);
      throw error;
    },
  );
}

/** The same save for a caller with nothing to wait on. */
export function saveStep(
  patch: SettingsPatch["patch"],
  mutate: (draft: AppSettings) => void,
  onFailure: (error: unknown) => void,
): void {
  void saveStepAsync(patch, mutate, onFailure).catch(() => undefined);
}

export function useSetupState(settingsPatch: SettingsPatch): SetupState {
  const { settings } = settingsPatch;
  const [scan, setScan] = useState<ScanResponse | null>(null);
  const [step, setStep] = useState<StepId | null>(null);
  // State and not a ref: the rail has to re-render when Stats is skipped. It is still
  // "this visit only" in the sense that matters, which is that nothing is written to disk.
  const [statsSkipped, setStatsSkipped] = useState(false);
  const landed = useRef(false);

  useEffect(() => {
    if (landed.current || settings === undefined) return;
    landed.current = true;
    if (settings.connection.adb_path === "") setStep("bluestacks");
    else if (settings.instances.length === 0) setStep("instances");
    else setStep("display");
  }, [settings]);

  const done = useMemo<Record<StepId, boolean>>(
    () => ({
      // The step writes the path it found, so this turns true on the first pass without
      // anyone pressing anything.
      bluestacks: scan !== null && scan.adb_found && settings?.connection.adb_path === scan.adb_path,
      instances: (settings?.instances.length ?? 0) > 0,
      // Never stored, so never already done: it re-runs on every visit.
      display: false,
      stats:
        (settings?.connection.brawl_api_token ?? "") !== "" ||
        (settings?.instances.some((instance) => instance.player_tag !== "") ?? false) ||
        statsSkipped,
      // Reaching it is all it means, and you cannot reach it without being on it.
      done: false,
    }),
    [scan, settings, statsSkipped],
  );

  const current = step ?? "bluestacks";
  const index = SETUP_STEPS.findIndex((entry) => entry.id === current);

  const next = useCallback(() => {
    setStep((at) => {
      const from = SETUP_STEPS.findIndex((entry) => entry.id === (at ?? "bluestacks"));
      return SETUP_STEPS[Math.min(from + 1, SETUP_STEPS.length - 1)].id;
    });
  }, []);

  const back = useCallback(() => {
    setStep((at) => {
      const from = SETUP_STEPS.findIndex((entry) => entry.id === (at ?? "bluestacks"));
      return SETUP_STEPS[Math.max(from - 1, 0)].id;
    });
  }, []);

  return {
    step: current,
    index,
    ready: settings !== undefined,
    done,
    go: setStep,
    next,
    back,
    scan,
    setScan,
    skipStats: () => setStatsSkipped(true),
    settingsPatch,
  };
}
```

- [ ] **Step 4: Write the rail**

Create `brawlfarm/web/src/setup/StepRail.tsx`:

```tsx
/**
 * The five steps down the side of the wizard.
 *
 * Buttons, not links: there is one route, and a link that does not change the address bar
 * lies to the middle mouse button. A step at or before the one you are on is pressable, so
 * you can go back and check what you typed; a later one is disabled, because the wizard
 * cannot show you step 3 before it knows which instances step 2 picked.
 */
import { Check } from "lucide-react";

import { SETUP_STEPS, type StepId } from "./useSetupState";

export interface StepRailProps {
  index: number;
  done: Record<StepId, boolean>;
  onGo: (id: StepId) => void;
}

export function StepRail({ index, done, onGo }: StepRailProps) {
  return (
    <ol className="flex gap-1 overflow-x-auto min-[820px]:w-[180px] min-[820px]:flex-col min-[820px]:overflow-visible">
      {SETUP_STEPS.map((step, at) => {
        const here = at === index;
        const reachable = at <= index;
        return (
          <li key={step.id}>
            <button
              type="button"
              disabled={!reachable}
              aria-current={here ? "step" : undefined}
              onClick={() => onGo(step.id)}
              className={`inline-flex w-full items-center gap-2 whitespace-nowrap rounded-[6px] px-2 py-1.5 text-left text-[13px] transition-colors duration-[120ms] disabled:cursor-not-allowed disabled:opacity-50 ${
                here ? "bg-panel-2 text-accent" : "text-muted hover:text-text"
              }`}
            >
              {done[step.id] && <Check aria-hidden="true" size={16} strokeWidth={1.6} />}
              {step.label}
            </button>
          </li>
        );
      })}
    </ol>
  );
}
```

- [ ] **Step 5: Write the frame**

Create `brawlfarm/web/src/setup/Setup.tsx`:

```tsx
/**
 * The wizard's page.
 *
 * Its own chrome, not the Shell's: someone on this page has no fleet, and a rail listing
 * nothing with a top bar titled nothing is worse than a plain page. The wordmark is the
 * same one the rail carries, so it is recognisably the same program.
 *
 * STEP_VIEWS is Partial while the branch is being built. Task 10 fills the last of it in
 * and makes it a total Record, which is what then proves no step is missing.
 */
import type { ReactElement } from "react";

import { StepBlueStacks } from "./StepBlueStacks";
import { StepRail } from "./StepRail";
import { type StepId, type StepProps, useSetupState } from "./useSetupState";
import { useSettingsPatch } from "../settings/useSettingsPatch";

type StepView = (props: StepProps) => ReactElement;

const STEP_VIEWS: Partial<Record<StepId, StepView>> = {
  bluestacks: StepBlueStacks,
};

export function Setup() {
  const settingsPatch = useSettingsPatch();
  const setup = useSetupState(settingsPatch);
  const View = STEP_VIEWS[setup.step];

  return (
    <div className="min-h-screen bg-ground text-text">
      <header className="border-b border-line px-4 py-3">
        <span className="text-[15px] font-semibold tracking-tight">brawlfarm</span>
      </header>
      <main className="mx-auto flex max-w-[880px] flex-col gap-6 p-4 min-[820px]:flex-row">
        <StepRail index={setup.index} done={setup.done} onGo={setup.go} />
        <section className="min-w-0 flex-1">
          {settingsPatch.sectionErrors.map((line) => (
            <p key={line} className="mb-2 text-[12px] text-bad">
              {line}
            </p>
          ))}
          {setup.ready && View !== undefined && <View setup={setup} />}
        </section>
      </main>
    </div>
  );
}
```

- [ ] **Step 6: Write step 1**

Create `brawlfarm/web/src/setup/StepBlueStacks.tsx`. The scan lives in a `useCallback` so the
effect that runs it on entry and the "Scan again" button go through exactly the same code:

```tsx
/**
 * Step 1: find adb.
 *
 * The scan runs once when the step appears, and again only when it is asked to. It shells
 * out to adb and can take seconds, which is why the waiting state is a chip and a sentence
 * rather than a spinner: a sentence says what is being waited for.
 *
 * A scan that found adb writes the path it found, so the reader never has to press Save and
 * the next visit starts from what worked. The write is skipped when the path is already the
 * stored one, so a second Scan again does not raise a second toast about a file that has
 * not moved.
 */
import { useCallback, useEffect, useRef, useState } from "react";

import { type StepProps, saveStep } from "./useSetupState";
import { scanSetup } from "../api/setup";
import type { ScanResponse } from "../api/types";
import { Button } from "../components/ui/Button";
import { Chip } from "../components/ui/Chip";
import { ErrorBlock } from "../components/ui/ErrorBlock";
import { Field } from "../components/ui/Field";

const DEFAULT_ADB_PATH = "C:\\Program Files\\BlueStacks_nxt\\HD-Adb.exe";

export function StepBlueStacks({ setup }: StepProps) {
  const { setScan, next, settingsPatch } = setup;
  const { patch, settings } = settingsPatch;
  const [scanning, setScanning] = useState(true);
  const [result, setResult] = useState<ScanResponse | null>(null);
  const [typed, setTyped] = useState("");
  const [failure, setFailure] = useState<unknown>(null);
  // Read inside the callback rather than closed over, so re-scanning does not need a new
  // callback every time the document changes.
  const stored = useRef("");
  stored.current = settings?.connection.adb_path ?? "";

  const run = useCallback(
    (adbPath: string | undefined) => {
      setScanning(true);
      setFailure(null);
      void scanSetup(adbPath).then(
        (found) => {
          setScanning(false);
          setResult(found);
          setScan(found);
          if (found.adb_found && found.adb_path !== null && found.adb_path !== stored.current) {
            const path = found.adb_path;
            saveStep(
              patch,
              (draft) => {
                draft.connection.adb_path = path;
              },
              setFailure,
            );
          }
        },
        (error: unknown) => {
          setScanning(false);
          setResult(null);
          setScan(null);
          setFailure(error);
        },
      );
    },
    [patch, setScan],
  );

  useEffect(() => {
    run(undefined);
  }, [run]);

  const foundPath = result !== null && result.adb_found ? result.adb_path : null;

  return (
    <div>
      <h1 className="text-[18px] font-semibold">BlueStacks</h1>
      <p className="mt-1 text-[13px] text-muted">brawlfarm talks to BlueStacks through adb.</p>

      <div className="mt-4 space-y-3">
        {failure !== null && <ErrorBlock error={failure} />}

        {scanning && (
          <div className="flex items-center gap-2">
            <Chip tone="idle">Scanning</Chip>
            <span className="text-[12px] text-muted">Asking adb for devices</span>
          </div>
        )}

        {!scanning && foundPath !== null && (
          <div className="flex flex-wrap items-center gap-2">
            <Chip tone="ok">Found</Chip>
            <span className="font-mono text-[12px] text-text">{foundPath}</span>
          </div>
        )}

        {!scanning && foundPath === null && (
          <div className="space-y-2">
            <Field
              label="Where is BlueStacks installed"
              id="setup-adb-path"
              value={typed}
              onChange={setTyped}
              width="full"
              placeholder={DEFAULT_ADB_PATH}
            />
            <p className="text-[12px] text-muted">
              brawlfarm needs HD-Adb.exe from the BlueStacks folder.
            </p>
          </div>
        )}
      </div>

      <div className="mt-5 flex items-center gap-2">
        <Button variant="quiet" disabled={scanning} onClick={() => run(typed === "" ? undefined : typed)}>
          Scan again
        </Button>
        <Button
          variant="primary"
          disabled={foundPath === null}
          disabledReason="Find HD-Adb.exe first"
          onClick={next}
        >
          Continue
        </Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 7: Put the wizard beside the shell**

In `brawlfarm/web/src/App.tsx`, add the import and give `Panel` two routes:

```tsx
import { Setup } from "./setup/Setup";
```

```tsx
function Panel() {
  useThemeBootstrap();
  useLiveHandlers();

  // The wizard is deliberately outside ShellRoutes: it is the one page with no fleet
  // behind it, so it carries its own chrome.
  return (
    <Routes>
      <Route path="/setup" element={<Setup />} />
      <Route path="*" element={<ShellRoutes />} />
    </Routes>
  );
}
```

`ShellRoutes` keeps its own `<Routes>`: a `*` route renders it for every other path, and the
inner `Routes` then picks the screen. That is the declarative-mode way to nest, and it is why
task 5 pulled `ShellRoutes` out in the first place.

- [ ] **Step 8: Run the four files, then everything**

```bash
pnpm --dir brawlfarm/web test src/setup/useSetupState.test.tsx src/setup/StepRail.test.tsx src/setup/StepBlueStacks.test.tsx src/App.test.tsx
pnpm --dir brawlfarm/web typecheck
pnpm --dir brawlfarm/web test
pnpm --dir brawlfarm/web build
```

Expected: `useSetupState.test.tsx` at 4, `StepRail.test.tsx` at 3, `StepBlueStacks.test.tsx`
at 4 and `App.test.tsx` at 9, all passing. `tsc --noEmit` prints nothing. The whole suite is
50 files and 357 tests (47 and 345 after task 7). `vite build` writes
`brawlfarm/web/dist/index.html`.

- [ ] **Step 9: Look at it**

```bash
pnpm --dir brawlfarm/web build
uv run brawlfarm --no-browser
```

Open `http://127.0.0.1:8765/setup` against the real BlueStacks install: the page has no rail
and no top bar, the chip says Scanning for as long as adb takes, then Found with the real
path in mono, and the toast says "Saved to config.toml". Press Scan again: it scans once
more and, because the path has not moved, raises no second toast. Tab through the page and
confirm every control takes focus in reading order with a visible ring.

- [ ] **Step 10: Commit**

```bash
uv run python tools/scrub_check.py && git add brawlfarm/web/src && git commit -m "feat(web): the setup wizard's frame, its step rail and step 1

One route, five steps in component state, and its own chrome: someone on
this page has no fleet, so the shell's rail and top bar would frame
nothing. Where the wizard opens is derived from config.toml rather than
from the scan, because the scan has not answered when the page mounts and
a wizard that jumps a step half a second after it appears is worse than
one that always starts at the top. The rail's ticks do wait for the scan,
which is the other question entirely.

Step 1 scans on entry, says what it is waiting for rather than spinning,
and writes the path it found so nobody has to press Save. It skips the
write when the path has not moved, so a second Scan again does not claim
to have saved something that was already there. The wizard's own save
toasts \"Saved to config.toml\", because on this page there is no Settings
screen to have saved anything to.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CQ1GimQ3uiR2sXPzfZLNWV"
```

Expected: `0 hit(s)`, then the commit.

---

### Task 9: Wizard steps 2 and 3

The second half of the brief's task 6. Picking the instances, and proving each one is the
size the vision code assumes.

These two are one task because they share a shape: both read the ports out of what step 1
found, both probe adb per row, and both are the only steps where a wrong answer has to stay
on screen next to the row that produced it.

Accepted proposal ids covered: `wiz-instances`, `wiz-display`.

**Files:**
- Create: `brawlfarm/web/src/setup/StepInstances.tsx`
- Create: `brawlfarm/web/src/setup/StepDisplay.tsx`
- Modify: `brawlfarm/web/src/setup/Setup.tsx` (two entries in `STEP_VIEWS`)
- Test: `brawlfarm/web/src/setup/StepInstances.test.tsx` (create)
- Test: `brawlfarm/web/src/setup/StepDisplay.test.tsx` (create)

**Interfaces:**
- Consumes: task 8's `StepProps`, `saveStep`, `SetupState`; task 5's `scanSetup`, `testPort`,
  `checkDisplay`; task 1's `Table`, `Column`, `Field`; the phase 4 `Button`, `Chip`,
  `ErrorBlock`.
- Produces:
  - `setup/StepInstances.tsx`: `StepInstances`
  - `setup/StepDisplay.tsx`: `StepDisplay`
- Consumed by: task 10 (`STEP_VIEWS` gains the last two, and the summary on step 5 counts
  the instances step 2 wrote).

- [ ] **Step 1: Write the failing tests**

Create `brawlfarm/web/src/setup/StepInstances.test.tsx`:

```tsx
/** Step 2: the table of what BlueStacks has, testing a row, adding a port by hand, and
 * what Continue writes. */
import { renderHook, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Setup } from "./Setup";
import type { AppSettings, ScanResponse } from "../api/types";
import { resetToasts, useToasts } from "../lib/toast";
import { makeSettings } from "../test/fixtures";
import { type FetchCall, jsonResponse, stubFetch } from "../test/http";
import { renderWithProviders } from "../test/renderWithProviders";

const SCAN = "/api/setup/scan";
const TEST = "/api/setup/test";

const TWO: ScanResponse = {
  adb_path: "adb.exe",
  adb_found: true,
  conf_found: true,
  instances: [
    {
      name: "Pie64",
      display_name: "Nougat 64",
      adb_port: 5555,
      width: 1600,
      height: 900,
      dpi: 240,
      online: true,
    },
    {
      name: "Pie64_3",
      display_name: "Nougat 64 3",
      adb_port: 5585,
      width: null,
      height: null,
      dpi: null,
      online: false,
    },
  ],
};

const NONE: ScanResponse = {
  adb_path: "adb.exe",
  adb_found: true,
  conf_found: false,
  instances: [],
};

/** A settings document that lands the wizard on step 2: an adb path, and no fleet yet. */
function server(options: { scan?: ScanResponse; test?: { ok: boolean; detail: string } } = {}) {
  let stored = makeSettings({ instances: [] });
  const { calls } = stubFetch((url, init) => {
    if (url === SCAN) return jsonResponse(options.scan ?? TWO);
    if (url === TEST) {
      return jsonResponse(options.test ?? { ok: true, detail: "127.0.0.1:5555 answered" });
    }
    // Continue lands on step 3, which checks every instance it was handed.
    if (url === "/api/setup/display-check") {
      return jsonResponse({
        ok: true,
        width: 1600,
        height: 900,
        dpi: 240,
        detail: "1600x900 at 240 dpi",
        hint: "",
        expected: { width: 1600, height: 900, dpi: 240 },
      });
    }
    if (url !== "/api/settings") throw new Error(`unstubbed request: ${url}`);
    if (init?.method !== "PUT") return jsonResponse(stored);
    stored = JSON.parse(String(init.body)) as AppSettings;
    return jsonResponse(stored);
  });
  return { calls, current: () => stored };
}

function bodies(calls: FetchCall[], url: string): unknown[] {
  return calls
    .filter((call) => call.url === url)
    .map((call) => JSON.parse(String(call.init?.body)) as unknown);
}

function puts(calls: FetchCall[]): AppSettings[] {
  return calls
    .filter((call) => call.url === "/api/settings" && call.init?.method === "PUT")
    .map((call) => JSON.parse(String(call.init?.body)) as AppSettings);
}

function toastMessages(): string[] {
  return renderHook(() => useToasts()).result.current.map((item) => item.message);
}

/** The <tr> an instance sits in, found by its checkbox: a hand-added row is named after
 * its port, so its name appears in two cells and getByText would be ambiguous. */
function row(name: string): HTMLElement {
  const cell = screen.getByRole("checkbox", { name }).closest("tr");
  if (cell === null) throw new Error(`no row for ${name}`);
  return cell;
}

afterEach(() => {
  resetToasts();
  vi.unstubAllGlobals();
});

describe("Setup step 2: Instances", () => {
  it("lists what the scan found, with its columns and the status it starts from", async () => {
    server();
    renderWithProviders(<Setup />, { route: "/setup" });
    expect(await screen.findByText("Instances")).toBeInTheDocument();
    expect(
      screen.getByText("Pick the BlueStacks instances brawlfarm should farm."),
    ).toBeInTheDocument();
    expect(await screen.findByText("Pie64")).toBeInTheDocument();

    const headers = screen.getAllByRole("columnheader").map((cell) => cell.textContent);
    expect(headers).toEqual(["select", "Name", "Display name", "ADB port", "Status", "test"]);
    expect(within(row("Pie64")).getByText("Nougat 64")).toBeInTheDocument();
    expect(within(row("Pie64")).getByText("5555")).toBeInTheDocument();
    // The scan said this one answers, so it starts at Answers; the other was not probed
    // by the scan and has not been tested here either.
    expect(within(row("Pie64")).getByText("Answers")).toBeInTheDocument();
    expect(within(row("Pie64_3")).getByText("Not tested")).toBeInTheDocument();
    expect(
      screen.getByText("Enable ADB in BlueStacks: Settings, Advanced, Android Debug Bridge."),
    ).toBeInTheDocument();
    // No tag column here: tags are asked on step 4.
    expect(screen.queryByText("Player tag")).not.toBeInTheDocument();
  });

  it("tests one row and says what happened, with that row's own port", async () => {
    const { calls } = server({ test: { ok: false, detail: "127.0.0.1:5585: no answer" } });
    renderWithProviders(<Setup />, { route: "/setup" });
    expect(await screen.findByText("Pie64_3")).toBeInTheDocument();

    await userEvent.click(within(row("Pie64_3")).getByRole("button", { name: "Test" }));
    await waitFor(() => {
      expect(bodies(calls, TEST)).toEqual([{ adb_port: 5585 }]);
    });
    expect(await within(row("Pie64_3")).findByText("No answer")).toBeInTheDocument();
    expect(
      within(row("Pie64_3")).getByText("No answer on 5585. Is the instance running?"),
    ).toBeInTheDocument();
    // The other row is untouched by its neighbour's probe.
    expect(within(row("Pie64")).getByText("Answers")).toBeInTheDocument();
  });

  it("adds a port by hand and lets it be picked", async () => {
    const { calls } = server({ scan: NONE });
    renderWithProviders(<Setup />, { route: "/setup" });
    expect(
      await screen.findByText(
        "No instances found. Start a BlueStacks instance, enable ADB, then Scan again.",
      ),
    ).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Add a port" }));
    await userEvent.type(screen.getByLabelText("ADB port"), "5605");
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    expect(await screen.findByRole("checkbox", { name: "5605" })).toBeInTheDocument();
    expect(within(row("5605")).getByText("Not tested")).toBeInTheDocument();

    await userEvent.click(within(row("5605")).getByRole("checkbox"));
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    // Named after the port, which is the only thing known about it.
    expect(puts(calls)[0].instances).toEqual([
      { name: "5605", adb_port: 5605, player_tag: "" },
    ]);
  });

  it("keeps Continue shut until a row is ticked, then writes the ticked rows", async () => {
    const { calls, current } = server();
    renderWithProviders(<Setup />, { route: "/setup" });
    expect(await screen.findByText("Pie64")).toBeInTheDocument();
    const forward = screen.getByRole("button", { name: "Continue" });
    expect(forward).toBeDisabled();
    expect(forward).toHaveAttribute("title", "Select at least one instance");

    await userEvent.click(within(row("Pie64")).getByRole("checkbox"));
    await userEvent.click(within(row("Pie64_3")).getByRole("checkbox"));
    expect(forward).toBeEnabled();
    await userEvent.click(forward);
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    expect(puts(calls)[0].instances).toEqual([
      { name: "Pie64", adb_port: 5555, player_tag: "" },
      { name: "Pie64_3", adb_port: 5585, player_tag: "" },
    ]);
    expect(current().instances).toHaveLength(2);
    await waitFor(() => {
      expect(toastMessages()).toEqual(["Saved to config.toml"]);
    });
    // And it moved on: step 3 is on screen.
    expect(await screen.findByText("Display")).toBeInTheDocument();
  });

  it("re-scans on demand and goes back a step", async () => {
    const { calls } = server();
    renderWithProviders(<Setup />, { route: "/setup" });
    expect(await screen.findByText("Pie64")).toBeInTheDocument();
    expect(calls.filter((call) => call.url === SCAN)).toHaveLength(1);

    await userEvent.click(screen.getByRole("button", { name: "Scan again" }));
    await waitFor(() => {
      expect(calls.filter((call) => call.url === SCAN)).toHaveLength(2);
    });

    await userEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(await screen.findByText("brawlfarm talks to BlueStacks through adb.")).toBeInTheDocument();
  });
});
```

Create `brawlfarm/web/src/setup/StepDisplay.test.tsx`:

```tsx
/** Step 3: one card per instance, and the one sentence that says how to fix a wrong one. */
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Setup } from "./Setup";
import type { DisplayCheckResponse } from "../api/types";
import { makeSettings } from "../test/fixtures";
import { type FetchCall, jsonResponse, stubFetch } from "../test/http";
import { renderWithProviders } from "../test/renderWithProviders";

const CHECK = "/api/setup/display-check";
const EXPECTED = { width: 1600, height: 900, dpi: 240 };
const HINT =
  "Set the display to 1600 x 900 and pixel density 240 in BlueStacks: Settings, Display, " +
  "then restart the instance.";

const CORRECT: DisplayCheckResponse = {
  ok: true,
  width: 1600,
  height: 900,
  dpi: 240,
  detail: "1600x900 at 240 dpi",
  hint: HINT,
  expected: EXPECTED,
};

const WRONG: DisplayCheckResponse = {
  ok: false,
  width: 1920,
  height: 1080,
  dpi: 320,
  detail: "1920x1080 at 320 dpi",
  hint: HINT,
  expected: EXPECTED,
};

const UNKNOWN: DisplayCheckResponse = {
  ok: false,
  width: null,
  height: null,
  dpi: null,
  detail: "adb was not found; set its path in Connection",
  hint: HINT,
  expected: EXPECTED,
};

/** Two instances already in config.toml, so the wizard lands on step 3. `answers` is read
 * by port, and a port may answer differently the second time it is asked. */
function server(answers: Record<number, DisplayCheckResponse[]>) {
  const asked: Record<number, number> = {};
  const stored = makeSettings({
    instances: [
      { name: "Pie64", adb_port: 5555, player_tag: "" },
      { name: "Pie64_3", adb_port: 5585, player_tag: "" },
    ],
  });
  const { calls } = stubFetch((url, init) => {
    if (url === CHECK) {
      const port = (JSON.parse(String(init?.body)) as { adb_port: number }).adb_port;
      const queue = answers[port];
      const at = asked[port] ?? 0;
      asked[port] = at + 1;
      return jsonResponse(queue[Math.min(at, queue.length - 1)]);
    }
    if (url !== "/api/settings") throw new Error(`unstubbed request: ${url}`);
    return jsonResponse(stored);
  });
  return { calls };
}

function card(name: string): HTMLElement {
  const found = screen.getByText(name).closest("article");
  if (found === null) throw new Error(`no card for ${name}`);
  return found;
}

function checks(calls: FetchCall[]): number[] {
  return calls
    .filter((call) => call.url === CHECK)
    .map((call) => (JSON.parse(String(call.init?.body)) as { adb_port: number }).adb_port);
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Setup step 3: Display", () => {
  it("checks every instance and says Correct when it is", async () => {
    const { calls } = server({ 5555: [CORRECT], 5585: [CORRECT] });
    renderWithProviders(<Setup />, { route: "/setup" });
    expect(await screen.findByText("Display")).toBeInTheDocument();
    expect(
      screen.getByText("The farm reads the screen, so every instance has to be the same size."),
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(checks(calls).sort()).toEqual([5555, 5585]);
    });
    expect(await within(card("Pie64")).findByText("Correct")).toBeInTheDocument();
    expect(within(card("Pie64")).getByText("1600 x 900, pixel density 240")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Continue" })).toBeEnabled();
    // A card that is right does not repeat the fix.
    expect(screen.queryByText(HINT)).not.toBeInTheDocument();
  });

  it("shows what it measured and how to fix it when the size is wrong", async () => {
    server({ 5555: [CORRECT], 5585: [WRONG] });
    renderWithProviders(<Setup />, { route: "/setup" });
    expect(await within(card("Pie64_3")).findByText("Wrong size")).toBeInTheDocument();
    expect(
      within(card("Pie64_3")).getByText("1920 x 1080, pixel density 320"),
    ).toBeInTheDocument();
    expect(within(card("Pie64_3")).getByText(HINT)).toBeInTheDocument();
  });

  it("falls back to the API's own sentence when nothing could be measured", async () => {
    server({ 5555: [UNKNOWN], 5585: [UNKNOWN] });
    renderWithProviders(<Setup />, { route: "/setup" });
    expect(
      await within(card("Pie64")).findByText("adb was not found; set its path in Connection"),
    ).toBeInTheDocument();
    // The hint says "pixel density" too, so this pins the measured line's own shape.
    expect(
      within(card("Pie64")).queryByText(/^\d+ x \d+, pixel density \d+$/),
    ).not.toBeInTheDocument();
    expect(within(card("Pie64")).getByText(HINT)).toBeInTheDocument();
  });

  it("keeps Continue shut with its reason until Recheck finds every card correct", async () => {
    const { calls } = server({ 5555: [CORRECT], 5585: [WRONG, CORRECT] });
    renderWithProviders(<Setup />, { route: "/setup" });
    expect(await within(card("Pie64_3")).findByText("Wrong size")).toBeInTheDocument();
    const forward = screen.getByRole("button", { name: "Continue" });
    expect(forward).toBeDisabled();
    expect(forward).toHaveAttribute("title", "Fix the display first");

    await userEvent.click(within(card("Pie64_3")).getByRole("button", { name: "Recheck" }));
    await waitFor(() => {
      expect(checks(calls).filter((port) => port === 5585)).toHaveLength(2);
    });
    expect(await within(card("Pie64_3")).findByText("Correct")).toBeInTheDocument();
    await waitFor(() => {
      expect(forward).toBeEnabled();
    });
    // Nothing was saved: this step stores nothing at all.
    expect(calls.filter((call) => call.init?.method === "PUT")).toHaveLength(0);
  });
});
```

- [ ] **Step 2: Run both files to confirm they fail**

```bash
pnpm --dir brawlfarm/web test src/setup/StepInstances.test.tsx src/setup/StepDisplay.test.tsx
```

Expected: FAIL, 9 cases. Both collect, and both fail at their first `findBy`:
`Unable to find an element with the text: Instances` and
`Unable to find an element with the text: Display`, because `STEP_VIEWS` has no entry for
either step and the frame renders the rail with an empty section beside it.

- [ ] **Step 3: Write step 2**

Create `brawlfarm/web/src/setup/StepInstances.tsx`:

```tsx
/**
 * Step 2: which instances brawlfarm farms.
 *
 * The table is the scan's rows plus any port typed in by hand, because BlueStacks does not
 * always list an instance in bluestacks.conf and a port that answers is worth farming
 * whatever the file says. A hand-added row is named after its port: the name becomes a
 * folder name under the data home, and the port is the only thing actually known about it.
 *
 * The scan runs when the step appears only if step 1 did not already hand one over, so
 * walking forward from step 1 does not pay for a second round trip to adb.
 *
 * Testing a row is a real probe, per row, never per keystroke, and its answer replaces only
 * that row's status. The sentence under a failed probe names the row's own port, which is
 * what makes it actionable: "No answer on 5585" is a thing to go and look at.
 */
import { useCallback, useEffect, useState } from "react";

import { type StepProps, saveStep } from "./useSetupState";
import { scanSetup, testPort } from "../api/setup";
import type { ScanInstance } from "../api/types";
import { Button } from "../components/ui/Button";
import { Chip } from "../components/ui/Chip";
import { ErrorBlock } from "../components/ui/ErrorBlock";
import { Field } from "../components/ui/Field";
import { type Column, Table } from "../components/ui/Table";
import type { Tone } from "../lib/states";

type Status = "untested" | "testing" | "answers" | "no-answer";

const STATUS_LABEL: Record<Status, string> = {
  untested: "Not tested",
  testing: "Testing",
  answers: "Answers",
  "no-answer": "No answer",
};

const STATUS_TONE: Record<Status, Tone> = {
  untested: "idle",
  testing: "idle",
  answers: "ok",
  "no-answer": "bad",
};

export function StepInstances({ setup }: StepProps) {
  const { scan, setScan, back, next, settingsPatch } = setup;
  const { patch } = settingsPatch;
  const [rows, setRows] = useState<ScanInstance[]>(scan?.instances ?? []);
  const [picked, setPicked] = useState<string[]>([]);
  const [status, setStatus] = useState<Record<string, Status>>({});
  const [scanning, setScanning] = useState(false);
  const [adding, setAdding] = useState(false);
  const [port, setPort] = useState("");
  const [failure, setFailure] = useState<unknown>(null);

  const load = useCallback(
    (found: ScanInstance[]) => {
      setRows(found);
      setStatus(
        Object.fromEntries(
          found.map((row): [string, Status] => [row.name, row.online ? "answers" : "untested"]),
        ),
      );
      setPicked((kept) => kept.filter((name) => found.some((row) => row.name === name)));
    },
    [],
  );

  const run = useCallback(() => {
    setScanning(true);
    setFailure(null);
    void scanSetup().then(
      (found) => {
        setScanning(false);
        setScan(found);
        load(found.instances);
      },
      (error: unknown) => {
        setScanning(false);
        setFailure(error);
      },
    );
  }, [load, setScan]);

  // Once, on mount. Step 1 already scanned on the way here, so only a cold landing on
  // step 2 pays for one; and run() sets `scan`, so anything that watched it would loop.
  useEffect(() => {
    if (scan === null) run();
  }, []);

  const probe = (row: ScanInstance) => {
    if (row.adb_port === null) return;
    const adbPort = row.adb_port;
    setStatus((all) => ({ ...all, [row.name]: "testing" }));
    void testPort(adbPort).then(
      (answer) => {
        setStatus((all) => ({ ...all, [row.name]: answer.ok ? "answers" : "no-answer" }));
      },
      (error: unknown) => {
        setStatus((all) => ({ ...all, [row.name]: "no-answer" }));
        setFailure(error);
      },
    );
  };

  const addPort = () => {
    const value = Number(port);
    if (!Number.isInteger(value) || value < 1 || value > 65535) return;
    const name = String(value);
    if (rows.some((row) => row.name === name)) return;
    setRows((all) => [
      ...all,
      {
        name,
        display_name: "",
        adb_port: value,
        width: null,
        height: null,
        dpi: null,
        online: false,
      },
    ]);
    setStatus((all) => ({ ...all, [name]: "untested" }));
    setPort("");
    setAdding(false);
  };

  const toggle = (name: string) => {
    setPicked((all) => (all.includes(name) ? all.filter((one) => one !== name) : [...all, name]));
  };

  const forward = () => {
    const chosen = rows.filter(
      (row): row is ScanInstance & { adb_port: number } =>
        picked.includes(row.name) && row.adb_port !== null,
    );
    saveStep(
      patch,
      (draft) => {
        draft.instances = chosen.map((row) => ({
          name: row.name,
          adb_port: row.adb_port,
          player_tag: "",
        }));
      },
      setFailure,
    );
    next();
  };

  const columns: readonly Column<ScanInstance>[] = [
    {
      key: "select",
      label: "",
      width: "36px",
      render: (row) => (
        <input
          type="checkbox"
          aria-label={row.name}
          checked={picked.includes(row.name)}
          disabled={row.adb_port === null}
          onChange={() => toggle(row.name)}
          className="h-3.5 w-3.5 accent-[var(--accent)]"
        />
      ),
    },
    { key: "name", label: "Name", mono: true, render: (row) => row.name },
    { key: "display", label: "Display name", render: (row) => row.display_name },
    {
      key: "port",
      label: "ADB port",
      mono: true,
      width: "100px",
      render: (row) => (row.adb_port === null ? "" : String(row.adb_port)),
    },
    {
      key: "status",
      label: "Status",
      render: (row) => {
        const state = status[row.name] ?? "untested";
        return (
          <div className="space-y-1">
            <Chip tone={STATUS_TONE[state]}>{STATUS_LABEL[state]}</Chip>
            {state === "no-answer" && row.adb_port !== null && (
              <p className="text-[12px] text-muted">
                {`No answer on ${row.adb_port}. Is the instance running?`}
              </p>
            )}
          </div>
        );
      },
    },
    {
      key: "test",
      label: "",
      width: "72px",
      render: (row) => (
        <Button
          variant="text"
          size="sm"
          disabled={row.adb_port === null || status[row.name] === "testing"}
          disabledReason="This instance has no ADB port"
          onClick={() => probe(row)}
        >
          Test
        </Button>
      ),
    },
  ];

  return (
    <div>
      <h1 className="text-[18px] font-semibold">Instances</h1>
      <p className="mt-1 text-[13px] text-muted">
        Pick the BlueStacks instances brawlfarm should farm.
      </p>

      <div className="mt-4 space-y-3">
        {failure !== null && <ErrorBlock error={failure} />}
        <Table
          columns={columns}
          rows={rows}
          rowKey={(row) => row.name}
          empty="No instances found. Start a BlueStacks instance, enable ADB, then Scan again."
        />

        <div className="flex flex-wrap items-center gap-2">
          <Button variant="quiet" disabled={scanning} onClick={run}>
            Scan again
          </Button>
          <Button variant="text" size="sm" onClick={() => setAdding((on) => !on)}>
            Add a port
          </Button>
        </div>

        {adding && (
          <div className="flex flex-wrap items-end gap-2">
            <Field
              label="ADB port"
              id="setup-add-port"
              value={port}
              onChange={setPort}
              type="number"
              min={1}
            />
            <Button variant="quiet" onClick={addPort}>
              Add
            </Button>
          </div>
        )}

        <p className="text-[12px] text-muted">
          Enable ADB in BlueStacks: Settings, Advanced, Android Debug Bridge.
        </p>
      </div>

      <div className="mt-5 flex items-center gap-2">
        <Button variant="quiet" onClick={back}>
          Back
        </Button>
        <Button
          variant="primary"
          disabled={picked.length === 0}
          disabledReason="Select at least one instance"
          onClick={forward}
        >
          Continue
        </Button>
      </div>
    </div>
  );
}
```

That mount effect is deliberately dependency-free. `run` sets `scan`, so listing either of
them would re-run the scan forever; this repo has no eslint to argue with about it, and the
comment above it is there so nobody adds one and "fixes" it into a loop.

- [ ] **Step 4: Write step 3**

Create `brawlfarm/web/src/setup/StepDisplay.tsx`:

```tsx
/**
 * Step 3: every instance at 1600 x 900, pixel density 240.
 *
 * This is the one step that saves nothing. The controller asserts the size at startup and
 * exits otherwise, so the wizard's job here is to let someone find out now, with the
 * sentence that says where to change it, rather than later from a worker that quit.
 *
 * The fix sentence is the API's `hint`, rendered verbatim. It comes from
 * brawlfarm/setup/checks.py's DISPLAY_HINT, which is the one place that sentence is
 * written: a second copy here would drift the first time BlueStacks renames a menu.
 *
 * Each card checks itself and rechecks itself, and reports up only the one bit the step
 * needs, which is whether Continue may open.
 */
import { useCallback, useEffect, useState } from "react";

import { type StepProps } from "./useSetupState";
import { checkDisplay } from "../api/setup";
import type { DisplayCheckResponse } from "../api/types";
import { Button } from "../components/ui/Button";
import { Chip } from "../components/ui/Chip";
import { ErrorBlock } from "../components/ui/ErrorBlock";

function DisplayCard({
  name,
  port,
  onResult,
}: {
  name: string;
  port: number;
  onResult: (name: string, ok: boolean) => void;
}) {
  const [checking, setChecking] = useState(true);
  const [result, setResult] = useState<DisplayCheckResponse | null>(null);
  const [failure, setFailure] = useState<unknown>(null);

  const run = useCallback(() => {
    setChecking(true);
    setFailure(null);
    void checkDisplay(port).then(
      (answer) => {
        setChecking(false);
        setResult(answer);
        onResult(name, answer.ok);
      },
      (error: unknown) => {
        setChecking(false);
        setResult(null);
        setFailure(error);
        onResult(name, false);
      },
    );
  }, [name, port, onResult]);

  useEffect(() => {
    run();
  }, [run]);

  const measured =
    result === null || result.width === null || result.height === null || result.dpi === null
      ? (result?.detail ?? "")
      : `${result.width} x ${result.height}, pixel density ${result.dpi}`;

  return (
    <article className="rounded-[10px] border border-line bg-panel p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-[13px]">{name}</span>
        {checking ? (
          <Chip tone="idle">Checking</Chip>
        ) : (
          <Chip tone={result?.ok === true ? "ok" : "bad"}>
            {result?.ok === true ? "Correct" : "Wrong size"}
          </Chip>
        )}
      </div>
      {failure !== null && (
        <div className="mt-2">
          <ErrorBlock error={failure} />
        </div>
      )}
      {!checking && measured !== "" && (
        <p className="mt-1 font-mono text-[12px] tabular-nums text-muted">{measured}</p>
      )}
      {!checking && result !== null && !result.ok && (
        <p className="mt-1 text-[12px] text-muted">{result.hint}</p>
      )}
      <div className="mt-2">
        <Button variant="quiet" size="sm" disabled={checking} onClick={run}>
          Recheck
        </Button>
      </div>
    </article>
  );
}

export function StepDisplay({ setup }: StepProps) {
  const { back, next, settingsPatch } = setup;
  const instances = settingsPatch.settings?.instances ?? [];
  const [ok, setOk] = useState<Record<string, boolean>>({});

  const report = useCallback((name: string, good: boolean) => {
    setOk((all) => ({ ...all, [name]: good }));
  }, []);

  const allOk = instances.length > 0 && instances.every((one) => ok[one.name] === true);

  return (
    <div>
      <h1 className="text-[18px] font-semibold">Display</h1>
      <p className="mt-1 text-[13px] text-muted">
        The farm reads the screen, so every instance has to be the same size.
      </p>

      <div className="mt-4 space-y-2">
        {instances.map((one) => (
          <DisplayCard key={one.name} name={one.name} port={one.adb_port} onResult={report} />
        ))}
      </div>

      <div className="mt-5 flex items-center gap-2">
        <Button variant="quiet" onClick={back}>
          Back
        </Button>
        <Button
          variant="primary"
          disabled={!allOk}
          disabledReason="Fix the display first"
          onClick={next}
        >
          Continue
        </Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Put the two steps in the table**

In `brawlfarm/web/src/setup/Setup.tsx`, add the two imports and the two entries:

```tsx
import { StepBlueStacks } from "./StepBlueStacks";
import { StepDisplay } from "./StepDisplay";
import { StepInstances } from "./StepInstances";
import { StepRail } from "./StepRail";
```

```tsx
const STEP_VIEWS: Partial<Record<StepId, StepView>> = {
  bluestacks: StepBlueStacks,
  instances: StepInstances,
  display: StepDisplay,
};
```

- [ ] **Step 6: Run both files, then everything**

```bash
pnpm --dir brawlfarm/web test src/setup/StepInstances.test.tsx src/setup/StepDisplay.test.tsx
pnpm --dir brawlfarm/web typecheck
pnpm --dir brawlfarm/web test
pnpm --dir brawlfarm/web build
```

Expected: `StepInstances.test.tsx` at 5 and `StepDisplay.test.tsx` at 4, all passing.
`tsc --noEmit` prints nothing. The whole suite is 52 files and 366 tests (50 and 357 after
task 8). `vite build` writes `brawlfarm/web/dist/index.html`.

- [ ] **Step 7: Look at it against a real instance**

```bash
pnpm --dir brawlfarm/web build
uv run brawlfarm --no-browser
```

Open `http://127.0.0.1:8765/setup` and walk to step 2 against the real BlueStacks install:
the table lists the real instances with their real ports, Test on a running one goes green
within a couple of seconds, Test on a stopped one says "No answer on <port>. Is the instance
running?". Tick one, Continue, and confirm step 3 measures it. Set that instance's display to
something else in BlueStacks, restart it, press Recheck, and confirm the card turns red with
the hint sentence and Continue closes again.

- [ ] **Step 8: Commit**

```bash
uv run python tools/scrub_check.py && git add brawlfarm/web/src && git commit -m "feat(web): the wizard's instances and display steps

Step 2 lists what the scan found plus any port typed in by hand, because
BlueStacks does not always write an instance into bluestacks.conf and a
port that answers is worth farming whatever the file says. It scans on
entry only when step 1 did not already hand one over. Testing a row is a
real probe of that row, and a failure says the row's own port, which is
the part that makes it something to go and look at.

Step 3 saves nothing at all: the controller asserts 1600 x 900 at startup
and exits otherwise, so this step exists to let someone find out now. The
fix sentence is the API's hint rendered verbatim, so it stays the one
sentence in setup/checks.py rather than a second copy that drifts the
first time BlueStacks renames a menu.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CQ1GimQ3uiR2sXPzfZLNWV"
```

Expected: `0 hit(s)`, then the commit.

---

### Task 10: Wizard steps 4 and 5, and the way in from Fleet

The brief's task 7. The last two steps, and the door that makes the wizard reachable:
Fleet's empty state stops telling people to edit config.toml by hand.

`STEP_VIEWS` becomes a total `Record` at the end of this task, which is what then proves no
step is missing.

Accepted proposal ids covered: `wiz-token`, `wiz-done`, `wiz-entry`.

**Files:**
- Create: `brawlfarm/web/src/setup/StepStats.tsx`
- Create: `brawlfarm/web/src/setup/StepDone.tsx`
- Modify: `brawlfarm/web/src/setup/Setup.tsx` (`STEP_VIEWS` becomes total)
- Modify: `brawlfarm/web/src/fleet/Fleet.tsx` (the empty state)
- Test: `brawlfarm/web/src/setup/StepStats.test.tsx` (create)
- Test: `brawlfarm/web/src/setup/StepDone.test.tsx` (create)
- Test: `brawlfarm/web/src/fleet/Fleet.test.tsx` (modify: one case rewritten)

**Interfaces:**
- Consumes: task 8's `StepProps`, `saveStepAsync`, `SetupState`; task 2's `useDebouncedSave`
  and `fieldError`; task 1's `Field`; the phase 4 `Button`, `Switch`, `ErrorBlock`,
  `startInstance`, `toast`, `failureMessage`.
- Produces:
  - `setup/StepStats.tsx`: `StepStats`
  - `setup/StepDone.tsx`: `StepDone`
- Consumed by: task 11 (the keyboard and screenshot pass walks all five steps).

- [ ] **Step 1: Write the failing tests**

Create `brawlfarm/web/src/setup/StepStats.test.tsx`:

```tsx
/** Step 4: the optional token and one tag per instance, and the button that says no. */
import { fireEvent, renderHook, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Setup } from "./Setup";
import type { AppSettings } from "../api/types";
import { resetToasts, useToasts } from "../lib/toast";
import { makeSettings } from "../test/fixtures";
import { type FetchCall, jsonResponse, stubFetch } from "../test/http";
import { renderWithProviders } from "../test/renderWithProviders";

const CHECK = "/api/setup/display-check";

const CORRECT = {
  ok: true,
  width: 1600,
  height: 900,
  dpi: 240,
  detail: "1600x900 at 240 dpi",
  hint: "",
  expected: { width: 1600, height: 900, dpi: 240 },
};

function server(options: { putStatus?: number; putDetail?: string } = {}) {
  let stored = makeSettings({
    instances: [
      { name: "Pie64", adb_port: 5555, player_tag: "" },
      { name: "Pie64_3", adb_port: 5585, player_tag: "" },
    ],
  });
  stored.connection.brawl_api_token = "";
  const { calls } = stubFetch((url, init) => {
    if (url === CHECK) return jsonResponse(CORRECT);
    if (url !== "/api/settings") throw new Error(`unstubbed request: ${url}`);
    if (init?.method !== "PUT") return jsonResponse(stored);
    if (options.putStatus !== undefined) {
      return jsonResponse({ detail: options.putDetail }, options.putStatus);
    }
    stored = JSON.parse(String(init.body)) as AppSettings;
    return jsonResponse(stored);
  });
  return { calls, current: () => stored };
}

function puts(calls: FetchCall[]): AppSettings[] {
  return calls
    .filter((call) => call.url === "/api/settings" && call.init?.method === "PUT")
    .map((call) => JSON.parse(String(call.init?.body)) as AppSettings);
}

function toastMessages(): string[] {
  return renderHook(() => useToasts()).result.current.map((item) => item.message);
}

/** The wizard lands on step 3 with a fleet already in config.toml; one Continue gets to 4. */
async function walkToStats() {
  const forward = await screen.findByRole("button", { name: "Continue" });
  await waitFor(() => {
    expect(forward).toBeEnabled();
  });
  await userEvent.click(forward);
  expect(await screen.findByText("Stats (optional)")).toBeInTheDocument();
}

afterEach(() => {
  resetToasts();
  vi.unstubAllGlobals();
});

describe("Setup step 4: Stats", () => {
  it("asks for the token and one tag per instance, and links the key page", async () => {
    server();
    renderWithProviders(<Setup />, { route: "/setup" });
    await walkToStats();

    expect(
      screen.getByText(
        "A token and your player tags let brawlfarm show per-brawler stats. Farming works without them.",
      ),
    ).toBeInTheDocument();
    const token = screen.getByLabelText("Brawl Stars API token");
    expect(token).toHaveAttribute("type", "password");
    expect(token).toHaveAttribute("data-private");
    expect(screen.getByLabelText("Pie64")).toHaveAttribute("placeholder", "#TAG");
    expect(screen.getByLabelText("Pie64_3")).toHaveAttribute("placeholder", "#TAG");

    const line = screen.getByText(/Create a key at/);
    expect(line).toHaveTextContent(
      "Create a key at developer.brawlstars.com and allow this machine's IP address.",
    );
    expect(screen.getByRole("link", { name: "developer.brawlstars.com" })).toHaveAttribute(
      "href",
      "https://developer.brawlstars.com",
    );
  });

  it("saves the token and a tag on blur, one field at a time", async () => {
    const { calls, current } = server();
    renderWithProviders(<Setup />, { route: "/setup" });
    await walkToStats();

    const token = screen.getByLabelText("Brawl Stars API token");
    fireEvent.change(token, { target: { value: "a-token-that-is-not-real" } });
    fireEvent.blur(token);
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    expect(puts(calls)[0].connection.brawl_api_token).toBe("a-token-that-is-not-real");

    const tag = screen.getByLabelText("Pie64_3");
    fireEvent.change(tag, { target: { value: "#2P0YLQ9" } });
    fireEvent.blur(tag);
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(2);
    });
    // Only that instance's tag moved, and the token written a moment ago is still there.
    expect(puts(calls)[1].instances).toEqual([
      { name: "Pie64", adb_port: 5555, player_tag: "" },
      { name: "Pie64_3", adb_port: 5585, player_tag: "#2P0YLQ9" },
    ]);
    expect(puts(calls)[1].connection.brawl_api_token).toBe("a-token-that-is-not-real");
    expect(current().instances[1].player_tag).toBe("#2P0YLQ9");
    await waitFor(() => {
      expect(toastMessages()).toEqual(["Saved to config.toml", "Saved to config.toml"]);
    });
  });

  it("puts a refused tag under the field that carried it", async () => {
    const { calls } = server({
      putStatus: 422,
      putDetail: "instances.0.player_tag: tag must be 3 to 15 characters after the #",
    });
    renderWithProviders(<Setup />, { route: "/setup" });
    await walkToStats();

    const tag = screen.getByLabelText("Pie64");
    fireEvent.change(tag, { target: { value: "#X" } });
    fireEvent.blur(tag);
    await waitFor(() => {
      expect(puts(calls)).toHaveLength(1);
    });
    expect(
      await screen.findByText("player_tag: tag must be 3 to 15 characters after the #"),
    ).toBeInTheDocument();
    // The box keeps what is being fixed, and no toast claims it was saved.
    expect(tag).toHaveValue("#X");
    expect(toastMessages()).toEqual([]);
  });

  it("Skip for now moves on without writing anything", async () => {
    const { calls } = server();
    renderWithProviders(<Setup />, { route: "/setup" });
    await walkToStats();

    await userEvent.click(screen.getByRole("button", { name: "Skip for now" }));
    expect(await screen.findByText("Setup complete.")).toBeInTheDocument();
    expect(puts(calls)).toHaveLength(0);
    expect(toastMessages()).toEqual([]);
    // Skipped counts as finished, so the rail ticks it.
    expect(screen.getByRole("button", { name: "Stats" }).querySelector("svg")).not.toBeNull();
  });
});
```

Create `brawlfarm/web/src/setup/StepDone.test.tsx`:

```tsx
/** Step 5: what setup did, the one start it offers, and the way out. */
import { renderHook, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Setup } from "./Setup";
import type { AppSettings } from "../api/types";
import { resetToasts, useToasts } from "../lib/toast";
import { makeSettings } from "../test/fixtures";
import { type FetchCall, jsonResponse, stubFetch } from "../test/http";
import { renderWithProviders } from "../test/renderWithProviders";

const CHECK = "/api/setup/display-check";
const START = "/api/instances/Pie64/start";

const CORRECT = {
  ok: true,
  width: 1600,
  height: 900,
  dpi: 240,
  detail: "1600x900 at 240 dpi",
  hint: "",
  expected: { width: 1600, height: 900, dpi: 240 },
};

function server(settings: AppSettings, options: { startStatus?: number; startDetail?: string } = {}) {
  const { calls } = stubFetch((url) => {
    if (url === CHECK) return jsonResponse(CORRECT);
    if (url === START) {
      if (options.startStatus !== undefined) {
        return jsonResponse({ detail: options.startDetail }, options.startStatus);
      }
      return jsonResponse({ ok: true }, 202);
    }
    if (url !== "/api/settings") throw new Error(`unstubbed request: ${url}`);
    return jsonResponse(settings);
  });
  return { calls };
}

function fleet(): AppSettings {
  const settings = makeSettings({
    instances: [
      { name: "Pie64", adb_port: 5555, player_tag: "#2P0YLQ9" },
      { name: "Pie64_3", adb_port: 5585, player_tag: "" },
    ],
  });
  settings.connection.adb_path = "adb.exe";
  settings.connection.brawl_api_token = "a-token-that-is-not-real";
  return settings;
}

function mount() {
  return renderWithProviders(
    <Routes>
      <Route path="/setup" element={<Setup />} />
      <Route path="/" element={<p>Fleet screen</p>} />
    </Routes>,
    { route: "/setup" },
  );
}

/** Land on step 3, then two Continues to step 5. */
async function walkToDone() {
  const forward = await screen.findByRole("button", { name: "Continue" });
  await waitFor(() => {
    expect(forward).toBeEnabled();
  });
  await userEvent.click(forward);
  expect(await screen.findByText("Stats (optional)")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Continue" }));
  expect(await screen.findByText("Setup complete.")).toBeInTheDocument();
}

function starts(calls: FetchCall[]): FetchCall[] {
  return calls.filter((call) => call.url === START);
}

function toastMessages(): string[] {
  return renderHook(() => useToasts()).result.current.map((item) => item.message);
}

afterEach(() => {
  resetToasts();
  vi.unstubAllGlobals();
});

describe("Setup step 5: Done", () => {
  it("summarises what setup did", async () => {
    server(fleet());
    mount();
    await walkToDone();

    const summary = screen.getByRole("list", { name: "Setup summary" });
    expect(within(summary).getAllByRole("listitem").map((item) => item.textContent)).toEqual([
      "Instances: 2 Pie64, Pie64_3",
      "adb: adb.exe",
      "Token: set",
      "Player tags: 1 of 2 set",
    ]);
    expect(
      screen.getByText(
        "Each step already saved to config.toml, so you can close this and come back.",
      ),
    ).toBeInTheDocument();
    // The token is summarised, never shown.
    expect(screen.queryByText(/a-token-that-is-not-real/)).not.toBeInTheDocument();
  });

  it("says skipped and none when neither was given", async () => {
    const bare = fleet();
    bare.connection.brawl_api_token = "";
    bare.instances = [
      { name: "Pie64", adb_port: 5555, player_tag: "" },
      { name: "Pie64_3", adb_port: 5585, player_tag: "" },
    ];
    server(bare);
    mount();
    await walkToDone();

    const summary = screen.getByRole("list", { name: "Setup summary" });
    expect(within(summary).getAllByRole("listitem").map((item) => item.textContent)).toEqual([
      "Instances: 2 Pie64, Pie64_3",
      "adb: adb.exe",
      "Token: skipped",
      "Player tags: none",
    ]);
  });

  it("starts the first instance and opens the fleet", async () => {
    const { calls } = server(fleet());
    mount();
    await walkToDone();

    const toggle = screen.getByRole("switch", { name: "Start Pie64 now" });
    expect(toggle).toHaveAttribute("aria-checked", "true");
    await userEvent.click(screen.getByRole("button", { name: "Open Fleet" }));
    await waitFor(() => {
      expect(starts(calls)).toHaveLength(1);
    });
    expect(starts(calls)[0].init?.method).toBe("POST");
    expect(await screen.findByText("Fleet screen")).toBeInTheDocument();
  });

  it("opens the fleet without starting when the switch is off", async () => {
    const { calls } = server(fleet());
    mount();
    await walkToDone();

    await userEvent.click(screen.getByRole("switch", { name: "Start Pie64 now" }));
    await userEvent.click(screen.getByRole("button", { name: "Open Fleet" }));
    expect(await screen.findByText("Fleet screen")).toBeInTheDocument();
    expect(starts(calls)).toHaveLength(0);
  });

  it("still opens the fleet when the start was refused, and says why", async () => {
    const { calls } = server(fleet(), { startStatus: 409, startDetail: "Pie64 is already running" });
    mount();
    await walkToDone();

    await userEvent.click(screen.getByRole("button", { name: "Open Fleet" }));
    await waitFor(() => {
      expect(starts(calls)).toHaveLength(1);
    });
    expect(await screen.findByText("Fleet screen")).toBeInTheDocument();
    await waitFor(() => {
      expect(toastMessages()).toEqual(["Pie64 is already running"]);
    });
  });
});
```

Rewrite the empty-state case in `brawlfarm/web/src/fleet/Fleet.test.tsx`:

```tsx
  it("tells a new user what to do when there are no instances", async () => {
    stubFleet([]);
    renderWithProviders(<Fleet />);
    expect(await screen.findByText("No instances yet.")).toBeInTheDocument();
    expect(
      screen.getByText("Open setup to find your BlueStacks instances."),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open setup" })).toHaveAttribute("href", "/setup");
    expect(screen.queryByRole("button", { name: "Start all" })).not.toBeInTheDocument();
  });
```

- [ ] **Step 2: Run the three files to confirm they fail**

```bash
pnpm --dir brawlfarm/web test src/setup/StepStats.test.tsx src/setup/StepDone.test.tsx src/fleet/Fleet.test.tsx
```

Expected: FAIL, 9 of them. The two setup files reach step 3 and then fail on
`Unable to find an element with the text: Stats (optional)`, because `STEP_VIEWS` has no
entry past `display`. `Fleet.test.tsx` fails its one rewritten case with
`Unable to find an element with the text: Open setup to find your BlueStacks instances.`

- [ ] **Step 3: Write step 4**

Create `brawlfarm/web/src/setup/StepStats.tsx`:

```tsx
/**
 * Step 4: the optional half.
 *
 * Nothing here is needed to farm, and the copy says so first, because a required-looking
 * token field is the commonest reason someone abandons a setup wizard. "Skip for now" is a
 * real answer, not a trap: it marks the step finished for this visit and moves on.
 *
 * The token reaches the masked Field, the PUT body and nowhere else: not a log, not a toast,
 * not the summary on the next step, which says only "set" or "skipped".
 *
 * A tag is its own field per instance, because the model upper-cases it and puts its # back,
 * and a refused one has to land under the instance it belongs to rather than at the top of
 * the step.
 */
import { useState } from "react";

import { type StepProps, saveStepAsync } from "./useSetupState";
import { Button } from "../components/ui/Button";
import { ErrorBlock } from "../components/ui/ErrorBlock";
import { Field } from "../components/ui/Field";
import { type SettingsPatch, fieldError, useDebouncedSave } from "../settings/useSettingsPatch";

function TagField({
  settingsPatch,
  name,
  onFailure,
}: {
  settingsPatch: SettingsPatch;
  name: string;
  onFailure: (error: unknown) => void;
}) {
  const { settings, patch, fieldErrors } = settingsPatch;
  const at = settings?.instances.findIndex((one) => one.name === name) ?? -1;
  const stored = at < 0 ? "" : (settings?.instances[at].player_tag ?? "");
  const box = useDebouncedSave(stored, (value) =>
    saveStepAsync(
      patch,
      (draft) => {
        const row = draft.instances.find((one) => one.name === name);
        if (row !== undefined) row.player_tag = value;
      },
      onFailure,
    ),
  );
  // pydantic names a list item by its index, so this is the loc a 422 for this row arrives
  // under.
  const message = fieldError(fieldErrors, `instances.${at}.player_tag`);

  return (
    <div onBlur={box.onBlur}>
      <Field
        label={name}
        id={`setup-tag-${name}`}
        value={box.value}
        onChange={box.onChange}
        width="full"
        placeholder="#TAG"
      />
      {message !== undefined && <p className="mt-1 text-[12px] text-bad">{message}</p>}
    </div>
  );
}

export function StepStats({ setup }: StepProps) {
  const { back, next, skipStats, settingsPatch } = setup;
  const { settings, patch, fieldErrors } = settingsPatch;
  const [failure, setFailure] = useState<unknown>(null);
  const instances = settings?.instances ?? [];

  const token = useDebouncedSave(settings?.connection.brawl_api_token ?? "", (value) =>
    saveStepAsync(
      patch,
      (draft) => {
        draft.connection.brawl_api_token = value;
      },
      setFailure,
    ),
  );
  const tokenError = fieldError(fieldErrors, "connection.brawl_api_token");

  const skip = () => {
    skipStats();
    next();
  };

  return (
    <div>
      <h1 className="text-[18px] font-semibold">Stats (optional)</h1>
      <p className="mt-1 text-[13px] text-muted">
        A token and your player tags let brawlfarm show per-brawler stats. Farming works
        without them.
      </p>

      <div className="mt-4 space-y-3">
        {failure !== null && <ErrorBlock error={failure} />}

        <div onBlur={token.onBlur}>
          <Field
            label="Brawl Stars API token"
            id="setup-token"
            value={token.value}
            onChange={token.onChange}
            type="password"
            width="full"
          />
          {tokenError !== undefined && (
            <p className="mt-1 text-[12px] text-bad">{tokenError}</p>
          )}
        </div>

        {instances.map((one) => (
          <TagField
            key={one.name}
            settingsPatch={settingsPatch}
            name={one.name}
            onFailure={setFailure}
          />
        ))}

        <p className="text-[12px] text-muted">
          {"Create a key at "}
          <a
            href="https://developer.brawlstars.com"
            target="_blank"
            rel="noreferrer"
            className="text-accent hover:underline"
          >
            developer.brawlstars.com
          </a>
          {" and allow this machine's IP address."}
        </p>
      </div>

      <div className="mt-5 flex flex-wrap items-center gap-2">
        <Button variant="quiet" onClick={back}>
          Back
        </Button>
        <Button variant="text" size="sm" onClick={skip}>
          Skip for now
        </Button>
        <Button variant="primary" onClick={next}>
          Continue
        </Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Write step 5**

Create `brawlfarm/web/src/setup/StepDone.tsx`:

```tsx
/**
 * Step 5: what setup did, and the one thing it offers to do next.
 *
 * The summary is four lines because four is what there is to say. The token is one of them
 * and is never printed: "set" or "skipped" is the whole truth a reader needs, and a token on
 * a screen is a token in a screenshot.
 *
 * The one start is the only process this whole phase begins. It goes through the same
 * POST /api/instances/{name}/start every other Start in the panel uses, so the supervisor
 * still owns the one-worker-per-instance rule. A refused start is said out loud and does not
 * trap anyone on this page: the fleet opens either way, and the fleet is where a refusal can
 * actually be looked at.
 */
import { useState } from "react";
import { useNavigate } from "react-router";

import { type StepProps } from "./useSetupState";
import { startInstance } from "../api/instances";
import { Button } from "../components/ui/Button";
import { Switch } from "../components/ui/Switch";
import { failureMessage, toast } from "../lib/toast";

export function StepDone({ setup }: StepProps) {
  const { settingsPatch } = setup;
  const settings = settingsPatch.settings;
  const navigate = useNavigate();
  const [startFirst, setStartFirst] = useState(true);

  const instances = settings?.instances ?? [];
  const first = instances.length === 0 ? "" : instances[0].name;
  const tagged = instances.filter((one) => one.player_tag !== "").length;

  const open = () => {
    if (!startFirst || first === "") {
      navigate("/");
      return;
    }
    void startInstance(first).then(
      () => navigate("/"),
      (error: unknown) => {
        toast(failureMessage(error));
        navigate("/");
      },
    );
  };

  return (
    <div>
      <h1 className="text-[18px] font-semibold">Done</h1>
      <p className="mt-1 text-[13px] text-muted">Setup complete.</p>

      <ul aria-label="Setup summary" className="mt-4 space-y-1 text-[13px]">
        <li>
          {`Instances: ${instances.length} `}
          <span className="font-mono text-[12px] text-muted">
            {instances.map((one) => one.name).join(", ")}
          </span>
        </li>
        <li>
          {"adb: "}
          <span className="font-mono text-[12px] text-muted">
            {settings?.connection.adb_path ?? ""}
          </span>
        </li>
        <li>
          {(settings?.connection.brawl_api_token ?? "") === "" ? "Token: skipped" : "Token: set"}
        </li>
        <li>{tagged === 0 ? "Player tags: none" : `Player tags: ${tagged} of ${instances.length} set`}</li>
      </ul>

      {first !== "" && (
        <div className="mt-4">
          <Switch
            checked={startFirst}
            onChange={setStartFirst}
            label={`Start ${first} now`}
          />
        </div>
      )}

      <p className="mt-4 text-[12px] text-muted">
        Each step already saved to config.toml, so you can close this and come back.
      </p>

      <div className="mt-5">
        <Button variant="primary" onClick={open}>
          Open Fleet
        </Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Close the step table**

In `brawlfarm/web/src/setup/Setup.tsx`, add the last two imports and drop the `Partial`:

```tsx
import { StepBlueStacks } from "./StepBlueStacks";
import { StepDisplay } from "./StepDisplay";
import { StepDone } from "./StepDone";
import { StepInstances } from "./StepInstances";
import { StepRail } from "./StepRail";
import { StepStats } from "./StepStats";
```

```tsx
/** Total, not Partial: every id in SETUP_STEPS has a view, and the compiler is what says
 * so. Adding a step to the rail without writing it now fails typecheck. */
const STEP_VIEWS: Record<StepId, StepView> = {
  bluestacks: StepBlueStacks,
  instances: StepInstances,
  display: StepDisplay,
  stats: StepStats,
  done: StepDone,
};
```

and the render can stop asking whether there is one:

```tsx
          {setup.ready && <View setup={setup} />}
```

- [ ] **Step 6: Point Fleet's empty state at the wizard**

In `brawlfarm/web/src/fleet/Fleet.tsx`, add the router import:

```tsx
import { Link } from "react-router";
```

and replace the empty state:

```tsx
  if (instances !== undefined && fleet.length === 0) {
    return (
      <section className="max-w-[560px]">
        <h1 className="text-[28px] font-semibold tracking-tight">No instances yet.</h1>
        <p className="mt-2 text-[13px] text-muted">
          Open setup to find your BlueStacks instances.
        </p>
        <div className="mt-4">
          {/* A link, not a Button with a navigate: it goes somewhere, so it should open in
              a new tab on a middle click like every other link does. */}
          <Link
            to="/setup"
            className="inline-flex h-8 items-center gap-1.5 rounded-[6px] bg-accent px-3 text-[13px] font-medium text-accent-ink transition-[background-color,border-color,color] duration-[120ms] hover:brightness-110"
          >
            Open setup
          </Link>
        </div>
      </section>
    );
  }
```

- [ ] **Step 7: Run the three files, then everything**

```bash
pnpm --dir brawlfarm/web test src/setup/StepStats.test.tsx src/setup/StepDone.test.tsx src/fleet/Fleet.test.tsx
pnpm --dir brawlfarm/web typecheck
pnpm --dir brawlfarm/web test
pnpm --dir brawlfarm/web build
```

Expected: `StepStats.test.tsx` at 4, `StepDone.test.tsx` at 5 and `Fleet.test.tsx` at 8 with
its rewritten case passing. `tsc --noEmit` prints nothing. The whole
suite is 54 files and 375 tests (52 and 366 after task 9). `vite build` writes
`brawlfarm/web/dist/index.html`.

- [ ] **Step 8: Walk the whole wizard**

```bash
pnpm --dir brawlfarm/web build
uv run brawlfarm --no-browser
```

Move `config.toml` out of the data home first, so brawlfarm starts with nothing configured,
then open `http://127.0.0.1:8765/`: Fleet says "No instances yet." with an Open setup button.
Press it and walk all five steps against the real BlueStacks install. On step 4, put a real
tag in one field and confirm the box comes back upper-cased with its `#`. On step 5, leave
the switch on and press Open Fleet: the fleet appears with that instance starting. Then put
the old `config.toml` back.

- [ ] **Step 9: Commit**

```bash
uv run python tools/scrub_check.py && git add brawlfarm/web/src && git commit -m "feat(web): the wizard's stats and done steps, and the way in from Fleet

Step 4 says the quiet part first: none of it is needed to farm. Skip for
now is a real answer that marks the step finished for this visit rather
than a trap, because a required-looking token field is the commonest
reason a setup wizard gets abandoned. A refused tag lands under the
instance it came from, since pydantic names a list item by its index and
the mapper already knows how to read that.

Step 5 summarises in four lines and prints no token: set or skipped is
the whole truth, and a token on a screen is a token in a screenshot. Its
one start goes through the same route every other Start uses, so the
supervisor still owns one worker per instance, and a refusal is said out
loud without trapping anyone on a page that cannot act on it.

Fleet's empty state stops telling people to edit config.toml by hand and
sends them to the wizard instead, which is the only entry point that
exists: nothing auto-redirects.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CQ1GimQ3uiR2sXPzfZLNWV"
```

Expected: `0 hit(s)`, then the commit.

---

### Task 11: Finish. Polish pass, live evidence, docs and the pull request

The brief's task 8. No new features. This task proves the ten before it work in a real
browser against a real BlueStacks instance, and writes the documents that ship with them.

**This task has exactly one commit of its own, and it is a docs commit** (`README.md`). If a
check below fails, the fix belongs to the component that owns it: make it a small
`fix(web): ...` or `fix(api): ...` commit naming that file, with the same two trailers, and
re-run that component's test file. Do not fold a behaviour fix into the docs commit.

`docs/PLAN.md` is not touched on the branch. The board row is written on `main` after the
merge, which is what every phase has done, and step 11 below is that command.

**Files:**
- Modify: `README.md` (the status line at line 5; the Requirements paragraph at line 26; a new `## Setup` section after it; four rows in the API table)
- Create (outside the repo): `<scratchpad>/shots/*.png`
- Modify, on `main` after the merge: `docs/PLAN.md` (the phase 5 row)

**Interfaces:**
- Consumes: everything tasks 1 to 10 produced; `playwright-cli`; `uv run brawlfarm`; the API
  at `http://127.0.0.1:8765`.
- Produces: the README's Setup section and its four new API rows, the blurred screenshots
  attached to the PR, the PR body, and the board row on `main`.

- [ ] **Step 1: Serve the real panel**

```bash
pnpm --dir brawlfarm/web build
uv run brawlfarm --no-browser
```

Expected: `vite build` writes `brawlfarm/web/dist/index.html`, and the server prints its
three panel lines. Leave it running in this shell; every step below uses another one. The
instance is the real one, `Pie64` on adb port 5555, with its config already in
`%LOCALAPPDATA%\brawlfarm\config.toml`.

- [ ] **Step 2: Keyboard and focus pass over the new screens**

```bash
playwright-cli open http://127.0.0.1:8765/settings/instances
playwright-cli resize 1280 900
playwright-cli snapshot
```

Pressing Tab from the top of the page, confirm each of these and note any that fail:

- [ ] Tab order on a settings section is rail wordmark, Fleet, Stats, Settings, each instance link, the seven section links in order, then the section's own controls top to bottom.
- [ ] Every focused control shows the 2 px accent ring from `styles/theme.css`'s `:focus-visible`: the section links, every `Switch`, every table checkbox, the Show button on the masked field, the theme cards and the seven event checkboxes.
- [ ] The theme radio group on `/settings/about` takes one Tab stop, not three. Left and Right move between the three cards, selection follows focus, and both ends wrap.
- [ ] Opening the Remove dialog on `/settings/instances` moves focus into it, Tab cycles inside it and never reaches the page behind, Escape closes it, and focus returns to the Remove button that opened it.
- [ ] The same for the Delete data and Reset dialogs on `/settings/data`.
- [ ] A dialog's confirm button is disabled until the typed name matches exactly, and hovering it shows the title `Type Pie64 to confirm`.
- [ ] On `/setup`, Tab reaches the step rail before the step body. A step later than the current one is skipped by Tab, because it is disabled.
- [ ] On the wizard's Instances step, Tab reaches each row's checkbox then its Test button, row by row, and the table header is not a tab stop.

- [ ] **Step 3: Reduced motion**

```bash
playwright-cli eval "matchMedia('(prefers-reduced-motion: reduce)').matches"
```

With Windows animation effects turned off (Settings, Accessibility, Visual effects,
Animation effects), that prints `true`. Then confirm:

- [ ] Opening and closing a dialog is instant, with no fade and no slide.
- [ ] A `Switch` on `/settings/behavior` changes colour with no visible travel on the knob.
- [ ] Nothing on `/setup` animates between steps.

`styles/theme.css` already zeroes every transition and animation duration under that query,
so this is a check that nothing added an inline `style` that escapes it, not a change.

- [ ] **Step 4: Phone width**

```bash
playwright-cli resize 390 844
playwright-cli open http://127.0.0.1:8765/settings/notifications
playwright-cli snapshot
```

- [ ] The shell rail is a scrolling top row, and the settings nav is a second scrolling row under it. Neither clips its last item.
- [ ] Every `SettingRow` stacks: title and sentence above, control below, nothing overlapping.
- [ ] The Instances table scrolls sideways inside its own box rather than widening the page; the page itself has no horizontal scrollbar.
- [ ] On `/setup` the step rail is a horizontal row above the step body, and the wizard's own table behaves the same way.
- [ ] The Reset card on `/settings/data` keeps its red border and does not push the page wider.

- [ ] **Step 5: Light theme**

```bash
playwright-cli open http://127.0.0.1:8765/settings/about
```

Pick Light, then walk `/settings/instances`, `/settings/data`, `/setup` and back to `/`.

- [ ] Every chip, every dialog and every table row keeps its contrast; nothing is grey on grey.
- [ ] The Reset card's `--bad` border and the confirm button's `--bad` fill are both visible against the light panel.
- [ ] The masked field's dots and its Show button are legible.
- [ ] Set it back to System when the pass is done.

- [ ] **Step 6: Blurred screenshots**

```bash
playwright-cli resize 1280 900
playwright-cli open http://127.0.0.1:8765/setup
playwright-cli eval "document.querySelectorAll('[data-private]').forEach(n => { n.style.filter = 'blur(14px)'; })"
playwright-cli screenshot <scratchpad>/shots/wizard-bluestacks.png
```

Repeat the `eval` then `screenshot` pair for each of these; the `eval` has to run again after
every navigation, because it sets an inline style on the nodes that are on the page now:

- [ ] `<scratchpad>/shots/wizard-instances.png` at `/setup`, on step 2, with the real table
- [ ] `<scratchpad>/shots/wizard-display.png` at `/setup`, on step 3
- [ ] `<scratchpad>/shots/settings-instances.png` at `/settings/instances`
- [ ] `<scratchpad>/shots/settings-connection.png` at `/settings/connection`
- [ ] `<scratchpad>/shots/settings-data.png` at `/settings/data`

Then open each PNG and confirm by eye, before anything is attached anywhere:

- [ ] The token field is an unreadable smear, not dots that could be counted.
- [ ] The Instances table's Player tag column is blurred.
- [ ] No absolute path is on screen: the Data section shows `instances/Pie64`, and the home
      folder is only in the Open data folder tooltip, which a screenshot does not capture.
- [ ] No Windows user name appears in any shot, including in the browser's address bar.
- [ ] The screenshots stay in the scratchpad. They are attached to the PR and never committed.

- [ ] **Step 7: Everything green, both sides**

```bash
pnpm --dir brawlfarm/web typecheck
pnpm --dir brawlfarm/web test
pnpm --dir brawlfarm/web build
uv run ruff check . && uv run ruff format --check .
uv run pytest -q
uv run python tools/scrub_check.py
```

Expected: `tsc --noEmit` silent; 54 files and 375 tests passing; `vite build` writes
`brawlfarm/web/dist/index.html`; ruff says `All checks passed!` and prints nothing for the
format check; pytest reports 617 passed; the scrub check prints `0 hit(s)`.

- [ ] **Step 8: Update the README**

Replace the status line (line 5):

```markdown
Status: under construction. Phase 5 of 8 (the setup wizard and the Settings screens). The stats screens arrive in phase 6; see `docs/PLAN.md`.
```

Replace the Requirements paragraph (line 26):

```markdown
Windows 11, BlueStacks 5 with Android Debug Bridge enabled, an instance display of 1600 x 900 at pixel density 240, Python 3.13 and [uv](https://docs.astral.sh/uv/).
```

Add a `## Setup` section between `## Requirements` and `## Development`:

```markdown
## Setup

Start brawlfarm and open `http://127.0.0.1:8765/setup`. The wizard finds adb, lists your BlueStacks instances and their ports, checks each one is 1600 x 900 at pixel density 240, and optionally takes a Brawl Stars API token and your player tags. Every step writes straight to `config.toml`, so you can close it and come back. With nothing configured yet, the Fleet page offers the same wizard behind an Open setup button, and Settings, Connection has a Run setup again link once you are past it.

To change the display: BlueStacks, Settings, Display, set 1600 x 900 and pixel density 240, then restart the instance. A prose walkthrough with pictures joins `docs/setup.md` in phase 7.
```

Add four rows to the API table, each beside the routes it belongs with: after the
`GET, PUT | /api/settings` row,

```markdown
| POST | `/api/settings/reset` | every section back to its default; instances and their folders are kept |
| POST | `/api/settings/open-data-folder` | open the data folder in Explorer; 501 anywhere but Windows |
| POST | `/api/notifications/test` | send one test alert to every configured channel |
```

and after the `/api/instances/{name}/retry` row,

```markdown
| DELETE | `/api/instances/{name}/data` | delete that instance's folder; the instance stays in `config.toml` |
```

- [ ] **Step 9: Commit the docs**

```bash
uv run python tools/scrub_check.py && git add README.md && git commit -m "docs: the setup wizard, and the four new API routes

The Requirements line says pixel density rather than DPI, because that is
what the BlueStacks menu calls it and what the wizard's own hint says. A
Setup section points at the wizard and names the two other doors into it,
so nobody is told to hand-edit config.toml any more. The API table gains
the reset, open-folder, notification-test and delete-data routes.

docs/PLAN.md is left alone: the board is updated on main after the merge,
as in every phase.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CQ1GimQ3uiR2sXPzfZLNWV"
```

Expected: `0 hit(s)`, then the commit.

- [ ] **Step 10: Push and open the pull request**

```bash
git config user.name   # must print as9pa
git push -u origin phase-5/setup-wizard-and-settings
gh pr create --base main --title "Phase 5: the setup wizard and the Settings screens" --body-file /dev/stdin <<'EOF'
## What

`http://127.0.0.1:8765/setup` is a five-step wizard: find adb, pick the BlueStacks instances, check each one is 1600 x 900 at pixel density 240, optionally take a Brawl Stars token and player tags, then a summary that can start the first instance. Every step writes straight to `config.toml` through the whole-document settings route, so it can be closed and resumed, and the adb path it finds is finally persisted into `connection.adb_path`, which phase 3 deferred.

`/settings` is seven sections behind a second-level nav: Instances, Connection, Behavior, Schedule, Notifications, Data and About. They save on change, with a "Saved 19:04" caption per section and no Save button anywhere. A switch writes as it is flipped; a text field writes 500 ms after the last keystroke and at once on blur. Every write goes through one read-modify-write queue, so two quick changes cannot race and no section can blank another.

Five API additions back them: `POST /api/notifications/test`, `POST /api/settings/reset`, `POST /api/settings/open-data-folder`, `DELETE /api/instances/{name}/data`, and `notify.send_test`, which is the only thing added under `brawlfarm/core` in this phase. One supervisor line changes: a cleared token now clears the applied one instead of keeping the last non-blank value forever.

## Safety

- No safety rail moved. `controller.py`, `states.py`, `vision.py`, `farmplan.py` and the calibration block of `core/config.py` are untouched, and the never-tap tests pass unchanged.
- Nothing here starts, stops or kills a process except the Done step's single `POST /api/instances/{name}/start`, which is the same route every other Start uses.
- `DELETE /api/instances/{name}/data` goes through `resolve_instance` and additionally refuses any resolved path that is not under `<home>/instances`, refuses a live instance with a 409, and deletes the folder rather than the instance.
- The Brawl Stars token reaches one masked field, the PUT body and nothing else: not a log, not a toast, not the wizard's summary, which says only "set" or "skipped". Notification URLs and ntfy topics are never logged either.
- No `discord` import anywhere.

## How to verify

```
corepack enable
pnpm --dir brawlfarm/web install --frozen-lockfile
pnpm --dir brawlfarm/web typecheck && pnpm --dir brawlfarm/web test && pnpm --dir brawlfarm/web build
uv sync --group dev
uv run ruff check . && uv run ruff format --check .
uv run pytest -q
uv run python tools/scrub_check.py
uv run brawlfarm --no-browser
```

Then move `config.toml` aside, open `http://127.0.0.1:8765/`, press Open setup and walk the five steps against a real BlueStacks install.

## Evidence

- 375 vitest tests in 54 files, 617 pytest, ruff clean, scrub check 0 hits.
- Live run on the real instance: the wizard found adb, listed the instances with their real ports, probed a stopped one and said "No answer on <port>. Is the instance running?", measured the display, took a tag that came back upper-cased with its `#`, and the Done step started the instance and landed on Fleet with its card walking to Farming.
- Settings: removing a stopped instance worked and removing a farming one returned the API's own 409 inline in its row; a test ntfy message arrived on the phone; Open data folder opened Explorer; a reset kept both instances and their folders.
- Screenshots below are of the real panel with `[data-private]` blurred: the token field, the Instances table's tag column and the About home-folder tooltip.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01CQ1GimQ3uiR2sXPzfZLNWV
EOF
```

Then attach the five PNGs from `<scratchpad>/shots/` to the PR in the browser. They are not
committed.

Expected: `gh` prints the pull request URL. Keep it: step 11 needs it.

- [ ] **Step 11: After the merge, the board row on main**

Only once the PR is merged and its CI run is green:

```bash
git switch main && git pull
```

In `docs/PLAN.md`, replace the phase 5 line in the upcoming list with a completed row in the
same shape as the phase 4 row above it, using the pull request URL `gh` printed in step 10
and the CI run URL from that PR's checks tab:

```markdown
- Phase 5: Setup wizard and Settings screens. PR <the URL from step 10> (merged). Proof: CI run <the URL from that PR's checks tab> green on the pushed head (375 vitest tests in 54 files, 617 pytest, ruff clean, scrub check 0 hits); eleven plan tasks each reviewed with fix rounds closed by scoped re-reviews; live run against the real BlueStacks install: the wizard found adb, listed the instances, probed a stopped port and said so, measured the display, took a player tag that came back upper-cased, and the Done step started the instance and landed on Fleet with its card walking to Farming; Settings removed a stopped instance, refused a farming one with the API's own 409 inline, sent a test ntfy message that arrived on the phone, opened the data folder in Explorer, and reset every section while keeping both instances and their folders (blurred screenshots kept out of the repo). Deferred: the Stats page's prompts for a missing player tag and for an API key that stopped working are phase 6; `docs/setup.md` with pictures is phase 7; the wizard's Display step is re-run on every visit because nothing about it is stored.
```

```bash
uv run python tools/scrub_check.py && git add docs/PLAN.md && git commit -m "docs(board): phase 5 shipped

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CQ1GimQ3uiR2sXPzfZLNWV" && git push
```

Expected: `0 hit(s)`, then the commit and the push.

