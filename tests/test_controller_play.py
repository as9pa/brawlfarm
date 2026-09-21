"""The farm loop's shadow-session wiring: the tick, the rows and the close.

With `shadow` off the controller builds nothing and writes nothing, so a worker that
never asked for the play model never pays for it. With it on, the rows the session
returns are written from the controller thread in the order it returned them, and one
failure anywhere in the path turns shadow off for the rest of the process.

Like tests/test_controller_questpick.py these drive the controller's methods directly:
the object is built without __init__ (no adb, no API, no DataLog), so the inputs are
exactly the config flag and the session stub.
"""

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
    with pytest.raises(RuntimeError):  # run()'s finally owns the try/except
        c._play_close()
