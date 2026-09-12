"""Event captures: the always-on PNG of a notable event (recover/disconnect/stuck), with
a cap on how many are kept and how often one reason may write.

WHY: the controller wrote a full 1600x900 frame on EVERY notable event, uncapped. A
recovery loop that fires a few times a second turned that into ~80 MB an hour of
near-identical screenshots -- all of them useless, because the first one already showed
the screen the bot was stuck on. So:

  - at most one frame per tag per EVENT_MIN_INTERVAL_S (10 minutes), which keeps the
    first frame of a novel event and drops the repeats, and
  - at most EVENT_CAP (100) frames in the folder, oldest by mtime pruned after a write.

Best-effort in the strongest sense (same contract as preview.py): this runs in the
farm's hot path, so every failure -- mkdir, imwrite, a stat or unlink losing a race with
the owner's file explorer -- returns False and is reported at most once a minute. The
captured frame is only ever read, never modified.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import cv2

from brawlfarm.core import config

EVENT_CAP = 100  # frames kept in captures/events; oldest by mtime go first
EVENT_MIN_INTERVAL_S = 600.0  # one frame per tag per 10 minutes
WARN_INTERVAL_S = 60.0

log = logging.getLogger("brawlfarm.core.captures")

# Monotonic stamp of the last frame written for each tag, and of the last complaint.
# -inf so the very first call always writes, whatever the clock happens to read.
_last_by_tag: dict[str, float] = {}
_last_warn = float("-inf")


def write_event(screen, tag: str, *, now: float | None = None) -> bool:
    """Snapshot a notable event, unless this tag already wrote inside the interval.

    True when a frame landed on disk. Never raises: the farm keeps farming whatever the
    filesystem is doing.
    """
    at = time.monotonic() if now is None else now
    last = _last_by_tag.get(tag)
    if last is not None and at - last < EVENT_MIN_INTERVAL_S:
        return False
    try:
        # CAPTURES_DIR at call time, never at import: set_home() re-points it.
        d = config.CAPTURES_DIR / "events"
        d.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%H%M%S")
        if not cv2.imwrite(str(d / f"{ts}_{tag}.png"), screen):
            _warn(at, "cv2 could not write the frame")
            return False
    except Exception as exc:
        _warn(at, exc)
        return False
    _last_by_tag[tag] = at
    _prune(d, at)
    return True


def reset() -> None:
    """Forget every tag's stamp (and the complaint cooldown), so a test starts clean."""
    global _last_warn
    _last_by_tag.clear()
    _last_warn = float("-inf")


def _prune(d: Path, at: float) -> None:
    """Unlink oldest-first until at most EVENT_CAP frames remain. mtime, not filename:
    the name is only <HHMMSS>, so it says nothing about which day a frame is from."""
    try:
        shots = sorted(d.glob("*.png"), key=lambda p: p.stat().st_mtime)
    except OSError as exc:  # a frame vanished mid-listing, or the folder went away
        _warn(at, exc)
        return
    for old in shots[: len(shots) - EVENT_CAP]:
        try:
            old.unlink()
        except OSError as exc:  # someone has it open; the next write tries again
            _warn(at, exc)


def _warn(at: float, why: object) -> None:
    """One line a minute at most, and the reason only -- an OSError's str carries the full
    filename, and this line can end up in a log the owner shares."""
    global _last_warn
    if at - _last_warn < WARN_INTERVAL_S:
        return
    _last_warn = at
    log.warning("event capture not written: %s", getattr(why, "strerror", None) or why)
