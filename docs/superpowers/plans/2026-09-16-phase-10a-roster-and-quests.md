# Phase 10a: roster recalibration and quest-aware brawler choice, implementation plan

> For agentic workers: REQUIRED SUB-SKILL: use superpowers:subagent-driven-development (recommended)
> or superpowers:executing-plans to implement this plan task by task. Steps use checkbox syntax.

Goal: recalibrate the rebuilt brawler roster screen, then pick the farm brawler from an active quest.

Architecture: two branches in order. phase-10/roster-recal is a calibration pull request that moves
the roster constants to the new horizontally scrolling column-major grid and replaces the vertical
index-arithmetic scroll with a name-directed scan. phase-10/quest-pick then reads the quests screen
once per session inside the startup visit, parses multi-candidate quests and feeds the name into the
selection path that already exists.

Tech Stack: Python 3.13 with uv, pytest, ruff; pnpm for brawlfarm/web; adb and OpenCV plus EasyOCR
through brawlfarm/core/vision.py.

Spec: docs/superpowers/specs/2026-09-16-phase-10a-roster-and-quests.md. Read it first; every
coordinate in this plan comes from its config block and is provisional.

## Global constraints

- Every coordinate is PROVISIONAL, doubled from an 800x450 recording. Re-measure on session 2 before
  the calibration pull request merges, and say so in the pull request body.
- Calibration values change only in an owner-approved calibration pull request whose body says so
  and lists every changed value (CONTRIBUTING.md). Never fold a coordinate change into a feature PR.
- Never-tap: REROLL QUEST (1430,172), the roster shop offer panel at x below 270, UPGRADE, and the
  whole existing set.
- Gate for every task: uv run pytest, uv run ruff check ., uv run ruff format --check .,
  uv run python tools/scrub_check.py printing 0 hit(s). Tasks touching brawlfarm/web also run
  pnpm --dir brawlfarm/web test and pnpm --dir brawlfarm/web typecheck. A live pass on Pie64 is
  required before either pull request opens.
- Review is on for this project: each task gets a sonnet spec-compliance and code-quality review,
  each branch a whole-branch sonnet review before its pull request.
- Prose rule: no em-dashes and no emoji anywhere, including commit messages.
- Do not touch brawlfarm/core/recorder.py, preview.py, observer.py or docs/calibration.md while the
  phase-10 observe branch is open; coordinate with its owner before documenting the new geometry.

## File structure

Branch 1: brawlfarm/core/config.py (brawler calibration block), brawlfarm/core/brawlers.py
(_visible_cards, _scroll_grid, select_brawler_by_name_checked), tests/test_brawlers_select.py.
Branch 2: brawlfarm/core/questpick.py (regexes, Quest, group_cards, resolve),
brawlfarm/core/config.py (new QUEST block), brawlfarm/core/quests.py (read_quest_lines, visit),
brawlfarm/core/farmplan.py (owned_trophy_map, DEFAULT_PLAN), brawlfarm/core/controller.py
(_do_select_brawler), brawlfarm/api/plans.py, brawlfarm/api/feed.py,
brawlfarm/web/src/instance/FarmPlan.tsx, CONTRIBUTING.md, tests/test_questpick.py,
tests/test_quests_read.py, tests/test_controller_questpick.py, tests/test_never_tap.py.

---

# Branch 1: phase-10/roster-recal (calibration pull request)

### Task 1: the roster constants

Files: modify brawlfarm/core/config.py, brawler selection block (about lines 421 to 480).

- [ ] Step 1: set every value in the spec's roster config block, keeping each comment line that
      records the half-size measurement it came from. Add BRAWLER_SEARCH_FIELD and a comment saying
      the shop offer panel at x below 270 is never-tap.
- [ ] Step 2: delete BRAWLER_SCROLL_BOTTOM_Y, BRAWLER_SCROLL_TOP_Y, BRAWLER_SCROLL_MAX_PX,
      BRAWLER_SCROLL_MIN_PX, BRAWLER_SCROLL_FACTOR, BRAWLER_GRID_TARGET_Y, BRAWLER_GRID_COLS_X,
      BRAWLER_GRID_ROW0_Y and BRAWLER_GRID_ROW_H. Leave BRAWLER_SORT_DROPDOWN_REGION and the
      BRAWLER_TOGGLE_ORANGE values untouched, with a comment marking them UNVERIFIED on session 1.
- [ ] Step 3: run uv run ruff check . and uv run ruff format --check .
- [ ] Step 4: run uv run pytest. Expect failures only in tests/test_brawlers_select.py, from the
      names deleted in step 2. Record which ones; tasks 2 and 3 fix them.
