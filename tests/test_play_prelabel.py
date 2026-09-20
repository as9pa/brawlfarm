"""Template pre-labels and the Label Studio import file.

The template matcher is always a fake here: a pre-label is about the box maths, not about
what a real template picture happens to score on a synthetic frame.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from brawlfarm.core.vision import Match
from tools.play import classes, dataset, prelabel

LABELSTUDIO_XML = Path(prelabel.__file__).with_name("labelstudio.xml")


def _frame(h: int = dataset.FRAME_H, w: int = dataset.FRAME_W) -> np.ndarray:
    return np.zeros((h, w, 3), dtype=np.uint8)


def _finder(matches: dict[str, Match], scores: dict[str, float] | None = None):
    """A stand-in for vision.find_with_score that only knows the templates it was given."""
    scores = scores or {}

    def find(frame, name, threshold=None):
        match = matches.get(name)
        return match, scores.get(name, 0.9 if match is not None else 0.1)

    return find


def _match(name: str, x: int, y: int, w: int, h: int) -> Match:
    return Match(name=name, confidence=0.9, x=x, y=y, w=w, h=h)


def test_boxes_for_turns_a_centre_into_a_top_left_corner():
    find = _finder({"play": _match("play", 480, 270, 160, 90)}, {"play": 0.912345})

    boxes = prelabel.boxes_for(_frame(), find=find)

    assert boxes == [
        {"class": "play_button", "x": 400, "y": 225, "w": 160, "h": 90, "score": 0.9123}
    ]


def test_boxes_for_clips_a_match_hanging_over_the_frame_edge():
    find = _finder({"close_x": _match("close_x", 1590, 8, 60, 60)})

    boxes = prelabel.boxes_for(_frame(), find=find)

    assert boxes == [{"class": "close_x", "x": 1560, "y": 0, "w": 40, "h": 38, "score": 0.9}]


def test_boxes_for_has_no_box_when_nothing_matches():
    assert prelabel.boxes_for(_frame(), find=_finder({})) == []


def test_task_for_turns_pixels_into_percentages():
    box = {"class": "play_button", "x": 400, "y": 225, "w": 160, "h": 90, "score": 0.75}

    task = prelabel.task_for("frames/a/a-000001.jpg", [box])

    assert task["data"] == {
        "image": "/data/local-files/?d=frames/a/a-000001.jpg",
        "file": "frames/a/a-000001.jpg",
    }
    prediction = task["predictions"][0]
    assert prediction["model_version"] == prelabel.MODEL_VERSION
    assert prediction["score"] == 0.75
    result = prediction["result"][0]
    assert len(result["id"]) == 8
    assert result["from_name"] == "label"
    assert result["to_name"] == "image"
    assert result["type"] == "rectanglelabels"
    assert result["original_width"] == 1600
    assert result["original_height"] == 900
    assert result["value"] == {
        "x": 25.0,
        "y": 25.0,
        "width": 10.0,
        "height": 10.0,
        "rotation": 0,
        "rectanglelabels": ["play_button"],
    }


def test_task_for_without_boxes_has_no_predictions():
    task = prelabel.task_for("frames/a/a-000001.jpg", [])

    assert task["predictions"] == []
    assert task["data"]["file"] == "frames/a/a-000001.jpg"


def test_labelstudio_config_labels_are_the_class_list():
    text = LABELSTUDIO_XML.read_text(encoding="utf-8")

    values = [
        line.split('value="')[1].split('"')[0] for line in text.splitlines() if "<Label " in line
    ]
    assert tuple(values) == classes.CLASSES


def _index(root: Path, rows: list[tuple[str, str]]) -> None:
    index = dataset.Index(root)
    for source, rel in rows:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        dataset.save_frame(root, source, int(rel.split("-")[-1].split(".")[0]), _frame(90, 160))
        index.add(
            file=rel,
            source=source,
            kind="video",
            t=None,
            hash_=abs(hash(rel)) % (2**64),
            teams_left=1.0,
            pad=(0, 0, 0, 0),
        )


@pytest.fixture
def one_box(monkeypatch):
    """Every frame pre-labels as a single play button, so main's counts are predictable."""
    monkeypatch.setattr(
        prelabel,
        "boxes_for",
        lambda frame, **kw: [
            {"class": "play_button", "x": 10, "y": 10, "w": 20, "h": 20, "score": 0.9}
        ],
    )


def test_main_writes_one_task_per_frame_and_the_config(tmp_path, capsys, one_box):
    root = tmp_path / "play"
    _index(
        root, [("alpha", "frames/alpha/alpha-000001.jpg"), ("beta", "frames/beta/beta-000002.jpg")]
    )

    code = prelabel.main(["--root", str(root)])

    assert code == 0
    tasks = json.loads((root / "labelstudio" / "tasks.json").read_text(encoding="utf-8"))
    assert [task["data"]["file"] for task in tasks] == [
        "frames/alpha/alpha-000001.jpg",
        "frames/beta/beta-000002.jpg",
    ]
    assert (root / "labelstudio" / "config.xml").read_text(encoding="utf-8") == (
        LABELSTUDIO_XML.read_text(encoding="utf-8")
    )
    out = capsys.readouterr().out
    assert "2 frames" in out
    assert "play_button 2" in out


def test_main_can_pre_label_only_some_sources(tmp_path, capsys, one_box):
    root = tmp_path / "play"
    _index(
        root, [("alpha", "frames/alpha/alpha-000001.jpg"), ("beta", "frames/beta/beta-000002.jpg")]
    )

    code = prelabel.main(["--root", str(root), "--source", "beta"])

    assert code == 0
    tasks = json.loads((root / "labelstudio" / "tasks.json").read_text(encoding="utf-8"))
    assert [task["data"]["file"] for task in tasks] == ["frames/beta/beta-000002.jpg"]
