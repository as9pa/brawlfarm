"""Tests for ladder's rate-based rotation (r6: folded in from the old "optimal"
mode — legacy owner-instructions note, not ported).

Selection = ladder's lowest-first within the rising floor, PLUS rate-based
rotation: the controller asks farmplan.rotation_decision (win-rate model v2 —
empirical-Bayes-shrunk recency rate over games.csv; its own statistics live in
test_farmplan_winrate_v2.py) and rotates the brawler out for the session when it
says rotate AND the brawler is NOT on a winstreak (farmplan.recent_winstreak —
the owner's "never mid-winstreak" guard). Prestige is untouched by all of this.
"optimal" plans on disk alias to ladder.
"""

import csv

from brawlfarm.core import (
    config,  # noqa: F401 — imported for symmetry with the calibration consts
    farmplan,
)
from brawlfarm.core.controller import Controller


def _bs(*pairs):
    return [{"name": n, "trophies": t} for n, t in pairs]


# --- mode surface (r6: optimal folded into ladder) -------------------------------


def test_valid_modes_are_exactly_two():
    assert farmplan.VALID_MODES == ("prestige", "ladder")


def test_stored_optimal_plan_aliases_to_ladder(tmp_path):
    # a plan saved before r6 with mode=optimal must load as ladder (no migration)
    (tmp_path / "farmplan.json").write_text(
        '{"mode": "optimal", "goal_trophies": 1000}', encoding="utf-8"
    )
    assert farmplan.load_plan(data_dir=tmp_path)["mode"] == "ladder"


# --- selection (choose_target) -------------------------------------------------


def test_ladder_baseline_no_rotation():
    # no rotations -> the in-game lowest selection (None) toward the next 100-line
    plan = {"mode": "ladder", "goal_trophies": 1000}
    target, goal = farmplan.choose_target(plan, _bs(("A", 500), ("B", 650), ("C", 720)))
    assert target is None
    assert goal == 600


def test_ladder_rotation_picks_next_lowest_by_name():
    # the lowest brawler was rotated out -> pick the next candidate BY NAME (the
    # in-game lowest sort would just re-select the rotated one), with the step
    # goal computed over the remaining pool (no instant reselect loop)
    plan = {"mode": "ladder", "goal_trophies": 1000}
    target, goal = farmplan.choose_target(
        plan, _bs(("COLD", 36), ("NEXT", 140), ("HIGH", 500)), exclude={"COLD"}
    )
    assert target == "NEXT"
    assert goal == 200  # pool min 140 -> next tier, NOT the rotated brawler's 100


def test_ladder_all_rotated_falls_back_to_plain_ladder():
    plan = {"mode": "ladder", "goal_trophies": 1000}
    target, goal = farmplan.choose_target(plan, _bs(("A", 36), ("B", 140)), exclude={"A", "B"})
    assert target is None
    assert goal == 100


def test_prestige_ignores_exclude():
    # prestige is a goal statement — rotation is a ladder concept, never prestige
    brawlers = _bs(("A", 36), ("B", 140))
    t, g = farmplan.choose_target(
        {"mode": "prestige", "prestige_start": "lowest", "goal_trophies": 1000},
        brawlers,
        exclude={"A"},
    )
    assert (t, g) == ("A", 1000)  # prestige untouched


# --- games.csv helper (shared by the winstreak guard tests) ----------------------


def _write_games(tmp_path, rows):
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


# --- recent_winstreak (the r6 "never mid-winstreak" guard) -----------------------


def test_winstreak_all_wins_is_true(tmp_path):
    # last 3 showdown games all positive -> on a winstreak
    d = _write_games(tmp_path, [("CROW", -2, "True")] * 5 + [("CROW", 3, "True")] * 3)
    assert farmplan.recent_winstreak("CROW", data_dir=d) is True


def test_winstreak_mixed_recent_is_false(tmp_path):
    # one of the last 3 was a loss -> NOT a winstreak (even with a great older run)
    d = _write_games(
        tmp_path,
        [("CROW", 5, "True")] * 5
        + [("CROW", 4, "True"), ("CROW", -1, "True"), ("CROW", 2, "True")],
    )
    assert farmplan.recent_winstreak("CROW", data_dir=d) is False


def test_winstreak_zero_change_breaks_the_streak(tmp_path):
    # a draw (0) is not a WIN — strictly positive required
    d = _write_games(tmp_path, [("CROW", 2, "True"), ("CROW", 0, "True"), ("CROW", 3, "True")])
    assert farmplan.recent_winstreak("CROW", data_dir=d) is False


def test_winstreak_insufficient_games_is_false(tmp_path):
    # fewer than k logged games -> not enough evidence -> guard does NOT block
    d = _write_games(tmp_path, [("CROW", 9, "True")] * 2)
    assert farmplan.recent_winstreak("CROW", k=3, data_dir=d) is False


def test_winstreak_missing_csv_is_false(tmp_path):
    assert farmplan.recent_winstreak("CROW", data_dir=tmp_path / "nope") is False


def test_winstreak_filters_other_brawlers_and_non_showdown(tmp_path):
    rows = [("CROW", 3, "True")] * 3  # CROW's real streak
    rows += [("NITA", -5, "True")] * 3  # someone else's losses
    rows += [("CROW", -9, "False")] * 3  # CROW non-showdown losses don't count
    d = _write_games(tmp_path, rows)
    # CROW's last 3 SHOWDOWN games are the three +3s -> winstreak
    assert farmplan.recent_winstreak("CROW", data_dir=d) is True


# --- controller rotation wiring ---------------------------------------------------


