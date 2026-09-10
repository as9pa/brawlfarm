"""GET and PUT /api/settings: the whole config.toml document as JSON.

PUT validates the document, refuses to drop an instance whose worker is alive (one worker
per instance -- removing it from settings would orphan the process the supervisor is
watching), saves it atomically and hands it to the supervisor. Changing [app].port takes
effect on the next start, because uvicorn is already bound.

The Brawl Stars token is returned as stored: the API is loopback-only and unauthenticated
on the user's own machine, and the Settings screen is what masks it.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError

from brawlfarm import settings as S
from brawlfarm.api.deps import get_home, get_sup
from brawlfarm.supervisor.state import InstanceState

router = APIRouter()

# States that mean a worker process is running, or is about to be.
LIVE_STATES = frozenset(
    {
        InstanceState.FARMING,
        InstanceState.STARTING,
        InstanceState.STOPPING,
        InstanceState.RECONNECTING,
    }
)


@router.get("/api/settings")
async def read_settings(request: Request) -> dict:
    """The settings the supervisor is running with right now (not a re-read of the file)."""
    return get_sup(request).settings.model_dump(mode="json")


@router.put("/api/settings")
async def write_settings(request: Request, body: dict) -> dict:
    """Replace config.toml wholesale and re-apply it. 422 names the offending field, 409
    names the instance that has to be stopped first."""
    sup = get_sup(request)
    try:
        new = S.AppSettings.model_validate(body)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=S._explain(exc)) from exc
    keeping = {i.name for i in new.instances}
    views = {v.name: v for v in sup.views()}
    for inst in sup.settings.instances:
        if inst.name in keeping:
            continue
        view = views.get(inst.name)
        if view is not None and view.state in LIVE_STATES:
            raise HTTPException(status_code=409, detail=f"Stop {inst.name} before removing it")
    S.save(new, get_home(request))
    sup.apply_settings(new)
    sup.poke()
    return new.model_dump(mode="json")
