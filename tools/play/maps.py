"""Trio showdown map grids: fetch the pinned game CSVs and build showdown_maps.json.

    uv run python -m tools.play.maps fetch [--home PATH] [--force]
    uv run python -m tools.play.maps build [--src DIR] [--out PATH]

Standard library only. The raw CSVs stay in the cache under the brawlfarm home folder;
only the derived JSON is committed. See docs/play-maps.md.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import urllib.request
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


def cache_dir(home: Path) -> Path:
    return home / "assets" / PINNED_VERSION


def render(doc: dict) -> bytes:
    return (json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _check_source(src: Path) -> None:
    try:
        meta = json.loads((src / "SOURCE.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise BuildError(f"SOURCE.json unreadable in {src}: {exc}") from exc
    if meta.get("commit") != PINNED_COMMIT or meta.get("version") != PINNED_VERSION:
        raise BuildError(
            f"SOURCE.json names {meta.get('commit')} {meta.get('version')}, pins are {PINNED_COMMIT} {PINNED_VERSION}"
        )


def build(src: Path, out: Path) -> dict:
    _check_source(src)
    doc = build_document(
        parse_tiles(read_rows(src / "csv_logic/tiles.csv")),
        select_trio(
            records(read_rows(src / "csv_logic/locations.csv")),
            records(read_rows(src / "localization/texts.csv")),
            parse_maps(read_rows(src / "csv_logic/maps.csv")),
        ),
    )
    before: set[str] = set()
    if out.exists():
        try:
            before = set(json.loads(out.read_text(encoding="utf-8")).get("names", {}))
        except ValueError:
            before = set()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(render(doc))
    names = set(doc["names"])
    print(f"maps: {len(doc['maps'])}")
    print(f"names: {len(names)}")
    for n, ids in doc["names"].items():
        if len(ids) > 1:
            print(f"shared: {n}: {', '.join(ids)}")
    for m in doc["maps"]:
        if m["unknown_codes"]:
            print(f"unknown: {m['map_id']}: {' '.join(m['unknown_codes'])}")
    if before:
        print(f"names added: {', '.join(sorted(names - before)) or 'none'}")
        print(f"names removed: {', '.join(sorted(before - names)) or 'none'}")
    print(f"wrote: {out}")
    return doc


RAW_BASE = f"https://raw.githubusercontent.com/tailsjs/brawl-stars-assets/{PINNED_COMMIT}/{PINNED_VERSION}/"
_OPENER = urllib.request.urlopen


class FetchError(Exception):
    """A download failed; fetch exits 2 with the URL in the message."""


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _cached(cache: Path) -> bool:
    try:
        meta = json.loads((cache / "SOURCE.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if meta.get("commit") != PINNED_COMMIT:
        return False
    files = meta.get("files", {})
    return all((cache / rel).is_file() and files.get(rel) == _sha(cache / rel) for rel in FILES)


def fetch(cache: Path, *, force: bool = False, opener=None) -> bool:
    opener = opener or _OPENER
    if not force and _cached(cache):
        return False
    hashes = {}
    for rel in FILES:
        url = RAW_BASE + rel
        dest = cache / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        part = dest.with_name(dest.name + ".part")
        try:
            with opener(url, timeout=60) as resp:
                part.write_bytes(resp.read())
        except (OSError, ValueError) as exc:
            part.unlink(missing_ok=True)
            raise FetchError(f"{url}: {exc}") from exc
        os.replace(part, dest)
        hashes[rel] = _sha(dest)
    meta = {"commit": PINNED_COMMIT, "version": PINNED_VERSION, "files": hashes}
    (cache / "SOURCE.json").write_bytes(render(meta))
    return True


def _fetch_main(home: Path, force: bool) -> int:
    cache = cache_dir(home)
    try:
        downloaded = fetch(cache, force=force)
    except FetchError as exc:
        print(f"fetch failed: {exc}", file=sys.stderr)
        return 2
    print(f"fetched into {cache}" if downloaded else f"cached: {cache}")
    return 0


def main(argv: list[str] | None = None) -> int:
    from brawlfarm.settings import default_home

    ap = argparse.ArgumentParser(prog="python -m tools.play.maps")
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch")
    f.add_argument("--home", type=Path, default=None)
    f.add_argument("--force", action="store_true")
    b = sub.add_parser("build")
    b.add_argument("--src", type=Path, default=None)
    b.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    if args.cmd == "build":
        try:
            build(args.src or cache_dir(default_home()), args.out)
        except BuildError as exc:
            print(f"build failed: {exc}", file=sys.stderr)
            return 1
        return 0
    return _fetch_main(args.home or default_home(), args.force)


if __name__ == "__main__":
    raise SystemExit(main())
