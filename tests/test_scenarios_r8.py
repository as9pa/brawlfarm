"""Self-heal scenarios (r8, docs/future-plans/scenarios.md): the brawler-unlock
CEREMONY screens, the CHOOSE-A-BRAWLER chooser, and the in-match server-error modal.

Two layers:
  * DETECTION (states.green_cta / is_choose_a_brawler / in_match_modal)
    runs against REAL pixels — small crops of tonight's live 1600x900 frames committed
    under tests/fixtures/, composited back onto a black full-frame canvas at their true
    absolute coordinates (the detectors index full-frame regions). This exercises the
    color/structure gates exactly as they run live, without committing the 0.5-1 MB
    full captures (which are gitignored).
  * HANDLER wiring (Controller._handle_ceremony / _try_dismiss_ladder + the phase_playing
    modal scan) runs against a bare Controller with all I/O stubbed — it asserts WHICH
    coordinate is tapped (never TRY), the bounded budget, and the events emitted.
"""

from __future__ import annotations

import pathlib

import cv2
import numpy as np

from brawlfarm.core import config, states
from brawlfarm.core import controller as ctrlmod
from brawlfarm.core.controller import Controller
from brawlfarm.core.states import State

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


def _canvas() -> np.ndarray:
    return np.zeros((config.SCREEN_H, config.SCREEN_W, 3), dtype=np.uint8)


def _paste(name: str, x1: int, y1: int) -> np.ndarray:
    """Composite a fixture crop onto a black full-frame canvas at (x1, y1)."""
    crop = cv2.imread(str(FIXTURES / name))
    assert crop is not None, f"missing fixture {name}"
    f = _canvas()
    h, w = crop.shape[:2]
    f[y1 : y1 + h, x1 : x1 + w] = crop
    return f


# --- detection (real pixels) ---------------------------------------------------


def test_green_cta_letsgo_lands_in_the_right_third():
    # KAZE unlock: the green LET'S GO button sits bottom-RIGHT.
    f = _paste("r8_cta_letsgo_band.png", 0, 780)
    cta = states.green_cta(f)
    assert cta is not None and cta[0] > 1066  # right third
    assert states.is_choose_a_brawler(f) is False


def test_green_cta_gotit_lands_in_the_center_third():
    # ULTRA TRAIT: the green GOT IT button sits bottom-CENTER.
    f = _paste("r8_cta_gotit_band.png", 0, 780)
    cta = states.green_cta(f)
    assert cta is not None and 533 <= cta[0] <= 1066


def test_choose_a_brawler_title_detected_without_a_cta():
    # CHOOSE A BRAWLER, no card picked: the title reads, no green CTA yet (the
    # controller handles it with its own center-card tap).
    f = _paste("r8_choose_title.png", 300, 10)
    assert states.is_choose_a_brawler(f) is True
    assert states.green_cta(f) is None


def test_choose_a_brawler_with_a_selected_card_shows_the_green_choose():
    # Card selected: the green CHOOSE button is up; the title band carries
    # CHOOSE/SWITCH so the controller routes it through the chooser path.
    f = _paste("r8_choose_cta_band.png", 0, 780)
    f[10:160, 300:1300] = cv2.imread(str(FIXTURES / "r8_choose_title.png"))
    assert states.green_cta(f) is not None
    assert states.is_choose_a_brawler(f) is True


def test_no_green_cta_on_a_bare_choose_band():
    # The unselected CHOOSE band alone has no green CTA (the 3 cards, no button).
    f = _paste("r8_choose_nocta_band.png", 0, 780)
    assert states.green_cta(f) is None


def test_in_match_modal_detected_on_the_gray_body():
    f = _paste("r8_modal_body.png", 560, 320)
    assert states.in_match_modal(f) is True


def test_in_match_modal_quiet_on_a_colorful_match_scene():
    # The same modal-body region filled with real (colorful, high-saturation) map
    # pixels must NOT read as a modal — no false dismiss mid-match.
    f = _paste("r8_match_clean_body.png", 560, 320)
    assert states.in_match_modal(f) is False


def test_in_match_modal_quiet_on_an_empty_frame():
    assert states.in_match_modal(_canvas()) is False


# --- handler wiring (stubbed Controller) ---------------------------------------


class _DL:
    def __init__(self):
        self.events = []

    def event(self, etype, **fields):
        self.events.append((etype, fields))