- [ ] Step 5: commit. git commit -m "feat(calibration): roster constants for the new grid"

Acceptance: no module imports a deleted name (grep for each), ruff clean, and the only failing tests
are the select-by-name ones.

### Task 2: card geometry and a horizontal scroll

Files: modify brawlfarm/core/brawlers.py (_visible_cards about line 152, _scroll_grid about line
169); test tests/test_brawlers_select.py.

- [ ] Step 1: write failing tests: _visible_cards maps an OCR line at (520, 308) to the card whose
      centre is (456, 244) using BRAWLER_GRID_COL0_X, BRAWLER_GRID_COL_W, BRAWLER_GRID_ROWS_Y,
      BRAWLER_NAME_LABEL_DX and BRAWLER_NAME_LABEL_DY, and returns the card centre, not the label
      point; _scroll_grid("left") calls adb.swipe(1400, 488, 500, 488, 600) and _scroll_grid("right")
      calls adb.swipe(500, 488, 1400, 488, 600), with adb.swipe monkeypatched to record its args.
- [ ] Step 2: run uv run pytest tests/test_brawlers_select.py -v and confirm both fail.
- [ ] Step 3: implement. _visible_cards subtracts the label offset, snaps x to the nearest column
      centre (col0 plus k times col_w) and y to the nearest entry of BRAWLER_GRID_ROWS_Y.
      _scroll_grid takes a direction string, not a pixel count.
- [ ] Step 4: run uv run pytest tests/test_brawlers_select.py -v. Expect pass.
- [ ] Step 5: commit. git commit -m "feat(calibration): horizontal grid geometry and scroll"

Acceptance: no swipe endpoint has x below 500 or y outside the grid; no caller passes pixels to
_scroll_grid.

### Task 3: name-directed scan instead of index arithmetic

Files: modify brawlfarm/core/brawlers.py select_brawler_by_name_checked (about lines 186 to 277);
test tests/test_brawlers_select.py.

Interfaces: consumes _visible_cards and _scroll_grid(direction) from task 2. Produces the unchanged
signature select_brawler_by_name_checked(target, owned, log) returning (name or None, suspicion).

- [ ] Step 1: write failing tests with a fake screen source whose visible names are ["CARL", "COLT",
      "CROW"]: target "BULL" swipes right, target "DYNAMIKE" swipes left, target "COLT" taps its card
      centre and never swipes, an always-empty OCR returns suspicion True after
      BRAWLER_SELECT_MAX_SWIPES swipes, and a target that never appears returns (None, False).
- [ ] Step 2: run uv run pytest tests/test_brawlers_select.py -v. Expect failures.
- [ ] Step 3: implement. Delete both uses of owned_norm_list.index(n) // 3 and every pixel-offset
      calculation. Loop: OCR with _visible_cards; if the normalized target is a key, tap its centre
      and run the existing detail verification unchanged; else compare the normalized target with
      min and max of the visible normalized names and call _scroll_grid("right") or ("left");
      bail after BRAWLER_SELECT_MAX_SWIPES. Keep the RECALIB_TRIPWIRE branch exactly as it is.
- [ ] Step 4: run uv run pytest -v. Expect pass.
- [ ] Step 5: run uv run ruff check . and uv run ruff format --check . and
      uv run python tools/scrub_check.py. Expect 0 hit(s).
- [ ] Step 6: commit. git commit -m "feat(calibration): find the card by name, not by index"

Acceptance: the word index no longer appears in the function; the sorted-by-Name assumption is the
only ordering assumption left; the detail-screen verification before SELECT is unchanged.

### Task 4: live pass and the calibration pull request

- [ ] Step 1: re-measure every roster value against the session 2 recording and correct any that
      moved. Any value that moves more than 8 px is a finding, not a tweak: note it in the body.
- [ ] Step 2: park Pie64 with a stop override, drive a select-by-name through the API, and watch the
      grid. Confirm no tap lands on the offer panel, SEARCH, either toggle, or the sort label.
- [ ] Step 3: run the full gate: uv run pytest, uv run ruff check ., uv run ruff format --check .,
      uv run python tools/scrub_check.py.
- [ ] Step 4: open the pull request. Body says it is a calibration pull request, lists every changed
      value old to new, names the frames, and records the live pass. Request the owner's approval.

---

# Branch 2: phase-10/quest-pick (feature pull request)

### Task 5: multi-candidate parsing

Files: modify brawlfarm/core/questpick.py; test tests/test_questpick.py.

Interfaces: produces Quest(kind, candidates: tuple[str, ...], count: int, line: str) with target as a
property returning candidates[0], and parse(lines) unchanged in signature.

