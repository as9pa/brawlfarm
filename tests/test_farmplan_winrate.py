"""Tests for the win-rate-aware selection bias (Q2 -> model v2, r8).

Inside choose_target, ladder ONLY: candidates (owned brawlers below the current
step goal, minus the session's rotation exclude set) are ordered by their score,
tie-break lowest trophies; the top one is promoted only if its score beats the
roster-minimum brawler's by >= config.WINRATE_MARGIN.

r8: the SCORE is now the empirical-Bayes-shrunk recency rate (model v2 — the legacy
research note "winrate model", not ported): an EWMA over the brawler's history shrunk
toward the account mean by config.WINRATE_PRIOR_K games. This replaces v1's trailing-mean
+ hard min-sample/neutral-prior cliff. The SURFACE invariants below are unchanged
(missing/garbled csv = today, kill switch off = today, prestige untouched, exclude
wins); the cases whose VALUES depend on the scoring math were updated for v2 and
say so. v2's statistics are pinned in test_farmplan_winrate_v2.py.
"""

import csv

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


# --- rates_by_brawler (the stat) -------------------------------------------------


def test_rates_by_brawler_window_and_filters(tmp_path):
    rows = [("CROW", -3, "True")] * 5  # ages out of CROW's 20-game window
    rows += [("CROW", 4, "True")] * 20
    rows += [("CROW", -9, "False")] * 10  # non-showdown rows don't count
    rows += [("NITA", 2, "True")] * 3
    rows += [("NITA", "", "True")] * 2  # missing trophyChange (API gap) skipped
    d = _write_games(tmp_path, rows)
    rates = farmplan.rates_by_brawler(data_dir=d)
    assert rates["CROW"] == (4.0, 20)  # only the last 20, showdown only
    assert rates["NITA"] == (2.0, 3)


def test_rates_by_brawler_missing_csv_is_empty(tmp_path):
    assert farmplan.rates_by_brawler(data_dir=tmp_path) == {}


# --- ladder promotion + the rails ------------------------------------------------


def _promotable(tmp_path):
    """MINNIE (roster min) trails at +1/game, HOT at +5/game — both well-sampled.
    The trailing-20 account-wide prior is irrelevant here (both have real scores)."""
    rows = [("MINNIE", 1, "True")] * 10 + [("HOT", 5, "True")] * 10
    return _write_games(tmp_path, rows)


def test_ladder_promotes_a_clear_winner(tmp_path, monkeypatch):
    _on(monkeypatch)
    d = _promotable(tmp_path)
    plan = {"mode": "ladder", "goal_trophies": 1000}
    brawlers = _bs(("MINNIE", 500), ("HOT", 550), ("HIGH", 720))
    target, goal = farmplan.choose_target(plan, brawlers, data_dir=d)
    assert target == "HOT"  # +5 beats +1 by >= the 1.0 margin
    assert goal == 600  # the step goal (and so the floor invariant) is untouched


def test_margin_respected_near_tie_stays_default(tmp_path, monkeypatch):
    _on(monkeypatch)
    # HOT only +0.5/game better than the minimum -> inside the margin -> no churn
    rows = [("MINNIE", 1, "True")] * 10
    rows += [("HOT", 1, "True")] * 5 + [("HOT", 2, "True")] * 5  # mean 1.5
    d = _write_games(tmp_path, rows)
    plan = {"mode": "ladder", "goal_trophies": 1000}
    brawlers = _bs(("MINNIE", 500), ("HOT", 550), ("HIGH", 720))
    assert farmplan.choose_target(plan, brawlers, data_dir=d) == (None, 600)


def test_v2_near_tie_shrinks_inside_the_margin(tmp_path, monkeypatch):
    _on(monkeypatch)
    # v2: 10 games of +2 vs +1 is a NEAR TIE — both are shrunk toward the +1.5
    # account mean, so the gap (~0.47) stays inside the 1.0 margin and nothing
    # promotes. (Under v1 the raw +1.0 difference exactly met the margin; v2's
    # shrinkage deliberately damps small-sample differences — see the legacy
    # research note "winrate model", not ported.)
    rows = [("MINNIE", 1, "True")] * 10 + [("HOT", 2, "True")] * 10
    d = _write_games(tmp_path, rows)
    plan = {"mode": "ladder", "goal_trophies": 1000}
    brawlers = _bs(("MINNIE", 500), ("HOT", 550))
    assert farmplan.choose_target(plan, brawlers, data_dir=d) == (None, 600)


