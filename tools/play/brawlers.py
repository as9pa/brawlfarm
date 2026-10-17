"""Brawler auto-labels: anchors from one OCR pass and the health bar under each anchor.

An anchor is the HP number over a brawler: a 3 to 5 digit OCR box of normal height. Big
floating damage numbers are rejected by their font height unless a name sits right above them,
and a name with no number under it still anchors a bar where the number would be. Anchors in a
zone mask (the HUD and any per-source exclusion) are dropped. OCR text is only read here, never
kept: an anchor carries geometry and nothing else.

The class vote reads the bar colour first and the ring under the feet second. Green counts as
self only with the ammo bar under it or at the camera centre, a green ring still says self when
a hurt self's bar reads red, and at most one self survives per frame.

The box geometry prompts SAM with points and a box under each bar, keeps the mask that looks
most like a body, and falls back to a fixed-size box under the bar when no mask passes.
"""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, replace

import cv2
import numpy as np

DEFAULT_BW = 92.0  # bar width when no bar is found under the anchor
BAR_NEED = 12  # fill pixels one colour needs in the bar to decide it
RING_NEED = 40  # ring pixels one colour needs under the feet to decide it
AMMO_MIN = 0.3  # share of the bar width the orange ammo bar must pass to mark a self
CRATE_MIN = 0.12  # crate share that makes an unnamed red or colourless bar a power cube box
CRATE_STRONG = 0.2  # crate share that makes any unnamed bar a box
NAME_INK_MIN = 0.05  # name-like ink above an unnamed red bar: a name OCR could not read
CLASS_OF = {"green": "self", "blue": "teammate", "red": "enemy"}
FALLBACK_SCORE = 0.3  # score of the fixed-size box used when SAM finds no body


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


@dataclass(frozen=True)
class Evidence:
    """What the class vote reads about one bar: colour votes, OCR facts and nearby fills."""

    bar: dict[str, int]
    ring: dict[str, int]
    named: bool
    found: bool
    ammo: float
    centred: bool
    crate: float
    name_ink: float
    solo: bool


@dataclass
class Bar:
    """One classified health bar: its class, geometry and why its colour was picked."""

    cls: str
    cx: float
    bw: float
    bot: int
    named: bool
    colour: str | None
    why: str
    ammo: float

    def to_json(self) -> dict:
        return asdict(self)

    @classmethod
    def from_json(cls, blob: dict) -> Bar:
        return cls(**blob)


def top_colour(votes: dict[str, int], need: int, skip: tuple[str, ...] = ()) -> str | None:
    """The colour with the most votes, passing over `skip`, or None once votes fall below need."""
    for colour in sorted(votes, key=lambda c: (-votes[c], c)):
        if votes[colour] < need:
            return None
        if colour in skip:
            continue
        return colour
    return None


def bar_colour(ev: Evidence) -> tuple[str | None, str]:
    """The bar's colour and where it came from: "bar", "ring" or "none".

    Green only counts with the ammo bar under it or at the camera centre; elsewhere it is grass
    or a heal effect behind the bar and the next colour decides.
    """
    skip = () if (ev.ammo > AMMO_MIN or ev.centred) else ("green",)
    colour = top_colour(ev.bar, BAR_NEED, skip)
    if colour:
        return colour, "bar"
    colour = top_colour(ev.ring, RING_NEED, skip)
    if colour:
        return colour, "ring"
    return None, "none"


def vote_class(ev: Evidence) -> str | None:
    """The class of one bar: self, teammate, enemy or box, or None to drop it."""
    colour, _why = bar_colour(ev)
    if ev.ammo > AMMO_MIN:
        return "self"
    if not ev.named and (
        (ev.crate >= CRATE_MIN and colour in ("red", None)) or ev.crate >= CRATE_STRONG
    ):
        return "box"
    # a low-health self reads red; the green ring under its feet still says self
    if colour in ("red", None) and top_colour(ev.ring, RING_NEED) == "green":
        return "self"
    if not ev.named:
        if colour == "green":
            return "self"
        if colour == "red" and ev.found and ev.name_ink >= NAME_INK_MIN:
            return "enemy"  # a name OCR could not read
        return None  # own pet, turret or stray number
    # no colour reads as an enemy; solo showdown has no teammates, so blue came from an effect
    if colour is None or (colour == "blue" and ev.solo):
        return "enemy"
    return CLASS_OF[colour]


