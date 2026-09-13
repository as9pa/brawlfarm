# Phase 9 design: observe mode, quest-aware pick, opt-in auto-upgrade

Date: 2026-09-13. Status: approved by the owner in chat ("all", after the five-item menu); the review
page records the rulings below. Author: the phase 9 architect pass, edited by the orchestrator.

## Scope of the first phase 9 plan

The owner asked for all three game features plus the PyPI release workflow and README screenshots.
The release workflow and the screenshots are separate branches. This spec covers the three game
features; the first implementation plan built from it ships only the parts that need no live
captures:

1. Feature 1, observe-only recording mode, in full (all seven tasks below).
2. Feature 2, task 1 only: `questpick.parse` and `questpick.resolve` as pure functions with unit
   tests, not wired into the controller and with no config values.
3. Feature 3, task 2 only: the upgrade gate as a pure function with its truth-table tests, not
   wired anywhere.

Everything else in features 2 and 3 waits on two owner recordings made with feature 1: one session
that opens and scrolls the quests screen through the variants listed under feature 2, and one that
walks the farm brawler detail screen through the upgrade states listed under feature 3. Those
parts land later in owner-approved calibration pull requests.

## Rulings on the open questions

- `Recorder.MAX_FRAMES` stays at 2000. An observe session that hits the cap ends recording and the
  owner starts another one. Cost if wrong: one extra switch flip per long session.
- The class-to-brawler table for "deal damage with a class" quests is deferred until the quests
  captures exist. `questpick.resolve` returns None for class quests in this plan. Cost if wrong:
  class quests are not farmed until the follow-up.
- The `CONTRIBUTING.md` never-tap amendment for the Upgrade button is not part of this plan. It
  ships in the same owner-approved pull request as the feature 3 tap path, and that pull request
  needs an explicit owner go in chat; it is a safety-rail change the orchestrator does not merge on
  its own. Until then no code in the repo taps Upgrade.
- Observe mode is a third supervisor desired mode, `observe`, next to `run` and `stop`. The panel
  switch is on the Calibration page beside the existing recorder switch.
- The observe route refuses with 409 unless the instance is stopped. No farm-to-observe handoff in
  one call.


Three features. Paths are relative to the repo root. Every coordinate, needle, HSV band and
threshold named here lands in `brawlfarm/core/config.py` and ships in an owner-approved
calibration pull request that lists every changed value, per `CLAUDE.md` and `CONTRIBUTING.md`.

## 1. Observe-only recording mode

### Goal

The owner plays by hand while a process captures frames, classifies them with
`brawlfarm/core/states.py` and feeds `brawlfarm/core/recorder.py`, so the next recalibration of
the brawler screen and the event anchors comes from a labeled session of real play. The process
must never tap, and it must be impossible for it to run beside a farming worker on the same
instance.

### Two approaches

**A. Flag on the controller.** Add `observe=True` to `Controller.__init__` and guard every tap
site. Cheap to start. It is the wrong answer: `controller.py` is 1553 lines and the tap paths
run through `handle_popup`, `handle_disconnect`, `handle_daily_streak`, `handle_team_invite`,
recovery, and the in-match movement loop. One missed branch taps on the owner live game and
fails silently. There is no static check that can prove the guard is complete.

**B. Separate module plus a worker flag (recommended).** New `brawlfarm/core/observer.py` with an
`Observer` class that imports only `adb.connect` and `adb.screencap`, plus `states`, `recorder`,
`preview`, `status` and `config`. It never imports `controller`, `brawlers`, `quests`,
`core/settings` or `rewards`, so the tap functions are not in its reachable call graph and a
test can assert that. New `--observe` flag on `brawlfarm/worker.py` that constructs `Observer`
instead of `Controller`.

Recommendation: B. The decisive point is not code tidiness, it is mutual exclusion. Because
observe mode runs as `python -m brawlfarm.worker`, it occupies the same `status.json` PID slot
the supervisor already guards with its one-worker-per-instance rule
(`brawlfarm/supervisor/loop.py`, `_ensure_gone`, `_kill_hung_launch`, and `is_worker` in
`brawlfarm/supervisor/process.py`). A standalone daemon would sit outside that slot, the
supervisor would read "nothing is running" and launch a farming worker onto the same adb port,
and two processes would drive one instance. Reuse the existing lock rather than inventing a
second one.

