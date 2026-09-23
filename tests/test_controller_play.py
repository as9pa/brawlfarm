"""The farm loop's shadow-session wiring: the tick, the rows and the close.

With `shadow` off the controller builds nothing and writes nothing, so a worker that
never asked for the play model never pays for it. With it on, the rows the session
returns are written from the controller thread in the order it returned them, and one
failure anywhere in the path turns shadow off for the rest of the process.

Like tests/test_controller_questpick.py these drive the controller's methods directly:
the object is built without __init__ (no adb, no API, no DataLog), so the inputs are
exactly the config flag and the session stub.
"""

import subprocess
import sys

import pytest

from brawlfarm.core import config
from brawlfarm.core.controller import Controller
from brawlfarm.core.states import State


class _DL:
    """Event-recording stand-in for DataLog (no disk writes)."""

    def __init__(self):
        self.events = []

    def event(self, etype, **fields):
        self.events.append((etype, fields))


class _Session:
    """PlaySession stand-in: returns canned rows and records the ticks it saw."""

    def __init__(self, rows=None, close_rows=None, boom=False):
        self.rows = rows or []
        self.close_rows = close_rows or []
        self.boom = boom
        self.ticks = []
        self.closed = 0

    def observe(self, state, phase):
        if self.boom:
            raise RuntimeError("shadow blew up")
        self.ticks.append((state, phase))
        return self.rows

    def close(self):
        self.closed += 1
        if self.boom:
            raise RuntimeError("shadow blew up")
        return self.close_rows


def _ctrl(play=None):
    """A controller mid-match, with the shadow attributes __init__ sets."""
    c = Controller.__new__(Controller)  # skip __init__ (ApiClient/DataLog/adb)
    c.dl = _DL()
    c.logs = []
    c.log = c.logs.append
    c.phase = "playing"
    c.play = play
    c._play_off = False
    return c


def test_shadow_off_builds_nothing_and_writes_nothing(monkeypatch) -> None:
    monkeypatch.setattr(config, "PLAY_SHADOW", False)
    c = _ctrl()
    c._play_observe(State.IN_MATCH)
    assert c._play_shadow_on() is False
    assert c.play is None  # the session (and the play import) never happened
    assert c.dl.events == []
    assert c.logs == []


def test_shadow_on_builds_the_session_once(monkeypatch) -> None:
    monkeypatch.setattr(config, "PLAY_SHADOW", True)
    built = []

    class _Factory:
        def __init__(self):
            built.append(self)
            self.ticks = []

        def observe(self, state, phase):
            self.ticks.append((state, phase))
            return []

    monkeypatch.setattr("brawlfarm.play.session.PlaySession", _Factory)
    c = _ctrl()
    c._play_observe(State.IN_MATCH)
    c._play_observe(State.MENU)
    assert len(built) == 1
    assert built[0].ticks == [(State.IN_MATCH, "playing"), (State.MENU, "playing")]
    assert c.play is built[0]


def test_the_rows_reach_the_datalog_in_order(monkeypatch) -> None:
    monkeypatch.setattr(config, "PLAY_SHADOW", True)
    rows = [
        ("play_on", {"model": "play.onnx", "provider": "CPUExecutionProvider", "smoke": False}),
        ("play_fallback", {"reason": "no_model"}),
    ]
    session = _Session(rows=rows)
    c = _ctrl(session)
    c._play_observe(State.IN_MATCH)
    assert c.dl.events == rows
    assert session.ticks == [(State.IN_MATCH, "playing")]


def test_a_raising_session_turns_shadow_off_after_one_line(monkeypatch) -> None:
    monkeypatch.setattr(config, "PLAY_SHADOW", True)
    session = _Session(boom=True)
    c = _ctrl(session)
    c._play_observe(State.IN_MATCH)  # must not reach the loop
    c._play_observe(State.IN_MATCH)
    assert c._play_off is True
    assert len(c.logs) == 1
    assert "shadow blew up" in c.logs[0]
    assert c.dl.events == []


