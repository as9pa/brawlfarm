# Phase 9 Observe Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship observe-only recording in full, so the owner can play by hand while a process captures and labels every screen, and land the two pure functions that the quest-aware pick and the auto-upgrade gate are built on. Nothing here taps, nothing here adds a coordinate, and nothing here amends a safety rail.

**Architecture:** A new `brawlfarm/core/observer.py` holds an `Observer` class with its own loop: `adb.connect`, the 1600x900 assertion, then screencap, preview, `states.classify(screen, phase=None)`, `Recorder.observe(screen, state, "observe")`, a `status.json` heartbeat carrying `mode: "observe"`, and a `stop.flag` check. It raises `record.flag` itself on the way in and drops it on the way out, including on an exception, so the owner flips one switch. It runs as `python -m brawlfarm.worker --observe`, which puts it in the one worker slot per instance that the supervisor already guards, so a farming worker and an observer can never share a display. The supervisor gains a third desired mode, `observe`, carried by the same override file `/start` and `/stop` already write. `POST /api/instances/{name}/observe` writes that override and refuses with 409 while the instance is live. The Calibration page gets a second switch beside the recorder's. `questpick.py` and `upgrade_gate.py` are pure modules with no adb, no config and no screen read.

**Tech Stack:** Python 3.13, uv, FastAPI, pydantic, numpy, OpenCV, pytest, ruff; React 19, TypeScript strict, Tailwind v4, TanStack Query, vitest, pnpm.

**Spec:** `docs/superpowers/specs/2026-09-13-phase-9-design.md`

## Global Constraints

- Never edit never-tap logic, tap coordinates, OCR needles or templates in `brawlfarm/core/controller.py`, `states.py`, `vision.py` or `config.py`. No task below opens any of those four files.
- `brawlfarm/core/observer.py` must never import `controller`, `brawlers`, `quests`, `rewards` or `core/settings`, and must never reference `adb.tap`, `adb.swipe`, `adb.tap_hold`, `adb.input_text`, `adb.keyevent`, `adb.go_home`, `adb.launch_app` or `adb.force_stop`. Task 5 pins both rails in CI.
- One worker per instance. Observe mode occupies the same `status.json` PID slot the supervisor guards with `_ensure_gone`, `_kill_hung_launch` and `process.is_worker`; no second lock is invented.
- `POST /api/instances/{name}/observe` returns 409 unless the instance is stopped, and writes no override file when it refuses.
- `Recorder.MAX_FRAMES` stays 2000. A session that hits the cap ends; the owner starts another.
- The gate before every commit, from the repo root: `pnpm typecheck`, `pnpm test`, `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, and `uv run python tools/scrub_check.py` printing `0 hit(s)`. Web commands run from `brawlfarm/web`.
- Conventional commits, written with `git commit -F <file>` (message file in the scratchpad), ending with exactly one trailer line: `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- No em-dashes and no emoji in prose, docs, comments or commit messages.
- No absolute local path in any file, in any test, or in any doc. The legacy checkout is read-only reference and its path, tags and nicknames are never written anywhere.
- No `discord` import. Never log or print the API token or the player tag.

**Corrections to the spec, found against the real code.** The spec guessed a few names; these are the real ones and this plan uses them.

- The spec's "status" module is `brawlfarm/core/status.py` with `write_status(data_dir, fields)` and `read_status(data_dir)`. There is no status class.
- `Recorder.__init__(root, instance, flag, *, clock, wall)`. The controller builds it as `Recorder(config.HOME_DIR / "calibration", config.DATA_DIR.name, config.DATA_DIR / "record.flag")`, so recordings land under `<home>/calibration/recordings/<instance>/`, not under the instance folder. The observer builds it identically.
- The spec's feature 3 module name `upgrade.py` is reserved for the state machine that needs captures. The pure gate ships as `brawlfarm/core/upgrade_gate.py` so the two never share a file, and so no module named `upgrade` exists before the never-tap amendment does.
- `brawlers._norm` exists at `brawlfarm/core/brawlers.py:146` and is private. `questpick` keeps its own `norm_name` with the same rule and a test that pins the two together, rather than importing a private symbol out of a module that also holds tap paths.
- The spec says a third desired mode "alongside run and stop". `scheduler.evaluate` is the function that turns an override into a desired block, so `brawlfarm/core/scheduler.py` is modified too, not only `state.py` and `loop.py`.
- `InstanceState` gains no member. An observing instance reads as `FARMING` (alive) or `STARTING` (launching), which keeps it inside `deps.LIVE_STATES` so the delete-data and drop-instance guards still protect it, and keeps every `InstanceState` consumer in the panel unchanged. The panel tells observe apart from farming with `InstancePayload.desired === "observe"` and the recorder payload's new `mode` field.

---

### Task 1: The Observer class, its loop and the record.flag lifecycle

**Files:**
- Create: `brawlfarm/core/observer.py`
- Test: `tests/test_observer.py`

**Interfaces:**
- Consumes: `adb.connect()`, `adb.screen_size() -> tuple[int, int]`, `adb.screencap() -> np.ndarray`, `adb.AdbError`, `preview.maybe_write(screen) -> bool`, `states.classify(screen, phase=None) -> State`, `status.write_status(data_dir, fields) -> None`, `Recorder(root, instance, flag)` with `.poll()`, `.observe(screen, state, phase) -> bool`, `.status() -> dict`, `.close()`, `config.HOME_DIR`, `config.DATA_DIR`, `config.SCREEN_W`, `config.SCREEN_H`, `config.ADB_PORT`.
- Produces: `Observer(*, max_minutes: float | None = None)` with `.run() -> None`, `.frames: int`, `.recorder: Recorder`; module constants `POLL_INTERVAL_S`, `STATUS_EVERY`, `ADB_ERROR_LIMIT`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_observer.py
"""Observe mode: the loop records labeled frames off a fake adb that cannot tap, keeps
record.flag for exactly as long as it runs, refuses a display that is not 1600x900, and
stops on stop.flag. No real device, no real screencap, no tap function anywhere."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from brawlfarm.core import adb, config, observer


def _frame() -> np.ndarray:
    return np.zeros((config.SCREEN_H, config.SCREEN_W, 3), np.uint8)


@pytest.fixture()
def data(tmp_path: Path, monkeypatch) -> Path:
    """An instance folder under a throwaway home, with adb faked out entirely."""
    inst = tmp_path / "instances" / "alpha"
    inst.mkdir(parents=True)
    monkeypatch.setattr(config, "HOME_DIR", tmp_path)
    monkeypatch.setattr(config, "DATA_DIR", inst)
    monkeypatch.setattr(observer, "POLL_INTERVAL_S", 0.0)
    monkeypatch.setattr(adb, "connect", lambda serial=None: None)
    monkeypatch.setattr(adb, "screen_size", lambda: (config.SCREEN_W, config.SCREEN_H))
    monkeypatch.setattr(adb, "screencap", lambda serial=None: _frame())
    return inst


def test_one_pass_records_a_frame_and_leaves_no_flag(data: Path, tmp_path: Path) -> None:
    obs = observer.Observer(max_minutes=0.0)  # the cap is checked after the first frame
    obs.run()
    assert obs.frames == 1
    assert not (data / "record.flag").exists()
    sessions = sorted((tmp_path / "calibration" / "recordings" / "alpha").iterdir())
    assert len(sessions) == 1
    assert (sessions[0] / "labels.jsonl").read_text(encoding="utf-8").count("\n") == 1


def test_the_heartbeat_names_the_mode(data: Path) -> None:
    observer.Observer(max_minutes=0.0).run()
    from brawlfarm.core import status

    heartbeat = status.read_status(data)
    assert heartbeat is not None
    assert heartbeat["mode"] == "observe"
    assert heartbeat["phase"] == "observing"
    assert heartbeat["running"] is False


def test_stop_flag_ends_the_session(data: Path, monkeypatch) -> None:
    seen: list[int] = []

    def screencap(serial=None):
        seen.append(1)
        if len(seen) == 2:  # a leftover flag is cleared at startup, so raise it mid-loop
            (data / "stop.flag").write_text("stop\n", encoding="utf-8")
        return _frame()

    monkeypatch.setattr(adb, "screencap", screencap)
    observer.Observer().run()
    assert len(seen) == 2
    assert not (data / "record.flag").exists()


def test_a_display_that_is_not_1600x900_never_starts(data: Path, monkeypatch) -> None:
    monkeypatch.setattr(adb, "screen_size", lambda: (1280, 720))
    with pytest.raises(SystemExit, match="1280x720"):
        observer.Observer().run()
    assert not (data / "record.flag").exists()


def test_an_exception_still_clears_the_flag(data: Path, monkeypatch) -> None:
    def boom(serial=None):
        raise RuntimeError("device gone")

    monkeypatch.setattr(adb, "screencap", boom)
    with pytest.raises(RuntimeError):
        observer.Observer().run()
    assert not (data / "record.flag").exists()
```

- [ ] **Step 2: Run the tests and watch them fail**

```
uv run pytest tests/test_observer.py -q
```

Expect a collection error: `ModuleNotFoundError: No module named 'brawlfarm.core.observer'`.

- [ ] **Step 3: Implement**

```python
# brawlfarm/core/observer.py
"""Observe-only recording: the owner plays by hand while this process watches.

