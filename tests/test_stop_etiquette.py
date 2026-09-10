"""Tests for the /stop etiquette (discord-v3-refinements.md A3): a USER/OWNER-
initiated stop (the stop.flag path) best-effort turns the in-game DND OFF at the
menu before the force-stop; scheduled cap stops (max_games / max_minutes) and the
not-at-a-menu hard backstop never do — and a DND-off failure never blocks the stop.
"""

import time

from brawlfarm.core import adb, config, settings
from brawlfarm.core.controller import Controller


class _DL:
    def __init__(self):
        self.events = []

    def event(self, etype, **fields):
        self.events.append((etype, fields))


def _ctrl():
    c = Controller.__new__(Controller)  # skip __init__ (ApiClient/DataLog/adb)
    c.running = True
    c.games_played = 3
    c.start = time.monotonic()
    c._recap_done = True  # recap already logged; stop()'s _log_recap is a no-op
    c.dl = _DL()
    return c


def _wire(monkeypatch):
    """Record remove_dnd / force_stop calls; never touch adb or the screen."""
    calls = {"remove_dnd": 0, "force_stop": 0}
    monkeypatch.setattr(
        settings,
        "remove_dnd",
        lambda log=print: (
            calls.__setitem__("remove_dnd", calls["remove_dnd"] + 1),
            {"invites_unmuted": True},
        )[1],
    )
    monkeypatch.setattr(
        adb,
        "force_stop",
        lambda: calls.__setitem__("force_stop", calls["force_stop"] + 1),
    )
    monkeypatch.setattr(config, "DND_OFF_ON_STOP", True)
    monkeypatch.setattr(config, "CLOSE_GAME_ON_STOP", True)
    return calls


def test_stop_flag_turns_dnd_off_before_force_stop(monkeypatch):
    calls = _wire(monkeypatch)
    c = _ctrl()
    c.stop("stop_flag")
    assert c.running is False
    assert calls["remove_dnd"] == 1
    assert calls["force_stop"] == 1
    assert any(e == "dnd_off" for e, _ in c.dl.events)


def test_scheduled_cap_stops_do_not_toggle_dnd(monkeypatch):
    for reason in ("max_games", "max_minutes"):
        calls = _wire(monkeypatch)
        c = _ctrl()
        c.stop(reason)
        assert c.running is False
        assert calls["remove_dnd"] == 0, reason
        assert calls["force_stop"] == 1, reason


def test_hard_backstop_does_not_toggle_dnd(monkeypatch):
    # stop_flag_hard fires when the soft stop is >10 min overdue — we are NOT at
    # a menu (wedged recovery / endless match), so the DND nav must not run
    calls = _wire(monkeypatch)
    c = _ctrl()
    c.stop("stop_flag_hard")
    assert calls["remove_dnd"] == 0
    assert calls["force_stop"] == 1


def test_dnd_off_failure_never_blocks_the_stop(monkeypatch):
    calls = _wire(monkeypatch)

    def boom(log=print):
        raise RuntimeError("screen verify failed mid-nav")

    monkeypatch.setattr(settings, "remove_dnd", boom)
    c = _ctrl()
    c.stop("stop_flag")  # must not raise
    assert c.running is False
    assert calls["force_stop"] == 1  # game still closed
    assert any(e == "dnd_off_error" for e, _ in c.dl.events)


def test_kill_switch_disables_dnd_off(monkeypatch):
    calls = _wire(monkeypatch)
    monkeypatch.setattr(config, "DND_OFF_ON_STOP", False)
    c = _ctrl()
    c.stop("stop_flag")
    assert calls["remove_dnd"] == 0
    assert calls["force_stop"] == 1


def test_stop_is_idempotent(monkeypatch):
    calls = _wire(monkeypatch)
    c = _ctrl()
    c.stop("stop_flag")
    c.stop("stop_flag")  # second call: already stopped, no double DND nav
    assert calls["remove_dnd"] == 1
    assert calls["force_stop"] == 1
