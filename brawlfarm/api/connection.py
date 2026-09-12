"""GET /api/connection/check: does the Brawl Stars token work right now.

Five words, and only three of them cost anything. "no_token" and "no_tag" are read off
config.toml, so a panel with nothing configured never touches the network. The other
three come from one GET /players/{tag}, at most once every TTL_S, behind one lock, so two
open panels share one call.

credential_status is shared with plans.py, which is why it lives here rather than inline:
the plan route's four statuses and this route's five must agree about the first two.

Nothing here echoes, logs or returns the token or the tag. ApiError's message embeds the
requested path and therefore the tag, so only ApiError.status is read and only the
exception type reaches the log.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from datetime import datetime

from fastapi import APIRouter, Request

from brawlfarm.api.deps import get_sup
from brawlfarm.api.roster import fetch_player
from brawlfarm.core.api import ApiError

log = logging.getLogger("brawlfarm.api")
router = APIRouter()

TTL_S = 300.0  # five minutes, the same budget roster.py spends
STATUSES = ("ok", "no_token", "no_tag", "rejected", "unreachable")
REJECTING_STATUSES = frozenset({401, 403})


def credential_status(token: str, tag: str) -> str | None:
    """ "no_token", "no_tag", or None when both are present. plans.py imports this."""
    if not token.strip():
        return "no_token"
    if not tag.strip():
        return "no_tag"
    return None


class ConnectionCache:
    """One process-wide answer about the token, with a TTL and one lock.

    `now`, `clock` and `fetch` are injected so the tests need neither a clock nor a
    network; the app builds the cache with the defaults and keeps it on app.state for the
    process's lifetime.
    """

    def __init__(
        self,
        *,
        ttl_s: float = TTL_S,
        now: Callable[[], float] = time.monotonic,
        clock: Callable[[], datetime] = datetime.now,
        fetch: Callable[[str, str], dict] = fetch_player,
    ) -> None:
        self._ttl_s = ttl_s
        self._now = now
        self._clock = clock
        self._fetch = fetch
        self._status: str | None = None
        self._checked_at = ""
        self._fetched_at = 0.0
        self._lock: asyncio.Lock | None = None

    def _get_lock(self) -> asyncio.Lock:
        """Built on first use, so the cache holds nothing loop-bound until a request asks
        for it and a second app in the same process gets its own loop's lock."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def get(self, token: str, tag: str) -> tuple[str, str]:
        """(status, checked_at) for these credentials, fetched at most once per TTL_S.

        401 and 403 are "rejected": the token is wrong, or the IP it was made for is not
        this one. Everything else, including a connection error, a timeout and a 5xx, is
        "unreachable", because the difference does not change what the reader should do.
        """
        async with self._get_lock():
            if self._status is not None and self._now() - self._fetched_at < self._ttl_s:
                return self._status, self._checked_at
            try:
                await asyncio.to_thread(self._fetch, tag, token)
                status = "ok"
            except ApiError as exc:
                status = "rejected" if exc.status in REJECTING_STATUSES else "unreachable"
                log.warning("connection check failed (ApiError, HTTP %s)", exc.status)
            except Exception as exc:  # network, timeout, a shape we did not expect
                # str(exc) can carry the tag and the token, so only the type is logged.
                status = "unreachable"
                log.warning("connection check failed (%s)", type(exc).__name__)
            self._status = status
            self._fetched_at = self._now()
            self._checked_at = self._clock().isoformat(timespec="seconds")
            return status, self._checked_at


@router.get("/api/connection/check")
async def check_connection(request: Request) -> dict:
    """Whether the Brawl Stars API is answering for this install, and when that was last
    established. Always 200: this route reports a failure, it does not have one."""
    sup = get_sup(request)
    token = sup.settings.connection.brawl_api_token
    tag = next((i.player_tag for i in sup.settings.instances if i.player_tag.strip()), "")
    early = credential_status(token, tag)
    if early is not None:
        return {"status": early, "checked_at": datetime.now().isoformat(timespec="seconds")}
    status, checked_at = await request.app.state.connection.get(token.strip(), tag.strip())
    return {"status": status, "checked_at": checked_at}