def dedupe(bars: list[Bar]) -> list[Bar]:
    """One bar per health bar: of anchors on the same bar the named, then the higher, one stays."""
    keep: list[Bar] = []
    for b in sorted(bars, key=lambda b: (not b.named, b.bot)):
        if any(abs(b.cx - k.cx) < 0.8 * k.bw and abs(b.bot - k.bot) < 20 for k in keep):
            continue
        keep.append(b)
    return keep


def resolve_selfs(bars: list[Bar], width: int, height: int) -> list[Bar]:
    """At most one self: the one with the ammo bar, then the one nearest the camera centre.

    The spike turned every losing self into an enemy, which labelled own pets as enemies; a
    losing self now stays only when its bar read red and it has a name.
    """
    selfs = [b for b in bars if b.cls == "self"]
    if len(selfs) <= 1:
        return bars
    best = max(
        selfs,
        key=lambda b: (
            b.ammo > AMMO_MIN,
            -math.hypot(b.cx - 0.5 * width, b.bot - 0.42 * height),
        ),
    )
    out: list[Bar] = []
    for b in bars:
        if b.cls != "self" or b is best:
            out.append(b)
        elif b.colour == "red" and b.named:
            out.append(replace(b, cls="enemy"))
    return out


def colour_votes(
    fills: dict[str, np.ndarray], hsv: np.ndarray, cx: float, bot: int, bw: float, num_bottom: float
) -> tuple[dict[str, int], dict[str, int]]:
    """Fill pixels per colour in the bar, and ring pixels per colour under the feet.

    The bar box runs from just above the HP number's bottom edge down to the bar bottom; the
    ring box sits where the feet are, below the body.
    """
    height, width = hsv.shape[:2]
    y0, y1 = max(0, int(num_bottom) - 11), min(height, bot + 1)
    x0, x1 = int(max(0, cx - 0.55 * bw)), int(min(width, cx + 0.55 * bw))
    bar = {k: int(m[y0:y1, x0:x1].sum()) for k, m in fills.items()}
    ry0, ry1 = min(height, bot + int(0.7 * bw)), min(height, bot + int(1.6 * bw))
    rx0, rx1 = int(max(0, cx - 0.8 * bw)), int(min(width, cx + 0.8 * bw))
    h, s, v = (hsv[ry0:ry1, rx0:rx1, i].astype(int) for i in range(3))
    ring = {
        "green": int(((h >= 35) & (h <= 85) & (s >= 100) & (v >= 120)).sum()),
        "blue": int(((h >= 95) & (h <= 120) & (s >= 120) & (v >= 140)).sum()),
        "red": int((((h <= 6) | (h >= 172)) & (s >= 140) & (v >= 140)).sum()),
    }
    return bar, ring


def crate_share(hsv: np.ndarray, cx: float, bot: int, bw: float) -> float:
    """Share of crate-orange pixels in the body box under the bar."""
    height, width = hsv.shape[:2]
    y0, y1 = min(height, bot + int(0.15 * bw)), min(height, bot + int(1.05 * bw))
    x0, x1 = int(max(0, cx - 0.4 * bw)), int(min(width, cx + 0.4 * bw))
    h, s, v = (hsv[y0:y1, x0:x1, i] for i in range(3))
    if h.size == 0:
        return 0.0
    return float(((h >= 6) & (h <= 24) & (s >= 120) & (v >= 120)).mean())


def ammo_share(hsv: np.ndarray, cx: float, bot: int, bw: float) -> float:
    """Share of the bar width with the orange ammo bar in the band just under the bar."""
    width = hsv.shape[1]
    band = hsv[bot + 1 : bot + 13, int(max(0, cx - bw / 2)) : int(min(width, cx + bw / 2))]
    if band.size == 0:
        return 0.0
    h, s, v = (band[..., i] for i in range(3))
    mask = (h >= 8) & (h <= 20) & (s >= 140) & (v >= 170)
    return float(mask.any(axis=0).mean())


def name_ink(bgr: np.ndarray, cx: float, bw: float, top: float) -> float:
    """Edge density of bright ink over the HP number: a name. Crates and pets have none."""
    width = bgr.shape[1]
    y1 = int(top) - 1
    y0 = max(0, y1 - 22)
    x0, x1 = int(max(0, cx - 0.6 * bw)), int(min(width, cx + 0.6 * bw))
    if y1 <= y0 + 4:
        return 0.0
    patch = bgr[y0:y1, x0:x1]
    edges = cv2.Canny(cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY), 80, 200)
    v = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)[..., 2]
    return float(edges.mean() / 255.0) * float((v > 150).mean() + 0.01) * 10


