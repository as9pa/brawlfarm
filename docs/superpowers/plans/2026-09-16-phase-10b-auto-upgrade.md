# Phase 10b Auto-Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship opt-in auto-upgrade: once at session end, on the stop path, tap the coin-priced power Upgrade on the farm brawler's detail screen when the gate positively reads it as affordable.

**Architecture:** Approach B from the phase 9 spec. A new `brawlfarm/core/upgrade.py` runs a verify-then-act state machine called from `Controller.stop()` before the `CLOSE_GAME_ON_STOP` block. The decision stays in the already-shipped pure gate `brawlfarm/core/upgrade_gate.should_upgrade`. Every pixel value lands as a provisional placeholder and is replaced in a dedicated calibration pull request once session 2 exists.

**Tech Stack:** Python 3.13 under `uv`, pytest, ruff, pydantic settings, React and TypeScript panel under `pnpm`.

**Spec:** `docs/superpowers/specs/2026-09-16-phase-10b-auto-upgrade.md`

**Branch:** `phase-10/auto-upgrade`, cut from `main` after phase 10a merges.

## Global Constraints

- Working resolution is locked at 1600x900. The recording this plan derives from is 800x450; every coordinate in the spec is a doubled half-size measurement and is **provisional** until session 2.
- Never tap anything priced in gems. Gems in this game render **green**, coins **gold**, power points **pink and purple**. The phase 9 spec's "gem purple" guard is wrong and is corrected in Task 2.
- Tapping UPGRADE on the detail screen does **not** upgrade. It opens a confirmation dialog, and
  the currency is charged on the dialog's confirm button. The feature makes two fixed taps, plus a
  third fixed tap on the dialog X when it refuses there.
- All three tap coordinates are fixed `config.UPGRADE_*` constants, never derived from an OCR box.
- `states.classify` labels every dialog frame `popup`, so the generic farm-loop popup closer would
  dismiss the dialog. TAP, CONFIRM and VERIFY must run inside one uninterrupted `run_once` call
  with no farm-loop tick between them.
- At most one upgrade per session, tracked on the controller instance, never on disk.
- `auto_upgrade` defaults off. `BRAWL_AUTO_UPGRADE` tests `== "1"`, not `!= "0"`.
- No em-dashes and no emoji in prose, code comments, commit messages or the pull request body.
- Conventional commit subjects: `feat(scope): ...`, `fix(scope): ...`, `docs(scope): ...`, `chore: ...`.
- No `discord` import anywhere. No `shell=True`. No user string into a shell or a path.
- Per `CLAUDE.md`, every task gets a spec-compliance and code-quality review pass on **sonnet** before it counts as complete, and the branch gets a whole-branch review on **sonnet** before its pull request opens. Findings are fixed by an implementer, then re-reviewed once.

## The gate command block

Every task's final verification runs this, in this order, from the worktree root:

```
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run python tools/scrub_check.py
pnpm --dir brawlfarm/web test
pnpm --dir brawlfarm/web typecheck
```

`tools/scrub_check.py` must print `0 hit(s)`. Tasks 6 and 9 additionally require a live pass on Pie64.

## Blocking dependencies

- **The whole branch is blocked on phase 10a.** `docs/superpowers/plans/2026-09-16-phase-10a-roster-and-quests.md` recalibrates the roster grid, which now scrolls horizontally. Tasks 1, 2 and 3 touch no navigation and may start before 10a merges. Task 4 onward must not start until 10a has merged and its by-name locate path has passed a live run.
- **Task 7 is blocked on an explicit owner go in chat.** Do not open the pull request without it.
- **Task 8 is blocked on session 2**, a full-size 1600x900 observe recording containing the four items listed in the spec's "What session 2 must contain".
- **If session 2 already exists when Task 3 starts**, measure the `UPGRADE_*` block from its full-size frames directly, ship no PROVISIONAL marker, and fold Task 8 into the branch's own pull request: its body then says it is also a calibration pull request and lists every new value with the frame it came from. Task 8 stays as written only when Task 3 has to ship placeholders.

## File Structure

