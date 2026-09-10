"""GET /api/instances and the per-instance controls: start, stop, stop-now, restart,
retry.

The payload is the supervisor's InstanceView -- derived once per tick, so listing is free
and never blocks on adb -- plus the two things only the instance directory knows: the
live session from status.json and today's games and trophies from games.csv.

The controls are quick file writes (an override, a stop.flag, a kill by PID), so they run
on the event loop thread and end with sup.poke(), which wakes the supervisor now instead
of leaving the user waiting up to a tick.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from brawlfarm import settings as S
from brawlfarm.api.deps import get_home, get_sup, resolve_instance
from brawlfarm.core import status
from brawlfarm.supervisor.state import InstanceView

router = APIRouter()

# The battle log's own stamp format (core/datalog.py GAME_FIELDS): UTC, always.
BATTLE_TIME_FMT = "%Y%m%dT%H%M%S.%fZ"


class StartBody(BaseModel):
    """Optional body for POST start. No body at all means "undo the stop override"."""

    model_config = ConfigDict(extra="forbid")

    hours: float | None = Field(default=None, gt=0)


def view_to_dict(view: InstanceView) -> dict:
    """The InstanceView as JSON: enums become their string values and `until` becomes ISO
    seconds, so the browser always gets the same types for a field."""
    return {
        "name": view.name,
        "adb_port": view.adb_port,
        "state": str(view.state),
        "health": str(view.health),
        "pid": view.pid,
        "heartbeat_age_s": view.heartbeat_age_s,
        "phase": view.phase,
        "desired": view.desired,
        "desired_reason": view.desired_reason,
        "until": view.until.isoformat(timespec="seconds") if view.until else None,
        "games_played": view.games_played,
        "farm_brawler": view.farm_brawler,
        "note": view.note,
    }


def today_counts(inst_dir: Path, now: datetime) -> dict:
    """Games played and net trophies logged today, straight from games.csv.

    battleTime is UTC, so it is converted to local time before the date is compared: a
    match played at 00:30 local counts for today even though its UTC stamp says
    yesterday. A missing or unreadable file is zeros -- a broken CSV must never break a
    Fleet card.
    """
    path = Path(inst_dir) / "games.csv"
    today = now.date()
    local_tz = now.astimezone().tzinfo
    games = 0
    trophies = 0
    try:
        with path.open("r", encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                stamped = _battle_time(row.get("battleTime"))
                if stamped is None or stamped.astimezone(local_tz).date() != today:
                    continue
                games += 1
                trophies += _int_or_zero(row.get("trophyChange"))
    except (OSError, csv.Error, UnicodeDecodeError):
        return {"games": 0, "trophies": 0}
    return {"games": games, "trophies": trophies}


def instance_payload(
    view: InstanceView, inst: S.InstanceSettings, inst_dir: Path, now: datetime
) -> dict:
    """One Fleet card's whole row: the view, the tag from settings, the live session and
    today's totals."""
    payload = view_to_dict(view)
    payload["player_tag"] = inst.player_tag
    payload["session"] = _session(status.read_status(inst_dir))
    payload["today"] = today_counts(inst_dir, now)
    return payload


def _session(st: dict | None) -> dict | None:
    """The current session block from status.json, or None when the worker has never
    written one (a fresh instance, or one that has not run since this home was made)."""
    if not st:
        return None
    return {
        "minutes_elapsed": st.get("minutes_elapsed"),
        "start_trophies": st.get("start_trophies"),
        "last_trophies": st.get("last_trophies"),
        "disconnect_count": st.get("disconnect_count"),
        "recovery_attempts": st.get("recovery_attempts"),
        "session": st.get("session"),
    }


def _battle_time(value: str | None) -> datetime | None:
    try:
        return datetime.strptime(str(value), BATTLE_TIME_FMT).replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _int_or_zero(value) -> int:
    """A hand-edited or half-written cell counts as zero, never as an exception."""
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


@router.get("/api/instances")
async def list_instances(request: Request) -> dict:
    """Every configured instance in config.toml order.

    An instance added by PUT /api/settings appears here once the supervisor has derived a
    view for it; the PUT's sup.poke() asks for that tick immediately.
    """
    sup = get_sup(request)
    home = get_home(request)
    now = datetime.now()
    by_name = {v.name: v for v in sup.views()}
    out = []
    for inst in sup.settings.instances:
        view = by_name.get(inst.name)
        if view is None:
            continue
        out.append(instance_payload(view, inst, S.instance_dir(home, inst.name), now))
    return {"instances": out}


@router.post("/api/instances/{name}/start", status_code=202)
async def start_instance(request: Request, name: str, body: StartBody | None = None) -> dict:
    """Start it: clear the stop override, or with `hours` run for that long and stop."""
    inst, _dir = resolve_instance(request, name)
    sup = get_sup(request)
    sup.start(inst.name, body.hours if body else None)
    sup.poke()
    return {"ok": True}


@router.post("/api/instances/{name}/stop", status_code=202)
async def stop_instance(request: Request, name: str) -> dict:
    """Stop it after the current match: a stop override plus stop.flag. The tick kills by
    PID if the worker has not gone in 110 s."""
    inst, _dir = resolve_instance(request, name)
    sup = get_sup(request)
    sup.stop(inst.name)
    sup.poke()
    return {"ok": True}


@router.post("/api/instances/{name}/stop-now", status_code=202)
async def stop_instance_now(request: Request, name: str) -> dict:
    """Kill by PID right now, but only while a graceful stop is already pending: a kill
    out of nowhere would abandon a match in progress."""
    inst, _dir = resolve_instance(request, name)
    sup = get_sup(request)
    if not sup.stop_now(inst.name):
        raise HTTPException(status_code=409, detail="no stop pending")
    sup.poke()
    return {"killed": True}


@router.post("/api/instances/{name}/restart", status_code=202)
async def restart_instance(request: Request, name: str) -> dict:
    """Stop gracefully without touching the schedule; the next tick launches it again."""
    inst, _dir = resolve_instance(request, name)
    sup = get_sup(request)
    sup.restart(inst.name)
    sup.poke()
    return {"ok": True}


@router.post("/api/instances/{name}/retry", status_code=202)
async def retry_instance(request: Request, name: str) -> dict:
    """The offline card's "Retry now": drop the backoff and probe adb again this tick."""
    inst, _dir = resolve_instance(request, name)
    sup = get_sup(request)
    sup.retry_now(inst.name)
    sup.poke()
    return {"ok": True}
