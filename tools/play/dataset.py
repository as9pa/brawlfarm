"""The dataset folder: where it lives, how a frame is shaped, hashed, deduped and indexed.

Every frame in the set is 1600 x 900 BGR JPEG, the size the farm loop and the templates already
assume. Sources that are not 16:9 are padded with black, never cropped, and the pad is kept in
the index so a label can be mapped back to the original picture. Nothing here downloads, taps or
talks to adb; the dataset root is outside the checkout so training data never enters git.
"""

from __future__ import annotations

import json
import re
from collections import deque
from collections.abc import Iterable, Sequence
from pathlib import Path

import cv2
import numpy as np

from brawlfarm import settings

FRAME_W, FRAME_H = 1600, 900
JPEG_QUALITY = 92
# A row or column is border when its brightest mean gray level over the sample stays below
# this. JPEG ringing and a video encoder both lift a true black bar off zero by a little.
BORDER_LEVEL = 12
SOURCE_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def default_root() -> Path:
    """`<home>/datasets/play`, so a test's isolated BRAWLFARM_HOME moves the whole set."""
    return settings.default_home() / "datasets" / "play"


def check_source(name: str) -> str:
    """A source name goes into paths and file names, so it may only be a plain word."""
    if not SOURCE_RE.fullmatch(name):
        raise ValueError(f"bad source name: {name!r}")
    return name


def _lit_range(means: np.ndarray) -> tuple[int, int] | None:
    """First and one-past-last index whose mean is above the border level, or None if none is."""
    lit = np.flatnonzero(means >= BORDER_LEVEL)
    if lit.size == 0:
        return None
    return int(lit[0]), int(lit[-1]) + 1


def content_box(frames: Sequence[np.ndarray]) -> tuple[int, int, int, int]:
    """The picture inside a source's constant black borders, as x, y, w, h in source pixels.

    A downloaded video often carries the game inside baked-in bars, which would shrink the game
    against the emulator's own frames once everything is fitted to 1600 x 900. The bars are a
    property of the source, so the measurement takes several frames and keeps the brightest mean
    per row and per column: a dark moment in one frame must not widen the border. Anything that
    looks unlike a letterbox, a border that would eat half a dimension, a set of frames that do
    not agree on their size, gives the whole frame back rather than a guess.
    """
    frames = list(frames)
    if not frames:
        raise ValueError("content_box needs at least one frame")
    height, width = frames[0].shape[:2]
    full = (0, 0, width, height)
    if any(frame.shape[:2] != (height, width) for frame in frames):
        return full
    rows = np.zeros(height, dtype=np.float32)
    cols = np.zeros(width, dtype=np.float32)
    for frame in frames:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
        rows = np.maximum(rows, gray.mean(axis=1))
        cols = np.maximum(cols, gray.mean(axis=0))
    vertical = _lit_range(rows)
    horizontal = _lit_range(cols)
    if vertical is None or horizontal is None:
        return full
    top, bottom = vertical
    left, right = horizontal
    if 2 * (right - left) < width or 2 * (bottom - top) < height:
        return full
    return left, top, right - left, bottom - top


def dhash(frame: np.ndarray) -> int:
    """64-bit difference hash: gray, 9 x 8, one bit per row-wise left < right comparison."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA)
    bits = small[:, :-1] < small[:, 1:]
    return int.from_bytes(np.packbits(bits).tobytes(), "big")


def hamming(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def fit_frame(frame: np.ndarray) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    """Pad to 16:9 with black, then scale to 1600 x 900. Returns the frame and its pad
    (left, top, right, bottom) in output pixels. The pad is rounded down on purpose: a row
    it claims is black really is black, even after the resize blends the seam."""
    h, w = frame.shape[:2]
    left = top = right = bottom = 0
    if w * FRAME_H < h * FRAME_W:  # taller than 16:9, so the sides get the black
        extra = round(h * FRAME_W / FRAME_H) - w
        left = extra // 2
        right = extra - left
    elif w * FRAME_H > h * FRAME_W:  # wider than 16:9, so the top and bottom do
        extra = round(w * FRAME_H / FRAME_W) - h
        top = extra // 2
        bottom = extra - top
    if left or top or right or bottom:
        frame = cv2.copyMakeBorder(
            frame, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(0, 0, 0)
        )
    padded_h, padded_w = frame.shape[:2]
    if (padded_w, padded_h) == (FRAME_W, FRAME_H):
        return frame, (left, top, right, bottom)
    interpolation = cv2.INTER_AREA if padded_w > FRAME_W else cv2.INTER_LINEAR
    scale = FRAME_W / padded_w
    out = cv2.resize(frame, (FRAME_W, FRAME_H), interpolation=interpolation)
    pad = (int(left * scale), int(top * scale), int(right * scale), int(bottom * scale))
    return out, pad


class Deduper:
    """Keeps a frame out of the set when it repeats one we have already kept.

    Two filters, because a long clip needs both: every hash ever seen is remembered exactly,
    which catches a menu the video returns to minutes later, and the last `window` kept hashes
    are compared by distance, which catches the near-identical run of frames a static screen
    produces without making far-apart frames collide by accident.
    """

    def __init__(self, max_distance: int = 4, window: int = 64, seen: Iterable[int] = ()) -> None:
        seeds = list(seen)
        self.max_distance = max_distance
        self._seen: set[int] = set(seeds)
        self._recent: deque[int] = deque(seeds, maxlen=window)

    def is_new(self, h: int) -> bool:
        if h in self._seen:
            return False
        if any(hamming(h, kept) <= self.max_distance for kept in self._recent):
            return False
        self._seen.add(h)
        self._recent.append(h)
        return True


class Index:
    """`index.jsonl` at the dataset root: one line per kept frame, appended as they are saved."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.path = self.root / "index.jsonl"
        self._hashes: list[int] = []
        self._sources: set[str] = set()
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                self._hashes.append(int(row["hash"], 16))
                self._sources.add(row["source"])

    def hashes(self) -> list[int]:
        return list(self._hashes)

    def has_source(self, source: str) -> bool:
        return source in self._sources

    def add(
        self,
        *,
        file: str,
        source: str,
        kind: str,
        t: float | None,
        hash_: int,
        teams_left: float,
        pad: tuple[int, int, int, int],
        crop: tuple[int, int, int, int] | None = None,
    ) -> None:
        row = {
            "file": file,
            "source": source,
            "kind": kind,
            "t": t,
            "hash": f"{hash_:016x}",
            "teams_left": teams_left,
            "pad": list(pad),
            "crop": None if crop is None else list(crop),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Opened per line so an interrupted extraction still leaves a complete index behind.
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
        self._hashes.append(hash_)
        self._sources.add(source)


def save_frame(root: Path, source: str, n: int, frame: np.ndarray) -> str:
    """Write one JPEG and return its path relative to the root, with forward slashes."""
    rel = f"frames/{source}/{source}-{n:06d}.jpg"
    path = Path(root) / rel
    if path.exists():
        # An index line already points at this name; overwriting it would silently replace a
        # labelled frame with a different picture.
        raise FileExistsError(rel)
    path.parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY])
    if not ok:
        raise RuntimeError(f"could not encode {rel}")
    # imencode plus write_bytes, not imwrite: OpenCV cannot write a non-ASCII path on Windows.
    path.write_bytes(buf.tobytes())
    return rel
