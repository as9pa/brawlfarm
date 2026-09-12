# Phase 8 design brief: Calibration page, queue anchor fix, recorder, desktop window

This is the binding design for the phase 8 implementation plan. Plan writers copy its
values verbatim; they do not re-decide anything here. The spec is
`docs/superpowers/specs/2026-09-10-brawlfarm-design.md` (section 9 the safety rails, section
10 hygiene, section 11 testing, and the "After v1" list that names this phase). Every fact
below about the core, the API and the web code as they stand today was read against the
source at `fbae8c5` before this brief was written. The phase 6 brief next to this file is the
template and the inheritance.

The owner asked in chat on 2026-09-12 that work continue through phase ends without waiting.
The phase 8 review page (see the memory index) was published with the defaults printed under
each of its seven questions and its decision seeded as "go" on that instruction; the defaults
are the decisions recorded here. Any answer the owner types on the page later is a change
request against this brief, handled as a follow-up.

**Phase 8 is the owner-approved calibration PR named in the spec.** It is the one PR that
may change a shipped template and a threshold in `brawlfarm/core/config.py`. It moves exactly
one template (`matchmaking.png`) and one constant (`MATCHMAKING_THRESHOLD`), plus the
`COLOR_ONLY_TEMPLATES` membership that follows from the new template. No tap coordinate
moves. The PR body states this.

## 1. Outcome

`brawlfarm` gains a Calibration page, third in the rail, that shows what the workers see:
the chosen instance's latest frame with every tap coordinate and every anchor box drawn on
it, an anchor table with live scores against the 13 templates, and an overrides table that
shows every calibration constant whose value differs from the package default and where the
value came from. Calibration values become overridable from a file on disk,
`calibration.toml`, and templates become overridable from a folder, both under
`<home>/calibration/`. The queue anchor that has not matched since the game's UI update is
replaced from the measured corpus. A labeled frame recorder, off by default and switched per
instance from the page, saves the frames a worker classifies together with the label it gave
them, so the next recalibration starts from a corpus. `brawlfarm --window` opens the panel
in a desktop window with a tray icon; the browser stays the default and the desktop
libraries live in an optional dependency group.

## 2. What phase 8 inherits unchanged (decided)

Everything the phase 4 to 7 briefs established carries into phase 8 without restatement:
the tokens, fonts, type scale, radii, motion and focus ring in
`brawlfarm/web/src/styles/theme.css`; the state vocabulary in `lib/states.ts`; the copy
rules; `api/client.ts`, `api/queries.ts` (`queryKeys`, `createQueryClient`, `staleTime`
5000), `lib/toast.ts`; every existing component keeping its props; the vitest conventions
(`stubFetch`, `jsonResponse`, `jpegResponse`, `renderWithProviders`, `makeInstance`) and the
pytest conventions (`make_client`, the autouse `_isolated_home` fixture in
`tests/conftest.py`, `build_settings`); the commit trailers; the scrub rules; and the safety
rails of spec section 9. In particular: never-tap logic and verify-then-act are untouched;
the 1600x900 assertion in `controller.py` is untouched; one worker per instance; kill only by
PID from `status.json`; no user-supplied string reaches a shell or a filesystem path (the
only user-controlled names that reach the filesystem in this phase are instance names
validated by `resolve_instance` and template names validated against the fixed list in
section 4).

Also unchanged: `brawlfarm/core/recalib.py` keeps its name and its job (the drift alert
streak counter). The new code is `brawlfarm/core/calibration.py`.

## 3. Facts about the code today that the plan relies on

- `brawlfarm/core/config.py` is 724 lines of flat module constants. There is no
  calibration block marker. Env overrides are inline `os.environ.get("BRAWL_*", ...)` reads
  at each definition, not a helper. `HOME_DIR` is resolved at line 26 from `BRAWLFARM_HOME`;
  `set_home(path)` at lines 38 to 42 re-points `HOME_DIR`, `CAPTURES_DIR`, `DATA_DIR`.
  `DATA_DIR = HOME_DIR / os.environ.get("BRAWL_DATA_DIR", "data")` (line 32); a worker
  process is launched with `BRAWL_DATA_DIR=data/<instance>` so its `DATA_DIR` is
  `<home>/data/<instance>` and `DATA_DIR.name` is the instance name. `TEMPLATES_DIR =
  PACKAGE_DIR / "templates"` (line 24). Neither `tomllib` nor `tomli_w` is imported in
  `brawlfarm/core`. The file ends at line 724 with `BUSH_JITTER_MAX_INTERVAL = 8.0`.
