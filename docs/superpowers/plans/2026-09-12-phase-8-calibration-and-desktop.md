# Phase 8: Calibration and Desktop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the Calibration page with live scores and overlays, file-based calibration and template overrides, the recalibrated queue anchor, a labeled frame recorder, and an optional desktop window with a tray icon.

**Architecture:** A standard-library module `brawlfarm/core/calibration.py` applies `<home>/calibration/calibration.toml` over the constants in `config.py` at import and on `set_home()`. `vision.py` resolves each template through an override folder with an mtime-keyed cache. A `Recorder` object rides the worker loop behind a `record.flag` file. One new flat FastAPI router serves the page; the React page under `src/calibration/` reads and never writes coordinates. `brawlfarm/desktop.py` wraps pywebview and pystray behind lazy imports and an optional dependency group.

**Tech Stack:** Python 3.13, FastAPI, tomllib, OpenCV, numpy, pytest; React 19, TypeScript strict, Tailwind v4, TanStack Query, vitest; pywebview, pystray, Pillow (optional group).

**Spec:** `docs/superpowers/specs/2026-09-10-brawlfarm-design.md` (sections 9, 10, 11, After v1) with the binding design in `docs/superpowers/plans/2026-09-12-phase-8-design-brief.md`. Where this plan and the brief disagree, the brief wins.

## Global Constraints

- This is the owner-approved calibration PR named in the spec. Only Task 3 changes a shipped template or a threshold; it changes exactly `matchmaking.png`, `MATCHMAKING_THRESHOLD`, and the `COLOR_ONLY_TEMPLATES` membership. No tap coordinate constant changes value. Never-tap logic, verify-then-act, and the 1600x900 assertion in `controller.py` are untouched.
- No user-supplied string reaches a shell or a filesystem path except instance names validated by `resolve_instance` and template names checked against `vision.TEMPLATE_NAMES`.
- The legacy checkout `../bsutil` is read-only reference. Never write its path, nicknames, player tags, or the machine user name into any file. Never write an absolute path under the user's home directory into a file or a test. `uv run python tools/scrub_check.py` must print `0 hit(s)` before every commit.
- No `discord` import. Never log or print the API token or player tag.
- Commit messages follow conventional commits, are written with `git commit -F <file>` (file in the scratchpad or `.superpowers/`), and end with exactly one trailer line: `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. No em-dashes and no emoji in prose, docs, comments or commit messages.
- Web code: TypeScript strict, `pnpm typecheck` and `pnpm test` (vitest) pass; copy follows the existing tone (sentence case, plain words). Python: `uv run ruff check .` and `uv run pytest` pass.
- Nothing on the Calibration page writes a coordinate. The API has no route that writes `calibration.toml` or a template.
- The recorder deletes nothing. Recordings and corpus frames are never committed.
- Run pytest as `uv run pytest -q` and single files as `uv run pytest tests/test_x.py -q`. Run web commands from `brawlfarm/web` with `pnpm`.

---

### Task 1: Calibration override module and the config hook

**Files:**
- Create: `brawlfarm/core/calibration.py`
- Modify: `brawlfarm/core/config.py` (tail after line 724, and `set_home()` at lines 38 to 42)
- Test: `tests/test_calibration_overrides.py`

**Interfaces:**
- Produces: `calibration.overridable(ns) -> dict[str, object]`, `calibration.group_of(name, value) -> Literal["tap","threshold","timing"]`, `calibration.apply(ns, path) -> Report`, `calibration.changed_since(report) -> bool`, `Report(path, present, mtime_ns, applied, problems, defaults)`, `config.CALIBRATION_FILE: Path`, `config.CALIBRATION: Report`. Task 5 reads `config.CALIBRATION`, `calibration.overridable(vars(config))` and `calibration.group_of`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_calibration_overrides.py
from pathlib import Path

from brawlfarm.core import calibration


def _ns() -> dict[str, object]:
    return {
        "PLAY_BUTTON": (1434, 830),
        "MATCH_THRESHOLD": 0.85,
        "ATTACK_INTERVAL": 0.5,
        "SCREEN_W": 1600,
        "GRAY_MATCH": True,
        "MAX_GAMES": 40,
        "NAME": "x",
        "COLOR_ONLY_TEMPLATES": frozenset({"close_x"}),
        "REGION": (1, 2, 3, 4),
        "_PRIVATE": 1.0,
        "lower": 2.0,
    }


def test_overridable_picks_floats_and_two_int_tuples_only():
    picked = calibration.overridable(_ns())
    assert set(picked) == {"PLAY_BUTTON", "MATCH_THRESHOLD", "ATTACK_INTERVAL"}


def test_group_of():
    assert calibration.group_of("PLAY_BUTTON", (1, 2)) == "tap"
    assert calibration.group_of("MATCH_THRESHOLD", 0.85) == "threshold"
    assert calibration.group_of("ATTACK_INTERVAL", 0.5) == "timing"


def test_apply_missing_file_changes_nothing(tmp_path: Path):
    ns = _ns()
    report = calibration.apply(ns, tmp_path / "calibration.toml")
    assert report.present is False
    assert report.applied == {}
    assert report.problems == ()
    assert ns["PLAY_BUTTON"] == (1434, 830)
    assert report.defaults["PLAY_BUTTON"] == (1434, 830)


def test_apply_overrides_and_converts(tmp_path: Path):
    f = tmp_path / "calibration.toml"
    f.write_text("PLAY_BUTTON = [1434, 826]\nMATCH_THRESHOLD = 1\n", encoding="utf-8")
    ns = _ns()
    report = calibration.apply(ns, f)
    assert ns["PLAY_BUTTON"] == (1434, 826)
    assert ns["MATCH_THRESHOLD"] == 1.0 and isinstance(ns["MATCH_THRESHOLD"], float)
    assert report.applied == {"PLAY_BUTTON": (1434, 826), "MATCH_THRESHOLD": 1.0}
    assert report.present is True and report.mtime_ns is not None


def test_apply_reports_unknown_and_wrong_shape(tmp_path: Path):
    f = tmp_path / "calibration.toml"
    f.write_text(
        'PLAY_BUTON = [1, 2]\nPLAY_BUTTON = "no"\nMATCH_THRESHOLD = [1, 2]\nSCREEN_W = 1\n',
        encoding="utf-8",
    )
    ns = _ns()
    report = calibration.apply(ns, f)
    assert ns["PLAY_BUTTON"] == (1434, 830)
    assert ns["MATCH_THRESHOLD"] == 0.85
    assert ns["SCREEN_W"] == 1600
    assert report.problems == (
        "MATCH_THRESHOLD must be a number.",
        "PLAY_BUTON is not a calibration constant. The line is ignored.",
        "PLAY_BUTTON must be two integers.",
        "SCREEN_W is not a calibration constant. The line is ignored.",
    )


def test_apply_bad_toml_changes_nothing(tmp_path: Path):
    f = tmp_path / "calibration.toml"
    f.write_text("PLAY_BUTTON = [1,", encoding="utf-8")
    ns = _ns()
    report = calibration.apply(ns, f)
    assert ns["PLAY_BUTTON"] == (1434, 830)
    assert len(report.problems) == 1
    assert report.problems[0].startswith("calibration.toml could not be read: ")


def test_apply_twice_restores_defaults_when_key_removed(tmp_path: Path):
    f = tmp_path / "calibration.toml"
    ns = _ns()
    f.write_text("PLAY_BUTTON = [1, 2]\n", encoding="utf-8")
    calibration.apply(ns, f)
    assert ns["PLAY_BUTTON"] == (1, 2)
    f.write_text("MATCH_THRESHOLD = 0.5\n", encoding="utf-8")
    report = calibration.apply(ns, f)
    assert ns["PLAY_BUTTON"] == (1434, 830)
    assert ns["MATCH_THRESHOLD"] == 0.5
    assert report.applied == {"MATCH_THRESHOLD": 0.5}


def test_changed_since(tmp_path: Path):
    f = tmp_path / "calibration.toml"
    ns = _ns()
    report = calibration.apply(ns, f)
    assert calibration.changed_since(report) is False
    f.write_text("MATCH_THRESHOLD = 0.5\n", encoding="utf-8")
    assert calibration.changed_since(report) is True


def test_config_applies_file_from_home(tmp_path: Path):
    from brawlfarm.core import config

    (tmp_path / "calibration").mkdir()
    (tmp_path / "calibration" / "calibration.toml").write_text(
        "MATCH_THRESHOLD = 0.77\n", encoding="utf-8"
    )
    config.set_home(tmp_path)
    try:
        assert config.MATCH_THRESHOLD == 0.77
        assert config.CALIBRATION.applied == {"MATCH_THRESHOLD": 0.77}
        assert config.CALIBRATION_FILE == tmp_path / "calibration" / "calibration.toml"
    finally:
        (tmp_path / "calibration" / "calibration.toml").unlink()
        config.set_home(tmp_path)
    assert config.MATCH_THRESHOLD == 0.85
```

