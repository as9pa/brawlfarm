# Phase 1: Repo and core. Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the `brawlfarm` repository with the farm core ported from the legacy checkout, its tests green in CI, and a scrub check that fails the build on any legacy account identifier.

**Architecture:** The legacy `bot/` package and `config.py` become `brawlfarm/core/` with imports rewritten and user identity removed (instances are injected at runtime, the player tag default is empty, paths resolve from `BRAWLFARM_HOME`). Tests that never touched Discord are ported with the same import rewrite; the Discord suite is dropped. A hash-based scrub script guards the repo without containing the identifiers it forbids.

**Tech Stack:** Python 3.13, uv, hatchling, pytest, ruff, GitHub Actions on `windows-latest`. Runtime deps unchanged from legacy: opencv-python, numpy, requests, python-dotenv, rapidocr-onnxruntime, plus pandas (used by `core/stats.py`).

**Spec:** `docs/superpowers/specs/2026-09-10-brawlfarm-design.md` (sections 4, 5, 9, 10, 11).

## Global Constraints

- Python `>=3.13`; every command runs through `uv run`.
- The legacy checkout is the sibling folder `../bsutil` (read-only; never modify it). Refer to it only by that relative path. Never write its absolute path, its account nicknames, or its player tags into any file in this repo, including this plan, commit messages and PR text.
- The scrub check (`tools/scrub_check.py`) must pass before every commit from Task 4 on.
- No file in this repo may `import discord` or `from discord`.
- Instance names match `[A-Za-z0-9_-]{1,32}`. Never build a shell command from user text.
- Safety rails in spec section 9 are untouched by this phase: do not edit the never-tap logic, the verify-then-act flow, the 1600 x 900 assertion, or the kill-by-PID rule while porting.
- Commit messages are conventional (`feat:`, `chore:`, `test:`, `docs:`) and explain why. Git identity in this folder must be the personal account (`git config user.name` prints `as9pa`) before every commit.
- Windows shell: use bash (Git Bash) commands as written; paths with forward slashes.

---

### Task 1: Bootstrap the repository

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `.python-version`, `LICENSE`, `README.md`, `docs/PLAN.md`, `.github/workflows/ci.yml`, `brawlfarm/__init__.py`, `brawlfarm/__main__.py`, `brawlfarm/core/__init__.py`, `tests/__init__.py`
- Already present (commit them): `docs/superpowers/specs/2026-09-10-brawlfarm-design.md`, `docs/superpowers/plans/2026-09-10-phase-1-repo-and-core.md`

**Interfaces:**
- Produces: the `brawlfarm` console script (`brawlfarm.__main__:main`), the package roots `brawlfarm/` and `brawlfarm/core/`, the dev group with `pytest` and `ruff`, and the CI job later tasks extend.

- [ ] **Step 1: Initialise git and confirm identity**

Run from `C:/Users/<you>/projects/brawlfarm` (the folder already contains `docs/`):

```bash
git init -b main
git config user.name && git config user.email
```

Expected: `as9pa` and the personal email. If it prints the work identity, stop and report.

- [ ] **Step 2: Write `.gitignore` and `.python-version`**

```gitignore
# python
.venv/
__pycache__/
*.pyc
.pytest_cache/
.ruff_cache/
dist/
build/
*.egg-info/
# local runtime state (never commit account data)
data/
captures/
logs/
.env
*.log
# agent worktrees live inside the repo
.worktrees/
# web (phase 4)
node_modules/
brawlfarm/web/dist/
```

`.python-version`:

```
3.13
```

- [ ] **Step 3: Write `pyproject.toml`**

```toml
[project]
name = "brawlfarm"
version = "0.1.0"
description = "Open-source Brawl Stars trophy farmer for BlueStacks, with a local control panel"
readme = "README.md"
requires-python = ">=3.13"
license = "MIT"
dependencies = [
  "opencv-python>=4.10",
  "numpy>=2.0",
  "requests>=2.32",
  "python-dotenv>=1.0",
  "rapidocr-onnxruntime>=1.3",
  "pandas>=2.2",
]

[project.scripts]
brawlfarm = "brawlfarm.__main__:main"

[dependency-groups]
dev = ["pytest>=8.3", "ruff>=0.12"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["brawlfarm"]

[tool.ruff]
target-version = "py313"
line-length = 100
extend-exclude = ["docs"]

[tool.ruff.lint]
select = ["E", "F", "W", "I"]
ignore = ["E501"]

[tool.pytest.ini_options]
testpaths = ["tests"]
cache_dir = ".pytest_cache"
pythonpath = ["."]
```

