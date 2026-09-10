"""Scheduler verification (P2): invariants over thousands of simulated account-days,
distribution sanity, anti-self-similarity, determinism, the round-6 per-account phase
stagger — plus compressed-time multi-day tick sweeps (parametrized start times, pinned
salt — fully deterministic) against a tmp data root.

Round 6 redesign (docs/more instructions.md, "remove the sleep thing. … random hourly
breaks in between"): the day is NO LONGER sleep/rest/budget-shaped. A plan covers the
full local day 00:00->24:00 by alternating session -> break -> session -> … until the
next-midnight boundary. The invariants below pin THAT model: sessions ordered and
non-overlapping, every break in [45,125] min, the day fully covered by the alternation
(no idle holes beyond what a break allows), midnight truncation, determinism, the phase
stagger, and old-plan tolerance in evaluate().

Run:  uv run pytest tests/test_scheduler.py -q
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

import brawlfarm.core.scheduler as S
from brawlfarm.core import config

# The scheduler draws per REGISTERED instance, so the suite registers its own
# stand-ins (config.INSTANCES ships empty). Distinct tags -> distinct per-account
# phase offsets, which is what the stagger tests measure.
INSTANCES = {
    "Pie64": {"port": "5555", "tag": "#2P0YLQ9V", "data": "data/Pie64"},
    "Nest32": {"port": "5565", "tag": "#8CJRGUV2", "data": "data/Nest32"},
    "Rook17": {"port": "5585", "tag": "#9QLY2P0C", "data": "data/Rook17"},
}


@pytest.fixture(autouse=True)
def _registered():
    config.set_instances(INSTANCES)


# ~10,000 account-days: 3 accounts x ~3,334 play-days each.
SIM_DAYS = 3334
START = datetime(2026, 6, 10, 0, 0, 0)

BREAK_LO, BREAK_HI = 45, 125  # break clip [45, 125] min (r8 widened the tail 110->125)
OUTING_LO, OUTING_HI = 120, 240  # r8 long-outing clip [2 h, 4 h] min


def _is_outing_after(sessions: list[dict], i: int) -> bool:
    """The gap AFTER sessions[i] is an r8 long outing (vs a regular break)."""
    return bool(sessions[i].get("outing_after"))


def _mins(iso_a: str, iso_b: str) -> float:
    return (S._parse(iso_b) - S._parse(iso_a)).total_seconds() / 60.0


@pytest.fixture(scope="module")
def sims() -> dict[str, list[dict]]:
    # module scope is built before the function-scoped registration above
    config.set_instances(INSTANCES)
    draws = S.simulate_draws(SIM_DAYS, start=START, salt="pytest")
    config.set_instances({})
    return draws


# --- per-day invariants (the new alternation model's hard rules) -------------------


def test_no_legacy_keys_in_drawn_plans(sims):
    # the sleep/rest/budget model is gone — those keys must not appear in a new plan
    for plans in sims.values():
        for p in plans:
            assert "sleep" not in p, p["plan_date"]
            assert "is_rest" not in p, p["plan_date"]
            assert "games_budget" not in p, p["plan_date"]
            assert "day_end" in p and "phase_min" in p, p["plan_date"]


def test_session_lengths_within_bounds(sims):
    # lognormal clip [30,120] with the long re-clip up to 150 — EXCEPT a session
    # truncated at the midnight boundary may be shorter than 30 (the day's tail).
    for plans in sims.values():
        for p in plans:
            for i, s in enumerate(p["sessions"]):
                ln = _mins(s["start"], s["end"])
                is_last = i == len(p["sessions"]) - 1
                truncated = is_last and s["end"] == p["day_end"]
                if truncated:
                    assert 0 < ln <= 150 + 1e-6, (p["plan_date"], ln)
                else:
                    assert 30 - 1e-6 <= ln <= 150 + 1e-6, (p["plan_date"], ln)


def test_sessions_ordered_and_non_overlapping(sims):
    for plans in sims.values():
        for p in plans:
            ss = p["sessions"]
            for a, b in zip(ss, ss[1:]):
                # strictly ordered, and the next starts AFTER the previous ends
                assert S._parse(a["end"]) <= S._parse(b["start"]), p["plan_date"]


def test_every_break_within_clip(sims):
    # every gap between consecutive sessions is a clipped break in [45,125] min —
    # EXCEPT an r8 long outing, which is its own [2 h, 4 h] gap (asserted separately).
    for plans in sims.values():
        for p in plans:
            ss = p["sessions"]
            for i in range(len(ss) - 1):
                gap = _mins(ss[i]["end"], ss[i + 1]["start"])
                if _is_outing_after(ss, i):
                    assert OUTING_LO - 1e-6 <= gap <= OUTING_HI + 1e-6, (
                        p["plan_date"],
                        gap,
                    )
                else:
                    assert BREAK_LO - 1e-6 <= gap <= BREAK_HI + 1e-6, (
                        p["plan_date"],
                        gap,
                    )


def test_day_fully_covered_no_monster_holes(sims):
    # The day is filled by alternation: between the first session start and the last
    # session end there are NO idle stretches bigger than the max break (125 min) —
    # save for the r8 long outings, which are intentional [2 h, 4 h] gaps. And the
    # last session ends at/before the next midnight (day_end).
    for plans in sims.values():
        for p in plans:
            ss = p["sessions"]
            if not ss:
                continue
            for i in range(len(ss) - 1):
                hole = _mins(ss[i]["end"], ss[i + 1]["start"])
                ceiling = OUTING_HI if _is_outing_after(ss, i) else BREAK_HI
                assert hole <= ceiling + 1e-6, (p["plan_date"], hole)
            assert S._parse(ss[-1]["end"]) <= S._parse(p["day_end"]) + timedelta(
                seconds=1
            ), p["plan_date"]


def test_midnight_truncation(sims):
    # a session that would cross midnight is truncated exactly to day_end; no session
    # ever runs past it.
    for plans in sims.values():
        for p in plans:
            day_end = S._parse(p["day_end"])
            for s in p["sessions"]:
                assert S._parse(s["end"]) <= day_end + timedelta(seconds=1), p[
                    "plan_date"
                ]


def test_day_to_day_continuity(sims):
    # the next play-day's first session starts at/after this day's day_end (the next
    # midnight) — the pattern continues across the seam, no overlap.
    for plans in sims.values():
        for cur, nxt in zip(plans, plans[1:]):
            assert S._parse(nxt["sessions"][0]["start"]) >= S._parse(cur["day_end"]), (
                cur["plan_date"]
            )


def test_full_day_is_busy(sims):
    # alternation fills the day: every non-edge day should pack many sessions (a thin
    # day would mean the fill loop bailed early). With ~73-min sessions + ~73-min
    # breaks across ~24 h, expect well over 5 sessions on a midnight-anchored day.
    for name, plans in sims.items():
        avg = sum(len(p["sessions"]) for p in plans) / len(plans)
        assert avg >= 7, (name, avg)


# --- distribution sanity ------------------------------------------------------------


def _all_full_sessions_min(sims) -> list[float]:
    # exclude the midnight-truncated last session of each day (it skews short)
    out = []
    for plans in sims.values():
        for p in plans:
            ss = p["sessions"]
            for i, s in enumerate(ss):
                if i == len(ss) - 1 and s["end"] == p["day_end"]:
                    continue
                out.append(_mins(s["start"], s["end"]))
    return out


def test_mean_session_length(sims):
    sess = _all_full_sessions_min(sims)
    mean = sum(sess) / len(sess)
    assert 65 <= mean <= 75, mean


def test_heavy_tail(sims):
    # A long re-clip is attempted ~15% of the time (LONG_SESSION_P), but it draws
    # lognormal*2 clipped into [120,150] — roughly half of those land at/below 120 and
    # clip to the 120 floor, so the fraction running STRICTLY past 120 min (a genuine
    # heavy-tail session) is ~7%. That tail must exist and be bounded (not runaway).
    sess = _all_full_sessions_min(sims)
    frac = sum(1 for ln in sess if ln > 120) / len(sess)
    assert 0.04 <= frac <= 0.12, frac
    # and no session ever exceeds the hard cap
    assert max(sess) <= 150 + 1e-6


def test_breaks_distribution(sims):
    # regular breaks only (outings are their own distribution, asserted below)
    breaks = [
        _mins(p["sessions"][i]["end"], p["sessions"][i + 1]["start"])
        for plans in sims.values()
        for p in plans
        for i in range(len(p["sessions"]) - 1)
        if not _is_outing_after(p["sessions"], i)
    ]
    mean = sum(breaks) / len(breaks)
    assert BREAK_LO <= mean <= BREAK_HI, mean
    assert min(breaks) >= BREAK_LO - 1e-6 and max(breaks) <= BREAK_HI + 1e-6


# --- r8 long outings (safety variability: 1-2 long [2h,4h] breaks/day) --------------


def test_outing_count_per_day_is_one_or_two(sims):
    # the day DRAWS 1 or 2 outings; it PLACES at most that many (a rare day whose outing
    # target lands inside the final, midnight-truncated session has no trailing break to
    # splice into -> 0 placed). The placed count must match the `outing_after` flags, be
    # in [0, 2], and 0-placed must be vanishingly rare (the day stays mostly covered by
    # outings — that's the whole safety point).
    for name, plans in sims.items():
        zero = 0
        for p in plans:
            n = p.get("outings")
            assert 0 <= n <= 2, (name, p["plan_date"], n)
            flagged = sum(1 for s in p["sessions"] if s.get("outing_after"))
            assert flagged == n, (name, p["plan_date"], flagged, n)
            zero += n == 0
        assert zero / len(plans) < 0.01, (name, zero)  # < 1% of days get no outing


def test_outing_gaps_within_bounds(sims):
    # every flagged outing gap is a real [2 h, 4 h] break
    seen = 0
    for plans in sims.values():
        for p in plans:
            ss = p["sessions"]
            for i in range(len(ss) - 1):
                if _is_outing_after(ss, i):
                    gap = _mins(ss[i]["end"], ss[i + 1]["start"])
                    assert OUTING_LO - 1e-6 <= gap <= OUTING_HI + 1e-6, (
                        p["plan_date"],
                        gap,
                    )
                    seen += 1
    assert seen > 1000  # plenty of outings across ~10k days


def test_outing_count_distribution_spans_one_and_two(sims):
    # the 1-vs-2 choice actually varies day to day (not pinned to a constant) — both
    # outcomes show up at a non-trivial rate across the simulated days.
    for name, plans in sims.items():
        ones = sum(1 for p in plans if p.get("outings") == 1)
        twos = sum(1 for p in plans if p.get("outings") == 2)
        assert ones > 0.2 * len(plans), (name, ones)
        assert twos > 0.2 * len(plans), (name, twos)


def test_daily_play_stays_above_progress_floor(sims):
    # the owner wants PROGRESS: even with the wider tails + the long outings, the MEAN
    # daily play must stay >= ~9 h per account (the outings shave ~1-1.5 h/day, no more).
    for name, plans in sims.items():
        mean_h = sum(p["total_minutes"] / 60 for p in plans) / len(plans)
        assert mean_h >= 9.0, (name, mean_h)


def test_outings_deterministic_and_in_fixed_stream_slot():
    # determinism: the spliced outings are part of the bit-identical plan (same inputs
    # -> same `outings` count + same `outing_after` flags). And the FIXED-slot property:
    # passing the realized first start back as `wake` reproduces the plan incl. outings
    # (a shifted stream would scramble which break became an outing).
    a = S.draw_day_plan("salt", "#TAG", "2026-06-10", 0)
    b = S.draw_day_plan("salt", "#TAG", "2026-06-10", 0)
    assert a == b and a["outings"] in (1, 2)
    start = a["sessions"][0]["start"]
    replay = S.draw_day_plan("salt", "#TAG", "2026-06-10", 0, wake=S._parse(start))
    assert replay == a  # outings + flags reproduce bit-for-bit


# --- anti-self-similarity (the 95%-accuracy detector feature) -----------------------


def _day_vector(p: dict) -> tuple:
    """The day's transition schedule as minutes-of-day (what a detector sees)."""
    out = []
    for s in p["sessions"]:
        for iso in (s["start"], s["end"]):
            t = S._parse(iso)
            out.append(t.hour * 60 + t.minute)
    return tuple(out)