Note on the sorted problems: `apply` sorts `problems` by key name so the tuple order is stable; the test above lists them in that order.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_calibration_overrides.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'brawlfarm.core.calibration'`

- [ ] **Step 3: Write the module**

```python
# brawlfarm/core/calibration.py
"""Calibration overrides read from <home>/calibration/calibration.toml.

The file is flat TOML. Keys are the names of overridable constants in
brawlfarm.core.config: floats (timings and thresholds) and two-int tuples
(tap coordinates). Nothing here writes the file; the app only reads it.
This module imports only the standard library and never imports config.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Group = Literal["tap", "threshold", "timing"]

LOCKED: frozenset[str] = frozenset({"SCREEN_W", "SCREEN_H", "SCREEN_DPI"})

_DEFAULTS: dict[str, object] = {}


@dataclass(frozen=True)
class Report:
    path: Path
    present: bool
    mtime_ns: int | None
    applied: dict[str, object]
    problems: tuple[str, ...]
    defaults: dict[str, object]


def _is_tap(value: object) -> bool:
    return (
        isinstance(value, tuple)
        and len(value) == 2
        and all(isinstance(v, int) and not isinstance(v, bool) for v in value)
    )


def _is_float(value: object) -> bool:
    return isinstance(value, float)


def overridable(ns: Mapping[str, object]) -> dict[str, object]:
    """Names in ns that calibration.toml may override, with their values."""
    out: dict[str, object] = {}
    for name, value in ns.items():
        if not name.isupper() or name.startswith("_") or name in LOCKED:
            continue
        if _is_tap(value) or _is_float(value):
            out[name] = value
    return out


def group_of(name: str, value: object) -> Group:
    if _is_tap(value):
        return "tap"
    if name.endswith("_THRESHOLD"):
        return "threshold"
    return "timing"


def _coerce(name: str, default: object, raw: object) -> tuple[object | None, str | None]:
    if _is_tap(default):
        if (
            isinstance(raw, list)
            and len(raw) == 2
            and all(isinstance(v, int) and not isinstance(v, bool) for v in raw)
        ):
            return (raw[0], raw[1]), None
        return None, f"{name} must be two integers."
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return None, f"{name} must be a number."
    return float(raw), None


def apply(ns: dict[str, object], path: Path) -> Report:
    """Restore defaults for every overridable name, then apply the file over them."""
    if not _DEFAULTS:
        _DEFAULTS.update(overridable(ns))
    for name, value in _DEFAULTS.items():
        ns[name] = value
    defaults = dict(_DEFAULTS)

    if not path.is_file():
        return Report(path, False, None, {}, (), defaults)
    try:
        mtime_ns = path.stat().st_mtime_ns
        with path.open("rb") as fh:
            data = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return Report(path, True, None, {}, (f"calibration.toml could not be read: {exc}",), defaults)

    applied: dict[str, object] = {}
    problems: list[str] = []
    for name in sorted(data):
        raw = data[name]
        if name not in defaults:
            problems.append(f"{name} is not a calibration constant. The line is ignored.")
            continue
        value, problem = _coerce(name, defaults[name], raw)
        if problem is not None:
            problems.append(problem)
            continue
        ns[name] = value
        applied[name] = value
    return Report(path, True, mtime_ns, applied, tuple(problems), defaults)


def changed_since(report: Report) -> bool:
    """True when the file's presence or mtime differs from what report saw."""
    try:
        current: int | None = report.path.stat().st_mtime_ns
    except OSError:
        current = None
    return current != report.mtime_ns
```

- [ ] **Step 4: Hook config.py**

Append to the end of `brawlfarm/core/config.py` (after `BUSH_JITTER_MAX_INTERVAL = 8.0`):

```python

# --- Calibration overrides (phase 8): <home>/calibration/calibration.toml ----------
# Floats and two-int tap tuples above may be overridden from that file. The
# module below only reads; nothing in the app writes calibration.toml.
from brawlfarm.core import calibration as _calibration  # noqa: E402

CALIBRATION_FILE = HOME_DIR / "calibration" / "calibration.toml"
CALIBRATION = _calibration.apply(globals(), CALIBRATION_FILE)
```

Extend `set_home()` so its body ends with:

```python
    global CALIBRATION_FILE, CALIBRATION
    CALIBRATION_FILE = HOME_DIR / "calibration" / "calibration.toml"
    CALIBRATION = _calibration.apply(globals(), CALIBRATION_FILE)