The loop screencaps, writes the panel's preview frame, classifies the frame and hands it
to the same Recorder the farm uses, so the next recalibration corpus comes from real play
instead of from the bot's own narrow path through the game.

It imports adb for connect, screencap and screen_size and nothing that touches the screen:
controller, brawlers, quests, rewards and core/settings are all outside its import graph,
so no tap function is reachable from here and tests/test_observer.py asserts exactly that.

It runs as ``python -m brawlfarm.worker --observe``, which puts it in the one worker slot
per instance the supervisor already guards, so an observer and a farming worker can never
drive one display at the same time. Observe mode is recording by definition, so it raises
record.flag itself and drops it on the way out, including when the loop raises: one switch
for the owner, not two.
"""

from __future__ import annotations

import logging
import os
import time

from brawlfarm.core import adb, config, preview, states, status
from brawlfarm.core.recorder import Recorder

log = logging.getLogger("brawlfarm.core.observer")

POLL_INTERVAL_S = 0.5  # about two frames a second; the recorder keeps at most one
STATUS_EVERY = 10  # heartbeat and flag poll roughly every five seconds
ADB_ERROR_LIMIT = 8  # the same streak the farm loop tolerates before it gives up

RECORD_FLAG = "record.flag"
STOP_FLAG = "stop.flag"
# Recorder reasons that mean the session is over for good. Nothing is left to record
# after one of these, so the loop stops instead of spinning on a closed session.
_SPENT = ("frame_cap", "disk_cap", "error")


class Observer:
    """Watch one instance and record labeled frames until stop.flag or a cap."""

    def __init__(self, *, max_minutes: float | None = None) -> None:
        self.max_minutes = max_minutes
        self.frames = 0
        self.start = time.monotonic()
        self.recorder = Recorder(
            config.HOME_DIR / "calibration", config.DATA_DIR.name, config.DATA_DIR / RECORD_FLAG
        )

    # --- the flag the owner never has to touch ------------------------------------

    def _set_record_flag(self) -> None:
        flag = config.DATA_DIR / RECORD_FLAG
        try:
            flag.parent.mkdir(parents=True, exist_ok=True)
            flag.touch()
        except OSError as exc:
            log.warning("record.flag not raised: %s", getattr(exc, "strerror", None) or exc)

    def _clear_record_flag(self) -> None:
        try:
            (config.DATA_DIR / RECORD_FLAG).unlink(missing_ok=True)
        except OSError:
            pass

    # --- the heartbeat ------------------------------------------------------------

    def _write_status(self, *, running: bool = True) -> None:
        """The same status.json slot a farming worker writes, so the supervisor sees one
        process per instance whichever kind it is. ``mode`` is what tells them apart."""
        status.write_status(
            config.DATA_DIR,
            {
                "pid": os.getpid(),
                "running": running,
                "mode": "observe",
                "phase": "observing",
                "frames": self.frames,
                "minutes_elapsed": round((time.monotonic() - self.start) / 60, 1),
                "max_minutes": self.max_minutes,
                "port": config.ADB_PORT,
            },
        )

    # --- the loop -----------------------------------------------------------------

    def _done(self) -> bool:
        try:
            if (config.DATA_DIR / STOP_FLAG).exists():
                return True
        except OSError:
            pass
        if self.max_minutes is not None:
            if (time.monotonic() - self.start) / 60 >= self.max_minutes:
                return True
        return self.recorder.status()["reason"] in _SPENT

    def run(self) -> None:
        adb.connect()
        w, h = adb.screen_size()
        if (w, h) != (config.SCREEN_W, config.SCREEN_H):
            raise SystemExit(
                f"Display is {w}x{h}, expected {config.SCREEN_W}x{config.SCREEN_H}. "
                f"Lock BlueStacks resolution before recording."
            )
        # A leftover stop.flag belongs to the worker that stopped before this one, and
        # whoever launched us wants us running.
        try:
            (config.DATA_DIR / STOP_FLAG).unlink(missing_ok=True)
        except OSError:
            pass
        self._set_record_flag()
        self.recorder.poll()
        self._write_status()
        log.info("observing; turn the switch off to end the session")
        errors = 0
        i = 0
        try:
            while True:
                try:
                    screen = adb.screencap()
                    errors = 0
                except adb.AdbError as exc:
                    errors += 1
                    log.warning("adb error (streak %d): %s", errors, exc)
                    if errors >= ADB_ERROR_LIMIT:
                        raise
                    time.sleep(POLL_INTERVAL_S)
                    continue
                preview.maybe_write(screen)
                # No farm phase to hint with, and PHASE_ORDER only reorders anchors: it
                # never changes the label a frame gets.
                state = states.classify(screen, phase=None)
                if self.recorder.observe(screen, state, "observe"):
                    self.frames += 1
                i += 1
                if i % STATUS_EVERY == 0:
                    self._write_status()
                    self.recorder.poll()
                if self._done():
                    break
                time.sleep(POLL_INTERVAL_S)
        finally:
            self._clear_record_flag()
            self.recorder.close()
            self._write_status(running=False)
            log.info("observe session ended after %d frames", self.frames)
```

- [ ] **Step 4: Run the tests and watch them pass**

```
uv run pytest tests/test_observer.py -q
```

- [ ] **Step 5: Commit**

```
git add brawlfarm/core/observer.py tests/test_observer.py
git commit -F <scratchpad>/msg-task1.txt
```

Message file contents:

```
feat(core): observe-only recording loop that never taps

Observer watches one instance while the owner plays, classifies every
frame and feeds the existing Recorder. It imports adb only for connect,
screencap and screen_size, raises record.flag itself and drops it on
every exit path, and keeps the 1600x900 assertion the farm loop has.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
```

---

### Task 2: The --observe flag on the worker and the worker_args branch

**Files:**
- Modify: `brawlfarm/worker.py` (module docstring lines 1 to 13, the imports at lines 15 to 18, the argument block at lines 21 to 46, the construction at lines 54 to 62)
- Modify: `brawlfarm/settings.py` (`worker_args`, lines 233 to 241)
- Test: `tests/test_settings.py` (next to `test_worker_args_follow_dnd_and_cap` at line 191), `tests/test_core_imports.py` (`test_worker_help_runs` at the tail)

**Interfaces:**
- Consumes: `Observer(*, max_minutes)` from task 1.
- Produces: `worker_args(settings: AppSettings, max_minutes: float | None, *, observe: bool = False) -> list[str]`, and `python -m brawlfarm.worker --observe`. Task 3 calls `worker_args` with `observe=`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_settings.py, directly under test_worker_args_follow_dnd_and_cap
def test_worker_args_for_observe_carry_nothing_that_plays() -> None:
    s = build_settings()
    s.behavior.dnd_at_start = True
    assert S.worker_args(s, None, observe=True) == ["--observe"]
    assert S.worker_args(s, 42.7, observe=True) == ["--observe"]
```

Use whatever settings builder the neighbouring test already uses; match its local name rather than introducing `build_settings` if that file builds its `s` some other way.

```python
# tests/test_core_imports.py, directly under test_worker_help_runs
def test_worker_help_lists_observe() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "brawlfarm.worker", "--help"], capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "--observe" in result.stdout
```

- [ ] **Step 2: Run the tests and watch them fail**

```
uv run pytest tests/test_settings.py tests/test_core_imports.py -q
```

Expect `TypeError: worker_args() got an unexpected keyword argument 'observe'` and an assertion failure on `--observe`.

- [ ] **Step 3: Implement**

In `brawlfarm/worker.py`, extend the module docstring with the new mode, import the Observer, add the flag, and branch before the Controller is built:

```python
    uv run python -m brawlfarm.worker --observe       # record while you play, never taps
```

```python
from brawlfarm.core.controller import Controller
from brawlfarm.core.observer import Observer
```

```python
    ap.add_argument(
        "--observe",
        action="store_true",
        help="record while you play: capture and label frames, never tap. Ignores every "
        "other startup flag.",
    )
```

```python
    # Observe mode plays nothing, so it takes none of the startup tasks: it only watches.
    if args.observe:
        Observer(max_minutes=args.max_minutes).run()
        return 0

    # --startup-all is a convenience that turns on every startup task at once.
    startup = args.startup_all
```

In `brawlfarm/settings.py`:

```python
def worker_args(
    settings: AppSettings, max_minutes: float | None, *, observe: bool = False
) -> list[str]:
    """CLI flags for ``python -m brawlfarm.worker``: brawler selection always, DND when
    the behaviour setting says so, and the scheduler's session cap when there is one.

    Observe mode is the exception and takes the flag alone: it never plays, so a startup
    task that would touch the game has no business in its command line."""
    if observe:
        return ["--observe"]
    args = ["--select-brawler"]
    if settings.behavior.dnd_at_start:
        args.append("--dnd")
    if max_minutes is not None:
        args += ["--max-minutes", f"{max_minutes:g}"]
    return args
```

- [ ] **Step 4: Run the tests and watch them pass**

```
uv run pytest tests/test_settings.py tests/test_core_imports.py -q
```

- [ ] **Step 5: Commit**

```
git add brawlfarm/worker.py brawlfarm/settings.py tests/test_settings.py tests/test_core_imports.py
git commit -F <scratchpad>/msg-task2.txt
```

```
feat(worker): --observe launches the observer instead of the controller

The flag takes no startup task with it and worker_args returns it alone,
so an observe launch carries no --select-brawler and no --dnd.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
```

---

### Task 3: Observe as a third supervisor desired mode

**Files:**
- Modify: `brawlfarm/core/scheduler.py` (`evaluate`, the disabled-branch override check at lines 507 to 515 and the enabled-branch override block at lines 527 to 538)
- Modify: `brawlfarm/supervisor/state.py` (`InstanceView.desired` comment at line 41, `derive_state` docstring and its dead-branch test at lines 97 to 101)
- Modify: `brawlfarm/supervisor/loop.py` (`_launch_worker` at lines 327 to 338, and a new `observe` control next to `stop` at lines 356 to 361)
- Test: `tests/test_supervisor_loop.py`

**Interfaces:**
- Consumes: `S.worker_args(settings, max_minutes, observe=...)` from task 2, `scheduler.write_override(name, mode, until)`, `scheduler.read_override(name) -> dict | None`.
- Produces: desired blocks with `state == "observe"` and `reason == "override_observe"`; `Supervisor.observe(name: str, on: bool) -> None`. Task 4 calls `sup.observe`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_supervisor_loop.py, appended
def test_observe_override_launches_the_worker_with_observe(sup, world, tmp_path) -> None:
    sup.observe("Pie64", True)
    assert (scheduler.read_override("Pie64") or {})["mode"] == "observe"
    world.now += timedelta(seconds=L.BOOT_GRACE_S + 20)
    sup.tick()
    args = [a for a, _env, n in world.launches if n == "Pie64"][-1]
    assert args == ["--observe"]
    assert "--select-brawler" not in args and "--dnd" not in args


def test_observe_does_not_read_as_a_scheduled_break(sup, world, tmp_path) -> None:
    sup.observe("Pie64", True)
    views = sup.tick()
    view = _view(views, "Pie64")
    assert view.desired == "observe"
    assert view.state == InstanceState.STARTING


def test_observe_off_is_the_ordinary_stop(sup, world, tmp_path) -> None:
    sup.observe("Pie64", True)
    sup.observe("Pie64", False)
    assert (scheduler.read_override("Pie64") or {})["mode"] == "stop"
    assert (S.instance_dir(tmp_path, "Pie64") / "stop.flag").exists()
```

- [ ] **Step 2: Run the tests and watch them fail**

```
uv run pytest tests/test_supervisor_loop.py -q
```

Expect `AttributeError: 'Supervisor' object has no attribute 'observe'`.

- [ ] **Step 3: Implement**

In `brawlfarm/core/scheduler.py`, `evaluate`, the disabled branch. Replace the stop-only check with one that also honours observe (the comment above it stays, with the second sentence extended):

```python
        # A STOP or OBSERVE override is honored even with scheduling off (v3.1 #5):
        # /stop writes one so the watchdog doesn't relaunch ~1 min later (found live
        # 2026-06-10), and observe mode is a manual state the schedule knows nothing
        # about. Run overrides are meaningless here (disabled = always-run) and
        # malformed/expired ones were already pruned by the caller.
        if override and override.get("mode") in ("stop", "observe"):
            mode = str(override["mode"])
            try:
                return block(mode, f"override_{mode}", _iso(_parse(override["until"])))
            except (KeyError, ValueError):
                pass
```

And in the enabled branch, above the final stop return inside `if now < until:`:

```python
            if override.get("mode") == "observe":
                return block("observe", "override_observe", override["until"])
            return block("stop", "override_stop", override["until"])
```

In `brawlfarm/supervisor/state.py`, widen the field comment and the dead-branch test:

```python
    desired: str  # "run" | "stop" | "observe"
```

```python
    if booting or desired in ("run", "observe"):
        return InstanceState.STARTING
```

Add one sentence to `derive_state`'s docstring after the precedence line:

```
    ``observe`` is a desired mode, not a state: an observing instance reads as STARTING
    then FARMING, which keeps it inside the panel's live-instance guards. The recorder
    payload's ``mode`` field is what says which kind of worker is running.
```

In `brawlfarm/supervisor/loop.py`, `_launch_worker`:

```python
    def _launch_worker(self, inst: S.InstanceSettings, desired: dict | None, now: datetime) -> None:
        max_minutes = (desired or {}).get("max_minutes")
        observe = (desired or {}).get("state") == "observe"
        args = S.worker_args(
            self.settings, float(max_minutes) if max_minutes else None, observe=observe
        )
```

and a new control directly under `stop`:

```python
    def observe(self, name: str, on: bool) -> None:
        """Observe mode on: an observe override, so the next tick launches the worker with
        --observe. Off: the ordinary graceful stop, because an observer that is no longer
        wanted is just a worker to stop."""
        now = self._clock()
        self.settings.instance(name)
        if not on:
            self.stop(name)
            return
        scheduler.write_override(name, "observe", now + timedelta(days=STOP_OVERRIDE_DAYS))
        self._flag(name).unlink(missing_ok=True)
        self._stop_asked.pop(name, None)
        self._backoff.clear(name)
        self.poke()
```

- [ ] **Step 4: Run the tests and watch them pass**

```
uv run pytest tests/test_supervisor_loop.py tests/test_scheduler.py tests/test_supervisor_state.py tests/test_stop_override_disabled.py -q
```

- [ ] **Step 5: Commit**

```
git add brawlfarm/core/scheduler.py brawlfarm/supervisor/state.py brawlfarm/supervisor/loop.py tests/test_supervisor_loop.py
git commit -F <scratchpad>/msg-task3.txt
```

```
feat(supervisor): observe as a third desired mode

An observe override rides the same file /start and /stop write, so the
one-worker-per-instance rule covers observe mode for free. The launch
carries --observe and nothing else. InstanceState is unchanged: an
observing instance still reads as live, so every guard that protects a
running instance protects it too.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
```

---

### Task 4: The observe route and the recorder payload's mode field

**Files:**
- Modify: `brawlfarm/api/instances.py` (the `StartBody` block at lines 36 to 42, and a new route under `stop_instance` at lines 159 to 167)
- Modify: `brawlfarm/api/calibration.py` (`_recorder_payload` at lines 59 to 82, a new `_mode_of` next to `_phase_of` at lines 84 to 91)
- Test: `tests/test_api_observe.py` (create), `tests/test_api_calibration.py` (`test_recorder_routes` at line 155 gains the new key)

**Interfaces:**
- Consumes: `Supervisor.observe(name, on)` from task 3, `deps.LIVE_STATES`, `deps.resolve_instance`, `deps.get_sup`, `deps.get_home`.
- Produces: `POST /api/instances/{name}/observe` with body `{"on": bool}`, 202 `{"ok": true}` or 409; `GET|POST /api/instances/{name}/recorder` payloads gain `"mode": "farm" | "observe"`. Task 6 consumes both.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_api_observe.py
"""The observe route: it only starts from stopped, it writes the observe override, and
turning it off is the ordinary stop. Nothing here launches a process or talks to adb."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

