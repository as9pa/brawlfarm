# Phase 4 design brief: UI shell, Fleet and Instance

This is the binding design for the phase 4 implementation plan. Plan writers copy its
values verbatim; they do not re-decide anything here. Facts about the existing API come
from `phase4-explore-contracts.md` next to this file (exact payloads, status codes, event
names); the spec is `docs/superpowers/specs/2026-09-10-brawlfarm-design.md` (section 8 is
the UI, section 9 the safety rails, section 10 hygiene, section 11 testing). The owner
accepted all 27 proposal items (ids listed at the end) with no notes.

## 1. Outcome

`brawlfarm` serves a real panel at http://127.0.0.1:8765: a shell (left rail, top bar,
alerts drawer), the Fleet home page (one card per instance led by its live thumbnail) and
the Instance page (live screen, plain-language feed, farm plan, schedule timeline, session
panel). Stats and Settings exist as placeholder pages. Everything is driven by the phase 3
API plus three small API additions (alert dismiss-all, feed record sequence numbers, the
roster on GET plan). CI builds the web app before pytest; the wheel carries the built dist.

## 2. Stack and layout (decided)

- Directory `brawlfarm/web/` (spec section 4): Vite 7, React 19, TypeScript 5 strict,
  Tailwind v4 through `@tailwindcss/vite`, `react-router` v7 (declarative mode:
  `BrowserRouter`, `Routes`, `Route`, `Link`, `useParams`), `@tanstack/react-query` v5,
  `lucide-react`. Tests: `vitest` + `@testing-library/react` + `@testing-library/user-event`
  + `jsdom`. Package manager: pnpm via corepack (`"packageManager": "pnpm@10.17.1"` in
  package.json; `corepack enable` on the machine and in CI). Node 22 in CI
  (`actions/setup-node@v4` with `node-version: 22`); the dev machine has Node 26, which is
  fine. No ESLint in phase 4; `tsc --noEmit` is the lint. No other runtime dependencies.
- Scripts in `brawlfarm/web/package.json`: `dev` (vite), `build` (`tsc --noEmit && vite build`),
  `test` (`vitest run`), `typecheck` (`tsc --noEmit`).
- `vite.config.ts`: `plugins: [react(), tailwindcss()]`, `build.outDir: "dist"`,
  `build.emptyOutDir: true`, `server.proxy: { "/api": { target: "http://127.0.0.1:8765", changeOrigin: false } }`
  (the proxy carries SSE; the loopback middleware sees 127.0.0.1). `test` block:
  `environment: "jsdom"`, `setupFiles: ["src/test/setup.ts"]`, `globals: false`.
- Output `brawlfarm/web/dist` (already gitignored; `brawlfarm/api/app.py` mounts it when
  `dist/index.html` exists).
- Packaging: `pyproject.toml` gains `[tool.hatch.build.targets.wheel] artifacts = ["brawlfarm/web/dist/**"]`
  and excludes `brawlfarm/web/src`, `brawlfarm/web/public`, `brawlfarm/web/node_modules`,
  `brawlfarm/web/*.json`, `brawlfarm/web/*.ts`, `brawlfarm/web/*.html`, `brawlfarm/web/*.yaml`
  from the wheel. Acceptance: `uv build --wheel` then a Python `zipfile` listing shows
  `brawlfarm/web/dist/index.html` and no `brawlfarm/web/src/` entries.
- CI (`.github/workflows/ci.yml`, one windows-latest job) gains, before the Python steps:
  `actions/setup-node@v4` (node 22), `corepack enable`, `pnpm install --frozen-lockfile`
  (working-directory brawlfarm/web), `pnpm typecheck`, `pnpm test`, `pnpm build`. After
  pytest: `uv build --wheel` and a `uv run python -c` zipfile check that the wheel contains
  `brawlfarm/web/dist/index.html`. The scrub check also scans `brawlfarm/web/src` (it scans
  the tree already; confirm `tools/scrub_check.py` skips `node_modules` and `dist`, add the
  skip if it does not).
- Fonts self-hosted in `brawlfarm/web/public/fonts/`: Archivo variable (latin subset,
  weights 400 to 600, woff2 fetched from the Google Fonts CSS API with a modern browser
  User-Agent so it serves woff2) and JetBrains Mono 400 and 500 woff2 from the JetBrains
  Mono 2.304 GitHub release zip (`fonts/webfonts/JetBrainsMono-Regular.woff2`,
  `JetBrainsMono-Medium.woff2`). Both OFL licence texts land beside them
  (`OFL-Archivo.txt` from google/fonts `ofl/archivo/OFL.txt`, `OFL-JetBrainsMono.txt` from
  the zip). `@font-face` in `theme.css` with `font-display: swap`.