### Components

New: `brawlfarm/core/observer.py`, `tests/test_observer.py`, `tests/test_api_observe.py`,
`brawlfarm/web/src/calibration/ObserveCard.tsx` (or a second switch inside `RecorderCard.tsx`).

Modified: `brawlfarm/worker.py` (the `--observe` flag), `brawlfarm/settings.py`
(`worker_args` gains the flag when the instance override asks for it),
`brawlfarm/supervisor/loop.py` and `brawlfarm/supervisor/state.py` (a third desired mode,
`observe`, alongside `run` and `stop`), `brawlfarm/api/instances.py` (start and stop routes),
`brawlfarm/api/calibration.py` (status in the recorder payload),
`brawlfarm/web/src/calibration/Calibration.tsx` and `useCalibration.ts`,
`brawlfarm/web/src/api/calibration.ts`, `tests/test_core_imports.py` (add `observer` to MODULES).

### Data flow

`Observer.run()` calls `adb.connect`, asserts 1600x900, then loops at about two frames a second:
`screencap` then `preview.maybe_write(screen)` so the panel preview stays live, then
`states.classify(screen, phase=None)`, then `self.recorder.poll()` and
`self.recorder.observe(screen, state, "observe")`, then a `status.json` heartbeat carrying
`mode: "observe"`, then a `stop.flag` check and a clean exit. On start it creates `record.flag`
itself and removes it on exit, so the owner flips one switch, not two. `phase=None` is correct:
there is no farm phase to hint with, and `PHASE_ORDER` only reorders anchors, it never changes
the label a frame gets.

`Recorder.MAX_FRAMES` is 2000, which at one frame a second is roughly 33 minutes of distinct
states. Leave the cap alone for v1 and let the owner start a second session; the cap is what
keeps a runaway recorder from filling the disk.

### Settings and API

No new TOML settings. The mode is per instance and transient, so it lives with the existing
desired-state override files the supervisor already reads.

- `POST /api/instances/{name}/observe` with a body of `{"on": true}` or `{"on": false}`. Turning
  it on writes the `observe` desired override; the next supervisor tick launches the worker with
  `--observe`. Turning it off writes the stop override and `stop.flag`, exactly like the normal
  stop path.
- The route returns 409 unless the instance is currently stopped. Never hand off from farming to
  observing in one call, because the handoff window is where two processes overlap.
- `GET /api/instances/{name}/recorder` gains a `mode` field of `farm` or `observe` so the page can
  show which one is recording.
- Calibration page: a "Record while I play" switch beside the existing "Record frames" switch,
  disabled with a tooltip while the instance is farming, showing session id and frame count from
  the same `recorder.json` payload.

### Calibration dependency

None. This feature reads config, it does not add coordinates. That is why it goes first.

### Safety-rail impact

Three assertions, all testable in CI:

1. `tests/test_observer.py` asserts the module source of `brawlfarm/core/observer.py` contains no
   reference to `adb.tap`, `adb.swipe`, `adb.tap_hold`, `adb.input_text`, `adb.keyevent`,
   `adb.go_home`, `adb.launch_app` or `adb.force_stop`.
2. The same test imports `observer` in a subprocess and asserts `brawlfarm.core.controller`,
   `brawlfarm.core.brawlers`, `brawlfarm.core.quests` and `brawlfarm.core.settings` are absent
   from `sys.modules`.
3. An API test asserts that turning observe on for a farming instance returns 409 and writes no
   override file.

### Test plan

Unit: `Observer` against a fake adb module whose `screencap` yields canned frames and whose `tap`
raises; the loop must complete without raising. Flag lifecycle: `record.flag` appears on start and
is gone after a clean exit and after an exception. Supervisor: a desired override of `observe`
produces `--observe` in the launched args and no `--select-brawler` or `--dnd`. API: the 409 case,
the happy path, and the recorder payload shape. Web: the switch is disabled while farming, and the
mutation posts the right body.

### Tasks

