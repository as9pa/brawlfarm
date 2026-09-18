# Play mode pull request 1: stream, match recorder, extras. Implementation plan

> For agentic workers: REQUIRED SUB-SKILL: use superpowers:subagent-driven-development (recommended)
> or superpowers:executing-plans to implement this plan task by task. Steps use checkbox syntax.

Goal: a read-only 30 fps video feed of the BlueStacks display that the rest of play mode can build
on, recorded per match in observe mode, installable as an optional extra, and proven live on Pie64.

Architecture: a new package `brawlfarm/play/` holds the bundled scrcpy server jar, a single-threaded
parser-fed H.264 decoder, a `Stream` object that owns the server process, the adb forward and a
decode thread, and a `MatchRecorder` that observe mode drives from the classifier's state. Four small
adb helpers (push, forward, forward remove, a long-running shell process) go into
`brawlfarm/core/adb.py`. The health probe reports whether the extra is installed. Nothing in this
pull request taps, and nothing changes the farm loop.

Tech stack: Python 3.13 with uv, pytest, ruff; PyAV (`av>=14`, 18.1.0 on this machine) for H.264;
scrcpy 4.1 server jar (Apache-2.0); hatchling wheel; adb through `brawlfarm/core/adb.py`.

Spec: docs/superpowers/specs/2026-09-18-play-mode.md, sections 2, 7, 9 (first line) and 10
(recorder). Read it first. This plan implements build order step 1 only.

## Global constraints

- Gate for every task: `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`,
  `uv run python tools/scrub_check.py` printing `0 hit(s)`. No task touches `brawlfarm/web`.
- Review is on for this project: each task gets a sonnet spec-compliance and code-quality review,
  the branch a whole-branch sonnet review before its pull request.
- Never taps: `control=false` is a literal in the server arguments, not a parameter. No module in
  `brawlfarm/play/` imports `adb.tap`, `adb.swipe` or anything that sends input.
- No user string reaches a shell or a path (CONTRIBUTING.md). Every adb argument here is a literal
  or an integer port.
- Nothing under `brawlfarm/core/` imports PyAV at import time. `tests/test_core_imports.py` runs
  every core module in a bare subprocess and must stay green; `observer.py` may import
  `brawlfarm.play.matchrec`, which imports `brawlfarm.play.stream` lazily.
- The decoder runs with `thread_count = 1`. Measured 2026-09-18: frame threading holds back 18
  packets (600 ms at 30 fps); single-threaded decode is 1.2 ms median per packet.
- Prose rule: no em-dashes and no emoji anywhere, including commit messages and docstrings.
- Work happens in the worktree `.claude/worktrees/play-1-stream` on branch `play/stream`. Commit
  after every task with the trailer `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Source files to copy from: the jar and license from
  `%LOCALAPPDATA%\Microsoft\WinGet\Packages\Genymobile.scrcpy_Microsoft.Winget.Source_8wekyb3d8bbwe\scrcpy-win64-v4.1\`
  (`scrcpy-server`, `LICENSE.txt`); the synthetic test clip is already in the
  repository at `tests/fixtures/play/stream-2s.h264`, so no task copies it (testsrc2 pattern, 1600 x 900, 30 fps, 2 s, 60 frames, 125422 bytes, no account content).

## File structure

- Create `brawlfarm/play/__init__.py`: `available()`, `SERVER_JAR`, `SERVER_VERSION`,
  `SERVER_JAR_SIZE`.
- Create `brawlfarm/play/scrcpy-server` (binary, 733706 bytes) and `brawlfarm/play/LICENSE.scrcpy`.
- Create `brawlfarm/play/h264.py`: `Decoder` (feed bytes, get BGR frames).
- Create `brawlfarm/play/stream.py`: `Stream` (server, forward, socket, decode thread, latest frame,
  optional raw recording).
- Create `brawlfarm/play/matchrec.py`: `MatchRecorder` (state-driven per-match recording).
- Modify `brawlfarm/core/adb.py` after `_run` (line 44 to 72): `push`, `forward`, `forward_remove`,
  `shell_process`.
- Modify `brawlfarm/core/recorder.py`: `session_dir` property.
- Modify `brawlfarm/core/observer.py`: build a `MatchRecorder`, call it per frame, close it.
- Modify `brawlfarm/api/app.py` health route (lines 169 to 179): `play_available`.
- Modify `pyproject.toml`: extras, groups, dev group.
- Create `tools/play/stream_check.py`: the live pass tool.
- Create `docs/notes/2026-09-18-play-stream-spike.md`; modify `README.md`, `docs/calibration.md`,
  `CONTRIBUTING.md`.
- Tests: `tests/test_play_package.py`, `tests/test_adb_helpers.py`, `tests/test_play_h264.py`,
  `tests/test_play_stream.py`, `tests/test_play_matchrec.py`, `tests/test_observer.py` (extend),
  `tests/test_api_app.py` (extend), fixture `tests/fixtures/play/stream-2s.h264`.

---

### Task 1: the package, the jar and the extras

Files: create `brawlfarm/play/__init__.py`, `brawlfarm/play/scrcpy-server`,
`brawlfarm/play/LICENSE.scrcpy`; modify `pyproject.toml` lines 40 to 50; test
`tests/test_play_package.py`.

Interfaces:

- Produces: `brawlfarm.play.available() -> bool`, `brawlfarm.play.SERVER_JAR: Path`,
  `brawlfarm.play.SERVER_VERSION = "4.1"`, `brawlfarm.play.SERVER_JAR_SIZE = 733706`.

- [ ] Step 1: write the failing tests in `tests/test_play_package.py`:

```python
"""The play package: importable without PyAV, ships the scrcpy server jar and its license,
and says whether the play extra is installed without importing it."""