- [ ] **Step 4: Write the package stubs**

`brawlfarm/__init__.py`:

```python
"""brawlfarm: Brawl Stars trophy farmer for BlueStacks with a local control panel."""

__version__ = "0.1.0"
```

`brawlfarm/core/__init__.py`:

```python
"""The farm core: controller, vision, ADB, scheduler, farm plan and data logging."""
```

`brawlfarm/__main__.py`:

```python
"""Console entry point. The control panel arrives in phase 3; for now this reports the version."""

from __future__ import annotations

import sys

from brawlfarm import __version__


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args and args[0] in {"-V", "--version"}:
        print(f"brawlfarm {__version__}")
        return 0
    print(f"brawlfarm {__version__}: the control panel is not built yet. Run the worker with:")
    print("  uv run python -m brawlfarm.worker --help")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

`tests/__init__.py`: empty file.

- [ ] **Step 5: Write `LICENSE` (MIT)**

```
MIT License

Copyright (c) 2026 as9pa

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 6: Write the skeleton `README.md`**

```markdown
# brawlfarm

An open-source Brawl Stars trophy farmer for BlueStacks on Windows, with a local control panel in your browser.

Status: under construction. Phase 1 of 8 (repo and core). The control panel, setup wizard and stats screens arrive in later phases; see `docs/PLAN.md`.

## What it does

- Farms Trio Showdown on its own: queue, play, results, back to the menu, repeat.
- Survives interruptions: rewards, popups, rank-ups, disconnects, crashes, freezes, team invites.
- Two farm modes: ladder (raise the whole roster in 100-trophy tiers) and prestige (finish one brawler to 1000 at a time), plus an optional maxed fallback.
- An anti-ban scheduler that plays human-shaped sessions with breaks, on by default.
- Runs several BlueStacks instances at once, one worker per instance.

## Safety rails

These are absolute and are enforced in code and in review:

- Never taps ACCEPT on a team invite, GET or Upgrade, EQUIP NOW, any shop buy button, the pass VAULT, or anything priced in gems. Never blind-taps in the shop.
- Every navigation verifies the screen before acting and bails to the menu on a failed check, so stale coordinates degrade to logged no-ops.
- One worker per instance. Processes are stopped by the PID recorded in that instance's status file, never by name.
- No AI in the runtime loop: deterministic OpenCV template matching and OCR.

## Requirements

Windows 11, BlueStacks 5 with Android Debug Bridge enabled, an instance display of 1600 x 900 at DPI 240, Python 3.13 and [uv](https://docs.astral.sh/uv/). Setup steps arrive with the wizard in phase 5 and in `docs/setup.md` in phase 7.

## Development

```
uv sync --group dev
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run python tools/scrub_check.py
```

## Legal

brawlfarm is not affiliated with or endorsed by Supercell. Brawl Stars and its art belong to Supercell; brawler icons are fetched at runtime from the Brawlify CDN and cached locally under Supercell's fan content policy. Automating the game may violate its terms of service; use at your own risk. MIT licensed.
```

- [ ] **Step 7: Write `docs/PLAN.md`**

```markdown
# brawlfarm board

Living board. Finished work moves to the top with its proof.

## Done

(nothing yet)

## In flight

- Phase 1: repo and core. Plan: `docs/superpowers/plans/2026-09-10-phase-1-repo-and-core.md`.

## Queue (v1)

2. Settings and supervisor
3. API and events
4. UI shell, Fleet and Instance screens
5. Setup wizard and Settings screens
6. Stats with brawler icons
7. Docs and publish; archive the legacy repo

## After v1

8. Calibration page, then recalibration for the current game version; desktop window and tray icon; labeled frame recorder.

## On hold (owner decision)

- Quest-aware brawler choice.
- Opt-in auto-upgrade.

Design: `docs/superpowers/specs/2026-09-10-brawlfarm-design.md`.
```

- [ ] **Step 8: Write the CI workflow**

`.github/workflows/ci.yml`:

```yaml
name: ci

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
        with:
          python-version: "3.13"
      - run: uv sync --group dev
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run pytest -q
```

(Task 4 adds the scrub step.)

- [ ] **Step 9: Sync, smoke the entry point, run an empty test session**

```bash
uv sync --group dev
uv run brawlfarm --version
uv run ruff check . && uv run ruff format --check .
uv run pytest -q
```

Expected: `brawlfarm 0.1.0`; ruff clean; pytest reports "no tests ran" with exit code 5, which is fine for this step only.

