"""Terrain auto-labels: bushes and power cubes from colour masks on synthetic HSV frames."""

from __future__ import annotations

import cv2
import numpy as np

from tools.play import dataset, terrain, zones

H, W = dataset.FRAME_H, dataset.FRAME_W
NO_ZONES = np.zeros((H, W), dtype=bool)
LEAF = (95, 220, 180)


def _floor() -> np.ndarray:
    """A saturated sandy arena floor: a game frame with nothing on it."""
    hsv = np.zeros((H, W, 3), dtype=np.uint8)
    hsv[...] = (15, 120, 150)
    return hsv


def _cube(hsv, x, y, side):
    hsv[y : y + side, x : x + side] = (60, 150, 180)
    gx, gy = x + side // 2 - 5, y + side // 2 - 8
    hsv[gy : gy + 16, gx : gx + 10] = (27, 180, 220)


def test_game_frame_is_the_saturated_floor():
    assert terrain.is_game_frame(_floor())
    grey = np.zeros((H, W, 3), dtype=np.uint8)
    grey[..., 2] = 128
    assert not terrain.is_game_frame(grey)


def test_a_leafy_patch_is_one_edge_tight_bush():
    hsv = _floor()
    hsv[400:520, 600:800] = LEAF
    boxes = terrain.bush_boxes(hsv, NO_ZONES)
    assert len(boxes) == 1
    box = boxes[0]
    assert box["class"] == "bush"
    assert abs(box["x"] - 600) <= 1 and abs(box["y"] - 400) <= 1
    assert abs(box["w"] - 200) <= 2 and abs(box["h"] - 120) <= 2
    assert 0.5 <= box["score"] <= 1.0


def test_small_and_round_patches_are_not_bushes():
    hsv = _floor()
    hsv[100:120, 700:720] = LEAF
    disc = np.zeros((H, W), dtype=np.uint8)
    cv2.circle(disc, (1000, 450), 50, 255, -1)
    hsv[disc > 0] = LEAF
    assert terrain.bush_boxes(hsv, NO_ZONES) == []


def test_bush_pixels_in_a_zone_are_ignored():
    hsv = _floor()
    hsv[20:140, 20:220] = LEAF
    assert terrain.bush_boxes(hsv, zones.zone_mask()) == []


def test_green_body_with_a_yellow_glyph_is_a_power_cube():
    hsv = _floor()
    _cube(hsv, 700, 400, 40)
    boxes = terrain.power_cube_boxes(hsv, NO_ZONES)
    assert [(b["class"], b["x"], b["y"], b["w"], b["h"]) for b in boxes] == [
        ("power_cube", 700, 400, 40, 40)
    ]


def test_power_level_icon_with_a_white_digit_is_rejected():
    hsv = _floor()
    _cube(hsv, 700, 400, 30)
    hsv[405:425, 731:745] = (0, 0, 255)
    assert terrain.power_cube_boxes(hsv, NO_ZONES) == []


def test_terrain_boxes_is_bushes_then_cubes():
    hsv = _floor()
    hsv[400:520, 200:400] = LEAF
    _cube(hsv, 900, 400, 40)
    assert [b["class"] for b in terrain.terrain_boxes(hsv, NO_ZONES)] == ["bush", "power_cube"]
