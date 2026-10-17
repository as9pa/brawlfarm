"""The auto-labeller: in-match test, merge, the task file, and a run over a tiny dataset."""

from __future__ import annotations

import numpy as np

from tools.play import autolabel, coco, dataset, prelabel, zones

H, W = dataset.FRAME_H, dataset.FRAME_W


def _hsv(sat):
    hsv = np.zeros((H, W, 3), dtype=np.uint8)
    hsv[..., 1] = sat
    hsv[..., 2] = 150
    return hsv


def test_task_for_takes_a_model_version():
    box = {"class": "bush", "x": 10, "y": 20, "w": 30, "h": 40, "score": 0.8}
    task = prelabel.task_for("frames/a/a-000001.jpg", [box], model_version="autolabel-v1")
    assert task["predictions"][0]["model_version"] == "autolabel-v1"
    default = prelabel.task_for("frames/a/a-000001.jpg", [box])
    assert default["predictions"][0]["model_version"] == prelabel.MODEL_VERSION


def test_in_match_rules():
    play = [{"class": "play_button", "x": 1, "y": 1, "w": 5, "h": 5, "score": 0.9}]
    assert not autolabel.in_match({"hud": True}, _hsv(200), play)
    assert autolabel.in_match({"hud": True}, _hsv(0), [])
    assert not autolabel.in_match({"hud": False}, _hsv(200), [])
    assert autolabel.in_match({}, _hsv(200), [])
    assert not autolabel.in_match({}, _hsv(0), [])


def test_merge_keeps_templates_drops_hud_boxes_and_clips():
    zone = zones.zone_mask()
    template = [{"class": "play_button", "x": 1350, "y": 700, "w": 200, "h": 120, "score": 0.9}]
    on_button = {"class": "self", "x": 1200, "y": 630, "w": 50, "h": 50, "score": 0.8}
    edge = {"class": "enemy", "x": 1560, "y": 300, "w": 80, "h": 90, "score": 0.7}
    out = autolabel.merge(template, [on_button, edge], zone)
    assert out == [
        template[0],
        {"class": "enemy", "x": 1560, "y": 300, "w": 40, "h": 90, "score": 0.7},
    ]


def test_merged_task_round_trips_through_coco():
    bush = {"class": "bush", "x": 600, "y": 400, "w": 200, "h": 120, "score": 0.95}
    boxes = autolabel.merge([], [bush], zones.zone_mask())
    task = prelabel.task_for("frames/a/a-000001.jpg", boxes, model_version=autolabel.MODEL_VERSION)
    labels = coco.from_labelstudio([task], use_predictions=True)
    assert labels == {
        "frames/a/a-000001.jpg": [{"class": "bush", "x": 600, "y": 400, "w": 200, "h": 120}]
    }
