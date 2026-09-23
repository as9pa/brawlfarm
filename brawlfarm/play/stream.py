"""The play stream: the BlueStacks display as 30 fps frames, read-only.

Known defect: running this stream while a match is in progress makes the game show its
disconnect modal, 31 times across 16 matches on the reference instance, at every bit rate,
frame rate and frame size tried. The cause is unknown. Shadow mode no longer uses this
module, and nothing in the package uses it during a match any more.

Transport: the bundled scrcpy server jar is pushed over adb, started with control off, and
its raw H.264 comes back through an adb port forward. A thread decodes it and keeps only the
newest frame. Nothing here sends input: ``control=false`` is a literal in SERVER_ARGS and this
module imports no tap or swipe.
"""

from __future__ import annotations

import logging
import socket
import threading
import time
from collections import deque
from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np

from brawlfarm import play
from brawlfarm.core import adb

log = logging.getLogger("brawlfarm.play.stream")

STALE_AFTER = 0.5  # seconds; older than this and latest() says there is no frame
CONNECT_DEADLINE = 8.0  # seconds to wait for the first byte after the server starts
REMOTE_JAR = "/data/local/tmp/scrcpy-server.jar"
REMOTE_SOCKET = "localabstract:scrcpy"
SERVER_ARGS = [
    "tunnel_forward=true",
    "audio=false",
    "control=false",  # fixed: the stream never sends input
    "video_codec=h264",
    "max_fps=30",
    "raw_stream=true",
    "log_level=warn",
]
_RECV_BYTES = 1 << 16
_SERVER_LINES = 20  # the tail of the server's output kept for error messages


class StreamError(RuntimeError):
    """The stream could not be started."""


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _connect_forwarded(port: int) -> socket.socket:
    return socket.create_connection(("127.0.0.1", port), timeout=2.0)


