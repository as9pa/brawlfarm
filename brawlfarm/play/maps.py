"""Trio showdown map grids and the pure helpers the play mode builds on.

Standard library only; loads without the play extra. Sends no input. The data is
brawlfarm/play/data/showdown_maps.json, built by tools/play/maps.py (docs/play-maps.md).
Row 0 is taken as the top of the map; that is unverified (spec Q1).
"""

from __future__ import annotations

import difflib
import functools
import json
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from brawlfarm.play.detect import Box

Cell = tuple[int, int]


class MapsDataError(ValueError):
    """The map data file is missing, unparsable, or not schema 1."""


def fold(text: str) -> str:
    return re.sub(r"[^0-9a-z]", "", text.casefold())


@dataclass(frozen=True)
class ShowdownMap:
    map_id: str
    location: str
    name: str
    tid: str
    theme: str
    grid: tuple[str, ...]
    rows: int
    cols: int
    tiles: Mapping[str, Mapping[str, object]] = field(
        default_factory=dict, repr=False, compare=False, hash=False
    )
    markers: Mapping[str, str] = field(default_factory=dict, repr=False, compare=False, hash=False)

    def tile(self, row: int, col: int) -> str:
        if not (0 <= row < self.rows and 0 <= col < self.cols):
            raise IndexError(f"{self.map_id}: ({row}, {col}) is outside {self.rows}x{self.cols}")
        return self.grid[row][col]

    def _info(self, row: int, col: int) -> Mapping[str, object]:
        return self.tiles.get(self.tile(row, col), {})

    def is_bush(self, row: int, col: int) -> bool:
        return bool(self._info(row, col).get("forest"))

    def is_water(self, row: int, col: int) -> bool:
        return "Water" in str(self._info(row, col).get("name", ""))

    def is_wall(self, row: int, col: int) -> bool:
        return bool(self._info(row, col).get("blocks_movement")) and not self.is_water(row, col)

    def is_open(self, row: int, col: int) -> bool:
        return not (self.is_bush(row, col) or self.is_wall(row, col) or self.is_water(row, col))

    def _cells(self, test) -> frozenset[Cell]:
        return frozenset((r, c) for r in range(self.rows) for c in range(self.cols) if test(r, c))

    def bushes(self) -> frozenset[Cell]:
        return self._cells(self.is_bush)

    def walls(self) -> frozenset[Cell]:
        return self._cells(self.is_wall)

    def water(self) -> frozenset[Cell]:
        return self._cells(self.is_water)

    def open_tiles(self) -> frozenset[Cell]:
        return self._cells(self.is_open)

    def bush_clusters(self) -> tuple[frozenset[Cell], ...]:
        todo, clusters = set(self.bushes()), []
        while todo:
            stack, seen = [min(todo)], set()
            while stack:
                r, c = stack.pop()
                if (r, c) in seen or (r, c) not in todo:
                    continue
                seen.add((r, c))
                stack.extend(((r + 1, c), (r - 1, c), (r, c + 1), (r, c - 1)))
            todo -= seen
            clusters.append(frozenset(seen))
        return tuple(sorted(clusters, key=min))

    def center(self) -> tuple[float, float]:
        return (self.rows / 2, self.cols / 2)

    def spawns(self, kind: str = "trio_spawn") -> tuple[Cell, ...]:
        codes = {code for code, k in self.markers.items() if k == kind}
        return tuple(
            (r, c) for r in range(self.rows) for c in range(self.cols) if self.grid[r][c] in codes
        )

    def boxes(self) -> tuple[Cell, ...]:
        return self.spawns("power_cube_box")


class MapIndex:
    def __init__(self, doc: Mapping) -> None:
        try:
            if doc["schema"] != 1:
                raise MapsDataError(f"schema {doc['schema']!r}, expected 1")
            self.source, self.commit, self.version = (
                str(doc["source"]),
                str(doc["commit"]),
                str(doc["version"]),
            )
            tiles, markers = dict(doc["tiles"]), dict(doc["markers"])
            self._by_id = {
                m["map_id"]: ShowdownMap(
                    m["map_id"],
                    m["location"],
                    m["name"],
                    m["tid"],
                    m["theme"],
                    tuple(m["grid"]),
                    int(m["rows"]),
                    int(m["cols"]),
                    tiles,
                    markers,
                )
                for m in doc["maps"]
            }
            self._names = {str(n): [self._by_id[i] for i in ids] for n, ids in doc["names"].items()}
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            if isinstance(exc, MapsDataError):
                raise
            raise MapsDataError(f"bad map data: {exc!r}") from exc
        self._folded = {fold(n): n for n in self._names}

    def names(self) -> list[str]:
        return sorted(self._names)

    def variants(self, name: str) -> list[ShowdownMap]:
        real = self._folded.get(fold(name or ""))
        return list(self._names[real]) if real else []

    def by_name(self, name: str) -> ShowdownMap | None:
        found = self.variants(name)
        return found[0] if found else None

    def by_id(self, map_id: str) -> ShowdownMap | None:
        return self._by_id.get(map_id)


