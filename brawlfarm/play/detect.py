"""The ONNX contract at run time: play.onnx and play.json turned into boxes.

This is the worker's own copy of the pre-processing and decoding in tools/play/thresholds.py,
kept here because the tools are not in the wheel, and pinned to them by the parity test in
tests/test_play_detect.py. Change one side and that test fails, which is the point. Spec:
docs/superpowers/specs/2026-09-18-play-mode.md section 3.

Nothing here can send input, and onnxruntime and cv2 are imported inside the bodies that need
them, so a worker with shadow mode off pays nothing for this module existing.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from brawlfarm.core import config

log = logging.getLogger("brawlfarm.play.detect")

MODEL_FILE = "play.onnx"
META_FILE = "play.json"
# the ImageNet statistics RF-DETR normalises with, in RGB order; tools/play/thresholds.py
MEAN = (0.485, 0.456, 0.406)
STD = (0.229, 0.224, 0.225)


@dataclass(frozen=True)
class Box:
    """One detection in the pixels of the frame that was handed to ``detect()``."""

    cls: str
    score: float
    x: float  # left
    y: float  # top
    w: float
    h: float


class ModelMissing(Exception):
    """play.onnx or play.json is not there. The normal case until the model ships."""


class ModelInvalid(Exception):
    """The files are there and cannot be trusted. A threshold is never invented."""


def models_dir() -> Path:
    """The folder a play model lives in. Read at call time: set_home() moves it."""
    return config.HOME_DIR / "models"


def preprocess(bgr: np.ndarray, size: int) -> np.ndarray:
    """A BGR frame as the model's input: RGB, size x size, normalised, NCHW, batch of one.

    The resize is a plain squash with no letterbox, which is what the library does, so a box
    decoded from the output maps back to the original picture by scaling alone.
    """
    import cv2  # inside the body: nothing but the detector pays for OpenCV

    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    small = cv2.resize(rgb, (size, size), interpolation=cv2.INTER_LINEAR)
    scaled = small.astype(np.float32) / 255.0
    scaled = (scaled - np.array(MEAN, dtype=np.float32)) / np.array(STD, dtype=np.float32)
    return np.ascontiguousarray(scaled.transpose(2, 0, 1)[None], dtype=np.float32)


def decode(
    dets: np.ndarray,
    logits: np.ndarray,
    width: int,
    height: int,
    classes: Sequence[str],
    thresholds: Mapping[str, float],
) -> list[Box]:
    """RF-DETR's two outputs turned into pixel boxes, highest score first.

    ``dets`` is (queries, 4) as centre x, centre y, width, height in 0..1, ``logits`` is
    (queries, classes + 1) of unnormalised scores; a leading batch dimension of one is accepted
    for both. Column k is class index k and the last column is the background the library never
    reports. A box is kept only at or above its own class's threshold, which every class has:
    ``Detector.load`` refuses a model whose play.json is missing one.
    """
    boxes = np.asarray(dets, dtype=np.float64)
    boxes = boxes.reshape(-1, boxes.shape[-1])
    scores = np.asarray(logits, dtype=np.float64)
    scores = scores.reshape(-1, scores.shape[-1])[:, :-1]
    scores = 1.0 / (1.0 + np.exp(-scores))

    bars = np.array([thresholds[name] for name in classes], dtype=np.float64)
    found = []
    for query, cls in zip(*np.nonzero(scores >= bars), strict=True):
        cx, cy, w, h = boxes[query]
        found.append(
            Box(
                cls=classes[cls],
                score=float(scores[query, cls]),
                x=float((cx - w / 2) * width),
                y=float((cy - h / 2) * height),
                w=float(w * width),
                h=float(h * height),
            )
        )
    found.sort(key=lambda box: box.score, reverse=True)
    return found


def _default_session(path: Path) -> Any:
    """An onnxruntime session on the GPU if this build has one, the CPU otherwise."""
    import onnxruntime as ort  # heavy, and only shadow mode pays for it

    providers = ["CPUExecutionProvider"]
    if "CUDAExecutionProvider" in ort.get_available_providers():
        if hasattr(ort, "preload_dlls"):
            try:
                ort.preload_dlls()
            except Exception as exc:  # an old or CPU-only build: say so and carry on
                log.info("preload_dlls failed (%s); asking for CUDA anyway", exc)
        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
    return ort.InferenceSession(str(path), providers=providers)


def _object(meta: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    """One of play.json's sub-objects, or ModelInvalid naming it."""
    section = meta.get(key)
    if not isinstance(section, Mapping):
        raise ModelInvalid(f"{META_FILE}: {key} is not an object")
    return section