- Icons: `lucide-react` only, 16 px, `strokeWidth={1.6}`. No emoji anywhere in UI text.

## 3. Tokens and theme (spec section 8, verbatim)

`brawlfarm/web/src/styles/theme.css`:

```css
@import "tailwindcss";

:root {
  --ground: #0C0F14; --panel: #12161D; --panel-2: #181D26; --line: #252C38;
  --text: #E7EAF0; --muted: #8A94A6; --accent: #E0B84B; --accent-ink: #0C0F14;
  --ok: #58B77E; --warn: #E08A3C; --bad: #E06565; --idle: #6B7484;
  --series-1: #3987E5; --series-2: #D95926; --series-3: #199E70;
}
@media (prefers-color-scheme: light) {
  :root:not([data-theme="dark"]) {
    --ground: #F3F4F6; --panel: #FFFFFF; --panel-2: #EEF0F3; --line: #D9DDE4;
    --text: #161A21; --muted: #5F6876; --accent: #9A7418; --accent-ink: #FFFFFF;
    --ok: #2B8A57; --warn: #B8631E; --bad: #B94A4A; --idle: #7B838F;
    --series-1: #2A78D6; --series-2: #EB6834; --series-3: #1BAF7A;
  }
}
:root[data-theme="light"] {
  --ground: #F3F4F6; --panel: #FFFFFF; --panel-2: #EEF0F3; --line: #D9DDE4;
  --text: #161A21; --muted: #5F6876; --accent: #9A7418; --accent-ink: #FFFFFF;
  --ok: #2B8A57; --warn: #B8631E; --bad: #B94A4A; --idle: #7B838F;
  --series-1: #2A78D6; --series-2: #EB6834; --series-3: #1BAF7A;
}
@theme inline {
  --color-ground: var(--ground); --color-panel: var(--panel); --color-panel-2: var(--panel-2);
  --color-line: var(--line); --color-text: var(--text); --color-muted: var(--muted);
  --color-accent: var(--accent); --color-accent-ink: var(--accent-ink);
  --color-ok: var(--ok); --color-warn: var(--warn); --color-bad: var(--bad); --color-idle: var(--idle);
  --font-sans: "Archivo", system-ui, sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, monospace;
  --radius-control: 6px; --radius-panel: 10px;
}
```

Type scale (utilities via Tailwind sizes): 11 (ids, captions), 12 (labels), 13 (body in
panels), 15 (card titles, item text), 20 (page headers), 28 (h1). Numbers, ports, tags,
times and log lines use `font-mono` with `tabular-nums`. Theme bootstrap: `App` reads
`GET /api/settings` once, applies `app.theme` (`"dark"` or `"light"` sets
`document.documentElement.dataset.theme`; `"system"` deletes it). The client must never
log, store or display `connection.brawl_api_token`; only `app.theme` is read from that
response. Radius 6 px on controls, 10 px on panels. No gradients, no glows, no shadows
beyond a 1 px line. Motion: hover and press 120 ms; `@media (prefers-reduced-motion: reduce)`
removes transitions. Focus: `outline: 2px solid var(--accent); outline-offset: 2px` on
every interactive element via `:focus-visible`.

## 4. State vocabulary (verbatim strings)

State chips (`lib/states.ts`, `StateChip`), word plus colour:

| state | label | tone |
| --- | --- | --- |
| farming | Farming | ok |
| starting | Starting | idle |
| stopping | Stopping after this match | warn |
| stopped | Stopped | idle |
| scheduled_break | Scheduled break | idle |
| reconnecting | Reconnecting | warn |
| offline | Offline | bad |

Phase captions (`phaseLabel`): `at_menu` "at menu", `queuing` "queuing", `playing`
"playing", `returning` "returning", null "no status yet".

Alert kind chips (`AlertsDrawer`): offline "Offline" bad, crash "Crash" bad,
bad_resolution "Wrong resolution" bad, recover "Recover" warn, wrong_mode "Wrong mode"
warn, recalibrate "Recalibrate" warn, other kinds: the kind text, idle.

Connection pill (`TopBar`): `live` "Live" ok dot, `reconnecting` "Reconnecting" warn dot,
`connecting` "Connecting" idle dot (first second only).

Feed categories to dot colours: matches ok, interrupts warn, errors bad, other idle.