- `brawlfarm/settings.py`: `FarmSection`, wired into `AppSettings` and `worker_env`. Task 1.
- `brawlfarm/core/config.py`: `AUTO_UPGRADE`, `COIN_FLOOR`, and the `UPGRADE_*` region block. Tasks 1 and 3, values replaced in Task 8.
- `brawlfarm/core/upgrade_gate.py`: the pure gate. Renamed field only. Task 2.
- `brawlfarm/core/upgrade.py`: new. READ helpers (Task 3), then the state machine (Task 4). One responsibility: turn a detail screen into at most one verified tap.
- `brawlfarm/core/controller.py`: one call in `stop()`. Task 5.
- `brawlfarm/api/feed.py`, `brawlfarm/api/settings_routes.py`, `brawlfarm/web/src/settings/Behavior.tsx`: surfacing. Task 6.
- `CONTRIBUTING.md`, `brawlfarm/core/config.py` comment at line 459, `docs/calibration.md`: the rail amendment. Task 7.
- `tests/test_upgrade_gate.py`, `tests/test_upgrade.py`, `tests/test_settings.py`: tests.

---

### Task 1: FarmSection, env plumbing and the two config flags

**Files:**
- Modify: `brawlfarm/settings.py` (after `BehaviorSection`, in `AppSettings`, in `worker_env`)
- Modify: `brawlfarm/core/config.py` (next to `CLOSE_GAME_ON_STOP` at line 221)
- Test: `tests/test_settings.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `settings.FarmSection(auto_upgrade: bool = False, coin_floor: int = 0)`, `AppSettings.farm: FarmSection`, env keys `BRAWL_AUTO_UPGRADE` and `BRAWL_COIN_FLOOR`, and `config.AUTO_UPGRADE: bool`, `config.COIN_FLOOR: int`.

- [ ] **Step 1: Write the failing test**

```python
def test_farm_section_defaults_off_and_floor_is_non_negative():
    s = settings.AppSettings()
    assert s.farm.auto_upgrade is False
    assert s.farm.coin_floor == 0
    with pytest.raises(ValidationError):
        settings.FarmSection(coin_floor=-1)


def test_worker_env_carries_the_farm_flags(tmp_path):
    s = settings.AppSettings()
    s.farm.auto_upgrade = True
    s.farm.coin_floor = 500
    env = settings.worker_env(s, s.instances[0], tmp_path)
    assert env["BRAWL_AUTO_UPGRADE"] == "1"
    assert env["BRAWL_COIN_FLOOR"] == "500"
```

- [ ] **Step 2: Run it and confirm it fails**

Run: `uv run pytest tests/test_settings.py -k farm -v`
Expected: FAIL, `AttributeError: 'AppSettings' object has no attribute 'farm'`.

- [ ] **Step 3: Add the section**

In `brawlfarm/settings.py`, directly after `BehaviorSection`:

```python
class FarmSection(_Section):
    """Session-end farm chores. Off by default: auto_upgrade spends real currency."""

    auto_upgrade: bool = False
    coin_floor: int = Field(default=0, ge=0)
```

Add `farm: FarmSection = FarmSection()` to `AppSettings` alongside `behavior`. In `worker_env`, add `f` to the unpack line and add these two entries next to `BRAWL_CLOSE_GAME_ON_STOP`:

```python
        "BRAWL_AUTO_UPGRADE": _flag(f.auto_upgrade),
        "BRAWL_COIN_FLOOR": str(f.coin_floor),
```

- [ ] **Step 4: Add the config flags**

In `brawlfarm/core/config.py`, next to line 221:

```python
# Opt-in session-end auto-upgrade (phase 10b). Defaults OFF, so this tests for "1"
# rather than the != "0" the always-on flags use: a worker started without the var
# must never upgrade.
AUTO_UPGRADE = os.environ.get("BRAWL_AUTO_UPGRADE", "0") == "1"
COIN_FLOOR = max(0, int(os.environ.get("BRAWL_COIN_FLOOR", "0") or 0))
```

- [ ] **Step 5: Run the gate command block.** All green, `0 hit(s)`.

- [ ] **Step 6: Commit**

```bash
git add brawlfarm/settings.py brawlfarm/core/config.py tests/test_settings.py
git commit -m "feat(settings): a FarmSection with auto_upgrade off and a coin floor"
```

**Acceptance:** `AppSettings().farm.auto_upgrade` is False, `coin_floor=-1` raises, both env keys appear in `worker_env`, and importing `config` without either var gives `AUTO_UPGRADE is False` and `COIN_FLOOR == 0`.

---

### Task 2: Rename `purple_chip` to `gem_chip`

**Files:**
- Modify: `brawlfarm/core/upgrade_gate.py:36` and the `should_upgrade` body and docstring
- Test: `tests/test_upgrade_gate.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `Reading(power_points, power_points_needed, coins, cost, gold_chip: bool = False, gem_chip: bool = True)`. `should_upgrade(reading, *, auto_upgrade, coin_floor=0, done_this_session=False) -> bool` is otherwise unchanged. Tasks 3 and 4 build `Reading` with these names.

