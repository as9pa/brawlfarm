"""HUD zones and per-source exclusions: the parts of a frame where no auto-label may land.

HUD shapes are measured on an unpadded 1600 x 900 game picture and moved into the picture part
of a padded frame, so a source with black bars still masks its own buttons. Exclusions such as a
facecam are per source, live in `exclusions.json` at the dataset root, and adding a source is
one line there.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import cv2
import numpy as np

from tools.play import dataset

Rect = tuple[int, int, int, int]  # x0, y0, x1, y1, end exclusive

HUD_RECTS: tuple[Rect, ...] = (
    (0, 0, 470, 225),  # teams or brawlers left, and the player cards
    (1344, 648, 1600, 900),  # attack and gadget buttons
    (0, 820, 200, 900),  # joystick corner
)
HUD_CIRCLES: tuple[tuple[int, int, int], ...] = ((1228, 655, 66),)  # super button: cx, cy, r
# A box with at least this share of its area inside a zone is dropped.
ZONE_DROP = 0.5
EXCLUSIONS_FILE = "exclusions.json"


def zone_mask(pad: Sequence[int] = (0, 0, 0, 0), extra: Sequence[Rect] = ()) -> np.ndarray:
    """A (FRAME_H, FRAME_W) bool mask, True on the HUD and on every extra rectangle.

    `pad` is (left, top, right, bottom) black border in frame pixels, so the HUD shapes are
    scaled into the picture between the bars. `extra` rectangles are already frame pixels: they
    are drawn as given and clipped to the frame.
    """
    left, top, right, bottom = (int(v) for v in pad)
    sx = (dataset.FRAME_W - left - right) / dataset.FRAME_W
    sy = (dataset.FRAME_H - top - bottom) / dataset.FRAME_H
    canvas = np.zeros((dataset.FRAME_H, dataset.FRAME_W), dtype=np.uint8)
    for x0, y0, x1, y1 in HUD_RECTS:
        canvas[
            round(top + y0 * sy) : round(top + y1 * sy),
            round(left + x0 * sx) : round(left + x1 * sx),
        ] = 1
    for cx, cy, r in HUD_CIRCLES:
        centre = (round(left + cx * sx), round(top + cy * sy))
        cv2.circle(canvas, centre, round(r * min(sx, sy)), 1, -1)
    for rect in extra:
        x0, y0, x1, y1 = (int(v) for v in rect)
        canvas[
            max(0, y0) : min(dataset.FRAME_H, y1),
            max(0, x0) : min(dataset.FRAME_W, x1),
        ] = 1
    return canvas.astype(bool)


def in_zone(mask: np.ndarray, x: float, y: float) -> bool:
    """Whether a point is inside a zone; a point off the frame is read at the nearest edge."""
    height, width = mask.shape
    col = min(max(int(x), 0), width - 1)
    row = min(max(int(y), 0), height - 1)
    return bool(mask[row, col])


def inside_fraction(mask: np.ndarray, box: dict) -> float:
    """The share of a box's on-frame area that lies inside a zone, 0.0 for a box off the frame."""
    height, width = mask.shape
    x0 = max(0, int(box["x"]))
    y0 = max(0, int(box["y"]))
    x1 = min(width, int(box["x"]) + int(box["w"]))
    y1 = min(height, int(box["y"]) + int(box["h"]))
    if x1 <= x0 or y1 <= y0:
        return 0.0
    return float(mask[y0:y1, x0:x1].mean())


def drop_in_zones(boxes: list[dict], mask: np.ndarray, limit: float = ZONE_DROP) -> list[dict]:
    """The boxes with less than `limit` of their area in a zone, in their original order."""
    return [box for box in boxes if inside_fraction(mask, box) < limit]


def load_exclusions(path: Path) -> dict[str, list[Rect]]:
    """Per-source extra rectangles from `exclusions.json`; a missing file means none.

    The file maps a source name to a list of [x0, y0, x1, y1] frame-pixel rectangles. Anything
    else is refused with a ValueError rather than skipped, so a typo never silently unmasks a
    facecam.
    """
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} must map source names to rectangle lists")
    out: dict[str, list[Rect]] = {}
    for key, rects in data.items():
        source = dataset.check_source(key)
        if not isinstance(rects, list):
            raise ValueError(f"exclusions for {source} must be a list of rectangles")
        parsed: list[Rect] = []
        for rect in rects:
            if not (
                isinstance(rect, list)
                and len(rect) == 4
                and all(type(v) is int for v in rect)  # a JSON true is not a pixel
                and 0 <= rect[0] < rect[2] <= dataset.FRAME_W
                and 0 <= rect[1] < rect[3] <= dataset.FRAME_H
            ):
                raise ValueError(f"bad exclusion rectangle for {source}: {rect!r}")
            parsed.append((rect[0], rect[1], rect[2], rect[3]))
        out[source] = parsed
    return out
