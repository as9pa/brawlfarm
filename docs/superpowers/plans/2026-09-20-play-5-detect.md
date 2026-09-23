# Play mode 5 of 7: detector module and shadow mode. Implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** the worker can load `play.onnx` and, with the `shadow` setting on, run it beside an untouched farm loop during a match, logging its boxes and sending no input.

**Architecture:** `brawlfarm/play/detect.py` owns the ONNX contract at run time (its own copy of the tools' pre-processing and decoding, pinned to them by a parity test). `brawlfarm/play/session.py` `PlaySession` is driven once per controller tick, the way `MatchRecorder` is; a daemon thread inside it starts the stream, loads the detector, reads the newest frame at 5 Hz at most and appends one JSON line per inference. Feed rows are only ever emitted from the controller thread: `observe()` returns them, the controller writes them.

**Tech stack:** Python 3.13, numpy, OpenCV, onnxruntime (already a core dependency through rapidocr), PyAV behind the play extra, pytest.

**Spec:** `docs/superpowers/specs/2026-09-18-play-mode.md`, sections 1 (fallback rule, shadow rule), 3, 5 (shadow half, feed rows). The owner moved this pull request ahead of pull request 4 (first model) in chat on 2026-09-20, because 4 waits on the owner's labels.

## Global constraints

- This pull request sends no input. Nothing under `brawlfarm/play/` imports or calls a tap, swipe or key helper. With `shadow` off (the default) the worker's behaviour is unchanged to the byte: no import of `onnxruntime` or `av`, no thread, no file.
- With `shadow` on, nothing the session does may raise into the controller, block a controller tick for longer than a lock hand-off, or write a feed row from a thread other than the controller's.
- Never-tap logic, verify-then-act, the 1600x900 assertion, tap coordinates, OCR needles and templates in `brawlfarm/core/` are not touched. `brawlfarm/core/config.py` gains one flag outside its calibration blocks.
- A missing model is the normal case at merge time (no model ships until the calibration pull request). It is a quiet fallback, not an error in the log.
- A per-class threshold missing from `play.json` makes the model invalid; never invent a threshold.
- A `smoke: true` model may run in shadow and must say so in `play_on` and in the file header. Docstring invariant for pull request 6: a smoke model never drives.
- Shadow files hold boxes and timings only: no pixels, no names, no tags. They live under the instance's data folder, never in the repository.
- No em-dashes, no emoji, no Windows profile path or user name in any file (say `%LOCALAPPDATA%`). `../bsutil` is never named.
- Commands in the worktree: plain single commands; no `&&`, no `$(...)`, no `VAR=` prefixes, no `cd`, no `git -c`; stage files by name. Check `git config user.email` is `220869966+as9pa@users.noreply.github.com` before a commit. Commit messages end with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Gate: `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run python tools/scrub_check.py` printing `0 hit(s)`; in `brawlfarm/web`: `pnpm typecheck`, `pnpm test`.
- No visible web UI change in this pull request (the owner reviews UI proposals on a page first). The TypeScript settings type and its fixture gain the key; no component, no copy.

## Established facts (do not re-derive)

- Controller main loop: `adb.screencap()` at `brawlfarm/core/controller.py:1606`, `states.classify` at 1613, `self.recorder.observe(screen, state, self.phase)` at 1617, `finally:` with `self.recorder.close()` at 1694 to 1701. Seven ways leave the playing phase (results, menu, match timeout, in-match modal, two in `recover()`, the results-stuck path) plus stop and crash; a per-tick `observe(state, phase)` covers all of them, so `_enter_match` and `_end_match` are not edited.
- `brawlfarm/play/matchrec.py` is the house style: injected factory, injected clock, `STOP_STATES`, `MAX_SECONDS = 360.0`, "said once" flags, every exception caught and logged, `_await_stop` so a dead stream does not restart inside the same match. Its test double is `FakeStream` in `tests/test_play_matchrec.py:16`.
- `Stream(*, record=None, clock=..., connect=None, spawn=None)`, `start()` (blocks up to 8 s, raises `StreamError`), `latest() -> (frame, age) | (None, None)` (None when older than 0.5 s), `stop()` (idempotent), `.error`. The adb helpers it uses are one subprocess per call; the only module global in `brawlfarm/core/adb.py` is `_raw_cap_unsupported`, which `Stream` never touches, so `start()` may run on the session thread.
- Settings: `BehaviorSection` at `brawlfarm/settings.py:44`; `worker_env()` at 203 stringifies flags with `_flag`; `brawlfarm/core/config.py:768` shows the read (`BUSH_HIDE = os.environ.get("BRAWL_BUSH_HIDE", "1") != "0"`). Sections forbid unknown keys; a missing key takes the default. The web PUT sends back a clone of the GET document (`brawlfarm/web/src/settings/useSettingsPatch.ts:201`), so a key the UI does not render survives a save.
- Feed: `self.dl.event(kind, **fields)` (`brawlfarm/core/datalog.py:188`); categories are frozensets in `brawlfarm/api/feed.py:31-65`.
- ONNX contract, `tools/play/thresholds.py`: `preprocess` (119 to 131: BGR to RGB, plain `cv2.resize` to size x size with `INTER_LINEAR`, `/255`, ImageNet mean `[0.485, 0.456, 0.406]` and deviation `[0.229, 0.224, 0.225]`, NCHW float32, batch of one); `decode` (86 to 116: `dets` cxcywh 0..1, `labels` logits, last column is background and dropped, sigmoid, column k is class index k, no NMS, no top-k, sorted by score descending). `play.json` (`tools/play/export.py:249-277`): `model`, `rfdetr`, `input{name,size,layout,color,mean,std}`, `outputs{boxes,logits,box_format}`, `classes`, `thresholds{name: float}`, `training_set_hash`, `smoke`, `validation`, `exported`. Provider pattern: `tools/play/score.py:39-56`. `tools/` is not in the wheel; tests may import it (`pythonpath = ["."]`).
- `config.HOME_DIR` (`config.py:26`) and `config.DATA_DIR` (`config.py:32`, per instance) exist. There is no models folder helper yet.

## File map

| File                                                                      | Change                                                                         |
| ------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| `brawlfarm/play/detect.py`                                                | new: `Box`, `ModelMissing`, `ModelInvalid`, `preprocess`, `decode`, `Detector` |
| `tests/test_play_detect.py`                                               | new                                                                            |
| `brawlfarm/play/session.py`                                               | new: `PlaySession`                                                             |
| `tests/test_play_session.py`                                              | new                                                                            |
| `brawlfarm/settings.py`, `brawlfarm/core/config.py`                       | `shadow` flag end to end                                                       |
| `brawlfarm/web/src/api/types.ts`, `brawlfarm/web/src/test/fixtures.ts`    | the key in the type and the fixture, nothing else                              |
| `tests/test_settings.py`, `tests/test_api_settings.py`                    | the flag round-trips and reaches the env                                       |
| `brawlfarm/core/controller.py`, `brawlfarm/api/feed.py`                   | wiring and feed categories                                                     |
| `tests/test_controller_play.py` (or the controller test module that fits) | wiring tests                                                                   |
| `README.md`, `docs/superpowers/specs/2026-09-18-play-mode.md`             | how to turn shadow on; the per-tick design; the order change                   |

---

### Task 1: `brawlfarm/play/detect.py`

Files: create `brawlfarm/play/detect.py`, `tests/test_play_detect.py`.

Interfaces, exact:

```python
MODEL_FILE = "play.onnx"
META_FILE = "play.json"
MEAN = (0.485, 0.456, 0.406)
STD = (0.229, 0.224, 0.225)

@dataclass(frozen=True)
class Box:
    cls: str
    score: float
    x: float  # left, in pixels of the frame given to detect()
    y: float  # top
    w: float
    h: float

class ModelMissing(Exception): ...   # play.onnx or play.json is not there: the normal case
class ModelInvalid(Exception): ...   # the files are there and cannot be trusted

def models_dir() -> Path                      # config.HOME_DIR / "models"
def preprocess(bgr: np.ndarray, size: int) -> np.ndarray
def decode(dets, logits, width: int, height: int, classes: Sequence[str], thresholds: Mapping[str, float]) -> list[Box]

class Detector:
    name: str; provider: str; smoke: bool; training_set_hash: str; classes: tuple[str, ...]; size: int
    @classmethod
    def load(cls, folder: Path | None = None, *, session_factory: Callable[[Path], Any] | None = None) -> "Detector"
    def detect(self, frame: np.ndarray) -> list[Box]
```

Rules:

- `preprocess` and `decode` are this module's own copy of the tools' logic. `decode` keeps a box only when its sigmoid score is `>=` its class's threshold, sorted by score descending. A leading batch dimension of one is accepted.
- `load`: `ModelMissing` when either file is absent. `ModelInvalid` (message names the key) when `play.json` is not an object, `classes` is not a non-empty list of distinct strings, any class lacks a threshold or a threshold is not a number in (0, 1], `input.size` is not a positive int, or `input.name`, `outputs.boxes`, `outputs.logits` are not strings. `name` is `model`, `smoke` is `bool(meta.get("smoke", False))`, `training_set_hash` is `str(meta.get("training_set_hash", ""))`.
- Default session factory imports `onnxruntime` inside its body. When `"CUDAExecutionProvider"` is in `ort.get_available_providers()`: call `ort.preload_dlls()` if it exists (a failure is logged at info and ignored), ask for CUDA then CPU; otherwise CPU only. `provider` is `session.get_providers()[0]`, logged once at info as `play detector: <name> on <provider>`.
- `detect`: run the session with `{input_name: preprocess(frame, size)}`, asking for the two outputs by name in the order boxes, logits. When the logits' last dimension is not `len(classes) + 1`, raise `ModelInvalid` naming both numbers. Boxes are scaled by the frame's own width and height.
- Module imports nothing that can send input and does not import `onnxruntime`, `av` or `cv2` at import time (`cv2` inside `preprocess`, as the tools do).

Tests (`tests/test_play_detect.py`), all with a fake session (an object with `run(names, feeds)`, `get_providers()`), no real ONNX file:

- parity: for a seeded random `dets` (300, 4) and `logits` (300, 16), `detect.decode` equals `tools.play.thresholds.decode(..., floor=0.0)` filtered by the same per-class thresholds, box for box (class name through `tools.play.classes.CLASSES`, coordinates to 1e-9). For a seeded random BGR image (900, 1600, 3), `detect.preprocess(img, 384)` equals `thresholds.preprocess(img, 384)` exactly. `detect.MEAN`/`STD` equal the tools' constants.
- a box at exactly its threshold is kept; one below is dropped; two classes with different thresholds are judged separately.
- `load` raises `ModelMissing` for an empty folder and when only one of the two files exists.
- `load` raises `ModelInvalid` for: a class without a threshold, a threshold of 0 and of 1.5, duplicate class names, `input.size` of 0, a non-object JSON.
- `detect` raises `ModelInvalid` when the logits have the wrong number of columns.
- `detect` returns pixel boxes for a 1600 x 900 frame and scales with a 800 x 450 frame.
- `smoke`, `name`, `training_set_hash`, `provider` come through; the fake factory receives the `play.onnx` path.
- import hygiene: importing `brawlfarm.play.detect` in a subprocess (`sys.executable -c`) leaves `onnxruntime`, `av` and `cv2` out of `sys.modules`.

Steps: write the failing tests, run `uv run pytest tests/test_play_detect.py -q` and see them fail, implement, run to green, run the full gate, commit `feat(play): the detector module reads play.onnx the way the tools wrote it`.

### Task 2: `brawlfarm/play/session.py`

Files: create `brawlfarm/play/session.py`, `tests/test_play_session.py`.

Interfaces, exact:

```python
RATE_HZ = 5.0            # most inferences per second; a farm tick is about 0.75 s
STALE_LIMIT = 5.0        # seconds without a fresh frame before the session gives up
MAX_SECONDS = 360.0      # as matchrec: a backstop, not the rule
KEEP_FILES = 50          # newest shadow files kept per instance
JOIN_TIMEOUT = 3.0       # seconds close() waits for the thread

Event = tuple[str, dict]

class PlaySession:
    def __init__(self, *, folder: Path | None = None, stream_factory=None, detector_factory=None,
                 clock=time.monotonic, sleep=time.sleep, threaded: bool = True) -> None
    @property
    def active(self) -> bool
    def observe(self, state: State, phase: str) -> list[Event]
    def close(self) -> list[Event]
    def _begin(self) -> None      # what the thread runs first: stream start, detector load, header line
    def _tick(self) -> bool       # one iteration; False when the session is over
```

Behaviour:

- `folder` defaults to `config.DATA_DIR / "shadow"`. `stream_factory()` defaults to `stream.Stream()` imported inside the factory; `detector_factory()` defaults to `detect.Detector.load()` imported inside the factory. The detector is loaded once per process and kept across matches; a `ModelInvalid` or `ModelMissing` is remembered and never retried in this process.
- `observe` starts a session when `phase == "playing" and state == State.IN_MATCH`, none is active, and nothing has disabled it. It ends the session when `phase != "playing"`, `state in matchrec.STOP_STATES`, `MAX_SECONDS` have passed, or the thread has reported a failure. UNKNOWN and POPUP inside the playing phase keep it open.
- `play.available()` false: one `("play_fallback", {"reason": "extra_missing", "shadow": True})` for the life of the process, then nothing. Model missing or invalid: the same with `model_missing` or `model_invalid` (plus `detail` for invalid), once per process.
- With `threaded=True`, starting a session starts a daemon thread named `play-shadow` that runs `_begin()` then `_tick()` until it returns False or the stop flag is set, sleeping so that ticks start at most `RATE_HZ` times a second. With `threaded=False` nothing runs on its own; tests call `_begin()` and `_tick()`.
- `_begin`: start the stream (`stream_start` failure), load the detector, prune the folder to `KEEP_FILES - 1` newest `*.jsonl`, open `<folder>/<YYYYmmdd-HHMMSS>.jsonl` (local time; a numeric suffix `-2`, `-3` if the name exists) and write the header line `{"model", "training_set_hash", "provider", "smoke", "classes", "rate_hz", "started"}` (`started` ISO local time). Then queue `("play_on", {"shadow": True, "model", "provider", "smoke", "start_ms"})`, `start_ms` being the time `_begin` took.
- `_tick`: if the stream's `error` is set, fail with `stream_error`. `latest()`; on `(None, None)` count a stale tick, and fail with `stale` once `STALE_LIMIT` seconds have passed since the last fresh frame (or since `_begin`). Otherwise time `detector.detect(frame)` and append `{"t": seconds since the session began (3 decimals), "age": (3 decimals), "ms": (1 decimal), "boxes": [[cls, score (3 decimals), x, y, w, h (ints)], ...]}`, flushed per line. Any exception from `detect` fails with `detector_error` and `detail=repr(exc)`.
- A failure: stop the stream, close the file, queue exactly one `("play_fallback", {"reason", "shadow": True, ...})`, and wait for the match to end before a new session may start (the `_await_stop` idea from matchrec). No `play_summary` after a failure that happened before the first inference; after one, the summary is still queued.
- A normal end queues `("play_summary", {"shadow": True, "frames", "seconds", "fps", "ms_p50", "ms_p95", "stale_ticks", "boxes": {cls: count}, "file": <file name only>})`.
- The thread never calls the datalog. It appends events to a list under a lock; `observe()` and `close()` drain and return them. `observe` and `close` never raise: any exception inside them is logged at warning and turned into one `play_fallback` with reason `session_error`.
- `close()` ends an active session (setting the stop flag, joining up to `JOIN_TIMEOUT`, then stopping the stream from the calling thread regardless) and returns what is queued. Closing twice is a no-op returning `[]`.

Tests (`tests/test_play_session.py`), `threaded=False` unless said, fake stream modelled on `tests/test_play_matchrec.py:16` with a settable `latest` result and `error`, fake detector returning fixed boxes, fake clock:

- start only on `("playing", IN_MATCH)`; not on IN_MATCH in another phase; not on `playing` with MENU.
- the happy path: `_begin`, three `_tick`s, then `observe(State.RESULTS, "playing")` returns `play_on` then `play_summary` with `frames == 3`, the box counts, and a file with a header and three lines that parse as JSON; no pixel data keys.
- each way out ends the session and stops the stream: phase `returning`, phase `at_menu`, state MENU, state DISCONNECT, `MAX_SECONDS`.
- UNKNOWN and POPUP in `playing` keep it open.
- each failure gives exactly one `play_fallback` with its reason and never raises: stream factory raises, `start()` raises, `error` set mid-match, stale past `STALE_LIMIT` (and not before), detector raises, detector factory raises `ModelMissing`, raises `ModelInvalid`.
- after a mid-match failure no new session starts until a stop state was seen; after `model_missing` none ever starts and no second fallback row appears; the same for `extra_missing` (monkeypatch `importlib.util.find_spec` as the matchrec tests do).
- the detector factory is called once across two matches.
- `KEEP_FILES`: with 55 old files present, a new session leaves 50.
- `close()` mid-session stops the stream, returns a summary, and a second `close()` returns `[]`.
- one threaded test with real threads and a fake stream: a session runs, `observe(RESULTS)` ends it within `JOIN_TIMEOUT`, the thread is gone (`threading.enumerate()` has no `play-shadow`), and the rate cap held (with `RATE_HZ` monkeypatched high the test stays fast; assert ticks happened, not timing).
- rails: no module under `brawlfarm/play/` imports a name containing `tap`, `swipe`, `input_` or `keyevent` from `brawlfarm.core.adb` (parse the sources with `ast`); importing `brawlfarm.play.session` in a subprocess leaves `onnxruntime` and `av` out of `sys.modules`.

Steps: failing tests, implement, green, full gate, commit `feat(play): a shadow session runs the detector beside the farm loop and sends nothing`.

### Task 3: the `shadow` setting

Files: `brawlfarm/settings.py`, `brawlfarm/core/config.py`, `brawlfarm/web/src/api/types.ts`, `brawlfarm/web/src/test/fixtures.ts`, `tests/test_settings.py`, `tests/test_api_settings.py`.

- `BehaviorSection.shadow: bool = False` with the comment `# play mode's detector runs beside the farm loop and logs; sends no input`.
- `worker_env`: `"BRAWL_PLAY_SHADOW": _flag(b.shadow)` after the `BRAWL_BUSH_HIDE` line.
- `config.py`, next to `BUSH_HIDE` but outside any calibration block: `PLAY_SHADOW = os.environ.get("BRAWL_PLAY_SHADOW", "0") == "1"` with a one-line comment. Default off when the variable is absent.
- `types.ts`: `shadow: boolean;` in the behaviour block of `AppSettings`; `fixtures.ts`: `shadow: false`. No component and no copy changes; if a web test enumerates behaviour keys and fails, report it instead of adding UI.
- Tests: the default is False; an old `config.toml` without the key loads; True round-trips through save and load and through PUT and GET; `worker_env` carries `"1"` and `"0"`; `config.PLAY_SHADOW` follows the env (reload the module under `monkeypatch.setenv`, the way the existing flag tests do; if none do, test the expression through a subprocess).

Steps: failing tests, implement, green, full gate including `pnpm typecheck` and `pnpm test` in `brawlfarm/web`, commit `feat(settings): a shadow flag reaches the worker, off by default`.

### Task 4: controller wiring and feed categories

Files: `brawlfarm/core/controller.py`, `brawlfarm/api/feed.py`, a controller test module, `tests/test_api_feed.py` (or the feed test module that exists).

- Controller `__init__`: `self.play = None`. A helper `_play_shadow_on(self) -> bool` returning `config.PLAY_SHADOW` (the one expression pull request 6 will edit). When it is true, build the session lazily on first use: `from brawlfarm.play import session` inside the method, so a worker with shadow off never imports the module.
- One method `_play_observe(self, state) -> None`: returns at once when shadow is off; otherwise `for kind, fields in self.play.observe(state, self.phase): self.dl.event(kind, **fields)`, the whole body inside `try/except Exception` that logs once and sets a flag that turns shadow off for the rest of the process. Call it on the line after `self.recorder.observe(screen, state, self.phase)` (`controller.py:1617`), before the DISCONNECT and POPUP `continue`s so those ticks are seen.
- In the `finally` at 1694, after the recorder's close and in its own `try/except`: drain `self.play.close()` into `self.dl.event` when a session object exists.
- `feed.py`: `play_on` and `play_summary` join `MATCHES`; `play_fallback` joins `ERRORS`.
- Do not touch `_enter_match`, `_end_match`, any tap, any coordinate, or anything under a calibration block. Do not add web feed copy; report how an unknown kind renders today (`brawlfarm/web/src/lib/feedText.ts`) so the controller can put it in the pull request body.

Tests: with `PLAY_SHADOW` false the controller never imports `brawlfarm.play.session` and `_play_observe` does nothing; with it true and a stub session injected (`self.play = Stub()`), events returned by `observe` reach `dl.event` in order, a raising stub turns shadow off after one log line and the loop method does not raise, and the `finally` path drains `close()`. Feed: the three kinds land in their categories. Use the controller test helpers that exist (find how other controller tests build a controller without adb; if none can, test `_play_observe` and the close helper as plain methods on a minimal instance and say so in the report).

Steps: failing tests, implement, green, full gate, commit `feat(core): the farm loop ticks the shadow session and writes its feed rows`.

### Task 5: documents, then the controller's live pass

Documents (a sonnet implementer): `README.md` gains a short "Shadow mode" part under the play extra section: what it does, that it sends no input, how to turn it on (`[behavior]` `shadow = true` in `config.toml` under `%LOCALAPPDATA%\brawlfarm`, then restart the instance), what it needs (the play extra, `models\play.onnx` and `models\play.json`), where the files go (`instances\<name>\shadow\`, newest 50 kept), the three feed rows, and the cost (the stream takes about 60 percent of one BlueStacks core while a match runs). The spec: section 1's shadow rule says the `shadow` setting alone turns shadow on until pull request 6 adds `plan.play`; section 5 says the session is driven per tick like the match recorder, with the reasons (seven exits from the playing phase); the build order notes that 5 was built before 4 by the owner's decision on 2026-09-20. No em-dashes, no emoji. Commit `docs(play): shadow mode, how to turn it on and what it writes`.

Live pass (the controller, not a subagent): copy the smoke model from the pull request 2 scratch export into `%LOCALAPPDATA%\brawlfarm\models\`, turn `shadow` on, run Pie64 for a few matches, then a few with it off. Report from the datalog: median and p95 controller tick interval inside the playing phase and the `adb_error` count, on against off; `start_ms`; frames, fps and `ms_p50` from `play_summary`; the provider. Remove the smoke model and turn `shadow` off afterwards.

### Task 6: whole-branch review and the pull request

Whole-branch review on sonnet, one fix round, one scoped re-review. Full gate. Push with the personal token scoped to the one command; open "Play mode 5 of 7: the detector module and shadow mode" with the live pass numbers, the order change and its reason, and the limits (smoke model only; no real model exists yet; no web copy for the new feed rows). Do not merge.

---

## Redesign: the detector reads screencaps, not the stream (2026-09-22)

Task 7 (a stream bit rate cap) was reverted: no stream setting stops the disconnects. The owner
chose the screencap-fed detector. Tasks 8 to 11 replace the stream as the session's frame source;
Task 6 still ends the branch.

**Measured on the live instance, at the game's menu, no input, no stream, no match:**
`adb.screencap()` one thread 5.34 per second, p50 180 ms, p95 238 ms, 0 failures, BGR (900, 1600, 3).
Two concurrent capture threads 4.57 and 4.64 per second, 0 failures. A farm-shaped thread (capture
plus classify on a 1.379 s tick) had a busy time of p50 464 ms alone and 510 ms beside a 5 Hz capture
thread, which itself got 4.88 captures per second. In a match a capture costs 236 to 278 ms, not 180.
The stream delivered the session 4.9 frames per second because the session throttles to `RATE_HZ`, so
the pull source is throughput-equivalent. What changes is age: 0.03 to 0.05 s becomes 0.2 to 0.3 s.

### Task 8: the screencap frame source

**Files:**
- Create: `brawlfarm/play/capture.py`
- Test: `tests/test_play_capture.py`

**Interfaces:**
- Consumes: `brawlfarm.core.adb.screencap() -> np.ndarray` (BGR, 900x1600x3, raises `adb.AdbError`).
- Produces: `ScreencapSource`, which Task 9 uses through the same four names the session already
  calls on a stream: `start()`, `latest()`, `stop()`, and the attribute `error`.

The class duck-types `brawlfarm/play/stream.py`'s `Stream` so the session changes as little as
possible. A daemon thread captures in a loop and keeps only the newest frame.

```python
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
from typing import Any, Callable

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
        """Begin capturing. Calling it twice is a no-op, never a second thread."""
        if self._thread is not None:
            return
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
```

- [ ] **Step 1: write the failing tests**

`tests/test_play_capture.py`, following the fakes and naming style already used by
`tests/test_play_session.py` (read that file first). Every test drives a fake capture and a fake
clock; none of them touches adb, a thread's timing, or the real emulator. Drive `_pump` directly
where a test needs determinism rather than starting the thread. Cover exactly these:

1. `latest()` is `(None, None)` before anything has been captured.
2. The age comes from before the capture call: a capture whose fake clock advances 0.25 s during
   the call reports an age of at least 0.25 s, not near zero.
3. A frame older than `STALE_AFTER` reports `(None, None)`.
4. One capture failure does not set `error`, and the next success clears the count.
5. Three consecutive failures set `error` to a string naming the count, and the pump returns.
6. Once `error` is set, `latest()` is `(None, None)` even with a stored frame.
7. `start()` twice runs one thread.
8. `stop()` before `start()` does not raise, and `stop()` twice does not raise.
9. The pump paces itself: with a capture that takes no time and `min_interval=0.2`, the fake
   sleep is asked for about 0.2 s each round.
10. `frames` counts successful captures only.
11. The default `capture` is `adb.screencap` (assert the attribute, do not call it).

- [ ] **Step 2: run them and watch them fail**

`uv --directory <worktree> run pytest tests/test_play_capture.py -q`

- [ ] **Step 3: write `capture.py` as given above, then make the tests pass**

- [ ] **Step 4: full gate**, then commit

```
feat(play): the detector's frames come from screencaps, not the stream
```

### Task 9: the session pulls from the new source

**Files:**
- Modify: `brawlfarm/play/session.py`
- Modify: `tests/test_play_session.py`

**Interfaces:**
- Consumes: `capture.ScreencapSource` from Task 8.
- Produces: the constructor keyword `source_factory` (was `stream_factory`) and the fallback
  reasons `source_start` and `source_error` (were `stream_start` and `stream_error`).

The seam does not change shape, only its names, so that nothing in the file claims a stream where
there is none. The web panel does not key on these strings (a grep of `brawlfarm/web/src` finds
none) and this pull request has never been pushed, so the rename costs nothing outside the branch.

- [ ] **Step 1**: grep the repository for `stream_factory`, `stream_start`, `stream_error`,
  `_stop_stream`, `_default_stream` and `_stream` across `brawlfarm`, `tests`, `tools`, `docs` and
  `README.md`, and change every hit that belongs to the session: `stream_factory` to
  `source_factory`, `_stream_factory` to `_source_factory`, `_stream` to `_source`, `_stop_stream`
  to `_stop_source`, `_default_stream` to `_default_source`, and the two reason strings. Leave every
  hit that belongs to `brawlfarm/play/stream.py`, `brawlfarm/play/matchrec.py` or
  `tools/play/stream_check.py` alone: those really are the stream.
- [ ] **Step 2**: `_default_source` returns `capture.ScreencapSource()`:

```python
def _default_source() -> Any:
    from brawlfarm.play import capture  # kept lazy so the module stays cheap to import

    return capture.ScreencapSource()
```

- [ ] **Step 3**: update the module docstring (session.py line 4 says the thread starts the stream)
  and the `PlaySession` class docstring to say the source is the emulator's screen captures, and
  that a frame is 0.2 to 0.3 s old by the time the model sees it. `RATE_HZ`, `STALE_LIMIT`,
  `MAX_SECONDS`, `KEEP_FILES` and `JOIN_TIMEOUT` keep their values; add to `RATE_HZ`'s comment that
  a capture costs 180 to 280 ms, so the real rate is about 5 per second and the throttle rarely
  binds.
- [ ] **Step 4**: in `tests/test_play_session.py`, rename through the same list, fix any wording
  that says stream, and add one test: the default factory builds a `ScreencapSource` and does not
  call adb (patch `brawlfarm.play.capture.adb.screencap` with something that raises if called).
  The existing `FakeStream` shape still fits; rename it `FakeSource`.
- [ ] **Step 5**: full gate, then commit

```
refactor(play): the shadow session pulls frames from the capture source
```

### Task 10: the stream modules say what they cost

**Files:**
- Modify: `brawlfarm/play/stream.py` (module docstring only)
- Modify: `brawlfarm/play/matchrec.py` (one log line and one feed field)

- [ ] **Step 1**: add to the top of `stream.py`'s module docstring, in its own paragraph:

```
Known defect: running this stream while a match is in progress makes the game show its
disconnect modal, 31 times across 16 matches on the reference instance, at every bit rate,
frame rate and frame size tried. See the open defect in
docs/superpowers/specs/2026-09-18-play-mode.md, section 2. Shadow mode no longer uses this
module; the observe-mode match recorder still does, and a match it records may disconnect.
```

- [ ] **Step 2**: in `matchrec.py`, find where the recorder starts a stream for a match (grep for
  `Stream(`), and log one line before it starts, at warning level:
  `"match recording uses the play stream, which can disconnect the match (spec section 2)"`.
  Add the field `stream_warning=True` to the feed event the recorder already emits when it starts
  (find it by grepping the file for `event(` or the queue it uses). If it emits no start event, add
  only the log line and say so in your report. Change nothing else in the file: its own on/off flag
  stays the gate.
- [ ] **Step 3**: extend the matchrec test file that covers the start path with one assertion for
  the new field, or for the log line if there is no event. Do not add a new test file.
- [ ] **Step 4**: full gate, then commit

```
docs(play): the stream modules name the disconnect defect they carry
```

### Task 11: the documents describe the design that exists

**Files:**
- Modify: `docs/superpowers/specs/2026-09-18-play-mode.md`
- Modify: `README.md`

Prose rules: no em-dashes, no emoji, lines at most 100 columns. A user-global formatter hook
rewraps Markdown at 80 columns whenever the Edit or Write tool touches a `.md` file, so apply every
Markdown edit with a small Python script run through Bash (read bytes, replace, write bytes, keep
the file's newline style) and then check `git diff --stat` shows only your lines.

- [ ] **Step 1**: spec section 2 keeps its open-defect subsection exactly as written. Add one
  sentence at the end of that subsection saying the detector no longer uses the stream, and that
  section 3 now names the source. Do not soften or re-run the numbers.
- [ ] **Step 2**: spec section 3 (detector): say the frames come from `brawlfarm/play/capture.py`,
  about 5 per second, each 0.2 to 0.3 s old when the model sees it, and that the capture thread
  costs the farm loop about 46 ms of busy time per tick (measured).
- [ ] **Step 3**: spec section 4 (the pull request 6 rules policy). Add a paragraph: at 5 frames a
  second with a 0.4 to 0.6 s end-to-end delay, gas avoidance, power cubes, boxes and the late bush
  hide all survive; treating an enemy as a repulsor survives; aiming at a moving enemy, duelling and
  dodging do not, so the policy never tries them and keeps attacking on the existing timer. Keep the
  anti-AFK rule already written there and add that anti-AFK input must never wait on a fresh frame.
- [ ] **Step 4**: spec section 5 and the build order: say shadow mode reads screen captures, and
  that the stream survives only for the observe-mode recorder and `tools/play/stream_check.py`.
- [ ] **Step 5**: `README.md` line 68: replace `stream_start` and `stream_error` with `source_start`
  and `source_error` in the reason list. Line 70 says the stream takes about 60 percent of one
  BlueStacks core while a match runs, which is now false for shadow mode: replace it with one
  sentence saying shadow mode captures the screen about 5 times a second and costs the farm loop
  about 46 ms a tick. Check line 51 and the rest of the play section for any other sentence the
  change makes false, and fix only those.
- [ ] **Step 6**: `uv run python tools/scrub_check.py` prints `0 hit(s)`, `ruff format --check .`
  passes, then commit

```
docs(play): shadow mode reads screen captures
```

### Then Task 6 (unchanged in shape)

Whole-branch review on sonnet, one fix round, one scoped re-review, full gate, and a live pass of
five matches with shadow on. The live pass passes only if: zero disconnect modals, the farm tick in
a match stays within 10 percent of the shadow-off baseline (p50 1.379 s, p95 2.021 s), the session
reports at least 3.5 frames per second, `stale_ticks` stays near zero, and the adb error count is
unchanged. Then push and open the pull request. Do not merge.

### Task 12: shadow mode stops asking for a library it does not use

**Files:**
- Modify: `brawlfarm/play/session.py`
- Modify: `tests/test_play_session.py`

**Why this task exists:** `play.available()` is true only when PyAV imports, and PyAV is the whole
content of the `play` extra. That gate was right when the session read frames from the scrcpy
stream, because the stream decodes H.264 with PyAV. The session now reads `adb.screencap()` and
decodes nothing, so it needs numpy and cv2 and onnxruntime, all three of which are core
dependencies: `rapidocr-onnxruntime` requires `onnxruntime>=1.7.0`, so onnxruntime is installed on
every brawlfarm. Leaving the gate in place means a user who sets `shadow = true` on a plain install
gets one feed row saying an extra is missing, and nothing else, for a dependency the code never
touches.

**Interfaces:**
- Consumes: nothing new.
- Produces: the `play_fallback` reason `extra_missing` is no longer emitted by `PlaySession`. The
  reasons it can still emit are `model_missing`, `model_invalid`, `source_start`, `source_error`,
  `stale`, `detector_error` and `session_error`. Task 11 writes that list into `README.md`.

**Not in scope, do not touch:**
- `brawlfarm/play/__init__.py`. `available()` keeps its meaning, which is "PyAV imports".
- `brawlfarm/play/matchrec.py:86`. The observe-mode recorder really does decode a stream, so its
  own `available()` gate and its "match recording off" log line stay exactly as they are.
- `brawlfarm/api/app.py:180`. The `play_available` field keeps reporting `play.available()`. No
  panel code reads it (a grep of `brawlfarm/web/src` for `play_available` and `playAvailable`
  finds nothing), so its meaning is not load bearing, and changing an API field in this pull
  request would be a UI change without a review page.

- [ ] **Step 1**: in `brawlfarm/play/session.py`, delete the five-line block that reads

```python
        if not play.available():
            if not self._said_extra:
                self._said_extra = True
                self._off = True
                log.info("shadow mode off: the play extra is not installed")
                self._queue("play_fallback", reason="extra_missing")
            return
```

so the tick falls straight through to `self._start()`.

- [ ] **Step 2**: delete the `self._said_extra` attribute where it is initialised, and delete the
  `play` import from `session.py` if nothing else in the file uses it. Run
  `uv run ruff check .` to catch the unused import either way.

- [ ] **Step 3**: in `session.py`, put one sentence in the class docstring next to the model
  paragraph:

```
Shadow mode needs no optional extra. It captures the screen through adb and runs the model on
onnxruntime, which rapidocr-onnxruntime already requires, so a plain install can run it.
```

- [ ] **Step 4**: in `tests/test_play_session.py`, find the test that asserts the
  `extra_missing` fallback (grep for `extra_missing`) and replace it with one that proves the
  opposite: with `play.available()` patched to return `False`, a tick in a match still starts a
  session and emits `play_on`, and no `play_fallback` row carries `extra_missing`. Keep the test
  name honest about what it checks, for example
  `test_a_missing_play_extra_no_longer_stops_shadow_mode`. Do not delete any other test.

- [ ] **Step 5**: grep the whole tree for `extra_missing` and report every remaining hit. Leave
  `README.md` and the spec alone: Task 11 owns them.

- [ ] **Step 6**: full gate, then commit

```
fix(play): shadow mode no longer needs the play extra
```

### Task 13: the whole-branch review findings

Written after the whole-branch review, so it records what was fixed rather than what to do.

**Files:**
- Modify: `brawlfarm/play/session.py`
- Modify: `tests/test_play_session.py`
- Modify: `brawlfarm/core/controller.py`

**Finding 1, severe.** `PlaySession._end()` runs on the controller thread. It joined the session
thread for up to `JOIN_TIMEOUT` of 3.0 s and then, through `_stop_source()`, joined the screencap
pump thread for another 3.0 s, so the end of every match could hold the farm loop for six seconds.
The global constraint says nothing the session does may block a controller tick for longer than a
lock hand-off, and a multi-second join is not that. An `adb.screencap()` that hangs is the case
that makes it bite. No test bounded it.

Fixed in `d94abec`. `_end()` signals and returns: it sets the stop flag, `_running = False` and
`_await_stop = True`. The session's own thread tears itself down from a `finally` in `_run()`,
which is where the pump thread's join now happens, and it queues the summary for the controller to
drain on a later tick, so feed rows still leave only the controller's thread. `_teardown()` runs
once per session under a `_torn_down` flag reset in `_start()` under the counters' lock.
`_winding_down()` keeps a second thread from starting under a live one and reaps the handle when
it is gone. The one surviving join is in `_finish()`, reached only from `close()`, which the
controller calls from its `finally` at process shutdown, where there is no tick left to hold.

Two tests were added that bound what the controller thread does against a source whose capture
hangs, and both fail against the pre-fix file at 3.0 s against a 1.0 s bound.

**Finding 2, trivial.** Two em-dashes this branch added to `brawlfarm/core/controller.py`, at line
148 and in the `_play_observe` docstring. Both are colons now, fixed in `a1f4dc6`. A byte scan over
the branch diff for U+2012 to U+2015 found no others. `controller.py` carries about 90 older
em-dashes that predate the merge base; none were touched, because that file holds never-tap logic,
verify-then-act, the 1600x900 assertion, tap coordinates and OCR needles that change only in an
owner-approved calibration pull request.