- [ ] Step 1: write failing tests from the spec's verbatim wording list: the six brawler quests give
      the right candidate tuples, JAE-YONG normalizes to JAEYONG, DEAL 160000 POINTS OF DAMAGE with
      no WITH is dropped, DEFEAT and PLAY and USE lines are dropped, and target still equals
      candidates[0] for a single-name quest.
- [ ] Step 2: run uv run pytest tests/test_questpick.py -v. Expect failures.
- [ ] Step 3: implement. Widen the damage regex to make POINTS OF optional; split the names group on
      commas and on the standalone word OR; normalize each candidate with norm_name and drop empties;
      keep KIND_CLASS when any candidate is in CLASSES; keep KIND_MODE untouched.
- [ ] Step 4: run uv run pytest tests/test_questpick.py -v. Expect pass. Commit.
      git commit -m "feat(questpick): parse quests that name several brawlers"

### Task 6: claimed rows and card grouping

Files: modify brawlfarm/core/questpick.py; test tests/test_questpick.py.

Interfaces: produces group_cards(lines) taking the list of (text, conf, (cx, cy)) that
vision.read_lines_boxes returns and giving back a list of joined card strings in screen order.

- [ ] Step 1: write failing tests: a progress token N/M with N equal to M drops its card (8/8, 5/5),
      0/5 and 7/24 keep it; a three-line title at cy 300, 320, 340 with the same cx joins in cy order
      with single spaces; two cards 457 apart in cx stay separate; a card with cluster mean cx 96 or
      1490 is dropped by QUEST_EDGE_MARGIN_X.
- [ ] Step 2: run uv run pytest tests/test_questpick.py -v. Expect failures.
- [ ] Step 3: implement using only the centres, since read_lines_boxes returns no rectangles: bucket
      by cy into the three bands from QUEST_TITLE_BAND0, QUEST_PROGRESS_BAND0 and QUEST_ROW_PITCH,
      cluster a row's titles by cx within QUEST_CARD_X_TOL, attach the nearest progress token within
      half QUEST_CARD_PITCH_X, drop edge clusters, drop claimed cards.
- [ ] Step 4: run uv run pytest tests/test_questpick.py -v. Expect pass. Commit.
      git commit -m "feat(questpick): group OCR lines into quest cards"

### Task 7: resolve with trophies and a preferred name

Files: modify brawlfarm/core/questpick.py and brawlfarm/core/farmplan.py; tests
tests/test_questpick.py and tests/test_farmplan.py.

Interfaces: produces resolve(quests, owned, trophies=None, prefer=None) returning a roster-spelled
name or None, and farmplan.owned_trophy_map(api) returning dict[str, int] keyed by norm_name.

- [ ] Step 1: write failing tests: prefer wins when it is an owned candidate; without prefer the
      lowest-trophy owned candidate wins; equal trophies fall back to candidate order; with no
      trophies the first owned candidate wins; nothing owned gives None; class and mode quests give
      None; owned_trophy_map turns [{"name": "NITA", "trophies": 7}] into {"NITA": 7} and treats a
      missing trophies key as 0.
- [ ] Step 2: run uv run pytest tests/test_questpick.py tests/test_farmplan.py -v. Expect failures.
- [ ] Step 3: implement. Leave farmplan.resolve_target byte-identical: tests/test_controller_reselect
      monkeypatches it with a three-tuple lambda.
- [ ] Step 4: run uv run pytest -v. Expect pass. Commit.
      git commit -m "feat(questpick): resolve a candidate list against the roster"

### Task 8: the quest config block and the screen read

Files: modify brawlfarm/core/config.py (new QUEST block, after the mega quest block) and
brawlfarm/core/quests.py; test tests/test_quests_read.py.

Interfaces: consumes group_cards from task 6. Produces quests.read_quest_lines(log) returning a list
of joined card strings, and quests.visit(log) returning that same list after doing today's mega
activation, both leaving the game on the menu.

- [ ] Step 1: add every value from the spec's quests config block with its derivation comment.
- [ ] Step 2: write failing tests with adb.screencap and vision.read_lines_boxes monkeypatched to
      return two scripted pages then a repeat: read_quest_lines returns the union with no duplicate,
      it stops on the repeated page before QUEST_SWEEP_MAX, it swipes exactly
      adb.swipe(1300, 490, 700, 490, 600), and an empty OCR returns an empty list and logs the
      tripwire line rather than raising.
- [ ] Step 3: run uv run pytest tests/test_quests_read.py -v. Expect failures.
- [ ] Step 4: implement. visit opens QUESTS once, keeps the existing _on_quests_screen check and the
      existing mega activation, then calls read_quest_lines before the existing _exit_to_menu. Never
      tap inside the grid and never go near QUEST_REROLL_BUTTON.
