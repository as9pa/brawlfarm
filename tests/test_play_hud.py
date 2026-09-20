"""The HUD reader: circles first, colour second, and the mobile HUD verdict.

Synthetic images only, drawn by tests/hud_draw.py. The constants in tools/play/hud.py are
calibration values measured on real footage, so a picture that does not trip them is the
picture's fault and gets redrawn, never the constant.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from tests import hud_draw
from tests.hud_draw import draw_hud
from tools.play import hud

BOX = (140, 80, 1316, 736)


def _at(box: tuple[int, int, int, int], at: tuple[float, float]) -> tuple[float, float]:
    x, y, w, h = box
    return x + at[0] * w, y + at[1] * h


def test_frame_box_removes_the_pad():
    assert hud.frame_box((0, 80, 0, 80)) == (0, 80, 1600, 740)
    assert hud.frame_box((0, 0, 0, 0)) == (0, 0, 1600, 900)


def test_inner_hsv_means_red_across_the_wrap():
    frame = np.zeros((200, 200, 3), np.uint8)
    cv2.circle(frame, (100, 100), 40, hud_draw.bgr(2, 200, 200), -1)
    other = np.zeros_like(frame)
    cv2.circle(other, (100, 100), 40, hud_draw.bgr(178, 200, 200), -1)
    frame[:, 100:] = other[:, 100:]
    h, s, v = hud.inner_hsv(frame, 100, 100, 40)
    assert min(abs(h - 0.0), abs(h - 179.0)) <= 3.0
    assert not 80.0 <= h <= 100.0
    assert s == pytest.approx(200, abs=2)
    assert v == pytest.approx(200, abs=2)


@pytest.mark.parametrize(
    ("cls", "hsv", "state"),
    [
        ("attack", (2.0, 200.0, 210.0), "red"),
        ("attack", (170.0, 60.0, 130.0), "dim"),
        ("super", (108.0, 200.0, 200.0), "blue"),
        ("super", (18.0, 180.0, 245.0), "gold"),
        ("super", (0.0, 10.0, 250.0), "white"),
        ("super", (0.0, 10.0, 90.0), "dark"),
        ("gadget", (60.0, 200.0, 160.0), "green"),
        ("gadget", (0.0, 20.0, 130.0), "grey"),
        ("hyper", (135.0, 180.0, 160.0), "purple"),
        ("knob", (108.0, 220.0, 200.0), "blue"),
        ("super", (108.0, 100.0, 200.0), None),
        ("knob", (108.0, 160.0, 200.0), None),
        ("attack", (60.0, 200.0, 200.0), None),
    ],
)
def test_state_of(cls, hsv, state):
    assert hud.state_of(cls, *hsv) == state


def test_find_reads_a_full_hud():
    found = hud.find(draw_hud(), BOX)
    assert set(found) == {"attack", "super", "gadget", "knob"}
    for cls, at, state in (
        ("attack", (0.92, 0.62), "red"),
        ("super", hud_draw.SUPER_AT, "blue"),
        ("gadget", hud_draw.GADGET_AT, "green"),
        ("knob", (0.12, 0.80), "blue"),
    ):
        px, py = _at(BOX, at)
        assert found[cls].cls == cls
        assert found[cls].state == state
        assert abs(found[cls].x - px) <= 4.0
        assert abs(found[cls].y - py) <= 4.0


def test_find_is_relative_to_the_box():
    box = (172, 96, 1252, 704)
    frame = draw_hud(box=box)
    assert "gadget" in hud.find(frame, box)
    assert "gadget" not in hud.find(frame, (0, 0, 1600, 900))


def test_floor_colour_does_not_matter():
    """A pink arena floor is what killed the colour-first method; circles first survives it."""
    found = hud.find(draw_hud(floor_tint=(170, 120)), BOX)
    assert "attack" in found
    assert found["attack"].state == "red"


def test_visible_needs_the_super():
    assert not hud.visible(hud.find(draw_hud(super_state=None), BOX))
    blank = draw_hud(attack=None, super_state=None, knob=None, base=None, gadget=False)
    assert not hud.visible(hud.find(blank, BOX))
    assert hud.visible(hud.find(draw_hud(knob=None, base=None), BOX))
    assert hud.visible(hud.find(draw_hud(attack=None), BOX))


def test_menu_like_frame_is_not_visible():
    found = hud.find(draw_hud(super_state=None, gadget=False, base=None), BOX)
    assert "attack" in found
    assert "knob" in found
    assert not hud.visible(found)


def test_base_free_and_fixed():
    frame = draw_hud()
    knob = hud.find(frame, BOX)["knob"]
    bx, by = _at(BOX, (0.10, 0.78))
    free = hud.base(frame, BOX, knob)
    assert free is not None
    assert abs(free.x - bx) <= 6.0
    assert abs(free.y - by) <= 6.0
    fixed = hud.base(frame, BOX, knob, radius=hud_draw.BASE_R * BOX[3])
    assert fixed is not None
    assert (fixed.cls, fixed.state) == ("base", "ring")
    assert abs(fixed.x - bx) <= 6.0
    assert abs(fixed.y - by) <= 6.0
    bare = draw_hud(base=None)
    assert hud.base(bare, BOX, hud.find(bare, BOX)["knob"]) is None


def test_base_rejects_a_circle_that_does_not_hold_the_knob():
    frame = draw_hud(base=None)
    knob = hud.find(frame, BOX)["knob"]
    ring = int(round(hud_draw.BASE_R * BOX[3]))
    far = (int(round(knob.x)) + 2 * ring, int(round(knob.y)))
    cv2.circle(frame, far, ring, (hud_draw.BASE_GRAY,) * 3, hud_draw.RIM, cv2.LINE_AA)
    assert hud.base(frame, BOX, knob) is None
    # A ring that far out never reaches the accumulator at all. A small one whose centre does
    # sit inside the search window is the case the guard itself has to turn away.
    small = int(round(hud.BASE_FREE[0] * knob.r)) + 4
    near = (int(round(knob.x)) + int(1.5 * small), int(round(knob.y)))
    cv2.circle(frame, near, small, (hud_draw.BASE_GRAY,) * 3, hud_draw.RIM, cv2.LINE_AA)
    assert hud.base(frame, BOX, knob) is None
