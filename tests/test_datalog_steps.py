"""The startup-narration mirror in brawlfarm/core/datalog.py: controller events (launch_game,
dnd, daily_streak_claim, …) become canonical {"kind":"step"} records, once each,
with error→ok upgrades; the first menu→queuing phase flip emits {"kind":"farming"}.
All file IO redirected to tmp_path.
"""

from __future__ import annotations

import json

import pytest

from brawlfarm.core import config, datalog


@pytest.fixture()
def dl(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(datalog, "GAMES_CSV", tmp_path / "games.csv")
    monkeypatch.setattr(datalog, "TROPHIES_CSV", tmp_path / "menu_trophies.csv")
    return datalog.DataLog()


def _recs(dl, kind=None):
    out = []
    for line in dl.session_path.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        if kind is None or rec.get("kind") == kind:
            out.append(rec)
    return out


def test_launch_game_mirrors_a_step(dl):
    dl.event("launch_game", method="icon")
    steps = _recs(dl, "step")
    assert len(steps) == 1
    assert steps[0]["step"] == "launch"
    assert steps[0]["status"] == "ok"
    assert steps[0]["label"] == datalog.STEP_LABELS["launch"]


def test_each_step_mirrors_only_once(dl):
    dl.event("dnd", friends="ok")
    dl.event("dnd", friends="ok")  # controller never does this, but be safe
    assert len(_recs(dl, "step")) == 1


def test_error_then_ok_upgrades_the_step(dl):
    # _do_select_brawler: planned select fails -> lowest-trophy fallback succeeds.
    dl.event("select_brawler_error", err="boom")
    dl.event("select_brawler", brawler="COLT")
    steps = [r for r in _recs(dl, "step") if r["step"] == "brawler"]
    assert [s["status"] for s in steps] == ["error", "ok"]
    assert steps[-1]["label"] == "Brawler selected: COLT"


def test_ok_is_never_downgraded(dl):
    dl.event("dnd", friends="ok")
    dl.event("dnd_error", err="later hiccup")
    steps = [r for r in _recs(dl, "step") if r["step"] == "dnd"]
    assert [s["status"] for s in steps] == ["ok"]


def test_daily_streak_maps_to_daily_reward(dl):
    dl.event("daily_streak_claim")
    assert _recs(dl, "step")[0]["step"] == "daily_reward"


def test_first_queuing_phase_emits_farming_with_the_selected_brawler(dl):
    dl.event("select_brawler", brawler="JANET")
    dl.event("phase", to="queuing", frm="at_menu", games=0)
    dl.event("phase", to="playing", frm="queuing", games=0)
    dl.event("phase", to="queuing", frm="at_menu", games=1)  # between games
    farming = _recs(dl, "farming")
    assert len(farming) == 1
    assert farming[0]["brawler"] == "JANET"


def test_non_milestone_events_do_not_mirror(dl):
    dl.event("tap", button="play", x=1, y=2, phase="at_menu")
    dl.event("trophies", total=1000)
    assert _recs(dl, "step") == []
    assert _recs(dl, "farming") == []


def test_original_events_still_logged_unchanged(dl):
    # A milestone event (dnd) lands its plain record first, then the mirrored step.
    dl.event("dnd", friends="ok")
    kinds = [r["kind"] for r in _recs(dl)]
    assert kinds == ["dnd", "step"]  # mirror appends AFTER the original
