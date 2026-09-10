"""GET and PUT /api/instances/{name}/plan: the instance's farmplan.json, typed.

core/farmplan.py stores an untyped dict and validates nothing, so the model here is the
only gate: four keys, no others, so a typo in the editor cannot write a field the worker
will never read. Legacy files on disk carry extra keys and retired modes -- GET drops the
extras and load_plan aliases the modes, because the editor must always have something to
show.

The worker re-reads the plan live (at startup and on every trophy snapshot, roughly once
a minute), so a PUT takes effect without restarting anything. The owned-brawler roster
and the queue the editor will offer arrive with the Instance screen in phase 4.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from brawlfarm.api.deps import resolve_instance
from brawlfarm.core import farmplan

router = APIRouter()

MAXED_FALLBACK_MAX = 32  # a brawler name; anything longer is a paste accident


class FarmPlan(BaseModel):
    """The four keys core/farmplan.py stores (its DEFAULT_PLAN), with types."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["ladder", "prestige"] = "ladder"
    prestige_start: Literal["highest", "lowest"] = "highest"
    goal_trophies: int = Field(default=1000, ge=0)
    maxed_fallback: str | None = Field(default=None, max_length=MAXED_FALLBACK_MAX)

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


@router.get("/api/instances/{name}/plan")
async def read_plan(request: Request, name: str) -> dict:
    """The stored plan merged over the defaults (a missing file reads as ladder)."""
    _inst, inst_dir = resolve_instance(request, name)
    return _as_plan(farmplan.load_plan(data_dir=inst_dir)).model_dump()


@router.put("/api/instances/{name}/plan")
async def write_plan(request: Request, name: str, body: FarmPlan) -> dict:
    """Replace the plan. A running worker picks it up within a minute; no restart."""
    _inst, inst_dir = resolve_instance(request, name)
    inst_dir.mkdir(parents=True, exist_ok=True)
    return _as_plan(farmplan.save_plan(body.model_dump(), data_dir=inst_dir)).model_dump()
