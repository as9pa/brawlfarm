"""Score an exported model against what the farm's own templates say about every frame on disk.

The templates are the only truth this kit has outside the labelled set, and they are the same
truth the farm loop already trusts, so a model is judged by them before it is ever allowed to
drive: per template class and per frame, the model and the template matcher either agree or
they do not. The bar is the never-tap rail, not the average: one detection of a tappable
control on a frame where the template sees none fails the whole report, because a tap on the
wrong pixel spends gems or leaves a queue. Missing a control is only a slow loop.

Three tap anchors have no template behind them (skull_star, team_up_panel, event_tab), so
nothing here can tell a good detection of one from a bad one. Those are listed on their own
and decide nothing; they are for the owner to look at.

    uv run python tools/play/score.py
    uv run python tools/play/score.py --frames D:/shots --cuda
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort

from brawlfarm import settings
from brawlfarm.core import vision
from tools.play import classes, dataset, prelabel, thresholds

SUFFIXES = frozenset({".jpg", ".jpeg", ".png"})
# tap anchors the templates cannot judge: a detection of one is reported, never counted
UNVERIFIABLE: frozenset[str] = classes.TAP_ANCHORS - set(classes.TEMPLATE_CLASS.values())


def load_model(models: Path, *, cuda: bool = False) -> tuple[ort.InferenceSession, dict]:
    """play.onnx and play.json out of a models folder, on the CPU provider unless cuda is asked.

    The providers the session really got are printed rather than assumed: onnxruntime falls back
    to the CPU without a word when the CUDA libraries are missing, and a report that took an hour
    on the CPU while the owner thought it was on the GPU is a report nobody trusts twice.
    """
    meta = json.loads((models / "play.json").read_text(encoding="utf-8"))
    providers = ["CPUExecutionProvider"]
    if cuda:
        if hasattr(ort, "preload_dlls"):
            try:
                ort.preload_dlls()
            except Exception as exc:  # an old or CPU-only build: say so and carry on
                print(f"preload_dlls failed ({exc}); trying CUDA anyway")
        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    session = ort.InferenceSession(str(models / "play.onnx"), providers=providers)
    print(f"providers: {', '.join(session.get_providers())}")
    return session, meta


def detect(sess, meta: dict, frame: np.ndarray) -> list[dict]:
    """One frame through the model: the detections at or above their own class threshold.

    The two outputs are taken by the names play.json recorded, looked up in the session, so an
    export that reordered them cannot silently swap the boxes with the logits. A class the
    export left out of the thresholds has not earned the right to be believed at all, so it
    gets the ceiling and is effectively off.
    """
    height, width = frame.shape[:2]
    names = [output.name for output in sess.get_outputs()]
    outputs = dict(
        zip(names, sess.run(None, {meta["input"]["name"]: preprocessed(meta, frame)}), strict=True)
    )
    found = thresholds.decode(
        outputs[meta["outputs"]["boxes"]], outputs[meta["outputs"]["logits"]], width, height
    )

    kept = []
    for box in found:
        if not 0 <= box["class_index"] < len(meta["classes"]):
            continue
        name = meta["classes"][box["class_index"]]
        if box["score"] < meta["thresholds"].get(name, thresholds.CEILING):
            continue
        kept.append({**box, "class": name})
    return kept


def preprocessed(meta: dict, frame: np.ndarray) -> np.ndarray:
    """The model's input tensor, at whatever size play.json says the export used."""
    return thresholds.preprocess(frame, meta["input"]["size"])


def template_truth(frame: np.ndarray, *, find=vision.find_with_score) -> dict[str, dict | None]:
    """What the templates say about a frame: a box per template class, or None for that class.

    Every template class is a key even when nothing matched, because an absent box is the half
    of the truth that catches a false positive.
    """
    boxes = {box["class"]: box for box in prelabel.boxes_for(frame, find=find)}
    return {cls: boxes.get(cls) for cls in classes.TEMPLATE_CLASS.values()}


def compare(detections: list[dict], truth: dict[str, dict | None], iou_min: float = 0.5) -> dict:
    """One verdict per template class for one frame: tp, fn, fp or tn.

    A detection of the right class in the wrong place is an fn and not also an fp: the template
    box proves there is something of that class on the frame, so the model is wrong about where
    it is, not about whether it is there, and only the empty-frame case is the never-tap failure.
    """
    verdicts = {}
    for cls, real in truth.items():
        here = [box for box in detections if box["class"] == cls]
        if real is None:
            verdicts[cls] = "fp" if here else "tn"
            continue
        box = (real["x"], real["y"], real["w"], real["h"])
        hit = any(
            thresholds.iou(box, (det["x"], det["y"], det["w"], det["h"])) >= iou_min for det in here
        )
        verdicts[cls] = "tp" if hit else "fn"
    return verdicts


