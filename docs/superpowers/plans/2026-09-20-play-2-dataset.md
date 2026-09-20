# Play mode pull request 2: the dataset kit. Implementation plan

> For agentic workers: REQUIRED SUB-SKILL: use superpowers:subagent-driven-development to implement
> this plan task by task. Steps use checkbox syntax. Unlike the pull request 1 plan, this plan fixes
> interfaces, constants, behaviour and test cases, and leaves the function bodies to the implementer.
> Where a body is given, use it verbatim.

Goal: everything needed to turn video into a labelled training set and a scored model, as tools
under `tools/play/`: frame extraction, YouTube ingest, template pre-labels, a Label Studio project,
Label Studio export to a COCO folder split by source, RF-DETR nano training, ONNX export with
per-class thresholds, and a score report. No model ships in this pull request; the first model is
pull request 4.

Architecture: small modules under `tools/play/`, none of them in the wheel (`packages =
["brawlfarm"]`). Everything that can run in the project environment does, and is unit tested with
synthetic images. Only `train.py` and `export.py` need torch; they are self-contained scripts with
inline script metadata (PEP 723), run with `uv run tools/play/train.py`, so torch never enters
`pyproject.toml` or `uv.lock`. Nothing here touches `brawlfarm/`, taps, or talks to adb.

Tech stack: Python 3.13, uv, pytest, ruff, OpenCV and numpy (already dependencies), PyAV (`av>=14`,
already in dev), yt-dlp (new, in a `dataset` dependency group and in dev), onnxruntime (already a
dependency through the text reader), `rfdetr[train,onnx]` 1.10.1 with `torch` from the cu128 index
(inline script metadata only).

Spec: `docs/superpowers/specs/2026-09-18-play-mode.md`, section 8, the detector spike and the HUD
colour spike under Measured facts, the class list in section 3. This plan implements build order
step 2.

## Global constraints

- Gate for every task: `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check .`,
  `uv run python tools/scrub_check.py` printing `0 hit(s)`. No task touches `brawlfarm/` or
  `brawlfarm/web`.
- Review is on: each task gets a sonnet spec-compliance and code-quality review, the branch a
  whole-branch sonnet review before its pull request.
- No tool in `tools/play/` imports `brawlfarm.core.adb` except the existing `stream_check.py`. None
  sends input.
- No user string reaches a shell or a path. Subprocesses take argument lists, never `shell=True`.
  A YouTube URL is validated against a fixed pattern and only its 11 character video id is used in
  a file name. Source names used in paths match `^[A-Za-z0-9_-]{1,64}$` or the tool refuses them.
- Training data, videos, frames, models and Label Studio files never enter the repository. The
  dataset root is outside the checkout (`<home>/datasets/play`).
- Prose rule: no em-dashes and no emoji anywhere, including commit messages and docstrings. No
  Windows user profile path or username in any file; say `%LOCALAPPDATA%`.
- Commit after every task with the trailer `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.
- Commands are plain single commands run from the worktree `.claude/worktrees/play-2-dataset` on
  branch `play/dataset`: no `&&`, no `$(...)`, no `VAR=` prefixes, no `cd`, no `git -c`.
- Tests never download, never start Label Studio, never import torch or rfdetr, never read the
  owner's data home. `tests/conftest.py` already isolates `BRAWLFARM_HOME`.

## Shared facts (from the codebase, verified 2026-09-20)

- `brawlfarm.settings.default_home() -> Path`: `BRAWLFARM_HOME` if set, else `%LOCALAPPDATA%\brawlfarm`.
- `brawlfarm.core.vision`: `TEMPLATE_NAMES: tuple[str, ...]`; `find_with_score(screen, name,
threshold=None) -> tuple[Match | None, float]`; `score(screen, name) -> float`; `Match` has
  `x, y` (centre), `w, h`, `confidence`, `name`, so the top-left corner is `x - w // 2, y - h // 2`.
  Screens are BGR `numpy` arrays, 1600 x 900.
- Recorder sessions: `<home>/calibration/recordings/<instance>/<YYYYmmdd-HHMMSS>/` holding
  `NNNN-<state>.jpg` (1600 x 900 only when recorded at full size, else 800 x 450), `labels.jsonl`
  with `{"seq", "ts", "file", "state", "phase", "scores": {template: score}}`, and `match-N.h264`.
