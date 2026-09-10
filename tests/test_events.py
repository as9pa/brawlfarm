"""Event-rotation snapshotter (Phase 0) verification: throttle, atomic write,
history append, and the fail-open contract (API failure keeps the last file,
refresh never raises / always exits 0). The HTTP layer is faked at the module's
single fetch seam (events._fetch_rotation) — no network in the suite.

Run:  uv run pytest tests/test_events.py -q
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

import brawlfarm.core.events as E
from brawlfarm.core.api import ApiClient, ApiError

NOW = datetime(2026, 6, 10, 12, 0, 0)

ROTATION = [
    {
        "startTime": "20260610T080000.000Z",
        "endTime": "20260611T080000.000Z",
        "event": {"id": 15000132, "mode": "trioShowdown", "map": "Double Trouble"},
    }
]


@pytest.fixture
def data_root(tmp_path, monkeypatch):
    """Redirect all of bot.events' file IO to a tmp dir (BRAWL_EVENTS_DATA_ROOT,
    same env-root pattern as the scheduler's BRAWL_SCHED_DATA_ROOT)."""
    monkeypatch.setenv("BRAWL_EVENTS_DATA_ROOT", str(tmp_path))
    return tmp_path


@pytest.fixture
def fake_fetch(monkeypatch):
    """Replace the HTTP seam with a canned rotation; returns a call counter."""
    calls = {"n": 0}

    def fetch():
        calls["n"] += 1
        return ROTATION

    monkeypatch.setattr(E, "_fetch_rotation", fetch)
    return calls


def _events(data_root) -> dict:
    return json.loads((data_root / "data" / "events.json").read_text(encoding="utf-8"))


def _history_lines(data_root) -> list[dict]:
    p = data_root / "data" / "events_history.jsonl"
    if not p.exists():
        return []
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln]


# --- the happy path -----------------------------------------------------------------


def test_refresh_writes_events_json_and_history(data_root, fake_fetch):
    assert E.refresh(now=NOW) == 0
    j = _events(data_root)
    assert j["fetched_at"] == NOW.strftime(E.TIME_FMT)
    assert j["rotation"] == ROTATION
    hist = _history_lines(data_root)
    assert len(hist) == 1
    assert hist[0]["ts"] == j["fetched_at"]
    assert hist[0]["rotation"] == ROTATION
    assert fake_fetch["n"] == 1


def test_atomic_write_leaves_no_tmp_file(data_root, fake_fetch):
    E.refresh(now=NOW)
    leftovers = list((data_root / "data").glob("*.tmp"))
    assert leftovers == []
    # and the file parses as valid JSON (no half-written content)
    assert _events(data_root)["rotation"] == ROTATION


# --- throttle -----------------------------------------------------------------------


def test_throttle_skips_fresh_file(data_root, fake_fetch):
    E.refresh(now=NOW)
    # 29 min later: still inside the 30-min throttle — no fetch, no history line.
    assert E.refresh(now=NOW + timedelta(minutes=29)) == 0
    assert fake_fetch["n"] == 1
    assert len(_history_lines(data_root)) == 1


def test_throttle_expires_after_30_min(data_root, fake_fetch):
    E.refresh(now=NOW)
    later = NOW + timedelta(minutes=31)
    assert E.refresh(now=later) == 0
    assert fake_fetch["n"] == 2
    hist = _history_lines(data_root)
    assert len(hist) == 2
    assert _events(data_root)["fetched_at"] == later.strftime(E.TIME_FMT)


def test_corrupt_events_json_counts_as_stale(data_root, fake_fetch):
    p = data_root / "data" / "events.json"
    p.parent.mkdir(parents=True)
    p.write_text("{not json", encoding="utf-8")
    assert E.refresh(now=NOW) == 0
    assert fake_fetch["n"] == 1
    assert _events(data_root)["rotation"] == ROTATION  # repaired by the rewrite


# --- fail-open: API failure keeps the last file, never raises -------------------------


def test_api_failure_keeps_last_file(data_root, fake_fetch, monkeypatch):
    E.refresh(now=NOW)
    before = _events(data_root)

    def boom():
        raise ApiError("HTTP 503")

    monkeypatch.setattr(E, "_fetch_rotation", boom)
    # past the throttle so the fetch is actually attempted
    assert E.refresh(now=NOW + timedelta(hours=1)) == 0  # exit 0, no raise
    assert _events(data_root) == before  # last good file untouched
    assert len(_history_lines(data_root)) == 1  # no phantom history line


def test_api_failure_with_no_existing_file(data_root, monkeypatch):
    def boom():
        raise ApiError("no token")

    monkeypatch.setattr(E, "_fetch_rotation", boom)
    assert E.refresh(now=NOW) == 0
    assert not (data_root / "data" / "events.json").exists()


def test_unexpected_exception_never_raises(data_root, monkeypatch):
    # Even a non-Api exception in the fetch path must come back as exit 0.
    monkeypatch.setattr(E, "_fetch_rotation", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    assert E.refresh(now=NOW) == 0


# --- CLI ------------------------------------------------------------------------------


def test_cli_refresh_exit_code(data_root, fake_fetch):
    assert E.main(["refresh"]) == 0
    assert _events(data_root)["rotation"] == ROTATION


# --- ApiClient.get_event_rotation shape handling --------------------------------------


def _client_with_payload(monkeypatch, payload):
    c = ApiClient(token="test-token")
    monkeypatch.setattr(c, "_get", lambda path: payload)
    return c


def test_get_event_rotation_bare_array(monkeypatch):
    c = _client_with_payload(monkeypatch, ROTATION)
    assert c.get_event_rotation() == ROTATION


def test_get_event_rotation_items_wrapper(monkeypatch):
    c = _client_with_payload(monkeypatch, {"items": ROTATION})
    assert c.get_event_rotation() == ROTATION
