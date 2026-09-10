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
