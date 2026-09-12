"""Calibration overrides read from <home>/calibration/calibration.toml.

The file is flat TOML. Keys are the names of overridable constants in
brawlfarm.core.config: floats (timings and thresholds) and two-int tuples
(tap coordinates). Nothing here writes the file; the app only reads it.
This module imports only the standard library and never imports config.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Group = Literal["tap", "threshold", "timing"]

LOCKED: frozenset[str] = frozenset({"SCREEN_W", "SCREEN_H", "SCREEN_DPI"})

_DEFAULTS: dict[str, object] = {}


@dataclass(frozen=True)
class Report:
    path: Path
    present: bool
    mtime_ns: int | None
    applied: dict[str, object]
    problems: tuple[str, ...]
    defaults: dict[str, object]


def _is_tap(value: object) -> bool:
    return (
        isinstance(value, tuple)
        and len(value) == 2
        and all(isinstance(v, int) and not isinstance(v, bool) for v in value)
    )


def _is_float(value: object) -> bool:
    return isinstance(value, float)


def overridable(ns: Mapping[str, object]) -> dict[str, object]:
    """Names in ns that calibration.toml may override, with their values."""
    out: dict[str, object] = {}
    for name, value in ns.items():
        if not name.isupper() or name.startswith("_") or name in LOCKED:
            continue
        if _is_tap(value) or _is_float(value):
            out[name] = value
    return out


def group_of(name: str, value: object) -> Group:
    if _is_tap(value):
        return "tap"
    if name.endswith("_THRESHOLD"):
        return "threshold"
    return "timing"


def _coerce(name: str, default: object, raw: object) -> tuple[object | None, str | None]:
    if _is_tap(default):
        if (
            isinstance(raw, list)
            and len(raw) == 2
            and all(isinstance(v, int) and not isinstance(v, bool) for v in raw)
        ):
            return (raw[0], raw[1]), None
        return None, f"{name} must be two integers."
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return None, f"{name} must be a number."
    return float(raw), None


def apply(ns: dict[str, object], path: Path) -> Report:
    """Restore defaults for every overridable name, then apply the file over them."""
    if not _DEFAULTS:
        _DEFAULTS.update(overridable(ns))
    for name, value in _DEFAULTS.items():
        ns[name] = value
    defaults = dict(_DEFAULTS)

    if not path.is_file():
        return Report(path, False, None, {}, (), defaults)
    try:
        mtime_ns = path.stat().st_mtime_ns
        with path.open("rb") as fh:
            data = tomllib.load(fh)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return Report(
            path, True, None, {}, (f"calibration.toml could not be read: {exc}",), defaults
        )

    applied: dict[str, object] = {}
    problems: list[str] = []
    for name in sorted(data):
        raw = data[name]
        if name not in defaults:
            problems.append(f"{name} is not a calibration constant. The line is ignored.")
            continue
        value, problem = _coerce(name, defaults[name], raw)
        if problem is not None:
            problems.append(problem)
            continue
        ns[name] = value
        applied[name] = value
    return Report(path, True, mtime_ns, applied, tuple(problems), defaults)


def changed_since(report: Report) -> bool:
    """True when the file's presence or mtime differs from what report saw."""
    try:
        current: int | None = report.path.stat().st_mtime_ns
    except OSError:
        current = None
    return current != report.mtime_ns
