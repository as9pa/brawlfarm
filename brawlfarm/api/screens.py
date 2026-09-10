"""GET /api/instances/{name}/screenshot.png: one live adb frame for the Fleet thumbnail
and the Instance screen.

A screencap takes about a second and BlueStacks does not enjoy two at once against the
same instance, so each instance has its own asyncio.Lock and the call runs in a thread.
Nothing is cached and the response says so: the browser asks again when it wants a newer
frame (the UI refreshes every 15 s while the tab is visible).
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Request, Response

from brawlfarm.api.deps import get_sup, resolve_instance
from brawlfarm.setup.checks import AdbUnavailable, screencap_png

router = APIRouter()


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
