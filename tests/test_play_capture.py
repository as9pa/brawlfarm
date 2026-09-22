"""The screencap frame source: fake captures and a fake clock, no adb and no emulator.

Every test drives ``_pump`` by hand except the two about ``start()`` and ``stop()``, so the reads
are deterministic: the fake clock only moves when a test or a fake capture moves it.
"""

from __future__ import annotations

import numpy as np
import pytest

from brawlfarm.core import adb
from brawlfarm.play import capture


def a_frame(value: int) -> np.ndarray:
    return np.full((900, 1600, 3), value % 256, dtype=np.uint8)


class Harness:
    """A source and the doubles behind it, plus the fake clock the tests move."""

    def __init__(
        self,
        *,
        rounds: int = 1,
        fail_on: tuple[int, ...] = (),
        cost: float = 0.0,
        min_interval: float = capture.MIN_INTERVAL,
        max_errors: int = capture.MAX_ERRORS,
    ) -> None:
        self.rounds = rounds  # the capture that ends this round asks the pump to stop
        self.fail_on = fail_on  # the call numbers, counting from one, that raise
        self.cost = cost  # seconds the fake clock moves during one capture
        self.now = [100.0]
        self.calls = 0
        self.slept: list[float] = []
        self.source = capture.ScreencapSource(
            capture=self._capture,
            clock=lambda: self.now[0],
            sleep=self.slept.append,
            min_interval=min_interval,
            max_errors=max_errors,
        )

    def _capture(self) -> np.ndarray:
        self.calls += 1
        if self.calls >= self.rounds:
            self.source._stop.set()
        self.now[0] += self.cost
        if self.calls in self.fail_on:
            raise adb.AdbError("device offline")
        return a_frame(self.calls)

    def pump(self) -> None:
        """What the thread would do, but on this thread and for ``rounds`` captures."""
        self.source._pump()


# -- frames ------------------------------------------------------------------------


def test_there_is_no_frame_before_the_first_capture() -> None:
    h = Harness()

    assert h.source.latest() == (None, None)


def test_the_age_counts_from_before_the_capture_call() -> None:
    h = Harness(cost=0.25)

    h.pump()

    frame, age = h.source.latest()
    assert frame is not None
    assert age == pytest.approx(0.25)


def test_a_frame_older_than_the_stale_limit_is_no_frame() -> None:
    h = Harness()
    h.pump()

    h.now[0] += capture.STALE_AFTER
    assert h.source.latest()[1] == pytest.approx(capture.STALE_AFTER)
    h.now[0] += 0.01
    assert h.source.latest() == (None, None)


def test_the_frame_count_is_successful_captures_only() -> None:
    h = Harness(rounds=3, fail_on=(2,))

    h.pump()

    assert h.calls == 3 and h.source.frames == 2


def test_the_pump_paces_itself_at_the_interval() -> None:
    h = Harness(rounds=3, min_interval=0.2)

    h.pump()

    assert h.slept == pytest.approx([0.2, 0.2, 0.2])


# -- failures ----------------------------------------------------------------------


def test_one_failure_sets_no_error_and_the_next_success_clears_the_count() -> None:
    h = Harness(rounds=4, fail_on=(1, 3), max_errors=2)

    h.pump()

    assert h.source.error is None
    assert h.calls == 4 and h.source.frames == 2
    frame, age = h.source.latest()
    assert frame is not None and age == pytest.approx(0.0)


def test_three_failures_in_a_row_give_up_and_end_the_pump() -> None:
    h = Harness(rounds=9, fail_on=(1, 2, 3))

    h.pump()

    assert h.calls == 3 and not h.source._stop.is_set()  # it returned, it was not stopped
    assert h.source.error is not None
    assert "3 captures failed" in h.source.error and "device offline" in h.source.error


def test_a_source_that_gave_up_reports_no_frame_even_with_one_stored() -> None:
    h = Harness(rounds=9, fail_on=(2, 3, 4))

    h.pump()

    assert h.source.error is not None and h.source._frame is not None
    assert h.source.latest() == (None, None)


# -- lifetime ----------------------------------------------------------------------


def test_start_twice_runs_one_thread() -> None:
    h = Harness()

    h.source.start()
    thread = h.source._thread
    h.source.start()

    assert h.source._thread is thread
    assert thread is not None and thread.daemon
    h.source.stop()
    assert not thread.is_alive() and h.calls == 1


def test_stop_is_safe_before_start_and_twice() -> None:
    never_started = Harness().source
    never_started.stop()
    assert never_started._thread is None

    h = Harness()
    h.source.start()
    h.source.stop()
    h.source.stop()

    assert h.source._thread is None


# -- defaults ----------------------------------------------------------------------


def test_the_default_capture_is_the_adb_screencap() -> None:
    assert capture.ScreencapSource()._capture is adb.screencap
