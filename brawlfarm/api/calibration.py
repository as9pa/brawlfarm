"""Calibration read-outs, template files, recorder switch, open folder.

Nothing here writes calibration.toml or a template. The only writes are
creating the calibration folder and creating or removing record.flag in an
instance's data folder.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from brawlfarm import settings as S
from brawlfarm.api.deps import LIVE_STATES, get_home, get_sup, resolve_instance
from brawlfarm.core import calibration, config, states, vision

router = APIRouter()

# Which anchors a phase should be able to see, so the page can say "this one is missing
# where it matters" instead of listing thirteen scores flat. The keys are the controller's
# self.phase values ("returning" walks the results and trophy screens back to the menu);
# "menu" is the shorthand a status.json may carry for at_menu. A phase that is not here
# expects nothing, which is the honest answer for a transient one.
EXPECTED_BY_PHASE: dict[str, frozenset[str]] = {
    "at_menu": frozenset({"play"}),
    "menu": frozenset({"play"}),
    "returning": frozenset(
        {"play", "playagain", "proceed", "exit", "trophy_screen", "trophy_brawler"}
    ),
    "queuing": frozenset({"matchmaking"}),
    "playing": frozenset({"teams_left"}),
}

# find_with_score returns no Match below its threshold, and the page wants the best box
# even for a miss, so the scores route asks with a threshold nothing can fall under
# (TM_CCOEFF_NORMED bottoms out at -1) and does the found/not-found call itself.
_ALWAYS = -1.0


class RecorderBody(BaseModel):
    on: bool


def _jsonable(value: object) -> object:
    """Tuples are tap coordinates; JSON has no tuple, so they go out as two-item lists."""
    return list(value) if isinstance(value, tuple) else value


def _recorder_payload(inst: Path) -> dict:
    """recorder.json as the worker left it, plus whether the flag is currently set.

    The worker owns recorder.json: a missing or half-written file means "nothing has
    recorded here yet", never a 500. mode comes from status.json, not from recorder.json,
    because it is the worker that knows which kind it is.
    """
    status = {
        "on": False,
        "frames": 0,
        "bytes": 0,
        "session": None,
        "path": None,
        "reason": None,
        "last_session": None,
        "last_frames": 0,
    }
    try:
        data = json.loads((inst / "recorder.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = None
    if isinstance(data, dict):
        status.update({k: v for k, v in data.items() if k in status})
    status["flag"] = (inst / "record.flag").exists()
    status["mode"] = _mode_of(inst)
    return status


def _mode_of(inst: Path) -> str:
    """Which kind of worker is recording here. Only an instance whose own heartbeat says
    ``observe`` is observing; no heartbeat, an unreadable one or anything else is "farm",
    which is the answer that makes the page's switch stay disabled rather than inviting a
    click that the observe route would refuse."""
    try:
        data = json.loads((inst / "status.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "farm"
    mode = data.get("mode") if isinstance(data, dict) else None
    return "observe" if mode == "observe" else "farm"


def _phase_of(inst: Path) -> str | None:
    """The worker's current phase from status.json, or None when there is no usable one."""
    try:
        data = json.loads((inst / "status.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    phase = data.get("phase") if isinstance(data, dict) else None
    return phase if isinstance(phase, str) else None


def _anchors(screen: np.ndarray, phase: str | None) -> list[dict]:
    """Every template scored against one frame. About 150 ms for the thirteen of them,
    which is why the route runs this in a thread."""
    expected = EXPECTED_BY_PHASE.get(phase or "", frozenset())
    out: list[dict] = []
    for name in vision.TEMPLATE_NAMES:
        match, score = vision.find_with_score(screen, name, threshold=_ALWAYS)
        if not math.isfinite(score):  # a flat frame divides by zero in matchTemplate
            score = 0.0
        threshold = vision.threshold_for(name)
        box = (
            {"x": match.x - match.w // 2, "y": match.y - match.h // 2, "w": match.w, "h": match.h}
            if match is not None
            else {"x": 0, "y": 0, "w": 0, "h": 0}
        )
        out.append(
            {
                "name": name,
                "score": score,
                "threshold": threshold,
                "found": score >= threshold,
                "expected": name in expected,
                "box": box,
            }
        )
    return out


@router.get("/api/calibration")
async def get_calibration(request: Request) -> dict:
    """Every overridable constant and every template, with where its value came from.

    config.CALIBRATION is the report from the last set_home(), so "changed_since_start"
    is how the page knows the file on disk has moved on from the running process.
    """
    report = config.CALIBRATION
    values = calibration.overridable(vars(config))
    constants = [
        {
            "name": name,
            "group": calibration.group_of(name, value),
            "value": _jsonable(value),
            "default": _jsonable(report.defaults.get(name, value)),
            "source": "calibration.toml" if name in report.applied else "package",
        }
        for name, value in values.items()
    ]
    constants.sort(key=lambda c: (c["group"], c["name"]))
    templates = []
    for name in vision.TEMPLATE_NAMES:
        height, width = vision._load_template(name).shape[:2]
        templates.append(
            {
                "name": name,
                "source": vision.template_source(name),
                "width": int(width),
                "height": int(height),
                "threshold": vision.threshold_for(name),
            }
        )
    return {
        "file": {
            "present": report.present,
            "changed_since_start": calibration.changed_since(report),
            "problems": list(report.problems),
        },
        "constants": constants,
        "templates": templates,
    }


@router.get("/api/calibration/templates/{name}.png")
async def template_png(name: str) -> Response:
    """The template image actually in use: the override if there is one, else packaged.

    The name is matched against TEMPLATE_NAMES before it ever reaches a path, so no
    request can point this at a file of its own choosing.
    """
    if name not in vision.TEMPLATE_NAMES:
        raise HTTPException(status_code=404, detail="unknown template")
    try:
        data = vision.template_path(name).read_bytes()
    except OSError as exc:
        raise HTTPException(status_code=404, detail="unknown template") from exc
    return Response(content=data, media_type="image/png", headers={"Cache-Control": "no-store"})


@router.post("/api/calibration/open-folder", status_code=204)
async def open_calibration_folder(request: Request) -> Response:
    """Open the calibration folder in Explorer, creating it on the way.

    The folder is always <home>/calibration: nothing from the request reaches the path.
    Windows only, same as the data-folder button, and the path is never echoed back.
    """
    folder = get_home(request) / "calibration"
    folder.mkdir(parents=True, exist_ok=True)
    if sys.platform != "win32":
        raise HTTPException(status_code=501, detail="Only on Windows")
    try:
        await asyncio.to_thread(os.startfile, str(folder))
    except OSError as exc:
        raise HTTPException(
            status_code=500, detail="could not open the calibration folder"
        ) from exc
    return Response(status_code=204)


@router.get("/api/instances/{name}/calibration/scores")
async def get_scores(request: Request, name: str) -> dict:
    """Every anchor scored against this instance's last preview frame.

    The frame is the one the worker already wrote, never a fresh screencap: the page
    polls this while the farm runs and must not fight it for the adb connection.
    """
    inst_settings, _dir = resolve_instance(request, name)
    inst = S.instance_dir(get_home(request), inst_settings.name)
    frame = inst / "preview.jpg"
    try:
        data = frame.read_bytes()
        mtime_ns = frame.stat().st_mtime_ns
    except OSError as exc:
        raise HTTPException(status_code=404, detail="no frame yet") from exc
    screen = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if screen is None:
        raise HTTPException(status_code=404, detail="no frame yet")
    phase = _phase_of(inst)
    state, anchors, (height, width) = await asyncio.to_thread(_classify_and_score, screen, phase)
    return {
        "at": datetime.fromtimestamp(mtime_ns / 1e9, timezone.utc).isoformat(),
        "width": int(width),
        "height": int(height),
        "phase": phase,
        "state": state,
        "anchors": anchors,
    }


def _classify_and_score(
    screen: np.ndarray, phase: str | None
) -> tuple[str, list[dict], tuple[int, int]]:
    """The whole CPU half of the scores route, so one hop to a thread covers both.

    The worker's preview is half size; the templates and every anchor box are 1600x900,
    so we scale the frame up here rather than have the worker store a second frame.
    """
    if screen.shape[1] != config.SCREEN_W or screen.shape[0] != config.SCREEN_H:
        screen = cv2.resize(
            screen, (config.SCREEN_W, config.SCREEN_H), interpolation=cv2.INTER_LINEAR
        )
    height, width = screen.shape[:2]
    return (
        states.classify(screen, phase=phase).name.lower(),
        _anchors(screen, phase),
        (height, width),
    )


@router.get("/api/instances/{name}/recorder")
async def get_recorder(request: Request, name: str) -> dict:
    """What the recorder is doing, as the worker last reported it."""
    inst_settings, _dir = resolve_instance(request, name)
    return _recorder_payload(S.instance_dir(get_home(request), inst_settings.name))


@router.post("/api/instances/{name}/recorder")
async def set_recorder(request: Request, name: str, body: RecorderBody) -> dict:
    """Flip record.flag. The worker notices within a few ticks and answers in
    recorder.json, so the payload here is the flag plus whatever it last wrote.

    409 while an observe worker is live, in either position: the observer raises and drops
    the same flag itself, so a click here would close the owner's recording session behind
    the observe switch's back.
    """
    inst_settings, _dir = resolve_instance(request, name)
    inst = S.instance_dir(get_home(request), inst_settings.name)
    view = next((v for v in get_sup(request).views() if v.name == inst_settings.name), None)
    if view is not None and view.state in LIVE_STATES and _mode_of(inst) == "observe":
        raise HTTPException(
            status_code=409,
            detail=f"{inst_settings.name} is recording play; use the observe switch",
        )
    flag = inst / "record.flag"
    if body.on:
        inst.mkdir(parents=True, exist_ok=True)
        flag.touch()
    else:
        flag.unlink(missing_ok=True)
    return _recorder_payload(inst)
