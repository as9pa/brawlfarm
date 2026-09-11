"""The instance's screen, two ways.

GET /api/instances/{name}/screenshot.png is one live adb frame, full size, for the "Full
size" link. A screencap takes about a second and BlueStacks does not enjoy two at once
against the same instance, so each instance has its own asyncio.Lock and the call runs in
a thread. Nothing is cached and the response says so.

GET /api/instances/{name}/preview.jpg is what the Fleet cards and the Instance page poll.
A running worker writes preview.jpg into its own data dir once a second off the frame it
already classified (core/preview.py), so the panel can refresh at that cadence for the
price of reading a 30 kB file. The response carries an ETag, so a poll that arrives
between two worker frames costs a 304 and no body at all. A stopped instance has nobody
writing frames: that falls back to one live screencap, throttled to LIVE_MIN_INTERVAL_S
however fast the page asks, and to the last file the worker left behind if adb is gone
too.
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from email.utils import formatdate
from pathlib import Path

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException, Request, Response

from brawlfarm.api.deps import get_sup, resolve_instance
from brawlfarm.core import preview
from brawlfarm.setup.checks import AdbUnavailable, screencap_png

router = APIRouter()

FRESH_S = 5.0  # a worker writes every second: older than this means nobody is writing
LIVE_MIN_INTERVAL_S = 15.0  # the fallback capture's floor, per instance


@dataclass(frozen=True)
class _LiveFrame:
    """One fallback capture, kept per instance so a fast poll never repeats it."""

    jpeg: bytes
    etag: str
    at_wall: float  # for Last-Modified
    at_monotonic: float  # for the throttle, which must not care about clock changes


def _lock_for(request: Request, name: str) -> asyncio.Lock:
    """One lock per instance, created on first use so it binds to the running loop."""
    locks = request.app.state.screenshot_locks
    lock = locks.get(name)
    if lock is None:
        lock = locks[name] = asyncio.Lock()
    return lock


@router.get("/api/instances/{name}/screenshot.png")
async def screenshot(request: Request, name: str) -> Response:
    """The instance's screen right now, or 503 with one line saying why adb could not."""
    inst, _dir = resolve_instance(request, name)
    adb_path = get_sup(request).settings.connection.adb_path
    async with _lock_for(request, inst.name):
        try:
            png = await asyncio.to_thread(screencap_png, adb_path, inst.adb_port)
        except AdbUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
    return Response(content=png, media_type="image/png", headers={"Cache-Control": "no-store"})


@router.get("/api/instances/{name}/preview.jpg")
async def preview_jpg(request: Request, name: str) -> Response:
    """The worker's latest frame, a throttled live one when no worker is running, or 503."""
    inst, inst_dir = resolve_instance(request, name)
    on_disk = await asyncio.to_thread(_read_file, inst_dir / preview.PREVIEW_NAME)
    if on_disk is not None:
        jpeg, at_wall, etag = on_disk
        if time.time() - at_wall <= FRESH_S:
            return _send(request, jpeg, etag, at_wall, "worker")

    cached = _cached(request, inst.name)
    if cached is not None:
        return _send(request, cached.jpeg, cached.etag, cached.at_wall, "live")

    adb_path = get_sup(request).settings.connection.adb_path
    async with _lock_for(request, inst.name):
        # Requests that queued on the lock take the frame the winner just captured.
        cached = _cached(request, inst.name)
        if cached is not None:
            return _send(request, cached.jpeg, cached.etag, cached.at_wall, "live")
        try:
            png = await asyncio.to_thread(screencap_png, adb_path, inst.adb_port)
        except AdbUnavailable as exc:
            if on_disk is not None:
                jpeg, at_wall, etag = on_disk
                return _send(request, jpeg, etag, at_wall, "stale")
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        jpeg = await asyncio.to_thread(_shrink, png)
        at_wall = time.time()
        cached = _LiveFrame(jpeg, f'"live-{time.time_ns()}"', at_wall, time.monotonic())
        request.app.state.preview_cache[inst.name] = cached
    return _send(request, cached.jpeg, cached.etag, cached.at_wall, "live")


def _read_file(path: Path) -> tuple[bytes, float, str] | None:
    """The file's bytes, its mtime and its ETag, or None if it is not there.

    Statted through the open handle, never by path: the worker replaces this file every
    second, so a separate stat() could describe a frame other than the bytes we read.
    """
    try:
        with path.open("rb") as handle:
            data = handle.read()
            st = os.fstat(handle.fileno())
    except OSError:
        return None
    return data, st.st_mtime, f'"{st.st_mtime_ns}-{st.st_size}"'


def _shrink(png: bytes) -> bytes:
    """A full-size adb PNG as a preview JPEG, the same size the worker writes."""
    frame = cv2.imdecode(np.frombuffer(png, dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(status_code=503, detail="the screenshot could not be decoded")
    return preview.encode(frame)


def _cached(request: Request, name: str) -> _LiveFrame | None:
    """This instance's fallback frame while it is still inside the throttle window."""
    frame = request.app.state.preview_cache.get(name)
    if frame is None or time.monotonic() - frame.at_monotonic >= LIVE_MIN_INTERVAL_S:
        return None
    return frame


def _send(request: Request, jpeg: bytes, etag: str, at_wall: float, source: str) -> Response:
    """The frame, or 304 when the browser already holds this exact one."""
    headers = {
        "ETag": etag,
        "Last-Modified": formatdate(at_wall, usegmt=True),
        "Cache-Control": "no-cache",
        "X-Preview-Source": source,
    }
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return Response(content=jpeg, media_type="image/jpeg", headers=headers)