from brawlfarm import settings as S
from brawlfarm.core import scheduler
from brawlfarm.supervisor.loop import BOOT_GRACE_S
from tests.apihelpers import FakeWorld, make_client


@pytest.fixture()
def api(tmp_path: Path):
    world = FakeWorld()
    client, sup, home = make_client(tmp_path, ("alpha", "bravo"), world=world)
    try:
        yield client, sup, home, world
    finally:
        client.__exit__(None, None, None)


def _park(client, sup, name: str) -> None:
    """Stop the instance the startup tick launched, so the route's guard is satisfied."""
    client.post(f"/api/instances/{name}/stop")
    sup.tick()


def test_observe_refuses_a_running_instance_and_writes_nothing(api) -> None:
    client, sup, _home, _world = api
    name = sup.settings.instances[0].name
    r = client.post(f"/api/instances/{name}/observe", json={"on": True})
    assert r.status_code == 409
    assert scheduler.read_override(name) is None


def test_observe_on_writes_the_override_and_launches_with_observe(api) -> None:
    client, sup, _home, world = api
    name = sup.settings.instances[0].name
    _park(client, sup, name)
    r = client.post(f"/api/instances/{name}/observe", json={"on": True})
    assert r.status_code == 202 and r.json() == {"ok": True}
    assert (scheduler.read_override(name) or {})["mode"] == "observe"
    world.now += timedelta(seconds=BOOT_GRACE_S + 20)
    sup.tick()
    assert [a for a, _env, n in world.launches if n == name][-1] == ["--observe"]


