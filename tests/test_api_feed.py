"""The activity feed: which session event kinds land in which chip, reading the newest
session file for GET .../feed, and the tailer that publishes new lines onto the bus —
starting at the end of a session already in progress, following a session roll, and
waiting for a half-written line to finish."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from brawlfarm import settings as S
from brawlfarm.api import feed
from brawlfarm.api.events import EventBus
from brawlfarm.api.feed import FeedTailer, classify, latest_session, read_feed, scan_lines
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


class RacingPath:
    """A session path that lets the worker win a byte race: the first time anything opens
    it, one more complete line lands on disk first. Only the handful of attributes the
    tailer uses are delegated; identity equality is what `known != path` wants anyway."""

    def __init__(self, real: Path, inject) -> None:
        self._real = real
        self._inject = inject
        self.opened = 0

    @property
    def name(self) -> str:
        return self._real.name

    def open(self, *args, **kwargs):
        self.opened += 1
        if self.opened == 1:
            self._inject()
        return self._real.open(*args, **kwargs)

    def stat(self):
        return self._real.stat()


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
        "seq": 5,
        "event": "phase",
        "category": "matches",
        "fields": {"to": "queuing", "frm": "menu", "games": 0},
    }
    # The dropped tap and the torn line still consume their own line numbers.
    assert [r["seq"] for r in records] == [1, 4, 5]
    assert [r["event"] for r in read_feed(tmp_path, "errors")] == ["crash"]
    assert [r["event"] for r in read_feed(tmp_path, "matches", limit=1)] == ["phase"]


def test_read_feed_is_empty_without_a_session(tmp_path: Path) -> None:
    assert latest_session(tmp_path) is None
    assert read_feed(tmp_path) == []


def test_scan_lines_stops_at_a_half_written_tail(tmp_path: Path) -> None:
    session = tmp_path / "session-20260911-100000.jsonl"
    _append(session, "start", max_minutes=90)
    _append(session, "phase", to="queuing", frm="menu", games=0)
    whole = session.stat().st_size
    assert scan_lines(session) == (2, whole)
    with session.open("a", encoding="utf-8") as f:
        f.write('{"ts": "2026-09-11T18:05:00", "kind": "rec')
    # The torn line is not a line yet; it becomes line 3 once the worker finishes it. The
    # offset stops just before it, so the next read picks it up whole rather than skipping
    # the bytes already on disk.
    assert scan_lines(session) == (2, whole)
    assert scan_lines(tmp_path / "nothing.jsonl") == (0, 0)


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
    published = [(e.kind, e.data["record"]["event"], e.data["record"]["seq"]) for e in bus.recent()]
    assert published == [("feed", "crash", 3), ("feed", "recover", 5)]
    assert bus.recent()[0].data["instance"] == "alpha"
    assert bus.recent()[0].data["session"] == "session-20260910-100000.jsonl"
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
    # A new file starts its own numbering at 1, not where the old one left off.
    assert bus.recent()[-1].data["record"]["seq"] == 1
    assert bus.recent()[-1].data["session"] == "session-20260910-120000.jsonl"


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
    assert record["seq"] == 1  # the file was empty when the tailer first looked


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


@pytest.mark.asyncio
async def test_get_and_the_stream_agree_on_a_line_number(tmp_path: Path) -> None:
    """The panel de-duplicates a streamed record against a polled one by (session, seq),
    so the two paths have to number the same physical line identically -- including the
    lines neither path shows."""
    inst_dir = S.instance_dir(tmp_path, "alpha")
    session = inst_dir / "session-20260911-100000.jsonl"
    _append(session, "start", max_minutes=90)  # line 1
    _append(session, "tap", button="play", x=1, y=2)  # line 2, dropped by both paths
    bus = EventBus()
    tailer = FeedTailer(tmp_path, StubSup(build_settings(("alpha",))), bus)
    assert await tailer.poll_once() == 0  # joins the session already in progress at its end

    _append(session, "crash", err="adb gone")  # line 3
    assert await tailer.poll_once() == 1
    streamed = bus.recent()[-1].data
    assert streamed["instance"] == "alpha"
    assert streamed["session"] == "session-20260911-100000.jsonl"
    assert streamed["record"]["seq"] == 3

    polled = read_feed(inst_dir)
    assert [(r["event"], r["seq"]) for r in polled] == [("start", 1), ("crash", 3)]
    assert polled[-1] == streamed["record"]


@pytest.mark.asyncio
async def test_a_line_written_during_the_first_look_is_not_renumbered(
    tmp_path: Path, monkeypatch
) -> None:
    """The first look has to take the file's length and its line count from one read.
    Taking them separately leaves a window: a line the worker appends inside it is counted
    but still sits past the recorded offset, so the tailer reads it a second time and every
    number it hands out for that session is one ahead of the number GET gives the same
    line -- which breaks the panel's de-duplication on (session, seq)."""
    inst_dir = S.instance_dir(tmp_path, "alpha")
    session = inst_dir / "session-20260911-100000.jsonl"
    _append(session, "start", max_minutes=90)  # line 1
    _append(session, "phase", to="queuing", frm="menu", games=0)  # line 2
    racing = RacingPath(session, lambda: _append(session, "recover", reason="stuck", attempt=1))
    monkeypatch.setattr(feed, "latest_session", lambda _dir: racing)
    bus = EventBus()
    tailer = FeedTailer(tmp_path, StubSup(build_settings(("alpha",))), bus)

    # Line 3 lands while the tailer is looking; it is history like the two before it.
    assert await tailer.poll_once() == 0
    assert racing.opened >= 1
    assert bus.recent() == []

    _append(session, "crash", err="adb gone")  # line 4
    assert await tailer.poll_once() == 1
    monkeypatch.undo()  # the GET path reads the real file, not the racing stand-in
    streamed = bus.recent()[-1].data["record"]
    assert streamed["event"] == "crash"
    assert streamed["seq"] == 4
    assert read_feed(inst_dir)[-1] == streamed


@pytest.mark.asyncio
async def test_a_torn_tail_at_first_look_is_published_once_and_whole(tmp_path: Path) -> None:
    """The offset stops before a half-written tail rather than past it, so when its newline
    lands the line is read whole -- once, with the number GET gives it."""
    inst_dir = S.instance_dir(tmp_path, "alpha")
    session = inst_dir / "session-20260911-100000.jsonl"
    _append(session, "start", max_minutes=90)  # line 1
    with session.open("a", encoding="utf-8") as f:
        f.write('{"ts": "2026-09-11T18:05:00", "kind": "cra')  # line 2, mid-write
    bus = EventBus()
    tailer = FeedTailer(tmp_path, StubSup(build_settings(("alpha",))), bus)
    assert await tailer.poll_once() == 0  # a torn tail is not a line yet

    with session.open("a", encoding="utf-8") as f:
        f.write('sh", "err": "adb gone"}\n')
    assert await tailer.poll_once() == 1
    assert await tailer.poll_once() == 0  # numbered once, not again on the next pass
    streamed = bus.recent()[-1].data["record"]
    assert (streamed["event"], streamed["seq"]) == ("crash", 2)
    assert streamed["fields"] == {"err": "adb gone"}
    assert read_feed(inst_dir)[-1] == streamed