- [ ] **Step 10: Commit and create the private GitHub repo**

```bash
git add -A
git commit -m "chore: bootstrap brawlfarm (uv project, license, spec, plan, CI)

Open-source successor to the private legacy repo. Private until phase 7."
gh auth status
gh repo create as9pa/brawlfarm --private --source . --remote origin --push --description "Brawl Stars trophy farmer for BlueStacks with a local control panel"
```

Expected: `gh auth status` shows `as9pa` as the active account before `gh repo create` runs; the push succeeds and the CI run starts. Report the run URL.

---

### Task 2: Port the farm core

**Files:**
- Create: `brawlfarm/core/<module>.py` for each of the 21 legacy modules in `../bsutil/bot/` (adb, api, brawlers, controller, datalog, events, farmplan, jsonio, match_vision, notify, onboarding, quests, recalib, rewards, scheduler, settings, states, stats, status, vision) plus `brawlfarm/core/config.py` (from `../bsutil/config.py`) and `brawlfarm/core/janitor.py` (from `../bsutil/tools/data_janitor.py`)
- Create: `brawlfarm/core/templates/*.png` (the 13 anchor templates from `../bsutil/templates/`)
- Create: `brawlfarm/worker.py` (from `../bsutil/run.py`)
- Create: `tests/test_core_imports.py`

**Interfaces:**
- Produces: `brawlfarm.core.config` with `HOME_DIR`, `DATA_DIR`, `CAPTURES_DIR`, `TEMPLATES_DIR`, `INSTANCES` (empty dict at import) and `set_instances(mapping: dict[str, dict]) -> None`; `brawlfarm.core.onboarding.farm_ports() -> frozenset[str]`; `python -m brawlfarm.worker` with the legacy CLI flags (`--max-games`, `--max-minutes`, `--debug-shots`, `--select-brawler`, `--dnd`, `--startup-all`).

- [ ] **Step 1: Write the failing import test**

`tests/test_core_imports.py`:

```python
"""Every core module imports with no .env, no BRAWL_* env, and an empty home directory."""

from __future__ import annotations

import importlib
import os
import subprocess
import sys

import pytest

MODULES = [
    "adb", "api", "brawlers", "config", "controller", "datalog", "events", "farmplan",
    "janitor", "jsonio", "match_vision", "notify", "onboarding", "quests", "recalib",
    "rewards", "scheduler", "settings", "states", "stats", "status", "vision",
]


@pytest.mark.parametrize("name", MODULES)
def test_module_imports(name: str) -> None:
    importlib.import_module(f"brawlfarm.core.{name}")


def test_config_has_no_instances_or_tag_at_import(tmp_path) -> None:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("BRAWL_", "DISCORD_"))}
    env["BRAWLFARM_HOME"] = str(tmp_path)
    code = (
        "from brawlfarm.core import config; "
        "assert config.INSTANCES == {}, config.INSTANCES; "
        "assert config.PLAYER_TAG == '', config.PLAYER_TAG; "
        "assert config.HOME_DIR.exists(); "
        "assert config.TEMPLATES_DIR.joinpath('play.png').exists(), config.TEMPLATES_DIR"
    )
    result = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_set_instances_feeds_scheduler_and_onboarding() -> None:
    from brawlfarm.core import config, onboarding

    config.set_instances({"Pie64": {"port": "5555", "tag": "", "data": "data/Pie64"}})
    try:
        assert "5555" in onboarding.farm_ports()
        assert config.INSTANCES["Pie64"]["data"] == "data/Pie64"
    finally:
        config.set_instances({})


def test_worker_help_runs() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "brawlfarm.worker", "--help"], capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "--max-games" in result.stdout
```

- [ ] **Step 2: Run it to confirm it fails**

```bash
uv run pytest tests/test_core_imports.py -q
```

Expected: every test fails with `ModuleNotFoundError: No module named 'brawlfarm.core.adb'` (or similar).

- [ ] **Step 3: Copy the modules and templates**

```bash
cp ../bsutil/bot/*.py brawlfarm/core/
rm -f brawlfarm/core/__init__.py && printf '"""The farm core: controller, vision, ADB, scheduler, farm plan and data logging."""\n' > brawlfarm/core/__init__.py
cp ../bsutil/config.py brawlfarm/core/config.py
cp ../bsutil/tools/data_janitor.py brawlfarm/core/janitor.py
mkdir -p brawlfarm/core/templates && cp ../bsutil/templates/*.png brawlfarm/core/templates/
cp ../bsutil/run.py brawlfarm/worker.py
```