## 5. Copy (verbatim)

- Fleet empty: heading "No instances yet." body "Setup arrives in the next phase; until then
  add an [[instances]] table to config.toml and restart brawlfarm."
- Offline card: "BlueStacks window not found. Retrying in N min." second line "Open the
  instance, or Retry now." where "Retry now" is a text button. N comes from the note
  (`/Retrying in (\d+) min/`), else the line reads "BlueStacks window not found. Retrying soon."
- Scheduled break thumb caption: "Break until HH:MM" from `until`, or "On a scheduled break"
  when `until` is null.
- Alerts drawer empty: "No alerts. Offline instances, crashes and wrong-mode recoveries show
  up here."
- Alert strip: `${instance} ${title.toLowerCase()}: ${detail}` shortened to one line; for
  kind offline the strip reads "${instance} has been offline for ${age}. BlueStacks window
  not found."; buttons "Retry now" (offline only), "Dismiss", and "${n} more" when unread > 1.
- Toasts: stop "Stopping ${name} after this match" with Undo (6 s); start "Started ${name}";
  restart "Restarting ${name}"; retry "Retrying ${name} now"; start all "Starting ${n}
  instances"; stop all "Stopping ${n} instances after their matches"; plan "Plan saved";
  schedule on/off "Schedule on" / "Schedule off"; redraw "Redrawing today; new sessions
  appear after the next tick"; run for "Running ${name} for ${hours} h"; dismiss all
  "Alerts dismissed".
- Feed empty: "No lines yet. The feed fills as the worker plays." Filter empty: matches "No
  matches this session.", interrupts "No interrupts this session.", errors "No errors this
  session."
- Live screen error (inside the 16:9 box): "Screenshot failed: ${detail}" second line
  "Retrying in 15 s."
- Schedule empty: "No sessions drawn yet. The supervisor draws today on its next tick."
- Session panel ended: "Session ended HH:MM".
- Roster status copy (FarmPlan): no_token "Add a Brawl Stars API token in Settings to see
  the roster."; no_tag "Set this instance's player tag in Settings to see the roster.";
  unavailable "Roster unavailable right now; showing the last known list." (when a stale
  roster exists) or "Roster unavailable right now." (when none).
- Errors: `ErrorBlock` shows the API `detail` string verbatim when the response carried one
  ("adb did not answer", "Stop Pie64 before removing it", "unknown instance") and otherwise
  "Request failed (HTTP ${status})". A 422 with FastAPI's list body renders
  `${loc.join(".")}: ${msg}` lines. A network failure renders "The panel cannot reach
  brawlfarm. Is it still running?".
- Placeholder pages: Stats "Stats arrive in phase 6." Settings "Settings arrive in phase 5.
  Until then edit config.toml and restart brawlfarm." (paragraph under an h1 with the page name).
- Rail: wordmark "brawlfarm"; nav "Fleet", "Stats", "Settings" with a muted "soon" tag on the
  last two; group label "Instances".

## 6. Feed sentences (`lib/feedText.ts`)

`feedText(record): { text: string; tone: "ok" | "warn" | "bad" | "idle" }`. Tone comes from
the record's `category` (matches ok, interrupts warn, errors bad, other idle) except where
noted. Table (event, fields → text):

- phase: `to=playing` "Playing"; `to=queuing` "Queuing for Showdown"; `to=at_menu` "At the
  menu"; `to=returning` "Returning to the menu"; other "Phase ${to}".
- games_logged: "Logged ${count} game(s)" (singular when 1).
- recap: "Match ended, ${signed(trophies)} trophies" plus ", ${skins} skin(s)" when skins > 0.
  (`recap.trophies` is the session delta; `trophies` events carry the total.)
- trophies: "Trophies: ${total}".
- farming: "Farming ${brawler}".
- select_brawler: "Brawler selected: ${brawler}" plus " (goal ${goal})" when goal present.
- rotate_brawler: "Rotated to ${brawler}: ${reason}".
- reselect_brawler: "Reselecting the brawler".
- wrong_mode: recovered true "Wrong mode detected, switched back" else "Wrong mode detected".
- popup_close: "Popup closed". team_invite_decline: "Team invite declined".
  daily_streak_claim: "Daily streak claimed". ceremony_cleared: "Ceremony cleared".
  skin_reward: "Skin reward: ${skin}". ingame_modal_cleared: "In-game dialog closed".
  gas_relocate: "Moved away from the gas". bush_hide: "Hiding in a bush".
  game_left_foreground: "Game left the foreground (${pkg})".
