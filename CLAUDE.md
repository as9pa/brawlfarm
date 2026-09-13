# brawlfarm: instructions for Claude Code

## Code review

Code review is on for this project. Every implementation task in a plan gets a spec-compliance and code-quality review pass on sonnet before it counts as complete, and every branch gets a whole-branch review on sonnet before its pull request opens. Review findings are fixed by an implementer, then re-reviewed once. The gate stays: `pnpm typecheck`, `pnpm test`, `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run python tools/scrub_check.py` printing `0 hit(s)`, and a live pass for anything that touches the farm loop.

## Safety rails

See `CONTRIBUTING.md`. Never-tap logic, verify-then-act, the 1600x900 assertion and the tap coordinates, OCR needles and templates in `brawlfarm/core/` change only in an owner-approved calibration pull request that says so in its body and lists every changed value.