1. `Observer` class and its loop, with the heartbeat and the `record.flag` lifecycle.
2. `--observe` in `brawlfarm/worker.py`, plus the `worker_args` branch.
3. Supervisor desired mode `observe` in `state.py` and `loop.py`.
4. The two API routes and the recorder payload field.
5. The import-rail and no-tap tests.
6. The Calibration page switch and its API client.
7. Docs: a short "record while I play" section in `docs/` and in the README calibration section.

## 2. Quest-aware brawler choice

### Goal

Pick the farm brawler so the session also clears an active quest, falling back to today's choice
when no quest maps to an owned brawler.

### What exists today

`--select-brawler` picks the lowest-trophy brawler once at startup
(`brawlers.select_lowest_trophy_brawler`). The farm plan (`brawlfarm/api/plans.py`,
`brawlfarm/core/farmplan.py`) can name a target, and
`brawlers.select_brawler_by_name_checked(target, owned, log)` already does verify-then-act
selection by name with a self-correcting scroll. `brawlfarm/core/quests.py` opens the quests
screen today, but only to activate a new mega quest: it reads a gold fraction and never reads
text. The legacy checkout has the same mega-quest activation and nothing more, so there is no
prior art for reading quest lines.

The only genuinely new work is producing a brawler name. Selection, verification, roster lookup
and the fallback chain all exist.

### Two approaches

**A. Per game, at the menu.** Re-read quests between every match. Buys freshness when a quest
completes mid-session. Costs a quests-screen round trip on every menu visit, more chances to wedge
the menu, and it breaks `farmplan.rotation_decision` and `_check_farm_brawler_trophies`, which
both assume `_farm_brawler` is stable for the session. Reject.

**B. Once per session, at startup (recommended).** Extend the existing startup quests visit to
also read the list, resolve a name, and hand it to the selection step that already runs.

Recommendation: B. It adds one OCR pass to a screen the bot already opens, touches no hot path,
and keeps the ladder logic assumption intact.

### Components

New: `brawlfarm/core/questpick.py` (parsing and mapping, pure functions plus one screen read),
`tests/test_questpick.py`.

Modified: `brawlfarm/core/quests.py` (the startup visit returns the OCR lines),
`brawlfarm/core/config.py` (a `QUEST_LIST_*` block: list region, row pitch, scroll lane, title
needles), `brawlfarm/core/controller.py` (`_do_select_brawler` consults the quest pick first),
`brawlfarm/api/plans.py` (`FarmPlan` gains `quest_aware: bool = False`),
`brawlfarm/core/farmplan.py` (`DEFAULT_PLAN`), `brawlfarm/web/src/instance/FarmPlan.tsx`,
`brawlfarm/api/feed.py` (a `quest_pick` event kind).

### Data flow

Startup: open QUESTS via the existing nav, then `vision.read_lines_boxes` over
`QUEST_LIST_REGION`, one swipe down and a second read to cover the scrolled rows. Then
`questpick.parse(lines)` yields a kind, a target and a count for three patterns: win N battles
with a named brawler, deal damage with a class, play N battles in a mode. Then
`questpick.resolve(parsed, owned)` matches a brawler quest directly against the owned roster,
normalized the way `brawlers._norm` does, maps a class quest through a static class-to-brawler
table in `config.py` intersected with the roster, and ignores mode quests for v1 because the bot
only plays Trio Showdown. If nothing resolves it returns None and the existing plan or
lowest-trophy path runs unchanged. Log and emit a feed line naming the quest and the brawler.

Ordering constraint: the quest read must happen inside the same quests-screen visit that already
exists, before `_exit_to_menu`, and the resolved name must reach `_do_select_brawler` before it
runs. Both are startup work in `controller.run` today, so read quests first and pass the name
down; do not add a second navigation.

### Settings and API

Per instance, in the farm plan, not in global settings: `quest_aware: bool = False` on `FarmPlan`
in `brawlfarm/api/plans.py` and in `farmplan.DEFAULT_PLAN`. The plan editor gets a toggle with
help text saying it only applies at session start. The enriched plan response adds a `quest_pick`
field so the card can show what the last session chose.

### Calibration dependency

This cannot be calibrated from memory. Live captures needed, all from observe mode:

- The quests screen scrolled to the top, and scrolled to the bottom, on an account with at least
  one win-N-battles-with-a-brawler quest.
