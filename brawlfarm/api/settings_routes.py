"""GET and PUT /api/settings: the whole config.toml document as JSON.

PUT validates the document, refuses to drop an instance whose worker is alive (one worker
per instance -- removing it from settings would orphan the process the supervisor is
watching), saves it atomically and hands it to the supervisor. Changing [app].port takes
effect on the next start, because uvicorn is already bound.

The Brawl Stars token is returned as stored: the API is loopback-only and unauthenticated
on the user's own machine, and the Settings screen is what masks it.
"""

from __future__ import annotations

import asyncio
import os
import sys

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import ValidationError

from brawlfarm import settings as S
from brawlfarm.api.deps import LIVE_STATES, get_home, get_sup

router = APIRouter()


@router.get("/api/settings")
async def read_settings(request: Request) -> dict:
    """The settings the supervisor is running with right now (not a re-read of the file)."""
    return get_sup(request).settings.model_dump(mode="json")


@router.get("/api/settings/defaults")
async def read_settings_defaults() -> dict:
    """Every section at its model default, with no instances. Read only: nothing is saved
    and nothing is applied, so the panel can show what a switch would go back to."""
    return S.AppSettings().model_dump(mode="json")


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


@router.post("/api/settings/reset")
async def reset_settings(request: Request) -> dict:
    """Every section back to its model default, with the instances list carried over.

    A reset that also emptied the fleet would be a factory reset of somebody's farm, and it
    would orphan every data folder behind it. Because nothing is removed, the 409 that
    guards PUT cannot happen here, and no instance has to be stopped first.
    """
    sup = get_sup(request)
    new = S.AppSettings(instances=list(sup.settings.instances))
    S.save(new, get_home(request))
    sup.apply_settings(new)
    sup.poke()
    return new.model_dump(mode="json")


@router.post("/api/settings/open-data-folder", status_code=204)
async def open_data_folder(request: Request) -> Response:
    """Open the data directory in Explorer.

    Windows only, and the guard is on sys.platform rather than on a try around os.startfile,
    because that attribute does not exist anywhere else. startfile can block on a busy shell,
    so it goes through a thread. The path is never put in the answer: the panel shows it in
    one tooltip and nowhere else, and it is a Windows user path.
    """
    if sys.platform != "win32":
        raise HTTPException(status_code=501, detail="Only on Windows")
    try:
        await asyncio.to_thread(os.startfile, str(get_home(request)))
    except OSError as exc:
        raise HTTPException(status_code=500, detail="could not open the data folder") from exc
    return Response(status_code=204)