- `brawlfarm.play.h264.Decoder`: `feed(bytes) -> list[np.ndarray]` (BGR), `flush()`.
- Fixture clip: `tests/fixtures/play/stream-2s.h264` (1600 x 900, 30 fps, 59 decodable frames).

## Dataset layout (all under the dataset root, default `<home>/datasets/play`)

```
videos/<source>.mp4              downloads (YouTube) kept for re-extraction
frames/<source>/<source>-NNNNNN.jpg   1600 x 900 JPEG, quality 92
index.jsonl                      one line per kept frame
labelstudio/config.xml           copy of tools/play/labelstudio.xml
labelstudio/tasks.json           import file with pre-label predictions
coco/{train,valid,test}/         images plus _annotations.coco.json (RF-DETR layout)
coco/split.json                  which source went to which split, plus the training set hash
runs/<YYYYmmdd-HHMMSS>/          training output
models/play.onnx, models/play.json   export output (the calibration pull request copies these)
```

`index.jsonl` line: `{"file": "frames/<source>/<source>-000012.jpg", "source": "<source>", "kind":
"youtube" | "session" | "match" | "video", "t": <seconds into the source, float, or null>, "hash":
"<16 hex digits>", "teams_left": <float, 4 decimals>, "pad": [left, top, right, bottom]}`.

## File structure

- Create `tools/play/classes.py`, `tools/play/dataset.py`, `tools/play/frames.py`,
  `tools/play/ingest_youtube.py`, `tools/play/prelabel.py`, `tools/play/labelstudio.xml`,
  `tools/play/coco.py`, `tools/play/thresholds.py`, `tools/play/train.py`, `tools/play/export.py`,
  `tools/play/score.py`, `docs/play-training.md`.
- Create tests: `tests/test_play_dataset.py`, `tests/test_play_frames.py`,
  `tests/test_play_ingest.py`, `tests/test_play_prelabel.py`, `tests/test_play_coco.py`,
  `tests/test_play_thresholds.py`, `tests/test_play_score.py`.
- Modify `pyproject.toml` (dependency groups only), `uv.lock`, `README.md` (one pointer line),
  `CONTRIBUTING.md` (one rail).

---

### Task 1: classes, dataset core and frame extraction

Files: create `tools/play/classes.py`, `tools/play/dataset.py`, `tools/play/frames.py`,
`tests/test_play_dataset.py`, `tests/test_play_frames.py`; modify `pyproject.toml`, `uv.lock`.

Interfaces produced:

```python
# tools/play/classes.py
CLASSES: tuple[str, ...] = (
    "self", "enemy", "teammate", "power_cube", "box", "bush",
    "showdown_card", "skull_star", "team_up_panel", "event_tab",
    "play_button", "play_again_button", "proceed_button", "exit_button", "close_x",
)
# templates whose match is a pre-label box for a class (template name -> class name)
TEMPLATE_CLASS: dict[str, str] = {
    "trio_showdown": "showdown_card",
    "play": "play_button",
    "playagain": "play_again_button",
    "proceed": "proceed_button",
    "exit": "exit_button",
    "close_x": "close_x",
}
# anchors a controller would tap: a false positive on one of these is a never-tap failure
TAP_ANCHORS: frozenset[str] = frozenset(TEMPLATE_CLASS.values()) | {"skull_star", "team_up_panel", "event_tab"}
def category_id(name: str) -> int   # 1-based position in CLASSES; KeyError on an unknown name

# tools/play/dataset.py
FRAME_W, FRAME_H = 1600, 900
JPEG_QUALITY = 92
SOURCE_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
def default_root() -> Path                       # settings.default_home() / "datasets" / "play"
def check_source(name: str) -> str               # returns name, raises ValueError when SOURCE_RE fails
def dhash(frame: np.ndarray) -> int              # 64-bit difference hash: gray, resize to 9 x 8, row-wise left < right
def hamming(a: int, b: int) -> int
def fit_frame(frame: np.ndarray) -> tuple[np.ndarray, tuple[int, int, int, int]]
    # pad with black to 16:9 (never crop), then resize to 1600 x 900 with INTER_AREA when shrinking,
    # INTER_LINEAR when growing; returns the frame and the pad (left, top, right, bottom) in output pixels
class Deduper:
    def __init__(self, max_distance: int = 4, window: int = 64, seen: Iterable[int] = ()) -> None
    def is_new(self, h: int) -> bool             # False for an exact repeat of any hash ever seen, or within
                                                 # max_distance of one of the last `window` kept hashes; records h when True
class Index:
    def __init__(self, root: Path) -> None       # root / "index.jsonl"; loads existing hashes and files
    def hashes(self) -> list[int]
    def has_source(self, source: str) -> bool
    def add(self, *, file: str, source: str, kind: str, t: float | None, hash_: int,
            teams_left: float, pad: tuple[int, int, int, int]) -> None   # appends one line, flushes
def save_frame(root: Path, source: str, n: int, frame: np.ndarray) -> str
    # writes frames/<source>/<source>-NNNNNN.jpg, returns the path relative to root with forward slashes

# tools/play/frames.py
FPS_OUT = 2.0
def iter_h264(path: Path, fps_in: float = 30.0, fps_out: float = FPS_OUT) -> Iterator[tuple[float, np.ndarray]]
    # raw elementary stream through brawlfarm.play.h264.Decoder in 64 KiB reads, plus flush(); frame k has t = k / fps_in;
    # yields the first frame at or after each multiple of 1 / fps_out
def iter_video(path: Path, fps_out: float = FPS_OUT) -> Iterator[tuple[float, np.ndarray]]
    # container files through av.open; t from frame.time; BGR via to_ndarray(format="bgr24"); same sampling rule
def iter_session(folder: Path) -> Iterator[tuple[float | None, np.ndarray]]
    # the session's jpg files in name order that are exactly 1600 x 900; t is None; smaller frames are skipped and counted
def add_source(root: Path, source: str, kind: str, frames: Iterable[tuple[float | None, np.ndarray]],
               *, score=vision.score) -> dict[str, int]
    # for each frame: fit_frame, dhash, Deduper (seeded from the index), save, index line with teams_left =
    # round(score(frame, "teams_left"), 4); returns {"seen": .., "kept": .., "duplicates": ..}
def main(argv=None) -> int
    # frames.py --session <folder> | --match <file.h264> | --video <file> [--source NAME] [--root PATH]
    # the source name defaults to the file or folder stem run through check_source; a session also adds every
    # match-N.h264 inside it as source "<session>-match-N"; refuses a source that is already in the index
    # unless --again is given; prints the counts
```

Dependency groups in `pyproject.toml`: add `dataset = ["yt-dlp>=2025.1", "av>=14"]` and add
`"yt-dlp>=2025.1"` to `dev`. Run `uv lock`. No extra: tools are not in the wheel.

Tests (synthetic images only, `tmp_path` as root):

- `dhash` is equal for a frame and the same frame with every pixel raised by 3; differs by more
  than 10 bits between two unrelated synthetic frames (a gradient and a checkerboard).
- `fit_frame`: a 1920 x 1080 frame comes back 1600 x 900 with pad (0, 0, 0, 0); a 2340 x 1080
  frame comes back 1600 x 900 with equal top and bottom pads greater than 0 and left and right 0,
  and the top pad rows are black; a 1600 x 900 frame is returned unchanged.
- `Deduper`: an exact repeat is refused even after more than `window` other hashes; a hash at
  distance 3 from the last kept is refused; at distance 5 it is kept.
- `check_source` refuses `"../x"`, `"a b"`, an empty string and a 65 character name.
- `Index`: two `add` calls produce two JSON lines; a new `Index` on the same root reports both
  hashes and `has_source`.
- `iter_h264` on the fixture clip with `fps_out=2.0` yields 4 frames (t = 0, 0.5, 1.0, 1.5) of shape
  (900, 1600, 3); `pytest.importorskip("av")`.
- `iter_video`: build a 1 s, 10 fps, 320 x 180 mp4 with PyAV in the test (mpeg4 codec), expect 2
  frames at `fps_out=2.0`.
- `iter_session`: a folder with one 1600 x 900 jpg and one 800 x 450 jpg yields one frame.
- `add_source` with a fake `score` returning 0.5: three frames where the second repeats the first
  give `{"seen": 3, "kept": 2, "duplicates": 1}`, two files on disk, two index lines with
  `teams_left` 0.5.