- `brawlfarm/core/vision.py`: `Match(name, confidence, x, y, w, h)` with `.center`
  (lines 27 to 37); `_load_template(name)` (line 41, `cv2.imread`, `lru_cache(64)`) and
  `_load_template_gray(name)` (line 50) build the path as
  `config.TEMPLATES_DIR / f"{name}.png"`; `find(screen, name, threshold=None)` (line 74),
  `find_with_score` (line 113), `score(screen, name) -> float` (line 148) all branch on
  `config.GRAY_MATCH and name not in config.COLOR_ONLY_TEMPLATES`. No list of template
  names exists in code; the folder holds exactly 13 PNGs: `close_x, exit, matchmaking,
  other_device, play, playagain, proceed, reload, skin_popup, teams_left, trio_showdown,
  trophy_brawler, trophy_screen`.
- `brawlfarm/core/config.py:196` `COLOR_ONLY_TEMPLATES = frozenset({"close_x",
  "matchmaking"})`; lines 206 to 208 `MATCH_THRESHOLD = 0.85`, `IN_MATCH_THRESHOLD = 0.70`,
  `MATCHMAKING_THRESHOLD = 0.90`.
- `brawlfarm/core/states.py`: `State` enum `DISCONNECT, MENU, MATCHMAKING, RESULTS,
  IN_MATCH, TROPHY_SCREEN, POPUP, UNKNOWN` (lines 23 to 31); `_ANCHOR_STATE` maps `play ->
  MENU`, `playagain/proceed/exit -> RESULTS`, `matchmaking -> MATCHMAKING`, `teams_left ->
  IN_MATCH`, `trophy_screen/trophy_brawler -> TROPHY_SCREEN`; `classify(screen, phase=None)`
  at line 118 checks `reload` (DISCONNECT) and `close_x` (POPUP) first.
- `brawlfarm/core/controller.py`: `Controller.run()` (lines 1427 to 1531) is the worker
  loop. Per tick: `screen = adb.screencap()` (line 1451, BGR `np.ndarray` 900x1600x3
  uint8), `preview.maybe_write(screen)` (line 1455, once a second), `state =
  states.classify(screen, phase=self.phase)` (line 1458), the phase handler, then
  `self._loop_i += 1` and every 25 ticks `self._write_status()` and the `stop.flag` poll
  (lines 1504 to 1512). `self.phase` is a string. The worker never reads `override.json`;
  that file belongs to the scheduler process (`scheduler.write_override` writes `{mode,
  until, set_at}` whole, so an extra key would be clobbered).
- `brawlfarm/core/preview.py`: `encode(screen) -> bytes` (lines 38 to 48) is the only JPEG
  encoder; `maybe_write` writes `config.DATA_DIR / "preview.jpg"` atomically.
- `brawlfarm/core/captures.py`: `write_event(screen, tag, *, now=None) -> bool` writes PNGs
  under `CAPTURES_DIR/events`, throttled per tag, pruned to 100. Untouched by this phase.
- `brawlfarm/core/status.py`: `write_status(dir, dict)`; `status.json` fields are listed
  at `controller.py:262-284`. The recorder does not touch `status.json`.
- API: routers are flat files under `brawlfarm/api/` registered in
  `brawlfarm/api/app.py:182-194` via `app.include_router(x.router)` with imports at lines
  28 to 47. `brawlfarm/api/deps.py`: `get_home(request)`, `get_sup(request)`,
  `resolve_instance(request, name)` (validates against `S.INSTANCE_NAME_RE` and the
  configured instances, raises `HTTPException(404, "unknown instance")`).
  `brawlfarm/api/screens.py` reads `preview.jpg` through its `_read_file` helper (lines 107
  to 119) and returns `Response(content=..., media_type="image/jpeg", headers=...)`.
  `brawlfarm/api/settings_routes.py:72-87` implements `POST /api/settings/open-data-folder`:
  501 unless `sys.platform == "win32"`, `await asyncio.to_thread(os.startfile, str(path))`
  in a try/except OSError (500), returns `Response(status_code=204)`, never echoes the path.
  Request bodies are inline Pydantic models; responses are plain dicts.
  `Supervisor.views()` (`brawlfarm/supervisor/loop.py:103`) gives `InstanceView` with
  `pid` set only when alive.
