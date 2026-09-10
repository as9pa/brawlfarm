"""Shared route plumbing: reach the supervisor and the data directory from a request, and
turn the {name} in a path into that instance's settings plus its directory.

resolve_instance is the safety gate of spec section 9: an instance name becomes a folder
name, so it is matched against INSTANCE_NAME_RE and checked against config.toml BEFORE
anything touches the filesystem. It never creates the directory -- readers must not
conjure folders for instances that have never run; writers call mkdir themselves.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, Request

from brawlfarm import settings as S
from brawlfarm.supervisor import Supervisor


def get_sup(request: Request) -> Supervisor:
    """The one live Supervisor this process is running (put there by create_app)."""
    return request.app.state.sup


def get_home(request: Request) -> Path:
    """The resolved data directory: <home>/config.toml, <home>/instances/<name>/, ..."""
    return request.app.state.home


def resolve_instance(request: Request, name: str) -> tuple[S.InstanceSettings, Path]:
    """The instance's settings and its directory, or 404 "unknown instance".

    The same 404 covers a name that is not configured and a name that could never be a
    folder: telling those apart would only help someone probing the filesystem.
    """
    if not S.INSTANCE_NAME_RE.match(name):
        raise HTTPException(status_code=404, detail="unknown instance")
    try:
        inst = get_sup(request).settings.instance(name)
    except KeyError:
        raise HTTPException(status_code=404, detail="unknown instance") from None
    return inst, S.instance_dir(get_home(request), inst.name)
