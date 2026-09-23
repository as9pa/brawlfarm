"""Per-match recording for observe mode.

While the frame recorder has a session open, every match the classifier sees becomes one
``match-N/`` folder in that session: the emulator's own screen captures (``adb screencap``
through ``brawlfarm.play.capture.ScreencapSource``, not the scrcpy stream, which disconnects the
match), at most ``RATE_HZ`` a second, each new capture written once as ``NNNN.jpg`` at full size
with one line in ``frames.jsonl``: ``{"i", "t", "age", "state"}``. Nothing here needs the play
extra. Older sessions may still hold ``match-N.h264`` clips; numbering counts both.
"""

from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from brawlfarm.core import preview
from brawlfarm.core.states import State
from brawlfarm.play.capture import ScreencapSource

log = logging.getLogger("brawlfarm.play.matchrec")

# Menu-side states: seeing one means the match is over. UNKNOWN and POPUP are not here
# because both happen inside a match (the counter hides, a dialog covers the arena).
STOP_STATES = frozenset(
    {State.RESULTS, State.TROPHY_SCREEN, State.MENU, State.MATCHMAKING, State.DISCONNECT}
)
MAX_SECONDS = 360.0  # a match is about 150 s; this is the backstop, not the rule
RATE_HZ = 5.0  # most frames written per second, the same rate the play session reads at

_NUMBERED = re.compile(r"match-(\d+)(?:\.h264)?")


def _default_factory() -> Any:
    return ScreencapSource()


def _next_number(session: Path) -> int:
    """One past the highest ``match-N`` folder or old ``match-N.h264`` clip in the session."""
    highest = 0
    for path in session.glob("match-*"):
        found = _NUMBERED.fullmatch(path.name)
        if found:
            highest = max(highest, int(found.group(1)))
    return highest + 1


class MatchRecorder:
    """Drive one recording per match from the per-frame state. Never raises into the loop."""

    def __init__(
        self,
        *,
        factory: Callable[[], Any] | None = None,
        clock: Callable[[], float] = time.monotonic,
        wall: Callable[[], float] = time.time,
    ) -> None:
        self._factory = factory or _default_factory
        self._clock = clock
        self._wall = wall
        self._source: Any = None
        self._path: Path | None = None
        self._session: Path | None = None
        self._opened_at: float | None = None
        self._written_at: float | None = None
        self._last_frame: Any = None
        self._count = 0
        self._disabled_for: Path | None = None
        self._await_stop: Path | None = None

    @property
    def recording(self) -> Path | None:
        return self._path

    def observe(self, state: State, session: Path | None) -> None:
        if self._source is not None:
            error = getattr(self._source, "error", None)
            if error is not None:
                # The source died inside the match: release it now and wait for the next match,
                # because restarting here would cut this one into pieces.
                log.warning("match recording ended early: %s", error)
                # Latched to the session the source died in, so a new session records at once.
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
            else:
                self._write(state)
            return
        if state in STOP_STATES or session is None:
            self._await_stop = None
        if state != State.IN_MATCH or session is None:
            return
        if self._disabled_for == session or self._await_stop == session:
            return
        self._start(session)

    def _start(self, session: Path) -> None:
        try:
            # Numbered off the folder every time: this side creates the folder at once, so the
            # next match always sees it, and a resumed session never overwrites.
            path = session / f"match-{_next_number(session)}"
            path.mkdir()
            source = self._factory()
            source.start()
        except Exception as exc:  # observation must never stop the loop
            log.warning("match recording off for this session: %s", exc)
            self._disabled_for = session
            return
        self._source = source
        self._path = path
        self._session = session
        self._opened_at = self._clock()
        self._written_at = None
        self._last_frame = None
        self._count = 0
        log.info("recording the match into %s", path)

    def _write(self, state: State) -> None:
        """Write the source's newest capture if it is new and the rate allows it."""
        if self._written_at is not None and self._clock() - self._written_at < 1.0 / RATE_HZ:
            return
        try:
            frame, age = self._source.latest()
            # The same capture comes back until the next one lands: identity, not content,
            # is what says it was already written.
            if frame is None or frame is self._last_frame:
                return
            assert self._path is not None
            data = preview.encode(frame, full=True)
            (self._path / f"{self._count:04d}.jpg").write_bytes(data)
            line = {
                "i": self._count,
                "t": round(self._wall(), 3),
                "age": round(float(age), 3) if age is not None else None,
                "state": state.name,
            }
            with (self._path / "frames.jsonl").open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(line) + "\n")
        except Exception as exc:  # a full disk ends this session's recordings, not the loop
            log.warning("match recording off for this session: %s", exc)
            self._disabled_for = self._session
            self._stop()
            return
        self._last_frame = frame
        self._written_at = self._clock()
        self._count += 1

    def _stop(self) -> None:
        source, self._source = self._source, None
        self._path = None
        self._session = None
        self._opened_at = None
        self._last_frame = None
        if source is None:
            return
        try:
            source.stop()
        except Exception as exc:
            log.warning("match recording did not close cleanly: %s", exc)

    def close(self) -> None:
        self._stop()
