"""The calibration router: the constants and templates read-out, the template PNGs, the
per-instance anchor scores, the open-folder button and the recorder switch. Nothing here
writes calibration.toml or a template; the only writes are the calibration folder and an
instance's record.flag."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

from brawlfarm import settings as S
from brawlfarm.core import config, vision
from brawlfarm.core.states import State
from tests.apihelpers import make_client


@pytest.fixture()
def api(tmp_path: Path):
    client, sup, home = make_client(tmp_path, ("alpha", "bravo"))
    try:
        yield client, sup, home
    finally:
        client.__exit__(None, None, None)


def test_get_calibration_defaults(api) -> None:
    client, _sup, _home = api
    r = client.get("/api/calibration")
    assert r.status_code == 200
    body = r.json()
    assert body["file"] == {"present": False, "changed_since_start": False, "problems": []}
    names = {c["name"] for c in body["constants"]}
    assert {"PLAY_BUTTON", "MATCH_THRESHOLD", "MATCHMAKING_THRESHOLD"} <= names
    play = next(c for c in body["constants"] if c["name"] == "PLAY_BUTTON")
    assert play["group"] == "tap" and play["source"] == "package"
    assert play["default"] == play["value"] == list(config.PLAY_BUTTON)
    mk = next(t for t in body["templates"] if t["name"] == "matchmaking")
    assert mk == {
        "name": "matchmaking",
        "source": "package",
        "width": 276,
        "height": 45,
        "threshold": config.MATCHMAKING_THRESHOLD,
    }
    assert [t["name"] for t in body["templates"]] == list(vision.TEMPLATE_NAMES)


def test_get_calibration_with_override_file(api) -> None:
    client, _sup, home = api
    (home / "calibration").mkdir(exist_ok=True)
    (home / "calibration" / "calibration.toml").write_text(
        "PLAY_BUTTON = [1, 2]\nNOPE = 3\n", encoding="utf-8"
    )
    config.set_home(home)
    try:
        body = client.get("/api/calibration").json()
        assert body["file"]["present"] is True
        assert body["file"]["problems"] == [
            "NOPE is not a calibration constant. The line is ignored."
        ]
        play = next(c for c in body["constants"] if c["name"] == "PLAY_BUTTON")
        assert play["value"] == [1, 2] and play["source"] == "calibration.toml"
        (home / "calibration" / "calibration.toml").write_text(
            "PLAY_BUTTON = [3, 4]\n", encoding="utf-8"
        )
        os.utime(home / "calibration" / "calibration.toml", ns=(1, 1))
        assert client.get("/api/calibration").json()["file"]["changed_since_start"] is True
    finally:
        (home / "calibration" / "calibration.toml").unlink()
        config.set_home(home)


def test_template_png_route(api) -> None:
    client, _sup, _home = api
    r = client.get("/api/calibration/templates/play.png")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.headers["cache-control"] == "no-store"
    assert r.content[:4] == b"\x89PNG"
    assert client.get("/api/calibration/templates/nope.png").status_code == 404
    assert client.get("/api/calibration/templates/..%2Fplay.png").status_code in (404, 422)


def test_scores_route_no_frame_then_frame(api) -> None:
    client, sup, home = api
    name = sup.settings.instances[0].name
    r = client.get(f"/api/instances/{name}/calibration/scores")
    assert r.status_code == 404 and r.json()["detail"] == "no frame yet"
    inst = S.instance_dir(home, name)
    inst.mkdir(parents=True, exist_ok=True)
    frame = np.zeros((900, 1600, 3), dtype=np.uint8)
    cv2.imwrite(str(inst / "preview.jpg"), frame)
    (inst / "status.json").write_text(json.dumps({"phase": "menu"}), encoding="utf-8")
    r = client.get(f"/api/instances/{name}/calibration/scores")
    assert r.status_code == 200
    body = r.json()
    assert body["width"] == 1600 and body["height"] == 900
    assert body["phase"] == "menu"
    assert body["state"] in {s.name.lower() for s in State}
    assert [a["name"] for a in body["anchors"]] == list(vision.TEMPLATE_NAMES)
    play = next(a for a in body["anchors"] if a["name"] == "play")
    assert play["expected"] is True and play["found"] is False
    assert set(play["box"]) == {"x", "y", "w", "h"}
    assert client.get("/api/instances/Nope/calibration/scores").status_code == 404


def test_scores_route_scales_a_half_size_preview(api) -> None:
    """The worker writes preview.jpg at half size; the route must score it at 1600x900,
    or the templates (which are cut from the locked screen) miss everything."""
    client, sup, home = api
    name = sup.settings.instances[0].name
    inst = S.instance_dir(home, name)
    inst.mkdir(parents=True, exist_ok=True)
    template = vision._load_template("play")
    th, tw = template.shape[:2]
    full = np.zeros((config.SCREEN_H, config.SCREEN_W, 3), dtype=np.uint8)
    left = config.PLAY_BUTTON[0] - tw // 2
    top = config.PLAY_BUTTON[1] - th // 2
    full[top : top + th, left : left + tw] = template
    half = cv2.resize(full, (800, 450), interpolation=cv2.INTER_AREA)
    cv2.imwrite(str(inst / "preview.jpg"), half)
    (inst / "status.json").write_text(json.dumps({"phase": "menu"}), encoding="utf-8")
    r = client.get(f"/api/instances/{name}/calibration/scores")
    assert r.status_code == 200
    body = r.json()
    assert body["width"] == 1600 and body["height"] == 900
    play = next(a for a in body["anchors"] if a["name"] == "play")
    assert play["found"] is True
    assert abs(play["box"]["x"] - left) <= 2 and abs(play["box"]["y"] - top) <= 2
    for anchor in body["anchors"]:
        box = anchor["box"]
        assert 0 <= box["x"] and box["x"] + box["w"] <= config.SCREEN_W
        assert 0 <= box["y"] and box["y"] + box["h"] <= config.SCREEN_H


def test_open_folder(api, monkeypatch) -> None:
    client, _sup, home = api
    monkeypatch.setattr(sys, "platform", "win32")
    opened: list[str] = []
    monkeypatch.setattr("os.startfile", lambda p: opened.append(p), raising=False)
    r = client.post("/api/calibration/open-folder")
    assert r.status_code == 204
    assert (home / "calibration").is_dir()
    assert opened and opened[0].endswith("calibration")
    monkeypatch.setattr(sys, "platform", "linux")
    assert client.post("/api/calibration/open-folder").status_code == 501


def test_recorder_routes(api) -> None:
    client, sup, home = api
    name = sup.settings.instances[0].name
    inst = S.instance_dir(home, name)
    body = client.get(f"/api/instances/{name}/recorder").json()
    assert body == {
        "on": False,
        "frames": 0,
        "bytes": 0,
        "session": None,
        "path": None,
        "reason": None,
        "last_session": None,
        "last_frames": 0,
        "flag": False,
        "mode": "farm",
    }
    r = client.post(f"/api/instances/{name}/recorder", json={"on": True})
    assert r.status_code == 200 and r.json()["flag"] is True
    assert (inst / "record.flag").exists()
    (inst / "recorder.json").write_text(
        json.dumps(
            {
                "on": True,
                "frames": 5,
                "bytes": 1234,
                "session": "20260912-211103",
                "path": f"recordings/{name}/20260912-211103",
                "reason": None,
                "last_session": None,
                "last_frames": 0,
            }
        ),
        encoding="utf-8",
    )
    body = client.get(f"/api/instances/{name}/recorder").json()
    assert body["frames"] == 5 and body["flag"] is True
    r = client.post(f"/api/instances/{name}/recorder", json={"on": False})
    assert r.status_code == 200 and r.json()["flag"] is False
    assert not (inst / "record.flag").exists()
    assert client.post("/api/instances/Nope/recorder", json={"on": True}).status_code == 404


def test_recorder_payload_names_the_mode(api) -> None:
    client, sup, home = api
    name = sup.settings.instances[0].name
    inst = S.instance_dir(home, name)
    assert client.get(f"/api/instances/{name}/recorder").json()["mode"] == "farm"
    inst.mkdir(parents=True, exist_ok=True)
    (inst / "status.json").write_text(json.dumps({"mode": "observe"}), encoding="utf-8")
    assert client.get(f"/api/instances/{name}/recorder").json()["mode"] == "observe"
