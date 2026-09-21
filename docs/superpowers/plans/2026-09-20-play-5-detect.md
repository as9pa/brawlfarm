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
