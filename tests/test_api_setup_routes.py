"""The setup wizard's three probes over HTTP: the body's adb path wins over the configured
one, a missing adb is reported instead of crashing, and the display check always carries
the resolution the farm expects."""

from __future__ import annotations

from pathlib import Path

import pytest

from brawlfarm.setup import checks, discover
from tests.apihelpers import make_client


@pytest.fixture()
def api(tmp_path: Path):
    client, sup, home = make_client(tmp_path, ("alpha", "bravo"))
    try:
        yield client, sup, home
    finally:
        client.__exit__(None, None, None)


def test_scan_uses_the_configured_adb_path(api, monkeypatch) -> None:
    client, _sup, _home = api
    seen: dict[str, object] = {}

    def fake_find_adb(configured=None):
        seen["configured"] = configured
        return "C:/tools/adb.exe"

    def fake_scan(adb_path, conf_path=None, *, runner=None):
        return {"adb_path": adb_path, "adb_found": True, "conf_found": True, "instances": []}

    monkeypatch.setattr(discover, "find_adb", fake_find_adb)
    monkeypatch.setattr(discover, "scan", fake_scan)
    r = client.post("/api/setup/scan", json={})
    assert r.status_code == 200
    assert str(seen["configured"]).endswith("HD-Adb.exe")  # the configured default
    assert r.json() == {
        "adb_path": "C:/tools/adb.exe",
        "adb_found": True,
        "conf_found": True,
        "instances": [],
    }


def test_scan_prefers_the_path_in_the_body(api, monkeypatch) -> None:
    client, _sup, _home = api
    seen: dict[str, object] = {}

    def fake_find_adb(configured=None):
        seen["configured"] = configured
        return configured

    monkeypatch.setattr(discover, "find_adb", fake_find_adb)
    monkeypatch.setattr(
        discover,
        "scan",
        lambda adb_path, conf_path=None, *, runner=None: {
            "adb_path": adb_path,
            "adb_found": bool(adb_path),
            "conf_found": False,
            "instances": [],
        },
    )
    r = client.post("/api/setup/scan", json={"adb_path": "D:/portable/adb.exe"})
    assert r.status_code == 200
    assert seen["configured"] == "D:/portable/adb.exe"
    assert r.json()["adb_path"] == "D:/portable/adb.exe"


def test_test_reports_a_port_that_answers(api, monkeypatch) -> None:
    client, _sup, _home = api
    monkeypatch.setattr(discover, "find_adb", lambda configured=None: "C:/tools/adb.exe")
    monkeypatch.setattr(
        discover,
        "probe_port",
        lambda adb_path, port, **kw: {"ok": True, "detail": f"127.0.0.1:{port} answered"},
    )
    r = client.post("/api/setup/test", json={"adb_port": 5565})
    assert r.status_code == 200
    assert r.json() == {"ok": True, "detail": "127.0.0.1:5565 answered"}


def test_test_without_adb_says_so_instead_of_failing(api, monkeypatch) -> None:
    client, _sup, _home = api
    monkeypatch.setattr(discover, "find_adb", lambda configured=None: None)
    r = client.post("/api/setup/test", json={"adb_port": 5565})
    assert r.status_code == 200
    assert r.json() == {"ok": False, "detail": "adb was not found; set its path in Connection"}


def test_display_check_carries_what_the_farm_expects(api, monkeypatch) -> None:
    client, _sup, _home = api
    monkeypatch.setattr(discover, "find_adb", lambda configured=None: "C:/tools/adb.exe")
    monkeypatch.setattr(
        checks,
        "display_check",
        lambda adb_path, port, **kw: checks.DisplayCheck(
            False, 1280, 720, 320, "1280 x 720 at DPI 320", checks.DISPLAY_HINT
        ),
    )
    r = client.post("/api/setup/display-check", json={"adb_port": 5555})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert (body["width"], body["height"], body["dpi"]) == (1280, 720, 320)
    assert body["hint"] == checks.DISPLAY_HINT
    assert body["expected"] == {"width": 1600, "height": 900, "dpi": 240}


def test_a_port_outside_the_valid_range_is_rejected(api) -> None:
    client, _sup, _home = api
    assert client.post("/api/setup/test", json={"adb_port": 0}).status_code == 422
    assert client.post("/api/setup/display-check", json={"adb_port": 99999}).status_code == 422
    assert client.post("/api/setup/scan", json={"nope": 1}).status_code == 422
