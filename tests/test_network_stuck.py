"""Network-stuck end-screen rails (owner-reported live, 2026-06-10).

A short disconnect can wedge the game on the END of a Showdown match with dead
buttons. The frames keep animating (freeze detection blind) and the results
branch used to RESET the stuck counter on every tap — an unbounded tap loop
with healthy heartbeats. These tests pin the two new rails:

  1. RESULTS_STUCK_TAPS consecutive results-advance taps without leaving the
     RESULTS state escalate to recover("results_stuck") — whose force-stop is
     the only thing that un-wedges the game (a plain HOME resumes back into
     the stuck screen; verified live).
  2. recover() with a soft stop already pending stops (game closes, account
     offline) instead of relaunching a wedged game back ONLINE into what
     should be its scheduled break.

All offline: Controller.__new__ + minimal attrs (the test_recalib.py pattern).
"""

from __future__ import annotations

import time

from brawlfarm.core import controller as controller_mod
from brawlfarm.core.controller import RESULTS_STUCK_TAPS, Controller
from brawlfarm.core.states import State


class _DL:
    def __init__(self):
        self.events = []

    def event(self, etype, **fields):
        self.events.append((etype, fields))


def _ctrl(monkeypatch):
    c = Controller.__new__(Controller)  # skip __init__ (ApiClient/DataLog/adb)
    c.dl = _DL()
    c.phase = "returning"
    c.phase_started = time.monotonic()
    c.games_played = 0
    c.unknown_clears = 0
    c._results_taps = 0
    c.recovery_attempts = 0
    c.disconnect_count = 0
    c.popup_count = 0
    c._stop_flag_seen = False
    c._soft_stop_since = None
    c.max_games = None
    c.max_minutes = None
    c.start = time.monotonic()
    c.running = True
    c.recovered = []
    monkeypatch.setattr(Controller, "recover", lambda self, reason: self.recovered.append(reason))
    monkeypatch.setattr(Controller, "advance_results", lambda self, screen: None)
    monkeypatch.setattr(Controller, "_write_status", lambda self: None)
    monkeypatch.setattr(Controller, "log", lambda self, msg: None)
    return c


def test_stuck_results_escalates_to_recover(monkeypatch):
    c = _ctrl(monkeypatch)
    for _ in range(RESULTS_STUCK_TAPS):
        c.phase_returning(screen=None, state=State.RESULTS)
    assert c.recovered == []  # within budget: still tapping normally
    c.phase_returning(screen=None, state=State.RESULTS)
    assert c.recovered == ["results_stuck"]


def test_results_counter_resets_when_results_actually_clear(monkeypatch):
    """Reaching the menu (set_phase) resets the budget — normal 2-3 tap results
    flows can never accumulate into a false escalation across games."""
    c = _ctrl(monkeypatch)
    for _ in range(RESULTS_STUCK_TAPS - 1):
        c.phase_returning(screen=None, state=State.RESULTS)
    c.phase_returning(screen=None, state=State.MENU)  # results cleared
    assert c.phase == "at_menu" and c._results_taps == 0
    c.phase = "returning"
    for _ in range(RESULTS_STUCK_TAPS):
        c.phase_returning(screen=None, state=State.RESULTS)
    assert c.recovered == []  # fresh budget after the reset


def test_recover_stops_instead_of_relaunching_when_stop_pending(monkeypatch):
    """The 2026-06-10 morning failure shape: a wedged end screen + a pending
    scheduler stop must take the game OFFLINE, not relaunch it into the break."""
    c = _ctrl(monkeypatch)
    monkeypatch.undo()  # restore the real recover
    monkeypatch.setattr(Controller, "log", lambda self, msg: None)
    monkeypatch.setattr(Controller, "event_shot", lambda self, *a, **k: None)
    monkeypatch.setattr(controller_mod.adb, "screencap", lambda: None)
    stopped = []
    monkeypatch.setattr(Controller, "stop", lambda self, reason: stopped.append(reason))
    relaunched = []
    monkeypatch.setattr(controller_mod.adb, "force_stop", lambda: relaunched.append("force_stop"))
    monkeypatch.setattr(controller_mod.adb, "launch_app", lambda: relaunched.append("launch"))
    c._stop_flag_seen = True  # scheduler/Discord asked us to stop
    c.recovery_attempts = 0
    c.dl = _DL()
    c.recover("results_stuck")
    # Review #60 MINOR: the reason names WHICH soft stop was pending too.
    assert stopped == ["recover_while_stopping:stop_flag:results_stuck"]
    assert relaunched == []  # the wedged game is NOT brought back online


def test_recover_still_relaunches_mid_session(monkeypatch):
    """No pending stop -> recover keeps its normal force-stop + relaunch flow
    (the mid-match variant heals through MATCH_TIMEOUT -> this path)."""
    c = _ctrl(monkeypatch)
    monkeypatch.undo()
    monkeypatch.setattr(Controller, "log", lambda self, msg: None)
    monkeypatch.setattr(Controller, "event_shot", lambda self, *a, **k: None)
    monkeypatch.setattr(Controller, "set_phase", lambda self, name: None)
    monkeypatch.setattr(controller_mod.adb, "screencap", lambda: None)
    monkeypatch.setattr(controller_mod.time, "sleep", lambda s: None)
    calls = []
    monkeypatch.setattr(controller_mod.adb, "go_home", lambda: calls.append("home"))
    monkeypatch.setattr(controller_mod.adb, "force_stop", lambda: calls.append("force_stop"))
    monkeypatch.setattr(controller_mod.adb, "launch_app", lambda: calls.append("launch"))
    c.dl = _DL()
    c.last_change = 0.0
    c.recover("results_stuck")
    assert calls == ["home", "force_stop", "launch"]


def test_counter_survives_flicker_without_phase_change(monkeypatch):
    """Review #60 pin: the wedge FLICKERS — UNKNOWN/transition frames interleave
    with RESULTS frames without any phase change. Only a real set_phase may reset
    the budget; a future "reset on any non-RESULTS frame" refactor must fail here
    or the rail dies exactly on the screen it exists for."""
    c = _ctrl(monkeypatch)
    for _ in range(RESULTS_STUCK_TAPS - 2):
        c.phase_returning(screen=None, state=State.RESULTS)
    c.unknown_clears += 3  # what interleaved UNKNOWN frames do; no set_phase call
    assert c._results_taps == RESULTS_STUCK_TAPS - 2  # untouched by the flicker
    for _ in range(3):
        c.phase_returning(screen=None, state=State.RESULTS)
    assert c.recovered == ["results_stuck"]