def test_observe_off_stops_it(api) -> None:
    client, sup, home, _world = api
    name = sup.settings.instances[0].name
    _park(client, sup, name)
    client.post(f"/api/instances/{name}/observe", json={"on": True})
    assert client.post(f"/api/instances/{name}/observe", json={"on": False}).status_code == 202
    assert (scheduler.read_override(name) or {})["mode"] == "stop"
    assert (S.instance_dir(home, name) / "stop.flag").exists()


def test_observe_404s_an_unknown_instance(api) -> None:
    client, _sup, _home, _world = api
    assert client.post("/api/instances/Nope/observe", json={"on": True}).status_code == 404


def test_observe_rejects_a_body_with_anything_else_in_it(api) -> None:
    client, sup, _home, _world = api
    name = sup.settings.instances[0].name
    r = client.post(f"/api/instances/{name}/observe", json={"on": True, "hours": 2})
    assert r.status_code == 422
```

```python
# tests/test_api_calibration.py, appended
def test_recorder_payload_names_the_mode(api) -> None:
    client, sup, home = api
    name = sup.settings.instances[0].name
    inst = S.instance_dir(home, name)
    assert client.get(f"/api/instances/{name}/recorder").json()["mode"] == "farm"
    inst.mkdir(parents=True, exist_ok=True)
    (inst / "status.json").write_text(json.dumps({"mode": "observe"}), encoding="utf-8")
    assert client.get(f"/api/instances/{name}/recorder").json()["mode"] == "observe"
```

And in the existing `test_recorder_routes`, the exact-equality dict at line 160 gains one key:

```python
        "last_frames": 0,
        "flag": False,
        "mode": "farm",
    }
```

- [ ] **Step 2: Run the tests and watch them fail**

```
uv run pytest tests/test_api_observe.py tests/test_api_calibration.py -q
```

Expect 405s from the missing route and a `KeyError: 'mode'`.

- [ ] **Step 3: Implement**

In `brawlfarm/api/instances.py`, next to `StartBody`:

```python
class ObserveBody(BaseModel):
    """Observe mode's switch, and nothing else: this route cannot start a farm."""

    model_config = ConfigDict(extra="forbid")

    on: bool
```

and the route directly under `stop_instance`:

```python
@router.post("/api/instances/{name}/observe", status_code=202)
async def observe_instance(request: Request, name: str, body: ObserveBody) -> dict:
    """Record while the owner plays: write the observe override so the next tick launches
    the worker with --observe. Turning it off is the ordinary graceful stop.

    409 while the instance is doing anything else. Handing a live instance straight from
    farming to observing would put two processes on one display during the handoff, so the
    owner stops it first and turns this on from stopped. A second on for an instance that
    is already observing is not a handoff, so it passes.
    """
    inst, _dir = resolve_instance(request, name)
    sup = get_sup(request)
    view = next((v for v in sup.views() if v.name == inst.name), None)
    live = view is not None and view.state in LIVE_STATES and view.desired != "observe"
    if body.on and live:
        raise HTTPException(status_code=409, detail=f"Stop {inst.name} before recording play")
    sup.observe(inst.name, body.on)
    sup.poke()
    return {"ok": True}
```

In `brawlfarm/api/calibration.py`, add to the `_recorder_payload` default dict and its return, and a reader beside `_phase_of`:

```python
    status["flag"] = (inst / "record.flag").exists()
    status["mode"] = _mode_of(inst)
    return status