- `main` refuses a source that is already indexed (exit code 2) and accepts it with `--again`.

Steps:

- [ ] Step 1: write the tests; run them; expect import errors.
- [ ] Step 2: write `classes.py`, `dataset.py`, `frames.py`; run the two test files; expect all passed.
- [ ] Step 3: edit `pyproject.toml`, run `uv lock`.
- [ ] Step 4: run the gate.
- [ ] Step 5: commit: `feat(tools): play dataset core and frame extraction from sessions, match files and videos`.

### Task 2: YouTube ingest

Files: create `tools/play/ingest_youtube.py`, `tests/test_play_ingest.py`.

Interfaces:

```python
URL_RE = re.compile(r"^https://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([A-Za-z0-9_-]{11})(?:[&?].*)?$")
FORMAT = "bv*[height<=1080][ext=mp4]/bv*[height<=1080]/b[height<=1080]"
def read_urls(path: Path) -> list[tuple[str, str]]   # (video id, canonical url https://www.youtube.com/watch?v=<id>);
    # blank lines and lines starting with # are skipped; any other line that fails URL_RE raises ValueError naming the line number
def download(video_id: str, url: str, videos: Path, *, run=subprocess.run) -> Path
    # [sys.executable, "-m", "yt_dlp", "--no-playlist", "--no-progress", "-f", FORMAT, "--merge-output-format", "mp4",
    #  "-o", str(videos / f"{video_id}.%(ext)s"), url]; check=True; skips the download when videos/<id>.mp4 exists;
    # raises RuntimeError when the file is missing afterwards
def main(argv=None) -> int
    # ingest_youtube.py URLS.txt [--root PATH] [--keep-going]; per url: download, then frames.add_source(root, "yt-<id>",
    # "youtube", frames.iter_video(path)); a source already in the index is skipped with a line saying so; a failed
    # download stops the run (exit 1) unless --keep-going; prints one summary line per video and a total
```

The canonical URL is rebuilt from the validated id, so nothing else from the owner's line reaches
the subprocess. The source name is `yt-<id>` (ids may hold `-` and `_`, both allowed by `SOURCE_RE`).

Tests: `read_urls` accepts both URL shapes and extra query parameters, skips comments, raises on
`http://`, on a playlist URL without `v=`, and on `https://evil.example/watch?v=AAAAAAAAAAA`; the
error names the line number. `download` with a fake `run` that records its arguments and touches
the output file: asserts the argument list exactly, asserts no element contains the raw input line,
asserts the skip when the file exists (fake `run` not called). `main` with monkeypatched `download`
and `frames.iter_video`: two urls, one already indexed, prints a skip line and returns 0;
`--keep-going` turns a `RuntimeError` into a counted failure and exit code 1 at the end.

Steps: tests first (fail), implementation, focused tests pass, gate, commit
`feat(tools): ingest_youtube, an owner-supplied URL list into dataset frames`.

### Task 3: pre-labels, the Label Studio project, export to COCO

Files: create `tools/play/prelabel.py`, `tools/play/labelstudio.xml`, `tools/play/coco.py`,
`tests/test_play_prelabel.py`, `tests/test_play_coco.py`.

Interfaces:

