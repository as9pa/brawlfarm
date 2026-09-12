"""
Vision: find known UI elements on the current screen.

The core trick is OpenCV "template matching": we keep a small reference image of
a button (e.g. the PLAY button) in templates/, then slide it over a screenshot
to find where (and how confidently) it appears.

  find(screen, "play")        -> Match | None
  wait_for(screen_fn, "play") -> block until a template appears

Each Match carries the center point, so the bot can tap it directly.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

import cv2
import numpy as np

from brawlfarm.core import config


@dataclass
class Match:
    name: str
    confidence: float
    x: int  # center x
    y: int  # center y
    w: int
    h: int

    @property
    def center(self) -> tuple[int, int]:
        return (self.x, self.y)


# The templates that ship with the package. Fixed at import: the folder is package
# data, so a calibration override never adds or removes a name, it only replaces a file.
TEMPLATE_NAMES: tuple[str, ...] = tuple(sorted(p.stem for p in config.TEMPLATES_DIR.glob("*.png")))


def OVERRIDE_DIR() -> Path:
    """Where the Calibration page writes re-cropped templates. Read from config at CALL
    time, never at import: config.set_home() re-points HOME_DIR under us."""
    return config.HOME_DIR / "calibration" / "templates"


def template_path(name: str) -> Path:
    """The file actually used for `name`: the override if one exists, else packaged."""
    override = OVERRIDE_DIR() / f"{name}.png"
    if override.is_file():
        return override
    return config.TEMPLATES_DIR / f"{name}.png"


def template_source(name: str) -> Literal["package", "override"]:
    return "override" if (OVERRIDE_DIR() / f"{name}.png").is_file() else "package"


@lru_cache(maxsize=64)
def _read_template(path_str: str, mtime_ns: int) -> np.ndarray:
    img = cv2.imread(path_str, cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"Template not found: {path_str}")
    return img


@lru_cache(maxsize=64)
def _read_template_gray(path_str: str, mtime_ns: int) -> np.ndarray:
    """Grayscale variant for the fast matching path (config.GRAY_MATCH). Converted
    from the BGR load (not IMREAD_GRAYSCALE) so the pixels are guaranteed to use the
    same BGR->gray weights as the screen-side cvtColor in _as_gray."""
    return cv2.cvtColor(_read_template(path_str, mtime_ns), cv2.COLOR_BGR2GRAY)


def _stat_key(name: str) -> tuple[str, int]:
    """Cache key for the loaders: path plus mtime, so dropping (or deleting) an override
    is picked up on the next match without restarting the bot."""
    path = template_path(name)
    try:
        mtime_ns = path.stat().st_mtime_ns
    except OSError:
        raise FileNotFoundError(f"Template not found: {path}") from None
    return str(path), mtime_ns


def _load_template(name: str) -> np.ndarray:
    return _read_template(*_stat_key(name))


def _load_template_gray(name: str) -> np.ndarray:
    return _read_template_gray(*_stat_key(name))


# Per-frame grayscale cache: classify() calls find() up to ~10x on the SAME frame, so we
# convert once and reuse (keyed by object identity — frames are never mutated in place).
# Holding a reference to the last frame (~4 MB) is a fine trade for skipping ~9 cvtColors.
_gray_cache: tuple[np.ndarray, np.ndarray] | None = None  # (bgr_frame, gray_frame)


def _as_gray(screen: np.ndarray) -> np.ndarray:
    global _gray_cache
    if screen.ndim == 2:
        return screen  # already grayscale
    if _gray_cache is not None and _gray_cache[0] is screen:
        return _gray_cache[1]
    gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
    _gray_cache = (screen, gray)
    return gray


def threshold_for(name: str) -> float:
    """The threshold find() uses for this template when none is passed. Two templates
    are tuned away from the default: "teams_left" is text over varying maps (lower) and
    "matchmaking" hit 0.86 on a reward screen (higher). See config "Vision tuning"."""
    if name == "matchmaking":
        return config.MATCHMAKING_THRESHOLD
    if name == "teams_left":
        return config.IN_MATCH_THRESHOLD
    return config.MATCH_THRESHOLD


def find(screen: np.ndarray, name: str, threshold: float | None = None) -> Match | None:
    """Return the best match for template `name` in `screen`, or None if the
    best score is below threshold. A threshold of None means threshold_for(name).

    When config.GRAY_MATCH is on (default), the match runs on grayscale views of both
    the screen and the template — ~4.7x faster than BGR for TM_CCOEFF_NORMED (which
    correlates per channel). Decision-equivalence to color was validated per template
    on the full capture corpus; the two templates where grayscale has NO valid
    threshold (config.COLOR_ONLY_TEMPLATES) keep matching in color. See config.py
    "Vision tuning" and the legacy research note "performance optimization", item 1
    (not ported)."""
    if threshold is None:
        threshold = threshold_for(name)

    if config.GRAY_MATCH and name not in config.COLOR_ONLY_TEMPLATES:
        template = _load_template_gray(name)
        haystack = _as_gray(screen)
    else:
        template = _load_template(name)
        haystack = screen
    th, tw = template.shape[:2]

    result = cv2.matchTemplate(haystack, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    if max_val < threshold:
        return None

    top_left = max_loc
    return Match(
        name=name,
        confidence=float(max_val),
        x=top_left[0] + tw // 2,
        y=top_left[1] + th // 2,
        w=tw,
        h=th,
    )


def find_with_score(
    screen: np.ndarray, name: str, threshold: float | None = None
) -> tuple[Match | None, float]:
    """Like :func:`find`, but ALSO returns the best match score (0..1) regardless of
    whether it cleared the threshold — one matchTemplate pass for both. The score is
    handy for honest diagnostics (e.g. logging WHY a mode check missed without a second
    OCR/template pass). Follows config.GRAY_MATCH and the COLOR_ONLY_TEMPLATES carve-out
    exactly like find()/score(), so its verdict matches find()'s on the same frame."""
    if threshold is None:
        threshold = threshold_for(name)
    if config.GRAY_MATCH and name not in config.COLOR_ONLY_TEMPLATES:
        template = _load_template_gray(name)
        haystack = _as_gray(screen)
    else:
        template = _load_template(name)
        haystack = screen
    th, tw = template.shape[:2]
    result = cv2.matchTemplate(haystack, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    max_val = float(max_val)
    if max_val < threshold:
        return None, max_val
    return (
        Match(
            name=name,
            confidence=max_val,
            x=max_loc[0] + tw // 2,
            y=max_loc[1] + th // 2,
            w=tw,
            h=th,
        ),
        max_val,
    )


def score(screen: np.ndarray, name: str) -> float:
    """Return just the best match confidence (0..1), ignoring the threshold.
    Handy for debugging / tuning. Follows config.GRAY_MATCH (including the
    COLOR_ONLY_TEMPLATES carve-out) so tuning reflects what find() actually does."""
    if config.GRAY_MATCH and name not in config.COLOR_ONLY_TEMPLATES:
        template = _load_template_gray(name)
        haystack = _as_gray(screen)
    else:
        template = _load_template(name)
        haystack = screen
    result = cv2.matchTemplate(haystack, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return float(max_val)


# --- color detection (for the dynamic ability buttons) -----------------------


def color_fraction(screen: np.ndarray, region: tuple, hsv_lo, hsv_hi) -> float:
    """Fraction (0..1) of pixels in `region` whose HSV falls within [lo, hi]."""
    x1, y1, x2, y2 = region
    crop = screen[y1:y2, x1:x2]
    if crop.size == 0:
        return 0.0
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array(hsv_lo, np.uint8), np.array(hsv_hi, np.uint8))
    return float((mask > 0).mean())


def frame_signature(screen: np.ndarray) -> int:
    """Cheap perceptual-ish hash for freeze detection: mean of a downscaled gray
    image, quantized. Equal signatures across time => screen likely frozen."""
    small = cv2.resize(screen, (32, 18))
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    return hash(gray.tobytes())


# --- OCR: read text / numbers off the screen ---------------------------------
#
# Template matching only answers "is this exact button here?". OCR reads the
# actual text/numbers, which templates can't: live trophy totals, the matchmaking
# "N/12" count, "Teams left: N", and a new account's player tag (for multi-account
# onboarding). Backed by RapidOCR (onnxruntime) — pure-pip, no system install. The
# engine is built lazily on first use (loading the models takes ~1s) so importing
# this module stays cheap.

_ocr_engine = None


def _get_ocr():
    global _ocr_engine
    if _ocr_engine is None:
        from rapidocr_onnxruntime import RapidOCR

        _ocr_engine = RapidOCR()
    return _ocr_engine


def _crop(screen: np.ndarray, region: tuple | None) -> np.ndarray:
    if region is None:
        return screen
    x1, y1, x2, y2 = region
    return screen[y1:y2, x1:x2]


def read_lines(
    screen: np.ndarray, region: tuple | None = None, scale: float = 2.0
) -> list[tuple[str, float]]:
    """OCR a region (or the whole frame) and return [(text, confidence), ...],
    one entry per detected text line, in reading order.

    `region` is (x1, y1, x2, y2). Game UI text is small, so the crop is upscaled
    by `scale` first — that noticeably improves recognition on tiny labels.
    """
    img = _crop(screen, region)
    if img.size == 0:
        return []
    if scale and scale != 1.0:
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    # Our frames are BGR (cv2), but RapidOCR's detector normalizes with RGB
    # ImageNet stats (it expects the PIL/RGB order it was trained on). Feeding BGR
    # applies the R/B constants to the wrong channels and degrades recognition on
    # colored HUD text — so convert first.
    if img.ndim == 3 and img.shape[2] == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    result, _ = _get_ocr()(img)
    if not result:
        return []
    # RapidOCR returns [box, text, confidence] per line.
    return [(line[1], float(line[2])) for line in result]


def read_lines_boxes(
    screen: np.ndarray, region: tuple | None = None, scale: float = 2.0
) -> list[tuple[str, float, tuple[int, int]]]:
    """Like ``read_lines`` but each entry also carries the line's center (x, y) in
    FULL-FRAME coordinates: [(text, confidence, (cx, cy)), ...]. Used when a whole
    screen of labels must be located in one OCR pass (e.g. every brawler-card name on
    the BRAWLERS grid) — calling find_text per needle would re-run OCR N times."""
    img = _crop(screen, region)
    if img.size == 0:
        return []
    if scale and scale != 1.0:
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    if img.ndim == 3 and img.shape[2] == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    result, _ = _get_ocr()(img)
    if not result:
        return []
    ox, oy = (region[0], region[1]) if region else (0, 0)
    out = []
    for box, text, conf in result:
        cx = sum(p[0] for p in box) / len(box) / scale + ox
        cy = sum(p[1] for p in box) / len(box) / scale + oy
        out.append((text, float(conf), (int(cx), int(cy))))
    return out


def read_text(screen: np.ndarray, region: tuple | None = None, scale: float = 2.0) -> str:
    """OCR a region (or the whole frame) and return all detected text joined into
    one string. Returns "" if nothing is read."""
    return " ".join(text for text, _ in read_lines(screen, region, scale)).strip()


def read_int(screen: np.ndarray, region: tuple | None = None, scale: float = 3.0) -> int | None:
    """Read the first integer in `region` (trophy total, players "N/12", "Teams
    left: N", ...). Strips thousands separators. Returns None if no digits found.
    Uses a higher default `scale` since number labels are usually small."""
    text = read_text(screen, region, scale=scale)
    m = re.search(r"-?\d[\d,]*", text)
    return int(m.group(0).replace(",", "")) if m else None


def find_text(
    screen: np.ndarray,
    needle: str,
    region: tuple | None = None,
    scale: float = 2.0,
    exact: bool = False,
) -> tuple[int, int] | None:
    """Locate a text label by its CONTENT and return its center (x, y) in full-frame
    coordinates, or None if not found. Case-insensitive. `exact=False` does a substring
    match; `exact=True` requires the whole detected line to equal `needle` (use this to
    target "SHOWDOWN" without also matching the "LOADED DUO SHOWDOWN" event card).

    This lets OCR DRIVE taps, not just read. The motivating case: the event/mode
    selector lays out cards (SHOWDOWN, BRAWL BALL, ...) whose positions shift as
    events rotate, so a hard-coded coordinate breaks at the next rotation — but
    `find_text(screen, "SHOWDOWN")` finds the card wherever it landed.
    """
    img = _crop(screen, region)
    if img.size == 0:
        return None
    if scale and scale != 1.0:
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    if img.ndim == 3 and img.shape[2] == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    result, _ = _get_ocr()(img)
    if not result:
        return None
    ox, oy = (region[0], region[1]) if region else (0, 0)
    needle = needle.lower()
    for box, text, _conf in result:  # box = 4 corner points in scaled-crop coords
        t = text.strip().lower()
        if (t == needle) if exact else (needle in t):
            cx = sum(p[0] for p in box) / len(box) / scale + ox
            cy = sum(p[1] for p in box) / len(box) / scale + oy
            return (int(cx), int(cy))
    return None