- The same screen with a deal-damage-with-a-class quest and with a play-N-battles-in-a-mode quest,
  to fix the three parse patterns.
- A quests screen with no brawler quest at all, to prove the fallback.
- A quests screen where a quest is already complete or claimed, since a claimed row must not be
  chosen.

Until those exist, `questpick.parse` and `questpick.resolve` can be written and unit tested
against hand-typed line lists, but `QUEST_LIST_REGION` and the row geometry stay unset and the
feature stays off.

### Safety-rail impact

Read-only on the quests screen. The only new tap is the scroll swipe in the list lane, which must
be inside `QUEST_LIST_REGION` and clear of any claim or reward button. No never-tap change. If the
list OCR reads zero lines on an account that should have quests, treat it like the existing
`RECALIB_TRIPWIRE` case in `brawlers.py`: log, alert, and fall back rather than guess.

### Test plan

Unit: `parse` against the three patterns plus mangled OCR (styled fonts drop characters, as the
`SELET` note in `config.py` records), and against claimed rows. `resolve` against rosters that do
and do not own the target, and a class quest with two owned candidates, which must pick the
lowest-trophy one deterministically. Controller: with `quest_aware` off, the selection path is
byte-identical to today. Feed: the new event kind routes to the right panel group in
`brawlfarm/api/feed.py`. Fixture frames from a recorded observe session drive an end-to-end parse
test once they exist.

### Tasks

1. `questpick.parse` and `questpick.resolve` as pure functions, with unit tests. No config needed.
2. The class-to-brawler table in `config.py`, seeded from the owned roster shape.
3. `quests.py` returns the OCR lines from the startup visit, behind the new config region.
4. Controller wiring: the quest pick feeds `_do_select_brawler`, fallback chain preserved.
5. `FarmPlan.quest_aware` through `plans.py`, `farmplan.DEFAULT_PLAN` and the plan editor.
6. Feed event kind and the panel line.
7. Calibration pull request with the `QUEST_LIST_*` values, once the captures exist.

## 3. Opt-in auto-upgrade

### Goal

Default off. When on, after a session, open the farm brawler detail screen and tap Upgrade if
power points and coins suffice. Verify then act, never gems, at most one upgrade per session.

### The rail this breaks, stated plainly

`CONTRIBUTING.md` line 9 lists "GET or Upgrade" in the never-tap set, and `config.py` around the
`BRAWLER_SELECT_BUTTON` block documents the bottom-right UPGRADE button as never tapped. This
feature contradicts a hard rule. The rule must be amended in the same owner-approved pull request,
narrowed to something like: never tap Upgrade except the coin-priced power upgrade on the farm
brawler own detail screen, while `auto_upgrade` is on. Shipping the code without that amendment
leaves the repo self-contradictory and the rail unenforceable.

### Two approaches

**A. At a cadence between games.** More upgrades per day. Costs hot-path time on the menu, and
every extra trip to the brawler screen is another chance to be on an unknown screen next to a
gem-priced button. Reject for v1.

**B. Once at session end (recommended).** Runs on the stop path, after the last match and before
`close_game_on_stop`. The bot is already at the menu, nothing is time critical, and a failure
costs nothing because the session is over.

Recommendation: B.

### Components

New: `brawlfarm/core/upgrade.py`, `tests/test_upgrade.py`.

Modified: `brawlfarm/core/controller.py` (one call on the stop path), `brawlfarm/settings.py`
(a new `FarmSection`), `brawlfarm/core/config.py` (an `UPGRADE_*` block),
`brawlfarm/api/settings_routes.py`, `brawlfarm/web/src/settings/Behavior.tsx`,
`brawlfarm/api/feed.py`, `CONTRIBUTING.md`.

### State machine

States: AT_MENU, OPEN_BRAWLERS, LOCATE (reusing the by-name locate half of
`brawlers.select_brawler_by_name_checked`), ON_DETAIL, READ, GATE, TAP, VERIFY, EXIT.

Every transition re-classifies with `states.classify`. Any state that is not the expected one,
including UNKNOWN, jumps straight to EXIT, which is the existing tap-only `_exit_to_menu` path.
No retries beyond the existing nav retry budgets.