**Why:** gems in this game render green, and the power-point cost chip is pink by design. A field called `purple_chip` invites a future calibrator to derive a purple band, which would match the power-point chip on every upgradeable screen and refuse forever. The rename is the guardrail; the behaviour is identical.

- [ ] **Step 1: Rename in the test first**

In `tests/test_upgrade_gate.py`, replace every `purple_chip=` with `gem_chip=`. Add:

```python
def test_a_gem_colour_in_the_coin_slot_refuses():
    r = upgrade_gate.Reading(
        power_points=100, power_points_needed=20, coins=5000, cost=20,
        gold_chip=True, gem_chip=True,
    )
    assert upgrade_gate.should_upgrade(r, auto_upgrade=True) is False
```

- [ ] **Step 2: Run it and confirm it fails**

Run: `uv run pytest tests/test_upgrade_gate.py -v`
Expected: FAIL, `TypeError: ... unexpected keyword argument 'gem_chip'`.

- [ ] **Step 3: Rename in the module**

In `brawlfarm/core/upgrade_gate.py`, change line 36 to:

```python
    gem_chip: bool = True  # a GEM colour (green in this game) was seen in the coin slot
```

Change `if not reading.gold_chip or reading.purple_chip:` to `if not reading.gold_chip or reading.gem_chip:`. In the `should_upgrade` docstring, change "the chip is coin gold and not gem purple" to "the coin slot is gold and carries no gem colour".

- [ ] **Step 4: Confirm no stragglers**

Run: `grep -rn "purple" brawlfarm/ tests/`
Expected: no output.

- [ ] **Step 5: Run the gate command block.** All green.

- [ ] **Step 6: Commit**

```bash
git add brawlfarm/core/upgrade_gate.py tests/test_upgrade_gate.py
git commit -m "fix(upgrade): the gem guard is green, not purple"
```

**Acceptance:** `grep -rn purple brawlfarm/ tests/` is empty, the full truth table still passes, and `gem_chip` still defaults to `True` so an unset field is a refusal.

---

### Task 3: The READ layer and the provisional `UPGRADE_*` block

**Files:**
- Create: `brawlfarm/core/upgrade.py`
- Create: `tests/test_upgrade.py`
- Modify: `brawlfarm/core/config.py` (a new `UPGRADE_*` block after the `BRAWLER_*` block)

**Interfaces:**
- Consumes: `upgrade_gate.Reading` from Task 2, `config.AUTO_UPGRADE` and `config.COIN_FLOOR` from Task 1.
- Produces: `upgrade.read_detail(screen) -> upgrade_gate.Reading | None`, `upgrade.read_power_level(screen) -> int | None`, and `upgrade.read_dialog(screen) -> tuple[int, int] | None` returning `(pp_cost, coin_cost)` only when the title region prefix-matches `config.UPGRADE_DIALOG_TITLE` and both costs parse to positive integers, else `None`. Task 4 calls all three.

**Blocked on nothing.** The values are placeholders; Task 8 replaces them.

- [ ] **Step 1: Add the config block**

In `brawlfarm/core/config.py`, after the `BRAWLER_*` block:

