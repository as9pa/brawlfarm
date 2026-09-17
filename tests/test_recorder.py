import json
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import pytest

from brawlfarm.core import vision
from brawlfarm.core.recorder import Recorder
from brawlfarm.core.states import State


class Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


def _screen(v: int = 0) -> np.ndarray:
    return np.full((900, 1600, 3), v, dtype=np.uint8)


@pytest.fixture
def rec(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(vision, "score", lambda screen, name: 0.25)
    data = tmp_path / "data" / "Pie64"
    data.mkdir(parents=True)
    clock = Clock()
    wall = lambda: datetime(2026, 9, 12, 21, 11, 3, 200000)  # noqa: E731
    r = Recorder(tmp_path / "calibration", "Pie64", data / "record.flag", clock=clock, wall=wall)
    return r, clock, data, tmp_path / "calibration"


def test_off_by_default_writes_nothing(rec):
    r, clock, data, root = rec
    r.poll()
    assert r.observe(_screen(), State.MENU, "menu") is False
    assert not (root / "recordings").exists()
    st = json.loads((data / "recorder.json").read_text(encoding="utf-8"))
    assert st == {
        "on": False,
        "frames": 0,
        "bytes": 0,
        "session": None,
        "path": None,
        "reason": None,
        "last_session": None,
        "last_frames": 0,
    }


def test_flag_opens_session_and_writes_labeled_frames(rec):
    r, clock, data, root = rec
    (data / "record.flag").touch()
    r.poll()
    assert r.observe(_screen(), State.MENU, "menu") is True
    assert r.observe(_screen(), State.MENU, "menu") is False  # same state, < 1 s
    clock.t += 1.0
    assert r.observe(_screen(), State.MENU, "menu") is True
    assert r.observe(_screen(), State.MATCHMAKING, "queue") is True  # state change
    session = root / "recordings" / "Pie64" / "20260912-211103"
    assert sorted(p.name for p in session.glob("*.jpg")) == [
        "0001-menu.jpg",
        "0002-menu.jpg",
        "0003-matchmaking.jpg",
    ]
    raw = (session / "labels.jsonl").read_text(encoding="utf-8").splitlines()
    lines = [json.loads(ln) for ln in raw]
    assert [ln["seq"] for ln in lines] == [1, 2, 3]
    assert lines[0]["ts"] == "21:11:03.2"
    assert lines[2]["state"] == "matchmaking" and lines[2]["phase"] == "queue"
    assert set(lines[0]["scores"]) == set(vision.TEMPLATE_NAMES)
    st = r.status()
    assert st["on"] is True and st["frames"] == 3 and st["session"] == "20260912-211103"
    assert st["path"] == "recordings/Pie64/20260912-211103"
    assert st["bytes"] > 0


def test_frames_are_half_size_by_default(rec):
    r, clock, data, root = rec
    (data / "record.flag").touch()
    r.poll()
    assert r.observe(_screen(), State.MENU, "menu") is True
    session = root / "recordings" / "Pie64" / "20260912-211103"
    assert cv2.imread(str(session / "0001-menu.jpg")).shape == (450, 800, 3)


def test_full_size_keeps_the_native_frame(rec):
    _, clock, data, root = rec
    wall = lambda: datetime(2026, 9, 12, 21, 11, 3, 200000)  # noqa: E731
    r = Recorder(root, "Pie64", data / "record.flag", clock=clock, wall=wall, full_size=True)
    (data / "record.flag").touch()
    r.poll()
    assert r.observe(_screen(), State.MENU, "menu") is True
    session = root / "recordings" / "Pie64" / "20260912-211103"
    assert cv2.imread(str(session / "0001-menu.jpg")).shape == (900, 1600, 3)


def test_flag_removed_closes_session(rec):
    r, clock, data, root = rec
    (data / "record.flag").touch()
    r.poll()
    r.observe(_screen(), State.MENU, "menu")
    (data / "record.flag").unlink()
    r.poll()
    assert r.observe(_screen(), State.RESULTS, "results") is False
    st = r.status()
    assert st["on"] is False and st["last_session"] == "20260912-211103" and st["last_frames"] == 1


def test_frame_cap_closes_session(rec, monkeypatch):
    r, clock, data, root = rec
    monkeypatch.setattr(Recorder, "MAX_FRAMES", 3)
    (data / "record.flag").touch()
    r.poll()
    for i in range(3):
        clock.t += 1.0
        assert r.observe(_screen(), State.MENU, "menu") is True
    clock.t += 1.0
    assert r.observe(_screen(), State.MENU, "menu") is False
    assert r.status()["on"] is False and r.status()["reason"] == "frame_cap"
    r.poll()  # flag still set: stays closed
    assert r.status()["on"] is False


def test_disk_cap_refuses_to_open(rec, monkeypatch):
    r, clock, data, root = rec
    monkeypatch.setattr(Recorder, "MAX_BYTES", 10)
    old = root / "recordings" / "Pie64" / "20260101-000000"
    old.mkdir(parents=True)
    (old / "0001-menu.jpg").write_bytes(b"x" * 11)
    (data / "record.flag").touch()
    r.poll()
    assert r.status()["on"] is False and r.status()["reason"] == "disk_cap"
    assert r.observe(_screen(), State.MENU, "menu") is False


def test_write_failure_does_not_raise(rec, monkeypatch):
    r, clock, data, root = rec
    (data / "record.flag").touch()
    r.poll()
    from brawlfarm.core import preview

    def boom(screen, *, full=False):
        raise OSError("disk gone")

    monkeypatch.setattr(preview, "encode", boom)
    assert r.observe(_screen(), State.MENU, "menu") is False
    assert r.status()["on"] is False
