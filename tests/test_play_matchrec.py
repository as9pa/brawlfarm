"""Per-match recording in observe mode: a stream opens on IN_MATCH, stays open through
UNKNOWN and POPUP, closes on a menu-side state, a closed session or the time cap, and one
stream failure switches match recording off for the rest of the session."""

from __future__ import annotations

from pathlib import Path

import pytest

from brawlfarm.core.states import State
from brawlfarm.play import matchrec


class FakeStream:
    def __init__(self, path: Path, *, fail: bool = False) -> None:
        self.path = path
        self.fail = fail
        self.started = False
        self.stopped = False

    def start(self) -> None:
        if self.fail:
            raise RuntimeError("no encoder")
        self.started = True

    def stop(self) -> None:
        self.stopped = True


@pytest.fixture()
def rec(monkeypatch):
    made: list[FakeStream] = []

    def factory(path: Path) -> FakeStream:
        s = FakeStream(path)
        made.append(s)
        return s

    monkeypatch.setattr(matchrec.play, "available", lambda: True)
    now = [0.0]
    r = matchrec.MatchRecorder(factory=factory, clock=lambda: now[0])
    return r, made, now


def test_a_match_opens_one_recording_and_a_results_screen_closes_it(rec, tmp_path: Path) -> None:
    r, made, now = rec
    r.observe(State.MENU, tmp_path)
    assert made == []
    r.observe(State.IN_MATCH, tmp_path)
    assert len(made) == 1 and made[0].started
    assert made[0].path == tmp_path / "match-1.h264"
    assert r.recording == tmp_path / "match-1.h264"
    r.observe(State.UNKNOWN, tmp_path)
    r.observe(State.POPUP, tmp_path)
    r.observe(State.IN_MATCH, tmp_path)
    assert len(made) == 1
    r.observe(State.RESULTS, tmp_path)
    assert made[0].stopped and r.recording is None
    r.observe(State.IN_MATCH, tmp_path)
    assert made[1].path == tmp_path / "match-2.h264"


def test_numbering_continues_from_files_already_in_the_session(rec, tmp_path: Path) -> None:
    r, made, now = rec
    (tmp_path / "match-1.h264").write_bytes(b"")
    (tmp_path / "match-2.h264").write_bytes(b"")
    r.observe(State.IN_MATCH, tmp_path)
    assert made[0].path == tmp_path / "match-3.h264"


def test_a_closed_session_and_the_time_cap_stop_the_recording(rec, tmp_path: Path) -> None:
    r, made, now = rec
    r.observe(State.IN_MATCH, tmp_path)
    r.observe(State.IN_MATCH, None)
    assert made[0].stopped
    r.observe(State.IN_MATCH, tmp_path)
    now[0] += matchrec.MAX_SECONDS + 1
    r.observe(State.UNKNOWN, tmp_path)
    assert made[1].stopped


def test_a_stream_failure_disables_recording_for_the_session(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(matchrec.play, "available", lambda: True)
    made: list[FakeStream] = []

    def factory(path: Path) -> FakeStream:
        s = FakeStream(path, fail=True)
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


def test_without_the_play_extra_nothing_is_recorded(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(matchrec.play, "available", lambda: False)
    calls = []
    r = matchrec.MatchRecorder(factory=lambda path: calls.append(path))
    r.observe(State.IN_MATCH, tmp_path)
    assert calls == [] and r.recording is None


def test_close_stops_an_open_recording(rec, tmp_path: Path) -> None:
    r, made, now = rec
    r.observe(State.IN_MATCH, tmp_path)
    r.close()
    assert made[0].stopped and r.recording is None