```python
# --- Auto-upgrade (phase 10b) -------------------------------------------------
# PROVISIONAL. Every value below was measured on an 800x450 observe recording
# (Pie64, 20260916-212232) and doubled to the locked 1600x900. Re-measure on the
# full-size session 2 recording before trusting any of it. See
# docs/superpowers/specs/2026-09-16-phase-10b-auto-upgrade.md.
UPGRADE_PP_BALANCE_REGION = (1150, 6, 140, 50)
UPGRADE_COIN_BALANCE_REGION = (1320, 6, 150, 50)
UPGRADE_POWER_LEVEL_REGION = (1130, 374, 60, 52)
UPGRADE_PP_COST_REGION = (1188, 726, 112, 50)
UPGRADE_COIN_COST_REGION = (1368, 726, 112, 50)
UPGRADE_HEADER_REGION = (1250, 680, 180, 36)
UPGRADE_MAX_LEVEL_REGION = (1150, 696, 370, 60)
# The first tap. Opens the confirmation dialog; spends nothing. Fixed, never derived
# from an OCR box.
UPGRADE_TAP = (1336, 744)
# The confirmation dialog the first tap opens. This is where the money moves.
UPGRADE_DIALOG_TITLE_REGION = (480, 78, 640, 56)
UPGRADE_DIALOG_PP_COST_REGION = (1208, 792, 104, 44)
UPGRADE_DIALOG_COIN_COST_REGION = (1320, 792, 112, 44)
UPGRADE_CONFIRM_TAP = (1326, 810)
UPGRADE_DIALOG_CLOSE = (1402, 106)
UPGRADE_DIALOG_TITLE = "UPGRADE TO POWER LEVEL"  # prefix match, case-insensitive
UPGRADE_GOLD_LO, UPGRADE_GOLD_HI = (18, 120, 120), (35, 255, 255)  # PROVISIONAL HSV
UPGRADE_GEM_LO, UPGRADE_GEM_HI = (45, 120, 120), (75, 255, 255)  # PROVISIONAL HSV
UPGRADE_GOLD_FRAC = 0.10  # PROVISIONAL
UPGRADE_GEM_FRAC = 0.05  # PROVISIONAL
```

- [ ] **Step 2: Write the failing tests**

In `tests/test_upgrade.py`, build synthetic 1600x900 frames with `numpy.zeros((900, 1600, 3), np.uint8)` and stub `vision.read_int` and `vision.find_text` with monkeypatch. Cover: a happy screen returns a `Reading` with all four integers; a screen whose `UPGRADE_MAX_LEVEL_REGION` reads `MAX LEVEL!` returns `None`; a screen whose `UPGRADE_HEADER_REGION` does not read `UPGRADE` returns `None`; an unparsed coin cost leaves `Reading.cost is None`. For `read_dialog`: a frame titled `UPGRADE TO POWER LEVEL 2?` with costs 20 and 20 returns `(20, 20)`; the level 3 variant titled `UPGRADE TO POWER LEVEL 3?` with 30 and 35 returns `(30, 35)`; a frame with no title returns `None`; a frame with an unparsed cost returns `None`.

- [ ] **Step 3: Run them and confirm they fail**

Run: `uv run pytest tests/test_upgrade.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'brawlfarm.core.upgrade'`.

- [ ] **Step 4: Implement `read_detail` and `read_power_level`**

`read_detail` takes one screencap, checks the two structural preconditions in that order, then OCRs the four integers from their regions into a `Reading`, and sets `gold_chip` from the gold HSV fraction in `UPGRADE_COIN_COST_REGION` and `gem_chip` from the gem HSV fraction in `UPGRADE_COIN_COST_REGION` **or** `UPGRADE_PP_COST_REGION`. It never reads the stats panel: the green upgrade arrows there would false-positive the gem check. Any unparsed integer stays `None`.

`read_dialog` takes one screencap, prefix-matches `config.UPGRADE_DIALOG_TITLE` against `UPGRADE_DIALOG_TITLE_REGION` case-insensitively, then OCRs the two dialog cost regions. It returns `(pp_cost, coin_cost)` only when the title matched and both parsed to positive integers, and `None` otherwise. It makes no comparison and no decision; Task 4 owns the equality check.

- [ ] **Step 5: Run the tests and confirm they pass.** Then run the gate command block.

- [ ] **Step 6: Commit**

```bash
git add brawlfarm/core/upgrade.py tests/test_upgrade.py brawlfarm/core/config.py
git commit -m "feat(upgrade): read the brawler detail screen into a gate Reading"
```

