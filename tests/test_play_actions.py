"""The action labels: what a source teaches about itself, and what one frame is worth.

Synthetic HUDs only, drawn by tests/hud_draw.py and written into a tmp_path dataset through
frames.add_source, so every test walks the real path: index rows, JPEG on disk, the content box
measured rather than assumed. The constants in tools/play/actions.py are calibration values, so
a picture that does not trip them is the picture's fault and gets redrawn, never the constant.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import cv2
import numpy as np
import pytest

from tests import hud_draw
from tests.hud_draw import draw_hud
from tools.play import actions, dataset, frames, hud

BOX = (140, 80, 1316, 736)
HOME = (0.93, 0.62)  # where the attack disc rests, as (u, v) of the content box
DRAGGED = [(0.88, 0.55), (0.86, 0.70), (0.90, 0.52)]  # and where an aiming finger takes it
KNOB_RADIUS = hud_draw.DISC_R["knob"] * BOX[3]  # what hud_draw draws the joystick at
RING_RADIUS = hud.RING_RATIO * KNOB_RADIUS  # and the ring the stick is clamped to


def _at(at: tuple[float, float]) -> tuple[float, float]:
    x, y, w, h = BOX
    return x + at[0] * w, y + at[1] * h


def _scene(frame: np.ndarray, n: int) -> np.ndarray:
    """A changing arena above the HUD, so the deduper keeps every frame of a source.

    Twelve near identical HUDs hash alike and all but a few are dropped as duplicates before
    any of this is tested. The blocks sit in the band no search box and no base window reaches,
    between the top of the content box and the top of the attack box.
    """
    rng = np.random.default_rng(n)
    for col in range(9):
        for row in range(3):
            x0, y0 = 145 + col * 146, 85 + row * 72
            gray = int(rng.integers(20, 221))
            cv2.rectangle(frame, (x0, y0), (x0 + 145, y0 + 71), (gray,) * 3, -1)
    return frame


def _clip_frames(
    n: int = 12, *, knob: bool = True, base: bool = True, scene: int = 0
) -> list[np.ndarray]:
    """A source of n frames: the attack disc home in three of four, the joystick wandering.

    The stick is pushed a whole ring radius up and left of its origin in every frame, which is
    where a clamped stick spends its time and what leaves the dot clear of the knob.
    """
    out = []
    for i in range(n):
        u, v = 0.13 + 0.011 * i, 0.70 + 0.012 * i
        out.append(
            _scene(
                draw_hud(
                    attack=HOME if i % 4 else DRAGGED[i // 4],
                    knob=(u, v) if knob else None,
                    base=(u - 0.05, v - 0.086) if knob and base else None,
                    seed=i,
                ),
                scene + i,
            )
        )
    return out


def _no_score(frame: np.ndarray, name: str) -> float:
    """add_source scores every frame against a template; these tests have no template."""
    return 0.0


def _read_frame(path: Path) -> np.ndarray:
    return cv2.imdecode(np.frombuffer(path.read_bytes(), np.uint8), cv2.IMREAD_COLOR)


def _build(root: Path, source: str, images: list[np.ndarray]) -> list[np.ndarray]:
    """Write a source into the dataset and hand back the frames that survived the deduper."""
    incoming = [(float(i) / 2, frame) for i, frame in enumerate(images)]
    counts = frames.add_source(root, source, "youtube", incoming, score=_no_score)
    assert counts["kept"] == len(images), counts
    return [
        _read_frame(root / row["file"])
        for row in dataset.index_rows(root)
        if row["source"] == source
    ]


def _clip(**changes) -> actions.Clip:
    """A learned clip, as learn would return it for a source with both channels readable."""
    fields = {
        "box": BOX,
        "hud_frames": 12,
        "home": _at(HOME),
        "ring_radius": RING_RADIUS,
        "channels": {"move": "ok", "aim": "ok"},
    }
    return actions.Clip(**{**fields, **changes})


def test_spread():
    assert actions.spread(list(range(10)), 4) == [0, 3, 6, 9]
    assert actions.spread([1, 2, 3], 24) == [1, 2, 3]


def test_learn_finds_the_home_and_the_radius(tmp_path):
    kept = _build(tmp_path, "yt-learn", _clip_frames())
    box = dataset.content_box(kept)
    clip = actions.learn(kept, box, min_frames=5)

    assert clip.channels == {"move": "ok", "aim": "ok"}
    assert clip.hud_frames == 12
    assert clip.home is not None
    assert math.dist(clip.home, _at(HOME)) <= 4.0
    assert clip.ring_radius == pytest.approx(RING_RADIUS, rel=0.05)


def test_covered_joystick_rejects_move_only(tmp_path):
    kept = _build(tmp_path, "yt-covered", _clip_frames(knob=False))
    clip = actions.learn(kept, dataset.content_box(kept), min_frames=5)

    assert clip.channels == {"move": "joystick knob in 0.00 of HUD frames", "aim": "ok"}
    assert clip.ring_radius is None
    assert clip.home is not None


def test_a_joystick_with_no_origin_rejects_move_only(tmp_path):
    kept = _build(tmp_path, "yt-nodot", _clip_frames(base=False))
    clip = actions.learn(kept, dataset.content_box(kept), min_frames=5)

    assert clip.channels == {"move": "joystick origin in 0.00 of knob frames", "aim": "ok"}
    assert clip.ring_radius is None
    assert clip.home is not None


def test_too_few_hud_frames_rejects_everything(tmp_path):
    kept = _build(tmp_path, "yt-short", _clip_frames(3))
    clip = actions.learn(kept, dataset.content_box(kept), min_frames=5)

    assert clip.hud_frames == 3
    assert clip.channels == {
        "move": "too few HUD frames (3)",
        "aim": "too few HUD frames (3)",
    }
    assert clip.home is None
    assert clip.ring_radius is None


def test_read_move_vector():
    base = (0.16, 0.70)
    bx, by = _at(base)
    knob = (
        (bx - 0.70 * RING_RADIUS - BOX[0]) / BOX[2],
        (by + 0.65 * RING_RADIUS - BOX[1]) / BOX[3],
    )
    row = actions.read(draw_hud(knob=knob, base=base), _clip())
    assert row["move"][0] == pytest.approx(-0.70, abs=0.08)
    assert row["move"][1] == pytest.approx(0.65, abs=0.08)


def test_read_move_is_none_when_the_knob_hides_the_dot():
    """A stick at rest covers its own origin, and there is nothing to measure a push from."""
    at = (0.12, 0.78)
    row = actions.read(draw_hud(knob=at, base=at), _clip())

    assert row["hud"] is True
    assert row["move"] is None
    assert row["aim"] is not None


def test_read_aim():
    # Dragged up and left by a whole AIM_RADIUS on both axes, and still inside the attack search
    # box at both ends of the drag, which is what puts the home this far down and right.
    home = (0.93, 0.68)
    hx, hy = _at(home)
    drag = actions.AIM_RADIUS * BOX[3]
    dragged = ((hx - drag - BOX[0]) / BOX[2], (hy - drag - BOX[1]) / BOX[3])
    clip = _clip(home=(hx, hy))

    rest = actions.read(draw_hud(attack=home), clip)
    assert math.hypot(*rest["aim"]) < 0.05
    assert rest["aiming"] is False

    aiming = actions.read(draw_hud(attack=dragged, seed=3), clip)
    assert aiming["aim"][0] == pytest.approx(-1.0, abs=0.05)
    assert aiming["aim"][1] == pytest.approx(-1.0, abs=0.05)
    assert aiming["aiming"] is True


def test_read_without_hud_is_all_none():
    frame = draw_hud(attack=None, super_state=None, knob=None, base=None, gadget=False)
    assert actions.read(frame, _clip()) == {
        "hud": False,
        "move": None,
        "aim": None,
        "aiming": None,
        "super": None,
        "gadget": None,
        "hyper": None,
    }


def test_read_respects_a_rejected_channel():
    clip = _clip(
        ring_radius=None,
        channels={"move": "joystick knob in 0.00 of HUD frames", "aim": "ok"},
    )
    row = actions.read(draw_hud(), clip)

    assert row["hud"] is True
    assert row["move"] is None
    assert row["aim"] is not None
    assert row["super"] == "blue"
    assert row["gadget"] == "green"


def test_run_writes_one_row_per_frame(tmp_path):
    _build(tmp_path, "yt-run", _clip_frames(6))
    counts = actions.run(tmp_path, "yt-run", min_frames=5)
    folder = tmp_path / "frames" / "yt-run"

    files = [row["file"] for row in dataset.index_rows(tmp_path) if row["source"] == "yt-run"]
    rows = [
        json.loads(line)
        for line in (folder / "actions.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [row["file"] for row in rows] == files
    assert counts["frames"] == len(files)
    assert counts["hud"] == len(files)
    assert counts["move"] == len(files)
    assert all(row["t"] is not None for row in rows)

    meta = json.loads((folder / "actions.meta.json").read_text(encoding="utf-8"))
    assert meta["box"] == list(BOX)
    assert set(meta["channels"]) == {"move", "aim"}
    assert meta["counts"]["frames"] == len(files)
    assert list(folder.glob("*.tmp")) == []


def test_run_refuses_a_source_that_is_not_in_the_index(tmp_path):
    with pytest.raises(ValueError, match="yt-nothing is not in the index"):
        actions.run(tmp_path, "yt-nothing")


def test_main_reports_a_rejected_channel(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(actions, "MIN_HUD_FRAMES", 5)
    _build(tmp_path, "yt-covered", _clip_frames(6, knob=False))

    assert actions.main(["--root", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "yt-covered: 6 frames, HUD on 6, move on 0, aim on 6 (aiming 2)" in out
    assert "yt-covered: move rejected, joystick knob in 0.00 of HUD frames" in out
    assert "1 sources: 0 with every channel, 1 with a rejected channel" in out


def test_main_refuses_an_unknown_source(tmp_path, capsys):
    assert actions.main(["--root", str(tmp_path), "--source", "yt-nothing"]) == 2
    assert "yt-nothing is not in the index" in capsys.readouterr().out
    assert actions.main(["--root", str(tmp_path), "--source", "../x"]) == 2
