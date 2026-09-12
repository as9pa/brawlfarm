"""The owned-brawler roster behind GET and PUT /api/instances/{name}/plan.

The plan editor needs the account's brawlers: the current brawler's trophies for its
progress bar, the next few the plan would farm, and the names its maxed-fallback box
offers. Until now only the worker subprocess called the Brawl Stars API; the supervisor
process had the token and the tag but no code path that used them. This module is that
path, and it is a cache first and a client second.

The official API is rate limited and its token is locked to one IP, so the budget is one
fetch per instance per TTL_S no matter how many panels are open, and two callers racing
share one call through that instance's lock. A fetch that fails keeps the last good list
and reports "unavailable" beside it, because a five-minute-old roster is far more useful
to the editor than an empty one. Neither the token nor the tag is ever logged: the
upstream client puts the requested path in its error message, so only the exception TYPE
reaches the log.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from brawlfarm.core.api import ApiClient

log = logging.getLogger("brawlfarm.api")

TTL_S = 300.0  # five minutes: a roster moves a few trophies per match, not per second


def fetch_player(tag: str, token: str) -> dict:
    """One blocking GET /players/{tag}. The default fetcher; tests inject their own."""
    return ApiClient(token=token).get_player(tag)


def _brawler(raw: object) -> dict | None:
    """One upstream brawler entry as the six fields the editor draws, or None when the
    entry is not one it could draw. The rest of the payload (gadgets, star powers, gears)
    is dropped here rather than in the browser.

    A name and a trophy count are what every consumer reads -- the progress bar, the queue
    preview, the fallback picker -- so an entry missing either is skipped rather than
    passed on as a row of nulls. A malformed entry costs its own line, never the roster.
    """
    if not isinstance(raw, dict) or raw.get("name") is None or raw.get("trophies") is None:
        return None
    return {
        "id": raw.get("id"),
        "name": raw.get("name"),
        "trophies": raw.get("trophies"),
        "highest": raw.get("highestTrophies"),
        "rank": raw.get("rank"),
        "power": raw.get("power"),
    }


@dataclass
class Entry:
    """One instance's cached roster: the last good value, when it was fetched, and the
    lock that stops two requests fetching it twice."""

    brawlers: list[dict] | None = None
    fetched_at: float = 0.0
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class RosterCache:
    """Per-instance owned-brawler lists with a TTL and stale-on-failure.

    `now` and `fetch` are injected so the tests need neither a clock nor a network; the
    app builds the cache with the defaults. One instance lives on app.state.roster for
    the process's lifetime.
    """

    def __init__(
        self,
        *,
        ttl_s: float = TTL_S,
        now: Callable[[], float] = time.monotonic,
        fetch: Callable[[str, str], dict] = fetch_player,
    ) -> None:
        self._ttl_s = ttl_s
        self._now = now
        self._fetch = fetch
        self._entries: dict[str, Entry] = {}

    def _entry(self, name: str) -> Entry:
        """This instance's entry, created on first use. The Entry brings its own lock, so
        the cache holds nothing loop-bound until a request actually asks for a name."""
        entry = self._entries.get(name)
        if entry is None:
            entry = self._entries[name] = Entry()
        return entry

    def cached_names(self) -> list[str]:
        """Every brawler name in every cached roster, once each, in insertion order. The
        icon prewarm is the only caller: it wants something to warm, and this is the only
        list of brawler names the API process has without reading a file."""
        seen: dict[str, None] = {}
        for entry in self._entries.values():
            for brawler in entry.brawlers or []:
                name = brawler.get("name")
                if isinstance(name, str) and name:
                    seen.setdefault(name, None)
        return list(seen)

    async def get(self, name: str, tag: str, token: str) -> tuple[list[dict] | None, str]:
        """This instance's owned brawlers sorted by trophies descending, and a status.

        The status is "ok" when the list is fresh or was just refreshed, "unavailable"
        when anything on the way to a clean list went wrong -- with the previous list, if
        there is one, still returned beside it. A blank token or tag is the route's
        business, not this call's.

        The parse is inside the try with the fetch on purpose: ApiClient._get returns
        whatever the endpoint sent (its type is `dict | list`), so a 200 carrying a JSON
        array must cost this refresh and not 500 the plan route that awaited it.
        """
        entry = self._entry(name)
        async with entry.lock:
            if entry.brawlers is not None and self._now() - entry.fetched_at < self._ttl_s:
                return entry.brawlers, "ok"
            try:
                player = await asyncio.to_thread(self._fetch, tag, token)
                raw = player.get("brawlers") or []
                brawlers = [b for b in map(_brawler, raw) if b is not None]
            except Exception as exc:  # network, auth, rate limit, a shape we did not expect
                # str(exc) can carry the tag and the token, so only the type is logged.
                log.warning("%s: roster fetch failed (%s)", name, type(exc).__name__)
                return entry.brawlers, "unavailable"
            brawlers.sort(key=lambda b: b.get("name") or "")
            brawlers.sort(key=lambda b: b.get("trophies") or 0, reverse=True)
            entry.brawlers = brawlers
            entry.fetched_at = self._now()
            return brawlers, "ok"
