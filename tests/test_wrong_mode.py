"""Mode-verify hardening (round 6, legacy owner-instructions note, not ported).

The two live "wrong_mode" firings today both RECOVERED — the mode banner was caught
mid-animation, not a real switch. So the at-menu mode check now:
  1. DOUBLE-CONFIRMS — a first miss waits + re-captures; a transient miss (re-check
     hits) fires NOTHING (just a debug log);
  2. on a CONFIRMED miss logs the template score + a diagnostic shot, attempts
     recovery, and emits a wrong_mode event with score + recovered (even when
     recovery succeeds);
  3. on nav failure stops with the HONEST reason "mode_verify_failed" (not the
     misleading "wrong_mode").

These drive Controller.phase_at_menu through fake vision sequences — no adb taps,
no real templates: trio_showdown_score and navigate_to_trio_showdown are stubbed,
and every gate BEFORE the mode check is short-circuited so the check is reached.
"""

from brawlfarm.core import controller as ctrlmod
from brawlfarm.core import quests, states
from brawlfarm.core.controller import Controller
from brawlfarm.core.states import State

SCREEN = object()  # opaque sentinel — every vision call is stubbed


class _DL:
    def __init__(self):
        self.events = []

    def event(self, etype, **fields):
        self.events.append((etype, fields))


def _ctrl(monkeypatch):
    """Bare controller positioned right at the mode-verify check: all earlier at-menu
    gates are no-ops, the soft-stop says 'keep running', and nothing else fires."""
    c = Controller.__new__(Controller)
    c.running = True
    c.dl = _DL()
    c.log = lambda *a, **k: None
    # the startup-task feature flags are OFF -> each gate short-circuits, so the
    # mode-verify check is the first thing reached after the soft-stop check
    c.dnd = c.select_brawler = False
    c._dnd_done = True
    c._select_brawler_done = True
    c._reselect_pending = False
    c._mega_quest_streak = 0
    c.shots = []
    # neutralize the gates the check sits behind
    monkeypatch.setattr(c, "maybe_snapshot_trophies", lambda: None)
    monkeypatch.setattr(c, "maybe_log_battlelog", lambda: None)
    monkeypatch.setattr(c, "_soft_stop_reason", lambda: None)
    monkeypatch.setattr(quests, "quests_button_has_new", lambda s: False)
    monkeypatch.setattr(ctrlmod.adb, "tap", lambda *a, **k: None)
    monkeypatch.setattr(ctrlmod.time, "sleep", lambda *_a: None)  # no real wait
    # capture event shots without touching disk
    monkeypatch.setattr(c, "event_shot", lambda screen, tag: c.shots.append(tag), raising=False)
    # capture stop reasons without running the real stop side effects
    c.stopped_with = []
    monkeypatch.setattr(c, "stop", lambda reason: (c.shots and None, c.stopped_with.append(reason)))
    return c


def _seq(monkeypatch, *results):
    """Feed trio_showdown_score a sequence of (selected, score) tuples; the controller
    re-captures via adb.screencap between calls, so just hand back SCREEN each time."""
    it = iter(results)
    monkeypatch.setattr(states, "trio_showdown_score", lambda s: next(it))
    monkeypatch.setattr(ctrlmod.adb, "screencap", lambda: SCREEN)


def test_hit_first_pass_is_normal(monkeypatch):
    """Mode selected on the first check -> PLAY pressed, no event, no shot."""
    c = _ctrl(monkeypatch)
    _seq(monkeypatch, (True, 0.97))
    monkeypatch.setattr(c, "tap", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(c, "set_phase", lambda *a, **k: None, raising=False)
    c.phase_at_menu(SCREEN, State.MENU)
    assert not any(e == "wrong_mode" for e, _ in c.dl.events)
    assert c.shots == []
    assert c.stopped_with == []


def test_transient_miss_then_hit_fires_nothing(monkeypatch):
    """miss -> (wait, re-capture) -> hit = a transient miss: NO event, NO shot, NO
    recovery attempt, NO stop. This is the false-alarm case the owner saw."""
    c = _ctrl(monkeypatch)
    _seq(monkeypatch, (False, 0.40), (True, 0.95))
    nav = {"n": 0}
    monkeypatch.setattr(
        c,
        "navigate_to_trio_showdown",
        lambda: nav.__setitem__("n", nav["n"] + 1) or True,
        raising=False,
    )
    c.phase_at_menu(SCREEN, State.MENU)
    assert not any(e == "wrong_mode" for e, _ in c.dl.events)
    assert c.shots == []
    assert c.stopped_with == []
    assert nav["n"] == 0  # never tried to navigate


def test_confirmed_miss_recovers_logs_event_and_shot(monkeypatch):
    """miss -> miss = confirmed. Recovery SUCCEEDS, but we still log the event
    (score + recovered=True) and save a diagnostic shot; no stop."""
    c = _ctrl(monkeypatch)
    _seq(monkeypatch, (False, 0.42), (False, 0.39))
    monkeypatch.setattr(c, "navigate_to_trio_showdown", lambda: True, raising=False)
    c.phase_at_menu(SCREEN, State.MENU)
    ev = [f for e, f in c.dl.events if e == "wrong_mode"]
    assert len(ev) == 1
    assert ev[0]["recovered"] is True
    assert ev[0]["score"] == 0.39  # the CONFIRMED (second) frame's score
    assert "wrong_mode" in c.shots
    assert c.stopped_with == []


def test_confirmed_miss_nav_fails_stops_with_honest_reason(monkeypatch):
    """miss -> miss, recovery FAILS -> stop reason is 'mode_verify_failed' (NOT the
    misleading 'wrong_mode'); event recovered=False; shot saved."""
    c = _ctrl(monkeypatch)
    _seq(monkeypatch, (False, 0.30), (False, 0.28))
    monkeypatch.setattr(c, "navigate_to_trio_showdown", lambda: False, raising=False)
    c.phase_at_menu(SCREEN, State.MENU)
    ev = [f for e, f in c.dl.events if e == "wrong_mode"]
    assert len(ev) == 1 and ev[0]["recovered"] is False
    assert "wrong_mode" in c.shots
    assert c.stopped_with == ["mode_verify_failed"]
