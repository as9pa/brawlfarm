"""Tests for the win-rate model v2 (r8, docs/research/winrate-model.md):
empirical-Bayes shrinkage, recency-weighted EWMA, and opportunity-cost rotation.

The SURFACE is unchanged (choose_target signature, WINRATE_AWARE kill-switch,
WINRATE_MARGIN gate, prestige untouched) — those invariants are covered by
test_farmplan_winrate.py; here we pin the v2 STATISTICS and the new rotation
trigger, plus the fail-open paths.
"""

import csv
import math

from brawlfarm.core import config, farmplan


def _bs(*pairs):
    return [{"name": n, "trophies": t} for n, t in pairs]


def _write_games(tmp_path, rows):
    """rows = (brawler, trophyChange, is_showdown) in chronological order."""
    p = tmp_path / "games.csv"
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["battleTime", "brawler", "trophyChange", "is_showdown"])
        w.writeheader()
        for i, (brawler, tc, sd) in enumerate(rows):
            w.writerow(
                {
                    "battleTime": f"20260610T10{i:04d}.000Z",
                    "brawler": brawler,
                    "trophyChange": tc,
                    "is_showdown": sd,
                }
            )
    return tmp_path


def _on(monkeypatch):
    monkeypatch.setattr(config, "WINRATE_AWARE", True)


def _opp(monkeypatch):
    """Enable BOTH win-rate awareness and opportunity-cost rotation. The latter is
    OFF by default since 2026-06-14 (config.WINRATE_OPPORTUNITY_COST) because it
    thrashed near-maxed rosters; these tests turn it back on to pin the band /
    mean / alternative LOGIC (not just the kill-switch)."""
    monkeypatch.setattr(config, "WINRATE_AWARE", True)
    monkeypatch.setattr(config, "WINRATE_OPPORTUNITY_COST", True)


# --- _shrink: empirical-Bayes posterior mean -------------------------------------


def test_shrink_pure_prior_at_zero_samples():
    assert farmplan._shrink(99.0, 0.0, mu0=2.0, k=10.0) == 2.0  # n=0 -> all prior


def test_shrink_midpoint_at_n_equals_k():
    # n == k -> exactly halfway between own rate and the prior
    assert farmplan._shrink(8.0, 10.0, mu0=2.0, k=10.0) == (8.0 + 2.0) / 2


def test_shrink_approaches_own_rate_with_many_games():
    far = farmplan._shrink(8.0, 1000.0, mu0=2.0, k=10.0)
    assert abs(far - 8.0) < 0.1  # n >> k -> basically the brawler's own rate


def test_shrink_degenerate_guard():
    assert farmplan._shrink(5.0, 0.0, mu0=1.5, k=0.0) == 1.5  # n+k==0 -> prior


# --- _ewma: recency weighting ----------------------------------------------------


def test_ewma_constant_series_is_that_constant():
    mean, neff = farmplan._ewma([3, 3, 3, 3], halflife=25)
    assert math.isclose(mean, 3.0)
    assert neff > 0


def test_ewma_weights_recent_games_more():
    # newest games are +10, older are -10; the EWMA must lean POSITIVE
    changes = [-10] * 20 + [10] * 20  # oldest-first
    mean, _ = farmplan._ewma(changes, halflife=25)
    assert mean > 0


def test_ewma_halflife_weighting_is_exact():
    # two games: newest=4 (weight 1), older=0 (weight 0.5^(1/hl)). With hl such
    # that the older weight is exactly 0.5 (hl=1): mean = (1*4 + 0.5*0)/(1.5) = 8/3
    mean, neff = farmplan._ewma([0, 4], halflife=1)
    assert math.isclose(mean, (1 * 4 + 0.5 * 0) / 1.5)
    assert math.isclose(neff, 1.5)


def test_ewma_empty():
    assert farmplan._ewma([], halflife=25) == (0.0, 0.0)


# --- shrunk_rates + mu0 ----------------------------------------------------------


def test_shrunk_rates_missing_csv():
    rates, mu0 = farmplan.shrunk_rates(data_dir="/no/such/dir")
    assert rates == {} and mu0 is None


