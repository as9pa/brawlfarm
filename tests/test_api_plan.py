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
        json.dumps({"mode": "optimal", "goal_trophies": 1500, "queue": ["Shelly"], "target": None}),
        encoding="utf-8",
    )
    body = client.get(PLAN_URL).json()
    assert body["mode"] == "ladder"  # load_plan aliases the removed mode
    assert body["goal_trophies"] == 1500
    assert set(body) == {"mode", "prestige_start", "goal_trophies", "maxed_fallback"}
