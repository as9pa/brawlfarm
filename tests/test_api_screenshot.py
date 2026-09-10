"""GET /api/instances/{name}/screenshot.png: the PNG straight through with no caching,
503 when adb cannot answer, 404 for a name that is not configured, and one lock per
instance so two thumbnails never race the same BlueStacks window."""

from __future__ import annotations

import asyncio
import struct
from pathlib import Path

import pytest

from brawlfarm.api import screens
from brawlfarm.setup.checks import PNG_SIGNATURE, AdbUnavailable
from tests.apihelpers import make_client


@pytest.fixture()
def api(tmp_path: Path):
    client, sup, home = make_client(tmp_path, ("alpha", "bravo"))
    try:
        yield client, sup, home
    finally:
        client.__exit__(None, None, None)


def _png(width: int, height: int) -> bytes:
    ihdr = struct.pack(">II", width, height) + b"\x08\x06\x00\x00\x00"
    return PNG_SIGNATURE + struct.pack(">I", len(ihdr)) + b"IHDR" + ihdr


def test_screenshot_returns_the_png_and_forbids_caching(api, monkeypatch) -> None:
    client, _sup, _home = api
    frame = _png(1600, 900)
    seen: dict[str, object] = {}

    def fake_screencap(adb_path, port, **kw):
        seen["adb_path"], seen["port"] = adb_path, port
        return frame

    monkeypatch.setattr(screens, "screencap_png", fake_screencap)
    r = client.get("/api/instances/alpha/screenshot.png")
    assert r.status_code == 200
    assert r.content == frame
    assert r.headers["content-type"] == "image/png"
    assert r.headers["cache-control"] == "no-store"
    assert seen["port"] == 5555
    assert str(seen["adb_path"]).endswith("HD-Adb.exe")


def test_screenshot_is_503_when_adb_cannot_answer(api, monkeypatch) -> None:
    client, _sup, _home = api

    def boom(adb_path, port, **kw):
        raise AdbUnavailable("adb screencap failed for 127.0.0.1:5555: device offline")

    monkeypatch.setattr(screens, "screencap_png", boom)
    r = client.get("/api/instances/alpha/screenshot.png")
    assert r.status_code == 503
    assert r.json() == {"detail": "adb screencap failed for 127.0.0.1:5555: device offline"}


def test_screenshot_of_an_unknown_instance_is_404(api) -> None:
    client, _sup, _home = api
    r = client.get("/api/instances/ghost/screenshot.png")
    assert r.status_code == 404
    assert r.json() == {"detail": "unknown instance"}


def test_each_instance_gets_one_reused_lock(api, monkeypatch) -> None:
    client, _sup, _home = api
    monkeypatch.setattr(screens, "screencap_png", lambda adb_path, port, **kw: _png(16, 9))
    assert client.get("/api/instances/alpha/screenshot.png").status_code == 200
    assert client.get("/api/instances/alpha/screenshot.png").status_code == 200
    assert client.get("/api/instances/bravo/screenshot.png").status_code == 200
    locks = client.app.state.screenshot_locks
    assert set(locks) == {"alpha", "bravo"}
    assert all(isinstance(lock, asyncio.Lock) for lock in locks.values())