class Stream:
    """One live feed of one instance. start(), then latest() from any thread, then stop()."""

    def __init__(
        self,
        *,
        record: Path | None = None,
        clock: Callable[[], float] = time.monotonic,
        connect: Callable[[int], Any] | None = None,
        spawn: Callable[[list[str]], Any] | None = None,
    ) -> None:
        self._record_path = Path(record) if record is not None else None
        self._clock = clock
        self._connect = connect or _connect_forwarded
        self._spawn = spawn or adb.shell_process
        self._lock = threading.Lock()
        self._frame: np.ndarray | None = None
        self._frame_at: float | None = None
        self._sock: Any = None
        self._proc: Any = None
        self._thread: threading.Thread | None = None
        self._drain: threading.Thread | None = None
        self._server_lines: deque[str] = deque(maxlen=_SERVER_LINES)
        self._record_fh = None
        self._forwarded = False
        self._stopping = False
        self._stopped = False
        self.port: int | None = None
        self.error: str | None = None
        self.frames = 0
        self.started_at: float | None = None

    # -- lifetime ----------------------------------------------------------------

    def start(self) -> None:
        """Push, forward, spawn, wait for the first byte, then decode in the background.
        Raises StreamError (after cleaning up) when the start does not finish: no byte before
        the deadline, or anything else failing once the forward is in place."""
        adb.push(play.SERVER_JAR, REMOTE_JAR)
        self.port = _free_port()
        adb.forward(self.port, REMOTE_SOCKET)
        self._forwarded = True
        # From here on the forward outlives a half-started stream unless start() tears it down:
        # the caller drops the Stream on failure and never reaches stop().
        try:
            # app_process finds the server class through CLASSPATH; without it the program aborts.
            self._proc = self._spawn(
                [
                    f"CLASSPATH={REMOTE_JAR}",
                    "app_process",
                    "/",
                    "com.genymobile.scrcpy.Server",
                    play.SERVER_VERSION,
                    *SERVER_ARGS,
                ]
            )
            # Drain the server's output so its pipe never fills and stalls it; keep the tail.
            self._drain = threading.Thread(
                target=self._drain_output, name="play-stream-log", daemon=True
            )
            self._drain.start()
            self._sock = self._wait_for_bytes()
            if self._record_path is not None:
                self._record_fh = self._record_path.open("wb")
            self.started_at = self._clock()
            self._thread = threading.Thread(target=self._pump, name="play-stream", daemon=True)
            self._thread.start()
        except StreamError:
            self._teardown()
            self._close_record()
            raise
        except Exception as exc:  # one type for the caller to catch
            self._teardown()
            self._close_record()
            raise StreamError(f"stream start failed: {exc}") from exc

    def _wait_for_bytes(self) -> Any:
        """adb accepts the forwarded connection before the server listens and closes it without
        a byte, so connect, peek, and retry until the deadline."""
        deadline = time.monotonic() + CONNECT_DEADLINE
        while time.monotonic() < deadline:
            if self._proc is not None and self._proc.poll() is not None:
                break
            try:
                cand = self._connect(self.port)
            except OSError:
                time.sleep(0.2)
                continue
            try:
                cand.settimeout(2.0)
                peek = cand.recv(1, socket.MSG_PEEK)
            except (OSError, socket.timeout):
                peek = b""
            if peek:
                cand.settimeout(None)
                return cand
            cand.close()
            time.sleep(0.2)
        tail = self._server_output()
        self._teardown()
        raise StreamError(
            f"no stream bytes within {CONNECT_DEADLINE:g} s" + (f": {tail}" if tail else "")
        )

    def _drain_output(self) -> None:
        proc = self._proc
        out = getattr(proc, "stdout", None)
        if out is None:
            return
        try:
            for raw in iter(out.readline, b""):
                self._server_lines.append(raw.decode("utf-8", errors="replace").rstrip())
        except (OSError, ValueError):  # the pipe closed under us at stop()
            pass

    def _server_output(self) -> str:
        if self._drain is not None:
            self._drain.join(timeout=0.5)
        return " | ".join(line for line in self._server_lines if line)[-400:]

    def stop(self) -> None:
        """Tear down once: socket, server process, forward, recording. Safe to call twice."""
        if self._stopped:
            return
        self._stopped = True
        self._stopping = True
        self._teardown()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        if self._drain is not None:
            self._drain.join(timeout=1.0)
        self._close_record()

    def _close_record(self) -> None:
        """Only once the pump is gone or was never started: it is the handle's one writer."""
        if self._record_fh is not None:
            try:
                self._record_fh.close()
            except OSError:
                pass
            self._record_fh = None

    def _teardown(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        if self._proc is not None:
            try:
                self._proc.kill()
            except Exception:
                pass
            self._proc = None
        if self.port is not None and self._forwarded:
            self._forwarded = False  # a second teardown must not remove it twice
            try:
                adb.forward_remove(self.port)
            except adb.AdbError as exc:
                log.debug("forward not removed: %s", exc)
            self.port = None if self._stopped else self.port

    # -- frames --------------------------------------------------------------------

    def latest(self) -> tuple[np.ndarray | None, float | None]:
        """The newest frame and its age in seconds, or (None, None) when there is none, the
        newest is older than STALE_AFTER, or the stream has ended."""
        with self._lock:
            frame, at = self._frame, self._frame_at
        if frame is None or at is None or self.error is not None:
            return None, None
        age = self._clock() - at
        if age > STALE_AFTER:
            return None, None
        return frame, age

    def _pump(self) -> None:
        from brawlfarm.play import h264

        try:
            dec = h264.Decoder()
        except Exception as exc:  # the play extra is missing or broken
            self.error = f"decoder unavailable: {exc}"
            return
        sock = self._sock
        try:
            while not self._stopping:
                chunk = sock.recv(_RECV_BYTES)
                if not chunk:
                    self.error = "stream ended"
                    break
                if self._record_fh is not None:
                    self._record_fh.write(chunk)
                for frame in dec.feed(chunk):
                    with self._lock:
                        self._frame = frame
                        self._frame_at = self._clock()
                    self.frames += 1
        except OSError as exc:
            if not self._stopping:
                self.error = f"stream failed: {exc}"
        except Exception as exc:  # a decode fault ends the stream, never the caller
            self.error = f"decode failed: {exc}"
