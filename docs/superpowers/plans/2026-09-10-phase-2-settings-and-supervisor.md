# Phase 2: Settings and supervisor. Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give brawlfarm a typed `config.toml` settings model and a Python supervisor that launches, watches, stops and kills one worker per instance the way the legacy PowerShell watchdog did, runnable today as `uv run brawlfarm` (headless; the API and browser arrive in phase 3).

**Architecture:** `brawlfarm/settings.py` (pydantic) owns the data directory, `config.toml` load/save and the translation of settings into the worker's env contract, so the farm core never learns about TOML. `brawlfarm/supervisor/` is four small modules: `state.py` (pure heartbeat classification and the derived instance state), `backoff.py` (offline backoff), `process.py` (PID checks, launch, kill, adb probe), `loop.py` (the `Supervisor` tick, its control methods and the asyncio loop). Three small hooks land in the core so settings can reach it: `config.set_home()`, lazy CSV paths in `datalog`/`stats`, `notify.configure()` and `scheduler.set_default_enabled()`.

**Tech Stack:** Python 3.13, uv, pytest, ruff. New runtime deps: `pydantic>=2.9`, `tomli-w>=1.1` (TOML writing; reading uses stdlib `tomllib`), `psutil>=6.1` (PID liveness, command-line guard, kill). No FastAPI yet (phase 3).

**Spec:** `docs/superpowers/specs/2026-09-10-brawlfarm-design.md` (sections 3, 4, 5, 6, 9, 11). The legacy behaviour being ported is `../bsutil/tools/watchdog.ps1` (read-only reference).

## Global Constraints

- Python `>=3.13`; every command runs through `uv run`. Windows shell: use bash (Git Bash) commands as written; paths with forward slashes.
- The legacy checkout is the sibling folder `../bsutil` (read-only; never modify it). Refer to it only by that relative path. Never write its absolute path, its account nicknames, or its player tags into any file in this repo, including this plan, commit messages and PR text.
- `uv run python tools/scrub_check.py` must print `0 hit(s)` before every commit. No file may `import discord` or `from discord`.
- Instance names match `[A-Za-z0-9_-]{1,32}` (spec section 9); they become folder names. No user-supplied string ever reaches a shell: every subprocess call uses an argument list with `shell=False`, and adb serials are built only from a validated integer port.
- One worker per instance. Kill only by the PID read from that instance's `status.json`, never by process name or command-line search. A kill additionally refuses when the PID's command line does not run `brawlfarm.worker` (protection against PID reuse; still "by PID only").
- Safety rails in spec section 9 are untouched: do not edit the never-tap logic, the verify-then-act flow, the 1600 x 900 assertion, or any tap coordinate, OCR needle or timing in `core/controller.py`, `core/states.py`, `core/vision.py`, or the calibration block of `core/config.py`.
- Worker env contract (unchanged): `BRAWL_ADB_PORT`, `BRAWL_PLAYER_TAG`, `BRAWL_DATA_DIR`, plus `BRAWLFARM_HOME`. Env must be passed to `subprocess.Popen(env=...)` because `core/config.py` reads it at import time.
- Data directory: `%LOCALAPPDATA%\brawlfarm` by default; `BRAWLFARM_HOME` overrides it. Layout: `<home>/config.toml`, `<home>/instances/<name>/` (per-instance files, formats unchanged), `<home>/logs/`, `<home>/data/` (scheduler control and state files, unchanged from the core).
- Supervisor timings (spec section 6 and the legacy watchdog): tick 60 s, heartbeat stale at 240 s, boot grace 180 s, stop escalation 110 s, schedule freshness 600 s, offline backoff 2, 4, 8, 16, then 30 minutes, adb probe timeout 15 s, offline alert after 3 misses, at most one launch per tick.
- Every new `.py` file has a module docstring that says what the module is for. Every new test file has a docstring naming the behaviour it pins. Test output must be pristine (no warnings).
- Commit messages are conventional (`feat:`, `fix:`, `test:`, `docs:`, `chore:`) and explain why. Git identity must be `as9pa` (`git config user.name`) before every commit. Work on branch `phase-2/settings-supervisor`.
- `ruff check .` and `ruff format --check .` clean before every commit (run `uv run ruff format <changed files>` and `uv run ruff check --fix <changed files>` first). Line length 100.

---

### Task 1: Core path plumbing (`config.set_home`, lazy CSV paths, conftest)

Closes the phase 1 deferral: "conftest isolation does not reach module-level cached paths in core/config, core/datalog and core/stats". Gives the supervisor a single call to point the core at the user's data directory.

**Files:**
- Modify: `brawlfarm/core/config.py` (paths block, lines 17 to 36, and `ONBOARD_SHOTS_DIR` at line 581)
- Modify: `brawlfarm/core/datalog.py` (lines 24 to 25, 104 to 105, 119, 133, 169)
- Modify: `brawlfarm/core/stats.py` (lines 20 to 21, 30, 51)
- Modify: `tests/conftest.py`
- Modify: `tests/test_datalog_steps.py` (fixture at lines 17 to 22)
- Create: `tests/test_home_isolation.py`

**Interfaces:**
- Produces: `config.set_home(home: Path) -> None` (re-points `HOME_DIR`, `CAPTURES_DIR`, `ONBOARD_SHOTS_DIR`, `DATA_DIR`); `datalog.games_csv() -> Path`, `datalog.trophies_csv() -> Path`, `stats.games_csv() -> Path`, `stats.trophies_csv() -> Path`. The module constants `datalog.GAMES_CSV`, `datalog.TROPHIES_CSV`, `stats.GAMES_CSV`, `stats.TROPHIES_CSV` are removed.
- Consumed by: Task 5 (`Supervisor.__init__` calls `config.set_home`), the new `conftest.py`.

- [ ] **Step 1: Write the failing tests**

`tests/test_home_isolation.py`:

```python
"""config.set_home re-points every derived core path, and the suite-wide isolation
fixture reaches the CSV paths in datalog and stats (phase 1 deferral)."""

from __future__ import annotations

from pathlib import Path

from brawlfarm.core import config, datalog, stats


def test_set_home_repoints_every_derived_path(tmp_path: Path) -> None:
    home = tmp_path / "elsewhere"
    config.set_home(home)
    assert config.HOME_DIR == home.resolve()
    assert config.DATA_DIR == home.resolve() / "data"
    assert config.CAPTURES_DIR == home.resolve() / "captures"
    assert config.ONBOARD_SHOTS_DIR == home.resolve() / "captures" / "onboard"
    assert datalog.games_csv() == config.DATA_DIR / "games.csv"
    assert datalog.trophies_csv() == config.DATA_DIR / "menu_trophies.csv"
    assert stats.games_csv() == config.DATA_DIR / "games.csv"
    assert stats.trophies_csv() == config.DATA_DIR / "menu_trophies.csv"


def test_set_home_honours_brawl_data_dir(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BRAWL_DATA_DIR", "instances/Pie64")
    config.set_home(tmp_path)
    assert config.DATA_DIR == tmp_path.resolve() / "instances" / "Pie64"


def test_datalog_writes_under_the_isolated_home(tmp_path: Path) -> None:
    dl = datalog.DataLog()
    assert datalog.games_csv().exists()
    assert datalog.games_csv().is_relative_to(tmp_path)
    assert datalog.trophies_csv().is_relative_to(tmp_path)
    assert dl.session_path.is_relative_to(tmp_path)


def test_no_module_level_csv_constants_remain() -> None:
    for mod in (datalog, stats):
        assert not hasattr(mod, "GAMES_CSV")
        assert not hasattr(mod, "TROPHIES_CSV")
```

- [ ] **Step 2: Run them to confirm they fail**

```bash
uv run pytest tests/test_home_isolation.py -q
```

Expected: `AttributeError: module 'brawlfarm.core.config' has no attribute 'set_home'` and `has no attribute 'games_csv'`.

- [ ] **Step 3: Add `set_home` to `brawlfarm/core/config.py`**

Replace the paths block (lines 17 to 28, from the `# --- Paths` comment through the `DATA_DIR = ...` line) with:

```python
# --- Paths -------------------------------------------------------------------
# HOME_DIR is where runtime state lives (data, captures, .env). The control panel sets
# BRAWLFARM_HOME to the user data directory; a bare checkout defaults to the current
# working directory so `uv run python -m brawlfarm.worker` behaves like the legacy layout.
# set_home() re-points every derived path at runtime (the supervisor and the test suite
# call it); modules must read these names at call time, never cache them at import.
PACKAGE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = PACKAGE_DIR / "templates"

HOME_DIR = Path(os.environ.get("BRAWLFARM_HOME", "") or Path.cwd()).resolve()
CAPTURES_DIR = HOME_DIR / "captures"
ONBOARD_SHOTS_DIR = CAPTURES_DIR / "onboard"  # step-by-step evidence screenshots
# Data dir is env-overridable so concurrent workers on different instances write to
# separate folders (one shared games.csv would race and corrupt). Pairs with
# BRAWL_ADB_PORT and BRAWL_PLAYER_TAG for multi-instance runs.
DATA_DIR = HOME_DIR / os.environ.get("BRAWL_DATA_DIR", "data")


def set_home(home: Path) -> None:
    """Point every home-derived path at ``home`` (resolved). DATA_DIR keeps honouring
    BRAWL_DATA_DIR so a worker process still lands in its own instance folder."""
    global HOME_DIR, CAPTURES_DIR, ONBOARD_SHOTS_DIR, DATA_DIR
    HOME_DIR = Path(home).resolve()
    CAPTURES_DIR = HOME_DIR / "captures"
    ONBOARD_SHOTS_DIR = CAPTURES_DIR / "onboard"
    DATA_DIR = HOME_DIR / os.environ.get("BRAWL_DATA_DIR", "data")
```

Then delete the old `ONBOARD_SHOTS_DIR = CAPTURES_DIR / "onboard"` line near line 581 (it now lives in the paths block; keep the surrounding onboarding constants untouched). Keep `ADB_PATH`, `BS_PACKAGE` and `load_dotenv(HOME_DIR / ".env")` exactly where they were, after the new block.

- [ ] **Step 4: Make the CSV paths lazy in `datalog.py` and `stats.py`**

In `brawlfarm/core/datalog.py` replace lines 24 to 25 with:

```python
def games_csv() -> Path:
    """Per-instance games log; resolved at call time so config.set_home() is honoured."""
    return config.DATA_DIR / "games.csv"


def trophies_csv() -> Path:
    return config.DATA_DIR / "menu_trophies.csv"
```

and change every use: `_ensure_csv(GAMES_CSV, ...)` to `_ensure_csv(games_csv(), ...)`, `_ensure_csv(TROPHIES_CSV, ...)` to `_ensure_csv(trophies_csv(), ...)`, `GAMES_CSV.open(...)` to `games_csv().open(...)` (two sites), `TROPHIES_CSV.open(...)` to `trophies_csv().open(...)`. Add `from pathlib import Path` if the module does not import it yet.

In `brawlfarm/core/stats.py` replace lines 20 to 21 with the same two functions (same docstring), and change `path = Path(path) if path else GAMES_CSV` to `path = Path(path) if path else games_csv()` and the trophies twin likewise.

- [ ] **Step 5: Rewrite `tests/conftest.py` and trim the datalog fixture**

`tests/conftest.py`:

```python
"""Suite-wide isolation: every test gets an empty home directory and no farm env."""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    for key in list(os.environ):
        if key.startswith(("BRAWL_", "DISCORD_", "NTFY_")):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("BRAWLFARM_HOME", str(tmp_path))
    from brawlfarm.core import config

    previous_home = config.HOME_DIR
    config.set_home(tmp_path)
    config.set_instances({})
    yield
    config.set_instances({})
    config.set_home(previous_home)
```

In `tests/test_datalog_steps.py` the `dl` fixture becomes:

```python
@pytest.fixture()
def dl(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    return datalog.DataLog()
```

(The two `GAMES_CSV` / `TROPHIES_CSV` setattr lines go away; the lazy functions read `config.DATA_DIR` at call time.)

- [ ] **Step 6: Run the new test file, then the whole suite**

```bash
uv run pytest tests/test_home_isolation.py -q
uv run pytest -q
```

Expected: 4 new tests pass; the full suite passes (336 + 4). If any ported test still references `datalog.GAMES_CSV` or `stats.GAMES_CSV`, switch it to the function.

- [ ] **Step 7: Lint, scrub, commit**

```bash
uv run ruff format brawlfarm/core/config.py brawlfarm/core/datalog.py brawlfarm/core/stats.py tests/conftest.py tests/test_datalog_steps.py tests/test_home_isolation.py
uv run ruff check . && uv run ruff format --check .
uv run python tools/scrub_check.py
git add brawlfarm/core/config.py brawlfarm/core/datalog.py brawlfarm/core/stats.py tests/conftest.py tests/test_datalog_steps.py tests/test_home_isolation.py
git commit -m "fix(core): resolve home-derived paths at call time

config.set_home() re-points HOME_DIR, DATA_DIR, CAPTURES_DIR and
ONBOARD_SHOTS_DIR; datalog and stats resolve their CSV paths per call.
The supervisor needs one call to aim the core at the user data directory,
and the test suite's isolation now reaches every path (phase 1 deferral)."
```

