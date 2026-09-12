# Phase 6: Stats with brawler icons Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give brawlfarm a Stats screen: `/stats` replaces the phase 4 placeholder with a toolbar, an inline metrics row, a hand-drawn SVG chart of cumulative trophy change, a per-brawler table beside a rank distribution and the last twenty games, all reflected in the URL, with a 22 px brawler icon in front of every brawler name on Stats and on the Instance farm plan.

**Architecture:** Nothing new is collected. Every number already exists in the `games.csv` and `session-*.jsonl` files the workers write, and `GET /api/stats` already aggregates them; phase 6 draws the aggregate it already returns and fixes two of its expressions. Three small Python additions sit beside the existing route-side readers: `core/icons.py` holds a brawler catalog and a disk icon cache that only the API process touches, `api/connection.py` answers one cached question about the Brawl Stars token, and `api/sessions.py` reads the newest finished session out of an instance folder so a stopped card is not all zeros. On the web side the URL is the single source of truth for the range and the instance selection, the chart and the bars are hand-written SVG with no library, and `Table` gains three optional sort props so every phase 5 call site renders exactly as it does today.

**Tech Stack:** Python 3.13 with uv, FastAPI, pydantic v2, pytest, ruff. Web: Vite 7, React 19, TypeScript 5.9 (strict, `any` banned, `tsc --noEmit` is the lint), Tailwind v4 through `@tailwindcss/vite` with the tokens already in `src/styles/theme.css`, `react-router` 7 (declarative mode), `@tanstack/react-query` 5, `lucide-react` at 16 px with `strokeWidth={1.6}`. Tests: vitest 3 + `@testing-library/react` 16 + `@testing-library/user-event` 14 + jsdom 26. pnpm 10.17.1. No new dependency on either side, and no chart library.

