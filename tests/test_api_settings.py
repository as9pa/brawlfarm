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
