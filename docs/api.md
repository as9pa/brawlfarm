# The panel and its API

The panel lives at `http://127.0.0.1:8765/`: a Fleet page with one card per instance led by its live screen, and an Instance page with the screen, the activity feed in plain sentences, the farm plan, today's schedule and the session's figures. Change the port in Settings (it takes effect on the next start) or for one run with `--port`. The API behind it is browsable at `http://127.0.0.1:8765/docs`.

The API binds 127.0.0.1 only and has no authentication: anything that can reach it can drive your instances, so do not port-forward it or put it behind a reverse proxy.

| Method | Path | What it does |
| --- | --- | --- |
| GET | `/api/health` | version, data directory, instance count, uptime |
| GET | `/api/instances` | one payload per instance: state, phase, session, today's games and trophies, and the last finished session |
| POST | `/api/instances/{name}/start` | start, or run for `{"hours": N}` |
| POST | `/api/instances/{name}/stop` | stop after the current match |
| POST | `/api/instances/{name}/stop-now` | kill the worker by its PID, only while a stop is pending |
| POST | `/api/instances/{name}/restart` | stop now, relaunch on the next tick |
| POST | `/api/instances/{name}/retry` | clear the offline backoff and probe again |
| DELETE | `/api/instances/{name}/data` | delete that instance's folder; the instance stays in `config.toml` |
| GET | `/api/instances/{name}/screenshot.png` | a live adb screencap |
| GET | `/api/instances/{name}/preview.jpg` | the small frame the worker writes every second, or one throttled live capture when it is stopped |
| GET, PUT | `/api/instances/{name}/plan` | the farm plan, plus the owned roster, the queue and the current brawler |
| GET, PUT | `/api/instances/{name}/schedule` | today's sessions, the override, on/off, redraw |
| GET | `/api/instances/{name}/feed` | session narration with a `seq` on every record, `kind=all\|matches\|interrupts\|errors` |
| GET | `/api/stats` | `range=today\|7d\|30d\|all`, `instances=a,b` |
| GET | `/api/stats/export.csv` | the same selection as a CSV download |
| GET | `/api/brawlers/{name}/icon.png` | the brawler's portrait from a local cache, fetched once from the Brawlify CDN |
| GET | `/api/connection/check` | whether the Brawl Stars token works: `ok`, `no_token`, `no_tag`, `rejected` or `unreachable` |
| GET, PUT | `/api/settings` | the whole `config.toml` document |
| POST | `/api/settings/reset` | every section back to its default; instances and their folders are kept |
| POST | `/api/settings/open-data-folder` | open the data folder in Explorer; 501 anywhere but Windows |
| POST | `/api/notifications/test` | send one test alert to every configured channel |
| POST | `/api/setup/scan` | find adb and the BlueStacks instances |
| POST | `/api/setup/test` | can adb reach this port |
| POST | `/api/setup/display-check` | is this instance 1600 x 900 at DPI 240 |
| GET | `/api/alerts` | the alert list and its unread count |
| POST | `/api/alerts/{id}/dismiss` | mark one alert read |
| POST | `/api/alerts/dismiss-all` | mark every alert read |
| GET | `/api/events` | server-sent events |

## Live events

`GET /api/events` is a server-sent event stream with four kinds: `instance` (a state change), `feed` (a new session narration line), `alert`, and `log` (the supervisor's own log lines). It replays from `Last-Event-ID` on a reconnect and sends a keepalive comment every 15 seconds. Alerts are kept in memory only, so a restart clears them; the session files under `instances/<name>/` keep the history.

## Notifications and health monitoring

`[notifications]` in `config.toml` takes a webhook URL, an ntfy topic and server, the list of event kinds worth sending, and `healthchecks_url`. Every completed supervisor tick GETs that URL, so a supervisor that stops ticking raises an alarm on healthchecks.io, or anything else that speaks the same one-URL protocol, without you watching the window.
