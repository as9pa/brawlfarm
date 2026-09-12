"""The brawler catalog and the local icon cache.

Pure functions with no FastAPI in sight, so the logic is testable without a client and
the route in api/brawlers.py stays twenty lines of HTTP. Two caches live under the data
directory and nowhere else:

  <home>/cache/brawlers.json      {UPPERCASED NAME: id}, written atomically
  <home>/cache/brawlers/<id>.png  one file per brawler, written temp-then-replace

Names are matched upper-cased and stripped because games.csv stores the official API's
names and the plan queue stores the same. The path of a cached icon is built from the
integer id and NEVER from the name, so nothing a browser sends reaches the filesystem.

Only the API process imports this module. No worker, and nothing under core/controller.py,
core/states.py or core/vision.py, ever talks to the CDN.

The token reaches ApiClient and nothing else: it is never logged, never put in a URL and
never returned. Only the exception type and, for the CDN, the HTTP status are logged.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from collections.abc import Callable
from pathlib import Path

import requests

from brawlfarm.core import jsonio
from brawlfarm.core.api import ApiClient

log = logging.getLogger("brawlfarm.api")

CDN_URL = "https://cdn.brawlify.com/brawlers/borderless/{id}.png"
MAX_AGE_S = 604800  # one week, the Cache-Control the route sends
REFRESH_S = 3600.0  # at most one catalog refresh an hour
BRAWLER_NAME_RE = re.compile(r"^[A-Za-z0-9 .'&_-]{1,32}$")
FETCH_TIMEOUT_S = 10.0
MAX_ICON_BYTES = 512 * 1024
PREWARM_SLEEP_S = 0.1
# setup/checks.py has its own copy of this signature for its own screenshot check; core
# must not import brawlfarm.setup, so the eight bytes are spelled out again rather than
# inverting the layering for them.
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

# When the catalog was last refreshed, successfully or not. Module level on purpose: a run
# of unknown names costs one call an hour for the process, not one call each.
_last_refresh_at: float | None = None


class IconUnavailable(RuntimeError):
    """The CDN answered, but not with an icon. `status` is its HTTP status, which is the
    only part of that answer worth logging."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


def catalog_path(home: Path) -> Path:
    """<home>/cache/brawlers.json."""
    return Path(home) / "cache" / "brawlers.json"


def icon_path(home: Path, brawler_id: int) -> Path:
    """<home>/cache/brawlers/<id>.png. Built from the integer id, never from a name."""
    return Path(home) / "cache" / "brawlers" / f"{int(brawler_id)}.png"


def load_catalog(home: Path) -> dict[str, int]:
    """The stored {UPPERCASED NAME: id} map. A missing, unreadable or malformed file is an
    empty catalog: a cache that cannot be read costs one refresh, never an exception.

    Read with json.loads rather than through jsonio, which owns the atomic WRITE and has
    no reader of its own.
    """
    try:
        raw = json.loads(catalog_path(home).read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return {str(k): int(v) for k, v in raw.items() if isinstance(v, int)}


def fetch_brawlers(token: str) -> list[dict]:
    """One blocking GET /brawlers. The default fetcher; tests inject their own."""
    return ApiClient(token=token).get_brawlers()


def fetch_icon_bytes(url: str) -> bytes:
    """One blocking GET of a CDN icon. Raises IconUnavailable on a non-200 so the caller
    can log the status without touching the body."""
    resp = requests.get(url, timeout=FETCH_TIMEOUT_S)
    if resp.status_code != 200:
        raise IconUnavailable("the CDN did not serve an icon", resp.status_code)
    return resp.content


def resolve_id(
    home: Path,
    name: str,
    token: str,
    *,
    now: Callable[[], float] = time.monotonic,
    fetch: Callable[[str], list[dict]] = fetch_brawlers,
) -> int | None:
    """This brawler's numeric id, or None.

    The cached catalog answers first. Only a miss refreshes, and only when REFRESH_S has
    passed since the last refresh ATTEMPT, success or failure. A blank token, a fetch that
    raises and a fetch that brings back nothing usable are all misses that leave the file
    on disk exactly as it was.
    """
    global _last_refresh_at
    key = name.strip().upper()
    if not key:
        return None
    found = load_catalog(home).get(key)
    if found is not None:
        return found
    if not token.strip():
        return None
    stamp = now()
    if _last_refresh_at is not None and stamp - _last_refresh_at < REFRESH_S:
        return None
    _last_refresh_at = stamp
    try:
        items = fetch(token)
    except Exception as exc:  # network, auth, rate limit, a shape we did not expect
        # str(exc) can carry the requested path and the token, so only the type is logged.
        log.warning("brawler catalog refresh failed (%s)", type(exc).__name__)
        return None
    fresh: dict[str, int] = {}
    for item in items or []:
        if not isinstance(item, dict):
            continue
        raw_name, raw_id = item.get("name"), item.get("id")
        if isinstance(raw_name, str) and isinstance(raw_id, int):
            fresh[raw_name.strip().upper()] = raw_id
    if not fresh:
        return None
    try:
        jsonio.atomic_write_json(catalog_path(home), fresh)
    except OSError as exc:
        log.warning("brawler catalog write failed (%s)", type(exc).__name__)
    return fresh.get(key)


def ensure_icon(
    home: Path,
    brawler_id: int,
    fetch: Callable[[str], bytes] = fetch_icon_bytes,
) -> bytes | None:
    """This brawler's PNG bytes, from disk when they are there and from the CDN otherwise.

    A fetched body is written temp-then-replace inside the cache folder, so a torn download
    never becomes a cached icon. A non-200, a timeout, a body that is not a PNG and a body
    over MAX_ICON_BYTES all return None and write nothing.
    """
    path = icon_path(home, brawler_id)
    try:
        return path.read_bytes()
    except OSError:
        pass  # not cached yet, or unreadable: either way, fetch it
    try:
        body = fetch(CDN_URL.format(id=int(brawler_id)))
    except IconUnavailable as exc:
        log.warning("brawler icon fetch failed (HTTP %s)", exc.status)
        return None
    except Exception as exc:
        log.warning("brawler icon fetch failed (%s)", type(exc).__name__)
        return None
    if not body or not body.startswith(PNG_MAGIC) or len(body) > MAX_ICON_BYTES:
        log.warning("brawler icon rejected (%d bytes)", len(body or b""))
        return None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_bytes(body)
        os.replace(tmp, path)
    except OSError as exc:  # an uncacheable icon is still a servable icon
        log.warning("brawler icon write failed (%s)", type(exc).__name__)
    return body