def _ctrl(monkeypatch):
    c = Controller.__new__(Controller)
    c.dl = _DL()
    c.log = lambda *a, **k: None
    c.phase = "returning"
    c._ceremony_count = 0
    c._dismiss_tried = False
    c.taps = []
    monkeypatch.setattr(
        c, "tap", lambda point, kind=None: c.taps.append((point, kind)), raising=False
    )
    monkeypatch.setattr(c, "event_shot", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(c, "set_phase", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(ctrlmod.time, "sleep", lambda *_a: None)
    return c


def test_handle_ceremony_taps_the_detected_green_cta(monkeypatch):
    c = _ctrl(monkeypatch)
    monkeypatch.setattr(states, "is_choose_a_brawler", lambda s: False)
    monkeypatch.setattr(states, "green_cta", lambda s: (1380, 822))
    assert c._handle_ceremony(object()) is True
    assert c.taps == [((1380, 822), "ceremony_cta")]
    assert c._ceremony_count == 1
    assert any(e == "ceremony_cleared" for e, _ in c.dl.events)


def test_handle_choose_no_card_taps_center_card_never_try(monkeypatch):
    c = _ctrl(monkeypatch)
    monkeypatch.setattr(states, "is_choose_a_brawler", lambda s: True)
    monkeypatch.setattr(states, "green_cta", lambda s: None)  # no card picked yet
    assert c._handle_ceremony(object()) is True
    assert c.taps == [(config.CHOOSE_BRAWLER_CENTER_CARD, "choose_card")]


def test_handle_choose_selected_taps_choose_button_not_the_detected_third(monkeypatch):
    # When a card is selected the green CHOOSE is up; we confirm via the CONFIGURED
    # CHOOSE coord (clear of the blue TRY beside it), NOT the detected green third.
    c = _ctrl(monkeypatch)
    monkeypatch.setattr(states, "is_choose_a_brawler", lambda s: True)
    monkeypatch.setattr(states, "green_cta", lambda s: (800, 822))  # green present
    assert c._handle_ceremony(object()) is True
    assert c.taps == [(config.CHOOSE_BRAWLER_CONFIRM, "choose_confirm")]
    assert config.CHOOSE_BRAWLER_CONFIRM != (800, 822)  # not the detected third


def test_handle_ceremony_noop_when_nothing_present(monkeypatch):
    c = _ctrl(monkeypatch)
    monkeypatch.setattr(states, "is_choose_a_brawler", lambda s: False)
    monkeypatch.setattr(states, "green_cta", lambda s: None)
    assert c._handle_ceremony(object()) is False
    assert c.taps == []


def test_dismiss_ladder_prefers_the_ceremony_then_close_x(monkeypatch):
    c = _ctrl(monkeypatch)
    # ceremony present -> handled first, close_x never consulted
    monkeypatch.setattr(states, "is_choose_a_brawler", lambda s: False)
    monkeypatch.setattr(states, "green_cta", lambda s: (800, 822))
    called = {"find": 0}
    monkeypatch.setattr(
        ctrlmod.vision, "find", lambda *a, **k: called.__setitem__("find", 1)
    )
    assert c._try_dismiss_ladder(object()) is True
    assert called["find"] == 0  # short-circuited at the ceremony check


def test_dismiss_ladder_bounded_by_ceremony_budget(monkeypatch):
    c = _ctrl(monkeypatch)
    c._ceremony_count = config.CEREMONY_MAX_SCREENS  # budget exhausted
    monkeypatch.setattr(states, "is_choose_a_brawler", lambda s: True)
    monkeypatch.setattr(states, "green_cta", lambda s: None)
    monkeypatch.setattr(ctrlmod.vision, "find", lambda *a, **k: None)
    monkeypatch.setattr(ctrlmod.vision, "find_text", lambda *a, **k: None)
    # ceremony budget gone AND no close_x/proceed/CONTINUE -> ladder does nothing
    assert c._try_dismiss_ladder(object()) is False


# --- phase_playing in-match modal scan -----------------------------------------


def _playing_ctrl(monkeypatch):
    c = Controller.__new__(Controller)
    c.dl = _DL()
    c.log = lambda *a, **k: None
    c.phase = "playing"
    c.phase_started = 0.0
    c._playing_modal_i = 0
    c.taps = []
    # move/attack state: gaps far in the future so the joystick/attack blocks that run
    # AFTER the modal scan don't fire (we're only exercising the scan here).
    c.last_move = c.last_attack = 1e9
    c._move_gap = c._attack_gap = 1e9
    c._heading = 0.0
    monkeypatch.setattr(
        c, "tap", lambda point, kind=None: c.taps.append((point, kind)), raising=False
    )
    monkeypatch.setattr(c, "event_shot", lambda *a, **k: None, raising=False)
    c.set_phase_calls = []
    monkeypatch.setattr(
        c, "set_phase", lambda name: c.set_phase_calls.append(name), raising=False
    )
    monkeypatch.setattr(ctrlmod.time, "sleep", lambda *_a: None)
    # huge MATCH_TIMEOUT headroom (phase_started=0, monotonic is large) would trip the
    # timeout; stub monotonic to a small value so we reach the modal scan.
    monkeypatch.setattr(ctrlmod.time, "monotonic", lambda: 1.0)
    # neutralize the gas/move/attack machinery that runs after the modal scan
    monkeypatch.setattr(config, "GAS_AWARE", False)
    monkeypatch.setattr(config, "ABILITY_BUTTONS_ENABLED", False)
    monkeypatch.setattr(ctrlmod.adb, "swipe", lambda *a, **k: None)
    return c


def test_playing_modal_scan_taps_ok_and_returns(monkeypatch):
    c = _playing_ctrl(monkeypatch)
    monkeypatch.setattr(states, "in_match_modal", lambda s: True)
    # advance to the Nth iteration so the throttled scan fires
    c._playing_modal_i = config.INGAME_MODAL_CHECK_EVERY - 1
    c.phase_playing(object(), State.IN_MATCH)
    assert (config.INGAME_MODAL_OK_BUTTON, "ingame_modal_ok") in c.taps
    assert "returning" in c.set_phase_calls
    assert any(e == "ingame_modal_cleared" for e, _ in c.dl.events)


def test_playing_modal_scan_throttled_off_cadence(monkeypatch):
    c = _playing_ctrl(monkeypatch)
    seen = {"n": 0}
    monkeypatch.setattr(
        states,
        "in_match_modal",
        lambda s: seen.__setitem__("n", seen["n"] + 1) or False,
    )
    c._playing_modal_i = 0  # first iteration -> 1 % EVERY != 0, scan skipped
    c.phase_playing(object(), State.IN_MATCH)
    assert seen["n"] == 0  # the gate wasn't even evaluated this iteration
