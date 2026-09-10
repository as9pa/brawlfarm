"""POST /api/setup/scan, /api/setup/test and /api/setup/display-check: the three probes
the setup wizard runs.

Each one shells out to adb, which can take seconds and can hang, so each one goes through
asyncio.to_thread -- the event loop also carries the supervisor task and the SSE stream.
The body's adb_path wins over the configured one, so the wizard's Browse field works
before anything has been saved to config.toml.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from brawlfarm.api.deps import get_sup
from brawlfarm.core import config
from brawlfarm.setup import checks, discover

router = APIRouter()

NO_ADB_DETAIL = "adb was not found; set its path in Connection"


class ScanBody(BaseModel):
    """Optional body for the scan: the path the user typed, if any."""

    model_config = ConfigDict(extra="forbid")

    adb_path: str | None = None


class PortBody(BaseModel):
    """One instance to probe. The port range is what makes the serial safe to build."""

    model_config = ConfigDict(extra="forbid")

    adb_port: int = Field(ge=1, le=65535)
    adb_path: str | None = None


def _expected() -> dict:
    """The display the controller asserts at startup (core/config.py calibration block)."""
    return {"width": config.SCREEN_W, "height": config.SCREEN_H, "dpi": config.SCREEN_DPI}


async def _adb_path(request: Request, override: str | None) -> str | None:
    """The adb to probe with: the body's path if it is really there, else the configured
    one, else the BlueStacks default or PATH."""
    configured = override or get_sup(request).settings.connection.adb_path
    return await asyncio.to_thread(discover.find_adb, configured)


@router.post("/api/setup/scan")
async def scan(request: Request, body: ScanBody | None = None) -> dict:
    """Find adb and list the BlueStacks instances with their ports, display size and
    whether they answer."""
    adb_path = await _adb_path(request, body.adb_path if body else None)
    return await asyncio.to_thread(discover.scan, adb_path)


@router.post("/api/setup/test")
async def test_instance_port(request: Request, body: PortBody) -> dict:
    """Does this port answer? Fails closed: no answer reads as not working."""
    adb_path = await _adb_path(request, body.adb_path)
    if not adb_path:
        return {"ok": False, "detail": NO_ADB_DETAIL}
    return await asyncio.to_thread(discover.probe_port, adb_path, body.adb_port)


@router.post("/api/setup/display-check")
async def display_check(request: Request, body: PortBody) -> dict:
    """1600 x 900 at DPI 240 or not, plus the sentence naming where to change it."""
    adb_path = await _adb_path(request, body.adb_path)
    if not adb_path:
        missing = checks.DisplayCheck(False, None, None, None, NO_ADB_DETAIL, checks.DISPLAY_HINT)
        return {**asdict(missing), "expected": _expected()}
    result = await asyncio.to_thread(checks.display_check, adb_path, body.adb_port)
    return {**asdict(result), "expected": _expected()}