from __future__ import annotations

import subprocess
import sys

from brawlfarm import play


def test_available_is_a_bool() -> None:
    assert isinstance(play.available(), bool)


def test_the_server_jar_ships_with_its_license() -> None:
    assert play.SERVER_JAR.is_file()
    assert play.SERVER_JAR.stat().st_size == play.SERVER_JAR_SIZE == 733706
    assert play.SERVER_VERSION == "4.1"
    license_text = (play.SERVER_JAR.parent / "LICENSE.scrcpy").read_text(encoding="utf-8")
    assert "Apache License" in license_text


def test_importing_the_package_does_not_import_pyav() -> None:
    code = "import sys, brawlfarm.play as p; p.available(); print('av' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False"
```

- [ ] Step 2: run `uv run pytest tests/test_play_package.py -q`. Expected: FAIL with
      `ModuleNotFoundError: No module named 'brawlfarm.play'`.

- [ ] Step 3: copy the jar and the license into the package:

```powershell
$src = "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Genymobile.scrcpy_Microsoft.Winget.Source_8wekyb3d8bbwe\scrcpy-win64-v4.1"
New-Item -ItemType Directory -Force brawlfarm\play | Out-Null
Copy-Item "$src\scrcpy-server" brawlfarm\play\scrcpy-server
Copy-Item "$src\LICENSE.txt" brawlfarm\play\LICENSE.scrcpy
(Get-Item brawlfarm\play\scrcpy-server).Length   # must print 733706
```

- [ ] Step 4: write `brawlfarm/play/__init__.py`:

```python
"""Play mode: the opt-in in-match brain. Spec: docs/superpowers/specs/2026-09-18-play-mode.md.

Nothing in this file imports PyAV or onnxruntime. The core loop and the API import this
package to ask ``available()`` and must keep working when the play extra is absent.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

# The scrcpy 4.1 server (Apache-2.0, license text in LICENSE.scrcpy next to it). It is pushed
# onto the instance by brawlfarm.play.stream and streams the display back over adb; it sends
# nothing in.
SERVER_JAR = Path(__file__).resolve().parent / "scrcpy-server"
SERVER_VERSION = "4.1"
SERVER_JAR_SIZE = 733706


def available() -> bool:
    """True when the play extra is installed (PyAV imports), without importing it."""
    return importlib.util.find_spec("av") is not None
```

- [ ] Step 5: edit `pyproject.toml`. Replace the optional-dependencies and dependency-groups
      blocks (keep the comment above them) with:

```toml
[project.optional-dependencies]
desktop = ["pywebview>=5.3", "pystray>=0.19", "pillow>=10"]
# The play extras: PyAV decodes the scrcpy stream; onnxruntime-gpu runs the detector on CUDA.
# Keep each list identical to its dependency group below.
play = ["av>=14"]
play-gpu = ["av>=14", "onnxruntime-gpu>=1.20"]

[dependency-groups]
# av is in dev as well so the decoder tests run in CI; the tests skip when it is absent.
dev = ["pytest>=8.3", "pytest-asyncio>=0.24", "ruff>=0.12", "httpx>=0.27", "av>=14"]
desktop = ["pywebview>=5.3", "pystray>=0.19", "pillow>=10"]
play = ["av>=14"]
play-gpu = ["av>=14", "onnxruntime-gpu>=1.20"]
```

      Then run `uv sync` (installs av into the worktree venv) and `uv lock` if it changed.

- [ ] Step 6: run `uv run pytest tests/test_play_package.py -q`. Expected: 3 passed.

- [ ] Step 7: prove the wheel carries the jar:

```powershell
uv build --wheel -o "$env:TEMP\bf-wheel" 2>&1 | Select-Object -Last 2
uv run python -m zipfile -l (Get-ChildItem "$env:TEMP\bf-wheel\*.whl").FullName | Select-String "brawlfarm/play/"
```

      Expected: lines for `brawlfarm/play/__init__.py`, `brawlfarm/play/scrcpy-server` and
      `brawlfarm/play/LICENSE.scrcpy`. If the jar is missing, add
      `artifacts = ["brawlfarm/web/dist/**", "brawlfarm/play/scrcpy-server"]` under
      `[tool.hatch.build.targets.wheel]` and rebuild.

- [ ] Step 8: run the gate (`uv run pytest -q`, `uv run ruff check .`,
      `uv run ruff format --check .`, `uv run python tools/scrub_check.py`).

- [ ] Step 9: commit:

```bash
git add brawlfarm/play pyproject.toml uv.lock tests/test_play_package.py
git commit -m "feat(play): package skeleton, bundled scrcpy server and the play extras"
```

### Task 2: adb helpers for the stream

Files: modify `brawlfarm/core/adb.py` (add after `_run`, which ends at line 72; `import
subprocess` is already there); test `tests/test_adb_helpers.py`.

Interfaces:

- Consumes: `adb._run(args, *, binary=False, timeout=20.0, retries=2)`, `config.ADB_PATH`,
  `config.ADB_SERIAL`, `adb.AdbError`.
- Produces: `adb.push(local: Path, remote: str) -> None`,
  `adb.forward(local_port: int, remote: str) -> None`, `adb.forward_remove(local_port: int) -> None`,
  `adb.shell_process(args: list[str]) -> subprocess.Popen`.

- [ ] Step 1: write the failing tests in `tests/test_adb_helpers.py`:

```python
"""The four adb helpers the play stream needs: push a file, add and remove a port forward,
and start a long-running shell process. Every call is checked as an argument list; nothing
reaches a real adb."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from brawlfarm.core import adb, config