Do not copy `__pycache__`, anything under `../bsutil/discord_bot/`, or any other `tools/` script.

- [ ] **Step 4: Rewrite imports mechanically**

Apply to every `.py` under `brawlfarm/` (including `worker.py` and `core/janitor.py`):

| Legacy form | New form |
|---|---|
| `import config` | `from brawlfarm.core import config` |
| `from config import X` | `from brawlfarm.core.config import X` |
| `from bot.X import Y` | `from brawlfarm.core.X import Y` |
| `from bot import X` | `from brawlfarm.core import X` |
| `import bot.X as Y` | `import brawlfarm.core.X as Y` |

Use a script so nothing is missed (indented, function-local imports included, for example the `ApiClient` import inside `core/events.py`):

```bash
uv run python - <<'PY'
import re, pathlib
rules = [
    (re.compile(r"^(\s*)import config\s*$", re.M), r"\1from brawlfarm.core import config"),
    (re.compile(r"^(\s*)from config import ", re.M), r"\1from brawlfarm.core.config import "),
    (re.compile(r"^(\s*)from bot\.", re.M), r"\1from brawlfarm.core."),
    (re.compile(r"^(\s*)from bot import ", re.M), r"\1from brawlfarm.core import "),
    (re.compile(r"^(\s*)import bot\.", re.M), r"\1import brawlfarm.core."),
]
for p in pathlib.Path("brawlfarm").rglob("*.py"):
    s = p.read_text(encoding="utf-8"); t = s
    for rx, rep in rules: t = rx.sub(rep, t)
    if t != s: p.write_text(t, encoding="utf-8"); print("rewrote", p)
PY
grep -rnE "^\s*(from|import) (bot|config)\b" brawlfarm/ && echo "LEFTOVERS ABOVE" || echo "no leftovers"
```

- [ ] **Step 5: Edit `brawlfarm/core/config.py`: paths, identity, dotenv**

Replace the paths block (legacy lines 17 to 34) with:

```python
# --- Paths -------------------------------------------------------------------
# HOME_DIR is where runtime state lives (data, captures, .env). The control panel sets
# BRAWLFARM_HOME to the user data directory; a bare checkout defaults to the current
# working directory so `uv run python -m brawlfarm.worker` behaves like the legacy layout.
HOME_DIR = Path(os.environ.get("BRAWLFARM_HOME", "") or Path.cwd()).resolve()
PACKAGE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = PACKAGE_DIR / "templates"
CAPTURES_DIR = HOME_DIR / "captures"
# Data dir is env-overridable so concurrent workers on different instances write to
# separate folders (one shared games.csv would race and corrupt). Pairs with
# BRAWL_ADB_PORT and BRAWL_PLAYER_TAG for multi-instance runs.
DATA_DIR = HOME_DIR / os.environ.get("BRAWL_DATA_DIR", "data")

# BlueStacks ships its own adb; use it directly. Overridable for non-default installs.
ADB_PATH = os.environ.get("BRAWL_ADB_PATH", r"C:\Program Files\BlueStacks_nxt\HD-Adb.exe")

# Brawl Stars Android package (for relaunch / freeze recovery).
BS_PACKAGE = "com.supercell.brawlstars"

load_dotenv(HOME_DIR / ".env")
```

Delete `DOCS_DIR` (nothing in the core uses it) and every later reference to `PROJECT_ROOT`: in `core/events.py` and `core/scheduler.py` the `_root()` helpers fall back to `config.PROJECT_ROOT`; change both to `config.HOME_DIR`.

Replace the farm instances block (legacy lines 37 to 49) with:

```python
# --- Farm instances ------------------------------------------------------------
# Populated at runtime by the supervisor from the user's settings (phase 2). Shape per
# entry: {"port": "5555", "tag": "#XXXXXXX" or "", "data": "data/<name>"}. The module
# ships EMPTY so the package never carries anyone's account identifiers.
INSTANCES: dict[str, dict[str, str]] = {}


def set_instances(mapping: dict[str, dict[str, str]]) -> None:
    """Replace the runtime instance table in place (callers hold references to the dict)."""
    INSTANCES.clear()
    INSTANCES.update({name: dict(entry) for name, entry in mapping.items()})
```

Change the player tag default (legacy line 109) to an empty string:

```python
PLAYER_TAG = os.environ.get("BRAWL_PLAYER_TAG", "")
```