@functools.lru_cache(maxsize=8)
def load(path: Path | None = None) -> MapIndex:
    try:
        if path is None:
            text = (resources.files("brawlfarm.play") / "data" / "showdown_maps.json").read_text(
                encoding="utf-8"
            )
        else:
            text = Path(path).read_text(encoding="utf-8")
        doc = json.loads(text)
    except (OSError, ValueError) as exc:
        raise MapsDataError(f"cannot read map data: {exc}") from exc
    if not isinstance(doc, dict):
        raise MapsDataError("map data is not an object")
    return MapIndex(doc)


NAME_MATCH_RATIO = 0.85
MODE_TEXT = "TRIO SHOWDOWN"
TRIO_MODES = frozenset({"trioShowdown"})  # assumed rotation event.mode string (spec Q5)
_UNITS = {"d": 86400, "h": 3600, "m": 60, "s": 1}


def _best(text: str, index: MapIndex) -> tuple[float, str | None]:
    key = fold(text)
    if not key:
        return (0.0, None)
    best = (0.0, None)
    for name in index.names():
        ratio = 1.0 if fold(name) == key else difflib.SequenceMatcher(None, key, fold(name)).ratio()
        if ratio > best[0]:
            best = (ratio, name)
    return best


def match_name(text: str, index: MapIndex) -> str | None:
    ratio, name = _best(text, index)
    return name if ratio >= NAME_MATCH_RATIO else None


def _is_mode_line(line: str) -> bool:
    return difflib.SequenceMatcher(None, fold(line), fold(MODE_TEXT)).ratio() >= NAME_MATCH_RATIO


def parse_refresh(text: str) -> int | None:
    parts = re.findall(r"(\d+)\s*([dhms])(?![a-z])", text or "", flags=re.IGNORECASE)
    return sum(int(n) * _UNITS[u.lower()] for n, u in parts) if parts else None


def current_map_name(
    ocr_lines: Sequence[str] | None,
    rotation: Sequence[Mapping] | None = None,
    index: MapIndex | None = None,
) -> str | None:
    index = index or load()
    lines = [str(line) for line in ocr_lines or ()]
    if any(_is_mode_line(line) for line in lines):
        others = [ln for ln in lines if not _is_mode_line(ln) and parse_refresh(ln) is None]
        ratio, name = max(
            (_best(ln, index) for ln in others), default=(0.0, None), key=lambda b: b[0]
        )
        if name is not None and ratio >= NAME_MATCH_RATIO:
            return name
    if rotation:
        trio = []
        for entry in rotation:
            event = entry.get("event") if isinstance(entry, Mapping) else None
            if isinstance(event, Mapping) and event.get("mode") in TRIO_MODES:
                trio.append(event)
        if len(trio) == 1:
            return match_name(str(trio[0].get("map") or ""), index)
    return None


# Placeholders: every value below is unmeasured. The gas schedule measurement PR (spec
# section 8) measures them from the owner recorder sessions and replaces them in one PR.
GAS_START_S = 20.0  # unmeasured, spec section 8; measured by the gas schedule measurement PR
GAS_END_S = 160.0  # unmeasured, spec section 8; measured by the gas schedule measurement PR
GAS_FINAL_HALF = 3.0  # unmeasured, spec section 8, tiles; measured by the gas schedule PR
BUSH_GAS_MARGIN_TILES = 4.0  # unmeasured, spec section 9; measured by the gas schedule PR


def safe_half_extent(m: ShowdownMap, seconds: float) -> float:
    full = max(m.rows, m.cols) / 2
    if seconds <= GAS_START_S:
        return full
    if seconds >= GAS_END_S:
        return GAS_FINAL_HALF
    frac = (seconds - GAS_START_S) / (GAS_END_S - GAS_START_S)
    return full + (GAS_FINAL_HALF - full) * frac


def in_safe_area(
    m: ShowdownMap, row: float, col: float, seconds: float, margin: float = 0.0
) -> bool:
    cr, cc = m.center()
    return max(abs(row - cr), abs(col - cc)) <= safe_half_extent(m, seconds) - margin


@dataclass(frozen=True)
class BushTarget:
    row: float  # tile units (grid) or frame pixels (frame)
    col: float
    source: Literal["grid", "frame"]
    box: Box | None


def choose_bush(
    m: ShowdownMap | None,
    self_pos: tuple[float, float] | None,
    seconds: float,
    bush_boxes: Sequence[Box] = (),
    margin: float = BUSH_GAS_MARGIN_TILES,
) -> BushTarget | None:
    """Pure: no I/O, no clock, no randomness (spec section 9)."""
    if m is not None and self_pos is not None:
        cr, cc = m.center()
        best = None
        for cluster in m.bush_clusters():
            r = sum(c[0] + 0.5 for c in cluster) / len(cluster)
            c = sum(c[1] + 0.5 for c in cluster) / len(cluster)
            if not in_safe_area(m, r, c, seconds, margin):
                continue
            key = (math.hypot(r - cr, c - cc), math.hypot(r - self_pos[0], c - self_pos[1]), r, c)
            if best is None or key < best:
                best = key
        return None if best is None else BushTarget(best[2], best[3], "grid", None)
    if not bush_boxes:
        return None
    box = max(bush_boxes, key=lambda b: b.w * b.h)
    return BushTarget(box.y + box.h / 2, box.x + box.w / 2, "frame", box)
