"""The pure half of the quest-aware pick: OCR lines in, a brawler name or None out.

Every line here is hand-typed, including the mangled ones and the centres, because the
only quests-screen recording so far is half size. Nothing in this file reads a screen, and
nothing it tests can."""

from __future__ import annotations

from brawlfarm.core import brawlers, questpick

OWNED = ["Shelly", "El Primo", "8-Bit", "Larry & Lawrie"]


def _line(text: str, cx: int, cy: int) -> tuple[str, float, tuple[int, int]]:
    """One entry shaped like vision.read_lines_boxes gives it: text, confidence, centre."""
    return (text, 0.99, (cx, cy))


def test_a_cards_title_lines_join_in_cy_order() -> None:
    lines = [
        _line("WITH NITA,", 400, 320),
        _line("WIN 5 BATTLES", 400, 300),
        _line("PAM OR MINA", 400, 340),
    ]
    assert questpick.group_cards(lines) == ["WIN 5 BATTLES WITH NITA, PAM OR MINA"]


def test_two_cards_a_card_pitch_apart_stay_separate() -> None:
    lines = [
        _line("WIN 5 BATTLES WITH NITA", 400, 300),
        _line("WIN 3 BATTLES WITH PAM", 857, 300),
    ]
    assert questpick.group_cards(lines) == [
        "WIN 5 BATTLES WITH NITA",
        "WIN 3 BATTLES WITH PAM",
    ]


def test_a_card_whose_progress_is_finished_is_dropped() -> None:
    """Rows come back top to bottom, cards left to right, and no title carries its token."""
    lines = [
        _line("WIN 5 BATTLES WITH NITA", 400, 300),
        _line("8 / 8", 400, 400),
        _line("WIN 3 BATTLES WITH PAM", 857, 300),
        _line("0/5", 857, 400),
        _line("DEAL 20000 DAMAGE WITH SHELLY", 400, 513),
        _line("5/5", 400, 613),
        _line("WIN 2 BATTLES WITH EDGAR", 857, 513),
        _line("7 / 24", 857, 613),
    ]
    assert questpick.group_cards(lines) == [
        "WIN 3 BATTLES WITH PAM",
        "WIN 2 BATTLES WITH EDGAR",
    ]


def test_a_progress_token_further_than_half_a_pitch_belongs_to_no_card() -> None:
    lines = [
        _line("WIN 5 BATTLES WITH NITA", 400, 300),
        _line("8/8", 857, 400),
    ]
    assert questpick.group_cards(lines) == ["WIN 5 BATTLES WITH NITA"]


def test_a_card_cut_off_by_a_region_edge_is_dropped() -> None:
    lines = [
        _line("TTLES WITH NITA", 96, 300),
        _line("WIN 3 BATTLES WITH PAM", 800, 300),
        _line("WIN 2 BATTLES WI", 1490, 300),
    ]
    assert questpick.group_cards(lines) == ["WIN 3 BATTLES WITH PAM"]


def test_a_line_in_no_row_band_is_ignored() -> None:
    lines = [
        _line("QUESTS", 800, 240),
        _line("WIN 5 BATTLES WITH NITA", 800, 300),
        _line("BRAWL PASS", 800, 440),
    ]
    assert questpick.group_cards(lines) == ["WIN 5 BATTLES WITH NITA"]


def test_no_lines_at_all_group_into_no_cards() -> None:
    assert questpick.group_cards([]) == []


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


def test_resolve_takes_the_first_owned_candidate_when_a_quest_names_several() -> None:
    quests = questpick.parse(["Win 5 battles with Crow, El Primo or Shelly"])
    assert questpick.resolve(quests, OWNED) == "El Primo"


def test_resolve_prefers_the_named_brawler_over_the_lowest_trophy_one() -> None:
    quests = questpick.parse(["Win 5 battles with Shelly, El Primo or 8-Bit"])
    trophies = {"SHELLY": 200, "ELPRIMO": 900, "8BIT": 400}
    assert questpick.resolve(quests, OWNED, trophies, prefer="el primo") == "El Primo"