def test_no_identical_consecutive_day_vectors(sims):
    for name, plans in sims.items():
        for prev, cur in zip(plans, plans[1:]):
            assert _day_vector(prev) != _day_vector(cur), (name, cur["plan_date"])


def test_low_day_over_day_start_correlation(sims):
    for name, plans in sims.items():
        xs, ys = [], []
        for prev, cur in zip(plans, plans[1:]):
            pv, cv = _day_vector(prev)[0], _day_vector(cur)[0]
            xs.append(pv)
            ys.append(cv)
        n = len(xs)
        mx, my = sum(xs) / n, sum(ys) / n
        cov = sum((a - mx) * (b - my) for a, b in zip(xs, ys)) / n
        vx = sum((a - mx) ** 2 for a in xs) / n
        vy = sum((b - my) ** 2 for b in ys) / n
        r = cov / (vx**0.5 * vy**0.5)
        assert abs(r) < 0.3, (name, r)


# --- determinism --------------------------------------------------------------------


def test_draw_day_plan_deterministic():
    a = S.draw_day_plan("salt", "#TAG", "2026-06-10", 0)
    b = S.draw_day_plan("salt", "#TAG", "2026-06-10", 0)
    assert a == b
    # any changed seed input -> a different plan
    assert S.draw_day_plan("salt", "#TAG", "2026-06-10", 1) != a
    assert S.draw_day_plan("salt", "#TAG", "2026-06-11", 0) != a
    assert S.draw_day_plan("other", "#TAG", "2026-06-10", 0) != a
    assert S.draw_day_plan("salt", "#OTHER", "2026-06-10", 0) != a


