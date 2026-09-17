"""brawlfarm/core/settings.py — the in-game DND (SOCIAL SETTINGS) navigation, previously
untested (r10 hardening). Pins the three load-bearing behaviors:

  (a) verify-then-act: a failed OCR verify at ANY hop bails to the menu and
      returns failure — no blind tap ever fires past a failed verify;
  (b) the orange-fill HSV radio check decides tap vs skip — already-set radios
      are never re-tapped (mute), only SELECTED radios are tapped (unmute);
  (c) remove_dnd runs ONLY on the owner-initiated stop path (stop_flag), never
      on scheduled cap stops or the hard backstop (Controller.stop wiring —
      the deep version lives in test_stop_etiquette.py);
  (d) the calibration fix of 2026-09-17: each panel gets a measured TIME budget to
      animate in, and the exit path taps only what OCR proves is on screen — never
      the blind HOME_BUTTON rotation that hit the main menu's hamburger.

House style (test_stop_etiquette.py): direct calls into settings.py with the
adb/vision/states seams monkeypatched — no real adb, no screen, anywhere.
"""

from __future__ import annotations

import time

import pytest

from brawlfarm.core import adb, config, settings, states, vision

ALL_RADIOS = {xy for col in config.DND_MUTE_RADIO_GRID.values() for xy in col}
ROW_TAPS = (config.DND_MUTE_FRIENDS_24H, config.DND_MUTE_RECENT_30D)