Then check how `core/api.py` and `core/datalog.py` behave with an empty tag: if a request would be built with an empty tag, make the client skip the call and return `None`/an empty list (look for where `PLAYER_TAG` is used, guard with `if not config.PLAYER_TAG: return ...`, and keep the existing behaviour for a set tag).

- [ ] **Step 6: Scrub comments in `config.py` and the core**

Rewrite every comment that names a legacy account. Known lines in the legacy file (line numbers refer to `../bsutil/config.py`): 53, 230 to 234, 248, 269 to 271, 302 to 303, 377, 405, 461, 488, 509. Replace nicknames with neutral labels ("account A / B / C", "a near-maxed account", "a fresh account") and the BlueStacks instance-name comment on line 53 with a generic note ("ports come from bluestacks.conf, one per instance, usually 5555, 5565, 5575 ..."). Keep the measured numbers; they are calibration facts, not identifiers.

Then sweep the rest of the core for Discord wording that describes the removed bot and reword it to the control panel (for example in `core/adb.py` line 86, `core/controller.py` lines 125, 274, 798, 837, 1217, 1358, 1417, `core/datalog.py` lines 28 to 50, `core/scheduler.py` lines 8, 35, 39, 691, 947, 956). `core/notify.py` keeps its webhook backend; rename nothing there, only reword comments that call it "the Discord bot".

Finally make `onboarding.farm_ports()` lazy. Legacy lines 40 to 42 compute a frozenset at import time from `config.INSTANCES`, which is now empty at import. Replace with:

```python
def farm_ports() -> frozenset[str]:
    """Ports of registered farm instances, read at call time so runtime registration counts."""
    return frozenset(inst["port"] for inst in config.INSTANCES.values())
```

and update every use of `FARM_PORTS` in `core/onboarding.py` to call `farm_ports()`.

- [ ] **Step 7: Port `worker.py` and `janitor.py` names**

In `brawlfarm/worker.py` keep the argparse flags exactly; change the module docstring to say it is the per-instance worker started by the supervisor; make sure it ends with:

```python
if __name__ == "__main__":
    raise SystemExit(main())
```

(wrap the existing top-level code in `def main() -> int:` if it is not already). In `brawlfarm/core/janitor.py` keep the CLI (it will be called by the supervisor in phase 2); only the imports change.

- [ ] **Step 8: Run the import test until green**

```bash
uv run pytest tests/test_core_imports.py -q
```

Expected: all pass. Typical failures to fix on the way: a module that still references `PROJECT_ROOT` or `FARM_PORTS`; `pandas` missing (it is in `pyproject.toml`; run `uv sync --group dev` again).

- [ ] **Step 9: Commit**

```bash
git checkout -b phase-1/core-port
git add brawlfarm tests/test_core_imports.py
git commit -m "feat(core): port the farm core from the legacy bot package

Imports rewritten to brawlfarm.core, paths resolve from BRAWLFARM_HOME, the
instance table is injected at runtime and the player tag default is empty, so
the package carries no account identity."
```

---

### Task 3: Port the farm tests

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/<name>.py` for each of these legacy files from `../bsutil/tests/`: test_api, test_bush, test_bush_controller, test_ci_guard, test_controller_reselect, test_data_janitor, test_datalog_steps, test_events, test_farmplan, test_farmplan_optimal, test_farmplan_winrate, test_farmplan_winrate_v2, test_match_vision, test_network_stuck, test_never_tap_rail, test_onboarding_rails, test_recalib, test_scenarios_r8, test_scheduler, test_settings_dnd, test_stop_etiquette, test_stop_override_disabled, test_wrong_mode
- Create: `tests/fixtures/<renamed>.png` only for fixtures those tests actually load
- Do NOT port: `test_set_token.py` (edits a legacy `.env` tool that no longer exists), the legacy `conftest.py`, or any test that references `discord_bot`

**Interfaces:**
- Consumes: `brawlfarm.core.*` from Task 2, `config.set_instances`, `onboarding.farm_ports`.
- Produces: a green `uv run pytest` and a `conftest.py` that isolates `BRAWLFARM_HOME` per test.

- [ ] **Step 1: Write the new `tests/conftest.py`**

```python
"""Suite-wide isolation: every test gets an empty home directory and no farm env."""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    for key in list(os.environ):
        if key.startswith(("BRAWL_", "DISCORD_")):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("BRAWLFARM_HOME", str(tmp_path))
    from brawlfarm.core import config

    monkeypatch.setattr(config, "HOME_DIR", tmp_path)
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(config, "CAPTURES_DIR", tmp_path / "captures")
    config.set_instances({})
    yield
    config.set_instances({})