def test_wake_floor_reproduces_via_snapshotted_start():
    # the re-derive contract: passing the plan's own first-session start back as the
    # `wake` floor reproduces the SAME plan bit-for-bit (this is how a lost
    # schedule.json re-derives from the state snapshot).
    base = S.draw_day_plan("salt", "#TAG", "2026-06-10", 0)
    start = base["sessions"][0]["start"]
    replay = S.draw_day_plan("salt", "#TAG", "2026-06-10", 0, wake=S._parse(start))
    assert replay == base


# --- midnight seam (review #67 MAJOR-1: bridge the cross-day gap) --------------------
#
# Before the fix ~28.5% of days ended truncated exactly at 24:00, so the cross-midnight
# gap (day N last-session end -> day N+1 first-session start) fell BELOW the 45-min
# break floor on ~16% of nights (min ~0.1 min — continuous play across midnight, the
# exact 24/7 self-similarity the scheduler exists to break). The fix floors day N+1's
# first session at max(00:00 + phase, prev_day_end + seam_break), seam_break a real
# [45,125] min break drawn from N+1's own RNG stream. The simulate path carries
# prev_day_end across days via the per-account state snapshot.


def _cross_midnight_gaps(plans: list[dict]) -> list[float]:
    out = []
    for a, b in zip(plans, plans[1:]):
        if a["sessions"] and b["sessions"]:
            out.append(_mins(a["sessions"][-1]["end"], b["sessions"][0]["start"]))
    return out


