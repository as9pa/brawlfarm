"""Brawler auto-labels: OCR anchors, bar measure, class vote and the SAM box geometry.

Everything runs on synthetic arrays and fake OCR results. Names in them are placeholders; a
real player name never goes into a test.
"""

from __future__ import annotations

import numpy as np

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