def test_shrunk_rates_small_sample_pulled_toward_prior(tmp_path, monkeypatch):
    # 3 stellar CROW games, a long +1 baseline from others -> CROW's shrunk rate
    # sits FAR below its raw +9 (small sample pulled toward the ~+1 account mean)
    rows = [("CROW", 9, "True")] * 3 + [("BASE", 1, "True")] * 40
    d = _write_games(tmp_path, rows)
    rates, mu0 = farmplan.shrunk_rates(data_dir=d)
    assert mu0 is not None
    assert rates["CROW"] < 9.0  # shrunk down hard from the raw mean
    assert rates["CROW"] > mu0  # but still above the prior (some positive signal)


# --- v2 selection bias (kills the v1 min-sample cliff) ---------------------------


def test_tiny_streak_shrinks_inside_the_margin(tmp_path, monkeypatch):
    _on(monkeypatch)
    # HOT: 2 games modestly above a long, dominant baseline. With only ~2 effective
    # games the shrinkage pulls HOT's score almost all the way to the account mean,
    # so the gap over MINNIE stays inside the 1.0 margin -> no churn. (Demonstrates
    # the small-sample protection: a 2-game blip cannot promote.)
    rows = [("HOT", 5, "True")] * 2 + [("MINNIE", 2, "True")] * 40
    d = _write_games(tmp_path, rows)
    plan = {"mode": "ladder", "goal_trophies": 1000}
    brawlers = _bs(("MINNIE", 500), ("HOT", 550), ("HIGH", 720))
    assert farmplan.choose_target(plan, brawlers, data_dir=d) == (None, 600)


def test_well_sampled_winner_promotes(tmp_path, monkeypatch):
    _on(monkeypatch)
    # HOT: 30 games at +6, MINNIE 30 at +1. Well past the prior's pull -> promote.
    rows = [("MINNIE", 1, "True")] * 30 + [("HOT", 6, "True")] * 30
    d = _write_games(tmp_path, rows)
    plan = {"mode": "ladder", "goal_trophies": 1000}
    brawlers = _bs(("MINNIE", 500), ("HOT", 550), ("HIGH", 720))
    target, goal = farmplan.choose_target(plan, brawlers, data_dir=d)
    assert target == "HOT"
    assert goal == 600  # step goal untouched


def test_v2_kill_switch_skips_the_read(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "WINRATE_AWARE", False)

    def boom(*a, **k):
        raise AssertionError("kill switch must prevent any games.csv read")

    monkeypatch.setattr(farmplan, "_winrate_stats_v2", boom)
    rows = [("MINNIE", 1, "True")] * 30 + [("HOT", 6, "True")] * 30
    d = _write_games(tmp_path, rows)
    plan = {"mode": "ladder", "goal_trophies": 1000}
    brawlers = _bs(("MINNIE", 500), ("HOT", 550))
    assert farmplan.choose_target(plan, brawlers, data_dir=d) == (None, 600)


# --- opportunity-cost rotation ---------------------------------------------------


def test_rotation_opportunity_cost(tmp_path, monkeypatch):
    _opp(monkeypatch)
    # CUR is below the account mean and a clearly-better same-band alternative ALT
    # exists -> rotate on opportunity cost. Long histories so shrinkage is small.
    rows = [("CUR", 0, "True")] * 40
    rows += [("ALT", 6, "True")] * 40
    rows += [("FILLER", 3, "True")] * 40  # pins mu0 well above CUR's 0
    d = _write_games(tmp_path, rows)
    pool = _bs(("CUR", 520), ("ALT", 560), ("HIGH", 800))  # CUR/ALT same 500-band
    rotate, reason = farmplan.rotation_decision("CUR", pool, data_dir=d)
    assert rotate is True
    assert reason == "opportunity_cost"


