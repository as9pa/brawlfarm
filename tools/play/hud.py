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
RING_RATIO = 1.9  # the base ring's radius in knob radii; the HUD scales as one piece
ORIGIN_BAND = (0.40, 0.58)  # the centre dot's radius, in knob radii
ORIGIN_VOTES = 24  # param2; the dot is small and translucent
ORIGIN_MIN_DIST = 20  # px between Hough centres
ORIGIN_REACH = 1.25  # ring radii from the knob; the knob is clamped to the ring, the rest is noise
ORIGIN_CLEAR = 0.5  # knob radii; a circle this close to the knob's centre is its own glyph
ORIGIN_DARKER = 12  # V levels the dot must be darker than the floor around it
ORIGIN_SURROUND = (1.35, 1.9)  # the annulus, in dot radii, that stands for the floor
KNOB_GUARD = 1.1  # knob radii around the knob left out of the surround
ORIGIN_FLOOR = 50  # px of surround needed before it may speak for the floor
ORIGIN_WINDOW = 40  # px; a window smaller than this on a side has no room for a joystick


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


def origin(frame: np.ndarray, box: tuple[int, int, int, int], knob: Found) -> Found | None:
    """The dot at the centre of the joystick, which is what a push is measured from.

    The ring itself was tried first and does not survive real footage: a fixed radius search
    found it in 3 percent of knob frames and a free one followed whatever band it was given,
    with a centre wrong on two frames of three read by eye. The small dark dot at the middle of
    the ring is a circle Hough does see, on 0.77 to 0.83 of the knob frames of a clean source.

    The dot is translucent and takes the colour of the floor under it, so it is recognised as
    darker than the floor around it and never by an absolute colour. A stick near its centre
    covers its own dot: that frame has no origin, and a caller that wanted a move vector gets
    nothing rather than a guess.
    """
    ring = RING_RATIO * knob.r
    reach = ORIGIN_REACH * ring + ORIGIN_SURROUND[1] * ORIGIN_BAND[1] * knob.r
    bx, by, bw, bh = box
    x0, y0 = max(bx, 0, int(knob.x - reach)), max(by, 0, int(knob.y - reach))
    x1 = min(bx + bw, frame.shape[1], int(knob.x + reach))
    y1 = min(by + bh, frame.shape[0], int(knob.y + reach))
    if x1 - x0 < ORIGIN_WINDOW or y1 - y0 < ORIGIN_WINDOW:
        return None

    crop = frame[y0:y1, x0:x1]
    circles = cv2.HoughCircles(
        cv2.medianBlur(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), BLUR),
        cv2.HOUGH_GRADIENT,
        dp=HOUGH_DP,
        minDist=ORIGIN_MIN_DIST,
        param1=HOUGH_EDGE,
        param2=ORIGIN_VOTES,
        minRadius=int(ORIGIN_BAND[0] * knob.r),
        maxRadius=int(ORIGIN_BAND[1] * knob.r) + 1,
    )
    if circles is None:
        return None
    # The surround is measured inside the window, never on a whole frame mask: this runs on
    # every frame of a source, and the floor a dot sits on is the floor right around it.
    value = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)[:, :, 2]
    ys, xs = np.mgrid[y0:y1, x0:x1]
    clear = (xs - knob.x) ** 2 + (ys - knob.y) ** 2 > (KNOB_GUARD * knob.r) ** 2
    for cx, cy, r in circles[0]:
        x, y = float(cx) + x0, float(cy) + y0
        away = math.hypot(x - knob.x, y - knob.y)
        if away > ORIGIN_REACH * ring or away < ORIGIN_CLEAR * knob.r:
            continue
        span = (xs - x) ** 2 + (ys - y) ** 2
        surround = (
            clear & (span > (ORIGIN_SURROUND[0] * r) ** 2) & (span < (ORIGIN_SURROUND[1] * r) ** 2)
        )
        if int(surround.sum()) < ORIGIN_FLOOR:
            continue
        inside = inner_hsv(frame, x, y, float(r))[2]
        if float(np.median(value[surround])) - inside >= ORIGIN_DARKER:
            return Found("origin", x, y, float(r), "dot")
    return None