def _text(section: Mapping[str, Any], key: str) -> str:
    value = section.get(key)
    if not isinstance(value, str) or not value:
        raise ModelInvalid(f"{META_FILE}: {key} is not a name")
    return value


def _classes(meta: Mapping[str, Any]) -> tuple[str, ...]:
    names = meta.get("classes")
    if not isinstance(names, list) or not names or not all(isinstance(n, str) for n in names):
        raise ModelInvalid(f"{META_FILE}: classes is not a non-empty list of names")
    if len(set(names)) != len(names):
        raise ModelInvalid(f"{META_FILE}: classes repeats a name")
    return tuple(names)


def _thresholds(meta: Mapping[str, Any], classes: Sequence[str]) -> dict[str, float]:
    """One threshold per class. A class without one makes the model invalid: a detector that
    believed an unthresholded class would tap on whatever it hallucinated there."""
    given = _object(meta, "thresholds")
    bars = {}
    for name in classes:
        bar = given.get(name)
        if isinstance(bar, bool) or not isinstance(bar, (int, float)) or not 0 < bar <= 1:
            raise ModelInvalid(f"{META_FILE}: threshold for {name} is not a number in (0, 1]")
        bars[name] = float(bar)
    return bars


def _size(section: Mapping[str, Any]) -> int:
    size = section.get("size")
    if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
        raise ModelInvalid(f"{META_FILE}: input.size is not a positive whole number")
    return size


class Detector:
    """One loaded model, ready to be asked about a frame. Raises ModelInvalid, never guesses.

    ``smoke`` comes through from play.json because a smoke model is allowed to run in shadow
    mode and is never allowed to drive; the caller that drives has to check it.
    """

    def __init__(
        self,
        session: Any,
        *,
        name: str,
        smoke: bool,
        training_set_hash: str,
        classes: tuple[str, ...],
        thresholds: Mapping[str, float],
        size: int,
        input_name: str,
        boxes_name: str,
        logits_name: str,
    ) -> None:
        self._session = session
        self.name = name
        self.smoke = smoke
        self.training_set_hash = training_set_hash
        self.classes = classes
        self.size = size
        self._thresholds = dict(thresholds)
        self._input = input_name
        self._outputs = [boxes_name, logits_name]
        # what the session really got, not what was asked for: onnxruntime falls back to the
        # CPU without a word when the CUDA libraries are missing.
        self.provider = session.get_providers()[0]

    @classmethod
    def load(
        cls,
        folder: Path | None = None,
        *,
        session_factory: Callable[[Path], Any] | None = None,
    ) -> Detector:
        """The model in ``folder`` (the models folder by default), or ModelMissing."""
        folder = Path(folder) if folder is not None else models_dir()
        model, meta_file = folder / MODEL_FILE, folder / META_FILE
        if not model.is_file() or not meta_file.is_file():
            raise ModelMissing(f"no {MODEL_FILE} and {META_FILE} in {folder}")

        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
        except ValueError as exc:
            raise ModelInvalid(f"{META_FILE} is not JSON: {exc}") from exc
        if not isinstance(meta, Mapping):
            raise ModelInvalid(f"{META_FILE} is not an object")

        classes = _classes(meta)
        thresholds = _thresholds(meta, classes)
        source = _object(meta, "input")
        outputs = _object(meta, "outputs")
        detector = cls(
            (session_factory or _default_session)(model),
            name=str(meta.get("model", "")),
            smoke=bool(meta.get("smoke", False)),
            training_set_hash=str(meta.get("training_set_hash", "")),
            classes=classes,
            thresholds=thresholds,
            size=_size(source),
            input_name=_text(source, "name"),
            boxes_name=_text(outputs, "boxes"),
            logits_name=_text(outputs, "logits"),
        )
        log.info("play detector: %s on %s", detector.name, detector.provider)
        return detector

    def detect(self, frame: np.ndarray) -> list[Box]:
        """One frame through the model: the boxes at or above their own class's threshold.

        The two outputs are asked for by the names play.json recorded, so an export that
        reordered them cannot silently swap the boxes with the logits.
        """
        height, width = frame.shape[:2]
        dets, logits = self._session.run(self._outputs, {self._input: preprocess(frame, self.size)})
        columns = np.asarray(logits).shape[-1]
        if columns != len(self.classes) + 1:
            raise ModelInvalid(
                f"{self._outputs[1]} has {columns} columns, "
                f"expected {len(self.classes) + 1} for {len(self.classes)} classes"
            )
        return decode(dets, logits, width, height, self.classes, self._thresholds)
