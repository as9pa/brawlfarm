"""Tests for brawlfarm/core/farmplan.py target selection — focus on the new ladder mode.

Ladder mode farms the lowest-trophy brawler toward the next 100-trophy tier above
the current minimum, capped at goal_trophies. The key property is the invariant:
the floor only rises to the next tier once the MINIMUM has reached the current one,
so the whole roster reaches 700 before any brawler is pushed toward 800.
"""

from brawlfarm.core import farmplan


def _bs(*trophies):
    """A fake API brawler list from a sequence of trophy counts."""
    return [{"name": f"B{i}", "trophies": t} for i, t in enumerate(trophies)]


def test_ladder_is_a_valid_mode():
    assert "ladder" in farmplan.VALID_MODES


def test_ladder_pulls_the_lowest_band_up_one_tier():
    # everyone below 700: target is the lowest (None = in-game lowest selection),
    # goal is the next 100-line above the minimum (500 -> 600, climbs in 100s).
    plan = {"mode": "ladder", "goal_trophies": 1000}
    target, goal = farmplan.choose_target(plan, _bs(500, 650, 720, 860))
    assert target is None
    assert goal == 600


def test_ladder_invariant_all_reach_a_tier_before_the_next():
    # floor only reaches 800 once the MINIMUM is >= 700 (=> every brawler >= 700)
    plan = {"mode": "ladder", "goal_trophies": 1000}
    _, goal = farmplan.choose_target(plan, _bs(700, 700, 720, 860))
    assert goal == 800
    # one brawler still under 700 -> floor stays at 700
    _, goal = farmplan.choose_target(plan, _bs(699, 700, 720, 860))
    assert goal == 700


def test_ladder_never_exceeds_the_cap():
    plan = {"mode": "ladder", "goal_trophies": 700}
    _, goal = farmplan.choose_target(plan, _bs(450, 500, 680))
    assert goal == 500  # min 450 -> next tier 500, under the 700 cap
    _, goal = farmplan.choose_target(plan, _bs(650, 680, 690))
    assert goal == 700  # min 650 -> 700, equal to the cap, never above


def test_ladder_on_a_tier_boundary():
    # a brawler exactly on a 100-line counts as not-yet-past it
    plan = {"mode": "ladder", "goal_trophies": 1000}
    _, goal = farmplan.choose_target(plan, _bs(600, 600, 600))
    assert goal == 700


def test_ladder_empty_list_falls_back_to_lowest_flow():
    plan = {"mode": "ladder", "goal_trophies": 1000}
    target, goal = farmplan.choose_target(plan, [])
    assert target is None and goal == 1000


def test_ladder_survives_save_load(tmp_path):
    farmplan.save_plan({"mode": "ladder", "goal_trophies": 1000}, data_dir=tmp_path)
    plan = farmplan.load_plan(data_dir=tmp_path)
    assert plan["mode"] == "ladder"


def test_stored_least_aliases_to_ladder(tmp_path):
    # v5 (legacy owner note, not ported): "least" is removed from the surface — ladder subsumes
    # it — and stored least plans alias to ladder at load (no data migration).
    farmplan.save_plan({"mode": "least", "goal_trophies": 1000}, data_dir=tmp_path)
    plan = farmplan.load_plan(data_dir=tmp_path)
    assert plan["mode"] == "ladder"
    target, goal = farmplan.choose_target(plan, _bs(500, 650, 720))
    assert target is None and goal == 600  # ladder semantics: the next 100-step


def test_stored_manual_aliases_to_ladder(tmp_path):
    # v5: /farm (which wrote mode=manual + target/queue) is gone — stored manual
    # plans degrade gracefully to ladder; the leftover target/queue keys are inert.
    farmplan.save_plan(
        {"mode": "manual", "target": "CROW", "queue": ["NITA"], "goal_trophies": 700},
        data_dir=tmp_path,
    )
    plan = farmplan.load_plan(data_dir=tmp_path)
    assert plan["mode"] == "ladder"
    target, goal = farmplan.choose_target(plan, _bs(500, 650))
    assert target is None and goal == 600  # ladder ignores the stale manual target


def test_missing_plan_defaults_to_ladder(tmp_path):
    plan = farmplan.load_plan(data_dir=tmp_path)  # no farmplan.json at all
    assert plan["mode"] == "ladder"


def test_garbage_mode_falls_back_to_ladder(tmp_path):
    farmplan.save_plan({"mode": "yolo"}, data_dir=tmp_path)
    assert farmplan.load_plan(data_dir=tmp_path)["mode"] == "ladder"


# --- prestige/lowest: the owner's "switch off anything over 1000" plan -----------
# (owner rule 2026-06-14) Farm the genuinely-lowest brawler UNDER the goal, by name
# (API-authoritative — the in-game "Least Trophies" sort is fooled by the visual
# prestige-reset), to 1000, then switch to the next lowest. The farm accounts
# run this.


def test_prestige_lowest_picks_lowest_under_goal():
    plan = {"mode": "prestige", "prestige_start": "lowest", "goal_trophies": 1000}
    # 88-of-103-maxed shape: most brawlers >= 1000, a few still under it.
    target, goal = farmplan.choose_target(plan, _bs(807, 1200, 999, 2019, 850))
    assert target == "B0"  # the 807-trophy brawler, the genuinely lowest under 1000
    assert goal == 1000


def test_prestige_lowest_skips_brawlers_over_the_goal():
    # the global minimum is OVER the goal-pool: a brawler at exactly 1000 is not
    # under it, so the lowest UNDER 1000 wins even though it's not the global min
    plan = {"mode": "prestige", "prestige_start": "lowest", "goal_trophies": 1000}
    target, goal = farmplan.choose_target(plan, _bs(1000, 1000, 950, 1500))
    assert target == "B2"  # the 950 brawler (only one under 1000)
    assert goal == 1000


