"""The worker's preview frame: a small JPEG written from the frame the main loop already
captured, so the control panel can watch an instance without a second adb screencap.

The loop classifies a fresh 1600x900 frame every few hundred milliseconds. Once a second
that same array is scaled to half size, JPEG-encoded and written ATOMICALLY (temp file +
``os.replace``) into the instance's data dir, next to status.json -- the folder the API
already knows as ``instance_dir(home, name)``.

Best-effort in the strongest sense: this runs in the farm's hot path, so every failure
(encode, mkdir, full disk, a reader holding the file open on Windows) returns False and
is reported at most once a minute. The captured frame is only ever read, never modified.
"""

from __future__ import annotations

import logging
import os
import time

import cv2

from brawlfarm.core import config

PREVIEW_INTERVAL_S = 1.0  # one frame a second is plenty for a human watching a card
PREVIEW_SIZE = (800, 450)  # width, height: half of the locked 1600x900
PREVIEW_JPEG_QUALITY = 70
PREVIEW_NAME = "preview.jpg"
WARN_INTERVAL_S = 60.0

log = logging.getLogger("brawlfarm.core.preview")

# Monotonic stamps of the last attempt and the last complaint. -inf so the very first
# call always writes, whatever the clock happens to read.
_last_write = float("-inf")
_last_warn = float("-inf")


def encode(screen, *, full: bool = False) -> bytes:
    """``screen`` JPEG-encoded, scaled to PREVIEW_SIZE unless ``full`` is set. Raises if cv2
    cannot encode it.

    INTER_AREA is the right filter for shrinking: it averages the pixels it drops, so the
    game's thin UI text stays readable at half size instead of aliasing into noise.

    ``full`` skips the resize and encodes the frame at its native size, same quality. That
    is what an observe recording wants: a template crop has to come off a 1600x900 frame.
    """
    frame = screen if full else cv2.resize(screen, PREVIEW_SIZE, interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), PREVIEW_JPEG_QUALITY])
    if not ok:
        raise ValueError("cv2 could not encode the preview frame")
    return bytes(buf)


def maybe_write(screen, *, now: float | None = None) -> bool:
    """Write the preview frame unless the last attempt was under PREVIEW_INTERVAL_S ago.

    True when a frame landed on disk. Never raises: the farm keeps farming whatever the
    filesystem is doing.
    """
    global _last_write
    at = time.monotonic() if now is None else now
    if at - _last_write < PREVIEW_INTERVAL_S:
        return False
    # Stamp the ATTEMPT, not the success: a folder that keeps refusing must cost one
    # resize a second, not one on every iteration of the loop.
    _last_write = at
    try:
        data = encode(screen)
        # DATA_DIR at call time, never at import: set_home() re-points it.
        path = config.DATA_DIR / PREVIEW_NAME
        tmp = path.with_name(path.name + ".tmp")
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_bytes(data)
        os.replace(tmp, path)  # same directory, so atomic on Windows too
    except Exception as exc:
        _warn(at, exc)
        return False
    return True


def _warn(at: float, exc: BaseException) -> None:
    """One line a minute at most, and the reason only -- an OSError's str carries the full
    filename, and this line can end up in a log the owner shares."""
    global _last_warn
    if at - _last_warn < WARN_INTERVAL_S:
        return
    _last_warn = at
    log.warning("preview frame not written: %s", getattr(exc, "strerror", None) or exc)