- Tests: `tests/apihelpers.py:106-146` `make_client() -> (TestClient, Supervisor, home)`;
  `tests/test_api_screenshot.py` is the image-route example; `tests/test_api_settings.py:
  152-179` is the open-folder example (monkeypatches `sys.platform` and `os.startfile`).
  No test drives `Controller.run()` end to end; recorder tests use the class directly with
  numpy arrays.
- `brawlfarm/__main__.py`: `_parser()` (lines 51 to 71) has `-V/--version, --home, --once,
  --interval, --no-launch, --port, --no-browser`; `_uvicorn_server()` (103 to 117);
  `_open_later()` (120 to 127, `webbrowser.open` after 1 s); `_serve()` from line 129 runs
  the supervisor task and `server.serve()` on the main thread's asyncio loop; Ctrl+C ends
  `server.serve()`, then the supervisor is stopped, and worker processes are deliberately
  left running (that is what "Quit does what Ctrl+C does" means).
- `pyproject.toml`: version `1.0.0` (line 3); `[dependency-groups]` at line 25 with `dev`
  only.
- Web (`brawlfarm/web/src`): `App.tsx:20-25` imports pages directly and `ShellRoutes()`
  at lines 85 to 89 lists the routes; `app/Rail.tsx:13-17` `SECTIONS: {to, label, soon}[]`
  mapped at lines 39 to 50, `linkClass()` at 19 to 23; instances group from
  `useInstances()`. Stats uses `useQuery` with `queryKeys` (`api/queries.ts:12-27`); live
  updates come from SSE (`live/useEvents.ts`), not polling. Instance chips are inline
  `<button aria-pressed>` toggles in `stats/StatsToolbar.tsx:56-61` with "last chip stays
  on" logic. Primitives in `components/ui/`: `Button, Chip, Table, Switch, Segmented,
  StateChip, ErrorBlock, Dialog, Drawer, ConfirmDialog, Thumb, Toast`. No `Card`, no shared
  `Skeleton`. Tone tokens `--ok --warn --bad --idle --accent` are used as
  `text-[var(--ok)]`. `settings/Data.tsx:39-43,82-84` is the "Open data folder" button
  (`openDataFolder()` in `api/settings.ts:29-31`, failure toasted, no success toast).
  `components/ui/Thumb.tsx` fetches `/api/instances/${name}/preview.jpg` as a blob with an
  ETag check on a `refreshMs` timer and renders `<img src={objectUrl}>`. Tests: setup
  `src/test/setup.ts`, `src/test/renderWithProviders.tsx` (MemoryRouter plus a fresh
  QueryClient), `src/test/http.ts`. Commands: `pnpm typecheck` (`tsc --noEmit`), `pnpm test`
  (`vitest run`).

## 4. Calibration overrides (decided)

**Folder.** `<home>/calibration/` holds everything in this phase: `calibration.toml`,
`templates/`, `recordings/`. The app creates the folder on demand (open-folder, recorder
start) and never writes `calibration.toml` or anything under `templates/`.

**Overridable constants.** `brawlfarm/core/calibration.py` exposes
`overridable(ns: Mapping[str, object]) -> dict[str, object]`: every name in `ns` that is
upper case, does not start with `_`, and whose value is either a `float` (never `bool`) or a
`tuple` of exactly two `int`s (never `bool`), excluding `LOCKED = frozenset({"SCREEN_W",
"SCREEN_H", "SCREEN_DPI"})` (these are ints anyway; the set is there so the rule survives a
future type change). Two-int tuples are reported in group `"tap"`, floats whose name ends in
`_THRESHOLD` in group `"threshold"`, other floats in group `"timing"`. Ints, bools, strings,
paths, regions (4-tuples), HSV triples and frozensets are not overridable in this phase.

**File format.** TOML, flat, keys are constant names, values a float or int for floats and a
two-element array of ints for taps:

```toml
MATCHMAKING_THRESHOLD = 0.85
PLAY_BUTTON = [1434, 826]
```

**Validation and application.** `apply(ns: dict[str, object], path: Path) -> Report`
reads `path` with `tomllib` (missing file: empty report, nothing changes; unreadable or
invalid TOML: one problem `calibration.toml could not be read: <tomllib message>`, nothing
changes). For each key: unknown name -> problem `<KEY> is not a calibration constant. The
line is ignored.`; wrong shape -> problem `<KEY> must be a number.` or `<KEY> must be two
integers.`; otherwise `ns[KEY]` is replaced (an int for a float target is converted to
float; a two-int list becomes a tuple). The first call captures `ns` defaults for every
overridable name into a module-level `_DEFAULTS`; `apply` always restores defaults before
applying, so a later call with a changed or removed file lands on the right values.
`Report` is a frozen dataclass: `path: Path`, `present: bool`, `mtime_ns: int | None`,
`applied: dict[str, object]` (name to new value), `problems: tuple[str, ...]`,
`defaults: dict[str, object]` (the captured defaults for all overridable names).
`calibration.py` imports only the standard library; it never imports `config`.

**Hook.** `config.py` ends with:

```python
# --- Calibration overrides (phase 8): <home>/calibration/calibration.toml ----------
from brawlfarm.core import calibration as _calibration  # noqa: E402

