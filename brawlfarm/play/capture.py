"""The detector's frame source: the emulator's own screen captures, pulled on a thread.

Play mode was designed around a live scrcpy stream. That stream disconnects the game during a
match (see the open defect in docs/superpowers/specs/2026-09-18-play-mode.md, section 2), so the
detector reads ``adb.screencap()`` instead. One capture costs 180 to 280 ms, which gives about 5
frames a second: the same rate the session consumed from the stream, with a later frame.

This class duck-types ``brawlfarm.play.stream.Stream`` on purpose: ``start()``, ``latest()``,
``stop()`` and ``error`` are all the session uses.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from typing import Any

import numpy as np

from brawlfarm.core import adb

log = logging.getLogger("brawlfarm.play.capture")

STALE_AFTER = 1.0  # seconds; older than this and latest() says there is no frame
MIN_INTERVAL = 0.2  # seconds between captures: the session reads at 5 Hz, so do not capture faster
MAX_ERRORS = 3  # consecutive capture failures before the source gives up (one adb hiccup is normal)
JOIN_TIMEOUT = 3.0


class ScreencapSource:
    """Newest-frame-wins screen captures on a background thread."""

    def __init__(
        self,
        *,
        capture: Callable[[], np.ndarray] | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Any] = time.sleep,
        min_interval: float = MIN_INTERVAL,
        max_errors: int = MAX_ERRORS,
    ) -> None:
        self._capture = capture or adb.screencap
        self._clock = clock
        self._sleep = sleep
        self._min_interval = float(min_interval)
        self._max_errors = int(max_errors)
        self._lock = threading.Lock()
        self._frame: np.ndarray | None = None
        self._frame_at: float | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.error: str | None = None
        self.frames = 0

    # -- lifetime ----------------------------------------------------------------

    def start(self) -> None:
        """Begin capturing. Calling it twice is a no-op, never a second thread.

        A source that was stopped starts again: without clearing the flag the new thread
        would see a set stop event and return at once, capturing nothing and saying nothing."""
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._pump, name="play-capture", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop capturing and wait briefly for the thread. Safe to call twice, or before start."""
        self._stop.set()
        thread, self._thread = self._thread, None
        if thread is not None:
            thread.join(JOIN_TIMEOUT)

    # -- frames --------------------------------------------------------------------

    def latest(self) -> tuple[np.ndarray | None, float | None]:
        """The newest frame and its age in seconds, or (None, None) when there is none, the
        newest is older than STALE_AFTER, or the source has given up."""
        with self._lock:
            frame, at = self._frame, self._frame_at
        if frame is None or at is None or self.error is not None:
            return None, None
        age = self._clock() - at
        if age > STALE_AFTER:
            return None, None
        return frame, age

    def _pump(self) -> None:
        failures = 0
        while not self._stop.is_set():
            began = self._clock()
            try:
                frame = self._capture()
            except Exception as exc:  # one hiccup is normal; a run of them is not
                failures += 1
                if failures >= self._max_errors:
                    self.error = f"{self._max_errors} captures failed: {exc!r}"
                    log.warning("capture source gave up: %s", self.error)
                    return
            else:
                failures = 0
                with self._lock:
                    # the age counts from BEFORE the call, so it includes the capture's own cost
                    self._frame, self._frame_at = frame, began
                    self.frames += 1
            rest = self._min_interval - (self._clock() - began)
            if rest > 0:
                self._sleep(rest)