- disconnect: "Disconnected, reconnecting (${count})".
- recover: "Recovering: ${reason}, attempt ${attempt}". recover_dismissed: "Recovery
  dismissed: ${reason}".
- crash: "Crash: ${err}". adb_error: "ADB error: ${err}" plus " (streak ${streak})".
  bad_resolution: "Wrong resolution: ${got[0]} x ${got[1]}, need 1600 x 900".
  recalibrate: "Recalibration needed: ${surface}". Any other `*_error`: "${event without
  _error, underscores to spaces} failed: ${err}".
- start: "Worker started". stop: "Worker stopped: ${reason} (${games} games, ${minutes} min)".
  launch_game: "Brawl Stars opened". game_closed: "Brawl Stars closed: ${reason}".
  dnd: "DND enabled". dnd_off: "DND disabled". mega_quest: "Mega quest activated".
  account_maxed: "Every brawler is at the goal (${goal})". maxed_fallback_switch: "Switched
  to the maxed fallback ${fallback}". step: "${label}" with tone bad when status is error.
- Fallback for anything else: "${event with underscores to spaces}" plus, when fields are
  present, ": " + `k=v` pairs joined by ", ".

Tests must assert every event name in the table above yields its sentence (one test per
row is fine as a table-driven test).

## 7. Time and number helpers (`lib/time.ts`, `lib/format.ts`)

- `age(fromMs: number, nowMs: number): string` → "8 s ago", "3 min ago", "2 h ago"
  (thresholds 60 s, 60 min).
- `hhmm(iso: string): string` → "20:18" in local time; `hhmmss(iso)` → "19:05:40".
- `duration(minutes: number): string` → "4 min", "1 h 12 min", "0 min" for < 1.
- `signed(n: number): string` → "+86", "-12", "0" (a plain 0 shows as "0").
- `hoursText(h: number): string` → "3 h 40 min" from a fractional hour count.

## 8. API client and data layer (`src/api/*`, `src/live/*`)

`api/client.ts`:

```ts
export class ApiError extends Error { constructor(public status: number, public detail: string, public lines: string[] = []) { super(detail); } }
export async function api<T>(path: string, init?: RequestInit): Promise<T>
// JSON request/response; on non-2xx builds ApiError: detail string when body.detail is a string,
// or lines from FastAPI's list body (loc joined with ".", then ": ", msg) with detail "Validation failed";
// 204 resolves to undefined as T; a TypeError from fetch becomes ApiError(0, "The panel cannot reach brawlfarm. Is it still running?").
```

`api/types.ts` mirrors the contracts file exactly: `InstanceState`, `Health`,
`InstancePayload` (name, adb_port, state, health, pid, heartbeat_age_s, phase, desired,
desired_reason, until, games_played, farm_brawler, note, player_tag, session, today),
`InstanceSession`, `Today`, `FarmPlan`, `PlanResponse` (FarmPlan plus `current`, `roster`,
`queue`, `roster_status`, see section 10), `SchedulePayload`, `SchedulePatch`,
`FeedRecord` (ts, seq, event, category, fields), `FeedResponse`, `Alert`, `AlertsResponse`,
`StatsResponse` (only `summary` is used), `AppSettings` (only `app.theme` is read).

`api/*.ts` functions (all return typed promises): `listInstances()`,
`startInstance(name, hours?)`, `stopInstance(name)`, `restartInstance(name)`,
`retryInstance(name)`, `getPlan(name)`, `putPlan(name, plan)`, `getSchedule(name)`,
`patchSchedule(name, patch)`, `getFeed(name, kind, limit)`, `listAlerts()`,
`dismissAlert(id)`, `dismissAllAlerts()`, `getStatsToday()`, `getSettings()`,
`screenshotUrl(name)` (returns `/api/instances/${name}/screenshot.png`),
`fetchScreenshot(name): Promise<Blob>` (throws ApiError with the 503 detail).

Query keys: `["instances"]`, `["alerts"]`, `["plan", name]`, `["schedule", name]`,
`["feed", name, kind]`, `["stats", "today"]`, `["settings"]`. Default `staleTime` 5 s,
`retry: 1`, `refetchOnWindowFocus: true`.