```

- [ ] **Step 2: Copy the test files and rewrite imports**

```bash
for t in test_api test_bush test_bush_controller test_ci_guard test_controller_reselect test_data_janitor test_datalog_steps test_events test_farmplan test_farmplan_optimal test_farmplan_winrate test_farmplan_winrate_v2 test_match_vision test_network_stuck test_never_tap_rail test_onboarding_rails test_recalib test_scenarios_r8 test_scheduler test_settings_dnd test_stop_etiquette test_stop_override_disabled test_wrong_mode; do cp "../bsutil/tests/$t.py" tests/; done
```

Run the same rewrite script as Task 2 Step 4 with `pathlib.Path("tests")` instead of `brawlfarm`, and additionally:

- delete every `sys.path.insert(...)` line and the now-unused `import sys` / `import os` it needed (the package is installed editable by `uv sync`);
- in `tests/test_data_janitor.py` replace references to `tools.data_janitor` / `data_janitor` with `brawlfarm.core.janitor`;
- in `tests/test_api.py` replace the hardcoded tag constant on legacy line 19 with a made-up tag that uses the game's tag alphabet, for example `MY_TAG = "#2P0YLQ9"`;
- in `tests/test_ci_guard.py` replace the copy-config-to-temp-dir approach with a subprocess that runs `python -c "from brawlfarm.core import config"` with `BRAWL_*` and `DISCORD_*` stripped and `BRAWLFARM_HOME` set to an empty temp dir (this duplicates the guarantee in `tests/test_core_imports.py`; keep the ported file because its docstring documents the rail, and trim it to the one subprocess assertion);
- anywhere a test monkeypatches `config.INSTANCES` by assignment, change it to `config.set_instances({...})`, and anywhere it reads `onboarding.FARM_PORTS`, call `onboarding.farm_ports()`.

- [ ] **Step 3: Port only the fixtures that tests load**

```bash
grep -n "fixtures" tests/test_match_vision.py tests/test_scenarios_r8.py
```

For each fixture filename those two tests reference, copy it from `../bsutil/tests/fixtures/`. If a filename contains a legacy account nickname, rename it on copy to the same name with the nickname replaced by `a` or `b` (one letter per legacy account, consistently), and update the test to the new name. Do not copy any other fixture.

- [ ] **Step 4: Run the suite and fix ports until green**

```bash
uv run pytest -q
```

Expected: all pass. Expected kinds of fixes: a test that assumed `config.DATA_DIR` sits inside a repo checkout (use the `tmp_path` home from `conftest`); a test that wrote into `data/` relative to the cwd (point it at `config.DATA_DIR`); a test in `test_scheduler.py` that seeds `config.INSTANCES` directly. Do not weaken assertions to get green; if a test encodes legacy-only behaviour (Discord, `.env` editing), delete that test function and say so in the commit message.

- [ ] **Step 5: Commit**

```bash
git add tests
git commit -m "test: port the farm-core suite, drop the Discord suite

conftest no longer imports the Discord package; every test runs against an
empty BRAWLFARM_HOME. Fixtures are ported only where a test loads them."
```

---

### Task 4: Scrub check

**Files:**
- Create: `tools/scrub_check.py`, `tests/test_scrub.py`
- Modify: `.github/workflows/ci.yml` (add the scrub step)

**Interfaces:**
- Produces: `scrub_check.scan(root: Path, extra_hashes: frozenset[str] = frozenset()) -> list[str]` returning `"<relative path>:<line>: <reason>"` strings, and a CLI that exits 1 on any hit.

- [ ] **Step 1: Write the failing tests**

`tests/test_scrub.py`:

```python
"""The scrub check keeps legacy account identifiers and Discord imports out of the repo."""

from __future__ import annotations

import hashlib
from pathlib import Path

from tools import scrub_check

REPO = Path(__file__).resolve().parents[1]


def _h(token: str) -> str:
    return hashlib.sha256(token.lower().encode()).hexdigest()


def test_repo_is_clean() -> None:
    assert scrub_check.scan(REPO) == []


def test_detects_forbidden_token_in_text(tmp_path: Path) -> None:
    (tmp_path / "note.md").write_text("the account forbiddenword was here\n", encoding="utf-8")
    hits = scrub_check.scan(tmp_path, extra_hashes=frozenset({_h("forbiddenword")}))
    assert hits == ["note.md:1: forbidden identifier"]


