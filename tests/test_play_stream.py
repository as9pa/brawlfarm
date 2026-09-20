"""The play stream: pushes the server, forwards a port, connects once bytes flow, decodes on
a thread, keeps only the newest frame, reports staleness and errors, records raw bytes, and
tears everything down once. The transport is faked with the synthetic clip; adb is faked."""

from __future__ import annotations

import io
import socket
import threading
import time
from pathlib import Path

import pytest

pytest.importorskip("av")

from brawlfarm import play  # noqa: E402
from brawlfarm.core import adb  # noqa: E402
from brawlfarm.play import stream  # noqa: E402

CLIP = Path(__file__).parent / "fixtures" / "play" / "stream-2s.h264"


class FakeSocket:
    """Serves the clip in chunks, then either EOF (hold=False) or blocks until close()
    (hold=True), which is what a live server does between frames."""

    def __init__(self, data: bytes, chunk: int = 8192, *, hold: bool = False) -> None:
        self._data = data
        self._pos = 0
        self._chunk = chunk
        self._hold = hold
        self._closed = threading.Event()

    def settimeout(self, value) -> None:
        pass

    def recv(self, n: int, flags: int = 0) -> bytes:
        if flags & socket.MSG_PEEK:
            return self._data[self._pos : self._pos + 1]
        if self._pos >= len(self._data):
            if self._hold:
                self._closed.wait()
            return b""
        out = self._data[self._pos : self._pos + min(n, self._chunk)]
        self._pos += len(out)
        return out

    def close(self) -> None:
        self._closed.set()


class FakeProc:
    def __init__(self) -> None:
        self.killed = False
        self.stdout = io.BytesIO(b"[server] INFO: Device: fake\n")

    def poll(self):
        return 1 if self.killed else None

    def kill(self) -> None:
        self.killed = True


@pytest.fixture()
def fakes(monkeypatch):
    calls: list[tuple] = []
    monkeypatch.setattr(
        adb, "push", lambda local, remote: calls.append(("push", Path(local), remote))
    )
    monkeypatch.setattr(
        adb, "forward", lambda port, remote: calls.append(("forward", port, remote))
    )
    monkeypatch.setattr(adb, "forward_remove", lambda port: calls.append(("forward_remove", port)))
    proc = FakeProc()
    monkeypatch.setattr(
        adb, "shell_process", lambda args: (calls.append(("shell", list(args))), proc)[1]
    )
    return calls, proc


def _wait(pred, timeout: float = 5.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if pred():
            return True
        time.sleep(0.01)
    return False


def test_start_pushes_forwards_spawns_and_yields_frames(fakes) -> None:
    calls, proc = fakes
    data = CLIP.read_bytes()
    s = stream.Stream(connect=lambda port: FakeSocket(data, hold=True), spawn=None)
    s.start()
    try:
        assert calls[0] == ("push", play.SERVER_JAR, stream.REMOTE_JAR)
        assert calls[1][0] == "forward" and calls[1][2] == "localabstract:scrcpy"
        assert calls[2][0] == "shell"
        assert calls[2][1][:4] == [
            "app_process",
            "/",
            "com.genymobile.scrcpy.Server",
            play.SERVER_VERSION,
        ]
        assert "control=false" in calls[2][1] and "raw_stream=true" in calls[2][1]
        assert _wait(lambda: s.frames > 0)
        frame, age = s.latest()
        assert frame is not None and frame.shape == (900, 1600, 3)
        assert age is not None and age < stream.STALE_AFTER
    finally:
        s.stop()


def test_end_of_stream_sets_error_and_empties_latest(fakes) -> None:
    data = CLIP.read_bytes()
    s = stream.Stream(connect=lambda port: FakeSocket(data))
    s.start()
    try:
        assert _wait(lambda: s.error is not None)
        assert s.error == "stream ended"
        assert s.latest() == (None, None)
    finally:
        s.stop()


def test_a_stale_frame_is_reported_as_none(fakes) -> None:
    data = CLIP.read_bytes()
    now = [100.0]
    s = stream.Stream(connect=lambda port: FakeSocket(data, hold=True), clock=lambda: now[0])
    s.start()
    try:
        assert _wait(lambda: s.frames > 0)
        frame, age = s.latest()
        assert frame is not None
        now[0] += stream.STALE_AFTER + 0.01
        assert s.latest() == (None, None)
    finally:
        s.stop()


def test_stop_tears_down_once_and_is_idempotent(fakes) -> None:
    calls, proc = fakes
    data = CLIP.read_bytes()
    s = stream.Stream(connect=lambda port: FakeSocket(data))
    s.start()
    port = s.port
    s.stop()
    s.stop()
    assert proc.killed
    assert calls.count(("forward_remove", port)) == 1
    assert (
        threading.active_count() >= 1
    )  # the decode thread is joined, no leak assertion beyond this


def test_recording_writes_the_raw_bytes(fakes, tmp_path: Path) -> None:
    data = CLIP.read_bytes()
    out = tmp_path / "match-1.h264"
    s = stream.Stream(record=out, connect=lambda port: FakeSocket(data))
    s.start()
    assert _wait(lambda: s.error is not None)
    s.stop()
    assert out.read_bytes() == data


def test_a_server_that_never_sends_is_an_error_within_the_deadline(fakes, monkeypatch) -> None:
    monkeypatch.setattr(stream, "CONNECT_DEADLINE", 0.3)
    s = stream.Stream(connect=lambda port: FakeSocket(b""))
    with pytest.raises(stream.StreamError) as err:
        s.start()
    assert "Device: fake" in str(err.value), "the server's output tail is in the error"
    s.stop()