**Acceptance:** `read_detail` returns `None` on a MAX LEVEL frame and on a headerless frame, returns a fully populated `Reading` on a happy frame, `read_dialog` returns `(20, 20)` and `(30, 35)` on the two dialog variants and `None` on both negatives, and `grep -n "gem" brawlfarm/core/upgrade.py` shows the gem check referencing only the two detail-screen cost regions.

---

### Task 4: The state machine, against a fake adb

**BLOCKED on phase 10a.** Do not start until `docs/superpowers/plans/2026-09-16-phase-10a-roster-and-quests.md` has merged and its by-name locate path has passed a live run. The roster grid now scrolls horizontally, so the locate half of `brawlers.select_brawler_by_name_checked` is uncalibrated until then, and a mis-locate here taps the wrong brawler's detail screen.

**Files:**
- Modify: `brawlfarm/core/upgrade.py`
- Modify: `tests/test_upgrade.py`

**Interfaces:**
- Consumes: `read_detail`, `read_power_level` and `read_dialog` from Task 3, `upgrade_gate.should_upgrade` from Task 2, `config.AUTO_UPGRADE` and `config.COIN_FLOOR` from Task 1, `brawlers._exit_to_menu`, `states.classify`.
- Produces: `upgrade.run_once(brawler_name: str, dl, log=print, *, done_this_session: bool) -> bool`, True only when a tap was made and VERIFY passed. Task 5 calls it.

- [ ] **Step 1: Write the failing tests.** In `tests/test_upgrade.py`, add a `FakeAdb` recording every `tap` and serving a scripted list of frames. Cases, each asserting the exact tap list, not just a count:

- Flag off: `[]`.
- Happy path: exactly `[config.UPGRADE_TAP, config.UPGRADE_CONFIRM_TAP]`, in that order.
- MAX LEVEL, missing header, `coin_floor` above `coins - cost`, each of the four integers unreadable in turn, `gem_chip` True, `done_this_session=True`, a detail-screen name mismatch: `[]` in every case.
- An UNKNOWN frame injected at OPEN_BRAWLERS, LOCATE, ON_DETAIL and READ: `[]`, and `_exit_to_menu` called.
- Dialog title absent: `[config.UPGRADE_TAP, config.UPGRADE_DIALOG_CLOSE]`, `upgrade_dialog_refused` logged, no confirm tap.
- Dialog pp cost disagreeing with the detail-screen `power_points_needed`: `[config.UPGRADE_TAP, config.UPGRADE_DIALOG_CLOSE]`.
- Dialog coin cost disagreeing with the detail-screen `cost`: `[config.UPGRADE_TAP, config.UPGRADE_DIALOG_CLOSE]`.
- Either dialog cost unparsed: `[config.UPGRADE_TAP, config.UPGRADE_DIALOG_CLOSE]`.
- VERIFY failure: exactly `[config.UPGRADE_TAP, config.UPGRADE_CONFIRM_TAP]`, `upgrade_unverified` logged, no third tap.

- [ ] **Step 2: Add the rail test**

```python
def test_upgrade_module_holds_no_literal_coordinates():
    src = (Path(__file__).parents[1] / "brawlfarm/core/upgrade.py").read_text()
    stripped = re.sub(r"config\.UPGRADE_[A-Z_]+", "", src)
    assert not re.search(r"\(\s*\d{2,4}\s*,\s*\d{2,4}\s*\)", stripped)
```

- [ ] **Step 3: Run them and confirm they fail.** Run: `uv run pytest tests/test_upgrade.py -v`. Expected: FAIL, `run_once` not defined.

- [ ] **Step 4: Implement `run_once`.** AT_MENU, OPEN_BRAWLERS, LOCATE (the by-name locate half only, no SELECT tap), ON_DETAIL (OCR the name against `brawler_name` via `config.BRAWLER_NAME_REGION`), READ, GATE, TAP, CONFIRM, VERIFY, EXIT.