def report(rows: list[dict]) -> dict:
    """The verdicts of every frame summed per class, plus the never-tap count and the pass flag.

    A precision or a recall with nothing under it is 0.0, the way export.py reports one: a class
    the model never detected has not shown anything, and printing 1.0 there would read as perfect.
    """
    totals: dict[str, Counter[str]] = {}
    for row in rows:
        for cls, verdict in row.items():
            totals.setdefault(cls, Counter())[verdict] += 1

    per_class = {}
    for cls, count in totals.items():
        tp, fp, fn, tn = count["tp"], count["fp"], count["fn"], count["tn"]
        per_class[cls] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "tn": tn,
            "precision": round(tp / (tp + fp), 4) if tp + fp else 0.0,
            "recall": round(tp / (tp + fn), 4) if tp + fn else 0.0,
        }
    bad = sum(count["fp"] for cls, count in totals.items() if cls in classes.TAP_ANCHORS)
    return {"classes": per_class, "tap_anchor_false_positives": bad, "pass": bad == 0}


def _read_frame(path: Path) -> np.ndarray | None:
    """imdecode, not imread: OpenCV cannot read a non-ASCII path on Windows."""
    return cv2.imdecode(np.frombuffer(path.read_bytes(), np.uint8), cv2.IMREAD_COLOR)


def _pictures(folder: Path) -> list[Path]:
    return sorted(path for path in folder.rglob("*") if path.suffix.lower() in SUFFIXES)


def main(argv: list[str] | None = None, *, find=vision.find_with_score) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--root", type=Path, default=None, help="dataset root")
    ap.add_argument("--models", type=Path, default=None, help="folder holding play.onnx")
    ap.add_argument(
        "--frames",
        action="append",
        default=None,
        metavar="FOLDER",
        help="score the pictures under this folder; repeat for more",
    )
    ap.add_argument("--cuda", action="store_true", help="ask for the CUDA provider")
    args = ap.parse_args(argv)

    root = args.root if args.root is not None else dataset.default_root()
    models = args.models if args.models is not None else root / "models"
    if args.frames is not None:
        folders = [Path(name) for name in args.frames]
    else:
        folders = [root / "frames", settings.default_home() / "calibration" / "recordings"]
    folders = [folder for folder in folders if folder.is_dir()]
    if not folders:
        print("no frame folder to score: pass --frames")
        return 1
    if not (models / "play.onnx").is_file() or not (models / "play.json").is_file():
        print(f"no play.onnx and play.json under {models}: export a model first")
        return 1

    sess, meta = load_model(models, cuda=args.cuda)
    rows: list[dict] = []
    failures: list[dict] = []
    unverified: list[dict] = []
    scored = skipped = 0
    for folder in folders:
        for path in _pictures(folder):
            frame = _read_frame(path)
            if frame is None:
                skipped += 1
                continue
            height, width = frame.shape[:2]
            if (width, height) != (dataset.FRAME_W, dataset.FRAME_H):
                skipped += 1
                continue
            scored += 1
            # The name is relative to its folder: an absolute path carries the user profile.
            name = path.relative_to(folder).as_posix()
            found = detect(sess, meta, frame)
            verdicts = compare(found, template_truth(frame, find=find))
            rows.append(verdicts)
            failures.extend(
                {"file": name, "class": cls}
                for cls, verdict in sorted(verdicts.items())
                if verdict == "fp" and cls in classes.TAP_ANCHORS
            )
            unverified.extend(
                {"file": name, "class": box["class"]}
                for box in found
                if box["class"] in UNVERIFIABLE
            )

    summary = report(rows)
    summary |= {
        "generated": datetime.now(UTC).isoformat(timespec="seconds"),
        "training_set_hash": meta["training_set_hash"],
        "smoke": meta["smoke"],
        "frames": {"scored": scored, "skipped": skipped},
        "tap_anchor_failures": failures,
        "unverified_tap_anchor_detections": unverified,
    }
    models.mkdir(parents=True, exist_ok=True)
    (models / "score.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")

    print(f"{scored} frames scored, {skipped} skipped (unreadable or not 1600 x 900)")
    print(f"  {'class':<18} {'tp':>5} {'fp':>5} {'fn':>5} {'tn':>5} {'prec':>6} {'rec':>6}")
    for cls, count in summary["classes"].items():
        anchor = " tap anchor" if cls in classes.TAP_ANCHORS else ""
        print(
            f"  {cls:<18} {count['tp']:>5} {count['fp']:>5} {count['fn']:>5} {count['tn']:>5} "
            f"{count['precision']:>6.3f} {count['recall']:>6.3f}{anchor}"
        )
    for bad in failures:
        print(f"  never-tap failure: {bad['class']} on {bad['file']}, no template there")
    if unverified:
        print(
            f"{len(unverified)} detections of {', '.join(sorted(UNVERIFIABLE))}: these tap anchors "
            "have no template, so nothing here can call them right or wrong. Check them by hand."
        )
        for box in unverified:
            print(f"  unverified: {box['class']} on {box['file']}")
    if meta["smoke"]:
        print("WARNING: this model was trained on a smoke set. The report means nothing.")
    print(f"wrote {models / 'score.json'}")
    print(
        "PASS: no tap anchor detected where the templates see none" if summary["pass"] else "FAIL"
    )
    return 0 if summary["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
