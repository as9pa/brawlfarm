"""Unit tests for brawlfarm/core/match_vision.py (Phase A gas heading + Phase D buttons).

Two layers:
  * pure-math tests for the hysteresis tracker and the heading-bias function
    (no I/O, no fixtures);
  * detector tests against small REAL crops committed under tests/fixtures/
    (cut from the P9 harvest corpus / the Phase-D calibration captures), so the
    validated thresholds are pinned by CI without needing the full corpus.
"""

import math
import pathlib

import cv2
import pytest

from brawlfarm.core import config, match_vision
from brawlfarm.core.vision import color_fraction

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def _angle_close(a: float, b: float, tol: float = 1e-6) -> bool:
    """Compare two angles modulo 2*pi."""
    return abs((a - b + math.pi) % (2 * math.pi) - math.pi) <= tol


def _clear():
    return {"top": 0.0, "bottom": 0.0, "left": 0.0, "right": 0.0}


# --- GasTracker hysteresis -------------------------------------------------------


def test_tracker_starts_clear():
    assert match_vision.GasTracker().update(_clear()) == set()


def test_tracker_on_at_threshold():
    t = match_vision.GasTracker()
    fr = _clear() | {"top": config.GAS_BAND_ON}  # exactly at ON -> gassed
    assert t.update(fr) == {"top"}


def test_tracker_holds_in_dead_zone_then_clears():
    t = match_vision.GasTracker()
    t.update(_clear() | {"left": 0.30})
    # fraction sags into the [OFF, ON) dead zone -> edge stays gassed (hysteresis)
    assert t.update(_clear() | {"left": 0.03}) == {"left"}
    # below OFF -> clears
    assert t.update(_clear() | {"left": 0.01}) == set()


def test_tracker_dead_zone_does_not_turn_on():
    t = match_vision.GasTracker()
    # 0.03 is "gas arriving" — not yet ON (that's the whole point of the valley)
    assert t.update(_clear() | {"right": 0.03}) == set()


def test_tracker_reset():
    t = match_vision.GasTracker()
    t.update(_clear() | {"top": 0.5, "bottom": 0.5})
    t.reset()
    assert t.update(_clear()) == set()


# --- gas_bias_heading ------------------------------------------------------------


def test_no_gas_keeps_heading():
    assert match_vision.gas_bias_heading(1.234, _clear(), set()) == 1.234


def test_top_gas_pushes_downward():
    # heading straight up (screen coords: -pi/2), top edge fully gassed -> the
    # repulsion (0, +1) must pull the heading back toward down (positive y).
    fr = _clear() | {"top": 1.0}
    out = match_vision.gas_bias_heading(-math.pi / 2, fr, {"top"}, gain=2.5)
    assert math.sin(out) > 0  # now heading downward


def test_left_gas_pushes_right():
    fr = _clear() | {"left": 1.0}
    out = match_vision.gas_bias_heading(math.pi, fr, {"left"}, gain=2.5)
    assert math.cos(out) > 0  # now heading right


def test_weak_gas_only_nudges():
    # A barely-gassed edge (fraction at the ON threshold) must NOT flip a heading
    # that runs parallel to it — just nudge it. Heading right, gas on top.
    fr = _clear() | {"top": config.GAS_BAND_ON}
    out = match_vision.gas_bias_heading(0.0, fr, {"top"}, gain=2.5)
    assert abs(out) < math.pi / 8  # still basically heading right...
    assert out > 0  # ...but nudged slightly downward (away from top)


def test_deeper_gas_pushes_harder():
    fr_shallow = _clear() | {"top": 0.05}
    fr_deep = _clear() | {"top": 0.8}
    nudge_shallow = match_vision.gas_bias_heading(0.0, fr_shallow, {"top"}, gain=2.5)
    nudge_deep = match_vision.gas_bias_heading(0.0, fr_deep, {"top"}, gain=2.5)
    assert nudge_deep > nudge_shallow > 0  # urgency scales with penetration


