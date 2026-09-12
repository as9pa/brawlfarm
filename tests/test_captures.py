"""Event captures: one frame per tag per 10 minutes, newest EVENT_CAP frames kept.

The recovery loop used to write a full 1600x900 PNG on every notable event -- about
80 MB an hour when it got stuck. These cover both halves of the fix (the throttle and
the prune) plus the two failure paths that must never reach the farm's hot loop.
"""

from __future__ import annotations

import os
import time

import cv2
import numpy as np
import pytest

from brawlfarm.core import captures, config


@pytest.fixture(autouse=True)
def _reset_captures():
    captures.reset()
    yield
    captures.reset()


def _screen():
    return np.zeros((900, 1600, 3), dtype=np.uint8)


def _events_dir():
    return config.CAPTURES_DIR / "events"


def _shots():
    d = _events_dir()
    return sorted(d.glob("*.png")) if d.is_dir() else []


def test_first_write_lands_a_full_frame():
    assert captures.write_event(_screen(), "recover_stuck", now=100.0) is True
    shots = _shots()
    assert len(shots) == 1
    assert shots[0].name.endswith("_recover_stuck.png")
    assert cv2.imread(str(shots[0])).shape == (900, 1600, 3)


def test_same_tag_inside_the_interval_writes_nothing():
    assert captures.write_event(_screen(), "disconnect", now=100.0) is True
    assert captures.write_event(_screen(), "disconnect", now=100.0 + 599.0) is False
    assert len(_shots()) == 1


def test_a_different_tag_inside_the_interval_still_writes():
    assert captures.write_event(_screen(), "disconnect", now=100.0) is True
    assert captures.write_event(_screen(), "unknown", now=101.0) is True
    assert len(_shots()) == 2


def test_same_tag_writes_again_after_the_interval():
    assert captures.write_event(_screen(), "unknown", now=100.0) is True
    # Both land in the same wall-clock second, so they share a <HHMMSS>_<tag> name and
    # the second overwrites the first -- the return value is what says it wrote.
    assert (
        captures.write_event(_screen(), "unknown", now=100.0 + captures.EVENT_MIN_INTERVAL_S)
        is True
    )


def test_a_write_prunes_the_folder_back_to_the_cap():
    d = _events_dir()
    d.mkdir(parents=True, exist_ok=True)
    base = time.time() - 10_000  # older than the frame we are about to write
    seeded = []
    for i in range(105):
        p = d / f"000000_seed{i:03d}.png"
        p.write_bytes(b"not really a png")
        os.utime(p, (base + i, base + i))
        seeded.append(p)

    assert captures.write_event(_screen(), "recover_freeze", now=100.0) is True

    survivors = _shots()
    assert len(survivors) == captures.EVENT_CAP
    # The six oldest seeds went; the new frame and the 99 newest seeds stayed.
    assert set(survivors) == {*seeded[6:], *(p for p in survivors if p not in seeded)}
    assert not any(p.exists() for p in seeded[:6])


def test_imwrite_failing_returns_false_and_does_not_raise(monkeypatch):
    monkeypatch.setattr(captures.cv2, "imwrite", lambda path, img: False)
    assert captures.write_event(_screen(), "unknown", now=100.0) is False
    assert _shots() == []
    # The tag was not stamped, so a later event of the same kind may still try.
    monkeypatch.undo()
    assert captures.write_event(_screen(), "unknown", now=101.0) is True


def test_captures_dir_pointing_at_a_file_returns_false(monkeypatch):
    blocked = config.CAPTURES_DIR.parent / "blocked"
    blocked.write_bytes(b"a file where the captures folder should be")
    monkeypatch.setattr(config, "CAPTURES_DIR", blocked)
    assert captures.write_event(_screen(), "unknown", now=100.0) is False


def test_the_screen_is_never_modified():
    screen = _screen()
    screen[10, 10] = (1, 2, 3)
    before = screen.copy()
    assert captures.write_event(screen, "unknown", now=100.0) is True
    assert np.array_equal(screen, before)
