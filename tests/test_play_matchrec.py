"""Per-match recording in observe mode: a screencap source opens on IN_MATCH, stays open
through UNKNOWN and POPUP, closes on a menu-side state, a closed session or the time cap, and
one source failure switches match recording off for the rest of the session. Each new capture
becomes a JPEG in ``match-N/`` with one line in its ``frames.jsonl``."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import cv2
import numpy as np
import pytest

from brawlfarm.core.states import State
from brawlfarm.play import matchrec


class FakeSource:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.started = False
        self.stopped = False
        self.error: str | None = None
        self.frame: np.ndarray | None = None
        self.age: float | None = None

    def start(self) -> None:
        if self.fail:
            raise RuntimeError("adb is gone")
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def latest(self):
        return self.frame, self.age

    def capture(self, value: int = 0, age: float = 0.1) -> None:
        self.frame = np.full((900, 1600, 3), value, np.uint8)
        self.age = age


@pytest.fixture()
def rec():
    made: list[FakeSource] = []

    def factory() -> FakeSource:
        s = FakeSource()
        made.append(s)
        return s

    now = [0.0]
    r = matchrec.MatchRecorder(factory=factory, clock=lambda: now[0], wall=lambda: 1000.0 + now[0])
    return r, made, now


def _lines(folder: Path) -> list[dict]:
    path = folder / "frames.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_a_match_opens_one_recording_and_a_results_screen_closes_it(rec, tmp_path: Path) -> None:
    r, made, now = rec
    r.observe(State.MENU, tmp_path)
    assert made == []
    r.observe(State.IN_MATCH, tmp_path)
    assert len(made) == 1 and made[0].started
    assert r.recording == tmp_path / "match-1"
    assert (tmp_path / "match-1").is_dir()
    r.observe(State.UNKNOWN, tmp_path)
    r.observe(State.POPUP, tmp_path)
    r.observe(State.IN_MATCH, tmp_path)
    assert len(made) == 1
    r.observe(State.RESULTS, tmp_path)
    assert made[0].stopped and r.recording is None
    r.observe(State.IN_MATCH, tmp_path)
    assert r.recording == tmp_path / "match-2"


def test_each_new_capture_is_written_once_with_a_frames_line(rec, tmp_path: Path) -> None:
    r, made, now = rec
    r.observe(State.IN_MATCH, tmp_path)
    folder = tmp_path / "match-1"
    r.observe(State.IN_MATCH, tmp_path)
    assert list(folder.glob("*.jpg")) == [], "no frame yet, nothing written"
    made[0].capture(10, age=0.12)
    now[0] += 0.25
    r.observe(State.IN_MATCH, tmp_path)
    now[0] += 0.25
    r.observe(State.UNKNOWN, tmp_path)  # the same capture again: never written twice
    made[0].capture(20, age=0.05)
    now[0] += 0.25
    r.observe(State.UNKNOWN, tmp_path)
    assert sorted(p.name for p in folder.glob("*.jpg")) == ["0000.jpg", "0001.jpg"]
    assert _lines(folder) == [
        {"i": 0, "t": 1000.25, "age": 0.12, "state": "IN_MATCH"},
        {"i": 1, "t": 1000.75, "age": 0.05, "state": "UNKNOWN"},
    ]
    frame = cv2.imread(str(folder / "0000.jpg"))
    assert frame.shape == (900, 1600, 3), "full size, the size training needs"


def test_writes_are_capped_at_the_rate(rec, tmp_path: Path) -> None:
    r, made, now = rec
    assert matchrec.RATE_HZ == 5.0
    r.observe(State.IN_MATCH, tmp_path)
    for i in range(16):
        made[0].capture(i)
        now[0] += 0.0625
        r.observe(State.IN_MATCH, tmp_path)
    # one second of ticks at 16 a second, a fresh capture each: writes at 0.0625, 0.3125,
    # 0.5625 and 0.8125, never closer than 1 / RATE_HZ
    assert len(_lines(tmp_path / "match-1")) == 4


def test_starting_a_recording_logs_the_folder_once(rec, tmp_path: Path, caplog) -> None:
    r, made, now = rec
    with caplog.at_level(logging.INFO, logger="brawlfarm.play.matchrec"):
        r.observe(State.IN_MATCH, tmp_path)
        r.observe(State.IN_MATCH, tmp_path)
    assert not any("disconnect" in m for m in caplog.messages)
    assert sum(str(tmp_path / "match-1") in m for m in caplog.messages) == 1
    assert all(record.levelno == logging.INFO for record in caplog.records)


def test_numbering_continues_from_folders_and_old_clips(rec, tmp_path: Path) -> None:
    r, made, now = rec
    (tmp_path / "match-1.h264").write_bytes(b"")
    (tmp_path / "match-2").mkdir()
    (tmp_path / "match-3.h264").write_bytes(b"")
    r.observe(State.IN_MATCH, tmp_path)
    assert r.recording == tmp_path / "match-4"


def test_a_closed_session_and_the_time_cap_stop_the_recording(rec, tmp_path: Path) -> None:
    r, made, now = rec
    r.observe(State.IN_MATCH, tmp_path)
    r.observe(State.IN_MATCH, None)
    assert made[0].stopped
    r.observe(State.IN_MATCH, tmp_path)
    now[0] += matchrec.MAX_SECONDS + 1
    r.observe(State.UNKNOWN, tmp_path)
    assert made[1].stopped


def test_a_source_failure_disables_recording_for_the_session(tmp_path: Path) -> None:
    made: list[FakeSource] = []

    def factory() -> FakeSource:
        s = FakeSource(fail=True)
        made.append(s)
        return s

    r = matchrec.MatchRecorder(factory=factory)
    r.observe(State.IN_MATCH, tmp_path)
    r.observe(State.RESULTS, tmp_path)
    r.observe(State.IN_MATCH, tmp_path)
    assert len(made) == 1
    other = tmp_path / "other"
    other.mkdir()
    r.observe(State.MENU, None)
    r.observe(State.IN_MATCH, other)
    assert len(made) == 2, "a new session gets a fresh chance"


def test_recording_needs_no_play_extra(monkeypatch, rec, tmp_path: Path) -> None:
    from brawlfarm import play

    monkeypatch.setattr(play, "available", lambda: False)
    r, made, now = rec
    r.observe(State.IN_MATCH, tmp_path)
    assert len(made) == 1 and r.recording is not None


def test_the_default_source_is_the_screencap_source() -> None:
    from brawlfarm.play.capture import ScreencapSource

    assert isinstance(matchrec._default_factory(), ScreencapSource)


def test_close_stops_an_open_recording(rec, tmp_path: Path) -> None:
    r, made, now = rec
    r.observe(State.IN_MATCH, tmp_path)
    r.close()
    assert made[0].stopped and r.recording is None


def test_a_session_folder_that_cannot_be_listed_disables_recording(
    rec, tmp_path: Path, monkeypatch
) -> None:
    r, made, now = rec

    def boom(self, pattern):
        raise OSError("session folder gone")

    monkeypatch.setattr(Path, "glob", boom)
    r.observe(State.IN_MATCH, tmp_path)
    assert made == [] and r.recording is None


def test_a_frame_that_cannot_be_written_ends_recording_for_the_session(
    rec, tmp_path: Path, monkeypatch
) -> None:
    r, made, now = rec
    r.observe(State.IN_MATCH, tmp_path)
    made[0].capture(5)

    def broken(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(matchrec.preview, "encode", broken)
    now[0] += 1
    r.observe(State.IN_MATCH, tmp_path)
    assert made[0].stopped and r.recording is None
    r.observe(State.RESULTS, tmp_path)
    r.observe(State.IN_MATCH, tmp_path)
    assert len(made) == 1


def test_a_source_that_dies_mid_match_is_released_and_logged(rec, tmp_path: Path, caplog) -> None:
    r, made, now = rec
    r.observe(State.IN_MATCH, tmp_path)
    made[0].error = "3 captures failed"
    with caplog.at_level(logging.WARNING, logger="brawlfarm.play.matchrec"):
        r.observe(State.UNKNOWN, tmp_path)
    assert made[0].stopped and r.recording is None
    assert sum("ended early" in message for message in caplog.messages) == 1
    r.observe(State.IN_MATCH, tmp_path)
    assert len(made) == 1, "the same match never starts a second source"
    r.observe(State.RESULTS, tmp_path)
    r.observe(State.IN_MATCH, tmp_path)
    assert len(made) == 2, "the next match records again"


def test_a_new_session_records_at_once_after_a_source_died(rec, tmp_path: Path) -> None:
    r, made, now = rec
    first, second = tmp_path / "a", tmp_path / "b"
    first.mkdir()
    second.mkdir()
    r.observe(State.IN_MATCH, first)
    made[0].error = "3 captures failed"
    r.observe(State.IN_MATCH, first)
    r.observe(State.IN_MATCH, first)
    assert len(made) == 1, "the dead match stays unrecorded in its own session"
    r.observe(State.IN_MATCH, second)
    assert len(made) == 2, "the latch belongs to the session the source died in"