def test_seam_gap_always_at_least_break_floor():
    # The reviewer's simulation, ported: many consecutive days across multiple
    # salts/tags; assert the cross-midnight gap is ALWAYS >= the 45-min break floor.
    # ~250 days x 3 instances x 3 salts ~= 2,200 day-pairs — well past the ~16%
    # pre-fix incidence (so any regression would surface on dozens of nights). Fast:
    # simulate_draws is pure in-memory (~0.1 s per 250-day call).
    all_gaps: list[float] = []
    for salt in ("seam-A", "seam-B", "seam-C"):
        sims_ = S.simulate_draws(250, start=datetime(2026, 1, 1), salt=salt)
        for plans in sims_.values():
            all_gaps += _cross_midnight_gaps(plans)
    assert len(all_gaps) > 500, len(all_gaps)
    # the invariant: every seam gap is itself a real break — never below the floor
    # (exact-floor allowed). No ceiling assert: the gap is the [45,125]-clipped seam
    # break OR the next day's phase, which can only push it later (loose ceiling).
    assert min(all_gaps) >= BREAK_LO - 1e-6, min(all_gaps)


def test_seam_draw_deterministic_and_redrives():
    # determinism: same (salt, tag, date, nonce, prev_day_end) -> identical plan,
    # seam included; a different prev_day_end -> a different plan.
    prev = datetime(2026, 6, 10, 0, 0, 0)  # yesterday ended exactly at midnight
    a = S.draw_day_plan("salt", "#TAG", "2026-06-10", 0, prev_day_end=prev)
    b = S.draw_day_plan("salt", "#TAG", "2026-06-10", 0, prev_day_end=prev)
    assert a == b
    later = S.draw_day_plan(
        "salt", "#TAG", "2026-06-10", 0, prev_day_end=prev + timedelta(minutes=30)
    )
    assert later != a  # prev_day_end participates in the start floor
    # re-derive identity WITH a seam: replaying with the realized first start as the
    # wake floor (and the same prev_day_end) reproduces the plan bit-for-bit.
    start = a["sessions"][0]["start"]
    replay = S.draw_day_plan(
        "salt", "#TAG", "2026-06-10", 0, wake=S._parse(start), prev_day_end=prev
    )
    assert replay == a


def test_seam_floor_pushes_past_midnight_when_prev_ended_at_2400():
    # yesterday truncated at 24:00 -> today's first session must be a full break past
    # midnight (>= 00:45), NOT a few seconds after 00:00.
    prev = datetime(2026, 6, 11, 0, 0, 0)  # == day 2026-06-10's day_end
    p = S.draw_day_plan("salt", "#TAG", "2026-06-11", 0, prev_day_end=prev)
    first = S._parse(p["sessions"][0]["start"])
    gap = (first - prev).total_seconds() / 60.0
    assert BREAK_LO - 1e-6 <= gap <= BREAK_HI + 1e-6, gap


def test_seam_floor_phase_wins_when_prev_ended_early():
    # yesterday ended early (e.g. 22:00) so prev_day_end + seam_break can still be
    # BEFORE 00:00 + phase -> phase wins (max), the seam is a no-op, and the plan is
    # IDENTICAL to one drawn with no prev at all (same RNG stream, seam slot still
    # consumed). Pick a tag whose phase lands the start after the seam floor.
    prev = datetime(2026, 6, 9, 22, 0, 0)  # ended at 22:00, two hours before midnight
    no_prev = S.draw_day_plan("salt", "#TAG", "2026-06-10", 0)
    with_prev = S.draw_day_plan("salt", "#TAG", "2026-06-10", 0, prev_day_end=prev)
    # 22:00 + a <=110 min break is <= 23:50, always before 00:00, so the seam floor is
    # below midnight+phase -> phase wins and the plans match bit-for-bit.
    assert with_prev == no_prev


def test_seam_failsoft_no_snapshot():
    # fail-soft: no prev_day_end (first-ever day / fresh install / old-model state)
    # -> no seam floor at all, plain midnight+phase. The plan is well-formed and its
    # first session can legitimately start moments after 00:00 (no prev to bridge).
    p = S.draw_day_plan("salt", "#TAG", "2026-06-10", 0, prev_day_end=None)
    assert p["sessions"]
    first = S._parse(p["sessions"][0]["start"])
    day0 = datetime(2026, 6, 10, 0, 0, 0)
    # within the phase window past midnight (PHASE_HI_MIN), nothing pushing it later
    assert day0 <= first <= day0 + timedelta(minutes=S.PHASE_HI_MIN + 1e-6)


