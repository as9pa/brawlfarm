"""The supervisor tick and its controls (spec section 6), ported from the legacy
PowerShell watchdog.

One tick: scheduler tick for every instance; then per instance read status.json,
classify the heartbeat, read the scheduler's desired state, and act: desired stop and
alive -> write stop.flag, kill by PID after STOP_ESCALATE_S; desired run and unhealthy
-> probe adb (offline backoff), kill a stale PID, launch (one launch per tick).
Everything the panel shows is derived here once per tick into InstanceView objects.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path

from brawlfarm import settings as S
from brawlfarm.core import config, events, notify, scheduler, status
from brawlfarm.supervisor import process
from brawlfarm.supervisor.backoff import OfflineBackoff
from brawlfarm.supervisor.state import (
    Health,
    InstanceState,
    InstanceView,
    classify,
    derive_state,
    heartbeat_age_s,
)

log = logging.getLogger("brawlfarm.supervisor")

TICK_S = 60.0
BOOT_GRACE_S = 180.0  # after a launch, do not relaunch before the worker can heartbeat
STOP_ESCALATE_S = 110.0  # graceful stop.flag first, kill by PID after this
ALERT_AFTER_MISSES = 3
STOP_OVERRIDE_DAYS = 365  # "stopped until you start it again"
STOP_FLAG = "stop.flag"


class Supervisor:
    def __init__(
        self,
        settings: S.AppSettings,
        home: Path,
        *,
        clock: Callable[[], datetime] = datetime.now,
        probe: Callable[..., bool] = process.instance_online,
        launcher: Callable[..., object] = process.launch_worker,
        alive: Callable[[int], bool] = process.pid_alive,
        killer: Callable[..., bool] = process.kill_worker,
        sleep: Callable[[float], None] = time.sleep,
        events_refresh: Callable[..., int] = events.refresh,
        interval_s: float = TICK_S,
    ) -> None:
        self.settings = settings
        self.home = Path(home).resolve()
        self.interval_s = interval_s
        self._clock, self._probe, self._launch = clock, probe, launcher
        self._alive, self._kill, self._sleep, self._refresh = alive, killer, sleep, events_refresh
        self._backoff = OfflineBackoff()
        self._stop_asked: dict[str, datetime] = {}
        self._run_until: dict[str, datetime] = {}
        self._launched_at: dict[str, datetime] = {}
        self._procs: dict[str, object] = {}
        self._views: dict[str, InstanceView] = {}
        self._listeners: list[Callable[[InstanceView], None]] = []
        self._poke: asyncio.Event | None = None
        self._shutdown = False
        self.apply_settings(settings)

    # --- wiring -----------------------------------------------------------------------

    def apply_settings(self, settings: S.AppSettings) -> None:
        """Point the core at the home directory and the instance table; safe to call again
        after the user edits settings (phase 5)."""
        self.settings = settings
        config.set_home(self.home)
        config.set_instances(S.instances_table(settings))
        config.API_TOKEN = settings.connection.brawl_api_token or config.API_TOKEN
        scheduler.set_default_enabled(settings.scheduler.default_enabled)
        n = settings.notifications
        notify.configure(
            webhook_url=n.webhook_url or None,  # blank defers to the environment
            ntfy_server=n.ntfy_server or None,
            ntfy_topic=n.ntfy_topic or None,
            events=list(n.events),
        )

    def views(self) -> list[InstanceView]:
        return [self._views[i.name] for i in self.settings.instances if i.name in self._views]

    def subscribe(self, cb: Callable[[InstanceView], None]) -> None:
        self._listeners.append(cb)

    def _dir(self, name: str) -> Path:
        return S.instance_dir(self.home, name)

    def _flag(self, name: str) -> Path:
        return self._dir(name) / STOP_FLAG

    # --- the tick ---------------------------------------------------------------------

    def tick(self) -> list[InstanceView]:
        now = self._clock()
        rc = scheduler.tick(now)
        if rc != 0:
            log.warning("scheduler tick failed (rc=%s); fail open to always-run", rc)
        if self.settings.connection.brawl_api_token:  # the rotation fetch needs the API
            try:
                self._refresh(now)
            except Exception as exc:  # best effort, never blocks the tick
                log.debug("events refresh failed: %s", exc)
        launched_this_tick = False
        out: list[InstanceView] = []
        for inst in self.settings.instances:
            view, launched = self._tick_instance(inst, now, launched_this_tick)
            launched_this_tick = launched_this_tick or launched
            out.append(view)
            previous = self._views.get(inst.name)
            self._views[inst.name] = view
            if previous is None or previous.state != view.state:
                for cb in self._listeners:
                    try:
                        cb(view)
                    except Exception as exc:
                        log.debug("listener failed: %s", exc)
        log.info("tick: %s", ", ".join(f"{v.name}={v.state}" for v in out) or "no instances")
        return out

    def _tick_instance(
        self, inst: S.InstanceSettings, now: datetime, launched_this_tick: bool
    ) -> tuple[InstanceView, bool]:
        name = inst.name
        st = status.read_status(self._dir(name))
        pid = int(st["pid"]) if st and st.get("pid") else None
        alive = pid is not None and self._alive(pid)
        health = classify(st, alive, now)
        desired = scheduler.sched_desired(name, now)
        want = (desired or {}).get("state", "run")
        reason = (desired or {}).get("reason")
        until = _parse_until((desired or {}).get("until"))
        note = ""
        launched = False

        if want == "stop":
            self._backoff.clear(name)
            if alive:
                self._request_stop(name, now)
                if self._maybe_escalate(name, pid, now):
                    alive, health = False, Health.DEAD
            else:
                self._stop_asked.pop(name, None)
        else:
            if health == Health.HEALTHY:
                self._backoff.clear(name)
                if self._maybe_escalate(name, pid, now):  # a restart in flight
                    alive, health = False, Health.DEAD
            elif self._booting(name, now):
                note = "Starting; waiting for the first heartbeat"
            elif (retry := self._backoff.until(name, now)) is not None:
                note = _offline_note(retry, now)
            elif launched_this_tick:
                note = "Waiting for its turn to start"
            elif not self._probe(self.settings.connection.adb_path, inst.adb_port):
                retry = self._backoff.record_miss(name, now)
                misses = self._backoff.misses(name)
                log.warning("%s: adb probe failed (miss %d); retry at %s", name, misses, retry)
                if misses == ALERT_AFTER_MISSES:
                    notify.maybe_alert("offline", {"instance": name, "misses": misses})
                note = _offline_note(retry, now)
            else:
                self._backoff.clear(name)
                if alive and pid is not None:
                    log.warning("%s: stale heartbeat, killing pid %s before relaunch", name, pid)
                    self._kill(pid, log=log.warning)
                    self._sleep(0.5)
                    alive, health = False, Health.DEAD
                self._launch_worker(inst, desired, now)
                launched = True
                note = "Starting"

        stop_deadline = (
            self._stop_asked[name] + timedelta(seconds=STOP_ESCALATE_S)
            if name in self._stop_asked and alive
            else None
        )
        state, shown_until = derive_state(
            health=health,
            desired=want,
            desired_reason=reason,
            desired_until=until,
            stop_pending=stop_deadline,
            booting=self._booting(name, now) or launched,
            offline_until=self._backoff.until(name, now),
            status=st,
        )
        if state == InstanceState.STOPPING:
            note = "Stopping after this match"
        view = InstanceView(
            name=name,
            adb_port=inst.adb_port,
            state=state,
            health=health,
            pid=pid if alive else None,
            heartbeat_age_s=heartbeat_age_s(st, now),
            phase=(st or {}).get("phase"),
            desired=want,
            desired_reason=reason,
            until=shown_until,
            games_played=_int_or_none((st or {}).get("games_played")),
            farm_brawler=(st or {}).get("farm_brawler") or None,
            note=note,
        )
        return view, launched

    # --- helpers ----------------------------------------------------------------------

    def _booting(self, name: str, now: datetime) -> bool:
        # The window is inclusive of its last instant: TICK_S divides BOOT_GRACE_S, so a
        # tick can land exactly on it and the worker still deserves that tick to report.
        started = self._launched_at.get(name)
        if started is None or (now - started).total_seconds() > BOOT_GRACE_S:
            return False
        proc = self._procs.get(name)
        poll = getattr(proc, "poll", None)
        return poll is None or poll() is None

    def _request_stop(self, name: str, now: datetime) -> None:
        if name in self._stop_asked:
            return
        flag = self._flag(name)
        flag.parent.mkdir(parents=True, exist_ok=True)
        flag.write_text(f"stop requested {now:%Y-%m-%dT%H:%M:%S}\n", encoding="utf-8")
        self._stop_asked[name] = now
        log.info("%s: stop requested (stop.flag written)", name)

    def _maybe_escalate(self, name: str, pid: int | None, now: datetime) -> bool:
        """Kill by PID once a requested stop has waited STOP_ESCALATE_S. True when killed."""
        asked = self._stop_asked.get(name)
        if asked is None or pid is None:
            return False
        if (now - asked).total_seconds() < STOP_ESCALATE_S:
            return False
        log.warning("%s: stop not honoured in %ds, killing pid %s", name, STOP_ESCALATE_S, pid)
        self._kill(pid, log=log.warning)
        self._stop_asked.pop(name, None)
        return True

    def _run_minutes_left(self, name: str, now: datetime) -> float | None:
        """Minutes left on a ``start(name, hours=...)`` request. The scheduler echoes that
        cap back as desired.max_minutes only while the schedule is on; with it off a run
        override just means always-run, so the loop keeps the deadline itself."""
        until = self._run_until.get(name)
        if until is None:
            return None
        if until <= now:
            self._run_until.pop(name, None)
            return None
        return max(1.0, round((until - now).total_seconds() / 60.0, 1))

    def _launch_worker(self, inst: S.InstanceSettings, desired: dict | None, now: datetime) -> None:
        max_minutes = (desired or {}).get("max_minutes") or self._run_minutes_left(inst.name, now)
        args = S.worker_args(self.settings, float(max_minutes) if max_minutes else None)
        env = {**os.environ, **S.worker_env(self.settings, inst, self.home)}
        self._flag(inst.name).unlink(missing_ok=True)
        self._stop_asked.pop(inst.name, None)
        proc = self._launch(args, env, self.home / "logs", inst.name)
        self._procs[inst.name] = proc
        self._launched_at[inst.name] = now
        log.info(
            "%s: launched worker pid %s (%s)", inst.name, getattr(proc, "pid", "?"), " ".join(args)
        )

    # --- controls (called from the event loop thread; phase 3 wires them to the API) ---

    def start(self, name: str, hours: float | None = None) -> None:
        """Start (or undo a pending stop): clear the stop override, or run for N hours."""
        now = self._clock()
        self.settings.instance(name)
        if hours:
            until = now + timedelta(hours=hours)
            scheduler.write_override(name, "run", until)
            self._run_until[name] = until
        else:
            scheduler.clear_override(name)
            self._run_until.pop(name, None)
        self._flag(name).unlink(missing_ok=True)
        self._stop_asked.pop(name, None)
        self._backoff.clear(name)
        self.poke()

    def stop(self, name: str) -> None:
        """Graceful: schedule override to stop, stop.flag now; the tick kills after 110 s."""
        now = self._clock()
        self.settings.instance(name)
        scheduler.write_override(name, "stop", now + timedelta(days=STOP_OVERRIDE_DAYS))
        self._run_until.pop(name, None)
        self._request_stop(name, now)
        self.poke()

    def stop_now(self, name: str) -> bool:
        """Kill by PID immediately. Only while a graceful stop is pending; else no-op."""
        if name not in self._stop_asked:
            return False
        st = status.read_status(self._dir(name))
        pid = int(st["pid"]) if st and st.get("pid") else None
        if pid is None:
            return False
        ok = bool(self._kill(pid, log=log.warning))
        self._stop_asked.pop(name, None)
        self.poke()
        return ok

    def restart(self, name: str) -> None:
        """Stop gracefully without touching the schedule; the next tick relaunches."""
        now = self._clock()
        self.settings.instance(name)
        st = status.read_status(self._dir(name))
        pid = int(st["pid"]) if st and st.get("pid") else None
        if pid is not None and self._alive(pid):
            self._request_stop(name, now)
        self.poke()

    def retry_now(self, name: str) -> None:
        self._backoff.clear(name)
        self.poke()

    def poke(self) -> None:
        if self._poke is not None:
            self._poke.set()

    # --- the loop ---------------------------------------------------------------------

    def request_shutdown(self) -> None:
        self._shutdown = True
        self.poke()

    async def run_forever(self) -> None:
        """Tick, then sleep interval_s or until poked. Workers keep running when this
        returns; the next start reattaches through status.json PIDs."""
        self._poke = asyncio.Event()
        self._shutdown = False
        while not self._shutdown:
            try:
                await asyncio.to_thread(self.tick)
            except Exception:
                log.exception("tick failed")
            try:
                await asyncio.wait_for(self._poke.wait(), timeout=self.interval_s)
            except TimeoutError:
                pass
            self._poke.clear()
        log.info("supervisor loop stopped; workers keep running")


def _parse_until(value) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _int_or_none(value) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _offline_note(retry: datetime, now: datetime) -> str:
    minutes = max(1, round((retry - now).total_seconds() / 60))
    return f"BlueStacks window not found. Retrying in {minutes} min."
