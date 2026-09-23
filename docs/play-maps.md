# Showdown map grids

## What this is

Play mode needs to know where the bushes, walls and water are on a trio showdown map. `brawlfarm/play/data/showdown_maps.json` holds the tile grid of every trio showdown map, derived from game version 69.230. `brawlfarm/play/maps.py` loads it with the standard library only, so you can use it without the play extra, and it never sends input.

## Where it comes from

The data comes from https://github.com/tailsjs/brawl-stars-assets at commit `cc307ff`, folder `69.230/`. The build tool reads four files from it:

- `csv_logic/maps.csv`
- `csv_logic/tiles.csv`
- `csv_logic/locations.csv`
- `localization/texts.csv`

Nothing raw is committed. The only committed file is the derived JSON, which holds only the trio showdown maps and ships in the wheel. Its `source`, `commit` and `version` keys record where it came from.

## Disclaimer

This file is derived from Brawl Stars game data (version 69.230) via github.com/tailsjs/brawl-stars-assets. Brawl Stars and its content belong to Supercell. brawlfarm is not affiliated with, endorsed, sponsored, or specifically approved by Supercell, and Supercell is not responsible for it. Used under the Supercell Fan Content Policy: www.supercell.com/fan-content-policy.

## Rebuilding

Download the pinned CSVs, then build the JSON from them:

```
uv run python -m tools.play.maps fetch
uv run python -m tools.play.maps build
```

The download cache is `%LOCALAPPDATA%\brawlfarm\assets\69.230`, or `assets\69.230` under `BRAWLFARM_HOME` when you set it. The cache is never committed. The same cache always gives the same bytes, so a rebuild with no version change leaves the JSON untouched.

## Bumping the game version

1. Change `PINNED_COMMIT` and `PINNED_VERSION` in `tools/play/maps.py`.
2. Run `fetch`, then `build`.
3. Commit the regenerated JSON in its own pull request, with the summary the tool prints: map count, names added, names removed, unknown codes.

Old cache folders stay on disk. Each is keyed by version, and nothing reads the old ones.

## What is inferred or unknown

- The spawn and box markers (the digits `1` to `4` in the grids) are inferred, and the JSON says so with `markers_inferred: true`.
- Tile codes the tiles table does not describe count as open ground. Each map lists its own in `unknown_codes`.
- Row 0 is assumed to be the top of the screen. Nothing has checked it yet.
- The gas constants in `brawlfarm/play/maps.py` (`GAS_START_S`, `GAS_END_S`, `GAS_FINAL_HALF` and `BUSH_GAS_MARGIN_TILES`) are unmeasured placeholders. A later pull request measures them from recorded matches and replaces them.

The design and the open questions are in the spec, [docs/superpowers/specs/2026-09-23-play-maps-kit.md](superpowers/specs/2026-09-23-play-maps-kit.md).
