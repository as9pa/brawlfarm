"""The quests-screen sweep: scripted OCR pages in, the session's quest cards out.

Nothing here reads a screen or runs OCR. The pages are hand-written at the session 2
centres, and the swipe and the tap coordinates are spelled out rather than read from
config, so a calibration edit has to come through this file too.

The rail these tests hold: the sweep READS and SWIPES, it never taps, and no swipe
endpoint leaves the card lane (the reroll button sits at y 167, well above it).
"""

from __future__ import annotations

from brawlfarm.core import config, quests

# Two cards in row 1, a card pitch apart, both clear of the region edges.
CARD_CX = (400, 871)
TITLE_CY = 300  # inside QUEST_TITLE_BAND0 (250, 356)
PROGRESS_CY = 390  # inside QUEST_PROGRESS_BAND0 (362, 420)

LANE_Y = (225, 860)  # QUEST_LIST_REGION's rows
LANE_X_MIN = 250  # left of this the grid gives way to the mega-quest column

# Stands in for the BGR frame adb.screencap returns; every read of it is patched out.
SCREEN = object()


def _page(*titles: str) -> list[tuple[str, float, tuple[int, int]]]:
    """One OCR page shaped like vision.read_lines_boxes gives it: text, confidence, centre.
    Each title gets an unfinished progress token so group_cards keeps its card."""
    lines: list[tuple[str, float, tuple[int, int]]] = []
    for cx, title in zip(CARD_CX, titles, strict=False):
        lines.append((title, 0.99, (cx, TITLE_CY)))
        lines.append(("0/5", 0.99, (cx, PROGRESS_CY)))
    return lines


def _script(monkeypatch, pages) -> dict:
    """Drive the sweep over `pages` scripted OCR pages and record what it did. Reads past
    the end of the script get the last page again, which is how a repeat is scripted."""
    state: dict = {"reads": 0, "swipes": [], "taps": [], "logs": []}

    def read_lines_boxes(screen, region=None):
        page = pages[min(state["reads"], len(pages) - 1)]
        state["reads"] += 1
        return page

    monkeypatch.setattr(quests.adb, "screencap", lambda: SCREEN)
    monkeypatch.setattr(quests.adb, "swipe", lambda *a: state["swipes"].append(a))
    monkeypatch.setattr(quests.adb, "tap", lambda *a: state["taps"].append(a))
    monkeypatch.setattr(quests.vision, "read_lines_boxes", read_lines_boxes)
    monkeypatch.setattr(quests.time, "sleep", lambda s: None)
    return state


def test_the_sweep_returns_the_union_of_its_pages_without_duplicates(monkeypatch) -> None:
    pages = [
        _page("WIN 5 BATTLES WITH NITA", "WIN 3 BATTLES WITH PAM"),
        _page("WIN 3 BATTLES WITH PAM", "DEAL 20000 DAMAGE WITH SHELLY"),
    ]
    _script(monkeypatch, pages)
    assert quests.read_quest_lines(lambda m: None) == [
        "WIN 5 BATTLES WITH NITA",
        "WIN 3 BATTLES WITH PAM",
        "DEAL 20000 DAMAGE WITH SHELLY",
    ]


def test_the_sweep_stops_on_the_repeated_page_before_the_budget(monkeypatch) -> None:
    pages = [
        _page("WIN 5 BATTLES WITH NITA"),
        _page("WIN 3 BATTLES WITH PAM"),
    ]
    state = _script(monkeypatch, pages)
    quests.read_quest_lines(lambda m: None)
    # Page 3 repeats page 2, so the sweep ends there: 3 reads, 2 page turns, not 10.
    assert config.QUEST_SWEEP_MAX == 10
    assert (state["reads"], len(state["swipes"])) == (3, 2)


def test_every_page_turn_is_the_calibrated_lane_drag(monkeypatch) -> None:
    pages = [
        _page("WIN 5 BATTLES WITH NITA"),
        _page("WIN 3 BATTLES WITH PAM"),
    ]
    state = _script(monkeypatch, pages)
    quests.read_quest_lines(lambda m: None)
    assert state["swipes"] == [(1250, 470, 650, 470, 600)] * 2
    for x1, y1, x2, y2, _ms in state["swipes"]:
        assert LANE_Y[0] <= y1 <= LANE_Y[1] and LANE_Y[0] <= y2 <= LANE_Y[1]
        assert x1 >= LANE_X_MIN and x2 >= LANE_X_MIN


