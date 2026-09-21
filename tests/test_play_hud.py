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
BASE_AT = (0.12, 0.677)  # where draw_hud puts the joystick centre, ring and dot, by default


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


def test_origin_reads_the_dot():
    frame = draw_hud()
    knob = hud.find(frame, BOX)["knob"]
    got = hud.origin(frame, BOX, knob)
    assert got is not None
    assert (got.cls, got.state) == ("origin", "dot")
    bx, by = _at(BOX, BASE_AT)
    assert abs(got.x - bx) <= 3.0
    assert abs(got.y - by) <= 3.0


@pytest.mark.parametrize("push", [(1, 0), (-1, 0), (0, 1), (0, -1)])
def test_origin_at_full_push(push):
    """The stick is clamped to its ring, so a full push puts the knob one ring radius out."""
    base = (0.16, 0.76)
    bx, by = _at(BOX, base)
    ring = hud.RING_RATIO * hud_draw.DISC_R["knob"] * BOX[3]
    at = ((bx + push[0] * ring - BOX[0]) / BOX[2], (by + push[1] * ring - BOX[1]) / BOX[3])
    frame = draw_hud(knob=at, base=base)
    knob = hud.find(frame, BOX)["knob"]
    got = hud.origin(frame, BOX, knob)
    assert got is not None
    assert abs(got.x - bx) <= 3.0
    assert abs(got.y - by) <= 3.0


def test_origin_hidden_under_the_knob():
    """A stick near its centre covers its own dot, and a covered dot is no move label at all."""
    at = (0.12, 0.78)
    frame = draw_hud(knob=at, base=at)
    knob = hud.find(frame, BOX)["knob"]
    assert hud.origin(frame, BOX, knob) is None


def test_origin_needs_a_dot():
    for at in ((0.12, 0.80), (0.22, 0.62), (0.08, 0.90)):
        frame = draw_hud(knob=at, base=None)
        knob = hud.find(frame, BOX)["knob"]
        assert hud.origin(frame, BOX, knob) is None


def test_origin_ignores_a_bright_disc():
    """The real dot is translucent and always darker than the floor it sits on."""
    frame = draw_hud(base=None)
    knob = hud.find(frame, BOX)["knob"]
    bx, by = _at(BOX, BASE_AT)
    radius = int(round(hud_draw.DOT_R * knob.r))
    cv2.circle(frame, (int(bx), int(by)), radius, (200,) * 3, -1, cv2.LINE_AA)
    assert hud.origin(frame, BOX, knob) is None


def test_origin_ignores_a_dot_out_of_reach():
    """The knob never gets further from its dot than the ring, so a blob past it is somebody
    else's: a shadow, a bush, another player's HUD in a spectator clip."""
    frame = draw_hud(base=None)
    knob = hud.find(frame, BOX)["knob"]
    far = int(round(knob.x + 1.6 * hud.RING_RATIO * knob.r)), int(round(knob.y))
    hud_draw.origin_dot(frame, far, int(round(hud_draw.DOT_R * knob.r)))
    assert hud.origin(frame, BOX, knob) is None


def test_origin_window_clips():
    """A knob at the edge of a pillarboxed frame keeps the black bar, and its decoys, out.

    The window stops at the content box and at the frame, so a dot drawn in the bar is never a
    candidate and a knob in the corner is a small window, not an exception.
    """
    box = (172, 96, 1252, 704)
    frame = draw_hud(box=box, knob=None, base=None)
    knob = hud.Found("knob", float(box[0] + 30), box[1] + 0.8 * box[3], 0.065 * box[3], "blue")
    decoy = (box[0] - 60, int(round(knob.y)))
    hud_draw.origin_dot(frame, decoy, int(round(hud_draw.DOT_R * knob.r)))
    assert hud.origin(frame, box, knob) is None

    full = (0, 0, 1600, 900)
    corner = hud.Found("knob", 24.0, 876.0, 46.0, "blue")
    got = hud.origin(draw_hud(box=full, knob=None, base=None), full, corner)
    assert got is None or got.cls == "origin"


def test_origin_does_not_depend_on_the_floor_colour():
    frame = draw_hud(floor_tint=(170, 120))
    knob = hud.find(frame, BOX)["knob"]
    got = hud.origin(frame, BOX, knob)
    assert got is not None
    bx, by = _at(BOX, BASE_AT)
    assert abs(got.x - bx) <= 3.0
    assert abs(got.y - by) <= 3.0
