"""Brawler auto-labels: OCR anchors, bar measure, class vote and the SAM box geometry.

Everything runs on synthetic arrays and fake OCR results. Names in them are placeholders; a
real player name never goes into a test.
"""

from __future__ import annotations

import json

import cv2
import numpy as np
import pytest

from tools.play import brawlers

H, W = 900, 1600
NO_ZONES = np.zeros((H, W), dtype=bool)


def _text(x0, y0, x1, y1, text, score=0.95):
    return [[[x0, y0], [x1, y0], [x1, y1], [x0, y1]], text, score]


def _bar_frame(colour_hsv, *, cx=800, top=300, width=100, height=10):
    hsv = np.zeros((H, W, 3), dtype=np.uint8)
    hsv[...] = (0, 0, 128)
    x0 = cx - width // 2
    hsv[top - 2 : top + height + 2, x0 - 2 : x0 + width + 2] = (0, 0, 30)
    hsv[top : top + height, x0 : x0 + width] = colour_hsv
    return hsv


def _any_fill(hsv):
    fills = brawlers.fill_masks(hsv)
    return fills["green"] | fills["red"] | fills["blue"] | (hsv[..., 2] <= 70)


def test_hp_number_under_a_name_is_a_named_anchor():
    result = [_text(770, 256, 830, 274, "Alpha"), _text(780, 280, 820, 298, "3600")]
    anchors, solo = brawlers.anchors_from_ocr(result, NO_ZONES)
    assert solo is False
    assert len(anchors) == 1
    a = anchors[0]
    assert a.named and a.name_y0 == 256
    assert (a.cx, a.y1) == (800, 298)


def test_tall_unnamed_number_is_a_damage_number():
    assert brawlers.anchors_from_ocr([_text(780, 280, 840, 316, "1200")], NO_ZONES)[0] == []


def test_anchor_in_a_zone_is_dropped():
    zones = np.zeros((H, W), dtype=bool)
    zones[0:225, 0:470] = True
    assert brawlers.anchors_from_ocr([_text(100, 100, 140, 118, "4200")], zones)[0] == []


def test_brawlers_left_means_solo():
    assert brawlers.anchors_from_ocr([_text(20, 20, 200, 44, "Brawlers left: 7")], NO_ZONES)[1]


def test_name_without_a_number_still_anchors_the_bar():
    anchors, _ = brawlers.anchors_from_ocr([_text(770, 256, 830, 274, "Alpha")], NO_ZONES)
    assert len(anchors) == 1 and anchors[0].from_name and anchors[0].named
    assert anchors[0].y0 == 274


def test_measure_bar_finds_width_and_bottom():
    hsv = _bar_frame((0, 200, 220))
    anchor = brawlers.Anchor(x0=780, y0=280, x1=820, y1=298, named=True, name_y0=256)
    bw, bot, found = brawlers.measure_bar(_any_fill(hsv), anchor)
    assert found
    assert 95 <= bw <= 110
    assert 300 <= bot <= 312


def test_measure_bar_without_a_bar_falls_back():
    hsv = np.zeros((H, W, 3), dtype=np.uint8)
    hsv[..., 2] = 128
    anchor = brawlers.Anchor(x0=780, y0=280, x1=820, y1=298)
    assert brawlers.measure_bar(_any_fill(hsv), anchor) == (brawlers.DEFAULT_BW, 301, False)


RED_BAR = {"green": 0, "red": 60, "blue": 0}
BLUE_BAR = {"green": 0, "red": 0, "blue": 60}
GREEN_BAR = {"green": 60, "red": 0, "blue": 0}
GREEN_RING = {"green": 120, "red": 0, "blue": 0}
RED_RING = {"green": 0, "red": 120, "blue": 0}


def _ev(**over):
    base = dict(
        bar={"green": 0, "red": 0, "blue": 0},
        ring={"green": 0, "red": 0, "blue": 0},
        named=True,
        found=True,
        ammo=0.0,
        centred=False,
        crate=0.0,
        name_ink=0.0,
        solo=False,
    )
    base.update(over)
    return brawlers.Evidence(**base)