def test_seam_redrives_via_state_snapshot(tmp_path, monkeypatch):
    # End-to-end: _draw_account_day persists last_session_end (the seam source) and
    # seam_prev (the value fed to THIS draw) into the state snapshot. Draw day N,
    # then day N+1 (seam applied), then RE-DERIVE day N+1 from the snapshot (same
    # plan_date+nonce) and confirm it reproduces — incl. the seam — bit-for-bit, and
    # that the re-derive never recomputes the seam from a changed prev.
    monkeypatch.setenv("BRAWL_SCHED_DATA_ROOT", str(tmp_path))
    monkeypatch.delenv("BRAWL_SCHED_TEST_PLAN", raising=False)
    st: dict = {}
    n1 = S._draw_account_day(
        "salt", "Pie64", "#TAG", st, "2026-06-10", 0, datetime(2026, 6, 10, 0, 0)
    )
    assert st["last_session_end"] == n1["sessions"][-1]["end"]
    n2 = S._draw_account_day(
        "salt", "Pie64", "#TAG", st, "2026-06-11", 0, datetime(2026, 6, 11, 0, 0)
    )
    # the seam: day N+1's first start is a real break past day N's last end
    gap = _mins(n1["sessions"][-1]["end"], n2["sessions"][0]["start"])
    assert gap >= BREAK_LO - 1e-6, gap
    assert st["seam_prev"] == n1["sessions"][-1]["end"]  # snapshot kept yesterday
    # re-derive day N+1 from the (now-mutated) snapshot -> identical plan
    replay = S._draw_account_day(
        "salt", "Pie64", "#TAG", st, "2026-06-11", 0, datetime(2026, 6, 11, 12, 0)
    )
    assert replay["sessions"] == n2["sessions"]
    assert replay["day_end"] == n2["day_end"]


# --- cross-account phase stagger (round 6) ------------------------------------------


def test_accounts_do_not_start_in_lockstep(sims):
    # The stagger property we actually implement: on a given date, the accounts' first
    # session starts (which carry the phase) are not all identical — they're spread by
    # their distinct phase offsets. Pin it: per date, the spread across accounts > a
    # few minutes on essentially every day.
    by_date: dict[str, list[int]] = {}
    for plans in sims.values():
        for p in plans:
            t = S._parse(p["sessions"][0]["start"])
            by_date.setdefault(p["plan_date"], []).append(t.hour * 60 + t.minute)
    identical = 0
    for date, firsts in by_date.items():
        if len(set(firsts)) == 1:
            identical += 1
    # at most a negligible fraction of days have all-equal first-starts
    assert identical / len(by_date) < 0.01, identical


# --- games counting (D4) -------------------------------------------------------------


def _utc_bt(local: datetime) -> str:
    return local.astimezone().astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S.000Z")


