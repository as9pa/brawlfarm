"""brawlfarm/core/api.py battlelog helpers — is_showdown / my_brawler across the payload
shapes the live API actually returns (r10 hardening; previously untested).

The API is the source of truth for results data, so a silent misread here
corrupts games.csv and every stat downstream. No network anywhere — these are
pure dict-shape tests; the ApiClient HTTP path is deliberately out of scope.
"""

from __future__ import annotations

from brawlfarm.core import api

MY_TAG = "#2P0YLQ9"


# --- is_showdown ----------------------------------------------------------------------


def test_is_showdown_event_mode_variants():
    # the event block is the primary source; key is a case-folded substring match
    assert api.is_showdown({"event": {"mode": "soloShowdown"}}) is True
    assert api.is_showdown({"event": {"mode": "duoShowdown"}}) is True
    assert api.is_showdown({"event": {"mode": "trioShowdown"}}) is True


def test_is_showdown_falls_back_to_battle_mode():
    # ranked/friendly entries sometimes carry mode only under battle
    assert api.is_showdown({"battle": {"mode": "soloShowdown"}}) is True
    assert api.is_showdown({"event": {}, "battle": {"mode": "duoShowdown"}}) is True


def test_is_showdown_non_showdown_modes():
    assert api.is_showdown({"event": {"mode": "gemGrab"}}) is False
    assert api.is_showdown({"event": {"mode": "brawlBall"}, "battle": {}}) is False


def test_is_showdown_missing_keys_is_false_not_a_crash():
    assert api.is_showdown({}) is False
    assert api.is_showdown({"event": {}}) is False
    assert api.is_showdown({"event": {}, "battle": {}}) is False


def test_is_showdown_tolerates_json_null_mode():
    # the API can send {"mode": null}: event's "" default then `or`-chains into
    # battle's None, and None.lower() raises. Must read as "not showdown".
    assert api.is_showdown({"event": {}, "battle": {"mode": None}}) is False
    assert api.is_showdown({"event": {"mode": None}, "battle": {"mode": None}}) is False


# --- my_brawler -----------------------------------------------------------------------


def _player(tag, name):
    return {"tag": tag, "brawler": {"name": name}}


SHOWDOWN_TEAMS = {
    "battle": {
        "teams": [
            [_player("#AAA", "COLT")],
            [_player(MY_TAG, "SHELLY")],
            [_player("#BBB", "NITA")],
        ]
    }
}

FLAT_PLAYERS = {
    "battle": {
        "players": [_player("#AAA", "COLT"), _player(MY_TAG, "JANET")],
    }
}


def test_my_brawler_finds_us_in_showdown_teams():
    assert api.my_brawler(SHOWDOWN_TEAMS, MY_TAG) == "SHELLY"


def test_my_brawler_finds_us_in_a_flat_players_list():
    assert api.my_brawler(FLAT_PLAYERS, MY_TAG) == "JANET"


def test_my_brawler_tag_match_is_case_insensitive():
    assert api.my_brawler(SHOWDOWN_TEAMS, MY_TAG.lower()) == "SHELLY"
    entry = {"battle": {"players": [_player(MY_TAG.lower(), "JANET")]}}
    assert api.my_brawler(entry, MY_TAG) == "JANET"


def test_my_brawler_absent_when_we_are_not_in_the_entry():
    assert (
        api.my_brawler({"battle": {"teams": [[_player("#AAA", "COLT")]]}}, MY_TAG)
        is None
    )


def test_my_brawler_missing_keys_degrade_to_none():
    assert api.my_brawler({}, MY_TAG) is None
    assert api.my_brawler({"battle": {}}, MY_TAG) is None
    # JSON-null containers (seen on in-progress entries) must not crash
    assert api.my_brawler({"battle": {"teams": None, "players": None}}, MY_TAG) is None


def test_my_brawler_player_without_a_brawler_block_is_skipped():
    # tag matches but there's no brawler payload -> None, not a KeyError
    entry = {"battle": {"players": [{"tag": MY_TAG}]}}
    assert api.my_brawler(entry, MY_TAG) is None
