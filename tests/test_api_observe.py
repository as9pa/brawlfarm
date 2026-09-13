"""The observe route: it only starts from stopped, it writes the observe override, and
turning it off is the ordinary stop. Nothing here launches a process or talks to adb."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

from brawlfarm import settings as S
from brawlfarm.api.deps import LIVE_STATES
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


def _park(client, sup, world, name: str) -> None:
    """Stop the instance the startup tick launched, so the route's guard is satisfied. The
    fake worker's pid has to leave the world the way an exiting process would, and the
    clock has to pass the boot grace, or the instance still reads STARTING, which is live.
    """
    client.post(f"/api/instances/{name}/stop")
    view = next(v for v in sup.views() if v.name == name)
    if view.pid is not None:
        world.alive.discard(view.pid)
    world.now += timedelta(seconds=BOOT_GRACE_S + 20)
    sup.tick()
    assert next(v for v in sup.views() if v.name == name).state not in LIVE_STATES


def test_observe_refuses_a_running_instance_and_writes_nothing(api) -> None:
    client, sup, _home, _world = api
    name = sup.settings.instances[0].name
    r = client.post(f"/api/instances/{name}/observe", json={"on": True})
    assert r.status_code == 409
    assert scheduler.read_override(name) is None


def test_observe_on_writes_the_override_and_launches_with_observe(api) -> None:
    client, sup, _home, world = api
    name = sup.settings.instances[0].name
    _park(client, sup, world, name)
    r = client.post(f"/api/instances/{name}/observe", json={"on": True})
    assert r.status_code == 202 and r.json() == {"ok": True}
    assert (scheduler.read_override(name) or {})["mode"] == "observe"
    world.now += timedelta(seconds=BOOT_GRACE_S + 20)
    sup.tick()
    assert [a for a, _env, n in world.launches if n == name][-1] == ["--observe"]


def test_observe_on_again_while_observing_is_accepted(api) -> None:
    """Already observing is not a handoff from farming, so a second on passes the guard
    and lands on the same override the first one wrote."""
    client, sup, _home, world = api
    name = sup.settings.instances[0].name
    _park(client, sup, world, name)
    client.post(f"/api/instances/{name}/observe", json={"on": True})
    world.now += timedelta(seconds=BOOT_GRACE_S + 20)
    sup.tick()
    view = next(v for v in sup.views() if v.name == name)
    assert view.desired == "observe" and view.state in LIVE_STATES
    r = client.post(f"/api/instances/{name}/observe", json={"on": True})
    assert r.status_code == 202 and r.json() == {"ok": True}
    assert (scheduler.read_override(name) or {})["mode"] == "observe"


def test_observe_off_stops_it(api) -> None:
    client, sup, home, world = api
    name = sup.settings.instances[0].name
    _park(client, sup, world, name)
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
