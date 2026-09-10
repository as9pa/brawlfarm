"""The supervisor tick against a temp home with fake process plumbing: launches one
worker per tick with the settings env, stops gracefully then kills after 110 s, honours
boot grace and offline backoff, and exposes start / stop / stop-now / restart / retry."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from brawlfarm import settings as S
from brawlfarm.core import scheduler, status
from brawlfarm.supervisor import Health, InstanceState, Supervisor
from brawlfarm.supervisor import loop as L

T0 = datetime(2026, 9, 10, 12, 0, 0)


@dataclass
class FakeProc:
    pid: int
    exited: bool = False

    def poll(self):
        return 0 if self.exited else None


@dataclass
class World:
    now: datetime = T0
    online: dict[int, bool] = field(default_factory=dict)
    alive: set[int] = field(default_factory=set)
    launches: list[tuple[list[str], dict[str, str], str]] = field(default_factory=list)
    kills: list[int] = field(default_factory=list)
    procs: list[FakeProc] = field(default_factory=list)
    refreshes: int = 0
    next_pid: int = 100

    def clock(self):
        return self.now

    def probe(self, adb_path, port, timeout_s=15.0):
        return self.online.get(port, True)

    def launcher(self, args, env, log_dir, name, module=None):
        self.launches.append((list(args), dict(env), name))
        proc = FakeProc(self.next_pid)
        self.next_pid += 1
        self.alive.add(proc.pid)
        self.procs.append(proc)
        return proc

    def is_alive(self, pid):
        return pid in self.alive

    def kill(self, pid, log=print):
        if pid in self.alive:
            self.alive.discard(pid)
            self.kills.append(pid)
            return True
        return False

    def refresh(self, now=None):
        self.refreshes += 1
        return 0


_PORTS = {"Pie64": 5555, "Rome64": 5565}
_TAGS = {"Pie64": "#2P0YLQ9", "Rome64": ""}


def _settings(names=("Pie64", "Rome64")) -> S.AppSettings:
    s = S.AppSettings(
        instances=[
            S.InstanceSettings(name=n, adb_port=_PORTS[n], player_tag=_TAGS[n]) for n in names
        ]
    )
    s.connection.brawl_api_token = "tok"  # the events refresh only runs with a token
    return s


def make_sup(tmp_path: Path, world: World, names=("Pie64", "Rome64")) -> Supervisor:
    s = _settings(names)
    S.save(s, tmp_path)
    sup = Supervisor(
        s,
        tmp_path,
        clock=world.clock,
        probe=world.probe,
        launcher=world.launcher,
        alive=world.is_alive,
        killer=world.kill,
        sleep=lambda _s: None,
        events_refresh=world.refresh,
    )
    # Schedule off = legacy always-run, so tests control "desired" through overrides.
    scheduler.set_enabled(list(names), False)
    return sup


@pytest.fixture()
def world() -> World:
    return World()


@pytest.fixture()
def sup(tmp_path: Path, world: World) -> Supervisor:
    return make_sup(tmp_path, world)


def _heartbeat(tmp_path: Path, name: str, pid: int, now: datetime, age_s: float = 5, **fields):
    d = S.instance_dir(tmp_path, name)
    d.mkdir(parents=True, exist_ok=True)
    ts = (now - timedelta(seconds=age_s)).strftime("%Y-%m-%dT%H:%M:%S")
    status.write_status(d, {"pid": pid, "phase": "playing", "games_played": 3, **fields})
    # write_status stamps "now"; rewrite ts to the age we want
    import json

    p = d / "status.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    data["ts"] = ts
    p.write_text(json.dumps(data), encoding="utf-8")


def _view(views, name):
    return next(v for v in views if v.name == name)


def test_init_points_the_core_at_home(sup: Supervisor, tmp_path: Path) -> None:
    from brawlfarm.core import config

    assert config.HOME_DIR == tmp_path.resolve()
    assert set(config.INSTANCES) == {"Pie64", "Rome64"}
    assert config.INSTANCES["Pie64"]["data"] == "instances/Pie64"


def test_first_tick_launches_one_worker_and_defers_the_rest(sup, world, tmp_path) -> None:
    views = sup.tick()
    assert len(world.launches) == 1
    args, env, name = world.launches[0]
    assert name == "Pie64"
    assert args == ["--select-brawler", "--dnd"]
    assert env["BRAWL_ADB_PORT"] == "5555"
    assert env["BRAWL_DATA_DIR"] == "instances/Pie64"
    assert env["BRAWLFARM_HOME"] == str(tmp_path.resolve())
    assert "SystemRoot" in env or "PATH" in env  # inherits the parent environment
    assert _view(views, "Pie64").state == InstanceState.STARTING
    assert _view(views, "Rome64").state == InstanceState.STARTING
    assert _view(views, "Rome64").note == "Waiting for its turn to start"
    assert world.refreshes == 1
    world.now += timedelta(seconds=60)
    sup.tick()
    assert [n for _, _, n in world.launches] == ["Pie64", "Rome64"]


def test_boot_grace_prevents_double_launch(sup, world) -> None:
    sup.tick()
    world.now += timedelta(seconds=60)
    sup.tick()
    world.now += timedelta(seconds=60)  # 120 s after Pie64's launch, still no heartbeat
    views = sup.tick()
    assert [n for _, _, n in world.launches] == ["Pie64", "Rome64"]
    assert _view(views, "Pie64").state == InstanceState.STARTING
    world.now += timedelta(seconds=120)  # 240 s: grace over, still dead -> relaunch
    sup.tick()
    assert [n for _, _, n in world.launches] == ["Pie64", "Rome64", "Pie64"]


def test_healthy_worker_is_farming_and_left_alone(sup, world, tmp_path) -> None:
    world.alive.add(4242)
    _heartbeat(tmp_path, "Pie64", 4242, world.now, farm_brawler="Shelly")
    views = sup.tick()
    v = _view(views, "Pie64")
    assert v.state == InstanceState.FARMING
    assert v.health == Health.HEALTHY
    assert v.pid == 4242
    assert v.games_played == 3
    assert v.farm_brawler == "Shelly"
    assert [n for _, _, n in world.launches] == ["Rome64"]


def test_stale_worker_is_killed_then_relaunched(sup, world, tmp_path) -> None:
    world.alive.add(4242)
    _heartbeat(tmp_path, "Pie64", 4242, world.now, age_s=500)
    sup.tick()
    assert world.kills == [4242]
    assert [n for _, _, n in world.launches] == ["Pie64"]


def test_hung_worker_is_killed_before_relaunch(tmp_path, world) -> None:
    sup = make_sup(tmp_path, world, ("Pie64",))
    sup.tick()  # launches a worker that never writes status.json
    first = world.procs[0]
    world.now += timedelta(seconds=240)  # boot grace over, still no heartbeat, still running
    views = sup.tick()
    assert world.kills == [first.pid]
    assert [n for _, _, n in world.launches] == ["Pie64", "Pie64"]
    assert _view(views, "Pie64").state == InstanceState.STARTING


def test_graceful_stop_then_kill_after_escalation(sup, world, tmp_path) -> None:
    world.alive.add(4242)
    _heartbeat(tmp_path, "Pie64", 4242, world.now)
    sup.stop("Pie64")
    flag = S.instance_dir(tmp_path, "Pie64") / "stop.flag"
    assert flag.exists()
    views = sup.tick()
    v = _view(views, "Pie64")
    assert v.state == InstanceState.STOPPING
    assert v.until == world.now + timedelta(seconds=110)
    assert world.kills == []
    world.now += timedelta(seconds=60)
    _heartbeat(tmp_path, "Pie64", 4242, world.now)
    sup.tick()
    assert world.kills == []
    world.now += timedelta(seconds=60)
    _heartbeat(tmp_path, "Pie64", 4242, world.now)
    views = sup.tick()
    assert world.kills == [4242]
    assert _view(views, "Pie64").state == InstanceState.STOPPED  # killed this tick
    assert _view(views, "Pie64").pid is None
    world.now += timedelta(seconds=60)
    views = sup.tick()
    assert _view(views, "Pie64").state == InstanceState.STOPPED
    assert [n for _, _, n in world.launches] == ["Rome64"]  # never relaunched while stopped


def test_undo_stop_is_start(sup, world, tmp_path) -> None:
    world.alive.add(4242)
    _heartbeat(tmp_path, "Pie64", 4242, world.now)
    sup.stop("Pie64")
    sup.start("Pie64")
    assert not (S.instance_dir(tmp_path, "Pie64") / "stop.flag").exists()
    views = sup.tick()
    assert _view(views, "Pie64").state == InstanceState.FARMING
    assert world.kills == []


def test_stop_now_only_while_pending(sup, world, tmp_path) -> None:
    world.alive.add(4242)
    _heartbeat(tmp_path, "Pie64", 4242, world.now)
    assert sup.stop_now("Pie64") is False
    assert world.kills == []
    sup.stop("Pie64")
    assert sup.stop_now("Pie64") is True
    assert world.kills == [4242]


def test_restart_stops_then_relaunches(sup, world, tmp_path) -> None:
    world.alive.add(4242)
    _heartbeat(tmp_path, "Pie64", 4242, world.now)
    sup.tick()
    sup.restart("Pie64")
    flag = S.instance_dir(tmp_path, "Pie64") / "stop.flag"
    assert flag.exists()
    views = sup.tick()
    assert _view(views, "Pie64").state == InstanceState.STOPPING
    world.alive.discard(4242)  # the worker exited at the menu
    world.now += timedelta(seconds=60)
    views = sup.tick()
    assert [n for _, _, n in world.launches] == ["Rome64", "Pie64"]
    assert _view(views, "Pie64").state == InstanceState.STARTING


def test_offline_backoff_and_alert(tmp_path, world, monkeypatch) -> None:
    sup = make_sup(tmp_path, world, ("Pie64",))  # one instance, so nothing else launches
    alerts: list[tuple[str, dict]] = []
    monkeypatch.setattr(L.notify, "maybe_alert", lambda kind, fields: alerts.append((kind, fields)))
    world.online[5555] = False
    views = sup.tick()
    v = _view(views, "Pie64")
    assert v.state == InstanceState.OFFLINE
    assert v.until == world.now + timedelta(minutes=2)
    assert v.note == "BlueStacks window not found. Retrying in 2 min."
    assert world.launches == []
    world.now += timedelta(minutes=1)
    sup.tick()  # still inside the 2 min window: no probe, no launch
    assert world.launches == []
    world.now += timedelta(minutes=1)
    sup.tick()  # miss 2 -> 4 min
    world.now += timedelta(minutes=4)
    sup.tick()  # miss 3 -> 8 min, alert
    assert alerts == [("offline", {"instance": "Pie64", "misses": 3})]
    assert world.launches == []
    sup.retry_now("Pie64")
    world.online[5555] = True
    views = sup.tick()
    assert [n for _, _, n in world.launches] == ["Pie64"]
    assert _view(views, "Pie64").state == InstanceState.STARTING


def test_events_refresh_only_with_a_token(tmp_path, world) -> None:
    sup = make_sup(tmp_path, world, ("Pie64",))
    sup.settings.connection.brawl_api_token = ""
    sup.apply_settings(sup.settings)
    sup.tick()
    assert world.refreshes == 0


def test_scheduled_break_and_run_for_hours(sup, world, tmp_path) -> None:
    scheduler.write_override("Pie64", "stop", world.now + timedelta(hours=2))
    views = sup.tick()
    assert _view(views, "Pie64").state == InstanceState.STOPPED
    scheduler.set_enabled(["Pie64"], True)  # caps come from the scheduler, so turn it on
    sup.start("Pie64", hours=1.5)
    views = sup.tick()
    assert _view(views, "Pie64").state == InstanceState.STARTING
    assert world.launches[-1][0] == ["--select-brawler", "--dnd", "--max-minutes", "90"]


def test_state_change_callbacks(sup, world, tmp_path) -> None:
    seen: list[tuple[str, str]] = []
    sup.subscribe(lambda v: seen.append((v.name, v.state)))
    sup.tick()
    world.now += timedelta(seconds=60)
    sup.tick()
    assert seen == [("Pie64", "starting"), ("Rome64", "starting")]
    world.alive.add(7)
    _heartbeat(tmp_path, "Pie64", 7, world.now)
    sup.tick()
    assert seen[-1] == ("Pie64", "farming")


def test_desired_stop_from_scheduler_writes_flag_without_user_action(sup, world, tmp_path) -> None:
    world.alive.add(4242)
    _heartbeat(tmp_path, "Pie64", 4242, world.now)
    scheduler.write_override("Pie64", "stop", world.now + timedelta(hours=1))
    views = sup.tick()
    assert (S.instance_dir(tmp_path, "Pie64") / "stop.flag").exists()
    assert _view(views, "Pie64").state == InstanceState.STOPPING


@pytest.mark.asyncio
async def test_run_forever_ticks_and_shuts_down(sup, world) -> None:
    import asyncio

    sup.interval_s = 0.05
    task = asyncio.create_task(sup.run_forever())
    await asyncio.sleep(0.2)
    sup.poke()
    await asyncio.sleep(0.05)
    sup.request_shutdown()
    await asyncio.wait_for(task, 2)
    assert world.launches  # at least one tick ran
