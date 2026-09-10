# Phase 3: API and events. Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put spec section 7 on the wire: a loopback-only FastAPI app that lists and controls instances, reads and writes settings, the farm plan and the schedule, runs the setup wizard's adb probes, serves a live screenshot, streams instances, feed lines, alerts and log lines over SSE, aggregates stats, and turns `uv run brawlfarm` into "supervisor + API + browser" instead of a headless loop.

**Architecture:** One process and one asyncio loop. `uvicorn` serves the app built by `brawlfarm/api/app.py::create_app(sup, home)` while `Supervisor.run_forever()` runs as a task beside it, so the API talks to the same live supervisor object the tick uses; the tick itself runs in a worker thread (`asyncio.to_thread`), which is why supervisor listeners fire off the loop thread and the event bus has to be thread-safe. Route handlers are `async def` and hand anything blocking (adb subprocesses, pandas, file scans) to `asyncio.to_thread`; supervisor controls are quick file writes, so they are called directly and followed by `sup.poke()`. A new `brawlfarm/setup/` package holds the adb discovery and display checks the wizard needs, kept apart from `core/adb.py` so the panel never mutates the worker's process-global config.

**Tech Stack:** Python 3.13, uv, pytest, pytest-asyncio (strict), ruff. New runtime deps: `fastapi>=0.115`, `uvicorn>=0.30`. New dev dep: `httpx>=0.27` (starlette's `TestClient` is an httpx client). Resolved today: fastapi 0.141.1, uvicorn 0.52.4, httpx 0.28.1, starlette 1.6.0. No `sse-starlette`: the event stream is a plain `StreamingResponse`.

**Spec:** `docs/superpowers/specs/2026-09-10-brawlfarm-design.md` (sections 3, 4, 7, 9, 10, 11). This phase implements section 7 in full; the React UI that consumes it is phase 4.

## Global Constraints

- Python `>=3.13`; every command runs through `uv run`. Windows shell: use bash (Git Bash) commands as written; paths with forward slashes.
- The legacy checkout is the sibling folder `../bsutil` (read-only; never modify it). Refer to it only by that relative path. Never write its absolute path, its account nicknames, or its player tags into any file in this repo, including this plan, commit messages and PR text.
- `uv run python tools/scrub_check.py` must print `0 hit(s)` before every commit. No file may `import discord` or `from discord`.
- Never paste an API response, a log excerpt, a screenshot or a CSV row that contains a real player tag, account nickname, Windows user path or webhook/token value into a commit message, the pull request, `docs/PLAN.md` or any file in the repo. Live evidence gets scrubbed first: replace tags with an invented one from the game's alphabet (`0289PYLQGRJCUV`, e.g. `#2P0YLQ9`) and instance names with `alpha`, `bravo`, `Pie64`.
- The API binds `127.0.0.1` only and refuses every non-loopback client with `403 {"detail": "loopback only"}` before the request reaches a route (spec section 3: no authentication in v1). `uvicorn` is started with `host="127.0.0.1"`, never `0.0.0.0`.
- Instance names match `[A-Za-z0-9_-]{1,32}` (spec section 9) and are validated with `settings.INSTANCE_NAME_RE` **before any filesystem access**, because they become folder names. An unknown or malformed name is `404 {"detail": "unknown instance"}`.
- No user-supplied string ever reaches a shell: every subprocess call uses an argument list with `shell=False`, and an adb serial is only ever `f"127.0.0.1:{int(port)}"` built from a validated integer port.
- One worker per instance. Kill only by the PID read from that instance's `status.json`, never by process name or command-line search.
- Safety rails in spec section 9 are untouched: do not edit the never-tap logic, the verify-then-act flow, the 1600 x 900 assertion, or any tap coordinate, OCR needle or timing in `core/controller.py`, `core/states.py`, `core/vision.py`, or the calibration block of `core/config.py`.
- Worker env contract (unchanged): `BRAWL_ADB_PORT`, `BRAWL_PLAYER_TAG`, `BRAWL_DATA_DIR`, plus `BRAWLFARM_HOME`. Env must be passed to `subprocess.Popen(env=...)` because `core/config.py` reads it at import time. Nothing in `brawlfarm/api/` or `brawlfarm/setup/` changes it.
- Data directory: `%LOCALAPPDATA%\brawlfarm` by default; `BRAWLFARM_HOME` overrides it. Layout: `<home>/config.toml`, `<home>/instances/<name>/`, `<home>/logs/`, `<home>/data/`. Readers never create an instance directory; writers call `mkdir(parents=True, exist_ok=True)` themselves.
- Supervisor timings are unchanged (tick 60 s, heartbeat stale 240 s, boot grace 180 s, stop escalation 110 s, offline alert after 3 misses). The API never reimplements them; it reads `sup.views()`.
- Every new `.py` file has a module docstring that says what the module is for. Every new test file has a docstring naming the behaviour it pins. Test output must be pristine (no warnings).
- `asyncio_mode = "strict"` is already set in `pyproject.toml`: every async test carries `@pytest.mark.asyncio`. Sync tests drive the app through `TestClient(app, client=("127.0.0.1", 50000))`.
- Commit messages are conventional (`feat:`, `fix:`, `test:`, `docs:`, `chore:`) and explain why. Git identity must be `as9pa` (`git config user.name`) before every commit. Work on branch `phase-3/api-and-events`.
- `ruff check .` and `ruff format --check .` clean before every commit (run `uv run ruff format <changed files>` and `uv run ruff check --fix <changed files>` first). Line length 100, lint select `E`, `F`, `W`, `I`.

## File Structure

New packages and files across all ten tasks:

```
brawlfarm/api/__init__.py         # docstring only: what the panel's HTTP surface is
brawlfarm/api/app.py              # create_app(sup, home) -> FastAPI: app.state, loopback guard, lifespan, /api/health, index + dist  (task 1)
brawlfarm/api/deps.py             # get_sup / get_home / resolve_instance: the name-to-(settings, dir) gate every per-instance route uses (task 2)
brawlfarm/api/instances.py        # GET /api/instances and start|stop|stop-now|restart|retry; view_to_dict, instance_payload, today_counts (task 2)
brawlfarm/api/settings_routes.py  # GET|PUT /api/settings: the whole config.toml document, with the live-instance removal guard          (task 2)
brawlfarm/api/setup_routes.py     # POST /api/setup/scan|test|display-check: the wizard's three probes, each in a thread                (task 4)
brawlfarm/api/screens.py          # GET /api/instances/{name}/screenshot.png: one adb frame, one lock per instance                      (task 4)
brawlfarm/api/plans.py            # GET|PUT /api/instances/{name}/plan: the FarmPlan model over core/farmplan.py                        (task 5)
brawlfarm/api/schedule.py         # GET|PUT /api/instances/{name}/schedule: enabled, override, redraw, today's sessions                 (task 5)
brawlfarm/api/events.py           # EventBus, Event, format_sse, BusLogHandler, GET /api/events                                         (task 6)
brawlfarm/api/feed.py             # classify, read_feed, FeedTailer, GET /api/instances/{name}/feed                                     (task 7)
brawlfarm/api/alerts.py           # Alert, AlertStore, GET /api/alerts, POST /api/alerts/{id}/dismiss                                   (task 8)
brawlfarm/api/stats.py            # aggregate, export_csv, GET /api/stats, GET /api/stats/export.csv                                    (task 9)
brawlfarm/setup/__init__.py       # docstring only: what the wizard's probes are
brawlfarm/setup/discover.py       # find_adb, bluestacks_conf_path, parse_bluestacks_conf, parse_devices, scan, probe_port               (task 3)
brawlfarm/setup/checks.py         # run_adb, serial, screencap_png, png_size, parse_wm_size, parse_wm_density, display_check            (task 3)
tests/apihelpers.py               # FakeWorld, build_settings, make_client: a supervisor with no real processes behind a TestClient     (task 1)
```

Existing files touched:

```
pyproject.toml, uv.lock           # fastapi, uvicorn (runtime); httpx (dev)                                                  (task 1)
tests/conftest.py                 # teardown also resets notify._overrides, notify._last_alert and scheduler.DEFAULT_ENABLED                     (task 1)
brawlfarm/core/scheduler.py       # tick's print()/traceback go through logging; new read_override() and is_enabled()        (tasks 1, 5)
brawlfarm/core/notify.py          # healthchecks_url in configure/_overrides, alert_title(), ping_healthchecks()             (task 8)
brawlfarm/supervisor/loop.py      # subscribe_alerts(), the healthchecks ping at the end of a successful tick                (task 8)
brawlfarm/__main__.py             # serve: uvicorn + run_forever, --port, --no-browser, the phase 2 flag fixes               (task 10)
README.md, docs/PLAN.md           # the Running section, the API table, the events and healthchecks notes                    (task 10)
```

Safety-rail files (`core/controller.py`, `core/states.py`, `core/vision.py`, the calibration block of `core/config.py`) are not touched by any task.

---
### Task 1: Dependencies, the app factory, the test harness, and the scheduler's log lines

The skeleton every later task hangs off: `create_app`, the loopback guard, the lifespan that runs one supervisor tick before the first request, `/api/health`, the placeholder index, and `tests/apihelpers.py`. It also closes two phase 2 deferrals that this phase needs: the conftest teardown that puts `notify._overrides` and `scheduler.DEFAULT_ENABLED` back, and the scheduler tick's `print()` lines, which have to become log records before the SSE log stream (task 6) can carry them.

**Files:**
- Modify: `pyproject.toml` (`dependencies` at lines 8 to 18, `[dependency-groups]` at line 24)
- Modify: `uv.lock` (regenerated by `uv add`)
- Modify: `brawlfarm/core/scheduler.py` (imports at 73 to 87, `tick` at 654 to 661, the prints at 730, 767 to 771 and 820)
- Modify: `tests/conftest.py` (whole file, 24 lines)
- Create: `brawlfarm/api/__init__.py`
- Create: `brawlfarm/api/app.py`
- Create: `tests/apihelpers.py`
- Create: `tests/test_api_app.py`
- Create: `tests/test_conftest_reset.py`
- Create: `tests/test_scheduler_logging.py`

**Interfaces:**
- Consumes: `Supervisor` (`tick`, `views`, `settings`) from `brawlfarm.supervisor`; `brawlfarm.__version__`; `settings.AppSettings`, `settings.InstanceSettings`, `settings.save`; `scheduler.set_enabled`.
- Produces:
  - `brawlfarm.api.app.create_app(sup: Supervisor, home: Path) -> FastAPI` with `app.state.sup`, `app.state.home`, `app.state.started_at` (a `time.monotonic()` stamp)
  - `brawlfarm.api.app.dist_dir() -> Path`, `brawlfarm.api.app.SpaFiles`, `brawlfarm.api.app.LOOPBACK_HOSTS`, `brawlfarm.api.app.PLACEHOLDER_HTML`
  - `GET /api/health -> {"version": str, "home": str, "instances": int, "uptime_s": float}`
  - `scheduler.log` (`logging.getLogger("brawlfarm.scheduler")`); `scheduler.tick()` no longer writes to stdout or stderr
  - `tests.apihelpers.FakeWorld`, `tests.apihelpers.FakeProc`, `tests.apihelpers.build_settings(names, ports, **overrides) -> AppSettings`, `tests.apihelpers.make_client(tmp_path, names, *, world, **settings_overrides) -> tuple[TestClient, Supervisor, Path]`, `tests.apihelpers.LOOPBACK`
- Consumed by: every later task (tasks 2 to 9 add routers to `create_app` and build their clients with `make_client`; task 10 calls `create_app` from the CLI).

- [ ] **Step 1: Branch and add the dependencies**

```bash
# The branch may already exist (the plan's own working branch); this is idempotent.
git switch phase-3/api-and-events 2>/dev/null || git switch -c phase-3/api-and-events
uv add fastapi uvicorn
uv add --group dev httpx
```

`pyproject.toml` afterwards (check that `uv add` produced exactly this; edit by hand if the version pins differ):

```toml
dependencies = [
  "opencv-python>=4.10",
  "numpy>=2.0",
  "requests>=2.32",
  "python-dotenv>=1.0",
  "rapidocr-onnxruntime>=1.3",
  "pandas>=2.2",
  "pydantic>=2.9",
  "tomli-w>=1.1",
  "psutil>=6.1",
  "fastapi>=0.115",
  "uvicorn>=0.30",
]
```

```toml
[dependency-groups]
dev = ["pytest>=8.3", "pytest-asyncio>=0.24", "ruff>=0.12", "httpx>=0.27"]
```

Confirm the resolution:

```bash
uv run python -c "import fastapi, uvicorn, httpx, starlette; print(fastapi.__version__, uvicorn.__version__, httpx.__version__, starlette.__version__)"
```

Expected: `0.141.1 0.52.4 0.28.1 1.6.0` (or newer patch releases of the same minors).

- [ ] **Step 2: Write the test harness `tests/apihelpers.py`**

Not a test file: pytest never collects it (no `test_` prefix), the API test modules import from it. It mirrors the `World` fake and the `make_sup` helper in `tests/test_supervisor_loop.py` so both suites inject the same seams.

```python
"""Fakes and builders for the API tests: a supervisor whose clock, adb probe, launcher,
liveness check, killer, sleep and events refresh are all in memory, an AppSettings
builder, and a TestClient whose lifespan has already run.

Mirrors the World fake in tests/test_supervisor_loop.py. Nothing here starts a process,
opens a socket or talks to adb; player tags are invented from the game's alphabet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

from brawlfarm import settings as S
from brawlfarm.api.app import create_app
from brawlfarm.core import scheduler
from brawlfarm.supervisor import Supervisor

T0 = datetime(2026, 9, 10, 12, 0, 0)
DEFAULT_PORTS = (5555, 5565, 5575)
LOOPBACK = ("127.0.0.1", 50000)  # what TestClient reports as request.client


@dataclass
class FakeProc:
    """Stands in for subprocess.Popen: the supervisor only ever reads .pid and .poll()."""

    pid: int
    exited: bool = False

    def poll(self):
        return 0 if self.exited else None


@dataclass
class FakeWorld:
    """The supervisor's injectable seams. Set `online[port] = False` to make the adb probe
    miss, put a pid in `alive` to make it look like a running worker."""

    now: datetime = T0
    online: dict[int, bool] = field(default_factory=dict)
    alive: set[int] = field(default_factory=set)
    launches: list[tuple[list[str], dict[str, str], str]] = field(default_factory=list)
    kills: list[int] = field(default_factory=list)
    procs: list[FakeProc] = field(default_factory=list)
    refreshes: int = 0
    next_pid: int = 100

    def clock(self) -> datetime:
        return self.now

    def probe(self, adb_path, port, timeout_s=15.0) -> bool:
        return self.online.get(port, True)

    def launcher(self, args, env, log_dir, name, module=None) -> FakeProc:
        self.launches.append((list(args), dict(env), name))
        proc = FakeProc(self.next_pid)
        self.next_pid += 1
        self.alive.add(proc.pid)
        self.procs.append(proc)
        return proc

    def is_alive(self, pid) -> bool:
        return pid in self.alive

    def kill(self, pid, log=print) -> bool:
        if pid in self.alive:
            self.alive.discard(pid)
            self.kills.append(pid)
            return True
        return False

    def refresh(self, now=None) -> int:
        self.refreshes += 1
        return 0


def build_settings(
    names: tuple[str, ...] = ("alpha",),
    ports: tuple[int, ...] | None = None,
    **overrides: object,
) -> S.AppSettings:
    """AppSettings with one instance per name; ports default to 5555, 5565, 5575 in order.

    Overrides are dotted section paths, e.g. build_settings(**{"app.port": 9000}) or
    build_settings(**{"connection.adb_path": str(fake_adb)}).
    """
    if ports is None:
        ports = DEFAULT_PORTS[: len(names)]
    if len(ports) != len(names):
        raise ValueError("ports must line up with names")
    s = S.AppSettings(
        instances=[S.InstanceSettings(name=n, adb_port=p) for n, p in zip(names, ports)]
    )
    for dotted, value in overrides.items():
        section, _, field_name = dotted.partition(".")
        if not field_name:
            raise ValueError(f"override {dotted!r} must be section.field")
        setattr(getattr(s, section), field_name, value)
    return s


def make_client(
    tmp_path: Path,
    names: tuple[str, ...] = ("alpha",),
    *,
    world: FakeWorld | None = None,
    **settings_overrides: object,
) -> tuple[TestClient, Supervisor, Path]:
    """A TestClient with the lifespan already entered, plus its supervisor and home dir.

    The caller closes it -- `client.__exit__(None, None, None)` runs the lifespan shutdown,
    which `client.close()` does not -- so every API test module wraps this in a fixture:

        @pytest.fixture()
        def api(tmp_path):
            client, sup, home = make_client(tmp_path, ("alpha", "bravo"))
            try:
                yield client, sup, home
            finally:
                client.__exit__(None, None, None)

    The schedule is switched off for every instance so the tick's desired state is always
    "run" and never depends on the wall clock (the same trick tests/test_supervisor_loop.py
    uses). Turn it back on inside a test with scheduler.set_enabled([name], True).
    """
    world = world or FakeWorld()
    settings = build_settings(names, **settings_overrides)
    home = Path(tmp_path)
    S.save(settings, home)
    sup = Supervisor(
        settings,
        home,
        clock=world.clock,
        probe=world.probe,
        launcher=world.launcher,
        alive=world.is_alive,
        killer=world.kill,
        sleep=lambda _s: None,
        events_refresh=world.refresh,
    )
    scheduler.set_enabled(list(names), False)
    client = TestClient(create_app(sup, home), client=LOOPBACK)
    client.__enter__()  # runs the lifespan, so the startup tick has filled sup.views()
    return client, sup, home
```

- [ ] **Step 3: Write the failing tests**

`tests/test_api_app.py`:

```python
"""The app factory: loopback-only access, the health probe, the startup tick that fills
the instance views before the first request, and the index (placeholder now, the built
single-page app once brawlfarm/web/dist exists)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from brawlfarm.api import app as app_module
from tests.apihelpers import make_client


@pytest.fixture()
def api(tmp_path: Path):
    client, sup, home = make_client(tmp_path, ("alpha", "bravo"))
    try:
        yield client, sup, home
    finally:
        client.__exit__(None, None, None)


def test_health_reports_version_home_and_instances(api) -> None:
    client, _sup, home = api
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["version"].startswith("0.")
    assert body["home"] == str(home.resolve())
    assert body["instances"] == 2
    assert body["uptime_s"] >= 0.0


def test_the_lifespan_runs_one_tick_so_views_exist(api) -> None:
    _client, sup, _home = api
    assert [v.name for v in sup.views()] == ["alpha", "bravo"]


def test_a_non_loopback_client_is_refused(api) -> None:
    client, _sup, _home = api
    stranger = TestClient(client.app, client=("10.0.0.5", 1))
    r = stranger.get("/api/health")
    assert r.status_code == 403
    assert r.json() == {"detail": "loopback only"}


def test_the_index_is_a_placeholder_until_the_ui_is_built(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(app_module, "dist_dir", lambda: tmp_path / "no-dist-here")
    client, _sup, _home = make_client(tmp_path)
    try:
        r = client.get("/")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/html")
        assert "The panel arrives in phase 4" in r.text
    finally:
        client.__exit__(None, None, None)


def test_a_built_ui_is_served_with_a_single_page_fallback(tmp_path: Path, monkeypatch) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><title>panel</title>", encoding="utf-8")
    (dist / "app.js").write_text("export const ok = 1;\n", encoding="utf-8")
    monkeypatch.setattr(app_module, "dist_dir", lambda: dist)
    client, _sup, _home = make_client(tmp_path / "home")
    try:
        assert client.get("/").text.startswith("<!doctype html>")
        assert "export const ok" in client.get("/app.js").text
        # A client-side route the browser deep-links into still gets index.html ...
        assert client.get("/instances/alpha").text.startswith("<!doctype html>")
        # ... but an unknown API path is still a 404, never the shell.
        assert client.get("/api/nope").status_code == 404
        assert client.get("/api/health").status_code == 200
    finally:
        client.__exit__(None, None, None)
```

`tests/test_conftest_reset.py`:

```python
"""The suite-wide fixture puts back the module globals a test may set: notify's settings
overrides and the scheduler's default-enabled flag (phase 2 deferral).

The two tests run in definition order, which is what makes the pin work: the first
dirties both globals, the second proves the autouse fixture's teardown cleaned them.
"""

from __future__ import annotations

from brawlfarm.core import notify, scheduler


def test_a_test_may_dirty_the_notify_and_scheduler_globals() -> None:
    notify.configure(webhook_url="https://example.invalid/hook", events=["crash"])
    notify._last_alert["crash"] = 1.0
    scheduler.set_default_enabled(False)
    assert notify._overrides["webhook_url"] == "https://example.invalid/hook"
    assert scheduler.DEFAULT_ENABLED is False


def test_the_next_test_sees_them_clean() -> None:
    assert notify._overrides == {}
    assert notify._last_alert == {}
    assert scheduler.DEFAULT_ENABLED is True
```

`tests/test_scheduler_logging.py`:

```python
"""The scheduler tick reports through logging, never print: the headless CLI prints its
own instance table, and the panel's log stream (phase 3) only sees log records."""

from __future__ import annotations

import logging
from pathlib import Path

from brawlfarm.core import config, scheduler

_INSTANCES = {"alpha": {"port": "5555", "tag": "", "data": "instances/alpha"}}


def _one_instance(home: Path) -> None:
    config.set_home(home)
    config.set_instances(_INSTANCES)


def test_the_all_disabled_summary_is_logged_not_printed(tmp_path, caplog, capsys) -> None:
    _one_instance(tmp_path)
    scheduler.set_enabled(["alpha"], False)  # the legacy always-run path
    with caplog.at_level(logging.INFO, logger="brawlfarm.scheduler"):
        assert scheduler.tick() == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""
    messages = [r.getMessage() for r in caplog.records]
    assert any(m.startswith("tick ") and "alpha=run" in m for m in messages)
    assert {r.name for r in caplog.records} == {"brawlfarm.scheduler"}


def test_the_draw_line_is_logged_too(tmp_path, caplog, capsys) -> None:
    _one_instance(tmp_path)  # scheduling on by default: the tick draws a day
    with caplog.at_level(logging.INFO, logger="brawlfarm.scheduler"):
        assert scheduler.tick() == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""
    messages = [r.getMessage() for r in caplog.records]
    assert any(m.startswith("drew alpha ") and "session(s)" in m for m in messages)
    assert any(m.startswith("tick ") for m in messages)


def test_an_internal_failure_is_logged_with_its_traceback(
    tmp_path, caplog, capsys, monkeypatch
) -> None:
    _one_instance(tmp_path)

    def boom(_now):
        raise RuntimeError("scheduler exploded")

    monkeypatch.setattr(scheduler, "_tick_inner", boom)
    with caplog.at_level(logging.ERROR, logger="brawlfarm.scheduler"):
        assert scheduler.tick() == 1  # still fails open: desired=run is written
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert errors and errors[0].exc_info is not None
    assert "scheduler exploded" in caplog.text
```

- [ ] **Step 4: Run them to confirm they fail**

```bash
uv run pytest tests/test_api_app.py tests/test_conftest_reset.py tests/test_scheduler_logging.py -v
```

Expected: `tests/test_api_app.py` errors during collection with `ModuleNotFoundError: No module named 'brawlfarm.api'`; `test_the_next_test_sees_them_clean` fails with `AssertionError: assert {'webhook_url': ...} == {}`; the three scheduler tests fail with `AssertionError` on `captured.out == ""` (the tick still prints) and `AttributeError: module 'brawlfarm.core.scheduler' has no attribute 'log'` is not raised yet because there is no logger at all.

- [ ] **Step 5: Create the api package and the app factory**

`brawlfarm/api/__init__.py`:

```python
"""The control panel's HTTP surface: a FastAPI app on 127.0.0.1 that drives the
supervisor, reads the instance directories and streams events to the browser.

No authentication (spec section 3): the app refuses every client that is not on the
loopback interface instead. Nothing in this package writes to core.config globals -- the
process-global adb path and player tag belong to a worker, not to the panel.
"""
```

`brawlfarm/api/app.py`:

```python
"""The FastAPI application factory.

One app per process. create_app(sup, home) stores the live supervisor and the data
directory on app.state, refuses non-loopback clients, runs one supervisor tick during
startup so the first request already has instance views to show, and serves the built web
UI from brawlfarm/web/dist when phase 4 has produced one.

Routers are included before the static mount, so /api/* always wins over the single-page
app's catch-all.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

import brawlfarm
from brawlfarm import __version__
from brawlfarm.supervisor import Supervisor

log = logging.getLogger("brawlfarm.api")

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1"})

PLACEHOLDER_HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>brawlfarm</title>
  </head>
  <body>
    <p>brawlfarm is running. The panel arrives in phase 4. API docs at /docs.</p>
  </body>
</html>
"""


def dist_dir() -> Path:
    """Where the built web UI lands (phase 4 builds it, CI packages it into the wheel).
    A function rather than a constant so tests can point it somewhere else."""
    return Path(brawlfarm.__file__).resolve().parent / "web" / "dist"


class SpaFiles(StaticFiles):
    """StaticFiles with a single-page-app fallback: an unknown path serves index.html so
    the browser can deep-link to /instances/alpha. Starlette's html=True only covers
    directory indexes. /api/* is never rewritten -- an unknown API path stays a 404."""

    async def get_response(self, path: str, scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404 or path.startswith("api/"):
                raise
            return await super().get_response("index.html", scope)


def create_app(sup: Supervisor, home: Path) -> FastAPI:
    """Build the panel's app around a live supervisor. The caller serves it with uvicorn
    on 127.0.0.1 (brawlfarm/__main__.py) or drives it with starlette's TestClient."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # One tick before the first request, so GET /api/instances is never empty on a
        # cold start. It runs in a thread because a tick shells out to adb and writes
        # files. Later tasks attach the event bus, the feed tailer and the alert store
        # here; a failed startup tick must not stop the app from serving.
        try:
            await asyncio.to_thread(app.state.sup.tick)
        except Exception:
            log.exception("startup tick failed")
        yield

    app = FastAPI(title="brawlfarm", version=__version__, lifespan=lifespan)
    app.state.sup = sup
    app.state.home = Path(home).resolve()
    app.state.started_at = time.monotonic()

    @app.middleware("http")
    async def _loopback_only(request: Request, call_next):
        """Spec section 3: the panel binds 127.0.0.1 and has no authentication, so a
        request from any other host is refused before it reaches a route. request.client
        is None for an ASGI transport that does not report a peer; that is us."""
        client = request.client
        if client is not None and client.host not in LOOPBACK_HOSTS:
            return JSONResponse({"detail": "loopback only"}, status_code=403)
        return await call_next(request)

    @app.get("/api/health")
    async def health(request: Request) -> dict:
        """The shell's probe: which version is running, where its data lives, how many
        instances it manages and how long this process has been up."""
        state = request.app.state
        return {
            "version": __version__,
            "home": str(state.home),
            "instances": len(state.sup.settings.instances),
            "uptime_s": round(time.monotonic() - state.started_at, 3),
        }

    # --- routers ---------------------------------------------------------------------
    # Included here, before the static mount below. Later tasks add their lines here.

    # --- the web UI ------------------------------------------------------------------
    dist = dist_dir()
    if (dist / "index.html").exists():
        app.mount("/", SpaFiles(directory=dist, html=True), name="web")
    else:

        @app.get("/", response_class=HTMLResponse)
        async def index() -> HTMLResponse:
            """Placeholder until phase 4 builds the UI into brawlfarm/web/dist."""
            return HTMLResponse(PLACEHOLDER_HTML)

    return app
```

- [ ] **Step 6: Route the scheduler tick's output through logging**

In `brawlfarm/core/scheduler.py`, replace the import block (lines 73 to 87) with:

```python
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import math
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from brawlfarm.core import config
from brawlfarm.core.jsonio import atomic_write_json

# The tick runs headless under the supervisor and its output is the panel's log stream
# (phase 3), so it logs. The read-only dev tools below (preview, simulate) keep printing:
# they are run by hand from a console.
log = logging.getLogger("brawlfarm.scheduler")
```

(`traceback` goes away with the only call that used it; leaving the import would trip ruff F401.)

In `tick()` (line 661), replace `traceback.print_exc()` with the logger so the failure reaches the log file and the SSE stream instead of a console nobody is watching:

```python
def tick(now: datetime | None = None) -> int:
    now = now or datetime.now()
    try:
        return _tick_inner(now)
    except Exception:
        # FAIL-OPEN: a scheduler bug must never strand farms stopped. Write
        # desired=run for everything, scream, exit nonzero (watchdog logs it).
        log.exception("scheduler tick failed; failing open to desired=run for every account")
```

At line 730 (the all-disabled early return) replace the `print` with:

```python
        log.info("tick %s  %s", _iso(now), "  ".join(parts))
        return 0
```

At lines 767 to 771 (the fresh-day draw) replace the `print(...)` block with:

```python
        log.info(
            "drew %s %s: %d session(s), %.0f min, day_end %s",
            name,
            date_str,
            len(plan["sessions"]),
            plan["total_minutes"],
            _hhmm(plan["day_end"]),
        )
```

At line 820 (the end-of-tick summary) replace the `print` with:

```python
    log.info("tick %s  %s", _iso(now), "  ".join(parts))
    return 0
```

- [ ] **Step 7: Reset the notify and scheduler globals in the conftest teardown**

`tests/conftest.py` becomes:

```python
"""Suite-wide isolation: every test gets an empty home directory, no farm env, and the
module-level globals the panel and the supervisor mutate (notify's settings overrides,
the scheduler's default-enabled flag) put back afterwards."""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    for key in list(os.environ):
        if key.startswith(("BRAWL_", "DISCORD_", "NTFY_")):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("BRAWLFARM_HOME", str(tmp_path))
    from brawlfarm.core import config, notify, scheduler

    previous_home = config.HOME_DIR
    previous_default_enabled = scheduler.DEFAULT_ENABLED
    config.set_home(tmp_path)
    config.set_instances({})
    yield
    config.set_instances({})
    config.set_home(previous_home)
    # Supervisor.apply_settings() calls both of these, so any test that builds a
    # Supervisor leaves them set for the next test unless we put them back.
    notify._overrides.clear()
    notify._last_alert.clear()  # the 120 s per-kind alert cooldown is process-global too
    scheduler.set_default_enabled(previous_default_enabled)
```

- [ ] **Step 8: Run the new tests, then the whole suite**

```bash
uv run pytest tests/test_api_app.py tests/test_conftest_reset.py tests/test_scheduler_logging.py -v
uv run pytest -q
```

Expected: 10 new tests PASS; the full suite passes at 426 tests (416 + 10) with no warnings. If a ported scheduler test asserted on the tick's stdout it now needs `caplog` instead; none do today (`grep -rn "capsys" tests/test_scheduler.py` finds nothing).

- [ ] **Step 9: Lint, scrub, commit**

```bash
uv run ruff format brawlfarm/api/__init__.py brawlfarm/api/app.py brawlfarm/core/scheduler.py tests/apihelpers.py tests/conftest.py tests/test_api_app.py tests/test_conftest_reset.py tests/test_scheduler_logging.py
uv run ruff check --fix brawlfarm/api tests
uv run ruff check . && uv run ruff format --check .
uv run python tools/scrub_check.py
git add pyproject.toml uv.lock brawlfarm/api brawlfarm/core/scheduler.py tests/apihelpers.py tests/conftest.py tests/test_api_app.py tests/test_conftest_reset.py tests/test_scheduler_logging.py
git commit -m "feat(api): loopback-only FastAPI app around the live supervisor

create_app(sup, home) is the one app factory every route module hangs off: it
keeps the supervisor and the home directory on app.state, refuses any client
that is not on the loopback interface (spec section 3 has no auth), and runs one
tick during startup so the first GET /api/instances is never empty.

Two phase 2 deferrals come with it, because phase 3 needs them: the scheduler
tick logs instead of printing, so the panel's log stream can carry it and the
headless CLI stops double-reporting; and the conftest teardown puts back
notify._overrides and scheduler.DEFAULT_ENABLED, which Supervisor.apply_settings
sets for the rest of the session."
```

---
### Task 2: Instance routes and settings routes

The Fleet screen's whole data contract: one payload per instance (the supervisor's view plus the session from `status.json` and today's totals from `games.csv`), the five controls, and the settings document. `deps.resolve_instance` lands here because it is the gate every per-instance route in tasks 4 and 5 goes through.

**Files:**
- Create: `brawlfarm/api/deps.py`
- Create: `brawlfarm/api/instances.py`
- Create: `brawlfarm/api/settings_routes.py`
- Modify: `brawlfarm/api/app.py` (the `# --- routers ---` block)
- Create: `tests/test_api_instances.py`
- Create: `tests/test_api_settings.py`

**Interfaces:**
- Consumes: `Supervisor.views/start/stop/stop_now/restart/retry_now/poke/apply_settings/settings`; `settings.INSTANCE_NAME_RE`, `settings.instance_dir`, `settings.save`, `settings.AppSettings.model_validate`, `settings._explain`; `status.read_status`; `supervisor.state.InstanceView`, `InstanceState`.
- Produces:
  - `deps.get_sup(request) -> Supervisor`, `deps.get_home(request) -> Path`, `deps.resolve_instance(request, name) -> tuple[InstanceSettings, Path]` (404 `{"detail": "unknown instance"}`)
  - `instances.router`, `instances.view_to_dict(view) -> dict`, `instances.instance_payload(view, inst, inst_dir, now) -> dict`, `instances.today_counts(inst_dir, now) -> dict`, `instances.StartBody`
  - `settings_routes.router`, `settings_routes.LIVE_STATES`
  - `GET /api/instances`, `POST /api/instances/{name}/start|stop|stop-now|restart|retry`, `GET|PUT /api/settings`
- Consumed by: tasks 4, 5, 7 and 9 (`resolve_instance`), task 6 (`view_to_dict` is the `instance` event payload), task 8 (`LIVE_STATES` is unused elsewhere but the alert drawer reads the same view dicts).

- [ ] **Step 1: Write the failing tests**

`tests/test_api_instances.py`:

```python
"""GET /api/instances and the five controls: the payload the Fleet card is built from,
today's totals from games.csv, and start / stop / stop-now / restart / retry writing the
same files the supervisor tick reads."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from brawlfarm import settings as S
from brawlfarm.api import instances
from brawlfarm.core import scheduler
from tests.apihelpers import FakeWorld, make_client


@pytest.fixture()
def api(tmp_path: Path):
    client, sup, home = make_client(tmp_path, ("alpha", "bravo"))
    try:
        yield client, sup, home
    finally:
        client.__exit__(None, None, None)


def _heartbeat(home: Path, name: str, pid: int, now: datetime, age_s: float = 5, **fields) -> None:
    """A status.json the supervisor reads as a live heartbeat `age_s` seconds old."""
    d = S.instance_dir(home, name)
    d.mkdir(parents=True, exist_ok=True)
    payload = {
        "ts": (now - timedelta(seconds=age_s)).strftime("%Y-%m-%dT%H:%M:%S"),
        "pid": pid,
        "phase": "playing",
        "games_played": 3,
        **fields,
    }
    (d / "status.json").write_text(json.dumps(payload), encoding="utf-8")


def _write_games(inst_dir: Path, rows: list[tuple[datetime, int]]) -> None:
    """The two columns today_counts reads, with battleTime in the API's UTC format."""
    inst_dir.mkdir(parents=True, exist_ok=True)
    lines = ["battleTime,trophyChange"]
    for when, delta in rows:
        stamp = when.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S.000Z")
        lines.append(f"{stamp},{delta}")
    (inst_dir / "games.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_list_returns_one_payload_per_instance_in_settings_order(api) -> None:
    client, _sup, _home = api
    body = client.get("/api/instances").json()
    assert [i["name"] for i in body["instances"]] == ["alpha", "bravo"]
    first = body["instances"][0]
    assert set(first) == {
        "name",
        "adb_port",
        "state",
        "health",
        "pid",
        "heartbeat_age_s",
        "phase",
        "desired",
        "desired_reason",
        "until",
        "games_played",
        "farm_brawler",
        "note",
        "player_tag",
        "session",
        "today",
    }
    assert first["adb_port"] == 5555
    assert first["state"] == "starting"  # the startup tick launched it
    assert first["health"] == "dead"
    assert first["desired"] == "run" and first["desired_reason"] == "disabled"
    assert first["player_tag"] == ""
    assert first["session"] is None
    assert first["today"] == {"games": 0, "trophies": 0}


def test_the_payload_carries_the_session_and_today_totals(tmp_path: Path) -> None:
    world = FakeWorld()
    world.alive.add(4242)
    _heartbeat(
        tmp_path,
        "alpha",
        4242,
        world.now,
        minutes_elapsed=42.5,
        start_trophies=41000,
        last_trophies=41120,
        disconnect_count=1,
        recovery_attempts=0,
        session="session-20260910-101500.jsonl",
        farm_brawler="Shelly",
    )
    noon = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0)
    _write_games(
        S.instance_dir(tmp_path, "alpha"),
        [(noon - timedelta(hours=1), 8), (noon - timedelta(hours=2), -3), (noon - timedelta(days=1), 99)],
    )
    client, _sup, _home = make_client(tmp_path, ("alpha",), world=world)
    try:
        payload = client.get("/api/instances").json()["instances"][0]
    finally:
        client.__exit__(None, None, None)
    assert payload["state"] == "farming"
    assert payload["pid"] == 4242
    assert payload["farm_brawler"] == "Shelly"
    assert payload["session"] == {
        "minutes_elapsed": 42.5,
        "start_trophies": 41000,
        "last_trophies": 41120,
        "disconnect_count": 1,
        "recovery_attempts": 0,
        "session": "session-20260910-101500.jsonl",
    }
    assert payload["today"] == {"games": 2, "trophies": 5}


def test_today_counts_only_counts_todays_local_matches(tmp_path: Path) -> None:
    now = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0)
    inst_dir = tmp_path / "alpha"
    _write_games(
        inst_dir,
        [(now - timedelta(hours=1), 9), (now - timedelta(hours=2), -4), (now - timedelta(days=1), 50)],
    )
    assert instances.today_counts(inst_dir, now) == {"games": 2, "trophies": 5}
    assert instances.today_counts(tmp_path / "no-such-instance", now) == {"games": 0, "trophies": 0}


def test_an_unknown_or_malformed_name_is_404_before_any_folder_is_made(api) -> None:
    client, _sup, home = api
    for path in ("/api/instances/ghost/stop", "/api/instances/not$valid/stop"):
        r = client.post(path)
        assert r.status_code == 404
        assert r.json() == {"detail": "unknown instance"}
    assert not (home / "instances" / "ghost").exists()
    assert not (home / "instances" / "not$valid").exists()


def test_start_without_hours_clears_a_stop_override(api) -> None:
    client, _sup, home = api
    scheduler.write_override("alpha", "stop", datetime(2027, 1, 1, 0, 0, 0))
    override = S.instance_dir(home, "alpha") / "override.json"
    assert override.exists()
    r = client.post("/api/instances/alpha/start")
    assert r.status_code == 202 and r.json() == {"ok": True}
    assert not override.exists()


def test_start_with_hours_writes_a_run_override(api) -> None:
    client, _sup, home = api
    r = client.post("/api/instances/alpha/start", json={"hours": 2})
    assert r.status_code == 202 and r.json() == {"ok": True}
    written = json.loads((S.instance_dir(home, "alpha") / "override.json").read_text("utf-8"))
    assert written["mode"] == "run"
    assert written["until"] == "2026-09-10T14:00:00"  # the FakeWorld clock plus two hours


def test_start_rejects_a_non_positive_number_of_hours(api) -> None:
    client, _sup, _home = api
    assert client.post("/api/instances/alpha/start", json={"hours": 0}).status_code == 422
    assert client.post("/api/instances/alpha/start", json={"nope": 1}).status_code == 422


def test_stop_writes_the_stop_flag_and_a_stop_override(api) -> None:
    client, _sup, home = api
    r = client.post("/api/instances/alpha/stop")
    assert r.status_code == 202 and r.json() == {"ok": True}
    assert (S.instance_dir(home, "alpha") / "stop.flag").exists()
    written = json.loads((S.instance_dir(home, "alpha") / "override.json").read_text("utf-8"))
    assert written["mode"] == "stop"


def test_stop_now_is_409_until_a_stop_is_pending(api) -> None:
    client, _sup, _home = api
    r = client.post("/api/instances/alpha/stop-now")
    assert r.status_code == 409
    assert r.json() == {"detail": "no stop pending"}


def test_stop_now_kills_the_worker_once_a_stop_is_pending(tmp_path: Path) -> None:
    world = FakeWorld()
    world.alive.add(4242)
    _heartbeat(tmp_path, "alpha", 4242, world.now)
    client, _sup, _home = make_client(tmp_path, ("alpha",), world=world)
    try:
        assert client.post("/api/instances/alpha/stop").status_code == 202
        r = client.post("/api/instances/alpha/stop-now")
        assert r.status_code == 202 and r.json() == {"killed": True}
        assert world.kills == [4242]
    finally:
        client.__exit__(None, None, None)


def test_restart_stops_the_worker_without_touching_the_schedule(tmp_path: Path) -> None:
    world = FakeWorld()
    world.alive.add(4242)
    _heartbeat(tmp_path, "alpha", 4242, world.now)
    client, _sup, home = make_client(tmp_path, ("alpha",), world=world)
    try:
        r = client.post("/api/instances/alpha/restart")
        assert r.status_code == 202 and r.json() == {"ok": True}
        assert (S.instance_dir(home, "alpha") / "stop.flag").exists()
        assert not (S.instance_dir(home, "alpha") / "override.json").exists()
        assert client.post("/api/instances/alpha/retry").status_code == 202
    finally:
        client.__exit__(None, None, None)
```

`tests/test_api_settings.py`:

```python
"""GET and PUT /api/settings: the whole config.toml document round-trips, a bad field is
named in the 422, and an instance whose worker is alive cannot be removed."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from brawlfarm import settings as S
from brawlfarm.supervisor import InstanceState
from tests.apihelpers import FakeWorld, make_client


@pytest.fixture()
def api(tmp_path: Path):
    client, sup, home = make_client(tmp_path, ("alpha", "bravo"))
    try:
        yield client, sup, home
    finally:
        client.__exit__(None, None, None)


def _heartbeat(home: Path, name: str, pid: int, now: datetime) -> None:
    d = S.instance_dir(home, name)
    d.mkdir(parents=True, exist_ok=True)
    payload = {
        "ts": (now - timedelta(seconds=5)).strftime("%Y-%m-%dT%H:%M:%S"),
        "pid": pid,
        "phase": "playing",
        "games_played": 3,
    }
    (d / "status.json").write_text(json.dumps(payload), encoding="utf-8")


def test_get_returns_the_whole_document(api) -> None:
    client, _sup, _home = api
    body = client.get("/api/settings").json()
    assert body["app"]["port"] == 8765
    assert body["scheduler"]["default_enabled"] is True
    assert body["connection"]["adb_path"].endswith("HD-Adb.exe")
    assert [i["name"] for i in body["instances"]] == ["alpha", "bravo"]


def test_put_saves_the_document_and_reapplies_it(api) -> None:
    client, sup, home = api
    doc = client.get("/api/settings").json()
    doc["app"]["theme"] = "dark"
    doc["instances"].append({"name": "charlie", "adb_port": 5575, "player_tag": "#8GC9Q2"})
    r = client.put("/api/settings", json=doc)
    assert r.status_code == 200
    assert r.json()["app"]["theme"] == "dark"
    assert sup.settings.app.theme == "dark"
    assert [i.name for i in sup.settings.instances] == ["alpha", "bravo", "charlie"]
    assert "charlie" in S.config_path(home).read_text(encoding="utf-8")


def test_put_names_the_field_it_rejected(api) -> None:
    client, sup, _home = api
    doc = client.get("/api/settings").json()
    doc["app"]["prot"] = 1
    r = client.put("/api/settings", json=doc)
    assert r.status_code == 422
    assert "app.prot" in r.json()["detail"]
    assert sup.settings.app.port == 8765  # nothing was applied


def test_put_refuses_to_remove_an_instance_that_is_still_running(tmp_path: Path) -> None:
    world = FakeWorld()
    world.alive.add(4242)
    _heartbeat(tmp_path, "bravo", 4242, world.now)
    client, sup, _home = make_client(tmp_path, ("alpha", "bravo"), world=world)
    try:
        live = next(v for v in sup.views() if v.name == "bravo")
        assert live.state == InstanceState.FARMING
        doc = client.get("/api/settings").json()
        doc["instances"] = [i for i in doc["instances"] if i["name"] != "bravo"]
        r = client.put("/api/settings", json=doc)
        assert r.status_code == 409
        assert r.json() == {"detail": "Stop bravo before removing it"}
        assert [i.name for i in sup.settings.instances] == ["alpha", "bravo"]
    finally:
        client.__exit__(None, None, None)


def test_put_allows_removing_an_offline_instance_and_keeps_its_data(tmp_path: Path) -> None:
    world = FakeWorld()
    world.online[5555] = False  # alpha's BlueStacks window is not there
    client, sup, home = make_client(tmp_path, ("alpha", "bravo"), world=world)
    try:
        assert next(v for v in sup.views() if v.name == "alpha").state == InstanceState.OFFLINE
        S.instance_dir(home, "alpha").mkdir(parents=True, exist_ok=True)
        doc = client.get("/api/settings").json()
        doc["instances"] = [i for i in doc["instances"] if i["name"] != "alpha"]
        r = client.put("/api/settings", json=doc)
        assert r.status_code == 200
        assert [i["name"] for i in r.json()["instances"]] == ["bravo"]
        assert [i.name for i in sup.settings.instances] == ["bravo"]
        assert S.instance_dir(home, "alpha").exists()  # spec: removing keeps the data folder
    finally:
        client.__exit__(None, None, None)
```

- [ ] **Step 2: Run them to confirm they fail**

```bash
uv run pytest tests/test_api_instances.py tests/test_api_settings.py -v
```

Expected: both files error during collection with `ModuleNotFoundError: No module named 'brawlfarm.api.instances'`.

- [ ] **Step 3: Create `brawlfarm/api/deps.py`**

```python
"""Shared route plumbing: reach the supervisor and the data directory from a request, and
turn the {name} in a path into that instance's settings plus its directory.

resolve_instance is the safety gate of spec section 9: an instance name becomes a folder
name, so it is matched against INSTANCE_NAME_RE and checked against config.toml BEFORE
anything touches the filesystem. It never creates the directory -- readers must not
conjure folders for instances that have never run; writers call mkdir themselves.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, Request

from brawlfarm import settings as S
from brawlfarm.supervisor import Supervisor


def get_sup(request: Request) -> Supervisor:
    """The one live Supervisor this process is running (put there by create_app)."""
    return request.app.state.sup


def get_home(request: Request) -> Path:
    """The resolved data directory: <home>/config.toml, <home>/instances/<name>/, ..."""
    return request.app.state.home


def resolve_instance(request: Request, name: str) -> tuple[S.InstanceSettings, Path]:
    """The instance's settings and its directory, or 404 "unknown instance".

    The same 404 covers a name that is not configured and a name that could never be a
    folder: telling those apart would only help someone probing the filesystem.
    """
    if not S.INSTANCE_NAME_RE.match(name):
        raise HTTPException(status_code=404, detail="unknown instance")
    try:
        inst = get_sup(request).settings.instance(name)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown instance") from None
    return inst, S.instance_dir(get_home(request), inst.name)
```

- [ ] **Step 4: Create `brawlfarm/api/instances.py`**

```python
"""GET /api/instances and the per-instance controls: start, stop, stop-now, restart,
retry.

The payload is the supervisor's InstanceView -- derived once per tick, so listing is free
and never blocks on adb -- plus the two things only the instance directory knows: the
live session from status.json and today's games and trophies from games.csv.

The controls are quick file writes (an override, a stop.flag, a kill by PID), so they run
on the event loop thread and end with sup.poke(), which wakes the supervisor now instead
of leaving the user waiting up to a tick.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from brawlfarm import settings as S
from brawlfarm.api.deps import get_home, get_sup, resolve_instance
from brawlfarm.core import status
from brawlfarm.supervisor.state import InstanceView

router = APIRouter()

# The battle log's own stamp format (core/datalog.py GAME_FIELDS): UTC, always.
BATTLE_TIME_FMT = "%Y%m%dT%H%M%S.%fZ"


class StartBody(BaseModel):
    """Optional body for POST start. No body at all means "undo the stop override"."""

    model_config = ConfigDict(extra="forbid")

    hours: float | None = Field(default=None, gt=0)


def view_to_dict(view: InstanceView) -> dict:
    """The InstanceView as JSON: enums become their string values and `until` becomes ISO
    seconds, so the browser always gets the same types for a field."""
    return {
        "name": view.name,
        "adb_port": view.adb_port,
        "state": str(view.state),
        "health": str(view.health),
        "pid": view.pid,
        "heartbeat_age_s": view.heartbeat_age_s,
        "phase": view.phase,
        "desired": view.desired,
        "desired_reason": view.desired_reason,
        "until": view.until.isoformat(timespec="seconds") if view.until else None,
        "games_played": view.games_played,
        "farm_brawler": view.farm_brawler,
        "note": view.note,
    }


def today_counts(inst_dir: Path, now: datetime) -> dict:
    """Games played and net trophies logged today, straight from games.csv.

    battleTime is UTC, so it is converted to local time before the date is compared: a
    match played at 00:30 local counts for today even though its UTC stamp says
    yesterday. A missing or unreadable file is zeros -- a broken CSV must never break a
    Fleet card.
    """
    path = Path(inst_dir) / "games.csv"
    today = now.date()
    local_tz = now.astimezone().tzinfo
    games = 0
    trophies = 0
    try:
        with path.open("r", encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                stamped = _battle_time(row.get("battleTime"))
                if stamped is None or stamped.astimezone(local_tz).date() != today:
                    continue
                games += 1
                trophies += _int_or_zero(row.get("trophyChange"))
    except (OSError, csv.Error, UnicodeDecodeError):
        return {"games": 0, "trophies": 0}
    return {"games": games, "trophies": trophies}


def instance_payload(
    view: InstanceView, inst: S.InstanceSettings, inst_dir: Path, now: datetime
) -> dict:
    """One Fleet card's whole row: the view, the tag from settings, the live session and
    today's totals."""
    payload = view_to_dict(view)
    payload["player_tag"] = inst.player_tag
    payload["session"] = _session(status.read_status(inst_dir))
    payload["today"] = today_counts(inst_dir, now)
    return payload


def _session(st: dict | None) -> dict | None:
    """The current session block from status.json, or None when the worker has never
    written one (a fresh instance, or one that has not run since this home was made)."""
    if not st:
        return None
    return {
        "minutes_elapsed": st.get("minutes_elapsed"),
        "start_trophies": st.get("start_trophies"),
        "last_trophies": st.get("last_trophies"),
        "disconnect_count": st.get("disconnect_count"),
        "recovery_attempts": st.get("recovery_attempts"),
        "session": st.get("session"),
    }


def _battle_time(value: str | None) -> datetime | None:
    try:
        return datetime.strptime(str(value), BATTLE_TIME_FMT).replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _int_or_zero(value) -> int:
    """A hand-edited or half-written cell counts as zero, never as an exception."""
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


@router.get("/api/instances")
async def list_instances(request: Request) -> dict:
    """Every configured instance in config.toml order.

    An instance added by PUT /api/settings appears here once the supervisor has derived a
    view for it; the PUT's sup.poke() asks for that tick immediately.
    """
    sup = get_sup(request)
    home = get_home(request)
    now = datetime.now()
    by_name = {v.name: v for v in sup.views()}
    out = []
    for inst in sup.settings.instances:
        view = by_name.get(inst.name)
        if view is None:
            continue
        out.append(instance_payload(view, inst, S.instance_dir(home, inst.name), now))
    return {"instances": out}


@router.post("/api/instances/{name}/start", status_code=202)
async def start_instance(request: Request, name: str, body: StartBody | None = None) -> dict:
    """Start it: clear the stop override, or with `hours` run for that long and stop."""
    inst, _dir = resolve_instance(request, name)
    sup = get_sup(request)
    sup.start(inst.name, body.hours if body else None)
    sup.poke()
    return {"ok": True}


@router.post("/api/instances/{name}/stop", status_code=202)
async def stop_instance(request: Request, name: str) -> dict:
    """Stop it after the current match: a stop override plus stop.flag. The tick kills by
    PID if the worker has not gone in 110 s."""
    inst, _dir = resolve_instance(request, name)
    sup = get_sup(request)
    sup.stop(inst.name)
    sup.poke()
    return {"ok": True}


@router.post("/api/instances/{name}/stop-now", status_code=202)
async def stop_instance_now(request: Request, name: str) -> dict:
    """Kill by PID right now, but only while a graceful stop is already pending: a kill
    out of nowhere would abandon a match in progress."""
    inst, _dir = resolve_instance(request, name)
    sup = get_sup(request)
    if not sup.stop_now(inst.name):
        raise HTTPException(status_code=409, detail="no stop pending")
    sup.poke()
    return {"killed": True}


@router.post("/api/instances/{name}/restart", status_code=202)
async def restart_instance(request: Request, name: str) -> dict:
    """Stop gracefully without touching the schedule; the next tick launches it again."""
    inst, _dir = resolve_instance(request, name)
    sup = get_sup(request)
    sup.restart(inst.name)
    sup.poke()
    return {"ok": True}


@router.post("/api/instances/{name}/retry", status_code=202)
async def retry_instance(request: Request, name: str) -> dict:
    """The offline card's "Retry now": drop the backoff and probe adb again this tick."""
    inst, _dir = resolve_instance(request, name)
    sup = get_sup(request)
    sup.retry_now(inst.name)
    sup.poke()
    return {"ok": True}
```

- [ ] **Step 5: Create `brawlfarm/api/settings_routes.py`**

```python
"""GET and PUT /api/settings: the whole config.toml document as JSON.

PUT validates the document, refuses to drop an instance whose worker is alive (one worker
per instance -- removing it from settings would orphan the process the supervisor is
watching), saves it atomically and hands it to the supervisor. Changing [app].port takes
effect on the next start, because uvicorn is already bound.

The Brawl Stars token is returned as stored: the API is loopback-only and unauthenticated
on the user's own machine, and the Settings screen is what masks it.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError

from brawlfarm import settings as S
from brawlfarm.api.deps import get_home, get_sup
from brawlfarm.supervisor.state import InstanceState

router = APIRouter()

# States that mean a worker process is running, or is about to be.
LIVE_STATES = frozenset(
    {
        InstanceState.FARMING,
        InstanceState.STARTING,
        InstanceState.STOPPING,
        InstanceState.RECONNECTING,
    }
)


@router.get("/api/settings")
async def read_settings(request: Request) -> dict:
    """The settings the supervisor is running with right now (not a re-read of the file)."""
    return get_sup(request).settings.model_dump(mode="json")


@router.put("/api/settings")
async def write_settings(request: Request, body: dict) -> dict:
    """Replace config.toml wholesale and re-apply it. 422 names the offending field, 409
    names the instance that has to be stopped first."""
    sup = get_sup(request)
    try:
        new = S.AppSettings.model_validate(body)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=S._explain(exc)) from exc
    keeping = {i.name for i in new.instances}
    views = {v.name: v for v in sup.views()}
    for inst in sup.settings.instances:
        if inst.name in keeping:
            continue
        view = views.get(inst.name)
        if view is not None and view.state in LIVE_STATES:
            raise HTTPException(
                status_code=409, detail=f"Stop {inst.name} before removing it"
            )
    S.save(new, get_home(request))
    sup.apply_settings(new)
    sup.poke()
    return new.model_dump(mode="json")
```

- [ ] **Step 6: Include the routers in `create_app`**

In `brawlfarm/api/app.py`, add the two imports next to the existing `brawlfarm` imports:

```python
import brawlfarm
from brawlfarm import __version__
from brawlfarm.api import instances, settings_routes
from brawlfarm.supervisor import Supervisor
```

and replace the routers block inside `create_app` with:

```python
    # --- routers ---------------------------------------------------------------------
    # Included before the static mount below, so /api/* always wins over the SPA.
    app.include_router(instances.router)
    app.include_router(settings_routes.router)
```

- [ ] **Step 7: Run the new tests, then the whole suite**

```bash
uv run pytest tests/test_api_instances.py tests/test_api_settings.py -v
uv run pytest -q
```

Expected: 16 new tests PASS; the full suite passes at 442 tests (426 + 16) with no warnings.

- [ ] **Step 8: Lint, scrub, commit**

```bash
uv run ruff format brawlfarm/api tests/test_api_instances.py tests/test_api_settings.py
uv run ruff check --fix brawlfarm/api tests
uv run ruff check . && uv run ruff format --check .
uv run python tools/scrub_check.py
git add brawlfarm/api tests/test_api_instances.py tests/test_api_settings.py
git commit -m "feat(api): instance list, the five controls and the settings document

GET /api/instances is the Fleet screen's whole contract: the supervisor's
per-tick view plus the live session from status.json and today's games and
trophies from games.csv, so the card needs one request and never waits on adb.
start / stop / stop-now / restart / retry write exactly the files the tick
already reads, then poke the supervisor so the user does not wait a minute.

PUT /api/settings refuses to drop an instance whose worker is alive: settings
are the only record of which processes we watch, so removing a live one would
orphan it and break one-worker-per-instance. deps.resolve_instance validates the
name against INSTANCE_NAME_RE before any path is built, because names become
folder names (spec section 9)."
```

---
### Task 3: The `setup` package (adb discovery and the display check)

Everything the setup wizard's three probes need, with no HTTP in sight so it can be tested with a fake runner. This is a second, small adb wrapper on purpose (ruling 7): it runs in the supervisor process against an arbitrary instance port and must never mutate `core/config.py`'s process globals, which belong to a worker.

**Files:**
- Create: `brawlfarm/setup/__init__.py`
- Create: `brawlfarm/setup/checks.py`
- Create: `brawlfarm/setup/discover.py`
- Create: `tests/test_setup_checks.py`
- Create: `tests/test_setup_discover.py`

**Interfaces:**
- Consumes: `core.config.SCREEN_W`, `SCREEN_H`, `SCREEN_DPI` (1600, 900, 240); `settings.INSTANCE_NAME_RE`, `settings.DEFAULT_ADB_PATH`.
- Produces (all in `brawlfarm.setup`):
  - `checks.Runner = Callable[[list[str], float], subprocess.CompletedProcess]`, `checks.PNG_SIGNATURE`, `checks.AdbUnavailable`
  - `checks.serial(port: int) -> str`, `checks.decode(raw) -> str`, `checks.first_line(raw) -> str`
  - `checks.run_adb(adb_path, args, *, timeout_s=15.0, runner=None) -> subprocess.CompletedProcess`
  - `checks.screencap_png(adb_path, port, *, timeout_s=15.0, runner=None) -> bytes`
  - `checks.png_size(data: bytes) -> tuple[int, int]`
  - `checks.parse_wm_size(text) -> tuple[int, int] | None`, `checks.parse_wm_density(text) -> int | None`
  - `checks.DisplayCheck` (frozen dataclass: `ok`, `width`, `height`, `dpi`, `detail`, `hint`), `checks.DISPLAY_HINT`, `checks.display_check(adb_path, port, *, runner=None) -> DisplayCheck`
  - `discover.DEFAULT_ADB`, `discover.bluestacks_conf_path() -> Path`, `discover.find_adb(configured=None) -> str | None`
  - `discover.Discovered` (frozen dataclass: `name`, `display_name`, `adb_port`, `width`, `height`, `dpi`)
  - `discover.parse_bluestacks_conf(text) -> list[Discovered]`, `discover.parse_devices(text) -> set[int]`
  - `discover.scan(adb_path, conf_path=None, *, runner=None) -> dict`, `discover.probe_port(adb_path, port, *, timeout_s=15.0, runner=None) -> dict`
- Consumed by: task 4 (all three routes and the screenshot route).

> **Naming note:** the brief called this function `test_port`; it is `probe_port` here because a test module importing a `test_`-prefixed function would have it collected as a test. Tests import the module (`from brawlfarm.setup import discover`) and call `discover.probe_port(...)`.

- [ ] **Step 1: Write the failing tests**

`tests/test_setup_checks.py`:

```python
"""The panel's own adb wrapper: argv lists only, a serial built from a validated integer
port, a screencap that refuses anything that is not a PNG, and the 1600 x 900 / DPI 240
display check with the sentence that tells the user where to change it."""

from __future__ import annotations

import struct
import subprocess

import pytest

from brawlfarm.core import config
from brawlfarm.setup import checks


def _done(argv: list[str], rc: int = 0, out: bytes = b"", err: bytes = b"") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(argv, rc, out, err)


class RecordingRunner:
    """A checks.Runner: answers by the first key found in the joined argv, records every
    call, and never starts a process."""

    def __init__(self, answers: dict[str, subprocess.CompletedProcess]) -> None:
        self.answers = answers
        self.calls: list[list[str]] = []

    def __call__(self, argv: list[str], timeout_s: float) -> subprocess.CompletedProcess:
        self.calls.append(list(argv))
        joined = " ".join(argv)
        for key, done in self.answers.items():
            if key in joined:
                return done
        return _done(argv, rc=1, err=b"unexpected argv")


def _png(width: int, height: int) -> bytes:
    """A PNG signature plus an IHDR chunk: all png_size and the guard ever look at."""
    ihdr = struct.pack(">II", width, height) + b"\x08\x06\x00\x00\x00"
    return checks.PNG_SIGNATURE + struct.pack(">I", len(ihdr)) + b"IHDR" + ihdr


def test_run_adb_passes_an_argv_list_with_the_binary_first() -> None:
    runner = RecordingRunner({"devices": _done(["adb", "devices"], out=b"List of devices\n")})
    done = checks.run_adb("C:/tools/adb.exe", ["devices"], runner=runner)
    assert runner.calls == [["C:/tools/adb.exe", "devices"]]
    assert done.returncode == 0


def test_serial_is_built_from_an_integer_port_only() -> None:
    assert checks.serial(5555) == "127.0.0.1:5555"
    assert checks.serial("5565") == "127.0.0.1:5565"
    with pytest.raises(ValueError):
        checks.serial("5555 && shutdown")


def test_screencap_returns_the_png_bytes() -> None:
    frame = _png(1600, 900)
    runner = RecordingRunner(
        {
            "connect": _done(["adb", "connect"], out=b"connected to 127.0.0.1:5555\n"),
            "screencap": _done(["adb", "screencap"], out=frame),
        }
    )
    assert checks.screencap_png("C:/tools/adb.exe", 5555, runner=runner) == frame
    assert runner.calls[1] == [
        "C:/tools/adb.exe",
        "-s",
        "127.0.0.1:5555",
        "exec-out",
        "screencap",
        "-p",
    ]


def test_screencap_raises_when_adb_fails() -> None:
    runner = RecordingRunner(
        {
            "connect": _done(["adb", "connect"], out=b"connected\n"),
            "screencap": _done(["adb", "screencap"], rc=1, err=b"error: device offline\n"),
        }
    )
    with pytest.raises(checks.AdbUnavailable) as exc:
        checks.screencap_png("C:/tools/adb.exe", 5555, runner=runner)
    assert "device offline" in str(exc.value)


def test_screencap_raises_when_the_output_is_not_a_png() -> None:
    runner = RecordingRunner(
        {
            "connect": _done(["adb", "connect"], out=b"connected\n"),
            "screencap": _done(["adb", "screencap"], out=b"error: closed\n"),
        }
    )
    with pytest.raises(checks.AdbUnavailable) as exc:
        checks.screencap_png("C:/tools/adb.exe", 5555, runner=runner)
    assert "did not return a PNG" in str(exc.value)


def test_png_size_reads_the_ihdr_chunk() -> None:
    assert checks.png_size(_png(1600, 900)) == (1600, 900)
    with pytest.raises(checks.AdbUnavailable):
        checks.png_size(b"not a png at all")


def test_parse_wm_size_prefers_the_override_line() -> None:
    assert checks.parse_wm_size("Physical size: 1600x900\n") == (1600, 900)
    assert (
        checks.parse_wm_size("Physical size: 1920x1080\nOverride size: 1600x900\n") == (1600, 900)
    )
    assert checks.parse_wm_size("") is None
    assert checks.parse_wm_size("error: device offline") is None


def test_parse_wm_density_prefers_the_override_line() -> None:
    assert checks.parse_wm_density("Physical density: 240\n") == 240
    assert checks.parse_wm_density("Physical density: 320\nOverride density: 240\n") == 240
    assert checks.parse_wm_density("nothing here") is None


def test_display_check_passes_at_the_resolution_the_controller_asserts() -> None:
    runner = RecordingRunner(
        {
            "connect": _done(["adb", "connect"], out=b"connected\n"),
            "wm size": _done(["adb", "wm", "size"], out=b"Physical size: 1600x900\n"),
            "wm density": _done(["adb", "wm", "density"], out=b"Physical density: 240\n"),
        }
    )
    result = checks.display_check("C:/tools/adb.exe", 5555, runner=runner)
    assert result.ok is True
    assert (result.width, result.height, result.dpi) == (
        config.SCREEN_W,
        config.SCREEN_H,
        config.SCREEN_DPI,
    )
    assert result.detail == "1600 x 900 at DPI 240"
    assert result.hint == ""


def test_display_check_explains_a_mismatch_and_where_to_fix_it() -> None:
    runner = RecordingRunner(
        {
            "connect": _done(["adb", "connect"], out=b"connected\n"),
            "wm size": _done(["adb", "wm", "size"], out=b"Physical size: 1280x720\n"),
            "wm density": _done(["adb", "wm", "density"], out=b"Physical density: 320\n"),
        }
    )
    result = checks.display_check("C:/tools/adb.exe", 5555, runner=runner)
    assert result.ok is False
    assert (result.width, result.height, result.dpi) == (1280, 720, 320)
    assert "1600 x 900 at DPI 240" in result.detail
    assert result.hint == checks.DISPLAY_HINT
    assert "Settings > Display" in result.hint
```

`tests/test_setup_discover.py`:

```python
"""Finding adb and the BlueStacks instances: the bluestacks.conf parser, the adb devices
parser, and the two probes the wizard runs. The fixture conf text is invented -- no real
instance names, display names or ports from anyone's machine."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from brawlfarm.setup import discover

CONF_TEXT = """[general]
bst.feature.rooting="0"
bst.instance.Pie64.adb_port="5555"
bst.instance.Pie64.display_name="BlueStacks App Player 1"
bst.instance.Pie64.fb_width="1600"
bst.instance.Pie64.fb_height="900"
bst.instance.Pie64.dpi="240"
bst.instance.Pie64_1.adb_port="5565"
bst.instance.Pie64_1.display_name="BlueStacks App Player 2"
bst.instance.Pie64_1.fb_width="1280"
bst.instance.Pie64_1.fb_height="720"
bst.instance.Pie64_1.dpi="240"
bst.instance.Nougat32.adb_port="5575"
"""

DEVICES_TEXT = "List of devices attached\n127.0.0.1:5555\tdevice\n127.0.0.1:5575\toffline\n\n"


def _done(argv: list[str], rc: int = 0, out: bytes = b"", err: bytes = b"") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(argv, rc, out, err)


class RecordingRunner:
    """A checks.Runner: answers by the first key found in the joined argv, records calls."""

    def __init__(self, answers: dict[str, subprocess.CompletedProcess]) -> None:
        self.answers = answers
        self.calls: list[list[str]] = []

    def __call__(self, argv: list[str], timeout_s: float) -> subprocess.CompletedProcess:
        self.calls.append(list(argv))
        joined = " ".join(argv)
        for key, done in self.answers.items():
            if key in joined:
                return done
        return _done(argv, rc=1, err=b"unexpected argv")


def test_parse_bluestacks_conf_reads_every_instance_block() -> None:
    found = discover.parse_bluestacks_conf(CONF_TEXT)
    assert [d.name for d in found] == ["Nougat32", "Pie64", "Pie64_1"]
    pie = found[1]
    assert pie.display_name == "BlueStacks App Player 1"
    assert (pie.adb_port, pie.width, pie.height, pie.dpi) == (5555, 1600, 900, 240)
    bare = found[0]
    assert bare.display_name == "Nougat32"  # no display_name key: fall back to the name
    assert (bare.width, bare.height, bare.dpi) == (None, None, None)


def test_parse_bluestacks_conf_skips_names_that_could_not_be_folders() -> None:
    too_long = "A" * 40
    text = CONF_TEXT + f'bst.instance.{too_long}.adb_port="5585"\n'
    assert [d.name for d in discover.parse_bluestacks_conf(text)] == [
        "Nougat32",
        "Pie64",
        "Pie64_1",
    ]
    assert discover.parse_bluestacks_conf("") == []


def test_parse_devices_reads_only_the_ports_that_say_device() -> None:
    assert discover.parse_devices(DEVICES_TEXT) == {5555}
    assert discover.parse_devices("") == set()


def test_find_adb_prefers_the_configured_path_then_bluestacks_then_the_path(
    tmp_path: Path, monkeypatch
) -> None:
    configured = tmp_path / "HD-Adb.exe"
    configured.write_text("", encoding="utf-8")
    bundled = tmp_path / "bundled-adb.exe"
    monkeypatch.setattr(discover, "DEFAULT_ADB", str(bundled))
    assert discover.find_adb(str(configured)) == str(configured)
    bundled.write_text("", encoding="utf-8")
    assert discover.find_adb(str(tmp_path / "gone.exe")) == str(bundled)
    bundled.unlink()
    monkeypatch.setattr(shutil, "which", lambda _name: "C:/tools/adb.exe")
    assert discover.find_adb(None) == "C:/tools/adb.exe"
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    assert discover.find_adb(None) is None


def test_scan_marks_the_instances_adb_can_see(tmp_path: Path) -> None:
    conf = tmp_path / "bluestacks.conf"
    conf.write_text(CONF_TEXT, encoding="utf-8")
    runner = RecordingRunner({"devices": _done(["adb", "devices"], out=DEVICES_TEXT.encode())})
    out = discover.scan("C:/tools/adb.exe", conf, runner=runner)
    assert out["adb_path"] == "C:/tools/adb.exe"
    assert out["adb_found"] is True and out["conf_found"] is True
    by_name = {i["name"]: i for i in out["instances"]}
    assert by_name["Pie64"] == {
        "name": "Pie64",
        "display_name": "BlueStacks App Player 1",
        "adb_port": 5555,
        "width": 1600,
        "height": 900,
        "dpi": 240,
        "online": True,
    }
    assert by_name["Pie64_1"]["online"] is False  # not in adb devices
    assert by_name["Nougat32"]["online"] is False  # listed, but "offline"


def test_scan_without_adb_or_without_the_conf_still_answers(tmp_path: Path) -> None:
    conf = tmp_path / "bluestacks.conf"
    conf.write_text(CONF_TEXT, encoding="utf-8")
    out = discover.scan(None, conf)
    assert out["adb_found"] is False and out["adb_path"] is None
    assert all(i["online"] is False for i in out["instances"])
    missing = discover.scan(None, tmp_path / "nope.conf")
    assert missing["conf_found"] is False and missing["instances"] == []


def test_test_port_reports_a_device_that_answers() -> None:
    runner = RecordingRunner(
        {
            "connect": _done(["adb", "connect"], out=b"connected to 127.0.0.1:5555\n"),
            "get-state": _done(["adb", "get-state"], out=b"device\n"),
        }
    )
    assert discover.probe_port("C:/tools/adb.exe", 5555, runner=runner) == {
        "ok": True,
        "detail": "127.0.0.1:5555 answered",
    }
    assert runner.calls[1] == ["C:/tools/adb.exe", "-s", "127.0.0.1:5555", "get-state"]


def test_test_port_fails_closed_when_the_port_does_not_answer() -> None:
    runner = RecordingRunner(
        {
            "connect": _done(["adb", "connect"], rc=1, err=b"cannot connect to 127.0.0.1:5599\n"),
            "get-state": _done(["adb", "get-state"], rc=1, err=b"error: device offline\n"),
        }
    )
    out = discover.probe_port("C:/tools/adb.exe", 5599, runner=runner)
    assert out["ok"] is False
    assert out["detail"] == "127.0.0.1:5599: error: device offline"


def test_test_port_reports_a_timeout_instead_of_raising() -> None:
    def slow(argv: list[str], timeout_s: float) -> subprocess.CompletedProcess:
        raise subprocess.TimeoutExpired(argv, timeout_s)

    assert discover.probe_port("C:/tools/adb.exe", 5555, runner=slow) == {
        "ok": False,
        "detail": "adb timed out talking to 127.0.0.1:5555",
    }
```

- [ ] **Step 2: Run them to confirm they fail**

```bash
uv run pytest tests/test_setup_checks.py tests/test_setup_discover.py -v
```

Expected: both files error during collection with `ModuleNotFoundError: No module named 'brawlfarm.setup'`.

- [ ] **Step 3: Create `brawlfarm/setup/__init__.py`**

```python
"""The setup wizard's probes: find adb, list the BlueStacks instances and their ports,
test one, and check that its display is 1600 x 900 at DPI 240.

Deliberately separate from core/adb.py. The core's adb module reads the process-global
config (one instance per worker process); these run in the panel's process against any
port the user points at, so they take the adb path as an argument and build their own
`-s 127.0.0.1:<port>` serial. Nothing here mutates core.config.
"""
```

- [ ] **Step 4: Create `brawlfarm/setup/checks.py`**

```python
"""ADB calls the setup wizard and the screenshot route need.

Every call is an argv list with shell=False, and every serial is built as
f"127.0.0.1:{int(port)}" from a validated integer port (spec section 9: no user-supplied
string reaches a shell). The subprocess runner is injectable so tests never spawn adb.
"""

from __future__ import annotations

import struct
import subprocess
from collections.abc import Callable
from dataclasses import dataclass

from brawlfarm.core import config

# The eight bytes every PNG starts with; adb prints its errors on stdout, so this is how
# we tell a frame from an error message.
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

DISPLAY_HINT = (
    "In BlueStacks open Settings > Display, choose Custom resolution 1600 x 900 and "
    "DPI 240, then restart the instance."
)

Runner = Callable[[list[str], float], subprocess.CompletedProcess]


class AdbUnavailable(RuntimeError):
    """adb could not answer for this instance. The message is one line, for the panel."""


def serial(port: int) -> str:
    """The adb serial for a local BlueStacks instance. int() is the validation: a string
    from the user can never widen this into a second argument."""
    return f"127.0.0.1:{int(port)}"


def decode(raw: bytes | str | None) -> str:
    """adb output as text. It is captured as bytes because screencap needs a binary pipe."""
    if raw is None:
        return ""
    return raw.decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw)


def first_line(raw: bytes | str | None) -> str:
    """The first non-empty line of an adb message, for a one-line panel detail."""
    for line in decode(raw).splitlines():
        if line.strip():
            return line.strip()
    return ""


def _default_runner(argv: list[str], timeout_s: float) -> subprocess.CompletedProcess:
    return subprocess.run(
        argv,
        capture_output=True,
        timeout=timeout_s,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def run_adb(
    adb_path: str,
    args: list[str],
    *,
    timeout_s: float = 15.0,
    runner: Runner | None = None,
) -> subprocess.CompletedProcess:
    """Run `<adb_path> <args...>`. An argv list, never a command string."""
    return (runner or _default_runner)([str(adb_path), *args], timeout_s)


def screencap_png(
    adb_path: str, port: int, *, timeout_s: float = 15.0, runner: Runner | None = None
) -> bytes:
    """One PNG frame from the instance, straight out of `adb exec-out screencap -p`.

    Raises AdbUnavailable with a one-line reason when adb errors, returns nothing, or
    returns something that is not a PNG (a closed instance answers with an error on
    stdout, which would otherwise reach the browser as a broken image).
    """
    dev = serial(port)
    try:
        run_adb(adb_path, ["connect", dev], timeout_s=timeout_s, runner=runner)
        done = run_adb(
            adb_path,
            ["-s", dev, "exec-out", "screencap", "-p"],
            timeout_s=timeout_s,
            runner=runner,
        )
    except subprocess.TimeoutExpired as exc:
        raise AdbUnavailable(f"adb timed out taking a screenshot of {dev}") from exc
    except (OSError, subprocess.SubprocessError) as exc:
        raise AdbUnavailable(f"adb failed for {dev}: {exc}") from exc
    if done.returncode != 0:
        raise AdbUnavailable(f"adb screencap failed for {dev}: {first_line(done.stderr)}")
    data = done.stdout or b""
    if not data:
        raise AdbUnavailable(f"adb screencap returned nothing for {dev}")
    if not data.startswith(PNG_SIGNATURE):
        raise AdbUnavailable(f"adb screencap did not return a PNG for {dev}")
    return data


def png_size(data: bytes) -> tuple[int, int]:
    """Width and height from the PNG's IHDR chunk (bytes 16 to 24, big-endian)."""
    if len(data) < 24 or not data.startswith(PNG_SIGNATURE):
        raise AdbUnavailable("not a PNG")
    width, height = struct.unpack(">II", data[16:24])
    return int(width), int(height)
```

Then the display check, in the same file:

```python
def parse_wm_size(text: str) -> tuple[int, int] | None:
    """`adb shell wm size`. An Override line wins: that is what the instance is actually
    running at, and it is what BlueStacks writes when the user picks a custom size."""
    found: dict[str, tuple[int, int]] = {}
    for kind, w, h in _SIZE_RE.findall(text or ""):
        found[kind] = (int(w), int(h))
    return found.get("Override") or found.get("Physical")


def parse_wm_density(text: str) -> int | None:
    """`adb shell wm density`, same Override-wins rule as parse_wm_size."""
    found: dict[str, int] = {}
    for kind, value in _DENSITY_RE.findall(text or ""):
        found[kind] = int(value)
    density = found.get("Override", found.get("Physical"))
    return density


@dataclass(frozen=True)
class DisplayCheck:
    """The wizard's Display step: what adb reported, and what to do when it is wrong."""

    ok: bool
    width: int | None
    height: int | None
    dpi: int | None
    detail: str
    hint: str


def display_check(adb_path: str, port: int, *, runner: Runner | None = None) -> DisplayCheck:
    """Is this instance at 1600 x 900 with DPI 240?

    The controller asserts the resolution at startup and exits otherwise (spec section 9),
    so the wizard checks it first and names the exact BlueStacks screen to change it on.
    """
    dev = serial(port)
    try:
        run_adb(adb_path, ["connect", dev], runner=runner)
        size_out = run_adb(adb_path, ["-s", dev, "shell", "wm", "size"], runner=runner)
        density_out = run_adb(adb_path, ["-s", dev, "shell", "wm", "density"], runner=runner)
    except subprocess.TimeoutExpired:
        return DisplayCheck(False, None, None, None, f"adb timed out talking to {dev}", DISPLAY_HINT)
    except (OSError, subprocess.SubprocessError) as exc:
        return DisplayCheck(False, None, None, None, f"adb failed for {dev}: {exc}", DISPLAY_HINT)
    size = parse_wm_size(decode(size_out.stdout))
    dpi = parse_wm_density(decode(density_out.stdout))
    if size is None:
        detail = first_line(size_out.stderr) or first_line(size_out.stdout) or "no answer"
        return DisplayCheck(
            False, None, None, dpi, f"adb could not read the display of {dev}: {detail}", DISPLAY_HINT
        )
    width, height = size
    if width == config.SCREEN_W and height == config.SCREEN_H and dpi == config.SCREEN_DPI:
        return DisplayCheck(True, width, height, dpi, f"{width} x {height} at DPI {dpi}", "")
    detail = (
        f"{width} x {height} at DPI {dpi if dpi is not None else '?'}; "
        f"the farm needs {config.SCREEN_W} x {config.SCREEN_H} at DPI {config.SCREEN_DPI}"
    )
    return DisplayCheck(False, width, height, dpi, detail, DISPLAY_HINT)
```

and the two regexes go up with the other module constants, next to `PNG_SIGNATURE` (add `import re` to the imports):

```python
# `wm size` / `wm density` answer with a Physical line and, when the user set a custom
# resolution, an Override line as well.
_SIZE_RE = re.compile(r"^(Physical|Override) size:\s*(\d+)x(\d+)\s*$", re.MULTILINE)
_DENSITY_RE = re.compile(r"^(Physical|Override) density:\s*(\d+)\s*$", re.MULTILINE)
```

- [ ] **Step 5: Create `brawlfarm/setup/discover.py`**

```python
"""Finding adb and the BlueStacks instances the setup wizard offers.

Parsing plus one adb call: bluestacks.conf names the instances and their ADB ports,
`adb devices` says which of them are answering. Nothing here writes anything.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from brawlfarm import settings as S
from brawlfarm.setup.checks import Runner, decode, first_line, run_adb, serial

DEFAULT_ADB = S.DEFAULT_ADB_PATH
CONF_NAME = "bluestacks.conf"

# bluestacks.conf is flat `key="value"` lines. Only the five keys the wizard shows are
# read, and the name group is already narrower than a folder name has to be.
_CONF_RE = re.compile(
    r'^bst\.instance\.([A-Za-z0-9_-]+)\.(adb_port|display_name|fb_width|fb_height|dpi)="(.*)"$'
)
_DEVICE_RE = re.compile(r"^127\.0\.0\.1:(\d+)\s+device\s*$")


@dataclass(frozen=True)
class Discovered:
    """One row in the wizard's Instances step, straight from bluestacks.conf."""

    name: str
    display_name: str
    adb_port: int | None
    width: int | None
    height: int | None
    dpi: int | None


def bluestacks_conf_path() -> Path:
    """%PROGRAMDATA%\\BlueStacks_nxt\\bluestacks.conf, where BlueStacks 5 keeps the
    instance table."""
    root = os.environ.get("PROGRAMDATA", "").strip() or r"C:\ProgramData"
    return Path(root) / "BlueStacks_nxt" / CONF_NAME


def find_adb(configured: str | None = None) -> str | None:
    """The adb to use: what the user configured if it is really there, else the one
    BlueStacks ships, else whatever is on PATH. None when nothing is installed."""
    for candidate in (configured, DEFAULT_ADB):
        if candidate and Path(candidate).exists():
            return str(candidate)
    return shutil.which("adb")


def parse_bluestacks_conf(text: str) -> list[Discovered]:
    """One Discovered per `bst.instance.<name>.*` block, sorted by name.

    A name that could not be a folder (INSTANCE_NAME_RE) is skipped: the wizard writes it
    straight into config.toml and creates <home>/instances/<name>/ from it.
    """
    fields: dict[str, dict[str, str]] = {}
    for line in (text or "").splitlines():
        m = _CONF_RE.match(line.strip())
        if not m:
            continue
        name, key, value = m.group(1), m.group(2), m.group(3)
        if not S.INSTANCE_NAME_RE.match(name):
            continue
        fields.setdefault(name, {})[key] = value
    out: list[Discovered] = []
    for name in sorted(fields):
        f = fields[name]
        out.append(
            Discovered(
                name=name,
                display_name=f.get("display_name") or name,
                adb_port=_int_or_none(f.get("adb_port")),
                width=_int_or_none(f.get("fb_width")),
                height=_int_or_none(f.get("fb_height")),
                dpi=_int_or_none(f.get("dpi")),
            )
        )
    return out


def parse_devices(text: str) -> set[int]:
    """The local ports `adb devices` reports as `device`. An `offline` or `unauthorized`
    row is not one of them."""
    ports: set[int] = set()
    for line in (text or "").splitlines():
        m = _DEVICE_RE.match(line.strip())
        if m:
            ports.add(int(m.group(1)))
    return ports


def scan(
    adb_path: str | None, conf_path: Path | None = None, *, runner: Runner | None = None
) -> dict:
    """What the wizard's Instances step shows: where adb is, whether bluestacks.conf was
    found, and a row per instance with its port, display size and whether it answers.

    Blocking (it shells out to adb), so route handlers call it through asyncio.to_thread.
    """
    path = Path(conf_path) if conf_path is not None else bluestacks_conf_path()
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        conf_found = True
    except OSError:
        text, conf_found = "", False
    online = _online_ports(adb_path, runner) if adb_path else set()
    return {
        "adb_path": str(adb_path) if adb_path else None,
        "adb_found": bool(adb_path),
        "conf_found": conf_found,
        "instances": [
            {**asdict(d), "online": d.adb_port is not None and d.adb_port in online}
            for d in parse_bluestacks_conf(text)
        ],
    }


def probe_port(
    adb_path: str, port: int, *, timeout_s: float = 15.0, runner: Runner | None = None
) -> dict:
    """Can the panel actually talk to this instance? `adb connect`, then `adb get-state`.

    Fails CLOSED, unlike supervisor.process.instance_online: the wizard is asking the user
    to trust this row, so an unanswered probe must read as "not working", not as
    "probably fine". The supervisor's probe fails open for the opposite reason -- a broken
    probe there would strand a healthy instance in backoff.
    """
    dev = serial(port)
    try:
        connected = run_adb(adb_path, ["connect", dev], timeout_s=timeout_s, runner=runner)
        state = run_adb(adb_path, ["-s", dev, "get-state"], timeout_s=timeout_s, runner=runner)
    except subprocess.TimeoutExpired:
        return {"ok": False, "detail": f"adb timed out talking to {dev}"}
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ok": False, "detail": f"adb failed for {dev}: {exc}"}
    if decode(state.stdout).strip() == "device":
        return {"ok": True, "detail": f"{dev} answered"}
    reason = (
        first_line(state.stderr)
        or first_line(state.stdout)
        or first_line(connected.stdout)
        or "no answer"
    )
    return {"ok": False, "detail": f"{dev}: {reason}"}


def _online_ports(adb_path: str, runner: Runner | None) -> set[int]:
    try:
        done = run_adb(adb_path, ["devices"], runner=runner)
    except (OSError, subprocess.SubprocessError):
        return set()
    if done.returncode != 0:
        return set()
    return parse_devices(decode(done.stdout))


def _int_or_none(value: str | None) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None
```

- [ ] **Step 6: Run the new tests, then the whole suite**

```bash
uv run pytest tests/test_setup_checks.py tests/test_setup_discover.py -v
uv run pytest -q
```

Expected: 19 new tests PASS; the full suite passes at 461 tests (442 + 19) with no warnings. If pytest reports `fixture 'adb_path' not found` in `tests/test_setup_discover.py`, a `from ... import probe_port` slipped in: import the module instead.

- [ ] **Step 7: Lint, scrub, commit**

```bash
uv run ruff format brawlfarm/setup tests/test_setup_checks.py tests/test_setup_discover.py
uv run ruff check --fix brawlfarm/setup tests
uv run ruff check . && uv run ruff format --check .
uv run python tools/scrub_check.py
git add brawlfarm/setup tests/test_setup_checks.py tests/test_setup_discover.py
git commit -m "feat(setup): adb discovery and the 1600x900 display check

The setup wizard needs to find HD-Adb.exe, read the instance table out of
bluestacks.conf, say which ports answer, and prove an instance is at 1600 x 900
with DPI 240 before the controller's startup assertion kills a worker over it.

This is a second, small adb wrapper next to supervisor/process.py rather than a
reuse of core/adb.py: core/adb.py reads the process-global config that belongs to
a worker, and the panel must not mutate it. Serials are built from int(port) and
every call is an argv list. probe_port fails closed (the user is being asked to
trust the row) where the supervisor's probe fails open (a broken probe must never
strand a healthy instance)."
```

---
### Task 4: Setup routes and the screenshot route

The four routes that shell out to adb. Each one runs its blocking call in `asyncio.to_thread` so a slow or hung adb never freezes the event loop (and with it the SSE stream and the supervisor task sharing it).

**Files:**
- Create: `brawlfarm/api/setup_routes.py`
- Create: `brawlfarm/api/screens.py`
- Modify: `brawlfarm/api/app.py` (the `app.state` block and the `# --- routers ---` block)
- Create: `tests/test_api_setup_routes.py`
- Create: `tests/test_api_screenshot.py`

**Interfaces:**
- Consumes: `setup.discover.find_adb/scan/probe_port`, `setup.checks.display_check/screencap_png/AdbUnavailable/DisplayCheck/DISPLAY_HINT`, `api.deps.get_sup/resolve_instance`, `core.config.SCREEN_W/SCREEN_H/SCREEN_DPI`.
- Produces:
  - `setup_routes.router`, `setup_routes.ScanBody`, `setup_routes.PortBody`, `setup_routes.NO_ADB_DETAIL`
  - `screens.router`
  - `app.state.screenshot_locks: dict[str, asyncio.Lock]`
  - `POST /api/setup/scan` -> the `discover.scan` dict; `POST /api/setup/test` -> `{"ok", "detail"}`; `POST /api/setup/display-check` -> the `DisplayCheck` fields plus `"expected": {"width": 1600, "height": 900, "dpi": 240}`
  - `GET /api/instances/{name}/screenshot.png` -> `image/png`, `Cache-Control: no-store`, 503 on `AdbUnavailable`
- Consumed by: phase 4's Setup wizard and the Fleet thumbnail; nothing else in phase 3.

- [ ] **Step 1: Write the failing tests**

`tests/test_api_setup_routes.py`:

```python
"""The setup wizard's three probes over HTTP: the body's adb path wins over the configured
one, a missing adb is reported instead of crashing, and the display check always carries
the resolution the farm expects."""

from __future__ import annotations

from pathlib import Path

import pytest

from brawlfarm.setup import checks, discover
from tests.apihelpers import make_client


@pytest.fixture()
def api(tmp_path: Path):
    client, sup, home = make_client(tmp_path, ("alpha", "bravo"))
    try:
        yield client, sup, home
    finally:
        client.__exit__(None, None, None)


def test_scan_uses_the_configured_adb_path(api, monkeypatch) -> None:
    client, _sup, _home = api
    seen: dict[str, object] = {}

    def fake_find_adb(configured=None):
        seen["configured"] = configured
        return "C:/tools/adb.exe"

    def fake_scan(adb_path, conf_path=None, *, runner=None):
        return {"adb_path": adb_path, "adb_found": True, "conf_found": True, "instances": []}

    monkeypatch.setattr(discover, "find_adb", fake_find_adb)
    monkeypatch.setattr(discover, "scan", fake_scan)
    r = client.post("/api/setup/scan", json={})
    assert r.status_code == 200
    assert str(seen["configured"]).endswith("HD-Adb.exe")  # the configured default
    assert r.json() == {
        "adb_path": "C:/tools/adb.exe",
        "adb_found": True,
        "conf_found": True,
        "instances": [],
    }


def test_scan_prefers_the_path_in_the_body(api, monkeypatch) -> None:
    client, _sup, _home = api
    seen: dict[str, object] = {}

    def fake_find_adb(configured=None):
        seen["configured"] = configured
        return configured

    monkeypatch.setattr(discover, "find_adb", fake_find_adb)
    monkeypatch.setattr(
        discover,
        "scan",
        lambda adb_path, conf_path=None, *, runner=None: {
            "adb_path": adb_path,
            "adb_found": bool(adb_path),
            "conf_found": False,
            "instances": [],
        },
    )
    r = client.post("/api/setup/scan", json={"adb_path": "D:/portable/adb.exe"})
    assert r.status_code == 200
    assert seen["configured"] == "D:/portable/adb.exe"
    assert r.json()["adb_path"] == "D:/portable/adb.exe"


def test_test_reports_a_port_that_answers(api, monkeypatch) -> None:
    client, _sup, _home = api
    monkeypatch.setattr(discover, "find_adb", lambda configured=None: "C:/tools/adb.exe")
    monkeypatch.setattr(
        discover,
        "probe_port",
        lambda adb_path, port, **kw: {"ok": True, "detail": f"127.0.0.1:{port} answered"},
    )
    r = client.post("/api/setup/test", json={"adb_port": 5565})
    assert r.status_code == 200
    assert r.json() == {"ok": True, "detail": "127.0.0.1:5565 answered"}


def test_test_without_adb_says_so_instead_of_failing(api, monkeypatch) -> None:
    client, _sup, _home = api
    monkeypatch.setattr(discover, "find_adb", lambda configured=None: None)
    r = client.post("/api/setup/test", json={"adb_port": 5565})
    assert r.status_code == 200
    assert r.json() == {"ok": False, "detail": "adb was not found; set its path in Connection"}


def test_display_check_carries_what_the_farm_expects(api, monkeypatch) -> None:
    client, _sup, _home = api
    monkeypatch.setattr(discover, "find_adb", lambda configured=None: "C:/tools/adb.exe")
    monkeypatch.setattr(
        checks,
        "display_check",
        lambda adb_path, port, **kw: checks.DisplayCheck(
            False, 1280, 720, 320, "1280 x 720 at DPI 320", checks.DISPLAY_HINT
        ),
    )
    r = client.post("/api/setup/display-check", json={"adb_port": 5555})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert (body["width"], body["height"], body["dpi"]) == (1280, 720, 320)
    assert body["hint"] == checks.DISPLAY_HINT
    assert body["expected"] == {"width": 1600, "height": 900, "dpi": 240}


def test_a_port_outside_the_valid_range_is_rejected(api) -> None:
    client, _sup, _home = api
    assert client.post("/api/setup/test", json={"adb_port": 0}).status_code == 422
    assert client.post("/api/setup/display-check", json={"adb_port": 99999}).status_code == 422
    assert client.post("/api/setup/scan", json={"nope": 1}).status_code == 422
```

`tests/test_api_screenshot.py`:

```python
"""GET /api/instances/{name}/screenshot.png: the PNG straight through with no caching,
503 when adb cannot answer, 404 for a name that is not configured, and one lock per
instance so two thumbnails never race the same BlueStacks window."""

from __future__ import annotations

import asyncio
import struct
from pathlib import Path

import pytest

from brawlfarm.api import screens
from brawlfarm.setup.checks import PNG_SIGNATURE, AdbUnavailable
from tests.apihelpers import make_client


@pytest.fixture()
def api(tmp_path: Path):
    client, sup, home = make_client(tmp_path, ("alpha", "bravo"))
    try:
        yield client, sup, home
    finally:
        client.__exit__(None, None, None)


def _png(width: int, height: int) -> bytes:
    ihdr = struct.pack(">II", width, height) + b"\x08\x06\x00\x00\x00"
    return PNG_SIGNATURE + struct.pack(">I", len(ihdr)) + b"IHDR" + ihdr


def test_screenshot_returns_the_png_and_forbids_caching(api, monkeypatch) -> None:
    client, _sup, _home = api
    frame = _png(1600, 900)
    seen: dict[str, object] = {}

    def fake_screencap(adb_path, port, **kw):
        seen["adb_path"], seen["port"] = adb_path, port
        return frame

    monkeypatch.setattr(screens, "screencap_png", fake_screencap)
    r = client.get("/api/instances/alpha/screenshot.png")
    assert r.status_code == 200
    assert r.content == frame
    assert r.headers["content-type"] == "image/png"
    assert r.headers["cache-control"] == "no-store"
    assert seen["port"] == 5555
    assert str(seen["adb_path"]).endswith("HD-Adb.exe")


def test_screenshot_is_503_when_adb_cannot_answer(api, monkeypatch) -> None:
    client, _sup, _home = api

    def boom(adb_path, port, **kw):
        raise AdbUnavailable("adb screencap failed for 127.0.0.1:5555: device offline")

    monkeypatch.setattr(screens, "screencap_png", boom)
    r = client.get("/api/instances/alpha/screenshot.png")
    assert r.status_code == 503
    assert r.json() == {"detail": "adb screencap failed for 127.0.0.1:5555: device offline"}


def test_screenshot_of_an_unknown_instance_is_404(api) -> None:
    client, _sup, _home = api
    r = client.get("/api/instances/ghost/screenshot.png")
    assert r.status_code == 404
    assert r.json() == {"detail": "unknown instance"}


def test_each_instance_gets_one_reused_lock(api, monkeypatch) -> None:
    client, _sup, _home = api
    monkeypatch.setattr(screens, "screencap_png", lambda adb_path, port, **kw: _png(16, 9))
    assert client.get("/api/instances/alpha/screenshot.png").status_code == 200
    assert client.get("/api/instances/alpha/screenshot.png").status_code == 200
    assert client.get("/api/instances/bravo/screenshot.png").status_code == 200
    locks = client.app.state.screenshot_locks
    assert set(locks) == {"alpha", "bravo"}
    assert all(isinstance(lock, asyncio.Lock) for lock in locks.values())
```

- [ ] **Step 2: Run them to confirm they fail**

```bash
uv run pytest tests/test_api_setup_routes.py tests/test_api_screenshot.py -v
```

Expected: both files error during collection with `ModuleNotFoundError: No module named 'brawlfarm.api.screens'` and `... 'brawlfarm.api.setup_routes'`.

- [ ] **Step 3: Create `brawlfarm/api/setup_routes.py`**

```python
"""POST /api/setup/scan, /api/setup/test and /api/setup/display-check: the three probes
the setup wizard runs.

Each one shells out to adb, which can take seconds and can hang, so each one goes through
asyncio.to_thread -- the event loop also carries the supervisor task and the SSE stream.
The body's adb_path wins over the configured one, so the wizard's Browse field works
before anything has been saved to config.toml.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from brawlfarm.api.deps import get_sup
from brawlfarm.core import config
from brawlfarm.setup import checks, discover

router = APIRouter()

NO_ADB_DETAIL = "adb was not found; set its path in Connection"


class ScanBody(BaseModel):
    """Optional body for the scan: the path the user typed, if any."""

    model_config = ConfigDict(extra="forbid")

    adb_path: str | None = None


class PortBody(BaseModel):
    """One instance to probe. The port range is what makes the serial safe to build."""

    model_config = ConfigDict(extra="forbid")

    adb_port: int = Field(ge=1, le=65535)
    adb_path: str | None = None


def _expected() -> dict:
    """The display the controller asserts at startup (core/config.py calibration block)."""
    return {"width": config.SCREEN_W, "height": config.SCREEN_H, "dpi": config.SCREEN_DPI}


async def _adb_path(request: Request, override: str | None) -> str | None:
    """The adb to probe with: the body's path if it is really there, else the configured
    one, else the BlueStacks default or PATH."""
    configured = override or get_sup(request).settings.connection.adb_path
    return await asyncio.to_thread(discover.find_adb, configured)


@router.post("/api/setup/scan")
async def scan(request: Request, body: ScanBody | None = None) -> dict:
    """Find adb and list the BlueStacks instances with their ports, display size and
    whether they answer."""
    adb_path = await _adb_path(request, body.adb_path if body else None)
    return await asyncio.to_thread(discover.scan, adb_path)


@router.post("/api/setup/test")
async def test_instance_port(request: Request, body: PortBody) -> dict:
    """Does this port answer? Fails closed: no answer reads as not working."""
    adb_path = await _adb_path(request, body.adb_path)
    if not adb_path:
        return {"ok": False, "detail": NO_ADB_DETAIL}
    return await asyncio.to_thread(discover.probe_port, adb_path, body.adb_port)


@router.post("/api/setup/display-check")
async def display_check(request: Request, body: PortBody) -> dict:
    """1600 x 900 at DPI 240 or not, plus the sentence naming where to change it."""
    adb_path = await _adb_path(request, body.adb_path)
    if not adb_path:
        missing = checks.DisplayCheck(False, None, None, None, NO_ADB_DETAIL, checks.DISPLAY_HINT)
        return {**asdict(missing), "expected": _expected()}
    result = await asyncio.to_thread(checks.display_check, adb_path, body.adb_port)
    return {**asdict(result), "expected": _expected()}
```

- [ ] **Step 4: Create `brawlfarm/api/screens.py`**

```python
"""GET /api/instances/{name}/screenshot.png: one live adb frame for the Fleet thumbnail
and the Instance screen.

A screencap takes about a second and BlueStacks does not enjoy two at once against the
same instance, so each instance has its own asyncio.Lock and the call runs in a thread.
Nothing is cached and the response says so: the browser asks again when it wants a newer
frame (the UI refreshes every 15 s while the tab is visible).
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Request, Response

from brawlfarm.api.deps import get_sup, resolve_instance
from brawlfarm.setup.checks import AdbUnavailable, screencap_png

router = APIRouter()


def _lock_for(request: Request, name: str) -> asyncio.Lock:
    """One lock per instance, created on first use so it binds to the running loop."""
    locks = request.app.state.screenshot_locks
    lock = locks.get(name)
    if lock is None:
        lock = locks[name] = asyncio.Lock()
    return lock


@router.get("/api/instances/{name}/screenshot.png")
async def screenshot(request: Request, name: str) -> Response:
    """The instance's screen right now, or 503 with one line saying why adb could not."""
    inst, _dir = resolve_instance(request, name)
    adb_path = get_sup(request).settings.connection.adb_path
    async with _lock_for(request, inst.name):
        try:
            png = await asyncio.to_thread(screencap_png, adb_path, inst.adb_port)
        except AdbUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    return Response(content=png, media_type="image/png", headers={"Cache-Control": "no-store"})
```

- [ ] **Step 5: Wire both routers and the lock table into `create_app`**

In `brawlfarm/api/app.py`, extend the import to:

```python
from brawlfarm.api import instances, screens, settings_routes, setup_routes
```

add the lock table to the `app.state` block:

```python
    app = FastAPI(title="brawlfarm", version=__version__, lifespan=lifespan)
    app.state.sup = sup
    app.state.home = Path(home).resolve()
    app.state.started_at = time.monotonic()
    # One asyncio.Lock per instance, filled lazily by the screenshot route: two
    # concurrent screencaps against one BlueStacks window fight each other.
    app.state.screenshot_locks = {}
```

and extend the routers block:

```python
    # --- routers ---------------------------------------------------------------------
    # Included before the static mount below, so /api/* always wins over the SPA.
    app.include_router(instances.router)
    app.include_router(settings_routes.router)
    app.include_router(setup_routes.router)
    app.include_router(screens.router)
```

- [ ] **Step 6: Run the new tests, then the whole suite**

```bash
uv run pytest tests/test_api_setup_routes.py tests/test_api_screenshot.py -v
uv run pytest -q
```

Expected: 10 new tests PASS; the full suite passes at 471 tests (461 + 10) with no warnings.

- [ ] **Step 7: Lint, scrub, commit**

```bash
uv run ruff format brawlfarm/api tests/test_api_setup_routes.py tests/test_api_screenshot.py
uv run ruff check --fix brawlfarm/api tests
uv run ruff check . && uv run ruff format --check .
uv run python tools/scrub_check.py
git add brawlfarm/api tests/test_api_setup_routes.py tests/test_api_screenshot.py
git commit -m "feat(api): setup probes and the live screenshot route

The wizard's scan, test and display-check routes plus the per-instance
screenshot. All four shell out to adb, which can take seconds and can hang, so
each runs in asyncio.to_thread: the same event loop carries the supervisor task
and the event stream, and a blocked loop would freeze the whole panel.

Screenshots take one lock per instance because two concurrent screencaps against
one BlueStacks window fight each other, and they are served no-store so the
15 s thumbnail refresh actually gets a new frame. An adb failure is a 503 with
one plain line, never a stack trace or a broken image."
```

---
### Task 5: Plan and schedule routes, and the scheduler's read-only twins

The Instance screen's right column. The farm plan is a typed model over `core/farmplan.py`'s untyped dict; the schedule route needs two readers the scheduler never had, because the panel until now only ever wrote to those files (`set_enabled`, `bump_nonce`, `write_override`, `clear_override`).

**Files:**
- Modify: `brawlfarm/core/scheduler.py` (the panel-side helpers block; insert after `clear_override`, around line 980)
- Create: `brawlfarm/api/plans.py`
- Create: `brawlfarm/api/schedule.py`
- Modify: `brawlfarm/api/app.py` (the `# --- routers ---` block)
- Create: `tests/test_scheduler_reads.py`
- Create: `tests/test_api_plan.py`
- Create: `tests/test_api_schedule.py`

**Interfaces:**
- Consumes: `farmplan.load_plan(data_dir=...)`, `farmplan.save_plan(plan, data_dir=...)`; `scheduler.read_schedule`, `scheduler.set_enabled`, `scheduler.bump_nonce`, `scheduler.clear_override`, `scheduler.read_control`, `scheduler._ctl_enabled`, `scheduler._override_path`, `scheduler._read_json`; `api.deps.resolve_instance`, `api.deps.get_sup`.
- Produces:
  - `scheduler.read_override(name: str) -> dict | None` (exactly `{"mode", "until", "set_at"}`, or None)
  - `scheduler.is_enabled(name: str) -> bool` (the default-on control-file rule as a public call)
  - `plans.router`, `plans.FarmPlan` (pydantic, `extra="forbid"`), `plans.MAXED_FALLBACK_MAX`
  - `schedule.router`, `schedule.SchedulePatch`, `schedule.schedule_payload(name, now) -> dict`
  - `GET|PUT /api/instances/{name}/plan`, `GET|PUT /api/instances/{name}/schedule`
- Consumed by: phase 4's Instance screen. Nothing else in phase 3 depends on these.

- [ ] **Step 1: Write the failing tests**

`tests/test_scheduler_reads.py`:

```python
"""scheduler.read_override and scheduler.is_enabled: the read-only twins of the writers
the panel already had. The panel has to show the switch and the override it is about to
change, and until now it could only write them."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from brawlfarm.core import config, scheduler

_INSTANCES = {"alpha": {"port": "5555", "tag": "", "data": "instances/alpha"}}


def _one_instance(home: Path) -> None:
    config.set_home(home)
    config.set_instances(_INSTANCES)


def test_read_override_returns_what_write_override_wrote(tmp_path: Path) -> None:
    _one_instance(tmp_path)
    assert scheduler.read_override("alpha") is None
    scheduler.write_override("alpha", "run", datetime(2026, 9, 10, 16, 0, 0))
    override = scheduler.read_override("alpha")
    assert set(override) == {"mode", "until", "set_at"}
    assert override["mode"] == "run"
    assert override["until"] == "2026-09-10T16:00:00"
    scheduler.clear_override("alpha")
    assert scheduler.read_override("alpha") is None


def test_read_override_is_none_for_junk_or_an_unknown_instance(tmp_path: Path) -> None:
    _one_instance(tmp_path)
    path = tmp_path / "instances" / "alpha" / "override.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"mode": "sideways", "until": "2026-09-10T16:00:00"}', encoding="utf-8")
    assert scheduler.read_override("alpha") is None
    path.write_text("not json at all", encoding="utf-8")
    assert scheduler.read_override("alpha") is None
    assert scheduler.read_override("ghost") is None  # not in config.INSTANCES


def test_is_enabled_is_default_on_and_honours_an_explicit_false(tmp_path: Path) -> None:
    _one_instance(tmp_path)
    assert scheduler.is_enabled("alpha") is True  # no control file at all
    scheduler.set_enabled(["alpha"], False)
    assert scheduler.is_enabled("alpha") is False
    scheduler.set_enabled(["alpha"], True)
    assert scheduler.is_enabled("alpha") is True
    scheduler.bump_nonce("alpha")  # a redraw must never silently disable an account
    assert scheduler.is_enabled("alpha") is True
```

`tests/test_api_plan.py`:

```python
"""GET and PUT /api/instances/{name}/plan: the four keys core/farmplan.py stores, typed,
with the legacy files on disk still readable."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from brawlfarm import settings as S
from brawlfarm.core import farmplan
from tests.apihelpers import make_client

PLAN_URL = "/api/instances/alpha/plan"


@pytest.fixture()
def api(tmp_path: Path):
    client, sup, home = make_client(tmp_path, ("alpha", "bravo"))
    try:
        yield client, sup, home
    finally:
        client.__exit__(None, None, None)


def test_get_returns_the_defaults_for_a_fresh_instance(api) -> None:
    client, _sup, _home = api
    assert client.get(PLAN_URL).json() == {
        "mode": "ladder",
        "prestige_start": "highest",
        "goal_trophies": 1000,
        "maxed_fallback": None,
    }
    assert client.get("/api/instances/ghost/plan").status_code == 404


def test_put_writes_the_plan_the_worker_reads(api) -> None:
    client, _sup, home = api
    r = client.put(
        PLAN_URL,
        json={
            "mode": "prestige",
            "prestige_start": "lowest",
            "goal_trophies": 1200,
            "maxed_fallback": "  Shelly  ",
        },
    )
    assert r.status_code == 200
    assert r.json() == {
        "mode": "prestige",
        "prestige_start": "lowest",
        "goal_trophies": 1200,
        "maxed_fallback": "Shelly",
    }
    assert farmplan.load_plan(data_dir=S.instance_dir(home, "alpha")) == r.json()


def test_put_rejects_a_mode_the_worker_does_not_know(api) -> None:
    client, _sup, _home = api
    assert client.put(PLAN_URL, json={"mode": "manual"}).status_code == 422
    assert client.put(PLAN_URL, json={"prestige_start": "sideways"}).status_code == 422
    assert client.put(PLAN_URL, json={"goal_trophies": -1}).status_code == 422


def test_put_rejects_a_key_the_worker_would_never_read(api) -> None:
    client, _sup, _home = api
    assert client.put(PLAN_URL, json={"queue": ["Shelly"]}).status_code == 422


def test_a_blank_maxed_fallback_is_stored_as_null(api) -> None:
    client, _sup, _home = api
    assert client.put(PLAN_URL, json={"maxed_fallback": "   "}).json()["maxed_fallback"] is None
    assert client.put(PLAN_URL, json={"maxed_fallback": None}).json()["maxed_fallback"] is None
    assert client.put(PLAN_URL, json={"maxed_fallback": "X" * 40}).status_code == 422


def test_a_legacy_plan_file_still_reads(api) -> None:
    client, _sup, home = api
    inst_dir = S.instance_dir(home, "alpha")
    inst_dir.mkdir(parents=True, exist_ok=True)
    (inst_dir / "farmplan.json").write_text(
        json.dumps(
            {"mode": "optimal", "goal_trophies": 1500, "queue": ["Shelly"], "target": None}
        ),
        encoding="utf-8",
    )
    body = client.get(PLAN_URL).json()
    assert body["mode"] == "ladder"  # load_plan aliases the removed mode
    assert body["goal_trophies"] == 1500
    assert set(body) == {"mode", "prestige_start", "goal_trophies", "maxed_fallback"}
```

`tests/test_api_schedule.py`:

```python
"""GET and PUT /api/instances/{name}/schedule: the on/off switch, today's sessions, the
scheduler's desired block and the manual override, and the three things a PUT can do."""

from __future__ import annotations

from pathlib import Path

import pytest

from brawlfarm.core import scheduler
from tests.apihelpers import make_client

SCHEDULE_URL = "/api/instances/alpha/schedule"


@pytest.fixture()
def api(tmp_path: Path):
    client, sup, home = make_client(tmp_path, ("alpha", "bravo"))
    try:
        yield client, sup, home
    finally:
        client.__exit__(None, None, None)


def test_get_reports_the_switch_the_plan_and_the_override(api) -> None:
    client, _sup, _home = api
    body = client.get(SCHEDULE_URL).json()
    assert set(body) == {
        "enabled",
        "override",
        "plan_date",
        "sessions",
        "day_end",
        "desired",
        "games_played_today",
        "now",
    }
    assert body["enabled"] is False  # make_client switches the schedule off
    assert body["override"] is None
    assert body["sessions"] == [] and body["plan_date"] is None and body["day_end"] is None
    assert body["desired"]["state"] == "run" and body["desired"]["reason"] == "disabled"
    assert body["games_played_today"] == 0
    assert body["now"].count(":") == 2  # ISO seconds


def test_put_turns_the_schedule_on_for_that_instance_only(api) -> None:
    client, _sup, _home = api
    r = client.put(SCHEDULE_URL, json={"enabled": True})
    assert r.status_code == 200 and r.json()["enabled"] is True
    assert scheduler.is_enabled("alpha") is True
    assert scheduler.is_enabled("bravo") is False


def test_put_redraw_bumps_the_nonce(api) -> None:
    client, _sup, _home = api
    before = int(((scheduler.read_control().get("accounts") or {}).get("alpha") or {}).get("nonce") or 0)
    assert client.put(SCHEDULE_URL, json={"redraw": True}).status_code == 200
    after = int(scheduler.read_control()["accounts"]["alpha"]["nonce"])
    assert after == before + 1
    assert scheduler.is_enabled("alpha") is False  # a redraw does not touch the switch


def test_put_clear_override_cancels_a_stop(api) -> None:
    client, _sup, _home = api
    assert client.post("/api/instances/alpha/stop").status_code == 202
    assert client.get(SCHEDULE_URL).json()["override"]["mode"] == "stop"
    r = client.put(SCHEDULE_URL, json={"clear_override": True})
    assert r.status_code == 200
    assert r.json()["override"] is None
    assert scheduler.read_override("alpha") is None


def test_unknown_keys_and_unknown_instances_are_refused(api) -> None:
    client, _sup, _home = api
    assert client.put(SCHEDULE_URL, json={"nope": True}).status_code == 422
    assert client.get("/api/instances/ghost/schedule").status_code == 404
    assert client.put("/api/instances/ghost/schedule", json={"redraw": True}).status_code == 404
```

- [ ] **Step 2: Run them to confirm they fail**

```bash
uv run pytest tests/test_scheduler_reads.py tests/test_api_plan.py tests/test_api_schedule.py -v
```

Expected: `tests/test_scheduler_reads.py` fails with `AttributeError: module 'brawlfarm.core.scheduler' has no attribute 'read_override'`; the two API files error during collection with `ModuleNotFoundError: No module named 'brawlfarm.api.plans'` and `... 'brawlfarm.api.schedule'`.

- [ ] **Step 3: Add the two readers to `brawlfarm/core/scheduler.py`**

In the "Panel-side helpers" block, immediately after `clear_override` (around line 980) and before `read_schedule`, insert:

```python
def read_override(name: str) -> dict | None:
    """The account's manual override (/start or /stop), or None when there is none, the
    file is unreadable, or the account is not configured. Read-only twin of
    write_override: pruning an expired override stays the tick's job, so the panel can
    show one that is about to lapse."""
    try:
        raw = _read_json(_override_path(name))
    except KeyError:  # not in config.INSTANCES
        return None
    if not raw or raw.get("mode") not in ("run", "stop") or not raw.get("until"):
        return None
    return {"mode": raw["mode"], "until": raw["until"], "set_at": raw.get("set_at")}


def is_enabled(name: str) -> bool:
    """Is the schedule ON for this account? The DEFAULT-ON rule of _ctl_enabled as a
    public call: a missing control file or a missing entry counts as enabled, and only an
    explicit enabled=false (what the panel's switch writes) opts out."""
    accounts = read_control().get("accounts") or {}
    return _ctl_enabled(accounts.get(name) or {})
```

- [ ] **Step 4: Create `brawlfarm/api/plans.py`**

```python
"""GET and PUT /api/instances/{name}/plan: the instance's farmplan.json, typed.

core/farmplan.py stores an untyped dict and validates nothing, so the model here is the
only gate: four keys, no others, so a typo in the editor cannot write a field the worker
will never read. Legacy files on disk carry extra keys and retired modes -- GET drops the
extras and load_plan aliases the modes, because the editor must always have something to
show.

The worker re-reads the plan live (at startup and on every trophy snapshot, roughly once
a minute), so a PUT takes effect without restarting anything. The owned-brawler roster
and the queue the editor will offer arrive with the Instance screen in phase 4.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from brawlfarm.api.deps import resolve_instance
from brawlfarm.core import farmplan

router = APIRouter()

MAXED_FALLBACK_MAX = 32  # a brawler name; anything longer is a paste accident


class FarmPlan(BaseModel):
    """The four keys core/farmplan.py stores (its DEFAULT_PLAN), with types."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["ladder", "prestige"] = "ladder"
    prestige_start: Literal["highest", "lowest"] = "highest"
    goal_trophies: int = Field(default=1000, ge=0)
    maxed_fallback: str | None = Field(default=None, max_length=MAXED_FALLBACK_MAX)

    @field_validator("maxed_fallback")
    @classmethod
    def _blank_is_none(cls, v: str | None) -> str | None:
        """An empty box means "no fallback", not a brawler called "" (the worker matches
        this name case-insensitively against the owned roster)."""
        v = (v or "").strip()
        return v or None


def _as_plan(raw: dict) -> FarmPlan:
    """A stored plan as the model. Unknown keys are dropped and an unusable value falls
    back to the default: a hand-edited or legacy farmplan.json must not 500 the editor."""
    known = {k: v for k, v in raw.items() if k in FarmPlan.model_fields}
    try:
        return FarmPlan(**known)
    except ValidationError:
        return FarmPlan()


@router.get("/api/instances/{name}/plan")
async def read_plan(request: Request, name: str) -> dict:
    """The stored plan merged over the defaults (a missing file reads as ladder)."""
    _inst, inst_dir = resolve_instance(request, name)
    return _as_plan(farmplan.load_plan(data_dir=inst_dir)).model_dump()


@router.put("/api/instances/{name}/plan")
async def write_plan(request: Request, name: str, body: FarmPlan) -> dict:
    """Replace the plan. A running worker picks it up within a minute; no restart."""
    _inst, inst_dir = resolve_instance(request, name)
    inst_dir.mkdir(parents=True, exist_ok=True)
    return _as_plan(farmplan.save_plan(body.model_dump(), data_dir=inst_dir)).model_dump()
```

- [ ] **Step 5: Create `brawlfarm/api/schedule.py`**

```python
"""GET and PUT /api/instances/{name}/schedule: the on/off switch, today's drawn sessions,
the scheduler's desired block and the manual override.

The scheduler tick owns schedule.json and scheduler_state.json; the panel only ever
writes the control file (enabled, nonce) and override.json -- exactly the three
primitives the legacy chat commands had. "Run for N hours" and "Stop" are the start and
stop controls in instances.py (they write the override); clear_override here cancels
either one.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict

from brawlfarm.api.deps import get_sup, resolve_instance
from brawlfarm.core import scheduler

router = APIRouter()


class SchedulePatch(BaseModel):
    """A patch, not a document: only what is present acts. All three can arrive at once."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = None
    redraw: bool = False
    clear_override: bool = False


def schedule_payload(name: str, now: datetime) -> dict:
    """Everything the Instance screen's schedule panel draws. `sessions` is trimmed to
    start and end: entry_delay_s and the outing flags are the tick's business, and the
    timeline only draws the windows."""
    sched = scheduler.read_schedule(name) or {}
    sessions = [
        {"start": s.get("start"), "end": s.get("end")}
        for s in (sched.get("sessions") or [])
        if isinstance(s, dict)
    ]
    return {
        "enabled": scheduler.is_enabled(name),
        "override": scheduler.read_override(name),
        "plan_date": sched.get("plan_date"),
        "sessions": sessions,
        "day_end": sched.get("day_end"),
        "desired": sched.get("desired"),
        "games_played_today": int(sched.get("games_played_today") or 0),
        "now": now.isoformat(timespec="seconds"),
    }


@router.get("/api/instances/{name}/schedule")
async def read_schedule(request: Request, name: str) -> dict:
    """Today's schedule as the last tick left it, plus the switch and the override."""
    inst, _dir = resolve_instance(request, name)
    return schedule_payload(inst.name, datetime.now())


@router.put("/api/instances/{name}/schedule")
async def write_schedule(request: Request, name: str, body: SchedulePatch) -> dict:
    """Flip the switch, redraw today, or cancel the override, then poke the supervisor so
    the next tick happens now instead of up to 60 s later. Returns the GET payload; the
    sessions of a redraw appear once that tick has run."""
    inst, _dir = resolve_instance(request, name)
    sup = get_sup(request)
    if body.enabled is not None:
        scheduler.set_enabled([inst.name], body.enabled)
    if body.redraw:
        scheduler.bump_nonce(inst.name)
    if body.clear_override:
        scheduler.clear_override(inst.name)
    sup.poke()
    return schedule_payload(inst.name, datetime.now())
```

- [ ] **Step 6: Include both routers in `create_app`**

In `brawlfarm/api/app.py`, extend the import to:

```python
from brawlfarm.api import instances, plans, schedule, screens, settings_routes, setup_routes
```

and extend the routers block:

```python
    # --- routers ---------------------------------------------------------------------
    # Included before the static mount below, so /api/* always wins over the SPA.
    app.include_router(instances.router)
    app.include_router(settings_routes.router)
    app.include_router(setup_routes.router)
    app.include_router(screens.router)
    app.include_router(plans.router)
    app.include_router(schedule.router)
```

- [ ] **Step 7: Run the new tests, then the whole suite**

```bash
uv run pytest tests/test_scheduler_reads.py tests/test_api_plan.py tests/test_api_schedule.py -v
uv run pytest -q
```

Expected: 14 new tests PASS; the full suite passes at 485 tests (471 + 14) with no warnings.

- [ ] **Step 8: Lint, scrub, commit**

```bash
uv run ruff format brawlfarm/api brawlfarm/core/scheduler.py tests/test_scheduler_reads.py tests/test_api_plan.py tests/test_api_schedule.py
uv run ruff check --fix brawlfarm/api brawlfarm/core/scheduler.py tests
uv run ruff check . && uv run ruff format --check .
uv run python tools/scrub_check.py
git add brawlfarm/api brawlfarm/core/scheduler.py tests/test_scheduler_reads.py tests/test_api_plan.py tests/test_api_schedule.py
git commit -m "feat(api): farm plan and schedule routes

The Instance screen's right column. core/farmplan.py stores an untyped dict and
validates nothing, so the FarmPlan model is the only gate on what reaches the
worker: four keys, extra=forbid, a blank fallback stored as null. A GET drops
unknown keys instead of failing, because legacy plan files on disk still carry a
queue and a target and the editor has to show something.

scheduler gains read_override() and is_enabled(): the panel could already write
the control file and the override, but had no way to read back the switch it was
about to flip. Both follow the module's existing rules -- default-ON for a
missing entry, pruning an expired override stays the tick's job."
```

---

---

### Task 6: The event bus and `GET /api/events`

Spec section 7's last line: one SSE stream carrying instance state changes, feed lines, alerts
and supervisor log lines. Everything the panel updates from live goes through one bus, so a
publisher never learns who is listening and a slow browser tab can never stall the farm.

**Files:**
- Create: `brawlfarm/api/events.py`
- Modify: `brawlfarm/api/app.py` (the route-module import and `include_router` block from task 1, and the `lifespan` function task 1 wrote with only `started_at` and the first tick)
- Create: `tests/test_api_events.py`

**Interfaces:**
- Consumes: `brawlfarm.api.app.create_app(sup, home) -> FastAPI` and `app.state.sup` (task 1); `brawlfarm.api.instances.view_to_dict(view) -> dict` (task 2); `Supervisor.subscribe(cb: Callable[[InstanceView], None]) -> None` (`brawlfarm/supervisor/loop.py:95`, listeners fire inside `tick()` which `run_forever` runs via `asyncio.to_thread`, i.e. OFF the loop thread); `tests.apihelpers.make_client` (task 1).
- Produces (all in `brawlfarm.api.events`):
  - `@dataclass(frozen=True) class Event: id: int; kind: str; data: dict; ts: str`
  - `class EventBus`: `__init__(self, *, history: int = 500, queue_size: int = 200)`, `attach(self, loop: asyncio.AbstractEventLoop) -> None`, `publish(self, kind: str, data: dict) -> None`, `subscribe(self, last_id: int | None = None) -> AsyncIterator[Event]`, `recent(self, n: int = 50) -> list[Event]`
  - `format_sse(event: Event) -> str`
  - `event_stream(bus: EventBus, request, last_id: int | None = None, keepalive_s: float = KEEPALIVE_S) -> AsyncIterator[str]`
  - `class BusLogHandler(logging.Handler)`: `__init__(self, bus: EventBus, level: int = logging.INFO)`
  - `router = APIRouter()` with `GET /api/events`
  - `app.state.bus: EventBus`
- Consumed by: task 7 (`FeedTailer` publishes kind `feed`), task 8 (`AlertStore` publishes kind `alert`).

- [ ] **Step 1: Write the failing test**

`tests/test_api_events.py`:

```python
"""The event bus and GET /api/events: SSE framing, replay after Last-Event-ID, the
oldest-first drop policy on a slow subscriber, publishing from the supervisor's tick
thread, log lines mirrored onto the bus, and supervisor state changes arriving as
"instance" events. No socket is opened: the stream generator is driven directly with a
fake request whose is_disconnected() flips after N polls."""

from __future__ import annotations

import asyncio
import json
import logging

import pytest

from brawlfarm.api.events import BusLogHandler, Event, EventBus, event_stream, format_sse
from tests.apihelpers import make_client


class FakeRequest:
    """Stands in for a Starlette Request: the stream only ever asks whether the client is
    still there. is_disconnected() returns True after `checks` polls, which is how a test
    ends an otherwise infinite generator."""

    def __init__(self, checks: int) -> None:
        self.checks = checks
        self.seen = 0

    async def is_disconnected(self) -> bool:
        self.seen += 1
        return self.seen > self.checks


def test_format_sse_frames_id_kind_and_json() -> None:
    frame = format_sse(Event(id=7, kind="alert", data={"title": "Bot crashed"}, ts="t"))
    assert frame == 'id: 7\nevent: alert\ndata: {"title": "Bot crashed"}\n\n'


def test_format_sse_survives_a_value_json_cannot_encode() -> None:
    frame = format_sse(Event(id=1, kind="log", data={"when": object()}, ts="t"))
    assert frame.startswith("id: 1\nevent: log\ndata: {")
    assert json.loads(frame.split("data: ", 1)[1].strip())["when"].startswith("<object")


def test_publish_numbers_events_and_keeps_history() -> None:
    bus = EventBus(history=3)
    for n in range(5):
        bus.publish("log", {"n": n})
    assert [e.id for e in bus.recent()] == [3, 4, 5]
    assert [e.data["n"] for e in bus.recent(2)] == [3, 4]
    assert bus.recent()[0].ts  # stamped on publish


@pytest.mark.asyncio
async def test_subscribe_replays_history_after_last_id() -> None:
    bus = EventBus()
    bus.publish("instance", {"name": "alpha"})
    bus.publish("instance", {"name": "bravo"})
    subscription = bus.subscribe(last_id=1)
    replayed = await anext(subscription)
    await subscription.aclose()
    assert replayed.id == 2 and replayed.data == {"name": "bravo"}


@pytest.mark.asyncio
async def test_a_full_queue_drops_the_oldest_event_for_that_subscriber() -> None:
    bus = EventBus(queue_size=3)
    subscription = bus.subscribe()
    for n in range(5):
        bus.publish("log", {"n": n})
    kept = [(await anext(subscription)).data["n"] for _ in range(3)]
    await subscription.aclose()
    assert kept == [2, 3, 4]


@pytest.mark.asyncio
async def test_publish_from_a_worker_thread_reaches_the_loop() -> None:
    bus = EventBus()
    bus.attach(asyncio.get_running_loop())
    await asyncio.to_thread(bus.publish, "instance", {"name": "alpha"})
    await asyncio.sleep(0)  # let the scheduled call_soon_threadsafe run
    assert [e.kind for e in bus.recent()] == ["instance"]


@pytest.mark.asyncio
async def test_stream_keepalives_when_idle_then_stops_on_disconnect() -> None:
    bus = EventBus()
    request = FakeRequest(checks=3)
    stream = event_stream(bus, request, keepalive_s=0.02)
    assert await anext(stream) == ": keepalive\n\n"
    bus.publish("alert", {"id": 1})
    assert await anext(stream) == 'id: 1\nevent: alert\ndata: {"id": 1}\n\n'
    bus.publish("feed", {"instance": "alpha"})
    assert (await anext(stream)).startswith("id: 2\nevent: feed\n")
    with pytest.raises(StopAsyncIteration):
        await anext(stream)
    assert bus.subscriber_count() == 0  # the subscription is released on disconnect


@pytest.mark.asyncio
async def test_stream_replays_from_the_last_event_id() -> None:
    bus = EventBus()
    bus.publish("log", {"message": "one"})
    bus.publish("log", {"message": "two"})
    stream = event_stream(bus, FakeRequest(checks=1), last_id=1, keepalive_s=0.02)
    assert await anext(stream) == 'id: 2\nevent: log\ndata: {"message": "two"}\n\n'
    await stream.aclose()


def test_bus_log_handler_publishes_log_events() -> None:
    bus = EventBus()
    log = logging.getLogger("brawlfarm.test-bus")
    log.setLevel(logging.INFO)
    handler = BusLogHandler(bus)
    log.addHandler(handler)
    try:
        log.info("tick: %s", "alpha=farming")
        log.debug("too quiet for the panel")
    finally:
        log.removeHandler(handler)
    assert [e.kind for e in bus.recent()] == ["log"]
    data = bus.recent()[0].data
    assert data["level"] == "INFO"
    assert data["logger"] == "brawlfarm.test-bus"
    assert data["message"] == "tick: alpha=farming"
    assert data["ts"]


def test_the_events_route_is_registered(tmp_path) -> None:
    with make_client(tmp_path, ("alpha",)) as (client, _sup, _home):
        assert "/api/events" in {getattr(r, "path", "") for r in client.app.routes}


def test_supervisor_state_changes_arrive_as_instance_events(tmp_path) -> None:
    with make_client(tmp_path, ("alpha",)) as (client, _sup, _home):
        client.get("/api/health")  # one request turns the loop, so the queued publish lands
        bus = client.app.state.bus
        instance = next(e for e in bus.recent(500) if e.kind == "instance")
        assert instance.data["name"] == "alpha"
        assert instance.data["state"]
        assert instance.data["adb_port"] == 5555
```

- [ ] **Step 2: Run it to confirm it fails**

```bash
uv run pytest tests/test_api_events.py -v
```

Expected: collection fails with `ModuleNotFoundError: No module named 'brawlfarm.api.events'`.

- [ ] **Step 3: Write `brawlfarm/api/events.py`**

```python
"""The in-process event bus and the SSE stream behind GET /api/events (spec section 7).

Everything the panel updates from live goes through one bus: supervisor state changes
(kind "instance"), session narration lines (kind "feed", task 7), alerts (kind "alert",
task 8) and the supervisor's own log lines (kind "log"). Publishers may be on any thread
— the supervisor's tick runs in a worker thread, so its listeners do too — so publish()
hops back onto the event loop with call_soon_threadsafe. Every subscriber gets its own
bounded queue: a browser tab that stops reading loses its oldest events instead of
stalling the farm.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import deque
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

router = APIRouter()

KEEPALIVE_S = 15.0  # an idle stream still writes a comment frame this often


@dataclass(frozen=True)
class Event:
    """One thing that happened, as the stream sends it. `id` is monotonic per process so a
    reconnecting browser can ask for everything after the last one it saw."""

    id: int
    kind: str
    data: dict
    ts: str


def _running_loop() -> asyncio.AbstractEventLoop | None:
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        return None


class EventBus:
    def __init__(self, *, history: int = 500, queue_size: int = 200) -> None:
        self._history: deque[Event] = deque(maxlen=history)
        self._queue_size = queue_size
        self._subscribers: list[asyncio.Queue[Event]] = []
        self._loop: asyncio.AbstractEventLoop | None = None
        self._next_id = 1

    def attach(self, loop: asyncio.AbstractEventLoop) -> None:
        """Remember the loop the app runs on; publishers on other threads hand their events
        to it. Called once from the lifespan."""
        self._loop = loop

    def publish(self, kind: str, data: dict) -> None:
        """Thread-safe. Never logs anything: BusLogHandler publishes INTO this bus, so a log
        call here would recurse."""
        loop = self._loop
        if loop is not None and loop is not _running_loop():
            loop.call_soon_threadsafe(self._push, kind, data)
            return
        self._push(kind, data)

    def _push(self, kind: str, data: dict) -> None:
        """Always runs on the loop thread, so the id counter and the queues need no lock."""
        event = Event(
            id=self._next_id,
            kind=kind,
            data=data,
            ts=datetime.now().isoformat(timespec="seconds"),
        )
        self._next_id += 1
        self._history.append(event)
        for queue in self._subscribers:
            if queue.full():
                # Drop this subscriber's oldest event rather than blocking the publisher:
                # a stalled tab must never slow the supervisor down.
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

    def subscribe(self, last_id: int | None = None) -> AsyncIterator[Event]:
        """History after `last_id` (if given), then live events. NOT an async generator on
        purpose: a generator body does not run until its first __anext__, and every event
        published in that window would be lost. Registering the queue here closes the gap.
        The caller must iterate the result (the SSE route always does) — the queue is
        released in the iterator's finally block."""
        queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=self._queue_size)
        self._subscribers.append(queue)
        replay = [e for e in self._history if e.id > last_id] if last_id is not None else []
        return self._iterate(queue, replay)

    async def _iterate(
        self, queue: asyncio.Queue[Event], replay: list[Event]
    ) -> AsyncIterator[Event]:
        try:
            for event in replay:
                yield event
            while True:
                yield await queue.get()
        finally:
            self._subscribers.remove(queue)

    def recent(self, n: int = 50) -> list[Event]:
        """The newest `n` events, oldest first."""
        return list(self._history)[-n:]

    def subscriber_count(self) -> int:
        """Open streams; the tests assert a disconnect actually releases the queue."""
        return len(self._subscribers)


def format_sse(event: Event) -> str:
    """One SSE frame. default=str so an odd value in a payload degrades to its repr instead
    of breaking the whole stream."""
    payload = json.dumps(event.data, ensure_ascii=False, default=str)
    return f"id: {event.id}\nevent: {event.kind}\ndata: {payload}\n\n"


class BusLogHandler(logging.Handler):
    """Mirrors the `brawlfarm` logger onto the bus as kind "log" so the panel can show what
    the supervisor is doing. Attached in the lifespan, removed on shutdown."""

    def __init__(self, bus: EventBus, level: int = logging.INFO) -> None:
        super().__init__(level)
        self._bus = bus

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._bus.publish(
                "log",
                {
                    "ts": datetime.fromtimestamp(record.created).isoformat(timespec="seconds"),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                },
            )
        except Exception:  # a bad format string must never take the process down
            pass


async def event_stream(
    bus: EventBus,
    request,
    last_id: int | None = None,
    keepalive_s: float = KEEPALIVE_S,
) -> AsyncIterator[str]:
    """The SSE body: replay after `last_id`, then live events, with a comment frame every
    `keepalive_s` while idle so proxies keep the connection and a dead client is noticed.

    The pending __anext__ is kept across a timeout instead of being cancelled: cancelling
    it would close the async generator (its finally runs and the next __anext__ raises
    StopAsyncIteration), which would end the stream at the first keepalive.
    """
    subscription = bus.subscribe(last_id)
    pending: asyncio.Task[Event] | None = None
    try:
        while not await request.is_disconnected():
            if pending is None:
                pending = asyncio.ensure_future(anext(subscription))
            done, _ = await asyncio.wait({pending}, timeout=keepalive_s)
            if not done:
                yield ": keepalive\n\n"
                continue
            try:
                event = pending.result()
            except StopAsyncIteration:
                return
            finally:
                pending = None
            yield format_sse(event)
    finally:
        if pending is not None:
            pending.cancel()
        await subscription.aclose()


def _parse_last_id(header: str | None) -> int | None:
    """The browser's Last-Event-ID on a reconnect. Junk is ignored (start from live)."""
    try:
        return int(header) if header else None
    except (TypeError, ValueError):
        return None


@router.get("/api/events")
async def get_events(request: Request) -> StreamingResponse:
    """Server-sent events: instance state changes, feed lines, alerts and supervisor log
    lines. Send Last-Event-ID to resume; the bus keeps the newest 500 events."""
    bus: EventBus = request.app.state.bus
    last_id = _parse_last_id(request.headers.get("Last-Event-ID"))
    return StreamingResponse(
        event_stream(bus, request, last_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

- [ ] **Step 4: Wire the bus into `brawlfarm/api/app.py`**

Add `events` to the route-module import task 1 wrote and include its router with the others
(order among the API routers does not matter; they all stay before the static mount so
`/api/*` wins):

```python
from brawlfarm.api import events, instances, plans, schedule, screens, settings_routes, setup_routes
```

```python
    app.include_router(events.router)
```

Then replace the whole `lifespan` function (task 1 wrote it with only `started_at` and the
first tick) with:

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup: attach the bus to this loop, mirror the brawlfarm logger onto it, publish
    every supervisor state change, and run one tick so the first GET /api/instances already
    has views. Shutdown: detach the log handler so a second app in the same process (the
    test suite makes many) does not publish into a dead bus."""
    app.state.started_at = time.monotonic()
    bus = EventBus()
    bus.attach(asyncio.get_running_loop())
    app.state.bus = bus
    # tick() runs in a worker thread, so this callback fires OFF the loop thread;
    # EventBus.publish hops back with call_soon_threadsafe.
    app.state.sup.subscribe(lambda view: bus.publish("instance", view_to_dict(view)))
    handler = BusLogHandler(bus)
    logging.getLogger("brawlfarm").addHandler(handler)
    try:
        try:
            await asyncio.to_thread(app.state.sup.tick)
        except Exception:  # a failed startup tick must not stop the app from serving
            log.exception("startup tick failed")
        yield
    finally:
        logging.getLogger("brawlfarm").removeHandler(handler)
```

with these imports added at the top of `app.py` (keep whatever task 1 already imports):

```python
import asyncio
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from brawlfarm.api.events import BusLogHandler, EventBus
from brawlfarm.api.instances import view_to_dict
```

- [ ] **Step 5: Run the tests**

```bash
uv run pytest tests/test_api_events.py -v
uv run pytest -q
```

Expected: 11 passed in `tests/test_api_events.py`, and the whole suite green with no warnings.

- [ ] **Step 6: Lint, scrub, commit**

```bash
uv run ruff format brawlfarm/api/events.py brawlfarm/api/app.py tests/test_api_events.py
uv run ruff check . && uv run ruff format --check .
uv run python tools/scrub_check.py
git add brawlfarm/api/events.py brawlfarm/api/app.py tests/test_api_events.py
git commit -m "feat(api): one event bus behind GET /api/events

Instance state changes, alerts, feed lines and supervisor log lines share
a single SSE stream, so the panel needs one connection and no polling.
publish() is thread-safe because the supervisor's listeners fire from the
tick thread, and a subscriber that stops reading loses its oldest events
rather than blocking the farm."
```

---

### Task 7: The activity feed and its tailer

Spec section 7: `GET /api/instances/{name}/feed?kind=all|matches|interrupts|errors&limit=N` over
the session narration JSONL, plus the live half — a tailer that turns new lines into `feed`
events on the bus so the Instance screen's feed scrolls without polling.

**Files:**
- Create: `brawlfarm/api/feed.py`
- Modify: `brawlfarm/api/app.py` (the import and `include_router` block, and the `lifespan` function task 6 left)
- Create: `tests/test_api_feed.py`

**Interfaces:**
- Consumes: `brawlfarm.api.deps.resolve_instance(request, name) -> (InstanceSettings, Path)` (task 1); `brawlfarm.api.events.EventBus.publish` (task 6); `settings.instance_dir(home, name)`; the session file contract in `brawlfarm/core/datalog.py` (`session-<YYYYmmdd-HHMMSS>.jsonl`, datalog.py:115-116; one JSON object per line, `{"ts": ..., "kind": <etype>, **fields}`, datalog.py:188-206); `tests.apihelpers.build_settings`, `make_client` (task 1).
- Produces (all in `brawlfarm.api.feed`):
  - `MATCHES`, `INTERRUPTS`, `ERRORS`, `DROP` (frozensets), `KINDS = ("all", "matches", "interrupts", "errors")`, `FeedKind = Literal["all", "matches", "interrupts", "errors"]`
  - `classify(kind: str) -> str | None`
  - `to_record(line: dict) -> dict | None`
  - `latest_session(inst_dir: Path) -> Path | None`
  - `read_session(path: Path, *, kind: str = "all", limit: int = 100) -> list[dict]`
  - `read_feed(inst_dir: Path, kind: str = "all", limit: int = 100) -> list[dict]`
  - `class FeedTailer`: `__init__(self, home, sup, bus, alerts=None, interval_s: float = 2.0)`, `async run(self) -> None`, `async poll_once(self) -> int`
  - `router = APIRouter()` with `GET /api/instances/{name}/feed`
  - `app.state.tailer: FeedTailer`
- Consumed by: task 8 (`FeedTailer(..., alerts=AlertStore(...))`).

- [ ] **Step 1: Write the failing test**

`tests/test_api_feed.py`:

```python
"""The activity feed: which session event kinds land in which chip, reading the newest
session file for GET .../feed, and the tailer that publishes new lines onto the bus —
starting at the end of a session already in progress, following a session roll, and
waiting for a half-written line to finish."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from brawlfarm import settings as S
from brawlfarm.api.events import EventBus
from brawlfarm.api.feed import FeedTailer, classify, latest_session, read_feed
from tests.apihelpers import build_settings, make_client


class StubSup:
    """The tailer only reads sup.settings.instances; a stub keeps this test off the real
    supervisor (make_client's app already runs a tailer of its own)."""

    def __init__(self, settings) -> None:
        self.settings = settings


class StubAlerts:
    def __init__(self) -> None:
        self.seen: list[tuple[str, str]] = []

    def ingest(self, instance: str, record: dict):
        self.seen.append((instance, record.get("kind", "")))
        return None


def _append(path: Path, kind: str, **fields) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": "2026-09-10T18:00:00", "kind": kind, **fields}) + "\n")


def test_classify_sorts_every_kind_into_a_chip() -> None:
    assert classify("phase") == "matches"
    assert classify("games_logged") == "matches"
    assert classify("recap") == "matches"
    assert classify("select_brawler") == "matches"
    assert classify("disconnect") == "interrupts"
    assert classify("daily_streak_claim") == "interrupts"
    assert classify("recover") == "interrupts"
    assert classify("crash") == "errors"
    assert classify("bad_resolution") == "errors"
    assert classify("recalibrate") == "errors"
    assert classify("select_brawler_error") == "errors"  # _error wins over the matches set
    assert classify("adb_error") == "errors"
    assert classify("mega_quest") == "other"  # visible under All only
    assert classify("tap") is None  # one per tap: noise
    assert classify("gas_edges") is None


def test_read_feed_reads_the_newest_session_newest_last(tmp_path: Path) -> None:
    old = tmp_path / "session-20260910-100000.jsonl"
    new = tmp_path / "session-20260910-120000.jsonl"
    _append(old, "start", max_minutes=90)
    _append(new, "start", max_minutes=90)
    _append(new, "tap", button="play", x=1, y=2)
    with new.open("a", encoding="utf-8") as f:
        f.write("not json at all\n")  # a torn line must not empty the screen
    _append(new, "crash", err="adb gone")
    _append(new, "phase", to="queuing", frm="menu", games=0)
    assert latest_session(tmp_path) == new
    records = read_feed(tmp_path)
    assert [r["event"] for r in records] == ["start", "crash", "phase"]
    assert records[-1] == {
        "ts": "2026-09-10T18:00:00",
        "event": "phase",
        "category": "matches",
        "fields": {"to": "queuing", "frm": "menu", "games": 0},
    }
    assert [r["event"] for r in read_feed(tmp_path, "errors")] == ["crash"]
    assert [r["event"] for r in read_feed(tmp_path, "matches", limit=1)] == ["phase"]


def test_read_feed_is_empty_without_a_session(tmp_path: Path) -> None:
    assert latest_session(tmp_path) is None
    assert read_feed(tmp_path) == []


def test_feed_route_returns_the_session_name_and_records(tmp_path: Path) -> None:
    with make_client(tmp_path, ("alpha",)) as (client, _sup, home):
        session = S.instance_dir(home, "alpha") / "session-20260910-120000.jsonl"
        _append(session, "crash", err="adb gone")
        _append(session, "phase", to="queuing", frm="menu", games=0)
        body = client.get("/api/instances/alpha/feed").json()
        assert body["session"] == "session-20260910-120000.jsonl"
        assert [r["event"] for r in body["records"]] == ["crash", "phase"]
        assert client.get("/api/instances/alpha/feed?kind=errors").json()["records"][0][
            "event"
        ] == "crash"
        assert client.get("/api/instances/alpha/feed?kind=nope").status_code == 422
        assert client.get("/api/instances/alpha/feed?limit=0").status_code == 422
        assert client.get("/api/instances/ghost/feed").status_code == 404


def test_feed_route_without_a_session_says_so(tmp_path: Path) -> None:
    with make_client(tmp_path, ("alpha",)) as (client, _sup, _home):
        assert client.get("/api/instances/alpha/feed").json() == {"session": None, "records": []}


@pytest.mark.asyncio
async def test_tailer_skips_history_then_publishes_new_lines(tmp_path: Path) -> None:
    inst_dir = S.instance_dir(tmp_path, "alpha")
    session = inst_dir / "session-20260910-100000.jsonl"
    _append(session, "start", max_minutes=90)
    _append(session, "phase", to="queuing", frm="menu", games=0)
    bus, alerts = EventBus(), StubAlerts()
    tailer = FeedTailer(tmp_path, StubSup(build_settings(("alpha",))), bus, alerts=alerts)

    assert await tailer.poll_once() == 0  # ruling 4: start at the end of a live session
    assert bus.recent() == []

    _append(session, "crash", err="adb gone")
    _append(session, "tap", button="play", x=1, y=2)
    _append(session, "recover", reason="stuck", attempt=1)
    assert await tailer.poll_once() == 2  # tap is dropped
    published = [(e.kind, e.data["record"]["event"]) for e in bus.recent()]
    assert published == [("feed", "crash"), ("feed", "recover")]
    assert bus.recent()[0].data["instance"] == "alpha"
    assert alerts.seen == [("alpha", "crash"), ("alpha", "tap"), ("alpha", "recover")]


@pytest.mark.asyncio
async def test_tailer_follows_a_session_roll_from_the_top(tmp_path: Path) -> None:
    inst_dir = S.instance_dir(tmp_path, "alpha")
    _append(inst_dir / "session-20260910-100000.jsonl", "start", max_minutes=90)
    bus = EventBus()
    tailer = FeedTailer(tmp_path, StubSup(build_settings(("alpha",))), bus)
    await tailer.poll_once()
    _append(inst_dir / "session-20260910-120000.jsonl", "start", max_minutes=90)
    assert await tailer.poll_once() == 1
    assert bus.recent()[-1].data["record"]["event"] == "start"


@pytest.mark.asyncio
async def test_tailer_waits_for_a_half_written_line(tmp_path: Path) -> None:
    inst_dir = S.instance_dir(tmp_path, "alpha")
    inst_dir.mkdir(parents=True, exist_ok=True)
    session = inst_dir / "session-20260910-100000.jsonl"
    session.write_text("", encoding="utf-8")
    bus = EventBus()
    tailer = FeedTailer(tmp_path, StubSup(build_settings(("alpha",))), bus)
    await tailer.poll_once()
    with session.open("a", encoding="utf-8") as f:
        f.write('{"ts": "2026-09-10T18:05:00", "kind": "rec')
    assert await tailer.poll_once() == 0
    with session.open("a", encoding="utf-8") as f:
        f.write('ap", "trophies": 120, "games": 4, "skins": 0}\n')
    assert await tailer.poll_once() == 1
    record = bus.recent()[-1].data["record"]
    assert record["event"] == "recap" and record["fields"]["trophies"] == 120


@pytest.mark.asyncio
async def test_tailer_survives_an_instance_with_no_folder(tmp_path: Path) -> None:
    bus = EventBus()
    tailer = FeedTailer(tmp_path, StubSup(build_settings(("alpha", "bravo"))), bus)
    assert await tailer.poll_once() == 0
    assert await tailer.poll_once() == 0


def test_the_app_runs_a_tailer(tmp_path: Path) -> None:
    with make_client(tmp_path, ("alpha",)) as (client, _sup, _home):
        assert isinstance(client.app.state.tailer, FeedTailer)
        assert client.app.state.tailer.interval_s == 2.0
```

- [ ] **Step 2: Run it to confirm it fails**

```bash
uv run pytest tests/test_api_feed.py -v
```

Expected: collection fails with `ModuleNotFoundError: No module named 'brawlfarm.api.feed'`.

- [ ] **Step 3: Write `brawlfarm/api/feed.py`**

```python
"""The activity feed: the worker's session narration turned into something a screen can
show (spec section 7, Instance screen).

The worker appends one JSON object per line to `<instance dir>/session-<ts>.jsonl`
(core/datalog.py): `{"ts": ..., "kind": <event kind>, **fields}`. Two readers live here.
`read_feed` serves history on demand for GET .../feed; `FeedTailer` follows the newest
file and publishes each new line onto the event bus, so the panel's feed scrolls without
polling. Both drop `tap` (one line per tap) and label everything else with the chip it
belongs under: All, Matches, Interrupts, Errors.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Query, Request

from brawlfarm import settings as S
from brawlfarm.api.deps import resolve_instance

log = logging.getLogger("brawlfarm.api")
router = APIRouter()

# Kinds are the etypes core/controller.py passes to DataLog.event(); see that file for the
# full inventory. Anything unlisted is "other" and shows under All only, so a new event
# kind in the core is never silently invisible.
MATCHES = frozenset(
    {"phase", "games_logged", "recap", "trophies", "farming", "select_brawler", "rotate_brawler"}
)
INTERRUPTS = frozenset(
    {
        "disconnect",
        "popup_close",
        "team_invite_decline",
        "daily_streak_claim",
        "ceremony_cleared",
        "recover",
        "recover_dismissed",
        "game_left_foreground",
        "wrong_mode",
        "reselect_brawler",
        "gas_relocate",
        "bush_hide",
        "ingame_modal_cleared",
        "skin_reward",
    }
)
ERRORS = frozenset({"crash", "bad_resolution", "recalibrate"})
DROP = frozenset({"tap", "gas_edges"})  # per-tap noise, never worth a feed line

KINDS = ("all", "matches", "interrupts", "errors")
FeedKind = Literal["all", "matches", "interrupts", "errors"]

MAX_LIMIT = 1000
TAIL_INTERVAL_S = 2.0


def classify(kind: str) -> str | None:
    """The chip a session event belongs under, or None when it is dropped. `_error` is
    checked first so select_brawler_error lands in Errors, not Matches."""
    if kind in DROP:
        return None
    if kind.endswith("_error") or kind in ERRORS:
        return "errors"
    if kind in MATCHES:
        return "matches"
    if kind in INTERRUPTS:
        return "interrupts"
    return "other"


def to_record(line: dict) -> dict | None:
    """One session line as a feed record, or None when the kind is dropped. `kind` is
    renamed to `event` because the screen's filter is also called kind."""
    kind = str(line.get("kind") or "")
    if not kind:
        return None
    category = classify(kind)
    if category is None:
        return None
    fields = {k: v for k, v in line.items() if k not in ("ts", "kind")}
    return {"ts": str(line.get("ts") or ""), "event": kind, "category": category, "fields": fields}


def latest_session(inst_dir: Path) -> Path | None:
    """The newest session-<ts>.jsonl. The worker's timestamp is %Y%m%d-%H%M%S, so the name
    sorts chronologically and no stat() call is needed."""
    try:
        files = sorted(Path(inst_dir).glob("session-*.jsonl"))
    except OSError:
        return None
    return files[-1] if files else None


def read_session(path: Path, *, kind: str = "all", limit: int = 100) -> list[dict]:
    """Feed records from one session file, newest last, at most `limit` of them.
    Unparsable lines are skipped: a half-written tail must not empty the screen."""
    if kind not in KINDS:
        raise ValueError(f"unknown feed kind {kind!r}")
    limit = max(1, min(int(limit), MAX_LIMIT))
    records: list[dict] = []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for raw in f:
                try:
                    line = json.loads(raw)
                except ValueError:
                    continue
                if not isinstance(line, dict):
                    continue
                record = to_record(line)
                if record is None or (kind != "all" and record["category"] != kind):
                    continue
                records.append(record)
    except OSError as exc:
        log.debug("cannot read %s: %s", path, exc)
        return []
    return records[-limit:]


def read_feed(inst_dir: Path, kind: str = "all", limit: int = 100) -> list[dict]:
    """The newest session's feed records. Only the newest file is read: the screen shows
    "this session", and older files are for the stats page."""
    path = latest_session(Path(inst_dir))
    return [] if path is None else read_session(path, kind=kind, limit=limit)


def _feed_payload(inst_dir: Path, kind: str, limit: int) -> dict:
    """Name and records resolved from one lookup, so a session roll between them cannot
    label one file's records with another file's name. Blocking; call it in a thread."""
    path = latest_session(inst_dir)
    return {
        "session": path.name if path is not None else None,
        "records": [] if path is None else read_session(path, kind=kind, limit=limit),
    }


class FeedTailer:
    """Follows every instance's newest session file and publishes new lines onto the bus as
    kind "feed" (`{"instance": name, "record": <feed record>}`).

    On its first look at an instance it seeks to the END of the session already in progress
    (ruling 4): a supervisor restart must not replay a whole night onto the panel, and
    GET .../feed still serves that history on demand. A file that appears or rolls later is
    read from the top. Every parsed line — dropped kinds included — is offered to the alert
    store, because `tap` is noise on a screen but `crash` is not.
    """

    def __init__(self, home, sup, bus, alerts=None, interval_s: float = TAIL_INTERVAL_S) -> None:
        self.home = Path(home)
        self.interval_s = interval_s
        self._sup = sup
        self._bus = bus
        self._alerts = alerts
        self._positions: dict[str, tuple[Path, int]] = {}
        self._seen: set[str] = set()

    async def run(self) -> None:
        """Poll until cancelled (the lifespan cancels it on shutdown)."""
        while True:
            await self.poll_once()
            await asyncio.sleep(self.interval_s)

    async def poll_once(self) -> int:
        """One pass over every configured instance; returns how many feed events it
        published. The tests call this instead of run(). File reads happen in a thread; the
        publishing happens here on the loop thread."""
        published = 0
        for inst in self._sup.settings.instances:
            name = inst.name
            try:
                lines = await asyncio.to_thread(self._read_new, name)
            except Exception:  # one unreadable folder must never kill the tailer
                log.exception("%s: feed tail failed", name)
                continue
            for line in lines:
                if self._alerts is not None:
                    self._alerts.ingest(name, line)
                record = to_record(line)
                if record is None:
                    continue
                self._bus.publish("feed", {"instance": name, "record": record})
                published += 1
        return published

    def _read_new(self, name: str) -> list[dict]:
        """Blocking: the session lines written since the last poll. Offsets are counted in
        bytes on a binary handle because text-mode tell() is not allowed while iterating."""
        inst_dir = S.instance_dir(self.home, name)
        path = latest_session(inst_dir)
        first_look = name not in self._seen
        self._seen.add(name)
        if path is None:
            self._positions.pop(name, None)
            return []
        known, offset = self._positions.get(name, (None, 0))
        if known != path:
            offset = path.stat().st_size if first_look else 0
        lines: list[dict] = []
        try:
            with path.open("rb") as f:
                f.seek(0, 2)
                if f.tell() < offset:  # replaced or truncated under us
                    offset = 0
                f.seek(offset)
                for raw in f:
                    if not raw.endswith(b"\n"):
                        break  # a half-written line; the next poll picks it up whole
                    offset += len(raw)
                    try:
                        line = json.loads(raw.decode("utf-8"))
                    except (ValueError, UnicodeDecodeError):
                        continue
                    if isinstance(line, dict):
                        lines.append(line)
        except OSError as exc:
            log.debug("%s: cannot read %s: %s", name, path.name, exc)
            return []
        self._positions[name] = (path, offset)
        return lines


@router.get("/api/instances/{name}/feed")
async def get_feed(
    request: Request,
    name: str,
    kind: FeedKind = "all",
    limit: int = Query(100, ge=1, le=MAX_LIMIT),
) -> dict:
    """This instance's newest session narration, newest last. An unknown kind or a limit
    outside 1..1000 is a 422; an unknown instance is a 404."""
    _inst, inst_dir = resolve_instance(request, name)
    return await asyncio.to_thread(_feed_payload, inst_dir, kind, limit)
```

- [ ] **Step 4: Start the tailer in `brawlfarm/api/app.py`**

Add `feed` to the route-module import and include its router next to the others:

```python
from brawlfarm.api import (
    events,
    feed,
    instances,
    plans,
    schedule,
    screens,
    settings_routes,
    setup_routes,
)
```

```python
    app.include_router(feed.router)
```

Then replace the whole `lifespan` function (task 6's version) with:

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup: attach the bus to this loop, mirror the brawlfarm logger onto it, publish
    every supervisor state change, start the feed tailer, and run one tick so the first
    GET /api/instances already has views. Shutdown: stop the tailer and detach the log
    handler so a second app in the same process does not publish into a dead bus."""
    app.state.started_at = time.monotonic()
    bus = EventBus()
    bus.attach(asyncio.get_running_loop())
    app.state.bus = bus
    # tick() runs in a worker thread, so this callback fires OFF the loop thread;
    # EventBus.publish hops back with call_soon_threadsafe.
    app.state.sup.subscribe(lambda view: bus.publish("instance", view_to_dict(view)))
    handler = BusLogHandler(bus)
    logging.getLogger("brawlfarm").addHandler(handler)
    tailer = FeedTailer(app.state.home, app.state.sup, bus)
    app.state.tailer = tailer
    tailing = asyncio.create_task(tailer.run())
    try:
        try:
            await asyncio.to_thread(app.state.sup.tick)
        except Exception:  # a failed startup tick must not stop the app from serving
            log.exception("startup tick failed")
        yield
    finally:
        tailing.cancel()
        with suppress(asyncio.CancelledError):
            await tailing
        logging.getLogger("brawlfarm").removeHandler(handler)
```

with these imports added at the top of `app.py`:

```python
from contextlib import asynccontextmanager, suppress

from brawlfarm.api.feed import FeedTailer
```

- [ ] **Step 5: Run the tests**

```bash
uv run pytest tests/test_api_feed.py -v
uv run pytest -q
```

Expected: 10 passed in `tests/test_api_feed.py`, whole suite green.

- [ ] **Step 6: Lint, scrub, commit**

```bash
uv run ruff format brawlfarm/api/feed.py brawlfarm/api/app.py tests/test_api_feed.py
uv run ruff check . && uv run ruff format --check .
uv run python tools/scrub_check.py
git add brawlfarm/api/feed.py brawlfarm/api/app.py tests/test_api_feed.py
git commit -m "feat(api): activity feed route and live tailer

The Instance screen reads the worker's session narration through
GET .../feed and follows it live through the bus, so a disconnect or a
crash shows up within two seconds without polling. The tailer starts at
the end of a session already in progress: a supervisor restart must not
replay a whole night onto the panel."
```

---
### Task 8: Alerts, the offline hook and the healthchecks ping

Spec section 7: `GET /api/alerts`, `POST /api/alerts/{id}/dismiss`, and alerts drawn from the
worker's existing alert kinds. The push notifier already turns those kinds into a phone buzz;
this task gives the panel the same events as a list it can show and dismiss. It also closes the
phase 2 deferral recorded in `docs/PLAN.md`: `notifications.healthchecks_url` was modelled but
never pinged.

**Files:**
- Create: `brawlfarm/api/alerts.py`
- Modify: `brawlfarm/core/notify.py` (`_TITLES` at lines 56 to 64, `configure` at 77 to 96, `maybe_alert`'s title lookup at 200 to 221)
- Modify: `brawlfarm/supervisor/loop.py` (`__init__` at 45 to 72, `apply_settings` at 76 to 90, the end of `tick()` at 134 to 135, the offline alert site at 171 to 177)
- Modify: `brawlfarm/api/app.py` (the import and `include_router` block, and the `lifespan` function task 7 left)
- Modify: `tests/conftest.py` (the env prefix tuple in `_isolated_home`)
- Modify: `tests/test_notify_config.py` (append four tests)
- Modify: `tests/test_supervisor_loop.py` (`World` at lines 30 to 71, `make_sup` at 85 to 102, append two tests)
- Create: `tests/test_api_alerts.py`

**Interfaces:**
- Consumes: `notify.ALERT_KINDS` (notify.py:37-45, seven kinds including `stop`), `notify._TITLES` (56-64); `EventBus.publish` (task 6); `FeedTailer(home, sup, bus, alerts=...)` (task 7); `Supervisor` (loop.py); `tests.apihelpers.make_client` (task 1).
- Produces:
  - `brawlfarm.api.alerts`: `@dataclass class Alert: id: int; ts: str; instance: str; kind: str; title: str; detail: str; dismissed: bool = False`; `class AlertStore` with `__init__(self, bus: EventBus | None = None, *, maxlen: int = 200)`, `add(self, instance: str, kind: str, fields: dict, ts: str | None = None) -> Alert`, `ingest(self, instance: str, record: dict) -> Alert | None`, `list(self, *, include_dismissed: bool = False) -> list[Alert]`, `dismiss(self, alert_id: int) -> bool`, `unread_count(self) -> int`; `router = APIRouter()` with `GET /api/alerts` and `POST /api/alerts/{alert_id}/dismiss`; `app.state.alerts: AlertStore`
  - `brawlfarm.core.notify`: `alert_title(kind: str) -> str`, `healthchecks_url() -> str`, `ping_healthchecks(*, getter=None) -> bool`, and `configure(..., healthchecks_url: str | None = None)`
  - `brawlfarm.supervisor.loop.Supervisor`: `subscribe_alerts(cb: Callable[[str, str, dict], None]) -> None` and the constructor keyword `pinger: Callable[[], bool] = notify.ping_healthchecks`

- [ ] **Step 1: Write the failing tests**

`tests/test_api_alerts.py`:

```python
"""Alerts: the worker's alert-worthy session events kept in memory for the Fleet drawer,
published on the bus as they arrive, listed newest first and dismissed one at a time."""

from __future__ import annotations

from pathlib import Path

from brawlfarm.api.alerts import Alert, AlertStore
from brawlfarm.api.events import EventBus
from tests.apihelpers import make_client


def test_add_titles_the_kind_and_joins_the_detail() -> None:
    bus = EventBus()
    store = AlertStore(bus)
    alert = store.add("alpha", "crash", {"err": "adb gone", "streak": 3, "note": None})
    assert alert == Alert(
        id=1,
        ts=alert.ts,
        instance="alpha",
        kind="crash",
        title="Bot crashed",
        detail="err=adb gone, streak=3",
        dismissed=False,
    )
    assert [(e.kind, e.data["title"]) for e in bus.recent()] == [("alert", "Bot crashed")]


def test_ingest_only_reacts_to_alert_kinds() -> None:
    store = AlertStore()
    assert store.ingest("alpha", {"ts": "2026-09-10T18:00:00", "kind": "tap", "x": 1}) is None
    assert store.ingest("alpha", {"ts": "2026-09-10T18:00:00", "kind": "phase"}) is None
    # a graceful stop pushes a notification (notify.ALERT_KINDS) but is not a panel alert
    assert store.ingest("alpha", {"ts": "2026-09-10T18:00:00", "kind": "stop", "games": 2}) is None
    alert = store.ingest(
        "alpha", {"ts": "2026-09-10T18:00:00", "kind": "recover", "reason": "stuck", "attempt": 1}
    )
    assert alert is not None
    assert alert.ts == "2026-09-10T18:00:00"
    assert alert.title == "Bot recovering"
    assert alert.detail == "reason=stuck, attempt=1"


def test_list_is_newest_first_and_hides_dismissed() -> None:
    store = AlertStore()
    first = store.add("alpha", "crash", {})
    second = store.add("bravo", "offline", {"misses": 3})
    assert [a.id for a in store.list()] == [second.id, first.id]
    assert store.unread_count() == 2
    assert store.dismiss(first.id) is True
    assert store.dismiss(999) is False
    assert [a.id for a in store.list()] == [second.id]
    assert [a.id for a in store.list(include_dismissed=True)] == [second.id, first.id]
    assert store.unread_count() == 1


def test_the_store_is_bounded() -> None:
    store = AlertStore(maxlen=3)
    for n in range(5):
        store.add("alpha", "crash", {"n": n})
    assert [a.detail for a in store.list()] == ["n=4", "n=3", "n=2"]


def test_alert_routes_list_and_dismiss(tmp_path: Path) -> None:
    with make_client(tmp_path, ("alpha",)) as (client, _sup, _home):
        store: AlertStore = client.app.state.alerts
        crash = store.add("alpha", "crash", {"err": "adb gone"})
        store.add("alpha", "offline", {"misses": 3})
        body = client.get("/api/alerts").json()
        assert body["unread"] == 2
        assert [a["kind"] for a in body["alerts"]] == ["offline", "crash"]
        assert body["alerts"][1]["title"] == "Bot crashed"
        assert body["alerts"][1]["instance"] == "alpha"

        assert client.post(f"/api/alerts/{crash.id}/dismiss").status_code == 204
        after = client.get("/api/alerts").json()
        assert after["unread"] == 1
        assert [a["kind"] for a in after["alerts"]] == ["offline"]
        assert len(client.get("/api/alerts?include_dismissed=true").json()["alerts"]) == 2
        assert client.post("/api/alerts/999/dismiss").status_code == 404


def test_the_app_wires_the_store_to_the_tailer_and_the_supervisor(tmp_path: Path) -> None:
    with make_client(tmp_path, ("alpha",)) as (client, _sup, _home):
        store = client.app.state.alerts
        assert isinstance(store, AlertStore)
        assert client.app.state.tailer._alerts is store
```

Append to `tests/test_notify_config.py`:

```python
def test_healthchecks_url_from_settings_then_env(monkeypatch) -> None:
    assert notify.healthchecks_url() == ""
    monkeypatch.setenv("HEALTHCHECKS_URL", "https://hc.invalid/from-env")
    assert notify.healthchecks_url() == "https://hc.invalid/from-env"
    notify.configure(healthchecks_url="https://hc.invalid/from-settings")
    assert notify.healthchecks_url() == "https://hc.invalid/from-settings"


def test_ping_healthchecks_is_a_no_op_without_a_url() -> None:
    calls: list[str] = []
    assert notify.ping_healthchecks(getter=lambda url, timeout: calls.append(url)) is False
    assert calls == []


def test_ping_healthchecks_gets_the_url_and_never_raises() -> None:
    seen: list[tuple[str, int]] = []

    class _Ok:
        status_code = 200

    def _get(url, timeout):
        seen.append((url, timeout))
        return _Ok()

    notify.configure(healthchecks_url="https://hc.invalid/uuid")
    assert notify.ping_healthchecks(getter=_get) is True
    assert seen == [("https://hc.invalid/uuid", 5)]

    def _boom(url, timeout):
        raise OSError("network down")

    assert notify.ping_healthchecks(getter=_boom) is False


def test_alert_title_is_shared_with_the_panel() -> None:
    assert notify.alert_title("crash") == "Bot crashed"
    assert notify.alert_title("offline") == "Instance offline"
    assert notify.alert_title("mystery") == "Bot: mystery"
```

Append to `tests/test_supervisor_loop.py`:

```python
def test_every_completed_tick_pings_healthchecks(sup, world) -> None:
    sup.tick()
    sup.tick()
    assert world.pings == 2


def test_offline_alert_also_reaches_the_panel(tmp_path, world, monkeypatch) -> None:
    sup = make_sup(tmp_path, world, ("Pie64",))
    monkeypatch.setattr(L.notify, "maybe_alert", lambda kind, fields: None)
    seen: list[tuple[str, str, dict]] = []
    sup.subscribe_alerts(lambda name, kind, fields: seen.append((name, kind, fields)))
    world.online[5555] = False
    sup.tick()  # miss 1 -> retry in 2 min
    world.now += timedelta(minutes=2)
    sup.tick()  # miss 2 -> retry in 4 min
    world.now += timedelta(minutes=4)
    sup.tick()  # miss 3 -> alert
    assert seen == [("Pie64", "offline", {"misses": 3})]
```

- [ ] **Step 2: Run them to confirm they fail**

```bash
uv run pytest tests/test_api_alerts.py tests/test_notify_config.py tests/test_supervisor_loop.py -v
```

Expected: `tests/test_api_alerts.py` fails collection with `ModuleNotFoundError: No module named
'brawlfarm.api.alerts'`; `AttributeError: module 'brawlfarm.core.notify' has no attribute
'healthchecks_url'`; `AttributeError: 'World' object has no attribute 'pings'`.

- [ ] **Step 3: Add the healthchecks ping and the shared title to `brawlfarm/core/notify.py`**

Replace `configure` (lines 77 to 96) with:

```python
def configure(
    *,
    webhook_url: str | None = None,
    ntfy_server: str | None = None,
    ntfy_topic: str | None = None,
    events: list[str] | None = None,
    healthchecks_url: str | None = None,
) -> None:
    """Set the backends from settings. Workers keep reading the environment the
    supervisor hands them; the supervisor process itself calls this once."""
    for key, value in (
        ("webhook_url", webhook_url),
        ("ntfy_server", ntfy_server),
        ("ntfy_topic", ntfy_topic),
        ("events", events),
        ("healthchecks_url", healthchecks_url),
    ):
        if value is None:
            _overrides.pop(key, None)
        else:
            _overrides[key] = value
```

Add, immediately after `_ascii` (so it sits with the other small helpers, before `_overrides`):

```python
def alert_title(kind: str) -> str:
    """The human title for an alert kind. Shared with the control panel's alert list so a
    phone notification and the Fleet drawer name the same event the same way."""
    return _TITLES.get(kind, f"Bot: {kind}")
```

Add, after `configured()` (line 126):

```python
def healthchecks_url() -> str:
    """The healthchecks.io (or compatible) ping URL: settings first, then HEALTHCHECKS_URL."""
    if "healthchecks_url" in _overrides:
        return str(_overrides["healthchecks_url"]).strip()
    return os.environ.get("HEALTHCHECKS_URL", "").strip()


def ping_healthchecks(*, getter=None) -> bool:
    """GET the ping URL so a supervisor that stops ticking raises an alarm somewhere the
    owner will see. No-op (False) when no URL is set. Never raises and never retries: a
    dead monitor must not stall the tick. `getter` is injected by tests; the default is
    imported lazily so the module keeps working without requests installed."""
    url = healthchecks_url()
    if not url:
        return False
    try:
        if getter is None:
            import requests

            getter = requests.get
        response = getter(url, timeout=5)
        return int(getattr(response, "status_code", 0)) < 300
    except Exception:
        return False
```

In `maybe_alert` (line 217) replace the title lookup so both paths share one table:

```python
    title = alert_title(kind)
```

- [ ] **Step 4: Add the alert listeners and the ping to `brawlfarm/supervisor/loop.py`**

In `__init__` (lines 45 to 72), add the keyword after `events_refresh` and keep `interval_s` last:

```python
        events_refresh: Callable[..., int] = events.refresh,
        pinger: Callable[[], bool] = notify.ping_healthchecks,
        interval_s: float = TICK_S,
```

and, in the body, store it next to the other injected collaborators and add the listener list:

```python
        self._alive, self._kill, self._sleep, self._refresh = alive, killer, sleep, events_refresh
        self._ping = pinger
        self._backoff = OfflineBackoff()
```

```python
        self._listeners: list[Callable[[InstanceView], None]] = []
        self._alert_listeners: list[Callable[[str, str, dict], None]] = []
```

In `apply_settings` (lines 84 to 90) pass the new key:

```python
        n = settings.notifications
        notify.configure(
            webhook_url=n.webhook_url or None,  # blank defers to the environment
            ntfy_server=n.ntfy_server or None,
            ntfy_topic=n.ntfy_topic or None,
            events=list(n.events),
            healthchecks_url=n.healthchecks_url or None,
        )
```

Add, right after `subscribe` (line 96):

```python
    def subscribe_alerts(self, cb: Callable[[str, str, dict], None]) -> None:
        """Called with (instance name, alert kind, fields) for alerts the supervisor raises
        itself. The panel's alert store registers here; the push notifier is separate and
        keeps its own cooldown."""
        self._alert_listeners.append(cb)

    def _fire_alert(self, name: str, kind: str, fields: dict) -> None:
        for cb in self._alert_listeners:
            try:
                cb(name, kind, fields)
            except Exception as exc:
                log.debug("alert listener failed: %s", exc)
```

At the offline site (lines 175 to 177) add the panel's copy next to the push alert:

```python
                if misses == ALERT_AFTER_MISSES:
                    notify.maybe_alert("offline", {"instance": name, "misses": misses})
                    self._fire_alert(name, "offline", {"misses": misses})
                note = _offline_note(retry, now)
```

At the end of `tick()` (lines 134 to 135) replace the return with:

```python
        log.info("tick: %s", ", ".join(f"{v.name}={v.state}" for v in out) or "no instances")
        # Only a tick that got this far pings: a wedged supervisor stops pinging, which is
        # exactly what the healthchecks alarm is for. Never allowed to raise.
        try:
            self._ping()
        except Exception as exc:
            log.debug("healthchecks ping failed: %s", exc)
        return out
```

- [ ] **Step 5: Write `brawlfarm/api/alerts.py`**

```python
"""Alerts for the Fleet drawer (spec section 7).

The worker already writes alert-worthy events into its session JSONL and the push notifier
already turns them into a phone buzz (core/notify.py). This store collects the same kinds
for the panel: the feed tailer offers it every session line, and the supervisor hands it
the `offline` alert it raises itself. In memory only (ruling 3) — alerts are a "look at
this now" list, not a record; the session files keep the history.
"""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request, Response

from brawlfarm.core import notify

router = APIRouter()

MAX_ALERTS = 200
# The panel's alert kinds are the spec's six (section 7). notify.ALERT_KINDS also carries
# "stop" for push notifications; a graceful stop is not a panel alert.
PANEL_ALERT_KINDS = frozenset(notify.ALERT_KINDS) - {"stop"}


@dataclass
class Alert:
    """One thing worth interrupting the owner for. Mutable so dismiss() can flip a flag
    without rebuilding the list."""

    id: int
    ts: str
    instance: str
    kind: str
    title: str
    detail: str
    dismissed: bool = False


class AlertStore:
    def __init__(self, bus=None, *, maxlen: int = MAX_ALERTS) -> None:
        self._bus = bus
        self._alerts: deque[Alert] = deque(maxlen=maxlen)
        self._next_id = 1

    def add(self, instance: str, kind: str, fields: dict, ts: str | None = None) -> Alert:
        """Record an alert and publish it on the bus. The detail line is built the same way
        notify.maybe_alert builds its message, so the drawer and the phone agree."""
        alert = Alert(
            id=self._next_id,
            ts=ts or datetime.now().isoformat(timespec="seconds"),
            instance=instance,
            kind=kind,
            title=notify.alert_title(kind),
            detail=", ".join(f"{k}={v}" for k, v in fields.items() if v is not None),
        )
        self._next_id += 1
        self._alerts.append(alert)
        if self._bus is not None:
            self._bus.publish("alert", asdict(alert))
        return alert

    def ingest(self, instance: str, record: dict) -> Alert | None:
        """A raw session line; None unless its kind is one of PANEL_ALERT_KINDS."""
        kind = str(record.get("kind") or "")
        if kind not in PANEL_ALERT_KINDS:
            return None
        stamped = record.get("ts")
        fields = {k: v for k, v in record.items() if k not in ("ts", "kind")}
        return self.add(instance, kind, fields, ts=str(stamped) if stamped else None)

    def list(self, *, include_dismissed: bool = False) -> list[Alert]:
        """Newest first, which is the order the drawer shows them in."""
        return [a for a in reversed(self._alerts) if include_dismissed or not a.dismissed]

    def dismiss(self, alert_id: int) -> bool:
        for alert in self._alerts:
            if alert.id == alert_id:
                alert.dismissed = True
                return True
        return False

    def unread_count(self) -> int:
        return sum(1 for alert in self._alerts if not alert.dismissed)


@router.get("/api/alerts")
async def get_alerts(request: Request, include_dismissed: bool = False) -> dict:
    """The alert list for the Fleet drawer, newest first, with the count for its badge."""
    store: AlertStore = request.app.state.alerts
    return {
        "alerts": [asdict(a) for a in store.list(include_dismissed=include_dismissed)],
        "unread": store.unread_count(),
    }


@router.post("/api/alerts/{alert_id}/dismiss", status_code=204)
async def dismiss_alert(request: Request, alert_id: int) -> Response:
    """Mark one alert read. 404 when it has already fallen off the end of the store."""
    store: AlertStore = request.app.state.alerts
    if not store.dismiss(alert_id):
        raise HTTPException(status_code=404, detail="unknown alert")
    return Response(status_code=204)
```

- [ ] **Step 6: Wire the store into `brawlfarm/api/app.py`**

Add `alerts` to the route-module import and include its router:

```python
from brawlfarm.api import (
    alerts,
    events,
    feed,
    instances,
    plans,
    schedule,
    screens,
    settings_routes,
    setup_routes,
)
```

```python
    app.include_router(alerts.router)
```

Then replace the whole `lifespan` function (task 7's version) with:

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup: attach the bus to this loop, mirror the brawlfarm logger onto it, publish
    every supervisor state change, collect alerts from the tailer and from the supervisor
    itself, start the feed tailer, and run one tick so the first GET /api/instances already
    has views. Shutdown: stop the tailer and detach the log handler so a second app in the
    same process does not publish into a dead bus."""
    app.state.started_at = time.monotonic()
    bus = EventBus()
    bus.attach(asyncio.get_running_loop())
    app.state.bus = bus
    store = AlertStore(bus)
    app.state.alerts = store
    # tick() runs in a worker thread, so both callbacks fire OFF the loop thread;
    # EventBus.publish hops back with call_soon_threadsafe.
    app.state.sup.subscribe(lambda view: bus.publish("instance", view_to_dict(view)))
    app.state.sup.subscribe_alerts(store.add)
    handler = BusLogHandler(bus)
    logging.getLogger("brawlfarm").addHandler(handler)
    tailer = FeedTailer(app.state.home, app.state.sup, bus, alerts=store)
    app.state.tailer = tailer
    tailing = asyncio.create_task(tailer.run())
    try:
        try:
            await asyncio.to_thread(app.state.sup.tick)
        except Exception:  # a failed startup tick must not stop the app from serving
            log.exception("startup tick failed")
        yield
    finally:
        tailing.cancel()
        with suppress(asyncio.CancelledError):
            await tailing
        logging.getLogger("brawlfarm").removeHandler(handler)
```

with this import added at the top of `app.py`:

```python
from brawlfarm.api.alerts import AlertStore
```

- [ ] **Step 7: Keep the healthchecks URL out of the test environment**

`notify.healthchecks_url()` falls back to `HEALTHCHECKS_URL`, so a developer with that variable
set would have the suite ping a real monitor. In `tests/conftest.py`, extend the prefix tuple in
`_isolated_home` (task 1 added the notify and scheduler teardown to this same fixture; only this
tuple changes):

```python
        if key.startswith(("BRAWL_", "DISCORD_", "NTFY_", "HEALTHCHECKS")):
```

- [ ] **Step 8: Give the supervisor test world a ping counter**

In `tests/test_supervisor_loop.py`, add one field to the `World` dataclass (after `refreshes`):

```python
    refreshes: int = 0
    pings: int = 0
    next_pid: int = 100
```

one method (after `refresh`):

```python
    def ping(self) -> bool:
        self.pings += 1
        return True
```

and wire it in `make_sup` (the `Supervisor(...)` call), which also keeps every existing
supervisor test off the network:

```python
        sleep=lambda _s: None,
        events_refresh=world.refresh,
        pinger=world.ping,
    )
```

- [ ] **Step 9: Run the tests**

```bash
uv run pytest tests/test_api_alerts.py tests/test_notify_config.py tests/test_supervisor_loop.py -v
uv run pytest -q
```

Expected: 6 passed in `tests/test_api_alerts.py`, 10 in `tests/test_notify_config.py`, and the
supervisor file green with its two new tests. Whole suite green, no warnings.

- [ ] **Step 10: Lint, scrub, commit**

```bash
uv run ruff format brawlfarm/api/alerts.py brawlfarm/api/app.py brawlfarm/core/notify.py brawlfarm/supervisor/loop.py tests/conftest.py tests/test_api_alerts.py tests/test_notify_config.py tests/test_supervisor_loop.py
uv run ruff check . && uv run ruff format --check .
uv run python tools/scrub_check.py
git add brawlfarm/api/alerts.py brawlfarm/api/app.py brawlfarm/core/notify.py brawlfarm/supervisor/loop.py tests/conftest.py tests/test_api_alerts.py tests/test_notify_config.py tests/test_supervisor_loop.py
git commit -m "feat(api): alert list, dismiss, and the healthchecks ping

The Fleet drawer needs the alert kinds the push notifier already sends,
as a list it can dismiss; the store is in memory because alerts are a
'look at this now' list and the session files keep the history. Each
completed tick pings notifications.healthchecks_url, closing the phase 2
deferral: a supervisor that stops ticking now raises an alarm."
```

---

### Task 9: Stats aggregation and its two routes

Spec section 7 and the Stats screen in section 8: one summary row, one cumulative-trophy series
per instance, a per-brawler table, the rank distribution, the recent games list, and a CSV
export. `core/stats.py` already parses `games.csv`; this module adds the multi-instance,
range-filtered shape the screen wants and keeps NaN out of the JSON.

**Files:**
- Create: `brawlfarm/api/stats.py`
- Modify: `brawlfarm/api/app.py` (the import and `include_router` block only; the lifespan is unchanged from task 8)
- Create: `tests/test_api_stats.py`

**Interfaces:**
- Consumes: `brawlfarm.core.stats.load_games(path) -> DataFrame` (stats.py:34-52; parses `battleTime` with `%Y%m%dT%H%M%S.%fZ` as UTC-aware and coerces `rank`, `trophyChange`, `duration_s` to numbers); `brawlfarm.core.datalog.GAME_FIELDS` (datalog.py:78-91); `settings.instance_dir(home, name)`; `app.state.home`, `app.state.sup` (task 1); `tests.apihelpers.make_client` (task 1).
- Produces (all in `brawlfarm.api.stats`):
  - `RANGES = ("today", "7d", "30d", "all")`, `RangeName = Literal["today", "7d", "30d", "all"]`, `SESSION_GAP_S = 1800.0`, `RECENT_LIMIT = 20`
  - `range_start(range_: str, now: datetime) -> datetime | None`
  - `load_games_for(home: Path, names: Sequence[str], range_: str, now: datetime) -> DataFrame`
  - `sessions_hours(games: DataFrame) -> float`
  - `aggregate(home: Path, names: Sequence[str], range_: str, now: datetime) -> dict`
  - `export_csv(home: Path, names: Sequence[str], range_: str, now: datetime) -> str`
  - `router = APIRouter()` with `GET /api/stats` and `GET /api/stats/export.csv`

- [ ] **Step 1: Write the failing test**

`tests/test_api_stats.py`:

```python
"""Stats aggregation over fixture games.csv files: local-time range filtering, the
30-minute session-gap rule behind "time farmed", the summary row, the per-instance
cumulative series, the per-brawler and rank tables, the recent list, the CSV export, and
the two routes with their 404 and 422 answers. No NaN ever reaches the JSON."""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from brawlfarm import settings as S
from brawlfarm.api.stats import aggregate, export_csv, load_games_for, range_start, sessions_hours
from brawlfarm.core import datalog
from tests.apihelpers import make_client

NOW = datetime(2026, 9, 10, 18, 0, 0)  # naive local, the way the routes call datetime.now()


def _battle_time(moment: datetime) -> str:
    """A local moment as the API's UTC battleTime string (datalog's %Y%m%dT%H%M%S.%fZ)."""
    return moment.astimezone(UTC).strftime("%Y%m%dT%H%M%S.%f")[:-3] + "Z"


def _game(minutes_ago: float, brawler: str, rank: int, change: int, duration: int = 150) -> dict:
    moment = NOW - timedelta(minutes=minutes_ago)
    return {
        "battleTime": _battle_time(moment),
        "logged_at": moment.isoformat(timespec="seconds"),
        "event_mode": "soloShowdown",
        "battle_mode": "soloShowdown",
        "type": "ranked",
        "rank": rank,
        "trophyChange": change,
        "result": "",
        "duration_s": duration,
        "map": "Feast or Famine",
        "brawler": brawler,
        "is_showdown": True,
    }


def _write_games(home: Path, name: str, rows: list[dict]) -> None:
    inst_dir = S.instance_dir(home, name)
    inst_dir.mkdir(parents=True, exist_ok=True)
    with (inst_dir / "games.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=datalog.GAME_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _fixture(home: Path) -> None:
    """alpha: one game yesterday, a three-game block, then one game after a 90 min gap.
    bravo: a single game. Numbers are chosen so every summary field is checkable by hand."""
    _write_games(
        home,
        "alpha",
        [
            _game(1500, "SHELLY", 9, -4),  # 25 h ago: outside "today", inside "7d"
            _game(120, "SHELLY", 2, 7),
            _game(115, "COLT", 4, 3),
            _game(110, "SHELLY", 1, 9),
            _game(20, "COLT", 8, -3),  # after a 90 min gap: a second session
        ],
    )
    _write_games(home, "bravo", [_game(60, "NITA", 3, 5)])


def test_range_start_is_local_and_midnight_for_today() -> None:
    assert range_start("today", NOW) == NOW.astimezone().replace(hour=0, minute=0, second=0)
    assert range_start("7d", NOW) == NOW.astimezone() - timedelta(days=7)
    assert range_start("30d", NOW) == NOW.astimezone() - timedelta(days=30)
    assert range_start("all", NOW) is None


def test_today_summary_across_two_instances(tmp_path: Path) -> None:
    _fixture(tmp_path)
    out = aggregate(tmp_path, ["alpha", "bravo"], "today", NOW)
    assert out["range"] == "today"
    assert out["instances"] == ["alpha", "bravo"]
    # 5 games today (yesterday's is excluded); 7+3+9-3+5 = 21 trophies; ranks 2,4,1,8,3;
    # sessions 16:00-16:10 (+150 s), 17:40 alone, bravo 17:00 alone = 17.5 min = 0.29 h.
    assert out["summary"] == {
        "games": 5,
        "trophies": 21,
        "trophies_per_hour": 72.0,
        "avg_rank": 3.6,
        "top4_rate": 80.0,
        "hours_farmed": 0.3,
    }


def test_seven_days_reaches_back_past_midnight(tmp_path: Path) -> None:
    _fixture(tmp_path)
    summary = aggregate(tmp_path, ["alpha"], "7d", NOW)["summary"]
    assert summary["games"] == 5
    assert summary["trophies"] == 12
    assert summary["avg_rank"] == 4.8
    assert summary["top4_rate"] == 60.0


def test_series_brawlers_ranks_and_recent(tmp_path: Path) -> None:
    _fixture(tmp_path)
    out = aggregate(tmp_path, ["alpha", "bravo"], "today", NOW)
    series = {s["instance"]: [p["cum"] for p in s["points"]] for s in out["series"]}
    assert series["alpha"] == [7, 10, 19, 16]
    assert series["bravo"] == [5]
    assert out["series"][0]["points"][0]["t"].startswith("2026-09-10T")
    assert out["brawlers"] == [
        {"name": "COLT", "games": 2, "net": 0, "avg_rank": 6.0, "top4_rate": 50.0},
        {"name": "SHELLY", "games": 2, "net": 16, "avg_rank": 1.5, "top4_rate": 100.0},
        {"name": "NITA", "games": 1, "net": 5, "avg_rank": 3.0, "top4_rate": 100.0},
    ]
    assert out["ranks"] == [
        {"rank": 1, "games": 1},
        {"rank": 2, "games": 1},
        {"rank": 3, "games": 1},
        {"rank": 4, "games": 1},
        {"rank": 8, "games": 1},
    ]
    assert len(out["recent"]) == 5
    assert out["recent"][0]["instance"] == "alpha"
    assert out["recent"][0]["brawler"] == "COLT"
    assert out["recent"][0]["rank"] == 8
    assert out["recent"][0]["trophy_change"] == -3
    assert out["recent"][0]["map"] == "Feast or Famine"
    assert out["recent"][0]["mode"] == "soloShowdown"


def test_empty_data_is_zeroed_and_json_safe(tmp_path: Path) -> None:
    out = aggregate(tmp_path, ["charlie"], "all", NOW)
    assert out["summary"] == {
        "games": 0,
        "trophies": 0,
        "trophies_per_hour": None,
        "avg_rank": None,
        "top4_rate": None,
        "hours_farmed": 0.0,
    }
    assert out["series"] == [{"instance": "charlie", "points": []}]
    assert out["brawlers"] == [] and out["ranks"] == [] and out["recent"] == []
    json.dumps(out, allow_nan=False)  # NaN would make the browser's JSON.parse fail


def test_sessions_hours_splits_on_a_thirty_minute_gap(tmp_path: Path) -> None:
    _write_games(
        tmp_path,
        "alpha",
        [_game(200, "SHELLY", 1, 9, duration=0), _game(180, "SHELLY", 1, 9, duration=0)],
    )
    together = load_games_for(tmp_path, ["alpha"], "all", NOW)
    assert round(sessions_hours(together), 3) == round(20 / 60, 3)

    _write_games(
        tmp_path,
        "alpha",
        [_game(200, "SHELLY", 1, 9, duration=0), _game(120, "SHELLY", 1, 9, duration=0)],
    )
    apart = load_games_for(tmp_path, ["alpha"], "all", NOW)
    assert sessions_hours(apart) == 0.0  # two one-game sessions, no duration to add


def test_export_csv_is_the_raw_rows_in_time_order(tmp_path: Path) -> None:
    _fixture(tmp_path)
    body = export_csv(tmp_path, ["alpha", "bravo"], "today", NOW)
    rows = list(csv.DictReader(body.splitlines()))
    assert list(rows[0]) == ["instance", *datalog.GAME_FIELDS]
    assert [r["instance"] for r in rows] == ["alpha", "alpha", "alpha", "bravo", "alpha"]
    assert [r["rank"] for r in rows] == ["2", "4", "1", "3", "8"]  # ints, not 2.0
    assert rows[0]["battleTime"] == _battle_time(NOW - timedelta(minutes=120))


def test_stats_routes(tmp_path: Path) -> None:
    with make_client(tmp_path, ("alpha", "bravo")) as (client, _sup, home):
        _fixture(home)
        body = client.get("/api/stats?range=all").json()
        assert body["range"] == "all"
        assert body["instances"] == ["alpha", "bravo"]
        assert body["summary"]["games"] == 6
        assert client.get("/api/stats").json()["range"] == "today"
        assert client.get("/api/stats?range=all&instances=bravo").json()["instances"] == ["bravo"]
        assert client.get("/api/stats?range=year").status_code == 422
        assert client.get("/api/stats?instances=ghost").status_code == 404

        export = client.get("/api/stats/export.csv?range=all")
        assert export.status_code == 200
        assert export.headers["content-type"].startswith("text/csv")
        assert (
            export.headers["content-disposition"]
            == 'attachment; filename="brawlfarm-games-all.csv"'
        )
        assert export.text.splitlines()[0] == ",".join(["instance", *datalog.GAME_FIELDS])
        assert len(export.text.splitlines()) == 7  # header + 6 games
```

- [ ] **Step 2: Run it to confirm it fails**

```bash
uv run pytest tests/test_api_stats.py -v
```

Expected: collection fails with `ImportError: cannot import name 'aggregate' from
'brawlfarm.api.stats'` (or `ModuleNotFoundError` if the file does not exist yet).

- [ ] **Step 3: Write `brawlfarm/api/stats.py`**

```python
"""Stats for the Stats screen (spec sections 7 and 8).

core/stats.py reads one instance's games.csv; this module reads several, filters them to a
range in LOCAL time (the owner thinks in local days, the API stamps battleTime in UTC) and
shapes the numbers the screen draws: the summary row, one cumulative-trophy series per
instance, the per-brawler table, the rank distribution and the recent games list. Every
number is rounded for display and NaN is turned into None, because json.dumps would happily
write NaN and the browser's JSON.parse would then reject the whole response.

"Time farmed" is an approximation (ruling 9): games are grouped per instance into sessions
split wherever more than 30 minutes passed since the previous game, and each session counts
as first-to-last plus the last game's duration.
"""

from __future__ import annotations

import asyncio
import csv
import io
import logging
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

import pandas as pd
from fastapi import APIRouter, HTTPException, Query, Request, Response

from brawlfarm import settings as S
from brawlfarm.core import datalog
from brawlfarm.core import stats as core_stats

log = logging.getLogger("brawlfarm.api")
router = APIRouter()

RANGES = ("today", "7d", "30d", "all")
RangeName = Literal["today", "7d", "30d", "all"]
SESSION_GAP_S = 1800.0  # more than 30 min between games ends a farming session
RECENT_LIMIT = 20
_BATTLETIME_FMT = "%Y%m%dT%H%M%S.%fZ"  # the API's format, as written by core/datalog.py


def range_start(range_: str, now: datetime) -> datetime | None:
    """The oldest local moment inside `range_`, or None for "all". `today` is local midnight
    so a session that ran past midnight splits across two days, which is what the owner
    means by "today"."""
    if range_ not in RANGES:
        raise ValueError(f"unknown range {range_!r}")
    local = now.astimezone()
    if range_ == "today":
        return local.replace(hour=0, minute=0, second=0, microsecond=0)
    if range_ == "7d":
        return local - timedelta(days=7)
    if range_ == "30d":
        return local - timedelta(days=30)
    return None


def load_games_for(
    home: Path, names: Sequence[str], range_: str, now: datetime
) -> pd.DataFrame:
    """Every selected instance's games.csv in one frame with an `instance` column, times
    converted to the local zone and filtered to the range, oldest first. An instance with no
    file contributes nothing; nothing at all gives an empty frame with the right columns so
    every caller below can assume the columns exist."""
    start = range_start(range_, now)
    frames: list[pd.DataFrame] = []
    for name in names:
        df = core_stats.load_games(S.instance_dir(home, name) / "games.csv")
        if df.empty:
            continue
        df = df.copy()
        df["instance"] = name
        frames.append(df)
    if not frames:
        return pd.DataFrame(columns=["instance", *datalog.GAME_FIELDS])
    games = pd.concat(frames, ignore_index=True)
    if "battleTime" in games:
        games = games.dropna(subset=["battleTime"])
        # One fixed offset for the whole window: a DST change inside a 30-day range shifts
        # the boundary by an hour, which no owner will notice on a daily total.
        games["battleTime"] = games["battleTime"].dt.tz_convert(now.astimezone().tzinfo)
        if start is not None:
            games = games[games["battleTime"] >= start]
        games = games.sort_values("battleTime").reset_index(drop=True)
    return games


def sessions_hours(games: pd.DataFrame) -> float:
    """Hours actually farmed (ruling 9): per instance, sum first-to-last plus the last
    game's duration over each block of games no more than SESSION_GAP_S apart."""
    if games.empty or "battleTime" not in games or "instance" not in games:
        return 0.0
    total = 0.0
    for _name, part in games.groupby("instance", sort=False):
        part = part.dropna(subset=["battleTime"]).sort_values("battleTime")
        if part.empty:
            continue
        times = list(part["battleTime"])
        if "duration_s" in part:
            durations = [_num(d, 3) or 0.0 for d in part["duration_s"]]
        else:
            durations = [0.0] * len(times)
        start = times[0]
        previous, previous_duration = times[0], durations[0]
        for moment, duration in zip(times[1:], durations[1:], strict=True):
            if (moment - previous).total_seconds() > SESSION_GAP_S:
                total += (previous - start).total_seconds() + previous_duration
                start = moment
            previous, previous_duration = moment, duration
        total += (previous - start).total_seconds() + previous_duration
    return total / 3600.0


def _num(value, digits: int = 1) -> float | None:
    """Round for display; None for anything that is not a real number. pandas hands back
    NaN for a missing cell and json.dumps would write a bare NaN, which no browser parses."""
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:  # NaN
        return None
    return round(number, digits)


def _text(value) -> str | None:
    if value is None or (isinstance(value, float) and value != value):
        return None
    return str(value)


def aggregate(home: Path, names: Sequence[str], range_: str, now: datetime) -> dict:
    """Everything the Stats screen draws for one range and one set of instances.
    Blocking (pandas); the routes run it in a thread."""
    games = load_games_for(home, names, range_, now)
    hours = sessions_hours(games)
    changes = games["trophyChange"].dropna() if "trophyChange" in games else pd.Series(dtype=float)
    ranks = games["rank"].dropna() if "rank" in games else pd.Series(dtype=float)
    net = int(changes.sum()) if len(changes) else 0
    return {
        "range": range_,
        "instances": list(names),
        "summary": {
            "games": int(len(games)),
            "trophies": net,
            "trophies_per_hour": _num(net / hours) if hours > 0 else None,
            "avg_rank": _num(ranks.mean()) if len(ranks) else None,
            "top4_rate": _num(float((ranks <= 4).mean()) * 100) if len(ranks) else None,
            "hours_farmed": _num(hours),
        },
        "series": _series(games, names),
        "brawlers": _brawlers(games),
        "ranks": _ranks(ranks),
        "recent": _recent(games),
    }


def _series(games: pd.DataFrame, names: Sequence[str]) -> list[dict]:
    """One cumulative net-trophy line per instance, in battleTime order. An instance with no
    games still gets an entry so the chart legend matches the chips the user picked."""
    out: list[dict] = []
    for name in names:
        points: list[dict] = []
        if not games.empty and "instance" in games:
            running = 0
            for row in games[games["instance"] == name].to_dict("records"):
                change = _num(row.get("trophyChange"), 0)
                running += int(change) if change is not None else 0
                moment = row["battleTime"].to_pydatetime()
                points.append({"t": moment.isoformat(timespec="seconds"), "cum": running})
        out.append({"instance": name, "points": points})
    return out


def _brawlers(games: pd.DataFrame) -> list[dict]:
    if games.empty or "brawler" not in games:
        return []
    out: list[dict] = []
    for brawler, part in games.groupby("brawler", sort=False):
        ranks = part["rank"].dropna() if "rank" in part else pd.Series(dtype=float)
        changes = (
            part["trophyChange"].dropna() if "trophyChange" in part else pd.Series(dtype=float)
        )
        out.append(
            {
                "name": str(brawler),
                "games": int(len(part)),
                "net": int(changes.sum()) if len(changes) else 0,
                "avg_rank": _num(ranks.mean()) if len(ranks) else None,
                "top4_rate": _num(float((ranks <= 4).mean()) * 100) if len(ranks) else None,
            }
        )
    out.sort(key=lambda row: (-row["games"], row["name"]))  # name breaks ties, so it is stable
    return out


def _ranks(ranks: pd.Series) -> list[dict]:
    if not len(ranks):
        return []
    counts = ranks.astype(int).value_counts().sort_index()
    return [{"rank": int(rank), "games": int(n)} for rank, n in counts.items()]


def _recent(games: pd.DataFrame) -> list[dict]:
    """The newest RECENT_LIMIT games, newest first."""
    if games.empty:
        return []
    out: list[dict] = []
    for row in games.tail(RECENT_LIMIT).iloc[::-1].to_dict("records"):
        rank = _num(row.get("rank"), 0)
        change = _num(row.get("trophyChange"), 0)
        out.append(
            {
                "instance": _text(row.get("instance")),
                "t": row["battleTime"].to_pydatetime().isoformat(timespec="seconds"),
                "brawler": _text(row.get("brawler")),
                "rank": int(rank) if rank is not None else None,
                "trophy_change": int(change) if change is not None else None,
                "map": _text(row.get("map")),
                "mode": _text(row.get("event_mode")),
            }
        )
    return out


def _parse_battle_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, _BATTLETIME_FMT).replace(tzinfo=UTC)
    except (TypeError, ValueError):
        return None


def export_csv(home: Path, names: Sequence[str], range_: str, now: datetime) -> str:
    """The selected games as CSV: `instance` plus datalog.GAME_FIELDS, oldest first. Read
    with the csv module rather than pandas on purpose — pandas turns an int column with one
    empty cell into floats, and the export must be byte-for-byte the values the worker
    logged. Blocking; the route runs it in a thread."""
    start = range_start(range_, now)
    rows: list[tuple[datetime, dict]] = []
    for name in names:
        path = S.instance_dir(home, name) / "games.csv"
        if not path.exists():
            continue
        try:
            with path.open("r", newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    moment = _parse_battle_time(row.get("battleTime"))
                    if moment is None or (start is not None and moment < start):
                        continue
                    fields = {k: row.get(k, "") for k in datalog.GAME_FIELDS}
                    rows.append((moment, {"instance": name, **fields}))
        except OSError as exc:
            log.warning("%s: cannot read games.csv: %s", name, exc)
    rows.sort(key=lambda pair: pair[0])
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=["instance", *datalog.GAME_FIELDS], lineterminator="\n")
    writer.writeheader()
    for _moment, row in rows:
        writer.writerow(row)
    return buf.getvalue()


def _selected(request: Request, instances: str | None) -> list[str]:
    """The instance filter: a comma-separated list, or every configured instance. An unknown
    name is a 404 like every other instance route, not a silently empty chart."""
    configured = [i.name for i in request.app.state.sup.settings.instances]
    if not instances:
        return configured
    names = [n.strip() for n in instances.split(",") if n.strip()]
    for name in names:
        if name not in configured:
            raise HTTPException(status_code=404, detail="unknown instance")
    return names


@router.get("/api/stats")
async def get_stats(
    request: Request,
    range_: RangeName = Query("today", alias="range"),
    instances: str | None = None,
) -> dict:
    """Summary, series, brawlers, ranks and recent games for one range. An unknown range is
    a 422 (FastAPI validates the Literal); an unknown instance is a 404."""
    names = _selected(request, instances)
    return await asyncio.to_thread(aggregate, request.app.state.home, names, range_, datetime.now())


@router.get("/api/stats/export.csv")
async def get_stats_csv(
    request: Request,
    range_: RangeName = Query("today", alias="range"),
    instances: str | None = None,
) -> Response:
    """The same selection as a CSV download, one row per game."""
    names = _selected(request, instances)
    body = await asyncio.to_thread(
        export_csv, request.app.state.home, names, range_, datetime.now()
    )
    return Response(
        content=body,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="brawlfarm-games-{range_}.csv"'},
    )
```

- [ ] **Step 4: Include the router in `brawlfarm/api/app.py`**

Add `stats` to the route-module import and include its router with the others (the lifespan
is unchanged from task 8):

```python
from brawlfarm.api import (
    alerts,
    events,
    feed,
    instances,
    plans,
    schedule,
    screens,
    settings_routes,
    setup_routes,
    stats,
)
```

```python
    app.include_router(stats.router)
```

- [ ] **Step 5: Run the tests**

```bash
uv run pytest tests/test_api_stats.py -v
uv run pytest -q
```

Expected: 8 passed in `tests/test_api_stats.py`, whole suite green with no warnings.

- [ ] **Step 6: Lint, scrub, commit**

```bash
uv run ruff format brawlfarm/api/stats.py brawlfarm/api/app.py tests/test_api_stats.py
uv run ruff check . && uv run ruff format --check .
uv run python tools/scrub_check.py
git add brawlfarm/api/stats.py brawlfarm/api/app.py tests/test_api_stats.py
git commit -m "feat(api): stats aggregation and CSV export

The Stats screen needs several instances in one frame, filtered by local
day rather than UTC, with every number rounded and NaN turned into null
so the browser can parse the response. Time farmed uses the 30-minute
session-gap rule; the CSV export goes through the csv module so the rows
stay exactly what the worker logged."
```

---
### Task 10: `brawlfarm` serves the panel, docs, and the pull request

Spec section 3: one process, one loop — uvicorn serves the API and the supervisor task ticks
beside it, bound to 127.0.0.1, with the browser opened on start. This task also clears the
three phase 2 CLI deferrals recorded in `docs/PLAN.md` (`--no-launch` help text, `--interval`
validation, an unwritable `--home`), rewrites the README's Running section around the API, and
opens the phase 3 pull request.

**Files:**
- Modify: `brawlfarm/__main__.py` (whole file)
- Create: `tests/test_cli_serve.py`
- Modify: `tests/test_cli.py` (append three tests)
- Modify: `README.md` (the status line at line 5, and the "Running (headless...)" section at lines 37 to 44)
- Modify: `docs/PLAN.md` (the "In flight" row at line 12)

**Interfaces:**
- Consumes: `brawlfarm.api.app.create_app(sup, home) -> FastAPI` (task 1); `Supervisor(settings, home, *, launcher, interval_s)`, `Supervisor.tick()`, `Supervisor.run_forever()`, `Supervisor.request_shutdown()` (`brawlfarm/supervisor/loop.py`); `settings.default_home/load/save/config_path`; `settings.app.port` (default 8765).
- Produces: `brawlfarm` console script flags `--version`, `--home`, `--once`, `--interval` (> 0), `--no-launch`, `--port`, `--no-browser`; `_serve(sup, app, port, *, open_browser, make_server=_uvicorn_server, browser_open=webbrowser.open, delay_s=1.0) -> None`; `_uvicorn_server(app, port)`.

- [ ] **Step 1: Write the failing tests**

`tests/test_cli_serve.py`:

```python
"""`brawlfarm` with no flags serves the panel: uvicorn and the supervisor share one loop,
the browser opens once on the right URL unless --no-browser, and the supervisor is asked to
stop when the server returns. No socket is bound: the server object is a fake."""

from __future__ import annotations

import asyncio

import pytest

from brawlfarm.__main__ import _parser, _serve


class FakeServer:
    """Stands in for uvicorn.Server: serve() returns when the user presses Ctrl+C."""

    def __init__(self) -> None:
        self.served = False

    async def serve(self) -> None:
        self.served = True
        await asyncio.sleep(0.05)  # long enough for the browser task to get its turn


class FakeSup:
    def __init__(self) -> None:
        self.runs = 0
        self.stopped = False
        self._stop = asyncio.Event()

    async def run_forever(self) -> None:
        self.runs += 1
        await self._stop.wait()

    def request_shutdown(self) -> None:
        self.stopped = True
        self._stop.set()


@pytest.mark.asyncio
async def test_serve_runs_the_supervisor_and_opens_the_browser() -> None:
    sup, server, opened = FakeSup(), FakeServer(), []
    await _serve(
        sup,
        object(),
        8765,
        open_browser=True,
        make_server=lambda app, port: server,
        browser_open=opened.append,
        delay_s=0.0,
    )
    assert server.served is True
    assert opened == ["http://127.0.0.1:8765/"]
    assert sup.runs == 1
    assert sup.stopped is True  # the supervisor loop is stopped; the workers are not


@pytest.mark.asyncio
async def test_no_browser_skips_the_browser_hook() -> None:
    sup, server, opened = FakeSup(), FakeServer(), []
    await _serve(
        sup,
        object(),
        9001,
        open_browser=False,
        make_server=lambda app, port: server,
        browser_open=opened.append,
        delay_s=0.0,
    )
    assert opened == []
    assert server.served is True
    assert sup.stopped is True


@pytest.mark.asyncio
async def test_a_browser_that_will_not_open_is_not_fatal() -> None:
    def _boom(url: str) -> None:
        raise RuntimeError("no display")

    sup, server = FakeSup(), FakeServer()
    await _serve(
        sup,
        object(),
        8765,
        open_browser=True,
        make_server=lambda app, port: server,
        browser_open=_boom,
        delay_s=0.0,
    )
    assert server.served is True and sup.stopped is True


def test_serve_flags_have_sane_defaults() -> None:
    args = _parser().parse_args([])
    assert args.port is None and args.no_browser is False and args.once is False
    args = _parser().parse_args(["--port", "9100", "--no-browser"])
    assert args.port == 9100 and args.no_browser is True
```

Append to `tests/test_cli.py`:

```python
def test_interval_must_be_positive(tmp_path: Path) -> None:
    r = _run(["--once", "--interval", "0"], tmp_path)
    assert r.returncode == 2
    assert "greater than 0" in r.stderr


def test_unwritable_home_exits_without_a_traceback(tmp_path: Path) -> None:
    blocked = tmp_path / "not-a-folder"
    blocked.write_text("this is a file, not a directory\n", encoding="utf-8")
    r = _run(["--once", "--home", str(blocked)], tmp_path)
    assert r.returncode == 2
    assert "data directory" in r.stderr
    assert "Traceback" not in r.stderr


def test_help_lists_the_serve_flags_and_the_fixed_no_launch_text() -> None:
    r = _run(["--help"], Path.cwd())
    helped = " ".join(r.stdout.split())  # argparse wraps at the terminal width
    assert "never start a worker (dry run)" in helped
    assert "--no-browser" in helped and "--port" in helped
```

- [ ] **Step 2: Run them to confirm they fail**

```bash
uv run pytest tests/test_cli_serve.py tests/test_cli.py -v
```

Expected: `tests/test_cli_serve.py` fails collection with `ImportError: cannot import name
'_serve' from 'brawlfarm.__main__'`; `test_interval_must_be_positive` fails (exit 0, the tick
runs with interval 0); `test_unwritable_home_exits_without_a_traceback` fails with a traceback
in stderr and returncode 1; the help test fails on `--no-browser`.

- [ ] **Step 3: Rewrite `brawlfarm/__main__.py`**

```python
"""Console entry point.

`brawlfarm` with no flags serves the control panel: uvicorn and the supervisor share one
asyncio loop bound to 127.0.0.1, and the default browser opens on the panel a second later
(spec section 3). `--once` keeps the headless mode phase 2 shipped: one tick, print the
instance table, exit. Closing the process leaves workers running; the next start reattaches
to them through their status.json PIDs.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import os
import sys
import webbrowser
from logging.handlers import RotatingFileHandler
from pathlib import Path

from brawlfarm import __version__
from brawlfarm import settings as S

log = logging.getLogger("brawlfarm")


def _positive(value: str) -> float:
    """argparse type for --interval: a tick every 0 seconds is a busy loop, not a setting."""
    try:
        seconds = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be a number of seconds") from None
    if seconds <= 0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return seconds


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="brawlfarm", description="Brawl Stars trophy farmer")
    ap.add_argument("-V", "--version", action="store_true", help="print the version and exit")
    ap.add_argument(
        "--home",
        type=Path,
        default=None,
        help="data directory (default: BRAWLFARM_HOME or %%LOCALAPPDATA%%\\brawlfarm)",
    )
    ap.add_argument(
        "--once", action="store_true", help="run one supervisor tick, print the instances, exit"
    )
    ap.add_argument(
        "--interval", type=_positive, default=None, help="seconds between ticks (default 60)"
    )
    ap.add_argument("--no-launch", action="store_true", help="never start a worker (dry run)")
    ap.add_argument("--port", type=int, default=None, help="panel port (default: app.port, 8765)")
    ap.add_argument(
        "--no-browser", action="store_true", help="serve the panel without opening a browser"
    )
    return ap


def _setup_logging(home: Path) -> None:
    logs = home / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S")
    root = logging.getLogger("brawlfarm")
    root.setLevel(logging.INFO)
    root.handlers.clear()
    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(fmt)
    root.addHandler(stream)
    file = RotatingFileHandler(
        logs / "supervisor.log", maxBytes=5_000_000, backupCount=1, encoding="utf-8"
    )
    file.setFormatter(fmt)
    root.addHandler(file)


def _print_table(views) -> None:
    if not views:
        print("no instances configured; add [[instances]] entries to config.toml")
        return
    print(f"{'name':<16}{'port':<8}{'state':<18}{'health':<9}{'pid':<8}{'note'}")
    for v in views:
        until = f" (until {v.until:%H:%M})" if v.until else ""
        print(
            f"{v.name:<16}{v.adb_port:<8}{v.state:<18}{v.health:<9}{v.pid or '-':<8}{v.note}{until}"
        )


def _uvicorn_server(app, port: int):
    """A uvicorn Server, not yet started. Imported here so `brawlfarm --version` and
    `--once` do not pay for the import."""
    import uvicorn

    return uvicorn.Server(
        uvicorn.Config(
            app,
            host="127.0.0.1",  # loopback only; there is no authentication (spec section 3)
            port=port,
            log_level="warning",
            log_config=None,  # keep our handlers; uvicorn's default config replaces them
            access_log=False,
        )
    )


async def _open_later(url: str, delay_s: float, opener) -> None:
    """Give uvicorn a moment to bind before the browser asks for the page."""
    await asyncio.sleep(delay_s)
    try:
        opener(url)
    except Exception as exc:  # a machine with no browser is not an error
        log.warning("could not open a browser: %s", exc)


async def _serve(
    sup,
    app,
    port: int,
    *,
    open_browser: bool,
    make_server=_uvicorn_server,
    browser_open=webbrowser.open,
    delay_s: float = 1.0,
) -> None:
    """Serve the panel and supervise the fleet on one loop. uvicorn owns the signal
    handling: Ctrl+C ends serve(), and only then is the supervisor asked to stop. The final
    await lets a tick already running in its worker thread finish; the workers themselves
    are left alone on purpose."""
    server = make_server(app, port)
    supervising = asyncio.create_task(sup.run_forever())
    browsing = None
    if open_browser:
        browsing = asyncio.create_task(
            _open_later(f"http://127.0.0.1:{port}/", delay_s, browser_open)
        )
    try:
        await server.serve()
    finally:
        if browsing is not None:
            browsing.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await browsing
        sup.request_shutdown()
        await supervising


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(sys.argv[1:] if argv is None else argv)
    if args.version:
        print(f"brawlfarm {__version__}")
        return 0
    home = (args.home or S.default_home()).resolve()
    os.environ["BRAWLFARM_HOME"] = str(home)  # the core reads it at import time
    try:
        home.mkdir(parents=True, exist_ok=True)
    except OSError as exc:  # a path that is a file, a read-only drive, a bad UNC share
        print(f"error: cannot use {home} as the data directory: {exc}", file=sys.stderr)
        return 2
    try:
        settings = S.load(home)
    except S.SettingsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not S.config_path(home).exists():
        S.save(settings, home)
        print(f"wrote default settings to {S.config_path(home)}")
    _setup_logging(home)
    from brawlfarm.supervisor import Supervisor  # after BRAWLFARM_HOME is set

    kwargs = {}
    if args.no_launch:
        kwargs["launcher"] = _dry_launcher
    sup = Supervisor(settings, home, interval_s=args.interval or 60.0, **kwargs)
    if args.once:
        _print_table(sup.tick())
        return 0

    from brawlfarm.api.app import create_app  # pulls in FastAPI; --once must not pay for it

    port = args.port or settings.app.port
    app = create_app(sup, home)
    print(f"brawlfarm {__version__}: panel on http://127.0.0.1:{port}/ (loopback only)")
    print(f"supervising {len(settings.instances)} instance(s) from {home}")
    print("Ctrl+C stops the panel; workers keep running and are reattached on the next start.")
    try:
        asyncio.run(_serve(sup, app, port, open_browser=not args.no_browser))
    except KeyboardInterrupt:  # Ctrl+C before uvicorn installed its own handlers
        sup.request_shutdown()
    except OSError as exc:
        print(f"error: cannot serve on 127.0.0.1:{port}: {exc}", file=sys.stderr)
        return 1
    except SystemExit:
        # uvicorn logs the bind failure and calls sys.exit(1) itself rather than raising.
        print(
            f"error: cannot serve on 127.0.0.1:{port}; is brawlfarm already running?",
            file=sys.stderr,
        )
        return 1
    return 0


class _DryProc:
    pid = 0

    def poll(self):
        return None


def _dry_launcher(args, env, log_dir, name, module=None):
    logging.getLogger("brawlfarm.supervisor").info("%s: dry run, would launch %s", name, args)
    return _DryProc()


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the CLI tests, then serve for real**

```bash
uv run pytest tests/test_cli_serve.py tests/test_cli.py -v
uv run brawlfarm --version
uv run brawlfarm --once --home "$(pwd)/.tmp-home" --no-launch
uv run brawlfarm --home "$(pwd)/.tmp-home" --no-launch --no-browser --port 8799
```

Expected: 4 passed in `tests/test_cli_serve.py`, 7 in `tests/test_cli.py`; `brawlfarm 0.1.0`;
the `--once` run prints "wrote default settings" and "no instances configured". The last
command prints the three panel lines and stays up — in another shell,
`curl -s http://127.0.0.1:8799/api/health` returns the version JSON and
`curl -s http://127.0.0.1:8799/api/events --max-time 20` prints a `: keepalive` frame. Ctrl+C
returns to the prompt with "supervisor loop stopped; workers keep running", then
`rm -rf .tmp-home`.

- [ ] **Step 5: Rewrite the README's Running section**

Replace line 5 with:

```markdown
Status: under construction. Phase 3 of 8 (API and events). The React control panel, setup wizard and stats screens arrive in later phases; see `docs/PLAN.md`.
```

Replace the whole "## Running (headless, until the panel lands in phase 3)" section (lines 37
to 44, up to but not including "## Legal") with:

````markdown
## Running

```
uv run brawlfarm                 # supervise every instance and open the panel
uv run brawlfarm --no-browser    # same, without opening a browser
uv run brawlfarm --port 9000     # serve the panel somewhere else
uv run brawlfarm --once          # one supervisor tick, print the instances, exit
```

Settings live in `%LOCALAPPDATA%\brawlfarm\config.toml` (override the folder with `BRAWLFARM_HOME`). Add one `[[instances]]` table per BlueStacks instance with its `name` and `adb_port`; each instance's files live under `instances/<name>/`. Stopping the process leaves workers running; the next start reattaches to them through their status files.

## The panel and its API

The panel lives at `http://127.0.0.1:8765/`. Change the port in Settings (it takes effect on the next start) or for one run with `--port`. Until the React UI lands in phase 4 the page is a placeholder, and the interesting surface is the API itself, browsable at `http://127.0.0.1:8765/docs`.

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
| GET, PUT | `/api/instances/{name}/plan` | the farm plan: mode, goal, maxed fallback |
| GET, PUT | `/api/instances/{name}/schedule` | today's sessions, the override, on/off, redraw |
| GET | `/api/instances/{name}/feed` | session narration, `kind=all\|matches\|interrupts\|errors` |
| GET | `/api/stats` | `range=today\|7d\|30d\|all`, `instances=a,b` |
| GET | `/api/stats/export.csv` | the same selection as a CSV download |
| GET, PUT | `/api/settings` | the whole `config.toml` document |
| POST | `/api/setup/scan` | find adb and the BlueStacks instances |
| POST | `/api/setup/test` | can adb reach this port |
| POST | `/api/setup/display-check` | is this instance 1600 x 900 at DPI 240 |
| GET | `/api/alerts` | the alert list and its unread count |
| POST | `/api/alerts/{id}/dismiss` | mark one alert read |
| GET | `/api/events` | server-sent events |

### Live events

`GET /api/events` is a server-sent event stream with four kinds: `instance` (a state change), `feed` (a new session narration line), `alert`, and `log` (the supervisor's own log lines). It replays from `Last-Event-ID` on a reconnect and sends a keepalive comment every 15 seconds. Alerts are kept in memory only, so a restart clears them; the session files under `instances/<name>/` keep the history.

### Notifications and health monitoring

`[notifications]` in `config.toml` takes a webhook URL, an ntfy topic and server, the list of event kinds worth sending, and `healthchecks_url`. Every completed supervisor tick GETs that URL, so a supervisor that stops ticking raises an alarm on healthchecks.io — or anything else that speaks the same one-URL protocol — without you watching the window.
````

- [ ] **Step 6: Point the board at this plan**

In `docs/PLAN.md`, replace the "In flight" line (line 12) with:

```markdown
- Phase 3: API and events. Plan: `docs/superpowers/plans/2026-09-10-phase-3-api-and-events.md`. PR: (link once opened).
```

- [ ] **Step 7: Run everything and check the whole surface**

```bash
uv run pytest -q
uv run ruff format brawlfarm/__main__.py tests/test_cli.py tests/test_cli_serve.py
uv run ruff check . && uv run ruff format --check .
uv run python tools/scrub_check.py
```

Expected: the full suite green with no warnings (416 tests before phase 3, plus this phase's);
`ruff check` prints `All checks passed!`; `ruff format --check` reports every file already
formatted; the scrub check prints `0 hit(s)`.

- [ ] **Step 8: Commit, push, open the pull request**

```bash
git config user.name    # must print as9pa before committing
git add brawlfarm/__main__.py tests/test_cli.py tests/test_cli_serve.py README.md docs/PLAN.md
git commit -m "feat(cli): brawlfarm serves the panel and the supervisor together

One process, one loop: uvicorn on 127.0.0.1 with the supervisor task
beside it, and the browser opened on the panel unless --no-browser.
Closes the phase 2 CLI deferrals: --no-launch's help text covers both
modes, --interval must be greater than 0, and an unwritable --home exits
2 with one line instead of a traceback."
git push -u origin phase-3/api-and-events
gh pr create --base main --title "Phase 3: API and events" --body-file /dev/stdin <<'EOF'
## What and why
FastAPI on 127.0.0.1 in front of the phase 2 supervisor: every route in spec section 7, one server-sent event stream for state changes, feed lines, alerts and log lines, and the `setup/` package the wizard needs. `uv run brawlfarm` now serves the panel and supervises the fleet on one asyncio loop and opens the browser. Phase 3 of the approved build plan; the React UI is phase 4.

## Risk tier
T2 (runtime behaviour: the API drives the supervisor's start, stop, kill and restart controls, and runs adb screencaps). Safety rails: never-tap logic, verify-then-act and the 1600 x 900 assertion untouched; kill is still by PID from `status.json` only; adb serials are built from validated integer ports; instance names are validated before they become folder names.

## Safety-rail checklist
- [ ] No tap coordinate, OCR needle or core loop edited (`core/controller.py`, `core/states.py`, `core/vision.py`, `core/config.py` calibration block unchanged).
- [ ] Every subprocess call is an argument list with `shell=False`; instance names validated `[A-Za-z0-9_-]{1,32}`; adb serial built from an integer port.
- [ ] No process is found by name; kill only by the PID read from that instance's `status.json`.
- [ ] The API binds 127.0.0.1 only and refuses non-loopback clients with 403; there is no authentication by design (spec section 3) and the README says so.
- [ ] No `discord` import; scrub check green; no player tag, account nickname or token in the diff.

## Evidence
(paste: pytest summary line, scrub check output, CI run URL, `curl /api/health` output, a `/api/events` frame, a Fleet-state transition seen on the stream)

## Docs
README gains a Running section, the full API table, the live-events and notifications notes, and the phase 3 status; `docs/PLAN.md` links this plan and this PR.

## Rollback
Revert the merge commit; nothing outside this repo changes. Workers started by a supervisor run keep running and are reattached by any later start, so a revert never orphans one.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01CQ1GimQ3uiR2sXPzfZLNWV
EOF
```

Then put the PR URL into `docs/PLAN.md`'s phase 3 line, commit
`docs: link the phase 3 pull request from the plan board`, push, and once CI is green edit the
PR body's Evidence section with the real outputs (`gh pr edit --body-file`). Report the PR URL
and the CI run URL.

---
