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
from brawlfarm.supervisor import InstanceState
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
        "last_session",
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
        [
            (noon - timedelta(hours=1), 8),
            (noon - timedelta(hours=2), -3),
            (noon - timedelta(days=1), 99),
        ],
    )
    client, _sup, _home = make_client(tmp_path, ("alpha",), world=world)
    try:
        payload = client.get("/api/instances").json()["instances"][0]
    finally:
        client.__exit__(None, None, None)
    # A disconnect in the heartbeat is "reconnecting" to derive_state, not "farming".
    assert payload["state"] == "reconnecting"
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
        [
            (now - timedelta(hours=1), 9),
            (now - timedelta(hours=2), -4),
            (now - timedelta(days=1), 50),
        ],
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


def _offline_client(tmp_path: Path):
    """alpha and bravo with no BlueStacks window, so the startup tick leaves them offline
    instead of starting them: everything in LIVE_STATES is refused by the delete route, and
    the default fixture's instances are STARTING the moment the lifespan tick has run."""
    world = FakeWorld()
    world.online[5555] = False
    world.online[5565] = False
    return make_client(tmp_path, ("alpha", "bravo"), world=world)


def test_deleting_data_removes_the_folder_and_keeps_the_instance(tmp_path: Path) -> None:
    client, sup, home = _offline_client(tmp_path)
    try:
        inst_dir = S.instance_dir(home, "alpha")
        (inst_dir / "sessions").mkdir(parents=True, exist_ok=True)
        (inst_dir / "games.csv").write_text("battleTime,trophyChange\n", encoding="utf-8")
        (inst_dir / "sessions" / "session-20260911-100000.jsonl").write_text(
            '{"ts": "2026-09-11T10:00:00", "kind": "start"}\n', encoding="utf-8"
        )
        S.instance_dir(home, "bravo").mkdir(parents=True, exist_ok=True)

        r = client.delete("/api/instances/alpha/data")
        assert r.status_code == 204
        assert r.content == b""
        assert not inst_dir.exists()
        assert S.instance_dir(home, "bravo").exists()  # only the one that was asked for
        # This deletes the folder, not the instance: it is still in the fleet and the file.
        assert [i.name for i in sup.settings.instances] == ["alpha", "bravo"]
        assert "alpha" in S.config_path(home).read_text(encoding="utf-8")
    finally:
        client.__exit__(None, None, None)


def test_deleting_data_twice_is_still_204(tmp_path: Path) -> None:
    client, _sup, home = _offline_client(tmp_path)
    try:
        S.instance_dir(home, "alpha").mkdir(parents=True, exist_ok=True)
        assert client.delete("/api/instances/alpha/data").status_code == 204
        # Idempotent: a folder that is already gone is the state the caller asked for.
        assert client.delete("/api/instances/alpha/data").status_code == 204
        assert not S.instance_dir(home, "alpha").exists()
    finally:
        client.__exit__(None, None, None)


def test_deleting_data_for_an_unknown_or_malformed_name_is_404(tmp_path: Path) -> None:
    client, _sup, _home = _offline_client(tmp_path)
    try:
        assert client.delete("/api/instances/charlie/data").status_code == 404
        r = client.delete("/api/instances/bad.name/data")
        assert r.status_code == 404
        assert r.json() == {"detail": "unknown instance"}
    finally:
        client.__exit__(None, None, None)


def test_deleting_data_refuses_while_the_worker_is_alive(tmp_path: Path) -> None:
    world = FakeWorld()
    world.alive.add(4242)
    _heartbeat(tmp_path, "bravo", 4242, world.now)
    client, sup, home = make_client(tmp_path, ("alpha", "bravo"), world=world)
    try:
        assert next(v for v in sup.views() if v.name == "bravo").state == InstanceState.FARMING
        r = client.delete("/api/instances/bravo/data")
        assert r.status_code == 409
        assert r.json() == {"detail": "Stop bravo before deleting its data"}
        # Deleting the files a live worker is writing would leave it logging into nothing.
        assert (S.instance_dir(home, "bravo") / "status.json").exists()
    finally:
        client.__exit__(None, None, None)


def test_deleting_data_refuses_a_target_outside_the_data_folder(tmp_path, monkeypatch) -> None:
    client, _sup, _home = _offline_client(tmp_path)
    try:
        elsewhere = Path(tmp_path) / "elsewhere" / "alpha"
        elsewhere.mkdir(parents=True, exist_ok=True)
        # The folder name comes out of config.toml, so a resolved path that left
        # <home>/instances is a refusal rather than a delete, whatever put it there.
        monkeypatch.setattr(instances.S, "instance_dir", lambda home, name: elsewhere)
        r = client.delete("/api/instances/alpha/data")
        assert r.status_code == 400
        assert r.json() == {"detail": "refusing to delete outside the data folder"}
        assert elsewhere.exists()
    finally:
        client.__exit__(None, None, None)


def test_a_file_still_in_use_is_a_409_naming_the_instance(tmp_path, monkeypatch) -> None:
    client, _sup, home = _offline_client(tmp_path)
    try:
        S.instance_dir(home, "alpha").mkdir(parents=True, exist_ok=True)

        def locked(path):
            raise OSError("the process cannot access the file because it is being used")

        monkeypatch.setattr(instances.shutil, "rmtree", locked)
        r = client.delete("/api/instances/alpha/data")
        assert r.status_code == 409
        assert r.json() == {"detail": "could not delete alpha's data; a file is still in use"}
        assert S.instance_dir(home, "alpha").exists()
    finally:
        client.__exit__(None, None, None)
