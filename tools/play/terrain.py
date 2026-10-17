"""Terrain auto-labels: bush and power cube boxes from colour masks on an HSV frame.

Bushes are the saturated teal or blue leafy patches; a power cube is a small green body carrying
a yellow lightning glyph. Pixels inside a zone mask (the HUD and any per-source exclusion) are
cleared before anything is measured, so no box grows out of a button or a facecam.
"""

from __future__ import annotations

import cv2
import numpy as np

# Teal (pink arena) and saturated blue (graveyard) leaves. Water and stone are less saturated.
BUSH_LO = (86, 195, 70)
BUSH_HI = (107, 255, 240)
BUSH_MIN_AREA = 1500
BUSH_MIN_SIDE = 30
BUSH_MIN_FILL = 0.45
CUBE_GREEN_LO = (48, 70, 90)
CUBE_GREEN_HI = (78, 220, 255)
CUBE_YELLOW_LO = (20, 100, 165)
CUBE_YELLOW_HI = (34, 230, 255)
WHITE_LO = (0, 0, 215)
WHITE_HI = (180, 50, 255)
CUBE_MIN_SIDE = 22
CUBE_MAX_SIDE = 68


def _kernel(n: int) -> np.ndarray:
    return cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (n, n))


def _in_range(hsv: np.ndarray, lo: tuple[int, int, int], hi: tuple[int, int, int]) -> np.ndarray:
    return cv2.inRange(hsv, np.array(lo, np.uint8), np.array(hi, np.uint8))


def _tight_box(mask: np.ndarray) -> tuple[int, int, int, int]:
    ys, xs = np.nonzero(mask)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    return int(x0), int(y0), int(x1 - x0 + 1), int(y1 - y0 + 1)


def _touches_edge(x: int, y: int, w: int, h: int, width: int, height: int) -> bool:
    """Whether a box runs to the border of a width x height window."""
    return x == 0 or y == 0 or x + w >= width or y + h >= height


def _overlaps(a: dict, b: dict) -> bool:
    return (
        a["x"] < b["x"] + b["w"]
        and b["x"] < a["x"] + a["w"]
        and a["y"] < b["y"] + b["h"]
        and b["y"] < a["y"] + a["h"]
    )


def is_game_frame(hsv: np.ndarray) -> bool:
    """Menus and loading screens have no game floor. Cheap test on the colour spread."""
    return float((hsv[..., 1] > 40).mean()) > 0.5