def is_centred(cx: float, bot: int, width: int, height: int) -> bool:
    """Whether a bar sits where the camera keeps the own brawler."""
    return abs(cx - 0.5 * width) < 0.3 * width and abs(bot - 0.42 * height) < 0.08 * height


def classify(bgr: np.ndarray, hsv: np.ndarray, anchors: list[Anchor], solo: bool) -> list[Bar]:
    """One classified bar per brawler or power cube box on a frame, at most one of them self.

    `bgr` and `hsv` are the same frame; `solo` says the frame is solo showdown.
    """
    height, width = hsv.shape[:2]
    fills = fill_masks(hsv)
    any_fill = fills["green"] | fills["red"] | fills["blue"] | (hsv[..., 2] <= 70)
    bars: list[Bar] = []
    for anchor in anchors:
        bw, bot, found = measure_bar(any_fill, anchor)
        if anchor.from_name and not found:
            continue
        if height - bot < 0.35 * bw:  # body off-screen under the bottom edge
            continue
        bar, ring = colour_votes(fills, hsv, anchor.cx, bot, bw, anchor.y1)
        ev = Evidence(
            bar=bar,
            ring=ring,
            named=anchor.named,
            found=found,
            ammo=ammo_share(hsv, anchor.cx, bot, bw),
            centred=is_centred(anchor.cx, bot, width, height),
            crate=crate_share(hsv, anchor.cx, bot, bw),
            name_ink=0.0 if anchor.named else name_ink(bgr, anchor.cx, bw, anchor.y0),
            solo=solo,
        )
        cls = vote_class(ev)
        if cls is None:
            continue
        colour, why = bar_colour(ev)
        bars.append(Bar(cls, anchor.cx, bw, bot, anchor.named, colour, why, ev.ammo))
    return resolve_selfs(dedupe(bars), width, height)


def sam_prompt(
    bar: Bar, width: int, height: int
) -> tuple[list[list[float]], list[int], list[float]]:
    """SAM points, their labels and the prompt box for the body under one bar.

    Two positive points run down the body and three negative points sit left, right and below
    it. Every point is clamped to the frame.
    """
    bw, cx, bot = bar.bw, bar.cx, bar.bot
    raw = [
        [cx, bot + 0.45 * bw],
        [cx, bot + 0.75 * bw],
        [cx - 0.85 * bw, bot + 1.15 * bw],
        [cx + 0.85 * bw, bot + 1.15 * bw],
        [cx, bot + 1.55 * bw],
    ]
    points = [[min(width - 1, max(0, px)), min(height - 1, max(0, py))] for px, py in raw]
    box = [
        max(0, cx - 0.7 * bw),
        bot + 2,
        min(width - 1, cx + 0.7 * bw),
        min(height - 1, bot + 1.35 * bw),
    ]
    return points, [1, 1, 0, 0, 0], box


def ring_mask(hsv: np.ndarray, cls: str) -> np.ndarray:
    """Bool mask of the ring colour under a brawler of one class: green, blue, else red."""
    h, s, v = (hsv[..., i].astype(int) for i in range(3))
    if cls == "self":
        return (h >= 35) & (h <= 90) & (s >= 50) & (v >= 35)
    if cls == "teammate":
        return (h >= 90) & (h <= 125) & (s >= 60) & (v >= 40)
    return ((h <= 6) | (h >= 165)) & (s >= 70) & (v >= 50)


def pick_box(
    masks: np.ndarray, scores: np.ndarray, bar: Bar, ring: np.ndarray
) -> tuple[tuple[int, int, int, int], float, float] | None:
    """The body box from the SAM mask that looks most like a body, or None when all are empty.

    Returns the box, the mask's raw SAM score and that score less the shape penalties. A mask is
    penalised for ring pixels, for being too wide, too tall, head-only, low, small or off the bar
    centre. Ring pixels low in the mask are cut so the feet ring does not stretch the box.
    """
    best, best_score = None, -1e9
    bw = bar.bw
    ylow = int(bar.bot + 0.55 * bw)
    kernel = np.ones((max(3, int(bw / 18)),) * 2, np.uint8)
    for k in range(masks.shape[0]):
        m = masks[k].copy()
        m[: bar.bot + 2, :] = False
        total = m.sum()
        if total == 0:
            continue
        ring_share = (m & ring).sum() / total
        m[ylow:] &= ~ring[ylow:]
        m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, kernel)
        n, _labels, stats, _centroids = cv2.connectedComponentsWithStats(m, 8)
        if n <= 1:
            continue
        j = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        x, y, w, h, area = stats[j]
        pen = 0.8 * ring_share
        if w > 1.3 * bw:
            pen += (w - 1.3 * bw) / bw
        if h > 1.5 * bw:
            pen += (h - 1.5 * bw) / bw
        if h < 0.55 * bw:  # head-only masks
            pen += 0.7 + (0.55 * bw - h) / bw
        if y - bar.bot > 0.6 * bw:
            pen += 1.0
        if area < 0.15 * bw * bw:
            pen += 1.0
        if abs(x + w / 2 - bar.cx) > 0.45 * bw:
            pen += 1.0
        adjusted = float(scores[k]) - pen
        if adjusted > best_score:
            best_score = adjusted
            best = ((int(x), int(y), int(w), int(h)), float(scores[k]), adjusted)
    return best