`live/useEvents.ts`: one module-level `EventSource` on `/api/events` (created on first use,
shared by every subscriber), tracks the last `id` and reconnects itself with backoff 1, 2,
4, 8, 16, 30 s (EventSource auto-reconnect is disabled by closing on error and reopening
with a manual timer so the backoff is ours; the browser sends `Last-Event-ID` only on its
own reconnects, so pass the last id as a query param `?last_id=` is NOT supported by the
API: instead rely on the query refetches after reconnect). Exposes
`useConnection(): "connecting" | "live" | "reconnecting"` and `subscribe(kind, handler)`.
Handlers installed by `App`: `instance` → `queryClient.invalidateQueries(["instances"])`
(debounced 250 ms); `alert` → invalidate `["alerts"]`; `feed` → `queryClient.setQueryData`
append on `["feed", instance, kind]` for every kind the record belongs to (all, and its
category) with de-duplication by `${session}:${seq}`; `log` ignored. After every reconnect:
invalidate `["instances"]`, `["alerts"]` and every `["feed"]` query.

`live/useVisiblePolling.ts`: `useVisiblePolling(intervalMs): number | false` returns the
interval while `document.visibilityState === "visible"` and `false` otherwise (feeds
`refetchInterval`).

## 9. Components and pages (props are the contract)

`components/ui/`:
- `Button` props `{ variant?: "primary" | "quiet" | "text"; size?: "sm" | "md"; disabled?; disabledReason?: string (rendered as title); onClick; children; type? }`. Primary = accent fill with accent-ink text; quiet = panel-2 fill with a 1 px line; text = no fill, accent text.
- `StateChip` props `{ state: InstanceState }` (word plus colour dot; 1 px line border; panel fill).
- `Chip` props `{ tone: "ok" | "warn" | "bad" | "idle"; children }` (generic word chip, used for alert kinds and override).
- `Switch` props `{ checked; onChange(next: boolean); label: string; disabled? }` (a real `<button role="switch" aria-checked>`).
- `Segmented` props `{ value: string; options: { value: string; label: string }[]; onChange; label: string }` (radio group semantics).
- `Field` props `{ label: string; id: string; value: string; onChange(v: string); type?: "text" | "number"; suffix?: string; min?; disabled?; placeholder?; list?: string }`.
- `Toast` and `lib/toast.ts`: `toast(message: string, opts?: { undo?: () => void | Promise<void>; durationMs?: number })`; one visible at a time (a queue), bottom centre, a hairline progress bar draining over the duration (default 4000 ms, 6000 ms when undo is present), `Undo` button, `aria-live="polite"`. `useToasts()` for the `Toaster` component mounted once in `App`.
- `Drawer` props `{ open; onClose; title; children; actions?: ReactNode }` (right side, 360 px, focus trapped, Escape closes, `aria-modal`).
- `ErrorBlock` props `{ error: unknown; onRetry?: () => void }` renders per section 5.
- `Thumb` props `{ name: string; refreshMs: number | false; dimmed?: boolean; caption?: string; overlay?: ReactNode }`: fetches the screenshot blob on mount and every `refreshMs` while visible, shows the age ("8 s ago") top-right in mono, the `overlay` (the chip) top-left, an in-box error state on failure with a retry every 15 s, and revokes object URLs on replace/unmount.

`app/`: `Shell` (grid: rail 220 px, top bar 52 px, content; under 820 px the rail becomes a top row of links and the instance list hides), `Rail` (wordmark with a 10 px gold square; nav; instances group from `["instances"]` with a 6 px state dot coloured by the StateChip tone; current page gets a 2 px accent inset bar on the left and panel-2 fill; `NavLink` for aria-current), `TopBar` (page title from route; connection pill; Alerts `Button` quiet with a badge of `unread` from `["alerts"]`, hidden when 0), `AlertsDrawer` (rows newest first: kind `Chip`, instance mono, `hhmm(ts)`, detail, a "Dismiss" text button per row; header action "Dismiss all"; empty copy), `Placeholder` (h1 + paragraph).

`fleet/`: `Fleet` (header "Fleet" + "${n} instances" muted; Start all / Stop all; `AlertStrip`; grid `repeat(auto-fill, minmax(340px, 1fr))` gap 16 px; totals line; empty state), `InstanceCard` (props `{ inst: InstancePayload }`: a `Link` wrapping the card to `/instances/${name}`, `Thumb` with `StateChip` overlay, dimmed with caption on scheduled_break, replaced by the offline block on offline; name row: name (15 px semibold), port mono muted, phase caption muted; metrics 2 x 2 in mono: "Games today" `today.games`, "Trophies today" `signed(today.trophies)`, "Session" `duration(session.minutes_elapsed)` or "none", fourth label by state: farming/starting/stopping/reconnecting "Next break", scheduled_break/stopped "Next session", offline "Next retry"; value `hhmm(until)` or "none", offline "${N} min" from the note or "soon"; footer Stop (quiet, disabled with reason "Not running" when stopped, scheduled_break or offline), Restart (quiet), Open (text with a ChevronRight icon). Button clicks call `preventDefault` + `stopPropagation` so the card link does not fire), `AlertStrip` (props `{ alert: Alert; unread: number; onOpen(): void }`).

