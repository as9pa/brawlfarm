# brawlfarm

An open-source Brawl Stars trophy farmer for BlueStacks on Windows, with a local control panel in your browser.

Status: under construction. Phase 4 of 8 (the control panel: shell, Fleet and Instance). The setup wizard and the stats screens arrive in later phases; see `docs/PLAN.md`.

## What it does

- Farms Trio Showdown on its own: queue, play, results, back to the menu, repeat.
- Survives interruptions: rewards, popups, rank-ups, disconnects, crashes, freezes, team invites.
- Two farm modes: ladder (raise the whole roster in 100-trophy tiers) and prestige (finish one brawler to 1000 at a time), plus an optional maxed fallback.
- An anti-ban scheduler that plays human-shaped sessions with breaks, on by default.
- Runs several BlueStacks instances at once, one worker per instance.

## Safety rails

These are absolute and are enforced in code and in review:

- Never taps ACCEPT on a team invite, GET or Upgrade, EQUIP NOW, any shop buy button, the pass VAULT, or anything priced in gems. Never blind-taps in the shop.
- Every navigation verifies the screen before acting and bails to the menu on a failed check, so stale coordinates degrade to logged no-ops.
- One worker per instance. Processes are stopped by the PID recorded in that instance's status file, never by name.
- No AI in the runtime loop: deterministic OpenCV template matching and OCR.

## Requirements

Windows 11, BlueStacks 5 with Android Debug Bridge enabled, an instance display of 1600 x 900 at DPI 240, Python 3.13 and [uv](https://docs.astral.sh/uv/). Setup steps arrive with the wizard in phase 5 and in `docs/setup.md` in phase 7.

## Development

```
uv sync --group dev
corepack enable
pnpm --dir brawlfarm/web install
pnpm --dir brawlfarm/web build     # the panel is served from brawlfarm/web/dist
uv run pytest
pnpm --dir brawlfarm/web test && pnpm --dir brawlfarm/web typecheck
uv run ruff check . && uv run ruff format --check .
uv run python tools/scrub_check.py
```

If `corepack enable` fails with EPERM, which is what a Windows shell without elevation gives you, `npm install -g pnpm@10.17.1` installs the same pnpm.

`pnpm --dir brawlfarm/web dev` serves the panel on Vite's port with hot reload and proxies `/api` to a `uv run brawlfarm` on 8765, so the two run side by side while you work on the UI.

## Running

```
uv run brawlfarm                 # supervise every instance and open the panel
uv run brawlfarm --no-browser    # same, without opening a browser
uv run brawlfarm --port 9000     # serve the panel somewhere else
uv run brawlfarm --once          # one supervisor tick, print the instances, exit
```

Settings live in `%LOCALAPPDATA%\brawlfarm\config.toml` (override the folder with `BRAWLFARM_HOME`). Add one `[[instances]]` table per BlueStacks instance with its `name` and `adb_port`; each instance's files live under `instances/<name>/`. Stopping the process leaves workers running; the next start reattaches to them through their status files.

## The panel and its API

The panel lives at `http://127.0.0.1:8765/`: a Fleet page with one card per instance led by its live screen, and an Instance page with the screen, the activity feed in plain sentences, the farm plan, today's schedule and the session's figures. Change the port in Settings (it takes effect on the next start) or for one run with `--port`. The API behind it is browsable at `http://127.0.0.1:8765/docs`.

The API binds 127.0.0.1 only and has no authentication: anything that can reach it can drive your instances, so do not port-forward it or put it behind a reverse proxy.

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/health` | version, data directory, instance count, uptime |
| GET | `/api/instances` | one payload per instance: state, phase, session, today's games and trophies |
| POST | `/api/instances/{name}/start` | start, or run for `{"hours": N}` |
| POST | `/api/instances/{name}/stop` | stop after the current match |
| POST | `/api/instances/{name}/stop-now` | kill the worker by its PID, only while a stop is pending |
| POST | `/api/instances/{name}/restart` | stop now, relaunch on the next tick |
| POST | `/api/instances/{name}/retry` | clear the offline backoff and probe again |
| GET | `/api/instances/{name}/screenshot.png` | a live adb screencap |
| GET, PUT | `/api/instances/{name}/plan` | the farm plan, plus the owned roster, the queue and the current brawler |
| GET, PUT | `/api/instances/{name}/schedule` | today's sessions, the override, on/off, redraw |
| GET | `/api/instances/{name}/feed` | session narration with a `seq` on every record, `kind=all\|matches\|interrupts\|errors` |
| GET | `/api/stats` | `range=today\|7d\|30d\|all`, `instances=a,b` |
| GET | `/api/stats/export.csv` | the same selection as a CSV download |
| GET, PUT | `/api/settings` | the whole `config.toml` document |
| POST | `/api/setup/scan` | find adb and the BlueStacks instances |
| POST | `/api/setup/test` | can adb reach this port |
| POST | `/api/setup/display-check` | is this instance 1600 x 900 at DPI 240 |
| GET | `/api/alerts` | the alert list and its unread count |
| POST | `/api/alerts/{id}/dismiss` | mark one alert read |
| POST | `/api/alerts/dismiss-all` | mark every alert read |
| GET | `/api/events` | server-sent events |

### Live events

`GET /api/events` is a server-sent event stream with four kinds: `instance` (a state change), `feed` (a new session narration line), `alert`, and `log` (the supervisor's own log lines). It replays from `Last-Event-ID` on a reconnect and sends a keepalive comment every 15 seconds. Alerts are kept in memory only, so a restart clears them; the session files under `instances/<name>/` keep the history.

### Notifications and health monitoring

`[notifications]` in `config.toml` takes a webhook URL, an ntfy topic and server, the list of event kinds worth sending, and `healthchecks_url`. Every completed supervisor tick GETs that URL, so a supervisor that stops ticking raises an alarm on healthchecks.io — or anything else that speaks the same one-URL protocol — without you watching the window.

## Legal

brawlfarm is not affiliated with or endorsed by Supercell. Brawl Stars and its art belong to Supercell; brawler icons are fetched at runtime from the Brawlify CDN and cached locally under Supercell's fan content policy. Automating the game may violate its terms of service; use at your own risk. MIT licensed.
