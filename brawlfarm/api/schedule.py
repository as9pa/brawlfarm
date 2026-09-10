"""GET and PUT /api/instances/{name}/schedule: the on/off switch, today's drawn sessions,
the scheduler's desired block and the manual override.

The scheduler tick owns schedule.json and scheduler_state.json; the panel only ever
writes the control file (enabled, nonce) and override.json -- exactly the three
primitives the legacy chat commands had. "Run for N hours" and "Stop" are the start and
stop controls in instances.py (they write the override); clear_override here cancels
either one.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict

from brawlfarm.api.deps import get_sup, resolve_instance
from brawlfarm.core import scheduler

router = APIRouter()


class SchedulePatch(BaseModel):
    """A patch, not a document: only what is present acts. All three can arrive at once."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = None
    redraw: bool = False
    clear_override: bool = False


def schedule_payload(name: str, now: datetime) -> dict:
    """Everything the Instance screen's schedule panel draws. `sessions` is trimmed to
    start and end: entry_delay_s and the outing flags are the tick's business, and the
    timeline only draws the windows."""
    sched = scheduler.read_schedule(name) or {}
    sessions = [
        {"start": s.get("start"), "end": s.get("end")}
        for s in (sched.get("sessions") or [])
        if isinstance(s, dict)
    ]
    return {
        "enabled": scheduler.is_enabled(name),
        "override": scheduler.read_override(name),
        "plan_date": sched.get("plan_date"),
        "sessions": sessions,
        "day_end": sched.get("day_end"),
        "desired": sched.get("desired"),
        "games_played_today": int(sched.get("games_played_today") or 0),
        "now": now.isoformat(timespec="seconds"),
    }


@router.get("/api/instances/{name}/schedule")
async def read_schedule(request: Request, name: str) -> dict:
    """Today's schedule as the last tick left it, plus the switch and the override."""
    inst, _dir = resolve_instance(request, name)
    return schedule_payload(inst.name, datetime.now())


@router.put("/api/instances/{name}/schedule")
async def write_schedule(request: Request, name: str, body: SchedulePatch) -> dict:
    """Flip the switch, redraw today, or cancel the override, then poke the supervisor so
    the next tick happens now instead of up to 60 s later. Returns the GET payload; the
    sessions of a redraw appear once that tick has run."""
    inst, _dir = resolve_instance(request, name)
    sup = get_sup(request)
    if body.enabled is not None:
        scheduler.set_enabled([inst.name], body.enabled)
    if body.redraw:
        scheduler.bump_nonce(inst.name)
    if body.clear_override:
        scheduler.clear_override(inst.name)
    sup.poke()
    return schedule_payload(inst.name, datetime.now())
