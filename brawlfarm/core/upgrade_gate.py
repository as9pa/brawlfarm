"""The auto-upgrade decision: one pure function, no screen and no adb.

The tap path this guards does not exist and cannot exist yet. CONTRIBUTING.md lists
Upgrade in the never-tap set, and that rule is only narrowed in an owner-approved pull
request that says so (phase 9 spec, feature 3). This module ships first and alone so the
decision is written, tested and reviewable before anything can press a button that spends
coins. Nothing imports it yet.

Every reading is optional because every one of them comes from OCR or from a color check
that can fail, and a failed read is never a zero. Every ambiguous input is a no: an
unparsed cost, a missing power-point line, a price chip that is not clearly coin gold, or
any trace of gem purple. There is no branch that answers True without the gold check
passing and the purple check failing, which is how "never gems" is enforced here rather
than promised.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Reading:
    """What READ managed to get off the brawler detail screen.

    The defaults are the refusing ones: a Reading nobody filled in says "nothing was read,
    the chip is not gold, and there might be purple in it", so a caller that forgets a
    field gets a no instead of an upgrade.
    """

    power_points: int | None = None
    power_points_needed: int | None = None
    coins: int | None = None
    cost: int | None = None
    gold_chip: bool = False  # the price chip's coin-gold fraction cleared its band
    purple_chip: bool = True  # the gem-purple fraction is NOT near zero


def should_upgrade(
    reading: Reading,
    *,
    auto_upgrade: bool,
    coin_floor: int = 0,
    done_this_session: bool = False,
) -> bool:
    """True only when every condition holds: the setting is on, no upgrade has been done
    this session, the chip is coin gold and not gem purple, all four numbers were read,
    none of them is nonsense, the power points are there, and paying the cost still leaves
    ``coin_floor`` coins behind."""
    if not auto_upgrade or done_this_session:
        return False
    if not reading.gold_chip or reading.purple_chip:
        return False
    points, needed = reading.power_points, reading.power_points_needed
    coins, cost = reading.coins, reading.cost
    if points is None or needed is None or coins is None or cost is None:
        return False
    # A negative anywhere is a misread digit or a caller passing a discount as a floor.
    if min(points, needed, coins, cost, coin_floor) < 0:
        return False
    if needed <= 0 or cost <= 0:
        return False
    if points < needed:
        return False
    return coins - cost >= coin_floor