CONFIRM sits between TAP and VERIFY and is the step that spends. After `adb.tap(*config.UPGRADE_TAP)`, sleep the nav settle, screencap, call `read_dialog`. Require a non-`None` result **and** `dialog_pp == reading.power_points_needed` **and** `dialog_coins == reading.cost`. On success, `adb.tap(*config.UPGRADE_CONFIRM_TAP)` and continue to VERIFY. On any failure, log `upgrade_dialog_refused` with both the detail-screen pair and whatever the dialog read, `adb.tap(*config.UPGRADE_DIALOG_CLOSE)`, set the once-per-session flag and EXIT. The cost equality is a second independent read of the price: a detail-screen misread cannot agree with the dialog, so it costs nothing.

Do not yield, sleep into a farm-loop tick, or return between TAP and CONFIRM. `states.classify` labels the dialog `popup`, and the generic popup closer would dismiss it. Re-classify with `states.classify` at every transition; anything unexpected, including UNKNOWN, goes straight to EXIT via `brawlers._exit_to_menu`. No retries beyond the existing nav budgets. Wrap the whole body so any exception logs `upgrade_error` and still exits to the menu. VERIFY requires the power level to be exactly the pre-tap level plus one **and** the power-point balance to be strictly lower; anything else logs `upgrade_unverified` with both pre and post values and returns False. Never tap a second time on either branch.

- [ ] **Step 5: Run the tests and confirm they pass.** Then run the gate command block.

- [ ] **Step 6: Commit**

```bash
git add brawlfarm/core/upgrade.py tests/test_upgrade.py
git commit -m "feat(upgrade): the verify-then-act state machine, one tap at most"
```

**Acceptance:** every listed case asserts an exact tap list, the happy path is exactly `[config.UPGRADE_TAP, config.UPGRADE_CONFIRM_TAP]`, every dialog refusal is exactly `[config.UPGRADE_TAP, config.UPGRADE_DIALOG_CLOSE]`, no case ever taps `config.UPGRADE_CONFIRM_TAP` more than once, and the rail test passes.

---

### Task 5: Controller stop-path wiring

**Files:**
- Modify: `brawlfarm/core/controller.py` (in `stop()`, between the DND-off block and the `if config.CLOSE_GAME_ON_STOP:` block at line 1321)
- Modify: `tests/test_upgrade.py`

**Interfaces:**
- Consumes: `upgrade.run_once` from Task 4.
- Produces: `Controller._upgraded_this_session: bool`, initialised False in `__init__`.

- [ ] **Step 1: Write the failing test.** Assert that `stop("stop_flag")` with `AUTO_UPGRADE` False makes zero taps; that with it True it calls `upgrade.run_once` exactly once; that calling `stop()` twice still calls it once; and that an exception raised inside `run_once` does not prevent the `CLOSE_GAME_ON_STOP` force-stop from running.

- [ ] **Step 2: Run it and confirm it fails.** Run: `uv run pytest tests/test_upgrade.py -k stop -v`.

- [ ] **Step 3: Implement.** Insert before the `CLOSE_GAME_ON_STOP` block:

```python
        # Session-end auto-upgrade (phase 10b, opt-in, default off). Runs here because
        # the bot is already at the menu, nothing is time critical, and a failure costs
        # nothing: the session is over. Once per session, tracked in memory so a crash
        # cannot resume mid-upgrade. Guarded: an upgrade hiccup must never block the stop.
        if config.AUTO_UPGRADE and not self._upgraded_this_session:
            try:
                if upgrade.run_once(
                    self.farm_brawler, self.dl, self.log,
                    done_this_session=self._upgraded_this_session,
                ):
                    self._upgraded_this_session = True
            except Exception as e:
                self.dl.event("upgrade_error", err=repr(e))
                self.log(f"auto-upgrade error (continuing the stop): {e!r}")
```

Substitute the controller's real attribute for the farm brawler name if it is not `self.farm_brawler`.

- [ ] **Step 4: Run the tests and confirm they pass.** Then run the gate command block.

- [ ] **Step 5: Commit**

```bash
git add brawlfarm/core/controller.py tests/test_upgrade.py
git commit -m "feat(controller): run auto-upgrade once on the stop path"
```

**Acceptance:** zero taps with the flag off, exactly one `run_once` call with it on, idempotent across a double `stop()`, and the force-stop still runs after an upgrade exception.

---

### Task 6: Panel controls and the feed line

