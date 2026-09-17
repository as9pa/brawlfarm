"""Card geometry and the horizontal scroll of the BRAWLERS grid: the mapping from an OCR
name line to the card centre it belongs to (_visible_cards), the two swipes that move the
column-major grid (_scroll_grid) and the name-directed scan that drives them.

Nothing here reads a screen or runs OCR: the line boxes are hand-written from the session
2 measurements, and the coordinates are spelled out rather than read from config so that a
calibration edit has to come through this file too."""

from __future__ import annotations

import pytest

from brawlfarm.core import brawlers, config

OWNED = {"SHELLY", "BEA", "COLT"}


def _cards(monkeypatch, lines) -> dict[str, tuple[int, int]]:
    """_visible_cards over hand-written OCR lines: [(text, (centre_x, centre_y)), ...]."""
    boxes = [(text, 0.99, centre) for text, centre in lines]
    monkeypatch.setattr(brawlers.vision, "read_lines_boxes", lambda screen, region=None: boxes)
    return brawlers._visible_cards(None, OWNED)


def test_name_label_maps_to_its_card_centre(monkeypatch) -> None:
    assert _cards(monkeypatch, [("Shelly", (541, 310))]) == {"SHELLY": (457, 255)}


def test_short_right_aligned_name_snaps_to_its_column(monkeypatch) -> None:
    # BEA is short, so its label ends well left of where a long name's would.
    assert _cards(monkeypatch, [("Bea", (1238, 310))]) == {"BEA": (1217, 255)}


def test_second_row_label_maps_to_the_second_row_centre(monkeypatch) -> None:
    assert _cards(monkeypatch, [("Shelly", (541, 556))]) == {"SHELLY": (457, 501)}


def test_half_cut_right_column_is_not_a_visible_card(monkeypatch) -> None:
    # Column centre 1597 plus half a card runs past the grid region's right edge 1600.
    assert _cards(monkeypatch, [("Colt", (1610, 310))]) == {}


def test_line_left_of_the_first_column_is_not_a_visible_card(monkeypatch) -> None:
    assert _cards(monkeypatch, [("Colt", (200, 310))]) == {}


def _swipes(monkeypatch) -> list[tuple[int, ...]]:
    calls: list[tuple[int, ...]] = []
    monkeypatch.setattr(brawlers.adb, "swipe", lambda *a: calls.append(a))
    monkeypatch.setattr(brawlers.time, "sleep", lambda s: None)
    return calls


def test_scroll_left_drags_the_grid_from_the_right_edge(monkeypatch) -> None:
    calls = _swipes(monkeypatch)
    brawlers._scroll_grid("left")
    assert calls == [(1400, 501, 500, 501, 600)]


def test_scroll_right_is_the_reverse_swipe(monkeypatch) -> None:
    calls = _swipes(monkeypatch)
    brawlers._scroll_grid("right")
    assert calls == [(500, 501, 1400, 501, 600)]


def test_scroll_grid_rejects_anything_but_a_direction(monkeypatch) -> None:
    calls = _swipes(monkeypatch)
    with pytest.raises(ValueError):
        brawlers._scroll_grid(240)
    with pytest.raises(ValueError):
        brawlers._scroll_grid("up")
    assert calls == []


# --- the name-directed scan -----------------------------------------------------

VISIBLE = {"CARL": (457, 255), "COLT": (837, 255), "CROW": (1217, 255)}
ROSTER = ["Bull", "Carl", "Chester", "Colt", "Crow", "Dynamike"]


def _scan(monkeypatch, cards, detail_lines=()):
    """Stub everything around the scan loop: the grid always shows ``cards`` and the detail
    screen always reads ``detail_lines``. Returns the (taps, swipe directions) lists the
    loop fills in."""
    taps: list[tuple[int, ...]] = []
    swipes: list[str] = []
    monkeypatch.setattr(brawlers.adb, "tap", lambda *a: taps.append(a))
    monkeypatch.setattr(brawlers.adb, "screencap", lambda: None)
    monkeypatch.setattr(brawlers, "_on_brawlers_screen", lambda screen: True)
    monkeypatch.setattr(brawlers, "_set_sort", lambda item, log: True)
    monkeypatch.setattr(brawlers, "_ensure_toggle_off", lambda centre, name, log: None)
    monkeypatch.setattr(brawlers, "_visible_cards", lambda screen, owned: dict(cards))
    monkeypatch.setattr(brawlers, "_scroll_grid", lambda direction: swipes.append(direction))
    monkeypatch.setattr(brawlers, "_exit_to_menu", lambda: None)
    monkeypatch.setattr(
        brawlers.vision, "read_lines", lambda screen, region=None: list(detail_lines)
    )
    monkeypatch.setattr(brawlers.time, "sleep", lambda s: None)
    return taps, swipes


def test_target_before_the_visible_names_scrolls_right(monkeypatch) -> None:
    # BULL sorts before CARL, the smallest name on screen, so the target sits in the
    # columns to the LEFT, the ones a swipe to the right brings back.
    _taps, swipes = _scan(monkeypatch, VISIBLE)
    name, suspicion = brawlers.select_brawler_by_name_checked("Bull", ROSTER, log=lambda *a: None)
    assert (name, suspicion) == (None, None)
    assert swipes == ["right"] * config.BRAWLER_SELECT_MAX_SWIPES


def test_target_after_the_visible_names_scrolls_left(monkeypatch) -> None:
    _taps, swipes = _scan(monkeypatch, VISIBLE)
    name, suspicion = brawlers.select_brawler_by_name_checked(
        "Dynamike", ROSTER, log=lambda *a: None
    )
    assert (name, suspicion) == (None, None)
    assert swipes == ["left"] * config.BRAWLER_SELECT_MAX_SWIPES


def test_visible_target_is_tapped_at_its_card_centre_without_a_swipe(monkeypatch) -> None:
    taps, swipes = _scan(monkeypatch, VISIBLE, detail_lines=[("Colt", 0.99)])
    name, suspicion = brawlers.select_brawler_by_name_checked("Colt", ROSTER, log=lambda *a: None)
    assert (name, suspicion) == ("Colt", None)
    assert swipes == []
    assert taps == [(110, 415), (837, 255), (213, 818)]  # BRAWLERS, the card, SELECT


def test_target_inside_the_visible_range_keeps_scanning_one_way(monkeypatch) -> None:
    # CHESTER sorts between CARL and CROW yet no card reads as it: a roster gap (not owned
    # here, or a misread), which is no reason to swing back and forth.
    _taps, swipes = _scan(monkeypatch, VISIBLE)
    name, suspicion = brawlers.select_brawler_by_name_checked(
        "Chester", ROSTER, log=lambda *a: None
    )
    assert (name, suspicion) == (None, None)
    assert swipes == ["left"] * config.BRAWLER_SELECT_MAX_SWIPES


def test_a_grid_that_never_ocrs_a_name_spends_the_budget_and_flags(monkeypatch) -> None:
    _taps, swipes = _scan(monkeypatch, {})
    name, suspicion = brawlers.select_brawler_by_name_checked("Colt", ROSTER, log=lambda *a: None)
    assert name is None
    assert suspicion is not None and "0 owned names" in suspicion
    assert len(swipes) == config.BRAWLER_SELECT_MAX_SWIPES
