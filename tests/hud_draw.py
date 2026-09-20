"""Draws a synthetic mobile HUD, for the tests of the HUD reader and of what reads it.

Not a test module: `tests` is a package, so the action tests import `draw_hud` from here. The
picture only has to trip the real detector, so each disc is drawn in the middle of its class
colour test with a dark rim to give Hough a clean edge, on a noise floor blurred until it holds
no crisp arc of its own. Every circle is anti-aliased: a staircased rim scatters the gradient
directions Hough votes along, and a real button edge is smooth anyway. Nothing here reads the
owner's data home or a real frame.
"""

from __future__ import annotations

import cv2
import numpy as np

from tools.play import dataset

# The pinned buttons sit at fixed (u, v) shares of the content box, well inside their search
# boxes. The two spike sources agreed on these anchors to 0.023 in u and 0.016 in v.
SUPER_AT = (0.77, 0.735)
GADGET_AT = (0.86, 0.89)
# Disc radius per class, as a share of the box height. Mid band where the search box has room
# for a whole disc; near the bottom of the band for the super, the gadget and the hyper, whose
# boxes are barely 0.09 of the box high and would otherwise cut the circle in half.
DISC_R = {"attack": 0.065, "super": 0.041, "gadget": 0.041, "hyper": 0.041, "knob": 0.065}
BASE_R = 0.149  # the median joystick base radius measured in the spike
RIM = 3  # thickness of the dark rim around a disc, and of the base ring
RIM_GRAY = 20
BASE_GRAY = 170
FLOOR_LO, FLOOR_HI = 60, 110  # the arena floor is a mid gray, never black and never blown out
FLOOR_BLUR = 9
# HSV in the middle of each state's test in hud.state_of, converted to BGR when drawn.
COLOURS = {
    ("attack", "red"): (0, 210, 220),
    ("attack", "dim"): (0, 60, 130),
    ("super", "blue"): (108, 200, 200),
    ("super", "gold"): (18, 180, 245),
    ("super", "white"): (0, 10, 250),
    ("super", "dark"): (0, 10, 90),
    ("gadget", "green"): (60, 200, 160),
    ("gadget", "grey"): (0, 20, 130),
    ("hyper", "purple"): (135, 180, 160),
    ("knob", "blue"): (108, 220, 200),
}


def bgr(h: int, s: int, v: int) -> tuple[int, int, int]:
    """One OpenCV HSV triple as the BGR triple cv2.circle wants."""
    pixel = cv2.cvtColor(np.uint8([[[h, s, v]]]), cv2.COLOR_HSV2BGR)
    return tuple(int(c) for c in pixel[0, 0])


def _point(box: tuple[int, int, int, int], at: tuple[float, float]) -> tuple[int, int]:
    x, y, w, h = box
    return int(round(x + at[0] * w)), int(round(y + at[1] * h))


def _floor(w: int, h: int, seed: int, tint: tuple[int, int] | None) -> np.ndarray:
    """A blurred gray noise floor, optionally tinted to an arena colour given as (hue, sat)."""
    rng = np.random.default_rng(seed)
    noise = rng.integers(FLOOR_LO, FLOOR_HI + 1, size=(h, w), dtype=np.int16).astype(np.uint8)
    noise = cv2.GaussianBlur(noise, (FLOOR_BLUR, FLOOR_BLUR), 0)
    if tint is None:
        return np.dstack([noise, noise, noise])
    hue = np.full_like(noise, tint[0])
    sat = np.full_like(noise, tint[1])
    return cv2.cvtColor(np.dstack([hue, sat, noise]), cv2.COLOR_HSV2BGR)


def _disc(
    frame: np.ndarray, box: tuple[int, int, int, int], at: tuple[float, float], cls: str, state: str
) -> None:
    centre = _point(box, at)
    radius = int(round(DISC_R[cls] * box[3]))
    cv2.circle(frame, centre, radius, bgr(*COLOURS[cls, state]), -1, cv2.LINE_AA)
    cv2.circle(frame, centre, radius, (RIM_GRAY,) * 3, RIM, cv2.LINE_AA)


def draw_hud(
    box: tuple[int, int, int, int] = (140, 80, 1316, 736),
    *,
    attack: tuple[float, float] | None = (0.92, 0.62),
    super_state: str | None = "blue",
    knob: tuple[float, float] | None = (0.12, 0.80),
    base: tuple[float, float] | None = (0.10, 0.78),
    gadget: bool = True,
    seed: int = 0,
    floor_tint: tuple[int, int] | None = None,
) -> np.ndarray:
    """A 1600 x 900 BGR frame with a HUD drawn inside `box`; None leaves that element out.

    Positions are (u, v) shares of the box, the coordinates the detector works in. The super
    and the gadget are pinned, so they take a state instead of a position.
    """
    x, y, w, h = box
    frame = np.zeros((dataset.FRAME_H, dataset.FRAME_W, 3), np.uint8)
    frame[y : y + h, x : x + w] = _floor(w, h, seed, floor_tint)
    if base is not None:
        centre, ring = _point(box, base), int(round(BASE_R * h))
        cv2.circle(frame, centre, ring, (BASE_GRAY,) * 3, RIM, cv2.LINE_AA)
    if attack is not None:
        _disc(frame, box, attack, "attack", "red")
    if super_state is not None:
        _disc(frame, box, SUPER_AT, "super", super_state)
    if gadget:
        _disc(frame, box, GADGET_AT, "gadget", "green")
    if knob is not None:
        _disc(frame, box, knob, "knob", "blue")
    return frame
