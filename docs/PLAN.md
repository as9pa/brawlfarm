# brawlfarm board

Living board. Finished work moves to the top with its proof.

## Done

- Phase 2: settings and supervisor. PR https://github.com/as9pa/brawlfarm/pull/2 (merged 2026-09-10). Proof: CI run https://github.com/as9pa/brawlfarm/actions/runs/34473328978 green on the merged head (416 tests, ruff clean, scrub check 0 hits); live run on one BlueStacks instance: the supervisor launched the worker with the settings env, showed starting, farming, stopping and stopped in turn, the worker played 2 matches and honoured the graceful stop at the menu without the 110 s escalation (excerpts in the PR). Deferred: the healthchecks ping (phase 3); a conftest reset of the notify and scheduler globals and the --no-launch help text (phase 3); schedule off means always-run, so Stopped only comes from the user's stop (owner to confirm the wording); battle-log stats stayed empty because the owner's API token is IP-restricted.
- Phase 1: repo and core. PR https://github.com/as9pa/brawlfarm/pull/1 (merged 2026-09-10). Proof: CI run https://github.com/as9pa/brawlfarm/actions/runs/34446450332 green on the merged head (336 tests, ruff clean, scrub check 0 hits); farm core ported from the legacy bot package with identity removed; final whole-branch review MERGE with no blockers. Deferred: conftest isolation does not reach module-level cached paths in core/config, core/datalog and core/stats (fix in phase 2 with the settings model); ported test docstrings still cite legacy doc paths; CI actions warn about Node 20 deprecation.

## In flight

- Phase 3: API and events. Plan: not yet written; spec section 7.

## Queue (v1)

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
