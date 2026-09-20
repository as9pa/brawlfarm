"""The Label Studio export turned into the COCO folder RF-DETR trains on.

Synthetic tiny JPEGs only, and never a real export file: the shapes here are the ones the
tool has to survive, including a cancelled annotation and a path that tries to leave the set.
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from tools.play import classes, coco


def _task(rel: str, boxes: list[tuple[str, float, float, float, float]], **kw) -> dict:
    result = [
        {
            "from_name": "label",
            "to_name": "image",
            "type": "rectanglelabels",
            "original_width": 1600,
            "original_height": 900,
            "value": {
                "x": x,
                "y": y,
                "width": w,
                "height": h,
                "rotation": 0,
                "rectanglelabels": [cls],
            },
        }
        for cls, x, y, w, h in boxes
    ]
    task = {"data": {"image": "/data/local-files/?d=" + rel, "file": rel}}
    task["annotations"] = [{"was_cancelled": False, "result": result}]
    task.update(kw)
    return task


def _write_frames(root: Path, sources: list[str], per_source: int = 2) -> list[str]:
    rels = []
    for source in sources:
        for n in range(1, per_source + 1):
            rel = f"frames/{source}/{source}-{n:06d}.jpg"
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            picture = np.full((90, 160, 3), n * 20, dtype=np.uint8)
            ok, buf = cv2.imencode(".jpg", picture)
            assert ok
            path.write_bytes(buf.tobytes())
            rels.append(rel)
    return rels


def test_split_of_is_stable_and_not_the_same_for_every_source():
    names = [f"yt-{n:011d}" for n in range(20)]

    first = [coco.split_of(name) for name in names]

    assert first == [coco.split_of(name) for name in names]
    assert len(set(first)) > 1


def test_assign_splits_of_ten_sources_leaves_no_split_empty():
    sources = [f"yt-{n:011d}" for n in range(10)]

    assigned = coco.assign_splits(sources)

    assert set(assigned) == set(sources)
    assert set(assigned.values()) == {"train", "valid", "test"}


def test_assign_splits_repairs_a_train_the_hash_left_empty():
    # These three hash to valid, valid, test, which used to train on nothing at all.
    assigned = coco.assign_splits(["src3", "src8", "src11"])

    assert sorted(assigned.values()) == ["test", "train", "valid"]


@pytest.mark.parametrize("count", range(3, 13))
def test_assign_splits_fills_every_split_and_keeps_train_the_largest(count):
    sources = [f"s{n}" for n in range(count)]

    assigned = coco.assign_splits(sources)

    sizes = {
        name: sum(1 for split in assigned.values() if split == name) for name, _ in coco.SPLITS
    }
    assert min(sizes.values()) >= 1
    assert sizes["train"] >= max(sizes["valid"], sizes["test"])


def test_assign_splits_does_not_depend_on_the_order_of_its_input():
    sources = [f"s{n}" for n in range(7)]

    assigned = coco.assign_splits(sources)

    assert assigned == coco.assign_splits(sources)
    assert assigned == coco.assign_splits(list(reversed(sources)))


def test_assign_splits_of_two_sources_keeps_them_all_in_train():
    assigned = coco.assign_splits(["alpha", "beta"])

    assert assigned == {"alpha": "train", "beta": "train"}


def test_from_labelstudio_reads_annotations_in_pixels():
    labels = coco.from_labelstudio(
        [_task("frames/a/a-000001.jpg", [("play_button", 25, 25, 10, 10)])]
    )

    assert labels == {
        "frames/a/a-000001.jpg": [{"class": "play_button", "x": 400, "y": 225, "w": 160, "h": 90}]
    }


def test_from_labelstudio_falls_back_to_the_image_url_for_the_file():
    task = _task("frames/a/a-000001.jpg", [])
    del task["data"]["file"]

    assert list(coco.from_labelstudio([task])) == ["frames/a/a-000001.jpg"]


def test_from_labelstudio_skips_a_cancelled_annotation():
    task = _task("frames/a/a-000001.jpg", [("play_button", 25, 25, 10, 10)])
    task["annotations"][0]["was_cancelled"] = True

    assert coco.from_labelstudio([task]) == {}


def test_from_labelstudio_reads_predictions_only_with_the_flag():
    task = _task("frames/a/a-000001.jpg", [])
    task["predictions"] = [
        _task("frames/a/a-000001.jpg", [("close_x", 50, 50, 5, 5)])["annotations"][0]
    ]

    assert coco.from_labelstudio([task]) == {"frames/a/a-000001.jpg": []}
    from_predictions = coco.from_labelstudio([task], use_predictions=True)
    assert from_predictions["frames/a/a-000001.jpg"][0]["class"] == "close_x"


def test_from_labelstudio_refuses_an_unknown_class():
    task = _task("frames/a/a-000001.jpg", [("brawler", 25, 25, 10, 10)])

    with pytest.raises(ValueError, match="brawler"):
        coco.from_labelstudio([task])


def test_build_writes_three_splits_covering_every_frame(tmp_path):
    root = tmp_path / "play"
    rels = _write_frames(root, ["alpha", "beta", "gamma"])
    labels = {rel: [{"class": "play_button", "x": 10, "y": 20, "w": 30, "h": 40}] for rel in rels}

    summary = coco.build(root, labels)

    total = 0
    for split, _ratio in coco.SPLITS:
        blob = json.loads(
            (root / "coco" / split / "_annotations.coco.json").read_text(encoding="utf-8")
        )
        assert [c["id"] for c in blob["categories"]] == list(range(1, len(classes.CLASSES) + 1))
        assert blob["categories"][0]["supercategory"] == "none"
        assert len(blob["images"]) == summary["frames"][split]
        for image in blob["images"]:
            assert (root / "coco" / split / image["file_name"]).exists()
        for annotation in blob["annotations"]:
            assert annotation["bbox"] == [10, 20, 30, 40]
            assert annotation["area"] == 1200
            assert annotation["iscrowd"] == 0
        total += len(blob["images"])
    assert total == 6
    assert summary["smoke"] is False
    assert summary["boxes"]["play_button"] == 6
    assert set(summary["sources"]) == {"alpha", "beta", "gamma"}
    assert json.loads((root / "coco" / "split.json").read_text(encoding="utf-8")) == summary


def test_build_training_set_hash_moves_with_a_single_pixel(tmp_path):
    root = tmp_path / "play"
    rels = _write_frames(root, ["alpha", "beta", "gamma"])
    labels = {rel: [{"class": "play_button", "x": 10, "y": 20, "w": 30, "h": 40}] for rel in rels}

    before = coco.build(root, labels)["training_set_hash"]
    again = coco.build(root, labels)["training_set_hash"]
    labels[rels[0]] = [{"class": "play_button", "x": 11, "y": 20, "w": 30, "h": 40}]
    after = coco.build(root, labels)["training_set_hash"]

    assert before == again
    assert before != after


def test_build_keeps_a_frame_with_no_boxes(tmp_path):
    root = tmp_path / "play"
    rels = _write_frames(root, ["alpha", "beta", "gamma"])
    labels = {rel: [] for rel in rels}

    summary = coco.build(root, labels)

    assert sum(summary["frames"].values()) == 6
    assert summary["boxes"]["play_button"] == 0


def test_build_of_two_sources_is_a_smoke_layout(tmp_path):
    root = tmp_path / "play"
    rels = _write_frames(root, ["alpha", "beta"])
    labels = {rel: [] for rel in rels}

    summary = coco.build(root, labels)

    assert summary["smoke"] is True
    assert summary["frames"] == {"train": 4, "valid": 4, "test": 4}


def test_build_clears_a_previous_coco_folder(tmp_path):
    root = tmp_path / "play"
    rels = _write_frames(root, ["alpha", "beta", "gamma"])
    stale = root / "coco" / "train" / "stale-000001.jpg"
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_bytes(b"old")

    coco.build(root, {rel: [] for rel in rels})

    assert not stale.exists()


def test_build_refuses_a_file_outside_the_frames_folder(tmp_path):
    root = tmp_path / "play"
    _write_frames(root, ["alpha", "beta", "gamma"])

    with pytest.raises(ValueError):
        coco.build(root, {"../../secret.jpg": []})


def test_main_builds_from_an_export_file(tmp_path, capsys):
    root = tmp_path / "play"
    rels = _write_frames(root, ["alpha", "beta", "gamma"])
    export = tmp_path / "export.json"
    export.write_text(
        json.dumps([_task(rel, [("play_button", 25, 25, 10, 10)]) for rel in rels]),
        encoding="utf-8",
    )

    code = coco.main([str(export), "--root", str(root)])

    assert code == 0
    assert (root / "coco" / "split.json").exists()
    assert "6 frames" in capsys.readouterr().out


def test_build_refuses_to_write_an_empty_training_set(tmp_path):
    root = tmp_path / "play"
    _write_frames(root, ["alpha"])

    with pytest.raises(ValueError, match="no training frames"):
        coco.build(root, {})
