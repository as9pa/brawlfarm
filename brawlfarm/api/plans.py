"""GET and PUT /api/instances/{name}/plan: the instance's farmplan.json, typed.

core/farmplan.py stores an untyped dict and validates nothing, so the model here is the
only gate: five keys, no others, so a typo in the editor cannot write a field the worker
will never read. Legacy files on disk carry extra keys and retired modes -- GET drops the
extras and load_plan aliases the modes, because the editor must always have something to
show.

The worker re-reads the plan live (at startup and on every trophy snapshot, roughly once
a minute), so a PUT takes effect without restarting anything. Both routes return the same
enriched shape: the five stored keys plus the brawler being farmed, the owned roster from
api/roster.py, the next three names plan_queue would reach for, and a roster_status
saying why the roster is missing when it is. PUT returns it too, so the editor never has
to re-read the plan to refresh its rows after a save.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from brawlfarm.api.connection import credential_status
from brawlfarm.api.deps import get_sup, resolve_instance
from brawlfarm.core import farmplan

router = APIRouter()

MAXED_FALLBACK_MAX = 32  # a brawler name; anything longer is a paste accident


class FarmPlan(BaseModel):
    """The five keys core/farmplan.py stores (its DEFAULT_PLAN), with types."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["ladder", "prestige"] = "ladder"
    prestige_start: Literal["highest", "lowest"] = "highest"
    goal_trophies: int = Field(default=1000, ge=0)
    maxed_fallback: str | None = Field(default=None, max_length=MAXED_FALLBACK_MAX)
    # Ladder-only, opt-in: with it on the worker reads the quests screen once at session
    # start and picks an owned brawler that clears a quest. A plan file written before
    # the key existed has no such key, so it loads as False.
    quest_aware: bool = False

    @field_validator("maxed_fallback")
    @classmethod
    def _blank_is_none(cls, v: str | None) -> str | None:
        """An empty box means "no fallback", not a brawler called "" (the worker matches
        this name case-insensitively against the owned roster)."""
        v = (v or "").strip()
        return v or None


def _as_plan(raw: dict) -> FarmPlan:
    """A stored plan as the model. Unknown keys are dropped and an unusable value falls
    back to the default: a hand-edited or legacy farmplan.json must not 500 the editor."""
    known = {k: v for k, v in raw.items() if k in FarmPlan.model_fields}
    try:
        return FarmPlan(**known)
    except ValidationError:
        return FarmPlan()


async def enrich_plan(request: Request, name: str, plan: dict) -> dict:
    """The stored plan plus everything the editor draws around it.

    `current.goal` is the goal for the MODE, not the stored number: prestige always
    finishes a brawler at PRESTIGE_GOAL, whatever goal_trophies happens to say. The
    roster is None (and the queue empty) whenever roster_status is not "ok", except for
    "unavailable", which may still carry the last good list. resolve_instance runs again
    here rather than being threaded through from the route: it is a dict lookup, and the
    helper stays callable from both routes with nothing but a name.
    """
    inst, _dir = resolve_instance(request, name)
    sup = get_sup(request)
    token = sup.settings.connection.brawl_api_token.strip()
    tag = inst.player_tag.strip()
    view = next((v for v in sup.views() if v.name == inst.name), None)
    brawler = view.farm_brawler if view is not None else None

    roster: list[dict] | None = None
    status = credential_status(token, tag)
    if status is None:
        roster, status = await request.app.state.roster.get(inst.name, tag, token)

    trophies = None
    if roster is not None and brawler:
        want = brawler.upper()
        match = next((b for b in roster if (b.get("name") or "").upper() == want), None)
        trophies = None if match is None else match.get("trophies")
    goal = farmplan.PRESTIGE_GOAL if plan["mode"] == "prestige" else plan["goal_trophies"]
    queue = [] if roster is None else farmplan.plan_queue(plan, roster, current=brawler)
    return {
        **plan,
        "current": {"brawler": brawler, "trophies": trophies, "goal": goal},
        "roster": roster,
        "queue": queue,
        "roster_status": status,
    }


@router.get("/api/instances/{name}/plan")
async def read_plan(request: Request, name: str) -> dict:
    """The stored plan merged over the defaults (a missing file reads as ladder), plus
    the roster block the editor draws its rows from."""
    _inst, inst_dir = resolve_instance(request, name)
    plan = _as_plan(farmplan.load_plan(data_dir=inst_dir)).model_dump()
    return await enrich_plan(request, name, plan)


@router.put("/api/instances/{name}/plan")
async def write_plan(request: Request, name: str, body: FarmPlan) -> dict:
    """Replace the plan. A running worker picks it up within a minute; no restart."""
    _inst, inst_dir = resolve_instance(request, name)
    inst_dir.mkdir(parents=True, exist_ok=True)
    saved = _as_plan(farmplan.save_plan(body.model_dump(), data_dir=inst_dir)).model_dump()
    return await enrich_plan(request, name, saved)