def test_resolve_ignores_a_preferred_name_the_quest_does_not_list() -> None:
    quests = questpick.parse(["Win 5 battles with Shelly or El Primo"])
    trophies = {"SHELLY": 800, "ELPRIMO": 100}
    assert questpick.resolve(quests, OWNED, trophies, prefer="Crow") == "El Primo"


def test_resolve_takes_the_lowest_trophy_owned_candidate() -> None:
    quests = questpick.parse(["Win 5 battles with Shelly, El Primo or 8-Bit"])
    trophies = {"SHELLY": 640, "ELPRIMO": 300, "8BIT": 720}
    assert questpick.resolve(quests, OWNED, trophies) == "El Primo"


def test_resolve_breaks_a_trophy_tie_by_candidate_order() -> None:
    quests = questpick.parse(["Win 5 battles with 8-Bit, Shelly or El Primo"])
    trophies = {"SHELLY": 500, "ELPRIMO": 500, "8BIT": 500}
    assert questpick.resolve(quests, OWNED, trophies) == "8-Bit"


def test_resolve_counts_a_candidate_the_trophy_map_misses_as_zero() -> None:
    quests = questpick.parse(["Win 5 battles with Shelly or El Primo"])
    assert questpick.resolve(quests, OWNED, {"SHELLY": 300}) == "El Primo"


def test_resolve_falls_through_to_the_next_quest_it_can_farm() -> None:
    quests = questpick.parse(["Win 5 battles with Crow or Mina", "Win 2 battles with Shelly"])
    assert questpick.resolve(quests, OWNED, {"SHELLY": 900}) == "Shelly"


def test_resolve_skips_class_and_mode_quests_even_with_a_preference() -> None:
    """A preference never revives a quest the bot cannot farm."""
    quests = questpick.parse(["Deal 20000 damage with Tanks", "Play 8 battles in Gem Grab"])
    assert questpick.resolve(quests, OWNED, {"TANKS": 0, "GEMGRAB": 0}, prefer="Tanks") is None


def test_name_normalization_matches_the_brawler_screens() -> None:
    """questpick keeps its own copy so it stays import-light; the two must not drift."""
    for name in ("EL PRIMO", "8-BIT", "LARRY & LAWRIE", "Shelly", None):
        assert questpick.norm_name(name) == brawlers._norm(name)


