"""The auto-upgrade gate's truth table. Every ambiguous input is a no.

There is no tap path in the repo yet and there cannot be one until the never-tap rule in
CONTRIBUTING.md is amended in an owner-approved pull request, so this file tests a
decision and nothing that acts on it."""

from __future__ import annotations

import pytest

from brawlfarm.core import upgrade_gate


def reading(**overrides) -> upgrade_gate.Reading:
    """A reading that passes every condition, for one field at a time to be spoiled."""
    fields = {
        "power_points": 200,
        "power_points_needed": 180,
        "coins": 1500,
        "cost": 800,
        "gold_chip": True,
        "purple_chip": False,
    }
    return upgrade_gate.Reading(**{**fields, **overrides})


def test_the_happy_path_is_the_only_yes() -> None:
    assert upgrade_gate.should_upgrade(reading(), auto_upgrade=True) is True


def test_exactly_enough_of_everything_still_passes() -> None:
    r = reading(power_points=180, coins=800)
    assert upgrade_gate.should_upgrade(r, auto_upgrade=True) is True


@pytest.mark.parametrize(
    ("why", "spoiled"),
    [
        ("power points short by one", {"power_points": 179}),
        ("power points not read", {"power_points": None}),
        ("needed not read", {"power_points_needed": None}),
        ("needed is nonsense", {"power_points_needed": 0}),
        ("coins not read", {"coins": None}),
        ("coins short by one", {"coins": 799}),
        ("cost not parsed", {"cost": None}),
        ("cost is nonsense", {"cost": 0}),
        ("cost read as negative", {"cost": -800}),
        ("the price chip is not coin gold", {"gold_chip": False}),
        ("the price chip has gem purple in it", {"purple_chip": True}),
    ],
)
def test_every_ambiguous_reading_is_a_no(why: str, spoiled: dict) -> None:
    assert upgrade_gate.should_upgrade(reading(**spoiled), auto_upgrade=True) is False, why


def test_the_flag_off_is_a_no_whatever_the_screen_says() -> None:
    assert upgrade_gate.should_upgrade(reading(), auto_upgrade=False) is False


def test_one_upgrade_per_session() -> None:
    r = reading()
    assert upgrade_gate.should_upgrade(r, auto_upgrade=True, done_this_session=True) is False


def test_the_coin_floor_is_kept_whole() -> None:
    r = reading(coins=1000, cost=800)
    assert upgrade_gate.should_upgrade(r, auto_upgrade=True, coin_floor=200) is True
    assert upgrade_gate.should_upgrade(r, auto_upgrade=True, coin_floor=201) is False


def test_a_negative_coin_floor_is_a_no_not_a_discount() -> None:
    assert upgrade_gate.should_upgrade(reading(), auto_upgrade=True, coin_floor=-1000) is False


def test_a_reading_that_read_nothing_is_a_no() -> None:
    assert upgrade_gate.should_upgrade(upgrade_gate.Reading(), auto_upgrade=True) is False
