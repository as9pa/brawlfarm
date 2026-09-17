"""The quest-aware brawler pick: the plan flag, the one quests visit and the feed event.

With `quest_aware` on (ladder only) the session-start quests visit reads the quest cards
and _do_select_brawler hands the brawler they call for to the checked select, capped at
the farm goal so the pick never grinds a brawler past it. With the flag off, or in
prestige mode, nothing here runs: no trophy read, no quests visit, no event, and the
selection path is the one that shipped.

Like tests/test_controller_reselect.py these drive the controller's methods directly (no
adb, no API): the object is built without __init__ and every seam it reaches for is
patched, so the inputs are exactly the quest cards, the roster and the plan.
"""

from brawlfarm.core import brawlers, farmplan, quests
from brawlfarm.core.controller import Controller
from brawlfarm.core.states import State


class _DL:
    """Event-recording stand-in for DataLog (no disk writes)."""

    def __init__(self):
        self.events = []

    def event(self, etype, **fields):
        self.events.append((etype, fields))


def _ctrl(cards=None, quest_aware=True, goal=1000):
    c = Controller.__new__(Controller)  # skip __init__ (ApiClient/DataLog/adb)
    c.api = object()
    c.dl = _DL()
    c.log = lambda *a, **k: None
    c._farm_brawler = None
    c._farm_goal = goal
    c._rotated = set()
    c._account_maxed = False
    c._quest_aware = quest_aware
    c._quest_visit_done = True  # the menu step already ran the visit below
    c._quest_cards = cards
    c._note_recalib = lambda *a, **k: None
    c._capture_farm_brawler = lambda: None
    return c


def _plan(quest_aware=True, mode="ladder"):
    return {"mode": mode, "goal_trophies": 1000, "quest_aware": quest_aware}


def _picks(monkeypatch, target, owned, goal=1000):
    """Patch the resolve + select seams and return the list the checked select was
    handed. `owned` is the roster spelling the API reports."""
    monkeypatch.setattr(
        farmplan, "resolve_target", lambda api, exclude=(): (target, goal, list(owned))
    )
    picked = []
    monkeypatch.setattr(
        brawlers,
        "select_brawler_by_name_checked",
        lambda name, owned_names, log: (picked.append(name), (name, False))[1],
    )
    monkeypatch.setattr(
        brawlers,
        "select_lowest_trophy_brawler",
        lambda log: (picked.append("<lowest>"), "SPIKE")[1],
    )
    return picked


def _trophies(monkeypatch, **by_name):
    calls = []
    monkeypatch.setattr(
        farmplan,
        "owned_trophy_map",
        lambda api: (calls.append(True), dict(by_name))[1],
    )
    return calls


def _event(c, kind):
    return next((fields for etype, fields in c.dl.events if etype == kind), None)


def test_quest_pick_is_off_without_the_flag(monkeypatch):
    monkeypatch.setattr(farmplan, "load_plan", lambda: _plan(quest_aware=False))
    assert Controller._quest_pick_on(_ctrl()) is False


def test_quest_pick_is_off_for_a_plan_file_without_the_key(monkeypatch):
    monkeypatch.setattr(farmplan, "load_plan", lambda: {"mode": "ladder"})
    assert Controller._quest_pick_on(_ctrl()) is False


def test_quest_pick_is_off_in_prestige_mode(monkeypatch):
    # Owner decision: the quest pick is a ladder feature; prestige ignores the flag.
    monkeypatch.setattr(farmplan, "load_plan", lambda: _plan(mode="prestige"))
    assert Controller._quest_pick_on(_ctrl()) is False


def test_quest_pick_is_on_for_ladder_with_the_flag(monkeypatch):
    monkeypatch.setattr(farmplan, "load_plan", lambda: _plan())
    assert Controller._quest_pick_on(_ctrl()) is True


def test_an_unreadable_plan_counts_as_off(monkeypatch):
    def boom():
        raise OSError("farmplan.json unreadable")

    monkeypatch.setattr(farmplan, "load_plan", boom)
    assert Controller._quest_pick_on(_ctrl()) is False


