"""The pure half of the quest-aware pick: OCR lines in, a brawler name or None out.

Every line here is hand-typed, including the mangled ones, because the quests screen has
not been recorded yet. Nothing in this file reads a screen, and nothing it tests can."""

from __future__ import annotations

from brawlfarm.core import brawlers, questpick

OWNED = ["Shelly", "El Primo", "8-Bit", "Larry & Lawrie"]


def test_parses_win_n_battles_with_a_named_brawler() -> None:
    (quest,) = questpick.parse(["Win 5 battles with Shelly"])
    assert quest.kind == questpick.KIND_BRAWLER
    assert quest.target == "SHELLY"
    assert quest.count == 5


def test_parses_deal_damage_with_a_class() -> None:
    (quest,) = questpick.parse(["Deal 20,000 damage with Damage Dealers"])
    assert quest.kind == questpick.KIND_CLASS
    assert quest.target == "DAMAGEDEALERS"
    assert quest.count == 20000


def test_parses_play_n_battles_in_a_mode() -> None:
    (quest,) = questpick.parse(["Play 8 battles in Gem Grab"])
    assert quest.kind == questpick.KIND_MODE
    assert quest.target == "GEMGRAB"
    assert quest.count == 8


def test_deal_damage_with_a_named_brawler_is_a_brawler_quest() -> None:
    (quest,) = questpick.parse(["Deal 12000 damage with El Primo"])
    assert (quest.kind, quest.target) == (questpick.KIND_BRAWLER, "ELPRIMO")


def test_mangled_ocr_still_reads() -> None:
    lines = ["W1N 5 BATTLE5 W1TH 5HELLY", "Win 3 battles with  8-BIT!"]
    assert [(q.target, q.count) for q in questpick.parse(lines)] == [("SHELLY", 5), ("8BIT", 3)]


def test_a_claimed_row_is_never_a_quest() -> None:
    lines = ["Win 5 battles with Shelly  CLAIMED", "Win 2 battles with El Primo"]
    assert [q.target for q in questpick.parse(lines)] == ["ELPRIMO"]


def test_lines_it_does_not_understand_are_dropped() -> None:
    assert questpick.parse(["QUESTS", "", "Collect 3 star points", "Win battles with"]) == []


def test_parses_every_brawler_a_quest_names() -> None:
    lines = [
        "WIN 5 BATTLES WITH NITA, PAM OR MINA",
        "WIN 5 BATTLES WITH PAM, LOLA OR MEEPLE",
        "WIN 5 BATTLES WITH SPIKE, EDGAR OR JAE-YONG",
        "WIN 5 BATTLES WITH MORTIS, DARRYL OR BUZZ",
        "WIN 5 BATTLES WITH LEON, SURGE OR FINX",
        "WIN 5 BATTLES WITH GALE, BYRON OR MINA",
    ]
    quests = questpick.parse(lines)
    assert [quest.candidates for quest in quests] == [
        ("NITA", "PAM", "MINA"),
        ("PAM", "LOLA", "MEEPLE"),
        ("SPIKE", "EDGAR", "JAEYONG"),
        ("MORTIS", "DARRYL", "BUZZ"),
        ("LEON", "SURGE", "FINX"),
        ("GALE", "BYRON", "MINA"),
    ]
    assert [(quest.kind, quest.count) for quest in quests] == [(questpick.KIND_BRAWLER, 5)] * 6


def test_target_is_the_first_candidate() -> None:
    (quest,) = questpick.parse(["Win 5 battles with Shelly"])
    assert quest.candidates == ("SHELLY",)
    assert quest.target == quest.candidates[0]


def test_parses_points_of_damage_with_several_brawlers() -> None:
    (quest,) = questpick.parse(["DEAL 100,000 POINTS OF DAMAGE WITH BONNIE, MEEPLE OR FINX"])
    assert quest.kind == questpick.KIND_BRAWLER
    assert quest.candidates == ("BONNIE", "MEEPLE", "FINX")
    assert quest.count == 100000


def test_a_damage_quest_that_names_nobody_is_dropped() -> None:
    assert questpick.parse(["DEAL 160,000 POINTS OF DAMAGE"]) == []


def test_a_class_among_the_candidates_makes_it_a_class_quest() -> None:
    (quest,) = questpick.parse(["Win 5 battles with Tanks or Assassins"])
    assert quest.kind == questpick.KIND_CLASS
    assert quest.candidates == ("TANKS", "ASSASSINS")


def test_quests_the_bot_cannot_farm_are_dropped() -> None:
    lines = [
        "DEFEAT 24 ENEMIES",
        "DEFEAT 15 ENEMIES IN BRAWL BALL OR ANY SHOWDOWN",
        "PLAY 6 BATTLES",
        "PLAY 5 MATCHES IN A TEAM",
        'USE "PLAY AGAIN" 10 TIMES',
    ]
    assert questpick.parse(lines) == []


def test_resolve_returns_the_rosters_own_spelling() -> None:
    quests = questpick.parse(["Win 5 battles with LARRY AND LAWRIE", "Win 2 battles with Shelly"])
    assert questpick.resolve(quests, OWNED) == "Shelly"


def test_resolve_skips_a_brawler_that_is_not_owned() -> None:
    quests = questpick.parse(["Win 5 battles with Crow"])
    assert questpick.resolve(quests, OWNED) is None


def test_resolve_answers_none_for_a_class_quest() -> None:
    quests = questpick.parse(["Deal 20000 damage with Tanks"])
    assert questpick.resolve(quests, OWNED) is None


def test_resolve_answers_none_for_a_mode_quest() -> None:
    quests = questpick.parse(["Play 8 battles in Gem Grab"])
    assert questpick.resolve(quests, OWNED) is None


def test_resolve_answers_none_for_nothing_at_all() -> None:
    assert questpick.resolve([], OWNED) is None


def test_name_normalization_matches_the_brawler_screens() -> None:
    """questpick keeps its own copy so it stays import-light; the two must not drift."""
    for name in ("EL PRIMO", "8-BIT", "LARRY & LAWRIE", "Shelly", None):
        assert questpick.norm_name(name) == brawlers._norm(name)