# One sweep of the live quests screen on 2026-09-17, exactly as OCR handed the cards back:
# the styled 5 read as S, the 1 as I, the 0 as O, and the spaces went missing wherever they
# felt like it. Kept verbatim so a parser change that only suits tidy text fails here.
LIVE_CARDS = [
    "GAIN 3O TROPHIES",
    "DEAL300000POINTSOF DAMAGE",
    "DEAL6000O POINTSOF DAMAGE",
    "XP 1500",
    "VS",
    "PLAY6BATTLES",
    "PLAY S MATCHESIN A TEAM",
    "DEFEAT24ENEMIES",
    "PLAYSMATCHESINA TEAM",
    "DEAL160000POINTSOF DAMAGE",
    "DEAL160000 P0INTS0F DAMAGE",
    "PLAY16BATTLES",
    "DEAL160000 P0INTSOF DAMAGE",
    "WIN S BATTLES IN RANKED",
    "DEAL160000 P0INTS OF DAMAGE",
    "WIN S BATTLES WITH GALE,BYRON OR MINA",
    "WIN S BATTLES WITH NITA, PAm OR MINA",
    "DEAL100000 POINTS OF DAMAGE WITH BONNIE, MEEPLE OR FINX",
    "WINSBATTLES IN RANKED",
    "WIN S BATTLES WITH PAM,LOLA OR MEEPLE",
    "WIN S BATTLES WITH MORTIS,DARRYL OR BUZZ",
    "WIN S BATTLES WIth gale, Byron Or MINA",
    "WIN 5 BATTLES WITH SPIKE,EDGAR OR JAE-YONG",
    "DEFEAT24ENEMIES IN GEMGRAB ORANY SHOWDOWN",
    "DEAL100000 P0INTSOF DAMAGE WITH BONNIE,MEEPLEOR FINX",
    "WIN S BATTLES WIth leOn, SurgE OR FINX",
    "WIN S BATTLES IN GEM GRAB ORANY SHOWDOWN",
    "WIN S BATTLES WITh MORTIS,DARRYL OR BUZZ",
    "DEFEAT1SENEMIES IN BRAWL BALLORANY SHOWDOWN",
    "DEFEAT15ENEMIES ONMOGMOHS N NI BASKET BRAWL",
    "WIN S BATTLES WITHSPIKE,EDGAR OR JAE-YONG",
    "WINSBATTLES IN ANY SHOWDOWN OR HOT ZONE",
    "WIN S BATTLES WIth leOn, SuRgE Or FINX",
    "WIN S BATTLES IN GEM GRAB OR ANY SHOWDOWN",
    "WIN S BATTLES IN ANY SHOWDOWN",
    "DEFEAT15ENEMIES IN BRAWL BALLORANY SHOWDOWN",
    "DEAL100000 P0INTS OF DAMAGE IN HOT ZONE",
    "WIN 8 BATTLES",
    "DEAL100000 POINTSOF DAMAGE IN HOT ZONE",
    "GAIN 8O TROPHIES",
    "WIN 5 BATTLES IN RANKED",
    "WIN8BATTLES",
    "WIN S BATTLES WITH BROCK,BUZZOR CLANCY",
    "WIN S BATTLES WITH DARRYL, NANI OR NORI",
    "WIN 5BATTLES IN GEM GRAB OR ANY SHOWDOWN",
    "WIN S BATTLES WITH FRANK,CLANCYOR NORI",
    "DEFEAT15ENEMIES IN BRAWL BALL OR ANY SHOWDOWN",
    "DEFEAT1SENEMIES WITH SPIKE,DRACO OR JUJU",
    "WINSBATTLES IN ANY SHOWDOWN OR BRAWL HOCKEY",
]

# Every brawler quest the sweep held, in screen order. Five cards were read twice because
# the screen shows the same quest on more than one row, so sixteen readings of fourteen
# quest shapes come out.
LIVE_BRAWLER_QUESTS = [
    (("GALE", "BYRON", "MINA"), 5),
    (("NITA", "PAM", "MINA"), 5),
    (("BONNIE", "MEEPLE", "FINX"), 100000),
    (("PAM", "LOLA", "MEEPLE"), 5),
    (("MORTIS", "DARRYL", "BUZZ"), 5),
    (("GALE", "BYRON", "MINA"), 5),
    (("SPIKE", "EDGAR", "JAEYONG"), 5),
    (("BONNIE", "MEEPLE", "FINX"), 100000),
    (("LEON", "SURGE", "FINX"), 5),
    (("MORTIS", "DARRYL", "BUZZ"), 5),
    (("SPIKE", "EDGAR", "JAEYONG"), 5),
    (("LEON", "SURGE", "FINX"), 5),
    (("BROCK", "BUZZ", "CLANCY"), 5),
    (("DARRYL", "NANI", "NORI"), 5),
    (("FRANK", "CLANCY", "NORI"), 5),
    (("SPIKE", "DRACO", "JUJU"), 15),
]


def test_the_live_sweep_reads_every_brawler_quest_it_held() -> None:
    quests = questpick.parse(LIVE_CARDS)
    assert [(quest.candidates, quest.count) for quest in quests] == LIVE_BRAWLER_QUESTS
    assert all(quest.kind == questpick.KIND_BRAWLER for quest in quests)


def test_a_count_the_font_styled_into_letters_folds_back_to_digits() -> None:
    """S is 5, I is 1, O is 0: normalize folds those digits to letters inside a mixed word
    on purpose, so the matchers take either and fold the count back the other way."""
    lines = [
        "WIN S BATTLES WITH NITA",
        "DEFEAT1SENEMIES WITH SPIKE",
        "DEAL100000 POINTS OF DAMAGE WITH BONNIE",
    ]
    assert [quest.count for quest in questpick.parse(lines)] == [5, 15, 100000]