def test_flag_off_selects_the_plan_target_and_reads_no_quests(monkeypatch):
    """The byte-identical path: no trophy map, no quests visit, no quest_pick event."""

    def never(*a, **k):
        raise AssertionError("the flag is off")

    monkeypatch.setattr(farmplan, "owned_trophy_map", never)
    monkeypatch.setattr(quests, "visit", never)
    monkeypatch.setattr(farmplan, "load_plan", lambda: _plan(quest_aware=False))
    picked = _picks(monkeypatch, "SPIKE", ["Spike", "Nita"])
    c = _ctrl(cards=["Win 5 battles with Nita"], quest_aware=False)
    c._do_select_brawler()
    assert picked == ["SPIKE"]
    assert _event(c, "quest_pick") is None


def test_a_quest_brawler_is_what_reaches_the_checked_select(monkeypatch):
    monkeypatch.setattr(farmplan, "load_plan", lambda: _plan())
    picked = _picks(monkeypatch, "Spike", ["Spike", "Nita", "Crow"])
    _trophies(monkeypatch, SPIKE=400, NITA=300, CROW=900)
    c = _ctrl(cards=["Win 5 battles with Nita"])
    c._do_select_brawler()
    assert picked == ["Nita"]  # the roster's spelling, not the quest's
    assert _event(c, "quest_pick") == {
        "brawler": "Nita",
        "quest": "WIN 5 BATTLES WITH NITA",
        "reason": "chosen",
        "target": "Spike",
    }


def test_a_target_that_clears_a_quest_wins(monkeypatch):
    # The override rule: the plan's own target is kept when it clears a quest itself,
    # even though NITA is the lower-trophy candidate on that quest.
    monkeypatch.setattr(farmplan, "load_plan", lambda: _plan())
    picked = _picks(monkeypatch, "Spike", ["Spike", "Nita"])
    _trophies(monkeypatch, SPIKE=400, NITA=300)
    c = _ctrl(cards=["Win 5 battles with Nita or Spike"])
    c._do_select_brawler()
    assert picked == ["Spike"]
    assert _event(c, "quest_pick") == {
        "brawler": "Spike",
        "quest": "WIN 5 BATTLES WITH NITA OR SPIKE",
        "reason": "target_clears",
        "target": "Spike",
    }


def test_a_candidate_at_the_goal_is_skipped(monkeypatch):
    # The owner's cap: CROW clears the only quest but is already AT the goal, so the
    # pick leaves it alone and the plan's target is selected instead.
    monkeypatch.setattr(farmplan, "load_plan", lambda: _plan())
    picked = _picks(monkeypatch, "Nita", ["Nita", "Crow"])
    _trophies(monkeypatch, NITA=300, CROW=1000)
    c = _ctrl(cards=["Win 5 battles with Crow"])
    c._do_select_brawler()
    assert picked == ["Nita"]
    assert _event(c, "quest_pick") == {
        "brawler": None,
        "quest": None,
        "reason": "no_candidate",
        "target": "Nita",
    }


def test_the_cap_never_filters_the_plan_target(monkeypatch):
    # The plan already chose the target, so the cap must not drop it from the
    # candidates: a maxed target that clears a quest still reads as target_clears.
    monkeypatch.setattr(farmplan, "load_plan", lambda: _plan())
    picked = _picks(monkeypatch, "Nita", ["Nita", "Crow"])
    _trophies(monkeypatch, NITA=1000, CROW=900)
    c = _ctrl(cards=["Win 5 battles with Nita"])
    c._do_select_brawler()
    assert picked == ["Nita"]
    assert _event(c, "quest_pick")["reason"] == "target_clears"


def test_no_owned_candidate_runs_the_existing_lowest_chain(monkeypatch):
    # resolve finds nothing and the plan has no target either: the legacy in-game
    # lowest-trophy selection runs exactly as before.
    monkeypatch.setattr(farmplan, "load_plan", lambda: _plan())
    picked = _picks(monkeypatch, None, ["Nita", "Crow"])
    _trophies(monkeypatch, NITA=300, CROW=400)
    c = _ctrl(cards=["Win 5 battles with Mortis"])
    c._do_select_brawler()
    assert picked == ["<lowest>"]
    assert _event(c, "quest_pick") == {
        "brawler": None,
        "quest": None,
        "reason": "no_candidate",
        "target": None,
    }
    assert _event(c, "select_brawler") == {"brawler": "SPIKE"}