CALIBRATION_FILE = HOME_DIR / "calibration" / "calibration.toml"
CALIBRATION = _calibration.apply(globals(), CALIBRATION_FILE)
```

and `set_home()` re-points `CALIBRATION_FILE` and re-runs `apply` after re-pointing
`DATA_DIR`. Modules that did `from brawlfarm.core.config import PLAY_BUTTON` at import time
would miss the override; the code base reads constants as `config.PLAY_BUTTON` (this was
checked for the tap constants and thresholds; the plan's task 1 re-checks with a grep and
fixes any `from ... import CONSTANT` of an overridable name it finds).

**Changed since start.** `calibration.changed_since(report) -> bool` compares the file's
current `mtime_ns` (or absence) with `report.mtime_ns`. The API uses it for the "changed at
HH:MM" prompt; the worker never re-reads the file (restart applies it, as the page says).

## 5. Template overrides and the fixed template list (decided)

`vision.py` gains `TEMPLATE_NAMES: tuple[str, ...]`, computed at import as
`tuple(sorted(p.stem for p in config.TEMPLATES_DIR.glob("*.png")))` (13 names today), and
`template_path(name) -> Path`: `<home>/calibration/templates/<name>.png` when that file
exists, else `config.TEMPLATES_DIR / f"{name}.png"`. `template_source(name) -> Literal
["package", "override"]`. The cached loaders become keyed by `(path, mtime_ns)`:
`_load_template(name)` resolves the path and its `st_mtime_ns` and calls a
`lru_cache(64)`-wrapped `_read_template(path_str: str, mtime_ns: int)`; the gray loader
does the same. One `stat` per call is the cost; a dropped-in override takes effect on the
next call without a restart, in the worker and in the API alike. `name` is only ever one of
`TEMPLATE_NAMES`; the API route rejects anything else with 404 before touching the
filesystem.

`vision.threshold_for(name) -> float` returns the threshold `find()` uses when none is
passed (the same branching that exists in `find` today, moved into a helper that `find`
calls), so the page and the scores route show the real per-anchor threshold.

## 6. The queue anchor fix (decided)

- `brawlfarm/core/templates/matchmaking.png` is replaced by the measured crop of the
  "Players found N/12" line: source frame `040-rec.jpg` of the corpus, crop `x=611 y=112
  w=276 h=45`, 276x45 pixels, stored as the file
  `<scratchpad>/calib/candidates/matchmaking-prefix-tight.png` produced by the spike. The
  crop contains game UI text only.
- `MATCHMAKING_THRESHOLD` 0.90 becomes 0.85. `COLOR_ONLY_TEMPLATES` becomes
  `frozenset({"close_x"})`, so matchmaking scores on the gray path like the other anchors.
- Verification is the spike's `repro.py` over the 195 labeled frames run against the
  worktree: every queue frame scores at or above 0.99, every other frame at or below 0.51,
  `classify()` returns MATCHMAKING on all queue frames and on no other frame. The full
  pytest suite passes unchanged (the never-tap tests in particular).
- The corpus frames are never added to git.

## 7. The recorder (decided)

`brawlfarm/core/recorder.py`, class `Recorder`:

```python
class Recorder:
    MAX_FRAMES = 2000            # per session
    MAX_BYTES = 512 * 1024 * 1024  # per instance, all sessions
    MIN_INTERVAL_S = 1.0

    def __init__(self, root: Path, instance: str, flag: Path, *,
                 clock: Callable[[], float] = time.monotonic,
                 wall: Callable[[], datetime] = datetime.now) -> None: ...
    def poll(self) -> None: ...
    def observe(self, screen: np.ndarray, state: State, phase: str) -> bool: ...
    def status(self) -> dict[str, object]: ...
    def close(self) -> None: ...