def test_a_count_glued_to_its_keyword_and_its_noun_still_reads() -> None:
    """A glued WINSBATTLES is WIN, a count of S and BATTLES: backtracking hands the B back."""
    (quest,) = questpick.parse(["WINSBATTLES WITH NITA, PAM OR MINA"])
    assert (quest.count, quest.candidates) == (5, ("NITA", "PAM", "MINA"))


def test_a_name_glued_to_with_still_reads() -> None:
    (quest,) = questpick.parse(["WIN S BATTLES WITHSPIKE,EDGAR OR JAE-YONG"])
    assert quest.candidates == ("SPIKE", "EDGAR", "JAEYONG")


def test_an_or_glued_to_the_name_before_it_still_splits() -> None:
    lines = [
        "WIN S BATTLES WITH BROCK,BUZZOR CLANCY",
        "DEAL100000 P0INTSOF DAMAGE WITH BONNIE,MEEPLEOR FINX",
        "WIN S BATTLES WITH FRANK,CLANCYOR NORI",
    ]
    assert [quest.candidates for quest in questpick.parse(lines)] == [
        ("BROCK", "BUZZ", "CLANCY"),
        ("BONNIE", "MEEPLE", "FINX"),
        ("FRANK", "CLANCY", "NORI"),
    ]


def test_a_name_with_or_inside_it_keeps_it() -> None:
    """The glued-OR split only fires at the end of a token, so these names stay whole."""
    (quest,) = questpick.parse(["WIN S BATTLES WITH MORTIS, CORDELIUS OR NORI"])
    assert quest.candidates == ("MORTIS", "CORDELIUS", "NORI")


def test_defeat_enemies_with_named_brawlers_is_a_brawler_quest() -> None:
    (quest,) = questpick.parse(["DEFEAT1SENEMIES WITH SPIKE,DRACO OR JUJU"])
    assert quest.kind == questpick.KIND_BRAWLER
    assert (quest.candidates, quest.count) == (("SPIKE", "DRACO", "JUJU"), 15)


def test_defeat_enemies_with_a_class_is_a_class_quest() -> None:
    (quest,) = questpick.parse(["DEFEAT 15 ENEMIES WITH TANKS"])
    assert (quest.kind, quest.target) == (questpick.KIND_CLASS, "TANKS")


def test_a_defeat_quest_that_names_nobody_is_dropped() -> None:
    """A defeat row with no WITH names a mode, and the bot cannot pick a mode."""
    lines = [
        "DEFEAT24ENEMIES IN GEMGRAB ORANY SHOWDOWN",
        "DEFEAT1SENEMIES IN BRAWL BALLORANY SHOWDOWN",
        "DEFEAT15ENEMIES ONMOGMOHS N NI BASKET BRAWL",
    ]
    assert questpick.parse(lines) == []


def test_a_card_the_ocr_read_in_mixed_case_still_reads() -> None:
    (quest,) = questpick.parse(["WIN S BATTLES WIth leOn, SurgE OR FINX"])
    assert (quest.count, quest.candidates) == (5, ("LEON", "SURGE", "FINX"))


def test_a_non_ascii_glyph_is_noise_not_a_crash() -> None:
    """One live card held a CJK glyph inside its title. Nothing here may raise on it."""
    noisy = 'USE "PLAY AGAIN"图10 TIMES'
    assert questpick.normalize(noisy)
    assert questpick.parse([noisy]) == []


def test_resolve_over_the_live_cards_takes_the_lowest_trophy_owned_brawler() -> None:
    """The first live quest naming anything owned is the SPIKE, EDGAR or JAE-YONG one, and
    the lowest-trophy rule decides between the two owned names, not the screen order."""
    quests = questpick.parse(LIVE_CARDS)
    owned = ["NORI", "JAE-YONG", "SPIKE"]
    assert questpick.resolve(quests, owned, {"NORI": 0, "JAEYONG": 0, "SPIKE": 1200}) == "JAE-YONG"
    assert questpick.resolve(quests, owned, {"NORI": 0, "JAEYONG": 1200, "SPIKE": 0}) == "SPIKE"