def test_a_grid_that_never_repeats_stops_at_the_sweep_budget(monkeypatch) -> None:
    pages = [_page(f"WIN {n} BATTLES WITH NITA") for n in range(1, 13)]
    state = _script(monkeypatch, pages)
    cards = quests.read_quest_lines(lambda m: None)
    assert state["reads"] == config.QUEST_SWEEP_MAX
    assert len(cards) == config.QUEST_SWEEP_MAX


def test_the_sweep_only_reads_and_swipes(monkeypatch) -> None:
    state = _script(monkeypatch, [_page("WIN 5 BATTLES WITH NITA")])
    quests.read_quest_lines(lambda m: None)
    assert state["taps"] == []


def test_an_empty_read_returns_nothing_and_logs_the_tripwire(monkeypatch) -> None:
    """A page of placeholder '?' cards OCRs to nothing: an empty page, not an error."""
    state = _script(monkeypatch, [[]])
    logs: list[str] = []
    assert quests.read_quest_lines(logs.append) == []
    assert logs == ["[quests] read 0 quest cards over 2 pages"]
    assert state["reads"] == 2  # the second empty page repeats the first, so the sweep ends


def _visit_seams(monkeypatch, *, screen_opens: bool, has_mega: bool) -> dict:
    """The quests screen as `visit` and `activate_new_mega_quest` see it, minus the sweep."""
    state: dict = {"taps": [], "exits": 0, "logs": []}
    monkeypatch.setattr(quests.adb, "screencap", lambda: SCREEN)
    monkeypatch.setattr(quests.adb, "tap", lambda *a: state["taps"].append(a))
    monkeypatch.setattr(quests.time, "sleep", lambda s: None)
    monkeypatch.setattr(quests, "_on_quests_screen", lambda screen: screen_opens)
    monkeypatch.setattr(quests, "_has_new_mega_card", lambda screen: has_mega)
    monkeypatch.setattr(quests, "_exit_to_menu", lambda: state.update(exits=state["exits"] + 1))
    return state


def test_visit_returns_the_cards_it_read_and_still_exits_to_the_menu(monkeypatch) -> None:
    state = _visit_seams(monkeypatch, screen_opens=True, has_mega=True)
    monkeypatch.setattr(quests, "read_quest_lines", lambda log: ["WIN 5 BATTLES WITH NITA"])
    assert quests.visit(state["logs"].append) == (["WIN 5 BATTLES WITH NITA"], True)
    # The QUESTS button and the mega card, and nothing inside the grid.
    assert state["taps"] == [(340, 852), (312, 540)]
    assert state["exits"] == 1


def test_visit_reads_nothing_when_the_quests_screen_never_opens(monkeypatch) -> None:
    state = _visit_seams(monkeypatch, screen_opens=False, has_mega=True)
    monkeypatch.setattr(quests, "read_quest_lines", lambda log: ["WIN 5 BATTLES WITH NITA"])
    assert quests.visit(state["logs"].append) == ([], False)
    assert state["taps"] == [(340, 852)]
    assert state["exits"] == 1


def test_visit_reports_no_activation_when_no_card_is_offered(monkeypatch) -> None:
    """The caller logs the mega_quest feed row for this visit, so it has to be told the
    truth: cards read, nothing activated."""
    state = _visit_seams(monkeypatch, screen_opens=True, has_mega=False)
    monkeypatch.setattr(quests, "read_quest_lines", lambda log: ["WIN 5 BATTLES WITH NITA"])
    assert quests.visit(state["logs"].append) == (["WIN 5 BATTLES WITH NITA"], False)
    assert state["taps"] == [(340, 852)]  # the QUESTS button only: no card to tap
    assert state["exits"] == 1


def test_activate_new_mega_quest_still_taps_the_card_and_reports_it(monkeypatch) -> None:
    """The refactor that gave `visit` the open and the activation kept this entry point."""
    state = _visit_seams(monkeypatch, screen_opens=True, has_mega=True)
    assert quests.activate_new_mega_quest(state["logs"].append) is True
    assert state["taps"] == [(340, 852), (312, 540)]
    assert state["exits"] == 1


def test_activate_new_mega_quest_with_no_card_taps_nothing_further(monkeypatch) -> None:
    state = _visit_seams(monkeypatch, screen_opens=True, has_mega=False)
    assert quests.activate_new_mega_quest(state["logs"].append) is False
    assert state["taps"] == [(340, 852)]
    assert state["exits"] == 1
