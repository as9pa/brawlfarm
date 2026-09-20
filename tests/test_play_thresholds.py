"""Per-class thresholds, the ONNX decode and the preprocessing, on hand-built numbers only.

Nothing here loads a model: the arrays are small enough to work the expected boxes out by hand,
which is the point. The two training scripts are only read as text, never imported, because
importing them would pull in torch.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import numpy as np
import pytest

from tools.play import thresholds

SCRIPTS = Path(__file__).resolve().parents[1] / "tools" / "play"


def _det(class_index: int, score: float, box: tuple[float, float, float, float]) -> dict:
    x, y, w, h = box
    return {"class_index": class_index, "score": score, "x": x, "y": y, "w": w, "h": h}


def test_iou_identical_boxes_is_one():
    assert thresholds.iou((10, 20, 30, 40), (10, 20, 30, 40)) == pytest.approx(1.0)


def test_iou_disjoint_boxes_is_zero():
    assert thresholds.iou((0, 0, 10, 10), (20, 20, 10, 10)) == 0.0
    assert thresholds.iou((0, 0, 10, 10), (10, 0, 10, 10)) == 0.0


def test_iou_half_overlap():
    # 50 pixels of overlap over a union of 150
    assert thresholds.iou((0, 0, 10, 10), (5, 0, 10, 10)) == pytest.approx(1 / 3)


def test_match_detections_does_not_match_one_truth_box_twice():
    truth = [{"class_index": 0, "x": 0, "y": 0, "w": 10, "h": 10}]
    dets = [
        _det(0, 0.9, (0, 0, 10, 10)),
        _det(0, 0.8, (1, 1, 10, 10)),
    ]
    assert thresholds.match_detections(dets, truth) == [True, False]


def test_match_detections_does_not_match_across_classes():
    truth = [{"class_index": 1, "x": 0, "y": 0, "w": 10, "h": 10}]
    dets = [_det(0, 0.9, (0, 0, 10, 10))]
    assert thresholds.match_detections(dets, truth) == [False]


def test_match_detections_takes_the_better_box_for_the_higher_score():
    truth = [
        {"class_index": 0, "x": 0, "y": 0, "w": 10, "h": 10},
        {"class_index": 0, "x": 100, "y": 0, "w": 10, "h": 10},
    ]
    dets = [
        _det(0, 0.9, (101, 0, 10, 10)),
        _det(0, 0.7, (0, 0, 10, 10)),
        _det(0, 0.5, (400, 400, 10, 10)),
    ]
    assert thresholds.match_detections(dets, truth) == [True, True, False]


def test_pick_returns_the_floor_when_every_detection_is_true():
    scores = [0.9, 0.6, 0.35]
    assert thresholds.pick(scores, [True, True, True]) == thresholds.FLOOR


def test_pick_clears_one_low_scored_false_positive():
    scores = [0.91, 0.82, 0.73, 0.40]
    is_tp = [True, True, True, False]
    assert thresholds.pick(scores, is_tp) == pytest.approx(0.41)


def test_pick_returns_the_ceiling_without_detections():
    assert thresholds.pick([], []) == thresholds.CEILING


def test_pick_returns_the_ceiling_when_precision_is_never_reached():
    assert thresholds.pick([0.9, 0.8], [False, False]) == thresholds.CEILING


def test_decode_reads_the_expected_box_and_ignores_the_last_column():
    dets = np.zeros((1, 2, 4), dtype=np.float32)
    dets[0, 0] = (0.5, 0.5, 0.2, 0.4)
    dets[0, 1] = (0.1, 0.1, 0.1, 0.1)
    logits = np.full((1, 2, 3), -6.0, dtype=np.float32)
    logits[0, 0, 0] = 2.0  # class index 0, the only score above the floor
    logits[0, 0, 2] = 8.0  # the background column, which is never a class

    found = thresholds.decode(dets, logits, 1600, 900)

    assert len(found) == 1
    box = found[0]
    assert box["class_index"] == 0
    assert box["score"] == pytest.approx(1 / (1 + np.exp(-2.0)), abs=1e-6)
    assert (box["x"], box["y"], box["w"], box["h"]) == pytest.approx((640.0, 270.0, 320.0, 360.0))


def test_decode_keeps_every_class_above_the_floor_sorted_by_score():
    dets = np.zeros((1, 1, 4), dtype=np.float32)
    dets[0, 0] = (0.5, 0.5, 0.5, 0.5)
    logits = np.array([[[1.0, 2.0, -9.0, 9.0]]], dtype=np.float32)

    found = thresholds.decode(dets, logits, 384, 384)

    assert [box["class_index"] for box in found] == [1, 0]


def test_preprocess_shape_and_values():
    frame = np.full((900, 1600, 3), 128, dtype=np.uint8)

    batch = thresholds.preprocess(frame)

    assert batch.shape == (1, 3, 384, 384)
    assert batch.dtype == np.float32
    for channel in range(3):
        want = (128 / 255 - thresholds.MEAN[channel]) / thresholds.STD[channel]
        assert batch[0, channel] == pytest.approx(want, abs=1e-5)


def test_preprocess_swaps_the_colour_channels():
    frame = np.zeros((900, 1600, 3), dtype=np.uint8)
    frame[:, :, 0] = 255  # blue in BGR becomes the last channel in RGB

    batch = thresholds.preprocess(frame)

    assert batch[0, 2].mean() > batch[0, 0].mean()


@pytest.mark.parametrize("name", ["train.py", "export.py"])
def test_script_starts_with_inline_metadata(name):
    text = (SCRIPTS / name).read_text(encoding="utf-8")
    assert text.startswith("# /// script")
    assert "rfdetr[train,onnx]==1.10.1" in text


def test_thresholds_imports_only_numpy_and_the_standard_library():
    """The isolated scripts import this module, and that environment has no brawlfarm in it.

    Only top-level imports count: preprocess imports cv2 inside its body on purpose, so the
    module stays importable wherever numpy alone is installed.
    """
    tree = ast.parse((SCRIPTS / "thresholds.py").read_text(encoding="utf-8"))
    allowed = set(sys.stdlib_module_names) | {"numpy"}
    for node in tree.body:
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        else:
            continue
        for module in names:
            assert module.split(".")[0] in allowed, module