def _mode_of(inst: Path) -> str:
    """Which kind of worker is recording here. Only an instance whose own heartbeat says
    ``observe`` is observing; no heartbeat, an unreadable one or anything else is "farm",
    which is the answer that makes the page's switch stay disabled rather than inviting a
    click that the observe route would refuse."""
    try:
        data = json.loads((inst / "status.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "farm"
    mode = data.get("mode") if isinstance(data, dict) else None
    return "observe" if mode == "observe" else "farm"
```

Extend the `_recorder_payload` docstring with one sentence: `mode comes from status.json, not from recorder.json, because it is the worker that knows which kind it is.`

- [ ] **Step 4: Run the tests and watch them pass**

```
uv run pytest tests/test_api_observe.py tests/test_api_calibration.py tests/test_api_app.py -q
```

- [ ] **Step 5: Commit**

```
git add brawlfarm/api/instances.py brawlfarm/api/calibration.py tests/test_api_observe.py tests/test_api_calibration.py
git commit -F <scratchpad>/msg-task4.txt
```

```
feat(api): observe route and the recorder mode field

POST /api/instances/{name}/observe writes the observe override and
refuses with 409 unless the instance is stopped, so a farm is never
handed to an observer in one call. The recorder payload gains a mode
field read from the instance heartbeat.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
```

---

### Task 5: The import rail and the no-tap rail

**Files:**
- Modify: `tests/test_observer.py` (append a rails section)
- Modify: `tests/test_core_imports.py` (`MODULES`, lines 13 to 37)

**Interfaces:**
- Consumes: `brawlfarm/core/observer.py` as a source file and as a subprocess import.
- Produces: no runtime symbol. Two CI assertions.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_observer.py, appended
# --- the rails ------------------------------------------------------------------------
#
# Observe mode's whole safety argument is that no tap function is reachable from it. Both
# halves of that are checked here: the source names no input call, and importing the
# module pulls in nothing that owns one. A future edit that breaks either CANNOT land
# green, which is the point, so treat a failure here as a design question and not a test
# to fix.

NO_INPUT = (
    "adb.tap",
    "adb.swipe",
    "adb.tap_hold",
    "adb.input_text",
    "adb.keyevent",
    "adb.go_home",
    "adb.launch_app",
    "adb.force_stop",
)

FORBIDDEN_MODULES = (
    "brawlfarm.core.controller",
    "brawlfarm.core.brawlers",
    "brawlfarm.core.quests",
    "brawlfarm.core.rewards",
    "brawlfarm.core.settings",
)


def test_the_observer_source_names_no_input_call() -> None:
    source = Path(observer.__file__).read_text(encoding="utf-8")
    named = [call for call in NO_INPUT if call in source]
    assert named == [], f"observer.py must never tap: {named}"


def test_importing_the_observer_pulls_in_nothing_that_taps(tmp_path: Path) -> None:
    import os
    import subprocess
    import sys

    env = {k: v for k, v in os.environ.items() if not k.startswith(("BRAWL_", "DISCORD_"))}
    env["BRAWLFARM_HOME"] = str(tmp_path)
    code = (
        "import sys; import brawlfarm.core.observer; "
        f"bad = [m for m in {FORBIDDEN_MODULES!r} if m in sys.modules]; "
        "assert not bad, bad"
    )
    result = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
```

Add `from pathlib import Path` to the file's imports if the earlier tasks' tests did not already.

```python
# tests/test_core_imports.py, in MODULES, alphabetically between notify and preview
    "observer",
```

- [ ] **Step 2: Run the tests and watch them fail**

```
uv run pytest tests/test_observer.py tests/test_core_imports.py -q
```

If task 1 was implemented as written both rails pass already. That is fine and expected: run them first anyway, and if either fails, the fix belongs in `observer.py`, never in the rail.

- [ ] **Step 3: Implement**

Nothing to implement if both rails pass. If the import rail fails, remove the offending import from `observer.py`; the module needs only `adb`, `config`, `preview`, `states`, `status` and `recorder`.

- [ ] **Step 4: Run the tests and watch them pass**

```
uv run pytest tests/test_observer.py tests/test_core_imports.py tests/test_never_tap_rail.py -q
```

- [ ] **Step 5: Commit**

```
git add tests/test_observer.py tests/test_core_imports.py
git commit -F <scratchpad>/msg-task5.txt
```

```
test(core): pin the observer import and no-tap rails

The source names no adb input call and importing the module pulls in
neither controller, brawlers, quests, rewards nor core/settings. observer
joins the module list every core module import test walks.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
```

---

### Task 6: The Record while I play switch on the Calibration page

**Files:**
- Create: `brawlfarm/web/src/calibration/ObserveCard.tsx`, `brawlfarm/web/src/calibration/ObserveCard.test.tsx`
- Modify: `brawlfarm/web/src/api/calibration.ts` (the `Recorder` interface at lines 69 to 82, a new writer under `setRecorder` at lines 96 to 101)
- Modify: `brawlfarm/web/src/api/types.ts` (`InstancePayload.desired`, line 44)
- Modify: `brawlfarm/web/src/calibration/useCalibration.ts` (imports at lines 20 to 31, a new hook under `useRecorderToggle` at lines 67 to 78)
- Modify: `brawlfarm/web/src/calibration/Calibration.tsx` (imports at lines 16 to 30, the hooks at lines 85 to 87, the card stack at lines 186 to 194)

**Interfaces:**
- Consumes: `POST /api/instances/{name}/observe` and the recorder payload's `mode` from task 4, `Switch` from `../components/ui/Switch`, `queryKeys.instances()` and `queryKeys.recorder(name)`.
- Produces: `setObserve(name: string, on: boolean): Promise<{ ok: boolean }>`, `useObserveToggle(instance: string | null): UseMutationResult<{ ok: boolean }, Error, boolean>`, `ObserveCard(props: ObserveCardProps)`, `OBSERVE_BLOCKED_MESSAGE`.

- [ ] **Step 1: Write the failing test**

```tsx
// brawlfarm/web/src/calibration/ObserveCard.test.tsx
/** The observe card: the switch follows the supervisor's desired mode rather than the
 * worker, it is disabled while the instance is doing anything else, and it counts frames
 * only once an observing worker is answering. */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { OBSERVE_BLOCKED_MESSAGE, ObserveCard } from "./ObserveCard";
import type { Recorder } from "../api/calibration";

function makeRecorder(overrides: Partial<Recorder> = {}): Recorder {
  return {
    on: false,
    frames: 0,
    bytes: 0,
    session: null,
    path: null,
    reason: null,
    last_session: null,
    last_frames: 0,
    flag: false,
    mode: "farm",
    ...overrides,
  };
}

function mount(props: Partial<React.ComponentProps<typeof ObserveCard>> = {}) {
  const onToggle = vi.fn();
  render(
    <ObserveCard
      instance="Pie64"
      desired="stop"
      running={false}
      status={makeRecorder()}
      pending={false}
      onToggle={onToggle}
      {...props}
    />,
  );
  return onToggle;
}

describe("ObserveCard", () => {
  it("offers the switch on a stopped instance", async () => {
    const onToggle = mount();
    const control = screen.getByRole("switch", { name: "Record while I play" });
    expect(control).toHaveAttribute("aria-checked", "false");
    await userEvent.click(control);
    expect(onToggle).toHaveBeenCalledWith(true);
  });

  it("refuses to start on a farming instance and says why", () => {
    mount({ running: true, desired: "run" });
    expect(screen.getByRole("switch", { name: "Record while I play" })).toBeDisabled();
    expect(screen.getByText(OBSERVE_BLOCKED_MESSAGE)).toBeInTheDocument();
  });

  it("stays usable while it is the observer that is running", () => {
    mount({ running: true, desired: "observe" });
    expect(screen.getByRole("switch", { name: "Record while I play" })).not.toBeDisabled();
    expect(screen.getByRole("switch", { name: "Record while I play" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
  });

  it("waits for the worker before it counts frames", () => {
    mount({ running: true, desired: "observe", status: makeRecorder({ mode: "farm" }) });
    expect(screen.getByText(/Waiting for the worker to start/)).toBeInTheDocument();
  });

  it("counts the frames once the observer is answering", () => {
    mount({
      running: true,
      desired: "observe",
      status: makeRecorder({ mode: "observe", on: true, frames: 37 }),
    });
    expect(screen.getByText(/37 frames so far/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test and watch it fail**

```
cd brawlfarm/web && pnpm test -- ObserveCard
```

Expect `Failed to resolve import "./ObserveCard"`.

- [ ] **Step 3: Implement**

`brawlfarm/web/src/api/calibration.ts`, inside `Recorder` after `flag`:

```ts
  /** Which worker is recording: "observe" while the owner plays by hand, "farm"
   * otherwise. It comes from the instance's heartbeat, so it is the running process
   * answering rather than the switch that asked for it. */
  mode: "farm" | "observe";
```

and under `setRecorder`:

```ts
/** POST /api/instances/{name}/observe. 202 on the way in; 409 while the instance is
 * doing anything else, because observe mode only ever starts from stopped. The
 * supervisor launches the worker on its next tick, so the answer here is an
 * acknowledgement and not a status. */
export function setObserve(name: string, on: boolean): Promise<{ ok: boolean }> {
  return api<{ ok: boolean }>(`/api/instances/${encodeURIComponent(name)}/observe`, {
    method: "POST",
    body: JSON.stringify({ on }),
  });
}
```

`brawlfarm/web/src/api/types.ts`:

```ts
  desired: "run" | "stop" | "observe";
```

`brawlfarm/web/src/calibration/useCalibration.ts`, extend the import list with `setObserve`, and add under `useRecorderToggle`:

```ts
export function useObserveToggle(
  instance: string | null,
): UseMutationResult<{ ok: boolean }, Error, boolean> {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (on: boolean) => setObserve(instance as string, on),
    onSuccess: () => {
      // Unlike the recorder toggle there is no fresh status in the response: the
      // supervisor acts on its next tick, so both reads that will change are asked again.
      void client.invalidateQueries({ queryKey: queryKeys.instances() });
      void client.invalidateQueries({ queryKey: queryKeys.recorder(instance ?? "") });
    },
  });
}
```

`brawlfarm/web/src/calibration/ObserveCard.tsx`:

```tsx
/**
 * Observe mode's switch: the owner plays, the worker watches and records.
 *
 * The switch shows `desired`, the supervisor's answer to the last click, not whether a
 * process is up: the worker is launched a tick later, so a switch that waited for it
 * would sit in the old position for up to a minute. The route refuses to start observing
 * on a live instance, so the switch is disabled whenever something else is running and
 * says what to do instead rather than offering a click that would come back 409.
 */
import type { Recorder } from "../api/calibration";
import { Switch } from "../components/ui/Switch";

export interface ObserveCardProps {
  instance: string;
  /** The supervisor's desired mode for this instance, straight off the Fleet payload. */
  desired: string;
  running: boolean;
  status: Recorder | undefined;
  pending: boolean;
  onToggle: (on: boolean) => void;
}

export const OBSERVE_BLOCKED_MESSAGE =
  "Stop this instance first. Recording your own play never starts on top of a farming worker.";

export function ObserveCard({
  instance,
  desired,
  running,
  status,
  pending,
  onToggle,
}: ObserveCardProps) {
  const observing = desired === "observe";
  const blocked = running && !observing;
  const answering = status !== undefined && status.mode === "observe" && status.on;

  return (
    <section className="flex flex-col gap-2 rounded-[10px] border border-line bg-panel p-3">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-[13px] font-semibold">Observe</h2>
        <Switch
          label="Record while I play"
          checked={observing}
          disabled={blocked || pending}
          onChange={onToggle}
        />
      </div>

      {blocked && <p className="text-[12px] text-muted">{OBSERVE_BLOCKED_MESSAGE}</p>}

      {!blocked && observing && (
        <p className="text-[12px] text-muted">
          {`Recording ${instance} while you play. It watches and never taps.`}
          {answering ? ` ${status.frames} frames so far.` : " Waiting for the worker to start."}
        </p>
      )}

      {!blocked && !observing && (
        <p className="text-[12px] text-muted">
          Off. Turn it on and play the game yourself: every screen you visit is captured and
          labelled for calibration.
        </p>
      )}
    </section>
  );
}
```

`brawlfarm/web/src/calibration/Calibration.tsx`: import `ObserveCard` next to `RecorderCard`, import `useObserveToggle` in the `./useCalibration` block, add the hook beside the others, and render the card under `RecorderCard` in the same column. Mirror the existing `onToggle` handler that sits directly above; if it does not already report a failure, the new one still must:

```tsx
  const observe = useObserveToggle(chosen);
