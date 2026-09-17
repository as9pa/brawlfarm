"""Card geometry and the horizontal scroll of the BRAWLERS grid: the mapping from an OCR
name line to the card centre it belongs to (_visible_cards) and the two swipes that move
the column-major grid (_scroll_grid).

Nothing here reads a screen or runs OCR: the line boxes are hand-written from the session
2 measurements, and the coordinates are spelled out rather than read from config so that a
calibration edit has to come through this file too."""

from __future__ import annotations

import pytest

from brawlfarm.core import brawlers

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
