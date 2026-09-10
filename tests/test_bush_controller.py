"""Controller wiring for Phase B (bush-hide + gas relocation, r8).

Verifies the playing-phase helpers drive the joystick correctly and that EVERY
failure path degrades to the existing wander (the fail-safe contract): no bush ->
wander, detector exception -> wander, relocation cap -> wander. adb.swipe is
stubbed so no input is sent; we assert on the decisions, not pixels.
"""

import math

from brawlfarm.core import config
from brawlfarm.core import controller as controller_mod
from brawlfarm.core import match_vision as mv
from brawlfarm.core.controller import Controller


class _DL:
    def __init__(self):
        self.events = []

    def event(self, etype, **fields):
        self.events.append((etype, fields))


def _ctrl():
    c = Controller.__new__(Controller)
    c.dl = _DL()
    c._gas_edges = set()
    c._bush_jitter_at = 0.0
    c._relocations = 0
    c._bush_logged = None
    c._heading = 0.0
    c.logs = []
    c.log = lambda m: c.logs.append(m)
    return c


def _stub_swipe(monkeypatch):
    calls = []
    monkeypatch.setattr(controller_mod.adb, "swipe", lambda *a, **k: calls.append(a))
    return calls


# --- _bush_action: gate + fail-open ----------------------------------------------


def test_bush_action_off_when_kill_switch(monkeypatch):
    monkeypatch.setattr(config, "BUSH_HIDE", False)
    c = _ctrl()
    assert c._bush_action(object(), None) is None  # never even calls the detector


def test_bush_action_detector_exception_degrades_to_none(monkeypatch):
    monkeypatch.setattr(config, "BUSH_HIDE", True)

    def boom(_frame):
        raise RuntimeError("cv exploded")

    monkeypatch.setattr(mv, "bush_clusters", boom)
    c = _ctrl()
    assert c._bush_action(object(), None) is None
    assert any(e == "bush_error" for e, _ in c.dl.events)


def test_bush_action_passes_clusters_and_gas(monkeypatch):
    monkeypatch.setattr(config, "BUSH_HIDE", True)
    near = mv.Bush(config.BUSH_SELF_POS[0] + 100, config.BUSH_SELF_POS[1], 500)
    monkeypatch.setattr(mv, "bush_clusters", lambda _f: [near])
    c = _ctrl()
    c._gas_edges = set()
    a = c._bush_action(object(), {"top": 0.0})
    assert a.kind == "hide"
    assert a.target == (near.cx, near.cy)


# --- _steer_to_bush: hide / approach / relocate / cap ----------------------------


def test_steer_approach_swipes_toward_bush(monkeypatch):
    calls = _stub_swipe(monkeypatch)
    c = _ctrl()
    target = (config.BUSH_SELF_POS[0] + 200, config.BUSH_SELF_POS[1])  # to the right
    c._steer_to_bush(mv.BushAction("hide", target=target, at_target=False), now=100.0)
    assert len(calls) == 1
    # heading points right (toward +x): cos(heading) > 0
    assert math.cos(c._heading) > 0
    assert "bush_approach" == c._bush_logged


def test_steer_hide_at_target_jitters_then_holds(monkeypatch):
    calls = _stub_swipe(monkeypatch)
    c = _ctrl()
    target = (config.BUSH_SELF_POS[0] + 10, config.BUSH_SELF_POS[1])
    act = mv.BushAction("hide", target=target, at_target=True)
    # first call (jitter timer cold) -> one micro-jitter swipe + a bush_hide event
    c._steer_to_bush(act, now=100.0)
    assert len(calls) == 1
    assert any(e == "bush_hide" for e, _ in c.dl.events)
    # immediately again (interval not elapsed) -> NO new swipe (holds position)
    c._steer_to_bush(act, now=100.5)
    assert len(calls) == 1
    # well past the max interval -> jitters again
    c._steer_to_bush(act, now=100.0 + config.BUSH_JITTER_MAX_INTERVAL + 1)
    assert len(calls) == 2
    # bush_hide logged only once (sparse logging)
    assert sum(1 for e, _ in c.dl.events if e == "bush_hide") == 1


def test_steer_relocate_moves_and_caps(monkeypatch):
    calls = _stub_swipe(monkeypatch)
    c = _ctrl()
    target = (config.SCREEN_W // 2, config.SCREEN_H // 2)
    act = mv.BushAction("relocate", target=target)
    # spend the whole relocation budget
    for i in range(config.BUSH_MAX_RELOCATIONS):
        c._steer_to_bush(act, now=100.0 + i)
    assert c._relocations == config.BUSH_MAX_RELOCATIONS
    assert len(calls) == config.BUSH_MAX_RELOCATIONS
    assert any(e == "gas_relocate" for e, _ in c.dl.events)
    # over the cap -> wander fallback (still swipes, but _relocations does not grow)
    c._steer_to_bush(act, now=200.0)
    assert c._relocations == config.BUSH_MAX_RELOCATIONS
    assert len(calls) == config.BUSH_MAX_RELOCATIONS + 1  # the wander move


def test_wander_move_always_swipes(monkeypatch):
    calls = _stub_swipe(monkeypatch)
    c = _ctrl()
    c._wander_move(None)
    assert len(calls) == 1


def test_heading_to_bearing():
    c = _ctrl()
    sx, sy = config.BUSH_SELF_POS
    assert math.isclose(c._heading_to((sx + 100, sy)), 0.0, abs_tol=1e-9)  # due right
    assert math.isclose(
        c._heading_to((sx, sy + 100)), math.pi / 2, abs_tol=1e-9
    )  # downward (screen +y)