```

`set_home` is defined before `_calibration` is imported at the tail; that is fine because the name is only resolved when `set_home` is called. Add `CALIBRATION_FILE` and `CALIBRATION` to the existing `global` statement in `set_home` (or a second `global` line as above).

Then grep for `from brawlfarm.core.config import` across `brawlfarm/` and check whether any imported name is in `calibration.overridable(vars(config))`. If one is, change that import site to read `config.NAME` at call time. Report what you found in the task report.

- [ ] **Step 5: Run the tests and the suite**

Run: `uv run pytest tests/test_calibration_overrides.py -q` then `uv run pytest -q` and `uv run ruff check .`
Expected: all PASS, ruff clean. If `tests/conftest.py`'s `_isolated_home` fixture makes `config.MATCH_THRESHOLD == 0.85` false at the end of the last test (because another test left a file), fix the test's cleanup, not the fixture.

- [ ] **Step 6: Scrub and commit**

Run: `uv run python tools/scrub_check.py` (expect `0 hit(s)`), then commit with message file:

```
feat(core): calibration.toml overrides for tap points, timings and thresholds

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
```

---

### Task 2: Template override folder and the fixed template list

**Files:**
- Modify: `brawlfarm/core/vision.py:41-72` (loaders) and `find()` at line 74
- Test: `tests/test_vision_templates.py`

**Interfaces:**
- Produces: `vision.TEMPLATE_NAMES: tuple[str, ...]`, `vision.OVERRIDE_DIR() -> Path` (returns `config.HOME_DIR / "calibration" / "templates"`), `vision.template_path(name) -> Path`, `vision.template_source(name) -> Literal["package","override"]`, `vision.threshold_for(name) -> float`. Task 4 and Task 5 use `TEMPLATE_NAMES`, `template_path`, `template_source`, `threshold_for`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_vision_templates.py
from pathlib import Path

import cv2
import numpy as np

from brawlfarm.core import config, vision


def test_template_names_match_folder():
    names = sorted(p.stem for p in config.TEMPLATES_DIR.glob("*.png"))
    assert list(vision.TEMPLATE_NAMES) == names
    assert "play" in vision.TEMPLATE_NAMES


def test_template_path_prefers_override(tmp_path: Path):
    config.set_home(tmp_path)
    assert vision.template_source("play") == "package"
    assert vision.template_path("play") == config.TEMPLATES_DIR / "play.png"
    override = tmp_path / "calibration" / "templates"
    override.mkdir(parents=True)
    img = np.zeros((10, 20, 3), dtype=np.uint8)
    cv2.imwrite(str(override / "play.png"), img)
    assert vision.template_source("play") == "override"
    assert vision.template_path("play") == override / "play.png"


def test_loader_picks_up_override_without_restart(tmp_path: Path):
    config.set_home(tmp_path)
    packaged = vision._load_template("play")
    override = tmp_path / "calibration" / "templates"
    override.mkdir(parents=True)
    img = np.full((10, 20, 3), 7, dtype=np.uint8)
    cv2.imwrite(str(override / "play.png"), img)
    loaded = vision._load_template("play")
    assert loaded.shape == (10, 20, 3)
    assert loaded.shape != packaged.shape
    (override / "play.png").unlink()
    assert vision._load_template("play").shape == packaged.shape


def test_threshold_for_matches_find_defaults():
    assert vision.threshold_for("play") == config.MATCH_THRESHOLD
    assert vision.threshold_for("teams_left") == config.IN_MATCH_THRESHOLD
    assert vision.threshold_for("matchmaking") == config.MATCHMAKING_THRESHOLD
```

Before writing the last test, read `find()` to see which names get `IN_MATCH_THRESHOLD` and `MATCHMAKING_THRESHOLD` today; `threshold_for` must reproduce exactly that branching. Adjust the test's names to what `find()` actually does if they differ from the three lines above, and say so in the report.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_vision_templates.py -q`
Expected: FAIL with `AttributeError: module 'brawlfarm.core.vision' has no attribute 'TEMPLATE_NAMES'`

- [ ] **Step 3: Implement**

In `vision.py`, replace the two loaders with:

```python
TEMPLATE_NAMES: tuple[str, ...] = tuple(sorted(p.stem for p in config.TEMPLATES_DIR.glob("*.png")))


def OVERRIDE_DIR() -> Path:
    return config.HOME_DIR / "calibration" / "templates"


def template_path(name: str) -> Path:
    override = OVERRIDE_DIR() / f"{name}.png"
    if override.is_file():
        return override
    return config.TEMPLATES_DIR / f"{name}.png"


def template_source(name: str) -> Literal["package", "override"]:
    return "override" if (OVERRIDE_DIR() / f"{name}.png").is_file() else "package"


@lru_cache(maxsize=64)
def _read_template(path_str: str, mtime_ns: int) -> np.ndarray:
    img = cv2.imread(path_str, cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(path_str)
    return img


@lru_cache(maxsize=64)
def _read_template_gray(path_str: str, mtime_ns: int) -> np.ndarray:
    return cv2.cvtColor(_read_template(path_str, mtime_ns), cv2.COLOR_BGR2GRAY)


def _stat_key(name: str) -> tuple[str, int]:
    path = template_path(name)
    return str(path), path.stat().st_mtime_ns


def _load_template(name: str) -> np.ndarray:
    return _read_template(*_stat_key(name))


def _load_template_gray(name: str) -> np.ndarray:
    return _read_template_gray(*_stat_key(name))
```

Keep whatever error handling the current loaders have for a missing packaged file (read them first; if they raise a specific error type or log, preserve that). Then add:

```python
def threshold_for(name: str) -> float:
    """The threshold find() uses for this template when none is passed."""
    ...  # the exact branching currently inside find(), moved here
```

and make `find()` call `threshold_for(name)` when `threshold is None`. Behavior of `find`, `find_with_score` and `score` is otherwise unchanged.

- [ ] **Step 4: Run the tests and the suite**

Run: `uv run pytest tests/test_vision_templates.py -q`, then `uv run pytest -q`, `uv run ruff check .`
Expected: all PASS.

- [ ] **Step 5: Scrub and commit**

```
feat(vision): template overrides from the calibration folder and a fixed template list

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
```

---

### Task 3: The queue anchor fix

**Files:**
- Replace: `brawlfarm/core/templates/matchmaking.png` (binary)
- Modify: `brawlfarm/core/config.py:196` (`COLOR_ONLY_TEMPLATES`) and `:208` (`MATCHMAKING_THRESHOLD`)
- Test: existing suite; corpus check via the spike script (not committed)

**Interfaces:**
- Consumes: nothing new. Produces: the new template is 276x45; `config.MATCHMAKING_THRESHOLD == 0.85`; `"matchmaking" not in config.COLOR_ONLY_TEMPLATES`.

- [ ] **Step 1: Copy the template**

The new template file is provided by the controller in the dispatch as an absolute path in the scratchpad (never write that path into the repo). Copy it over `brawlfarm/core/templates/matchmaking.png` with a single `cp`. Verify with Python: `cv2.imread(...).shape == (45, 276, 3)`.

- [ ] **Step 2: Change the two constants**

`COLOR_ONLY_TEMPLATES = frozenset({"close_x"})` and `MATCHMAKING_THRESHOLD = 0.85`. Update the comment next to `MATCHMAKING_THRESHOLD` to say the anchor is the "Players found N/12" line, gray-matched, measured on the 2026-09 corpus (queue frames at or above 0.99, other frames at or below 0.51).

- [ ] **Step 3: Run the suite**

Run: `uv run pytest -q` and `uv run ruff check .`
Expected: PASS. If a test asserts the old threshold or the color-only membership for matchmaking, update that assertion (it is asserting the value this PR is approved to change) and name it in the report. Do not touch never-tap tests; if one fails, stop and report BLOCKED.

- [ ] **Step 4: Corpus verification**

The controller runs the spike script from the scratchpad against the worktree (`PYTHONDONTWRITEBYTECODE=1 uv run --no-sync --project <worktree> python repro.py`), not the implementer. The implementer's report ends at Step 5.

- [ ] **Step 5: Scrub and commit**

```
fix(vision): recalibrate the queue anchor to the Players found line

The shipped matchmaking.png was a flat gradient crop that no longer
appears in the queue screen, so the worker never saw MATCHMAKING and
every queue ended in a timeout recovery. The new template is the
"Players found N/12" line (276x45), matched in gray at 0.85. On the
2026-09 corpus of 195 labeled frames every queue frame scores at or
above 0.99 and every other frame at or below 0.51.

Owner-approved calibration change (phase 8).

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
```

---

### Task 4: The labeled frame recorder

**Files:**
- Create: `brawlfarm/core/recorder.py`
- Modify: `brawlfarm/core/controller.py` (`__init__`, `run()` around lines 1441, 1458, 1504 to 1512, and the exit of `run()`)
- Test: `tests/test_recorder.py`

