"""Scoring a model against the template verdicts, with the never-tap bar on tap anchors.

No model and no template picture is real here: the session is a fake returning hand-built
arrays and the matcher is a fake, so what is under test is the decoding, the per-class
threshold, the four verdicts and the pass flag, not what a real net happens to believe.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from brawlfarm.core.vision import Match
from tools.play import classes, dataset, score

PLAY = classes.CLASSES.index("play_button")
CLOSE = classes.CLASSES.index("close_x")
SKULL = classes.CLASSES.index("skull_star")


class _Session:
    """A stand-in for an onnxruntime session: fixed outputs, in the order it was given them."""

    def __init__(self, outputs: list[tuple[str, np.ndarray]]):
        self.outputs = outputs
        self.feeds: list[dict] = []

    def get_outputs(self):
        return [SimpleNamespace(name=name) for name, _ in self.outputs]

    def run(self, wanted, feeds):
        assert wanted is None
        self.feeds.append(feeds)
        return [array for _, array in self.outputs]


def _arrays(rows: list[tuple[int, float, tuple[float, float, float, float]]]):
    """Hand-built RF-DETR outputs: one query per row, as (class index, score, cxcywh in 0..1)."""
    dets = np.zeros((1, len(rows), 4), dtype=np.float32)
    logits = np.full((1, len(rows), len(classes.CLASSES) + 1), -20.0, dtype=np.float32)
    for query, (index, wanted, box) in enumerate(rows):
        dets[0, query] = box
        logits[0, query, index] = math.log(wanted / (1 - wanted))
    return dets, logits


def _meta(thresholds: dict[str, float]) -> dict:
    return {
        "input": {"name": "input", "size": 384},
        "outputs": {"boxes": "dets", "logits": "labels"},
        "classes": list(classes.CLASSES),
        "thresholds": thresholds,
        "training_set_hash": "0123456789abcdef",
        "smoke": False,
    }


def _session(rows, *, reversed_outputs: bool = False) -> _Session:
    dets, logits = _arrays(rows)
    outputs = [("dets", dets), ("labels", logits)]
    return _Session(list(reversed(outputs)) if reversed_outputs else outputs)


def _frame(h: int = dataset.FRAME_H, w: int = dataset.FRAME_W) -> np.ndarray:
    return np.zeros((h, w, 3), dtype=np.uint8)


def _finder(matches: dict[str, Match]):
    def find(frame, name, threshold=None):
        match = matches.get(name)
        return match, 0.9 if match is not None else 0.1

    return find


def _box(cls: str, x: int, y: int, w: int, h: int, sc: float = 0.9) -> dict:
    return {"class": cls, "x": x, "y": y, "w": w, "h": h, "score": sc}


def test_detect_keeps_only_a_score_at_or_above_the_per_class_threshold():
    session = _session([(PLAY, 0.9, (0.3, 0.5, 0.1, 0.1)), (CLOSE, 0.4, (0.9, 0.1, 0.05, 0.05))])

    found = score.detect(session, _meta({"play_button": 0.5, "close_x": 0.6}), _frame())

    assert [box["class"] for box in found] == ["play_button"]
    assert found[0]["x"] == pytest.approx(400, abs=0.01)
    assert found[0]["y"] == pytest.approx(405, abs=0.01)
    assert found[0]["w"] == pytest.approx(160, abs=0.01)
    assert found[0]["h"] == pytest.approx(90, abs=0.01)
    assert found[0]["score"] > 0.89
    assert session.feeds[0]["input"].shape == (1, 3, 384, 384)


def test_detect_takes_the_outputs_by_name_not_by_position():
    rows = [(PLAY, 0.8, (0.3, 0.5, 0.1, 0.1))]
    straight = score.detect(_session(rows), _meta({"play_button": 0.5}), _frame())
    swapped = score.detect(
        _session(rows, reversed_outputs=True), _meta({"play_button": 0.5}), _frame()
    )

    assert straight == swapped != []


def test_detect_disbelieves_a_class_with_no_threshold():
    session = _session([(PLAY, 0.9, (0.3, 0.5, 0.1, 0.1))])

    assert score.detect(session, _meta({}), _frame()) == []


def test_template_truth_has_a_box_for_a_match_and_none_for_the_rest():
    find = _finder({"play": Match(name="play", confidence=0.9, x=480, y=270, w=160, h=90)})

    truth = score.template_truth(_frame(), find=find)

    assert set(truth) == set(classes.TEMPLATE_CLASS.values())
    assert truth["play_button"] == {
        "class": "play_button",
        "x": 400,
        "y": 225,
        "w": 160,
        "h": 90,
        "score": 0.9,
    }
    assert truth["close_x"] is None


def test_compare_calls_an_overlapping_detection_a_true_positive():
    truth = {"play_button": _box("play_button", 400, 225, 160, 90), "close_x": None}
    found = [{"class": "play_button", "x": 405, "y": 230, "w": 160, "h": 90, "score": 0.9}]

    assert score.compare(found, truth)["play_button"] == "tp"


def test_compare_calls_a_template_box_with_no_detection_a_false_negative():
    truth = {"play_button": _box("play_button", 400, 225, 160, 90)}

    assert score.compare([], truth)["play_button"] == "fn"
    far = [{"class": "play_button", "x": 1000, "y": 700, "w": 160, "h": 90, "score": 0.9}]
    assert score.compare(far, truth)["play_button"] == "fn"


def test_compare_calls_a_detection_the_templates_do_not_see_a_false_positive():
    truth = {"play_button": None}
    found = [{"class": "play_button", "x": 400, "y": 225, "w": 160, "h": 90, "score": 0.9}]

    assert score.compare(found, truth)["play_button"] == "fp"


def test_compare_calls_silence_on_both_sides_a_true_negative():
    assert score.compare([], {"play_button": None})["play_button"] == "tn"


def report_of(rows: list[dict]) -> dict:
    return score.report(rows)["classes"]


def test_report_sums_the_verdicts_per_class():
    rows = [
        {"play_button": "tp", "close_x": "tn"},
        {"play_button": "fn", "close_x": "tn"},
        {"play_button": "tp", "close_x": "tn"},
    ]

    totals = report_of(rows)["play_button"]

    assert totals["tp"] == 2 and totals["fn"] == 1 and totals["fp"] == 0 and totals["tn"] == 0
    assert totals["precision"] == 1.0
    assert totals["recall"] == round(2 / 3, 4)


def test_report_passes_with_no_tap_anchor_false_positive():
    summary = score.report([{"play_button": "tp", "close_x": "fn"}])

    assert summary["tap_anchor_false_positives"] == 0
    assert summary["pass"] is True


def test_report_fails_on_a_single_tap_anchor_false_positive():
    summary = score.report([{"play_button": "tp"}, {"play_button": "fp"}])

    assert summary["tap_anchor_false_positives"] == 1
    assert summary["pass"] is False


def _write_frames(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(folder / "good.jpg"), _frame())
    cv2.imwrite(str(folder / "small.jpg"), _frame(450, 800))
    (folder / "broken.png").write_bytes(b"not a picture")


def _write_model(models: Path) -> None:
    """The files main checks for before it loads anything; the fake load_model ignores them."""
    models.mkdir(parents=True, exist_ok=True)
    (models / "play.onnx").write_bytes(b"not a real model")
    (models / "play.json").write_text("{}", encoding="utf-8")


def _fake_load_model(session, meta):
    def load_model(models, *, cuda=False):
        return session, meta

    return load_model


def test_main_passes_and_writes_score_json(tmp_path, monkeypatch, capsys):
    frames = tmp_path / "frames"
    _write_frames(frames)
    _write_model(tmp_path / "models")
    session = _session([(PLAY, 0.9, (0.3, 0.5, 0.1, 0.1))])
    monkeypatch.setattr(score, "load_model", _fake_load_model(session, _meta({"play_button": 0.5})))
    find = _finder({"play": Match(name="play", confidence=0.9, x=480, y=450, w=160, h=90)})

    code = score.main(
        ["--models", str(tmp_path / "models"), "--frames", str(frames)],
        find=find,
    )

    assert code == 0
    written = json.loads((tmp_path / "models" / "score.json").read_text(encoding="utf-8"))
    assert written["pass"] is True
    assert written["frames"] == {"scored": 1, "skipped": 2}
    assert written["classes"]["play_button"]["tp"] == 1
    assert written["training_set_hash"] == "0123456789abcdef"
    assert written["smoke"] is False
    assert written["generated"].endswith("+00:00")
    assert str(frames) not in capsys.readouterr().out


def test_main_fails_on_a_tap_anchor_the_templates_do_not_see(tmp_path, monkeypatch, capsys):
    frames = tmp_path / "frames"
    _write_frames(frames)
    _write_model(tmp_path / "models")
    session = _session([(PLAY, 0.9, (0.3, 0.5, 0.1, 0.1))])
    monkeypatch.setattr(score, "load_model", _fake_load_model(session, _meta({"play_button": 0.5})))

    code = score.main(
        ["--models", str(tmp_path / "models"), "--frames", str(frames)],
        find=_finder({}),
    )

    assert code == 1
    written = json.loads((tmp_path / "models" / "score.json").read_text(encoding="utf-8"))
    assert written["pass"] is False
    assert written["tap_anchor_false_positives"] == 1
    assert written["tap_anchor_failures"] == [{"file": "good.jpg", "class": "play_button"}]
    assert "good.jpg" in capsys.readouterr().out


def test_main_reports_a_tap_anchor_with_no_template_as_unverified(tmp_path, monkeypatch):
    frames = tmp_path / "frames"
    _write_frames(frames)
    _write_model(tmp_path / "models")
    session = _session([(SKULL, 0.9, (0.3, 0.5, 0.1, 0.1))])
    monkeypatch.setattr(score, "load_model", _fake_load_model(session, _meta({"skull_star": 0.5})))

    code = score.main(
        ["--models", str(tmp_path / "models"), "--frames", str(frames)],
        find=_finder({}),
    )

    assert code == 0
    written = json.loads((tmp_path / "models" / "score.json").read_text(encoding="utf-8"))
    assert written["unverified_tap_anchor_detections"] == [
        {"file": "good.jpg", "class": "skull_star"}
    ]
    assert written["tap_anchor_false_positives"] == 0
    assert written["pass"] is True


def test_compare_keeps_an_extra_detection_beside_a_true_positive():
    truth = {"play_button": _box("play_button", 400, 225, 160, 90)}
    found = [
        {"class": "play_button", "x": 405, "y": 230, "w": 160, "h": 90, "score": 0.9},
        {"class": "play_button", "x": 1000, "y": 700, "w": 160, "h": 90, "score": 0.8},
    ]

    assert score.compare(found, truth)["play_button"] == "tp+extra"


def test_compare_calls_two_detections_on_one_template_box_a_plain_true_positive():
    truth = {"play_button": _box("play_button", 400, 225, 160, 90)}
    found = [
        {"class": "play_button", "x": 400, "y": 225, "w": 160, "h": 90, "score": 0.9},
        {"class": "play_button", "x": 410, "y": 235, "w": 160, "h": 90, "score": 0.8},
    ]

    assert score.compare(found, truth)["play_button"] == "tp"


def test_report_counts_an_extra_as_a_true_and_a_false_positive():
    totals = report_of([{"play_button": "tp+extra"}])["play_button"]

    assert totals["tp"] == 1 and totals["fp"] == 1
    assert totals["precision"] == 0.5


def test_report_fails_on_an_extra_tap_anchor_detection():
    summary = score.report([{"play_button": "tp"}, {"play_button": "tp+extra"}])

    assert summary["tap_anchor_false_positives"] == 1
    assert summary["pass"] is False


def test_report_passes_on_an_extra_for_a_class_that_is_not_a_tap_anchor():
    summary = score.report([{"power_cube": "tp+extra"}])

    assert summary["classes"]["power_cube"]["fp"] == 1
    assert summary["tap_anchor_false_positives"] == 0
    assert summary["pass"] is True


def test_report_fails_when_there_is_nothing_to_report():
    assert score.report([])["pass"] is False


def test_main_fails_when_no_frame_could_be_scored(tmp_path, monkeypatch, capsys):
    frames = tmp_path / "frames"
    frames.mkdir()
    cv2.imwrite(str(frames / "small.jpg"), _frame(450, 800))
    _write_model(tmp_path / "models")
    session = _session([(PLAY, 0.9, (0.3, 0.5, 0.1, 0.1))])
    monkeypatch.setattr(score, "load_model", _fake_load_model(session, _meta({"play_button": 0.5})))

    code = score.main(
        ["--models", str(tmp_path / "models"), "--frames", str(frames)],
        find=_finder({}),
    )

    assert code == 1
    written = json.loads((tmp_path / "models" / "score.json").read_text(encoding="utf-8"))
    assert written["pass"] is False
    assert written["frames"] == {"scored": 0, "skipped": 1}
    assert "nothing is proven" in capsys.readouterr().out


def test_main_fails_on_an_extra_tap_anchor_detection(tmp_path, monkeypatch):
    frames = tmp_path / "frames"
    _write_frames(frames)
    _write_model(tmp_path / "models")
    session = _session([(PLAY, 0.9, (0.3, 0.5, 0.1, 0.1)), (PLAY, 0.8, (0.8, 0.8, 0.1, 0.1))])
    monkeypatch.setattr(score, "load_model", _fake_load_model(session, _meta({"play_button": 0.5})))
    find = _finder({"play": Match(name="play", confidence=0.9, x=480, y=450, w=160, h=90)})

    code = score.main(
        ["--models", str(tmp_path / "models"), "--frames", str(frames)],
        find=find,
    )

    assert code == 1
    written = json.loads((tmp_path / "models" / "score.json").read_text(encoding="utf-8"))
    assert written["tap_anchor_failures"] == [{"file": "good.jpg", "class": "play_button"}]
    assert written["classes"]["play_button"] == {
        "tp": 1,
        "fp": 1,
        "fn": 0,
        "tn": 0,
        "precision": 0.5,
        "recall": 1.0,
    }