def test_detects_forbidden_token_in_filename(tmp_path: Path) -> None:
    (tmp_path / "shot_forbiddenword_1.png").write_bytes(b"\x89PNG")
    hits = scrub_check.scan(tmp_path, extra_hashes=frozenset({_h("forbiddenword")}))
    assert hits == ["shot_forbiddenword_1.png:0: forbidden identifier in filename"]


def test_detects_discord_import(tmp_path: Path) -> None:
    (tmp_path / "x.py").write_text("import os\nfrom discord import app_commands\n", encoding="utf-8")
    assert scrub_check.scan(tmp_path) == ["x.py:2: discord import"]


def test_ignores_token_with_hash_prefix_only(tmp_path: Path) -> None:
    (tmp_path / "ok.md").write_text("forbiddenwords are longer tokens\n", encoding="utf-8")
    assert scrub_check.scan(tmp_path, extra_hashes=frozenset({_h("forbiddenword")})) == []
```

Also create `tools/__init__.py` (empty) so the test can import the module.

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_scrub.py -q
```

Expected: `ModuleNotFoundError: No module named 'tools.scrub_check'`.

- [ ] **Step 3: Write `tools/scrub_check.py`**

```python
"""Fail if the repo contains a legacy account identifier or a Discord import.

The identifiers themselves never appear here: the check compares SHA-256 hashes of
lowercase tokens against a fixed set, so publishing this file reveals nothing.
Run: uv run python tools/scrub_check.py  (exit 1 on any hit)
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from pathlib import Path

# sha256 of lowercase tokens: three legacy player tags (with and without the leading
# '#'), three legacy account nicknames, and the legacy machine's user name.
FORBIDDEN_SHA256: frozenset[str] = frozenset(
    {
        "e571ad0b63e2aff44a1557adabe80093cdc3d3e3d6ca45dc25abdc58ecf688af",
        "6a51aa76773df41d7dc0ba5a4b37f4a567b363d9be317edbd21b2bbfe02f6ec8",
        "9bd320a413eed31d21577f0e3b8f904547bf155468b6b791b70c8c2430dad392",
        "8e81eaa8a6719ec6cc1cc39ab93bfd8b391d1d9011b5e7ac54a8525e090bb330",
        "a64654a48b4cb2c8d5e45dfcb2df116a0089a932a6593c0818f7aeff64b4d3b4",
        "9e4807c28c77922e03edb58914dd2e258aa8bd817ca08c31db83a8269d416d87",
        "16d1551686f4cb08f88335d39d505708f5618bd8762c62fba9f9d1d3f3bdb850",
        "7fb26a8732f70c7392214b9056c2cd60f5b2d8a6e64d2356ae396297fd750b4a",
        "bc98bb50e8094b2ac3ceb90ba2512587c0513cd294a07efcfdcf467198da6266",
        "7764735c5d4d88ae3ef1c0d6c0a5769e4187c341895db19a82ba7d4e17b8c914",
    }
)

TEXT_SUFFIXES = {
    ".py", ".md", ".toml", ".yml", ".yaml", ".txt", ".json", ".ps1", ".cfg", ".ini",
    ".html", ".css", ".ts", ".tsx", ".js", ".jsx", ".csv", ".env", ".example",
}
SKIP_DIRS = {".git", ".venv", "node_modules", ".pytest_cache", ".ruff_cache", "dist", "build", ".worktrees"}
TOKEN_RE = re.compile(r"#?[A-Za-z0-9]+")
DISCORD_IMPORT_RE = re.compile(r"^\s*(?:import|from)\s+discord\b")


def _hash(token: str) -> str:
    return hashlib.sha256(token.lower().encode()).hexdigest()


def _tracked_files(root: Path) -> list[Path]:
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            capture_output=True, text=True, check=True,
        ).stdout
        files = [root / p for p in out.split("\0") if p]
    except (subprocess.CalledProcessError, FileNotFoundError):
        files = [p for p in root.rglob("*") if p.is_file()]
    return [p for p in files if p.is_file() and not (set(p.relative_to(root).parts[:-1]) & SKIP_DIRS)]


def scan(root: Path, extra_hashes: frozenset[str] = frozenset()) -> list[str]:
    forbidden = FORBIDDEN_SHA256 | extra_hashes
    hits: list[str] = []
    for path in sorted(_tracked_files(root)):
        rel = path.relative_to(root).as_posix()
        if any(_hash(t) in forbidden for t in TOKEN_RE.findall(path.name)):
            hits.append(f"{rel}:0: forbidden identifier in filename")
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for n, line in enumerate(lines, 1):
            if any(_hash(t) in forbidden for t in TOKEN_RE.findall(line)):
                hits.append(f"{rel}:{n}: forbidden identifier")
            if path.suffix == ".py" and DISCORD_IMPORT_RE.match(line):
                hits.append(f"{rel}:{n}: discord import")
    return hits


def main(argv: list[str] | None = None) -> int:
    root = Path(argv[0]) if argv else Path(__file__).resolve().parents[1]
    hits = scan(root)
    for h in hits:
        print(h)
    print(f"scrub check: {len(hits)} hit(s)")
    return 1 if hits else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

Note for the implementer: the ten hashes above are exact and must be copied verbatim. Do not attempt to reconstruct or print the tokens they represent.

- [ ] **Step 4: Run the tests and the check on the repo**

```bash
uv run pytest tests/test_scrub.py -q
uv run python tools/scrub_check.py
```

Expected: tests pass; the check prints `scrub check: 0 hit(s)`. If it reports hits, fix the flagged lines (a missed comment, a fixture name) and re-run. Never edit the hash set to make the check pass.

- [ ] **Step 5: Add the CI step and commit**

Insert after the `ruff format --check` step in `.github/workflows/ci.yml`:

```yaml
      - run: uv run python tools/scrub_check.py
