"""Trio showdown map grids: fetch the pinned game CSVs and build showdown_maps.json.

    uv run python -m tools.play.maps fetch [--home PATH] [--force]
    uv run python -m tools.play.maps build [--src DIR] [--out PATH]

Standard library only. The raw CSVs stay in the cache under the brawlfarm home folder;
only the derived JSON is committed. See docs/play-maps.md.
"""

from __future__ import annotations

import csv
from pathlib import Path

PINNED_COMMIT = "cc307ff"
PINNED_VERSION = "69.230"
SOURCE_REPO = "https://github.com/tailsjs/brawl-stars-assets"
FILES = (
    "csv_logic/maps.csv",
    "csv_logic/tiles.csv",
    "csv_logic/locations.csv",
    "localization/texts.csv",
)
DISCLAIMER = (
    "This file is derived from Brawl Stars game data (version 69.230) via "
    "github.com/tailsjs/brawl-stars-assets. Brawl Stars and its content belong to Supercell. "
    "brawlfarm is not affiliated with, endorsed, sponsored, or specifically approved by "
    "Supercell, and Supercell is not responsible for it. Used under the Supercell Fan Content "
    "Policy: www.supercell.com/fan-content-policy."
)
MARKERS = {"1": "solo_spawn", "2": "duo_spawn", "3": "trio_spawn", "4": "power_cube_box"}
TYPE_NAMES = {"string", "int", "boolean", "number"}
REPO = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO / "brawlfarm" / "play" / "data" / "showdown_maps.json"


class BuildError(Exception):
    """The inputs cannot produce a trustworthy file; build exits 1 with this message."""


def read_rows(path: Path) -> list[list[str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        return [row for row in csv.reader(fh)]


def _body(rows: list[list[str]]) -> list[list[str]]:
    """Rows after the header, minus the Supercell type row when there is one."""
    body = rows[1:]
    if (
        body
        and all(c.strip().lower() in TYPE_NAMES for c in body[0] if c.strip())
        and any(c.strip() for c in body[0])
    ):
        body = body[1:]
    return body


def records(rows: list[list[str]]) -> list[dict[str, str]]:
    header = rows[0]
    return [dict(zip(header, row + [""] * (len(header) - len(row)))) for row in _body(rows)]


def _true(value: str) -> bool:
    return value.strip().lower() == "true"


def parse_maps(rows: list[list[str]]) -> dict[str, list[str]]:
    grids: dict[str, list[str]] = {}
    current: list[str] | None = None
    for row in _body(rows):
        if len(row) < 2:
            continue
        if row[0].strip():
            current = grids.setdefault(row[0].strip(), [])
        if current is not None:
            current.append(row[1])
    return grids


def parse_tiles(rows: list[list[str]]) -> dict[str, dict]:
    tiles: dict[str, dict] = {}
    for rec in records(rows):
        code = rec.get("TileCode", "")
        if not code:
            continue
        name = rec.get("Name") or next(iter(rec.values()))
        tiles[code] = {
            "name": name,
            "blocks_movement": _true(rec.get("BlocksMovement", "")),
            "blocks_projectiles": _true(rec.get("BlocksProjectiles", "")),
            "destructible": _true(rec.get("IsDestructible", "")),
            "forest": _true(rec.get("IsForest", "")),
        }
    return tiles


def select_trio(locations: list[dict], texts: list[dict], maps: dict[str, list[str]]) -> list[dict]:
    en = {t.get("TID", ""): t.get("EN", "") for t in texts}
    out = []
    for loc in locations:
        if loc.get("GameModeVariation") != "TrioShowdown" or _true(loc.get("Disabled", "")):
            continue
        map_id, tid = loc.get("Map", ""), loc.get("TID", "")
        if map_id not in maps:
            raise BuildError(f"{loc.get('Name')}: map {map_id} is not in maps.csv")
        if not en.get(tid):
            raise BuildError(f"{loc.get('Name')}: no text for {tid}")
        grid = maps[map_id]
        cols = len(grid[0]) if grid else 0
        if not grid or any(len(line) != cols for line in grid):
            raise BuildError(f"{map_id}: ragged grid")
        out.append(
            {
                "map_id": map_id,
                "location": loc["Name"],
                "name": en[tid],
                "tid": tid,
                "theme": loc.get("LocationTheme", ""),
                "rows": len(grid),
                "cols": cols,
                "grid": list(grid),
            }
        )
    return out


def preference_key(map_id: str) -> tuple[int, str]:
    """Sort key: the highest number after the last underscore first (Survival_605 before Survival_3)."""
    tail = map_id.rsplit("_", 1)[-1]
    return (-int(tail) if tail.isdigit() else 1, map_id)


def build_document(tiles: dict[str, dict], selected: list[dict]) -> dict:
    known = set(tiles) | set(MARKERS)
    maps = []
    for s in selected:
        codes = {c for line in s["grid"] for c in line}
        maps.append({**s, "unknown_codes": sorted(codes - known)})
    maps.sort(key=lambda m: (m["name"], m["map_id"]))
    names: dict[str, list[str]] = {}
    for m in maps:
        names.setdefault(m["name"], []).append(m["map_id"])
    names = {n: sorted(ids, key=preference_key) for n, ids in names.items()}
    return {
        "schema": 1,
        "source": SOURCE_REPO,
        "commit": PINNED_COMMIT,
        "version": PINNED_VERSION,
        "disclaimer": DISCLAIMER,
        "tiles": tiles,
        "markers": dict(MARKERS),
        "markers_inferred": True,
        "maps": maps,
        "names": names,
    }