def test_top_colour_skips_and_needs():
    votes = {"green": 50, "red": 30, "blue": 0}
    assert brawlers.top_colour(votes, 12) == "green"
    assert brawlers.top_colour(votes, 12, skip=("green",)) == "red"
    assert brawlers.top_colour({"green": 5, "red": 3, "blue": 0}, 12) is None


@pytest.mark.parametrize(
    ("ev", "want"),
    [
        (_ev(bar=RED_BAR, ring=RED_RING), "enemy"),
        (_ev(bar=BLUE_BAR), "teammate"),
        (_ev(bar=BLUE_BAR, solo=True), "enemy"),
        (_ev(bar=BLUE_BAR, ring=GREEN_RING), "teammate"),
        (_ev(bar=GREEN_BAR, centred=True), "self"),
        (_ev(bar=RED_BAR, ammo=0.8), "self"),
        (_ev(bar=RED_BAR, ring=GREEN_RING), "self"),
        (_ev(bar=RED_BAR, ring=GREEN_RING, named=False), "self"),
        (_ev(bar=RED_BAR, named=False, crate=0.3), "box"),
        (_ev(named=False, crate=0.15), "box"),
        (_ev(bar=BLUE_BAR, named=False), None),
        (_ev(bar=RED_BAR, named=False, name_ink=0.2), "enemy"),
        (_ev(bar=RED_BAR, named=False), None),
        (_ev(), "enemy"),
    ],
)
def test_vote_class(ev, want):
    assert brawlers.vote_class(ev) == want


def _bar(cls, cx, bot, *, named=True, colour="green", ammo=0.0):
    return brawlers.Bar(
        cls=cls, cx=cx, bw=90.0, bot=bot, named=named, colour=colour, why="bar", ammo=ammo
    )


def test_one_self_survives_and_a_red_named_loser_turns_enemy():
    real = _bar("self", 800, 380, ammo=0.7)
    on_grass = _bar("self", 300, 600, colour="red")
    pet = _bar("self", 900, 420, named=False, colour="blue")
    mate = _bar("teammate", 1100, 300, colour="blue")
    out = brawlers.resolve_selfs([real, on_grass, pet, mate], W, H)
    assert [(b.cls, b.cx) for b in out] == [("self", 800), ("enemy", 300), ("teammate", 1100)]


def test_dedupe_keeps_the_named_anchor_on_one_bar():
    named = _bar("enemy", 800, 300)
    echo = _bar("enemy", 810, 305, named=False)
    other = _bar("enemy", 1200, 300)
    assert brawlers.dedupe([echo, named, other]) == [named, other]


def test_bar_round_trips_through_json():
    bar = _bar("box", 640.5, 512, named=False, colour=None)
    assert brawlers.Bar.from_json(json.loads(json.dumps(bar.to_json()))) == bar


def _frame_with_bar(fill_hsv, *, cx=800, top=380, ammo=False):
    hsv = _bar_frame(fill_hsv, cx=cx, top=top)
    if ammo:
        hsv[top + 13 : top + 19, cx - 45 : cx + 45] = (14, 200, 230)
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR), hsv


def test_classify_low_health_self_with_ammo_is_self():
    bgr, hsv = _frame_with_bar((0, 200, 220), ammo=True)
    anchor = brawlers.Anchor(x0=780, y0=360, x1=820, y1=378, named=True, name_y0=336)
    bars = brawlers.classify(bgr, hsv, [anchor], solo=False)
    assert [b.cls for b in bars] == ["self"]
    assert bars[0].ammo > brawlers.AMMO_MIN


def test_classify_red_named_bar_is_enemy():
    bgr, hsv = _frame_with_bar((0, 200, 220), cx=400, top=500)
    anchor = brawlers.Anchor(x0=380, y0=480, x1=420, y1=498, named=True, name_y0=456)
    bars = brawlers.classify(bgr, hsv, [anchor], solo=False)
    assert [(b.cls, b.colour, b.why) for b in bars] == [("enemy", "red", "bar")]