def test_a_raising_quests_visit_is_caught_and_falls_back(monkeypatch):
    def boom(log=print):
        raise RuntimeError("quests screen gone")

    monkeypatch.setattr(quests, "visit", boom)
    logged = []
    c = _ctrl(cards=None)
    c.log = logged.append
    c._do_quest_visit()
    assert c._quest_cards is None
    assert any("quest read error" in line for line in logged)

    # ... and the select then says so and uses the plan, without a trophy read.
    def never(api):
        raise AssertionError("no cards, nothing to pick from")

    monkeypatch.setattr(farmplan, "owned_trophy_map", never)
    monkeypatch.setattr(farmplan, "load_plan", lambda: _plan())
    picked = _picks(monkeypatch, "Spike", ["Spike", "Nita"])
    c._do_select_brawler()
    assert picked == ["Spike"]
    assert _event(c, "quest_pick") == {
        "brawler": None,
        "quest": None,
        "reason": "unreadable",
        "target": "Spike",
    }


def test_a_quests_visit_that_read_nothing_reports_unreadable(monkeypatch):
    monkeypatch.setattr(farmplan, "load_plan", lambda: _plan())
    picked = _picks(monkeypatch, "Spike", ["Spike"])
    c = _ctrl(cards=[])
    c._do_select_brawler()
    assert picked == ["Spike"]
    assert _event(c, "quest_pick")["reason"] == "unreadable"


def test_a_trophy_read_error_leaves_the_plans_answer_alone(monkeypatch):
    def boom(api):
        raise RuntimeError("api down")

    monkeypatch.setattr(farmplan, "owned_trophy_map", boom)
    monkeypatch.setattr(farmplan, "load_plan", lambda: _plan())
    picked = _picks(monkeypatch, "Spike", ["Spike", "Nita"])
    c = _ctrl(cards=["Win 5 battles with Nita"])
    c._do_select_brawler()
    assert picked == ["Spike"]
    assert _event(c, "quest_pick") is None
    assert _event(c, "quest_pick_error") is not None


def test_the_pick_applies_to_the_session_start_select_only(monkeypatch):
    # A mid-session reselect is the plan's call: the quest cards steer the first select
    # and nothing after it.
    monkeypatch.setattr(farmplan, "load_plan", lambda: _plan())
    picked = _picks(monkeypatch, "Spike", ["Spike", "Nita"])
    _trophies(monkeypatch, SPIKE=400, NITA=300)
    c = _ctrl(cards=["Win 5 battles with Nita"])
    c._do_select_brawler()
    c._do_select_brawler()
    assert picked == ["Nita", "Spike"]
    assert len([f for e, f in c.dl.events if e == "quest_pick"]) == 1


def test_the_menu_runs_the_quests_visit_before_the_select(monkeypatch):
    """The ordering ruling: today's menu selects the brawler before the mega-quest
    check, so with the flag on the visit moves ahead of the select. One visit only."""
    monkeypatch.setattr(farmplan, "load_plan", lambda: _plan())
    order = []
    c = _ctrl()
    c._quest_visit_done = False
    c._quest_aware = False
    c.select_brawler = True
    c._select_brawler_done = False
    c.dnd = False
    c._dnd_done = True
    c._soft_stop_reason = lambda: None
    c._do_quest_visit = lambda: order.append("quests")
    c._do_select_brawler = lambda: order.append("select")
    c.phase_at_menu(None, State.MENU)
    assert order == ["quests"]  # and it returned, to re-read the menu
    c.phase_at_menu(None, State.MENU)
    assert order == ["quests", "select"]  # the visit does not repeat


def test_the_menu_skips_the_quests_visit_with_the_flag_off(monkeypatch):
    monkeypatch.setattr(farmplan, "load_plan", lambda: _plan(quest_aware=False))
    order = []
    c = _ctrl(quest_aware=False)
    c._quest_visit_done = False
    c.select_brawler = True
    c._select_brawler_done = False
    c.dnd = False
    c._dnd_done = True
    c._soft_stop_reason = lambda: None
    c._do_quest_visit = lambda: order.append("quests")
    c._do_select_brawler = lambda: order.append("select")
    c.phase_at_menu(None, State.MENU)
    assert order == ["select"]
    assert c._quest_aware is False
