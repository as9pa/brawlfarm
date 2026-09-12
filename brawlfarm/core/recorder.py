"""Labeled frame recorder for recalibration corpora.

Switched by an empty record.flag file in the instance data dir, which the
API creates and deletes. Off by default. Writes JPEG frames plus one
labels.jsonl line per frame. Never deletes anything.

Every operation is best-effort: the recorder observes the farm, it never
steers it, so a full disk or a bad frame closes the session and logs once
instead of propagating out into the control loop.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import numpy as np

from brawlfarm.core import jsonio, preview, vision
from brawlfarm.core.states import State

log = logging.getLogger(__name__)


class Recorder:
    # Caps that bound one session. Both stick until the flag is cleared, so a
    # recorder that hit a cap never silently reopens on the next poll.
    MAX_FRAMES = 2000
    MAX_BYTES = 512 * 1024 * 1024
    MIN_INTERVAL_S = 1.0

    def __init__(
        self,
        root: Path,
        instance: str,
        flag: Path,
        *,
        clock: Callable[[], float] = time.monotonic,
        wall: Callable[[], datetime] = datetime.now,
    ) -> None:
        self._root = Path(root)
        self._instance = instance
        self._flag = Path(flag)
        self._clock = clock
        self._wall = wall
        self._session: Path | None = None
        self._session_id: str | None = None
        self._seq = 0
        self._bytes = 0
        self._last_write = float("-inf")
        self._last_state: State | None = None
        self._reason: str | None = None
        self._last_session: str | None = None
        self._last_frames = 0
        self._warned = False
        self._status_path = self._flag.parent / "recorder.json"
        self._write_status()

    # -- the switch ------------------------------------------------------

    def poll(self) -> None:
        """Open or close the session to match the flag file. Cheap enough for
        the controller's every-25-ticks cadence (one stat, plus one directory
        walk on the poll that opens a session)."""
        try:
            wanted = self._flag.exists()
        except OSError:
            wanted = False
        if wanted:
            if self._session is None and self._reason not in ("frame_cap", "error"):
                if self._instance_bytes() >= self.MAX_BYTES:
                    self._reason = "disk_cap"
                else:
                    self._open_session()
        else:
            # Clearing the flag is also how the owner clears a stuck cap.
            self._reason = None
            self._warned = False
            self._close_session()
        self._write_status()

    def _open_session(self) -> None:
        session_id = self._wall().strftime("%Y%m%d-%H%M%S")
        session = self._root / "recordings" / self._instance / session_id
        try:
            session.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self._reason = "error"
            log.warning("recorder stopped: %s", exc)
            self._warned = True
            return
        self._session = session
        self._session_id = session_id
        self._seq = 0
        self._bytes = 0
        self._last_write = float("-inf")
        self._last_state = None
        self._reason = None

    def _instance_bytes(self) -> int:
        """Bytes already on disk for this instance across every session (0 when
        nothing was ever recorded)."""
        base = self._root / "recordings" / self._instance
        total = 0
        try:
            for p in base.rglob("*"):
                if p.is_file():
                    total += p.stat().st_size
        except OSError:
            return 0
        return total

    # -- the frames ------------------------------------------------------

    def observe(self, screen: np.ndarray, state: State, phase: str) -> bool:
        """Record one labeled frame. Returns True when a frame was written.

        Frames are deduplicated in time: while the state is unchanged at most
        one frame per MIN_INTERVAL_S is kept, so a long menu sit costs a frame
        a second, not a frame a tick. Any state change is always recorded.
        """
        if self._session is None:
            return False
        if state == self._last_state and self._clock() - self._last_write < self.MIN_INTERVAL_S:
            return False
        try:
            seq = self._seq + 1
            name = f"{seq:04d}-{state.name.lower()}.jpg"
            data = preview.encode(screen)
            (self._session / name).write_bytes(data)
            line = {
                "seq": seq,
                "ts": self._wall().strftime("%H:%M:%S.%f")[:-5],
                "file": name,
                "state": state.value,
                "phase": phase,
                "scores": {
                    n: round(float(vision.score(screen, n)), 4) for n in vision.TEMPLATE_NAMES
                },
            }
            with (self._session / "labels.jsonl").open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(line) + "\n")
        except Exception as exc:  # observation must never stop the farm
            if not self._warned:
                log.warning("recorder stopped: %s", exc)
                self._warned = True
            self._reason = "error"
            self._close_session()
            self._write_status()
            return False
        self._seq = seq
        self._bytes += len(data)
        self._last_write = self._clock()
        self._last_state = state
        if self._seq >= self.MAX_FRAMES:
            self._reason = "frame_cap"
            self._close_session()
        self._write_status()
        return True

    # -- state -----------------------------------------------------------

    def _close_session(self) -> None:
        if self._session is None:
            return
        self._last_session = self._session_id
        self._last_frames = self._seq
        self._session = None
        self._session_id = None

    def status(self) -> dict:
        return {
            "on": self._session is not None,
            "frames": self._seq,
            "bytes": self._bytes,
            "session": self._session_id,
            "path": (
                f"recordings/{self._instance}/{self._session_id}"
                if self._session_id is not None
                else None
            ),
            "reason": self._reason,
            "last_session": self._last_session,
            "last_frames": self._last_frames,
        }

    def _write_status(self) -> None:
        try:
            jsonio.atomic_write_json(self._status_path, self.status())
        except OSError:
            pass

    def close(self) -> None:
        self._close_session()
        self._write_status()