`instance/`: `Instance` (route `/instances/:name`; finds the instance in `["instances"]`; unknown name renders `ErrorBlock` with "unknown instance"; header per proposal; two columns 3fr / 2fr at >= 1100 px, stacked below), `LiveScreen` (props `{ name }`: 16:9 box up to 760 px wide, `Thumb` with `refreshMs` 15 000, "Refresh" text button forcing a fetch, "Full size" text button opening `screenshotUrl(name)` in a new tab), `Feed` (props `{ name; session: string | null }`: chips All / Matches / Interrupts / Errors (`Segmented` with the pressed one in accent), Follow `Switch` on by default; rows: `hhmmss(ts)` mono, 6 px dot, sentence; `getFeed(name, kind, 200)` initial load then SSE appends; auto-scroll to bottom while Follow is on; scrolling up more than 40 px turns Follow off; turning it on scrolls to bottom; empty copy per filter), `FarmPlan` (props `{ name }`; see section 10), `Schedule` (props `{ name }`; see section 11), `SessionPanel` (props `{ inst: InstancePayload; feedCounts: { avgRank: number | null; interrupts: number } }`; six mono figures "Games" `games_played ?? 0`, "Trophies" `signed(last_trophies - start_trophies)` or "0" when either is null, "Avg rank" `avgRank?.toFixed(1) ?? "none"`, "Disconnects" `disconnect_count ?? 0`, "Duration" `duration(minutes_elapsed ?? 0)`, "Interrupts" `interrupts`; when `inst.state` is stopped, scheduled_break or offline the panel keeps the last non-null values it rendered (a ref) and shows the caption "Session ended HH:MM" using the time the component first saw the stopped state, or `hhmm` of the last `stop` feed record when the feed has one).

Average rank and interrupt count for the session come from the feed: `avgRank` is the
mean of `fields.rank` over `games_logged`-adjacent records? No: ranks live in games.csv,
not the feed. Use `GET /api/stats?range=today&instances=${name}` `summary.avg_rank` for
"Avg rank" (label it "Avg rank today" in the panel) and count feed records with category
interrupts for "Interrupts". Session panel therefore takes `{ inst; avgRank; interrupts }`.

## 10. Roster on GET plan (Python, API task)

`GET /api/instances/{name}/plan` response grows:

```json
{
  "mode": "ladder", "prestige_start": "highest", "goal_trophies": 1000, "maxed_fallback": null,
  "current": {"brawler": "NORI", "trophies": 812, "goal": 1000},
  "roster": [{"id": 16000101, "name": "NORI", "trophies": 812, "highest": 830, "rank": 25, "power": 11}],
  "queue": ["TARA", "SHELLY", "DYNAMIKE"],
  "roster_status": "ok"
}
```

- `current.brawler` = the instance's `farm_brawler` from its view (null when none);
  `current.trophies` = that brawler's trophies from the roster (null when unknown);
  `current.goal` = the plan's goal for the current mode (`goal_trophies` for ladder,
  `farmplan.PRESTIGE_GOAL` for prestige).
- `roster` = the owned brawlers from `ApiClient(token).get_player(tag)["brawlers"]`
  mapped to `{id, name, trophies, highest (highestTrophies), rank, power}`, sorted by
  trophies descending; `null` when unavailable.
- `queue` = `farmplan.plan_queue(plan, roster_brawlers, current=current.brawler, n=3)`:
  a NEW pure function in `brawlfarm/core/farmplan.py` (no change to `choose_target` or any
  existing function): ladder → owned brawlers under `goal_trophies`, excluding `current`,
  sorted by trophies ascending then name; prestige → the prestige pool (under
  `PRESTIGE_GOAL`) ordered by `prestige_start` (highest → descending, lowest → ascending),
  excluding `current`; returns the first `n` names. Empty list when the roster is null.
- `roster_status`: `"ok"`, `"no_token"` (settings.connection.brawl_api_token blank),
  `"no_tag"` (instance player_tag blank), `"unavailable"` (the upstream call raised; a
  stale cached roster, if any, is still returned).