def test_v2_no_min_sample_cliff(tmp_path, monkeypatch):
    _on(monkeypatch)
    # v2 has NO hard min-sample line: a STRONG, well-above-baseline 9-game run is
    # usable signal (shrunk toward the ~+3.4 mean it still reads ~+5.4 vs MINNIE's
    # ~+2.7 -> gap > 1.0). v1 would have scored HOT the neutral prior here (9 < 10)
    # and held the default; v2 promotes on the real evidence. This is the cliff
    # removal the model upgrade is for.
    rows = [("HOT", 8, "True")] * 9
    rows += [("MINNIE", 2, "True")] * 10
    rows += [("FILLER", 2, "True")] * 20
    d = _write_games(tmp_path, rows)
    plan = {"mode": "ladder", "goal_trophies": 1000}
    brawlers = _bs(("MINNIE", 500), ("HOT", 550), ("HIGH", 720))
    assert farmplan.choose_target(plan, brawlers, data_dir=d) == ("HOT", 600)


def test_tie_break_prefers_lowest_trophies(tmp_path, monkeypatch):
    _on(monkeypatch)
    rows = [("MINNIE", 1, "True")] * 10
    rows += [("HIA", 5, "True")] * 10  # same score as HIB...
    rows += [("HIB", 5, "True")] * 10  # ...but HIB sits lower on the ladder
    d = _write_games(tmp_path, rows)
    plan = {"mode": "ladder", "goal_trophies": 1000}
    brawlers = _bs(("MINNIE", 500), ("HIA", 560), ("HIB", 540))
    assert farmplan.choose_target(plan, brawlers, data_dir=d) == ("HIB", 600)


def test_step_goal_ceiling_never_violated(tmp_path, monkeypatch):
    _on(monkeypatch)
    # STAR's stellar score can't promote it: at 650 it is AT/above the 600 step,
    # so it isn't a candidate at all — only MINNIE is, and a lone candidate is
    # never "promoted" (today's in-game lowest flow handles it).
    rows = [("MINNIE", 1, "True")] * 10 + [("STAR", 9, "True")] * 10
    d = _write_games(tmp_path, rows)
    plan = {"mode": "ladder", "goal_trophies": 1000}
    brawlers = _bs(("MINNIE", 500), ("STAR", 650))
    assert farmplan.choose_target(plan, brawlers, data_dir=d) == (None, 600)


# --- ladder rotation pool: exclusion always wins (r6: folded in from optimal) -----


def test_ladder_exclude_wins_over_a_good_score(tmp_path, monkeypatch):
    _on(monkeypatch)
    # COLD has the best trailing score on file but was rotated out this session:
    # exclusion filters BEFORE scoring, so it can never be re-picked by a stale
    # good score. NEXT/OTHER tie all-around -> no promotion -> today's by-name
    # next-lowest pick with the pool's step goal. (r6: ladder honors exclude now.)
    rows = [("COLD", 9, "True")] * 10
    rows += [("NEXT", 2, "True")] * 10
    rows += [("OTHER", 2, "True")] * 10
    d = _write_games(tmp_path, rows)
    plan = {"mode": "ladder", "goal_trophies": 1000}
    brawlers = _bs(("COLD", 36), ("NEXT", 140), ("OTHER", 150), ("HIGH", 500))
    target, goal = farmplan.choose_target(plan, brawlers, exclude={"COLD"}, data_dir=d)
    assert target == "NEXT"
    assert goal == 200  # pool min 140 -> next tier, not the rotated brawler's 100