```

- `root` is `config.HOME_DIR / "calibration"`, `instance` is `config.DATA_DIR.name`, `flag`
  is `config.DATA_DIR / "record.flag"`. Sessions live at
  `root / "recordings" / instance / <YYYYmmdd-HHMMSS>/`.
- `poll()` is called by the worker on the existing 25-tick cadence next to the `stop.flag`
  check. Flag present and no session open: if the instance's recordings folder already
  holds `MAX_BYTES` or more (sum of file sizes, walked once per poll), set `reason =
  "disk_cap"` and stay closed; else open a session folder and set `reason = None`. Flag
  absent and a session open: close it. The flag is a plain empty file; the recorder never
  creates or deletes it.
- `observe(screen, state, phase)` is called by the worker right after `classify`. It
  writes when a session is open and (the state differs from the last written state, or at
  least `MIN_INTERVAL_S` has passed since the last write). A write is
  `<seq:04d>-<state.name.lower()>.jpg` (bytes from `preview.encode(screen)`) plus one line
  appended to `labels.jsonl`: `{"seq": 412, "ts": "21:11:03.2", "state": "match", "phase":
  "in_match", "scores": {"play": 0.12, ...}}` where `ts` is wall-clock `HH:MM:SS.f`,
  `state` is `state.name.lower()`, and `scores` holds `vision.score(screen, name)` for
  every name in `vision.TEMPLATE_NAMES` (13 gray template passes, about 150 ms, once per
  second at most). When `seq` reaches `MAX_FRAMES` the session closes with `reason =
  "frame_cap"`; it reopens only after the flag is cleared and set again (a fresh session
  folder). Returns True when a frame was written.
- After every write and every state change `status()` is written to `config.DATA_DIR /
  "recorder.json"` through `jsonio.atomic_write_json`:
  `{"on": bool, "frames": int, "bytes": int, "session": "<YYYYmmdd-HHMMSS>" | null, "path":
  "recordings/<instance>/<session>" | null, "reason": null | "frame_cap" | "disk_cap",
  "last_session": "<YYYYmmdd-HHMMSS>" | null, "last_frames": int}`. `path` is relative to
  the calibration folder; no absolute path is written anywhere the API serves.
- Everything is best effort: every filesystem call is wrapped so a recorder failure can
  never stop or slow the worker beyond the write itself; failures are logged once through
  the controller's logger and the recorder closes its session.
- The recorder deletes nothing, ever.

Controller changes are three lines plus construction: `self.recorder = Recorder(...)` in
`__init__`, `self.recorder.observe(screen, state, self.phase)` after line 1458,
`self.recorder.poll()` inside the 25-tick block, and `self.recorder.close()` on the way out
of `run()`.

## 8. API (decided)

New flat router `brawlfarm/api/calibration.py`, registered in `app.py` like the others.

- `GET /api/calibration` ->
  ```json
  {"file": {"present": true, "changed_since_start": false, "problems": ["PLAY_BUTON is not a calibration constant. The line is ignored."]},
   "constants": [{"name": "PLAY_BUTTON", "group": "tap", "default": [1434, 830], "value": [1434, 826], "source": "calibration.toml"}],
   "templates": [{"name": "matchmaking", "source": "package", "width": 276, "height": 45, "threshold": 0.85}]}
  ```
  `constants` lists every overridable name (all groups), sorted by group then name;
  `source` is `"calibration.toml"` when the name is in `config.CALIBRATION.applied`, else
  `"package"`. `templates` covers `vision.TEMPLATE_NAMES`.
- `GET /api/instances/{name}/calibration/scores` -> reads the instance's `preview.jpg`
  the way `screens.py` does; 404 `{"detail": "no frame yet"}` when there is none. Response
  `{"ts": <preview mtime iso>, "width": 1600, "height": 900, "state": "menu", "phase":
  "<status.json phase or null>", "anchors": [{"name": "play", "threshold": 0.85, "score":
  0.97, "found": true, "expected": true, "box": {"x": 1312, "y": 783, "w": 224, "h": 81}}]}`.
  `score` and `box` come from `vision.find_with_score`; `found` is `score >= threshold`;
  `expected` is true when the worker's current phase names this anchor in
  `EXPECTED_BY_PHASE`, a table in the router built by the implementer from the
  `phase_*` handler names in `controller.py` and `states._ANCHOR_STATE` (menu phases expect
  `play`, the queue phase expects `matchmaking`, the in-match phase expects `teams_left`,
  the results phases expect `playagain`, `proceed`, `exit`). The web shows Drift when
  `expected and not found`.
- `GET /api/calibration/templates/{name}.png` -> 404 unless `name in
  vision.TEMPLATE_NAMES`; returns the active file's bytes as `image/png` with
  `Cache-Control: no-store`.
- `POST /api/calibration/open-folder` -> creates `<home>/calibration` if missing, then the
  exact `open-data-folder` behavior (501 off Windows, 500 on OSError, 204).
- `GET /api/instances/{name}/recorder` -> the instance's `recorder.json` merged with
  `"flag": <record.flag exists>`; when the file is missing: `{"on": false, "frames": 0,
  "bytes": 0, "session": null, "path": null, "reason": null, "last_session": null,
  "last_frames": 0, "flag": false}`.
- `POST /api/instances/{name}/recorder` body `{"on": true}` creates
  `<instance dir>/record.flag` (empty file), `{"on": false}` removes it; returns the GET
  payload. The instance dir is `S.instance_dir(home, name)`, the same folder the worker
  has as `DATA_DIR`.

## 9. Web (decided)

- Rail: `SECTIONS` gains `{to: "/calibration", label: "Calibration"}` third, between Stats
  and Settings. Route `/calibration` in `ShellRoutes()`.
- `src/api/calibration.ts`: typed fetchers `getCalibration()`, `getScores(name)`,
  `getRecorder(name)`, `setRecorder(name, on)`, `openCalibrationFolder()`, plus the
  response types; `queryKeys.calibration`, `queryKeys.calibrationScores(name)`,
  `queryKeys.recorder(name)`.
- `src/calibration/Calibration.tsx` (page): header "Calibration"; instance chips as in
  `StatsToolbar` (one selected at a time here, first running instance preselected, else the
  first configured); `Segmented` Taps / Anchors / Both (Both default); `Button` quiet "Open
  calibration folder" and `RecorderCard`'s toggle. Two columns on wide screens (frame left,
  anchor table right), stacked under 1100 px; overrides table full width below.
- `src/calibration/FrameOverlay.tsx`: a `relative` box with `aspect-[16/9]` holding
  `Thumb` (refreshMs 2000) and an absolutely positioned SVG `viewBox="0 0 1600 900"`
  covering it. Tap crosshairs (circle r 7, two 26-px lines, accent stroke) at each
  `group === "tap"` constant's current value, with a mono label "NAME x,y". Anchor boxes
  from `scores.anchors[].box`: solid `--ok` stroke when `found`, dashed `--bad` when not
  (drawn where the search landed). Nothing on the page ever POSTs a coordinate; the overlay
  has no pointer handlers.
- `src/calibration/AnchorTable.tsx`: `Table` with Anchor, Threshold, Score, Status, Last
  seen. Status pill: Found (`--ok`), Drift (`--bad`, when `expected && !found`), Absent
  (muted). Last seen is kept in component state per anchor from the polled responses ("now"
  when found in the latest response, `HH:MM` of the last response where it was found, "never"
  otherwise).
- `src/calibration/OverridesTable.tsx`: Constant, Default, Override, Source for every
  constant whose `source !== "package"` plus the three thresholds always; template rows for
  every template whose source is `override`. Values render as `x, y` for taps and plain
  numbers otherwise; source renders as a `Chip` "calibration.toml" or "calibration/templates".
  Above the table, when `file.problems` is non-empty, one `--bad` strip per problem; when
  `file.changed_since_start`, one `--warn` strip: "calibration.toml changed. Instances started
  before that run the old values until restarted."
- `src/calibration/RecorderCard.tsx`: `Switch` labeled Record frames; frames, size on disk
  (MB, one decimal), session `HH:MM` and the relative path; off state shows "Off. Last
  session <id>, <n> frames." when known; `reason === "frame_cap"` shows "Recorder stopped at
  2000 frames for this session. Start it again for a new session folder."; `reason ===
  "disk_cap"` shows "Recordings for <instance> use 512 MB. Delete old session folders from
  the calibration folder to record again." in a `--bad` strip.
- Polling: scores and recorder use `useQuery` with `refetchInterval: 2000` while the chosen
  instance is running (from `useInstances()`); no interval when it is stopped (the last
  preview stays and is scored once). `getCalibration()` uses `refetchInterval: 10000`.
- States: loading skeleton (inline, as Stats does); no frame yet ("Start <name> to see its
  frame. Scores appear after the first capture."); stopped instance (pill Stopped, no
  polling); error via `ErrorBlock` with retry.

## 10. Desktop window and tray (decided)

- `pyproject.toml` gains `desktop = ["pywebview>=5.3", "pystray>=0.19", "pillow>=10"]`
  under `[dependency-groups]`. Nothing in the base install or CI imports them.
- `brawlfarm/desktop.py`: `available() -> bool` (tries `import webview, pystray, PIL`
  lazily, False on ImportError), `MISSING_MESSAGE = "The desktop window needs the optional
  extras.\nRun: uv sync --group desktop\nOpening in the browser instead."`, and
  `run(url: str, *, running: Callable[[], int], quit_cb: Callable[[], None]) -> None`, which
  blocks the main thread: creates the pywebview window titled `brawlfarm`, 1280x800, at
  `url`; a pystray icon (a 64x64 Pillow image, accent `#E0B84B` rounded square on
  transparent) with menu header `brawlfarm, <n> running` (from `running()`), `Open panel`
  (default action, shows the window) and `Quit`; the window's `closing` event hides the
  window instead and shows the balloon `brawlfarm is still running. Open it again from the
  tray icon.` once per process; `Quit` destroys the window, stops the icon and calls
  `quit_cb`.