def test_two_edges_combined_repulsion():
    # gas top + left, equal depth -> push toward down-right (+x, +y quadrant);
    # start heading INTO the corner so only the repulsion can save us.
    fr = _clear() | {"top": 0.6, "left": 0.6}
    out = match_vision.gas_bias_heading(math.atan2(-1, -1), fr, {"top", "left"}, gain=2.5)
    assert math.cos(out) > 0 and math.sin(out) > 0


def test_three_edges_head_for_least_gassed():
    # endgame ring: top/left/right gassed, bottom least -> head straight DOWN
    # (toward the bottom edge), regardless of the incoming heading.
    fr = {"top": 0.9, "left": 0.7, "right": 0.5, "bottom": 0.1}
    out = match_vision.gas_bias_heading(0.3, fr, {"top", "left", "right"}, gain=2.5)
    assert _angle_close(out, math.pi / 2)  # +y = down = toward the bottom edge


def test_four_edges_head_for_least_gassed():
    fr = {"top": 0.2, "left": 0.9, "right": 0.8, "bottom": 0.9}
    out = match_vision.gas_bias_heading(0.0, fr, {"top", "left", "right", "bottom"}, gain=2.5)
    assert _angle_close(out, -math.pi / 2)  # -y = up = toward the least-gassed top


# --- gas detector on real corpus crops --------------------------------------------
# Band crops cut from the harvested corpus (see tools/validate_gas_detector.py and
# docs/research/in-match-vision.md): gas_* crops are visually-confirmed gas inside
# an edge band; clean_* crops are the same bands from gas-free in-match frames.


def _band_fraction(path: pathlib.Path) -> float:
    img = cv2.imread(str(path))
    assert img is not None, f"unreadable fixture: {path}"
    h, w = img.shape[:2]
    return color_fraction(img, (0, 0, w, h), config.GAS_HSV_LO, config.GAS_HSV_HI)


@pytest.mark.parametrize("name", sorted(p.name for p in FIXTURES.glob("gas_*.png")) or ["MISSING"])
def test_gas_band_crops_detect(name):
    if name == "MISSING":
        pytest.skip("no gas fixtures present")
    assert _band_fraction(FIXTURES / name) >= config.GAS_BAND_ON


@pytest.mark.parametrize(
    "name", sorted(p.name for p in FIXTURES.glob("clean_*.png")) or ["MISSING"]
)
def test_clean_band_crops_stay_clear(name):
    if name == "MISSING":
        pytest.skip("no clean fixtures present")
    assert _band_fraction(FIXTURES / name) < config.GAS_BAND_OFF


# --- Phase D: gadget ready-state on real button-ROI crops --------------------------
# Crops of the gadget button face from a live TARA calibration (2026-06-09):
# lit = flat ready-green (corpus fraction >= 0.54); unlit = dark cooldown face
# (zero qualifying pixels); gasoverlap = poison gas drifting over the unlit button
# (the worst plausible false-positive source — the S >= 180 window must reject it).


def _gadget_fraction(path: pathlib.Path) -> float:
    spec = config.ABILITY_BUTTONS["gadget"]
    img = cv2.imread(str(path))
    assert img is not None, f"unreadable fixture: {path}"
    h, w = img.shape[:2]
    return color_fraction(img, (0, 0, w, h), spec["hsv_lo"], spec["hsv_hi"])


def test_gadget_lit_reads_ready():
    spec = config.ABILITY_BUTTONS["gadget"]
    assert _gadget_fraction(FIXTURES / "ability_gadget_lit.png") >= spec["min_fraction"]


def test_gadget_unlit_reads_not_ready():
    spec = config.ABILITY_BUTTONS["gadget"]
    frac = _gadget_fraction(FIXTURES / "ability_gadget_unlit.png")
    assert frac < spec["min_fraction"] / 4  # not just under threshold — far under


def test_gadget_gas_overlap_reads_not_ready():
    spec = config.ABILITY_BUTTONS["gadget"]
    frac = _gadget_fraction(FIXTURES / "ability_gadget_gasoverlap.png")
    assert frac < spec["min_fraction"]
