# Contributing to brawlfarm

Bug reports and pull requests are welcome. Read this first; most of it is about the one part of the project where review is not a negotiation.

## The safety rails

A change that weakens any of these is not merged, regardless of how good the rest of it is. This is a blocker in review, not a comment to argue with.

- The never-tap set: ACCEPT on a team invite, GET or Upgrade, EQUIP NOW, any shop buy button, the pass VAULT, anything priced in gems, REROLL QUEST on the quests screen, the shop offer panel on the BRAWLERS screen. No blind taps in the shop.
- REROLL QUEST sits top right on the quests screen (`QUEST_REROLL_BUTTON`). It is calibrated as a landmark only, so the sweep that reads the quest cards can be measured against it: a reroll throws a quest away, so nothing taps it and no module outside `config.py` may even name it.
- The shop offer panel on the BRAWLERS screen runs from x 0 to x 125 and carries a live buy control. No swipe endpoint goes below x 146.
- Verify then act: every navigation checks the screen before it taps and bails to the menu on a failed check, so a stale coordinate becomes a logged no-op instead of a wrong tap.
- The 1600 x 900 assertion at worker startup, which exits rather than guessing.
- One worker per instance.
- Kill only by the PID recorded in that instance's `status.json`, never by process name.
- No user string reaches a shell or a path. No `shell=True`, no string interpolation into a command line or a filesystem path.
- The play stream is read-only. The scrcpy server runs with control off, and nothing under `brawlfarm/play/` may import a tap or swipe.

## Calibration changes

The calibration block of `brawlfarm/core/config.py`, and the tap coordinates and OCR needles in `brawlfarm/core/controller.py`, `brawlfarm/core/states.py` and `brawlfarm/core/vision.py`, change only in a dedicated calibration PR that carries live evidence: the frames you matched against and the scores you measured. Do not fold a coordinate change into a feature PR.

## What never goes in the repository

- No `discord` import anywhere, in any module, test or tool.
- Never commit `.env`, the data directory, captures, logs, or screenshots of an account.
- Training data, videos, frames and model files never enter the repository; `play.onnx` and `play.json` arrive only through a calibration pull request.
- `uv run python tools/scrub_check.py` must print `0 hit(s)`. It is a gate, and it fails the build.

## Running the checks

```
uv sync --group dev
corepack enable
pnpm --dir brawlfarm/web install
pnpm --dir brawlfarm/web build     # the panel is served from brawlfarm/web/dist
uv run pytest
pnpm --dir brawlfarm/web test && pnpm --dir brawlfarm/web typecheck
uv run ruff check . && uv run ruff format --check .
uv run python tools/scrub_check.py
```

If `corepack enable` fails with EPERM, which is what a Windows shell without elevation gives you, `npm install -g pnpm@10.17.1` installs the same pnpm.

## Commits and pull requests

Conventional commit subjects: `feat(scope): ...`, `fix(scope): ...`, `docs(scope): ...`, `chore: ...`.

One PR per change. Give it four sections:

- **What** it changes and why.
- **Safety**: which rails the change touches, or a plain statement that it touches none.
- **How to verify**: the commands a reviewer runs.
- **Evidence**: the output of those commands, and for anything that touches the game loop, what you saw on a live instance.

## Prose

No em-dashes and no emoji in prose, in the README, the docs, commit messages or PR descriptions. Plain sentences, second person where you are addressing the reader.