```python
# tools/play/prelabel.py
MODEL_VERSION = "templates-v1"
def boxes_for(frame: np.ndarray, *, find=vision.find_with_score) -> list[dict]
    # for each (template, class) in TEMPLATE_CLASS: match, score = find(frame, template); when match is not None,
    # {"class": cls, "x": left, "y": top, "w": w, "h": h, "score": round(score, 4)} clipped to the frame
def task_for(rel_file: str, boxes: list[dict]) -> dict
    # Label Studio task: {"data": {"image": "/data/local-files/?d=" + rel_file, "file": rel_file},
    #  "predictions": [{"model_version": MODEL_VERSION, "score": <mean box score or 0>, "result": [...]}]}
    # each result: {"id": "<8 hex>", "from_name": "label", "to_name": "image", "type": "rectanglelabels",
    #  "original_width": 1600, "original_height": 900, "score": s,
    #  "value": {"x": pct, "y": pct, "width": pct, "height": pct, "rotation": 0, "rectanglelabels": [cls]}}
    # percentages are of the frame size, rounded to 4 decimals; the predictions list is empty when there are no boxes
def main(argv=None) -> int
    # prelabel.py [--root PATH] [--source NAME ...]: walks index.jsonl (optionally only some sources), writes
    # labelstudio/tasks.json and copies labelstudio.xml to labelstudio/config.xml; prints frames, frames with boxes, boxes per class

# tools/play/coco.py
SPLITS = (("train", 0.8), ("valid", 0.1), ("test", 0.1))
def split_of(source: str) -> str
    # deterministic by source, never by frame: int(sha256(source).hexdigest()[:8], 16) / 2**32 against the cumulative ratios
def assign_splits(sources: list[str]) -> dict[str, str]
    # split_of for each; then, when there are at least 3 sources and valid or test came out empty, move the
    # lexicographically last train sources into the empty splits, one each; with fewer than 3 sources every
    # source goes to train AND valid AND test is filled by copying train (a smoke-run layout, flagged in split.json)
def from_labelstudio(export: list[dict], *, use_predictions: bool = False) -> dict[str, list[dict]]
    # rel_file -> boxes in pixels [{"class", "x", "y", "w", "h"}]; reads task["annotations"][0]["result"], or
    # task["predictions"][0]["result"] when use_predictions; skips cancelled annotations; unknown class names raise ValueError
def build(root: Path, labels: dict[str, list[dict]]) -> dict
    # writes coco/<split>/ images (copies) and _annotations.coco.json with categories from classes.CLASSES
    # (ids 1..N, supercategory "none"), bbox [x, y, w, h] in pixels, area, iscrowd 0; writes coco/split.json with
    # {"sources": {source: split}, "smoke": bool, "frames": {split: n}, "boxes": {class: n},
    #  "training_set_hash": sha256 over the sorted "<file>|<class>|<x>|<y>|<w>|<h>" lines}; returns that dict;
    # clears a previous coco/ folder first (only that folder, under root)
def main(argv=None) -> int
    # coco.py EXPORT.json [--root PATH] [--from-predictions]
```

`labelstudio.xml`: a `<View>` with `<Image name="image" value="$image" zoom="true" zoomControl="true"/>`
and `<RectangleLabels name="label" toName="image">` holding one `<Label value="..."/>` per entry of
`CLASSES`, in order. A test asserts the file's label values equal `CLASSES`.

Tests: `boxes_for` with a fake `find` returning a `Match` for `play` only gives one box with the
top-left corner computed from the centre; a match hanging over the frame edge is clipped.
`task_for` percent maths on a known box (x 400, y 225, w 160, h 90 gives 25, 25, 10, 10).
`from_labelstudio` reads annotations, reads predictions with the flag, skips `was_cancelled`,
raises on an unknown class. `split_of` is stable across calls and differs for some pair of names.
`assign_splits` with 10 sources leaves no split empty and keeps every frame of a source together;
with 2 sources marks smoke. `build` on a `tmp_path` root with 3 sources of 2 tiny jpgs each writes
three annotation files whose image counts add to 6, category ids 1..N, and a `training_set_hash`
that changes when one box moves by a pixel. `main` of `prelabel` on a small index writes
`tasks.json` with one task per frame.

Steps: tests first (fail), implementation, focused tests pass, gate, commit
`feat(tools): template pre-labels, the Label Studio project and the export to a COCO folder`.

### Task 4: thresholds, training, export

Files: create `tools/play/thresholds.py`, `tools/play/train.py`, `tools/play/export.py`,
`tests/test_play_thresholds.py`.