```

```tsx
  const onObserve = (on: boolean) => {
    observe.mutate(on, { onError: (error) => toast(failureMessage(error)) });
  };
```

```tsx
                <ObserveCard
                  instance={chosen}
                  desired={instance?.desired ?? "stop"}
                  running={running}
                  status={recorder.data}
                  pending={observe.isPending}
                  onToggle={onObserve}
                />
```

- [ ] **Step 4: Run the tests and watch them pass**

```
cd brawlfarm/web && pnpm test && pnpm typecheck
```

- [ ] **Step 5: Commit**

```
git add brawlfarm/web/src/calibration/ObserveCard.tsx brawlfarm/web/src/calibration/ObserveCard.test.tsx brawlfarm/web/src/calibration/useCalibration.ts brawlfarm/web/src/calibration/Calibration.tsx brawlfarm/web/src/api/calibration.ts brawlfarm/web/src/api/types.ts
git commit -F <scratchpad>/msg-task6.txt
```

```
feat(web): Record while I play switch on the Calibration page

The switch follows the supervisor's desired mode, is disabled while
anything else is running with a line saying to stop the instance first,
and counts frames once an observing worker answers in recorder.json.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
```

---

### Task 7: Docs, the spec and this plan

**Files:**
- Modify: `docs/calibration.md` (a new section after "## Recording frames" at line 44, before "## Safety" at line 56)
- Modify: `README.md` (the Calibration section, a paragraph after line 120)
- Create: `docs/superpowers/specs/2026-09-13-phase-9-design.md` (the approved spec, copied in verbatim)
- Create: `docs/superpowers/plans/2026-09-13-phase-9-observe-mode.md` (this plan, copied in verbatim)

**Interfaces:** none. Prose only.

- [ ] **Step 1: Write the failing check**

There is no unit test for prose. The check is the scrub tool, which is the thing that can actually fail here:

```
uv run python tools/scrub_check.py
```

It must print `0 hit(s)` after the two new files land. Read both before copying them in and remove any absolute path, machine name or legacy nickname; the spec and this plan are written to be safe already, so a hit means something was pasted in around them.

- [ ] **Step 2: Run it and see the state before the change**

```
uv run python tools/scrub_check.py
```

Expect `0 hit(s)` on the clean tree, so any hit after step 3 is from the new files.

- [ ] **Step 3: Implement**

`docs/calibration.md`, after the "Recording frames" section:

```markdown
## Record while I play

Recording frames captures what the bot sees, which is only the handful of screens the bot
visits. Record while I play captures what you see. Stop the instance, turn the switch on,
and the supervisor launches a worker in observe mode: it connects, checks the display is
1600x900, and from then on it screencaps about twice a second, labels each frame with the
state its anchors prove and writes it to the same session folder the recorder uses. Then
you play the game by hand and walk it through whatever screens the next calibration needs.

Observe mode never taps. It is a separate module from the farm controller and it imports
nothing that can send an input event, which two tests enforce: one reads its source and
fails on any adb input call, and one imports it in a fresh interpreter and fails if the
controller, the brawler screen, the quests screen, the reward paths or the core settings
came along with it.

It is one worker per instance either way, so observe mode takes the same slot a farming
worker would. That is why the switch refuses to start on a running instance: stop it
first. Turning the switch off is an ordinary stop.

The session ends at the same 2000 frame cap a farm recording has, which is roughly half an
hour of distinct screens. When it stops, turn the switch on again for a new folder.
```

`README.md`, after the "Record frames switch" paragraph:

```markdown
The Record while I play switch next to it stops short of farming entirely: it launches the
worker in observe mode, which watches and labels frames while you play the instance by
hand and never sends an input event. It only starts from a stopped instance, and it writes
into the same `recordings/<instance>/<yyyymmdd-hhmmss>/` folder with the same caps.
```

Then copy the approved spec to `docs/superpowers/specs/2026-09-13-phase-9-design.md` and this plan to `docs/superpowers/plans/2026-09-13-phase-9-observe-mode.md`, unchanged apart from removing any scratchpad path.

- [ ] **Step 4: Run the gate and watch it pass**

```
uv run python tools/scrub_check.py
uv run pytest tests/test_scrub.py -q
```

Both must be clean, and `scrub_check.py` must print `0 hit(s)`.

- [ ] **Step 5: Commit**

```
git add docs/calibration.md README.md docs/superpowers/specs/2026-09-13-phase-9-design.md docs/superpowers/plans/2026-09-13-phase-9-observe-mode.md
git commit -F <scratchpad>/msg-task7.txt
```

```
docs: record while I play, plus the phase 9 spec and plan

A calibration how-to section and a README paragraph for observe mode,
and the approved phase 9 design with the plan built from it.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
```

---

### Task 8: questpick.parse and questpick.resolve

**Files:**
- Create: `brawlfarm/core/questpick.py`
- Test: `tests/test_questpick.py`
- Modify: `tests/test_core_imports.py` (`MODULES`, alphabetically between `quests` and `recalib`)

**Interfaces:**
- Consumes: nothing. The module imports only `re`, `dataclasses` and `collections.abc`.
- Produces: `Quest(kind: str, target: str, count: int, line: str)` frozen dataclass; `KIND_BRAWLER`, `KIND_CLASS`, `KIND_MODE`, `CLASSES`; `normalize(line: str) -> str`; `norm_name(name: str | None) -> str`; `parse(lines: Iterable[str]) -> list[Quest]`; `resolve(quests: Sequence[Quest], owned: Sequence[str]) -> str | None`. The controller wiring in a later plan consumes `parse` and `resolve` only.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_questpick.py
"""The pure half of the quest-aware pick: OCR lines in, a brawler name or None out.

Every line here is hand-typed, including the mangled ones, because the quests screen has
not been recorded yet. Nothing in this file reads a screen, and nothing it tests can."""

from __future__ import annotations

from brawlfarm.core import brawlers, questpick

OWNED = ["Shelly", "El Primo", "8-Bit", "Larry & Lawrie"]


def test_parses_win_n_battles_with_a_named_brawler() -> None:
    (quest,) = questpick.parse(["Win 5 battles with Shelly"])
    assert quest.kind == questpick.KIND_BRAWLER
    assert quest.target == "SHELLY"
    assert quest.count == 5


def test_parses_deal_damage_with_a_class() -> None:
    (quest,) = questpick.parse(["Deal 20,000 damage with Damage Dealers"])
    assert quest.kind == questpick.KIND_CLASS
    assert quest.target == "DAMAGEDEALERS"
    assert quest.count == 20000


def test_parses_play_n_battles_in_a_mode() -> None:
    (quest,) = questpick.parse(["Play 8 battles in Gem Grab"])
    assert quest.kind == questpick.KIND_MODE
    assert quest.target == "GEMGRAB"
    assert quest.count == 8


def test_deal_damage_with_a_named_brawler_is_a_brawler_quest() -> None:
    (quest,) = questpick.parse(["Deal 12000 damage with El Primo"])
    assert (quest.kind, quest.target) == (questpick.KIND_BRAWLER, "ELPRIMO")


def test_mangled_ocr_still_reads(the_mangles=None) -> None:
    lines = ["W1N 5 BATTLE5 W1TH 5HELLY", "Win 3 battles with  8-BIT!"]
    assert [(q.target, q.count) for q in questpick.parse(lines)] == [("SHELLY", 5), ("8BIT", 3)]


def test_a_claimed_row_is_never_a_quest() -> None:
    lines = ["Win 5 battles with Shelly  CLAIMED", "Win 2 battles with El Primo"]
    assert [q.target for q in questpick.parse(lines)] == ["ELPRIMO"]


def test_lines_it_does_not_understand_are_dropped() -> None:
    assert questpick.parse(["QUESTS", "", "Collect 3 star points", "Win battles with"]) == []


def test_resolve_returns_the_rosters_own_spelling() -> None:
    quests = questpick.parse(["Win 5 battles with LARRY AND LAWRIE", "Win 2 battles with Shelly"])
    assert questpick.resolve(quests, OWNED) == "Shelly"


def test_resolve_skips_a_brawler_that_is_not_owned() -> None:
    quests = questpick.parse(["Win 5 battles with Crow"])
    assert questpick.resolve(quests, OWNED) is None


def test_resolve_answers_none_for_a_class_quest() -> None:
    quests = questpick.parse(["Deal 20000 damage with Tanks"])
    assert questpick.resolve(quests, OWNED) is None


def test_resolve_answers_none_for_a_mode_quest() -> None:
    quests = questpick.parse(["Play 8 battles in Gem Grab"])
    assert questpick.resolve(quests, OWNED) is None


def test_resolve_answers_none_for_nothing_at_all() -> None:
    assert questpick.resolve([], OWNED) is None


def test_name_normalization_matches_the_brawler_screens() -> None:
    """questpick keeps its own copy so it stays import-light; the two must not drift."""
    for name in ("EL PRIMO", "8-BIT", "LARRY & LAWRIE", "Shelly", None):
        assert questpick.norm_name(name) == brawlers._norm(name)
```