class World:
    """Stateful fake of the device: which OCR needles are visible and which
    radios show the orange 'selected' fill; taps mutate the state the way the
    live panel does (row tap selects its radio, selected-radio tap clears it)."""

    def __init__(self):
        self.taps: list[tuple[int, int]] = []
        self.selected: set[tuple[int, int]] = set()
        self.stuck: set[tuple[int, int]] = set()  # radios that refuse to clear
        self.teamup_opens = True  # "TEAM UP" title: the '+' slot verify AND the exit read
        self.social_opens = True  # "MUTE" verify after the gear tap
        self.social_title = False  # "SOCIAL SETTINGS" title, read by _exit_to_menu
        self.shots: list[str] = []  # _event_shot tags (failed-verify evidence)
        self.sleeps: list[float] = []  # every settings.py sleep (the wait budgets)

    # --- adb seams -------------------------------------------------------------
    def tap(self, x: int, y: int) -> None:
        xy = (x, y)
        self.taps.append(xy)
        if xy in self.selected and xy not in self.stuck:
            self.selected.discard(xy)  # tapping a SELECTED radio deselects it
        elif xy == config.DND_MUTE_FRIENDS_24H:
            self.selected.add(config.DND_MUTE_FRIENDS_24H_RADIO)
        elif xy == config.DND_MUTE_RECENT_30D:
            self.selected.add(config.DND_MUTE_RECENT_30D_RADIO)

    def screencap(self):
        return "screen"  # opaque — only the fakes below interpret it

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)  # instant, but the budget is still measurable

    # --- vision seams ----------------------------------------------------------
    def find_text(self, screen, needle, **kwargs):
        if needle == "TEAM UP":
            return (800, 100) if self.teamup_opens else None
        if needle == "MUTE":
            return (800, 200) if self.social_opens else None
        if needle == "SOCIAL SETTINGS":
            return (977, 42) if self.social_title else None
        return None

    def color_fraction(self, screen, region, lo, hi) -> float:
        # the radio check samples a box around the radio center — recover the
        # center from the region and answer from the selected-set
        x1, y1, x2, y2 = region
        center = ((x1 + x2) // 2, (y1 + y2) // 2)
        return 1.0 if center in self.selected else 0.0


@pytest.fixture()
def world(monkeypatch):
    w = World()
    monkeypatch.setattr(adb, "tap", w.tap)
    monkeypatch.setattr(adb, "screencap", w.screencap)
    monkeypatch.setattr(vision, "find_text", w.find_text)
    monkeypatch.setattr(vision, "color_fraction", w.color_fraction)
    # _exit_to_menu sees the MENU immediately (its own popup loop is pinned below)
    monkeypatch.setattr(states, "classify", lambda screen: states.State.MENU)
    monkeypatch.setattr(settings, "_event_shot", lambda screen, tag: w.shots.append(tag))
    monkeypatch.setattr(time, "sleep", w.sleep)  # instant polls, recorded durations
    return w


def _radio_taps(world):
    return [t for t in world.taps if t in ALL_RADIOS]


# --- (a) verify-then-act: failed verify bails, no blind taps continue ---------------


def test_teamup_verify_fail_bails_with_no_inner_taps(world):
    world.teamup_opens = False
    assert settings.ensure_team_invites_muted(log=lambda m: None) is False
    # ONLY the '+' slot probe fired; nothing past the failed verify was touched
    assert world.taps == [config.DND_TEAM_SLOT]


def test_social_settings_verify_fail_bails_before_any_panel_tap(world):
    world.social_opens = False
    assert settings.ensure_team_invites_muted(log=lambda m: None) is False
    assert world.taps.count(config.DND_TEAMUP_GEAR) == 2  # the documented retry
    for forbidden in (*ROW_TAPS, config.DND_MUTES_CONFIRM, *ALL_RADIOS):
        assert forbidden not in world.taps
    assert world.shots == ["dnd_no_mute_settings"]  # evidence screenshot saved


def test_unmute_teamup_verify_fail_bails(world):
    world.teamup_opens = False
    assert settings.ensure_team_invites_unmuted(log=lambda m: None) is False
    assert world.taps == [config.DND_TEAM_SLOT]


def test_unmute_social_verify_fail_bails_before_any_radio_tap(world):
    world.social_opens = False
    world.selected = set(ALL_RADIOS)  # even with everything lit, no tap may fire
    assert settings.ensure_team_invites_unmuted(log=lambda m: None) is False
    assert _radio_taps(world) == []
    assert config.DND_MUTES_CONFIRM not in world.taps
    assert world.shots == ["dndoff_no_mute_settings"]


def test_exit_to_menu_closes_popups_with_taps_only(world, monkeypatch):
    # a popup on the way out is closed via its detected/fallback ✕ — taps only
    seq = [states.State.POPUP]
    monkeypatch.setattr(states, "classify", lambda s: seq.pop(0) if seq else states.State.MENU)
    monkeypatch.setattr(vision, "find", lambda s, name: None)  # template miss
    settings._exit_to_menu(lambda m: None)
    assert world.taps == [config.CLOSE_X_BUTTON]


# --- (d) panel-open budgets: poll until the label reads or the budget is spent --------


def test_wait_for_screen_accepts_a_label_that_appears_late(world, monkeypatch):
    # live measurement: the TEAM UP title reads 4.9 s after the '+' slot tap, so a wait
    # that gives up early is exactly how the leg kept skipping
    polls = {"n": 0}

    def late(screen, needle, **kwargs):
        polls["n"] += 1
        return (977, 42) if polls["n"] >= 5 else None

    monkeypatch.setattr(vision, "find_text", late)
    assert settings._wait_for_screen("TEAM UP", config.DND_PANEL_WAIT_S) == "screen"
    assert polls["n"] == 5  # read on the 5th poll, i.e. 2.5 s in
    assert sum(world.sleeps) == pytest.approx(2.5)  # and it stopped polling there


def test_wait_for_screen_spends_the_whole_budget_before_giving_up(world, monkeypatch):
    monkeypatch.setattr(vision, "find_text", lambda *a, **k: None)
    assert settings._wait_for_screen("MUTE", config.DND_SETTINGS_WAIT_S) is None
    assert sum(world.sleeps) == pytest.approx(config.DND_SETTINGS_WAIT_S)


# --- (d) the exit path taps only what the screen proves is there ---------------------


def _classify_seq(monkeypatch, *seq):
    """states.classify answers `seq` in order, then MENU (the loop's normal exit)."""
    q = list(seq)
    monkeypatch.setattr(states, "classify", lambda s: q.pop(0) if q else states.State.MENU)


def test_exit_to_menu_taps_nothing_while_no_panel_is_readable(world, monkeypatch):
    world.teamup_opens = False  # neither panel title has animated in yet
    _classify_seq(monkeypatch, states.State.UNKNOWN)
    settings._exit_to_menu(lambda m: None)
    assert world.taps == []  # waited the cycle out instead of tapping blind
    assert world.sleeps == [1.2]


def test_exit_to_menu_closes_the_teamup_panel_by_its_own_x(world, monkeypatch):
    _classify_seq(monkeypatch, states.State.UNKNOWN)  # TEAM UP title readable
    settings._exit_to_menu(lambda m: None)
    assert world.taps == [config.DND_TEAMUP_CLOSE_X]


def test_exit_to_menu_closes_social_settings_before_the_teamup_panel(world, monkeypatch):
    world.social_title = True  # SOCIAL SETTINGS sits ON TOP of a readable TEAM UP
    _classify_seq(monkeypatch, states.State.UNKNOWN)
    settings._exit_to_menu(lambda m: None)
    assert world.taps == [config.CLOSE_X_BUTTON]


def test_exit_to_menu_never_taps_the_home_button(world, monkeypatch):
    # HOME_BUTTON (1525, 47) is the main menu's hamburger: the old blind rotation
    # opened the side menu, and the taps after it walked the game out of the app
    logs = []
    monkeypatch.setattr(states, "classify", lambda s: states.State.UNKNOWN)
    settings._exit_to_menu(logs.append)  # never reaches the MENU: all 8 cycles run
    assert config.HOME_BUTTON not in world.taps
    assert world.taps == [config.DND_TEAMUP_CLOSE_X] * 8
    assert "could not confirm the menu" in logs[0]


def test_exit_to_menu_never_taps_the_home_button_on_a_blank_screen(world, monkeypatch):
    world.teamup_opens = False
    monkeypatch.setattr(states, "classify", lambda s: states.State.UNKNOWN)
    settings._exit_to_menu(lambda m: None)
    assert world.taps == []  # nothing readable, nothing tapped, for all 8 cycles
    assert world.sleeps == [1.2] * 8


# --- (b) the orange-fill radio check decides tap vs skip ----------------------------


def test_already_set_radios_are_not_retapped(world):
    world.selected = {
        config.DND_MUTE_FRIENDS_24H_RADIO,
        config.DND_MUTE_RECENT_30D_RADIO,
    }
    assert settings.ensure_team_invites_muted(log=lambda m: None) is True
    for row in ROW_TAPS:
        assert row not in world.taps  # idempotent: nothing re-tapped
    assert config.DND_MUTES_CONFIRM in world.taps  # the deterministic close


def test_only_the_unset_radio_row_is_tapped(world):
    world.selected = {config.DND_MUTE_RECENT_30D_RADIO}  # recent already set
    assert settings.ensure_team_invites_muted(log=lambda m: None) is True
    assert config.DND_MUTE_FRIENDS_24H in world.taps
    assert config.DND_MUTE_RECENT_30D not in world.taps
    assert world.selected == {
        config.DND_MUTE_FRIENDS_24H_RADIO,
        config.DND_MUTE_RECENT_30D_RADIO,
    }


def test_unmute_taps_only_selected_radios(world):
    world.selected = {(278, 427), (868, 505)}  # friends=24h, recent=30d
    assert settings.ensure_team_invites_unmuted(log=lambda m: None) is True
    assert set(_radio_taps(world)) == {(278, 427), (868, 505)}
    assert world.selected == set()  # both cleared
    assert config.DND_MUTES_CONFIRM in world.taps


def test_unmute_with_nothing_selected_taps_no_radios(world):
    assert settings.ensure_team_invites_unmuted(log=lambda m: None) is True
    assert _radio_taps(world) == []
    assert config.DND_MUTES_CONFIRM in world.taps  # still the way off the panel


def test_unmute_stuck_radio_is_reported_never_relooped(world):
    world.selected = {(278, 427)}
    world.stuck = {(278, 427)}
    assert settings.ensure_team_invites_unmuted(log=lambda m: None) is False
    assert world.taps.count((278, 427)) == 1  # tapped once, never hammered
    assert "dndoff_radio_stuck" in world.shots


# --- the never-kill guards (the contract Controller.stop / the farm loop rely on) ----


def test_apply_dnd_swallows_nav_exceptions(world, monkeypatch):
    def boom(log):
        raise RuntimeError("verify exploded")

    monkeypatch.setattr(settings, "ensure_team_invites_muted", boom)
    assert settings.apply_dnd(log=lambda m: None) == {"invites_muted": False}


def test_remove_dnd_swallows_nav_exceptions(world, monkeypatch):
    def boom(log):
        raise RuntimeError("verify exploded")

    monkeypatch.setattr(settings, "ensure_team_invites_unmuted", boom)
    assert settings.remove_dnd(log=lambda m: None) == {"invites_unmuted": False}


# --- (c) remove_dnd fires ONLY on the owner-initiated stop path ----------------------
# Controller.stop wiring (controller.py ~1283): `reason == "stop_flag"` AND the
# DND_OFF_ON_STOP kill switch. test_stop_etiquette.py owns the deep version
# (failure handling, idempotence, kill switch); this pins the reason gate itself.


@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        ("stop_flag", 1),  # /stop, watchdog retire — a human gets the account
        ("max_games", 0),  # scheduled cap — the account comes right back
        ("max_minutes", 0),
        ("stop_flag_hard", 0),  # >10 min overdue backstop — NOT at a menu
    ],
)
def test_remove_dnd_only_on_owner_initiated_stops(world, monkeypatch, reason, expected):
    from brawlfarm.core.controller import Controller

    calls = {"remove_dnd": 0}
    monkeypatch.setattr(
        settings,
        "remove_dnd",
        lambda log: (
            calls.__setitem__("remove_dnd", calls["remove_dnd"] + 1),
            {"invites_unmuted": True},
        )[1],
    )
    monkeypatch.setattr(adb, "force_stop", lambda: None)
    monkeypatch.setattr(config, "DND_OFF_ON_STOP", True)

    class _DL:
        def event(self, etype, **fields):
            pass

    c = Controller.__new__(Controller)  # no __init__: no ApiClient/adb/DataLog
    c.running = True
    c.games_played = 1
    c.start = time.monotonic()
    c._recap_done = True
    c.dl = _DL()
    c.stop(reason)
    assert calls["remove_dnd"] == expected, reason