---

### Task 2: Settings model (`brawlfarm/settings.py`)

**Files:**
- Modify: `pyproject.toml` (add `pydantic>=2.9`, `tomli-w>=1.1`, `psutil>=6.1` to `dependencies`)
- Create: `brawlfarm/settings.py`
- Create: `tests/test_settings.py`

**Interfaces:**
- Produces (all in `brawlfarm.settings`):
  - `INSTANCE_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")`, `PLAYER_TAG_RE = re.compile(r"^#[0289PYLQGRJCUV]{3,}$")`
  - `class SettingsError(ValueError)`
  - `class InstanceSettings(BaseModel)`: `name: str`, `adb_port: int` (1..65535), `player_tag: str = ""` (normalised to upper case with a leading `#`, or empty)
  - `class AppSettings(BaseModel)` with sections `app`, `connection`, `behavior`, `advanced`, `scheduler`, `notifications` and `instances: list[InstanceSettings]`; unknown keys are rejected (`extra="forbid"`); duplicate instance names or ports are rejected
  - `default_home() -> Path`: `BRAWLFARM_HOME` if set, else `%LOCALAPPDATA%\brawlfarm`
  - `config_path(home: Path) -> Path` = `home / "config.toml"`
  - `load(home: Path) -> AppSettings` (missing file gives defaults; malformed raises `SettingsError`)
  - `save(settings: AppSettings, home: Path) -> Path` (atomic: temp file then `os.replace`)
  - `instance_dir(home: Path, name: str) -> Path` = `home / "instances" / name`
  - `instances_table(settings) -> dict[str, dict[str, str]]` for `config.set_instances`
  - `worker_env(settings, inst: InstanceSettings, home: Path) -> dict[str, str]`
  - `worker_args(settings, max_minutes: float | None) -> list[str]`
- Consumed by: Tasks 5 and 6.

- [ ] **Step 1: Add the dependencies**

In `pyproject.toml`, `dependencies` becomes:

```toml
dependencies = [
  "opencv-python>=4.10",
  "numpy>=2.0",
  "requests>=2.32",
  "python-dotenv>=1.0",
  "rapidocr-onnxruntime>=1.3",
  "pandas>=2.2",
  "pydantic>=2.9",
  "tomli-w>=1.1",
  "psutil>=6.1",
]
```

```bash
uv sync --group dev
uv run python -c "import pydantic, tomli_w, psutil; print(pydantic.VERSION, psutil.__version__)"
```

Expected: a pydantic 2.x version and a psutil version print; `uv.lock` changes.

- [ ] **Step 2: Write the failing tests**

`tests/test_settings.py`:

```python
"""config.toml settings model: defaults when the file is missing, round-trip through
save/load, validation of instance names, ports and tags, and the worker env contract."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

import pytest

from brawlfarm import settings as S


def _two_instances() -> S.AppSettings:
    return S.AppSettings(
        instances=[
            S.InstanceSettings(name="Pie64", adb_port=5555, player_tag="#2P0YLQ9"),
            S.InstanceSettings(name="Rome64", adb_port=5565),
        ]
    )


def test_defaults_match_the_spec() -> None:
    s = S.AppSettings()
    assert s.app.port == 8765
    assert s.app.theme == "system"
    assert s.connection.adb_path == r"C:\Program Files\BlueStacks_nxt\HD-Adb.exe"
    assert s.connection.brawl_api_token == ""
    assert s.behavior.winrate_aware is True
    assert s.behavior.opportunity_cost is False
    assert s.behavior.gas_aware is True
    assert s.behavior.bush_hide is False
    assert s.behavior.close_game_on_stop is True
    assert s.behavior.dnd_at_start is True
    assert s.scheduler.default_enabled is True
    assert s.notifications.webhook_url == ""
    assert s.notifications.ntfy_topic == ""
    assert s.notifications.ntfy_server == "https://ntfy.sh"
    assert s.notifications.healthchecks_url == ""
    assert s.notifications.events == ["crash", "recover", "offline", "wrong_mode", "recalibrate"]
    assert s.instances == []
    assert s.advanced.fast_input is True
    assert s.advanced.raw_cap is True
    assert s.advanced.gray_match is True
    assert s.advanced.phase_classify is True
    assert s.advanced.ability_buttons is True
    assert s.advanced.recalib_tripwire is True
    assert s.advanced.dnd_off_on_stop is True


def test_load_missing_file_gives_defaults(tmp_path: Path) -> None:
    assert S.load(tmp_path) == S.AppSettings()
    assert not S.config_path(tmp_path).exists()


def test_round_trip_preserves_every_field(tmp_path: Path) -> None:
    original = _two_instances()
    original.app.port = 9000
    original.behavior.bush_hide = True
    original.notifications.events = ["crash"]
    path = S.save(original, tmp_path)
    assert path == tmp_path / "config.toml"
    assert S.load(tmp_path) == original
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    assert raw["instances"][0] == {"name": "Pie64", "adb_port": 5555, "player_tag": "#2P0YLQ9"}
    assert raw["app"]["port"] == 9000


def test_save_is_atomic_and_leaves_no_temp_file(tmp_path: Path) -> None:
    S.save(S.AppSettings(), tmp_path)
    S.save(_two_instances(), tmp_path)
    leftovers = [p.name for p in tmp_path.iterdir() if p.name != "config.toml"]
    assert leftovers == []
    assert len(S.load(tmp_path).instances) == 2


def test_malformed_toml_raises_settings_error(tmp_path: Path) -> None:
    S.config_path(tmp_path).write_text("[app\nport = 1\n", encoding="utf-8")
    with pytest.raises(S.SettingsError) as exc:
        S.load(tmp_path)
    assert "config.toml" in str(exc.value)


def test_unknown_key_is_rejected(tmp_path: Path) -> None:
    S.config_path(tmp_path).write_text("[app]\nprot = 1\n", encoding="utf-8")
    with pytest.raises(S.SettingsError) as exc:
        S.load(tmp_path)
    assert "prot" in str(exc.value)


@pytest.mark.parametrize("bad", ["", "a" * 33, "bad name", "../x", "dot.name"])
def test_instance_name_is_validated(bad: str) -> None:
    with pytest.raises(ValueError):
        S.InstanceSettings(name=bad, adb_port=5555)


@pytest.mark.parametrize("port", [0, 65536, -1])
def test_adb_port_range(port: int) -> None:
    with pytest.raises(ValueError):
        S.InstanceSettings(name="ok", adb_port=port)


def test_player_tag_is_normalised_or_rejected() -> None:
    assert S.InstanceSettings(name="a", adb_port=1, player_tag="2p0ylq9").player_tag == "#2P0YLQ9"
    assert S.InstanceSettings(name="a", adb_port=1, player_tag="  ").player_tag == ""
    with pytest.raises(ValueError):
        S.InstanceSettings(name="a", adb_port=1, player_tag="#ABC")  # A and B are not tag letters


def test_duplicate_names_and_ports_are_rejected() -> None:
    with pytest.raises(ValueError):
        S.AppSettings(
            instances=[
                S.InstanceSettings(name="x", adb_port=1),
                S.InstanceSettings(name="x", adb_port=2),
            ]
        )
    with pytest.raises(ValueError):
        S.AppSettings(
            instances=[
                S.InstanceSettings(name="x", adb_port=1),
                S.InstanceSettings(name="y", adb_port=1),
            ]
        )


def test_theme_is_restricted() -> None:
    with pytest.raises(ValueError):
        S.AppSettings(app={"theme": "neon"})


def test_default_home_prefers_env_then_localappdata(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BRAWLFARM_HOME", str(tmp_path / "h"))
    assert S.default_home() == (tmp_path / "h").resolve()
    monkeypatch.delenv("BRAWLFARM_HOME")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "lad"))
    assert S.default_home() == (tmp_path / "lad" / "brawlfarm").resolve()


def test_instance_dir_and_table() -> None:
    s = _two_instances()
    home = Path("C:/h")
    assert S.instance_dir(home, "Pie64") == home / "instances" / "Pie64"
    assert S.instances_table(s) == {
        "Pie64": {"port": "5555", "tag": "#2P0YLQ9", "data": "instances/Pie64"},
        "Rome64": {"port": "5565", "tag": "", "data": "instances/Rome64"},
    }


def test_worker_env_is_the_full_contract(tmp_path: Path) -> None:
    s = _two_instances()
    s.behavior.bush_hide = False
    s.behavior.opportunity_cost = True
    s.advanced.raw_cap = False
    s.connection.brawl_api_token = "tok"
    s.notifications.webhook_url = "https://example.invalid/hook"
    s.notifications.ntfy_topic = "farm"
    s.notifications.events = ["crash", "offline"]
    env = S.worker_env(s, s.instances[0], tmp_path)
    assert env == {
        "BRAWLFARM_HOME": str(tmp_path.resolve()),
        "BRAWL_DATA_DIR": "instances/Pie64",
        "BRAWL_ADB_PORT": "5555",
        "BRAWL_PLAYER_TAG": "#2P0YLQ9",
        "BRAWL_ADB_PATH": r"C:\Program Files\BlueStacks_nxt\HD-Adb.exe",
        "BRAWL_API_TOKEN": "tok",
        "BRAWL_WINRATE_AWARE": "1",
        "BRAWL_WINRATE_OPPORTUNITY_COST": "1",
        "BRAWL_GAS_AWARE": "1",
        "BRAWL_BUSH_HIDE": "0",
        "BRAWL_CLOSE_GAME_ON_STOP": "1",
        "BRAWL_FAST_INPUT": "1",
        "BRAWL_RAW_CAP": "0",
        "BRAWL_GRAY_MATCH": "1",
        "BRAWL_PHASE_CLASSIFY": "1",
        "BRAWL_ABILITY_BUTTONS": "1",
        "BRAWL_RECALIB_TRIPWIRE": "1",
        "BRAWL_DND_OFF_ON_STOP": "1",
        "BRAWL_WEBHOOK_URL": "https://example.invalid/hook",
        "NTFY_TOPIC": "farm",
        "NTFY_SERVER": "https://ntfy.sh",
        "BRAWL_NOTIFY_EVENTS": "crash,offline",
    }
    assert all(isinstance(v, str) for v in env.values())


def test_worker_args_follow_dnd_and_cap() -> None:
    s = S.AppSettings()
    assert S.worker_args(s, None) == ["--select-brawler", "--dnd"]
    s.behavior.dnd_at_start = False
    assert S.worker_args(s, 42.7) == ["--select-brawler", "--max-minutes", "42.7"]


def test_settings_module_does_not_import_the_core() -> None:
    """settings.py decides BRAWLFARM_HOME before the core (which reads it at import) loads,
    so it must never import brawlfarm.core. Checked on the source, not by reloading modules."""
    source = Path(S.__file__).read_text(encoding="utf-8")
    offenders = [
        line for line in source.splitlines() if re.match(r"^\s*(from|import)\s+brawlfarm\.core", line)
    ]
    assert offenders == []
```