Note on `test_resolve_returns_the_rosters_own_spelling`: "LARRY AND LAWRIE" normalizes to `LARRYANDLAWRIE`, which the roster's `LARRYLAWRIE` does not match, so the first quest is skipped and the second resolves. That is the intended behaviour, and the test pins it.

Drop the stray default argument in `test_mangled_ocr_still_reads`; it is written here only to keep the name readable, so the real signature is `def test_mangled_ocr_still_reads() -> None:`.

- [ ] **Step 2: Run the tests and watch them fail**

```
uv run pytest tests/test_questpick.py -q
```

Expect `ModuleNotFoundError: No module named 'brawlfarm.core.questpick'`.

- [ ] **Step 3: Implement**

```python
# brawlfarm/core/questpick.py
"""Quest lines in, a farm brawler name out. Pure, and deliberately so.

``parse`` turns the OCR of the quests screen into quests; ``resolve`` turns those plus the
owned roster into one brawler name. Neither touches adb, a screen, a coordinate or
config.py, so both are tested today against hand-typed lines and wired to a real screen
read later, once an observe recording of the quests screen exists.

Three shapes matter:

    "Win 5 battles with Shelly"          -> KIND_BRAWLER, SHELLY, 5
    "Deal 20,000 damage with Tanks"      -> KIND_CLASS,   TANKS, 20000
    "Play 8 battles in Gem Grab"         -> KIND_MODE,    GEMGRAB, 8

Whether a quest is about a brawler or about a class is decided by the target, not by the
verb, because the game writes both "win with" and "deal damage with" for either one.

The class-to-brawler table is deferred until the captures exist (phase 9 spec, feature 2),
so ``resolve`` answers None for a class quest rather than naming a brawler the account may
not own. Mode quests answer None too: the bot only plays Trio Showdown. None is always the
safe answer, because the caller falls back to the farm plan or the lowest-trophy pick.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

KIND_BRAWLER = "brawler"
KIND_CLASS = "class"
KIND_MODE = "mode"

# The classes as the quests screen spells them, normalized. Game vocabulary, not
# calibration: there is no coordinate and no threshold here, so it does not belong in
# config.py and does not need an owner-approved calibration pull request to change.
CLASSES = frozenset(
    {
        "DAMAGEDEALERS",
        "TANKS",
        "MARKSMEN",
        "ARTILLERIES",
        "CONTROLLERS",
        "ASSASSINS",
        "SUPPORTS",
    }
)

# A row whose reward is already taken must never steer the session: farming it buys
# nothing. Anything that looks like a finished row is dropped rather than parsed.
_CLAIMED = re.compile(r"\b(CLAIMED|COLLECTED|COMPLETE|COMPLETED)\b")

_WIN_RE = re.compile(r"\bWIN (\d+) BATTLES? WITH (.+)$")
_DAMAGE_RE = re.compile(r"\bDEAL (\d+) DAMAGE WITH (.+)$")
_MODE_RE = re.compile(r"\bPLAY (\d+) BATTLES? IN (.+)$")

# The game's styled font reads letters as digits, the way config.py's SELET note records:
# "W1TH", "BATTLE5", "8ITE". Folded back only in words that are not a bare number, so a
# count stays a count.
_LOOKALIKE = str.maketrans({"0": "O", "1": "I", "5": "S", "|": "I"})


@dataclass(frozen=True)
class Quest:
    """One understood quest row."""

    kind: str  # KIND_BRAWLER | KIND_CLASS | KIND_MODE
    target: str  # normalized: "SHELLY", "TANKS", "GEMGRAB"
    count: int  # battles to win or play, or damage to deal
    line: str  # the normalized line it came from, for the log and the feed


def norm_name(name: str | None) -> str:
    """Collapse a name for comparison: uppercase, alphanumerics only ("EL PRIMO" ->
    "ELPRIMO", "8-BIT" -> "8BIT").

    The same rule as ``brawlers._norm``, kept here rather than imported so this module
    pulls in nothing that can touch the screen. tests/test_questpick.py asserts the two
    agree, so they cannot drift apart quietly.
    """
    return "".join(c for c in (name or "").upper() if c.isalnum())


def _fold(word: str) -> str:
    return word if word.isdigit() else word.translate(_LOOKALIKE)


def normalize(line: str) -> str:
    """One OCR line as the matchers want it: uppercase, punctuation gone, thousands
    separators gone, digit look-alikes folded back to letters, single spaces."""
    upper = (line or "").upper().replace(",", "").replace(".", "")
    cleaned = "".join(c if c.isalnum() else " " for c in upper)
    return " ".join(_fold(word) for word in cleaned.split())


def parse(lines: Iterable[str]) -> list[Quest]:
    """Every quest this OCR pass understood, in screen order.

    Lines it does not understand are dropped, and so are rows that read as already
    claimed: a quest the parser is not sure of must not steer a session.
    """
    out: list[Quest] = []
    for raw in lines:
        line = normalize(raw)
        if not line or _CLAIMED.search(line):
            continue
        quest = _parse_line(line)
        if quest is not None:
            out.append(quest)
    return out


def _parse_line(line: str) -> Quest | None:
    match = _WIN_RE.search(line) or _DAMAGE_RE.search(line)
    if match is not None:
        target = norm_name(match.group(2))
        if not target:
            return None
        kind = KIND_CLASS if target in CLASSES else KIND_BRAWLER
        return Quest(kind, target, int(match.group(1)), line)
    match = _MODE_RE.search(line)
    if match is not None:
        target = norm_name(match.group(2))
        return None if not target else Quest(KIND_MODE, target, int(match.group(1)), line)
    return None


def resolve(quests: Sequence[Quest], owned: Sequence[str]) -> str | None:
    """The owned brawler that clears the first quest it can, or None.

    The roster's own spelling comes back, never the quest's, so the name that leaves here
    is one ``brawlers.select_brawler_by_name_checked`` can verify on the detail screen.
    """
    by_norm = {norm_name(name): name for name in owned}
    for quest in quests:
        if quest.kind != KIND_BRAWLER:
            continue
        owned_name = by_norm.get(quest.target)
        if owned_name is not None:
            return owned_name
    return None
```

Add `"questpick",` to `MODULES` in `tests/test_core_imports.py`.

- [ ] **Step 4: Run the tests and watch them pass**

```
uv run pytest tests/test_questpick.py tests/test_core_imports.py -q
```

- [ ] **Step 5: Commit**

```
git add brawlfarm/core/questpick.py tests/test_questpick.py tests/test_core_imports.py
git commit -F <scratchpad>/msg-task8.txt
```

```
feat(core): questpick parse and resolve as pure functions

Three quest shapes, OCR look-alike folding, claimed rows dropped, and a
resolve that returns the roster's own spelling or None. Class quests
answer None until the class table lands with the quests captures. No
config value, no screen read, nothing wired to the controller yet.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
```

---

### Task 9: The auto-upgrade gate as a pure function

**Files:**
- Create: `brawlfarm/core/upgrade_gate.py`
- Test: `tests/test_upgrade_gate.py`
- Modify: `tests/test_core_imports.py` (`MODULES`, alphabetically after `stats`)

**Interfaces:**
- Consumes: nothing. The module imports only `dataclasses`.
- Produces: `Reading(power_points, power_points_needed, coins, cost, gold_chip, purple_chip)` frozen dataclass; `should_upgrade(reading: Reading, *, auto_upgrade: bool, coin_floor: int = 0, done_this_session: bool = False) -> bool`. The state machine in a later plan is its only caller.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_upgrade_gate.py
"""The auto-upgrade gate's truth table. Every ambiguous input is a no.

There is no tap path in the repo yet and there cannot be one until the never-tap rule in
CONTRIBUTING.md is amended in an owner-approved pull request, so this file tests a
decision and nothing that acts on it."""

