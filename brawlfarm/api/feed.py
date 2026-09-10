"""The activity feed: the worker's session narration turned into something a screen can
show (spec section 7, Instance screen).

The worker appends one JSON object per line to `<instance dir>/session-<ts>.jsonl`
(core/datalog.py): `{"ts": ..., "kind": <event kind>, **fields}`. Two readers live here.
`read_feed` serves history on demand for GET .../feed; `FeedTailer` follows the newest
file and publishes each new line onto the event bus, so the panel's feed scrolls without
polling. Both drop `tap` (one line per tap) and label everything else with the chip it
belongs under: All, Matches, Interrupts, Errors.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Query, Request

from brawlfarm import settings as S
from brawlfarm.api.deps import resolve_instance

log = logging.getLogger("brawlfarm.api")
router = APIRouter()

# Kinds are the etypes core/controller.py passes to DataLog.event(); see that file for the
# full inventory. Anything unlisted is "other" and shows under All only, so a new event
# kind in the core is never silently invisible.
MATCHES = frozenset(
    {"phase", "games_logged", "recap", "trophies", "farming", "select_brawler", "rotate_brawler"}
)
INTERRUPTS = frozenset(
    {
        "disconnect",
        "popup_close",
        "team_invite_decline",
        "daily_streak_claim",
        "ceremony_cleared",
        "recover",
        "recover_dismissed",
        "game_left_foreground",
        "wrong_mode",
        "reselect_brawler",
        "gas_relocate",
        "bush_hide",
        "ingame_modal_cleared",
        "skin_reward",
    }
)
ERRORS = frozenset({"crash", "bad_resolution", "recalibrate"})
DROP = frozenset({"tap", "gas_edges"})  # per-tap noise, never worth a feed line

KINDS = ("all", "matches", "interrupts", "errors")
FeedKind = Literal["all", "matches", "interrupts", "errors"]

MAX_LIMIT = 1000
TAIL_INTERVAL_S = 2.0


def classify(kind: str) -> str | None:
    """The chip a session event belongs under, or None when it is dropped. `_error` is
    checked first so select_brawler_error lands in Errors, not Matches."""
    if kind in DROP:
        return None
    if kind.endswith("_error") or kind in ERRORS:
        return "errors"
    if kind in MATCHES:
        return "matches"
    if kind in INTERRUPTS:
        return "interrupts"
    return "other"


def to_record(line: dict) -> dict | None:
    """One session line as a feed record, or None when the kind is dropped. `kind` is
    renamed to `event` because the screen's filter is also called kind."""
    kind = str(line.get("kind") or "")
    if not kind:
        return None
    category = classify(kind)
    if category is None:
        return None
    fields = {k: v for k, v in line.items() if k not in ("ts", "kind")}
    return {"ts": str(line.get("ts") or ""), "event": kind, "category": category, "fields": fields}


def latest_session(inst_dir: Path) -> Path | None:
    """The newest session-<ts>.jsonl. The worker's timestamp is %Y%m%d-%H%M%S, so the name
    sorts chronologically and no stat() call is needed."""
    try:
        files = sorted(Path(inst_dir).glob("session-*.jsonl"))
    except OSError:
        return None
    return files[-1] if files else None


def read_session(path: Path, *, kind: str = "all", limit: int = 100) -> list[dict]:
    """Feed records from one session file, newest last, at most `limit` of them.
    Unparsable lines are skipped: a half-written tail must not empty the screen."""
    if kind not in KINDS:
        raise ValueError(f"unknown feed kind {kind!r}")
    limit = max(1, min(int(limit), MAX_LIMIT))
    records: list[dict] = []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for raw in f:
                try:
                    line = json.loads(raw)
                except ValueError:
                    continue
                if not isinstance(line, dict):
                    continue
                record = to_record(line)
                if record is None or (kind != "all" and record["category"] != kind):
                    continue
                records.append(record)
    except OSError as exc:
        log.debug("cannot read %s: %s", path, exc)
        return []
    return records[-limit:]