```python
# tools/play/thresholds.py  (numpy and stdlib only: the isolated scripts import it)
MIN_PRECISION = 0.98
FLOOR, CEILING = 0.30, 0.95
def pick(scores: Sequence[float], is_tp: Sequence[bool], *, min_precision: float = MIN_PRECISION) -> float
    # the lowest threshold t in [FLOOR, CEILING] such that precision over detections with score >= t is at least
    # min_precision; CEILING when no threshold reaches it or when there are no detections; rounded to 2 decimals
def match_detections(dets: list[dict], truth: list[dict], iou_min: float = 0.5) -> list[bool]
    # dets sorted by score descending; greedy one-to-one matching per class; True for a true positive
def iou(a, b) -> float            # boxes as (x, y, w, h)
def decode(dets: np.ndarray, logits: np.ndarray, width: int, height: int, floor: float = 0.05) -> list[dict]
    # RF-DETR ONNX outputs to boxes: sigmoid(logits), column k is class index k (category id k + 1), the last
    # column is ignored; cx, cy, w, h in 0..1 scaled to pixels; returns {"class_index", "score", "x", "y", "w", "h"}
    # for every query and class with score >= floor
def preprocess(bgr: np.ndarray, size: int = 384) -> np.ndarray
    # BGR to RGB, plain resize to size x size (INTER_LINEAR), / 255, ImageNet mean and deviation, NCHW float32, batch of 1
```

`train.py` and `export.py` start with inline script metadata and import nothing from the project
except `thresholds` (through `sys.path.insert(0, <repository root>)` and `from tools.play import
thresholds`):

```python
# /// script
# requires-python = ">=3.13"
# dependencies = ["rfdetr[train,onnx]==1.10.1", "torch", "torchvision", "onnxruntime>=1.20", "opencv-python-headless"]
# [tool.uv.sources]
# torch = { index = "pytorch-cu128" }
# torchvision = { index = "pytorch-cu128" }
# [[tool.uv.index]]
# name = "pytorch-cu128"
# url = "https://download.pytorch.org/whl/cu128"
# explicit = true
# ///
```

- `train.py [--root PATH] [--epochs 60] [--batch 8] [--accum 2]`: refuses to run when
  `coco/split.json` is missing; prints the split summary and warns loudly when `smoke` is true;
  `RFDETRNano().train(dataset_dir=<root>/coco, epochs=..., batch_size=..., grad_accum_steps=...,
output_dir=<root>/runs/<stamp>, num_workers=0)`; prints the run folder.
- `export.py [--root PATH] [--run FOLDER]` (default: the newest run): loads
  `checkpoint_best_total.pth` with `RFDETRNano(pretrain_weights=...)`, exports ONNX into the run
  folder, then on every `valid` image runs the ONNX by hand (`thresholds.preprocess`,
  `thresholds.decode`) and the library's `predict(threshold=0.3)`, and fails with a clear message
  when, over the validation set, fewer than 95 percent of library detections have an ONNX detection
  of the same class index with IoU at least 0.9 (this is the column mapping check from the spec).
  Then per class: `thresholds.match_detections` against the validation truth and `thresholds.pick`.
  Writes `models/play.onnx` and `models/play.json`: `{"model": "rfdetr-nano", "rfdetr": "1.10.1",
"input": {"name": "input", "size": 384, "layout": "NCHW", "color": "RGB", "mean": [...], "std":
[...]}, "outputs": {"boxes": "dets", "logits": "labels", "box_format": "cxcywh_normalised"},
"classes": [...CLASSES order...], "thresholds": {class: t}, "training_set_hash": ..., "smoke":
bool, "validation": {class: {"truth": n, "detections": n, "precision_at_threshold": p}}, "exported":
"<UTC ISO time>"}`.

