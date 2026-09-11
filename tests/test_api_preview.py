"""GET /api/instances/{name}/preview.jpg: the worker's own frame when one is fresh, one
throttled live capture when no worker is running, the last file it wrote when adb is gone
too, and a 304 whenever the browser already holds the frame we were about to send.

The point of the route is that a visible panel polling once a second costs nothing: a
running instance is served a file the worker wrote anyway, and a stopped one is capped at
one screencap every LIVE_MIN_INTERVAL_S however fast the page asks.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import cv2
import numpy as np
import pytest

from brawlfarm import settings as S
from brawlfarm.api import screens
from brawlfarm.core import preview
from brawlfarm.setup.checks import AdbUnavailable
from tests.apihelpers import make_client

URL = "/api/instances/alpha/preview.jpg"


@pytest.fixture()
def api(tmp_path: Path):
    client, sup, home = make_client(tmp_path, ("alpha", "bravo"))
    try:
        yield client, sup, home
    finally:
        client.__exit__(None, None, None)


def _frame(value: int = 200) -> np.ndarray:
    return np.full((900, 1600, 3), value, dtype=np.uint8)


def _png(value: int = 200) -> bytes:
    ok, buf = cv2.imencode(".png", _frame(value))
    assert ok
    return bytes(buf)


def _write_preview(home: Path, name: str, *, age_s: float = 0.0) -> Path:
    """A preview.jpg in the instance's folder, optionally back-dated to look abandoned."""
    path = S.instance_dir(home, name) / preview.PREVIEW_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(preview.encode(_frame(120)))
    if age_s:
        stamp = time.time() - age_s
        os.utime(path, (stamp, stamp))
    return path


def _etag_of(path: Path) -> str:
    st = path.stat()
    return f'"{st.st_mtime_ns}-{st.st_size}"'


def test_a_fresh_worker_frame_is_served_from_disk(api) -> None:
    _client, _sup, home = api
    path = _write_preview(home, "alpha")
    r = _client.get(URL)
    assert r.status_code == 200
    assert r.content == path.read_bytes()
    assert r.headers["content-type"] == "image/jpeg"
    assert r.headers["x-preview-source"] == "worker"
    assert r.headers["etag"] == _etag_of(path)
    assert r.headers["last-modified"].endswith("GMT")
    assert r.headers["cache-control"] == "no-cache"


def test_the_same_etag_comes_back_as_304_with_no_body(api) -> None:
    client, _sup, home = api
    path = _write_preview(home, "alpha")
    etag = _etag_of(path)
    r = client.get(URL, headers={"If-None-Match": etag})
    assert r.status_code == 304
    assert r.content == b""
    assert r.headers["etag"] == etag
    assert r.headers["cache-control"] == "no-cache"


def test_a_stale_file_falls_back_to_one_live_capture(api, monkeypatch) -> None:
    client, _sup, home = api
    _write_preview(home, "alpha", age_s=60.0)
    monkeypatch.setattr(screens, "screencap_png", lambda adb_path, port, **kw: _png())
    r = client.get(URL)
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"
    assert r.headers["x-preview-source"] == "live"
    shrunk = cv2.imdecode(np.frombuffer(r.content, np.uint8), cv2.IMREAD_COLOR)
    assert shrunk is not None
    assert shrunk.shape == (450, 800, 3)


def test_the_live_capture_is_throttled(api, monkeypatch) -> None:
    client, _sup, _home = api
    captures: list[int] = []

    def fake_screencap(adb_path, port, **kw):
        captures.append(port)
        return _png()

    monkeypatch.setattr(screens, "screencap_png", fake_screencap)
    first = client.get(URL)
    second = client.get(URL)
    assert [first.status_code, second.status_code] == [200, 200]
    assert captures == [5555]  # the second request was served from the cache
    assert second.headers["etag"] == first.headers["etag"]


def test_each_instance_caches_its_own_live_frame(api, monkeypatch) -> None:
    client, _sup, _home = api
    captures: list[int] = []

    def fake_screencap(adb_path, port, **kw):
        captures.append(port)
        return _png()

    monkeypatch.setattr(screens, "screencap_png", fake_screencap)
    alpha = client.get(URL)
    bravo = client.get("/api/instances/bravo/preview.jpg")
    assert captures == [5555, 5565]
    assert alpha.headers["etag"] != bravo.headers["etag"]
    assert client.get(URL).headers["etag"] == alpha.headers["etag"]
    assert captures == [5555, 5565]


def test_a_dead_adb_falls_back_to_the_last_file_the_worker_wrote(api, monkeypatch) -> None:
    client, _sup, home = api
    path = _write_preview(home, "alpha", age_s=60.0)

    def boom(adb_path, port, **kw):
        raise AdbUnavailable("adb screencap failed for 127.0.0.1:5555: device offline")

    monkeypatch.setattr(screens, "screencap_png", boom)
    r = client.get(URL)
    assert r.status_code == 200
    assert r.content == path.read_bytes()
    assert r.headers["x-preview-source"] == "stale"
    assert r.headers["etag"] == _etag_of(path)


def test_a_dead_adb_with_no_file_at_all_is_503(api, monkeypatch) -> None:
    client, _sup, _home = api

    def boom(adb_path, port, **kw):
        raise AdbUnavailable("adb screencap failed for 127.0.0.1:5555: device offline")

    monkeypatch.setattr(screens, "screencap_png", boom)
    r = client.get(URL)
    assert r.status_code == 503
    assert r.json() == {"detail": "adb screencap failed for 127.0.0.1:5555: device offline"}


def test_the_preview_of_an_unknown_instance_is_404(api) -> None:
    client, _sup, _home = api
    r = client.get("/api/instances/ghost/preview.jpg")
    assert r.status_code == 404
    assert r.json() == {"detail": "unknown instance"}