def _write_games_csv(path, battle_locals, logged_at):
    rows = ["battleTime,logged_at,event_mode"]
    rows += [f"{_utc_bt(b)},{logged_at},trioShowdown" for b in battle_locals]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def test_games_played_since(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAWL_SCHED_DATA_ROOT", str(tmp_path))
    now = datetime(2026, 6, 10, 15, 0, 0)
    since = datetime(2026, 6, 10, 7, 0, 0)
    d = tmp_path / "data" / "Pie64"
    # 3 battles this window + 1 earlier (must not count)
    _write_games_csv(
        d / "games.csv",
        [
            now - timedelta(hours=2),
            now - timedelta(hours=1),
            now - timedelta(minutes=5),
            since - timedelta(hours=10),
        ],
        logged_at="2026-06-10T14:00:00",
    )
    assert S.games_played_since("Pie64", since, now) == 3
    # live worker: status says 5 games this session; csv only has 3 logged after
    # the session started -> 2 are still in battlelog lag -> played = 3 + 2
    (d / "status.json").write_text(
        json.dumps(
            {
                "ts": now.strftime("%Y-%m-%dT%H:%M:%S"),
                "pid": 1234,
                "games_played": 5,
                "session": "session-20260610-120000.jsonl",
            }
        ),
        encoding="utf-8",
    )
    assert S.games_played_since("Pie64", since, now) == 5


def test_tick_writes_nonzero_games_played_today(tmp_path, monkeypatch):
    """r10 regression (review MAJOR): the tick read plan["wake"] — a key plan dicts
    never carry (the wake lives in the STATE snapshot) — and the KeyError was
    swallowed into played=0, so schedule.json reported games_played_today: 0
    forever. Through the real tick/file path: draw a day, seed games.csv battles
    inside it, tick again, and the file must carry the real (nonzero) count."""
    monkeypatch.setenv("BRAWL_SCHED_DATA_ROOT", str(tmp_path))
    monkeypatch.delenv("BRAWL_SCHED_TEST_PLAN", raising=False)
    monkeypatch.setattr("os.urandom", lambda n: b"\x02" * n)
    t0 = datetime(2026, 6, 10, 9, 0, 0)
    assert S.tick(t0) == 0  # first tick draws the day (start floored at t0)
    state = json.loads(
        (tmp_path / "data" / "scheduler_state.json").read_text(encoding="utf-8")
    )
    wake = S._parse(state["accounts"]["Pie64"]["wake"])
    # three battles well inside the play-day, after the realized start
    _write_games_csv(
        tmp_path / "data" / "Pie64" / "games.csv",
        [wake + timedelta(hours=h) for h in (1, 2, 3)],
        logged_at="2026-06-10T14:00:00",
    )
    assert S.tick(wake + timedelta(hours=4)) == 0
    assert _plan(tmp_path, "Pie64")["games_played_today"] == 3


# --- compressed-time tick sweep (multi-day, fake clock, pinned salt) -----------------


def _desired(tmp_path, name) -> dict:
    p = tmp_path / "data" / name / "schedule.json"
    return json.loads(p.read_text(encoding="utf-8"))["desired"]


def _plan(tmp_path, name) -> dict:
    p = tmp_path / "data" / name / "schedule.json"
    return json.loads(p.read_text(encoding="utf-8"))


def _expected_state(plan: dict, now: datetime) -> str:
    for s in plan["sessions"]:
        start = S._parse(s["start"]) + timedelta(seconds=int(s["entry_delay_s"]))
        if start <= now < S._parse(s["end"]):
            return "run"
    return "stop"


# The plan shapes are a pure function of (salt, tag, date, nonce) and the alternation
# starts at midnight + phase regardless of when the first tick runs, so with the salt
# pinned (inside the test) every sweep walks the identical plan-days. Start times span
# mid-day and both sides of the midnight boundary.
# r9 (suite speedup): a 2-day sweep crosses at least one midnight boundary for
# every start time, which is all the seam/roll/immutability invariants need
# (the dedicated test_seam_* tests below pin the midnight math exhaustively, and
# the determinism crash-redraw fires on the day-after-start mid-afternoon). Two
# days @ 5-min steps is ~half the old 6-day cost — the dominant chunk of the
# whole suite — with the SAME coverage.
@pytest.mark.parametrize(
    ("start", "days"),
    [
        pytest.param(datetime(2026, 6, 10, 9, 0), 2, id="mid-day"),
        pytest.param(datetime(2026, 6, 10, 23, 0), 2, id="late-night"),
        pytest.param(datetime(2026, 6, 10, 23, 59), 2, id="23-59"),
        pytest.param(datetime(2026, 6, 11, 0, 0), 2, id="00-00"),
    ],
)
def test_tick_sweep_multi_day(tmp_path, monkeypatch, start, days):
    monkeypatch.setenv("BRAWL_SCHED_DATA_ROOT", str(tmp_path))
    monkeypatch.delenv("BRAWL_SCHED_TEST_PLAN", raising=False)
    # The per-install salt (os.urandom on the first enabled tick) is the ONLY
    # nondeterminism in the tick path — everything else runs on the injected fake
    # clock. Pin it so every run sweeps the identical plan-days.
    monkeypatch.setattr("os.urandom", lambda n: b"\x02" * n)
    names = list(S.config.INSTANCES)
    now = start

    # DEFAULT-ON: NO control file means the scheduler is ACTIVE — the very first tick
    # draws plans and gates on them.
    assert S.tick(now) == 0
    assert (tmp_path / "data" / "scheduler_state.json").exists()
    plans = {n: _plan(tmp_path, n) for n in names}
    for n in names:
        assert plans[n]["sessions"] is not None
        assert plans[n]["desired"]["enabled"] is True

    deletion_done = False
    end = start + timedelta(days=days)
    step = timedelta(minutes=5)
    # Crash-redraw probe: the day AFTER start, mid-afternoon — always inside the
    # 2-day window for every parametrized start (was a fixed day-3 date back when
    # the sweep ran 6 days).
    del_at = start.replace(hour=14, minute=0, second=0, microsecond=0) + timedelta(
        days=1
    )
    while now < end:
        now += step
        assert S.tick(now) == 0
        for n in names:
            sched = _plan(tmp_path, n)
            d = sched["desired"]
            assert d["state"] == _expected_state(sched, now), (n, now)
            if d["state"] == "run":
                assert d["reason"] in ("session", "override_run")
                assert d["max_minutes"] and d["max_minutes"] >= 1
                # round 6: the games budget is gone — no max_games cap anymore
                assert d["max_games"] is None
            else:
                assert d["reason"] in ("gap", "override_stop")
            # plan immutability within its play-day
            if plans[n]["plan_date"] == sched["plan_date"]:
                assert plans[n]["sessions"] == sched["sessions"], (n, now)
            else:
                assert now >= S._parse(plans[n]["day_end"])  # rolled at the boundary
                # r10: the midnight-seam invariant through the REAL tick()/file
                # path (the dedicated test_seam_* tests pin it via simulate/
                # draw_day_plan only): the new day's first session starts at
                # least a break floor past the old day's last session end.
                if plans[n]["sessions"] and sched["sessions"]:
                    seam = _mins(
                        plans[n]["sessions"][-1]["end"],
                        sched["sessions"][0]["start"],
                    )
                    assert seam >= BREAK_LO - 1e-6, (n, now, seam)
                plans[n] = sched

        # day-after-start, mid-day: delete a plan file -> the next tick must
        # re-derive the IDENTICAL plan from the state snapshot (determinism, no
        # fresh roll on crash)
        if not deletion_done and now >= del_at:
            before = _plan(tmp_path, "Pie64")
            (tmp_path / "data" / "Pie64" / "schedule.json").unlink()
            assert S.tick(now) == 0
            after = _plan(tmp_path, "Pie64")
            assert after["sessions"] == before["sessions"]
            assert after["day_end"] == before["day_end"]
            plans["Pie64"] = after
            deletion_done = True

    assert deletion_done


def test_overrides(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAWL_SCHED_DATA_ROOT", str(tmp_path))
    monkeypatch.delenv("BRAWL_SCHED_TEST_PLAN", raising=False)
    S.set_enabled(list(S.config.INSTANCES), True)
    # mid-morning, inside a break before the first session OR between sessions —
    # we find an explicit gap moment below.
    now = datetime(2026, 6, 10, 9, 0, 0)
    assert S.tick(now) == 0
    plan = _plan(tmp_path, "Pie64")

    # find a moment that is NOT inside any session (a break) to test the run override
    sessions = plan["sessions"]
    in_gap = None
    for a, b in zip(sessions, sessions[1:]):
        cand = S._parse(a["end"]) + timedelta(minutes=10)
        if cand < S._parse(b["start"]):
            in_gap = cand
            break
    assert in_gap is not None, "no break found to test override"

    # /start during a scheduled break -> run override until a bounded time
    S.write_override("Pie64", "run", in_gap + timedelta(hours=1))
    assert S.tick(in_gap) == 0
    d = _desired(tmp_path, "Pie64")
    assert d["state"] == "run" and d["reason"] == "override_run"
    assert d["max_minutes"] == pytest.approx(60, abs=1)

    # expiry: past `until` the override file is deleted and the schedule resumes
    after = in_gap + timedelta(hours=1, minutes=5)
    assert S.tick(after) == 0
    assert not (tmp_path / "data" / "Pie64" / "override.json").exists()

    # /stop during a session -> stop override wins over the session window
    mid = S._parse(sessions[0]["start"]) + timedelta(
        seconds=int(sessions[0]["entry_delay_s"]) + 60
    )
    S.write_override("Pie64", "stop", S._parse(sessions[0]["end"]))
    assert S.tick(mid) == 0
    d = _desired(tmp_path, "Pie64")
    assert d["state"] == "stop" and d["reason"] == "override_stop"
    S.clear_override("Pie64")

    # /schedule off -> immediately back to always-run (fail-open posture)
    S.set_enabled(list(S.config.INSTANCES), False)
    assert S.tick(mid) == 0
    d = _desired(tmp_path, "Pie64")
    assert d["state"] == "run" and d["reason"] == "disabled"


def test_until_run_override_wins_then_plan_resumes():
    """r8 /schedule until: a RUN override forces `run` through any scheduled break
    until T, then — once expired — evaluate() falls straight back to the normal plan.
    Pure evaluate() (no disk): pick a plan with a real break, assert the override
    flips that break to run while live, and that the SAME break reads `gap` again once
    the override is past."""
    plan = S.draw_day_plan("salt", "#TAG", "2026-06-10", 0)
    sessions = plan["sessions"]
    # a moment squarely inside a scheduled break (between two sessions)
    in_break = None
    for a, b in zip(sessions, sessions[1:]):
        cand = S._parse(a["end"]) + timedelta(minutes=5)
        if cand + timedelta(minutes=5) < S._parse(b["start"]):
            in_break = cand
            break
    assert in_break is not None
    # baseline: with no override that moment is a scheduled break (stop/gap)
    base = S.evaluate(in_break, plan, 0, None, enabled=True)
    assert base["state"] == "stop" and base["reason"] == "gap"
    # an until-override to 30 min out: run wins through the break
    until = in_break + timedelta(minutes=30)
    ov = {"mode": "run", "until": S._iso(until)}
    live = S.evaluate(in_break, plan, 0, ov, enabled=True)
    assert live["state"] == "run" and live["reason"] == "override_run"
    assert live["max_minutes"] == pytest.approx(30, abs=1)
    # past T (the tick would have deleted the file; evaluate treats an expired override
    # as absent) -> the normal plan resumes: the same break reads `gap` again
    resumed = S.evaluate(until + timedelta(minutes=1), plan, 0, None, enabled=True)
    assert resumed["reason"] in ("gap", "session")
    # and an EXPIRED override passed in still yields to the plan (now>until branch)
    expired = S.evaluate(until + timedelta(minutes=1), plan, 0, ov, enabled=True)
    assert expired["reason"] in ("gap", "session")


def test_default_on_then_last_set_semantics(tmp_path, monkeypatch):
    """DEFAULT-ON, then LAST-SET (round 6): missing control file, missing account
    entry, and an entry WITHOUT the `enabled` key all schedule; only an explicit
    enabled=false (what /schedule off writes) is legacy always-run. The flag is
    last-set — /start no longer flips it (tested in test_start_no_reenable.py)."""
    monkeypatch.setenv("BRAWL_SCHED_DATA_ROOT", str(tmp_path))
    monkeypatch.delenv("BRAWL_SCHED_TEST_PLAN", raising=False)
    monkeypatch.setattr("os.urandom", lambda n: b"\x02" * n)
    now = datetime(2026, 6, 10, 9, 0, 0)

    # mixed control file: Pie64 explicitly OFF, Nest32 key-less entry (a bump_nonce
    # leftover), Rook17 absent entirely
    S._write_json(
        tmp_path / "data" / "scheduler_control.json",
        {"accounts": {"Pie64": {"enabled": False, "nonce": 0}, "Nest32": {"nonce": 0}}},
    )
    assert S.tick(now) == 0
    d = _desired(tmp_path, "Pie64")
    assert d["state"] == "run" and d["reason"] == "disabled"  # explicit opt-out
    assert d["max_minutes"] is None and d["max_games"] is None
    for n in ("Nest32", "Rook17"):
        sched = _plan(tmp_path, n)
        assert sched["sessions"] is not None, n  # a real play-day was drawn
        assert sched["desired"]["enabled"] is True, n

    # a redraw nonce-bump must NOT flip a default-on account off
    S.bump_nonce("Rook17")
    ctl = S.read_control()["accounts"]["Rook17"]
    assert "enabled" not in ctl  # key stays absent -> still default-on
    assert S.tick(now) == 0
    assert _plan(tmp_path, "Rook17")["desired"]["enabled"] is True


def test_all_explicitly_off_is_legacy_for_everyone(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAWL_SCHED_DATA_ROOT", str(tmp_path))
    names = list(S.config.INSTANCES)
    S.set_enabled(names, False)  # /schedule off all
    assert S.tick(datetime(2026, 6, 10, 9, 0, 0)) == 0
    for n in names:
        d = _desired(tmp_path, n)
        assert d["state"] == "run" and d["reason"] == "disabled"
        assert d["max_minutes"] is None and d["max_games"] is None
    # the all-off fast path never creates scheduler state
    assert not (tmp_path / "data" / "scheduler_state.json").exists()


def test_old_plan_file_tolerated_in_evaluate(tmp_path, monkeypatch):
    """An old-model schedule.json (sleep/is_rest/games_budget, NO day_end) left on
    disk must not crash or strand: evaluate() treats it as no_plan (fail-open
    always-run) until the next tick draws a new-model day."""
    monkeypatch.setenv("BRAWL_SCHED_DATA_ROOT", str(tmp_path))
    now = datetime(2026, 6, 10, 9, 0, 0)
    old = {
        "account": "Pie64",
        "plan_date": "2026-06-10",
        "nonce": 0,
        "is_rest": False,
        "games_budget": 80,
        "sleep": {"start": "2026-06-10T22:00:00", "end": "2026-06-11T06:00:00"},
        "sessions": [
            {
                "start": "2026-06-10T08:00:00",
                "end": "2026-06-10T09:00:00",
                "entry_delay_s": 0,
            }
        ],
        "total_minutes": 60.0,
    }
    # evaluate() directly: no day_end -> no_plan (fail-open run)
    d = S.evaluate(now, old, 0, None, enabled=True)
    assert d["state"] == "run" and d["reason"] == "no_plan"
    assert d["max_games"] is None
    # and a full tick with this stale file present still succeeds and overwrites it
    monkeypatch.setattr("os.urandom", lambda n: b"\x02" * n)
    S._write_json(tmp_path / "data" / "Pie64" / "schedule.json", old)
    S.set_enabled(list(S.config.INSTANCES), True)
    assert S.tick(now) == 0
    fresh = _plan(tmp_path, "Pie64")
    assert "day_end" in fresh and "games_budget" not in fresh


def test_fail_open_on_scheduler_error(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAWL_SCHED_DATA_ROOT", str(tmp_path))

    def boom(now):
        raise RuntimeError("injected scheduler bug")

    monkeypatch.setattr(S, "_tick_inner", boom)
    assert S.tick(datetime(2026, 6, 10, 9, 0)) == 1  # nonzero -> watchdog logs it
    for n in S.config.INSTANCES:
        d = _desired(tmp_path, n)
        assert d["state"] == "run" and d["reason"] == "scheduler_error"


def test_test_plan_hook(tmp_path, monkeypatch):
    # The supervised-live-cycle hook: compressed 10-min sessions / 5-min gaps.
    monkeypatch.setenv("BRAWL_SCHED_DATA_ROOT", str(tmp_path))
    monkeypatch.setenv("BRAWL_SCHED_TEST_PLAN", "1")
    S.set_enabled(["Pie64"], True)
    now = datetime(2026, 6, 10, 9, 0, 0)
    assert S.tick(now) == 0
    plan = _plan(tmp_path, "Pie64")
    assert plan["test_plan"] is True
    assert len(plan["sessions"]) == 4
    for s in plan["sessions"]:
        assert _mins(s["start"], s["end"]) == 10
    # in-session -> run with caps; in-gap -> stop
    s0 = plan["sessions"][0]
    t_in = S._parse(s0["start"]) + timedelta(minutes=1)
    assert S.tick(t_in) == 0
    assert _desired(tmp_path, "Pie64")["state"] == "run"
    t_gap = S._parse(s0["end"]) + timedelta(minutes=1)
    assert S.tick(t_gap) == 0
    assert _desired(tmp_path, "Pie64")["state"] == "stop"
