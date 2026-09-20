"""The Label Studio export turned into the COCO folder RF-DETR trains on.

The split is by source video, never by frame: consecutive frames of one video look alike, so a
frame-wise split would put near-copies on both sides of it and score a model on pictures it has
already seen. A source is assigned by hashing its name, which keeps the split stable when more
videos are added later. Frames with no boxes are kept: a detector needs to be shown the screens
where there is nothing to find.

    uv run python tools/play/coco.py export.json
    uv run python tools/play/coco.py export.json --root D:/play-data --from-predictions
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

from tools.play import classes, dataset

SPLITS = (("train", 0.8), ("valid", 0.1), ("test", 0.1))
# Below this many sources a real split would leave a side empty, so the kit builds a smoke
# layout instead: the same frames in all three folders, good enough to prove the pipeline runs.
SMOKE_MIN = 3


def split_of(source: str) -> str:
    """Which split a source belongs to, from its name alone, the same answer every run."""
    point = int(hashlib.sha256(source.encode()).hexdigest()[:8], 16) / 2**32
    cumulative = 0.0
    for name, ratio in SPLITS:
        cumulative += ratio
        if point < cumulative:
            return name
    return SPLITS[-1][0]


def assign_splits(sources: list[str]) -> dict[str, str]:
    """Map each source to its split, then repair a split the hashing left empty.

    With a handful of sources the hash can easily put none of them in valid or test, which
    would silently train without a score. The repair moves whole sources out of train, one per
    empty split, and never the last one: a set has to keep something to train on.
    """
    assigned = {source: split_of(source) for source in sources}
    if len(assigned) < SMOKE_MIN:
        return {source: "train" for source in assigned}
    for name, _ratio in SPLITS:
        if name == "train" or any(split == name for split in assigned.values()):
            continue
        in_train = sorted(source for source, split in assigned.items() if split == "train")
        if len(in_train) < 2:
            continue
        assigned[in_train[-1]] = name
    return assigned


def _file_of(task: dict) -> str:
    """The frame path a task points at, as this kit imported it."""
    data = task.get("data", {})
    if data.get("file"):
        return str(data["file"])
    image = str(data.get("image", ""))
    if "?d=" not in image:
        raise ValueError(f"task has no frame path: {data!r}")
    return image.split("?d=", 1)[1]


def _result_of(task: dict, *, use_predictions: bool) -> list[dict] | None:
    """The result list to read, or None when the task has nothing to take."""
    if use_predictions:
        predictions = task.get("predictions") or []
        return predictions[0].get("result", []) if predictions else None
    for annotation in task.get("annotations") or []:
        # A cancelled annotation is the labeller saying the frame is unusable, not an empty one.
        if not annotation.get("was_cancelled"):
            return annotation.get("result", [])
    return None


def from_labelstudio(export: list[dict], *, use_predictions: bool = False) -> dict[str, list[dict]]:
    """Read an export into frame path -> boxes in pixels.

    Label Studio stores a box as percentages of the picture it showed, so the pixels come back
    through that picture's size rather than the dataset's, which keeps the maths honest if a
    frame was ever imported at another size.
    """
    labels: dict[str, list[dict]] = {}
    for task in export:
        result = _result_of(task, use_predictions=use_predictions)
        if result is None:
            continue
        boxes = []
        for item in result:
            value = item.get("value", {})
            names = value.get("rectanglelabels") or []
            if not names:
                continue
            cls = names[0]
            if cls not in classes.CLASSES:
                raise ValueError(f"unknown class in the export: {cls!r}")
            width = item.get("original_width", dataset.FRAME_W)
            height = item.get("original_height", dataset.FRAME_H)
            boxes.append(
                {
                    "class": cls,
                    "x": round(value["x"] * width / 100),
                    "y": round(value["y"] * height / 100),
                    "w": round(value["width"] * width / 100),
                    "h": round(value["height"] * height / 100),
                }
            )
        labels[_file_of(task)] = boxes
    return labels


def _source_of(root: Path, rel: str) -> tuple[Path, str]:
    """Resolve one export path against the root, refusing anything outside `frames/`.

    The path comes out of a file the owner exported, so it is untrusted: `..` in it would copy
    whatever it reached into the training folder.
    """
    frames = (root / "frames").resolve()
    path = (root / rel).resolve()
    if path == frames or frames not in path.parents:
        raise ValueError(f"frame path leaves the dataset: {rel!r}")
    return path, dataset.check_source(path.parent.name)


def _clear_coco(root: Path) -> Path:
    """Delete a previous build, after proving the folder is the one under this root."""
    coco = (root / "coco").resolve()
    if coco.name != "coco" or coco.parent != root.resolve():
        raise ValueError(f"refusing to clear {coco}")
    if coco.exists():
        shutil.rmtree(coco)
    return coco


def build(root: Path, labels: dict[str, list[dict]]) -> dict:
    """Write `coco/{train,valid,test}` plus `coco/split.json`, and return the summary."""
    root = Path(root)
    entries = []
    for rel in sorted(labels):
        path, source = _source_of(root, rel)
        entries.append((rel, path, source))
    sources = sorted({source for _rel, _path, source in entries})
    assigned = assign_splits(sources)
    smoke = len(sources) < SMOKE_MIN

    per_split: dict[str, list[tuple[str, Path]]] = {name: [] for name, _ratio in SPLITS}
    for rel, path, source in entries:
        names = [name for name, _ratio in SPLITS] if smoke else [assigned[source]]
        for name in names:
            per_split[name].append((rel, path))

    coco = _clear_coco(root)
    categories = [
        {"id": classes.category_id(cls), "name": cls, "supercategory": "none"}
        for cls in classes.CLASSES
    ]
    frames: dict[str, int] = {}
    # Counted over the labels, not the folders: a smoke layout writes each frame three times.
    boxes: Counter[str] = Counter(
        box["class"] for rel, _path, _source in entries for box in labels[rel]
    )
    for name, _ratio in SPLITS:
        folder = coco / name
        folder.mkdir(parents=True, exist_ok=True)
        images = []
        annotations = []
        for image_id, (rel, path) in enumerate(per_split[name], start=1):
            blob = path.read_bytes()
            picture = cv2.imdecode(np.frombuffer(blob, np.uint8), cv2.IMREAD_COLOR)
            if picture is None:
                raise ValueError(f"not a readable frame: {rel}")
            (folder / path.name).write_bytes(blob)
            height, width = picture.shape[:2]
            images.append(
                {"id": image_id, "file_name": path.name, "width": width, "height": height}
            )
            for box in labels[rel]:
                annotations.append(
                    {
                        "id": len(annotations) + 1,
                        "image_id": image_id,
                        "category_id": classes.category_id(box["class"]),
                        "bbox": [box["x"], box["y"], box["w"], box["h"]],
                        "area": box["w"] * box["h"],
                        "iscrowd": 0,
                    }
                )
        (folder / "_annotations.coco.json").write_text(
            json.dumps(
                {"images": images, "annotations": annotations, "categories": categories}, indent=1
            ),
            encoding="utf-8",
        )
        frames[name] = len(images)

    lines = sorted(
        f"{rel}|{box['class']}|{box['x']}|{box['y']}|{box['w']}|{box['h']}"
        for rel, _path in per_split[SPLITS[0][0]]
        for box in labels[rel]
    )
    summary = {
        "sources": assigned,
        "smoke": smoke,
        "frames": frames,
        "boxes": {cls: boxes[cls] for cls in classes.CLASSES},
        "training_set_hash": hashlib.sha256("\n".join(lines).encode()).hexdigest(),
    }
    (coco / "split.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("export", type=Path, help="the JSON file Label Studio exported")
    ap.add_argument("--root", type=Path, default=None, help="dataset root")
    ap.add_argument(
        "--from-predictions",
        action="store_true",
        help="take the template pre-labels instead of the labelled boxes",
    )
    args = ap.parse_args(argv)

    root = args.root if args.root is not None else dataset.default_root()
    export = json.loads(Path(args.export).read_text(encoding="utf-8"))
    labels = from_labelstudio(export, use_predictions=args.from_predictions)
    if not labels:
        print(f"{args.export} has no usable task")
        return 1

    summary = build(root, labels)
    counts = ", ".join(f"{name} {summary['frames'][name]}" for name, _ratio in SPLITS)
    print(f"{len(labels)} frames from {len(summary['sources'])} sources: {counts}")
    if summary["smoke"]:
        print("smoke layout: the same frames are in all three splits")
    for cls in classes.CLASSES:
        if summary["boxes"][cls]:
            print(f"  {cls} {summary['boxes'][cls]}")
    print(f"training set hash {summary['training_set_hash'][:16]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