def test_ammo_share_counts_columns_under_the_bar():
    hsv = _bar_frame((0, 200, 220))
    hsv[310:316, 755:845] = (14, 200, 230)
    assert brawlers.ammo_share(hsv, 800.0, 306, 100.0) == pytest.approx(0.9)


def _bar_at(cls="enemy", cx=800.0, bw=100.0, bot=300):
    return brawlers.Bar(
        cls=cls, cx=cx, bw=bw, bot=bot, named=True, colour="red", why="bar", ammo=0.0
    )


def test_fixed_box_sits_under_the_bar():
    assert brawlers.fixed_box(_bar_at(), W, H) == (752, 315, 95, 100)


def test_sane_accepts_a_body_and_refuses_a_far_box():
    bar = _bar_at()
    assert brawlers.sane((755, 310, 90, 100), bar, H)
    assert not brawlers.sane((900, 310, 90, 100), bar, H)
    assert not brawlers.sane((755, 310, 30, 100), bar, H)


def test_sam_prompt_points_and_box_follow_the_bar():
    points, labels, box = brawlers.sam_prompt(_bar_at(), W, H)
    assert labels == [1, 1, 0, 0, 0]
    assert len(points) == 5 and points[0] == [800.0, 345.0]
    assert box == [730.0, 302, 870.0, 435.0]


def test_pick_box_prefers_the_body_mask():
    body = np.zeros((H, W), dtype=bool)
    body[310:405, 755:845] = True
    head = np.zeros((H, W), dtype=bool)
    head[305:330, 780:820] = True
    ring = np.zeros((H, W), dtype=bool)
    box, raw, _adjusted = brawlers.pick_box(
        np.stack([head, body]), np.array([0.95, 0.9]), _bar_at(), ring
    )
    assert box == (755, 310, 90, 95)
    assert raw == pytest.approx(0.9)


def test_choose_box_falls_back_when_sam_misses():
    hsv = np.zeros((H, W, 3), dtype=np.uint8)
    out = brawlers.choose_box(
        np.zeros((3, H, W), dtype=bool), np.array([0.5, 0.5, 0.5]), _bar_at(), hsv
    )
    assert out == {
        "class": "enemy",
        "x": 752,
        "y": 315,
        "w": 95,
        "h": 100,
        "score": 0.3,
        "fallback": True,
    }


def test_suppress_drops_the_lower_overlapping_box():
    a = {"class": "enemy", "x": 100, "y": 100, "w": 80, "h": 80, "score": 0.9}
    b = {"class": "enemy", "x": 110, "y": 110, "w": 80, "h": 80, "score": 0.5}
    c = {"class": "self", "x": 400, "y": 100, "w": 80, "h": 80, "score": 0.4}
    assert brawlers.suppress([b, c, a]) == [a, c]


def test_fallback_box_is_the_fixed_box_with_the_fallback_score():
    out = brawlers.fallback_box(_bar_at(cls="box", cx=20.0), W, H)
    assert out == {
        "class": "box",
        "x": 0,
        "y": 315,
        "w": 67,
        "h": 100,
        "score": 0.3,
        "fallback": True,
    }


def test_choose_box_takes_the_crate_lid_from_the_mask_union():
    face = np.zeros((H, W), dtype=bool)
    face[330:405, 755:845] = True
    lid = np.zeros((H, W), dtype=bool)
    lid[305:330, 760:840] = True
    masks, scores = np.stack([face, lid]), np.array([0.9, 0.8])
    hsv = np.zeros((H, W, 3), dtype=np.uint8)
    crate = brawlers.choose_box(masks, scores, _bar_at(cls="box"), hsv)
    assert crate == {
        "class": "box",
        "x": 755,
        "y": 305,
        "w": 90,
        "h": 100,
        "score": 0.9,
        "fallback": False,
    }
    enemy = brawlers.choose_box(masks, scores, _bar_at(), hsv)
    assert (enemy["y"], enemy["h"], enemy["fallback"]) == (330, 75, False)