**Files:**
- Modify: `brawlfarm/api/settings_routes.py`, `brawlfarm/api/feed.py`, `brawlfarm/web/src/settings/Behavior.tsx`
- Test: `tests/test_api_settings.py`, `tests/test_feed.py`, `brawlfarm/web/src/settings/Behavior.test.tsx`

**Interfaces:**
- Consumes: `FarmSection` from Task 1, the `upgrade_ok` / `upgrade_unverified` / `upgrade_error` event kinds from Tasks 4 and 5.
- Produces: no new Python symbols.

- [ ] **Step 1: Write the failing tests.** API: PUT `farm.auto_upgrade=true, coin_floor=250` round-trips through GET, and `coin_floor=-1` is rejected with 422. Feed: `classify("upgrade_ok")` is a normal event, and `classify("upgrade_unverified")` and `classify("upgrade_dialog_refused")` both land in ERRORS. Panel: the number input is `disabled` while the toggle is off and enabled when it is on.

- [ ] **Step 2: Run them and confirm they fail.**

- [ ] **Step 3: Implement.** Expose `farm` in the settings routes the same way `behavior` is exposed. Add `upgrade_unverified` and `upgrade_dialog_refused` to `ERRORS` in `feed.py`; `upgrade_error` already matches the `_error` suffix path. In `Behavior.tsx`, add a toggle "Auto-upgrade the farm brawler" and a number input "Keep at least this many coins", `min={0}`, disabled while the toggle is off, with helper copy: "Spends coins and power points only, never gems. At most one upgrade per session, at the end of a run."

- [ ] **Step 4: Run the tests and confirm they pass.** Then run the gate command block including both `pnpm --dir brawlfarm/web` commands.

- [ ] **Step 5: Commit**

```bash
git add brawlfarm/api/settings_routes.py brawlfarm/api/feed.py brawlfarm/web/src/settings tests/
git commit -m "feat(panel): auto-upgrade toggle, coin floor and the feed line"
```

**Acceptance:** the settings round trip passes, `coin_floor=-1` is a 422, all three upgrade failure kinds classify as errors, and the number input is disabled while the toggle is off.

---

### Task 7: The CONTRIBUTING.md never-tap amendment

**BLOCKED on an explicit owner go in chat.** Do not run this task, and do not open the pull request, until the owner has said go. This is the task that makes tapping Upgrade legal in this repository. Shipping Tasks 4 through 6 without it leaves the repository self-contradictory and the rail unenforceable.

**Files:**
- Modify: `CONTRIBUTING.md` (line 9), `brawlfarm/core/config.py` (the comment at line 459), `docs/calibration.md`

- [ ] **Step 1: Confirm the go.** The owner's go must be quoted in the pull request body.
- [ ] **Step 2: Replace the never-tap bullet.** Use the two-bullet replacement given verbatim in the spec's "The rail amendment, proposed verbatim" section. Copy it exactly; do not paraphrase.
- [ ] **Step 3: Amend the config comment at line 459** so it stops claiming the bottom-right UPGRADE button is never tapped, and points at the `UPGRADE_*` block and the new exception.
- [ ] **Step 4: Add an auto-upgrade section to `docs/calibration.md`** listing every `UPGRADE_*` constant, its provisional value, and the frame it came from.
- [ ] **Step 5: Run the gate command block.**
- [ ] **Step 6: Commit**

```bash
git add CONTRIBUTING.md brawlfarm/core/config.py docs/calibration.md
git commit -m "docs(rails): the narrow auto-upgrade exception to the never-tap set"
```

**Acceptance:** `CONTRIBUTING.md` still lists Upgrade in the never-tap set, plus one exception naming the setting, **both** fixed tap coordinates (`UPGRADE_TAP` and `UPGRADE_CONFIRM_TAP`) and the dialog X (`UPGRADE_DIALOG_CLOSE`), once per session, the stop path, the dialog cost-equality check and the gate. No other never-tap entry is weakened.

---

### Task 8: The calibration pull request

**BLOCKED on session 2.** Do not start until a full-size 1600x900 observe recording exists containing items 1 through 4 of the spec's "What session 2 must contain". This ships as its own pull request, per `CONTRIBUTING.md`: a coordinate change is never folded into a feature pull request.