def test_prestige_all_maxed_returns_none():
    # every brawler at/above the goal -> no target. The controller treats this as
    # "account maxed" and holds, rather than grinding a >goal brawler.
    plan = {"mode": "prestige", "prestige_start": "lowest", "goal_trophies": 1000}
    target, goal = farmplan.choose_target(plan, _bs(1000, 1200, 2019))
    assert target is None
    assert goal == 1000


# --- maxed_fallback: keep farming a named brawler once prestige is exhausted -----
# (owner opt-in) When EVERY brawler is >= the goal (prestige pool empty), instead of
# the controller holding, switch to a configured owned brawler (FRANK) and keep
# playing it — a deliberate, gated >1000 grind for late-stage stats. Unset = today's
# hold; only fires in the all-maxed state.


def _bs_named(*pairs):
    """A fake brawler list from (name, trophies) pairs."""
    return [{"name": n, "trophies": t} for n, t in pairs]


def test_prestige_all_maxed_with_fallback_returns_fallback():
    # all maxed + maxed_fallback set + FRANK owned -> return FRANK (not None), so the
    # farm keeps playing it. Matched by uppercase; the actual roster name is returned.
    plan = {
        "mode": "prestige",
        "prestige_start": "lowest",
        "goal_trophies": 1000,
        "maxed_fallback": "FRANK",
    }
    target, goal = farmplan.choose_target(
        plan, _bs_named(("FRANK", 1200), ("SPIKE", 1000), ("TARA", 2019))
    )
    assert target == "FRANK"
    assert goal == 1000


def test_prestige_all_maxed_fallback_matches_case_insensitively():
    # plan stores any case; the brawler's actual roster name is returned.
    plan = {"mode": "prestige", "goal_trophies": 1000, "maxed_fallback": "frank"}
    target, goal = farmplan.choose_target(plan, _bs_named(("Frank", 1200), ("Spike", 1000)))
    assert target == "Frank"
    assert goal == 1000


def test_prestige_all_maxed_no_fallback_returns_none():
    # unchanged behavior: no fallback -> None (controller holds).
    plan = {"mode": "prestige", "goal_trophies": 1000}
    target, goal = farmplan.choose_target(plan, _bs_named(("FRANK", 1200), ("SPIKE", 1000)))
    assert target is None
    assert goal == 1000


def test_prestige_all_maxed_fallback_not_owned_returns_none():
    # fallback set but the named brawler is NOT in the roster -> hold (None), never
    # invent a target.
    plan = {"mode": "prestige", "goal_trophies": 1000, "maxed_fallback": "FRANK"}
    target, goal = farmplan.choose_target(plan, _bs_named(("SPIKE", 1000), ("TARA", 1200)))
    assert target is None
    assert goal == 1000


def test_prestige_fallback_empty_string_treated_as_unset():
    # a blank / whitespace fallback is "unset" -> hold.
    plan = {"mode": "prestige", "goal_trophies": 1000, "maxed_fallback": "  "}
    target, goal = farmplan.choose_target(plan, _bs_named(("FRANK", 1200), ("SPIKE", 1000)))
    assert target is None and goal == 1000


def test_prestige_fallback_ignored_when_pool_not_empty():
    # some brawler still under the goal -> the normal lowest-under-goal pick wins;
    # the fallback is ignored entirely (it only fires when prestige is exhausted).
    plan = {
        "mode": "prestige",
        "prestige_start": "lowest",
        "goal_trophies": 1000,
        "maxed_fallback": "FRANK",
    }
    target, goal = farmplan.choose_target(
        plan, _bs_named(("FRANK", 1200), ("SPIKE", 807), ("TARA", 2019))
    )
    assert target == "SPIKE"  # the lowest under 1000, NOT the fallback
    assert goal == 1000


def test_maxed_fallback_default_is_none():
    assert farmplan.DEFAULT_PLAN.get("maxed_fallback") is None


def test_maxed_fallback_survives_save_load(tmp_path):
    farmplan.save_plan({"mode": "prestige", "maxed_fallback": "FRANK"}, data_dir=tmp_path)
    plan = farmplan.load_plan(data_dir=tmp_path)
    assert plan["maxed_fallback"] == "FRANK"


class FakeApi:
    """Stands in for the API client: owned_trophy_map asks it for the player once."""

    def __init__(self, brawlers):
        self.brawlers = brawlers
        self.calls = 0

    def get_player(self):
        self.calls += 1
        return {"brawlers": self.brawlers}


def test_owned_trophy_map_keys_by_the_normalized_name():
    api = FakeApi([{"name": "NITA", "trophies": 7}])
    assert farmplan.owned_trophy_map(api) == {"NITA": 7}
    assert api.calls == 1  # one get_player per session, never one per quest


def test_owned_trophy_map_reads_a_missing_trophy_count_as_zero():
    api = FakeApi([{"name": "El Primo"}, {"name": "8-Bit", "trophies": None}])
    assert farmplan.owned_trophy_map(api) == {"ELPRIMO": 0, "8BIT": 0}


def test_owned_trophy_map_drops_a_nameless_row():
    api = FakeApi([{"trophies": 500}, {"name": "", "trophies": 400}, {"name": "Nita"}])
    assert farmplan.owned_trophy_map(api) == {"NITA": 0}


def test_owned_trophy_map_of_an_empty_roster_is_empty():
    assert farmplan.owned_trophy_map(FakeApi([])) == {}
