"""Per-match recording for observe mode.

While the frame recorder has a session open, every match the classifier sees becomes one
``match-N.h264`` in that session folder: the play stream's raw bytes, no re-encode. The
farm worker gets the same through its play session in a later pull request.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from brawlfarm import play
from brawlfarm.core.states import State

log = logging.getLogger("brawlfarm.play.matchrec")

# Menu-side states: seeing one means the match is over. UNKNOWN and POPUP are not here
# because both happen inside a match (the counter hides, a dialog covers the arena).
STOP_STATES = frozenset(
    {State.RESULTS, State.TROPHY_SCREEN, State.MENU, State.MATCHMAKING, State.DISCONNECT}
)
MAX_SECONDS = 360.0  # a match is about 150 s; this is the backstop, not the rule


def _default_factory(path: Path) -> Any:
    from brawlfarm.play import stream  # PyAV lives behind the play extra

    return stream.Stream(record=path)


class MatchRecorder:
    """Drive one recording per match from the per-frame state. Never raises into the loop."""

    def __init__(
        self,
        *,
        factory: Callable[[Path], Any] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._factory = factory or _default_factory
        self._clock = clock
        self._stream: Any = None
        self._path: Path | None = None
        self._session: Path | None = None
        self._opened_at: float | None = None
        self._disabled_for: Path | None = None
        self._numbered_for: Path | None = None
        self._next = 1
        self._await_stop: Path | None = None
        self._said_missing = False

    @property
    def recording(self) -> Path | None:
        return self._path

    def observe(self, state: State, session: Path | None) -> None:
        if self._stream is not None:
            error = getattr(self._stream, "error", None)
            if error is not None:
                # The stream died inside the match: release it now and wait for the next match,
                # because restarting here would cut this one into pieces.
                log.warning("match recording ended early: %s", error)
                # Latched to the session the stream died in, so a new session records at once.
                dead_in = self._session
                self._stop()
                self._await_stop = dead_in
                return
            over = (
                session is None
                or session != self._session
                or state in STOP_STATES
                or (self._opened_at is not None and self._clock() - self._opened_at >= MAX_SECONDS)
            )
            if over:
                self._stop()
            return
        if state in STOP_STATES or session is None:
            self._await_stop = None
        if state != State.IN_MATCH or session is None:
            return
        if not play.available():
            if not self._said_missing:
                log.info("match recording off: the play extra is not installed")
                self._said_missing = True
            return
        if self._disabled_for == session or self._await_stop == session:
            return
        self._start(session)

    def _start(self, session: Path) -> None:
        log.warning(
            "match recording uses the play stream, which can disconnect the match (spec section 2)"
        )
        try:
            # The first match of a session numbers itself off the folder, so a resumed
            # session never overwrites; after that the counter carries, because the stream
            # owns the file and this side does not wait for it to appear.
            if self._numbered_for != session:
                self._numbered_for = session
                self._next = len(list(session.glob("match-*.h264"))) + 1
            path = session / f"match-{self._next}.h264"
            stream = self._factory(path)
            stream.start()
        except Exception as exc:  # observation must never stop the loop
            log.warning("match recording off for this session: %s", exc)
            self._disabled_for = session
            return
        self._stream = stream
        self._path = path
        self._session = session
        self._opened_at = self._clock()
        self._next += 1
        log.info("recording %s", path.name)

    def _stop(self) -> None:
        stream, self._stream = self._stream, None
        self._path = None
        self._session = None
        self._opened_at = None
        if stream is None:
            return
        try:
            stream.stop()
        except Exception as exc:
            log.warning("match recording did not close cleanly: %s", exc)

    def close(self) -> None:
        self._stop()