Tests (`thresholds` only; the two scripts are proven by the controller's smoke run in Task 6):
`iou` of identical boxes 1.0, disjoint 0.0, half-overlap value; `match_detections` does not match
one truth box twice and does not match across classes; `pick` returns FLOOR when every detection is
a true positive, returns the score just above the last false positive when one low-scored false
positive exists, returns CEILING with no detections; `decode` on a hand-built `dets` and `logits`
pair returns the expected pixel box and class index and ignores the last column; `preprocess`
returns shape (1, 3, 384, 384) float32 and a mid-gray image maps to values near
`(0.5 - mean) / std`. A test asserts that `train.py` and `export.py` begin with `# /// script` and
that the module `thresholds` imports nothing outside numpy and the standard library (parse its
imports with `ast`).

Steps: tests first (fail), implementation, focused tests pass, gate (ruff covers the two scripts),
`uv run python -c "import ast, pathlib; [ast.parse(pathlib.Path(p).read_text(encoding='utf-8')) for p in ('tools/play/train.py', 'tools/play/export.py')]"`,
commit `feat(tools): RF-DETR nano training and ONNX export with per-class thresholds`.
Do not run `train.py` or `export.py`: they download torch.

### Task 5: the score report

Files: create `tools/play/score.py`, `tests/test_play_score.py`.

```python
def load_model(models: Path) -> tuple[ort.InferenceSession, dict]     # play.onnx and play.json; CPU provider unless --cuda
def detect(sess, meta: dict, frame: np.ndarray) -> list[dict]
    # thresholds.preprocess, run, thresholds.decode, keep score >= meta["thresholds"][class]; adds "class" names
def template_truth(frame: np.ndarray, *, find=vision.find_with_score) -> dict[str, dict | None]
    # for each class in TEMPLATE_CLASS values: the template box (as prelabel.boxes_for) or None
def compare(detections: list[dict], truth: dict[str, dict | None], iou_min: float = 0.5) -> dict[str, str]
    # per template class: "tp" (template box and a detection with IoU >= iou_min), "fn" (template box, no such
    # detection), "fp" (no template box, at least one detection), "tn"
def report(rows: list[dict]) -> dict
    # totals per class (tp, fp, fn, tn, precision, recall) and "tap_anchor_false_positives": the count of "fp" over
    # classes in TAP_ANCHORS; "pass": that count == 0
def main(argv=None) -> int
    # score.py [--root PATH] [--models PATH] [--frames FOLDER ...] [--cuda]: every 1600 x 900 jpg or png under the given
    # folders (default: the dataset frames/ and <home>/calibration/recordings), prints the table, writes
    # models/score.json, exits 0 when "pass" else 1. File names are printed relative to their root only.
```

Tests: `compare` for each of the four outcomes; `report` sums and the pass flag flips on a single
tap anchor false positive; `detect` with a fake session object returning hand-built arrays keeps
only detections at or above the per-class threshold; `main` on a `tmp_path` with a fake
`load_model` and a fake `find` returns 0 and writes `score.json`, and returns 1 when the fake model
reports a `play_button` on a frame where the fake `find` sees none.

Steps: tests first (fail), implementation, focused tests pass, gate, commit
`feat(tools): score, the model against the template verdicts with the never-tap bar`.

### Task 6: the guide, the rails, and the controller's smoke run

Files: create `docs/play-training.md`; modify `README.md` (one line under the play extras
pointing at the guide), `CONTRIBUTING.md` (one rail: training data, videos, frames and model files
never enter the repository; `play.onnx` and `play.json` arrive only through a calibration pull
request).

`docs/play-training.md` sections, in order: what the kit is and what it is not (no model ships
with it); where data lives (the layout above, outside the checkout); step 1 frames from your own
recordings (`uv run python tools/play/frames.py --session ...`); step 2 frames from YouTube (the
URL list file, the command, a note that the list is the owner's choice and the videos stay local);
step 3 pre-labels (`prelabel.py`); step 4 labelling in Label Studio (start command with
`LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED=true` and `LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT` set
to the dataset root, create a project, paste `config.xml`, import `tasks.json`, what each class
means in one line each, a labelling rule list: box the whole sprite, skip frames with no game in
them, never label names or tags); step 5 export as JSON and `coco.py`; step 6 `train.py` (first
run downloads torch, about 3 GB; what `smoke` means); step 7 `export.py` (the parity check, how
thresholds are picked, what `play.json` holds); step 8 `score.py` and the bar; how the first model
becomes a calibration pull request. The implementer writes the guide from this plan and the tools'
real `--help` output, and leaves the exact Label Studio start command as the controller hands it
over in the dispatch (the controller verifies it live first).

Controller proof for the pull request body, run by the controller, not by an agent: frames from
the full-size recorder session on disk; `prelabel.py`; `coco.py --from-predictions` on the
generated tasks; `train.py --epochs 8`; `export.py`; `score.py`; one short YouTube video through
`ingest_youtube.py`; Label Studio started once with the import file to confirm the pre-label boxes
show.

Steps: write the docs, gate, commit `docs(play): the training guide and the dataset rails`.

### Task 7: whole-branch review, evidence, pull request

Whole-branch sonnet review of `main..play/dataset`; one fix dispatch; one scoped re-review; gate
including `pnpm typecheck` and `pnpm test`; push with the personal account token scoped to the
command; pull request against main with the smoke run numbers, scrubbed.
