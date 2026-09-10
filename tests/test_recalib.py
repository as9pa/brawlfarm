"""Season-rollover tripwire (ops-resilience.md §B): the streak/cooldown state
machine (brawlfarm/core/recalib.py), the brawler-grid suspicion flag (driven with synthetic
frames + monkeypatched nav), and the controller wiring (_note_recalib → the
`recalibrate` event).

Everything here is offline: no adb, no OCR engine needed beyond what synthetic
black frames trivially exercise. (Round 7 removed the battle-pass and oddities
surfaces; round 8 removed the shop_freebie surface with the shop itself — the only
surviving tripwire is the brawler grid. The per_day path is still exercised with a
synthetic day-based surface, since recalib.record is surface-agnostic.)
"""

from __future__ import annotations

import json

import numpy as np

from brawlfarm.core import brawlers, config, recalib
from brawlfarm.core.controller import Controller

# --- streak / cooldown state machine -------------------------------------------------


def test_streak_bumps_and_fires_at_threshold(tmp_path):
    fire, streak = recalib.record(tmp_path, "brawlers", True, 2, today="2026-06-10")
    assert (fire, streak) == (False, 1)
    fire, streak = recalib.record(tmp_path, "brawlers", True, 2, today="2026-06-11")
    assert (fire, streak) == (True, 2)


def test_healthy_observation_resets_streak(tmp_path):
    recalib.record(tmp_path, "brawlers", True, 2, today="2026-06-10")
    recalib.record(tmp_path, "brawlers", False, 2, today="2026-06-11")
    fire, streak = recalib.record(tmp_path, "brawlers", True, 2, today="2026-06-12")
    assert (fire, streak) == (False, 1)  # the run was broken — start over


def test_cooldown_one_alert_per_day_streak_keeps_counting(tmp_path):
    recalib.record(tmp_path, "brawlers", True, 2, today="2026-06-10")
    fire, _ = recalib.record(tmp_path, "brawlers", True, 2, today="2026-06-10")
    assert fire is True  # threshold crossed (session-based: same-day bumps count)
    fire, streak = recalib.record(tmp_path, "brawlers", True, 2, today="2026-06-10")
    assert (fire, streak) == (False, 3)  # cooled down today, but still counting
    fire, streak = recalib.record(tmp_path, "brawlers", True, 2, today="2026-06-11")
    assert (fire, streak) == (True, 4)  # re-fires tomorrow while still broken


def test_per_day_dedupes_multi_session_days(tmp_path):
    # day-based surfaces use "N consecutive DAYS": two sessions on one day = 1 bump.
    # (recalib.record is surface-agnostic — "daily_surface" stands in for any per_day
    # surface now that shop_freebie is gone.)
    fire, streak = recalib.record(
        tmp_path, "daily_surface", True, 3, per_day=True, today="2026-06-10"
    )
    assert (fire, streak) == (False, 1)
    fire, streak = recalib.record(
        tmp_path, "daily_surface", True, 3, per_day=True, today="2026-06-10"
    )
    assert (fire, streak) == (False, 1)  # same day: no second bump
    fire, streak = recalib.record(
        tmp_path, "daily_surface", True, 3, per_day=True, today="2026-06-11"
    )
    assert (fire, streak) == (False, 2)
    fire, streak = recalib.record(
        tmp_path, "daily_surface", True, 3, per_day=True, today="2026-06-12"
    )
    assert (fire, streak) == (True, 3)


def test_state_persists_across_calls_and_surfaces_are_independent(tmp_path):
    recalib.record(tmp_path, "other", True, 5, today="2026-06-10")
    recalib.record(tmp_path, "brawlers", True, 5, today="2026-06-10")
    state = json.loads((tmp_path / recalib.FILE_NAME).read_text(encoding="utf-8"))
    assert state["other"]["streak"] == 1
    assert state["brawlers"]["streak"] == 1
    recalib.record(tmp_path, "other", False, 5, today="2026-06-11")
    state = recalib.load(tmp_path)
    assert state["other"]["streak"] == 0
    assert state["brawlers"]["streak"] == 1  # untouched by the other surface


def test_corrupt_state_file_degrades_to_fresh_start(tmp_path):
    (tmp_path / recalib.FILE_NAME).write_text("{not json", encoding="utf-8")
    fire, streak = recalib.record(tmp_path, "brawlers", True, 2, today="2026-06-10")
    assert (fire, streak) == (False, 1)
    assert recalib.load(tmp_path)["brawlers"]["streak"] == 1  # rewritten valid


def _black_frame():
    return np.zeros((900, 1600, 3), dtype=np.uint8)


# --- brawler grid: screen verified but 0 names ----------------------------------------


def _patch_brawler_nav(monkeypatch, cards):
    monkeypatch.setattr(brawlers.adb, "tap", lambda *a, **k: None)
    monkeypatch.setattr(brawlers.adb, "screencap", lambda: _black_frame())
    monkeypatch.setattr(brawlers, "_on_brawlers_screen", lambda s: True)
    monkeypatch.setattr(brawlers, "_set_sort", lambda item, log: True)
    monkeypatch.setattr(brawlers, "_ensure_toggle_off", lambda c, n, log: None)
    monkeypatch.setattr(brawlers, "_visible_cards", lambda s, owned: dict(cards))
    monkeypatch.setattr(brawlers, "_scroll_grid", lambda px: None)
    monkeypatch.setattr(brawlers, "_exit_to_menu", lambda: None)
    monkeypatch.setattr(brawlers.time, "sleep", lambda s: None)


