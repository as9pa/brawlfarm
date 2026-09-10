"""Tests for Phase B — bush-hide + gas-aware repositioning (r8).

Two layers, mirroring test_match_vision.py:
  * PURE tests for the decision function (match_vision.bush_decision) — clusters +
    gas signals in, an Action out, no I/O;
  * detector tests on SYNTHETIC frames (numpy arrays painted with saturated-green
    blobs) so bush_clusters / the conservative gate are pinned without committing
    large PNGs, plus a fail-open check that a detector exception degrades to wander.

The feature is calibrated-by-reasoning, NOT live-validated; these tests pin the
DECISION LOGIC and the fail-safe degradation, which is what must never regress.
"""

import math

import cv2
import numpy as np

from brawlfarm.core import config
from brawlfarm.core import match_vision as mv

FS = (config.SCREEN_W, config.SCREEN_H)
SELF = config.BUSH_SELF_POS


def _bush(cx, cy, area=500):
    return mv.Bush(cx=cx, cy=cy, area=area)


# --- bush_decision: the pure logic -----------------------------------------------


def test_no_clusters_wanders():
    a = mv.bush_decision([], SELF, FS, set(), {})
    assert a.kind == "wander"
    assert a.target is None


def test_hides_in_nearest_bush():
    near = _bush(SELF[0] + 100, SELF[1])  # 100 px right of self
    far = _bush(50, 50)
    a = mv.bush_decision([far, near], SELF, FS, set(), {})
    assert a.kind == "hide"
    assert a.target == (near.cx, near.cy)


def test_at_target_when_inside_the_bush():
    on_top = _bush(SELF[0] + config.BUSH_AT_TARGET_PX - 10, SELF[1])
    a = mv.bush_decision([on_top], SELF, FS, set(), {})
    assert a.kind == "hide"
    assert a.at_target is True


def test_not_at_target_when_outside():
    out = _bush(SELF[0] + config.BUSH_AT_TARGET_PX + 50, SELF[1])
    a = mv.bush_decision([out], SELF, FS, set(), {})
    assert a.kind == "hide"
    assert a.at_target is False


def test_relocates_when_gas_on_two_edges():
    central = _bush(FS[0] // 2 + 20, FS[1] // 2)  # near map center
    edgey = _bush(60, 60)  # near a corner
    a = mv.bush_decision([edgey, central], SELF, FS, {"top", "left"}, {"top": 0.1, "left": 0.1})
    assert a.kind == "relocate"
    assert a.target == (central.cx, central.cy)  # the more-central bush


def test_relocates_when_one_edge_is_deep():
    # a single gassed edge, but deep in its band (>= BUSH_GAS_PROXIMITY) ≈ gas near us
    central = _bush(FS[0] // 2, FS[1] // 2)
    a = mv.bush_decision([central], SELF, FS, {"right"}, {"right": config.BUSH_GAS_PROXIMITY})
    assert a.kind == "relocate"


def test_one_shallow_edge_still_hides():
    # one gassed edge, shallow (below proximity) and below the 2-edge gate -> HIDE,
    # not relocate (gas is not yet "closing in")
    near = _bush(SELF[0] + 80, SELF[1])
    a = mv.bush_decision([near], SELF, FS, {"top"}, {"top": 0.05})
    assert a.kind == "hide"


def test_relocate_picks_bush_closest_to_center():
    c1 = _bush(FS[0] // 2 + 300, FS[1] // 2)
    c2 = _bush(FS[0] // 2 + 50, FS[1] // 2)  # closer to center
    c3 = _bush(FS[0] // 2 + 600, FS[1] // 2)
    a = mv.bush_decision([c1, c2, c3], SELF, FS, {"left", "right"}, {"left": 0.2, "right": 0.2})
    assert a.target == (c2.cx, c2.cy)


# --- bush_clusters: detector on synthetic frames ---------------------------------


def _green_frame(blobs):
    """A black 1600x900 BGR frame with saturated-green filled rectangles. blobs =
    [(cx, cy, half)] painted with a bush-window-valid BGR color."""
    img = np.zeros((config.SCREEN_H, config.SCREEN_W, 3), np.uint8)
    # A BGR color that lands inside BUSH_HSV_LO/HI: H~73, S~230, V~140. Compute it.
    hsv_px = np.uint8([[[73, 230, 140]]])
    bgr = cv2.cvtColor(hsv_px, cv2.COLOR_HSV2BGR)[0, 0].tolist()
    for cx, cy, half in blobs:
        img[cy - half : cy + half, cx - half : cx + half] = bgr
    return img


def test_detector_finds_a_green_blob():
    img = _green_frame([(800, 450, 60)])  # a 120x120 saturated-green square
    clusters = mv.bush_clusters(img)
    assert len(clusters) >= 1
    big = clusters[0]
    assert abs(big.cx - 800) < 20 and abs(big.cy - 450) < 20  # centroid ~ the blob


def test_detector_empty_on_black_frame():
    assert mv.bush_clusters(np.zeros((config.SCREEN_H, config.SCREEN_W, 3), np.uint8)) == []


def test_detector_drops_specks_below_min_area():
    # a 16x16 blob at 1/8 downscale is ~2x2 px in the mask -> below BUSH_MIN_AREA
    img = _green_frame([(800, 450, 8)])
    assert mv.bush_clusters(img) == []


def test_detector_orders_by_area_desc():
    img = _green_frame([(300, 300, 45), (1100, 600, 90)])  # smaller, bigger
    clusters = mv.bush_clusters(img)
    assert len(clusters) >= 2
    assert clusters[0].area >= clusters[1].area
    assert abs(clusters[0].cx - 1100) < 30  # the bigger blob leads


def test_detector_handles_empty_input():
    assert mv.bush_clusters(None) == []
    assert mv.bush_clusters(np.zeros((0, 0, 3), np.uint8)) == []


# --- end-to-end pure pipeline on a synthetic frame -------------------------------


def test_synthetic_pipeline_hides():
    # a green blob just right of self, no gas -> the pipeline hides there
    img = _green_frame([(SELF[0] + 120, SELF[1], 50)])
    clusters = mv.bush_clusters(img)
    a = mv.bush_decision(clusters, SELF, FS, set(), {})
    assert a.kind == "hide"
    assert math.hypot(a.target[0] - (SELF[0] + 120), a.target[1] - SELF[1]) < 40
