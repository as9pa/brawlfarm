# brawlfarm design spec

Date: 2026-09-10. Status: approved by the owner on the proposal page (33 of 33 items accepted) and the build plan page (Go).

brawlfarm is the open-source successor to the private `bsutil` repo. It keeps the Brawl Stars farm workers, the anti-ban scheduler and every safety rail, and replaces the Discord control plane and the PowerShell watchdog with one local app: a Python backend with a built-in supervisor and a web UI opened in the browser.

## 1. Goals

- One command starts everything and opens the control panel on localhost.
- A first-run wizard takes a new user from "BlueStacks installed" to "first instance farming" without editing files.
- Every capability the Discord bot exposed maps to one of five screens: Setup, Fleet, Instance, Stats, Settings.
- The repo is publishable: no account identifiers, no secrets, clean history, MIT license, honest README.
- The bot core is reused, not rewritten.

Non-goals for v1: non-Windows platforms, emulators other than BlueStacks 5, LAN or remote access, any AI in the runtime loop, quest-aware farming, auto-upgrade (the last two stay on hold by the owner's earlier decision).

## 2. Decisions locked in chat

| Decision | Value |
|---|---|
| Name | `brawlfarm` (all lowercase; GitHub repo `as9pa/brawlfarm`, PyPI name reserved for later) |
| Form factor | Local web app first. Desktop window (pywebview) and tray icon after v1. |
| Architecture | One integrated process: backend + supervisor + web UI. Workers stay one subprocess per instance. |
| Repo | New public repo with clean history. `as9pa/bsutil` stays private and is archived on GitHub when brawlfarm is live. The local `bsutil` folder is not modified. |
| Web UI stack | Option A: Vite, React, TypeScript, Tailwind v4, components owned in the repo. Built UI ships inside the Python wheel. |
| Platform | Windows 11 + BlueStacks 5 only. Python 3.13, managed with uv. |

## 3. Process model

```
brawlfarm (one process, started by the `brawlfarm` command)
  |- supervisor task     (asyncio; replaces tools/watchdog.ps1)
  |- FastAPI app         (127.0.0.1:<port>; serves the built UI and the API; SSE event stream)
  |- worker subprocess   x N  (one per instance; `python -m brawlfarm.worker`, same env contract as today)
```

- The `brawlfarm` command starts the supervisor and the API, binds 127.0.0.1 only, and opens the default browser. There is no authentication in v1; non-loopback connections are refused.
- Closing the browser changes nothing. Closing the process leaves workers running; the next start reattaches through `status.json` PIDs.
- Worker env contract, unchanged from bsutil: `BRAWL_ADB_PORT`, `BRAWL_PLAYER_TAG`, `BRAWL_DATA_DIR`. The supervisor sets these exactly as the watchdog did.
- One worker per instance, ever. Kill only by PID read from that instance's `status.json`, never by process name or command line.

## 4. Package layout

```
brawlfarm/
  __init__.py, __main__.py        # CLI entry: `brawlfarm` (serve + open browser), `brawlfarm --no-browser`
  settings.py                     # typed settings model, config.toml load/save, data directory resolution
  core/                           # the farm core, ported from bsutil bot/ (controller, states, vision, adb,
                                  #   scheduler, farmplan, status, datalog, api, notify, stats, recalib, jsonio,
                                  #   onboarding), plus config.py holding calibration constants only
  worker.py                       # `python -m brawlfarm.worker`, ported from bsutil run.py
  supervisor/                     # loop, state, control (stop/kill), backoff, scheduler tick
  api/                            # FastAPI app, routes, SSE events, static file serving
  web/                            # Vite project (src/) and the built dist/ (packaged into the wheel by CI)
  setup/                          # discover.py (adb + instances), checks.py (display check)
templates/                        # anchor template PNGs used by core/vision.py (ported as-is)
tests/                            # farm-core tests ported from bsutil plus new tests per phase
docs/                             # setup.md, PLAN.md, superpowers/specs, superpowers/plans
```

## 5. Settings

One file, `config.toml`, in the brawlfarm data directory. Default data directory on Windows: `%LOCALAPPDATA%\brawlfarm`. Override with `BRAWLFARM_HOME` for development and tests.

```
[app]
port = 8765
theme = "system"            # system | dark | light

[connection]
adb_path = "C:\\Program Files\\BlueStacks_nxt\\HD-Adb.exe"   # autodetected; user-editable
brawl_api_token = ""        # optional; empty disables battle-log stats

[behavior]
winrate_aware = true
opportunity_cost = false    # off by default, it thrashed near-maxed rosters (bsutil, 2026-06-14)
gas_aware = true
bush_hide = false           # experimental, not validated live
close_game_on_stop = true
dnd_at_start = true

[scheduler]
default_enabled = true

[notifications]
webhook_url = ""            # any webhook that accepts {"content": ...}; Discord webhooks work
ntfy_topic = ""
ntfy_server = "https://ntfy.sh"
events = ["crash", "recover", "offline", "wrong_mode", "recalibrate"]

[[instances]]
name = "Pie64"
adb_port = 5555
player_tag = ""             # optional; only used for the Brawl Stars API
```

- Per-instance folders live under `<data dir>/instances/<name>/` and hold `status.json`, `farmplan.json`, `schedule.json`, `override.json`, `games.csv`, `menu_trophies.csv`, `session-*.jsonl`, `stop.flag`, `recalib.json`, `shop_done.json`, `archive/`. Formats are unchanged from bsutil.
- Calibration constants (tap coordinates, OCR regions, HSV windows, timings, needles) stay in `brawlfarm/core/config.py`. They are not user settings. Phase 8 adds a calibration file that overrides them.
- Environment variables remain as developer overrides only. `BRAWL_*` feature flags read by the core keep working; the settings model writes them into the worker's environment so the core does not need to know about `config.toml`.
- The settings model is typed (pydantic). Loading a missing file yields defaults; saving is atomic (write temp, replace).

## 6. Supervisor

Ported from `tools/watchdog.ps1` into Python, one tick per interval (default 60 s):

1. Scheduler tick for every instance (`core/scheduler.py`, default on, fail-open to always-run).
2. Read each instance's `status.json`; classify by heartbeat age: healthy, stale, dead.
3. Read the schedule's desired state and any manual override.
4. Desired stop and alive: write `stop.flag`, then after the grace period (110 s) kill by PID.
5. Desired run and unhealthy: kill the stale PID if any, then launch. At most one launch per tick for stagger.
6. Offline backoff: before relaunching an instance that fails the adb probe, wait 2, 4, 8, 16, then 30 minutes. "Retry now" resets it.
7. Optional healthchecks.io ping.

Instance state, derived once and shown everywhere:

| State | Meaning |
|---|---|
| Farming | Worker alive, heartbeat fresh, scheduler wants run |
| Stopped | No worker; user stopped it or schedule off and not started |
| Scheduled break | No worker; scheduler says break, with the resume time |
| Reconnecting | Worker alive after a disconnect event, not yet back to farming |
| Offline | adb probe fails; BlueStacks window closed; with the next retry time |

Stop is graceful by default: write `stop.flag` and the schedule override; the UI shows "Stopping after this match" with Undo for the grace window. "Stop now" appears only while a stop is pending and kills by PID. Restart is stop then launch.

## 7. API and events

FastAPI, JSON, no auth, loopback only.

- `GET /api/instances` list with derived state; `POST /api/instances/{name}/start|stop|stop-now|restart`
- `GET /api/instances/{name}/screenshot.png` (adb screencap, 1600 x 900)
- `GET|PUT /api/instances/{name}/plan` (farmplan.json), `GET|PUT /api/instances/{name}/schedule` (enabled, override, redraw)
- `GET /api/instances/{name}/feed?kind=all|matches|interrupts|errors&limit=N` (session JSONL narration)
- `GET /api/stats?range=today|7d|30d|all&instances=a,b` (summary, series, brawlers, ranks, recent), `GET /api/stats/export.csv`
- `GET|PUT /api/settings`, `POST /api/setup/scan`, `POST /api/setup/test`, `POST /api/setup/display-check`
- `GET /api/alerts`, `POST /api/alerts/{id}/dismiss`
- `GET /api/events` server-sent events: instance state changes, feed lines, alerts, supervisor log lines.

Alerts come from the worker's existing event kinds (`crash`, `recover`, `offline`, `wrong_mode`, `recalibrate`, `bad_resolution`). The optional push notifier (`core/notify.py`, webhook or ntfy) sends the same events.

## 8. Web UI

- Vite + React + TypeScript + Tailwind v4. Components owned in the repo (shadcn-style), one icon library, Archivo for UI text and JetBrains Mono for ids, values and log lines, both self-hosted.
- Dark by default, light available, system-following unless the user picks one.
- Tokens (dark): ground `#0C0F14`, panel `#12161D`, panel-2 `#181D26`, line `#252C38`, text `#E7EAF0`, muted `#8A94A6`, accent (trophy gold) `#E0B84B`, ok `#58B77E`, warn `#E08A3C`, bad `#E06565`, idle `#6B7484`. Light: ground `#F3F4F6`, panel `#FFFFFF`, panel-2 `#EEF0F3`, line `#D9DDE4`, text `#161A21`, muted `#5F6876`, accent `#9A7418`, ok `#2B8A57`, warn `#B8631E`, bad `#B94A4A`, idle `#7B838F`.
- Chart series use the validated categorical palette (dark `#3987E5`, `#D95926`, `#199E70`; light `#2A78D6`, `#EB6834`, `#1BAF7A`), capped at three series; more instances fold into Other. The accent is never a series color.
- Radius: 6 px on controls, 10 px on panels. No gradients, no glows, no emoji in UI text.
- Copy is plain: what happens, what went wrong, how to fix it. State chips always carry a word plus a color.
- Every screen has designed empty, no-results, error, toast/undo and focus states.
- Before coding each screen, do a taste-skill design read and collect two or three Mobbin references, linked in the pull request.

### Screens

**Setup wizard** (first run, and Settings > Connection > Run setup again). Steps: BlueStacks (find `HD-Adb.exe`, ask for the folder only if missing), Instances (scan `adb devices`, read names from the BlueStacks config, test each row, manual port field), Display (screenshot per selected instance, require 1600 x 900 at DPI 240, show the BlueStacks display settings path on mismatch, Recheck), API token (optional, link to developer.brawlstars.com, note about IP allow-listing, Skip for now), Done (lands on Fleet with the first instance started). Each step writes its result to `config.toml` as it completes, so an interrupted wizard resumes.

**Fleet** (home). One card per instance: name, port, state chip, live thumbnail refreshed every 15 s while the tab is visible with its age, phase, games today, trophies today, session length, next schedule event, Stop, Restart, Open. Header: Start all, Stop all. A one-line strip for the newest unread alert; an Alerts button with a count opens a drawer. A quiet totals line at the bottom, no big-number tiles. Offline cards say "BlueStacks window not found. Retrying in N min. Open the instance, or Retry now."

**Instance**. Header with name, port, tag, state chip, Stop, Restart, Screenshot. Left: live screen (15 s refresh while visible, Refresh, Full size) and the activity feed from the session narration with All, Matches, Interrupts, Errors chips. Right: farm plan (mode Ladder or Prestige, maxed fallback toggle with brawler picker, goal, current brawler with progress, next three in the queue, Show all brawlers), schedule (on/off, today's 24-hour timeline with sessions and a now line, Run for N hours, Redraw today), this session (games, trophies, avg rank, disconnects, duration, interrupts; freezes with "Session ended HH:MM").

**Stats**. Range tabs Today, 7 days, 30 days, All; instance chips; Export CSV. Inline metrics row (games, trophies, trophies per hour, average rank, top-4 rate, time farmed). One line chart of cumulative trophy change, one axis, one series per instance, legend plus end labels, crosshair tooltip, table view behind a toggle. Per-brawler table (icon, name, games, net, avg rank, top-4 rate; sortable), rank distribution as thin horizontal bars with direct labels, recent games list. Empty states: no token ("Battle log unavailable. Add a Brawl Stars API token in Settings to see per-game stats."), no games yet ("Stats appear after the first match.").

**Settings**. Left nav: Instances (table with name, ADB port, player tag, data folder, status; Add, Edit, Remove, Scan again; removing keeps the data folder), Connection (adb path, API token, Run setup again), Behavior (the toggles in section 5 with one plain sentence each; performance switches under Advanced), Schedule (defaults), Notifications (webhook, ntfy, event list), Data (open data folder, delete one instance's data, reset all settings; typed-name confirmation), About (theme, version, links).

### Brawler icons

Everywhere a brawler is named on Stats and on the Instance farm plan: a 22 px rounded icon before the name. Source: the Brawlify CDN, `https://cdn.brawlify.com/brawlers/borderless/<id>.png`, keyed by the official API's brawler id (the same source bsutil's Discord emoji sync used). Fetched on first use into `<data dir>/cache/brawlers/<id>.png`; refreshed only when a new id appears. Fallback: the brawler's initial in a square of the same size, so rows never shift. README carries an attribution line for Brawlify and notes that the art belongs to Supercell under its fan content policy.

## 9. Safety rails (unchanged, absolute)

- Never tap: ACCEPT on a team invite, GET/Upgrade, EQUIP NOW, shop buy buttons, the pass VAULT, anything gem-priced. Never blind-tap in the shop.
- Navigate by taps, verify the screen by template or OCR before acting, bail to the menu on any failed verify so stale coordinates degrade to logged no-ops.
- One worker per instance. Kill by PID from `status.json` only.
- The controller asserts 1600 x 900 at startup and exits otherwise.
- No AI in the runtime loop: deterministic OpenCV template matching and OCR. Frame recording for future training is opt-in and separate.
- No user-supplied string reaches a shell. Instance names are validated (`[A-Za-z0-9_-]{1,32}`) because they become folder names and adb serials are built from validated ports only.

## 10. Open-source hygiene

- Scrub list, enforced by a CI check that fails the build: the three legacy player tags, the three legacy account nicknames (as whole words in code, docs and filenames), the legacy machine's user path, and any `discord` import. Test fixtures that carried nicknames in their filenames are renamed on port.
- Never commit: `.env`, the data directory, captures, logs, screenshots of the owner's accounts.
- MIT license. README: what it does, the never-tap rules, setup, the no-AI principle, a Fleet screenshot, attribution. `docs/setup.md`: BlueStacks install, enable ADB (Settings, Advanced, Android Debug Bridge), display 1600 x 900 at DPI 240, finding ports, the API token portal. `CONTRIBUTING.md`: safety-rail violations are a blocker in review regardless of other merit; PR expectations; how to run tests.
- Research docs and Discord docs stay in bsutil, private.

## 11. Testing

- Farm-core tests ported from bsutil (scheduler, farm plan, vision, bush and gas, never-tap rail, recalibration, network stuck, wrong mode, api client, datalog, status). Discord tests dropped. `conftest.py` must not import anything Discord-related.
- New tests per phase: settings model round-trip and defaults; supervisor state derivation and backoff; API routes with a fake instance directory; discovery parsing; stats aggregation against fixture CSVs.
- CI on GitHub Actions for every pull request: `ruff check`, `ruff format --check`, `pytest`, the scrub grep. The UI build runs in CI from phase 4.
- Live evidence before any phase is called done: screenshots of the panel driving a real instance, `games.csv` deltas, supervisor log excerpts.

## 12. Phases

1. Repo and core: new repo, uv project, `brawlfarm/core` from `bot/` with the scrub, tests ported, CI, spec, PLAN.md, license, skeleton README.
2. Settings and supervisor.
3. API and events.
4. UI shell, Fleet, Instance.
5. Setup wizard and Settings.
6. Stats with brawler icons.
7. Docs and publish; archive bsutil.
8. After v1: calibration page, game-update recalibration, desktop window and tray icon, labeled frame recorder.

Each phase is one pull request, reviewed before merge, merged and captured live before the next starts.

## 13. Provenance

- Proposal page (33 items, all accepted, one note on brawler icons): https://claude.ai/code/artifact/dae89ddc-66b7-4ac5-b989-70810e291475
- Build plan page (Go): https://claude.ai/code/artifact/778a7961-66f1-431f-84ca-8ad826b81320
- Legacy: `as9pa/bsutil` (private), README and `docs/codebase-tour.md` there describe the core this spec reuses.