@pytest.fixture()
def calls(monkeypatch) -> list[list[str]]:
    seen: list[list[str]] = []

    def fake_run(args, **kwargs):
        seen.append(list(args))
        return ""

    monkeypatch.setattr(adb, "_run", fake_run)
    monkeypatch.setattr(config, "ADB_SERIAL", "127.0.0.1:5555")
    return seen


def test_push_sends_the_file_to_the_device_path(calls, tmp_path: Path) -> None:
    jar = tmp_path / "scrcpy-server"
    jar.write_bytes(b"x")
    adb.push(jar, "/data/local/tmp/scrcpy-server.jar")
    assert calls == [["-s", "127.0.0.1:5555", "push", str(jar), "/data/local/tmp/scrcpy-server.jar"]]


def test_forward_and_remove_name_the_tcp_port(calls) -> None:
    adb.forward(27183, "localabstract:scrcpy")
    adb.forward_remove(27183)
    assert calls == [
        ["-s", "127.0.0.1:5555", "forward", "tcp:27183", "localabstract:scrcpy"],
        ["-s", "127.0.0.1:5555", "forward", "--remove", "tcp:27183"],
    ]


def test_shell_process_starts_adb_shell_with_the_arguments(monkeypatch) -> None:
    seen = {}

    class FakePopen:
        def __init__(self, cmd, **kwargs):
            seen["cmd"] = cmd
            seen["kwargs"] = kwargs

    monkeypatch.setattr(config, "ADB_PATH", "C:/fake/adb.exe")
    monkeypatch.setattr(config, "ADB_SERIAL", "127.0.0.1:5555")
    monkeypatch.setattr(adb.subprocess, "Popen", FakePopen)
    proc = adb.shell_process(["app_process", "/", "com.example.Server", "4.1"])
    assert isinstance(proc, FakePopen)
    assert seen["cmd"] == [
        "C:/fake/adb.exe", "-s", "127.0.0.1:5555", "shell",
        "app_process", "/", "com.example.Server", "4.1",
    ]
    assert seen["kwargs"]["stdin"] is subprocess.DEVNULL
    assert seen["kwargs"]["stdout"] is subprocess.PIPE
```

- [ ] Step 2: run `uv run pytest tests/test_adb_helpers.py -q`. Expected: FAIL with
      `AttributeError: module 'brawlfarm.core.adb' has no attribute 'push'`.

- [ ] Step 3: add to `brawlfarm/core/adb.py` right after `_run`:

```python
# --- helpers for the play stream (brawlfarm/play/stream.py) -------------------------
# Read-only plumbing: a file onto the device, a port forward, a long-running device
# program. None of these sends input; every argument is a literal or an integer port.


def push(local: Path, remote: str) -> None:
    """Copy one local file to a device path. ``remote`` is chosen by the caller from a
    constant, never from user input."""
    _run(["-s", config.ADB_SERIAL, "push", str(local), remote], timeout=60.0)


def forward(local_port: int, remote: str) -> None:
    """Forward a host TCP port to a device socket (``localabstract:<name>`` or ``tcp:<n>``)."""
    _run(["-s", config.ADB_SERIAL, "forward", f"tcp:{int(local_port)}", remote])


def forward_remove(local_port: int) -> None:
    """Drop the forward for one host port. Raises AdbError when there is none."""
    _run(["-s", config.ADB_SERIAL, "forward", "--remove", f"tcp:{int(local_port)}"])