- [ ] Step 5: run uv run pytest -v, then ruff check, ruff format --check and scrub_check. Commit.
      git commit -m "feat(quests): read the quest cards during the startup visit"

### Task 9: controller wiring, the plan flag and the feed

Files: modify brawlfarm/core/controller.py (_do_select_brawler about line 801, and the startup call
site that visits quests), brawlfarm/api/plans.py, brawlfarm/core/farmplan.py DEFAULT_PLAN,
brawlfarm/api/feed.py, brawlfarm/web/src/instance/FarmPlan.tsx; test
tests/test_controller_questpick.py.

Interfaces: consumes quests.visit, questpick.parse, questpick.resolve, farmplan.owned_trophy_map.

- [ ] Step 1: write failing tests: with quest_aware False the selection path is byte-identical to
      today and owned_trophy_map is never called; with it True and a resolved name, that exact name
      is what reaches select_brawler_by_name_checked; with it True and resolve returning None, the
      existing plan then lowest-trophy chain runs unchanged; a raising quests.visit is caught, logged
      and falls back.
- [ ] Step 2: run uv run pytest tests/test_controller_questpick.py -v. Expect failures.
- [ ] Step 3: implement. Keep the ordering constraint: the quest read happens in the startup quests
      visit that already exists, before _exit_to_menu, and the resolved name reaches
      _do_select_brawler before it runs. Do not add a second navigation. Pass the farm plan target as
      prefer. Emit one quest_pick feed event naming the quest line and the chosen brawler.
- [ ] Step 4: add quest_aware: bool = False to FarmPlan and to DEFAULT_PLAN, a toggle in
      FarmPlan.tsx whose help text says it only applies at session start, and the quest_pick kind in
      feed.py routed to the same panel group as select_brawler.
- [ ] Step 5: run uv run pytest -v, pnpm --dir brawlfarm/web test, pnpm --dir brawlfarm/web typecheck,
      ruff check, ruff format --check, scrub_check. Commit.
      git commit -m "feat(controller): quest-aware brawler choice behind a plan flag"

### Task 10: the never-tap amendment and the rails test

Files: modify CONTRIBUTING.md; test tests/test_never_tap.py.

- [ ] Step 1: write a failing test asserting no module passes QUEST_REROLL_BUTTON to adb.tap (grep
      the source of brawlfarm/core for the constant name and assert it appears only in config.py and
      the test), and that every swipe endpoint in config (QUEST_SWIPE and BRAWLER_SCROLL) sits more
      than 120 px from QUEST_REROLL_BUTTON, HOME_BUTTON, QUESTS_CLOSE_BUTTON and QUESTS_MEGA_CARD.
- [ ] Step 2: run uv run pytest tests/test_never_tap.py -v. Expect failures where the constant or the
      distance rule is not yet satisfied.
- [ ] Step 3: add REROLL QUEST on the quests screen and the brawler-screen shop offer panel to the
      never-tap list in CONTRIBUTING.md.
- [ ] Step 4: run uv run pytest -v. Expect pass. Commit.
      git commit -m "docs(safety): REROLL QUEST and the roster offer panel are never-tap"

### Task 11: live pass and the feature pull request

- [ ] Step 1: park Pie64 with a stop override, turn quest_aware on for that instance, and drive one
      session start through the API. Confirm the log names the quest and the brawler, that the grid
      sweep never taps, and that the session plays the chosen brawler.
- [ ] Step 2: repeat with quest_aware off and confirm the old behaviour, byte for byte in the log.
- [ ] Step 3: full gate: pnpm --dir brawlfarm/web typecheck, pnpm --dir brawlfarm/web test,
      uv run pytest, uv run ruff check ., uv run ruff format --check .,
      uv run python tools/scrub_check.py printing 0 hit(s).
- [ ] Step 4: whole-branch sonnet review, fix findings with an implementer, re-review once, then open
      the pull request with the four sections What, Safety, How to verify, Evidence.

## Self-review notes

Spec coverage: config block is task 1 and task 8; parsing is task 5; grouping task 6; resolve and
trophies task 7; the read task 8; wiring, the flag and the feed task 9; safety rails task 10; the
session 2 re-measure task 4; live passes tasks 4 and 11. The class-to-brawler table stays deferred,
unchanged from phase 9. The SEARCH field is deliberately not a task: typing into it needs an adb
text-input primitive the project does not have.

Open risks: every coordinate is provisional until session 2; BRAWLER_SORT_DROPDOWN_REGION and the
orange toggle-ON band were never exercised in the recording, so task 4 must confirm both before the
calibration pull request merges; a session with no owned candidate silently falls back, which is the
intended behaviour and is why the feed event exists.
