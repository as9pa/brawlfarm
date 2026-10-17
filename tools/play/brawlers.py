"""Brawler auto-labels: anchors from one OCR pass and the health bar under each anchor.

An anchor is the HP number over a brawler: a 3 to 5 digit OCR box of normal height. Big
floating damage numbers are rejected by their font height unless a name sits right above them,
and a name with no number under it still anchors a bar where the number would be. Anchors in a
zone mask (the HUD and any per-source exclusion) are dropped. OCR text is only read here, never
kept: an anchor carries geometry and nothing else.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np

DEFAULT_BW = 92.0  # bar width when no bar is found under the anchor


@dataclass
class Anchor:
    """An HP number box, or the stand-in under a name whose number was not read."""

    x0: float
    y0: float
    x1: float
    y1: float
    named: bool = False
    name_y0: float | None = None
    from_name: bool = False

    @property
    def cx(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def h(self) -> float:
        return self.y1 - self.y0


def _at(zones: np.ndarray, x: float, y: float) -> bool:
    """Whether a point is inside a zone; a point off the frame is read at the nearest edge."""
    height, width = zones.shape
    col = min(max(int(x), 0), width - 1)
    row = min(max(int(y), 0), height - 1)
    return bool(zones[row, col])


def anchors_from_ocr(result: list | None, zones: np.ndarray) -> tuple[list[Anchor], bool]:
    """HP-number anchors from one RapidOCR result, and whether the frame is solo showdown.

    `result` is RapidOCR's list of [four (x, y) points, text, score], or None when nothing was
    read. Solo means a "Brawlers left" counter is on screen.
    """
    items = []
    for box, text, _score in result or []:
        xs = [float(p[0]) for p in box]
        ys = [float(p[1]) for p in box]
        items.append((min(xs), min(ys), max(xs), max(ys), text))

    nums: list[Anchor] = []
    names: list[tuple[float, float, float, float]] = []
    for x0, y0, x1, y1, text in items:
        h = y1 - y0
        digits = re.sub(r"\D", "", text)
        if digits and len(digits) >= 0.6 * len(text.replace(" ", "")):
            if 3 <= len(digits) <= 5 and 10 <= h <= 40:
                nums.append(Anchor(x0, y0, x1, y1))
        elif sum(c.isalpha() for c in text) >= 2 and h <= 34:
            names.append((x0, y0, x1, y1))

    # A name whose number was not read (merged with damage numbers, under effects) still
    # anchors the bar where the number would sit.
    digit_boxes = [((x0 + x1) / 2, y0) for x0, y0, x1, y1, text in items if re.search(r"\d", text)]
    for x0, _y0, x1, y1 in names:
        cx = (x0 + x1) / 2
        if any(abs(dx - cx) < 60 and y1 - 12 <= dy0 <= y1 + 34 for dx, dy0 in digit_boxes):
            continue
        nums.append(Anchor(cx - 22, y1, cx + 22, y1 + 22, from_name=True))

    out: list[Anchor] = []
    for n in nums:
        above = [
            m
            for m in names
            if n.y0 - 34 <= m[3] <= n.y0 + 10 and abs((m[0] + m[2]) / 2 - n.cx) < 60
        ]
        if above:
            n.named = True
            n.name_y0 = max(above, key=lambda m: m[3])[1]
        if n.from_name and not n.named:
            continue
        if n.h > 30 and not n.named:  # floating damage number
            continue
        if _at(zones, n.cx, n.y0 if n.from_name else n.y1):
            continue
        out.append(n)

    # A number sitting on top of another brawler's name and HP number is a floating damage number.
    out = [
        n
        for n in out
        if not any(
            o is not n
            and o.named
            and o.name_y0 is not None
            and abs(o.cx - n.cx) < 60
            and 0 < o.y1 - n.y1 < 90
            and o.name_y0 >= n.y1 - 6
            for o in out
        )
    ]
    solo = any("rawlers" in text for *_, text in items)  # "Brawlers left": solo showdown
    return out, solo


def fill_masks(hsv: np.ndarray) -> dict[str, np.ndarray]:
    """Bool masks of the three health bar fill colours on an OpenCV HSV frame."""
    h = hsv[..., 0].astype(int)
    s = hsv[..., 1].astype(int)
    v = hsv[..., 2].astype(int)
    return {
        "green": (h >= 22) & (h <= 85) & (s >= 100) & (v >= 150),  # self: green, yellow when hurt
        "red": ((h <= 8) | (h >= 165)) & (s >= 165) & (v >= 170),
        "blue": (h >= 96) & (h <= 106) & (s >= 185) & (v >= 200),
    }


def measure_bar(any_fill: np.ndarray, anchor: Anchor) -> tuple[float, int, bool]:
    """Bar width, bottom row and whether a bar was found, from the long run through the anchor.

    `any_fill` is the union of the fill masks and the dark bar outline. Without a bar the width
    is DEFAULT_BW and the bottom sits just under the anchor.
    """
    height, width = any_fill.shape
    nw = anchor.x1 - anchor.x0
    best_len, bot = 0, None
    c0 = min(max(int(anchor.cx), 0), width - 1)
    for r in range(max(0, int(anchor.y1) - 10), min(height, int(anchor.y1) + 9)):
        row = any_fill[r]
        left, gap = c0, 0
        while left > 0 and gap <= 3:
            left -= 1
            gap = 0 if row[left] else gap + 1
        right, gap = c0, 0
        while right < width - 1 and gap <= 3:
            right += 1
            gap = 0 if row[right] else gap + 1
        length = right - left - 8
        if 1.1 * nw <= length <= 3.8 * nw and length <= 150:
            if length >= 0.85 * best_len:
                bot = r
            best_len = max(best_len, length)
    found = best_len >= 60
    bw = float(best_len) if found else DEFAULT_BW
    if bot is None:
        bot = int(anchor.y1) + 3
    return min(bw, 130.0), int(bot), found