def shell_process(args: list[str]) -> subprocess.Popen:
    """Start ``adb shell <args>`` and hand back the running process; the caller owns its
    lifetime and must kill it. For device programs that run until stopped, unlike ``_run``,
    which waits for a command to finish."""
    return subprocess.Popen(
        [config.ADB_PATH, "-s", config.ADB_SERIAL, "shell", *args],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
```

      Add `from pathlib import Path` to the imports if it is not there.

- [ ] Step 4: run `uv run pytest tests/test_adb_helpers.py -q`. Expected: 3 passed.
- [ ] Step 5: run the gate.
- [ ] Step 6: commit:

```bash
git add brawlfarm/core/adb.py tests/test_adb_helpers.py
git commit -m "feat(adb): push, forward and shell_process for the play stream"
```

### Task 3: the decoder

Files: create `brawlfarm/play/h264.py`, `tests/fixtures/play/stream-2s.h264` (copied from the
scratchpad path in Global constraints); test `tests/test_play_h264.py`.

Interfaces:

- Produces: `h264.Decoder` with `feed(data: bytes) -> list[np.ndarray]`,
  `flush() -> list[np.ndarray]`, counters `packets: int`, `frames: int`. Frames are BGR uint8
  arrays of shape (height, width, 3).

- [ ] Step 1: confirm the fixture is present: `tests/fixtures/play/stream-2s.h264` is 125422 bytes
      (already committed; nothing to copy).

- [ ] Step 2: write the failing tests in `tests/test_play_h264.py`:

```python
"""The parser-fed H.264 decoder: raw bytes in any chunking, BGR frames out, single-threaded
so the first frame is not held back. The clip is a synthetic test pattern, not a capture."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("av")

from brawlfarm.play import h264  # noqa: E402

CLIP = Path(__file__).parent / "fixtures" / "play" / "stream-2s.h264"


def test_the_clip_decodes_to_full_size_bgr_frames() -> None:
    dec = h264.Decoder()
    frames = []
    data = CLIP.read_bytes()
    for i in range(0, len(data), 4096):
        frames.extend(dec.feed(data[i : i + 4096]))
    frames.extend(dec.flush())
    assert dec.packets == 59
    assert len(frames) == 59
    assert frames[0].shape == (900, 1600, 3)
    assert frames[0].dtype == np.uint8
    assert dec.frames == len(frames)


def test_the_first_frame_is_not_held_back_by_threading() -> None:
    dec = h264.Decoder()
    data = CLIP.read_bytes()
    fed = 0
    for i in range(0, len(data), 4096):
        out = dec.feed(data[i : i + 4096])
        fed = dec.packets
        if out:
            break
    assert fed <= 4, "a single-threaded decoder emits within the first few packets"


def test_feeding_nothing_is_harmless() -> None:
    dec = h264.Decoder()
    assert dec.feed(b"") == []
    assert dec.flush() == []
```

- [ ] Step 3: run `uv run pytest tests/test_play_h264.py -q`. Expected: FAIL with
      `ModuleNotFoundError: No module named 'brawlfarm.play.h264'`.

- [ ] Step 4: write `brawlfarm/play/h264.py`:

```python
"""Parser-fed H.264 decoding for the play stream.

The scrcpy server sends a raw H.264 elementary stream (Annex B). PyAV's file-object demuxer
does not decode it from a live socket; a codec context fed through ``parse()`` does. The
decoder runs on one thread on purpose: frame threading holds back about 18 packets before
the first frame comes out, 600 ms at 30 fps, measured on 2026-09-18 (spec, measured facts).
"""

from __future__ import annotations

import numpy as np


class Decoder:
    """Bytes in, BGR frames out. Chunking does not matter; the parser reassembles packets."""

    def __init__(self) -> None:
        import av  # the play extra; imported here so the package loads without it

        self._ctx = av.CodecContext.create("h264", "r")
        self._ctx.thread_count = 1
        self.packets = 0
        self.frames = 0

    def feed(self, data: bytes) -> list[np.ndarray]:
        """Decode whatever complete packets ``data`` completes. Returns zero or more frames."""
        out: list[np.ndarray] = []
        if not data:
            return out
        for packet in self._ctx.parse(data):
            self.packets += 1
            for frame in self._ctx.decode(packet):
                self.frames += 1
                out.append(frame.to_ndarray(format="bgr24"))
        return out

    def flush(self) -> list[np.ndarray]:
        """Drain the frames the decoder still holds. Only needed at end of stream."""
        out: list[np.ndarray] = []
        try:
            frames = self._ctx.decode()
        except Exception:  # a drained or closed context has nothing more to give
            return out
        for frame in frames:
            self.frames += 1
            out.append(frame.to_ndarray(format="bgr24"))
        return out
```

- [ ] Step 5: run `uv run pytest tests/test_play_h264.py -q`. Expected: 3 passed. If the first
      test reports 57 frames plus 2 on flush instead of 59 total, the assertion on `len(frames)`
      already includes the flush; if `dec.packets` is not 59, print it and fix the number in the
      test to what the fixture parses to (the fixture is fixed; the count is a fact about it).
- [ ] Step 6: run the gate.
- [ ] Step 7: commit:

```bash
git add brawlfarm/play/h264.py tests/test_play_h264.py tests/fixtures/play/stream-2s.h264
git commit -m "feat(play): single-threaded parser-fed H.264 decoder with a synthetic clip"
```

### Task 4: the stream

Files: create `brawlfarm/play/stream.py`; test `tests/test_play_stream.py`.

Interfaces:

- Consumes: `adb.push`, `adb.forward`, `adb.forward_remove`, `adb.shell_process`, `adb.AdbError`,
  `play.SERVER_JAR`, `play.SERVER_VERSION`, `h264.Decoder`.
- Produces: `stream.Stream(*, record: Path | None = None, clock=time.monotonic, connect=None,
spawn=None)` with `start() -> None`, `latest() -> tuple[np.ndarray | None, float | None]`,
  `stop() -> None`, attributes `error: str | None`, `frames: int`, `port: int | None`,
  `started_at: float | None`; constants `STALE_AFTER = 0.5`, `CONNECT_DEADLINE = 8.0`,
  `REMOTE_JAR`, `SERVER_ARGS`.

- [ ] Step 1: write the failing tests in `tests/test_play_stream.py`:

```python
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
    monkeypatch.setattr(adb, "push", lambda local, remote: calls.append(("push", Path(local), remote)))
    monkeypatch.setattr(adb, "forward", lambda port, remote: calls.append(("forward", port, remote)))
    monkeypatch.setattr(adb, "forward_remove", lambda port: calls.append(("forward_remove", port)))
    proc = FakeProc()
    monkeypatch.setattr(adb, "shell_process", lambda args: (calls.append(("shell", list(args))), proc)[1])
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
        assert calls[2][1][:4] == ["app_process", "/", "com.genymobile.scrcpy.Server", play.SERVER_VERSION]
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
    assert threading.active_count() >= 1  # the decode thread is joined, no leak assertion beyond this


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
```

- [ ] Step 2: run `uv run pytest tests/test_play_stream.py -q`. Expected: FAIL with
      `ModuleNotFoundError: No module named 'brawlfarm.play.stream'`.

- [ ] Step 3: write `brawlfarm/play/stream.py`:

```python
"""The play stream: the BlueStacks display as 30 fps frames, read-only.

Transport: the bundled scrcpy server jar is pushed over adb, started with control off, and
its raw H.264 comes back through an adb port forward. A thread decodes it and keeps only the
newest frame. Nothing here sends input: ``control=false`` is a literal in SERVER_ARGS and this
module imports no tap or swipe. Spec: docs/superpowers/specs/2026-09-18-play-mode.md section 2.
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
        self._stopping = False
        self._stopped = False
        self.port: int | None = None
        self.error: str | None = None
        self.frames = 0
        self.started_at: float | None = None

    # -- lifetime ----------------------------------------------------------------

    def start(self) -> None:
        """Push, forward, spawn, wait for the first byte, then decode in the background.
        Raises StreamError (after cleaning up) when no byte arrives before the deadline."""
        adb.push(play.SERVER_JAR, REMOTE_JAR)
        self.port = _free_port()
        adb.forward(self.port, REMOTE_SOCKET)
        self._proc = self._spawn(
            ["app_process", "/", "com.genymobile.scrcpy.Server", play.SERVER_VERSION, *SERVER_ARGS]
        )
        # Drain the server's output so its pipe never fills and stalls it; keep the tail.
        self._drain = threading.Thread(target=self._drain_output, name="play-stream-log", daemon=True)
        self._drain.start()
        self._sock = self._wait_for_bytes()
        if self._record_path is not None:
            self._record_fh = self._record_path.open("wb")
        self.started_at = self._clock()
        self._thread = threading.Thread(target=self._pump, name="play-stream", daemon=True)
        self._thread.start()

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
        raise StreamError(f"no stream bytes within {CONNECT_DEADLINE:g} s" + (f": {tail}" if tail else ""))

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
        if self.port is not None:
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
```

      Note on `_teardown` and `port`: `stop()` sets `_stopped` before calling it, so the port is
      cleared on a real stop and kept when `_wait_for_bytes` cleans up a failed start (the test
      reads `s.port` after `start()` and before `stop()`). Keep that line.

- [ ] Step 4: run `uv run pytest tests/test_play_stream.py -q`. Expected: 6 passed. The holding fakes block after the clip until stop() closes them, so the
      frame checks see a live stream; the EOF fakes drain in well under a second.
- [ ] Step 5: run the gate.
- [ ] Step 6: commit:

```bash
git add brawlfarm/play/stream.py tests/test_play_stream.py
git commit -m "feat(play): read-only scrcpy stream with the newest frame, staleness and raw recording"
```

### Task 5: per-match recording in observe mode

Files: create `brawlfarm/play/matchrec.py`; modify `brawlfarm/core/recorder.py` (add a property
after `status()`, about line 178), `brawlfarm/core/observer.py` (`__init__` lines 44 to 53, the loop
lines 136 to 150); tests `tests/test_play_matchrec.py`, extend `tests/test_observer.py`.

Interfaces:

- Consumes: `State` from `brawlfarm.core.states`, `play.available()`, `stream.Stream`.
- Produces: `Recorder.session_dir -> Path | None`; `matchrec.MatchRecorder(*, factory=None,
clock=time.monotonic)` with `observe(state: State, session: Path | None) -> None`,
  `close() -> None`, `recording -> Path | None`; constants `STOP_STATES`, `MAX_SECONDS = 360.0`.

- [ ] Step 1: write the failing tests in `tests/test_play_matchrec.py`:

```python
"""Per-match recording in observe mode: a stream opens on IN_MATCH, stays open through
UNKNOWN and POPUP, closes on a menu-side state, a closed session or the time cap, and one
stream failure switches match recording off for the rest of the session."""

from __future__ import annotations

from pathlib import Path

import pytest

from brawlfarm.core.states import State
from brawlfarm.play import matchrec


class FakeStream:
    def __init__(self, path: Path, *, fail: bool = False) -> None:
        self.path = path
        self.fail = fail
        self.started = False
        self.stopped = False

    def start(self) -> None:
        if self.fail:
            raise RuntimeError("no encoder")
        self.started = True

    def stop(self) -> None:
        self.stopped = True


@pytest.fixture()
def rec(monkeypatch):
    made: list[FakeStream] = []

    def factory(path: Path) -> FakeStream:
        s = FakeStream(path)
        made.append(s)
        return s

    monkeypatch.setattr(matchrec.play, "available", lambda: True)
    now = [0.0]
    r = matchrec.MatchRecorder(factory=factory, clock=lambda: now[0])
    return r, made, now


def test_a_match_opens_one_recording_and_a_results_screen_closes_it(rec, tmp_path: Path) -> None:
    r, made, now = rec
    r.observe(State.MENU, tmp_path)
    assert made == []
    r.observe(State.IN_MATCH, tmp_path)
    assert len(made) == 1 and made[0].started
    assert made[0].path == tmp_path / "match-1.h264"
    assert r.recording == tmp_path / "match-1.h264"
    r.observe(State.UNKNOWN, tmp_path)
    r.observe(State.POPUP, tmp_path)
    r.observe(State.IN_MATCH, tmp_path)
    assert len(made) == 1
    r.observe(State.RESULTS, tmp_path)
    assert made[0].stopped and r.recording is None
    r.observe(State.IN_MATCH, tmp_path)
    assert made[1].path == tmp_path / "match-2.h264"


def test_numbering_continues_from_files_already_in_the_session(rec, tmp_path: Path) -> None:
    r, made, now = rec
    (tmp_path / "match-1.h264").write_bytes(b"")
    (tmp_path / "match-2.h264").write_bytes(b"")
    r.observe(State.IN_MATCH, tmp_path)
    assert made[0].path == tmp_path / "match-3.h264"


def test_a_closed_session_and_the_time_cap_stop_the_recording(rec, tmp_path: Path) -> None:
    r, made, now = rec
    r.observe(State.IN_MATCH, tmp_path)
    r.observe(State.IN_MATCH, None)
    assert made[0].stopped
    r.observe(State.IN_MATCH, tmp_path)
    now[0] += matchrec.MAX_SECONDS + 1
    r.observe(State.UNKNOWN, tmp_path)
    assert made[1].stopped


def test_a_stream_failure_disables_recording_for_the_session(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(matchrec.play, "available", lambda: True)
    made: list[FakeStream] = []

    def factory(path: Path) -> FakeStream:
        s = FakeStream(path, fail=True)
        made.append(s)
        return s

    r = matchrec.MatchRecorder(factory=factory)
    r.observe(State.IN_MATCH, tmp_path)
    r.observe(State.RESULTS, tmp_path)
    r.observe(State.IN_MATCH, tmp_path)
    assert len(made) == 1
    other = tmp_path / "other"
    other.mkdir()
    r.observe(State.MENU, None)
    r.observe(State.IN_MATCH, other)
    assert len(made) == 2, "a new session gets a fresh chance"


def test_without_the_play_extra_nothing_is_recorded(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(matchrec.play, "available", lambda: False)
    calls = []
    r = matchrec.MatchRecorder(factory=lambda path: calls.append(path))
    r.observe(State.IN_MATCH, tmp_path)
    assert calls == [] and r.recording is None


def test_close_stops_an_open_recording(rec, tmp_path: Path) -> None:
    r, made, now = rec
    r.observe(State.IN_MATCH, tmp_path)
    r.close()
    assert made[0].stopped and r.recording is None
```

- [ ] Step 2: run `uv run pytest tests/test_play_matchrec.py -q`. Expected: FAIL with
      `ModuleNotFoundError: No module named 'brawlfarm.play.matchrec'`.

- [ ] Step 3: add the property to `Recorder` in `brawlfarm/core/recorder.py`, after `status()`:

```python
    @property
    def session_dir(self) -> Path | None:
        """The open session's folder, or None between sessions."""
        return self._session
```

- [ ] Step 4: write `brawlfarm/play/matchrec.py`:

```python
"""Per-match recording for observe mode.

While the frame recorder has a session open, every match the classifier sees becomes one
``match-N.h264`` in that session folder: the play stream's raw bytes, no re-encode. The
farm worker gets the same through its play session in a later pull request. Spec:
docs/superpowers/specs/2026-09-18-play-mode.md section 10.
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
STOP_STATES = frozenset({State.RESULTS, State.TROPHY_SCREEN, State.MENU, State.MATCHMAKING, State.DISCONNECT})
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
        self._said_missing = False

    @property
    def recording(self) -> Path | None:
        return self._path

    def observe(self, state: State, session: Path | None) -> None:
        if self._stream is not None:
            over = (
                session is None
                or session != self._session
                or state in STOP_STATES
                or (self._opened_at is not None and self._clock() - self._opened_at >= MAX_SECONDS)
            )
            if over:
                self._stop()
            return
        if state != State.IN_MATCH or session is None:
            return
        if not play.available():
            if not self._said_missing:
                log.info("match recording off: the play extra is not installed")
                self._said_missing = True
            return
        if self._disabled_for == session:
            return
        self._start(session)

    def _start(self, session: Path) -> None:
        n = len(list(session.glob("match-*.h264"))) + 1
        path = session / f"match-{n}.h264"
        try:
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
```

- [ ] Step 5: wire observe mode in `brawlfarm/core/observer.py`. In the imports add
      `from brawlfarm.play.matchrec import MatchRecorder`. In `Observer.__init__` after the
      `Recorder(...)` call add `self.matches = MatchRecorder()`. In `run()`, right after
      `state = states.classify(screen, phase=None)`, add
      `self.matches.observe(state, self.recorder.session_dir)`. In the `finally` block, before
      `self.recorder.close()`, add `self.matches.close()`.

- [ ] Step 6: add to `tests/test_observer.py` (uses the existing `data` fixture):

```python
def test_a_match_frame_opens_a_match_recording_in_the_session(data: Path, tmp_path: Path, monkeypatch) -> None:
    from brawlfarm.core import states
    from brawlfarm.core.states import State
    from brawlfarm.play import matchrec

    opened: list[Path] = []

    class FakeStream:
        def __init__(self, path: Path) -> None:
            opened.append(path)

        def start(self) -> None:
            pass

        def stop(self) -> None:
            pass

    monkeypatch.setattr(matchrec.play, "available", lambda: True)
    monkeypatch.setattr(matchrec, "_default_factory", FakeStream)
    monkeypatch.setattr(states, "classify", lambda screen, phase=None: State.IN_MATCH)
    observer.Observer(max_minutes=0.0).run()
    session = sorted((tmp_path / "calibration" / "recordings" / "alpha").iterdir())[0]
    assert opened == [session / "match-1.h264"]
```

- [ ] Step 7: run `uv run pytest tests/test_play_matchrec.py tests/test_observer.py
    tests/test_core_imports.py -q`. Expected: all passed. `test_core_imports` proves observer
      still imports in a bare subprocess (matchrec imports no PyAV at import time).
- [ ] Step 8: run the gate.
- [ ] Step 9: commit:

```bash
git add brawlfarm/play/matchrec.py brawlfarm/core/recorder.py brawlfarm/core/observer.py tests/test_play_matchrec.py tests/test_observer.py
git commit -m "feat(play): record each match observe mode sees as match-N.h264 in the session"
```

### Task 6: the health key and the docs

Files: modify `brawlfarm/api/app.py` (health route, lines 169 to 179), `README.md` (install
lines near line 50 and the paragraph near line 89), `docs/calibration.md` (after the recorder
paragraph near line 54), `CONTRIBUTING.md` (safety rails list); create
`docs/notes/2026-09-18-play-stream-spike.md`; extend `tests/test_api_app.py`.

Interfaces:

- Consumes: `play.available()`.
- Produces: `GET /api/health` payload key `play_available: bool`.

- [ ] Step 1: add to `tests/test_api_app.py` next to the existing health test:

```python
def test_health_says_whether_the_play_extra_is_installed(api, monkeypatch) -> None:
    from brawlfarm import play

    client, _sup, _home = api
    monkeypatch.setattr(play, "available", lambda: False)
    assert client.get("/api/health").json()["play_available"] is False
    monkeypatch.setattr(play, "available", lambda: True)
    assert client.get("/api/health").json()["play_available"] is True
```

- [ ] Step 2: run `uv run pytest tests/test_api_app.py -q`. Expected: the new test FAILS with
      `KeyError: 'play_available'`.
- [ ] Step 3: in `brawlfarm/api/app.py` add `from brawlfarm import play` to the imports and
      `"play_available": play.available(),` to the health payload, after `"uptime_s"`. Extend the
      docstring: "and whether the play extra is installed".
- [ ] Step 4: run `uv run pytest tests/test_api_app.py -q`. Expected: all passed.
- [ ] Step 5: docs.
      README.md, after the desktop install line: `uv tool install "brawlfarm[play]"     # the same,
    plus the play stream (PyAV)` and `uv tool install "brawlfarm[play-gpu]" # the same, plus
    onnxruntime on CUDA for the detector`. Near the `--window` paragraph add one paragraph:
      "The play extras add a 30 fps video feed of the instance for the in-match play mode that
      is being built (spec in docs/superpowers/specs/2026-09-18-play-mode.md). In observe mode,
      with the recorder on, each match is also saved as `match-N.h264` in the session folder.
      `uv sync --group play` installs it in a checkout."
      docs/calibration.md, after the "The recorder never deletes anything" paragraph: "When the
      play extra is installed, observe mode also saves each match the classifier sees as
      `match-N.h264` in the session folder: the instance's own video, 1600 x 900 at 30 fps, as a
      raw H.264 stream. ffmpeg, PyAV and VLC open it; `ffmpeg -i match-1.h264 -c copy
    match-1.mp4` wraps it in a container. Those files count toward the session's size cap."
      CONTRIBUTING.md safety rails list, one bullet: "The play stream is read-only. The scrcpy
      server runs with control off, and nothing under `brawlfarm/play/` may import a tap or
      swipe."
      `docs/notes/2026-09-18-play-stream-spike.md`: the spike as measured (copy the numbers from
      the spec's "Measured facts" section: fps, gaps, BGR cost, bandwidth, CPU, encoder, the
      decoder threading measurement), the two gotchas (adb accepts before the server listens;
      PyAV's file demuxer versus the parser path), and the layers paragraph from the spec. Title
      "Play stream: scrcpy over adb, measured", Date line, Status "adopted in pull request 1".
- [ ] Step 6: run the gate (the scrub check covers the new docs).
- [ ] Step 7: commit:

```bash
git add brawlfarm/api/app.py tests/test_api_app.py README.md docs/calibration.md CONTRIBUTING.md docs/notes/2026-09-18-play-stream-spike.md
git commit -m "feat(api): report the play extra in health; document the stream and the match files"
```

### Task 7: the live pass tool

Files: create `tools/play/__init__.py` (empty) and `tools/play/stream_check.py`; no unit test
(it drives a real instance); ruff applies.

Interfaces:

- Consumes: `stream.Stream`, `adb.screencap`, `vision.score`, `vision.TEMPLATE_NAMES`, `config`,
  `psutil` (already a dependency).
- Produces: a command `uv run python tools/play/stream_check.py --seconds 60 [--record PATH]`
  that prints fps, gap p50 and p95, frames, BlueStacks CPU before and during, host CPU, and the
  template score drift table, and exits 0.

- [ ] Step 1: write `tools/play/stream_check.py`:

```python
"""Live pass for the play stream. Read-only against the configured instance: streams for N
seconds, reports fps, frame gaps and CPU, and scores every template on one screencap and on
the stream frame taken at the same moment so the drift between the two capture paths is a
number in the pull request body.

    uv run python tools/play/stream_check.py --seconds 60
    uv run python tools/play/stream_check.py --seconds 20 --record out.h264
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

import psutil

from brawlfarm.core import adb, config, vision
from brawlfarm.play import stream


def _hd_player() -> psutil.Process | None:
    for p in psutil.process_iter(["name"]):
        if p.info["name"] == "HD-Player.exe":
            return p
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seconds", type=float, default=60.0)
    ap.add_argument("--record", type=Path, default=None)
    args = ap.parse_args(argv)

    adb.connect()
    hp = _hd_player()
    idle = hp.cpu_percent(interval=3.0) if hp else float("nan")

    s = stream.Stream(record=args.record)
    s.start()
    print(f"stream up on port {s.port}; sampling {args.seconds:g} s")
    if hp:
        hp.cpu_percent(None)
    psutil.cpu_percent(None)
    gaps: list[float] = []
    last = s.frames
    last_t = time.monotonic()
    end = last_t + args.seconds
    drift_rows: list[tuple[str, float, float]] = []
    try:
        while time.monotonic() < end:
            time.sleep(0.005)
            if s.frames != last:
                now = time.monotonic()
                gaps.append((now - last_t) * 1000)
                last, last_t = s.frames, now
            if s.error:
                print("stream error:", s.error)
                return 1
            if not drift_rows and s.frames > 30:
                shot = adb.screencap()
                frame, _age = s.latest()
                if frame is not None:
                    for name in vision.TEMPLATE_NAMES:
                        drift_rows.append(
                            (name, float(vision.score(shot, name)), float(vision.score(frame, name)))
                        )
    finally:
        busy = hp.cpu_percent(None) if hp else float("nan")
        host = psutil.cpu_percent(None)
        s.stop()

    span = max(1e-6, (last_t - (s.started_at or last_t)))
    print(f"frames {s.frames} in {span:.1f} s: {s.frames / span:.1f} fps")
    if gaps:
        gaps.sort()
        print(f"gap ms p50 {statistics.median(gaps):.1f} p95 {gaps[int(len(gaps) * 0.95)]:.1f} max {gaps[-1]:.0f}")
    print(f"HD-Player cpu % of one core: idle {idle:.0f}, streaming {busy:.0f}; host all cores {host:.0f}")
    if drift_rows:
        print("template score, screencap vs stream frame (same moment):")
        worst = 0.0
        for name, a, b in drift_rows:
            worst = max(worst, abs(a - b))
            print(f"  {name:16s} {a:.4f} {b:.4f} {b - a:+.4f}")
        print(f"largest drift {worst:.4f}")
    if args.record is not None:
        print(f"recorded {args.record} ({args.record.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] Step 2: run `uv run ruff check tools/play && uv run ruff format --check tools/play`; fix
      what it names.
- [ ] Step 3: run the tool for 20 s on Pie64 with `--record` into the scratchpad; then for 60 s
      without. Both must exit 0. Keep both outputs for the pull request body. Do not run it
      while a farm worker is mid-session on the same instance unless the owner's panel is parked;
      the stream is read-only but the encoder costs the instance a core.
- [ ] Step 4: run the gate.
- [ ] Step 5: commit:

```bash
git add tools/play
git commit -m "tools(play): stream_check, the live pass for the play stream"
```

### Task 8: whole-branch review, evidence, pull request

- [ ] Step 1: `git log --oneline main..HEAD` shows seven commits; run the full gate once more.
- [ ] Step 2: whole-branch sonnet review of `git diff main...HEAD`; fix findings, re-review once.
- [ ] Step 3: the recorded match: with the owner's instance parked, start observe mode on
      Pie64 with the play extra installed, drive one farm match through the API from a second
      panel or play one match by hand, and confirm `match-1.h264` lands in the session folder
      and opens with `ffprobe`. If observe mode cannot be driven without the owner, record the
      match with `stream_check.py --record` during a farm match instead and say so in the body.
- [ ] Step 4: open the pull request `play/stream` against `main` with sections What, Safety
      (read-only stream, control off, no farm-loop change), How to verify (the gate, the tool),
      Evidence (the tool outputs, the drift table, the match file's ffprobe line, both extras
      installing into fresh venvs, the CUDA provider line), and the scrub check result.

## Self-review

Spec coverage: section 2 (Tasks 1, 3, 4), section 7 health key (Task 6), section 9 first line
(Task 6 CONTRIBUTING), section 10 recorder (Task 5), the live pass proof (Tasks 7, 8). The
farm-session recording is deferred to pull request 6 by the spec. Type consistency: `Stream.start`,
`latest`, `stop`, `error`, `frames`, `port`, `started_at` are used with the same names in Tasks 4,
5 and 7; `MatchRecorder.observe(state, session)` in Tasks 5 and the observer wiring;
`Recorder.session_dir` in Task 5. Placeholders: none.
