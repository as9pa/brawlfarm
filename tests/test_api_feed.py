"""The activity feed: which session event kinds land in which chip, reading the newest
session file for GET .../feed, and the tailer that publishes new lines onto the bus —
starting at the end of a session already in progress, following a session roll, and
waiting for a half-written line to finish."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from brawlfarm import settings as S
from brawlfarm.api.events import EventBus
from brawlfarm.api.feed import FeedTailer, classify, latest_session, read_feed
from tests.apihelpers import build_settings, make_client


@pytest.fixture()
def api(tmp_path: Path):
    client, sup, home = make_client(tmp_path, ("alpha",))
    try:
        yield client, sup, home
    finally:
        client.__exit__(None, None, None)


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


def test_feed_route_returns_the_session_name_and_records(api) -> None:
    client, _sup, home = api
    session = S.instance_dir(home, "alpha") / "session-20260910-120000.jsonl"
    _append(session, "crash", err="adb gone")
    _append(session, "phase", to="queuing", frm="menu", games=0)
    body = client.get("/api/instances/alpha/feed").json()
    assert body["session"] == "session-20260910-120000.jsonl"
    assert [r["event"] for r in body["records"]] == ["crash", "phase"]
    assert (
        client.get("/api/instances/alpha/feed?kind=errors").json()["records"][0]["event"] == "crash"
    )
    assert client.get("/api/instances/alpha/feed?kind=nope").status_code == 422
    assert client.get("/api/instances/alpha/feed?limit=0").status_code == 422
    assert client.get("/api/instances/ghost/feed").status_code == 404


def test_feed_route_without_a_session_says_so(api) -> None:
    client, _sup, _home = api
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


def test_the_app_runs_a_tailer(api) -> None:
    client, _sup, _home = api
    assert isinstance(client.app.state.tailer, FeedTailer)
    assert client.app.state.tailer.interval_s == 2.0