def test_opportunity_cost_off_by_default(tmp_path, monkeypatch):
    # Same scenario as test_rotation_opportunity_cost, but with the DEFAULT flag
    # state (opportunity-cost OFF, owner decision 2026-06-14). A clearly-better
    # same-band alternative must NOT rotate CUR out — only the net-losing floor can.
    monkeypatch.setattr(config, "WINRATE_AWARE", True)
    monkeypatch.setattr(config, "WINRATE_OPPORTUNITY_COST", False)
    rows = [("CUR", 0, "True")] * 40
    rows += [("ALT", 6, "True")] * 40
    rows += [("FILLER", 3, "True")] * 40
    d = _write_games(tmp_path, rows)
    pool = _bs(("CUR", 520), ("ALT", 560), ("HIGH", 800))
    rotate, reason = farmplan.rotation_decision("CUR", pool, data_dir=d)
    # CUR's shrunk rate is positive (pulled toward the +3 account mean), so the
    # net-losing floor can't fire; opportunity-cost is off -> keep farming CUR.
    assert (rotate, reason) == (False, None)


def test_rotation_absolute_floor(tmp_path, monkeypatch):
    _on(monkeypatch)
    # CUR is net-losing on its shrunk rate (long negative history, prior also <0)
    rows = [("CUR", -3, "True")] * 40 + [("FILLER", -1, "True")] * 40
    d = _write_games(tmp_path, rows)
    pool = _bs(
        ("CUR", 520),
    )
    rotate, reason = farmplan.rotation_decision("CUR", pool, data_dir=d)
    assert rotate is True
    assert reason == "absolute_floor"


def test_no_rotation_when_no_better_alternative(tmp_path, monkeypatch):
    _opp(monkeypatch)
    # CUR slightly below the mean but the only same-band alternative is WORSE
    rows = [("CUR", 2, "True")] * 40
    rows += [("ALT", 1, "True")] * 40
    rows += [("FILLER", 4, "True")] * 40  # mu0 above CUR, but no better same-band alt
    d = _write_games(tmp_path, rows)
    pool = _bs(("CUR", 520), ("ALT", 560))
    rotate, reason = farmplan.rotation_decision("CUR", pool, data_dir=d)
    assert rotate is False
    assert reason is None


def test_no_rotation_when_current_above_mean(tmp_path, monkeypatch):
    _opp(monkeypatch)
    # Even with a better alternative, if CUR is at/above the account mean we keep it
    # (switching only pays when we're underperforming AND something better exists)
    rows = [("CUR", 5, "True")] * 40
    rows += [("ALT", 8, "True")] * 40
    rows += [("FILLER", 1, "True")] * 40  # mu0 below CUR's 5
    d = _write_games(tmp_path, rows)
    pool = _bs(("CUR", 520), ("ALT", 560))
    rotate, _ = farmplan.rotation_decision("CUR", pool, data_dir=d)
    assert rotate is False


def test_rotation_alternative_must_be_same_band(tmp_path, monkeypatch):
    _opp(monkeypatch)
    # ALT is far better but in a DIFFERENT trophy band -> not a candidate; CUR is
    # above the floor -> keep (respects the ladder floor invariant)
    rows = [("CUR", 1, "True")] * 40
    rows += [("ALT", 9, "True")] * 40
    rows += [("FILLER", 3, "True")] * 40
    d = _write_games(tmp_path, rows)
    pool = _bs(("CUR", 520), ("ALT", 880))  # ALT in the 800-band, not 500
    rotate, reason = farmplan.rotation_decision("CUR", pool, data_dir=d)
    assert rotate is False


def test_rotation_unseen_current_is_no_op(tmp_path, monkeypatch):
    _on(monkeypatch)
    d = _write_games(tmp_path, [("OTHER", 1, "True")] * 20)
    rotate, reason = farmplan.rotation_decision("CUR", _bs(("CUR", 520)), data_dir=d)
    assert (rotate, reason) == (False, None)


def test_rotation_missing_csv_is_no_op(tmp_path):
    rotate, reason = farmplan.rotation_decision(
        "CUR", _bs(("CUR", 520)), data_dir=tmp_path / "nope"
    )
    assert (rotate, reason) == (False, None)


def test_rotation_kill_switch(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "WINRATE_AWARE", False)

    def boom(*a, **k):
        raise AssertionError("kill switch must prevent any read")

    monkeypatch.setattr(farmplan, "shrunk_rates", boom)
    rotate, reason = farmplan.rotation_decision("CUR", _bs(("CUR", 520)), data_dir=tmp_path)
    assert (rotate, reason) == (False, None)
