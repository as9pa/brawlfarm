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
    before = int(
        ((scheduler.read_control().get("accounts") or {}).get("alpha") or {}).get("nonce") or 0
    )
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
