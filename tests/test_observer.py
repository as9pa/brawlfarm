"""Observe mode: the loop records labeled frames off a fake adb that cannot tap, keeps
record.flag for exactly as long as it runs, refuses a display that is not 1600x900, and
stops on stop.flag. No real device, no real screencap, no tap function anywhere."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from brawlfarm.core import adb, config, observer


def _frame() -> np.ndarray:
    return np.zeros((config.SCREEN_H, config.SCREEN_W, 3), np.uint8)


@pytest.fixture()
def data(tmp_path: Path, monkeypatch) -> Path:
    """An instance folder under a throwaway home, with adb faked out entirely."""
    inst = tmp_path / "instances" / "alpha"
    inst.mkdir(parents=True)
    monkeypatch.setattr(config, "HOME_DIR", tmp_path)
    monkeypatch.setattr(config, "DATA_DIR", inst)
    monkeypatch.setattr(observer, "POLL_INTERVAL_S", 0.0)
    monkeypatch.setattr(adb, "connect", lambda serial=None: None)
    monkeypatch.setattr(adb, "screen_size", lambda: (config.SCREEN_W, config.SCREEN_H))
    monkeypatch.setattr(adb, "screencap", lambda serial=None: _frame())
    return inst


def test_one_pass_records_a_frame_and_leaves_no_flag(data: Path, tmp_path: Path) -> None:
    obs = observer.Observer(max_minutes=0.0)  # the cap is checked after the first frame
    obs.run()
    assert obs.frames == 1
    assert not (data / "record.flag").exists()
    sessions = sorted((tmp_path / "calibration" / "recordings" / "alpha").iterdir())
    assert len(sessions) == 1
    assert (sessions[0] / "labels.jsonl").read_text(encoding="utf-8").count("\n") == 1


def test_the_heartbeat_names_the_mode(data: Path) -> None:
    observer.Observer(max_minutes=0.0).run()
    from brawlfarm.core import status

    heartbeat = status.read_status(data)
    assert heartbeat is not None
    assert heartbeat["mode"] == "observe"
    assert heartbeat["phase"] == "observing"
    assert heartbeat["running"] is False


def test_stop_flag_ends_the_session(data: Path, monkeypatch) -> None:
    seen: list[int] = []

    def screencap(serial=None):
        seen.append(1)
        if len(seen) == 2:  # a leftover flag is cleared at startup, so raise it mid-loop
            (data / "stop.flag").write_text("stop\n", encoding="utf-8")
        return _frame()

    monkeypatch.setattr(adb, "screencap", screencap)
    observer.Observer().run()
    assert len(seen) == 2
    assert not (data / "record.flag").exists()


def test_a_display_that_is_not_1600x900_never_starts(data: Path, monkeypatch) -> None:
    monkeypatch.setattr(adb, "screen_size", lambda: (1280, 720))
    with pytest.raises(SystemExit, match="1280x720"):
        observer.Observer().run()
    assert not (data / "record.flag").exists()


def test_an_exception_still_clears_the_flag(data: Path, monkeypatch) -> None:
    def boom(serial=None):
        raise RuntimeError("device gone")

    monkeypatch.setattr(adb, "screencap", boom)
    with pytest.raises(RuntimeError):
        observer.Observer().run()
    assert not (data / "record.flag").exists()
