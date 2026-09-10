"""In-match vision intelligence: gas detection + heading bias (Phase A) and
ability-button readiness (Phase D).

Everything here is deterministic color CV on frames the main loop already
captures — a handful of small-ROI ``color_fraction`` calls per frame (~1-2 ms,
negligible against the ~370 ms capture). No templates, no OCR, no taps: this
module only LOOKS; the controller decides and acts.

Phase A (gas-aware heading), per docs/research/in-match-vision.md:
  * ``gas_fractions(frame)``   — gas-colored fraction in each of the 4 HUD-clipped
    screen-edge bands (config.GAS_BANDS, validated HSV window).
  * ``GasTracker``             — per-edge hysteresis (ON >= 0.04, OFF < 0.02) so a
    fringe flicker can't whipsaw the heading.
  * ``gas_bias_heading(...)``  — pure math: push the wander heading away from
    gassed edges, weighted by how deep the gas has penetrated each band.

Phase D (ability buttons), spec in docs/future-plans/in-match-intelligence.md:
  * ``ready_abilities(frame)`` — which of gadget/super/hypercharge are lit with
    their ready color (green/yellow/purple) right now. The controller taps them
    on a per-button cooldown.

Phase B (bush-hide + gas-aware repositioning, r8):
  * ``bush_clusters(frame)``   — green-foliage clusters in screen space (downscaled
    HSV mask + connected components), conservative so a no-bush map reads empty.
  * ``bush_decision(...)``     — PURE function (clusters + gas signals + self pos
    in -> an Action out): hide in the nearest bush, or, when gas closes in,
    relocate to a bush nearer the map center. No frame access, no I/O — unit-tested
    offline. Calibrated-by-reasoning, NOT live-validated; kill-switch BRAWL_BUSH_HIDE.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np

from brawlfarm.core import config
from brawlfarm.core.vision import color_fraction

# Unit vector pointing AWAY from each screen edge, in screen coordinates
# (x right, y down — the same frame the joystick swipe vector uses, so an angle
# produced here feeds straight into the existing move swipe).
_AWAY = {
    "top": (0.0, 1.0),  # gas on top -> flee downward
    "bottom": (0.0, -1.0),
    "left": (1.0, 0.0),
    "right": (-1.0, 0.0),
}


def gas_fractions(frame: np.ndarray) -> dict[str, float]:
    """Gas-colored pixel fraction (0..1) per screen-edge band. 4 cheap ROI checks
    using the validated HSV window — see config.GAS_* and tools/probe_gas.py."""
    return {
        name: color_fraction(frame, band, config.GAS_HSV_LO, config.GAS_HSV_HI)
        for name, band in config.GAS_BANDS.items()
    }


class GasTracker:
    """Per-edge hysteresis over the band fractions: an edge becomes gassed at
    >= config.GAS_BAND_ON and clears below config.GAS_BAND_OFF. The corpus shows
    the [OFF, ON) zone is "gas arriving", so the lag is at most a frame or two
    while flicker (a cloud fringe wisping in and out of a band) is eliminated."""

    def __init__(self) -> None:
        self._gassed: set[str] = set()

    def update(self, fractions: dict[str, float]) -> set[str]:
        """Fold one frame's band fractions into the state; returns the (copied)
        current set of gassed edges."""
        for edge, frac in fractions.items():
            if frac >= config.GAS_BAND_ON:
                self._gassed.add(edge)
            elif frac < config.GAS_BAND_OFF:
                self._gassed.discard(edge)
        return set(self._gassed)

    def reset(self) -> None:
        """Forget everything (call at match boundaries — gas state must never
        leak from one match into the next)."""
        self._gassed.clear()


def gas_bias_heading(
    heading: float,
    fractions: dict[str, float],
    gassed: set[str],
    gain: float | None = None,
) -> float:
    """Return a new wander heading biased AWAY from gassed screen edges.

    The caller keeps its random drift (anti-detection); this only ADDS a weighted
    repulsion vector to the drift's unit vector, so the wander stays random while
    gaining a survival gradient:

      v = unit(heading) + gain * sum(fraction[edge] * away[edge] for gassed edges)

    Each edge's weight is its band fraction — the deeper the gas has penetrated,
    the harder the push (urgency scaling, per the research doc). With 3+ edges
    gassed (endgame ring) repulsion would mostly cancel, so instead we head
    straight for the least-gassed direction — the research doc's "strongest pull
    toward the least-gassed direction". Pure math, no I/O: unit-tested offline.
    """
    if not gassed:
        return heading
    if gain is None:
        gain = config.GAS_REPULSION_GAIN
    if len(gassed) >= 3:
        # Endgame: pick the least-gassed edge and head TOWARD it (i.e. away from
        # the deepest gas). The caller's per-move random turn still jitters this
        # frame to frame, and the fractions themselves shift as the gas animates.
        least = min(config.GAS_BANDS, key=lambda e: fractions.get(e, 0.0))
        ax, ay = _AWAY[least]
        return math.atan2(-ay, -ax)
    rx = sum(_AWAY[e][0] * fractions.get(e, 0.0) for e in gassed)
    ry = sum(_AWAY[e][1] * fractions.get(e, 0.0) for e in gassed)
    vx = math.cos(heading) + gain * rx
    vy = math.sin(heading) + gain * ry
    if vx == 0.0 and vy == 0.0:  # exactly cancelled (theoretical) — keep course
        return heading
    return math.atan2(vy, vx)


# --- Phase D: ability buttons --------------------------------------------------


def ready_abilities(frame: np.ndarray) -> dict[str, float]:
    """Which ability buttons are lit with their ready color right now.

    Returns {name: fraction} for each button in config.ABILITY_BUTTONS whose
    ready-color fraction meets its threshold (empty dict = nothing ready). One
    small-ROI color_fraction call per button. The controller owns tapping (with
    a per-button cooldown) — this only reports."""
    out: dict[str, float] = {}
    for name, spec in config.ABILITY_BUTTONS.items():
        frac = color_fraction(frame, spec["region"], spec["hsv_lo"], spec["hsv_hi"])
        if frac >= spec["min_fraction"]:
            out[name] = frac
    return out


# --- Phase B: bush detection + hide / gas-relocation decision -------------------
# CALIBRATED BY REASONING, NOT LIVE-VALIDATED. The P9 corpus had only RED-foliage
# bushes (Kroket); the green window below was measured from a real green-biome
# in-match frame (captures/live_inmatch.png: bush masses read H 60-95 / S >= 140 /
# V ~60-200, gas-window overlap negligible at 111/422 px in a gas-free frame). Map
# themes vary, so the gate is deliberately CONSERVATIVE (a high min-cluster-area and
# saturated-green window): "no bush detected" is the safe, common outcome that
# degrades to the existing random wander. The orchestrator/owner must watch the
# first live sessions; BRAWL_BUSH_HIDE=0 is the one-env-var kill-switch.


@dataclass(frozen=True)
class Bush:
    """A detected green-foliage cluster in FULL-FRAME screen coordinates."""

    cx: int
    cy: int
    area: int  # pixel area in the downscaled mask (relative size, not full-res px)


@dataclass(frozen=True)
class BushAction:
    """The pure decision's output. ``kind`` is one of:
      * "hide"     — steer toward ``target`` (a bush center) and stop/micro-jitter
                     once on top of it
      * "relocate" — gas is closing; move toward ``target`` (a more-central bush)
      * "wander"   — no usable bush / nothing to do -> the existing random drift
    ``target`` is a screen point (None for wander). ``at_target`` is True when the
    self position is already inside the chosen hide bush (the controller then holds
    + micro-jitters instead of swiping)."""

    kind: str
    target: tuple[int, int] | None = None
    at_target: bool = False


def bush_clusters(frame: np.ndarray) -> list[Bush]:
    """Green-foliage clusters in ``frame``, largest first. Downscale by
    config.BUSH_DOWNSCALE, HSV-threshold the saturated-green window
    (config.BUSH_HSV_LO/HI), connected-component the mask, and keep components whose
    (downscaled) area >= config.BUSH_MIN_AREA. Centroids are scaled back to full-frame
    coordinates. Empty list when nothing qualifies (the common, safe case on a
    non-green map). One resize + one inRange + one CC pass — a few ms, negligible
    against the ~370 ms capture."""
    if frame is None or frame.size == 0:
        return []
    f = config.BUSH_DOWNSCALE
    h, w = frame.shape[:2]
    small = cv2.resize(frame, (max(1, w // f), max(1, h // f)), interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(
        hsv,
        np.array(config.BUSH_HSV_LO, np.uint8),
        np.array(config.BUSH_HSV_HI, np.uint8),
    )
    n, _labels, stats, cents = cv2.connectedComponentsWithStats(mask, connectivity=8)
    out: list[Bush] = []
    for i in range(1, n):  # 0 is the background component
        area = int(stats[i, cv2.CC_STAT_AREA])
        if area < config.BUSH_MIN_AREA:
            continue
        cx, cy = cents[i]
        out.append(Bush(cx=int(cx * f), cy=int(cy * f), area=area))
    out.sort(key=lambda b: b.area, reverse=True)
    return out


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def bush_decision(
    clusters: list[Bush],
    self_pos: tuple[int, int],
    frame_size: tuple[int, int],
    gassed: set[str],
    gas_fractions: dict[str, float] | None = None,
) -> BushAction:
    """PURE decision (no frame access, no I/O — unit-tested offline). Given the
    detected bush ``clusters``, the self screen position ``self_pos`` (≈ (690, 440)
    per the research's anchor caveat — it drifts, so all distances are slack), the
    ``frame_size`` (w, h), and the current gas signals, decide what to do:

      * No clusters -> WANDER (the safe default — degrades to today's random drift).
      * Gas is "closing in" — gassed edges on >= config.BUSH_GAS_RELOCATE_EDGES sides,
        OR any gassed edge whose band fraction is within config.BUSH_GAS_PROXIMITY of
        saturating (gas deep in a band ≈ gas near us) — RELOCATE: pick the bush
        nearest the MAP CENTER (gas closes toward center) and head there.
      * Otherwise HIDE: steer to the cluster nearest ``self_pos`` — there is no
        distance cutoff, so a far bush still pulls us into cover over the next few
        moves rather than giving up. If already within config.BUSH_AT_TARGET_PX of
        it, signal at_target (the controller holds + micro-jitters there).

    This NEVER decides to attack or flee a fight — it only biases idle movement; the
    controller keeps its attack/disconnect/survival reactions on top. The
    relocation-attempt CAP is enforced by the CALLER (controller, per gas event)."""
    gas_fractions = gas_fractions or {}
    w, h = frame_size
    center = (w / 2.0, h / 2.0)

    if not clusters:
        return BushAction("wander")

    closing = len(gassed) >= config.BUSH_GAS_RELOCATE_EDGES or any(
        gas_fractions.get(e, 0.0) >= config.BUSH_GAS_PROXIMITY for e in gassed
    )
    if closing:
        # Relocate toward the map center: the bush whose centroid is closest to the
        # screen center is the most "inward" cover as the ring shrinks.
        target = min(clusters, key=lambda b: _dist((b.cx, b.cy), center))
        return BushAction("relocate", target=(target.cx, target.cy))

    # Hide: steer to the bush nearest self, however far — heading toward it pulls
    # us into cover over the next few moves.
    nearest = min(clusters, key=lambda b: _dist((b.cx, b.cy), self_pos))
    d = _dist((nearest.cx, nearest.cy), self_pos)
    at = d <= config.BUSH_AT_TARGET_PX
    return BushAction("hide", target=(nearest.cx, nearest.cy), at_target=at)