**Spec:** docs/superpowers/specs/2026-09-10-brawlfarm-design.md (section 8's Stats paragraph and its "Brawler icons" section, section 9 the safety rails, section 10 hygiene, section 11 testing)

**Design brief (binding):** docs/superpowers/plans/2026-09-12-phase-6-design-brief.md. Every value, every route, every prop and every string in this plan is copied from it. Sections 8 and 9 of the brief are the copy the tests quote; nothing here re-decides anything it settles.

**Task order:** the brief's section 13 lists ten tasks. This plan keeps that list and that order, one plan task per brief task, with no splits and no merges.

## Global Constraints

Copied verbatim from section 11 of the design brief. Every task's requirements implicitly include this section.

- The safety rails of spec section 9 are absolute and untouched. The UI never sends a tap,
  never exposes a shop or purchase action, never bypasses the API. Tap coordinates, OCR
  needles, HSV windows and the calibration block of `brawlfarm/core/config.py` are not
  edited. `controller.py`, `states.py`, `vision.py` and `farmplan.py` are not edited. The
  only files under `brawlfarm/core` that change in phase 6 are the new `icons.py` and the
  one optional `status` attribute on `api.py`'s `ApiError`. The never-tap rail tests must
  pass unchanged.
- One worker per instance, ever. Nothing in this phase starts, stops or kills a process.
- No user-supplied string reaches a shell or a filesystem path. A brawler name is matched
  against `BRAWLER_NAME_RE` and then discarded: the cached icon's path is built from the
  integer id. Instance names keep going through `resolve_instance`.
- No chart library and no new web dependency of any kind. The chart, the bars and the
  crosshair are hand-written SVG and CSS. No new Python dependency either: the CDN fetch
  uses `requests`, which `core/api.py` already imports.
- No CDN fetch from a worker. Only the API process talks to `cdn.brawlify.com`, only from
  `core/icons.py`, only on a request or the single start-up prewarm.
- The icon cache lives under the data directory only: `<home>/cache/brawlers.json` and
  `<home>/cache/brawlers/<id>.png`, both created by the API process. Nothing is written to
  the repository, to a temp directory outside that folder, or to any instance folder.
- The Brawl Stars API token never appears in a URL, a log line, an error message, a
  response body, a header the browser can see, or a screenshot. Only the exception type and
  an HTTP status code are logged. The player tag is subject to the same rule, and
  `ApiError`'s message, which embeds the requested path and therefore the tag, is never
  logged or returned.
- Copy: no em-dashes, no emoji, no exclamation marks; state is a word plus a colour; copy
  says what happened, what went wrong and how to fix it.
- Scrub: `uv run python tools/scrub_check.py` prints `0 hit(s)` before every commit, and
  the commit is chained on its exit code. No player tag, nickname, user path or token
  appears in code, tests, fixtures, screenshots or PR text. Fixtures use Pie64 / Pie64_1 /
  Pie64_3, ports 5555 / 5565 / 5585, and the made-up tag `#2P0YLQ9`. Docs show a data
  folder as `instances/Pie64`, never as an absolute path.
- Every commit carries a conventional message plus these two trailer lines exactly:
  `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>` and
  `Claude-Session: https://claude.ai/code/session_01CQ1GimQ3uiR2sXPzfZLNWV`.
  `git config user.name` is `as9pa`.
- Green before every commit: `pnpm typecheck`, `pnpm test`, `pnpm build`,
  `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest -q`.
- The branch is `phase-6/stats-with-brawler-icons` from `main`; one PR; the PR carries
  screenshots of the real panel with any player tag and every thumbnail blurred
  (playwright-cli `eval` sets `filter: blur(14px)` on `[data-private]` before the shot).

---

Two shell conventions for every task: commands are written for Git Bash on Windows with
forward slashes, web commands run as `pnpm --dir brawlfarm/web <script>` from the repo
root, and Python commands run from the repo root with `uv run`.

## File map

Everything phase 6 creates or modifies, across all ten tasks.

Python:

```
brawlfarm/core/icons.py                # the brawler catalog, the disk icon cache, the CDN fetch   (task 1)
brawlfarm/api/brawlers.py              # GET /api/brawlers/{name}/icon.png, the per-id lock, prewarm (task 1)
brawlfarm/api/roster.py                # one read-only accessor: RosterCache.cached_names()        (task 1)
brawlfarm/api/app.py                   # include brawlers and connection; the prewarm task; app.state.connection (tasks 1, 2)
brawlfarm/core/api.py                  # ApiError gains .status; _get sets it. Nothing else moves. (task 2)
brawlfarm/api/connection.py            # GET /api/connection/check, credential_status, ConnectionCache (task 2)
brawlfarm/api/plans.py                 # enrich_plan calls credential_status                       (task 2)
brawlfarm/api/sessions.py              # last_session(inst_dir)                                    (task 3)
brawlfarm/api/instances.py             # one line in instance_payload                              (task 3)
brawlfarm/api/stats.py                 # MIN_HOURS, and two decimals on hours_farmed               (task 4)
```

pytest files:

```
tests/test_core_icons.py               # the catalog, the rate limit, the disk cache, the rejections (task 1)
tests/test_api_brawlers.py             # the route's headers, its 404s, its 304, one lock, no token in the log (task 1)
tests/test_api_connection.py           # five statuses, the TTL, the quiet log                     (task 2)
tests/test_api_sessions.py             # last_session and its mtime cache                          (task 3)
tests/test_api_plans.py                # unchanged: the regression gate on credential_status       (task 2, not edited)
tests/test_api_stats.py                # MIN_HOURS and hours_farmed                                (task 4)
```

Web foundations and API client:

```
brawlfarm/web/src/api/types.ts                     # the stats payloads, ConnectionCheck, LastSession (task 6)
brawlfarm/web/src/api/brawlers.ts                  # brawlerIconHref                                  (task 5)
brawlfarm/web/src/api/connection.ts                # getConnection                                    (task 6)
brawlfarm/web/src/api/stats.ts                     # getStats, statsCsvHref                           (task 6)
brawlfarm/web/src/api/queries.ts                   # queryKeys.stats, queryKeys.connection            (task 6)
brawlfarm/web/src/components/ui/BrawlerIcon.tsx    # the 22 px square with its initial fallback       (task 5)
brawlfarm/web/src/components/ui/Table.tsx          # sortable, sort, onSort; nothing else             (task 8)
brawlfarm/web/src/test/fixtures.ts                 # makeStats, makeConnection, makeLastSession       (task 6)
```

The Stats screen:

```
brawlfarm/web/src/App.tsx                          # /stats renders Stats instead of Placeholder      (task 6)
brawlfarm/web/src/stats/Stats.tsx                  # the URL state, the two queries, the layout       (task 6)
brawlfarm/web/src/stats/StatsToolbar.tsx           # range radios, instance chips, Export CSV         (task 6)
brawlfarm/web/src/stats/MetricsRow.tsx             # six figures on one line                          (task 6)
brawlfarm/web/src/stats/ConnectionStrip.tsx        # the four sentences and their links               (task 6)
brawlfarm/web/src/stats/TrophyChart.tsx            # the SVG, the crosshair, the Table toggle         (task 7)
brawlfarm/web/src/stats/BrawlerTable.tsx           # the sortable per-brawler table                   (task 8)
brawlfarm/web/src/stats/RankBars.tsx               # ten rows, direct labels                          (task 8)
brawlfarm/web/src/stats/RecentGames.tsx            # twenty rows, newest first                        (task 8)
```

The Instance page and the rail:

```
brawlfarm/web/src/instance/FarmPlan.tsx            # three icon call sites (task 5); the rejected note (task 9)
brawlfarm/web/src/instance/SessionPanel.tsx        # the cold load seeded from last_session            (task 9)
brawlfarm/web/src/app/Rail.tsx                     # Stats loses its soon tag                          (task 9)
```

Vitest files sit next to the module they pin, named `<module>.test.tsx`:

```
src/components/ui/BrawlerIcon.test.tsx (task 5)    src/instance/FarmPlan.test.tsx (tasks 5, 9, modified)
src/stats/Stats.test.tsx (task 6)                  src/stats/StatsToolbar.test.tsx (task 6)
src/stats/MetricsRow.test.tsx (task 6)             src/stats/ConnectionStrip.test.tsx (task 6)
src/stats/TrophyChart.test.tsx (task 7)            src/components/ui/Table.test.tsx (task 8, modified)
src/stats/BrawlerTable.test.tsx (task 8)           src/stats/RankBars.test.tsx (task 8)
src/stats/RecentGames.test.tsx (task 8)            src/instance/SessionPanel.test.tsx (task 9, modified)
src/app/Rail.test.tsx (task 9, modified)
```

Repository files:

```
README.md          # the status line, the attribution line, three API rows                          (task 10)
docs/PLAN.md       # the phase 6 row, written on main after the merge                               (task 10)
```

`brawlfarm/core/controller.py`, `core/states.py`, `core/vision.py`, `core/farmplan.py` and
the calibration block of `core/config.py` (lines 326 to 725, the tap coordinates, the OCR
needles and the HSV windows) are off limits and are not touched by any task. `.gitignore`
and `tools/scrub_check.py` need no change.

## Five decisions the brief left open, settled once here

These are the only places the brief did not hand over a value. They are settled here so no
task re-decides them, and every task that touches them cites this list.

1. **The icon URL query helper's "shorter than the configured one" test lives in
   `Stats.tsx`, not in `api/stats.ts`.** Brief section 5 gives `getStats(range, instances)`
   two parameters and then says the `instances=` part is appended "when the list is shorter
   than the configured one", which the two-parameter signature cannot know. The signature
   wins: `Stats.tsx` passes `[]` for "every configured instance" and the narrowed list
   otherwise, and the helper appends `&instances=` whenever the list it was given is not
   empty. A full selection and no selection therefore send the same URL and share one cache
   entry, which is also what the API's own default does.
2. **`prewarm`'s names come from a new one-line accessor on `RosterCache`.** Brief section
   4a says the prewarm covers "the brawlers in every configured instance's cached roster"
   and that `app.py`'s lifespan starts it. `RosterCache` keeps its entries private, so
   task 1 adds `cached_names()`, a read-only list of every brawler name in every cached
   entry. Nothing else in `roster.py` changes. At startup that list is empty, which the
   brief already anticipates: the pass then ends immediately and icons arrive on first use.
3. **The Session panel's figure labels stay exactly as they are today.** Brief section 7
   maps `avg_rank` to "Avg rank", and brief section 8 says "Session figure labels stay as
   they are today", where that figure is labelled `Avg rank today`. Section 8 wins: the
   `Figures` keys are untouched, and `last_session.avg_rank` is written into the existing
   `"Avg rank today"` key.
4. **`--series-*` are raw CSS variables, not Tailwind colours.** `styles/theme.css` maps
   `--ok`, `--warn`, `--bad`, `--idle`, `--accent`, `--panel`, `--panel-2`, `--line`,
   `--text` and `--muted` into `@theme` as `--color-*`, so those have utility classes;
   `--series-1`, `--series-2` and `--series-3` are declared but not mapped. The chart
   therefore writes its series colours as inline `var(--series-1)` styles rather than
   classes. There is no `--info` token and none is added.
5. **The stats query waits for the instance list.** `Stats.tsx` needs the configured names
   to drop an unknown one out of `?instances=`, and that list arrives from
   `GET /api/instances`. The stats query carries `enabled: instancesQuery.isSuccess`, so
   the page never fires one request with an unfiltered selection and a second one with the
   filtered selection half a tick later. Until it is enabled the page shows the skeleton of
   brief section 9.

---
### Task 1: Icons, Python

The brief's task 1. `brawlfarm/core/icons.py` holds the catalog cache, the disk cache and
the two fetches, so the route is twenty lines of HTTP and the logic is testable without a
client. `brawlfarm/api/brawlers.py` is that route, plus the per-id lock and the start-up
prewarm hook.

Only the API process ever talks to `cdn.brawlify.com`. Nothing under
`brawlfarm/core/controller.py`, `states.py`, `vision.py` or the supervisor's worker path
imports `core/icons.py`, and no test in this task makes a network call.

Accepted proposal ids covered: `api-icons`.

**Files:**
- Create: `brawlfarm/core/icons.py`
- Create: `brawlfarm/api/brawlers.py`
- Modify: `brawlfarm/api/roster.py:89-95` (one accessor appended after `_entry`; nothing else moves)
- Modify: `brawlfarm/api/app.py:28-41` (import `brawlers`), `brawlfarm/api/app.py:113-121` (the prewarm task in the lifespan), `brawlfarm/api/app.py:166-176` (include the router after `stats`)
- Test: `tests/test_core_icons.py` (create)
- Test: `tests/test_api_brawlers.py` (create)

**Interfaces:**
- Consumes, unchanged: `brawlfarm.core.api.ApiClient(token=...).get_brawlers()`,
  `brawlfarm.core.jsonio.atomic_write_json(path, obj)`,
  `brawlfarm.api.deps.get_sup(request)`, `brawlfarm.api.deps.get_home(request)`,
  `tests.apihelpers.make_client(tmp_path, names, **overrides)`.
- Produces:
  - `brawlfarm/core/icons.py`: `CDN_URL: str`, `MAX_AGE_S: int`, `REFRESH_S: float`,
    `PREWARM_SLEEP_S: float`, `FETCH_TIMEOUT_S: float`, `MAX_ICON_BYTES: int`,
    `PNG_MAGIC: bytes`, `BRAWLER_NAME_RE: re.Pattern[str]`,
    `class IconUnavailable(RuntimeError)` with `status: int | None`,
    `catalog_path(home: Path) -> Path`, `icon_path(home: Path, brawler_id: int) -> Path`,
    `load_catalog(home: Path) -> dict[str, int]`,
    `fetch_brawlers(token: str) -> list[dict]`,
    `fetch_icon_bytes(url: str) -> bytes`,
    `resolve_id(home: Path, name: str, token: str, *, now: Callable[[], float] = time.monotonic, fetch: Callable[[str], list[dict]] = fetch_brawlers) -> int | None`,
    `ensure_icon(home: Path, brawler_id: int, fetch: Callable[[str], bytes] = fetch_icon_bytes) -> bytes | None`
  - `brawlfarm/api/brawlers.py`: `router`, `GET /api/brawlers/{name}/icon.png`,
    `prewarm(home: Path, token: str, names: Iterable[str], *, sleep: Callable[[float], None] = time.sleep) -> int`
  - `brawlfarm/api/roster.py`: `RosterCache.cached_names(self) -> list[str]`
- Consumed by: task 5 (`components/ui/BrawlerIcon.tsx` calls the route), task 2 (nothing),
  task 10 (the README route table).

- [ ] **Step 1: Branch**

```bash
cd <repo>
git switch -c phase-6/stats-with-brawler-icons
git config user.name   # must print as9pa
```

- [ ] **Step 2: Write the failing tests for the catalog half of `core/icons.py`**

Create `tests/test_core_icons.py`:

```python
"""core/icons.py: the brawler catalog and the disk icon cache.

Every test here stubs both fetches. Nothing in this file opens a socket, and the only
paths it writes are under the tmp_path home that conftest.py hands out.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from brawlfarm.core import icons

PNG = icons.PNG_MAGIC + b"the rest of a tiny png"


@pytest.fixture(autouse=True)
def _forget_refresh_stamp(monkeypatch):
    """The refresh rate limit is a module-level monotonic stamp, so it outlives a test
    unless it is put back. Every case starts as a fresh process would."""
    monkeypatch.setattr(icons, "_last_refresh_at", None)


def write_catalog(home: Path, catalog: dict[str, int]) -> None:
    path = icons.catalog_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(catalog), encoding="utf-8")


def test_resolve_id_answers_from_the_cached_catalog_without_fetching(tmp_path: Path) -> None:
    write_catalog(tmp_path, {"NORI": 42})
    calls: list[str] = []

    def fetch(token: str) -> list[dict]:
        calls.append(token)
        return []

    assert icons.resolve_id(tmp_path, "Nori", "tok", fetch=fetch) == 42
    assert calls == []


def test_resolve_id_matches_upper_cased_and_stripped(tmp_path: Path) -> None:
    write_catalog(tmp_path, {"MR. P": 7})
    assert icons.resolve_id(tmp_path, "  mr. p ", "tok", fetch=lambda _t: []) == 7


def test_a_miss_refreshes_once_and_writes_the_catalog(tmp_path: Path) -> None:
    write_catalog(tmp_path, {"NORI": 42})
    calls: list[str] = []

    def fetch(token: str) -> list[dict]:
        calls.append(token)
        return [{"id": 9, "name": "Shelly"}, {"id": 42, "name": "Nori"}]

    assert icons.resolve_id(tmp_path, "Shelly", "tok", fetch=fetch) == 9
    assert len(calls) == 1
    assert json.loads(icons.catalog_path(tmp_path).read_text(encoding="utf-8")) == {
        "SHELLY": 9,
        "NORI": 42,
    }


def test_a_second_miss_inside_the_hour_does_not_refresh(tmp_path: Path) -> None:
    calls: list[str] = []
    clock = [1000.0]

    def fetch(token: str) -> list[dict]:
        calls.append(token)
        return [{"id": 9, "name": "Shelly"}]

    assert icons.resolve_id(tmp_path, "Ghost", "tok", now=lambda: clock[0], fetch=fetch) is None
    clock[0] += icons.REFRESH_S - 1
    assert icons.resolve_id(tmp_path, "Other", "tok", now=lambda: clock[0], fetch=fetch) is None
    assert len(calls) == 1
    clock[0] += 2
    assert icons.resolve_id(tmp_path, "Shelly", "tok", now=lambda: clock[0], fetch=fetch) == 9
    assert len(calls) == 2


def test_a_blank_token_is_a_miss_and_leaves_the_catalog_alone(tmp_path: Path) -> None:
    write_catalog(tmp_path, {"NORI": 42})
    calls: list[str] = []

    def fetch(token: str) -> list[dict]:
        calls.append(token)
        return [{"id": 9, "name": "Shelly"}]

    assert icons.resolve_id(tmp_path, "Shelly", "", fetch=fetch) is None
    assert calls == []
    assert json.loads(icons.catalog_path(tmp_path).read_text(encoding="utf-8")) == {"NORI": 42}


def test_a_refresh_that_raises_leaves_the_catalog_alone(tmp_path: Path) -> None:
    write_catalog(tmp_path, {"NORI": 42})

    def boom(token: str) -> list[dict]:
        raise RuntimeError("the CDN said no")

    assert icons.resolve_id(tmp_path, "Shelly", "tok", fetch=boom) is None
    assert json.loads(icons.catalog_path(tmp_path).read_text(encoding="utf-8")) == {"NORI": 42}


def test_load_catalog_of_a_broken_file_is_empty(tmp_path: Path) -> None:
    path = icons.catalog_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")
    assert icons.load_catalog(tmp_path) == {}
```

- [ ] **Step 3: Run them to verify they fail**

```bash
uv run pytest tests/test_core_icons.py -q
```

Expected: a collection error, `ModuleNotFoundError: No module named 'brawlfarm.core.icons'`.

- [ ] **Step 4: Write `brawlfarm/core/icons.py`**

Create `brawlfarm/core/icons.py`:

```python
"""The brawler catalog and the local icon cache.

Pure functions with no FastAPI in sight, so the logic is testable without a client and
the route in api/brawlers.py stays twenty lines of HTTP. Two caches live under the data
directory and nowhere else:

  <home>/cache/brawlers.json      {UPPERCASED NAME: id}, written atomically
  <home>/cache/brawlers/<id>.png  one file per brawler, written temp-then-replace

Names are matched upper-cased and stripped because games.csv stores the official API's
names and the plan queue stores the same. The path of a cached icon is built from the
integer id and NEVER from the name, so nothing a browser sends reaches the filesystem.

Only the API process imports this module. No worker, and nothing under core/controller.py,
core/states.py or core/vision.py, ever talks to the CDN.

The token reaches ApiClient and nothing else: it is never logged, never put in a URL and
never returned. Only the exception type and, for the CDN, the HTTP status are logged.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from collections.abc import Callable
from pathlib import Path

import requests

from brawlfarm.core import jsonio
from brawlfarm.core.api import ApiClient

log = logging.getLogger("brawlfarm.api")

CDN_URL = "https://cdn.brawlify.com/brawlers/borderless/{id}.png"
MAX_AGE_S = 604800  # one week, the Cache-Control the route sends
REFRESH_S = 3600.0  # at most one catalog refresh an hour
BRAWLER_NAME_RE = re.compile(r"^[A-Za-z0-9 .'&_-]{1,32}$")
FETCH_TIMEOUT_S = 10.0
MAX_ICON_BYTES = 512 * 1024
PREWARM_SLEEP_S = 0.1
# setup/checks.py has its own copy of this signature for its own screenshot check; core
# must not import brawlfarm.setup, so the eight bytes are spelled out again rather than
# inverting the layering for them.
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

# When the catalog was last refreshed, successfully or not. Module level on purpose: a run
# of unknown names costs one call an hour for the process, not one call each.
_last_refresh_at: float | None = None


class IconUnavailable(RuntimeError):
    """The CDN answered, but not with an icon. `status` is its HTTP status, which is the
    only part of that answer worth logging."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


def catalog_path(home: Path) -> Path:
    """<home>/cache/brawlers.json."""
    return Path(home) / "cache" / "brawlers.json"


def icon_path(home: Path, brawler_id: int) -> Path:
    """<home>/cache/brawlers/<id>.png. Built from the integer id, never from a name."""
    return Path(home) / "cache" / "brawlers" / f"{int(brawler_id)}.png"


def load_catalog(home: Path) -> dict[str, int]:
    """The stored {UPPERCASED NAME: id} map. A missing, unreadable or malformed file is an
    empty catalog: a cache that cannot be read costs one refresh, never an exception.

    Read with json.loads rather than through jsonio, which owns the atomic WRITE and has
    no reader of its own.
    """
    try:
        raw = json.loads(catalog_path(home).read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return {str(k): int(v) for k, v in raw.items() if isinstance(v, int)}


def fetch_brawlers(token: str) -> list[dict]:
    """One blocking GET /brawlers. The default fetcher; tests inject their own."""
    return ApiClient(token=token).get_brawlers()


def fetch_icon_bytes(url: str) -> bytes:
    """One blocking GET of a CDN icon. Raises IconUnavailable on a non-200 so the caller
    can log the status without touching the body."""
    resp = requests.get(url, timeout=FETCH_TIMEOUT_S)
    if resp.status_code != 200:
        raise IconUnavailable("the CDN did not serve an icon", resp.status_code)
    return resp.content


def resolve_id(
    home: Path,
    name: str,
    token: str,
    *,
    now: Callable[[], float] = time.monotonic,
    fetch: Callable[[str], list[dict]] = fetch_brawlers,
) -> int | None:
    """This brawler's numeric id, or None.

    The cached catalog answers first. Only a miss refreshes, and only when REFRESH_S has
    passed since the last refresh ATTEMPT, success or failure. A blank token, a fetch that
    raises and a fetch that brings back nothing usable are all misses that leave the file
    on disk exactly as it was.
    """
    global _last_refresh_at
    key = name.strip().upper()
    if not key:
        return None
    found = load_catalog(home).get(key)
    if found is not None:
        return found
    if not token.strip():
        return None
    stamp = now()
    if _last_refresh_at is not None and stamp - _last_refresh_at < REFRESH_S:
        return None
    _last_refresh_at = stamp
    try:
        items = fetch(token)
    except Exception as exc:  # network, auth, rate limit, a shape we did not expect
        # str(exc) can carry the requested path and the token, so only the type is logged.
        log.warning("brawler catalog refresh failed (%s)", type(exc).__name__)
        return None
    fresh: dict[str, int] = {}
    for item in items or []:
        if not isinstance(item, dict):
            continue
        raw_name, raw_id = item.get("name"), item.get("id")
        if isinstance(raw_name, str) and isinstance(raw_id, int):
            fresh[raw_name.strip().upper()] = raw_id
    if not fresh:
        return None
    try:
        jsonio.atomic_write_json(catalog_path(home), fresh)
    except OSError as exc:
        log.warning("brawler catalog write failed (%s)", type(exc).__name__)
    return fresh.get(key)


def ensure_icon(
    home: Path,
    brawler_id: int,
    fetch: Callable[[str], bytes] = fetch_icon_bytes,
) -> bytes | None:
    """This brawler's PNG bytes, from disk when they are there and from the CDN otherwise.

    A fetched body is written temp-then-replace inside the cache folder, so a torn download
    never becomes a cached icon. A non-200, a timeout, a body that is not a PNG and a body
    over MAX_ICON_BYTES all return None and write nothing.
    """
    path = icon_path(home, brawler_id)
    try:
        return path.read_bytes()
    except OSError:
        pass  # not cached yet, or unreadable: either way, fetch it
    try:
        body = fetch(CDN_URL.format(id=int(brawler_id)))
    except IconUnavailable as exc:
        log.warning("brawler icon fetch failed (HTTP %s)", exc.status)
        return None
    except Exception as exc:
        log.warning("brawler icon fetch failed (%s)", type(exc).__name__)
        return None
    if not body or not body.startswith(PNG_MAGIC) or len(body) > MAX_ICON_BYTES:
        log.warning("brawler icon rejected (%d bytes)", len(body or b""))
        return None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_bytes(body)
        os.replace(tmp, path)
    except OSError as exc:  # an uncacheable icon is still a servable icon
        log.warning("brawler icon write failed (%s)", type(exc).__name__)
    return body
```

- [ ] **Step 5: Run the catalog tests to verify they pass**

```bash
uv run pytest tests/test_core_icons.py -q
```

Expected: 7 passed.

- [ ] **Step 6: Write the failing tests for the disk cache half**

Append to `tests/test_core_icons.py`:

```python
def test_ensure_icon_serves_an_existing_file_without_fetching(tmp_path: Path) -> None:
    path = icons.icon_path(tmp_path, 42)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(PNG)
    calls: list[str] = []

    def fetch(url: str) -> bytes:
        calls.append(url)
        return b""

    assert icons.ensure_icon(tmp_path, 42, fetch=fetch) == PNG
    assert calls == []


def test_ensure_icon_fetches_and_writes_on_a_miss(tmp_path: Path) -> None:
    calls: list[str] = []

    def fetch(url: str) -> bytes:
        calls.append(url)
        return PNG

    assert icons.ensure_icon(tmp_path, 42, fetch=fetch) == PNG
    assert calls == ["https://cdn.brawlify.com/brawlers/borderless/42.png"]
    assert icons.icon_path(tmp_path, 42).read_bytes() == PNG
    assert list(icons.icon_path(tmp_path, 42).parent.glob("*.tmp")) == []


def test_ensure_icon_rejects_a_body_that_is_not_a_png(tmp_path: Path) -> None:
    assert icons.ensure_icon(tmp_path, 42, fetch=lambda _u: b"<html>nope</html>") is None
    assert not icons.icon_path(tmp_path, 42).exists()


def test_ensure_icon_rejects_an_oversized_body(tmp_path: Path) -> None:
    huge = icons.PNG_MAGIC + b"x" * icons.MAX_ICON_BYTES
    assert icons.ensure_icon(tmp_path, 42, fetch=lambda _u: huge) is None
    assert not icons.icon_path(tmp_path, 42).exists()


def test_ensure_icon_rejects_a_non_200(tmp_path: Path) -> None:
    def fetch(url: str) -> bytes:
        raise icons.IconUnavailable("the CDN did not serve an icon", 404)

    assert icons.ensure_icon(tmp_path, 42, fetch=fetch) is None
    assert not icons.icon_path(tmp_path, 42).exists()


def test_ensure_icon_writes_only_under_the_home_cache(tmp_path: Path) -> None:
    icons.ensure_icon(tmp_path, 42, fetch=lambda _u: PNG)
    written = [p for p in tmp_path.rglob("*") if p.is_file()]
    assert written == [tmp_path / "cache" / "brawlers" / "42.png"]
```

- [ ] **Step 7: Run the whole icons file**

```bash
uv run pytest tests/test_core_icons.py -q
```

Expected: 13 passed. The implementation from step 4 already covers these; if any of the
six fails, the bug is in `ensure_icon`, not in the test.

- [ ] **Step 8: Commit `core/icons.py`**

```bash
uv run python tools/scrub_check.py && git add brawlfarm/core/icons.py tests/test_core_icons.py && git commit -m "feat(icons): the brawler catalog and the local icon cache

core/icons.py is the whole of the icon logic, with no FastAPI in it, so the
route that follows is twenty lines of HTTP. The catalog is refreshed at most
once an hour whatever a run of unknown names asks for, and a cached icon's
path is built from the integer id rather than from any name a browser sent.
A non-PNG body, a body over 512 KiB and a non-200 all write nothing.

Only the API process imports this. No worker path reaches the CDN.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CQ1GimQ3uiR2sXPzfZLNWV"
```

Expected: `0 hit(s)`, then the commit.

- [ ] **Step 9: Write the failing tests for the route**

Create `tests/test_api_brawlers.py`:

```python
"""GET /api/brawlers/{name}/icon.png: the PNG with a week of Cache-Control and an ETag,
304 on a match, one 404 detail for every kind of miss, one CDN call per id however many
requests race, and no token or tag anywhere in the log.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import pytest

from brawlfarm.api import brawlers
from brawlfarm.core import icons
from tests.apihelpers import make_client

PNG = icons.PNG_MAGIC + b"the rest of a tiny png"
TOKEN = "test-token-not-a-real-one"
NORI_URL = "https://cdn.brawlify.com/brawlers/borderless/42.png"
SHELLY_URL = "https://cdn.brawlify.com/brawlers/borderless/9.png"


class FakeCdn:
    """Stands in for requests.get against the CDN.

    The route reaches the network through icons.fetch_icon_bytes, whose default argument
    is bound at definition time, so replacing that NAME would not change what ensure_icon
    calls. icons.requests is looked up on every call, which makes it the seam that works.
    """

    def __init__(self, body: bytes = PNG, status: int = 200) -> None:
        self.body = body
        self.status = status
        self.urls: list[str] = []

    def get(self, url: str, timeout: float | None = None):
        self.urls.append(url)
        return _CdnResponse(self.status, self.body)


class _CdnResponse:
    def __init__(self, status_code: int, content: bytes) -> None:
        self.status_code = status_code
        self.content = content


class FakeApiClient:
    """Stands in for icons.ApiClient, for the same reason FakeCdn stands in for requests:
    fetch_brawlers looks the class up on the module at call time."""

    items: list[dict] = []

    def __init__(self, token: str | None = None, timeout: float = 20.0) -> None:
        self.token = token

    def get_brawlers(self) -> list[dict]:
        return list(type(self).items)


@pytest.fixture(autouse=True)
def _fresh_module_state(monkeypatch):
    """The refresh stamp, the per-id locks and the once-per-process prewarm flag all live
    at module level, so every test starts as a fresh process would."""
    monkeypatch.setattr(icons, "_last_refresh_at", None)
    monkeypatch.setattr(brawlers, "_locks", {})
    monkeypatch.setattr(brawlers, "_prewarmed", False)


@pytest.fixture()
def api(tmp_path: Path):
    client, sup, home = make_client(
        tmp_path, ("Pie64",), **{"connection.brawl_api_token": TOKEN}
    )
    try:
        yield client, sup, home
    finally:
        client.__exit__(None, None, None)


def write_catalog(home: Path, catalog: dict[str, int]) -> None:
    path = icons.catalog_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(catalog), encoding="utf-8")


def write_icon(home: Path, brawler_id: int, body: bytes = PNG) -> None:
    path = icons.icon_path(home, brawler_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)


def test_icon_is_served_with_a_week_of_cache_and_an_etag(api) -> None:
    client, _sup, home = api
    write_catalog(home, {"NORI": 42})
    write_icon(home, 42)
    r = client.get("/api/brawlers/Nori/icon.png")
    assert r.status_code == 200
    assert r.content == PNG
    assert r.headers["content-type"] == "image/png"
    assert r.headers["cache-control"] == "public, max-age=604800"
    assert len(r.headers["etag"]) == 18  # 16 hex chars inside quotes


def test_a_matching_if_none_match_is_304_with_the_same_headers(api) -> None:
    client, _sup, home = api
    write_catalog(home, {"NORI": 42})
    write_icon(home, 42)
    etag = client.get("/api/brawlers/Nori/icon.png").headers["etag"]
    r = client.get("/api/brawlers/Nori/icon.png", headers={"If-None-Match": etag})
    assert r.status_code == 304
    assert r.content == b""
    assert r.headers["etag"] == etag
    assert r.headers["cache-control"] == "public, max-age=604800"


def test_an_unknown_name_is_404_no_icon(api, monkeypatch) -> None:
    client, _sup, home = api
    write_catalog(home, {"NORI": 42})
    FakeApiClient.items = []
    monkeypatch.setattr(icons, "ApiClient", FakeApiClient)
    r = client.get("/api/brawlers/Ghost/icon.png")
    assert r.status_code == 404
    assert r.json() == {"detail": "no icon"}


def test_a_blank_token_is_404_no_icon(tmp_path: Path) -> None:
    client, _sup, _home = make_client(tmp_path, ("Pie64",))
    try:
        r = client.get("/api/brawlers/Nori/icon.png")
        assert r.status_code == 404
        assert r.json() == {"detail": "no icon"}
    finally:
        client.__exit__(None, None, None)


def test_a_cdn_failure_is_404_no_icon(api, monkeypatch) -> None:
    client, _sup, home = api
    write_catalog(home, {"NORI": 42})
    monkeypatch.setattr(icons, "requests", FakeCdn(body=b"<html>nope</html>"))
    r = client.get("/api/brawlers/Nori/icon.png")
    assert r.status_code == 404
    assert r.json() == {"detail": "no icon"}


@pytest.mark.parametrize("name", ["..%2Fetc", "a" * 33, "Nori/../..", "Nori%00"])
def test_a_name_that_fails_the_pattern_is_404_before_any_disk_work(api, name) -> None:
    client, _sup, _home = api
    r = client.get(f"/api/brawlers/{name}/icon.png")
    assert r.status_code == 404
    assert r.json() == {"detail": "no icon"}


def test_two_concurrent_requests_for_a_new_id_cost_one_cdn_call(api, monkeypatch) -> None:
    client, _sup, home = api
    write_catalog(home, {"NORI": 42})
    cdn = FakeCdn()
    monkeypatch.setattr(icons, "requests", cdn)

    async def both() -> list[int]:
        return await asyncio.gather(
            asyncio.to_thread(lambda: client.get("/api/brawlers/Nori/icon.png").status_code),
            asyncio.to_thread(lambda: client.get("/api/brawlers/Nori/icon.png").status_code),
        )

    assert asyncio.run(both()) == [200, 200]
    assert cdn.urls == [NORI_URL]


def test_neither_the_token_nor_the_tag_reaches_the_log(api, monkeypatch, caplog) -> None:
    client, _sup, home = api
    write_catalog(home, {"NORI": 42})
    monkeypatch.setattr(icons, "requests", FakeCdn(status=503))
    with caplog.at_level(logging.WARNING, logger="brawlfarm.api"):
        assert client.get("/api/brawlers/Nori/icon.png").status_code == 404
    text = "\n".join(record.getMessage() for record in caplog.records)
    assert TOKEN not in text
    assert "2P0YLQ9" not in text
    assert "HTTP 503" in text
```

- [ ] **Step 10: Run them to verify they fail**

```bash
uv run pytest tests/test_api_brawlers.py -q
```

Expected: a collection error, `ModuleNotFoundError: No module named 'brawlfarm.api.brawlers'`.

- [ ] **Step 11: Write `brawlfarm/api/brawlers.py`**

Create `brawlfarm/api/brawlers.py`:

```python
"""GET /api/brawlers/{name}/icon.png, and the start-up prewarm behind it.

Twenty lines of HTTP around core/icons.py. The name is checked against BRAWLER_NAME_RE
before anything touches the filesystem, and the cached path is built from the integer id
the catalog gave back, so nothing a browser sends becomes a path segment.

Every miss is the same 404 with the same detail: telling a bad token apart from a bad name
only helps someone probing. Both blocking calls run through asyncio.to_thread, and one
asyncio.Lock per id (the shape RosterCache.Entry already uses) means eight rows asking for
the same new brawler cost one CDN request.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from collections.abc import Callable, Iterable
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response

from brawlfarm.api.deps import get_home, get_sup
from brawlfarm.core import icons

log = logging.getLogger("brawlfarm.api")
router = APIRouter()

NOT_FOUND = "no icon"

# One lock per brawler id, filled lazily: the router holds nothing loop-bound until a
# request actually asks for an id.
_locks: dict[int, asyncio.Lock] = {}
# The prewarm runs at most once per process, whatever restarts the lifespan.
_prewarmed = False


def _lock(brawler_id: int) -> asyncio.Lock:
    lock = _locks.get(brawler_id)
    if lock is None:
        lock = _locks[brawler_id] = asyncio.Lock()
    return lock


def _etag(body: bytes) -> str:
    """The first 16 hex characters of the body's sha256, quoted as an ETag must be."""
    return f'"{hashlib.sha256(body).hexdigest()[:16]}"'


@router.get("/api/brawlers/{name}/icon.png")
async def get_brawler_icon(request: Request, name: str) -> Response:
    """This brawler's 200 PNG with a week of Cache-Control, a 304 when the browser already
    has it, or 404 "no icon" for every kind of miss."""
    if not icons.BRAWLER_NAME_RE.match(name):
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    home = get_home(request)
    token = get_sup(request).settings.connection.brawl_api_token
    brawler_id = await asyncio.to_thread(icons.resolve_id, home, name, token)
    if brawler_id is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    async with _lock(brawler_id):
        body = await asyncio.to_thread(icons.ensure_icon, home, brawler_id)
    if body is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    etag = _etag(body)
    headers = {"Cache-Control": f"public, max-age={icons.MAX_AGE_S}", "ETag": etag}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return Response(content=body, media_type="image/png", headers=headers)


def prewarm(
    home: Path,
    token: str,
    names: Iterable[str],
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Fetch the icons for `names` that have no file on disk yet, and say how many landed.

    Blocking, and started without being awaited, so start-up never waits on the CDN. It
    runs at most once per process, is skipped entirely when the token is blank, resolves
    the catalog once through resolve_id's own cache, sleeps between fetches and swallows
    every failure: a cold CDN must never stop the panel from serving.
    """
    global _prewarmed
    if _prewarmed:
        return 0
    _prewarmed = True
    if not token.strip():
        return 0
    warmed = 0
    for name in dict.fromkeys(names):
        try:
            brawler_id = icons.resolve_id(home, name, token)
            if brawler_id is None or icons.icon_path(home, brawler_id).exists():
                continue
            if icons.ensure_icon(home, brawler_id) is not None:
                warmed += 1
        except Exception as exc:  # one bad name must not end the pass
            log.warning("icon prewarm skipped one brawler (%s)", type(exc).__name__)
            continue
        sleep(icons.PREWARM_SLEEP_S)
    return warmed
```

- [ ] **Step 12: Register the router and add the accessor**

In `brawlfarm/api/app.py`, add `brawlers` to the import block at lines 28 to 41, keeping it
alphabetical:

```python
from brawlfarm.api import (
    alerts,
    brawlers,
    events,
    feed,
    instances,
    notify_routes,
    plans,
    roster,
    schedule,
    screens,
    settings_routes,
    setup_routes,
    stats,
)
```

Include it after `stats` at line 176:

```python
    app.include_router(stats.router)
    app.include_router(brawlers.router)
```

In `brawlfarm/api/roster.py`, append one accessor after `_entry`, which ends at line 95:

```python
    def cached_names(self) -> list[str]:
        """Every brawler name in every cached roster, once each, in insertion order. The
        icon prewarm is the only caller: it wants something to warm, and this is the only
        list of brawler names the API process has without reading a file."""
        seen: dict[str, None] = {}
        for entry in self._entries.values():
            for brawler in entry.brawlers or []:
                name = brawler.get("name")
                if isinstance(name, str) and name:
                    seen.setdefault(name, None)
        return list(seen)
```

- [ ] **Step 13: Start the prewarm from the lifespan**

In `brawlfarm/api/app.py`, inside `lifespan`, after the startup tick's `try`/`except` block
(lines 117 to 120) and before `yield` at line 121:

```python
            # One pass over the cached rosters, started and not awaited: start-up must
            # never block on the CDN, and a cold cache simply has nothing to warm.
            asyncio.create_task(
                asyncio.to_thread(
                    brawlers.prewarm,
                    app.state.home,
                    app.state.sup.settings.connection.brawl_api_token,
                    app.state.roster.cached_names(),
                )
            )
```

Also extend the lifespan's docstring line "and run one tick so the first" to read "run one
tick so the first `GET /api/instances` already has views, and start the icon prewarm
without awaiting it."

- [ ] **Step 14: Run the route tests to verify they pass**

```bash
uv run pytest tests/test_api_brawlers.py -q
```

Expected: 11 passed.

- [ ] **Step 15: Write the failing tests for `prewarm`**

Append to `tests/test_api_brawlers.py`:

```python
def test_prewarm_with_no_token_makes_no_call(tmp_path: Path, monkeypatch) -> None:
    cdn = FakeCdn()
    FakeApiClient.items = [{"id": 42, "name": "Nori"}]
    monkeypatch.setattr(icons, "requests", cdn)
    monkeypatch.setattr(icons, "ApiClient", FakeApiClient)
    assert brawlers.prewarm(tmp_path, "  ", ["Nori"], sleep=lambda _s: None) == 0
    assert cdn.urls == []
    assert not icons.catalog_path(tmp_path).exists()


def test_prewarm_fetches_only_the_ids_with_no_file(tmp_path: Path, monkeypatch) -> None:
    write_catalog(tmp_path, {"NORI": 42, "SHELLY": 9})
    write_icon(tmp_path, 42)
    cdn = FakeCdn()
    monkeypatch.setattr(icons, "requests", cdn)
    warmed = brawlers.prewarm(tmp_path, TOKEN, ["Nori", "Shelly", "Nori"], sleep=lambda _s: None)
    assert warmed == 1
    assert cdn.urls == [SHELLY_URL]


def test_prewarm_runs_once_per_process(tmp_path: Path, monkeypatch) -> None:
    write_catalog(tmp_path, {"SHELLY": 9})
    cdn = FakeCdn()
    monkeypatch.setattr(icons, "requests", cdn)
    assert brawlers.prewarm(tmp_path, TOKEN, ["Shelly"], sleep=lambda _s: None) == 1
    assert brawlers.prewarm(tmp_path, TOKEN, ["Shelly"], sleep=lambda _s: None) == 0
    assert cdn.urls == [SHELLY_URL]


def test_a_raising_fetch_does_not_propagate(tmp_path: Path, monkeypatch) -> None:
    write_catalog(tmp_path, {"SHELLY": 9})

    class Exploding:
        def get(self, url: str, timeout: float | None = None):
            raise OSError("the socket went away")

    monkeypatch.setattr(icons, "requests", Exploding())
    assert brawlers.prewarm(tmp_path, TOKEN, ["Shelly"], sleep=lambda _s: None) == 0
```

- [ ] **Step 16: Run the whole file**

```bash
uv run pytest tests/test_api_brawlers.py -q
```

Expected: 15 passed.

- [ ] **Step 17: Everything green on the Python side**

```bash
uv run ruff check . && uv run ruff format --check .
uv run pytest -q
```

Expected: `All checks passed!`, the format check prints nothing, and pytest reports 617
passed plus the 28 new ones, with no failures. The never-tap rail tests are among them and
must be untouched.

- [ ] **Step 18: Commit the route**

```bash
uv run python tools/scrub_check.py && git add brawlfarm/api/brawlers.py brawlfarm/api/app.py brawlfarm/api/roster.py tests/test_api_brawlers.py && git commit -m "feat(api): serve brawler icons from a local cache

GET /api/brawlers/{name}/icon.png answers from <home>/cache/brawlers/<id>.png
with a week of Cache-Control and an ETag, and 304s a browser that already has
the bytes. Every miss is the same 404 detail, because telling a bad token
apart from a bad name only helps someone probing.

One asyncio.Lock per id means a table of eight rows asking for the same new
brawler costs one CDN request. The start-up prewarm is created and not
awaited, runs once per process and swallows every failure, so a cold or slow
CDN cannot delay the first request.

RosterCache gains cached_names(), a read-only list of the brawler names the
process already has, which is the only thing the prewarm has to work from.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CQ1GimQ3uiR2sXPzfZLNWV"
```

Expected: `0 hit(s)`, then the commit.

---
### Task 2: Connection check, Python

The brief's task 2. One route says whether the Brawl Stars token works, in five words the
panel can turn into a sentence: `ok`, `no_token`, `no_tag`, `rejected`, `unreachable`. The
first two cost no network call; the other three come from one `GET /players/{tag}` at most
once every five minutes.

`plans.py` learns the first two from the same helper, so the plan route's four statuses
cannot drift from the connection route's five. `ApiError` gains one optional attribute so
`rejected` can be told from `unreachable` without parsing a message that carries the player
tag.

Accepted proposal ids covered: `api-connection`.

**Files:**
- Create: `brawlfarm/api/connection.py`
- Modify: `brawlfarm/core/api.py:26-27` (`ApiError` gains `__init__` and `.status`), `brawlfarm/core/api.py:50-53` (`_get` sets it)
- Modify: `brawlfarm/api/plans.py:78-84` (the inline token/tag branches become one call), `brawlfarm/api/plans.py:20-27` (one import)
- Modify: `brawlfarm/api/app.py:28-41` (import `connection`), `brawlfarm/api/app.py:138-140` (`app.state.connection`), `brawlfarm/api/app.py:166-177` (include the router after `plans`)
- Test: `tests/test_api_connection.py` (create)
- Test: `tests/test_api_plans.py` (not edited: it is the regression gate on `credential_status`)

**Interfaces:**
- Consumes, unchanged: `brawlfarm.api.roster.fetch_player(tag, token) -> dict`,
  `brawlfarm.core.api.ApiClient`, `brawlfarm.api.deps.get_sup`.
- Produces:
  - `brawlfarm/core/api.py`: `ApiError.status: int | None`
  - `brawlfarm/api/connection.py`: `TTL_S: float`, `STATUSES: tuple[str, ...]`,
    `credential_status(token: str, tag: str) -> str | None`,
    `class ConnectionCache` with
    `__init__(self, *, ttl_s: float = TTL_S, now: Callable[[], float] = time.monotonic, clock: Callable[[], datetime] = datetime.now, fetch: Callable[[str, str], dict] = fetch_player)`
    and `async get(self, token: str, tag: str) -> tuple[str, str]`,
    `router`, `GET /api/connection/check` returning `{"status": str, "checked_at": str}`
- Consumed by: task 6 (`api/connection.ts` calls the route, `ConnectionCheck` mirrors the
  body), task 9 (`FarmPlan.tsx` reads the same query), task 10 (the README route table).

- [ ] **Step 1: Write the failing test for `ApiError.status`**

Create `tests/test_api_connection.py` with only this first case for now:

```python
"""GET /api/connection/check: five statuses, one fetch per five minutes, and a log that
carries neither the token nor the player tag.

No test here opens a socket: fetch_player is replaced at every call site.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from pathlib import Path

import pytest
import requests

from brawlfarm.api import connection
from brawlfarm.core.api import ApiClient, ApiError
from tests.apihelpers import make_client

TOKEN = "test-token-not-a-real-one"
TAG = "#2P0YLQ9"
T0 = datetime(2026, 9, 12, 22, 14, 7)


class FakeResponse:
    """Enough of requests.Response for ApiClient._get: a status, a body and a json()."""

    def __init__(self, status_code: int, payload: object = None, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self) -> object:
        return self._payload


def test_api_error_carries_the_status_of_a_non_200(monkeypatch) -> None:
    client = ApiClient(token=TOKEN)
    monkeypatch.setattr(client._session, "get", lambda *a, **k: FakeResponse(403, text="nope"))
    with pytest.raises(ApiError) as caught:
        client.get_player(TAG)
    assert caught.value.status == 403
    # The message text is unchanged, so controller.py's three except ApiError blocks
    # behave exactly as they did. It carries the encoded tag, which is why nothing reads it.
    assert "HTTP 403" in str(caught.value)


def test_a_transport_failure_leaves_the_status_none(monkeypatch) -> None:
    client = ApiClient(token=TOKEN)

    def boom(*args, **kwargs):
        raise requests.RequestException("the socket went away")

    monkeypatch.setattr(client._session, "get", boom)
    with pytest.raises(ApiError) as caught:
        client.get_player(TAG)
    assert caught.value.status is None
```

- [ ] **Step 2: Run it to verify it fails**

```bash
uv run pytest tests/test_api_connection.py -q
```

Expected: a collection error, `ModuleNotFoundError: No module named 'brawlfarm.api.connection'`.
Comment out the `from brawlfarm.api import connection` line, run again, and the two cases
fail with `AttributeError: 'ApiError' object has no attribute 'status'`. Put the import
back before step 3.

- [ ] **Step 3: Add `status` to `ApiError`**

In `brawlfarm/core/api.py`, replace lines 26 and 27:

```python
class ApiError(RuntimeError):
    """Raised when an API call fails (network, auth, or non-200 status).

    ``status`` is the HTTP status of a non-200 answer and None for a transport failure or
    a missing token. Callers that need to tell a rejected token from an unreachable API
    read it rather than parsing the message: the message embeds the requested path, which
    carries the player tag, so it is never logged, echoed or matched against.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.status: int | None = None
```

and replace lines 50 to 53 inside `_get`:

```python
        if resp.status_code != 200:
            # 403 usually = bad token or IP not in the token's allowlist.
            body = resp.text[:300]
            err = ApiError(f"{path} -> HTTP {resp.status_code}: {body}")
            err.status = resp.status_code
            raise err
```

- [ ] **Step 4: Run the two cases to verify they pass**

```bash
uv run pytest tests/test_api_connection.py -q
```

Expected: 2 passed.

- [ ] **Step 5: Write the failing tests for `credential_status` and the five statuses**

Append to `tests/test_api_connection.py`:

```python
@pytest.mark.parametrize(
    "token,tag,expected",
    [
        ("", TAG, "no_token"),
        ("   ", TAG, "no_token"),
        (TOKEN, "", "no_tag"),
        (TOKEN, "  ", "no_tag"),
        (TOKEN, TAG, None),
    ],
)
def test_credential_status(token, tag, expected) -> None:
    assert connection.credential_status(token, tag) == expected


def cache(fetch, *, clock=lambda: T0, now=None) -> connection.ConnectionCache:
    ticker = now or (lambda: 1000.0)
    return connection.ConnectionCache(now=ticker, clock=clock, fetch=fetch)


def test_a_clean_answer_is_ok() -> None:
    got = asyncio.run(cache(lambda tag, token: {"tag": tag}).get(TOKEN, TAG))
    assert got == ("ok", "2026-09-12T22:14:07")


@pytest.mark.parametrize("status", [401, 403])
def test_a_401_or_a_403_is_rejected(status) -> None:
    def boom(tag: str, token: str) -> dict:
        err = ApiError("/players/x -> HTTP %d: nope" % status)
        err.status = status
        raise err

    assert asyncio.run(cache(boom).get(TOKEN, TAG))[0] == "rejected"


def test_a_request_exception_is_unreachable() -> None:
    def boom(tag: str, token: str) -> dict:
        raise requests.RequestException("the socket went away")

    assert asyncio.run(cache(boom).get(TOKEN, TAG))[0] == "unreachable"


def test_a_500_is_unreachable() -> None:
    def boom(tag: str, token: str) -> dict:
        err = ApiError("/players/x -> HTTP 500: nope")
        err.status = 500
        raise err

    assert asyncio.run(cache(boom).get(TOKEN, TAG))[0] == "unreachable"


def test_a_second_call_inside_the_ttl_does_not_fetch_again() -> None:
    calls: list[str] = []
    ticks = [1000.0]

    def fetch(tag: str, token: str) -> dict:
        calls.append(tag)
        return {}

    cached = cache(fetch, now=lambda: ticks[0])

    async def twice() -> list[tuple[str, str]]:
        first = await cached.get(TOKEN, TAG)
        ticks[0] += connection.TTL_S - 1
        second = await cached.get(TOKEN, TAG)
        ticks[0] += 2
        third = await cached.get(TOKEN, TAG)
        return [first, second, third]

    results = asyncio.run(twice())
    assert [r[0] for r in results] == ["ok", "ok", "ok"]
    assert len(calls) == 2


def test_the_failure_log_carries_neither_the_token_nor_the_tag(caplog) -> None:
    def boom(tag: str, token: str) -> dict:
        raise ApiError(f"/players/{tag} -> HTTP 403: {token}")

    with caplog.at_level(logging.WARNING, logger="brawlfarm.api"):
        asyncio.run(cache(boom).get(TOKEN, TAG))
    text = "\n".join(record.getMessage() for record in caplog.records)
    assert TOKEN not in text
    assert "2P0YLQ9" not in text
```

- [ ] **Step 6: Run them to verify they fail**

```bash
uv run pytest tests/test_api_connection.py -q
```

Expected: the two `ApiError` cases pass and the rest fail with
`AttributeError: module 'brawlfarm.api.connection' has no attribute 'credential_status'`.

- [ ] **Step 7: Write `brawlfarm/api/connection.py`**

Create `brawlfarm/api/connection.py`:

```python
"""GET /api/connection/check: does the Brawl Stars token work right now.

Five words, and only three of them cost anything. "no_token" and "no_tag" are read off
config.toml, so a panel with nothing configured never touches the network. The other
three come from one GET /players/{tag}, at most once every TTL_S, behind one lock, so two
open panels share one call.

credential_status is shared with plans.py, which is why it lives here rather than inline:
the plan route's four statuses and this route's five must agree about the first two.

Nothing here echoes, logs or returns the token or the tag. ApiError's message embeds the
requested path and therefore the tag, so only ApiError.status is read and only the
exception type reaches the log.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from datetime import datetime

from fastapi import APIRouter, Request

from brawlfarm.api.deps import get_sup
from brawlfarm.api.roster import fetch_player
from brawlfarm.core.api import ApiError

log = logging.getLogger("brawlfarm.api")
router = APIRouter()

TTL_S = 300.0  # five minutes, the same budget roster.py spends
STATUSES = ("ok", "no_token", "no_tag", "rejected", "unreachable")
REJECTING_STATUSES = frozenset({401, 403})


def credential_status(token: str, tag: str) -> str | None:
    """"no_token", "no_tag", or None when both are present. plans.py imports this."""
    if not token.strip():
        return "no_token"
    if not tag.strip():
        return "no_tag"
    return None


class ConnectionCache:
    """One process-wide answer about the token, with a TTL and one lock.

    `now`, `clock` and `fetch` are injected so the tests need neither a clock nor a
    network; the app builds the cache with the defaults and keeps it on app.state for the
    process's lifetime.
    """

    def __init__(
        self,
        *,
        ttl_s: float = TTL_S,
        now: Callable[[], float] = time.monotonic,
        clock: Callable[[], datetime] = datetime.now,
        fetch: Callable[[str, str], dict] = fetch_player,
    ) -> None:
        self._ttl_s = ttl_s
        self._now = now
        self._clock = clock
        self._fetch = fetch
        self._status: str | None = None
        self._checked_at = ""
        self._fetched_at = 0.0
        self._lock: asyncio.Lock | None = None

    def _get_lock(self) -> asyncio.Lock:
        """Built on first use, so the cache holds nothing loop-bound until a request asks
        for it and a second app in the same process gets its own loop's lock."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def get(self, token: str, tag: str) -> tuple[str, str]:
        """(status, checked_at) for these credentials, fetched at most once per TTL_S.

        401 and 403 are "rejected": the token is wrong, or the IP it was made for is not
        this one. Everything else, including a connection error, a timeout and a 5xx, is
        "unreachable", because the difference does not change what the reader should do.
        """
        async with self._get_lock():
            if self._status is not None and self._now() - self._fetched_at < self._ttl_s:
                return self._status, self._checked_at
            try:
                await asyncio.to_thread(self._fetch, tag, token)
                status = "ok"
            except ApiError as exc:
                status = "rejected" if exc.status in REJECTING_STATUSES else "unreachable"
                log.warning("connection check failed (ApiError, HTTP %s)", exc.status)
            except Exception as exc:  # network, timeout, a shape we did not expect
                # str(exc) can carry the tag and the token, so only the type is logged.
                status = "unreachable"
                log.warning("connection check failed (%s)", type(exc).__name__)
            self._status = status
            self._fetched_at = self._now()
            self._checked_at = self._clock().isoformat(timespec="seconds")
            return status, self._checked_at


@router.get("/api/connection/check")
async def check_connection(request: Request) -> dict:
    """Whether the Brawl Stars API is answering for this install, and when that was last
    established. Always 200: this route reports a failure, it does not have one."""
    sup = get_sup(request)
    token = sup.settings.connection.brawl_api_token
    tag = next((i.player_tag for i in sup.settings.instances if i.player_tag.strip()), "")
    early = credential_status(token, tag)
    if early is not None:
        return {"status": early, "checked_at": datetime.now().isoformat(timespec="seconds")}
    status, checked_at = await request.app.state.connection.get(token.strip(), tag.strip())
    return {"status": status, "checked_at": checked_at}
```

- [ ] **Step 8: Run the cache tests to verify they pass**

```bash
uv run pytest tests/test_api_connection.py -q
```

Expected: 13 passed.

- [ ] **Step 9: Write the failing tests for the route**

Append to `tests/test_api_connection.py`:

```python
def route_client(tmp_path: Path, *, token: str = TOKEN, tag: str = TAG):
    """A client whose one instance carries `tag`, with `token` in settings."""
    client, sup, home = make_client(tmp_path, ("Pie64",), **{"connection.brawl_api_token": token})
    sup.settings.instances[0].player_tag = tag
    return client, sup, home


def test_route_is_ok_when_the_player_endpoint_answers(tmp_path: Path) -> None:
    client, _sup, _home = route_client(tmp_path)
    try:
        client.app.state.connection = cache(lambda tag, token: {"tag": tag})
        r = client.get("/api/connection/check")
        assert r.status_code == 200
        assert r.json() == {"status": "ok", "checked_at": "2026-09-12T22:14:07"}
    finally:
        client.__exit__(None, None, None)


def test_route_is_no_token_without_a_network_call(tmp_path: Path) -> None:
    client, _sup, _home = route_client(tmp_path, token="")
    try:
        calls: list[str] = []
        client.app.state.connection = cache(lambda tag, token: calls.append(tag) or {})
        body = client.get("/api/connection/check").json()
        assert body["status"] == "no_token"
        assert body["checked_at"]
        assert calls == []
    finally:
        client.__exit__(None, None, None)


def test_route_is_no_tag_without_a_network_call(tmp_path: Path) -> None:
    client, _sup, _home = route_client(tmp_path, tag="")
    try:
        calls: list[str] = []
        client.app.state.connection = cache(lambda tag, token: calls.append(tag) or {})
        body = client.get("/api/connection/check").json()
        assert body["status"] == "no_tag"
        assert body["checked_at"]
        assert calls == []
    finally:
        client.__exit__(None, None, None)


def test_route_is_rejected_on_a_403(tmp_path: Path) -> None:
    client, _sup, _home = route_client(tmp_path)
    try:

        def boom(tag: str, token: str) -> dict:
            err = ApiError("/players/x -> HTTP 403: nope")
            err.status = 403
            raise err

        client.app.state.connection = cache(boom)
        assert client.get("/api/connection/check").json()["status"] == "rejected"
    finally:
        client.__exit__(None, None, None)


def test_route_is_unreachable_on_a_transport_failure(tmp_path: Path) -> None:
    client, _sup, _home = route_client(tmp_path)
    try:

        def boom(tag: str, token: str) -> dict:
            raise requests.RequestException("the socket went away")

        client.app.state.connection = cache(boom)
        assert client.get("/api/connection/check").json()["status"] == "unreachable"
    finally:
        client.__exit__(None, None, None)


def test_the_route_body_never_carries_the_token_or_the_tag(tmp_path: Path) -> None:
    client, _sup, _home = route_client(tmp_path)
    try:
        client.app.state.connection = cache(lambda tag, token: {"tag": tag})
        text = client.get("/api/connection/check").text
        assert TOKEN not in text
        assert "2P0YLQ9" not in text
    finally:
        client.__exit__(None, None, None)
```

- [ ] **Step 10: Run them to verify they fail**

```bash
uv run pytest tests/test_api_connection.py -q
```

Expected: the six new cases fail with 404, because the router is not registered yet.

- [ ] **Step 11: Register the router and the cache**

In `brawlfarm/api/app.py`, add `connection` to the import block at lines 28 to 41, keeping
it alphabetical:

```python
from brawlfarm.api import (
    alerts,
    brawlers,
    connection,
    events,
    feed,
    instances,
    notify_routes,
    plans,
    roster,
    schedule,
    screens,
    settings_routes,
    setup_routes,
    stats,
)
```

After `app.state.roster = roster.RosterCache()` (line 140), add:

```python
    # One connection check for the process: five-minute TTL, one lock. Built here for the
    # same reason the roster cache is, and its lock is made on first use.
    app.state.connection = connection.ConnectionCache()
```

Include the router after `plans` (line 172):

```python
    app.include_router(plans.router)
    app.include_router(connection.router)
```

- [ ] **Step 12: Run the route tests to verify they pass**

```bash
uv run pytest tests/test_api_connection.py -q
```

Expected: 19 passed.

- [ ] **Step 13: Share `credential_status` into `plans.py`**

In `brawlfarm/api/plans.py`, add one import beside the existing ones (lines 20 to 27):

```python
from brawlfarm.api.connection import credential_status
from brawlfarm.api.deps import get_sup, resolve_instance
```

and replace lines 78 to 84 of `enrich_plan`:

```python
    roster: list[dict] | None = None
    status = credential_status(token, tag)
    if status is None:
        roster, status = await request.app.state.roster.get(inst.name, tag, token)
```

`roster_status` keeps its four values `ok | no_token | no_tag | unavailable` on the plan
route; `rejected` and `unreachable` live only on the connection route.

- [ ] **Step 14: Run the plan tests unchanged**

```bash
uv run pytest tests/test_api_plans.py -q
```

Expected: every existing case passes with no edit to the file. The `no_token` and `no_tag`
cases are the regression gate: if either changed shape, the helper is wrong, not the test.

- [ ] **Step 15: Everything green on the Python side**

```bash
uv run ruff check . && uv run ruff format --check .
uv run pytest -q
```

Expected: `All checks passed!`, the format check prints nothing, pytest reports no
failures. `controller.py`'s three `except ApiError` blocks are exercised by the existing
controller tests and must still pass untouched.

- [ ] **Step 16: Commit**

```bash
uv run python tools/scrub_check.py && git add brawlfarm/api/connection.py brawlfarm/core/api.py brawlfarm/api/plans.py brawlfarm/api/app.py tests/test_api_connection.py && git commit -m "feat(api): one cached answer about the Brawl Stars token

GET /api/connection/check reports ok, no_token, no_tag, rejected or
unreachable and always 200s. The first two are read off config.toml and cost
nothing; the other three are one GET /players/{tag} every five minutes behind
one lock, so two open panels share one call.

401 and 403 are rejected and everything else is unreachable, which needs the
status of the failing call. ApiError gains an optional .status for that: its
message text is unchanged, because that message embeds the requested path and
therefore the player tag, and nothing may parse or log it.

plans.py now asks credential_status for its first two branches, so the plan
route's four statuses cannot drift from this route's five.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CQ1GimQ3uiR2sXPzfZLNWV"
```

Expected: `0 hit(s)`, then the commit.

---

### Task 3: `last_session`, Python

The brief's task 3. A stopped instance's Fleet card and Session panel currently read zeros
on a cold load, because `status.json` stops carrying a session block the moment the worker
stops. `brawlfarm/api/sessions.py` reads the newest finished session out of the instance
folder and `instance_payload` hands it over on every instance payload.

This goes beside the other route-side file readers rather than in the supervisor: the
supervisor's tick must not grow a per-status disk walk, and `instances.py` is where
`games.csv` and `status.json` are already read.

Accepted proposal ids covered: `inst-last-session`.

**Files:**
- Create: `brawlfarm/api/sessions.py`
- Modify: `brawlfarm/api/instances.py:89-99` (one line in `instance_payload`), `brawlfarm/api/instances.py:24-27` (one import)
- Test: `tests/test_api_sessions.py` (create)

**Interfaces:**
- Consumes, unchanged: `brawlfarm.api.feed.classify(kind) -> str | None`,
  `brawlfarm.core.datalog.GAME_FIELDS` (the column names `logged_at`, `rank`,
  `trophyChange`), `brawlfarm.api.deps.resolve_instance` through the existing routes.
- Produces:
  - `brawlfarm/api/sessions.py`: `SESSION_GLOB: str`, `SESSION_STAMP_FMT: str`,
    `last_session(inst_dir: Path) -> dict | None` returning
    `{"games": int, "trophies": int, "avg_rank": float | None, "disconnects": int,
    "duration_s": int, "interrupts": int, "ended_at": str}`
  - `brawlfarm/api/instances.py`: every instance payload gains `last_session`
- Consumed by: task 6 (`LastSession` in `api/types.ts`, `makeLastSession` in the
  fixtures), task 9 (`SessionPanel.tsx` seeds its cold load from it).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_api_sessions.py`:

```python
"""api/sessions.py: the newest finished session in an instance folder.

The session log narrates and games.csv carries the numbers, so the block is a join of the
two over the session's own window. Every read is guarded: a broken session file must never
break a Fleet card.
"""

from __future__ import annotations

import json
from pathlib import Path

from brawlfarm.api import sessions

GAMES_HEADER = "battleTime,logged_at,event_mode,battle_mode,type,rank,trophyChange,result,duration_s,map,brawler,is_showdown\n"


def write_session(inst_dir: Path, stamp: str, lines: list[dict]) -> Path:
    inst_dir.mkdir(parents=True, exist_ok=True)
    path = inst_dir / f"session-{stamp}.jsonl"
    path.write_text(
        "".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8"
    )
    return path


def write_games(inst_dir: Path, rows: list[str]) -> Path:
    inst_dir.mkdir(parents=True, exist_ok=True)
    path = inst_dir / "games.csv"
    path.write_text(GAMES_HEADER + "".join(row + "\n" for row in rows), encoding="utf-8")
    return path


def game(logged_at: str, rank: str, change: str, brawler: str = "NORI") -> str:
    """One games.csv row in GAME_FIELDS order, with only the four cells this module reads
    carrying anything worth reading."""
    return f"20260912T210000.000Z,{logged_at},soloShowdown,soloShowdown,ranked,{rank},{change},victory,150,Feast or Famine,{brawler},True"


def test_a_folder_with_no_session_file_is_none(tmp_path: Path) -> None:
    (tmp_path / "Pie64").mkdir()
    assert sessions.last_session(tmp_path / "Pie64") is None


def test_a_missing_folder_is_none(tmp_path: Path) -> None:
    assert sessions.last_session(tmp_path / "never-ran") is None


def test_one_finished_session_gives_the_seven_fields(tmp_path: Path) -> None:
    inst = tmp_path / "Pie64"
    write_session(
        inst,
        "20260912-210000",
        [
            {"ts": "2026-09-12T21:00:05", "kind": "farming", "brawler": "NORI"},
            {"ts": "2026-09-12T21:31:00", "kind": "disconnect"},
            {"ts": "2026-09-12T21:40:00", "kind": "popup_close"},
            {"ts": "2026-09-12T22:14:07", "kind": "recap"},
        ],
    )
    write_games(
        inst,
        [
            game("2026-09-12T20:59:00", "3", "8"),  # before the session started
            game("2026-09-12T21:10:00", "2", "12"),
            game("2026-09-12T21:50:00", "5", "-4"),
            game("2026-09-12T22:20:00", "1", "20"),  # after the session ended
        ],
    )
    assert sessions.last_session(inst) == {
        "games": 2,
        "trophies": 8,
        "avg_rank": 3.5,
        "disconnects": 1,
        "duration_s": 4447,
        "interrupts": 2,
        "ended_at": "2026-09-12T22:14:07",
    }


def test_a_session_with_no_ranked_game_has_a_null_avg_rank(tmp_path: Path) -> None:
    inst = tmp_path / "Pie64"
    write_session(inst, "20260912-210000", [{"ts": "2026-09-12T21:30:00", "kind": "recap"}])
    write_games(inst, [game("2026-09-12T21:10:00", "", "12")])
    block = sessions.last_session(inst)
    assert block is not None
    assert block["avg_rank"] is None
    assert block["games"] == 1
    assert block["trophies"] == 12


def test_a_broken_json_line_still_counts_the_rest(tmp_path: Path) -> None:
    inst = tmp_path / "Pie64"
    inst.mkdir(parents=True)
    (inst / "session-20260912-210000.jsonl").write_text(
        '{"ts": "2026-09-12T21:05:00", "kind": "disconnect"}\n'
        "{not json at all\n"
        "\n"
        '{"ts": "2026-09-12T21:30:00", "kind": "popup_close"}\n',
        encoding="utf-8",
    )
    block = sessions.last_session(inst)
    assert block is not None
    assert block["disconnects"] == 1
    assert block["interrupts"] == 2
    assert block["ended_at"] == "2026-09-12T21:30:00"


def test_a_half_written_games_csv_gives_zeros_instead_of_raising(tmp_path: Path) -> None:
    inst = tmp_path / "Pie64"
    write_session(inst, "20260912-210000", [{"ts": "2026-09-12T21:30:00", "kind": "recap"}])
    (inst / "games.csv").write_bytes(GAMES_HEADER.encode() + b"\xff\xfe not utf-8 at all")
    block = sessions.last_session(inst)
    assert block is not None
    assert (block["games"], block["trophies"], block["avg_rank"]) == (0, 0, None)


def test_the_newest_of_three_session_files_is_the_one_read(tmp_path: Path) -> None:
    inst = tmp_path / "Pie64"
    write_session(inst, "20260910-080000", [{"ts": "2026-09-10T09:00:00", "kind": "recap"}])
    write_session(inst, "20260912-210000", [{"ts": "2026-09-12T22:14:07", "kind": "recap"}])
    write_session(inst, "20260911-190540", [{"ts": "2026-09-11T20:00:00", "kind": "recap"}])
    block = sessions.last_session(inst)
    assert block is not None
    assert block["ended_at"] == "2026-09-12T22:14:07"


def test_a_second_call_with_nothing_changed_does_not_reread(tmp_path: Path, monkeypatch) -> None:
    inst = tmp_path / "Pie64"
    write_session(inst, "20260912-210000", [{"ts": "2026-09-12T22:14:07", "kind": "recap"}])
    write_games(inst, [game("2026-09-12T21:10:00", "2", "12")])
    first = sessions.last_session(inst)
    reads: list[Path] = []
    original = sessions._read

    def counted(session_path: Path, games_path: Path, filename: str):
        reads.append(session_path)
        return original(session_path, games_path, filename)

    monkeypatch.setattr(sessions, "_read", counted)
    assert sessions.last_session(inst) == first
    assert reads == []


def test_a_new_game_row_invalidates_the_cache(tmp_path: Path) -> None:
    inst = tmp_path / "Pie64"
    write_session(inst, "20260912-210000", [{"ts": "2026-09-12T22:14:07", "kind": "recap"}])
    write_games(inst, [game("2026-09-12T21:10:00", "2", "12")])
    assert sessions.last_session(inst)["games"] == 1
    write_games(
        inst,
        [game("2026-09-12T21:10:00", "2", "12"), game("2026-09-12T21:20:00", "4", "6")],
    )
    assert sessions.last_session(inst)["games"] == 2
```

- [ ] **Step 2: Run them to verify they fail**

```bash
uv run pytest tests/test_api_sessions.py -q
```

Expected: a collection error, `ModuleNotFoundError: No module named 'brawlfarm.api.sessions'`.

- [ ] **Step 3: Write `brawlfarm/api/sessions.py`**

Create `brawlfarm/api/sessions.py`:

```python
"""The newest finished session in one instance folder.

The API stops reporting status.json's session block the moment a worker stops, so a
stopped instance reads as zeros on a cold load. This joins the two files that survive the
stop: the session log narrates (its filename is the start, its last line is the end, its
kinds are the interrupts and the disconnects) and games.csv carries the only rank and
trophy change anyone wrote down.

It lives beside the other route-side readers rather than in the supervisor: a tick must
not grow a per-status disk walk, and instances.py is already where games.csv and
status.json are read.

Every read is wrapped. A broken session file must never break a Fleet card.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

from brawlfarm.api import feed

SESSION_GLOB = "session-*.jsonl"
SESSION_STAMP_FMT = "%Y%m%d-%H%M%S"  # core/datalog.py's filename, local time

# {resolved instance dir: (session filename, session mtime, games.csv mtime, value)}. The
# work is redone only when one of those three changes, so a Fleet poll every few seconds
# costs two stat calls per instance.
_cache: dict[Path, tuple[str, float, float, dict | None]] = {}


def _newest_name(inst_dir: Path) -> str | None:
    """The newest session file by NAME. The name is session-%Y%m%d-%H%M%S.jsonl, so the
    names sort chronologically, which beats an mtime sort on a folder copied between
    machines."""
    try:
        names = sorted(p.name for p in inst_dir.glob(SESSION_GLOB) if p.is_file())
    except OSError:
        return None
    return names[-1] if names else None


def _mtime(path: Path) -> float:
    """The file's mtime, or -1.0 when it is not there. A missing games.csv is a stable
    cache key, not an exception."""
    try:
        return path.stat().st_mtime
    except OSError:
        return -1.0


def _started_at(filename: str) -> datetime | None:
    """The session's start, parsed out of its own filename as local time."""
    stamp = filename[len("session-") : -len(".jsonl")]
    try:
        return datetime.strptime(stamp, SESSION_STAMP_FMT)
    except ValueError:
        return None


def _moment(value: object) -> datetime | None:
    """One "2026-09-12T22:14:07" as core/datalog.py writes it, or None."""
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _int_or_zero(value: object) -> int:
    """A hand-edited or half-written cell counts as zero, never as an exception."""
    try:
        return int(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def _float_or_none(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _games_window(
    path: Path, started: datetime, ended: datetime
) -> tuple[int, int, float | None]:
    """(games, net trophies, mean rank) for the rows whose logged_at falls inside the
    session, ends included. An unreadable file is zeros."""
    games = 0
    trophies = 0
    ranks: list[float] = []
    try:
        with path.open("r", encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                moment = _moment(row.get("logged_at"))
                if moment is None or moment < started or moment > ended:
                    continue
                games += 1
                trophies += _int_or_zero(row.get("trophyChange"))
                rank = _float_or_none(row.get("rank"))
                if rank is not None:
                    ranks.append(rank)
    except (OSError, csv.Error, UnicodeDecodeError, ValueError):
        return 0, 0, None
    avg_rank = round(sum(ranks) / len(ranks), 1) if ranks else None
    return games, trophies, avg_rank


def _read(session_path: Path, games_path: Path, filename: str) -> dict | None:
    """The block for one session file, or None when even its name cannot be read."""
    started = _started_at(filename)
    if started is None:
        return None
    ended = started
    interrupts = 0
    disconnects = 0
    try:
        with session_path.open("r", encoding="utf-8") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    line = json.loads(raw)
                except ValueError:  # one bad line costs its line, never the session
                    continue
                if not isinstance(line, dict):
                    continue
                kind = str(line.get("kind") or "")
                if feed.classify(kind) == "interrupts":
                    interrupts += 1
                if kind == "disconnect":
                    disconnects += 1
                moment = _moment(line.get("ts"))
                if moment is not None and moment > ended:
                    ended = moment
    except (OSError, UnicodeDecodeError):
        return None
    games, trophies, avg_rank = _games_window(games_path, started, ended)
    return {
        "games": games,
        "trophies": trophies,
        "avg_rank": avg_rank,
        "disconnects": disconnects,
        "duration_s": max(0, int((ended - started).total_seconds())),
        "interrupts": interrupts,
        "ended_at": ended.isoformat(timespec="seconds"),
    }


def last_session(inst_dir: Path) -> dict | None:
    """This instance's newest finished session, or None when it has never written one."""
    inst_dir = Path(inst_dir)
    filename = _newest_name(inst_dir)
    if filename is None:
        _cache.pop(inst_dir, None)
        return None
    session_path = inst_dir / filename
    games_path = inst_dir / "games.csv"
    stamp = (filename, _mtime(session_path), _mtime(games_path))
    cached = _cache.get(inst_dir)
    if cached is not None and cached[:3] == stamp:
        return cached[3]
    value = _read(session_path, games_path, filename)
    _cache[inst_dir] = (*stamp, value)
    return value
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
uv run pytest tests/test_api_sessions.py -q
```

Expected: 9 passed.

- [ ] **Step 5: Write the failing test for the payload**

Append to `tests/test_api_sessions.py`:

```python
def test_every_instance_payload_carries_last_session(tmp_path: Path) -> None:
    from brawlfarm import settings as S
    from tests.apihelpers import make_client

    client, _sup, home = make_client(tmp_path, ("Pie64",))
    try:
        inst = S.instance_dir(home, "Pie64")
        write_session(inst, "20260912-210000", [{"ts": "2026-09-12T22:14:07", "kind": "recap"}])
        write_games(inst, [game("2026-09-12T21:10:00", "2", "12")])
        payload = client.get("/api/instances").json()["instances"][0]
        assert payload["last_session"] == {
            "games": 1,
            "trophies": 12,
            "avg_rank": 2.0,
            "disconnects": 0,
            "duration_s": 4447,
            "interrupts": 0,
            "ended_at": "2026-09-12T22:14:07",
        }
        # The blocks beside it are untouched.
        assert "session" in payload
        assert payload["today"] == {"games": 0, "trophies": 0}
    finally:
        client.__exit__(None, None, None)


def test_an_instance_that_never_ran_carries_a_null_last_session(tmp_path: Path) -> None:
    from tests.apihelpers import make_client

    client, _sup, _home = make_client(tmp_path, ("Pie64",))
    try:
        payload = client.get("/api/instances").json()["instances"][0]
        assert payload["last_session"] is None
    finally:
        client.__exit__(None, None, None)
```

- [ ] **Step 6: Run them to verify they fail**

```bash
uv run pytest tests/test_api_sessions.py -q
```

Expected: the two new cases fail with `KeyError: 'last_session'`.

- [ ] **Step 7: Hand it over on the payload**

In `brawlfarm/api/instances.py`, add one import beside the existing ones (lines 24 to 27):

```python
from brawlfarm.api.deps import LIVE_STATES, get_home, get_sup, resolve_instance
from brawlfarm.api.sessions import last_session
```

and add one line to `instance_payload` (lines 89 to 99), after `payload["today"]`:

```python
def instance_payload(
    view: InstanceView, inst: S.InstanceSettings, inst_dir: Path, now: datetime
) -> dict:
    """One Fleet card's whole row: the view, the tag from settings, the live session,
    today's totals, and the last finished session so a stopped card is not all zeros."""
    payload = view_to_dict(view)
    payload["player_tag"] = inst.player_tag
    payload["session"] = _session(status.read_status(inst_dir))
    payload["today"] = today_counts(inst_dir, now)
    payload["last_session"] = last_session(inst_dir)
    return payload
```

`_session` and `today_counts` are not touched.

- [ ] **Step 8: Run the file and the instance tests**

```bash
uv run pytest tests/test_api_sessions.py tests/test_api_instances.py -q
```

Expected: 11 passed in the sessions file, and every existing instances case still passing.

- [ ] **Step 9: Everything green on the Python side**

```bash
uv run ruff check . && uv run ruff format --check .
uv run pytest -q
```

Expected: `All checks passed!`, the format check prints nothing, pytest reports no failures.

- [ ] **Step 10: Commit**

```bash
uv run python tools/scrub_check.py && git add brawlfarm/api/sessions.py brawlfarm/api/instances.py tests/test_api_sessions.py && git commit -m "feat(api): a last_session block on every instance payload

A stopped instance reads as zeros on a cold load, because status.json stops
carrying a session the moment its worker stops. api/sessions.py joins the two
files that survive the stop: the session log, whose filename is the start and
whose kinds are the interrupts and the disconnects, and games.csv, which is
the only place a rank or a trophy change was ever written.

The newest file is chosen by name rather than by mtime, so a folder copied
between machines still reads in the right order. The result is cached against
the session filename and the two mtimes, so a Fleet poll costs two stat calls
per instance and nothing else. Every read is guarded: a broken session file
must never break a Fleet card.

It sits beside the other route-side readers, not in the supervisor, so a tick
never grows a per-status disk walk.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CQ1GimQ3uiR2sXPzfZLNWV"
```

Expected: `0 hit(s)`, then the commit.

---
### Task 4: Stats aggregation, Python

The brief's task 4. Two expressions in `brawlfarm/api/stats.py`, and nothing else in the
file. This is the phase 3 deferral: today's guard is `hours > 0`, so one game logged in
ninety seconds reads as hundreds of trophies an hour, and `hours_farmed` rounds to one
digit, which hides the difference between two short sessions and one.

`aggregate` keeps its shape. Both routes keep their `range` and `instances` query params
and their 404 on an unknown instance, and `RECENT_LIMIT` stays 20.

Accepted proposal ids covered: `stats-metrics`.

**Files:**
- Modify: `brawlfarm/api/stats.py:36-40` (`MIN_HOURS` beside `RECENT_LIMIT`), `brawlfarm/api/stats.py:156` (the guard), `brawlfarm/api/stats.py:159` (two decimals)
- Test: `tests/test_api_stats.py` (modify: three tests appended)

**Interfaces:**
- Consumes: nothing new.
- Produces: `brawlfarm/api/stats.py`: `MIN_HOURS: float`, and a `summary` whose
  `trophies_per_hour` is `None` below `MIN_HOURS` and whose `hours_farmed` carries two
  decimals. The shape is unchanged: `range`, `instances`,
  `summary{games, trophies, trophies_per_hour, avg_rank, top4_rate, hours_farmed}`,
  `series[{instance, points[{t, cum}]}]`,
  `brawlers[{name, games, net, avg_rank, top4_rate}]`, `ranks[{rank, games}]`,
  `recent[{instance, t, brawler, rank, trophy_change, map, mode}]`.
- Consumed by: task 6 (`StatsSummary` and `MetricsRow` render exactly these fields, and
  `MetricsRow` shows "after 30 min" for the null).

- [ ] **Step 1: Write the failing tests**

In `tests/test_api_stats.py`, add `MIN_HOURS` to the import at line 16, keeping it
alphabetical:

```python
from brawlfarm.api.stats import (
    MIN_HOURS,
    aggregate,
    export_csv,
    load_games_for,
    range_start,
    sessions_hours,
)
```

Then append these three cases. They use the file's own helpers: `NOW` (line 20),
`_game(minutes_ago, brawler, rank, change, duration=150)` (line 37) and
`_write_games(home, name, rows)` (line 54). "Time farmed" is first-to-last plus the last
game's duration per session, and more than 30 minutes between games starts a new session,
which is why the gaps below are 9 and 29 minutes rather than anything longer:

```python
def test_trophies_per_hour_is_null_below_half_an_hour(tmp_path: Path) -> None:
    """Two games nine minutes apart must not read as hundreds of trophies an hour. The
    guard is MIN_HOURS, not "any positive number of hours" (the phase 3 deferral)."""
    _write_games(
        tmp_path,
        "alpha",
        [_game(9, "NORI", 2, 12), _game(0, "NORI", 3, 9)],
    )
    summary = aggregate(tmp_path, ["alpha"], "all", NOW)["summary"]
    assert summary["hours_farmed"] < MIN_HOURS
    assert summary["trophies_per_hour"] is None
    assert summary["games"] == 2
    assert summary["trophies"] == 21


def test_trophies_per_hour_is_a_number_above_half_an_hour(tmp_path: Path) -> None:
    _write_games(
        tmp_path,
        "alpha",
        [_game(29, "NORI", 2, 12), _game(0, "NORI", 3, 9)],
    )
    summary = aggregate(tmp_path, ["alpha"], "all", NOW)["summary"]
    assert summary["hours_farmed"] >= MIN_HOURS
    assert summary["trophies_per_hour"] == 40.0


def test_hours_farmed_carries_two_decimals(tmp_path: Path) -> None:
    """"3.2 h" hides the difference between two short sessions and one."""
    _write_games(
        tmp_path,
        "alpha",
        [_game(29, "NORI", 2, 12), _game(0, "NORI", 3, 9)],
    )
    hours = aggregate(tmp_path, ["alpha"], "all", NOW)["summary"]["hours_farmed"]
    assert hours == 0.53  # 29 min plus the last game's 150 s, to two digits
    assert hours != round(hours, 1)
```

- [ ] **Step 2: Run them to verify they fail**

```bash
uv run pytest tests/test_api_stats.py -q -k "trophies_per_hour or hours_farmed"
```

Expected: a collection error,
`ImportError: cannot import name 'MIN_HOURS' from 'brawlfarm.api.stats'`.

- [ ] **Step 3: Change the two expressions**

In `brawlfarm/api/stats.py`, add one constant beside `RECENT_LIMIT` at line 39:

```python
RECENT_LIMIT = 20
# Below half an hour, "trophies per hour" is an extrapolation from noise: two games in
# ninety seconds would read as hundreds an hour. The screen says "after 30 min" instead.
MIN_HOURS = 0.5
```

Replace line 156:

```python
            "trophies_per_hour": _num(net / hours) if hours >= MIN_HOURS else None,
```

Replace line 159:

```python
            "hours_farmed": _num(hours, 2),
```

Nothing else in the file changes.

- [ ] **Step 4: Run the whole stats file to verify it passes**

```bash
uv run pytest tests/test_api_stats.py -q
```

Expected: every existing case still passes and the three new ones pass. If an existing
case asserted a one-decimal `hours_farmed`, that assertion is the one thing in the file
that changes: update its expected number to two decimals and say so in the commit body.

- [ ] **Step 5: Everything green on the Python side**

```bash
uv run ruff check . && uv run ruff format --check .
uv run pytest -q
```

Expected: `All checks passed!`, the format check prints nothing, pytest reports no failures.

- [ ] **Step 6: Commit**

```bash
uv run python tools/scrub_check.py && git add brawlfarm/api/stats.py tests/test_api_stats.py && git commit -m "fix(stats): guard trophies per hour, and two decimals on hours farmed

Two games logged in ninety seconds used to read as hundreds of trophies an
hour, because the guard was any positive number of hours. Below MIN_HOURS the
figure is null and the screen says \"after 30 min\" instead. hours_farmed
carries two decimals, because one digit hid the difference between two short
sessions and one.

This is the phase 3 deferral. aggregate keeps its shape, both routes keep
their query params and their 404, and RECENT_LIMIT stays 20.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CQ1GimQ3uiR2sXPzfZLNWV"
```

Expected: `0 hit(s)`, then the commit.

---

### Task 5: `BrawlerIcon` and the farm plan icons

The brief's task 5. One component, one URL builder, three call sites on the Instance page.
The icon is decorative: the name is always beside it, so `alt` is empty and the square is
`aria-hidden`. The square is laid out before the image resolves and keeps its size in every
state, so no row ever shifts.

No retry, no timer, no cache of its own: the browser's HTTP cache plus the route's
week-long `Cache-Control` from task 1 is the cache.

Accepted proposal ids covered: `inst-icons`.

**Files:**
- Create: `brawlfarm/web/src/api/brawlers.ts`
- Create: `brawlfarm/web/src/components/ui/BrawlerIcon.tsx`
- Modify: `brawlfarm/web/src/instance/FarmPlan.tsx:8-20` (one import), `:253-257` (the current brawler), `:279-288` (the queue rows), `:298-310` (the full list)
- Test: `brawlfarm/web/src/components/ui/BrawlerIcon.test.tsx` (create)
- Test: `brawlfarm/web/src/instance/FarmPlan.test.tsx` (modify: one test appended)

**Interfaces:**
- Consumes: `GET /api/brawlers/{name}/icon.png` from task 1.
- Produces:
  - `api/brawlers.ts`: `brawlerIconHref(name: string): string`
  - `components/ui/BrawlerIcon.tsx`:
    `BrawlerIconProps { name: string | null; size?: number }`, `BrawlerIcon`
- Consumed by: task 8 (`BrawlerTable` and `RecentGames` both render a `BrawlerIcon`).

- [ ] **Step 1: Write the failing test**

Create `brawlfarm/web/src/components/ui/BrawlerIcon.test.tsx`:

```tsx
/** The 22 px brawler square: the image while it loads, the initial when it cannot, and the
 * same box in both states so no row ever shifts. */
import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BrawlerIcon } from "./BrawlerIcon";
import { renderWithProviders } from "../../test/renderWithProviders";

function box(): HTMLElement {
  return screen.getByTestId("brawler-icon");
}

describe("BrawlerIcon", () => {
  it("points the image at the icon route with the name encoded", () => {
    renderWithProviders(<BrawlerIcon name="Mr. P" />);
    const img = box().querySelector("img");
    expect(img).toHaveAttribute("src", "/api/brawlers/Mr.%20P/icon.png");
    expect(img).toHaveAttribute("alt", "");
    expect(img).toHaveAttribute("loading", "lazy");
    expect(img).toHaveAttribute("decoding", "async");
  });

  it("falls back to the upper-cased initial when the image errors", () => {
    renderWithProviders(<BrawlerIcon name="nori" />);
    const img = box().querySelector("img");
    expect(img).not.toBeNull();
    fireEvent.error(img as HTMLImageElement);
    expect(box().querySelector("img")).toBeNull();
    expect(box()).toHaveTextContent("N");
  });

  it("falls back for a null name and for a blank one", () => {
    const { unmount } = renderWithProviders(<BrawlerIcon name={null} />);
    expect(box().querySelector("img")).toBeNull();
    expect(box()).toHaveTextContent("");
    unmount();
    renderWithProviders(<BrawlerIcon name="   " />);
    expect(box().querySelector("img")).toBeNull();
  });

  it("keeps the same box in both states, at the default size and a given one", () => {
    const { unmount } = renderWithProviders(<BrawlerIcon name="Nori" />);
    expect(box()).toHaveStyle({ width: "22px", height: "22px" });
    const img = box().querySelector("img") as HTMLImageElement;
    fireEvent.error(img);
    expect(box()).toHaveStyle({ width: "22px", height: "22px" });
    unmount();
    renderWithProviders(<BrawlerIcon name="Nori" size={16} />);
    expect(box()).toHaveStyle({ width: "16px", height: "16px" });
  });

  it("is hidden from a screen reader, because the name is always beside it", () => {
    renderWithProviders(<BrawlerIcon name="Nori" />);
    expect(box()).toHaveAttribute("aria-hidden", "true");
  });

  it("goes back to the image when the name changes after an error", () => {
    const { rerender } = renderWithProviders(<BrawlerIcon name="Nori" />);
    fireEvent.error(box().querySelector("img") as HTMLImageElement);
    expect(box().querySelector("img")).toBeNull();
    rerender(<BrawlerIcon name="Shelly" />);
    expect(box().querySelector("img")).toHaveAttribute("src", "/api/brawlers/Shelly/icon.png");
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

```bash
pnpm --dir brawlfarm/web test -- src/components/ui/BrawlerIcon.test.tsx
```

Expected: `Failed to resolve import "./BrawlerIcon"`.

- [ ] **Step 3: Write the URL builder and the component**

Create `brawlfarm/web/src/api/brawlers.ts`:

```ts
/** The one place the brawler icon URL is built. BrawlerIcon is its only caller; nothing
 * else should be constructing a path out of a brawler's name. */
export function brawlerIconHref(name: string): string {
  return `/api/brawlers/${encodeURIComponent(name)}/icon.png`;
}
```

Create `brawlfarm/web/src/components/ui/BrawlerIcon.tsx`:

```tsx
/**
 * A brawler's portrait, or its initial.
 *
 * Decorative on purpose: the name is always beside it, so the square is aria-hidden and
 * the image's alt is empty rather than a second reading of the same word.
 *
 * The square is laid out at its final size before the image resolves and keeps that size
 * in every state, so a table of twenty rows does not shuffle as the icons arrive. There is
 * no retry, no timer and no cache here: the browser's HTTP cache plus the route's
 * week-long Cache-Control is the cache.
 */
import { useEffect, useState } from "react";

import { brawlerIconHref } from "../../api/brawlers";

export interface BrawlerIconProps {
  name: string | null;
  size?: number;
}

const DEFAULT_SIZE = 22;

export function BrawlerIcon({ name, size = DEFAULT_SIZE }: BrawlerIconProps) {
  const trimmed = (name ?? "").trim();
  const [failed, setFailed] = useState(false);

  // A row that scrolls into a different brawler must try again: the failure belonged to
  // the previous name, not to this square.
  useEffect(() => {
    setFailed(false);
  }, [trimmed]);

  const square = { width: `${size}px`, height: `${size}px` };

  return (
    <span
      data-testid="brawler-icon"
      aria-hidden="true"
      className="inline-flex items-center justify-center"
      style={{
        ...square,
        borderRadius: "6px",
        overflow: "hidden",
        background: "var(--panel-2)",
        flex: "none",
      }}
    >
      {trimmed === "" || failed ? (
        <span className="text-[11px] leading-none text-muted">
          {trimmed.slice(0, 1).toUpperCase()}
        </span>
      ) : (
        <img
          src={brawlerIconHref(trimmed)}
          alt=""
          loading="lazy"
          decoding="async"
          onError={() => setFailed(true)}
          style={square}
        />
      )}
    </span>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pnpm --dir brawlfarm/web test -- src/components/ui/BrawlerIcon.test.tsx
```

Expected: 6 passed.

- [ ] **Step 5: Write the failing test for the farm plan's three call sites**

Append to `brawlfarm/web/src/instance/FarmPlan.test.tsx`, inside its existing top-level
`describe`:

```tsx
  it("puts an icon in front of the current brawler, every queue row and the full list", async () => {
    mount(
      makePlan({
        current: { brawler: "NORI", trophies: 820, goal: 1000 },
        queue: ["SHELLY", "COLT"],
        roster: [
          makeRosterBrawler({ id: 1, name: "NORI", trophies: 820 }),
          makeRosterBrawler({ id: 2, name: "SHELLY", trophies: 740 }),
        ],
      }),
    );
    renderWithProviders(<FarmPlan name="Pie64" />);

    await screen.findByText("SHELLY");
    // One for the current brawler, one per queue row.
    expect(screen.getAllByTestId("brawler-icon")).toHaveLength(3);

    await userEvent.click(screen.getByRole("button", { name: "Show all brawlers" }));
    // Plus one per roster row.
    expect(screen.getAllByTestId("brawler-icon")).toHaveLength(5);
  });
```

`mount(body)`, `makePlan` and `renderWithProviders` are helpers this file already has.
`makeRosterBrawler` is not yet imported here, so extend the fixtures import at line 9:

```tsx
import { makePlan, makeRosterBrawler } from "../test/fixtures";
```

- [ ] **Step 6: Run it to verify it fails**

```bash
pnpm --dir brawlfarm/web test -- src/instance/FarmPlan.test.tsx
```

Expected: `Unable to find an element by: [data-testid="brawler-icon"]`.

- [ ] **Step 7: Add the icons to the three call sites**

In `brawlfarm/web/src/instance/FarmPlan.tsx`, add one import beside the existing component
imports (lines 14 to 18, keeping them alphabetical):

```tsx
import { BrawlerIcon } from "../components/ui/BrawlerIcon";
import { Button } from "../components/ui/Button";
```

Replace the current brawler's row (lines 253 to 257) so the icon comes before the name
inside the existing flex row, with `gap-2` unchanged. The row becomes `items-center`
rather than `items-baseline`, because a 22 px square has no baseline to sit on:

```tsx
        <div className="flex items-center gap-2">
          <BrawlerIcon name={plan.current.brawler} />
          <span className="font-mono text-[13px]">{plan.current.brawler ?? "none"}</span>
          <span className="ml-auto font-mono text-[12px] tabular-nums text-muted">
            {plan.current.trophies === null ? "none" : plan.current.trophies} / {goal}
          </span>
        </div>
```

Replace each queue row (lines 279 to 288):

```tsx
          <ul>
            {plan.queue.map((brawler) => (
              <li key={brawler} className="flex items-center gap-2 text-[13px]">
                <BrawlerIcon name={brawler} />
                <span className="font-mono">{brawler}</span>
                <span className="ml-auto font-mono text-[12px] tabular-nums text-muted">
                  {trophiesOf.get(brawler.toUpperCase()) ?? "none"}
                </span>
              </li>
            ))}
          </ul>
```

Replace each full-list row (lines 298 to 310):

```tsx
          {showAll ? (
            <ul data-testid="plan-roster">
              {roster.map((b) => (
                <li key={b.id} className="flex items-center gap-2 text-[13px]">
                  <BrawlerIcon name={b.name} />
                  <span className="font-mono">{b.name}</span>
                  <span className="ml-auto font-mono text-[12px] tabular-nums text-muted">
                    {b.trophies}
                  </span>
                </li>
              ))}
            </ul>
          ) : null}
```

Nothing else in the file moves. Row heights do not change: the icon is 22 px and each row
already clears that.

- [ ] **Step 8: Run the farm plan tests to verify they pass**

```bash
pnpm --dir brawlfarm/web test -- src/instance/FarmPlan.test.tsx
```

Expected: every existing case still passes, plus the new one. The progress bar, the queue
count and the roster assertions must not have needed an edit.

- [ ] **Step 9: Everything green on the web side**

```bash
pnpm --dir brawlfarm/web typecheck
pnpm --dir brawlfarm/web test
pnpm --dir brawlfarm/web build
```

Expected: `tsc --noEmit` silent, every vitest file passing, `vite build` writes
`brawlfarm/web/dist/index.html`.

- [ ] **Step 10: Commit**

```bash
uv run python tools/scrub_check.py && git add brawlfarm/web/src/api/brawlers.ts brawlfarm/web/src/components/ui/BrawlerIcon.tsx brawlfarm/web/src/components/ui/BrawlerIcon.test.tsx brawlfarm/web/src/instance/FarmPlan.tsx brawlfarm/web/src/instance/FarmPlan.test.tsx && git commit -m "feat(web): a brawler icon, and three of them on the farm plan

BrawlerIcon is a 22 px square that is laid out at its final size before the
image resolves and keeps that size in every state, so a list of twenty rows
does not shuffle as the icons arrive. It is decorative: the name is always
beside it, so alt is empty and the square is aria-hidden. A failed load, a
null name and a blank one all render the initial instead.

It brings no cache of its own. The browser's HTTP cache plus the icon route's
week-long Cache-Control is the cache.

The farm plan's current brawler, its queue rows and its full roster list each
gain one, inside the flex row they already had. Every row keeps its height.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CQ1GimQ3uiR2sXPzfZLNWV"
```

Expected: `0 hit(s)`, then the commit.

---
### Task 6: Stats shell

The brief's task 6. The page itself: the types, the fixtures, the two API modules, the two
query keys, the route swap, and the four components that make up everything on `/stats`
above the chart. The chart is task 7 and the band below it is task 8; this task leaves a
page that already works without them.

The URL is the single source of the range and the selection. Two query params, read and
written with `useSearchParams`: `range` (one of `today`, `7d`, `30d`, `all`) and
`instances` (a comma-separated list of configured names). An absent or unparsable `range`
is `7d`. An absent `instances` means every configured instance. A name that is not
configured is dropped before the request goes out, so a stale link degrades to a narrower
selection instead of a 404 from `_selected`. Changing a tab or a chip does a `replace`, not
a `push`, so Back leaves Stats rather than walking the ranges.

Accepted proposal ids covered: `stats-range`, `stats-metrics`, `stats-export`,
`stats-empty`, `stats-nav`.

**Files:**
- Modify: `brawlfarm/web/src/api/types.ts:1-7` (the module comment), `:36-54` (`InstancePayload` gains one field), `:159-172` (`StatsResponse` grows), and append the new payloads at the end of the file
- Modify: `brawlfarm/web/src/api/stats.ts:1-8` (the whole file)
- Create: `brawlfarm/web/src/api/connection.ts`
- Modify: `brawlfarm/web/src/api/queries.ts:12-25` (two keys)
- Modify: `brawlfarm/web/src/test/fixtures.ts:7-15` (the type import), `:17-44` (`makeInstance` gains one default), and append three builders
- Create: `brawlfarm/web/src/stats/Stats.tsx`
- Create: `brawlfarm/web/src/stats/StatsToolbar.tsx`
- Create: `brawlfarm/web/src/stats/MetricsRow.tsx`
- Create: `brawlfarm/web/src/stats/ConnectionStrip.tsx`
- Modify: `brawlfarm/web/src/App.tsx:16-25` (one import, one removed), `:87` (the route)
- Test: `brawlfarm/web/src/stats/ConnectionStrip.test.tsx` (create)
- Test: `brawlfarm/web/src/stats/MetricsRow.test.tsx` (create)
- Test: `brawlfarm/web/src/stats/StatsToolbar.test.tsx` (create)
- Test: `brawlfarm/web/src/stats/Stats.test.tsx` (create)

**Interfaces:**
- Consumes: `GET /api/stats` and `GET /api/stats/export.csv` (unchanged since phase 3),
  `GET /api/connection/check` from task 2, `last_session` from task 3,
  `useInstances()` from `api/useInstances.ts`, `Segmented`, `Chip`, `ErrorBlock` and
  `Placeholder` from phase 4, `hoursText` is NOT used (the metrics row formats its own).
- Produces:
  - `api/types.ts`: `StatsRange`, `StatsPoint`, `StatsSeries`, `StatsBrawler`,
    `StatsRank`, `StatsGame`, a grown `StatsResponse`, `ConnectionStatus`,
    `ConnectionCheck`, `LastSession`, and `InstancePayload.last_session`
  - `api/stats.ts`: `getStats(range: StatsRange, instances: string[]): Promise<StatsResponse>`,
    `statsCsvHref(range: StatsRange, instances: string[]): string`, and `getStatsToday`
    unchanged
  - `api/connection.ts`: `getConnection(): Promise<ConnectionCheck>`
  - `api/queries.ts`: `queryKeys.stats(range, instances)`, `queryKeys.connection()`
  - `test/fixtures.ts`: `makeStats(overrides?: Partial<StatsResponse>): StatsResponse`,
    `makeConnection(overrides?: Partial<ConnectionCheck>): ConnectionCheck`,
    `makeLastSession(overrides?: Partial<LastSession>): LastSession`
  - `stats/ConnectionStrip.tsx`:
    `ConnectionStripProps { status: ConnectionStatus; instanceWithoutTag: string | null }`,
    `ConnectionStrip`
  - `stats/MetricsRow.tsx`: `MetricsRowProps { summary: StatsSummary }`, `MetricsRow`
  - `stats/StatsToolbar.tsx`:
    `StatsToolbarProps { range: StatsRange; instances: string[]; selected: string[];
    onRange: (next: StatsRange) => void; onInstances: (next: string[]) => void;
    csvHref: string }`, `StatsToolbar`, `RANGE_LABELS: Record<StatsRange, string>`
  - `stats/Stats.tsx`: `Stats`, `RANGES: readonly StatsRange[]`,
    `parseRange(raw: string | null): StatsRange`
- Consumed by: task 7 (`TrophyChart` takes `StatsResponse["series"]` and the selected
  names), task 8 (`BrawlerTable`, `RankBars` and `RecentGames` take
  `StatsResponse["brawlers"]`, `.ranks` and `.recent`), task 9 (`FarmPlan` reads
  `queryKeys.connection()` and `getConnection`; `SessionPanel` reads `LastSession`).

- [ ] **Step 1: Grow the payload types**

In `brawlfarm/web/src/api/types.ts`, replace the module comment at lines 1 to 7:

```ts
/**
 * The API's payloads as TypeScript.
 *
 * Mirrors brawlfarm/api/*.py exactly: optional in Python means `| null` here, never `?`,
 * because the API always sends the key.
 */
```

Add one field to `InstancePayload`, after `today: Today;` (line 53):

```ts
  session: InstanceSession | null;
  today: Today;
  /** The newest finished session in the instance folder, so a stopped card is not all
   * zeros on a cold load. Null when that instance has never written one. */
  last_session: LastSession | null;
}
```

Replace the `StatsResponse` block at lines 168 to 172, and append the rest after it:

```ts
export type StatsRange = "today" | "7d" | "30d" | "all";

export interface StatsPoint {
  t: string;
  cum: number;
}

export interface StatsSeries {
  instance: string;
  points: StatsPoint[];
}

export interface StatsBrawler {
  name: string;
  games: number;
  net: number;
  avg_rank: number | null;
  top4_rate: number | null;
}

export interface StatsRank {
  rank: number;
  games: number;
}

export interface StatsGame {
  instance: string | null;
  t: string;
  brawler: string | null;
  rank: number | null;
  trophy_change: number | null;
  map: string | null;
  mode: string | null;
}

/** StatsResponse grows from the summary-only phase 4 shape to the whole aggregate. */
export interface StatsResponse {
  range: string;
  instances: string[];
  summary: StatsSummary;
  series: StatsSeries[];
  brawlers: StatsBrawler[];
  ranks: StatsRank[];
  recent: StatsGame[];
}

/** GET /api/connection/check. RosterStatus deliberately stays four values, because the
 * plan route still answers with those four; "rejected" and "unreachable" live only here. */
export type ConnectionStatus = "ok" | "no_token" | "no_tag" | "rejected" | "unreachable";

export interface ConnectionCheck {
  status: ConnectionStatus;
  checked_at: string;
}

export interface LastSession {
  games: number;
  trophies: number;
  avg_rank: number | null;
  disconnects: number;
  duration_s: number;
  interrupts: number;
  ended_at: string;
}
```

`StatsSummary` and `RosterStatus` keep their current definitions.

- [ ] **Step 2: Add the fixtures**

In `brawlfarm/web/src/test/fixtures.ts`, extend the type import at lines 7 to 15:

```ts
import type {
  Alert,
  AppSettings,
  ConnectionCheck,
  FeedRecord,
  InstancePayload,
  LastSession,
  PlanResponse,
  RosterBrawler,
  SchedulePayload,
  StatsResponse,
} from "../api/types";
```

Add one default to `makeInstance`, after `today: { games: 12, trophies: 86 },`:

```ts
    today: { games: 12, trophies: 86 },
    last_session: null,
    ...overrides,
```

Append three builders at the end of the file:

```ts
/** The whole stats aggregate for one range: two instances, four games, enough of every
 * block that a component test never has to hand-write one. The tag-free names and the
 * invented brawler names keep tools/scrub_check.py quiet. */
export function makeStats(overrides: Partial<StatsResponse> = {}): StatsResponse {
  return {
    range: "7d",
    instances: ["Pie64", "Pie64_1"],
    summary: {
      games: 4,
      trophies: 37,
      trophies_per_hour: 24.7,
      avg_rank: 3.3,
      top4_rate: 75,
      hours_farmed: 1.5,
    },
    series: [
      {
        instance: "Pie64",
        points: [
          { t: "2026-09-12T21:00:00", cum: 12 },
          { t: "2026-09-12T21:30:00", cum: 8 },
          { t: "2026-09-12T22:00:00", cum: 25 },
        ],
      },
      {
        instance: "Pie64_1",
        points: [
          { t: "2026-09-12T21:10:00", cum: -3 },
          { t: "2026-09-12T22:10:00", cum: 12 },
        ],
      },
    ],
    brawlers: [
      { name: "NORI", games: 3, net: 29, avg_rank: 2.7, top4_rate: 100 },
      { name: "SHELLY", games: 1, net: 8, avg_rank: 5, top4_rate: 0 },
    ],
    ranks: [
      { rank: 1, games: 1 },
      { rank: 2, games: 1 },
      { rank: 4, games: 1 },
      { rank: 5, games: 1 },
    ],
    recent: [
      {
        instance: "Pie64",
        t: "2026-09-12T22:00:00",
        brawler: "NORI",
        rank: 1,
        trophy_change: 17,
        map: "Feast or Famine",
        mode: "soloShowdown",
      },
      {
        instance: "Pie64_1",
        t: "2026-09-12T21:10:00",
        brawler: "SHELLY",
        rank: 5,
        trophy_change: -3,
        map: null,
        mode: null,
      },
    ],
    ...overrides,
  };
}

export function makeConnection(overrides: Partial<ConnectionCheck> = {}): ConnectionCheck {
  return { status: "ok", checked_at: "2026-09-12T22:14:07", ...overrides };
}

export function makeLastSession(overrides: Partial<LastSession> = {}): LastSession {
  return {
    games: 12,
    trophies: 86,
    avg_rank: 3.4,
    disconnects: 1,
    duration_s: 4447,
    interrupts: 2,
    ended_at: "2026-09-12T22:14:07",
    ...overrides,
  };
}
```

- [ ] **Step 3: Write the two API modules and the query keys**

Replace the whole of `brawlfarm/web/src/api/stats.ts`:

```ts
/**
 * The stats aggregate, and the CSV download's href.
 *
 * One query builder serves both, so the table the page shows and the file the reader
 * downloads can never describe different selections. `instances` empty means "every
 * configured instance", which is also the API's own default, so a full selection and no
 * selection send the same URL and share one cache entry. Stats.tsx is what decides which
 * of those two a click means.
 */
import { api } from "./client";
import type { StatsRange, StatsResponse } from "./types";

function statsQuery(range: StatsRange, instances: string[]): string {
  const scope = instances.length === 0 ? "" : `&instances=${instances.join(",")}`;
  return `?range=${range}${scope}`;
}

export function getStatsToday(instance?: string): Promise<StatsResponse> {
  const scope = instance === undefined ? "" : `&instances=${instance}`;
  return api<StatsResponse>(`/api/stats?range=today${scope}`);
}

export function getStats(range: StatsRange, instances: string[]): Promise<StatsResponse> {
  return api<StatsResponse>(`/api/stats${statsQuery(range, instances)}`);
}

/** The export's href for an anchor. The download is a plain link, not a fetch, so the
 * browser's own download is the feedback and there is no toast to write. */
export function statsCsvHref(range: StatsRange, instances: string[]): string {
  return `/api/stats/export.csv${statsQuery(range, instances)}`;
}
```

Create `brawlfarm/web/src/api/connection.ts`:

```ts
/** Whether the Brawl Stars API is answering for this install. Always 200: the route
 * reports a failure, it does not have one. */
import { api } from "./client";
import type { ConnectionCheck } from "./types";

export function getConnection(): Promise<ConnectionCheck> {
  return api<ConnectionCheck>("/api/connection/check");
}
```

In `brawlfarm/web/src/api/queries.ts`, add two keys beside `statsToday` (line 21):

```ts
  statsToday: (instance?: string) =>
    instance === undefined ? (["stats", "today"] as const) : (["stats", "today", instance] as const),
  /** The Stats page's own read. It deliberately does NOT start with ["stats", "today"],
   * so phase 4's invalidation still covers the Fleet and session reads without fighting
   * this one. */
  stats: (range: string, instances: string[]) =>
    ["stats", "range", range, instances.join(",")] as const,
  connection: () => ["connection"] as const,
```

- [ ] **Step 4: Write the failing test for `ConnectionStrip`**

Create `brawlfarm/web/src/stats/ConnectionStrip.test.tsx`:

```tsx
/** The quiet strip that says why there are no per-game numbers, in the spec's own
 * sentences, with the link that fixes it. */
import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ConnectionStrip } from "./ConnectionStrip";
import { renderWithProviders } from "../test/renderWithProviders";

describe("ConnectionStrip", () => {
  it("renders nothing when the connection is ok", () => {
    const { container } = renderWithProviders(
      <ConnectionStrip status="ok" instanceWithoutTag={null} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("asks for a token, in warn, linking to Settings, Connection", () => {
    renderWithProviders(<ConnectionStrip status="no_token" instanceWithoutTag={null} />);
    expect(screen.getByRole("status")).toHaveTextContent(
      "Battle log unavailable. Add a Brawl Stars API token in Settings to see per-game stats.",
    );
    expect(screen.getByRole("status")).toHaveAttribute("data-tone", "warn");
    expect(screen.getByRole("link", { name: "Settings" })).toHaveAttribute(
      "href",
      "/settings/connection",
    );
  });

  it("asks for a player tag, naming the instance", () => {
    renderWithProviders(<ConnectionStrip status="no_tag" instanceWithoutTag="Pie64" />);
    expect(screen.getByRole("status")).toHaveTextContent(
      "Add a player tag for Pie64 in Settings, Instances to see its games.",
    );
    expect(screen.getByRole("status")).toHaveAttribute("data-tone", "warn");
    expect(screen.getByRole("link", { name: "Settings, Instances" })).toHaveAttribute(
      "href",
      "/settings/instances",
    );
  });

  it("says nothing about a tag when there is no instance to name", () => {
    const { container } = renderWithProviders(
      <ConnectionStrip status="no_tag" instanceWithoutTag={null} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("reports a rejected token in bad, linking to Settings, Connection", () => {
    renderWithProviders(<ConnectionStrip status="rejected" instanceWithoutTag={null} />);
    expect(screen.getByRole("status")).toHaveTextContent(
      "The Brawl Stars API rejected the token. Check the token, and the IP address it was created for, in Settings, Connection.",
    );
    expect(screen.getByRole("status")).toHaveAttribute("data-tone", "bad");
    expect(screen.getByRole("link", { name: "Settings, Connection" })).toHaveAttribute(
      "href",
      "/settings/connection",
    );
  });

  it("reports an unreachable API in warn, with no link", () => {
    renderWithProviders(<ConnectionStrip status="unreachable" instanceWithoutTag={null} />);
    expect(screen.getByRole("status")).toHaveTextContent(
      "The Brawl Stars API did not answer. Stats show what was logged so far.",
    );
    expect(screen.getByRole("status")).toHaveAttribute("data-tone", "warn");
    expect(screen.queryByRole("link")).toBeNull();
  });
});
```

- [ ] **Step 5: Run it to verify it fails**

```bash
pnpm --dir brawlfarm/web test -- src/stats/ConnectionStrip.test.tsx
```

Expected: `Failed to resolve import "./ConnectionStrip"`.

- [ ] **Step 6: Write `ConnectionStrip`**

Create `brawlfarm/web/src/stats/ConnectionStrip.tsx`:

```tsx
/**
 * One quiet strip saying why there are no per-game numbers, and what to do about it.
 *
 * Never a modal and never a toast: the page below it still shows everything that was
 * logged, and the reader decides when to go and fix the credential. The sentences are the
 * spec's, letter for letter.
 */
import { Link } from "react-router";

import type { ConnectionStatus } from "../api/types";
import type { Tone } from "../lib/states";

export interface ConnectionStripProps {
  status: ConnectionStatus;
  /** The selected instance whose player_tag is blank, which the no_tag sentence names.
   * Null when there is none, and then no_tag says nothing at all. */
  instanceWithoutTag: string | null;
}

const TONE_BORDER: Record<Tone, string> = {
  ok: "border-l-ok",
  warn: "border-l-warn",
  bad: "border-l-bad",
  idle: "border-l-idle",
};

export function ConnectionStrip({ status, instanceWithoutTag }: ConnectionStripProps) {
  if (status === "ok") return null;
  if (status === "no_tag" && instanceWithoutTag === null) return null;

  const tone: Tone = status === "rejected" ? "bad" : "warn";

  return (
    <p
      role="status"
      data-tone={tone}
      className={`rounded-[6px] border border-line border-l-[3px] bg-panel-2 px-3 py-2 text-[12px] text-text ${TONE_BORDER[tone]}`}
    >
      {status === "no_token" && (
        <>
          Battle log unavailable. Add a Brawl Stars API token in{" "}
          <Link to="/settings/connection" className="underline">
            Settings
          </Link>{" "}
          to see per-game stats.
        </>
      )}
      {status === "no_tag" && (
        <>
          Add a player tag for {instanceWithoutTag} in{" "}
          <Link to="/settings/instances" className="underline">
            Settings, Instances
          </Link>{" "}
          to see its games.
        </>
      )}
      {status === "rejected" && (
        <>
          The Brawl Stars API rejected the token. Check the token, and the IP address it was
          created for, in{" "}
          <Link to="/settings/connection" className="underline">
            Settings, Connection
          </Link>
          .
        </>
      )}
      {status === "unreachable" && (
        <>The Brawl Stars API did not answer. Stats show what was logged so far.</>
      )}
    </p>
  );
}
```

- [ ] **Step 7: Run it to verify it passes**

```bash
pnpm --dir brawlfarm/web test -- src/stats/ConnectionStrip.test.tsx
```

Expected: 6 passed.

- [ ] **Step 8: Write the failing test for `MetricsRow`**

Create `brawlfarm/web/src/stats/MetricsRow.test.tsx`:

```tsx
/** Six figures on one line: their labels, their formatting, and the two placeholders that
 * stand in for a number that would be a lie. */
import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MetricsRow } from "./MetricsRow";
import type { StatsSummary } from "../api/types";
import { renderWithProviders } from "../test/renderWithProviders";

function summary(overrides: Partial<StatsSummary> = {}): StatsSummary {
  return {
    games: 4,
    trophies: 37,
    trophies_per_hour: 24.7,
    avg_rank: 3.3,
    top4_rate: 75,
    hours_farmed: 1.53,
    ...overrides,
  };
}

function figure(label: string): HTMLElement {
  return screen.getByTestId(`metric-${label}`);
}

describe("MetricsRow", () => {
  it("shows the six labels in order", () => {
    renderWithProviders(<MetricsRow summary={summary()} />);
    const labels = screen.getAllByTestId(/^metric-/).map((node) => {
      const caption = node.querySelector("[data-label]");
      return caption?.textContent ?? "";
    });
    expect(labels).toEqual([
      "games",
      "trophies",
      "trophies per hour",
      "average rank",
      "top-4 rate",
      "time farmed",
    ]);
  });

  it("formats every figure", () => {
    renderWithProviders(<MetricsRow summary={summary()} />);
    expect(within(figure("games")).getByTestId("metric-value")).toHaveTextContent("4");
    expect(within(figure("trophies")).getByTestId("metric-value")).toHaveTextContent("+37");
    expect(within(figure("trophies per hour")).getByTestId("metric-value")).toHaveTextContent(
      "24.7",
    );
    expect(within(figure("average rank")).getByTestId("metric-value")).toHaveTextContent("3.3");
    expect(within(figure("top-4 rate")).getByTestId("metric-value")).toHaveTextContent("75%");
    expect(within(figure("time farmed")).getByTestId("metric-value")).toHaveTextContent("1.53 h");
  });

  it("tints the trophy figure by its sign", () => {
    const { unmount } = renderWithProviders(<MetricsRow summary={summary()} />);
    expect(within(figure("trophies")).getByTestId("metric-value")).toHaveClass("text-accent");
    unmount();
    const second = renderWithProviders(<MetricsRow summary={summary({ trophies: -12 })} />);
    expect(within(figure("trophies")).getByTestId("metric-value")).toHaveClass("text-bad");
    expect(within(figure("trophies")).getByTestId("metric-value")).toHaveTextContent("-12");
    second.unmount();
    renderWithProviders(<MetricsRow summary={summary({ trophies: 0 })} />);
    expect(within(figure("trophies")).getByTestId("metric-value")).toHaveClass("text-muted");
  });

  it("says after 30 min when the rate is null and games were played", () => {
    renderWithProviders(<MetricsRow summary={summary({ trophies_per_hour: null })} />);
    expect(within(figure("trophies per hour")).getByTestId("metric-value")).toHaveTextContent(
      "after 30 min",
    );
  });

  it("says none when there are no games at all", () => {
    renderWithProviders(
      <MetricsRow
        summary={summary({
          games: 0,
          trophies: 0,
          trophies_per_hour: null,
          avg_rank: null,
          top4_rate: null,
          hours_farmed: 0,
        })}
      />,
    );
    expect(within(figure("trophies per hour")).getByTestId("metric-value")).toHaveTextContent(
      "none",
    );
    expect(within(figure("average rank")).getByTestId("metric-value")).toHaveTextContent("none");
    expect(within(figure("top-4 rate")).getByTestId("metric-value")).toHaveTextContent("none");
  });

  it("gives every number tabular figures", () => {
    renderWithProviders(<MetricsRow summary={summary()} />);
    for (const node of screen.getAllByTestId("metric-value")) {
      expect(node).toHaveClass("font-mono");
      expect(node).toHaveClass("tabular-nums");
    }
  });
});
```

- [ ] **Step 9: Run it to verify it fails**

```bash
pnpm --dir brawlfarm/web test -- src/stats/MetricsRow.test.tsx
```

Expected: `Failed to resolve import "./MetricsRow"`.

- [ ] **Step 10: Write `MetricsRow`**

Create `brawlfarm/web/src/stats/MetricsRow.tsx`:

```tsx
/**
 * Six figures on one line: the value at 18 px and its label at 11 px muted under it,
 * separated by a 1 px rule. No tiles, no big numbers, no sparkline. The row is the
 * summary, so it is the one thing on the page that is always readable at a glance.
 *
 * Two placeholders stand in for numbers that would be a lie: "after 30 min" while the
 * range is too short for a rate to mean anything, and "none" when there is nothing at all
 * to average.
 */
import type { StatsSummary } from "../api/types";
import { signed } from "../lib/format";

export interface MetricsRowProps {
  summary: StatsSummary;
}

const NONE = "none";
const TOO_SHORT = "after 30 min";

function trophyTone(trophies: number): string {
  if (trophies > 0) return "text-accent";
  if (trophies < 0) return "text-bad";
  return "text-muted";
}

function rateText(summary: StatsSummary): string {
  if (summary.trophies_per_hour !== null) return String(summary.trophies_per_hour);
  return summary.games > 0 ? TOO_SHORT : NONE;
}

function Figure({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div
      data-testid={`metric-${label}`}
      className="flex min-w-0 flex-1 flex-col gap-0.5 border-l border-line px-3 first:border-l-0 first:pl-0"
    >
      <span
        data-testid="metric-value"
        className={`truncate font-mono text-[18px] tabular-nums ${tone ?? "text-text"}`}
      >
        {value}
      </span>
      <span data-label="" className="truncate text-[11px] text-muted">
        {label}
      </span>
    </div>
  );
}

export function MetricsRow({ summary }: MetricsRowProps) {
  return (
    <div className="flex flex-wrap items-start rounded-[10px] border border-line bg-panel px-3 py-2">
      <Figure label="games" value={String(summary.games)} />
      <Figure
        label="trophies"
        value={signed(summary.trophies)}
        tone={trophyTone(summary.trophies)}
      />
      <Figure label="trophies per hour" value={rateText(summary)} />
      <Figure
        label="average rank"
        value={summary.avg_rank === null ? NONE : summary.avg_rank.toFixed(1)}
      />
      <Figure
        label="top-4 rate"
        value={summary.top4_rate === null ? NONE : `${Math.round(summary.top4_rate)}%`}
      />
      <Figure label="time farmed" value={`${summary.hours_farmed.toFixed(2)} h`} />
    </div>
  );
}
```

- [ ] **Step 11: Run it to verify it passes**

```bash
pnpm --dir brawlfarm/web test -- src/stats/MetricsRow.test.tsx
```

Expected: 6 passed.

- [ ] **Step 12: Write the failing test for `StatsToolbar`**

Create `brawlfarm/web/src/stats/StatsToolbar.test.tsx`:

```tsx
/** The toolbar: four range radios with a radio group's keyboard, one chip per configured
 * instance that cannot all be turned off, and an export link carrying the current query. */
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { StatsToolbar } from "./StatsToolbar";
import { statsCsvHref } from "../api/stats";
import { renderWithProviders } from "../test/renderWithProviders";

function mount(overrides: Partial<Parameters<typeof StatsToolbar>[0]> = {}) {
  const props = {
    range: "7d" as const,
    instances: ["Pie64", "Pie64_1"],
    selected: ["Pie64", "Pie64_1"],
    onRange: vi.fn(),
    onInstances: vi.fn(),
    csvHref: statsCsvHref("7d", []),
    ...overrides,
  };
  renderWithProviders(<StatsToolbar {...props} />);
  return props;
}

describe("StatsToolbar", () => {
  it("shows the four ranges as one radio group", () => {
    mount();
    const group = screen.getByRole("radiogroup", { name: "Range" });
    expect(
      Array.from(group.querySelectorAll('[role="radio"]')).map((n) => n.textContent),
    ).toEqual(["Today", "7 days", "30 days", "All"]);
    expect(screen.getByRole("radio", { name: "7 days" })).toHaveAttribute("aria-checked", "true");
  });

  it("moves between the ranges with Left and Right", async () => {
    const props = mount();
    await userEvent.click(screen.getByRole("radio", { name: "7 days" }));
    props.onRange.mockClear();
    await userEvent.keyboard("{ArrowRight}");
    expect(props.onRange).toHaveBeenCalledWith("30d");
    props.onRange.mockClear();
    await userEvent.keyboard("{ArrowLeft}");
    expect(props.onRange).toHaveBeenCalledWith("today");
  });

  it("toggles one instance chip", async () => {
    const props = mount();
    await userEvent.click(screen.getByRole("button", { name: "Pie64_1" }));
    expect(props.onInstances).toHaveBeenCalledWith(["Pie64"]);
  });

  it("turns a chip back on", async () => {
    const props = mount({ selected: ["Pie64"] });
    expect(screen.getByRole("button", { name: "Pie64_1" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
    await userEvent.click(screen.getByRole("button", { name: "Pie64_1" }));
    expect(props.onInstances).toHaveBeenCalledWith(["Pie64", "Pie64_1"]);
  });

  it("refuses to turn off the last enabled chip", async () => {
    const props = mount({ selected: ["Pie64"] });
    await userEvent.click(screen.getByRole("button", { name: "Pie64" }));
    expect(props.onInstances).not.toHaveBeenCalled();
  });

  it("exports the current query as a download link", () => {
    mount({ range: "30d", csvHref: statsCsvHref("30d", ["Pie64"]) });
    const link = screen.getByRole("link", { name: "Export CSV" });
    expect(link).toHaveAttribute("href", "/api/stats/export.csv?range=30d&instances=Pie64");
    expect(link).toHaveAttribute("download");
  });
});
```

- [ ] **Step 13: Run it to verify it fails**

```bash
pnpm --dir brawlfarm/web test -- src/stats/StatsToolbar.test.tsx
```

Expected: `Failed to resolve import "./StatsToolbar"`.

- [ ] **Step 14: Write `StatsToolbar`**

Create `brawlfarm/web/src/stats/StatsToolbar.tsx`:

```tsx
/**
 * The row above everything: which range, which instances, and the export.
 *
 * The ranges are the phase 4 Segmented shape rather than a new component, so the "one of
 * these is selected" relationship and the radio group's keyboard come with them. The
 * chips are buttons with aria-pressed, because "which of these are on" is a different
 * question from "which one of these", and at least one always stays on: a selection of
 * nothing would silently mean every instance to the API, which is not what the last click
 * asked for.
 *
 * Export CSV is an anchor with download, not a fetch: the browser's own download is the
 * feedback, so there is no toast and no pending state to draw.
 */
import type { StatsRange } from "../api/types";
import { Segmented } from "../components/ui/Segmented";

export interface StatsToolbarProps {
  range: StatsRange;
  /** Every configured instance, in config.toml order: one chip each. */
  instances: string[];
  selected: string[];
  onRange: (next: StatsRange) => void;
  onInstances: (next: string[]) => void;
  csvHref: string;
}

export const RANGE_LABELS: Record<StatsRange, string> = {
  today: "Today",
  "7d": "7 days",
  "30d": "30 days",
  all: "All",
};

const RANGE_OPTIONS: readonly { value: StatsRange; label: string }[] = [
  { value: "today", label: RANGE_LABELS.today },
  { value: "7d", label: RANGE_LABELS["7d"] },
  { value: "30d", label: RANGE_LABELS["30d"] },
  { value: "all", label: RANGE_LABELS.all },
];

export function StatsToolbar({
  range,
  instances,
  selected,
  onRange,
  onInstances,
  csvHref,
}: StatsToolbarProps) {
  const toggle = (name: string) => {
    const on = selected.includes(name);
    if (on && selected.length === 1) return; // the last chip stays on
    const next = on ? selected.filter((n) => n !== name) : [...selected, name];
    onInstances(instances.filter((n) => next.includes(n)));
  };

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Segmented label="Range" value={range} options={RANGE_OPTIONS} onChange={onRange} />

      <div className="order-last flex w-full flex-wrap gap-1 min-[900px]:order-none min-[900px]:w-auto">
        {instances.map((name) => {
          const on = selected.includes(name);
          return (
            <button
              key={name}
              type="button"
              aria-pressed={on}
              onClick={() => toggle(name)}
              className={`h-6 rounded-[6px] border border-line px-2 font-mono text-[12px] transition-colors duration-[120ms] ${
                on ? "bg-panel-2 text-text" : "bg-panel text-muted hover:text-text"
              }`}
            >
              {name}
            </button>
          );
        })}
      </div>

      <a
        href={csvHref}
        download
        className="ml-auto inline-flex h-6 items-center rounded-[6px] border border-line px-2 text-[12px] text-muted transition-colors duration-[120ms] hover:text-text"
      >
        Export CSV
      </a>
    </div>
  );
}
```

- [ ] **Step 15: Run it to verify it passes**

```bash
pnpm --dir brawlfarm/web test -- src/stats/StatsToolbar.test.tsx
```

Expected: 6 passed.

- [ ] **Step 16: Write the failing test for the page**

Create `brawlfarm/web/src/stats/Stats.test.tsx`:

```tsx
/** The Stats page: the URL is the only place the range and the selection live, an unknown
 * instance in a stale link is dropped rather than 404ing, and the three states above the
 * data (skeleton, empty, error) are the ones the brief pins. */
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { Stats } from "./Stats";
import { makeConnection, makeInstance, makeStats } from "../test/fixtures";
import { type FetchCall, jsonResponse, stubFetch } from "../test/http";
import { renderWithProviders } from "../test/renderWithProviders";

afterEach(() => {
  vi.unstubAllGlobals();
});

/** Two configured instances, an aggregate, and an ok connection. `stats` overrides the
 * aggregate; `statsStatus` makes GET /api/stats fail. */
function server(
  options: { stats?: ReturnType<typeof makeStats>; statsStatus?: number } = {},
): FetchCall[] {
  return stubFetch((url) => {
    if (url === "/api/instances") {
      return jsonResponse({
        instances: [
          makeInstance({ name: "Pie64", player_tag: "#2P0YLQ9" }),
          makeInstance({ name: "Pie64_1", adb_port: 5565, player_tag: "#2P0YLQ9" }),
        ],
      });
    }
    if (url === "/api/connection/check") return jsonResponse(makeConnection());
    if (url.startsWith("/api/stats")) {
      if (options.statsStatus !== undefined) {
        return jsonResponse({ detail: "games.csv is unreadable" }, options.statsStatus);
      }
      return jsonResponse(options.stats ?? makeStats());
    }
    throw new Error(`unstubbed request: ${url}`);
  }).calls;
}

function mount(route = "/stats") {
  return renderWithProviders(
    <Routes>
      <Route path="/stats" element={<Stats />} />
    </Routes>,
    { route },
  );
}

function statsUrls(calls: FetchCall[]): string[] {
  return calls.filter((c) => c.url.startsWith("/api/stats?")).map((c) => c.url);
}

describe("Stats", () => {
  it("defaults to 7 days with no query string", async () => {
    const calls = server();
    mount();
    await waitFor(() => {
      expect(statsUrls(calls)).toEqual(["/api/stats?range=7d"]);
    });
    expect(await screen.findByRole("radio", { name: "7 days" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
  });

  it("reads the range and the selection out of the URL", async () => {
    const calls = server();
    mount("/stats?range=30d&instances=Pie64");
    await waitFor(() => {
      expect(statsUrls(calls)).toEqual(["/api/stats?range=30d&instances=Pie64"]);
    });
    expect(screen.getByRole("radio", { name: "30 days" })).toHaveAttribute(
      "aria-checked",
      "true",
    );
    expect(screen.getByRole("button", { name: "Pie64_1" })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });

  it("falls back to 7 days for an unparsable range", async () => {
    const calls = server();
    mount("/stats?range=fortnight");
    await waitFor(() => {
      expect(statsUrls(calls)).toEqual(["/api/stats?range=7d"]);
    });
  });

  it("drops a name that is not configured", async () => {
    const calls = server();
    mount("/stats?instances=Pie64,Ghost");
    await waitFor(() => {
      expect(statsUrls(calls)).toEqual(["/api/stats?range=7d&instances=Pie64"]);
    });
  });

  it("rewrites the URL and refetches when a chip is toggled", async () => {
    const calls = server();
    mount();
    await screen.findByRole("button", { name: "Pie64_1" });
    await userEvent.click(screen.getByRole("button", { name: "Pie64_1" }));
    await waitFor(() => {
      expect(statsUrls(calls)).toEqual([
        "/api/stats?range=7d",
        "/api/stats?range=7d&instances=Pie64",
      ]);
    });
    expect(screen.getByRole("link", { name: "Export CSV" })).toHaveAttribute(
      "href",
      "/api/stats/export.csv?range=7d&instances=Pie64",
    );
  });

  it("will not let the last enabled chip be turned off", async () => {
    const calls = server();
    mount("/stats?instances=Pie64");
    await screen.findByRole("button", { name: "Pie64" });
    await userEvent.click(screen.getByRole("button", { name: "Pie64" }));
    await waitFor(() => {
      expect(statsUrls(calls)).toEqual(["/api/stats?range=7d&instances=Pie64"]);
    });
  });

  it("shows the skeleton while the first request is in flight, and the toolbar with it", () => {
    stubFetch(() => new Promise<Response>(() => undefined));
    mount();
    expect(screen.getByTestId("stats-skeleton")).toBeInTheDocument();
    expect(screen.getByRole("radiogroup", { name: "Range" })).toBeInTheDocument();
    expect(screen.getByTestId("stats-skeleton").querySelectorAll("[data-block]")).toHaveLength(7);
  });

  it("shows the empty sentence and nothing below it when the range has no games", async () => {
    server({
      stats: makeStats({
        summary: {
          games: 0,
          trophies: 0,
          trophies_per_hour: null,
          avg_rank: null,
          top4_rate: null,
          hours_farmed: 0,
        },
        series: [],
        brawlers: [],
        ranks: [],
        recent: [],
      }),
    });
    mount();
    expect(await screen.findByText("Stats appear after the first match.")).toBeInTheDocument();
    expect(screen.getByRole("radiogroup", { name: "Range" })).toBeInTheDocument();
    expect(screen.queryByTestId("metrics-row")).toBeNull();
  });

  it("shows an ErrorBlock and nothing else when the request fails", async () => {
    server({ statsStatus: 500 });
    mount();
    expect(await screen.findByText("games.csv is unreadable")).toBeInTheDocument();
    expect(screen.queryByTestId("metrics-row")).toBeNull();
    expect(screen.queryByText("Stats appear after the first match.")).toBeNull();
  });

  it("shows the metrics row and the connection strip above it", async () => {
    stubFetch((url) => {
      if (url === "/api/instances") {
        return jsonResponse({ instances: [makeInstance({ name: "Pie64", player_tag: "" })] });
      }
      if (url === "/api/connection/check") {
        return jsonResponse(makeConnection({ status: "no_tag" }));
      }
      if (url.startsWith("/api/stats")) return jsonResponse(makeStats());
      throw new Error(`unstubbed request: ${url}`);
    });
    mount();
    expect(await screen.findByTestId("metrics-row")).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(
      "Add a player tag for Pie64 in Settings, Instances to see its games.",
    );
  });
});
```

- [ ] **Step 17: Run it to verify it fails**

```bash
pnpm --dir brawlfarm/web test -- src/stats/Stats.test.tsx
```

Expected: `Failed to resolve import "./Stats"`.

- [ ] **Step 18: Write `Stats.tsx`**

Create `brawlfarm/web/src/stats/Stats.tsx`. The chart and the band below the metrics row
arrive in tasks 7 and 8; this version renders everything above them and leaves one comment
where each goes:

```tsx
/**
 * The Stats screen.
 *
 * The URL is the single source of the range and the instance selection, so a reload keeps
 * the view and a link carries it. A name in ?instances= that is not configured is dropped
 * before the request goes out, which turns a stale link into a narrower selection rather
 * than a 404 from the route's own _selected. Every change is a replace, not a push, so
 * Back leaves Stats instead of walking the ranges.
 *
 * The stats query waits for GET /api/instances: dropping an unknown name needs the
 * configured list, and firing once without it and again with it would double every load.
 */
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router";

import { ConnectionStrip } from "./ConnectionStrip";
import { MetricsRow } from "./MetricsRow";
import { StatsToolbar } from "./StatsToolbar";
import { getConnection } from "../api/connection";
import { queryKeys } from "../api/queries";
import { getStats, statsCsvHref } from "../api/stats";
import type { StatsRange } from "../api/types";
import { useInstances } from "../api/useInstances";
import { ErrorBlock } from "../components/ui/ErrorBlock";

export const RANGES: readonly StatsRange[] = ["today", "7d", "30d", "all"];
const DEFAULT_RANGE: StatsRange = "7d";
/** The server caches its answer for five minutes, so asking again inside that window only
 * costs a round trip to be told the same thing. */
const CONNECTION_STALE_MS = 300_000;

/** An absent or unparsable range is 7 days: Today is empty every morning until the first
 * match, and an empty page is a worse first impression than a slightly wider one. */
export function parseRange(raw: string | null): StatsRange {
  return RANGES.includes((raw ?? "") as StatsRange) ? (raw as StatsRange) : DEFAULT_RANGE;
}

function Skeleton() {
  return (
    <div data-testid="stats-skeleton" className="flex flex-col gap-3">
      <div className="flex gap-3 rounded-[10px] border border-line bg-panel px-3 py-2">
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <div key={i} data-block="" className="h-[18px] flex-1 rounded-[4px] bg-panel-2" />
        ))}
      </div>
      <div data-block="" className="h-[180px] rounded-[10px] bg-panel-2" />
    </div>
  );
}

export function Stats() {
  const [params, setParams] = useSearchParams();
  const instancesQuery = useInstances();
  const configured = (instancesQuery.data ?? []).map((inst) => inst.name);

  const range = parseRange(params.get("range"));
  const asked = (params.get("instances") ?? "")
    .split(",")
    .map((name) => name.trim())
    .filter((name) => name !== "");
  const narrowed = configured.filter((name) => asked.includes(name));
  const selected = narrowed.length === 0 ? configured : narrowed;
  // Empty means "every configured instance", which is the API's own default, so a full
  // selection and no selection share one URL and one cache entry.
  const scope = selected.length === configured.length ? [] : selected;

  const stats = useQuery({
    queryKey: queryKeys.stats(range, scope),
    queryFn: () => getStats(range, scope),
    enabled: instancesQuery.isSuccess,
  });
  const connection = useQuery({
    queryKey: queryKeys.connection(),
    queryFn: getConnection,
    staleTime: CONNECTION_STALE_MS,
    refetchOnWindowFocus: false,
  });

  const write = (next: { range?: StatsRange; instances?: string[] }) => {
    const params2 = new URLSearchParams();
    const wantRange = next.range ?? range;
    const wantInstances = next.instances ?? selected;
    if (wantRange !== DEFAULT_RANGE) params2.set("range", wantRange);
    if (wantInstances.length !== configured.length) {
      params2.set("instances", wantInstances.join(","));
    }
    setParams(params2, { replace: true });
  };

  const instanceWithoutTag =
    (instancesQuery.data ?? []).find(
      (inst) => selected.includes(inst.name) && inst.player_tag.trim() === "",
    )?.name ?? null;

  const toolbar = (
    <StatsToolbar
      range={range}
      instances={configured}
      selected={selected}
      onRange={(next) => write({ range: next })}
      onInstances={(next) => write({ instances: next })}
      csvHref={statsCsvHref(range, scope)}
    />
  );
  const strip = (
    <ConnectionStrip
      status={connection.data?.status ?? "ok"}
      instanceWithoutTag={instanceWithoutTag}
    />
  );

  if (stats.isError) {
    return (
      <section className="flex flex-col gap-3">
        <h1 className="text-[28px] font-semibold tracking-tight">Stats</h1>
        {toolbar}
        <ErrorBlock error={stats.error} onRetry={() => void stats.refetch()} />
      </section>
    );
  }

  return (
    <section className="flex flex-col gap-3">
      <h1 className="text-[28px] font-semibold tracking-tight">Stats</h1>
      {toolbar}
      {/* Above the empty state on purpose: a missing token explains the empty page. */}
      {strip}
      {stats.data === undefined ? (
        <Skeleton />
      ) : stats.data.summary.games === 0 ? (
        <p className="text-[13px] text-muted">Stats appear after the first match.</p>
      ) : (
        <>
          <div data-testid="metrics-row">
            <MetricsRow summary={stats.data.summary} />
          </div>
          {/* task 7 puts TrophyChart here */}
          {/* task 8 puts the BrawlerTable / RankBars band and RecentGames here */}
        </>
      )}
    </section>
  );
}
```

- [ ] **Step 19: Run it to verify it passes**

```bash
pnpm --dir brawlfarm/web test -- src/stats/Stats.test.tsx
```

Expected: 10 passed. The skeleton case counts seven `[data-block]` nodes: six metric
blocks and the chart block.

- [ ] **Step 20: Swap the route**

In `brawlfarm/web/src/App.tsx`, replace the `Placeholder` import at line 16 with the Stats
import, keeping the block alphabetical by path:

```tsx
import { Shell } from "./app/Shell";
import { createQueryClient, queryKeys } from "./api/queries";
import { getSettings } from "./api/settings";
import { Toaster } from "./components/ui/Toast";
import { Fleet } from "./fleet/Fleet";
import { Instance } from "./instance/Instance";
import { onReconnect, subscribe } from "./live/useEvents";
import { Settings } from "./settings/Settings";
import { Setup } from "./setup/Setup";
import { Stats } from "./stats/Stats";
```

and replace line 87:

```tsx
        <Route path="/stats" element={<Stats />} />
```

`app/Placeholder.tsx` stays in the tree: nothing else imports it today, and it is the
shape phase 7 and 8 will want. `TopBar.pageTitle` already maps `/stats` to "Stats" and is
not touched.

- [ ] **Step 21: Everything green on the web side**

```bash
pnpm --dir brawlfarm/web typecheck
pnpm --dir brawlfarm/web test
pnpm --dir brawlfarm/web build
```

Expected: `tsc --noEmit` silent, every vitest file passing, `vite build` writes
`brawlfarm/web/dist/index.html`. `App.test.tsx` may assert the placeholder sentence
"Stats arrive in phase 6."; if it does, change that assertion to expect the Stats heading
and say so in the commit body.

- [ ] **Step 22: Commit**

```bash
uv run python tools/scrub_check.py && git add brawlfarm/web/src/api/types.ts brawlfarm/web/src/api/stats.ts brawlfarm/web/src/api/connection.ts brawlfarm/web/src/api/queries.ts brawlfarm/web/src/test/fixtures.ts brawlfarm/web/src/stats brawlfarm/web/src/App.tsx && git commit -m "feat(web): the Stats page, its toolbar, metrics and connection strip

/stats replaces the phase 4 placeholder. The URL is the only place the range
and the instance selection live, so a reload keeps the view and a link
carries it, and a name in a stale link that is no longer configured is
dropped rather than 404ing the route. Every change is a replace, so Back
leaves Stats instead of walking the ranges.

The stats query waits for the instance list: dropping an unknown name needs
the configured names, and firing once without them and again with them would
double every load.

Six figures on one line, with \"after 30 min\" where a rate would be an
extrapolation from noise. One strip under the toolbar carries the spec's four
sentences and their links, and sits above the empty state, because a missing
token is what explains an empty page.

Export CSV is an anchor with download, not a fetch: the browser's own
download is the feedback.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CQ1GimQ3uiR2sXPzfZLNWV"
```

Expected: `0 hit(s)`, then the commit.

---
### Task 7: `TrophyChart`

The brief's task 7. One hand-written SVG: the axis, the paths, the legend, the end labels,
the crosshair, the keyboard handling, the live region and the Table toggle. No library, no
animation, no transition, nothing to disable for reduced motion.

Only the paths and the two rules are drawn in SVG. Every piece of text is HTML positioned
over or beside the plot, because `preserveAspectRatio="none"` stretches the viewBox
horizontally and would stretch any `<text>` in it with the rest.

Accepted proposal ids covered: `stats-chart`.

**Files:**
- Create: `brawlfarm/web/src/stats/TrophyChart.tsx`
- Modify: `brawlfarm/web/src/stats/Stats.tsx` (the chart replaces its placeholder comment)
- Test: `brawlfarm/web/src/stats/TrophyChart.test.tsx` (create)
- Test: `brawlfarm/web/src/stats/Stats.test.tsx` (modify: one test appended)

**Interfaces:**
- Consumes: `StatsResponse["series"]` and the selected names from task 6, `Table`,
  `Column<Row>` and `TableProps<Row>` from `components/ui/Table.tsx` as they stand today
  (task 8 adds the optional sort props after this), `hhmm` from `lib/time.ts`,
  the tokens `--accent`, `--ok`, `--warn`, `--series-1`, `--series-2`, `--series-3`,
  `--line`, `--panel`, `--panel-2` and `--muted` in `styles/theme.css`.
- Produces:
  - `stats/TrophyChart.tsx`:
    `TrophyChartProps { series: StatsSeries[]; instances: string[] }`, `TrophyChart`,
    `SERIES_COLORS: readonly string[]`, `CHART_LABEL: string`
- Consumed by: task 8 (nothing; the band sits beside it), task 10 (the keyboard pass and
  the reduced-motion check name this component).

- [ ] **Step 1: Write the failing test**

Create `brawlfarm/web/src/stats/TrophyChart.test.tsx`:

```tsx
/** The chart: one path per series that has points, a legend that matches the chips, a
 * crosshair the keyboard can reach, a live region saying the same thing, a Table view of
 * the same numbers, and no motion anywhere. */
import { fireEvent, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { TrophyChart } from "./TrophyChart";
import type { StatsSeries } from "../api/types";
import { renderWithProviders } from "../test/renderWithProviders";

const SERIES: StatsSeries[] = [
  {
    instance: "Pie64",
    points: [
      { t: "2026-09-12T21:00:00", cum: 12 },
      { t: "2026-09-12T21:30:00", cum: 8 },
      { t: "2026-09-12T22:00:00", cum: 25 },
    ],
  },
  {
    instance: "Pie64_1",
    points: [
      { t: "2026-09-12T21:30:00", cum: -3 },
      { t: "2026-09-12T22:00:00", cum: 12 },
    ],
  },
  { instance: "Pie64_3", points: [] },
];

const INSTANCES = ["Pie64", "Pie64_1", "Pie64_3"];

function mount(series = SERIES, instances = INSTANCES) {
  return renderWithProviders(<TrophyChart series={series} instances={instances} />);
}

function plot(): HTMLElement {
  return screen.getByRole("img", { name: "Cumulative trophy change" });
}

describe("TrophyChart", () => {
  it("draws one path per series that has points", () => {
    const { container } = mount();
    expect(container.querySelectorAll("[data-series-path]")).toHaveLength(2);
  });

  it("gives every selected instance a legend entry, points or not", () => {
    mount();
    const legend = screen.getByTestId("chart-legend");
    expect(within(legend).getAllByTestId("legend-entry").map((n) => n.textContent)).toEqual([
      "Pie64",
      "Pie64_1",
      "Pie64_3",
    ]);
  });

  it("puts an end label on every series that has points", () => {
    const { container } = mount();
    expect(
      Array.from(container.querySelectorAll("[data-end-label]")).map((n) => n.textContent),
    ).toEqual(["Pie64", "Pie64_1"]);
  });

  it("is one tab stop, labelled, and keeps its stroke when the viewBox stretches", () => {
    const { container } = mount();
    expect(plot()).toHaveAttribute("tabindex", "0");
    expect(plot()).toHaveAttribute("viewBox", "0 0 640 180");
    expect(plot()).toHaveAttribute("preserveAspectRatio", "none");
    for (const path of container.querySelectorAll("[data-series-path]")) {
      expect(path).toHaveAttribute("vector-effect", "non-scaling-stroke");
    }
  });

  it("moves the crosshair with Left and Right and clears it with Escape", async () => {
    mount();
    plot().focus();
    expect(screen.queryByTestId("chart-readout")).toBeNull();
    await userEvent.keyboard("{ArrowRight}");
    expect(screen.getByTestId("chart-readout")).toHaveTextContent("21:00");
    await userEvent.keyboard("{ArrowRight}");
    expect(screen.getByTestId("chart-readout")).toHaveTextContent("21:30");
    await userEvent.keyboard("{ArrowLeft}");
    expect(screen.getByTestId("chart-readout")).toHaveTextContent("21:00");
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByTestId("chart-readout")).toBeNull();
  });

  it("jumps to the ends with Home and End", async () => {
    mount();
    plot().focus();
    await userEvent.keyboard("{End}");
    expect(screen.getByTestId("chart-readout")).toHaveTextContent("22:00");
    await userEvent.keyboard("{Home}");
    expect(screen.getByTestId("chart-readout")).toHaveTextContent("21:00");
  });

  it("draws the crosshair rule only while there is a crosshair", async () => {
    const { container } = mount();
    expect(container.querySelector("[data-crosshair]")).toBeNull();
    plot().focus();
    await userEvent.keyboard("{End}");
    expect(container.querySelector("[data-crosshair]")).not.toBeNull();
  });

  it("announces the same readout in a polite live region", async () => {
    mount();
    plot().focus();
    await userEvent.keyboard("{End}");
    const live = screen.getByTestId("chart-live");
    expect(live).toHaveAttribute("aria-live", "polite");
    expect(live).toHaveTextContent("22:00, Pie64: 25, Pie64_1: 12, Pie64_3: none");
  });

  it("reads none for a series with no point yet at that moment", async () => {
    mount();
    plot().focus();
    await userEvent.keyboard("{Home}");
    expect(screen.getByTestId("chart-readout")).toHaveTextContent("Pie64_1");
    expect(screen.getByTestId("chart-readout")).toHaveTextContent("none");
  });

  it("swaps to a table of the same points and back, with the toggle reading Table both ways", async () => {
    mount();
    const toggle = screen.getByRole("button", { name: "Table" });
    expect(plot()).toBeInTheDocument();
    await userEvent.click(toggle);
    expect(screen.queryByRole("img", { name: "Cumulative trophy change" })).toBeNull();
    const table = screen.getByRole("table");
    expect(within(table).getAllByRole("columnheader").map((n) => n.textContent)).toEqual([
      "Time",
      "Pie64",
      "Pie64_1",
      "Pie64_3",
    ]);
    expect(within(table).getAllByRole("row")).toHaveLength(4); // header plus three moments
    expect(screen.getByRole("button", { name: "Table" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Table" }));
    expect(plot()).toBeInTheDocument();
  });

  it("has no transition and no animation on any element", () => {
    const { container } = mount();
    expect(container.querySelectorAll('[class*="transition"]')).toHaveLength(0);
    expect(container.querySelectorAll('[class*="animate"]')).toHaveLength(0);
    expect(container.querySelectorAll('[class*="duration-"]')).toHaveLength(0);
    for (const node of container.querySelectorAll<HTMLElement>("*")) {
      expect(node.style.transition).toBe("");
      expect(node.style.animation).toBe("");
    }
  });

  it("moves the crosshair on a pointer move and drops it on leave", () => {
    mount();
    const svg = plot();
    Object.defineProperty(svg, "clientWidth", { value: 640, configurable: true });
    fireEvent.mouseMove(svg, { clientX: 0 });
    expect(screen.getByTestId("chart-readout")).toBeInTheDocument();
    fireEvent.mouseLeave(svg);
    expect(screen.queryByTestId("chart-readout")).toBeNull();
  });

  it("draws nothing but the legend when no series has a point", () => {
    const { container } = mount([{ instance: "Pie64", points: [] }], ["Pie64"]);
    expect(container.querySelectorAll("[data-series-path]")).toHaveLength(0);
    expect(screen.getAllByTestId("legend-entry")).toHaveLength(1);
    expect(screen.getByTestId("chart-empty")).toHaveTextContent("No games in this range.");
  });
});
```

- [ ] **Step 2: Run it to verify it fails**

```bash
pnpm --dir brawlfarm/web test -- src/stats/TrophyChart.test.tsx
```

Expected: `Failed to resolve import "./TrophyChart"`.

- [ ] **Step 3: Write `TrophyChart`**

Create `brawlfarm/web/src/stats/TrophyChart.tsx`:

```tsx
/**
 * Cumulative trophy change, one line per instance, drawn by hand.
 *
 * There is no chart library here and there is not going to be one: this draws two rules
 * and a handful of polylines, and a dependency that renders its own DOM would also bring
 * its own focus behaviour, its own colours and its own animations, all three of which the
 * panel already decided.
 *
 * Only the paths and the two 1 px rules are SVG. Every piece of text is HTML positioned
 * over or beside the plot, because preserveAspectRatio="none" stretches the viewBox to the
 * panel's width and would stretch a <text> with it. The stroke survives that stretch
 * through vectorEffect="non-scaling-stroke".
 *
 * Nothing here animates. No draw-in, no transition on the crosshair, no easing, so there
 * is nothing for prefers-reduced-motion to turn off.
 *
 * The crosshair is reachable two ways and says the same thing both times: the pointer
 * moves it, and so do Left, Right, Home, End and Escape, with a polite live region
 * carrying the readout for a reader who cannot see the panel beside it.
 */
import { type KeyboardEvent, type MouseEvent, useState } from "react";

import type { StatsPoint, StatsSeries } from "../api/types";
import { Table, type Column } from "../components/ui/Table";
import { hhmm } from "../lib/time";

export interface TrophyChartProps {
  series: StatsSeries[];
  /** Every selected instance, in the order the chips are in. The legend follows this, so
   * an instance with no games still appears and the legend matches the chips. */
  instances: string[];
}

export const CHART_LABEL = "Cumulative trophy change";

/** In series order, cycling. Every one of these exists in styles/theme.css; the proposal
 * named an "--info" tone, which does not. */
export const SERIES_COLORS: readonly string[] = [
  "var(--accent)",
  "var(--ok)",
  "var(--warn)",
  "var(--series-1)",
  "var(--series-2)",
  "var(--series-3)",
];

const PLOT_W = 640;
const PLOT_H = 180;
const PAD_Y = 10; // so a point at the very top or bottom is not half a stroke off the box
const VALUE_PAD = 0.05; // the brief's 5 %
const EMPTY = "No games in this range.";
const NONE = "none";
/** hhmm is the panel's one clock format: the recent games table and the session caption
 * both use it, so the crosshair and the ends read the same way they do. */
const clock = hhmm;

function colorFor(index: number): string {
  return SERIES_COLORS[index % SERIES_COLORS.length];
}

function msOf(point: StatsPoint): number {
  return new Date(point.t).getTime();
}

/** The value this series had at `moment`, stepping: the last point at or before it, or
 * null when the instance had not logged a game yet. */
function valueAt(points: StatsPoint[], moment: number): number | null {
  let found: number | null = null;
  for (const point of points) {
    if (msOf(point) > moment) break;
    found = point.cum;
  }
  return found;
}

export function TrophyChart({ series, instances }: TrophyChartProps) {
  const [showTable, setShowTable] = useState(false);
  const [hover, setHover] = useState<number | null>(null);
  const [cursor, setCursor] = useState<number | null>(null);
  const active = hover ?? cursor;

  // The legend follows the chips, so an instance the API sent no entry for still shows.
  const ordered: StatsSeries[] = instances.map(
    (name) => series.find((s) => s.instance === name) ?? { instance: name, points: [] },
  );
  const drawn = ordered.filter((s) => s.points.length > 0);

  const moments = Array.from(
    new Set(ordered.flatMap((s) => s.points.map(msOf))),
  ).sort((a, b) => a - b);

  const values = drawn.flatMap((s) => s.points.map((p) => p.cum));
  // Zero is always in the domain, because the rule at zero is what the lines are read
  // against. A flat series gets a span of 1 rather than a division by zero.
  const rawLo = Math.min(0, ...values);
  const rawHi = Math.max(0, ...values);
  const span = rawHi - rawLo || 1;
  const lo = rawLo - span * VALUE_PAD;
  const hi = rawHi + span * VALUE_PAD;
  const firstMs = moments[0] ?? 0;
  const lastMs = moments[moments.length - 1] ?? 0;
  const timeSpan = lastMs - firstMs;

  const xFor = (ms: number): number =>
    timeSpan === 0 ? PLOT_W / 2 : ((ms - firstMs) / timeSpan) * PLOT_W;
  const yFor = (value: number): number =>
    PAD_Y + ((hi - value) / (hi - lo)) * (PLOT_H - PAD_Y * 2);
  const topPercent = (y: number): string => `${(y / PLOT_H) * 100}%`;

  const pathOf = (points: StatsPoint[]): string =>
    points
      .map((p, i) => `${i === 0 ? "M" : "L"}${xFor(msOf(p)).toFixed(2)},${yFor(p.cum).toFixed(2)}`)
      .join(" ");

  /** The end labels, nudged down in turn so two instances that finish on the same number
   * are both readable. 12 px is the line box at 11 px type. Sorted by y first, so the
   * nudge only ever pushes a label away from the one above it. */
  const placed: { name: string; color: string; y: number }[] = [];
  for (const label of ordered
    .map((s, index) => ({
      name: s.instance,
      color: colorFor(index),
      y: s.points.length === 0 ? null : yFor(s.points[s.points.length - 1].cum),
    }))
    .filter((label): label is { name: string; color: string; y: number } => label.y !== null)
    .sort((a, b) => a.y - b.y)) {
    const above = placed[placed.length - 1];
    placed.push({ ...label, y: above === undefined ? label.y : Math.max(label.y, above.y + 12) });
  }
  const endLabels = placed;

  const readout =
    active === null
      ? null
      : {
          time: clock(new Date(moments[active]).toISOString()),
          lines: ordered.map((s) => {
            const value = valueAt(s.points, moments[active]);
            return { name: s.instance, text: value === null ? NONE : String(value) };
          }),
        };
  const liveText =
    readout === null
      ? ""
      : `${readout.time}, ${readout.lines.map((l) => `${l.name}: ${l.text}`).join(", ")}`;

  const onKeyDown = (event: KeyboardEvent<SVGSVGElement>) => {
    if (moments.length === 0) return;
    const last = moments.length - 1;
    let next: number | null | undefined;
    if (event.key === "ArrowRight") next = Math.min(last, (cursor ?? -1) + 1);
    else if (event.key === "ArrowLeft") next = Math.max(0, (cursor ?? 1) - 1);
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = last;
    else if (event.key === "Escape") next = null;
    if (next === undefined) return;
    event.preventDefault();
    setHover(null);
    setCursor(next);
  };

  const onMouseMove = (event: MouseEvent<SVGSVGElement>) => {
    if (moments.length === 0) return;
    const box = event.currentTarget.getBoundingClientRect();
    const width = box.width || event.currentTarget.clientWidth || PLOT_W;
    const ratio = Math.min(1, Math.max(0, (event.clientX - box.left) / width));
    setHover(Math.round(ratio * (moments.length - 1)));
  };

  const columns: Column<{ t: string; values: (number | null)[] }>[] = [
    { key: "t", label: "Time", mono: true, width: "80px", render: (row) => clock(row.t) },
    ...ordered.map((s, index) => ({
      key: s.instance,
      label: s.instance,
      mono: true,
      render: (row: { t: string; values: (number | null)[] }) =>
        row.values[index] === null ? NONE : String(row.values[index]),
    })),
  ];
  const rows = moments.map((ms) => ({
    t: new Date(ms).toISOString(),
    values: ordered.map((s) => valueAt(s.points, ms)),
  }));

  return (
    <section className="flex flex-col gap-2 rounded-[10px] border border-line bg-panel p-3">
      <div className="flex items-center gap-3">
        <div data-testid="chart-legend" className="flex flex-wrap items-center gap-3">
          {ordered.map((s, index) => (
            <span
              key={s.instance}
              data-testid="legend-entry"
              className="inline-flex items-center gap-1.5 text-[11px] text-muted"
            >
              <span
                aria-hidden="true"
                className="h-2 w-2 rounded-full"
                style={{ background: colorFor(index) }}
              />
              {s.instance}
            </span>
          ))}
        </div>
        <button
          type="button"
          onClick={() => setShowTable((open) => !open)}
          className="ml-auto text-[12px] text-muted hover:text-text"
        >
          Table
        </button>
      </div>

      {showTable ? (
        <Table
          columns={columns}
          rows={rows}
          rowKey={(row) => row.t}
          empty={EMPTY}
        />
      ) : moments.length === 0 ? (
        <p data-testid="chart-empty" className="h-[180px] text-[13px] text-muted">
          {EMPTY}
        </p>
      ) : (
        <>
          <div className="flex gap-2">
            <div className="relative w-[44px] shrink-0" style={{ height: `${PLOT_H}px` }}>
              <span
                className="absolute right-0 -translate-y-1/2 text-[11px] tabular-nums text-muted"
                style={{ top: topPercent(yFor(rawHi)) }}
              >
                {rawHi}
              </span>
              <span
                className="absolute right-0 -translate-y-1/2 text-[11px] tabular-nums text-muted"
                style={{ top: topPercent(yFor(0)) }}
              >
                0
              </span>
              <span
                className="absolute right-0 -translate-y-1/2 text-[11px] tabular-nums text-muted"
                style={{ top: topPercent(yFor(rawLo)) }}
              >
                {rawLo}
              </span>
            </div>

            <div
              className="relative min-w-0 flex-1 pr-[72px]"
              style={{ height: `${PLOT_H}px` }}
            >
              <svg
                role="img"
                aria-label={CHART_LABEL}
                tabIndex={0}
                viewBox={`0 0 ${PLOT_W} ${PLOT_H}`}
                preserveAspectRatio="none"
                onKeyDown={onKeyDown}
                onMouseMove={onMouseMove}
                onMouseLeave={() => setHover(null)}
                className="block h-full w-full focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
              >
                <line
                  x1={0}
                  x2={PLOT_W}
                  y1={yFor(0)}
                  y2={yFor(0)}
                  stroke="var(--line)"
                  strokeWidth={1}
                  vectorEffect="non-scaling-stroke"
                />
                {active === null ? null : (
                  <line
                    data-crosshair=""
                    x1={xFor(moments[active])}
                    x2={xFor(moments[active])}
                    y1={0}
                    y2={PLOT_H}
                    stroke="var(--line)"
                    strokeWidth={1}
                    vectorEffect="non-scaling-stroke"
                  />
                )}
                {ordered.map((s, index) =>
                  s.points.length === 0 ? null : (
                    <path
                      key={s.instance}
                      data-series-path=""
                      d={pathOf(s.points)}
                      fill="none"
                      stroke={colorFor(index)}
                      strokeWidth={1.5}
                      strokeLinejoin="round"
                      strokeLinecap="round"
                      vectorEffect="non-scaling-stroke"
                    />
                  ),
                )}
              </svg>

              {endLabels.map((label) => (
                <span
                  key={label.name}
                  data-end-label=""
                  className="absolute right-0 w-[68px] -translate-y-1/2 truncate pl-1 text-[11px]"
                  style={{ top: topPercent(label.y), color: label.color }}
                >
                  {label.name}
                </span>
              ))}
            </div>
          </div>

          <div className="flex justify-between pl-[52px] pr-[72px] text-[11px] tabular-nums text-muted">
            <span>{clock(new Date(firstMs).toISOString())}</span>
            <span>{clock(new Date(lastMs).toISOString())}</span>
          </div>

          {readout === null ? null : (
            <div
              data-testid="chart-readout"
              className="rounded-[6px] border border-line bg-panel-2 px-2 py-1 text-[11px]"
            >
              <span className="font-mono tabular-nums text-muted">{readout.time}</span>
              {readout.lines.map((line) => (
                <span key={line.name} className="ml-3 font-mono tabular-nums">
                  {line.name}: {line.text}
                </span>
              ))}
            </div>
          )}
        </>
      )}

      <span data-testid="chart-live" aria-live="polite" className="sr-only">
        {liveText}
      </span>
    </section>
  );
}
```

- [ ] **Step 4: Run it to verify it passes**

```bash
pnpm --dir brawlfarm/web test -- src/stats/TrophyChart.test.tsx
```

Expected: 13 passed.

- [ ] **Step 5: Put the chart on the page**

In `brawlfarm/web/src/stats/Stats.tsx`, add the import beside the other stats imports:

```tsx
import { StatsToolbar } from "./StatsToolbar";
import { TrophyChart } from "./TrophyChart";
```

and replace the placeholder comment left by task 6:

```tsx
          <div data-testid="metrics-row">
            <MetricsRow summary={stats.data.summary} />
          </div>
          <TrophyChart series={stats.data.series} instances={selected} />
          {/* task 8 puts the BrawlerTable / RankBars band and RecentGames here */}
```

- [ ] **Step 6: Write the failing page test for the chart**

Append to `brawlfarm/web/src/stats/Stats.test.tsx`, inside its `describe`:

```tsx
  it("draws the chart for the selection, legend and all", async () => {
    server();
    mount();
    expect(
      await screen.findByRole("img", { name: "Cumulative trophy change" }),
    ).toBeInTheDocument();
    expect(screen.getAllByTestId("legend-entry").map((n) => n.textContent)).toEqual([
      "Pie64",
      "Pie64_1",
    ]);
  });
```

- [ ] **Step 7: Run the page tests to verify they pass**

```bash
pnpm --dir brawlfarm/web test -- src/stats/Stats.test.tsx
```

Expected: 11 passed. The empty-state case still shows no chart, because `summary.games`
is 0 and the whole block below the strip is the empty sentence.

- [ ] **Step 8: Everything green on the web side**

```bash
pnpm --dir brawlfarm/web typecheck
pnpm --dir brawlfarm/web test
pnpm --dir brawlfarm/web build
```

Expected: `tsc --noEmit` silent, every vitest file passing, `vite build` writes
`brawlfarm/web/dist/index.html`.

- [ ] **Step 9: Commit**

```bash
uv run python tools/scrub_check.py && git add brawlfarm/web/src/stats/TrophyChart.tsx brawlfarm/web/src/stats/TrophyChart.test.tsx brawlfarm/web/src/stats/Stats.tsx brawlfarm/web/src/stats/Stats.test.tsx && git commit -m "feat(stats): a hand-drawn cumulative trophy chart

No chart library. This draws two rules and a handful of polylines, and a
dependency that renders its own DOM would bring its own focus behaviour, its
own colours and its own animations, all three of which the panel already
decided.

Only the paths and the rules are SVG: preserveAspectRatio is none, so every
piece of text is HTML beside or over the plot rather than a <text> that would
stretch with the viewBox. The stroke survives the stretch through
vectorEffect.

The crosshair is reachable with the pointer and with Left, Right, Home, End
and Escape, and a polite live region carries the same readout. A Table toggle
shows the same points as rows. Nothing animates, so there is nothing for
prefers-reduced-motion to switch off.

The series colours are only tokens that exist: accent, ok, warn and the three
series tones. The proposal named an --info tone, which theme.css does not
have.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CQ1GimQ3uiR2sXPzfZLNWV"
```

Expected: `0 hit(s)`, then the commit.

---
### Task 8: Table sorting, brawlers, ranks, recent

The brief's task 8. `Table` gains three optional props and changes nothing else, so every
phase 5 call site renders byte-for-byte as it does today. Then the two-column band and the
recent list on top of it.

Sorting is the caller's job. `Table` never reorders `rows`: it draws the header buttons,
writes `aria-sort` and calls back.

Accepted proposal ids covered: `stats-brawlers`, `stats-ranks`, `stats-recent`.

**Files:**
- Modify: `brawlfarm/web/src/components/ui/Table.tsx:20-36` (the two interfaces), `:38-62` (the header)
- Create: `brawlfarm/web/src/stats/BrawlerTable.tsx`
- Create: `brawlfarm/web/src/stats/RankBars.tsx`
- Create: `brawlfarm/web/src/stats/RecentGames.tsx`
- Modify: `brawlfarm/web/src/stats/Stats.tsx` (the band and the list replace the placeholder comment)
- Test: `brawlfarm/web/src/components/ui/Table.test.tsx` (modify: four tests appended)
- Test: `brawlfarm/web/src/stats/BrawlerTable.test.tsx` (create)
- Test: `brawlfarm/web/src/stats/RankBars.test.tsx` (create)
- Test: `brawlfarm/web/src/stats/RecentGames.test.tsx` (create)
- Test: `brawlfarm/web/src/stats/Stats.test.tsx` (modify: one test appended)

**Interfaces:**
- Consumes: `StatsResponse["brawlers"]`, `["ranks"]` and `["recent"]` from task 6,
  `BrawlerIcon` from task 5, `signed` from `lib/format.ts`, `hhmm` from `lib/time.ts`,
  `ChevronDown` and `ChevronUp` from `lucide-react`.
- Produces:
  - `components/ui/Table.tsx`: `Column<Row>` gains `sortable?: boolean`; `TableProps<Row>`
    gains `sort?: { key: string; dir: "asc" | "desc" }` and `onSort?: (key: string) => void`
  - `stats/BrawlerTable.tsx`: `BrawlerTableProps { rows: StatsBrawler[] }`, `BrawlerTable`
  - `stats/RankBars.tsx`: `RankBarsProps { rows: StatsRank[] }`, `RankBars`
  - `stats/RecentGames.tsx`: `RecentGamesProps { rows: StatsGame[] }`, `RecentGames`
- Consumed by: task 10 (the keyboard and focus pass names the sortable headers).

- [ ] **Step 1: Write the failing tests for `Table`**

Append to `brawlfarm/web/src/components/ui/Table.test.tsx`, inside its existing
`describe`. The `Row` type and the `columns`/`rows` this file already builds are what the
first case reuses; these four bring their own so they read on their own:

```tsx
  it("writes no aria-sort and no header button without the new props", () => {
    renderWithProviders(
      <Table
        columns={[
          { key: "name", label: "Brawler", sortable: true },
          { key: "games", label: "Games", sortable: true },
        ]}
        rows={[{ name: "NORI", games: 3 }]}
        rowKey={(row) => row.name}
        empty="No games in this range."
      />,
    );
    for (const header of screen.getAllByRole("columnheader")) {
      expect(header).not.toHaveAttribute("aria-sort");
      expect(within(header).queryByRole("button")).toBeNull();
    }
  });

  it("writes aria-sort on the sorted column and none on the others", () => {
    renderWithProviders(
      <Table
        columns={[
          { key: "name", label: "Brawler", sortable: true },
          { key: "games", label: "Games", sortable: true },
          { key: "icon", label: "", width: "34px" },
        ]}
        rows={[{ name: "NORI", games: 3 }]}
        rowKey={(row) => row.name}
        empty="No games in this range."
        sort={{ key: "games", dir: "desc" }}
        onSort={() => undefined}
      />,
    );
    expect(screen.getByRole("columnheader", { name: "Games" })).toHaveAttribute(
      "aria-sort",
      "descending",
    );
    expect(screen.getByRole("columnheader", { name: "Brawler" })).toHaveAttribute(
      "aria-sort",
      "none",
    );
    // A column that is not sortable gets no aria-sort at all, sorted table or not.
    expect(screen.getByRole("columnheader", { name: "icon" })).not.toHaveAttribute("aria-sort");
  });

  it("calls onSort once per header click, with that column's key", async () => {
    const onSort = vi.fn();
    renderWithProviders(
      <Table
        columns={[
          { key: "name", label: "Brawler", sortable: true },
          { key: "games", label: "Games", sortable: true },
        ]}
        rows={[{ name: "NORI", games: 3 }]}
        rowKey={(row) => row.name}
        empty="No games in this range."
        sort={{ key: "games", dir: "desc" }}
        onSort={onSort}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Brawler" }));
    expect(onSort).toHaveBeenCalledTimes(1);
    expect(onSort).toHaveBeenCalledWith("name");
  });

  it("never reorders the rows it was given", () => {
    renderWithProviders(
      <Table
        columns={[{ key: "name", label: "Brawler", sortable: true, render: (r) => r.name }]}
        rows={[{ name: "SHELLY", games: 1 }, { name: "NORI", games: 3 }]}
        rowKey={(row) => row.name}
        empty="No games in this range."
        sort={{ key: "name", dir: "asc" }}
        onSort={() => undefined}
      />,
    );
    const cells = screen.getAllByRole("cell").map((cell) => cell.textContent);
    expect(cells).toEqual(["SHELLY", "NORI"]);
  });
```

If this file does not already import `userEvent`, `vi` or `within`, add them to its
existing imports.

- [ ] **Step 2: Run them to verify they fail**

```bash
pnpm --dir brawlfarm/web test -- src/components/ui/Table.test.tsx
```

Expected: the existing cases pass, and the four new ones fail at typecheck time in the
runner with `Object literal may only specify known properties, and 'sortable' does not
exist in type 'Column<...>'`, or at run time with a missing `aria-sort`.

- [ ] **Step 3: Add the three props to `Table`**

In `brawlfarm/web/src/components/ui/Table.tsx`, extend the module comment with one
paragraph after the existing ones:

```
 * Sorting is opt-in and is the caller's job. With `sort` and `onSort` a sortable column's
 * label becomes a full-width button and its <th> carries aria-sort; without them no header
 * is a button and no aria-sort is written, so every call site that predates this renders
 * exactly as it did. The table never reorders `rows`: the caller owns the order, because
 * only the caller knows how to compare its own values.
```

Replace the two interfaces at lines 22 to 36:

```tsx
export interface Column<Row> {
  key: string;
  label: string;
  mono?: boolean;
  /** A CSS track for this column, e.g. "120px", written onto its <col>. */
  width?: string;
  render?: (row: Row) => ReactNode;
  sortable?: boolean;
}

export interface TableProps<Row> {
  columns: readonly Column<Row>[];
  rows: readonly Row[];
  rowKey: (row: Row) => string;
  empty: ReactNode;
  sort?: { key: string; dir: "asc" | "desc" };
  onSort?: (key: string) => void;
}
```

Replace the component's signature and its `<thead>` (lines 38 to 62):

```tsx
export function Table<Row>({ columns, rows, rowKey, empty, sort, onSort }: TableProps<Row>) {
  const sorting = sort !== undefined && onSort !== undefined;

  const ariaSort = (column: Column<Row>): "ascending" | "descending" | "none" | undefined => {
    if (!sorting || column.sortable !== true) return undefined;
    if (sort.key !== column.key) return "none";
    return sort.dir === "asc" ? "ascending" : "descending";
  };

  return (
    <div className="relative overflow-x-auto">
      <table className="w-full border-collapse text-[13px]">
        <colgroup>
          {columns.map((column) => (
            <col
              key={column.key}
              style={column.width === undefined ? undefined : { width: column.width }}
            />
          ))}
        </colgroup>
        <thead>
          <tr className="border-b border-line">
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                aria-sort={ariaSort(column)}
                className="px-2 py-1.5 text-left text-[11px] font-medium uppercase tracking-wide text-muted"
              >
                {sorting && column.sortable === true ? (
                  <button
                    type="button"
                    onClick={() => onSort(column.key)}
                    className="flex w-full items-center gap-1 text-left uppercase tracking-wide"
                  >
                    {column.label === "" ? (
                      <span className="sr-only">{column.key}</span>
                    ) : (
                      column.label
                    )}
                    {sort.key === column.key ? (
                      sort.dir === "asc" ? (
                        <ChevronUp aria-hidden="true" size={12} strokeWidth={1.6} />
                      ) : (
                        <ChevronDown aria-hidden="true" size={12} strokeWidth={1.6} />
                      )
                    ) : null}
                  </button>
                ) : column.label === "" ? (
                  <span className="sr-only">{column.key}</span>
                ) : (
                  column.label
                )}
              </th>
            ))}
          </tr>
        </thead>
```

Add the icon import at the top of the file, above the type import:

```tsx
import { ChevronDown, ChevronUp } from "lucide-react";
import type { ReactNode } from "react";
```

The `<tbody>` is not touched.

- [ ] **Step 4: Run the whole Table file to verify it passes**

```bash
pnpm --dir brawlfarm/web test -- src/components/ui/Table.test.tsx
```

Expected: every existing case passes with no edit, plus the four new ones.

- [ ] **Step 5: Run the two phase 5 tables to prove nothing moved**

```bash
pnpm --dir brawlfarm/web test -- src/settings/Instances.test.tsx src/setup/StepInstances.test.tsx
```

Expected: both files pass untouched. They are the regression gate on the "byte-for-byte"
claim: neither passes `sort` or `onSort`, so neither gets a header button.

- [ ] **Step 6: Write the failing test for `BrawlerTable`**

Create `brawlfarm/web/src/stats/BrawlerTable.test.tsx`:

```tsx
/** The per-brawler table: games descending by default, a click that sorts descending
 * first and then toggles, aria-sort following it, and an icon in front of every name. */
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { BrawlerTable } from "./BrawlerTable";
import type { StatsBrawler } from "../api/types";
import { renderWithProviders } from "../test/renderWithProviders";

const ROWS: StatsBrawler[] = [
  { name: "NORI", games: 3, net: 29, avg_rank: 2.7, top4_rate: 100 },
  { name: "SHELLY", games: 1, net: -8, avg_rank: 5, top4_rate: 0 },
  { name: "COLT", games: 3, net: 4, avg_rank: 4.5, top4_rate: 50 },
];

function names(): string[] {
  return screen
    .getAllByRole("row")
    .slice(1)
    .map((row) => within(row).getAllByRole("cell")[1].textContent ?? "");
}

describe("BrawlerTable", () => {
  it("shows the six columns", () => {
    renderWithProviders(<BrawlerTable rows={ROWS} />);
    expect(screen.getAllByRole("columnheader").map((n) => n.textContent)).toEqual([
      "icon",
      "Brawler",
      "Games",
      "Net",
      "Avg rank",
      "Top 4",
    ]);
  });

  it("starts games descending, with name ascending breaking the tie", () => {
    renderWithProviders(<BrawlerTable rows={ROWS} />);
    expect(names()).toEqual(["COLT", "NORI", "SHELLY"]);
    expect(screen.getByRole("columnheader", { name: /Games/ })).toHaveAttribute(
      "aria-sort",
      "descending",
    );
  });

  it("sorts a new column descending first, then toggles it", async () => {
    renderWithProviders(<BrawlerTable rows={ROWS} />);
    await userEvent.click(screen.getByRole("button", { name: /Net/ }));
    expect(names()).toEqual(["NORI", "COLT", "SHELLY"]);
    expect(screen.getByRole("columnheader", { name: /Net/ })).toHaveAttribute(
      "aria-sort",
      "descending",
    );
    await userEvent.click(screen.getByRole("button", { name: /Net/ }));
    expect(names()).toEqual(["SHELLY", "COLT", "NORI"]);
    expect(screen.getByRole("columnheader", { name: /Net/ })).toHaveAttribute(
      "aria-sort",
      "ascending",
    );
    expect(screen.getByRole("columnheader", { name: /Games/ })).toHaveAttribute(
      "aria-sort",
      "none",
    );
  });

  it("sorts by name too", async () => {
    renderWithProviders(<BrawlerTable rows={ROWS} />);
    await userEvent.click(screen.getByRole("button", { name: /Brawler/ }));
    expect(names()).toEqual(["SHELLY", "NORI", "COLT"]);
  });

  it("puts a null avg rank and a null top-4 rate last, whichever way it is sorted", async () => {
    renderWithProviders(
      <BrawlerTable
        rows={[
          { name: "NORI", games: 1, net: 3, avg_rank: null, top4_rate: null },
          { name: "COLT", games: 1, net: 3, avg_rank: 2, top4_rate: 50 },
        ]}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: /Avg rank/ }));
    expect(names()).toEqual(["COLT", "NORI"]);
    await userEvent.click(screen.getByRole("button", { name: /Avg rank/ }));
    expect(names()).toEqual(["COLT", "NORI"]);
  });

  it("tints the net figure by its sign and shows its sign", () => {
    renderWithProviders(<BrawlerTable rows={ROWS} />);
    const shelly = screen.getAllByRole("row").find((r) => r.textContent?.includes("SHELLY"));
    expect(within(shelly as HTMLElement).getByTestId("brawler-net")).toHaveTextContent("-8");
    expect(within(shelly as HTMLElement).getByTestId("brawler-net")).toHaveClass("text-bad");
  });

  it("gives every row an icon and the icon column no sort button", () => {
    renderWithProviders(<BrawlerTable rows={ROWS} />);
    expect(screen.getAllByTestId("brawler-icon")).toHaveLength(3);
    expect(
      within(screen.getByRole("columnheader", { name: "icon" })).queryByRole("button"),
    ).toBeNull();
  });

  it("says so when the range has no games", () => {
    renderWithProviders(<BrawlerTable rows={[]} />);
    expect(screen.getByText("No games in this range.")).toBeInTheDocument();
  });
});
```

- [ ] **Step 7: Run it to verify it fails**

```bash
pnpm --dir brawlfarm/web test -- src/stats/BrawlerTable.test.tsx
```

Expected: `Failed to resolve import "./BrawlerTable"`.

- [ ] **Step 8: Write `BrawlerTable`**

Create `brawlfarm/web/src/stats/BrawlerTable.tsx`:

```tsx
/**
 * Which brawlers did the farming, and how they did.
 *
 * Sort state is this component's, not the URL's: it is a way of reading one table rather
 * than a view worth linking to, and the range and the selection are already in the URL.
 * The first click on a column sorts it descending, because every column here is a "most
 * of" question; the second toggles. Ties break on name ascending, which is the order the
 * API already returns.
 *
 * A null average rank or top-4 rate sorts last in both directions: an unranked brawler is
 * missing a number, not holding the worst one.
 */
import { useState } from "react";

import type { StatsBrawler } from "../api/types";
import { BrawlerIcon } from "../components/ui/BrawlerIcon";
import { Table, type Column } from "../components/ui/Table";
import { signed } from "../lib/format";

export interface BrawlerTableProps {
  rows: StatsBrawler[];
}

type SortKey = "name" | "games" | "net" | "avg_rank" | "top4_rate";

const NONE = "none";
const EMPTY = "No games in this range.";

function netTone(net: number): string {
  if (net > 0) return "text-accent";
  if (net < 0) return "text-bad";
  return "text-muted";
}

function compare(a: StatsBrawler, b: StatsBrawler, key: SortKey, dir: "asc" | "desc"): number {
  if (key === "name") {
    return dir === "asc" ? a.name.localeCompare(b.name) : b.name.localeCompare(a.name);
  }
  const left = a[key];
  const right = b[key];
  // A missing number is not a small one: it goes last whichever way the column points.
  if (left === null && right === null) return a.name.localeCompare(b.name);
  if (left === null) return 1;
  if (right === null) return -1;
  if (left !== right) return dir === "asc" ? left - right : right - left;
  return a.name.localeCompare(b.name);
}

export function BrawlerTable({ rows }: BrawlerTableProps) {
  const [sort, setSort] = useState<{ key: SortKey; dir: "asc" | "desc" }>({
    key: "games",
    dir: "desc",
  });

  const sorted = [...rows].sort((a, b) => compare(a, b, sort.key, sort.dir));

  const columns: Column<StatsBrawler>[] = [
    { key: "icon", label: "", width: "34px", render: (row) => <BrawlerIcon name={row.name} /> },
    { key: "name", label: "Brawler", mono: true, sortable: true, render: (row) => row.name },
    {
      key: "games",
      label: "Games",
      mono: true,
      sortable: true,
      render: (row) => String(row.games),
    },
    {
      key: "net",
      label: "Net",
      mono: true,
      sortable: true,
      render: (row) => (
        <span data-testid="brawler-net" className={netTone(row.net)}>
          {signed(row.net)}
        </span>
      ),
    },
    {
      key: "avg_rank",
      label: "Avg rank",
      mono: true,
      sortable: true,
      render: (row) => (row.avg_rank === null ? NONE : row.avg_rank.toFixed(1)),
    },
    {
      key: "top4_rate",
      label: "Top 4",
      mono: true,
      sortable: true,
      render: (row) => (row.top4_rate === null ? NONE : `${Math.round(row.top4_rate)}%`),
    },
  ];

  return (
    <Table
      columns={columns}
      rows={sorted}
      rowKey={(row) => row.name}
      empty={EMPTY}
      sort={sort}
      onSort={(key) =>
        setSort((current) =>
          current.key === key
            ? { key: current.key, dir: current.dir === "desc" ? "asc" : "desc" }
            : { key: key as SortKey, dir: "desc" },
        )
      }
    />
  );
}
```

- [ ] **Step 9: Run it to verify it passes**

```bash
pnpm --dir brawlfarm/web test -- src/stats/BrawlerTable.test.tsx
```

Expected: 8 passed.

- [ ] **Step 10: Write the failing test for `RankBars`**

Create `brawlfarm/web/src/stats/RankBars.test.tsx`:

```tsx
/** Ten rows, rank 1 at the top, including the ranks nobody finished at, each with a
 * direct label rather than an axis. */
import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RankBars } from "./RankBars";
import type { StatsRank } from "../api/types";
import { renderWithProviders } from "../test/renderWithProviders";

const ROWS: StatsRank[] = [
  { rank: 1, games: 12 },
  { rank: 2, games: 24 },
  { rank: 4, games: 14 },
];

describe("RankBars", () => {
  it("is headed Rank distribution", () => {
    renderWithProviders(<RankBars rows={ROWS} />);
    expect(screen.getByRole("heading", { name: "Rank distribution" })).toBeInTheDocument();
  });

  it("draws ten rows from 1 to 10, including the empty ones", () => {
    renderWithProviders(<RankBars rows={ROWS} />);
    const rows = screen.getAllByTestId("rank-row");
    expect(rows).toHaveLength(10);
    expect(rows.map((row) => within(row).getByTestId("rank-label").textContent)).toEqual([
      "1",
      "2",
      "3",
      "4",
      "5",
      "6",
      "7",
      "8",
      "9",
      "10",
    ]);
  });

  it("labels each bar with its count and its whole-percent share", () => {
    renderWithProviders(<RankBars rows={ROWS} />);
    const rows = screen.getAllByTestId("rank-row");
    expect(within(rows[0]).getByTestId("rank-count")).toHaveTextContent("12 (24%)");
    expect(within(rows[1]).getByTestId("rank-count")).toHaveTextContent("24 (48%)");
    expect(within(rows[2]).getByTestId("rank-count")).toHaveTextContent("0 (0%)");
  });

  it("scales every bar to the largest count", () => {
    renderWithProviders(<RankBars rows={ROWS} />);
    const rows = screen.getAllByTestId("rank-row");
    expect(within(rows[1]).getByTestId("rank-bar")).toHaveStyle({ width: "100%" });
    expect(within(rows[0]).getByTestId("rank-bar")).toHaveStyle({ width: "50%" });
    expect(within(rows[2]).getByTestId("rank-bar")).toHaveStyle({ width: "0%" });
  });

  it("draws ten empty rows when nothing was ranked", () => {
    renderWithProviders(<RankBars rows={[]} />);
    expect(screen.getAllByTestId("rank-row")).toHaveLength(10);
    for (const row of screen.getAllByTestId("rank-row")) {
      expect(within(row).getByTestId("rank-count")).toHaveTextContent("0 (0%)");
    }
  });
});
```

- [ ] **Step 11: Run it to verify it fails**

```bash
pnpm --dir brawlfarm/web test -- src/stats/RankBars.test.tsx
```

Expected: `Failed to resolve import "./RankBars"`.

- [ ] **Step 12: Write `RankBars`**

Create `brawlfarm/web/src/stats/RankBars.tsx`:

```tsx
/**
 * Where the farming finished: ten rows, rank 1 at the top.
 *
 * Ranks with no games are drawn anyway, because a gap in a distribution is information
 * and a list that silently skips rank 7 reads as if rank 7 did not exist. Each bar
 * carries its own label at its end, so there is no axis to read across and no gridline to
 * draw.
 */
import type { StatsRank } from "../api/types";

export interface RankBarsProps {
  rows: StatsRank[];
}

const RANKS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];

export function RankBars({ rows }: RankBarsProps) {
  const counts = new Map(rows.map((row) => [row.rank, row.games]));
  const total = rows.reduce((sum, row) => sum + row.games, 0);
  const largest = rows.reduce((most, row) => Math.max(most, row.games), 0);

  return (
    <section className="flex flex-col gap-2 rounded-[10px] border border-line bg-panel p-3">
      <h2 className="text-[13px] font-semibold">Rank distribution</h2>
      <ul className="flex flex-col gap-1.5">
        {RANKS.map((rank) => {
          const games = counts.get(rank) ?? 0;
          const width = largest === 0 ? 0 : Math.round((games / largest) * 100);
          const percent = total === 0 ? 0 : Math.round((games / total) * 100);
          return (
            <li key={rank} data-testid="rank-row" className="flex items-center gap-2">
              <span
                data-testid="rank-label"
                className="w-[18px] shrink-0 text-right font-mono text-[12px] tabular-nums text-muted"
              >
                {rank}
              </span>
              <span className="h-[4px] min-w-0 flex-1 rounded-[2px] bg-panel-2">
                <span
                  data-testid="rank-bar"
                  className="block h-full rounded-[2px] bg-accent"
                  style={{ width: `${width}%` }}
                />
              </span>
              <span
                data-testid="rank-count"
                className="w-[80px] shrink-0 font-mono text-[11px] tabular-nums text-muted"
              >
                {games} ({percent}%)
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
```

- [ ] **Step 13: Run it to verify it passes**

```bash
pnpm --dir brawlfarm/web test -- src/stats/RankBars.test.tsx
```

Expected: 5 passed.

- [ ] **Step 14: Write the failing test for `RecentGames`**

Create `brawlfarm/web/src/stats/RecentGames.test.tsx`:

```tsx
/** The last twenty games, newest first, with "none" where the API had nothing to say. */
import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RecentGames } from "./RecentGames";
import type { StatsGame } from "../api/types";
import { renderWithProviders } from "../test/renderWithProviders";

function game(overrides: Partial<StatsGame> = {}): StatsGame {
  return {
    instance: "Pie64",
    t: "2026-09-12T22:00:00",
    brawler: "NORI",
    rank: 1,
    trophy_change: 17,
    map: "Feast or Famine",
    mode: "soloShowdown",
    ...overrides,
  };
}

describe("RecentGames", () => {
  it("is headed Recent games and shows the seven columns", () => {
    renderWithProviders(<RecentGames rows={[game()]} />);
    expect(screen.getByRole("heading", { name: "Recent games" })).toBeInTheDocument();
    expect(screen.getAllByRole("columnheader").map((n) => n.textContent)).toEqual([
      "Time",
      "Instance",
      "Brawler",
      "Mode",
      "Map",
      "Rank",
      "Trophies",
    ]);
  });

  it("keeps the API's order, newest first, for twenty rows", () => {
    const rows = Array.from({ length: 20 }, (_, i) =>
      game({ t: `2026-09-12T22:${String(59 - i).padStart(2, "0")}:00`, rank: (i % 10) + 1 }),
    );
    renderWithProviders(<RecentGames rows={rows} />);
    const body = screen.getAllByRole("row").slice(1);
    expect(body).toHaveLength(20);
    expect(within(body[0]).getAllByRole("cell")[0]).toHaveTextContent("22:59");
    expect(within(body[19]).getAllByRole("cell")[0]).toHaveTextContent("22:40");
  });

  it("renders an icon beside every brawler name", () => {
    renderWithProviders(<RecentGames rows={[game(), game({ t: "2026-09-12T21:00:00" })]} />);
    expect(screen.getAllByTestId("brawler-icon")).toHaveLength(2);
  });

  it("says none for a null mode, a null map and a null brawler", () => {
    renderWithProviders(
      <RecentGames rows={[game({ mode: null, map: null, brawler: null, rank: null })]} />,
    );
    const cells = screen.getAllByRole("row")[1].querySelectorAll("td");
    expect(cells[2]).toHaveTextContent("none");
    expect(cells[3]).toHaveTextContent("none");
    expect(cells[4]).toHaveTextContent("none");
    expect(cells[5]).toHaveTextContent("none");
  });

  it("signs and tints the trophy change", () => {
    renderWithProviders(
      <RecentGames
        rows={[game({ trophy_change: -3, t: "2026-09-12T21:00:00" }), game()]}
      />,
    );
    const values = screen.getAllByTestId("recent-trophies");
    expect(values[0]).toHaveTextContent("-3");
    expect(values[0]).toHaveClass("text-bad");
    expect(values[1]).toHaveTextContent("+17");
    expect(values[1]).toHaveClass("text-accent");
  });

  it("says so when the range has no games", () => {
    renderWithProviders(<RecentGames rows={[]} />);
    expect(screen.getByText("No games in this range.")).toBeInTheDocument();
  });
});
```

- [ ] **Step 15: Run it to verify it fails**

```bash
pnpm --dir brawlfarm/web test -- src/stats/RecentGames.test.tsx
```

Expected: `Failed to resolve import "./RecentGames"`.

- [ ] **Step 16: Write `RecentGames`**

Create `brawlfarm/web/src/stats/RecentGames.tsx`:

```tsx
/**
 * The last twenty games the workers logged, newest first.
 *
 * The API already orders them, so this never sorts: the list is a log, and a log that
 * reorders itself is a different thing. A null mode, map, brawler or rank reads "none"
 * rather than blank, so an empty cell always means the column is empty and never that
 * something failed to render.
 */
import type { StatsGame } from "../api/types";
import { BrawlerIcon } from "../components/ui/BrawlerIcon";
import { Table, type Column } from "../components/ui/Table";
import { signed } from "../lib/format";
import { hhmm } from "../lib/time";

export interface RecentGamesProps {
  rows: StatsGame[];
}

const NONE = "none";
const EMPTY = "No games in this range.";

function trophyTone(change: number): string {
  if (change > 0) return "text-accent";
  if (change < 0) return "text-bad";
  return "text-muted";
}

function muted(value: string | null) {
  return value === null || value === "" ? <span className="text-muted">{NONE}</span> : value;
}

const columns: Column<StatsGame>[] = [
  { key: "t", label: "Time", mono: true, width: "70px", render: (row) => hhmm(row.t) },
  {
    key: "instance",
    label: "Instance",
    mono: true,
    width: "110px",
    render: (row) => muted(row.instance),
  },
  {
    key: "brawler",
    label: "Brawler",
    render: (row) => (
      <span className="flex items-center gap-2">
        <BrawlerIcon name={row.brawler} />
        <span className="font-mono">{muted(row.brawler)}</span>
      </span>
    ),
  },
  { key: "mode", label: "Mode", render: (row) => muted(row.mode) },
  { key: "map", label: "Map", render: (row) => muted(row.map) },
  {
    key: "rank",
    label: "Rank",
    mono: true,
    width: "60px",
    render: (row) => (row.rank === null ? <span className="text-muted">{NONE}</span> : String(row.rank)),
  },
  {
    key: "trophy_change",
    label: "Trophies",
    mono: true,
    width: "80px",
    render: (row) =>
      row.trophy_change === null ? (
        <span className="text-muted">{NONE}</span>
      ) : (
        <span data-testid="recent-trophies" className={trophyTone(row.trophy_change)}>
          {signed(row.trophy_change)}
        </span>
      ),
  },
];

export function RecentGames({ rows }: RecentGamesProps) {
  return (
    <section className="flex flex-col gap-2 rounded-[10px] border border-line bg-panel p-3">
      <h2 className="text-[13px] font-semibold">Recent games</h2>
      <Table
        columns={columns}
        rows={rows}
        rowKey={(row) => `${row.instance ?? ""}-${row.t}-${row.brawler ?? ""}`}
        empty={EMPTY}
      />
    </section>
  );
}
```

- [ ] **Step 17: Run it to verify it passes**

```bash
pnpm --dir brawlfarm/web test -- src/stats/RecentGames.test.tsx
```

Expected: 6 passed.

- [ ] **Step 18: Put the band and the list on the page**

In `brawlfarm/web/src/stats/Stats.tsx`, add the three imports beside the other stats ones:

```tsx
import { BrawlerTable } from "./BrawlerTable";
import { ConnectionStrip } from "./ConnectionStrip";
import { MetricsRow } from "./MetricsRow";
import { RankBars } from "./RankBars";
import { RecentGames } from "./RecentGames";
import { StatsToolbar } from "./StatsToolbar";
import { TrophyChart } from "./TrophyChart";
```

and replace the placeholder comment left by task 7:

```tsx
          <TrophyChart series={stats.data.series} instances={selected} />
          <div className="grid gap-3 min-[900px]:grid-cols-[1fr_320px]">
            <section className="flex flex-col gap-2 rounded-[10px] border border-line bg-panel p-3">
              <h2 className="text-[13px] font-semibold">Brawlers</h2>
              <BrawlerTable rows={stats.data.brawlers} />
            </section>
            <RankBars rows={stats.data.ranks} />
          </div>
          <RecentGames rows={stats.data.recent} />
```

At phone width the grid is one column and the table comes first, which is the order the
JSX is already in. Each block keeps its own `overflow-x-auto` box, which `Table` provides.

- [ ] **Step 19: Write the failing page test**

Append to `brawlfarm/web/src/stats/Stats.test.tsx`, inside its `describe`:

```tsx
  it("shows the brawler table, the rank bars and the recent games", async () => {
    server();
    mount();
    expect(await screen.findByRole("heading", { name: "Brawlers" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Rank distribution" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Recent games" })).toBeInTheDocument();
    expect(screen.getAllByRole("row", { name: /NORI/ }).length).toBeGreaterThan(0);
  });
```

- [ ] **Step 20: Run the page tests to verify they pass**

```bash
pnpm --dir brawlfarm/web test -- src/stats/Stats.test.tsx
```

Expected: 12 passed.

- [ ] **Step 21: Everything green on the web side**

```bash
pnpm --dir brawlfarm/web typecheck
pnpm --dir brawlfarm/web test
pnpm --dir brawlfarm/web build
```

Expected: `tsc --noEmit` silent, every vitest file passing, `vite build` writes
`brawlfarm/web/dist/index.html`.

- [ ] **Step 22: Commit**

```bash
uv run python tools/scrub_check.py && git add brawlfarm/web/src/components/ui/Table.tsx brawlfarm/web/src/components/ui/Table.test.tsx brawlfarm/web/src/stats && git commit -m "feat(stats): sortable headers, the brawler band and the recent list

Table gains three optional props and nothing else: a sortable column's label
becomes a full-width button and its th carries aria-sort only when both sort
and onSort are given, so every phase 5 call site renders exactly as it did.
The table never reorders rows, because only the caller knows how to compare
its own values.

BrawlerTable sorts descending on the first click and toggles after, breaks
ties on name ascending, and puts a null average rank last in both directions:
an unranked brawler is missing a number, not holding the worst one.

RankBars draws all ten ranks, including the ones nobody finished at, because
a gap in a distribution is information. Each bar carries its own label, so
there is no axis to read across.

RecentGames keeps the API's order and says none where the API had nothing.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CQ1GimQ3uiR2sXPzfZLNWV"
```

Expected: `0 hit(s)`, then the commit.

---
### Task 9: Session panel cold load and the rail

The brief's task 9. Three edits on the Instance page and one on the rail.

`SessionPanel` keeps doing exactly what it does now while the tab is open. What changes is
the cold load: a panel that mounts already frozen, and has therefore never seen live
figures, seeds itself from `inst.last_session` instead of from the zeroed `status.json`
session. `FarmPlan`'s roster note gains one branch for a rejected token. `Rail` drops the
"soon" tag from Stats, because Stats now exists.

Accepted proposal ids covered: `inst-last-session`, `stats-nav`.

**Files:**
- Modify: `brawlfarm/web/src/instance/SessionPanel.tsx:24-38` (`figuresOf` takes the frozen
  block too), `:47-73` (the seeded mount)
- Modify: `brawlfarm/web/src/instance/FarmPlan.tsx:35-49` (`rosterNote` gains a branch and
  becomes a component), `:8-20` (two imports), `:168` (the call site), `:315` (the render)
- Modify: `brawlfarm/web/src/app/Rail.tsx:13-17` (one field)
- Test: `brawlfarm/web/src/instance/SessionPanel.test.tsx` (modify: three tests appended)
- Test: `brawlfarm/web/src/instance/FarmPlan.test.tsx` (modify: two tests appended)
- Test: `brawlfarm/web/src/app/Rail.test.tsx:28-36` (modify: one assertion)

**Interfaces:**
- Consumes: `LastSession` and `InstancePayload.last_session` from task 6,
  `getConnection` and `queryKeys.connection()` from task 6, `GET /api/connection/check`
  from task 2, `duration` and `hhmm` from `lib/time.ts`, `signed` from `lib/format.ts`.
- Produces: no new exported name. `SessionPanel` and `FarmPlan` keep their props exactly;
  `Rail`'s `SECTIONS` keeps its `soon` field and the span at line 47.
- Consumed by: task 10 (the live pass checks the cold-load caption and the rejected note).

- [ ] **Step 1: Write the failing tests for the cold load**

Append to `brawlfarm/web/src/instance/SessionPanel.test.tsx`, inside its `describe`:

```tsx
  it("seeds a cold load from last_session and captions when it ended", () => {
    renderWithProviders(
      <SessionPanel
        inst={makeInstance({
          state: "stopped",
          games_played: 0,
          session: null,
          last_session: makeLastSession(),
        })}
        avgRank={null}
        interrupts={0}
        stopAt={null}
      />,
    );
    expect(screen.getByText("Session ended 22:14")).toBeInTheDocument();
    expect(figure("Games")).toHaveTextContent("12");
    expect(figure("Trophies")).toHaveTextContent("+86");
    expect(figure("Avg rank today")).toHaveTextContent("3.4");
    expect(figure("Disconnects")).toHaveTextContent("1");
    expect(figure("Duration")).toHaveTextContent("1 h 14 min");
    expect(figure("Interrupts")).toHaveTextContent("2");
  });

  it("behaves exactly as it does today when last_session is null", () => {
    renderWithProviders(
      <SessionPanel
        inst={makeInstance({
          state: "stopped",
          games_played: 0,
          session: null,
          last_session: null,
        })}
        avgRank={null}
        interrupts={0}
        stopAt={null}
      />,
    );
    expect(figure("Games")).toHaveTextContent("0");
    expect(figure("Trophies")).toHaveTextContent("0");
    expect(figure("Avg rank today")).toHaveTextContent("none");
    expect(figure("Duration")).toHaveTextContent("0 min");
  });

  it("follows a live worker and never reads last_session again for that mount", () => {
    const live = makeInstance({
      state: "farming",
      games_played: 4,
      last_session: makeLastSession({ games: 99 }),
    });
    const { rerender } = renderWithProviders(
      <SessionPanel inst={live} avgRank={2.5} interrupts={1} stopAt={null} />,
    );
    expect(figure("Games")).toHaveTextContent("4");
    rerender(
      <SessionPanel
        inst={{ ...live, state: "stopped" }}
        avgRank={2.5}
        interrupts={1}
        stopAt="2026-09-12T23:05:00"
      />,
    );
    // Frozen on what it saw live, not on the 99 games last_session carries.
    expect(figure("Games")).toHaveTextContent("4");
    expect(screen.getByText("Session ended 23:05")).toBeInTheDocument();
  });
```

Add `makeLastSession` to the fixtures import at the top of the file, and if the file has
no `figure` helper, add one beside its other helpers:

```tsx
/** One <dd> by the label in the <dt> beside it. */
function figure(label: string): HTMLElement {
  const term = screen.getByText(label);
  return term.parentElement?.querySelector("dd") as HTMLElement;
}
```

- [ ] **Step 2: Run them to verify they fail**

```bash
pnpm --dir brawlfarm/web test -- src/instance/SessionPanel.test.tsx
```

Expected: the first case fails with `Unable to find an element with the text: Session ended
22:14`, and the figures read zeros.

- [ ] **Step 3: Seed the cold load**

In `brawlfarm/web/src/instance/SessionPanel.tsx`, replace the module comment's second
paragraph and the two functions at lines 24 to 73:

```tsx
/**
 * This session's six figures. The awkward part is the end of a session: the API stops
 * reporting status.json's session block the moment the worker stops, so the panel holds
 * on to the last figures it saw live rather than blanking them to zero. On a cold load
 * there is nothing live to hold on to, so it reads inst.last_session instead, which is the
 * same session as told by the files the worker left behind.
 */
import { useEffect, useRef, useState } from "react";

import type { InstancePayload, LastSession } from "../api/types";
import { signed } from "../lib/format";
import { duration, hhmm } from "../lib/time";

/** States in which the API has stopped reporting a session, so the figures are frozen. */
const FROZEN = new Set(["stopped", "scheduled_break", "offline"]);

type Figures = {
  Games: string;
  Trophies: string;
  "Avg rank today": string;
  Disconnects: string;
  Duration: string;
  Interrupts: string;
};

function figuresOf(inst: InstancePayload, avgRank: number | null, interrupts: number): Figures {
  const session = inst.session;
  const start = session?.start_trophies ?? null;
  const last = session?.last_trophies ?? null;
  return {
    Games: String(inst.games_played ?? 0),
    // One null end of the pair makes the difference meaningless, so it reads 0, not NaN.
    Trophies: start === null || last === null ? "0" : signed(last - start),
    // Rank lives in games.csv, not the feed, so it comes from the stats route for today.
    "Avg rank today": avgRank === null ? "none" : avgRank.toFixed(1),
    Disconnects: String(session?.disconnect_count ?? 0),
    Duration: duration(session?.minutes_elapsed ?? 0),
    Interrupts: String(interrupts),
  };
}

/** The same six figures as api/sessions.py read them off the files. The labels are the
 * ones already on screen, so "Avg rank today" keeps its wording even here, where the
 * number is that session's rather than the day's. */
function figuresOfLast(last: LastSession): Figures {
  return {
    Games: String(last.games),
    Trophies: signed(last.trophies),
    "Avg rank today": last.avg_rank === null ? "none" : last.avg_rank.toFixed(1),
    Disconnects: String(last.disconnects),
    Duration: duration(Math.floor(last.duration_s / 60)),
    Interrupts: String(last.interrupts),
  };
}

/**
 * This session at a glance. When the worker stops, the API drops status.json's session
 * block and every figure would snap to zero, which reads as "the session did nothing".
 * The panel keeps the last figures it saw live and captions when the session ended,
 * preferring the timestamp of the feed's own `stop` line over the moment the browser
 * happened to notice, including when that line only arrives on a later poll.
 *
 * A panel that mounts already frozen has no live figures to keep, so it starts from
 * inst.last_session and from that session's own end. The moment a worker goes live the
 * panel follows it and never reads last_session again for that mount.
 */
export function SessionPanel({
  inst,
  avgRank,
  interrupts,
  stopAt,
}: {
  inst: InstancePayload;
  avgRank: number | null;
  interrupts: number;
  stopAt: string | null;
}) {
  const live = !FROZEN.has(inst.state);
  const cold = !live && inst.last_session !== null;
  const lastLive = useRef<Figures>(
    cold && inst.last_session !== null
      ? figuresOfLast(inst.last_session)
      : figuresOf(inst, avgRank, interrupts),
  );
  const [endedAt, setEndedAt] = useState<string | null>(
    cold && inst.last_session !== null ? inst.last_session.ended_at : null,
  );
  const shown = live ? figuresOf(inst, avgRank, interrupts) : lastLive.current;

  useEffect(() => {
    if (live) {
      lastLive.current = figuresOf(inst, avgRank, interrupts);
      setEndedAt(null);
      return;
    }
    // The feed's own stop line is the better answer whenever it exists, and it usually
    // arrives a poll after the state does. The browser's clock is only a stand-in until
    // then, so it is replaced rather than kept. The seeded last_session end counts as a
    // previous answer, so a cold load keeps its real caption until a stop line turns up.
    setEndedAt((previous) => stopAt ?? previous ?? new Date().toISOString());
  });

  return (
```

The JSX below `return (` is not touched.

- [ ] **Step 4: Run them to verify they pass**

```bash
pnpm --dir brawlfarm/web test -- src/instance/SessionPanel.test.tsx
```

Expected: every existing case still passes, including the freeze-on-stop ones, plus the
three new ones. `duration_s` 4447 is 74 minutes, which `duration` renders as "1 h 14 min".

- [ ] **Step 5: Write the failing tests for the rejected roster note**

Append to `brawlfarm/web/src/instance/FarmPlan.test.tsx`, inside its `describe`:

```tsx
  it("says the token was rejected when the connection check says so", async () => {
    stubFetch((url) => {
      if (url === "/api/connection/check") {
        return jsonResponse(makeConnection({ status: "rejected" }));
      }
      if (url === PLAN) {
        return jsonResponse(makePlan({ roster: null, queue: [], roster_status: "unavailable" }));
      }
      throw new Error(`unstubbed request: ${url}`);
    });
    renderWithProviders(<FarmPlan name="Pie64" />);
    expect(
      await screen.findByText(
        /The Brawl Stars API rejected the token\. Check the token, and the IP address it was created for, in/,
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Settings, Connection" })).toHaveAttribute(
      "href",
      "/settings/connection",
    );
  });

  it("keeps the plain unavailable note when the connection check does not say rejected", async () => {
    stubFetch((url) => {
      if (url === "/api/connection/check") return jsonResponse(makeConnection({ status: "ok" }));
      if (url === PLAN) {
        return jsonResponse(makePlan({ roster: null, queue: [], roster_status: "unavailable" }));
      }
      throw new Error(`unstubbed request: ${url}`);
    });
    renderWithProviders(<FarmPlan name="Pie64" />);
    expect(await screen.findByText("Roster unavailable right now.")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Settings, Connection" })).toBeNull();
  });
```

Add `makeConnection` to this file's fixtures import. The file's own `mount(body)` helper
throws on an unstubbed URL, which is why these two cases build their own stub: they need
the connection route as well as the plan route.

`mount` itself must stop throwing on the connection route, because every other case in the
file now renders a component that asks for it. Change its one line:

```tsx
function mount(body = makePlan(), putStatus = 200): FetchCall[] {
  return stubFetch((url, init) => {
    if (url === "/api/connection/check") return jsonResponse(makeConnection());
    if (url !== PLAN) throw new Error(`unstubbed request: ${url}`);
    if (init?.method !== "PUT") return jsonResponse(body);
    return putStatus === 200
      ? jsonResponse({ ...body, ...JSON.parse(String(init.body)) })
      : jsonResponse({ detail: "adb did not answer" }, putStatus);
  }).calls;
}
```

- [ ] **Step 6: Run them to verify they fail**

```bash
pnpm --dir brawlfarm/web test -- src/instance/FarmPlan.test.tsx
```

Expected: the first new case fails with `Unable to find an element with the text` for the
rejected sentence; the second passes already.

- [ ] **Step 7: Add the branch**

In `brawlfarm/web/src/instance/FarmPlan.tsx`, extend the imports at lines 8 to 20:

```tsx
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";

import { getConnection } from "../api/connection";
import { getPlan, putPlan } from "../api/plans";
import { queryKeys } from "../api/queries";
import type { ConnectionStatus, FarmPlan as FarmPlanBody, PlanResponse } from "../api/types";
```

Replace `rosterNote` at lines 35 to 49 with a small component, because one of its four
answers now carries a link:

```tsx
/** Why there is no roster, in words that say what to do about it (phase 5 brief section
 * 5). The rejected branch is the same sentence Stats shows, because it is the same
 * problem: the plan route only ever says "unavailable", and the connection route is what
 * knows the token itself was refused. */
function RosterNote({
  plan,
  connection,
}: {
  plan: PlanResponse;
  connection: ConnectionStatus | undefined;
}) {
  if (plan.roster_status === "no_token") {
    return (
      <p className="text-[12px] text-muted">
        Add a Brawl Stars API token in Settings to see the roster.
      </p>
    );
  }
  if (plan.roster_status === "no_tag") {
    return (
      <p className="text-[12px] text-muted">
        Set this instance's player tag in Settings to see the roster.
      </p>
    );
  }
  if (plan.roster_status !== "unavailable") return null;
  if (connection === "rejected") {
    return (
      <p className="text-[12px] text-muted">
        The Brawl Stars API rejected the token. Check the token, and the IP address it was
        created for, in{" "}
        <Link to="/settings/connection" className="underline">
          Settings, Connection
        </Link>
        .
      </p>
    );
  }
  return (
    <p className="text-[12px] text-muted">
      {plan.roster === null
        ? "Roster unavailable right now."
        : "Roster unavailable right now; showing the last known list."}
    </p>
  );
}
```

Inside the component, read the connection query beside the plan query (line 53):

```tsx
  const query = useQuery({ queryKey: queryKeys.plan(name), queryFn: () => getPlan(name) });
  const connection = useQuery({
    queryKey: queryKeys.connection(),
    queryFn: getConnection,
    staleTime: 300_000,
    refetchOnWindowFocus: false,
  });
```

Delete the `const note = rosterNote(plan);` line (line 168), and replace the render at
line 315:

```tsx
      <RosterNote plan={plan} connection={connection.data?.status} />
```

The three existing branches, and the wording of the `unavailable` fallback, are unchanged.

- [ ] **Step 8: Run them to verify they pass**

```bash
pnpm --dir brawlfarm/web test -- src/instance/FarmPlan.test.tsx
```

Expected: every existing case passes, plus the two new ones and the icon case from task 5.

- [ ] **Step 9: Write the failing test for the rail**

In `brawlfarm/web/src/app/Rail.test.tsx`, replace the first case's name and its Stats
assertion (lines 28 to 36):

```tsx
  it("shows the wordmark and no longer tags any section as unbuilt", async () => {
    stubInstances();
    renderWithProviders(<Rail />);
    expect(screen.getByText("brawlfarm")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Fleet" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "Stats" })).toHaveAttribute("href", "/stats");
    expect(screen.getByRole("link", { name: "Settings" })).toHaveAttribute("href", "/settings");
    expect(screen.queryByText("soon")).toBeNull();
    expect(await screen.findByText("Instances")).toBeInTheDocument();
  });
```

Also update the file's module comment on line 1 to say "three sections, none of them
tagged as unbuilt any more".

- [ ] **Step 10: Run it to verify it fails**

```bash
pnpm --dir brawlfarm/web test -- src/app/Rail.test.tsx
```

Expected: `Unable to find an accessible element with the role "link" and name "Stats"`,
because the link's accessible name is still "Stats soon".

- [ ] **Step 11: Drop the tag**

In `brawlfarm/web/src/app/Rail.tsx`, replace `SECTIONS[1]` at line 15:

```tsx
const SECTIONS: { to: string; label: string; soon: boolean }[] = [
  { to: "/", label: "Fleet", soon: false },
  { to: "/stats", label: "Stats", soon: false },
  { to: "/settings", label: "Settings", soon: false },
];
```

The `soon` field and the span at line 47 stay as they are: phase 7 and phase 8 add
sections, and the tag is what will mark them.

- [ ] **Step 12: Run it to verify it passes**

```bash
pnpm --dir brawlfarm/web test -- src/app/Rail.test.tsx
```

Expected: 3 passed.

- [ ] **Step 13: Everything green on the web side**

```bash
pnpm --dir brawlfarm/web typecheck
pnpm --dir brawlfarm/web test
pnpm --dir brawlfarm/web build
```

Expected: `tsc --noEmit` silent, every vitest file passing, `vite build` writes
`brawlfarm/web/dist/index.html`. `Instance.test.tsx` and `Fleet.test.tsx` may now need
`last_session` on the payloads they build by hand; they should not, because `makeInstance`
carries the default. If either builds a payload literal without the fixture, add
`last_session: null` to it and say so in the commit body.

- [ ] **Step 14: Commit**

```bash
uv run python tools/scrub_check.py && git add brawlfarm/web/src/instance/SessionPanel.tsx brawlfarm/web/src/instance/SessionPanel.test.tsx brawlfarm/web/src/instance/FarmPlan.tsx brawlfarm/web/src/instance/FarmPlan.test.tsx brawlfarm/web/src/app/Rail.tsx brawlfarm/web/src/app/Rail.test.tsx && git commit -m "feat(instance): a cold load shows the last session, and Stats is built

Opening a stopped instance used to show six zeros, because status.json stops
carrying a session the moment its worker stops and there were no live figures
to hold on to. A panel that mounts already frozen now seeds itself from
last_session and captions it with that session's own end. A live worker still
wins: the moment one goes live the panel follows it and never reads
last_session again for that mount, and with last_session null the panel
behaves exactly as it did.

The farm plan's roster note gains one branch. The plan route only ever says
\"unavailable\"; the connection route is what knows the token itself was
refused, so a rejected token now reads the same sentence on the Instance page
as it does on Stats, with the same link.

The rail drops the soon tag from Stats. The field and its span stay: phase 7
and phase 8 add sections, and the tag is what will mark them.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CQ1GimQ3uiR2sXPzfZLNWV"
```

Expected: `0 hit(s)`, then the commit.

---
### Task 10: Finish

The brief's task 10. The docs, the passes that only a human eye and a real keyboard can
do, the live run against the real install, the blurred screenshots, the pull request, and
the board row on main after the merge.

Nothing in this task changes behaviour. If a pass finds something, it is fixed here and
the fix is committed with the pass that found it.

Accepted proposal ids covered: `readme-attribution`, and the traceability sweep over all
fourteen.

**Files:**
- Modify: `README.md:5` (the status line), `README.md:83-95` (three API rows), `README.md:107` (the attribution paragraph)
- Modify: `docs/PLAN.md:20` (the phase 6 row, on main after the merge)
- Test: none new. Every test in the tree is the gate.

**Interfaces:**
- Consumes: everything tasks 1 to 9 produced.
- Produces: a merged pull request and a board row.

- [ ] **Step 1: Everything green, both sides**

```bash
pnpm --dir brawlfarm/web typecheck
pnpm --dir brawlfarm/web test
pnpm --dir brawlfarm/web build
uv run ruff check . && uv run ruff format --check .
uv run pytest -q
uv run python tools/scrub_check.py
```

Expected: `tsc --noEmit` silent; every vitest file passing, with the nine new files from
tasks 5 to 9 among them; `vite build` writes `brawlfarm/web/dist/index.html`; ruff says
`All checks passed!` and prints nothing for the format check; pytest reports no failures,
with the never-tap rail tests among the passes; the scrub check prints `0 hit(s)`.

Write down the two counts the runners print. The PR body and the board row quote them.

- [ ] **Step 2: Start the real install on a scratch home**

```bash
export BRAWLFARM_HOME="<scratchpad>/home6"
mkdir -p "$BRAWLFARM_HOME"
uv run brawlfarm --no-browser
```

The scratch home keeps the live pass off the real data folder, so nothing this task does
can disturb a running farm. Configure it through the wizard at
`http://127.0.0.1:8765/setup`: the real adb path, one real instance, the real Brawl Stars
token and that instance's player tag. Let it farm for at least half an hour, so
`trophies_per_hour` has something to say and the chart has more than one point.

- [ ] **Step 3: The keyboard and focus pass**

```bash
playwright-cli open http://127.0.0.1:8765/stats
```

Open the browser from the scratchpad, so any snapshot it writes lands there and not in the
repository. Then, using the keyboard only:

- [ ] Tab reaches the range group as one stop, and Left and Right move between Today,
      7 days, 30 days and All, each move changing the URL and the numbers.
- [ ] Tab reaches each instance chip in turn, Space and Enter toggle it, and the last
      enabled chip refuses to turn off.
- [ ] Tab reaches the Export CSV link and Enter downloads a file whose name carries the
      range.
- [ ] Tab reaches the chart as one stop. Right walks the crosshair one point at a time to
      the last point, Left walks it back, Home and End jump, and Escape clears it.
- [ ] With a screen reader running, the crosshair readout is announced on every move.
- [ ] Tab reaches the chart's Table button, and Enter swaps the view and swaps it back.
- [ ] Tab reaches each sortable header of the brawler table, Enter sorts it descending,
      Enter again sorts it ascending, and the chevron follows.
- [ ] Every one of those stops shows a visible focus ring, in both themes.
- [ ] Nothing on the page is reachable that should not be: the icon squares, the legend
      dots and the rank bars are not tab stops.

- [ ] **Step 4: Reduced motion**

In the browser's rendering settings, force `prefers-reduced-motion: reduce`, then reload
`/stats`.

- [ ] The chart draws the same way it does without it: there is no draw-in to skip.
- [ ] The crosshair moves with no transition, exactly as before.
- [ ] The skeleton has no pulse to stop.
- [ ] Nothing else on the page moves, so nothing needed a media query.

- [ ] **Step 5: Phone width**

```bash
playwright-cli resize 390 844
```

- [ ] The toolbar stacks: the range tabs and Export CSV on one row, the chips wrapped onto
      their own row beneath.
- [ ] The metrics row wraps rather than overflowing, and every label is still readable.
- [ ] The chart keeps its 180 px height and its labels do not collide.
- [ ] The brawler table and the rank bars stack, table first.
- [ ] Each table scrolls sideways inside its own box; the page itself has no horizontal
      scrollbar.
- [ ] The recent games table scrolls the same way.

- [ ] **Step 6: Light theme**

```bash
playwright-cli resize 1280 900
playwright-cli open http://127.0.0.1:8765/settings/about
```

Pick Light, then go back to `/stats` and to an instance page.

- [ ] Every series colour is distinguishable against the light panel, including the two
      that are closest.
- [ ] The zero rule and the crosshair rule are both visible.
- [ ] The rank bars' `--accent` fill reads against the `--panel-2` track.
- [ ] The icon fallback square and its initial are legible.
- [ ] The connection strip's 3 px left border carries its tone.
- [ ] Set it back to System when the pass is done.

- [ ] **Step 7: The live pass against brief section 9**

Every one of these is a state the brief pins. Drive them on the real install, and fix
anything that does not match before going on.

- [ ] Loading: six 18 px `--panel-2` blocks in the metrics row and one 180 px block where
      the chart goes, with the toolbar already drawn, no spinner and no pulse.
- [ ] Empty: switch to Today before the first match of the day. The toolbar, then "Stats
      appear after the first match.", and no chart, band or list.
- [ ] No token: clear the token in Settings, Connection, reload `/stats`. The warn strip
      reads "Battle log unavailable. Add a Brawl Stars API token in Settings to see
      per-game stats.", with "Settings" linking to `/settings/connection`.
- [ ] No tag: put the token back, clear the instance's player tag, reload. The warn strip
      names the instance: "Add a player tag for <name> in Settings, Instances to see its
      games."
- [ ] Rejected: put the tag back, paste a token that is not valid for this IP, wait out the
      five-minute cache or restart the server, reload. The bad strip reads "The Brawl Stars
      API rejected the token. Check the token, and the IP address it was created for, in
      Settings, Connection." The Instance page's roster note reads the same sentence.
- [ ] Unreachable: put the real token back, disconnect the network, restart the server,
      reload. The warn strip reads "The Brawl Stars API did not answer. Stats show what was
      logged so far.", and every number is still on the page below it.
- [ ] The chart's Table view shows the same points as rows, and the toggle reads "Table" in
      both directions.
- [ ] A sorted header shows the focus ring, the chevron, `aria-sort="descending"` on that
      `<th>` and `"none"` on the others (read them in the inspector).
- [ ] The icon fallback: a brawler the CDN has no art for shows the 22 px `--panel-2`
      square with its initial, on the exact baseline a loaded icon sits on.
- [ ] The Session panel on a cold load: stop the instance, reload the Instance page, and
      the last session's figures are there with "Session ended <hh:mm>".
- [ ] The farm plan's three icon rows all show art, and no row changed height.

- [ ] **Step 8: Blurred screenshots**

```bash
playwright-cli resize 1280 900
playwright-cli open http://127.0.0.1:8765/stats
playwright-cli eval "document.querySelectorAll('[data-private]').forEach(n => { n.style.filter = 'blur(14px)'; })"
playwright-cli screenshot <scratchpad>/shots/stats-overview.png
```

Repeat the `eval` then `screenshot` pair for each of these; the `eval` has to run again
after every navigation, because it sets an inline style on the nodes that are on the page
now:

- [ ] `<scratchpad>/shots/stats-chart-table.png` at `/stats`, with the chart's Table view open
- [ ] `<scratchpad>/shots/stats-sorted.png` at `/stats`, with the brawler table sorted by Net
- [ ] `<scratchpad>/shots/stats-strip.png` at `/stats`, showing one connection strip
- [ ] `<scratchpad>/shots/instance-cold-session.png` at `/instances/<name>`, stopped
- [ ] `<scratchpad>/shots/instance-farmplan-icons.png` at `/instances/<name>`, with the full
      brawler list open

Then open each PNG and confirm by eye, before anything is attached anywhere:

- [ ] Every player tag on screen is an unreadable smear, not characters that could be read.
- [ ] No absolute path is on screen, and no Windows user name appears in any shot,
      including in the browser's address bar.
- [ ] No token is visible anywhere, in any field or any tooltip.
- [ ] The screenshots stay in the scratchpad. They are attached to the PR and never
      committed.

- [ ] **Step 9: Update the README**

Replace the status line (line 5):

```markdown
Status: under construction. Phase 6 of 8 (the Stats screen and brawler icons). The schedule editor arrives in phase 7; see `docs/PLAN.md`.
```

Add three rows to the API table. After the `GET | /api/stats/export.csv` row (line 84):

```markdown
| GET | `/api/brawlers/{name}/icon.png` | the brawler's portrait from a local cache, fetched once from the Brawlify CDN |
| GET | `/api/connection/check` | whether the Brawl Stars token works: `ok`, `no_token`, `no_tag`, `rejected` or `unreachable` |
```

The third route is not new but its payload is, so extend the `GET | /api/instances` row
(line 71) rather than adding a row:

```markdown
| GET | `/api/instances` | one payload per instance: state, phase, session, today's games and trophies, and the last finished session |
```

Replace the Legal paragraph (line 107) so the brief's attribution sentence stands on its
own rather than being half of a longer one. The existing clause said the same thing in
passing; it is folded into the new sentence rather than repeated:

```markdown
brawlfarm is not affiliated with or endorsed by Supercell. Brawler art is served from the Brawlify CDN and belongs to Supercell under its fan content policy. Automating the game may violate its terms of service; use at your own risk. MIT licensed.
```

- [ ] **Step 10: Commit the docs**

```bash
uv run python tools/scrub_check.py && git add README.md && git commit -m "docs: the Stats screen, two new routes and the art attribution

The status line moves to phase 6. The API table gains the icon route and the
connection check, and the instances row now mentions the last finished
session it carries.

The Legal paragraph carries the brief's attribution sentence as a sentence of
its own, rather than as a clause inside the Supercell one, because the
Brawlify CDN is now a thing this program actually calls.

docs/PLAN.md is left alone: the board is updated on main after the merge, as
in every phase.

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CQ1GimQ3uiR2sXPzfZLNWV"
```

Expected: `0 hit(s)`, then the commit.

- [ ] **Step 11: The copy sweep**

Read every string the screen shows against brief section 8, letter for letter. These are
the ones with somewhere to get wrong:

- [ ] Range tabs "Today", "7 days", "30 days", "All"; group label "Range"; button
      "Export CSV"; chart toggle "Table"; chart label "Cumulative trophy change".
- [ ] Metrics labels, in order: "games", "trophies", "trophies per hour", "average rank",
      "top-4 rate", "time farmed"; the placeholders "after 30 min" and "none".
- [ ] Brawler columns "Brawler", "Games", "Net", "Avg rank", "Top 4"; empty "No games in
      this range."
- [ ] Rank bars heading "Rank distribution"; labels "1" through "10"; a direct label in the
      shape "12 (24%)".
- [ ] Recent games heading "Recent games"; columns "Time", "Instance", "Brawler", "Mode",
      "Map", "Rank", "Trophies"; empty "No games in this range."
- [ ] Empty state "Stats appear after the first match."
- [ ] The four strips, word for word, and the Instance page's rejected note matching the
      third of them.
- [ ] Session caption "Session ended 22:14" in that shape.
- [ ] No em-dash, no emoji and no exclamation mark anywhere on the screen or in this
      branch's commit messages.

Fix anything that differs, then:

```bash
uv run python tools/scrub_check.py && git add -A && git commit -m "fix(stats): copy corrections from the section 8 sweep

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CQ1GimQ3uiR2sXPzfZLNWV"
```

Skip this commit if the sweep found nothing.

- [ ] **Step 12: Push and open the pull request**

```bash
git config user.name   # must print as9pa
git push -u origin phase-6/stats-with-brawler-icons
gh pr create --base main --title "Phase 6: Stats with brawler icons" --body-file /dev/stdin <<'EOF'
## What

`/stats` replaces the phase 4 placeholder. A toolbar of range tabs, instance chips and Export CSV; an inline row of six figures; a hand-drawn SVG chart of cumulative trophy change with a keyboard-reachable crosshair and a Table view; a sortable per-brawler table beside a rank distribution; and the last twenty games. The range and the selection live in the URL, so a reload keeps the view and a link carries it, and a name in a stale link that is no longer configured is dropped rather than 404ing the route.

Every brawler named on Stats and on the Instance farm plan gets a 22 px icon. `GET /api/brawlers/{name}/icon.png` serves it from `<home>/cache/brawlers/<id>.png`, fetching once from the Brawlify CDN and caching it for a week, with one lock per id so a table of eight rows costs one request. A start-up prewarm runs once per process, is created and not awaited, and swallows every failure.

`GET /api/connection/check` says whether the token works: `ok`, `no_token`, `no_tag`, `rejected` or `unreachable`, cached five minutes. One strip on Stats and one note on the Instance page say the same sentence for the same problem.

A stopped instance stops reading as six zeros: `api/sessions.py` reads the newest finished session out of the instance folder and the Session panel seeds a cold load from it. Two stats expressions are corrected: trophies per hour is null below half an hour of farming, and hours farmed carries two decimals.

Nothing new is collected. Every number comes from the `games.csv` and `session-*.jsonl` files the workers already write.

## Safety

- No safety rail moved. `controller.py`, `states.py`, `vision.py`, `farmplan.py` and the calibration block of `core/config.py` are untouched, and the never-tap tests pass unchanged. The only files under `brawlfarm/core` that changed are the new `icons.py` and one optional attribute on `api.py`'s `ApiError`.
- Nothing here starts, stops or kills a process.
- No user-supplied string reaches a filesystem path: a brawler name is matched against a pattern and then discarded, and the cached icon's path is built from the integer id the catalog gave back. Instance names still go through `resolve_instance`.
- Only the API process talks to `cdn.brawlify.com`, only from `core/icons.py`, only on a request or the single start-up prewarm. No worker path imports it.
- The icon cache is written under `<home>/cache` and nowhere else.
- The token never reaches a URL, a log line, an error message, a response body or a screenshot. `ApiError`'s message embeds the requested path and therefore the player tag, so the new `.status` attribute is read instead and the message text is unchanged, which is why `controller.py`'s three `except ApiError` blocks behave as they did.
- No new dependency on either side, and no chart library.

## How to verify

```
corepack enable
pnpm --dir brawlfarm/web install --frozen-lockfile
pnpm --dir brawlfarm/web typecheck && pnpm --dir brawlfarm/web test && pnpm --dir brawlfarm/web build
uv sync --group dev
uv run ruff check . && uv run ruff format --check .
uv run pytest -q
uv run python tools/scrub_check.py
uv run brawlfarm --no-browser
```

Then open `http://127.0.0.1:8765/stats` against a real install with at least half an hour of farming behind it, walk the four ranges, toggle a chip, download the CSV, tab to the chart and walk the crosshair with the arrow keys, sort the brawler table by Net, and stop an instance and reload its page.

## Evidence

- Vitest and pytest both green, ruff clean, scrub check 0 hits.
- Live run on the real instance: the chart drew one line per selected instance over a real session, the crosshair walked every point with the arrow keys and announced each one, Export CSV downloaded the selected range, and the brawler table sorted by Net descending and then ascending with `aria-sort` following.
- The icon route served real art after one cold fetch and 304d on the reload; a brawler the CDN had no art for fell back to its initial with no row moving.
- Clearing the token showed the no-token strip, clearing the tag showed the no-tag strip naming the instance, a token that was not valid for this IP showed the rejected strip and the same sentence on the Instance page, and pulling the network showed the unreachable strip with every logged number still on the page.
- Stopping an instance and reloading showed that session's real figures with its own end time, rather than six zeros.
- Screenshots below are of the real panel with `[data-private]` blurred.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01CQ1GimQ3uiR2sXPzfZLNWV
EOF
```

Then attach the six PNGs from `<scratchpad>/shots/` to the PR in the browser. They are not
committed.

Expected: `gh` prints the pull request URL. Keep it: step 13 needs it.

- [ ] **Step 13: After the merge, the board row on main**

Only once the PR is merged and its CI run is green:

```bash
git switch main && git pull
```

In `docs/PLAN.md`, replace the phase 6 line (line 20) with a completed row in the same
shape as the phase 5 row above it, using the pull request URL `gh` printed in step 12, the
CI run URL from that PR's checks tab, and the two test counts written down in step 1:

```markdown
- Phase 6: Stats with brawler icons. PR <the URL from step 12> (merged). Proof: CI run <the URL from that PR's checks tab> green on the pushed head (<N> vitest tests in <M> files, <K> pytest, ruff clean, scrub check 0 hits); ten plan tasks each reviewed with fix rounds closed by scoped re-reviews; live run against the real BlueStacks install: the chart drew a real session and its crosshair walked every point from the keyboard, Export CSV downloaded the selected range, the brawler table sorted by Net both ways with aria-sort following, the icon route served real art after one cold fetch and 304d on the reload, a brawler with no art fell back to its initial with no row moving, all four connection strips appeared for their real causes, and a stopped instance reloaded with its last session's figures instead of six zeros (blurred screenshots kept out of the repo). Deferred: the schedule editor is phase 7; `docs/setup.md` with pictures is phase 7; the icon prewarm only covers instances whose roster is already cached, so a cold process warms nothing and icons arrive on first use.
```

```bash
uv run python tools/scrub_check.py && git add docs/PLAN.md && git commit -m "docs(board): phase 6 shipped

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01CQ1GimQ3uiR2sXPzfZLNWV" && git push
```

Expected: `0 hit(s)`, then the commit and the push.