```

```bash
git add tools tests/test_scrub.py .github/workflows/ci.yml
git commit -m "chore: scrub check for legacy identifiers and Discord imports

Hash-based so the repo never contains the identifiers it forbids. Runs in CI
and as a test."
```

---

### Task 5: Format, lint, and open the pull request

**Files:**
- Modify: any file ruff touches under `brawlfarm/`, `tests/`, `tools/`
- Modify: `docs/PLAN.md` (phase 1 status)

- [ ] **Step 1: Format once, then lint**

```bash
uv run ruff format .
uv run ruff check . --fix
uv run ruff check . && uv run ruff format --check .
```

Fix any remaining findings by hand (unused imports left by the port, import order). Do not add `noqa` to silence undefined names; those are real port bugs.

- [ ] **Step 2: Full verification**

```bash
uv run pytest -q
uv run python tools/scrub_check.py
uv run brawlfarm --version
uv run python -m brawlfarm.worker --help
```

Expected: all green, `0 hit(s)`, the version line, the worker help text.

- [ ] **Step 3: Commit the format pass**

```bash
git add -A
git commit -m "style: ruff format and lint the ported core and tests"
```

- [ ] **Step 4: Push and open the pull request**

```bash
git push -u origin phase-1/core-port
gh pr create --base main --title "Phase 1: repo and core" --body-file /dev/stdin <<'EOF'
## What and why
Ports the farm core and its tests from the legacy checkout into `brawlfarm/core`, with account identity removed and a hash-based scrub check in CI. Phase 1 of the approved build plan.

## Risk tier
T1 (tooling and port; no runtime behaviour change intended). Safety rails untouched: never-tap logic, verify-then-act, 1600 x 900 assertion, kill-by-PID.

## Safety-rail checklist
- [ ] No tap coordinate, OCR needle or core loop edited (diff reviewed for `core/controller.py`, `core/states.py`, `core/vision.py`, `core/config.py` calibration block).
- [ ] `config.INSTANCES` empty at import; `PLAYER_TAG` default empty.
- [ ] No `discord` import anywhere; scrub check green.

## Evidence
(paste: pytest summary line, scrub check output, CI run URL)

## Docs
`docs/PLAN.md` moves phase 1 to In flight with this PR; the spec and plan are in `docs/superpowers/`.

## Rollback
Revert the merge commit; nothing outside this repo changes.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
```

Paste the real evidence into the PR body (edit with `gh pr edit --body-file`) once CI finishes. Report the PR URL and the CI run URL.

---

## Self-review

- **Spec coverage.** Section 4 layout: Task 1 (package roots), Task 2 (core, templates, worker). Section 5 paths and identity: Task 2 Step 5. Section 9 rails: global constraint plus PR checklist. Section 10 hygiene: Task 4 scrub, Task 1 license and README, `.gitignore`. Section 11 testing: Tasks 3 and 4, CI in Task 1. Settings model, supervisor, API and UI are later phases by design.
- **Placeholders.** None; every step has the content or the exact command.
- **Type consistency.** `config.set_instances(mapping)` and `onboarding.farm_ports()` are named identically in Tasks 2 and 3; `scrub_check.scan(root, extra_hashes)` is named identically in Task 4's tests and implementation; `HOME_DIR` replaces `PROJECT_ROOT` in Tasks 2 and 3.