**Files:**
- Modify: `brawlfarm/core/config.py` (the whole `UPGRADE_*` block), `docs/calibration.md`

- [ ] **Step 1: Re-measure every region** on the full-size frames. Record the measured box for each one.
- [ ] **Step 2: Re-measure the four dialog regions and both dialog tap coordinates** on the full-size dialog frames, using both the level 2 and the level 3 variant so each cost slot is exercised with a different value.
- [ ] **Step 3: Derive `UPGRADE_GOLD_*` from the coin cost chip** and `UPGRADE_GEM_*` from the gem-priced element in item 4. Record both fractions on a positive and a negative sample, and confirm the gem band does **not** fire on the green stats arrows above the UPGRADE panel, and **not** on the dialog green confirm button, which is the same green family as the shop gem button.
- [ ] **Step 4: Fix both settle delays** from the full two-tap sequence in item 2: the detail-to-dialog settle, and the confirm-to-verified settle, which must outlast the sparkle animation.
- [ ] **Step 4: Replace the values and delete every PROVISIONAL marker** from the block.
- [ ] **Step 5: Re-run `tests/test_upgrade.py` against the full-size frames.**
- [ ] **Step 6: Run the gate command block.**
- [ ] **Step 7: Commit and open a calibration pull request** whose body says it is a calibration pull request and lists every changed value with its old value, its new value, the frame it came from and the score measured.

```bash
git add brawlfarm/core/config.py docs/calibration.md
git commit -m "fix(calibration): the UPGRADE_* block measured at 1600x900"
```

**Acceptance:** no `PROVISIONAL` marker remains in the `UPGRADE_*` block, the gem band fires on the gem sample and not on the stats arrows or the dialog confirm button, both dialog variants parse their costs correctly, and the pull request body lists every changed value.

---

### Task 9: Live pass, whole-branch review and the pull request

**Files:** none.

- [ ] **Step 1: Run the whole gate command block** one more time from a clean tree.
- [ ] **Step 2: Live pass on Pie64, part one.** Park the instance with a stop override, set `auto_upgrade` on and `coin_floor` above `coins - cost`, drive a short run through the API, and confirm the feed shows the refusal and the datalog shows **zero** taps.
- [ ] **Step 3: Live pass on Pie64, part two, with the owner watching.** Lower `coin_floor`, run again, and confirm the dialog opens, the two costs are logged as matching the detail screen, exactly one confirm tap follows, and exactly one real upgrade lands on a cheap brawler, an `upgrade_ok` feed line naming the brawler, the new power level and the coin cost, and the power level incremented on screen.
- [ ] **Step 4: Whole-branch review on sonnet**, per the project `CLAUDE.md`. Findings are fixed by an implementer, then re-reviewed once.
- [ ] **Step 5: Open the pull request** with the four required sections: What, Safety (name the never-tap amendment and quote the owner's go), How to verify (the gate command block), Evidence (the command output plus what you saw on Pie64).

**Acceptance:** both live passes appear in the pull request Evidence section, the whole-branch review is clean or its findings are fixed and re-reviewed, and the pull request body quotes the owner's go for the rail amendment.

---

## Self-review notes

- Spec coverage: goal Tasks 4 and 5; rail amendment Task 7; components Tasks 1, 3, 4, 5, 6; state machine Task 4; READ Task 3; GATE Task 2; VERIFY Task 4; settings and API Tasks 1 and 6; safety-rail impact Tasks 3, 4, 5, 7; test plan Tasks 2, 3, 4, 5, 6; session 2 Task 8.
- The `red_cost` field is deliberately unimplemented. It has no task because no frame showing it exists; the spec says why.
- Names used consistently across tasks: `Reading.gem_chip`, `upgrade.read_detail`, `upgrade.read_power_level`, `upgrade.read_dialog`, `upgrade.run_once`, `Controller._upgraded_this_session`, `config.UPGRADE_TAP`, `config.UPGRADE_CONFIRM_TAP`, `config.UPGRADE_DIALOG_CLOSE`.
- Revised 2026-09-16 after the `20260916-215108` recording showed the confirmation dialog. The CONFIRM step, the three dialog regions, the two extra coordinates and the `upgrade_dialog_refused` event all date from that revision.
