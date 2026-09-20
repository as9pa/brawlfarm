"""The mobile HUD reader: where the touch controls are on a frame, and whether a HUD is there.

Circles first, colour second. A colour mask on its own was tried in the spike and fails: an
arena floor that happens to be pink turns the attack mask into a single blob and swallows the
disc, so the attack button was found in 2 frames of 13. Every class is instead found by Hough
circles on the gray image, inside a search box and a radius band that are both relative to the
clip's content box, and the class verdict comes from the HSV inside the circle.

The state names are colours on purpose: what a gold super means is the policy's business, not
the reader's. Every number here is a calibration value measured on real footage; a synthetic
picture that does not trip them is the picture's fault.

Read only: nothing here downloads, taps or talks to adb.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass

import cv2
import numpy as np

from tools.play import dataset

SEARCH = {  # class: (u0, v0, u1, v1, r_min, r_max), radii as shares of the box height
    "attack": (0.80, 0.44, 1.00, 0.78, 0.042, 0.095),
    "super": (0.73, 0.69, 0.81, 0.78, 0.040, 0.090),
    "gadget": (0.82, 0.85, 0.90, 0.93, 0.038, 0.085),
    "hyper": (0.64, 0.85, 0.72, 0.93, 0.038, 0.085),
    "knob": (0.00, 0.55, 0.30, 1.00, 0.040, 0.095),
}
BLUR = 5
HOUGH_DP = 1.2
HOUGH_MIN_DIST = 0.05  # share of the box height
HOUGH_EDGE = 110  # param1
HOUGH_VOTES = 38  # param2
INNER = 0.62  # the colour is read inside this share of the radius
BASE_FREE = (1.3, 2.6, 26)  # knob radii from, to, and param2, when the base radius is unknown
BASE_FIXED = (0.95, 1.05, 22)  # shares of the known radius, and param2


@dataclass(frozen=True)
class Found:
    """One control read off a frame. x, y and r are frame pixels, not box shares."""

    cls: str
    x: float
    y: float
    r: float
    state: str


def frame_box(pad: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    """The content box of a frame that dataset.fit_frame padded by (left, top, right, bottom)."""
    left, top, right, bottom = pad
    return left, top, dataset.FRAME_W - left - right, dataset.FRAME_H - top - bottom


def _hue_mean(hues: np.ndarray) -> float:
    """Circular mean of an OpenCV hue channel, so 2 and 178 average to 0 and not to 90."""
    angles = np.exp(1j * hues.astype(np.float64) * np.pi / 90.0)
    return float(np.angle(np.mean(angles)) * 90.0 / np.pi % 180.0)


def inner_hsv(frame: np.ndarray, x: float, y: float, r: float) -> tuple[float, float, float]:
    """Hue, saturation and value inside INNER * r of (x, y), clipped to the frame.

    The hue is a circular mean because red wraps around 0; saturation and value are medians, so
    a highlight or a sliver of the rim cannot drag the reading.
    """
    height, width = frame.shape[:2]
    inner = max(1, int(round(r * INNER)))
    x0, y0 = max(0, int(round(x)) - inner), max(0, int(round(y)) - inner)
    x1, y1 = min(width, int(round(x)) + inner + 1), min(height, int(round(y)) + inner + 1)
    if x1 <= x0 or y1 <= y0:
        return 0.0, 0.0, 0.0
    ys, xs = np.mgrid[y0:y1, x0:x1]
    keep = (xs - x) ** 2 + (ys - y) ** 2 <= inner**2
    if not keep.any():
        return 0.0, 0.0, 0.0
    pixels = cv2.cvtColor(frame[y0:y1, x0:x1], cv2.COLOR_BGR2HSV)[keep]
    return (
        _hue_mean(pixels[:, 0]),
        float(np.median(pixels[:, 1])),
        float(np.median(pixels[:, 2])),
    )


def state_of(cls: str, h: float, s: float, v: float) -> str | None:
    """The first state of `cls` this colour passes, or None when it is not that class at all."""
    red = h >= 166 or h <= 17
    if cls == "attack":
        if red and s >= 120 and v >= 100:
            return "red"
        # the reloading disc keeps its hue and loses most of its saturation
        if red and 15 <= s < 120 and 90 <= v <= 180:
            return "dim"
    elif cls == "super":
        if 96 <= h <= 120 and s >= 110 and v >= 90:
            return "blue"
        if 4 <= h <= 32 and v >= 225:
            return "gold"
        if s <= 70 and v >= 235:
            return "white"
        if s <= 70 and 60 <= v <= 115:
            return "dark"
    elif cls == "gadget":
        if 40 <= h <= 90 and s >= 140 and v >= 110:
            return "green"
        if s <= 40 and 80 <= v <= 175:
            return "grey"
    elif cls == "hyper":
        if 120 <= h <= 150 and s >= 90 and v >= 80:
            return "purple"
    elif cls == "knob":
        if 96 <= h <= 120 and s >= 170 and v >= 130:
            return "blue"
    return None


def _circles(
    frame: np.ndarray,
    window: tuple[int, int, int, int],
    r_min: int,
    r_max: int,
    votes: int,
    min_dist: int,
) -> list[tuple[float, float, float]]:
    """Hough circles inside a window given as (x0, y0, x1, y1), as (x, y, r) in frame pixels.

    OpenCV returns them strongest first, and the caller keeps that order: the button is the
    loudest circle in its own search box.
    """
    height, width = frame.shape[:2]
    x0, y0 = max(0, window[0]), max(0, window[1])
    x1, y1 = min(width, window[2]), min(height, window[3])
    if x1 - x0 < 1 or y1 - y0 < 1 or r_max < 1:
        return []
    gray = cv2.cvtColor(frame[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
    circles = cv2.HoughCircles(
        cv2.medianBlur(gray, BLUR),
        cv2.HOUGH_GRADIENT,
        dp=HOUGH_DP,
        minDist=min_dist,
        param1=HOUGH_EDGE,
        param2=votes,
        minRadius=max(0, r_min),
        maxRadius=r_max,
    )
    if circles is None:
        return []
    return [(float(cx) + x0, float(cy) + y0, float(r)) for cx, cy, r in circles[0]]


def find(frame: np.ndarray, box: tuple[int, int, int, int]) -> dict[str, Found]:
    """Every control found in `box`, keyed by class. A class that finds nothing is absent."""
    bx, by, bw, bh = box
    min_dist = max(1, int(HOUGH_MIN_DIST * bh))
    found: dict[str, Found] = {}
    for cls, (u0, v0, u1, v1, r_lo, r_hi) in SEARCH.items():
        r_min, r_max = int(r_lo * bh), int(r_hi * bh)
        window = (
            max(0, bx + int(u0 * bw)),
            max(0, by + int(v0 * bh)),
            min(frame.shape[1], bx + int(u1 * bw)),
            min(frame.shape[0], by + int(v1 * bh)),
        )
        if window[2] - window[0] < 2 * r_min or window[3] - window[1] < 2 * r_min:
            continue
        for x, y, r in _circles(frame, window, r_min, r_max, HOUGH_VOTES, min_dist):
            state = state_of(cls, *inner_hsv(frame, x, y, r))
            if state is not None:
                found[cls] = Found(cls, x, y, r, state)
                break
    return found


def visible(found: Mapping[str, Found]) -> bool:
    """The mobile HUD verdict: the super disc plus one of the attack disc or the joystick knob.

    The super alone was perfect on the spike set, but the attack disc fires on 44 percent of
    emulator menu frames and the knob on 38 percent, so neither may stand alone.
    """
    return "super" in found and ("attack" in found or "knob" in found)


def base(
    frame: np.ndarray,
    box: tuple[int, int, int, int],
    knob: Found,
    radius: float | None = None,
) -> Found | None:
    """The joystick base ring around `knob`, or None when there is no ring holding it.

    The stick floats, so there is no rest position and the ring is found per frame. A free
    search finds one in most knob frames but its radius spreads from 0.094 to 0.193 of the box
    height, which is enough to turn a move vector the wrong way; so a caller that has learned
    the radius over a whole source passes it in and only the centre is searched for.
    """
    if radius is None:
        r_lo, r_hi, votes = BASE_FREE[0] * knob.r, BASE_FREE[1] * knob.r, BASE_FREE[2]
        reach = BASE_FREE[1] * knob.r
    else:
        r_lo, r_hi, votes = BASE_FIXED[0] * radius, BASE_FIXED[1] * radius, BASE_FIXED[2]
        reach = radius
    window = (
        int(knob.x - reach),
        int(knob.y - reach),
        int(knob.x + reach) + 1,
        int(knob.y + reach) + 1,
    )
    min_dist = max(1, int(HOUGH_MIN_DIST * box[3]))
    for x, y, r in _circles(frame, window, int(r_lo), int(r_hi), votes, min_dist):
        # the knob is always inside its own base, whatever else the window picked up
        if math.hypot(x - knob.x, y - knob.y) <= r:
            return Found("base", x, y, r, "ring")
    return None