def bush_boxes(hsv: np.ndarray, zones: np.ndarray) -> list[dict]:
    """One edge-tight box per leafy patch outside the zones."""
    raw = _in_range(hsv, BUSH_LO, BUSH_HI)
    raw[zones] = 0
    # Leaves leave dark gaps; close them, then drop speckle.
    closed = cv2.morphologyEx(raw, cv2.MORPH_CLOSE, _kernel(9))
    opened = cv2.morphologyEx(closed, cv2.MORPH_OPEN, _kernel(7))
    n, lab, st, _ = cv2.connectedComponentsWithStats(opened, 8)
    boxes = []
    for i in range(1, n):
        _, _, w, h, a = st[i]
        if a < BUSH_MIN_AREA or w < BUSH_MIN_SIDE or h < BUSH_MIN_SIDE:
            continue
        comp = (lab == i).astype(np.uint8)
        # Real bushes are leafy, so the raw mask is not too sparse inside the closed component.
        fill = float(raw[lab == i].mean()) / 255.0
        if fill < BUSH_MIN_FILL:
            continue
        # A solid round blue HUD disc is very compact; bushes rarely are.
        cnts, _ = cv2.findContours(comp, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        per = sum(cv2.arcLength(c, True) for c in cnts)
        circ = 4 * np.pi * a / (per * per + 1e-6)
        if circ > 0.8 and a < 40000:
            continue
        # Tight box from the raw (unclosed) pixels inside the component.
        x, y, bw, bh = _tight_box(cv2.bitwise_and(raw, raw, mask=comp))
        score = round(min(1.0, 0.5 + 0.5 * fill), 3)
        boxes.append({"class": "bush", "x": x, "y": y, "w": bw, "h": bh, "score": score})
    return boxes


def power_cube_boxes(hsv: np.ndarray, zones: np.ndarray) -> list[dict]:
    """One box per green cube body carrying a yellow glyph outside the zones.

    Gas, heal pads and the gadget button are green without yellow; the power-level icon above a
    name is a small green diamond with a glyph, followed by a white digit.
    """
    h_img, w_img = hsv.shape[:2]
    green = _in_range(hsv, CUBE_GREEN_LO, CUBE_GREEN_HI)
    yellow = _in_range(hsv, CUBE_YELLOW_LO, CUBE_YELLOW_HI)
    white = _in_range(hsv, WHITE_LO, WHITE_HI)
    yellow[zones] = 0
    n, lab, st, _ = cv2.connectedComponentsWithStats(yellow, 8)
    boxes = []
    for i in range(1, n):
        x, y, w, h, a = st[i]
        if a < 8 or a > 400 or w > 30 or h > 35:
            continue
        x0, y0 = max(0, x - 35), max(0, y - 35)
        x1, y1 = min(w_img, x + w + 35), min(h_img, y + h + 35)
        win_w, win_h = x1 - x0, y1 - y0
        g = green[y0:y1, x0:x1]
        yl = (lab[y0:y1, x0:x1] == i).astype(np.uint8) * 255
        # The body is the green blob touching the glyph, or a pixel or two off it (dark seam).
        gc = cv2.morphologyEx(g, cv2.MORPH_CLOSE, _kernel(3))
        _, ll, ss, _ = cv2.connectedComponentsWithStats(gc, 8)
        ring = cv2.dilate(yl, _kernel(11)) > 0
        ids = np.unique(ll[ring])
        ids = ids[ids > 0]
        # The glyph can split the body into faces; take every blob touching it, minus blobs that
        # run to the window edge (green bled into gas, grass, a button or a brawler).
        keep = [int(j) for j in ids if not _touches_edge(*ss[j, :4], win_w, win_h)]
        if not keep:
            continue
        comp = (np.isin(ll, keep) & (g > 0)) | (yl > 0)
        bx, by, bw, bh = _tight_box(comp)
        ba = int(comp.sum())
        g_px = int(np.count_nonzero(g[comp]))
        # Size and shape of a cube; anything touching the window edge bled into gas or a strip.
        if not (
            CUBE_MIN_SIDE <= bw <= CUBE_MAX_SIDE
            and CUBE_MIN_SIDE <= bh <= CUBE_MAX_SIDE
            and 0.5 <= bw / bh <= 2.0
        ):
            continue
        if _touches_edge(bx, by, bw, bh, win_w, win_h):
            continue
        if g_px < 300 or g_px < 2.5 * a or ba < 0.5 * bw * bh:
            continue
        ax, ay = int(x0 + bx), int(y0 + by)
        # Power-level icon: a white digit sits right next to it.
        sx0, sx1 = ax + bw + 1, min(w_img, ax + bw + 28)
        sy0, sy1 = ay + bh // 6, ay + bh - bh // 6
        wpx = int(np.count_nonzero(white[sy0:sy1, sx0:sx1])) if sx1 > sx0 else 0
        if wpx > 40 and bw < 40:
            continue
        score = round(min(1.0, 0.5 + g_px / 2000.0), 3)
        boxes.append({"class": "power_cube", "x": ax, "y": ay, "w": bw, "h": bh, "score": score})
    # One glyph can split into two yellow pieces; keep one box per cube.
    boxes.sort(key=lambda b: -b["w"] * b["h"])
    kept: list[dict] = []
    for box in boxes:
        if not any(_overlaps(box, other) for other in kept):
            kept.append(box)
    return kept


def terrain_boxes(hsv: np.ndarray, zones: np.ndarray) -> list[dict]:
    """Bush boxes, then power cube boxes."""
    return bush_boxes(hsv, zones) + power_cube_boxes(hsv, zones)
