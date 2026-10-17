"""HUD zones and per-source exclusions: where the auto-labeller must not put a box."""

from __future__ import annotations

import json

import pytest

from tools.play import dataset, zones


def test_unpadded_mask_covers_the_hud_and_not_the_arena():
    mask = zones.zone_mask()
    assert mask.shape == (dataset.FRAME_H, dataset.FRAME_W)
    assert mask.dtype == bool
    assert mask[10, 10]
    assert mask[890, 1590]
    assert mask[655, 1228]
    assert mask[860, 100]
    assert not mask[450, 800]


def test_pad_moves_the_hud_into_the_picture():
    mask = zones.zone_mask((200, 0, 200, 0))
    assert not mask[10, 100]
    assert mask[10, 210]
    assert not mask[450, 800]


def test_extra_rectangles_are_frame_pixels_and_clipped():
    mask = zones.zone_mask(extra=[(0, 370, 290, 900), (1500, 0, 1700, 50)])
    assert mask[500, 100]
    assert not mask[500, 300]
    assert mask[20, 1599]


def test_in_zone_clamps_coordinates():
    mask = zones.zone_mask()
    assert zones.in_zone(mask, -5, -5)
    assert not zones.in_zone(mask, 800.7, 450.2)


def test_drop_in_zones_uses_the_area_share():
    mask = zones.zone_mask()
    on_button = {"class": "self", "x": 1200, "y": 630, "w": 50, "h": 50, "score": 0.9}
    edge = {"class": "enemy", "x": 1274, "y": 760, "w": 100, "h": 60, "score": 0.9}  # 30% in
    arena = {"class": "bush", "x": 700, "y": 400, "w": 80, "h": 80, "score": 0.9}
    assert zones.inside_fraction(mask, edge) == pytest.approx(0.3)
    assert zones.drop_in_zones([on_button, edge, arena], mask) == [edge, arena]


def test_load_exclusions(tmp_path):
    assert zones.load_exclusions(tmp_path / "missing.json") == {}
    path = tmp_path / "exclusions.json"
    path.write_text(json.dumps({"yt-AAAAAAAAAAA": [[0, 370, 290, 900]]}), encoding="utf-8")
    assert zones.load_exclusions(path) == {"yt-AAAAAAAAAAA": [(0, 370, 290, 900)]}


@pytest.mark.parametrize(
    "blob",
    [
        [1, 2],
        {"../evil": [[0, 0, 10, 10]]},
        {"yt-AAAAAAAAAAA": [[10, 0, 5, 10]]},
        {"yt-AAAAAAAAAAA": [[0, 0, 1601, 10]]},
        {"yt-AAAAAAAAAAA": [[0, 0, 10]]},
        {"yt-AAAAAAAAAAA": [0, 0, 10, 10]},
        {"yt-AAAAAAAAAAA": "0,0,10,10"},
    ],
)
def test_load_exclusions_refuses_bad_entries(tmp_path, blob):
    path = tmp_path / "exclusions.json"
    path.write_text(json.dumps(blob), encoding="utf-8")
    with pytest.raises(ValueError):
        zones.load_exclusions(path)
