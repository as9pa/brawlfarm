"""GET /api/brawlers/{name}/icon.png, and the start-up prewarm behind it.

Twenty lines of HTTP around core/icons.py. The name is checked against BRAWLER_NAME_RE
before anything touches the filesystem, and the cached path is built from the integer id
the catalog gave back, so nothing a browser sends becomes a path segment.

Every miss is the same 404 with the same detail: telling a bad token apart from a bad name
only helps someone probing. Both blocking calls run through asyncio.to_thread, and one
asyncio.Lock per id (the shape RosterCache.Entry already uses) means eight rows asking for
the same new brawler cost one CDN request.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from collections.abc import Callable, Iterable
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response

from brawlfarm.api.deps import get_home, get_sup
from brawlfarm.core import icons

log = logging.getLogger("brawlfarm.api")
router = APIRouter()

NOT_FOUND = "no icon"

# One lock per brawler id, filled lazily: the router holds nothing loop-bound until a
# request actually asks for an id.
_locks: dict[int, asyncio.Lock] = {}
# The prewarm runs at most once per process, whatever restarts the lifespan.
_prewarmed = False


def _lock(brawler_id: int) -> asyncio.Lock:
    lock = _locks.get(brawler_id)
    if lock is None:
        lock = _locks[brawler_id] = asyncio.Lock()
    return lock


def _etag(body: bytes) -> str:
    """The first 16 hex characters of the body's sha256, quoted as an ETag must be."""
    return f'"{hashlib.sha256(body).hexdigest()[:16]}"'


@router.get("/api/brawlers/{name}/icon.png")
async def get_brawler_icon(request: Request, name: str) -> Response:
    """This brawler's 200 PNG with a week of Cache-Control, a 304 when the browser already
    has it, or 404 "no icon" for every kind of miss."""
    if not icons.BRAWLER_NAME_RE.match(name):
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    home = get_home(request)
    token = get_sup(request).settings.connection.brawl_api_token
    brawler_id = await asyncio.to_thread(icons.resolve_id, home, name, token)
    if brawler_id is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    async with _lock(brawler_id):
        body = await asyncio.to_thread(icons.ensure_icon, home, brawler_id)
    if body is None:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    etag = _etag(body)
    headers = {"Cache-Control": f"public, max-age={icons.MAX_AGE_S}", "ETag": etag}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return Response(content=body, media_type="image/png", headers=headers)


def prewarm(
    home: Path,
    token: str,
    names: Iterable[str],
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Fetch the icons for `names` that have no file on disk yet, and say how many landed.

    Blocking, and started without being awaited, so start-up never waits on the CDN. It
    runs at most once per process, is skipped entirely when the token is blank, resolves
    the catalog once through resolve_id's own cache, sleeps between fetches and swallows
    every failure: a cold CDN must never stop the panel from serving.
    """
    global _prewarmed
    if _prewarmed:
        return 0
    _prewarmed = True
    if not token.strip():
        return 0
    warmed = 0
    for name in dict.fromkeys(names):
        try:
            brawler_id = icons.resolve_id(home, name, token)
            if brawler_id is None or icons.icon_path(home, brawler_id).exists():
                continue
            if icons.ensure_icon(home, brawler_id) is not None:
                warmed += 1
        except Exception as exc:  # one bad name must not end the pass
            log.warning("icon prewarm skipped one brawler (%s)", type(exc).__name__)
            continue
        sleep(icons.PREWARM_SLEEP_S)
    return warmed