- `brawlfarm/api/roster.py`: `class RosterCache` with `get(name, tag, token, *, now, fetch)`
  keyed by instance name, TTL 300 s, one lock per name, `fetch` injectable (defaults to a
  thread-run `ApiClient(token=token).get_player(tag)`), keeps the last good value on
  failure. Stored on `app.state.roster`. The route awaits `asyncio.to_thread`.
- Never log the token or the tag. Tests use a fake `fetch` and a fake clock; cover ok,
  no_token, no_tag, unavailable-with-stale, TTL expiry, and `plan_queue` for both modes.
- `PUT /api/instances/{name}/plan` returns the same enriched shape (call the same helper).

Also in the API tasks:
- `POST /api/alerts/dismiss-all` → 204, dismisses every undismissed alert (`AlertStore.dismiss_all()`), test included.
- `FeedRecord` gains `seq: int` (1-based line index within the session file) on both the
  GET path and the tailer; the tailer counts existing lines when it first seeks to EOF so
  its numbering continues from the file's real line count; the SSE feed payload becomes
  `{"instance", "session", "record"}`. Tests updated and one new test proves GET and SSE
  agree on `seq` for the same line.

## 11. Schedule timeline (`lib/schedule.ts`, `instance/Schedule.tsx`)

Pure geometry: `timeline(payload: SchedulePayload, nowIso: string): { blocks: { leftPct: number; widthPct: number; state: "past" | "active" | "future" }[]; nowPct: number; ticks: { hour: number; leftPct: number }[] }`
with ticks at 0, 6, 12, 18, 24, percentages of the local calendar day of `payload.now`
(a session crossing midnight is clipped to the day). Test the geometry with fixed inputs.
`Schedule` renders: header "Schedule" with `Switch` "Schedule on" (`patchSchedule(name, { enabled })`),
the bar (past blocks at 40 % opacity in idle, active in ok, future in idle, now line 2 px
accent), the override `Chip` ("Override: run until HH:MM" / "Override: stop until HH:MM")
with an "x" text button that sends `clear_override: true`, a row "Run for" `Field` number
(default 2, min 0.5, step 0.5) + "hours" + "Start" `Button` primary (`startInstance(name, hours)`),
"Redraw today" `Button` quiet (`patchSchedule(name, { redraw: true })`, then refetch
`["schedule", name]` after 2 s and 10 s because the draw happens on the supervisor tick),
and the empty copy when `sessions` is empty.

## 12. Farm plan panel (`instance/FarmPlan.tsx`)

Reads `["plan", name]`. Controls write immediately with `putPlan` (goal debounced 500 ms,
validated as an integer >= 0), optimistic update, "Saved HH:MM" caption after success,
`ErrorBlock` inline on failure with the previous values restored. `Segmented` "Plan"
Ladder / Prestige; when prestige, a second `Segmented` "Start with" Highest / Lowest;
`Field` "Goal" number with suffix "trophies" (ladder only; prestige shows "Goal 1000, the
prestige threshold" muted); `Switch` "Maxed fallback" that enables a text `Field`
"Fallback brawler" (`list` bound to a `<datalist>` of roster names); rows: "Current
brawler" (name mono, `${trophies} / ${goal}` mono, a 3 px progress bar accent over line,
capped at 100 %), "Next in queue" (three rows name + trophies from the roster), "Show all
brawlers" text button toggling the full roster list (name, trophies, sorted descending),
roster status copy when the roster is null.

## 13. Safety, hygiene and process constraints (Global Constraints for the plan)

- The UI never sends a tap, never exposes shop or purchase actions, never bypasses the
  API. Only these files under `brawlfarm/core` may change: `farmplan.py` (adding
  `plan_queue` only). `controller.py`, `states.py`, `vision.py` and the calibration block
  of `config.py` are not touched. The never-tap rail tests must pass unchanged.
- Loopback only, no auth, no CORS middleware (the Vite proxy handles dev).
- Instance names in URLs are used as given; the API validates them (`^[A-Za-z0-9_-]{1,32}$`).
- Scrub: `uv run python tools/scrub_check.py` prints `0 hit(s)` before every commit; no
  player tag, nickname, user path or token appears in code, tests, fixtures, screenshots
  or PR text. Test fixtures use names Pie64 / Pie64_1 / Pie64_3, ports 5555 / 5565 / 5585,
  tag `#2P0YLQ9` (a made-up tag that the scrub list does not match).