from __future__ import annotations

import pytest

from brawlfarm.core import upgrade_gate


def reading(**overrides) -> upgrade_gate.Reading:
    """A reading that passes every condition, for one field at a time to be spoiled."""
    fields = {
        "power_points": 200,
        "power_points_needed": 180,
        "coins": 1500,
        "cost": 800,
        "gold_chip": True,
        "purple_chip": False,
    }
    return upgrade_gate.Reading(**{**fields, **overrides})


def test_the_happy_path_is_the_only_yes() -> None:
    assert upgrade_gate.should_upgrade(reading(), auto_upgrade=True) is True


def test_exactly_enough_of_everything_still_passes() -> None:
    r = reading(power_points=180, coins=800)
    assert upgrade_gate.should_upgrade(r, auto_upgrade=True) is True


@pytest.mark.parametrize(
    ("why", "spoiled"),
    [
        ("power points short by one", {"power_points": 179}),
        ("power points not read", {"power_points": None}),
        ("needed not read", {"power_points_needed": None}),
        ("needed is nonsense", {"power_points_needed": 0}),
        ("coins not read", {"coins": None}),
        ("coins short by one", {"coins": 799}),
        ("cost not parsed", {"cost": None}),
        ("cost is nonsense", {"cost": 0}),
        ("cost read as negative", {"cost": -800}),
        ("the price chip is not coin gold", {"gold_chip": False}),
        ("the price chip has gem purple in it", {"purple_chip": True}),
    ],
)
def test_every_ambiguous_reading_is_a_no(why: str, spoiled: dict) -> None:
    assert upgrade_gate.should_upgrade(reading(**spoiled), auto_upgrade=True) is False, why


def test_the_flag_off_is_a_no_whatever_the_screen_says() -> None:
    assert upgrade_gate.should_upgrade(reading(), auto_upgrade=False) is False


def test_one_upgrade_per_session() -> None:
    r = reading()
    assert upgrade_gate.should_upgrade(r, auto_upgrade=True, done_this_session=True) is False


def test_the_coin_floor_is_kept_whole() -> None:
    r = reading(coins=1000, cost=800)
    assert upgrade_gate.should_upgrade(r, auto_upgrade=True, coin_floor=200) is True
    assert upgrade_gate.should_upgrade(r, auto_upgrade=True, coin_floor=201) is False


def test_a_negative_coin_floor_is_a_no_not_a_discount() -> None:
    assert upgrade_gate.should_upgrade(reading(), auto_upgrade=True, coin_floor=-1000) is False


def test_a_reading_that_read_nothing_is_a_no() -> None:
    assert upgrade_gate.should_upgrade(upgrade_gate.Reading(), auto_upgrade=True) is False
```

- [ ] **Step 2: Run the tests and watch them fail**

```
uv run pytest tests/test_upgrade_gate.py -q
```

Expect `ModuleNotFoundError: No module named 'brawlfarm.core.upgrade_gate'`.

- [ ] **Step 3: Implement**

```python
# brawlfarm/core/upgrade_gate.py
"""The auto-upgrade decision: one pure function, no screen and no adb.

The tap path this guards does not exist and cannot exist yet. CONTRIBUTING.md lists
Upgrade in the never-tap set, and that rule is only narrowed in an owner-approved pull
request that says so (phase 9 spec, feature 3). This module ships first and alone so the
decision is written, tested and reviewable before anything can press a button that spends
coins. Nothing imports it yet.

Every reading is optional because every one of them comes from OCR or from a color check
that can fail, and a failed read is never a zero. Every ambiguous input is a no: an
unparsed cost, a missing power-point line, a price chip that is not clearly coin gold, or
any trace of gem purple. There is no branch that answers True without the gold check
passing and the purple check failing, which is how "never gems" is enforced here rather
than promised.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Reading:
    """What READ managed to get off the brawler detail screen.

    The defaults are the refusing ones: a Reading nobody filled in says "nothing was read,
    the chip is not gold, and there might be purple in it", so a caller that forgets a
    field gets a no instead of an upgrade.
    """

    power_points: int | None = None
    power_points_needed: int | None = None
    coins: int | None = None
    cost: int | None = None
    gold_chip: bool = False  # the price chip's coin-gold fraction cleared its band
    purple_chip: bool = True  # the gem-purple fraction is NOT near zero


def should_upgrade(
    reading: Reading,
    *,
    auto_upgrade: bool,
    coin_floor: int = 0,
    done_this_session: bool = False,
) -> bool:
    """True only when every condition holds: the setting is on, no upgrade has been done
    this session, the chip is coin gold and not gem purple, all four numbers were read,
    none of them is nonsense, the power points are there, and paying the cost still leaves
    ``coin_floor`` coins behind."""
    if not auto_upgrade or done_this_session:
        return False
    if not reading.gold_chip or reading.purple_chip:
        return False
    points, needed = reading.power_points, reading.power_points_needed
    coins, cost = reading.coins, reading.cost
    if points is None or needed is None or coins is None or cost is None:
        return False
    # A negative anywhere is a misread digit or a caller passing a discount as a floor.
    if min(points, needed, coins, cost, coin_floor) < 0:
        return False
    if needed <= 0 or cost <= 0:
        return False
    if points < needed:
        return False
    return coins - cost >= coin_floor
```

Add `"upgrade_gate",` to `MODULES` in `tests/test_core_imports.py`.

- [ ] **Step 4: Run the tests and watch them pass**

```
uv run pytest tests/test_upgrade_gate.py tests/test_core_imports.py -q
```

- [ ] **Step 5: Commit**

```
git add brawlfarm/core/upgrade_gate.py tests/test_upgrade_gate.py tests/test_core_imports.py
git commit -F <scratchpad>/msg-task9.txt
```

```
feat(core): the auto-upgrade gate as a pure function

The spec's GATE as one function over a Reading whose defaults refuse,
with the truth table across power points, coins, floor, gold, purple and
the session counter. Nothing imports it: the tap path waits on the
never-tap amendment and the brawler detail captures.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
```

---

## Self-review

**Spec coverage.** Feature 1's seven tasks map one to one onto tasks 1 through 7: the Observer class with its loop, heartbeat, record.flag lifecycle and 1600x900 assertion (task 1); `--observe` plus the `worker_args` branch (task 2); the third desired mode in `state.py` and `loop.py`, with `scheduler.py` added because that is where an override becomes a desired block (task 3); the observe route with its 409 and the recorder payload's `mode` field (task 4); the import rail and the no-tap rail plus `observer` in `MODULES` (task 5); the Calibration page switch and its API client (task 6); docs (task 7). Feature 2 task 1 is task 8, with class quests resolving to None as the spec's ruling requires. Feature 3 task 2 is task 9, truth table included. Out of scope and absent here, as required: nothing taps, no `config.py` value is added or changed, `CONTRIBUTING.md` is untouched, `quests.py`, `controller.py`, `plans.py`, `farmplan.py`, `feed.py`, `settings_routes.py` and `Behavior.tsx` are untouched, and `Recorder.MAX_FRAMES` stays 2000.

**Placeholder scan.** Every code step carries complete code. No `TODO`, no `...`, no `pass  # implement`, no invented helper. The three places an implementer must look at the file rather than paste blind are called out explicitly: the settings builder name in `tests/test_settings.py`, the existing `onToggle` handler in `Calibration.tsx` that the new one mirrors, and the scratchpad path in the `git commit -F` lines. The one deliberate defect is flagged in its own note: `test_mangled_ocr_still_reads` is written with a stray default argument and step 1 says to drop it.

**Type consistency.** `worker_args` gains a keyword-only `observe: bool = False`, so the three existing call sites and `tests/test_settings.py:193` keep compiling. `InstanceView.desired` stays `str`, so `derive_state` and `view_to_dict` need no signature change; only the comment and one membership test widen. `Recorder` in `api/calibration.ts` gains a required `mode: "farm" | "observe"`, which is why `RecorderCard.test.tsx`'s `makeRecorder` and `test_recorder_routes`' exact-equality dict are both listed as edits rather than left to fail later. `InstancePayload.desired` widens from a two-member union to three, which is safe for readers and is why `pnpm typecheck` runs before task 6's commit. `questpick.resolve` and `upgrade_gate.should_upgrade` return `str | None` and `bool` with no optional-shaped surprises, and both modules import only the standard library, so adding them to `tests/test_core_imports.py::MODULES` cannot fail on a missing environment.
