"""farmplan.plan_queue: the three brawlers the Instance screen lists under "Next in
queue". A preview of the plan's own order and never a decision -- it reads no games.csv,
so choose_target's win-rate bias and rotation set cannot be moved by anything here."""

from __future__ import annotations

from brawlfarm.core import farmplan

ROSTER = [
    {"name": "NORI", "trophies": 812},
    {"name": "TARA", "trophies": 540},
    {"name": "SHELLY", "trophies": 615},
    {"name": "DYNAMIKE", "trophies": 705},
    {"name": "EDGAR", "trophies": 1000},
    {"name": "SPIKE", "trophies": 1140},
]


def _plan(**over) -> dict:
    return {**farmplan.DEFAULT_PLAN, **over}


def test_ladder_lists_the_lowest_brawlers_still_under_the_goal() -> None:
    assert farmplan.plan_queue(_plan(), ROSTER, current="NORI") == ["TARA", "SHELLY", "DYNAMIKE"]


def test_the_current_brawler_is_dropped_case_insensitively() -> None:
    assert farmplan.plan_queue(_plan(), ROSTER, current="tara") == ["SHELLY", "DYNAMIKE", "NORI"]


def test_the_goal_is_the_ceiling_and_n_is_the_length() -> None:
    assert farmplan.plan_queue(_plan(goal_trophies=700), ROSTER, current=None) == [
        "TARA",
        "SHELLY",
    ]
    assert farmplan.plan_queue(_plan(), ROSTER, current=None, n=1) == ["TARA"]


def test_a_trophy_tie_breaks_on_the_name() -> None:
    tied = [{"name": "PIPER", "trophies": 600}, {"name": "BULL", "trophies": 600}]
    assert farmplan.plan_queue(_plan(), tied, current=None) == ["BULL", "PIPER"]


def test_prestige_starts_from_the_end_the_plan_names() -> None:
    high = _plan(mode="prestige", prestige_start="highest")
    low = _plan(mode="prestige", prestige_start="lowest")
    assert farmplan.plan_queue(high, ROSTER, current="NORI") == ["DYNAMIKE", "SHELLY", "TARA"]
    assert farmplan.plan_queue(low, ROSTER, current="NORI") == ["TARA", "SHELLY", "DYNAMIKE"]


def test_prestige_never_lists_a_brawler_at_or_past_the_prestige_goal() -> None:
    low = _plan(mode="prestige", prestige_start="lowest")
    # EDGAR at exactly 1000 and SPIKE at 1140 are done; the pool is strictly under 1000.
    assert farmplan.plan_queue(low, ROSTER, current=None, n=6) == [
        "TARA",
        "SHELLY",
        "DYNAMIKE",
        "NORI",
    ]


def test_an_empty_or_nameless_roster_is_an_empty_queue() -> None:
    assert farmplan.plan_queue(_plan(), [], current="NORI") == []
    assert farmplan.plan_queue(_plan(), [{"trophies": 10}], current=None) == []


def test_the_preview_never_moves_choose_target() -> None:
    plan = _plan()
    before = farmplan.choose_target(plan, ROSTER)
    farmplan.plan_queue(plan, ROSTER, current="NORI")
    assert farmplan.choose_target(plan, ROSTER) == before
    assert ROSTER[0] == {"name": "NORI", "trophies": 812}  # the caller's list is not sorted