def sane(box: tuple[int, int, int, int], bar: Bar, height: int) -> bool:
    """Whether a box sits under the bar with a body's size; edge brawlers may be cut short."""
    x, y, w, h = box
    bw, bot = bar.bw, bar.bot
    visible = height - bot  # rows under the bar; the frame edge cuts a brawler standing there
    return (
        abs(x + w / 2 - bar.cx) <= 0.4 * bw
        and bot - 2 <= y <= bot + 0.55 * bw
        and 0.4 * bw <= w <= 1.45 * bw
        and min(0.5 * bw, 0.8 * visible) <= h <= 1.6 * bw
    )


def fixed_box(bar: Bar, width: int, height: int) -> tuple[int, int, int, int]:
    """A body-sized box just under the bar, clipped to the frame."""
    bw = bar.bw
    w, h = 0.95 * bw, 1.0 * bw
    x0, y0 = max(0, bar.cx - w / 2), bar.bot + 0.15 * bw
    x1, y1 = min(width, bar.cx + w / 2), min(height, y0 + h)
    return int(x0), int(y0), int(x1 - x0), int(y1 - y0)


def fallback_box(bar: Bar, w: int, h: int) -> dict:
    """The box dict for a bar SAM found no body under: the fixed box at FALLBACK_SCORE.

    `w` and `h` are the frame width and height.
    """
    x, y, box_w, box_h = fixed_box(bar, w, h)
    return {
        "class": bar.cls,
        "x": x,
        "y": y,
        "w": box_w,
        "h": box_h,
        "score": FALLBACK_SCORE,
        "fallback": True,
    }


def choose_box(masks: np.ndarray, scores: np.ndarray, bar: Bar, hsv: np.ndarray) -> dict:
    """The box dict for one bar from its SAM masks, or the fallback box when no mask passes.

    `masks` is (k, H, W) bool and `scores` is (k,), both for this bar's prompt.
    """
    height, width = hsv.shape[:2]
    ring = ring_mask(hsv, "enemy" if bar.cls == "box" else bar.cls)
    picked = pick_box(masks, scores, bar, ring)
    if picked is None or not sane(picked[0], bar, height) or picked[2] <= -0.5:
        return fallback_box(bar, width, height)
    (x, y, w, h), score, _adjusted = picked
    if bar.cls == "box":
        # SAM often splits the crate lid from the front face; the union of masks has the lid top
        union = masks.any(axis=0)[:, x + w // 5 : x + w - w // 5]
        union[: bar.bot + 2] = False
        rows = np.where(union.any(axis=1))[0]
        if len(rows) and rows.min() < y and y - rows.min() < 0.8 * w:
            h += y - int(rows.min())
            y = int(rows.min())
    return {
        "class": bar.cls,
        "x": int(x),
        "y": int(y),
        "w": int(w),
        "h": int(h),
        "score": round(float(score), 3),
        "fallback": False,
    }


def suppress(boxes: list[dict]) -> list[dict]:
    """Boxes from the best score down, without any that overlaps a better box too much.

    Two boxes clash when their overlap passes half the smaller one's area, whatever the class.
    """
    keep: list[dict] = []
    for t in sorted(boxes, key=lambda b: b["score"], reverse=True):
        clash = False
        for k in keep:
            ix = max(0, min(t["x"] + t["w"], k["x"] + k["w"]) - max(t["x"], k["x"]))
            iy = max(0, min(t["y"] + t["h"], k["y"] + k["h"]) - max(t["y"], k["y"]))
            if ix * iy > 0.5 * min(t["w"] * t["h"], k["w"] * k["h"]):
                clash = True
                break
        if not clash:
            keep.append(t)
    return keep