(Add `import re` to the test module's imports; `os` is still used by nothing else, so drop the `import os` line.)

- [ ] **Step 3: Run to confirm failure**

```bash
uv run pytest tests/test_settings.py -q
```

Expected: `ModuleNotFoundError: No module named 'brawlfarm.settings'`.

- [ ] **Step 4: Write `brawlfarm/settings.py`**

```python
"""Typed settings: config.toml in the data directory, and the translation of those
settings into the worker's environment so the farm core never reads TOML.

This module must not import brawlfarm.core: it decides where the home directory is
before the core (which reads BRAWLFARM_HOME at import) is loaded.
"""

from __future__ import annotations

import os
import re
import tomllib
from pathlib import Path
from typing import Literal

import tomli_w
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

INSTANCE_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,32}$")
# The game's tag alphabet: no vowels, no 1/3/4/5/6/7, so tags never spell words.
PLAYER_TAG_RE = re.compile(r"^#[0289PYLQGRJCUV]{3,}$")
DEFAULT_ADB_PATH = r"C:\Program Files\BlueStacks_nxt\HD-Adb.exe"
CONFIG_NAME = "config.toml"


class SettingsError(ValueError):
    """config.toml is unreadable or invalid; the message names the file and the reason."""


class _Section(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class AppSection(_Section):
    port: int = Field(default=8765, ge=1, le=65535)
    theme: Literal["system", "dark", "light"] = "system"


class ConnectionSection(_Section):
    adb_path: str = DEFAULT_ADB_PATH
    brawl_api_token: str = ""


class BehaviorSection(_Section):
    winrate_aware: bool = True
    opportunity_cost: bool = False  # off by default: it thrashed near-maxed rosters
    gas_aware: bool = True
    bush_hide: bool = False  # experimental, not validated live
    close_game_on_stop: bool = True
    dnd_at_start: bool = True


class AdvancedSection(_Section):
    """Performance and safety switches the core exposes as BRAWL_* flags. All on."""

    fast_input: bool = True
    raw_cap: bool = True
    gray_match: bool = True
    phase_classify: bool = True
    ability_buttons: bool = True
    recalib_tripwire: bool = True
    dnd_off_on_stop: bool = True


class SchedulerSection(_Section):
    default_enabled: bool = True


class NotificationsSection(_Section):
    webhook_url: str = ""  # any webhook that accepts {"content": ...}
    ntfy_topic: str = ""
    ntfy_server: str = "https://ntfy.sh"
    healthchecks_url: str = ""
    events: list[str] = Field(
        default_factory=lambda: ["crash", "recover", "offline", "wrong_mode", "recalibrate"]
    )


class InstanceSettings(_Section):
    name: str
    adb_port: int = Field(ge=1, le=65535)
    player_tag: str = ""  # optional; only used for the Brawl Stars API

    @field_validator("name")
    @classmethod
    def _valid_name(cls, v: str) -> str:
        if not INSTANCE_NAME_RE.match(v):
            raise ValueError("instance name must match [A-Za-z0-9_-]{1,32} (it becomes a folder)")
        return v

    @field_validator("player_tag")
    @classmethod
    def _normalise_tag(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            return ""
        if not v.startswith("#"):
            v = "#" + v
        if not PLAYER_TAG_RE.match(v):
            raise ValueError("player tag must be # followed by letters from 0289PYLQGRJCUV")
        return v


class AppSettings(_Section):
    app: AppSection = Field(default_factory=AppSection)
    connection: ConnectionSection = Field(default_factory=ConnectionSection)
    behavior: BehaviorSection = Field(default_factory=BehaviorSection)
    advanced: AdvancedSection = Field(default_factory=AdvancedSection)
    scheduler: SchedulerSection = Field(default_factory=SchedulerSection)
    notifications: NotificationsSection = Field(default_factory=NotificationsSection)
    instances: list[InstanceSettings] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_instances(self) -> AppSettings:
        names = [i.name for i in self.instances]
        ports = [i.adb_port for i in self.instances]
        if len(set(names)) != len(names):
            raise ValueError("instance names must be unique")
        if len(set(ports)) != len(ports):
            raise ValueError("instance adb ports must be unique (one worker per instance)")
        return self

    def instance(self, name: str) -> InstanceSettings:
        for inst in self.instances:
            if inst.name == name:
                return inst
        raise KeyError(name)


# --- Locations -----------------------------------------------------------------------


def default_home() -> Path:
    """BRAWLFARM_HOME if set (development, tests), else %LOCALAPPDATA%\\brawlfarm."""
    env = os.environ.get("BRAWLFARM_HOME", "").strip()
    if env:
        return Path(env).resolve()
    local = os.environ.get("LOCALAPPDATA", "").strip() or str(Path.home() / "AppData" / "Local")
    return (Path(local) / "brawlfarm").resolve()


def config_path(home: Path) -> Path:
    return Path(home) / CONFIG_NAME


def instance_dir(home: Path, name: str) -> Path:
    return Path(home) / "instances" / name


# --- Load / save ---------------------------------------------------------------------


def load(home: Path) -> AppSettings:
    """Read config.toml under ``home``; a missing file yields defaults."""
    path = config_path(home)
    if not path.exists():
        return AppSettings()
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise SettingsError(f"{path}: cannot read config.toml: {exc}") from exc
    try:
        return AppSettings.model_validate(raw)
    except ValidationError as exc:
        raise SettingsError(f"{path}: invalid config.toml: {_explain(exc)}") from exc


def _explain(exc: ValidationError) -> str:
    parts = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err.get("loc", ())) or "(root)"
        parts.append(f"{loc}: {err.get('msg', 'invalid')}")
    return "; ".join(parts)


def save(settings: AppSettings, home: Path) -> Path:
    """Write config.toml atomically (temp file, then os.replace). Rewrites the whole file;
    comments a user added by hand are not preserved."""
    path = config_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = tomli_w.dumps(settings.model_dump(mode="json"))
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
    return path


# --- Worker contract -----------------------------------------------------------------


def instances_table(settings: AppSettings) -> dict[str, dict[str, str]]:
    """The runtime instance table the core expects from ``config.set_instances``."""
    return {
        i.name: {"port": str(i.adb_port), "tag": i.player_tag, "data": f"instances/{i.name}"}
        for i in settings.instances
    }


def _flag(value: bool) -> str:
    return "1" if value else "0"


def worker_env(settings: AppSettings, inst: InstanceSettings, home: Path) -> dict[str, str]:
    """Everything a worker process reads from its environment, as strings. Passed to
    Popen(env=...) because core/config.py reads these at import time."""
    b, a, n, c = settings.behavior, settings.advanced, settings.notifications, settings.connection
    return {
        "BRAWLFARM_HOME": str(Path(home).resolve()),
        "BRAWL_DATA_DIR": f"instances/{inst.name}",
        "BRAWL_ADB_PORT": str(inst.adb_port),
        "BRAWL_PLAYER_TAG": inst.player_tag,
        "BRAWL_ADB_PATH": c.adb_path,
        "BRAWL_API_TOKEN": c.brawl_api_token,
        "BRAWL_WINRATE_AWARE": _flag(b.winrate_aware),
        "BRAWL_WINRATE_OPPORTUNITY_COST": _flag(b.opportunity_cost),
        "BRAWL_GAS_AWARE": _flag(b.gas_aware),
        "BRAWL_BUSH_HIDE": _flag(b.bush_hide),
        "BRAWL_CLOSE_GAME_ON_STOP": _flag(b.close_game_on_stop),
        "BRAWL_FAST_INPUT": _flag(a.fast_input),
        "BRAWL_RAW_CAP": _flag(a.raw_cap),
        "BRAWL_GRAY_MATCH": _flag(a.gray_match),
        "BRAWL_PHASE_CLASSIFY": _flag(a.phase_classify),
        "BRAWL_ABILITY_BUTTONS": _flag(a.ability_buttons),
        "BRAWL_RECALIB_TRIPWIRE": _flag(a.recalib_tripwire),
        "BRAWL_DND_OFF_ON_STOP": _flag(a.dnd_off_on_stop),
        "BRAWL_WEBHOOK_URL": n.webhook_url,
        "NTFY_TOPIC": n.ntfy_topic,
        "NTFY_SERVER": n.ntfy_server,
        "BRAWL_NOTIFY_EVENTS": ",".join(n.events),
    }


def worker_args(settings: AppSettings, max_minutes: float | None) -> list[str]:
    """CLI flags for ``python -m brawlfarm.worker``: brawler selection always, DND when
    the behaviour setting says so, and the scheduler's session cap when there is one."""
    args = ["--select-brawler"]
    if settings.behavior.dnd_at_start:
        args.append("--dnd")
    if max_minutes is not None:
        args += ["--max-minutes", f"{max_minutes:g}"]
    return args
```

- [ ] **Step 5: Run the tests until green**

```bash
uv run pytest tests/test_settings.py -q
```

Expected: all pass. If `tomli_w.dumps` rejects the model dump, check that `model_dump(mode="json")` produced only str/int/bool/list/dict values (it should; there are no `None` fields).

- [ ] **Step 6: Lint, scrub, commit**

```bash
uv run ruff format brawlfarm/settings.py tests/test_settings.py
uv run ruff check . && uv run ruff format --check .
uv run python tools/scrub_check.py
git add pyproject.toml uv.lock brawlfarm/settings.py tests/test_settings.py
git commit -m "feat(settings): typed config.toml model and the worker env contract

pydantic model with the spec's sections and defaults, atomic save, defaults
when the file is missing, and worker_env()/worker_args() so the supervisor
launches workers with the same env the legacy watchdog set. The core stays
TOML-free."
```

---

### Task 3: Core hooks for settings (`notify.configure`, `scheduler.set_default_enabled`)

**Files:**
- Modify: `brawlfarm/core/notify.py` (lines 36 to 43 `ALERT_KINDS`, 55 to 62 `_TITLES`, 70 to 82 the env readers and `configured()`, 156 to 177 `maybe_alert`)
- Modify: `brawlfarm/core/scheduler.py` (`_ctl_enabled` at lines 679 to 684 and `enabled_from` at lines 992 to 1002)
- Create: `tests/test_notify_config.py`
- Modify: `tests/test_scheduler.py` (one new test appended)

**Interfaces:**
- Produces: `notify.configure(*, webhook_url: str | None = None, ntfy_server: str | None = None, ntfy_topic: str | None = None, events: list[str] | None = None) -> None` (explicit values win over the environment; `None` leaves that value on its env default), `notify.enabled_events() -> frozenset[str]`, `notify.ALERT_KINDS` now includes `"offline"`; env `BRAWL_WEBHOOK_URL` (with `DISCORD_WEBHOOK_URL` still honoured as a fallback) and `BRAWL_NOTIFY_EVENTS` (comma list; unset means every alert kind). `scheduler.DEFAULT_ENABLED: bool`, `scheduler.set_default_enabled(flag: bool) -> None`.
- Consumed by: Task 5 (the supervisor calls both at start-up and fires `maybe_alert("offline", ...)`).

- [ ] **Step 1: Write the failing tests**

`tests/test_notify_config.py`:

```python
"""notify reads its backends from BRAWL_WEBHOOK_URL / NTFY_* or from configure(), and
BRAWL_NOTIFY_EVENTS (or configure(events=...)) filters which alert kinds are sent."""

from __future__ import annotations

import pytest

from brawlfarm.core import notify


@pytest.fixture(autouse=True)
def _reset():
    notify.configure(webhook_url=None, ntfy_server=None, ntfy_topic=None, events=None)
    notify._overrides.clear()
    notify._last_alert.clear()
    yield
    notify._overrides.clear()
    notify._last_alert.clear()


def test_unconfigured_by_default() -> None:
    assert notify.configured() is False


def test_env_webhook_new_name_and_legacy_fallback(monkeypatch) -> None:
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://legacy.invalid/x")
    assert notify.configured() is True
    monkeypatch.setenv("BRAWL_WEBHOOK_URL", "https://new.invalid/y")
    assert notify._webhook_url() == "https://new.invalid/y"


def test_configure_wins_over_env(monkeypatch) -> None:
    monkeypatch.setenv("NTFY_TOPIC", "from-env")
    notify.configure(ntfy_topic="from-settings", ntfy_server="https://ntfy.example/")
    assert notify._ntfy() == ("https://ntfy.example", "from-settings")


def test_events_filter_from_env_and_configure(monkeypatch) -> None:
    assert notify.enabled_events() == frozenset(notify.ALERT_KINDS)
    monkeypatch.setenv("BRAWL_NOTIFY_EVENTS", "crash, offline")
    assert notify.enabled_events() == frozenset({"crash", "offline"})
    notify.configure(events=["recover"])
    assert notify.enabled_events() == frozenset({"recover"})


def test_offline_is_an_alert_kind_and_filter_applies(monkeypatch) -> None:
    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(notify, "notify", lambda title, msg, screenshot=None: sent.append((title, msg)) or True)
    notify.configure(webhook_url="https://hook.invalid/z", events=["offline"])
    notify.maybe_alert("crash", {"x": 1})
    notify.maybe_alert("offline", {"instance": "Pie64", "misses": 3})
    assert sent == [("Instance offline", "instance=Pie64, misses=3")]
```

Append to `tests/test_scheduler.py`:

```python
def test_default_enabled_flag_wires_into_control_and_schedule_defaults() -> None:
    from brawlfarm.core import scheduler as sch

    try:
        sch.set_default_enabled(False)
        assert sch._ctl_enabled({}) is False
        assert sch._ctl_enabled({"enabled": True}) is True
        assert sch.enabled_from(None) is False
        sch.set_default_enabled(True)
        assert sch._ctl_enabled({}) is True
        assert sch.enabled_from(None) is True
    finally:
        sch.set_default_enabled(True)
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_notify_config.py tests/test_scheduler.py::test_default_enabled_flag_wires_into_control_and_schedule_defaults -q
```

Expected: `AttributeError: module ... has no attribute 'configure'` / `'set_default_enabled'`.

- [ ] **Step 3: Edit `brawlfarm/core/notify.py`**

Add `"offline"` to `ALERT_KINDS` and `"offline": "Instance offline"` to `_TITLES`. Replace the block from `def _discord_url()` through `def configured()` (lines 70 to 82) with:

```python
# Explicit settings from the control panel; None means "use the environment".
_overrides: dict[str, object] = {}


def configure(
    *,
    webhook_url: str | None = None,
    ntfy_server: str | None = None,
    ntfy_topic: str | None = None,
    events: list[str] | None = None,
) -> None:
    """Set the backends from settings. Workers keep reading the environment the
    supervisor hands them; the supervisor process itself calls this once."""
    for key, value in (
        ("webhook_url", webhook_url),
        ("ntfy_server", ntfy_server),
        ("ntfy_topic", ntfy_topic),
        ("events", events),
    ):
        if value is None:
            _overrides.pop(key, None)
        else:
            _overrides[key] = value


def _webhook_url() -> str:
    if "webhook_url" in _overrides:
        return str(_overrides["webhook_url"]).strip()
    return (
        os.environ.get("BRAWL_WEBHOOK_URL", "") or os.environ.get("DISCORD_WEBHOOK_URL", "")
    ).strip()


def _ntfy() -> tuple[str, str]:
    server = str(_overrides.get("ntfy_server", os.environ.get("NTFY_SERVER", "https://ntfy.sh")))
    topic = str(_overrides.get("ntfy_topic", os.environ.get("NTFY_TOPIC", "")))
    return server.strip().rstrip("/"), topic.strip()


def enabled_events() -> frozenset[str]:
    """Alert kinds that may be sent: configure(events=...), else BRAWL_NOTIFY_EVENTS, else all."""
    if "events" in _overrides:
        return frozenset(str(e).strip() for e in _overrides["events"] if str(e).strip())
    raw = os.environ.get("BRAWL_NOTIFY_EVENTS", "").strip()
    if not raw:
        return frozenset(ALERT_KINDS)
    return frozenset(e.strip() for e in raw.split(",") if e.strip())


def configured() -> bool:
    """True if at least one notification backend is set up."""
    return bool(_webhook_url()) or bool(_ntfy()[1])
```

Then rename every remaining use of `_discord_url()` in the file to `_webhook_url()` (the webhook send function around line 120 uses it), and in `maybe_alert` change the guard to:

```python
    if kind not in ALERT_KINDS or kind not in enabled_events() or not configured():
        return
```

Finally change the stderr hint in `maybe_alert` from `DISCORD_WEBHOOK_URL / NTFY_TOPIC` to `BRAWL_WEBHOOK_URL / NTFY_TOPIC`, and reword any comment that still calls the webhook backend "Discord" as "webhook".

- [ ] **Step 4: Edit `brawlfarm/core/scheduler.py`**

Above `_ctl_enabled` add:

```python
# The [scheduler].default_enabled setting: what an account with no explicit enabled
# flag means. The supervisor sets it from config.toml before the first tick.
DEFAULT_ENABLED = True


def set_default_enabled(flag: bool) -> None:
    global DEFAULT_ENABLED
    DEFAULT_ENABLED = bool(flag)
```

Change `_ctl_enabled`'s body to `return bool(c.get("enabled", DEFAULT_ENABLED))` and its docstring's first sentence to "DEFAULT-ON semantics (configurable through set_default_enabled)". In `enabled_from`, replace the final `return True` fallback with `return DEFAULT_ENABLED`.

- [ ] **Step 5: Run the tests, then the full suite**

```bash
uv run pytest tests/test_notify_config.py tests/test_scheduler.py -q
uv run pytest -q
```

Expected: all pass, no warnings.

- [ ] **Step 6: Lint, scrub, commit**

```bash
uv run ruff format brawlfarm/core/notify.py brawlfarm/core/scheduler.py tests/test_notify_config.py tests/test_scheduler.py
uv run ruff check . && uv run ruff format --check .
uv run python tools/scrub_check.py
git add brawlfarm/core/notify.py brawlfarm/core/scheduler.py tests/test_notify_config.py tests/test_scheduler.py
git commit -m "feat(core): let settings configure notify and the scheduler default

notify.configure() and BRAWL_WEBHOOK_URL / BRAWL_NOTIFY_EVENTS carry the
[notifications] section (offline is a new alert kind for the supervisor);
scheduler.set_default_enabled() carries [scheduler].default_enabled."
```

---

### Task 4: Supervisor leaf modules (`state.py`, `backoff.py`, `process.py`)

**Files:**
- Create: `brawlfarm/supervisor/__init__.py`, `brawlfarm/supervisor/state.py`, `brawlfarm/supervisor/backoff.py`, `brawlfarm/supervisor/process.py`
- Create: `tests/test_supervisor_state.py`, `tests/test_supervisor_backoff.py`, `tests/test_supervisor_process.py`

**Interfaces:**
- Produces (`brawlfarm.supervisor.state`): `STALE_S = 240.0`; `class Health(StrEnum)`: `HEALTHY`, `STALE`, `DEAD`; `class InstanceState(StrEnum)`: `FARMING`, `STOPPED`, `SCHEDULED_BREAK`, `RECONNECTING`, `OFFLINE`, `STARTING`, `STOPPING`; `parse_ts(ts: str) -> datetime | None`; `heartbeat_age_s(status: dict | None, now: datetime) -> float | None`; `classify(status: dict | None, alive: bool, now: datetime) -> Health`; `@dataclass(frozen=True) class InstanceView` with fields `name: str`, `adb_port: int`, `state: InstanceState`, `health: Health`, `pid: int | None`, `heartbeat_age_s: float | None`, `phase: str | None`, `desired: str`, `desired_reason: str | None`, `until: datetime | None`, `games_played: int | None`, `farm_brawler: str | None`, `note: str`; `derive_state(*, health, desired, desired_reason, desired_until, stop_pending, booting, offline_until, status) -> tuple[InstanceState, datetime | None]`.
- Produces (`brawlfarm.supervisor.backoff`): `BACKOFF_MINUTES = (2, 4, 8, 16, 30)`; `class OfflineBackoff` with `record_miss(name, now) -> datetime`, `until(name, now) -> datetime | None`, `misses(name) -> int`, `clear(name) -> None`, `clear_all() -> None`.
- Produces (`brawlfarm.supervisor.process`): `WORKER_MODULE = "brawlfarm.worker"`; `pid_alive(pid: int) -> bool`; `is_worker(pid: int) -> bool`; `kill_worker(pid: int, log=print) -> bool`; `launch_worker(args: list[str], env: dict[str, str], log_dir: Path, name: str) -> subprocess.Popen`; `instance_online(adb_path: str, port: int, timeout_s: float = 15.0) -> bool`.
- Consumed by: Task 5.

- [ ] **Step 1: Write the failing tests**

`tests/test_supervisor_state.py`:

```python
"""Heartbeat classification (healthy / stale / dead) and the derived instance state the
spec shows everywhere (farming, stopped, scheduled break, reconnecting, offline, plus
the transitional starting and stopping)."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta

import pytest

from brawlfarm.supervisor import state as st

NOW = datetime(2026, 9, 10, 12, 0, 0)


def _status(age_s: float, **fields) -> dict:
    ts = (NOW - timedelta(seconds=age_s)).strftime("%Y-%m-%dT%H:%M:%S")
    return {"ts": ts, "pid": 4242, "phase": "playing", **fields}


def test_heartbeat_age() -> None:
    assert st.heartbeat_age_s(_status(12), NOW) == pytest.approx(12.0)
    assert st.heartbeat_age_s(None, NOW) is None
    assert st.heartbeat_age_s({"pid": 1}, NOW) is None
    assert st.heartbeat_age_s({"ts": "garbage"}, NOW) is None


@pytest.mark.parametrize(
    "status, alive, expected",
    [
        (_status(10), True, st.Health.HEALTHY),
        (_status(239.9), True, st.Health.HEALTHY),
        (_status(240), True, st.Health.STALE),
        (_status(9999), True, st.Health.STALE),
        (None, True, st.Health.STALE),
        (_status(10), False, st.Health.DEAD),
        (None, False, st.Health.DEAD),
    ],
)
def test_classify(status, alive, expected) -> None:
    assert st.classify(status, alive, NOW) == expected


def _derive(**kw):
    base = dict(
        health=st.Health.DEAD,
        desired="run",
        desired_reason="session",
        desired_until=None,
        stop_pending=False,
        booting=False,
        offline_until=None,
        status=None,
    )
    base.update(kw)
    return st.derive_state(**base)


def test_farming_when_alive_and_wanted() -> None:
    until = NOW + timedelta(minutes=30)
    assert _derive(health=st.Health.HEALTHY, desired_until=until, status=_status(5)) == (
        st.InstanceState.FARMING,
        until,
    )
    assert _derive(health=st.Health.STALE, status=_status(300))[0] == st.InstanceState.FARMING


def test_stopping_beats_everything_while_alive() -> None:
    deadline = NOW + timedelta(seconds=110)
    assert _derive(
        health=st.Health.HEALTHY, stop_pending=deadline, status=_status(5, recovery_attempts=2)
    ) == (st.InstanceState.STOPPING, deadline)


def test_reconnecting_when_alive_and_recovering() -> None:
    assert _derive(health=st.Health.HEALTHY, status=_status(5, recovery_attempts=1))[0] == (
        st.InstanceState.RECONNECTING
    )
    assert _derive(health=st.Health.HEALTHY, status=_status(5, disconnect_count=3))[0] == (
        st.InstanceState.RECONNECTING
    )
    assert _derive(health=st.Health.HEALTHY, status=_status(5, recovery_attempts=0))[0] == (
        st.InstanceState.FARMING
    )


def test_offline_wins_over_break_and_run_when_dead() -> None:
    retry = NOW + timedelta(minutes=4)
    assert _derive(offline_until=retry) == (st.InstanceState.OFFLINE, retry)
    assert _derive(offline_until=retry, desired="stop", desired_reason="gap") == (
        st.InstanceState.OFFLINE,
        retry,
    )


def test_starting_while_booting_or_awaiting_launch() -> None:
    assert _derive(booting=True) == (st.InstanceState.STARTING, None)
    assert _derive(desired="run") == (st.InstanceState.STARTING, None)


def test_scheduled_break_and_stopped() -> None:
    resume = NOW + timedelta(hours=1)
    assert _derive(desired="stop", desired_reason="gap", desired_until=resume) == (
        st.InstanceState.SCHEDULED_BREAK,
        resume,
    )
    assert _derive(desired="stop", desired_reason="override_stop", desired_until=resume) == (
        st.InstanceState.STOPPED,
        None,
    )


def test_instance_view_is_frozen() -> None:
    view = st.InstanceView(
        name="Pie64", adb_port=5555, state=st.InstanceState.STOPPED, health=st.Health.DEAD,
        pid=None, heartbeat_age_s=None, phase=None, desired="stop", desired_reason="override_stop",
        until=None, games_played=None, farm_brawler=None, note="",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        view.name = "x"  # type: ignore[misc]
```

`tests/test_supervisor_backoff.py`:

```python
"""Offline backoff: 2, 4, 8, 16, then 30 minutes (and 30 thereafter); clear resets."""

from __future__ import annotations

from datetime import datetime, timedelta

from brawlfarm.supervisor.backoff import BACKOFF_MINUTES, OfflineBackoff

NOW = datetime(2026, 9, 10, 12, 0, 0)


def test_sequence_caps_at_thirty() -> None:
    b = OfflineBackoff()
    waits = [(b.record_miss("a", NOW) - NOW) for _ in range(7)]
    assert [w.total_seconds() / 60 for w in waits] == [2, 4, 8, 16, 30, 30, 30]
    assert BACKOFF_MINUTES == (2, 4, 8, 16, 30)
    assert b.misses("a") == 7


def test_until_and_expiry() -> None:
    b = OfflineBackoff()
    assert b.until("a", NOW) is None
    b.record_miss("a", NOW)
    assert b.until("a", NOW + timedelta(minutes=1)) == NOW + timedelta(minutes=2)
    assert b.until("a", NOW + timedelta(minutes=2)) is None  # expired: probe again
    assert b.misses("a") == 1  # expiry does not forget the miss count


def test_clear_is_per_instance_and_clear_all() -> None:
    b = OfflineBackoff()
    b.record_miss("a", NOW)
    b.record_miss("b", NOW)
    b.clear("a")
    assert b.misses("a") == 0 and b.until("a", NOW) is None
    assert b.misses("b") == 1
    b.clear_all()
    assert b.misses("b") == 0
```

`tests/test_supervisor_process.py`:

```python
"""PID liveness, the worker command-line guard, kill by PID, and launching a worker
subprocess with the env it needs. Uses real short-lived subprocesses."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from brawlfarm.supervisor import process as P

SLEEPER = "import time; time.sleep(60)"


@pytest.fixture()
def sleeper():
    proc = subprocess.Popen([sys.executable, "-c", SLEEPER, P.WORKER_MODULE])
    yield proc
    if proc.poll() is None:
        proc.kill()
        proc.wait(5)


@pytest.fixture()
def bystander():
    proc = subprocess.Popen([sys.executable, "-c", SLEEPER])
    yield proc
    if proc.poll() is None:
        proc.kill()
        proc.wait(5)


def test_pid_alive(sleeper) -> None:
    assert P.pid_alive(sleeper.pid) is True
    sleeper.kill()
    sleeper.wait(5)
    assert P.pid_alive(sleeper.pid) is False
    assert P.pid_alive(0) is False
    assert P.pid_alive(-5) is False


def test_is_worker_guard(sleeper, bystander) -> None:
    assert P.is_worker(sleeper.pid) is True
    assert P.is_worker(bystander.pid) is False
    assert P.is_worker(os.getpid()) is False


def test_kill_worker_refuses_non_workers(sleeper, bystander) -> None:
    lines: list[str] = []
    assert P.kill_worker(bystander.pid, log=lines.append) is False
    assert bystander.poll() is None
    assert any("refus" in line for line in lines)
    assert P.kill_worker(sleeper.pid, log=lines.append) is True
    sleeper.wait(5)
    assert sleeper.poll() is not None
    assert P.kill_worker(sleeper.pid, log=lines.append) is False  # already gone


def test_launch_worker_passes_env_and_logs(tmp_path: Path) -> None:
    env = {**os.environ, "BRAWL_TEST_MARK": "hello"}
    log_dir = tmp_path / "logs"
    proc = P.launch_worker(
        ["-c", "import os,sys; print(os.environ['BRAWL_TEST_MARK']); print('err', file=sys.stderr)"],
        env,
        log_dir,
        "Pie64",
        module=None,
    )
    proc.wait(30)
    assert proc.returncode == 0
    assert (log_dir / "Pie64.out.log").read_text(encoding="utf-8").strip() == "hello"
    assert (log_dir / "Pie64.err.log").read_text(encoding="utf-8").strip() == "err"


def test_launch_worker_default_module_is_the_worker(tmp_path: Path) -> None:
    env = {**os.environ, "BRAWLFARM_HOME": str(tmp_path)}
    proc = P.launch_worker(["--help"], env, tmp_path / "logs", "Pie64")
    proc.wait(60)
    assert proc.returncode == 0
    assert "--max-minutes" in (tmp_path / "logs" / "Pie64.out.log").read_text(encoding="utf-8")


def test_instance_online_parses_adb_output(tmp_path: Path) -> None:
    fake = tmp_path / "adb.py"
    fake.write_text(
        "import sys\n"
        "if sys.argv[1] == 'connect': print('connected to 127.0.0.1:5555')\n"
        "else: print('List of devices attached\\n127.0.0.1:5555\\tdevice\\n127.0.0.1:5565\\toffline\\n')\n",
        encoding="utf-8",
    )
    assert P.instance_online(str(fake), 5555, runner=P._python_runner) is True
    assert P.instance_online(str(fake), 5565, runner=P._python_runner) is False
    assert P.instance_online(str(fake), 5575, runner=P._python_runner) is False


def test_instance_online_fails_open_on_probe_errors(tmp_path: Path) -> None:
    assert P.instance_online(str(tmp_path / "missing-adb.exe"), 5555) is True
    slow = tmp_path / "slow.py"
    slow.write_text("import time; time.sleep(5)", encoding="utf-8")
    t0 = time.monotonic()
    assert P.instance_online(str(slow), 5555, timeout_s=0.5, runner=P._python_runner) is True
    assert time.monotonic() - t0 < 4
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_supervisor_state.py tests/test_supervisor_backoff.py tests/test_supervisor_process.py -q
```

Expected: `ModuleNotFoundError: No module named 'brawlfarm.supervisor'`.

- [ ] **Step 3: Write `brawlfarm/supervisor/__init__.py` and `state.py`**

`brawlfarm/supervisor/__init__.py`:

```python
"""The supervisor: one tick a minute launches, watches, stops and kills one worker per
instance (ported from the legacy PowerShell watchdog). Task 5 adds the Supervisor class."""
```

`brawlfarm/supervisor/state.py`:

```python
"""Pure classification: heartbeat health from status.json, and the one instance state the
control panel shows everywhere (spec section 6). No I/O here; the loop feeds it facts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

STALE_S = 240.0  # heartbeat older than this while the PID is alive = stale
_TS_FMT = "%Y-%m-%dT%H:%M:%S"


class Health(StrEnum):
    HEALTHY = "healthy"
    STALE = "stale"
    DEAD = "dead"


class InstanceState(StrEnum):
    FARMING = "farming"
    STOPPED = "stopped"
    SCHEDULED_BREAK = "scheduled_break"
    RECONNECTING = "reconnecting"
    OFFLINE = "offline"
    STARTING = "starting"
    STOPPING = "stopping"


@dataclass(frozen=True)
class InstanceView:
    """Everything the panel needs about one instance, derived once per tick."""

    name: str
    adb_port: int
    state: InstanceState
    health: Health
    pid: int | None
    heartbeat_age_s: float | None
    phase: str | None
    desired: str  # "run" | "stop"
    desired_reason: str | None
    until: datetime | None  # session end, resume time, retry time or stop deadline
    games_played: int | None
    farm_brawler: str | None
    note: str  # one plain sentence for the card, "" when nothing to say


def parse_ts(ts: str) -> datetime | None:
    try:
        return datetime.strptime(ts, _TS_FMT)
    except (TypeError, ValueError):
        return None


def heartbeat_age_s(status: dict | None, now: datetime) -> float | None:
    if not status:
        return None
    stamped = parse_ts(str(status.get("ts", "")))
    if stamped is None:
        return None
    return (now - stamped).total_seconds()


def classify(status: dict | None, alive: bool, now: datetime) -> Health:
    """DEAD when the PID is gone; STALE when alive but the heartbeat is old or missing."""
    if not alive:
        return Health.DEAD
    age = heartbeat_age_s(status, now)
    if age is None or age >= STALE_S:
        return Health.STALE
    return Health.HEALTHY


def derive_state(
    *,
    health: Health,
    desired: str,
    desired_reason: str | None,
    desired_until: datetime | None,
    stop_pending: datetime | None | bool,
    booting: bool,
    offline_until: datetime | None,
    status: dict | None,
) -> tuple[InstanceState, datetime | None]:
    """Fold the tick's facts into one state plus the time the panel shows with it.

    ``stop_pending`` is the kill deadline when a graceful stop is in flight (or a bool
    for callers without one). Precedence, alive: stopping > reconnecting > farming.
    Dead: offline > starting > scheduled break / stopped.
    """
    alive = health in (Health.HEALTHY, Health.STALE)
    if alive:
        if stop_pending:
            return InstanceState.STOPPING, (stop_pending if isinstance(stop_pending, datetime) else None)
        s = status or {}
        if int(s.get("recovery_attempts") or 0) > 0 or int(s.get("disconnect_count") or 0) > 0:
            return InstanceState.RECONNECTING, None
        return InstanceState.FARMING, desired_until
    if offline_until is not None:
        return InstanceState.OFFLINE, offline_until
    if booting or desired == "run":
        return InstanceState.STARTING, None
    if desired_reason == "override_stop":
        return InstanceState.STOPPED, None
    return InstanceState.SCHEDULED_BREAK, desired_until
```

- [ ] **Step 4: Write `brawlfarm/supervisor/backoff.py`**

```python
"""Offline backoff for instances whose adb probe fails (BlueStacks window closed): wait
2, 4, 8, 16, then 30 minutes between relaunch attempts. In memory only, like the legacy
watchdog; a supervisor restart simply probes again."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

BACKOFF_MINUTES = (2, 4, 8, 16, 30)


@dataclass
class _Entry:
    misses: int = 0
    until: datetime | None = None


@dataclass
class OfflineBackoff:
    _entries: dict[str, _Entry] = field(default_factory=dict)

    def record_miss(self, name: str, now: datetime) -> datetime:
        e = self._entries.setdefault(name, _Entry())
        e.misses += 1
        minutes = BACKOFF_MINUTES[min(e.misses, len(BACKOFF_MINUTES)) - 1]
        e.until = now + timedelta(minutes=minutes)
        return e.until

    def until(self, name: str, now: datetime) -> datetime | None:
        e = self._entries.get(name)
        if e is None or e.until is None or e.until <= now:
            return None
        return e.until

    def misses(self, name: str) -> int:
        e = self._entries.get(name)
        return e.misses if e else 0

    def clear(self, name: str) -> None:
        self._entries.pop(name, None)

    def clear_all(self) -> None:
        self._entries.clear()
```

- [ ] **Step 5: Write `brawlfarm/supervisor/process.py`**

```python
"""Process plumbing for the supervisor: PID liveness, the worker command-line guard,
kill by PID, launching a worker with its env, and the adb online probe.

Safety rail: a worker is only ever killed by the PID read from its own status.json,
never found by name. kill_worker() additionally refuses a PID whose command line does
not run brawlfarm.worker, so a reused PID can never be killed by mistake.
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import psutil

WORKER_MODULE = "brawlfarm.worker"
_DEVICE_LINE = re.compile(r"^127\.0\.0\.1:(\d+)\s+device\s*$")

Runner = Callable[[list[str], float], str]


def pid_alive(pid: int) -> bool:
    if pid is None or pid <= 0:
        return False
    try:
        p = psutil.Process(pid)
        return p.is_running() and p.status() != psutil.STATUS_ZOMBIE
    except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError):
        return False


def is_worker(pid: int) -> bool:
    """True when the PID's command line runs brawlfarm.worker (``-m brawlfarm.worker`` or
    the module path). AccessDenied counts as "not ours"."""
    try:
        argv = psutil.Process(pid).cmdline()
    except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError):
        return False
    tail = WORKER_MODULE.replace(".", "/") + ".py"
    return any(a == WORKER_MODULE or a.replace("\\", "/").endswith(tail) for a in argv)


def kill_worker(pid: int, log: Callable[[str], None] = print) -> bool:
    """Kill by PID. Returns False (and logs why) when the PID is gone or is not a worker."""
    if not pid_alive(pid):
        log(f"kill {pid}: not running")
        return False
    if not is_worker(pid):
        log(f"kill {pid}: refused, command line is not {WORKER_MODULE}")
        return False
    try:
        p = psutil.Process(pid)
        p.kill()
        p.wait(timeout=10)
    except psutil.NoSuchProcess:
        pass
    except psutil.Error as exc:
        log(f"kill {pid}: failed: {exc}")
        return False
    return True


def launch_worker(
    args: list[str],
    env: dict[str, str],
    log_dir: Path,
    name: str,
    module: str | None = WORKER_MODULE,
) -> subprocess.Popen:
    """Start ``python -m brawlfarm.worker <args>`` with ``env``, hidden, stdout and stderr
    appended to <log_dir>/<name>.out.log and .err.log. ``module=None`` runs python with
    ``args`` directly (tests)."""
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable]
    if module:
        cmd += ["-m", module]
    cmd += list(args)
    out = open(log_dir / f"{name}.out.log", "ab")  # handed to the child, closed below
    err = open(log_dir / f"{name}.err.log", "ab")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        return subprocess.Popen(cmd, env=env, stdout=out, stderr=err, creationflags=flags)
    finally:
        out.close()
        err.close()


def _default_runner(cmd: list[str], timeout_s: float) -> str:
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout_s, check=False
    ).stdout


def _python_runner(cmd: list[str], timeout_s: float) -> str:
    """Test hook: run a .py stand-in for HD-Adb.exe through the interpreter."""
    return _default_runner([sys.executable, *cmd], timeout_s)


def instance_online(
    adb_path: str, port: int, timeout_s: float = 15.0, runner: Runner = _default_runner
) -> bool:
    """adb connect, then adb devices; online only when the row for this port says
    ``device``. Fails OPEN (True) on a missing adb, a timeout or any other probe error,
    so a broken probe never strands an instance in backoff."""
    serial = f"127.0.0.1:{int(port)}"
    if not Path(adb_path).exists():
        return True
    try:
        runner([adb_path, "connect", serial], timeout_s)
        out = runner([adb_path, "devices"], timeout_s)
    except (subprocess.TimeoutExpired, OSError, subprocess.SubprocessError):
        return True
    if not out.strip():
        return True
    for line in out.splitlines():
        m = _DEVICE_LINE.match(line.strip())
        if m and int(m.group(1)) == int(port):
            return True
    return False
```

- [ ] **Step 6: Run the tests until green**

```bash
uv run pytest tests/test_supervisor_state.py tests/test_supervisor_backoff.py tests/test_supervisor_process.py -q
```

Expected: all pass. If `is_worker` fails for the sleeper fixture on Windows, print `psutil.Process(pid).cmdline()` in a scratch script to see the exact argv shape and adjust the match, keeping the "exact module name or path ending in brawlfarm/worker.py" rule.

- [ ] **Step 7: Lint, scrub, commit**

```bash
uv run ruff format brawlfarm/supervisor tests/test_supervisor_state.py tests/test_supervisor_backoff.py tests/test_supervisor_process.py
uv run ruff check . && uv run ruff format --check .
uv run python tools/scrub_check.py
git add brawlfarm/supervisor tests/test_supervisor_state.py tests/test_supervisor_backoff.py tests/test_supervisor_process.py
git commit -m "feat(supervisor): state derivation, offline backoff and process plumbing

Pure heartbeat classification and the derived instance state, the 2/4/8/16/30
minute backoff, and PID-only process control with a command-line guard so a
reused PID is never killed by mistake."
```

---

### Task 5: The supervisor loop (`loop.py`)

**Files:**
- Create: `brawlfarm/supervisor/loop.py`
- Modify: `brawlfarm/supervisor/__init__.py` (re-export)
- Create: `tests/test_supervisor_loop.py`

**Interfaces:**
- Consumes: `settings.load/instance_dir/instances_table/worker_env/worker_args`, `config.set_home/set_instances`, `scheduler.tick/sched_desired/write_override/clear_override/set_default_enabled`, `status.read_status`, `notify.configure/maybe_alert`, `events.refresh`, everything from Task 4.
- Produces (`brawlfarm.supervisor.loop`): constants `TICK_S = 60.0`, `BOOT_GRACE_S = 180.0`, `STOP_ESCALATE_S = 110.0`, `ALERT_AFTER_MISSES = 3`, `STOP_OVERRIDE_DAYS = 365`, `STOP_FLAG = "stop.flag"`; `class Supervisor` with `__init__(self, settings: AppSettings, home: Path, *, clock=datetime.now, probe=process.instance_online, launcher=process.launch_worker, alive=process.pid_alive, killer=process.kill_worker, sleep=time.sleep, events_refresh=events.refresh, interval_s: float = TICK_S)`; `tick(self) -> list[InstanceView]`; `views(self) -> list[InstanceView]` (last tick); `subscribe(self, cb: Callable[[InstanceView], None]) -> None` (called when an instance's `state` changes); controls `start(name, hours: float | None = None)`, `stop(name)`, `stop_now(name) -> bool`, `restart(name)`, `retry_now(name)`, `poke()`; `async run_forever(self) -> None`, `request_shutdown(self) -> None`. `brawlfarm.supervisor` re-exports `Supervisor`, `InstanceView`, `InstanceState`, `Health`.
- Consumed by: Task 6 (CLI), phase 3 (API).

- [ ] **Step 1: Write the failing tests**

`tests/test_supervisor_loop.py`:

```python
"""The supervisor tick against a temp home with fake process plumbing: launches one
worker per tick with the settings env, stops gracefully then kills after 110 s, honours
boot grace and offline backoff, and exposes start / stop / stop-now / restart / retry."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from brawlfarm import settings as S
from brawlfarm.core import scheduler, status
from brawlfarm.supervisor import Health, InstanceState, Supervisor
from brawlfarm.supervisor import loop as L

T0 = datetime(2026, 9, 10, 12, 0, 0)


@dataclass
class FakeProc:
    pid: int
    exited: bool = False

    def poll(self):
        return 0 if self.exited else None


@dataclass
class World:
    now: datetime = T0
    online: dict[int, bool] = field(default_factory=dict)
    alive: set[int] = field(default_factory=set)
    launches: list[tuple[list[str], dict[str, str], str]] = field(default_factory=list)
    kills: list[int] = field(default_factory=list)
    procs: list[FakeProc] = field(default_factory=list)
    refreshes: int = 0
    next_pid: int = 100

    def clock(self):
        return self.now

    def probe(self, adb_path, port, timeout_s=15.0):
        return self.online.get(port, True)

    def launcher(self, args, env, log_dir, name, module=None):
        self.launches.append((list(args), dict(env), name))
        proc = FakeProc(self.next_pid)
        self.next_pid += 1
        self.alive.add(proc.pid)
        self.procs.append(proc)
        return proc

    def is_alive(self, pid):
        return pid in self.alive

    def kill(self, pid, log=print):
        if pid in self.alive:
            self.alive.discard(pid)
            self.kills.append(pid)
            return True
        return False

    def refresh(self, now=None):
        self.refreshes += 1
        return 0


_PORTS = {"Pie64": 5555, "Rome64": 5565}
_TAGS = {"Pie64": "#2P0YLQ9", "Rome64": ""}


def _settings(names=("Pie64", "Rome64")) -> S.AppSettings:
    s = S.AppSettings(
        instances=[
            S.InstanceSettings(name=n, adb_port=_PORTS[n], player_tag=_TAGS[n]) for n in names
        ]
    )
    s.connection.brawl_api_token = "tok"  # the events refresh only runs with a token
    return s


def make_sup(tmp_path: Path, world: World, names=("Pie64", "Rome64")) -> Supervisor:
    s = _settings(names)
    S.save(s, tmp_path)
    sup = Supervisor(
        s,
        tmp_path,
        clock=world.clock,
        probe=world.probe,
        launcher=world.launcher,
        alive=world.is_alive,
        killer=world.kill,
        sleep=lambda _s: None,
        events_refresh=world.refresh,
    )
    # Schedule off = legacy always-run, so tests control "desired" through overrides.
    scheduler.set_enabled(list(names), False)
    return sup


@pytest.fixture()
def world() -> World:
    return World()


@pytest.fixture()
def sup(tmp_path: Path, world: World) -> Supervisor:
    return make_sup(tmp_path, world)


def _heartbeat(tmp_path: Path, name: str, pid: int, now: datetime, age_s: float = 5, **fields):
    d = S.instance_dir(tmp_path, name)
    d.mkdir(parents=True, exist_ok=True)
    ts = (now - timedelta(seconds=age_s)).strftime("%Y-%m-%dT%H:%M:%S")
    status.write_status(d, {"pid": pid, "phase": "playing", "games_played": 3, **fields})
    # write_status stamps "now"; rewrite ts to the age we want
    import json

    p = d / "status.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    data["ts"] = ts
    p.write_text(json.dumps(data), encoding="utf-8")


def _view(views, name):
    return next(v for v in views if v.name == name)


def test_init_points_the_core_at_home(sup: Supervisor, tmp_path: Path) -> None:
    from brawlfarm.core import config

    assert config.HOME_DIR == tmp_path.resolve()
    assert set(config.INSTANCES) == {"Pie64", "Rome64"}
    assert config.INSTANCES["Pie64"]["data"] == "instances/Pie64"


def test_first_tick_launches_one_worker_and_defers_the_rest(sup, world, tmp_path) -> None:
    views = sup.tick()
    assert len(world.launches) == 1
    args, env, name = world.launches[0]
    assert name == "Pie64"
    assert args == ["--select-brawler", "--dnd"]
    assert env["BRAWL_ADB_PORT"] == "5555"
    assert env["BRAWL_DATA_DIR"] == "instances/Pie64"
    assert env["BRAWLFARM_HOME"] == str(tmp_path.resolve())
    assert "SystemRoot" in env or "PATH" in env  # inherits the parent environment
    assert _view(views, "Pie64").state == InstanceState.STARTING
    assert _view(views, "Rome64").state == InstanceState.STARTING
    assert _view(views, "Rome64").note == "Waiting for its turn to start"
    assert world.refreshes == 1
    world.now += timedelta(seconds=60)
    sup.tick()
    assert [n for _, _, n in world.launches] == ["Pie64", "Rome64"]


def test_boot_grace_prevents_double_launch(sup, world) -> None:
    sup.tick()
    world.now += timedelta(seconds=60)
    sup.tick()
    world.now += timedelta(seconds=60)  # 120 s after Pie64's launch, still no heartbeat
    views = sup.tick()
    assert [n for _, _, n in world.launches] == ["Pie64", "Rome64"]
    assert _view(views, "Pie64").state == InstanceState.STARTING
    world.now += timedelta(seconds=120)  # 240 s: grace over, still dead -> relaunch
    sup.tick()
    assert [n for _, _, n in world.launches] == ["Pie64", "Rome64", "Pie64"]


def test_healthy_worker_is_farming_and_left_alone(sup, world, tmp_path) -> None:
    world.alive.add(4242)
    _heartbeat(tmp_path, "Pie64", 4242, world.now, farm_brawler="Shelly")
    views = sup.tick()
    v = _view(views, "Pie64")
    assert v.state == InstanceState.FARMING
    assert v.health == Health.HEALTHY
    assert v.pid == 4242
    assert v.games_played == 3
    assert v.farm_brawler == "Shelly"
    assert [n for _, _, n in world.launches] == ["Rome64"]


def test_stale_worker_is_killed_then_relaunched(sup, world, tmp_path) -> None:
    world.alive.add(4242)
    _heartbeat(tmp_path, "Pie64", 4242, world.now, age_s=500)
    sup.tick()
    assert world.kills == [4242]
    assert [n for _, _, n in world.launches] == ["Pie64"]


def test_graceful_stop_then_kill_after_escalation(sup, world, tmp_path) -> None:
    world.alive.add(4242)
    _heartbeat(tmp_path, "Pie64", 4242, world.now)
    sup.stop("Pie64")
    flag = S.instance_dir(tmp_path, "Pie64") / "stop.flag"
    assert flag.exists()
    views = sup.tick()
    v = _view(views, "Pie64")
    assert v.state == InstanceState.STOPPING
    assert v.until == world.now + timedelta(seconds=110)
    assert world.kills == []
    world.now += timedelta(seconds=60)
    _heartbeat(tmp_path, "Pie64", 4242, world.now)
    sup.tick()
    assert world.kills == []
    world.now += timedelta(seconds=60)
    _heartbeat(tmp_path, "Pie64", 4242, world.now)
    views = sup.tick()
    assert world.kills == [4242]
    assert _view(views, "Pie64").state == InstanceState.STOPPED  # killed this tick
    assert _view(views, "Pie64").pid is None
    world.now += timedelta(seconds=60)
    views = sup.tick()
    assert _view(views, "Pie64").state == InstanceState.STOPPED
    assert [n for _, _, n in world.launches] == ["Rome64"]  # never relaunched while stopped


def test_undo_stop_is_start(sup, world, tmp_path) -> None:
    world.alive.add(4242)
    _heartbeat(tmp_path, "Pie64", 4242, world.now)
    sup.stop("Pie64")
    sup.start("Pie64")
    assert not (S.instance_dir(tmp_path, "Pie64") / "stop.flag").exists()
    views = sup.tick()
    assert _view(views, "Pie64").state == InstanceState.FARMING
    assert world.kills == []


def test_stop_now_only_while_pending(sup, world, tmp_path) -> None:
    world.alive.add(4242)
    _heartbeat(tmp_path, "Pie64", 4242, world.now)
    assert sup.stop_now("Pie64") is False
    assert world.kills == []
    sup.stop("Pie64")
    assert sup.stop_now("Pie64") is True
    assert world.kills == [4242]


def test_restart_stops_then_relaunches(sup, world, tmp_path) -> None:
    world.alive.add(4242)
    _heartbeat(tmp_path, "Pie64", 4242, world.now)
    sup.tick()
    sup.restart("Pie64")
    flag = S.instance_dir(tmp_path, "Pie64") / "stop.flag"
    assert flag.exists()
    views = sup.tick()
    assert _view(views, "Pie64").state == InstanceState.STOPPING
    world.alive.discard(4242)  # the worker exited at the menu
    world.now += timedelta(seconds=60)
    views = sup.tick()
    assert [n for _, _, n in world.launches] == ["Rome64", "Pie64"]
    assert _view(views, "Pie64").state == InstanceState.STARTING


def test_offline_backoff_and_alert(tmp_path, world, monkeypatch) -> None:
    sup = make_sup(tmp_path, world, ("Pie64",))  # one instance, so nothing else launches
    alerts: list[tuple[str, dict]] = []
    monkeypatch.setattr(L.notify, "maybe_alert", lambda kind, fields: alerts.append((kind, fields)))
    world.online[5555] = False
    views = sup.tick()
    v = _view(views, "Pie64")
    assert v.state == InstanceState.OFFLINE
    assert v.until == world.now + timedelta(minutes=2)
    assert v.note == "BlueStacks window not found. Retrying in 2 min."
    assert world.launches == []
    world.now += timedelta(minutes=1)
    sup.tick()  # still inside the 2 min window: no probe, no launch
    assert world.launches == []
    world.now += timedelta(minutes=1)
    sup.tick()  # miss 2 -> 4 min
    world.now += timedelta(minutes=4)
    sup.tick()  # miss 3 -> 8 min, alert
    assert alerts == [("offline", {"instance": "Pie64", "misses": 3})]
    assert world.launches == []
    sup.retry_now("Pie64")
    world.online[5555] = True
    views = sup.tick()
    assert [n for _, _, n in world.launches] == ["Pie64"]
    assert _view(views, "Pie64").state == InstanceState.STARTING


def test_events_refresh_only_with_a_token(tmp_path, world) -> None:
    sup = make_sup(tmp_path, world, ("Pie64",))
    sup.settings.connection.brawl_api_token = ""
    sup.apply_settings(sup.settings)
    sup.tick()
    assert world.refreshes == 0


def test_scheduled_break_and_run_for_hours(sup, world, tmp_path) -> None:
    scheduler.write_override("Pie64", "stop", world.now + timedelta(hours=2))
    views = sup.tick()
    assert _view(views, "Pie64").state == InstanceState.STOPPED
    sup.start("Pie64", hours=1.5)
    views = sup.tick()
    assert _view(views, "Pie64").state == InstanceState.STARTING
    assert world.launches[-1][0] == ["--select-brawler", "--dnd", "--max-minutes", "90"]


def test_state_change_callbacks(sup, world, tmp_path) -> None:
    seen: list[tuple[str, str]] = []
    sup.subscribe(lambda v: seen.append((v.name, v.state)))
    sup.tick()
    world.now += timedelta(seconds=60)
    sup.tick()
    assert seen == [("Pie64", "starting"), ("Rome64", "starting")]
    world.alive.add(7)
    _heartbeat(tmp_path, "Pie64", 7, world.now)
    sup.tick()
    assert seen[-1] == ("Pie64", "farming")


def test_desired_stop_from_scheduler_writes_flag_without_user_action(sup, world, tmp_path) -> None:
    world.alive.add(4242)
    _heartbeat(tmp_path, "Pie64", 4242, world.now)
    scheduler.write_override("Pie64", "stop", world.now + timedelta(hours=1))
    views = sup.tick()
    assert (S.instance_dir(tmp_path, "Pie64") / "stop.flag").exists()
    assert _view(views, "Pie64").state == InstanceState.STOPPING


@pytest.mark.asyncio
async def test_run_forever_ticks_and_shuts_down(sup, world) -> None:
    import asyncio

    sup.interval_s = 0.05
    task = asyncio.create_task(sup.run_forever())
    await asyncio.sleep(0.2)
    sup.poke()
    await asyncio.sleep(0.05)
    sup.request_shutdown()
    await asyncio.wait_for(task, 2)
    assert world.launches  # at least one tick ran
```

Add `pytest-asyncio>=0.24` to the `dev` dependency group in `pyproject.toml` and, under `[tool.pytest.ini_options]`, set `asyncio_mode = "strict"` and `asyncio_default_fixture_loop_scope = "function"` (the one async test is marked explicitly; the loop-scope line keeps pytest-asyncio from printing its configuration warning). Run `uv sync --group dev`.

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_supervisor_loop.py -q
```

Expected: `ImportError: cannot import name 'Supervisor' from 'brawlfarm.supervisor'`.

- [ ] **Step 3: Write `brawlfarm/supervisor/loop.py`**

```python
"""The supervisor tick and its controls (spec section 6), ported from the legacy
PowerShell watchdog.

One tick: scheduler tick for every instance; then per instance read status.json,
classify the heartbeat, read the scheduler's desired state, and act: desired stop and
alive -> write stop.flag, kill by PID after STOP_ESCALATE_S; desired run and unhealthy
-> probe adb (offline backoff), kill a stale PID, launch (one launch per tick).
Everything the panel shows is derived here once per tick into InstanceView objects.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path

from brawlfarm import settings as S
from brawlfarm.core import config, events, notify, scheduler, status
from brawlfarm.supervisor import process
from brawlfarm.supervisor.backoff import OfflineBackoff
from brawlfarm.supervisor.state import Health, InstanceState, InstanceView, classify, derive_state, heartbeat_age_s

log = logging.getLogger("brawlfarm.supervisor")

TICK_S = 60.0
BOOT_GRACE_S = 180.0  # after a launch, do not relaunch before the worker can heartbeat
STOP_ESCALATE_S = 110.0  # graceful stop.flag first, kill by PID after this
ALERT_AFTER_MISSES = 3
STOP_OVERRIDE_DAYS = 365  # "stopped until you start it again"
STOP_FLAG = "stop.flag"


class Supervisor:
    def __init__(
        self,
        settings: S.AppSettings,
        home: Path,
        *,
        clock: Callable[[], datetime] = datetime.now,
        probe: Callable[..., bool] = process.instance_online,
        launcher: Callable[..., object] = process.launch_worker,
        alive: Callable[[int], bool] = process.pid_alive,
        killer: Callable[..., bool] = process.kill_worker,
        sleep: Callable[[float], None] = time.sleep,
        events_refresh: Callable[..., int] = events.refresh,
        interval_s: float = TICK_S,
    ) -> None:
        self.settings = settings
        self.home = Path(home).resolve()
        self.interval_s = interval_s
        self._clock, self._probe, self._launch = clock, probe, launcher
        self._alive, self._kill, self._sleep, self._refresh = alive, killer, sleep, events_refresh
        self._backoff = OfflineBackoff()
        self._stop_asked: dict[str, datetime] = {}
        self._launched_at: dict[str, datetime] = {}
        self._procs: dict[str, object] = {}
        self._views: dict[str, InstanceView] = {}
        self._listeners: list[Callable[[InstanceView], None]] = []
        self._poke: asyncio.Event | None = None
        self._shutdown = False
        self.apply_settings(settings)

    # --- wiring -----------------------------------------------------------------------

    def apply_settings(self, settings: S.AppSettings) -> None:
        """Point the core at the home directory and the instance table; safe to call again
        after the user edits settings (phase 5)."""
        self.settings = settings
        config.set_home(self.home)
        config.set_instances(S.instances_table(settings))
        config.API_TOKEN = settings.connection.brawl_api_token or config.API_TOKEN
        scheduler.set_default_enabled(settings.scheduler.default_enabled)
        n = settings.notifications
        notify.configure(
            webhook_url=n.webhook_url,
            ntfy_server=n.ntfy_server,
            ntfy_topic=n.ntfy_topic,
            events=list(n.events),
        )

    def views(self) -> list[InstanceView]:
        return [self._views[i.name] for i in self.settings.instances if i.name in self._views]

    def subscribe(self, cb: Callable[[InstanceView], None]) -> None:
        self._listeners.append(cb)

    def _dir(self, name: str) -> Path:
        return S.instance_dir(self.home, name)

    def _flag(self, name: str) -> Path:
        return self._dir(name) / STOP_FLAG

    # --- the tick ---------------------------------------------------------------------

    def tick(self) -> list[InstanceView]:
        now = self._clock()
        rc = scheduler.tick(now)
        if rc != 0:
            log.warning("scheduler tick failed (rc=%s); fail open to always-run", rc)
        if self.settings.connection.brawl_api_token:  # the rotation fetch needs the API
            try:
                self._refresh(now)
            except Exception as exc:  # best effort, never blocks the tick
                log.debug("events refresh failed: %s", exc)
        launched_this_tick = False
        out: list[InstanceView] = []
        for inst in self.settings.instances:
            view, launched = self._tick_instance(inst, now, launched_this_tick)
            launched_this_tick = launched_this_tick or launched
            out.append(view)
            previous = self._views.get(inst.name)
            self._views[inst.name] = view
            if previous is None or previous.state != view.state:
                for cb in self._listeners:
                    try:
                        cb(view)
                    except Exception as exc:
                        log.debug("listener failed: %s", exc)
        log.info("tick: %s", ", ".join(f"{v.name}={v.state}" for v in out) or "no instances")
        return out

    def _tick_instance(
        self, inst: S.InstanceSettings, now: datetime, launched_this_tick: bool
    ) -> tuple[InstanceView, bool]:
        name = inst.name
        st = status.read_status(self._dir(name))
        pid = int(st["pid"]) if st and st.get("pid") else None
        alive = pid is not None and self._alive(pid)
        health = classify(st, alive, now)
        desired = scheduler.sched_desired(name, now)
        want = (desired or {}).get("state", "run")
        reason = (desired or {}).get("reason")
        until = _parse_until((desired or {}).get("until"))
        note = ""
        launched = False

        if want == "stop":
            self._backoff.clear(name)
            if alive:
                self._request_stop(name, now)
                if self._maybe_escalate(name, pid, now):
                    alive, health = False, Health.DEAD
            else:
                self._stop_asked.pop(name, None)
        else:
            if health == Health.HEALTHY:
                self._backoff.clear(name)
                if self._maybe_escalate(name, pid, now):  # a restart in flight
                    alive, health = False, Health.DEAD
            elif self._booting(name, now):
                note = "Starting; waiting for the first heartbeat"
            elif (retry := self._backoff.until(name, now)) is not None:
                note = _offline_note(retry, now)
            elif launched_this_tick:
                note = "Waiting for its turn to start"
            elif not self._probe(self.settings.connection.adb_path, inst.adb_port):
                retry = self._backoff.record_miss(name, now)
                misses = self._backoff.misses(name)
                log.warning("%s: adb probe failed (miss %d); retry at %s", name, misses, retry)
                if misses == ALERT_AFTER_MISSES:
                    notify.maybe_alert("offline", {"instance": name, "misses": misses})
                note = _offline_note(retry, now)
            else:
                self._backoff.clear(name)
                if alive and pid is not None:
                    log.warning("%s: stale heartbeat, killing pid %s before relaunch", name, pid)
                    self._kill(pid, log=log.warning)
                    self._sleep(0.5)
                    alive, health = False, Health.DEAD
                self._launch_worker(inst, desired, now)
                launched = True
                note = "Starting"

        stop_deadline = (
            self._stop_asked[name] + timedelta(seconds=STOP_ESCALATE_S)
            if name in self._stop_asked and alive
            else None
        )
        state, shown_until = derive_state(
            health=health,
            desired=want,
            desired_reason=reason,
            desired_until=until,
            stop_pending=stop_deadline,
            booting=self._booting(name, now) or launched,
            offline_until=self._backoff.until(name, now),
            status=st,
        )
        if state == InstanceState.STOPPING:
            note = "Stopping after this match"
        view = InstanceView(
            name=name,
            adb_port=inst.adb_port,
            state=state,
            health=health,
            pid=pid if alive else None,
            heartbeat_age_s=heartbeat_age_s(st, now),
            phase=(st or {}).get("phase"),
            desired=want,
            desired_reason=reason,
            until=shown_until,
            games_played=_int_or_none((st or {}).get("games_played")),
            farm_brawler=(st or {}).get("farm_brawler") or None,
            note=note,
        )
        return view, launched

    # --- helpers ----------------------------------------------------------------------

    def _booting(self, name: str, now: datetime) -> bool:
        started = self._launched_at.get(name)
        if started is None or (now - started).total_seconds() >= BOOT_GRACE_S:
            return False
        proc = self._procs.get(name)
        poll = getattr(proc, "poll", None)
        return poll is None or poll() is None

    def _request_stop(self, name: str, now: datetime) -> None:
        if name in self._stop_asked:
            return
        flag = self._flag(name)
        flag.parent.mkdir(parents=True, exist_ok=True)
        flag.write_text(f"stop requested {now:%Y-%m-%dT%H:%M:%S}\n", encoding="utf-8")
        self._stop_asked[name] = now
        log.info("%s: stop requested (stop.flag written)", name)

    def _maybe_escalate(self, name: str, pid: int | None, now: datetime) -> bool:
        """Kill by PID once a requested stop has waited STOP_ESCALATE_S. True when killed."""
        asked = self._stop_asked.get(name)
        if asked is None or pid is None:
            return False
        if (now - asked).total_seconds() < STOP_ESCALATE_S:
            return False
        log.warning("%s: stop not honoured in %ds, killing pid %s", name, STOP_ESCALATE_S, pid)
        self._kill(pid, log=log.warning)
        self._stop_asked.pop(name, None)
        return True

    def _launch_worker(self, inst: S.InstanceSettings, desired: dict | None, now: datetime) -> None:
        max_minutes = (desired or {}).get("max_minutes")
        args = S.worker_args(self.settings, float(max_minutes) if max_minutes else None)
        env = {**os.environ, **S.worker_env(self.settings, inst, self.home)}
        self._flag(inst.name).unlink(missing_ok=True)
        self._stop_asked.pop(inst.name, None)
        proc = self._launch(args, env, self.home / "logs", inst.name)
        self._procs[inst.name] = proc
        self._launched_at[inst.name] = now
        log.info("%s: launched worker pid %s (%s)", inst.name, getattr(proc, "pid", "?"), " ".join(args))

    # --- controls (called from the event loop thread; phase 3 wires them to the API) ---

    def start(self, name: str, hours: float | None = None) -> None:
        """Start (or undo a pending stop): clear the stop override, or run for N hours."""
        now = self._clock()
        self.settings.instance(name)
        if hours:
            scheduler.write_override(name, "run", now + timedelta(hours=hours))
        else:
            scheduler.clear_override(name)
        self._flag(name).unlink(missing_ok=True)
        self._stop_asked.pop(name, None)
        self._backoff.clear(name)
        self.poke()

    def stop(self, name: str) -> None:
        """Graceful: schedule override to stop, stop.flag now; the tick kills after 110 s."""
        now = self._clock()
        self.settings.instance(name)
        scheduler.write_override(name, "stop", now + timedelta(days=STOP_OVERRIDE_DAYS))
        self._request_stop(name, now)
        self.poke()

    def stop_now(self, name: str) -> bool:
        """Kill by PID immediately. Only while a graceful stop is pending; else no-op."""
        if name not in self._stop_asked:
            return False
        st = status.read_status(self._dir(name))
        pid = int(st["pid"]) if st and st.get("pid") else None
        if pid is None:
            return False
        ok = bool(self._kill(pid, log=log.warning))
        self._stop_asked.pop(name, None)
        self.poke()
        return ok

    def restart(self, name: str) -> None:
        """Stop gracefully without touching the schedule; the next tick relaunches."""
        now = self._clock()
        self.settings.instance(name)
        st = status.read_status(self._dir(name))
        pid = int(st["pid"]) if st and st.get("pid") else None
        if pid is not None and self._alive(pid):
            self._request_stop(name, now)
        self.poke()

    def retry_now(self, name: str) -> None:
        self._backoff.clear(name)
        self.poke()

    def poke(self) -> None:
        if self._poke is not None:
            self._poke.set()

    # --- the loop ---------------------------------------------------------------------

    def request_shutdown(self) -> None:
        self._shutdown = True
        self.poke()

    async def run_forever(self) -> None:
        """Tick, then sleep interval_s or until poked. Workers keep running when this
        returns; the next start reattaches through status.json PIDs."""
        self._poke = asyncio.Event()
        self._shutdown = False
        while not self._shutdown:
            try:
                await asyncio.to_thread(self.tick)
            except Exception:
                log.exception("tick failed")
            try:
                await asyncio.wait_for(self._poke.wait(), timeout=self.interval_s)
            except TimeoutError:
                pass
            self._poke.clear()
        log.info("supervisor loop stopped; workers keep running")


def _parse_until(value) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _int_or_none(value) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _offline_note(retry: datetime, now: datetime) -> str:
    minutes = max(1, round((retry - now).total_seconds() / 60))
    return f"BlueStacks window not found. Retrying in {minutes} min."
```

Then make `brawlfarm/supervisor/__init__.py`:

```python
"""The supervisor: one tick a minute launches, watches, stops and kills one worker per
instance (ported from the legacy PowerShell watchdog)."""

from brawlfarm.supervisor.loop import Supervisor
from brawlfarm.supervisor.state import Health, InstanceState, InstanceView

__all__ = ["Health", "InstanceState", "InstanceView", "Supervisor"]
```

- [ ] **Step 4: Run the tests until green**

```bash
uv run pytest tests/test_supervisor_loop.py -q
```

Expected: all pass. Things to check if not: `scheduler.sched_desired` returns `None` while the schedule file is missing (legacy always-run, `want == "run"`), so the first tick launches; `scheduler.write_override` uses the tick's `now` only through `evaluate`, so the test clock must pass through `scheduler.tick(now)` (it does). `write_status` stamps `ts` with the wall clock, which is why `_heartbeat` rewrites it.

- [ ] **Step 5: Run the whole suite, lint, scrub, commit**

```bash
uv run pytest -q
uv run ruff format brawlfarm/supervisor tests/test_supervisor_loop.py
uv run ruff check . && uv run ruff format --check .
uv run python tools/scrub_check.py
git add pyproject.toml uv.lock brawlfarm/supervisor tests/test_supervisor_loop.py
git commit -m "feat(supervisor): the tick loop, controls and asyncio runner

Ported from the legacy watchdog: scheduler tick, heartbeat classification,
graceful stop then kill by PID after 110 s, boot grace, one launch per tick,
offline backoff with an alert at the third miss. start/stop/stop-now/restart/
retry-now are the controls phase 3 exposes over the API."
```

---

### Task 6: The `brawlfarm` command, docs and the pull request

**Files:**
- Modify: `brawlfarm/__main__.py`
- Create: `tests/test_cli.py`
- Modify: `README.md` (status line, a "Running" section), `docs/PLAN.md` (phase 2 in flight with the plan and PR link)

**Interfaces:**
- Consumes: `settings.default_home/load/save/config_path`, `Supervisor`, `InstanceView`.
- Produces: `brawlfarm` console script with `--version`, `--home PATH`, `--once`, `--interval SECONDS`; logging to stdout and `<home>/logs/supervisor.log` (5 MB, one backup).

- [ ] **Step 1: Write the failing tests**

`tests/test_cli.py`:

```python
"""The brawlfarm command: writes a default config.toml on first run, prints the instance
table with --once, and reports settings errors plainly."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _run(args: list[str], home: Path) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("BRAWL_", "DISCORD_"))}
    env["BRAWLFARM_HOME"] = str(home)
    return subprocess.run(
        [sys.executable, "-m", "brawlfarm", *args], env=env, capture_output=True, text=True
    )


def test_version() -> None:
    r = _run(["--version"], Path.cwd())
    assert r.returncode == 0 and r.stdout.startswith("brawlfarm 0.")


def test_first_run_writes_defaults_and_once_prints_no_instances(tmp_path: Path) -> None:
    r = _run(["--once"], tmp_path)
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "config.toml").exists()
    assert "wrote default settings" in r.stdout
    assert "no instances configured" in r.stdout
    assert (tmp_path / "logs" / "supervisor.log").exists()


def test_once_prints_a_row_per_instance(tmp_path: Path) -> None:
    (tmp_path / "config.toml").write_text(
        '[connection]\nadb_path = "C:/definitely/missing/adb.exe"\n'
        '[[instances]]\nname = "Pie64"\nadb_port = 5555\n',
        encoding="utf-8",
    )
    r = _run(["--once", "--no-launch"], tmp_path)
    assert r.returncode == 0, r.stderr
    assert "Pie64" in r.stdout and "5555" in r.stdout and "starting" in r.stdout


def test_settings_error_is_reported_plainly(tmp_path: Path) -> None:
    (tmp_path / "config.toml").write_text("[app]\nprot = 1\n", encoding="utf-8")
    r = _run(["--once"], tmp_path)
    assert r.returncode == 2
    assert "config.toml" in r.stderr and "prot" in r.stderr
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_cli.py -q
```

Expected: the `--once` tests fail (the current stub ignores the flags and prints the phase 3 message).

- [ ] **Step 3: Write `brawlfarm/__main__.py`**

```python
"""Console entry point: `brawlfarm` runs the supervisor headless (the API and the browser
panel arrive in phase 3). `--once` runs one tick and prints the instance table, which is
the phase 2 live evidence."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from brawlfarm import __version__
from brawlfarm import settings as S


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="brawlfarm", description="Brawl Stars trophy farmer")
    ap.add_argument("-V", "--version", action="store_true", help="print the version and exit")
    ap.add_argument("--home", type=Path, default=None, help="data directory (default: BRAWLFARM_HOME or %%LOCALAPPDATA%%\\brawlfarm)")
    ap.add_argument("--once", action="store_true", help="run one supervisor tick, print the instances, exit")
    ap.add_argument("--interval", type=float, default=None, help="seconds between ticks (default 60)")
    ap.add_argument("--no-launch", action="store_true", help="with --once: never start a worker (dry run)")
    return ap


def _setup_logging(home: Path) -> None:
    logs = home / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S")
    root = logging.getLogger("brawlfarm")
    root.setLevel(logging.INFO)
    root.handlers.clear()
    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(fmt)
    root.addHandler(stream)
    file = RotatingFileHandler(logs / "supervisor.log", maxBytes=5_000_000, backupCount=1, encoding="utf-8")
    file.setFormatter(fmt)
    root.addHandler(file)


def _print_table(views) -> None:
    if not views:
        print("no instances configured; add [[instances]] entries to config.toml")
        return
    print(f"{'name':<16}{'port':<8}{'state':<18}{'health':<9}{'pid':<8}{'note'}")
    for v in views:
        until = f" (until {v.until:%H:%M})" if v.until else ""
        print(f"{v.name:<16}{v.adb_port:<8}{v.state:<18}{v.health:<9}{v.pid or '-':<8}{v.note}{until}")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(sys.argv[1:] if argv is None else argv)
    if args.version:
        print(f"brawlfarm {__version__}")
        return 0
    home = (args.home or S.default_home()).resolve()
    os.environ["BRAWLFARM_HOME"] = str(home)  # the core reads it at import time
    home.mkdir(parents=True, exist_ok=True)
    try:
        settings = S.load(home)
    except S.SettingsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not S.config_path(home).exists():
        S.save(settings, home)
        print(f"wrote default settings to {S.config_path(home)}")
    _setup_logging(home)
    from brawlfarm.supervisor import Supervisor  # after BRAWLFARM_HOME is set

    kwargs = {}
    if args.no_launch:
        kwargs["launcher"] = _dry_launcher
    sup = Supervisor(settings, home, interval_s=args.interval or 60.0, **kwargs)
    if args.once:
        _print_table(sup.tick())
        return 0
    print(f"brawlfarm {__version__}: supervising {len(settings.instances)} instance(s) from {home}")
    print("Ctrl+C stops the supervisor; workers keep running and are reattached on the next start.")
    try:
        asyncio.run(sup.run_forever())
    except KeyboardInterrupt:
        sup.request_shutdown()
    return 0


class _DryProc:
    pid = 0

    def poll(self):
        return None


def _dry_launcher(args, env, log_dir, name, module=None):
    logging.getLogger("brawlfarm.supervisor").info("%s: dry run, would launch %s", name, args)
    return _DryProc()


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the CLI tests, then everything**

```bash
uv run pytest tests/test_cli.py -q
uv run pytest -q
uv run brawlfarm --version
uv run brawlfarm --once --home "$(pwd)/.tmp-home" --no-launch && rm -rf .tmp-home
```

Expected: tests pass; `brawlfarm 0.1.0`; the dry-run tick prints "wrote default settings" and "no instances configured" and exits 0.

- [ ] **Step 5: Update the docs**

In `README.md`: change the status line to `Status: under construction. Phase 2 of 8 (settings and supervisor). The control panel, setup wizard and stats screens arrive in later phases; see docs/PLAN.md.` and add, after "Development", a section:

```markdown
## Running (headless, until the panel lands in phase 3)

```
uv run brawlfarm --once        # one supervisor tick; writes config.toml on first run
uv run brawlfarm               # supervise every configured instance, one tick a minute
```

Settings live in `%LOCALAPPDATA%\brawlfarm\config.toml` (override the folder with `BRAWLFARM_HOME`). Add one `[[instances]]` table per BlueStacks instance with its `name` and `adb_port`; each instance's files live under `instances/<name>/`. Stopping the supervisor leaves workers running; the next start reattaches to them through their status files.
```

In `docs/PLAN.md`, under "In flight", replace the phase 2 line with: `- Phase 2: settings and supervisor. Plan: docs/superpowers/plans/2026-09-10-phase-2-settings-and-supervisor.md. PR: (link once opened).`

- [ ] **Step 6: Lint, scrub, commit, push, open the PR**

```bash
uv run ruff format brawlfarm/__main__.py tests/test_cli.py
uv run ruff check . && uv run ruff format --check .
uv run python tools/scrub_check.py
git add brawlfarm/__main__.py tests/test_cli.py README.md docs/PLAN.md
git commit -m "feat(cli): brawlfarm runs the supervisor headless

--once runs one tick and prints the instance table (phase 2 evidence);
first run writes a default config.toml; logs go to <home>/logs/supervisor.log."
git push -u origin phase-2/settings-supervisor
gh pr create --base main --title "Phase 2: settings and supervisor" --body-file /dev/stdin <<'EOF'
## What and why
Typed `config.toml` settings (pydantic) and a Python supervisor ported from the legacy PowerShell watchdog, runnable headless as `uv run brawlfarm`. Phase 2 of the approved build plan; the API and the browser panel are phase 3.

## Risk tier
T2 (runtime behaviour: launches, stops and kills workers). Safety rails: never-tap logic, verify-then-act and the 1600 x 900 assertion untouched; kill is by PID from `status.json` only, with a command-line guard against PID reuse.

## Safety-rail checklist
- [ ] No tap coordinate, OCR needle or core loop edited (`core/controller.py`, `core/states.py`, `core/vision.py`, `core/config.py` calibration block unchanged).
- [ ] Every subprocess call is an argument list with `shell=False`; instance names validated `[A-Za-z0-9_-]{1,32}`; adb serial built from an integer port.
- [ ] No process is found by name; kill only by the PID read from that instance's `status.json`.
- [ ] No `discord` import; scrub check green.

## Evidence
(paste: pytest summary line, scrub check output, CI run URL, `brawlfarm --once` output)

## Docs
README gains a Running section and the phase 2 status; `docs/PLAN.md` links this PR.

## Rollback
Revert the merge commit; nothing outside this repo changes. The data directory it creates (`%LOCALAPPDATA%\brawlfarm`) can be deleted.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
```

Then put the PR URL into `docs/PLAN.md`'s phase 2 line, commit `docs: link the phase 2 pull request from the plan board`, push, and once CI is green edit the PR body's Evidence section with the real outputs (`gh pr edit --body-file`). Report the PR URL and the CI run URL.

---

## Self-review

- **Spec coverage.** Section 5 (settings): Task 2 covers the file, its location, every section and default, per-instance folders (`instance_dir`), env override (`default_home`), calibration staying in `core/config.py` (untouched), `BRAWL_*` flags written into the worker env (`worker_env`), typed model and atomic save. Section 6 (supervisor): Task 5 steps 1 to 7 map to `tick()` (scheduler tick, classify, desired state, stop then kill, kill stale then launch with one launch per tick, offline backoff with retry-now, healthchecks ping is **not** implemented in the loop; see the gap note below), the state table maps to `derive_state`, graceful stop with Undo maps to `stop()`/`start()`, Stop now to `stop_now()`, Restart to `restart()`. Section 3 process model: `run_forever` leaves workers running on exit; reattachment happens through `status.json` on the next tick. Section 11 tests: settings round-trip and defaults (Task 2), supervisor state derivation and backoff (Task 4), loop behaviour (Task 5). Phase 1 deferral: Task 1.
- **Known gap, decided:** the healthchecks.io ping (`notifications.healthchecks_url`) is modelled in Task 2 but not sent by Task 5. Add it in phase 3 next to the API's outbound calls; the setting exists so the file format does not change. Ledger this as a ruling.
- **Placeholders.** None; every step carries the code or the exact command. The `(link once opened)` text in `docs/PLAN.md` is replaced in Task 6's last step.
- **Type consistency.** `settings.instance_dir(home, name)`, `worker_env(settings, inst, home)`, `worker_args(settings, max_minutes)` and `instances_table(settings)` are used with those exact signatures in Task 5. `process.launch_worker(args, env, log_dir, name, module=...)`, `kill_worker(pid, log=...)`, `pid_alive(pid)`, `instance_online(adb_path, port, timeout_s=..., runner=...)` match between Task 4's code, its tests, Task 5's fakes and Task 6's dry launcher. `derive_state`'s keyword arguments match between Task 4's tests and Task 5's call. `Supervisor(settings, home, *, clock, probe, launcher, alive, killer, sleep, events_refresh, interval_s)` matches the Task 5 fixture and Task 6. `notify.configure(webhook_url=, ntfy_server=, ntfy_topic=, events=)` matches Task 3 and Task 5. `scheduler.set_default_enabled` matches Task 3 and Task 5.