- Copy: no em-dashes, no emoji, no exclamation marks; state = word plus colour.
- Every commit: conventional message plus the two trailers
  `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>` and
  `Claude-Session: https://claude.ai/code/session_01CQ1GimQ3uiR2sXPzfZLNWV`; `git config user.name` is `as9pa`.
- Tests: vitest for every lib function and component behaviour named above; pytest for
  every API change; `pnpm typecheck`, `pnpm test`, `pnpm build`, `uv run ruff check .`,
  `uv run ruff format --check .`, `uv run pytest -q` green before each commit.
- The branch is `phase-4/ui-shell-fleet-instance` from `main`; one PR; the PR carries
  screenshots of the real panel with the player tag and thumbnails blurred (playwright-cli
  `eval` sets `filter: blur(14px)` on `[data-private]` elements before the shot; the
  Instance header tag and every `Thumb` image carry `data-private`).
- Live evidence before done: the real instance (Pie64 on 5555) driven from the panel:
  Start from the card, the chip walks Starting → Farming, the feed streams a match, Stop
  shows "Stopping after this match" then Stopped; a plan change is visible in
  `farmplan.json` within a minute; the connection pill turns Reconnecting when the server
  is stopped and Live when it returns.

## 14. Task list for the plan (12 tasks, this order)

1. Web scaffold: pnpm/corepack, Vite + React + TS + Tailwind v4, theme.css tokens, fonts, `index.html` (title "brawlfarm", an inline SVG favicon of a gold square), `App` rendering the wordmark, vitest setup and one smoke test, CI steps, pyproject artifacts/exclude, README "Developing the panel" section. Verify: `pnpm build` produces `brawlfarm/web/dist/index.html` and `uv run pytest -q tests/test_api_app.py` still passes; `brawlfarm --no-browser` serves the built page.
2. Data layer: `api/client.ts`, `api/types.ts`, `api/*.ts`, `lib/time.ts`, `lib/format.ts`, `lib/toast.ts`, `live/useVisiblePolling.ts`, `live/useEvents.ts` with tests (fake fetch, fake EventSource class injected via a module-level `setEventSourceFactory` for tests).
3. UI primitives: `Button`, `StateChip`, `Chip`, `Switch`, `Segmented`, `Field`, `Toast` + `Toaster`, `Drawer`, `ErrorBlock`, `Thumb`, `lib/states.ts`; tests for StateChip mapping (all seven), Toast undo and timeout, Thumb error state and object URL revocation, Drawer escape.
4. Shell: `App` (providers, routes, theme bootstrap, SSE handlers, Toaster), `Shell`, `Rail`, `TopBar`, `AlertsDrawer`, `Placeholder`; tests for rail dots, pill states, badge count, drawer dismiss and dismiss-all calls.
5. API additions, Python: `POST /api/alerts/dismiss-all`, feed `seq` and SSE `session`, tests.
6. Fleet: `Fleet`, `InstanceCard`, `AlertStrip`, totals line, empty state, Start all / Stop all, toasts with Undo on stop; tests per card state (seven), totals text, empty copy, stop toast undo calls start.
7. Roster API, Python: `farmplan.plan_queue`, `api/roster.py` `RosterCache`, enriched GET/PUT plan, tests.
8. Instance page frame: route, header, `LiveScreen`, layout; tests for unknown instance, header actions, Refresh forcing a fetch, Full size link.
9. Feed: `lib/feedText.ts` (full table), `Feed` component with chips, Follow, SSE append and de-dup; tests.
10. FarmPlan panel; tests (mode switch writes PUT, goal debounce, fallback field enabling, roster status copy, progress bar cap).
11. Schedule and Session panels: `lib/schedule.ts`, `Schedule`, `SessionPanel`; tests (geometry, override chip, redraw refetch timing with fake timers, freeze caption).
12. Finish: keyboard and focus pass, reduced motion, phone width, light theme check, README Running section update, live evidence with blurred screenshots, PR body.

## 15. Accepted proposal ids (all 27, for traceability in task briefs)

shell-rail, shell-topbar, shell-alerts, shell-live, shell-nav-soon, fleet-card-thumb,
fleet-card-metrics, fleet-actions, fleet-header-all, fleet-alert-strip, fleet-offline-card,
fleet-totals, fleet-states, fleet-empty, inst-header, inst-live, inst-feed, inst-plan,
inst-plan-roster, inst-schedule, inst-session, found-tokens, found-type, found-controls,
found-toasts, found-errors, found-icons.
