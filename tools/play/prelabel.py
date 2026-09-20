"""Template pre-labels: the farm's own template matcher drafting boxes for the labeller.

Only a handful of classes have a template behind them, so a pre-label is a head start on the
buttons and cards, never the whole frame: brawlers, cubes and bushes are all drawn by hand.
The output is a Label Studio import file where each frame is one task carrying its drafts as a
prediction, so the labeller opens a frame with the boxes already on it and fixes what is wrong.

    uv run python tools/play/prelabel.py
    uv run python tools/play/prelabel.py --root D:/play-data --source yt-AAAAAAAAAAA
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

from brawlfarm.core import vision
from tools.play import classes, dataset

MODEL_VERSION = "templates-v1"
CONFIG_XML = Path(__file__).with_name("labelstudio.xml")


def boxes_for(frame: np.ndarray, *, find=vision.find_with_score) -> list[dict]:
    """Draft boxes for one frame: one per template in TEMPLATE_CLASS that matched.

    A Match carries its centre, so the corner is the centre minus half the template size, and
    a match that hangs over an edge is clipped rather than dropped: the visible part is still
    the right box, and a box outside the picture would be rejected on import.
    """
    height, width = frame.shape[:2]
    boxes: list[dict] = []
    for template, cls in classes.TEMPLATE_CLASS.items():
        match, score = find(frame, template)
        if match is None:
            continue
        left = max(0, match.x - match.w // 2)
        top = max(0, match.y - match.h // 2)
        right = min(width, match.x - match.w // 2 + match.w)
        bottom = min(height, match.y - match.h // 2 + match.h)
        if right <= left or bottom <= top:
            continue
        boxes.append(
            {
                "class": cls,
                "x": left,
                "y": top,
                "w": right - left,
                "h": bottom - top,
                "score": round(float(score), 4),
            }
        )
    return boxes


def task_for(rel_file: str, boxes: list[dict]) -> dict:
    """One Label Studio task: the frame plus its drafts as a single prediction.

    Label Studio stores a box as percentages of the picture, and serves the picture through
    its local files handler, hence the `?d=` URL. The result ids are derived from the frame
    and the box, so re-running the tool produces the same file instead of a fresh diff.
    """
    result = []
    for box in boxes:
        seed = f"{rel_file}|{box['class']}|{box['x']}|{box['y']}|{box['w']}|{box['h']}"
        result.append(
            {
                "id": hashlib.sha256(seed.encode()).hexdigest()[:8],
                "from_name": "label",
                "to_name": "image",
                "type": "rectanglelabels",
                "original_width": dataset.FRAME_W,
                "original_height": dataset.FRAME_H,
                "score": box["score"],
                "value": {
                    "x": round(box["x"] * 100 / dataset.FRAME_W, 4),
                    "y": round(box["y"] * 100 / dataset.FRAME_H, 4),
                    "width": round(box["w"] * 100 / dataset.FRAME_W, 4),
                    "height": round(box["h"] * 100 / dataset.FRAME_H, 4),
                    "rotation": 0,
                    "rectanglelabels": [box["class"]],
                },
            }
        )
    predictions = []
    if result:
        mean = sum(box["score"] for box in boxes) / len(boxes)
        predictions.append(
            {"model_version": MODEL_VERSION, "score": round(mean, 4), "result": result}
        )
    return {
        "data": {"image": "/data/local-files/?d=" + rel_file, "file": rel_file},
        "predictions": predictions,
    }


def _read_frame(path: Path) -> np.ndarray | None:
    """imdecode, not imread: OpenCV cannot read a non-ASCII path on Windows."""
    if not path.exists():
        return None
    return cv2.imdecode(np.frombuffer(path.read_bytes(), np.uint8), cv2.IMREAD_COLOR)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--root", type=Path, default=None, help="dataset root")
    ap.add_argument(
        "--source",
        action="append",
        default=None,
        metavar="NAME",
        help="pre-label only this source; repeat for more",
    )
    args = ap.parse_args(argv)

    root = args.root if args.root is not None else dataset.default_root()
    wanted = {dataset.check_source(name) for name in args.source} if args.source else None
    index = root / "index.jsonl"
    if not index.exists():
        print(f"no index at {index}; extract some frames first")
        return 1

    tasks = []
    missing = 0
    with_boxes = 0
    per_class: Counter[str] = Counter()
    for line in index.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if wanted is not None and row["source"] not in wanted:
            continue
        frame = _read_frame(root / row["file"])
        if frame is None:
            # The index outlives the files, so a deleted frame is reported, not fatal.
            missing += 1
            continue
        boxes = boxes_for(frame)
        if boxes:
            with_boxes += 1
            per_class.update(box["class"] for box in boxes)
        tasks.append(task_for(row["file"], boxes))

    out = root / "labelstudio"
    out.mkdir(parents=True, exist_ok=True)
    (out / "tasks.json").write_text(json.dumps(tasks, indent=1), encoding="utf-8")
    shutil.copyfile(CONFIG_XML, out / "config.xml")

    print(f"{len(tasks)} frames, {with_boxes} with boxes, {missing} missing")
    for cls in classes.CLASSES:
        if per_class[cls]:
            print(f"  {cls} {per_class[cls]}")
    print(f"wrote {out / 'tasks.json'} and {out / 'config.xml'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
