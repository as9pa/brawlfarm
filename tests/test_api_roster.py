"""The roster block on GET and PUT /api/instances/{name}/plan, and the cache behind it:
one upstream call per instance per TTL, the last good list kept when a call fails, and the
three reasons the list can be missing. No network anywhere -- the clock and the fetcher
are injected."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from brawlfarm import settings as S
from brawlfarm.api.roster import RosterCache
from tests.apihelpers import make_client

PLAN_URL = "/api/instances/alpha/plan"
TAG = "#2P0YLQ9"  # invented from the game's alphabet; not an account that exists
TOKEN = "not-a-real-token"

PLAYER = {
    "tag": TAG,
    "brawlers": [
        {
            "id": 16000000,
            "name": "SHELLY",
            "trophies": 615,
            "highestTrophies": 700,
            "rank": 20,
            "power": 9,
            "gadgets": [{"id": 1, "name": "CLAY PIGEONS"}],
        },
        {
            "id": 16000101,
            "name": "NORI",
            "trophies": 812,
            "highestTrophies": 830,
            "rank": 25,
            "power": 11,
            "gadgets": [],
        },
        {
            "id": 16000002,
            "name": "TARA",
            "trophies": 540,
            "highestTrophies": 615,
            "rank": 19,
            "power": 11,
            "gadgets": [],
        },
    ],
}

NORI = {"id": 16000101, "name": "NORI", "trophies": 812, "highest": 830, "rank": 25, "power": 11}


class FakeClock:
    """A monotonic clock the test moves by hand."""

    def __init__(self, t: float = 1000.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t


class FakeFetch:
    """One GET /players/{tag}: counts its calls, hands back a body of whatever shape the
    test gives it, and can be made to raise."""

    def __init__(self, player: object) -> None:
        self.player = player
        self.calls: list[tuple[str, str]] = []
        self.boom: Exception | None = None

    def __call__(self, tag: str, token: str) -> object:
        self.calls.append((tag, token))
        if self.boom is not None:
            raise self.boom
        return self.player


@pytest.mark.asyncio
async def test_the_cache_fetches_once_per_ttl_and_sorts_by_trophies() -> None:
    clock, fetch = FakeClock(), FakeFetch(PLAYER)
    cache = RosterCache(now=clock, fetch=fetch)
    first, status = await cache.get("alpha", TAG, TOKEN)
    assert status == "ok"
    assert [b["name"] for b in first] == ["NORI", "SHELLY", "TARA"]
    assert first[0] == NORI  # six fields, highestTrophies renamed, no gadgets
    clock.t += 299.0
    again, status = await cache.get("alpha", TAG, TOKEN)
    assert status == "ok" and again == first and len(fetch.calls) == 1
    clock.t += 2.0  # now past the 300 s TTL
    await cache.get("alpha", TAG, TOKEN)
    assert len(fetch.calls) == 2


@pytest.mark.asyncio
async def test_every_instance_has_its_own_entry() -> None:
    fetch = FakeFetch(PLAYER)
    cache = RosterCache(now=FakeClock(), fetch=fetch)
    await cache.get("alpha", TAG, TOKEN)
    await cache.get("bravo", TAG, TOKEN)
    assert len(fetch.calls) == 2


@pytest.mark.asyncio
async def test_a_failed_refresh_keeps_the_last_good_roster() -> None:
    clock, fetch = FakeClock(), FakeFetch(PLAYER)
    cache = RosterCache(now=clock, fetch=fetch)
    good, _ = await cache.get("alpha", TAG, TOKEN)
    fetch.boom = RuntimeError("upstream said no")
    clock.t += 400.0
    stale, status = await cache.get("alpha", TAG, TOKEN)
    assert status == "unavailable" and stale == good


@pytest.mark.asyncio
async def test_a_first_fetch_that_fails_has_nothing_to_show() -> None:
    fetch = FakeFetch(PLAYER)
    fetch.boom = RuntimeError("upstream said no")
    cache = RosterCache(now=FakeClock(), fetch=fetch)
    assert await cache.get("alpha", TAG, TOKEN) == (None, "unavailable")


@pytest.mark.asyncio
async def test_a_body_that_is_not_a_player_keeps_the_last_good_roster() -> None:
    """ApiClient._get returns whatever the endpoint sent, and its type is `dict | list`:
    a 200 carrying a JSON array must cost this refresh, not the whole request."""
    clock, fetch = FakeClock(), FakeFetch(PLAYER)
    cache = RosterCache(now=clock, fetch=fetch)
    good, _ = await cache.get("alpha", TAG, TOKEN)
    fetch.player = [{"name": "SHELLY", "trophies": 615}]  # an array where an object belongs
    clock.t += 400.0
    stale, status = await cache.get("alpha", TAG, TOKEN)
    assert status == "unavailable" and stale == good


@pytest.mark.asyncio
async def test_an_entry_the_editor_could_not_draw_is_skipped_not_raised() -> None:
    fetch = FakeFetch(
        {
            "brawlers": [
                {"id": 16000003, "name": "COLT"},  # no trophies: nothing to place or draw
                {"id": 16000004, "trophies": 300},  # no name: plan_queue could not list it
                "SHELLY",  # not an object at all
                PLAYER["brawlers"][1],
            ]
        }
    )
    cache = RosterCache(now=FakeClock(), fetch=fetch)
    brawlers, status = await cache.get("alpha", TAG, TOKEN)
    assert status == "ok" and brawlers == [NORI]


@pytest.mark.asyncio
async def test_the_failure_log_carries_neither_the_tag_nor_the_token(caplog) -> None:
    fetch = FakeFetch(PLAYER)
    fetch.boom = RuntimeError(f"/players/{TAG} -> HTTP 403: bad token {TOKEN}")
    cache = RosterCache(now=FakeClock(), fetch=fetch)
    with caplog.at_level("WARNING", logger="brawlfarm.api"):
        await cache.get("alpha", TAG, TOKEN)
    assert "roster fetch failed" in caplog.text
    assert TAG not in caplog.text and TOKEN not in caplog.text


@pytest.fixture()
def api(tmp_path: Path):
    client, sup, home = make_client(tmp_path, ("alpha", "bravo"))
    try:
        yield client, sup, home
    finally:
        client.__exit__(None, None, None)


def _credentials(client, sup) -> tuple[FakeFetch, FakeClock]:
    """Give the app a token, a tag and an upstream that never leaves the process."""
    fetch, clock = FakeFetch(PLAYER), FakeClock()
    sup.settings.connection.brawl_api_token = TOKEN
    sup.settings.instance("alpha").player_tag = TAG
    client.app.state.roster = RosterCache(now=clock, fetch=fetch)
    return fetch, clock


def _farming(home: Path, sup, name: str, brawler: str) -> None:
    """What the worker writes when it picks a brawler. The view reads farm_brawler from
    status.json, so the tick after this one carries it."""
    d = S.instance_dir(home, name)
    d.mkdir(parents=True, exist_ok=True)
    (d / "status.json").write_text(
        json.dumps({"ts": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"), "farm_brawler": brawler}),
        encoding="utf-8",
    )
    sup.tick()


def test_get_carries_the_current_brawler_the_roster_and_the_queue(api) -> None:
    client, sup, home = api
    fetch, _clock = _credentials(client, sup)
    _farming(home, sup, "alpha", "NORI")
    body = client.get(PLAN_URL).json()
    assert set(body) == {
        "mode",
        "prestige_start",
        "goal_trophies",
        "maxed_fallback",
        "current",
        "roster",
        "queue",
        "roster_status",
    }
    assert body["current"] == {"brawler": "NORI", "trophies": 812, "goal": 1000}
    assert body["queue"] == ["TARA", "SHELLY"]
    assert body["roster"][0] == NORI
    assert body["roster_status"] == "ok"
    client.get(PLAN_URL)
    assert len(fetch.calls) == 1  # the second GET is served from the cache


def test_prestige_reports_the_prestige_threshold_as_the_goal(api) -> None:
    client, sup, home = api
    _credentials(client, sup)
    _farming(home, sup, "alpha", "NORI")
    body = client.put(PLAN_URL, json={"mode": "prestige", "goal_trophies": 1400}).json()
    assert body["goal_trophies"] == 1400  # the stored plan is untouched
    assert body["current"]["goal"] == 1000  # prestige always finishes a brawler at 1000
    assert body["queue"] == ["SHELLY", "TARA"]  # highest first, NORI excluded


def test_put_returns_the_same_enriched_shape_as_get(api) -> None:
    client, sup, _home = api
    _credentials(client, sup)
    put = client.put(PLAN_URL, json={"mode": "ladder", "goal_trophies": 700})
    assert put.status_code == 200
    assert set(put.json()) == set(client.get(PLAN_URL).json())
    assert put.json()["queue"] == ["TARA", "SHELLY"]  # 540 and 615 are the two under 700


def test_no_token_is_reported_not_guessed(api) -> None:
    client, sup, _home = api
    sup.settings.instance("alpha").player_tag = TAG
    body = client.get(PLAN_URL).json()
    assert body["roster_status"] == "no_token"
    assert body["roster"] is None and body["queue"] == []
    assert body["current"] == {"brawler": None, "trophies": None, "goal": 1000}


def test_no_tag_is_reported_not_guessed(api) -> None:
    client, sup, _home = api
    sup.settings.connection.brawl_api_token = TOKEN
    body = client.get(PLAN_URL).json()
    assert body["roster_status"] == "no_tag" and body["roster"] is None


def test_an_unavailable_upstream_still_serves_the_last_known_roster(api) -> None:
    client, sup, home = api
    fetch, clock = _credentials(client, sup)
    _farming(home, sup, "alpha", "NORI")
    assert client.get(PLAN_URL).json()["roster_status"] == "ok"
    fetch.boom = RuntimeError("upstream said no")
    clock.t += 400.0  # the TTL has expired, so the next GET tries the upstream again
    body = client.get(PLAN_URL).json()
    assert body["roster_status"] == "unavailable"
    assert body["roster"][0] == NORI  # the stale list is still worth showing
    assert body["current"]["trophies"] == 812


def test_a_brawler_the_roster_does_not_know_has_no_trophies(api) -> None:
    client, sup, home = api
    _credentials(client, sup)
    _farming(home, sup, "alpha", "SURGE")  # owned in game, absent from this fake payload
    body = client.get(PLAN_URL).json()
    assert body["current"] == {"brawler": "SURGE", "trophies": None, "goal": 1000}


def test_an_unknown_instance_is_still_a_404(api) -> None:
    client, _sup, _home = api
    assert client.get("/api/instances/ghost/plan").status_code == 404