- `brawlfarm/__main__.py`: `--window` flag. With it, `main()` checks `desktop.available()`;
  when false it prints `MISSING_MESSAGE` to stderr and continues exactly as without the flag
  (browser opens). When true, the asyncio server runs in a background thread
  (`threading.Thread(target=asyncio.run, args=(_serve(...),), daemon=True)`), the browser is
  not opened, and `desktop.run(...)` owns the main thread; `quit_cb` sets an asyncio Event
  on that loop via `call_soon_threadsafe` that `_serve` awaits to stop the server and the
  supervisor the same way Ctrl+C does (workers keep running, as today).
- pytest covers the fallback (monkeypatch `desktop.available` to False: message printed,
  browser path taken) and the flag parsing; the window itself gets a manual pass with the
  extras installed in the worktree venv (`uv sync --group desktop`).

## 11. Docs (decided)

- `README.md`: a "Calibration" section (what the page shows, the override file, template
  overrides, the recorder, and that `--window` exists), linking to `docs/calibration.md`.
- `docs/calibration.md` (new): the how-to: where the folder is, the TOML format with the
  two examples above, the template override rule and the 13 names, how to record a session
  and what the files are, the two caps, the restart rule, and the safety statement (the page
  reads, the file writes; nothing on the page moves a tap).
- `docs/setup.md`: one paragraph on `uv sync --group desktop` and `brawlfarm --window`.
- `docs/PLAN.md`: the phase 8 row after merge, as for phase 7.

## 12. Verification and gate

Per task: the tests named in the plan. Whole branch: `pnpm typecheck`, `pnpm test`
(vitest), `uv run pytest`, `uv run ruff check .`, `uv run python tools/scrub_check.py` (`0
hit(s)`), then the live pass against the real install: `GET /api/calibration` shows the
package template at 276x45 and threshold 0.85; the worker for Pie64 gets through one queue
without a `queue_timeout` recovery in its session log; with `record.flag` set from the page
one match produces a session folder with JPEGs and a `labels.jsonl` whose lines parse; the
recorder toggled off writes nothing more. Screenshots of the live page stay out of git.

## 13. Open items after phase 8

Recalibration of the brawler screen and the event screens waits for a recording of the
owner's own play. Quest-aware brawler choice and opt-in auto-upgrade stay on hold. Answers
typed on the phase 8 page are follow-ups.