def read_feed(inst_dir: Path, kind: str = "all", limit: int = 100) -> list[dict]:
    """The newest session's feed records. Only the newest file is read: the screen shows
    "this session", and older files are for the stats page."""
    path = latest_session(Path(inst_dir))
    return [] if path is None else read_session(path, kind=kind, limit=limit)


def _feed_payload(inst_dir: Path, kind: str, limit: int) -> dict:
    """Name and records resolved from one lookup, so a session roll between them cannot
    label one file's records with another file's name. Blocking; call it in a thread."""
    path = latest_session(inst_dir)
    return {
        "session": path.name if path is not None else None,
        "records": [] if path is None else read_session(path, kind=kind, limit=limit),
    }


class FeedTailer:
    """Follows every instance's newest session file and publishes new lines onto the bus as
    kind "feed" (`{"instance": name, "record": <feed record>}`).

    On its first look at an instance it seeks to the END of the session already in progress
    (ruling 4): a supervisor restart must not replay a whole night onto the panel, and
    GET .../feed still serves that history on demand. A file that appears or rolls later is
    read from the top. Every parsed line -- dropped kinds included -- is offered to the
    alert store, because `tap` is noise on a screen but `crash` is not.
    """

    def __init__(self, home, sup, bus, alerts=None, interval_s: float = TAIL_INTERVAL_S) -> None:
        self.home = Path(home)
        self.interval_s = interval_s
        self._sup = sup
        self._bus = bus
        self._alerts = alerts
        self._positions: dict[str, tuple[Path, int]] = {}
        self._seen: set[str] = set()

    async def run(self) -> None:
        """Poll until cancelled (the lifespan cancels it on shutdown)."""
        while True:
            await self.poll_once()
            await asyncio.sleep(self.interval_s)

    async def poll_once(self) -> int:
        """One pass over every configured instance; returns how many feed events it
        published. The tests call this instead of run(). File reads happen in a thread; the
        publishing happens here on the loop thread."""
        published = 0
        for inst in self._sup.settings.instances:
            name = inst.name
            try:
                lines = await asyncio.to_thread(self._read_new, name)
            except Exception:  # one unreadable folder must never kill the tailer
                log.exception("%s: feed tail failed", name)
                continue
            for line in lines:
                if self._alerts is not None:
                    self._alerts.ingest(name, line)
                record = to_record(line)
                if record is None:
                    continue
                self._bus.publish("feed", {"instance": name, "record": record})
                published += 1
        return published

    def _read_new(self, name: str) -> list[dict]:
        """Blocking: the session lines written since the last poll. Offsets are counted in
        bytes on a binary handle because text-mode tell() is not allowed while iterating."""
        inst_dir = S.instance_dir(self.home, name)
        path = latest_session(inst_dir)
        first_look = name not in self._seen
        self._seen.add(name)
        if path is None:
            self._positions.pop(name, None)
            return []
        known, offset = self._positions.get(name, (None, 0))
        if known != path:
            offset = path.stat().st_size if first_look else 0
        lines: list[dict] = []
        try:
            with path.open("rb") as f:
                f.seek(0, 2)
                if f.tell() < offset:  # replaced or truncated under us
                    offset = 0
                f.seek(offset)
                for raw in f:
                    if not raw.endswith(b"\n"):
                        break  # a half-written line; the next poll picks it up whole
                    offset += len(raw)
                    try:
                        line = json.loads(raw.decode("utf-8"))
                    except (ValueError, UnicodeDecodeError):
                        continue
                    if isinstance(line, dict):
                        lines.append(line)
        except OSError as exc:
            log.debug("%s: cannot read %s: %s", name, path.name, exc)
            return []
        self._positions[name] = (path, offset)
        return lines


@router.get("/api/instances/{name}/feed")
async def get_feed(
    request: Request,
    name: str,
    kind: FeedKind = "all",
    limit: int = Query(100, ge=1, le=MAX_LIMIT),
) -> dict:
    """This instance's newest session narration, newest last. An unknown kind or a limit
    outside 1..1000 is a 422; an unknown instance is a 404."""
    _inst, inst_dir = resolve_instance(request, name)
    return await asyncio.to_thread(_feed_payload, inst_dir, kind, limit)