READ needs three OCR values and one color check:

- Power points, read as current over needed, from `UPGRADE_PP_REGION`.
- Coin balance from `UPGRADE_COINS_REGION`; the menu top bar also carries it, which gives a
  cross-check.
- The upgrade cost from `UPGRADE_COST_REGION`.
- The price chip color fraction against a coin-gold band, plus an explicit check that the
  gem-purple fraction is near zero.

GATE passes only if all of these hold: `auto_upgrade` is on, power points current is at least
needed, coins are at least cost plus `coin_floor`, the gold check passes, the purple check fails,
the cost OCR parsed to an integer, and no upgrade has been done this session. Anything ambiguous
is a no.

VERIFY re-screencaps after the tap and requires the power-point line to have changed. If it has
not, log an `upgrade_unverified` event and exit. Do not tap again.

### Settings and API

New section in `brawlfarm/settings.py`: a `FarmSection(_Section)` with `auto_upgrade: bool = False`
and `coin_floor: int` defaulting to 0 with a ge=0 field constraint. Wired into `AppSettings` as
`farm`, and into `worker_env` as `BRAWL_AUTO_UPGRADE` and `BRAWL_COIN_FLOOR`, read in `config.py`
next to the other `BRAWL_*` flags. Panel: two controls in Settings under Behavior, the number
input disabled while the toggle is off, with copy that says it never spends gems. Feed line on
success naming the brawler, the new power level and the coin cost.

### Calibration dependency

Live captures required, from observe mode, all on the brawler detail screen at 1600x900:

- The farm brawler with enough power points and coins, so the Upgrade button is live.
- The same brawler short on power points, and short on coins, so the two negative gates are real.
- A max-level brawler, where the button is absent or greyed.
- Any detail screen showing a gem-priced element in or near that area, to fix the purple band.
- The post-tap frame, to fix what VERIFY looks at.

Nothing in this feature can be calibrated without those five.

### Safety-rail impact

Largest of the three. Beyond the `CONTRIBUTING.md` amendment: the tap coordinate must be a fixed
config value, never an OCR-derived box, so a mis-read cannot move the tap; the gem guard is two
independent checks that must agree; the once-per-session counter lives on the controller instance,
not on disk, so a crash cannot resume mid-upgrade; and the whole path is skipped when
`auto_upgrade` is off, with a test that asserts zero taps in that case.

### Test plan

Unit: the GATE truth table across power points, coins, floor, gold, purple and the session
counter, with every ambiguous input resolving to no. A fake adb that records taps: assert exactly
zero taps with the flag off, and exactly one tap on the happy path. The VERIFY failure path emits
the event and does not re-tap. Unknown-screen injection at each state exits to the menu. Settings
round trip through the API. A rail test that greps `upgrade.py` for any tap coordinate that is not
a `config.UPGRADE_*` constant.

### Tasks

1. `FarmSection` in settings, env plumbing, config flags.
2. The gate as a pure function plus its truth-table tests. No screen reads.
3. `upgrade.py` state machine against a fake adb and canned frames.
4. Controller stop-path wiring, once per session.
5. Settings panel toggle and coin floor, plus the feed line.
6. The `CONTRIBUTING.md` never-tap amendment, in the owner-approved pull request.
7. Calibration pull request with the `UPGRADE_*` values, once the captures exist.

## Order and dependencies

Feature 1 first, and alone. It adds no coordinates, so it needs no calibration pull request, and
it is what produces the labeled captures the other two are blocked on. Ship it, then have the
owner record two sessions: one that opens and scrolls the quests screen through the variants
listed above, and one that walks the farm brawler detail screen through the upgrade states.

Features 2 and 3 are independent of each other and can run in parallel after that, but each splits
into a part that needs no captures and a part that does. Write `questpick.parse`,
`questpick.resolve` and the upgrade gate function first, with unit tests, since all three are pure
and unblocked today. The screen reads, the `config.py` values and the two calibration pull
requests wait on the recordings.

The `CONTRIBUTING.md` never-tap amendment is a prerequisite for merging any part of feature 3 that
taps, not a follow-up. Feature 2 has no rail change and can merge as soon as its captures land.