def test_ladder_promotes_within_the_excluded_pool(tmp_path, monkeypatch):
    _on(monkeypatch)
    rows = [("NEXT", 1, "True")] * 10 + [("OTHER", 6, "True")] * 10
    d = _write_games(tmp_path, rows)
    plan = {"mode": "ladder", "goal_trophies": 1000}
    brawlers = _bs(("COLD", 36), ("NEXT", 140), ("OTHER", 150), ("HIGH", 500))
    target, goal = farmplan.choose_target(plan, brawlers, exclude={"COLD"}, data_dir=d)
    assert target == "OTHER"  # +6 beats +1 within the 100-200 band
    assert goal == 200


# --- prestige untouched --------------------------------------------------------------


def test_prestige_never_consults_the_stats(tmp_path, monkeypatch):
    _on(monkeypatch)

    def boom(*a, **k):
        raise AssertionError("prestige must never read win-rate stats")

    monkeypatch.setattr(farmplan, "_winrate_stats", boom)
    brawlers = _bs(("A", 36), ("B", 140))
    t, g = farmplan.choose_target(
        {"mode": "prestige", "prestige_start": "lowest", "goal_trophies": 1000},
        brawlers,
        data_dir=tmp_path,
    )
    assert (t, g) == ("A", 1000)


# --- fail-open: missing/garbled csv, kill switch -----------------------------------


def test_missing_csv_is_today_exactly(tmp_path, monkeypatch):
    _on(monkeypatch)
    plan = {"mode": "ladder", "goal_trophies": 1000}
    brawlers = _bs(("MINNIE", 500), ("HOT", 550))
    assert farmplan.choose_target(plan, brawlers, data_dir=tmp_path) == (None, 600)
    # ladder with a rotation: today's by-name next-lowest, unchanged
    plan = {"mode": "ladder", "goal_trophies": 1000}
    brawlers = _bs(("COLD", 36), ("NEXT", 140), ("HIGH", 500))
    assert farmplan.choose_target(plan, brawlers, exclude={"COLD"}, data_dir=tmp_path) == (
        "NEXT",
        200,
    )


def test_garbled_csv_is_today_exactly(tmp_path, monkeypatch):
    _on(monkeypatch)
    (tmp_path / "games.csv").write_bytes(b"\x00\xff\x00garbage\xfe\x00\n\x00")
    plan = {"mode": "ladder", "goal_trophies": 1000}
    brawlers = _bs(("MINNIE", 500), ("HOT", 550))
    assert farmplan.choose_target(plan, brawlers, data_dir=tmp_path) == (None, 600)


def test_kill_switch_pins_old_behavior_and_skips_the_read(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "WINRATE_AWARE", False)

    def boom(*a, **k):
        raise AssertionError("kill switch must prevent any games.csv read")

    monkeypatch.setattr(farmplan, "_winrate_stats", boom)
    d = _promotable(tmp_path)
    plan = {"mode": "ladder", "goal_trophies": 1000}
    brawlers = _bs(("MINNIE", 500), ("HOT", 550), ("HIGH", 720))
    assert farmplan.choose_target(plan, brawlers, data_dir=d) == (None, 600)


def test_default_data_dir_is_config_data_dir(tmp_path, monkeypatch):
    # choose_target's existing callers pass no data_dir — the bias must follow
    # config.DATA_DIR (the instance's own dir in the worker process).
    _on(monkeypatch)
    d = _promotable(tmp_path)
    monkeypatch.setattr(config, "DATA_DIR", d)
    plan = {"mode": "ladder", "goal_trophies": 1000}
    brawlers = _bs(("MINNIE", 500), ("HOT", 550))
    assert farmplan.choose_target(plan, brawlers) == ("HOT", 600)


def test_unaliased_mode_never_consults_the_stats(tmp_path, monkeypatch):
    """v5: "least"/"manual" alias to ladder INSIDE load_plan; a raw plan that
    bypassed load_plan (so no alias ran) must degrade to the plain lowest-trophy
    flow — (None, goal) — without ever reading win-rate stats."""
    _on(monkeypatch)

    def boom(*a, **k):
        raise AssertionError("an unaliased mode must never read win-rate stats")

    monkeypatch.setattr(farmplan, "_winrate_stats", boom)
    t, g = farmplan.choose_target({"mode": "least"}, _bs(("A", 36), ("B", 140)), data_dir=tmp_path)
    assert (t, g) == (None, 1000)