def test_the_close_drains_the_summary_rows(monkeypatch) -> None:
    monkeypatch.setattr(config, "PLAY_SHADOW", True)
    rows = [("play_summary", {"frames": 12, "fps": 4.9})]
    session = _Session(close_rows=rows)
    c = _ctrl(session)
    c._play_close()
    assert session.closed == 1
    assert c.dl.events == rows


def test_the_close_lets_its_caller_swallow_the_failure() -> None:
    c = _ctrl(_Session(boom=True))
    with pytest.raises(RuntimeError):  # _play_shutdown owns the try/except
        c._play_close()


# --- the shutdown run()'s finally calls ---------------------------------------
#
# tests/test_preview.py drives the real loop on a controller built without __init__, so
# the shutdown may not assume `play` exists either: a finally that raises masks the
# exception it was handed.


def test_the_shutdown_survives_a_controller_without_the_attribute() -> None:
    c = Controller.__new__(Controller)  # no dl, no play, no _play_off
    c._play_shutdown()  # the AttributeError is the point: it must not escape
    assert not hasattr(c, "play")


def test_the_shutdown_swallows_a_failing_close() -> None:
    session = _Session(boom=True)
    c = _ctrl(session)
    c._play_shutdown()
    assert session.closed == 1
    assert c.dl.events == []


def test_the_shutdown_drains_the_summary_rows() -> None:
    rows = [("play_summary", {"frames": 12, "fps": 4.9}), ("play_fallback", {"reason": "stalled"})]
    session = _Session(close_rows=rows)
    c = _ctrl(session)
    c._play_shutdown()
    assert session.closed == 1
    assert c.dl.events == rows


def _boom_factory():
    """A PlaySession that cannot even be built (a broken play extra looks like this)."""
    raise RuntimeError("no session today")


def test_the_tick_survives_a_controller_without_the_attributes(monkeypatch) -> None:
    """Shadow on, and the controller has neither `_play_off` nor `play` (the loop tests
    build it that way). The failure latches on the instance it was handed."""
    monkeypatch.setattr(config, "PLAY_SHADOW", True)
    monkeypatch.setattr("brawlfarm.play.session.PlaySession", _boom_factory)
    c = Controller.__new__(Controller)
    c.dl = _DL()
    c.logs = []
    c.log = c.logs.append
    c.phase = "playing"
    c._play_observe(State.IN_MATCH)
    assert c._play_off is True
    assert len(c.logs) == 1 and "no session today" in c.logs[0]
    assert c.dl.events == []


# --- the import the shadow flag pays for --------------------------------------
#
# In-process this would pass or fail for the wrong reason: tests/test_play_session.py
# imports the module anyway. A fresh interpreter is the only honest answer, like
# tests/test_play_detect.py's "pulls nothing heavy".

_IMPORT_PROBE = (
    "import os, sys; "
    "os.environ['BRAWL_PLAY_SHADOW'] = {flag!r}; "
    "from brawlfarm.core.controller import Controller; "
    "from brawlfarm.core.states import State; "
    "c = Controller.__new__(Controller); "
    "c.dl = type('D', (), {{'event': lambda self, k, **f: None}})(); "
    "c.log = lambda msg: None; "
    "c.phase = {phase!r}; "
    "c._play_observe(State.{state}); "
    "print('brawlfarm.play.session' in sys.modules)"
)


def _probe(flag: str, phase: str, state: str) -> str:
    code = _IMPORT_PROBE.format(flag=flag, phase=phase, state=state)
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    return done.stdout.strip()


def test_shadow_off_never_imports_the_session_module() -> None:
    # A whole match of ticks costs the worker nothing: the import sits below the guard.
    assert _probe("0", "playing", "IN_MATCH") == "False"


def test_shadow_on_imports_the_session_module() -> None:
    # The mirror, at the menu: the session is built and ticked for real, but a tick that
    # is not a match starts no stream, so this needs neither adb nor the play extra.
    assert _probe("1", "menu", "MENU") == "True"