class _DL:
    def __init__(self):
        self.events = []

    def event(self, etype, **fields):
        self.events.append((etype, fields))


def _ctrl(farm_brawler="CROW"):
    c = Controller.__new__(Controller)
    c._farm_brawler = farm_brawler
    c._farm_goal = 1000
    c._reselect_pending = False
    c._rotated = set()
    c.dl = _DL()
    return c


def _player(*pairs):
    return {"brawlers": _bs(*pairs)}


# r8: the controller's rotation trigger now calls farmplan.rotation_decision
# (win-rate model v2 — shrinkage + opportunity cost), with the recent_winstreak
# guard applied verbatim by the controller. These tests patch rotation_decision to
# pin the controller WIRING (the decision's own statistics are tested in
# test_farmplan_winrate_v2.py).


def test_cold_streak_triggers_rotation(monkeypatch):
    monkeypatch.setattr(farmplan, "load_plan", lambda: {"mode": "ladder", "goal_trophies": 1000})
    monkeypatch.setattr(farmplan, "rotation_decision", lambda name, pool: (True, "absolute_floor"))
    monkeypatch.setattr(farmplan, "recent_winstreak", lambda name: False)
    c = _ctrl("CROW")
    c._check_farm_brawler_trophies(_player(("CROW", 36), ("NITA", 140)))
    assert c._reselect_pending is True
    assert "CROW" in c._rotated
    assert any(e == "rotate_brawler" for e, _ in c.dl.events)


def test_winstreak_suppresses_rotation(monkeypatch):
    # the owner's rule: rotation triggered but on a winstreak -> KEEP it (verbatim)
    monkeypatch.setattr(farmplan, "load_plan", lambda: {"mode": "ladder", "goal_trophies": 1000})
    monkeypatch.setattr(
        farmplan, "rotation_decision", lambda name, pool: (True, "opportunity_cost")
    )
    monkeypatch.setattr(farmplan, "recent_winstreak", lambda name: True)
    c = _ctrl("CROW")
    c._check_farm_brawler_trophies(_player(("CROW", 36), ("NITA", 140)))
    assert c._reselect_pending is False
    assert c._rotated == set()
    assert not any(e == "rotate_brawler" for e, _ in c.dl.events)


def test_normal_variance_does_not_rotate(monkeypatch):
    # a healthy brawler never rotates — and the winstreak guard isn't even consulted
    # (the controller only consults it when rotation_decision says rotate)
    monkeypatch.setattr(farmplan, "load_plan", lambda: {"mode": "ladder", "goal_trophies": 1000})
    monkeypatch.setattr(farmplan, "rotation_decision", lambda name, pool: (False, None))

    def boom(name):
        raise AssertionError("winstreak guard runs only when rotation is triggered")

    monkeypatch.setattr(farmplan, "recent_winstreak", boom)
    c = _ctrl("CROW")
    c._check_farm_brawler_trophies(_player(("CROW", 36), ("NITA", 140)))
    assert c._reselect_pending is False
    assert c._rotated == set()


def test_insufficient_evidence_does_not_rotate(monkeypatch):
    monkeypatch.setattr(farmplan, "load_plan", lambda: {"mode": "ladder", "goal_trophies": 1000})
    # no evidence -> rotation_decision returns (False, None)
    monkeypatch.setattr(farmplan, "rotation_decision", lambda name, pool: (False, None))
    c = _ctrl("CROW")
    c._check_farm_brawler_trophies(_player(("CROW", 36), ("NITA", 140)))
    assert c._reselect_pending is False


def test_prestige_mode_never_evaluates_the_rate(monkeypatch):
    monkeypatch.setattr(
        farmplan,
        "load_plan",
        lambda: {
            "mode": "prestige",
            "prestige_start": "highest",
            "goal_trophies": 1000,
        },
    )

    def boom(name, pool):
        raise AssertionError("rotation_decision must not be called in prestige mode")

    monkeypatch.setattr(farmplan, "rotation_decision", boom)
    c = _ctrl("CROW")
    # CROW under its 1000 prestige goal -> no goal-cross, no rotation eval
    c._check_farm_brawler_trophies(_player(("CROW", 500), ("NITA", 140)))
    assert c._reselect_pending is False


def test_rotation_goal_uses_the_excluded_pool(monkeypatch):
    # after CROW rotates out, later snapshots compute the goal over the remaining
    # pool — the new named target must NOT instantly re-trigger the goal switch
    monkeypatch.setattr(farmplan, "load_plan", lambda: {"mode": "ladder", "goal_trophies": 1000})
    monkeypatch.setattr(farmplan, "rotation_decision", lambda name, pool: (False, None))
    c = _ctrl("NEXT")
    c._rotated = {"CROW"}
    c._check_farm_brawler_trophies(_player(("CROW", 36), ("NEXT", 140)))
    assert c._farm_goal == 200  # pool floor, not CROW's 100
    assert c._reselect_pending is False


def test_rate_check_failure_never_blocks_the_snapshot(monkeypatch):
    monkeypatch.setattr(farmplan, "load_plan", lambda: {"mode": "ladder", "goal_trophies": 1000})

    def boom(name, pool):
        raise OSError("games.csv locked")

    monkeypatch.setattr(farmplan, "rotation_decision", boom)
    c = _ctrl("CROW")
    c._check_farm_brawler_trophies(_player(("CROW", 36), ("NITA", 140)))
    assert c._reselect_pending is False
    assert any(e == "farmplan_error" and f.get("where") == "rate_check" for e, f in c.dl.events)
