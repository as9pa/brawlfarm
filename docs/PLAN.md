# brawlfarm board

Living board. Finished work moves to the top with its proof.

## Done

- Phase 3: API and events. PR https://github.com/as9pa/brawlfarm/pull/3 (merged 2026-09-10). Proof: CI run https://github.com/as9pa/brawlfarm/actions/runs/34539932576 green on the merged head (540 tests, ruff clean, scrub check 0 hits); final whole-branch review MERGE with no blockers; live run on one BlueStacks instance driven entirely through the API: setup scan, display check and a 1600 x 900 screenshot answered, a start request took the instance from stopped through starting and farming to stopping and stopped over the event stream, the feed streamed the match, games.csv grew by 26 rows and the stats route reported the day (scrubbed excerpts in the PR). Deferred: the manual controls do not take the tick lock (consistency only; only the tick launches, so one worker per instance holds); trophies per hour needs a floor and 2-dp hours in the Stats UI (phase 6); the roster and queue for the plan editor join GET /plan in phase 4; the setup wizard must persist the discovered adb path into connection.adb_path (phase 5); core/events.py refresh prints still reach stdout; alerts are in memory only and vanish on restart.
- Phase 2: settings and supervisor. PR https://github.com/as9pa/brawlfarm/pull/2 (merged 2026-09-10). Proof: CI run https://github.com/as9pa/brawlfarm/actions/runs/34473328978 green on the merged head (416 tests, ruff clean, scrub check 0 hits); live run on one BlueStacks instance: the supervisor launched the worker with the settings env, showed starting, farming, stopping and stopped in turn, the worker played 2 matches and honoured the graceful stop at the menu without the 110 s escalation (excerpts in the PR). Deferred: the healthchecks ping (phase 3); a conftest reset of the notify and scheduler globals and the --no-launch help text (phase 3); schedule off means always-run, so Stopped only comes from the user's stop (owner to confirm the wording); battle-log stats stayed empty because the owner's API token is IP-restricted.
- Housekeeping: PR https://github.com/as9pa/brawlfarm/pull/4 (merged 2026-09-10) retired every comment and docstring citation of legacy notes that were never ported (comments and docstrings only, AST-equal on all 20 files, 540 tests, scrub check 0 hits), which closes the phase 1 deferred item about legacy doc paths, and added docs/notes/2026-09-10-frame-capture-assessment.md: direct window capture of BlueStacks is not worth it (adb capture measured at 172 ms, about a third of the loop, and window frames would need rescaling that breaks the template thresholds), so the frame-timing instrumentation was not added.
- Phase 1: repo and core. PR https://github.com/as9pa/brawlfarm/pull/1 (merged 2026-09-10). Proof: CI run https://github.com/as9pa/brawlfarm/actions/runs/34446450332 green on the merged head (336 tests, ruff clean, scrub check 0 hits); farm core ported from the legacy bot package with identity removed; final whole-branch review MERGE with no blockers. Deferred: conftest isolation does not reach module-level cached paths in core/config, core/datalog and core/stats (fix in phase 2 with the settings model); ported test docstrings still cite legacy doc paths; CI actions warn about Node 20 deprecation.

## In flight

- Phase 4: UI shell, Fleet and Instance screens. Proposal artifact published 2026-09-10 (27 items with Accept, Later or Reject per item, decisions stored on the page) and waiting for the owner's decisions; the follow-up page with a Go control comes after that, and the plan is written only after go. Spec section 8.

## Queue (v1)

5. Setup wizard and Settings screens
6. Stats with brawler icons
7. Docs and publish; archive the legacy repo

## After v1

8. Calibration page, then recalibration for the current game version; desktop window and tray icon; labeled frame recorder.

## On hold (owner decision)

- Quest-aware brawler choice.
- Opt-in auto-upgrade.

Design: `docs/superpowers/specs/2026-09-10-brawlfarm-design.md`.