**Interfaces:**
- Consumes: `preview.encode(screen) -> bytes`, `vision.TEMPLATE_NAMES`, `vision.score(screen, name) -> float`, `states.State`, `jsonio.atomic_write_json(path, obj)` (check the exact name in `brawlfarm/core/jsonio.py` and use what exists).
- Produces: `Recorder(root, instance, flag, *, clock=time.monotonic, wall=datetime.now)` with `poll()`, `observe(screen, state, phase) -> bool`, `status() -> dict`, `close()`; `recorder.json` in the instance data dir with keys `on, frames, bytes, session, path, reason, last_session, last_frames`; `record.flag` in the instance data dir as the switch. Task 5 reads `recorder.json` and creates/deletes `record.flag`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_recorder.py
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest

from brawlfarm.core import vision
from brawlfarm.core.recorder import Recorder
from brawlfarm.core.states import State


class Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


def _screen(v: int = 0) -> np.ndarray:
    return np.full((900, 1600, 3), v, dtype=np.uint8)


@pytest.fixture
def rec(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(vision, "score", lambda screen, name: 0.25)
    data = tmp_path / "data" / "Pie64"
    data.mkdir(parents=True)
    clock = Clock()
    wall = lambda: datetime(2026, 9, 12, 21, 11, 3, 200000)  # noqa: E731
    r = Recorder(tmp_path / "calibration", "Pie64", data / "record.flag", clock=clock, wall=wall)
    return r, clock, data, tmp_path / "calibration"


def test_off_by_default_writes_nothing(rec):
    r, clock, data, root = rec
    r.poll()
    assert r.observe(_screen(), State.MENU, "menu") is False
    assert not (root / "recordings").exists()
    st = json.loads((data / "recorder.json").read_text(encoding="utf-8"))
    assert st == {
        "on": False, "frames": 0, "bytes": 0, "session": None, "path": None,
        "reason": None, "last_session": None, "last_frames": 0,
    }


def test_flag_opens_session_and_writes_labeled_frames(rec):
    r, clock, data, root = rec
    (data / "record.flag").touch()
    r.poll()
    assert r.observe(_screen(), State.MENU, "menu") is True
    assert r.observe(_screen(), State.MENU, "menu") is False  # same state, < 1 s
    clock.t += 1.0
    assert r.observe(_screen(), State.MENU, "menu") is True
    assert r.observe(_screen(), State.MATCHMAKING, "queue") is True  # state change
    session = root / "recordings" / "Pie64" / "20260912-211103"
    assert sorted(p.name for p in session.glob("*.jpg")) == [
        "0001-menu.jpg", "0002-menu.jpg", "0003-matchmaking.jpg",
    ]
    lines = [json.loads(l) for l in (session / "labels.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [l["seq"] for l in lines] == [1, 2, 3]
    assert lines[0]["ts"] == "21:11:03.2"
    assert lines[2]["state"] == "matchmaking" and lines[2]["phase"] == "queue"
    assert set(lines[0]["scores"]) == set(vision.TEMPLATE_NAMES)
    st = r.status()
    assert st["on"] is True and st["frames"] == 3 and st["session"] == "20260912-211103"
    assert st["path"] == "recordings/Pie64/20260912-211103"
    assert st["bytes"] > 0


def test_flag_removed_closes_session(rec):
    r, clock, data, root = rec
    (data / "record.flag").touch()
    r.poll()
    r.observe(_screen(), State.MENU, "menu")
    (data / "record.flag").unlink()
    r.poll()
    assert r.observe(_screen(), State.RESULTS, "results") is False
    st = r.status()
    assert st["on"] is False and st["last_session"] == "20260912-211103" and st["last_frames"] == 1


def test_frame_cap_closes_session(rec, monkeypatch):
    r, clock, data, root = rec
    monkeypatch.setattr(Recorder, "MAX_FRAMES", 3)
    (data / "record.flag").touch()
    r.poll()
    for i in range(3):
        clock.t += 1.0
        assert r.observe(_screen(), State.MENU, "menu") is True
    clock.t += 1.0
    assert r.observe(_screen(), State.MENU, "menu") is False
    assert r.status()["on"] is False and r.status()["reason"] == "frame_cap"
    r.poll()  # flag still set: stays closed
    assert r.status()["on"] is False


def test_disk_cap_refuses_to_open(rec, monkeypatch):
    r, clock, data, root = rec
    monkeypatch.setattr(Recorder, "MAX_BYTES", 10)
    old = root / "recordings" / "Pie64" / "20260101-000000"
    old.mkdir(parents=True)
    (old / "0001-menu.jpg").write_bytes(b"x" * 11)
    (data / "record.flag").touch()
    r.poll()
    assert r.status()["on"] is False and r.status()["reason"] == "disk_cap"
    assert r.observe(_screen(), State.MENU, "menu") is False


def test_write_failure_does_not_raise(rec, monkeypatch):
    r, clock, data, root = rec
    (data / "record.flag").touch()
    r.poll()
    from brawlfarm.core import preview

    def boom(screen):
        raise OSError("disk gone")

    monkeypatch.setattr(preview, "encode", boom)
    assert r.observe(_screen(), State.MENU, "menu") is False
    assert r.status()["on"] is False
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_recorder.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'brawlfarm.core.recorder'`

- [ ] **Step 3: Implement `recorder.py`**

Follow the brief's section 7 exactly. Skeleton:

```python
"""Labeled frame recorder for recalibration corpora.

Switched by an empty record.flag file in the instance data dir, which the
API creates and deletes. Off by default. Writes JPEG frames plus one
labels.jsonl line per frame. Never deletes anything.
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
    MAX_FRAMES = 2000
    MAX_BYTES = 512 * 1024 * 1024
    MIN_INTERVAL_S = 1.0

    def __init__(self, root: Path, instance: str, flag: Path, *,
                 clock: Callable[[], float] = time.monotonic,
                 wall: Callable[[], datetime] = datetime.now) -> None:
        self._root = root
        self._instance = instance
        self._flag = flag
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
        self._status_path = flag.parent / "recorder.json"
        self._write_status()
```

`poll()`: flag exists and no session: compute `_instance_bytes()` by walking `root/recordings/instance` (0 when absent); if `>= MAX_BYTES` set `_reason = "disk_cap"`, else if `_reason == "frame_cap"` stay closed (cap sticks until the flag is cleared), else open `root/recordings/instance/<wall().strftime("%Y%m%d-%H%M%S")>` with `mkdir(parents=True, exist_ok=True)`, reset seq/bytes/last_state, `_reason = None`. Flag absent: `_reason = None` and `_close_session()` if open. Always `_write_status()` at the end.

`observe(screen, state, phase)`: return False when no session. Skip when `state == _last_state and clock() - _last_write < MIN_INTERVAL_S`. Otherwise seq += 1, `name = f"{seq:04d}-{state.name.lower()}.jpg"`, `data = preview.encode(screen)`, write bytes, append the labels line (`ts = wall().strftime("%H:%M:%S.%f")[:-5]` gives `HH:MM:SS.f`), `scores = {n: round(float(vision.score(screen, n)), 4) for n in vision.TEMPLATE_NAMES}`, update `_bytes`, `_last_write`, `_last_state`; if `seq >= MAX_FRAMES`: `_reason = "frame_cap"` and `_close_session()`. Wrap the whole write in `try/except Exception` that logs once (`log.warning("recorder stopped: %s", exc)`), closes the session, returns False. `_write_status()` after every write.

`_close_session()`: set `_last_session`, `_last_frames = _seq`, clear `_session`, `_session_id`. `status()` returns the eight keys; `path` is `f"recordings/{instance}/{session_id}"` or None. `close()` = `_close_session()` + `_write_status()`. `_write_status()` uses `jsonio`'s atomic writer inside try/except OSError.

- [ ] **Step 4: Wire the controller**

In `Controller.__init__`: `self.recorder = Recorder(config.HOME_DIR / "calibration", config.DATA_DIR.name, config.DATA_DIR / "record.flag")`. In `run()`: after the `classify` line, `self.recorder.observe(screen, state, self.phase)`; inside the every-25-ticks block, `self.recorder.poll()`; in the `finally` (or wherever `run()` exits, read it) `self.recorder.close()`. Do not touch the never-tap logic or the 1600x900 assertion. If a controller unit test constructs `Controller` with a fake config lacking `DATA_DIR.name`, adapt the recorder construction to `getattr` safely and note it.

- [ ] **Step 5: Run the tests and the suite**

Run: `uv run pytest tests/test_recorder.py -q`, `uv run pytest -q`, `uv run ruff check .`
Expected: PASS.

- [ ] **Step 6: Scrub and commit**

```
feat(core): labeled frame recorder behind record.flag

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
```

---

### Task 5: The calibration API router

**Files:**
- Create: `brawlfarm/api/calibration.py`
- Modify: `brawlfarm/api/app.py` (import near lines 28 to 47, `include_router` near lines 182 to 194)
- Test: `tests/test_api_calibration.py`

**Interfaces:**
- Consumes: Task 1 `config.CALIBRATION`, `calibration.overridable`, `calibration.group_of`, `calibration.changed_since`; Task 2 `vision.TEMPLATE_NAMES`, `template_path`, `template_source`, `threshold_for`, `find_with_score`; Task 4 `recorder.json` and `record.flag`; existing `deps.get_home`, `deps.resolve_instance`, `S.instance_dir`, `states.classify`.
- Produces: the six routes in the brief's section 8; Task 6 codes against these payloads.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_api_calibration.py
import json
import sys
from pathlib import Path

import cv2
import numpy as np

from brawlfarm.core import config, vision
from tests.apihelpers import make_client


def test_get_calibration_defaults():
    client, sup, home = make_client()
    r = client.get("/api/calibration")
    assert r.status_code == 200
    body = r.json()
    assert body["file"] == {"present": False, "changed_since_start": False, "problems": []}
    names = {c["name"] for c in body["constants"]}
    assert {"PLAY_BUTTON", "MATCH_THRESHOLD", "MATCHMAKING_THRESHOLD"} <= names
    play = next(c for c in body["constants"] if c["name"] == "PLAY_BUTTON")
    assert play["group"] == "tap" and play["source"] == "package"
    assert play["default"] == play["value"] == list(config.PLAY_BUTTON)
    mk = next(t for t in body["templates"] if t["name"] == "matchmaking")
    assert mk == {"name": "matchmaking", "source": "package", "width": 276, "height": 45,
                  "threshold": config.MATCHMAKING_THRESHOLD}
    assert [t["name"] for t in body["templates"]] == list(vision.TEMPLATE_NAMES)


def test_get_calibration_with_override_file():
    client, sup, home = make_client()
    (home / "calibration").mkdir(exist_ok=True)
    (home / "calibration" / "calibration.toml").write_text(
        "PLAY_BUTTON = [1, 2]\nNOPE = 3\n", encoding="utf-8"
    )
    config.set_home(home)
    try:
        body = client.get("/api/calibration").json()
        assert body["file"]["present"] is True
        assert body["file"]["problems"] == ["NOPE is not a calibration constant. The line is ignored."]
        play = next(c for c in body["constants"] if c["name"] == "PLAY_BUTTON")
        assert play["value"] == [1, 2] and play["source"] == "calibration.toml"
        (home / "calibration" / "calibration.toml").write_text("PLAY_BUTTON = [3, 4]\n", encoding="utf-8")
        import os
        os.utime(home / "calibration" / "calibration.toml", ns=(1, 1))
        assert client.get("/api/calibration").json()["file"]["changed_since_start"] is True
    finally:
        (home / "calibration" / "calibration.toml").unlink()
        config.set_home(home)


def test_template_png_route():
    client, sup, home = make_client()
    r = client.get("/api/calibration/templates/play.png")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.headers["cache-control"] == "no-store"
    assert r.content[:4] == b"\x89PNG"
    assert client.get("/api/calibration/templates/nope.png").status_code == 404
    assert client.get("/api/calibration/templates/..%2Fplay.png").status_code in (404, 422)


def test_scores_route_no_frame_then_frame(monkeypatch):
    client, sup, home = make_client()
    name = sup.settings.instances[0].name
    r = client.get(f"/api/instances/{name}/calibration/scores")
    assert r.status_code == 404 and r.json()["detail"] == "no frame yet"
    inst = home / "data" / name
    inst.mkdir(parents=True, exist_ok=True)
    frame = np.zeros((900, 1600, 3), dtype=np.uint8)
    cv2.imwrite(str(inst / "preview.jpg"), frame)
    (inst / "status.json").write_text(json.dumps({"phase": "menu"}), encoding="utf-8")
    r = client.get(f"/api/instances/{name}/calibration/scores")
    assert r.status_code == 200
    body = r.json()
    assert body["width"] == 1600 and body["height"] == 900
    assert body["phase"] == "menu"
    assert body["state"] in {s.name.lower() for s in __import__("brawlfarm.core.states", fromlist=["State"]).State}
    assert [a["name"] for a in body["anchors"]] == list(vision.TEMPLATE_NAMES)
    play = next(a for a in body["anchors"] if a["name"] == "play")
    assert play["expected"] is True and play["found"] is False
    assert set(play["box"]) == {"x", "y", "w", "h"}
    assert client.get("/api/instances/Nope/calibration/scores").status_code == 404


def test_open_folder(monkeypatch):
    client, sup, home = make_client()
    monkeypatch.setattr(sys, "platform", "win32")
    opened: list[str] = []
    monkeypatch.setattr("os.startfile", lambda p: opened.append(p), raising=False)
    r = client.post("/api/calibration/open-folder")
    assert r.status_code == 204
    assert (home / "calibration").is_dir()
    assert opened and opened[0].endswith("calibration")
    monkeypatch.setattr(sys, "platform", "linux")
    assert client.post("/api/calibration/open-folder").status_code == 501


def test_recorder_routes():
    client, sup, home = make_client()
    name = sup.settings.instances[0].name
    body = client.get(f"/api/instances/{name}/recorder").json()
    assert body == {"on": False, "frames": 0, "bytes": 0, "session": None, "path": None,
                    "reason": None, "last_session": None, "last_frames": 0, "flag": False}
    r = client.post(f"/api/instances/{name}/recorder", json={"on": True})
    assert r.status_code == 200 and r.json()["flag"] is True
    assert (home / "data" / name / "record.flag").exists()
    inst = home / "data" / name
    (inst / "recorder.json").write_text(json.dumps({
        "on": True, "frames": 5, "bytes": 1234, "session": "20260912-211103",
        "path": f"recordings/{name}/20260912-211103", "reason": None,
        "last_session": None, "last_frames": 0}), encoding="utf-8")
    body = client.get(f"/api/instances/{name}/recorder").json()
    assert body["frames"] == 5 and body["flag"] is True
    r = client.post(f"/api/instances/{name}/recorder", json={"on": False})
    assert r.status_code == 200 and r.json()["flag"] is False
    assert not (inst / "record.flag").exists()
    assert client.post("/api/instances/Nope/recorder", json={"on": True}).status_code == 404
```

Read `tests/apihelpers.py` first for the exact way to get the first configured instance name and where the instance data dir lives under `home` (`S.instance_dir(home, name)`); adjust the two `home / "data" / name` lines to that helper if it differs.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_api_calibration.py -q`
Expected: FAIL with 404s (routes missing).

- [ ] **Step 3: Implement the router**

```python
# brawlfarm/api/calibration.py
"""Calibration read-outs, template files, recorder switch, open folder.

Nothing here writes calibration.toml or a template. The only writes are
creating the calibration folder and creating or removing record.flag in an
instance's data folder.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from brawlfarm.api.deps import get_home, resolve_instance
from brawlfarm.core import calibration, config, states, vision
from brawlfarm.supervisor import settings as S

router = APIRouter()

EXPECTED_BY_PHASE: dict[str, frozenset[str]] = { ... }  # built from controller phase names, see below
```

Build `EXPECTED_BY_PHASE` by reading `controller.py` for the set of `self.phase` string values (grep `self.phase =`) and mapping each to the anchors that phase should see: phases that sit in the menu expect `{"play"}`, the queue phase `{"matchmaking"}`, the in-match phase `{"teams_left"}`, results phases `{"playagain", "proceed", "exit"}`, the trophy phase `{"trophy_screen", "trophy_brawler"}`; any other phase expects nothing. List the phase strings you found in the report.

Routes:

- `GET /api/calibration`: `report = config.CALIBRATION`; `ov = calibration.overridable(vars(config))`; constants sorted by `(group, name)` with `default = report.defaults.get(name, value)`, `value = ov[name]`, tuples serialized as lists, `source = "calibration.toml" if name in report.applied else "package"`; templates for `vision.TEMPLATE_NAMES` with `h, w = vision._load_template(name).shape[:2]`, `source = vision.template_source(name)`, `threshold = vision.threshold_for(name)`; `file = {"present": report.present, "changed_since_start": calibration.changed_since(report), "problems": list(report.problems)}`.
- `GET /api/instances/{name}/calibration/scores`: `resolve_instance`; `inst = S.instance_dir(home, name)`; read `preview.jpg` bytes (404 `"no frame yet"` when missing); `screen = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)` (404 when None); `ts` from the file mtime as ISO UTC; `phase` from `status.json` `"phase"` key or None (any read/parse error: None); `state = states.classify(screen, phase=phase).name.lower()`; per template `m = vision.find_with_score(screen, name)` (read its return shape first; it returns a match with confidence and box even below threshold, or a `(match, score)` pair; use whatever it returns to fill `score`, `box`) with `threshold = vision.threshold_for(name)`, `found = score >= threshold`, `expected = name in EXPECTED_BY_PHASE.get(phase or "", frozenset())`. Run the scoring in `asyncio.to_thread` because 13 matches take about 150 ms.
- `GET /api/calibration/templates/{name}.png`: declare the path as `/api/calibration/templates/{name}.png`; `if name not in vision.TEMPLATE_NAMES: raise HTTPException(404, "unknown template")`; return `Response(vision.template_path(name).read_bytes(), media_type="image/png", headers={"Cache-Control": "no-store"})`.
- `POST /api/calibration/open-folder`: `folder = home / "calibration"`, `folder.mkdir(parents=True, exist_ok=True)`; then the exact body of `settings_routes.py`'s open-data-folder (501 off win32, `asyncio.to_thread(os.startfile, str(folder))`, 500 on OSError, 204). Do not echo the path in any response.
- `GET /api/instances/{name}/recorder`: read `recorder.json` (defaults when missing or unparseable), add `"flag": (inst / "record.flag").exists()`.
- `POST /api/instances/{name}/recorder` with `class RecorderBody(BaseModel): on: bool`: `on` true -> `inst.mkdir(parents=True, exist_ok=True); (inst / "record.flag").touch()`; false -> `unlink(missing_ok=True)`; return the GET payload.

Register in `app.py`: import `calibration` next to the other routers (alias if `calibration` clashes with a name already imported there, e.g. `from brawlfarm.api import calibration as calibration_routes`) and `app.include_router(calibration_routes.router)`.

- [ ] **Step 4: Run the tests and the suite**

Run: `uv run pytest tests/test_api_calibration.py -q`, `uv run pytest -q`, `uv run ruff check .`
Expected: PASS.

- [ ] **Step 5: Scrub and commit**

```
feat(api): calibration read-outs, template files, recorder switch

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
```

---

### Task 6: The Calibration page

**Files:**
- Create: `brawlfarm/web/src/api/calibration.ts`, `brawlfarm/web/src/calibration/Calibration.tsx`, `FrameOverlay.tsx`, `AnchorTable.tsx`, `OverridesTable.tsx`, `RecorderCard.tsx`, `useCalibration.ts`
- Modify: `brawlfarm/web/src/App.tsx:20-25,85-89`, `brawlfarm/web/src/app/Rail.tsx:13-17`, `brawlfarm/web/src/api/queries.ts:12-27`
- Test: `brawlfarm/web/src/calibration/Calibration.test.tsx`, `FrameOverlay.test.tsx`, `RecorderCard.test.tsx`, `brawlfarm/web/src/app/Rail.test.tsx` (extend if it exists)

**Interfaces:**
- Consumes: Task 5 payloads. Existing: `Thumb`, `Table`, `Segmented`, `Switch`, `Button`, `Chip`, `ErrorBlock`, `toast`, `useInstances`, `queryKeys`, `renderWithProviders`, `stubFetch`, `jsonResponse`, `jpegResponse`, `makeInstance`.
- Produces: route `/calibration`, rail entry "Calibration".

- [ ] **Step 1: Types and fetchers**

```ts
// src/api/calibration.ts
import { request } from "./client"; // read client.ts for the exact helper name used by settings.ts and copy that pattern

export type ConstantGroup = "tap" | "threshold" | "timing";
export type CalibrationConstant = {
  name: string; group: ConstantGroup;
  default: number | [number, number]; value: number | [number, number];
  source: "package" | "calibration.toml";
};
export type CalibrationTemplate = {
  name: string; source: "package" | "override"; width: number; height: number; threshold: number;
};
export type Calibration = {
  file: { present: boolean; changed_since_start: boolean; problems: string[] };
  constants: CalibrationConstant[];
  templates: CalibrationTemplate[];
};
export type Anchor = {
  name: string; threshold: number; score: number; found: boolean; expected: boolean;
  box: { x: number; y: number; w: number; h: number };
};
export type Scores = {
  ts: string; width: number; height: number; state: string; phase: string | null; anchors: Anchor[];
};
export type Recorder = {
  on: boolean; frames: number; bytes: number; session: string | null; path: string | null;
  reason: null | "frame_cap" | "disk_cap"; last_session: string | null; last_frames: number; flag: boolean;
};

export const getCalibration = () => request<Calibration>("/api/calibration");
export const getScores = (name: string) => request<Scores>(`/api/instances/${encodeURIComponent(name)}/calibration/scores`);
export const getRecorder = (name: string) => request<Recorder>(`/api/instances/${encodeURIComponent(name)}/recorder`);
export const setRecorder = (name: string, on: boolean) =>
  request<Recorder>(`/api/instances/${encodeURIComponent(name)}/recorder`, { method: "POST", body: JSON.stringify({ on }) });
export const openCalibrationFolder = () => request<void>("/api/calibration/open-folder", { method: "POST" });
```

Add to `queryKeys`: `calibration: ["calibration"] as const`, `calibrationScores: (name: string) => ["calibration", "scores", name] as const`, `recorder: (name: string) => ["recorder", name] as const`.

- [ ] **Step 2: Write the failing tests**

`Calibration.test.tsx` (use `stubFetch` to answer `/api/instances` with two instances, one running; `/api/calibration` with two constants (PLAY_BUTTON tap default `[1434,830]` value `[1434,826]` source `calibration.toml`; MATCH_THRESHOLD package) and one template; `/api/instances/Pie64/calibration/scores` with anchors `play` found+expected and `matchmaking` expected but not found; `/api/instances/Pie64/recorder` default; preview as `jpegResponse`):

1. renders the heading "Calibration" and the instance chips, first running instance pressed
2. shows the anchor rows with pills Found for play and Drift for matchmaking
3. shows the overrides row for PLAY_BUTTON with "1434, 830" and "1434, 826" and a chip "calibration.toml"
4. shows the problems strip text when `file.problems` is non-empty
5. shows the "changed" warn strip when `changed_since_start` is true
6. scores 404 renders "Start Pie64 to see its frame. Scores appear after the first capture."
7. network error renders `ErrorBlock` and retry refetches
8. Segmented "Taps" hides anchor boxes, "Anchors" hides crosshairs (query the SVG by `data-testid="overlay"` and count `[data-kind="tap"]` / `[data-kind="anchor"]`)
9. "Open calibration folder" posts to `/api/calibration/open-folder`; 501 toasts

`FrameOverlay.test.tsx`: crosshair positions map 1:1 into the 1600x900 viewBox (a tap at `[1434, 826]` renders a `<g data-kind="tap" transform="translate(1434 826)">`); a found anchor gets `stroke="var(--ok)"`, an absent one `stroke-dasharray`.

`RecorderCard.test.tsx`: off state copy; toggling posts `{on: true}` and the switch reflects `flag`; `reason: "frame_cap"` and `"disk_cap"` render the two messages from the brief; on state shows "5 frames" and "1.2 MB".

Rail test: "Calibration" link exists between "Stats" and "Settings" and points to `/calibration`.

- [ ] **Step 3: Run tests to verify they fail**

Run: `pnpm test -- src/calibration src/app/Rail` from `brawlfarm/web`
Expected: FAIL (modules missing).

- [ ] **Step 4: Implement the page**

Follow the brief's section 9. Notes for the implementer:

- `useCalibration.ts` holds the three queries: `useQuery({queryKey: queryKeys.calibration, queryFn: getCalibration, refetchInterval: 10000})`, scores with `refetchInterval: running ? 2000 : false` and `retry: false` (a 404 is the empty state, distinguish by `ApiError.status === 404`), recorder likewise; plus a `useMutation` for `setRecorder` that writes the response into the recorder query cache.
- Instance selection: local `useState<string | null>`; resolve to the first running instance from `useInstances()` else the first instance; chips are `<button type="button" aria-pressed={selected === i.name}>` styled like `StatsToolbar` (copy its classes).
- `FrameOverlay` props: `{instance: string; taps: CalibrationConstant[]; anchors: Anchor[] | undefined; show: "taps" | "anchors" | "both"}`. Wrapper `relative w-full aspect-[16/9] overflow-hidden rounded-md border border-line bg-ground`; `Thumb` fills it (read Thumb's props for `className`/size); the SVG is `absolute inset-0 h-full w-full` with `viewBox="0 0 1600 900"` and `preserveAspectRatio="none"`, `data-testid="overlay"`, `pointer-events-none`. Crosshair: `<g data-kind="tap" transform={`translate(${x} ${y})`}><circle r="7" fill="none" stroke="var(--accent)" strokeWidth="2"/><line x1="-13" x2="13" y1="0" y2="0" stroke="var(--accent)" strokeWidth="2"/><line ... vertical/><text x="10" y="-10" className="font-mono" fontSize="16" fill="var(--accent)">{`${name} ${x},${y}`}</text></g>`. Anchor box: `<g data-kind="anchor"><rect x y width height fill="none" strokeWidth="2" stroke={found ? "var(--ok)" : "var(--bad)"} strokeDasharray={found ? undefined : "8 6"}/><text .../></g>`.
- `AnchorTable`: `Table` from `components/ui/Table.tsx` (read its API). Pill: reuse `StateChip` if it accepts arbitrary tone and label; else a small inline span with `text-[var(--ok)]` etc. "Last seen" via a `useRef<Map<string, string>>` updated on each scores response: found -> "now"; otherwise the stored `HH:MM` or "never".
- `OverridesTable` and `RecorderCard`: as in the brief. `bytes` to MB: `(bytes / 1048576).toFixed(1) + " MB"`.
- Copy in sentence case; the page title is "Calibration"; the hint under the title: "What the workers see. The page reads; calibration.toml and the templates folder write."

- [ ] **Step 5: Typecheck and test**

Run from `brawlfarm/web`: `pnpm typecheck`, `pnpm test`
Expected: PASS, all files.

- [ ] **Step 6: Scrub and commit**

```
feat(web): Calibration page with frame overlay, anchor scores, overrides and recorder

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
```

---

### Task 7: Desktop window and tray icon behind --window

**Files:**
- Create: `brawlfarm/desktop.py`
- Modify: `brawlfarm/__main__.py` (`_parser()` lines 51 to 71, `_serve()` from line 129, `main()` lines 169 to 237), `pyproject.toml:25` (`[dependency-groups]`)
- Test: `tests/test_desktop_flag.py`

**Interfaces:**
- Produces: `desktop.available() -> bool`, `desktop.MISSING_MESSAGE: str`, `desktop.run(url, *, running, quit_cb) -> None`; `--window` flag.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_desktop_flag.py
import argparse

import pytest

from brawlfarm import __main__ as main_mod
from brawlfarm import desktop


def test_parser_has_window_flag():
    ns = main_mod._parser().parse_args(["--window"])
    assert ns.window is True
    assert main_mod._parser().parse_args([]).window is False


def test_available_false_without_extras(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name in {"webview", "pystray", "PIL"}:
            raise ImportError(name)
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert desktop.available() is False


def test_missing_message_names_the_group():
    assert "uv sync --group desktop" in desktop.MISSING_MESSAGE
    assert "browser" in desktop.MISSING_MESSAGE


def test_window_falls_back_to_browser(monkeypatch, capsys):
    monkeypatch.setattr(desktop, "available", lambda: False)
    calls: list[str] = []
    monkeypatch.setattr(main_mod, "_run_browser_mode", lambda args: calls.append("browser"))
    monkeypatch.setattr(main_mod, "_run_window_mode", lambda args: calls.append("window"))
    main_mod._dispatch(argparse.Namespace(window=True))
    assert calls == ["browser"]
    assert desktop.MISSING_MESSAGE.splitlines()[0] in capsys.readouterr().err


def test_window_mode_used_when_available(monkeypatch):
    monkeypatch.setattr(desktop, "available", lambda: True)
    calls: list[str] = []
    monkeypatch.setattr(main_mod, "_run_browser_mode", lambda args: calls.append("browser"))
    monkeypatch.setattr(main_mod, "_run_window_mode", lambda args: calls.append("window"))
    main_mod._dispatch(argparse.Namespace(window=True))
    assert calls == ["window"]
```

Read `__main__.py` `main()` first. The tests assume `main()` is refactored so that after argument parsing and the `--once`/`--version` early exits, it calls `_dispatch(args)`, which chooses `_run_window_mode(args)` when `args.window and desktop.available()`, else prints `MISSING_MESSAGE` to stderr when `args.window` and calls `_run_browser_mode(args)`. `_run_browser_mode` is the current serve path; if `main()` is structured so that this split is awkward, keep the same three names and make the test's `Namespace` carry whatever extra attributes `_dispatch` reads (say which in the report).

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_desktop_flag.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'brawlfarm.desktop'`

- [ ] **Step 3: Dependency group**

In `pyproject.toml` under `[dependency-groups]` add:

```toml
desktop = ["pywebview>=5.3", "pystray>=0.19", "pillow>=10"]
```

Run `uv lock` (the lock file changes; commit it). Do not run `uv sync --group desktop` in this task; the controller does that for the manual pass.

- [ ] **Step 4: Implement `desktop.py`**

```python
"""Optional desktop window and tray icon (uv sync --group desktop).

Imports of pywebview, pystray and Pillow are lazy so the base install never
needs them. Quit does what Ctrl+C does: the server and supervisor stop,
worker processes keep running.
"""

from __future__ import annotations

import sys
import threading
from collections.abc import Callable

MISSING_MESSAGE = (
    "The desktop window needs the optional extras.\n"
    "Run: uv sync --group desktop\n"
    "Opening in the browser instead."
)

ACCENT = (0xE0, 0xB8, 0x4B, 0xFF)


def available() -> bool:
    try:
        import PIL  # noqa: F401
        import pystray  # noqa: F401
        import webview  # noqa: F401
    except ImportError:
        return False
    return True


def _icon_image():
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle((6, 6, 58, 58), radius=14, fill=ACCENT)
    return img


def run(url: str, *, running: Callable[[], int], quit_cb: Callable[[], None]) -> None:
    import pystray
    import webview

    window = webview.create_window("brawlfarm", url, width=1280, height=800)
    warned = {"done": False}
    icon: pystray.Icon | None = None

    def on_closing() -> bool:
        window.hide()
        if icon is not None and not warned["done"]:
            warned["done"] = True
            try:
                icon.notify("brawlfarm is still running. Open it again from the tray icon.")
            except Exception:  # noqa: BLE001  (notification support varies)
                pass
        return False  # cancel the close

    def show(icon_, item) -> None:
        window.show()

    def quit_(icon_, item) -> None:
        quit_cb()
        icon_.stop()
        window.destroy()

    def title(item) -> str:
        return f"brawlfarm, {running()} running"

    menu = pystray.Menu(
        pystray.MenuItem(title, None, enabled=False),
        pystray.MenuItem("Open panel", show, default=True),
        pystray.MenuItem("Quit", quit_),
    )
    icon = pystray.Icon("brawlfarm", _icon_image(), "brawlfarm", menu)
    window.events.closing += on_closing
    threading.Thread(target=icon.run, name="tray", daemon=True).start()
    webview.start()
```

Check the pywebview 5 API for `window.events.closing` (returning False cancels) and `webview.start()` blocking; check pystray's `Icon.run` in a thread on Windows. Use context7 for both if unsure.

- [ ] **Step 5: Wire `__main__.py`**

Add `parser.add_argument("--window", action="store_true", help="Open the panel in a desktop window with a tray icon (needs uv sync --group desktop).")`.

Refactor `main()` into `_dispatch(args)`, `_run_browser_mode(args)` (the existing behavior verbatim), `_run_window_mode(args)`:

```python
def _dispatch(args: argparse.Namespace) -> None:
    from brawlfarm import desktop

    if getattr(args, "window", False):
        if desktop.available():
            _run_window_mode(args)
            return
        print(desktop.MISSING_MESSAGE, file=sys.stderr)
    _run_browser_mode(args)
```

`_run_window_mode`: build the same supervisor and server as the browser path but with `open_browser=False`; create `stop = asyncio.Event()` inside the served coroutine; run `asyncio.run(_serve_until(stop, ...))` in a `threading.Thread(daemon=True)`; capture the loop with `loop_holder` so `quit_cb` does `loop.call_soon_threadsafe(stop.set)`; `_serve_until` starts the server task, awaits `stop.wait()`, then performs the same shutdown the Ctrl+C path performs (`server.should_exit = True`, await the serve task, stop the supervisor). `running` is `lambda: sum(1 for v in sup.views() if v.pid)` (read `InstanceView` for the running indicator). Then `desktop.run(f"http://127.0.0.1:{port}/", running=..., quit_cb=...)`, and after it returns, `thread.join(timeout=10)`.

Read `_serve()` fully before touching it; the simplest correct refactor is to add an optional `stop: asyncio.Event | None` parameter that, when given, replaces the "wait for Ctrl+C" wait.

- [ ] **Step 6: Run the tests and the suite**

Run: `uv run pytest tests/test_desktop_flag.py -q`, `uv run pytest -q`, `uv run ruff check .`, and `uv run brawlfarm --version` still works.
Expected: PASS.

- [ ] **Step 7: Scrub and commit**

```
feat(desktop): --window opens the panel in a desktop window with a tray icon

Optional extras in the desktop dependency group. Without them the flag
prints a hint and the browser opens as before.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
```

---

### Task 8: Docs

**Files:**
- Create: `docs/calibration.md`
- Modify: `README.md` (new "Calibration" section after the existing feature sections, plus one line under whatever "Running" section mentions the browser), `docs/setup.md` (one paragraph on the desktop extras), `CHANGELOG.md` if the repo has one (read the tree)

**Interfaces:** none.

- [ ] **Step 1: Write `docs/calibration.md`**

Sections: "What the page shows" (frame with taps and anchors, anchor table with Found / Drift / Absent, overrides table); "Where the folder is" (`%LOCALAPPDATA%\brawlfarm\calibration\` by default, or `<home>/calibration` under `--home`); "calibration.toml" (format, the two examples from the brief, unknown key and wrong type behavior, restart rule); "Template overrides" (`templates/<name>.png`, the 13 names, same size not required, takes effect on the next capture without restart); "Recording frames" (the switch, folder layout `recordings/<instance>/<yyyymmdd-hhmmss>/`, `NNNN-state.jpg`, `labels.jsonl` line fields, 1 frame per second or on state change, the two caps, "the recorder never deletes"); "Safety" (the page reads, files write, no route writes a coordinate; the calibration PR rule from CONTRIBUTING). Plain prose, sentence case headings, no em-dashes, no emoji. Never write an absolute path under a user's home; use `%LOCALAPPDATA%`.

- [ ] **Step 2: README and setup**

README "Calibration" section: five short paragraphs mirroring the doc's sections at one sentence each, then a link to `docs/calibration.md`. Add to the run instructions: `brawlfarm --window` opens a desktop window instead of the browser when the desktop extras are installed (`uv sync --group desktop`). `docs/setup.md`: one paragraph with the same two commands.

- [ ] **Step 3: Scrub and commit**

Run `uv run python tools/scrub_check.py` (expect `0 hit(s)`).

```
docs: calibration how-to, README section, desktop extras in setup

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
```

---

## After the tasks (controller)

1. Whole-branch gate: `pnpm typecheck`, `pnpm test`, `uv run pytest -q`, `uv run ruff check .`, scrub `0 hit(s)`.
2. Corpus check for Task 3 with the spike script against the worktree.
3. Live pass against the real install per the brief's section 12; nothing from it goes into git.
4. Manual desktop pass: `uv sync --group desktop` in the worktree, `uv run brawlfarm --window --no-launch`, check window, hide-on-close balloon, tray menu, Quit.
5. Push, PR against main with the standard body; the body states that this is the owner-approved calibration PR and lists the one template and two constants it changes.
6. After merge: board row in `docs/PLAN.md`.