def test_brawler_grid_zero_names_over_full_scroll_flags(monkeypatch):
    _patch_brawler_nav(monkeypatch, cards={})
    name, suspicion = brawlers.select_brawler_by_name_checked(
        "SHELLY", ["SHELLY", "COLT"], log=lambda *a: None
    )
    assert name is None
    assert suspicion is not None and "0 owned names" in suspicion


def test_brawler_grid_some_names_seen_is_quiet(monkeypatch):
    # OCR reads OTHER owned names fine; the target just never came into view —
    # that's "unreachable", not "the grid is blank": no tripwire.
    _patch_brawler_nav(monkeypatch, cards={"COLT": (770, 300)})
    name, suspicion = brawlers.select_brawler_by_name_checked(
        "SHELLY", ["SHELLY", "COLT"], log=lambda *a: None
    )
    assert (name, suspicion) == (None, None)


def test_brawler_grid_kill_switch_off_is_quiet(monkeypatch):
    monkeypatch.setattr(config, "RECALIB_TRIPWIRE", False)
    _patch_brawler_nav(monkeypatch, cards={})
    name, suspicion = brawlers.select_brawler_by_name_checked(
        "SHELLY", ["SHELLY"], log=lambda *a: None
    )
    assert (name, suspicion) == (None, None)


def test_brawler_select_returns_none_name_on_a_blank_grid(monkeypatch):
    # r9: the str-only select_brawler_by_name wrapper was deleted (the _checked
    # variant is the sole entry point); its name element is still None here.
    _patch_brawler_nav(monkeypatch, cards={})
    name, _suspicion = brawlers.select_brawler_by_name_checked(
        "SHELLY", ["SHELLY"], log=lambda *a: None
    )
    assert name is None


# --- controller wiring: _note_recalib → the recalibrate event -------------------------


class _DL:
    def __init__(self):
        self.events = []

    def event(self, etype, **fields):
        self.events.append((etype, fields))


def _ctrl(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    c = Controller.__new__(Controller)  # skip __init__ (ApiClient/DataLog/adb)
    c.dl = _DL()
    return c


def _recal_events(c):
    return [f for k, f in c.dl.events if k == "recalibrate"]


def test_note_recalib_emits_once_at_threshold_with_daily_cooldown(
    tmp_path, monkeypatch
):
    c = _ctrl(tmp_path, monkeypatch)
    c._note_recalib("brawlers", "screen verified but 0 owned names", 2)
    assert _recal_events(c) == []  # streak 1 < threshold
    c._note_recalib("brawlers", "screen verified but 0 owned names", 2)
    evs = _recal_events(c)
    assert len(evs) == 1
    assert evs[0]["surface"] == "brawlers"
    assert "0 owned names" in evs[0]["detail"]
    c._note_recalib("brawlers", "screen verified but 0 owned names", 2)
    assert len(_recal_events(c)) == 1  # cooled down: one alert per surface per day


def test_note_recalib_healthy_resets_and_kill_switch_writes_nothing(
    tmp_path, monkeypatch
):
    c = _ctrl(tmp_path, monkeypatch)
    c._note_recalib("brawlers", "sus", 2)
    c._note_recalib("brawlers", None, 2)  # healthy → reset
    c._note_recalib("brawlers", "sus", 2)
    assert _recal_events(c) == []
    assert recalib.load(tmp_path)["brawlers"]["streak"] == 1

    monkeypatch.setattr(config, "RECALIB_TRIPWIRE", False)
    c2 = _ctrl(tmp_path / "off", monkeypatch)
    c2._note_recalib("brawlers", "sus", 1)
    assert _recal_events(c2) == []
    assert not (tmp_path / "off" / recalib.FILE_NAME).exists()  # no writes when off


def test_note_recalib_record_error_is_swallowed(tmp_path, monkeypatch):
    c = _ctrl(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "brawlfarm.core.controller.recalib.record",
        lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")),
    )
    c._note_recalib("brawlers", "sus", 1)  # must not raise
    assert _recal_events(c) == []


def test_note_recalib_skip_neither_bumps_nor_resets(tmp_path, monkeypatch):
    """Review #56 MINOR: a nav failure (recalib.SKIP) is NO observation — it must
    not erase a genuine streak (a reskin that also breaks a nav needle) and must
    not count toward one either."""
    c = _ctrl(tmp_path, monkeypatch)
    c._note_recalib("brawlers", "sus", 3)
    c._note_recalib("brawlers", recalib.SKIP, 3)  # nav failed: untouched
    c._note_recalib("brawlers", "sus", 3)
    assert (
        recalib.load(tmp_path)["brawlers"]["streak"] == 2
    )  # SKIP neither reset nor bumped
    c._note_recalib("brawlers", None, 3)  # a real healthy observation DOES reset
    assert recalib.load(tmp_path)["brawlers"]["streak"] == 0
