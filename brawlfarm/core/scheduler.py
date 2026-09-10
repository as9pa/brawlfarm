"""Anti-ban scheduler — computes per-account desired run/stop state (P2).

WHY: 24/7 uptime + day-after-day self-similarity are the two macro ban tells
(docs/research/ban-mechanics.md). This module draws a randomized, human-shaped
play-day per account and continuously evaluates "should this farm be running
RIGHT NOW?" into ``data/<acct>/schedule.json``. It never launches or kills
anything itself: the supervisor stays the only automatic launcher/killer and the
control panel the only manual one — they just *gate* on the ``desired``
block written here.

DAY MODEL (round 6 redesign, docs/more instructions.md — "remove the sleep thing.
we should just have random hourly breaks in between"): a plan covers its FULL
local day (00:00 -> 24:00) by ALTERNATING play-session -> break -> play-session ->
… until the next-midnight boundary. There is NO overnight sleep block, NO rest
days, and NO daily total-hours cap — the day is filled by alternation, not capped.
Sessions keep the existing per-session lognormal length distribution; breaks are
lognormal "random hourly" gaps clipped to [45, 125] min (r8 widened the tail
110 -> 125). A session that would cross midnight is truncated to the boundary,
and the NEXT day's first session is floored a real [45, 125] min break past it
(the "midnight seam" — review #67 MAJOR-1) so play never runs continuously
across midnight: the [45,125] break invariant holds ACROSS days too, not just
within one. The previous
sleep/rest/budget model is GONE — old schedule.json files that still carry
``sleep`` / ``is_rest`` / ``games_budget`` are simply tolerated (keys ignored).

ARCHITECTURE (no resident process, no midnight cron):
  - The watchdog runs ``python -m brawlfarm.core.scheduler tick`` each 60 s loop.
  - A tick draws a full play-day plan (absolute local timestamps) the first time
    it runs on/after the previous plan's day_end (the next-midnight boundary);
    later ticks are pure evaluation.
  - EVERY draw is seeded ``SHA256(salt:tag:date:nonce[:purpose])`` ->
    ``random.Random`` — identical inputs give a bit-identical plan, so a crash or
    plan-file loss redraw reproduces the EXACT same day, never a fresh roll.
  - Cross-day state lives in ONE file, ``data/scheduler_state.json``; its single
    writer is the tick. The control panel's schedule controls write a separate
    ``data/scheduler_control.json`` (enabled flags + redraw nonces) that the tick
    reads — one writer per file, no lock needed.
  - Manual overrides: ``data/<acct>/override.json`` {mode, until} written by the
    control panel; honored by evaluate() until expiry (the tick deletes
    expired ones).

CROSS-ACCOUNT STAGGER (round 6 — simplified): two farms must not start sessions
in lockstep. The old transition-by-transition nudge machinery assumed a small
fixed set of transitions (sleep/few sessions); the new all-day alternation has
many more. So instead each account gets a deterministic per-account PHASE OFFSET
(drawn from its seed) applied to the first session start — different phases mean
the whole session/break rhythm is shifted relative to the other accounts, so they
never line up at 00:00. Simpler than re-nudging dozens of transitions and good
enough for 3 instances (documented choice, docs/bot/scheduler.md).

FAIL-OPEN CONTRACT: any tick exception writes desired=run reason=scheduler_error
for ALL accounts and exits nonzero — a scheduler bug must NEVER strand farms
stopped. DEFAULT-ON, then LAST-SET (round 6, docs/more instructions.md — "just
make it be set to the last thing that was set"): a missing control file, a
missing account entry, or an entry without the ``enabled`` key all mean the
scheduler IS enabled (a never-set account stays ON). The flag is then last-set:
only ``/schedule on|off`` writes it — ``/start`` no longer flips it. An explicit
enabled=false (``/schedule off``) opts an account into legacy always-run
(desired=run reason=disabled, no caps).

IMPORT BUDGET: this runs every 60 s — stdlib + config only (config imports
dotenv, ~40 ms). It must NOT import cv2/RapidOCR/core.adb/core.vision, directly or
transitively. ``python -c "import brawlfarm.core.scheduler"`` must stay < 0.5 s.

FILE FORMATS — see docs/bot/scheduler.md (the ops runbook).

CLI:
  python -m brawlfarm.core.scheduler tick [--now ISO]        # the watchdog's call
  python -m brawlfarm.core.scheduler preview [--days N]      # human-readable timeline (no writes)
  python -m brawlfarm.core.scheduler simulate --days 365     # distribution sanity stats (no writes)
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import sys
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

from brawlfarm.core import config
from brawlfarm.core.jsonio import atomic_write_json

# --- Randomization model (docs/research/ban-mechanics.md §5; all per-day draws) ---

# Round 6 redesign (docs/more instructions.md): NO sleep block, NO rest days, NO
# daily total-hours cap. A plan covers the full local day (00:00 -> 24:00) by
# alternating session -> break -> session -> … until the boundary. Daily volume is
# bounded by the alternation itself (a session + a >=45 min break each cycle), not
# by a games budget or an hours cap.

# Per-session length: lognormal, the SAME distribution the old model used for an
# individual session. mu set below ln(65) so the [30,120] clip + the occasional
# long re-clip land the realized session mean in the 65-75 min band (simulation-
# calibrated). 15% of sessions are re-clipped LONG [120,150] (heavy tail); hard
# cap 150.
SESSION_MU, SESSION_SIGMA = math.log(58), 0.45
SESSION_LO_MIN, SESSION_HI_MIN = 30, 120
LONG_SESSION_P = 0.15
LONG_LO_MIN, LONG_HI_MIN = 120, 150
SESSION_HARD_CAP_MIN = 150
# Breaks ("random hourly" gaps): lognormal clipped to [45, 125] min — the round-6
# replacement for the old [45 min, 4 h] gap + the deleted sleep block. mu = ln(70)
# centres breaks a bit over an hour; the ceiling keeps a "regular" break from growing
# into a de-facto sleep. r8: the ceiling widened 110 -> 125 min so the regular-break
# tail is a touch less flat (a perfectly uniform "heartbeat" is itself a tell); small
# enough that daily play stays >= ~9 h (verified by simulate / tests).
GAP_MU, GAP_SIGMA = math.log(70), 0.5
GAP_LO_MIN, GAP_HI_MIN = 45, 125
# OUTING BREAKS (r8 — owner: "optimize scheduling a little more so it's safer"). A real
# person is away from the game for a long stretch most days (errands, work, a lie-in) —
# not just a steady 1-2 h heartbeat all day. So 1-2 "long outing" breaks per day get
# spliced in: lognormal clipped to [2 h, 4 h], REPLACING the regular break that happens
# to straddle a deterministically-drawn target time-of-day. They are drawn from the
# day's own RNG in a FIXED stream slot (right after the seam break, before the session
# loop) so determinism + the snapshot re-derive stay bit-identical; the regular-break
# draw an outing replaces is STILL consumed, so the session-loop stream position never
# shifts on whether an outing landed. This breaks up the too-regular cadence WITHOUT
# reviving the removed sleep/rest machinery — no overnight block, no rest days, no hours
# cap, just a couple of longer gaps. Net effect on volume is modest (~1-1.5 h/day) so
# the owner's "make PROGRESS" bar (>= ~9 h/day mean) still holds.
OUTING_MIN_COUNT, OUTING_MAX_COUNT = 1, 2  # 1 or 2 outings per day (inclusive)
OUTING_LO_MIN, OUTING_HI_MIN = 120, 240  # [2 h, 4 h] clip
OUTING_MU, OUTING_SIGMA = math.log(165), 0.4  # centres outings ~2.75 h within the clip
# Outings sit away from the day's edges (no point "outing" at 00:30 just past the seam
# break, or in the day's final sliver) — target times are this fraction band of the
# 00:00 -> 24:00 window.
OUTING_TARGET_LO, OUTING_TARGET_HI = 0.12, 0.9
# Cross-account stagger (round 6 — simplified to a per-account PHASE OFFSET; see the
# module docstring). The day's first session starts this many minutes past 00:00,
# drawn U(0, PHASE_HI_MIN). Different per-account phases shift each account's whole
# session/break rhythm so two farms never start in lockstep at midnight.
PHASE_LO_MIN, PHASE_HI_MIN = 0, 120
# Per-session re-entry delay U(0-7 min): even within one account's plan, a launch
# starts this many seconds AFTER the window opens, so a relaunch is never at an
# exact round time.
ENTRY_DELAY_HI_S = 7 * 60

DESIRED_FRESH_S = 600  # consumers treat desired blocks older than this as stale
STATUS_FRESH_S = 240  # matches the watchdog/manager heartbeat staleness
TIME_FMT = "%Y-%m-%dT%H:%M:%S"


# --- paths (env-overridable root so tests run against a tmp dir) ---------------


def _root() -> Path:
    return Path(os.environ.get("BRAWL_SCHED_DATA_ROOT", "") or config.HOME_DIR)


def _state_path() -> Path:
    return _root() / "data" / "scheduler_state.json"


def _control_path() -> Path:
    return _root() / "data" / "scheduler_control.json"


def _acct_dir(name: str) -> Path:
    return _root() / config.INSTANCES[name]["data"]


def _schedule_path(name: str) -> Path:
    return _acct_dir(name) / "schedule.json"


def _override_path(name: str) -> Path:
    return _acct_dir(name) / "override.json"


# --- tiny json/time helpers ----------------------------------------------------


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json(path: Path, payload: dict) -> None:
    """Atomic write so a reader never catches a half-written file (core/jsonio.py)."""
    atomic_write_json(path, payload)


def _iso(dt: datetime) -> str:
    return dt.strftime(TIME_FMT)


def _parse(s: str) -> datetime:
    return datetime.strptime(s, TIME_FMT)


def _hhmm(s: str | None) -> str:
    if not s:
        return "?"
    try:
        return _parse(s).strftime("%H:%M")
    except ValueError:
        return s


def _rng(salt: str, tag: str, date_str: str, nonce: int, purpose: str = ""):
    """The determinism contract: every draw is seeded from the full identity of
    what is being drawn, so identical inputs always reproduce the identical plan."""
    import random  # stdlib; local import keeps module namespace tidy

    h = hashlib.sha256(f"{salt}:{tag}:{date_str}:{nonce}:{purpose}".encode()).digest()
    return random.Random(int.from_bytes(h[:16], "big"))


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


# --- pure draw: one account-day --------------------------------------------------


def _draw_session_len(rng) -> float:
    """One session length in minutes: lognormal clipped [30,120], with a
    LONG_SESSION_P chance it is re-clipped into the long tail [120,150]. This is
    exactly the per-session draw the old model used (reused verbatim per the round-6
    brief — only the day-fill logic around it changed)."""
    ln = _clip(rng.lognormvariate(SESSION_MU, SESSION_SIGMA), SESSION_LO_MIN, SESSION_HI_MIN)
    if rng.random() < LONG_SESSION_P:  # occasional heavy-tail long session
        ln = _clip(
            rng.lognormvariate(SESSION_MU, SESSION_SIGMA) * 2.0,
            LONG_LO_MIN,
            LONG_HI_MIN,
        )
    return ln


def _draw_break(rng) -> float:
    """One break ("random hourly" gap) in minutes: lognormal clipped [45,125]."""
    return _clip(rng.lognormvariate(GAP_MU, GAP_SIGMA), GAP_LO_MIN, GAP_HI_MIN)


def _draw_outings(rng) -> list[tuple[float, float]]:
    """Draw the day's long-outing breaks (r8) in a FIXED RNG-stream slot. Returns a
    list of ``(target_minute_of_day, duration_min)`` sorted by target time — one entry
    per outing the day will try to place.

    Stream stability is the whole game: this ALWAYS consumes the same number of draws
    (a count draw + ``OUTING_MAX_COUNT`` target/duration pairs) regardless of how many
    outings end up active, so the session loop downstream sees an identical stream
    position whether the day got 1 outing or 2. We just drop the unused pairs.

    ``target_minute_of_day`` is where in the 00:00->24:00 day the outing wants to land;
    the session loop splices the outing into the first regular break that starts at or
    after it (so the outing replaces a break, never a session)."""
    count = rng.randint(OUTING_MIN_COUNT, OUTING_MAX_COUNT)
    pairs: list[tuple[float, float]] = []
    for _ in range(OUTING_MAX_COUNT):  # always draw MAX — keeps the stream position fixed
        frac = rng.uniform(OUTING_TARGET_LO, OUTING_TARGET_HI)
        dur = _clip(rng.lognormvariate(OUTING_MU, OUTING_SIGMA), OUTING_LO_MIN, OUTING_HI_MIN)
        pairs.append((frac * 1440.0, dur))
    return sorted(pairs[:count])


def draw_day_plan(
    salt: str,
    tag: str,
    date_str: str,
    nonce: int,
    *,
    wake: datetime | None = None,
    phase_min: float | None = None,
    prev_day_end: datetime | None = None,
    attempt: int = 0,
) -> dict:
    """PURE: draw one account play-day. Same (salt, tag, date, nonce, wake/phase,
    prev_day_end, attempt) -> bit-identical plan. All timestamps are naive LOCAL
    absolute datetimes serialized as ISO strings.

    The day is the local 00:00 -> 24:00 window. The alternation begins at
    ``max(midnight + PHASE, prev_day_end + seam_break, wake)`` and runs session ->
    break -> session -> … until the next-midnight boundary, truncating a session
    that would cross it. PHASE is the deterministic per-account cross-account
    stagger offset (seed-drawn unless ``phase_min`` is given).

    SEAM BREAK (round-6 MAJOR fix, review #67): yesterday's last session often gets
    truncated exactly at 24:00, and a bare ``midnight + phase`` start could put
    today's first session a handful of minutes (sometimes seconds) later — continuous
    play straddling midnight, the exact 24/7 self-similarity this module exists to
    break, and a violation of the documented "every break ∈ [45,125] min" invariant
    ACROSS the seam. So when the caller supplies ``prev_day_end`` (yesterday's last
    session end, from the scheduler_state snapshot), the first session is floored at
    ``prev_day_end + seam_break``, where ``seam_break`` is a normal lognormal break
    drawn from THIS day's own RNG stream. Fail-soft: ``prev_day_end is None`` (the
    first-ever day, a fresh install, or an old-model state file) -> no seam floor,
    plain midnight+phase. ``prev_day_end`` is yesterday's reality (snapshotted, never
    recomputed) so a mid-day redraw/re-derive keeps the same seam.

    ``wake`` is an EARLIEST-start floor: at the normal midnight rollover it's <=
    the computed start so phase+seam win; a fresh mid-day enable passes a later
    ``wake`` so the day doesn't backfill the morning; a re-derive passes the
    snapshotted first-session start (which already baked in the seam) so the lost
    plan reproduces bit-for-bit. ``attempt`` is kept for signature stability; the
    simplified stagger never redraws, so it only varies the seed if nonzero."""
    rng = _rng(salt, tag, date_str, nonce, f"day{attempt}" if attempt else "")
    day0 = datetime.strptime(date_str, "%Y-%m-%d")
    day_end = day0 + timedelta(days=1)  # the next-midnight boundary

    # FIXED RNG-stream draw order (so a mid-day re-derive replaying with the
    # snapshotted start as `wake` reproduces the plan bit-for-bit):
    #   1. phase draw   2. seam-break draw   3. the outing specs   4. session/break loop.
    # The three leading draws are ALWAYS consumed in full — even when their value is
    # overridden or unused (phase_min given / prev_day_end None / fewer outings active)
    # — so the stream position for the session loop never depends on which floors were
    # supplied or how many outings end up placed.
    drawn_phase = rng.uniform(PHASE_LO_MIN, PHASE_HI_MIN)
    if phase_min is None:
        phase_min = drawn_phase
    seam_break = _draw_break(rng)  # slot 2: a real [45,125] min break across midnight
    outings = _draw_outings(rng)  # slot 3 (r8): [(target_min_of_day, duration_min), …]
    start = day0 + timedelta(minutes=phase_min)
    if prev_day_end is not None:  # bridge the midnight seam (review #67 MAJOR-1)
        seam_floor = prev_day_end + timedelta(minutes=seam_break)
        if seam_floor > start:  # prev day ran late -> push past phase; else phase wins
            start = seam_floor
    if wake is not None and wake > start:  # mid-day enable / re-derive: keep the floor
        start = wake
    if start < day0:
        start = day0

    sessions: list[dict] = []
    t = start
    oi = 0  # next outing to try to place (outings is sorted by target time)
    outings_placed = 0
    while t < day_end:
        ln = _draw_session_len(rng)
        end = t + timedelta(minutes=ln)
        if end > day_end:  # a session crossing midnight is truncated to the boundary
            end = day_end
        # drop a degenerate sliver (< the session floor) at the very end of the day
        if (end - t).total_seconds() / 60.0 < SESSION_LO_MIN and end >= day_end:
            break
        sessions.append(
            {
                "start": _iso(t),
                "end": _iso(end),
                "entry_delay_s": int(rng.uniform(0, ENTRY_DELAY_HI_S)),
            }
        )
        if end >= day_end:
            break
        # The break after this session. The regular [45,125] break is ALWAYS drawn
        # (stream stability); an outing whose target time-of-day this session has
        # reached SPLICES IN its long [2h,4h] duration in place of that value. Only
        # the FIRST eligible outing is placed at a given break, and a placed outing
        # is consumed (oi advances) so two outings never collapse onto one break.
        brk = _draw_break(rng)
        end_min_of_day = (end - day0).total_seconds() / 60.0
        if oi < len(outings) and end_min_of_day >= outings[oi][0]:
            brk = outings[oi][1]
            sessions[-1]["outing_after"] = True  # this session is followed by an outing
            oi += 1
            outings_placed += 1
        t = end + timedelta(minutes=brk)

    total_min = sum(
        (_parse(s["end"]) - _parse(s["start"])).total_seconds() / 60.0 for s in sessions
    )
    return {
        "plan_date": date_str,
        "nonce": nonce,
        "phase_min": round(phase_min, 2),
        "sessions": sessions,
        "day_end": _iso(day_end),
        "total_minutes": round(total_min, 1),
        "outings": outings_placed,  # r8: long [2h,4h] breaks actually spliced in today
        "test_plan": False,
    }


def _test_plan(now: datetime) -> dict:
    """BRAWL_SCHED_TEST_PLAN=1 hook (supervised live test only): compressed
    10-min sessions / 5-min gaps so a full launch->self-stop->gap->relaunch
    cycle is observable in under an hour. Never used in normal operation.

    day_end is the LAST session's end + 5 min (not real midnight) so the
    supervised test rolls a fresh plan promptly instead of waiting out the day."""
    t = now + timedelta(seconds=90)
    sessions = []
    for _ in range(4):
        sessions.append(
            {
                "start": _iso(t),
                "end": _iso(t + timedelta(minutes=10)),
                "entry_delay_s": 0,
            }
        )
        t += timedelta(minutes=15)
    day_end = _parse(sessions[-1]["end"]) + timedelta(minutes=5)
    return {
        "plan_date": now.strftime("%Y-%m-%d"),
        "nonce": 0,
        "phase_min": 0.0,
        "sessions": sessions,
        "day_end": _iso(day_end),
        "total_minutes": 40.0,
        "test_plan": True,
    }


# --- games counting (D4) ----------------------------------------------------------


def _battle_local(bt: str) -> datetime | None:
    """games.csv battleTime is UTC ('20260610T101530.000Z') -> naive local."""
    try:
        dt = datetime.strptime(bt, "%Y%m%dT%H%M%S.%fZ").replace(tzinfo=timezone.utc)
        return dt.astimezone().replace(tzinfo=None)
    except ValueError:
        return None


def games_played_since(name: str, since: datetime, now: datetime) -> int:
    """Games this play-day: counter of record = games.csv (battleTime bucketed to
    local time, window [since=wake, now]) + the live worker's games_played that
    the lagging battlelog hasn't landed in the csv yet (status.json games minus
    csv rows logged during that worker session)."""
    d = _acct_dir(name)
    csv_count = 0
    csv_this_session = 0
    status = _read_json(d / "status.json")
    session_start: datetime | None = None
    if status:
        try:  # "session-20260610-091830.jsonl" -> that worker's start time
            session_start = datetime.strptime(
                str(status.get("session", "")), "session-%Y%m%d-%H%M%S.jsonl"
            )
        except ValueError:
            session_start = None
        try:
            age = (now - _parse(status["ts"])).total_seconds()
        except (KeyError, ValueError):
            age = 1e9
        if age > STATUS_FRESH_S:
            status = None  # stale heartbeat: csv already has everything it logged
    try:
        with (d / "games.csv").open("r", newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                local = _battle_local(row.get("battleTime") or "")
                if local is None or not (since <= local <= now):
                    continue
                csv_count += 1
                if session_start is not None:
                    try:
                        if _parse(row.get("logged_at") or "") >= session_start:
                            csv_this_session += 1
                    except ValueError:
                        pass
    except FileNotFoundError:
        pass
    pending = 0
    if status is not None:
        pending = max(0, int(status.get("games_played") or 0) - csv_this_session)
    return csv_count + pending


# --- evaluate (pure) ---------------------------------------------------------------


def evaluate(
    now: datetime,
    plan: dict | None,
    played: int,
    override: dict | None,
    enabled: bool,
) -> dict:
    """PURE: the desired-state decision for one account at `now`. Returns the
    `desired` block consumers gate on: state run|stop, why, until when, and the
    launch cap (max_minutes = remaining session).

    `played` is accepted for signature stability (the tick still tracks
    games_played_today for display) but is otherwise UNUSED since round 6 removed
    the games budget. ``max_games`` is left in the block (always None) so old
    consumers reading the key don't KeyError — the watchdog/manager just won't add a
    --max-games arg anymore."""

    def block(state, reason, until=None, max_minutes=None):
        return {
            "state": state,
            "reason": reason,
            "until": until,
            "max_minutes": max_minutes,
            "max_games": None,  # round 6: games budget removed (key kept, always None)
            "enabled": enabled,
            "updated_at": _iso(now),
        }

    if not enabled:
        # A STOP override is honored even with scheduling off (v3.1 #5): /stop
        # writes one so the watchdog doesn't relaunch ~1 min later (found live
        # 2026-06-10). Run overrides are meaningless here (disabled = always-run)
        # and malformed/expired ones were already pruned by the caller.
        if override and override.get("mode") == "stop":
            try:
                return block("stop", "override_stop", _iso(_parse(override["until"])))
            except (KeyError, ValueError):
                pass
        return block("run", "disabled")
    # A plan must have sessions + a day_end to be live. (Old files carrying `sleep`/
    # `is_rest`/`games_budget` are NOT live by this check — they lack `day_end` — so
    # they fail open to always-run until the next tick draws a new-model day.)
    if plan is None or not plan.get("day_end"):
        return block("run", "no_plan")  # fail-open: never strand a farm stopped

    day_end = plan["day_end"]

    if override:
        try:
            until = _parse(override["until"])
        except (KeyError, ValueError):
            until = now  # malformed -> treat as expired
        if now < until:
            if override.get("mode") == "run":
                mins = round((until - now).total_seconds() / 60.0, 1)
                return block(
                    "run",
                    "override_run",
                    override["until"],
                    max_minutes=max(1.0, mins),
                )
            return block("stop", "override_stop", override["until"])

    sessions = plan.get("sessions", [])
    for s in sessions:
        start = _parse(s["start"]) + timedelta(seconds=int(s.get("entry_delay_s") or 0))
        end = _parse(s["end"])
        if start <= now < end:
            mins = round((end - now).total_seconds() / 60.0, 1)
            return block(
                "run",
                "session",
                s["end"],
                max_minutes=max(1.0, mins),
            )
    # not inside a session: it's a break. next boundary = the next session start,
    # else the day_end (the next-midnight boundary, when a fresh plan is drawn).
    for s in sessions:
        start = _parse(s["start"]) + timedelta(seconds=int(s.get("entry_delay_s") or 0))
        if now < start:
            return block("stop", "gap", _iso(start))
    return block("stop", "gap", day_end)


# --- draw orchestration (shared by tick / preview / simulate) ----------------------


def _instance_items() -> list[tuple[str, dict]]:
    return list(config.INSTANCES.items())


def _draw_account_day(
    salt: str,
    name: str,
    tag: str,
    st: dict,
    date_str: str,
    nonce: int,
    wake: datetime,
) -> dict:
    """Draw one account's play-day, snapshotting the draw inputs into `st` so a lost
    schedule.json re-derives identically. Deterministic given inputs.

    Round 6: the day model's only cross-day input is the SEAM — yesterday's last
    session end, used to floor today's first session a real break past it (review
    #67 MAJOR-1). A FRESH day (the normal case, ``wake`` at/before midnight, or the
    midnight rollover) starts at ``max(00:00 + seed PHASE, prev_day_end + seam_break)``.
    A mid-day enable (`wake` well after midnight) starts no earlier than `wake`. A
    RE-DERIVE (same plan_date + nonce as the snapshot) replays from the snapshotted
    start AND the snapshotted prev_day_end, so the lost plan reproduces bit-for-bit.

    Snapshot fields this writes into `st`:
      - ``wake``: the realized first-session start (the re-derive floor).
      - ``last_session_end``: THIS plan's last-session end — becomes the NEXT day's
        ``prev_day_end`` (the seam source). The tick is its single writer.
      - ``seam_prev``: the prev_day_end value actually fed to THIS draw (yesterday's
        reality, snapshotted so a redraw/re-derive never recomputes it).

    Note `wake` here is the alternation START FLOOR, not a "wake from sleep" — the
    sleep concept is gone; the name is kept only to minimise churn in the callers."""
    re_derive = st.get("plan_date") == date_str and st.get("nonce_used") == nonce

    # The seam source. Fresh draw: yesterday's last-session end from the snapshot
    # (None on the first-ever day / fresh install / old-model state -> fail-soft, no
    # seam floor). Re-derive: the SAME prev value the original draw used (snapshotted
    # as ``seam_prev``), so a mid-day nonce bump or lost-plan replay keeps the seam.
    if re_derive:
        seam_prev = _parse(st["seam_prev"]) if st.get("seam_prev") else None
    else:
        seam_prev = _parse(st["last_session_end"]) if st.get("last_session_end") else None

    if os.environ.get("BRAWL_SCHED_TEST_PLAN") == "1":
        plan = _test_plan(wake)
    else:
        # re-derive replays from the snapshotted start; a fresh draw uses `wake` as
        # the earliest-start floor (midnight+phase / seam wins at the normal rollover).
        floor = _parse(st["wake"]) if re_derive else wake
        plan = draw_day_plan(salt, tag, date_str, nonce, wake=floor, prev_day_end=seam_prev)

    st.update(
        {
            "plan_date": date_str,
            "nonce_used": nonce,
            "wake": plan["sessions"][0]["start"] if plan["sessions"] else _iso(wake),
            "day_end": plan["day_end"],
            "total_h": plan["total_minutes"] / 60.0,
            # the seam carry-over (see docstring); test plans have no real midnight
            # seam, so leave last_session_end untouched for them.
            "seam_prev": _iso(seam_prev) if seam_prev is not None else None,
        }
    )
    if plan["sessions"] and not plan.get("test_plan"):
        st["last_session_end"] = plan["sessions"][-1]["end"]
    return plan


def _plan_current(plan: dict | None, st: dict, nonce: int, now: datetime) -> bool:
    """Is the existing schedule.json plan still the live play-day?"""
    if not plan or not plan.get("day_end"):
        return False
    if plan.get("nonce") != nonce:
        return False  # /schedule redraw bumped the nonce
    if bool(plan.get("test_plan")) != (os.environ.get("BRAWL_SCHED_TEST_PLAN") == "1"):
        return False
    try:
        return now < _parse(plan["day_end"])
    except (KeyError, ValueError):
        return False


def _state_current(st: dict, nonce: int, now: datetime) -> bool:
    """Can the state snapshot re-derive the live play-day (plan file lost)?"""
    if st.get("plan_date") is None or st.get("nonce_used") != nonce:
        return False
    try:
        return now < _parse(st["day_end"])
    except (KeyError, TypeError, ValueError):
        return False


# --- the tick (the only writer of state + schedule files) --------------------------


def tick(now: datetime | None = None) -> int:
    now = now or datetime.now()
    try:
        return _tick_inner(now)
    except Exception:
        # FAIL-OPEN: a scheduler bug must never strand farms stopped. Write
        # desired=run for everything, scream, exit nonzero (watchdog logs it).
        traceback.print_exc()
        for name, _ in _instance_items():
            try:
                sched = _read_json(_schedule_path(name)) or {"account": name}
                sched["desired"] = {
                    "state": "run",
                    "reason": "scheduler_error",
                    "until": None,
                    "max_minutes": None,
                    "max_games": None,
                    "enabled": False,
                    "updated_at": _iso(now),
                }
                _write_json(_schedule_path(name), sched)
            except Exception:
                pass
        return 1


def _ctl_enabled(c: dict) -> bool:
    """DEFAULT-ON semantics: an account entry without the ``enabled`` key — which
    includes a missing entry and a missing control file entirely ({}) — counts as
    ENABLED. Only an explicit enabled=false (written when the user turns the
    schedule off) means always-run."""
    return bool(c.get("enabled", True))


def _tick_inner(now: datetime) -> int:
    control = _read_json(_control_path())
    items = _instance_items()

    def ctl(name: str) -> dict:
        return ((control or {}).get("accounts") or {}).get(name) or {}

    any_enabled = any(_ctl_enabled(ctl(n)) for n, _ in items)

    # Every account explicitly /schedule off'd -> legacy always-run for all.
    # Fresh desired=run blocks keep the watchdog on its normal path; no state
    # file is created, nothing else is touched. (This used to be the no-control
    # default — "Phase 0" — but the scheduler is DEFAULT-ON now, so reaching
    # here requires an explicit opt-out of every account.)
    if not any_enabled:
        parts = []
        for name, _ in items:
            # Stop overrides (/stop) hold even here — same v3.1 #5 rule as the
            # per-account path in evaluate(); expired/malformed ones are pruned.
            override = _read_json(_override_path(name))
            if override:
                try:
                    if now >= _parse(override["until"]):
                        _override_path(name).unlink(missing_ok=True)
                        override = None
                except (KeyError, ValueError):
                    _override_path(name).unlink(missing_ok=True)
                    override = None
            sched = _read_json(_schedule_path(name)) or {"account": name}
            sched["desired"] = evaluate(now, None, 0, override, enabled=False)
            _write_json(_schedule_path(name), sched)
            parts.append(f"{name}={sched['desired']['state']}({sched['desired']['reason']})")
        print(f"tick {_iso(now)}  " + "  ".join(parts))
        return 0

    state = _read_json(_state_path()) or {}
    if not state.get("salt"):
        state["salt"] = os.urandom(16).hex()  # per-install; never re-rolled
    salt = state["salt"]
    accounts = state.setdefault("accounts", {})

    # pass 1: draw any due play-days. Each account's plan is independent (the
    # cross-account stagger is now a per-account seed phase, not a function of the
    # others' plans), so no ordering matters here.
    plans: dict[str, dict | None] = {}
    for name, _ in items:
        plans[name] = _read_json(_schedule_path(name))
    for name, inst in items:
        c = ctl(name)
        if not _ctl_enabled(c):
            continue
        st = accounts.setdefault(name, {})
        nonce = int(c.get("nonce") or 0)
        if _plan_current(plans[name], st, nonce, now):
            continue
        if _state_current(st, nonce, now):
            # plan file lost mid-day: re-derive THE SAME day from the state
            # snapshot (same seed inputs + snapshotted start -> bit-identical)
            date_str, wake = st["plan_date"], _parse(st["wake"])
        else:
            # a fresh day: anchored to TODAY's local date; the alternation starts
            # at 00:00 + the seed phase. (wake = now signals "fresh"; _draw_account_day
            # ignores it for a midnight-anchored day and only honours a wake AFTER
            # midnight, i.e. a mid-day enable.)
            date_str = now.strftime("%Y-%m-%d")
            wake = now
        plan = _draw_account_day(salt, name, inst["tag"], st, date_str, nonce, wake)
        plan["account"] = name
        plans[name] = plan
        print(
            f"drew {name} {date_str}: {len(plan['sessions'])} session(s), "
            f"{plan['total_minutes']:.0f} min, "
            f"day_end {_hhmm(plan['day_end'])}"
        )

    # pass 2: evaluate every account -> desired block in schedule.json
    parts = []
    for name, _ in items:
        c = ctl(name)
        enabled = _ctl_enabled(c)
        override = _read_json(_override_path(name))
        if override:
            try:
                if now >= _parse(override["until"]):
                    _override_path(name).unlink(missing_ok=True)  # expired
                    override = None
            except (KeyError, ValueError):
                _override_path(name).unlink(missing_ok=True)
                override = None
        plan = plans.get(name) if enabled else None
        played = 0
        if enabled and plan and plan.get("sessions") is not None:
            # The day's start lives in the STATE SNAPSHOT (st["wake"], the realized
            # first-session start) — NOT in the plan dict, which has no "wake" key.
            # (r10 review MAJOR: reading plan["wake"] raised KeyError into a broad
            # except, so games_played_today silently froze at 0 forever.) Fallback:
            # the plan's own first session start, which is what the snapshot wake is
            # set from anyway. The except is NARROW — only the expected file-I/O /
            # parse failures — so a logic bug can't hide in here again.
            st = accounts.get(name) or {}
            wake_iso = st.get("wake") or (
                plan["sessions"][0]["start"] if plan["sessions"] else None
            )
            if wake_iso:
                try:
                    played = games_played_since(name, _parse(wake_iso), now)
                except (OSError, ValueError, TypeError, csv.Error):
                    played = 0  # bad csv/status data must never block evaluation
        desired = evaluate(now, plan, played, override, enabled)
        sched = dict(plan) if (enabled and plan) else (_read_json(_schedule_path(name)) or {})
        sched["account"] = name
        sched["desired"] = desired
        if enabled:
            sched["games_played_today"] = played
        _write_json(_schedule_path(name), sched)
        extra = ""
        if desired["state"] == "run" and desired.get("max_minutes"):
            extra = f" {desired['max_minutes']:.0f}m left"
        until = f" until {_hhmm(desired.get('until'))}" if desired.get("until") else ""
        parts.append(f"{name}={desired['state']}({desired['reason']}{until}{extra})")

    _write_json(_state_path(), state)
    print(f"tick {_iso(now)}  " + "  ".join(parts))
    return 0


# --- preview / simulate (read-only dev tools) ---------------------------------------


def simulate_draws(
    days: int, *, start: datetime | None = None, salt: str = "simulate"
) -> dict[str, list[dict]]:
    """Event-driven in-memory simulation of the real draw loop for all accounts
    (no disk writes). Used by `preview`, `simulate`, and the test suite."""
    # Anchor the sim to LOCAL MIDNIGHT so each account's plan covers a clean
    # 00:00->24:00 day (the real tick draws against the local date). A caller's
    # `start` time-of-day is dropped — only its date matters for the day model.
    start = (start or datetime.now()).replace(hour=0, minute=0, second=0, microsecond=0)
    items = _instance_items()
    accounts: dict[str, dict] = {n: {} for n, _ in items}
    out: dict[str, list[dict]] = {n: [] for n, _ in items}
    next_draw: dict[str, datetime] = {n: start for n, _ in items}
    horizon = start + timedelta(days=days)
    while True:
        name = min(next_draw, key=lambda n: next_draw[n])
        now = next_draw[name]
        if now >= horizon:
            break
        st = accounts[name]
        tag = config.INSTANCES[name]["tag"]
        # `wake` = the day's midnight; draw_day_plan applies the seed phase as the
        # real start. (A fresh midnight draw, so the phase always wins the floor.)
        plan = _draw_account_day(salt, name, tag, st, now.strftime("%Y-%m-%d"), 0, now)
        plan["account"] = name
        out[name].append(plan)
        # roll to the next local midnight (== this plan's day_end) and draw again
        next_draw[name] = _parse(plan["day_end"])
    return out


def preview(days: int, now: datetime | None = None) -> None:
    now = now or datetime.now()
    # use the real per-install salt when scheduling is already active, so the
    # preview shows the actual upcoming shape (simulate once — the default-salt
    # result was previously computed and then thrown away)
    state = _read_json(_state_path())
    salt = state["salt"] if state and state.get("salt") else "simulate"
    sims = simulate_draws(days, start=now, salt=salt)
    control = _read_json(_control_path()) or {}
    for name, plans in sims.items():
        enabled = _ctl_enabled((control.get("accounts") or {}).get(name) or {})
        print(f"\n=== {name} — {days}-day preview (scheduling {'ON' if enabled else 'OFF'}) ===")
        for p in plans:
            day = datetime.strptime(p["plan_date"], "%Y-%m-%d")
            head = f"{day.strftime('%a %Y-%m-%d')}"
            print(
                f"{head}  ·  {len(p['sessions'])} session(s), "
                f"{p['total_minutes'] / 60:.1f} h play  ·  phase +{p['phase_min']:.0f} min"
            )
            for i, s in enumerate(p["sessions"], 1):
                mins = (_parse(s["end"]) - _parse(s["start"])).total_seconds() / 60
                brk = ""
                if i < len(p["sessions"]):
                    gap = (
                        _parse(p["sessions"][i]["start"]) - _parse(s["end"])
                    ).total_seconds() / 60
                    kind = "🧳 LONG OUTING" if s.get("outing_after") else "break"
                    brk = f"   then {gap:.0f} min {kind}"
                print(
                    f"    session {i}:  {_hhmm(s['start'])}–{_hhmm(s['end'])}"
                    f"  ({mins:.0f} min, +{s['entry_delay_s'] // 60} min entry delay){brk}"
                )


def simulate(days: int) -> None:
    sims = simulate_draws(days)
    for name, plans in sims.items():
        sess = [
            (_parse(s["end"]) - _parse(s["start"])).total_seconds() / 60
            for p in plans
            for s in p["sessions"]
        ]
        # Separate regular breaks from r8 long outings so neither skews the other's
        # stats (an outing is the gap AFTER a session flagged ``outing_after``).
        breaks, outing_gaps = [], []
        for p in plans:
            ss = p["sessions"]
            for i, s in enumerate(ss[:-1]):
                gap = (_parse(ss[i + 1]["start"]) - _parse(s["end"])).total_seconds() / 60
                (outing_gaps if s.get("outing_after") else breaks).append(gap)
        totals = [p["total_minutes"] / 60 for p in plans]
        outs = [p.get("outings", 0) for p in plans]
        sess_sorted = sorted(sess)
        print(f"\n=== {name}: {len(plans)} play-days simulated ===")
        print(
            f"  sessions/day: {sum(len(p['sessions']) for p in plans) / max(1, len(plans)):.2f}"
            f"  ·  session min/mean/p90/max: {min(sess):.0f}/{sum(sess) / len(sess):.0f}"
            f"/{sess_sorted[int(0.9 * len(sess))]:.0f}/{max(sess):.0f} min"
        )
        if breaks:
            print(
                f"  break min/mean/max: {min(breaks):.0f}/{sum(breaks) / len(breaks):.0f}"
                f"/{max(breaks):.0f} min"
            )
        print(
            f"  outings/day mean: {sum(outs) / max(1, len(outs)):.2f}"
            + (
                f"  ·  outing min/mean/max: {min(outing_gaps):.0f}/"
                f"{sum(outing_gaps) / len(outing_gaps):.0f}/{max(outing_gaps):.0f} min"
                if outing_gaps
                else ""
            )
        )
        print(
            f"  daily play-h min/mean/max: {min(totals):.1f}/{sum(totals) / len(totals):.1f}"
            f"/{max(totals):.1f}"
        )


# --- Panel-side helpers (writers of the CONTROL file only) --------------------------


def read_control() -> dict:
    return _read_json(_control_path()) or {"accounts": {}}


def set_enabled(names: list[str], enabled: bool) -> None:
    """Flip per-account enabled flags (the schedule on/off master switch).
    Writer = the control panel process; the tick only reads this file."""
    c = read_control()
    accts = c.setdefault("accounts", {})
    for n in names:
        accts.setdefault(n, {"nonce": 0})["enabled"] = enabled
    c["updated_at"] = _iso(datetime.now())
    _write_json(_control_path(), c)


def bump_nonce(name: str) -> int:
    """/schedule redraw: a bumped nonce reseeds every draw for the account, so
    the next tick discards the current plan and draws a fresh day. A fresh entry
    deliberately omits the ``enabled`` key — default-ON must survive a redraw
    (an implicit enabled=false here would silently disable the account)."""
    c = read_control()
    a = c.setdefault("accounts", {}).setdefault(name, {"nonce": 0})
    a["nonce"] = int(a.get("nonce") or 0) + 1
    c["updated_at"] = _iso(datetime.now())
    _write_json(_control_path(), c)
    return a["nonce"]


def write_override(name: str, mode: str, until: datetime) -> None:
    """Manual override (/start during a scheduled stop, /stop during a session)."""
    _write_json(
        _override_path(name),
        {"mode": mode, "until": _iso(until), "set_at": _iso(datetime.now())},
    )


def clear_override(name: str) -> None:
    try:
        _override_path(name).unlink(missing_ok=True)
    except OSError:
        pass


def read_schedule(name: str) -> dict | None:
    return _read_json(_schedule_path(name))


def desired_from(sched: dict | None, now: datetime | None = None) -> dict | None:
    """The current desired block from an ALREADY-READ schedule dict, or None if
    missing/stale (>10 min — treat as 'scheduler not running', i.e. legacy
    always-run). Pure: takes the parsed schedule.json so a caller that already
    read the file once (e.g. manager.read_card_inputs) need not re-read it."""
    d = (sched or {}).get("desired")
    if not d:
        return None
    try:
        age = ((now or datetime.now()) - _parse(d["updated_at"])).total_seconds()
    except (KeyError, ValueError):
        return None
    return d if 0 <= age <= DESIRED_FRESH_S or age < 0 else None


def enabled_from(sched: dict | None) -> bool:
    """Is the scheduler ON, from an ALREADY-READ schedule dict? (v3 §A4 contract,
    the read-once twin of manager.schedule_enabled.) A top-level ``enabled`` key
    wins, else ``desired.enabled``; missing → True (DEFAULT-ON)."""
    sched = sched or {}
    if "enabled" in sched:
        return bool(sched["enabled"])
    d = sched.get("desired") or {}
    if "enabled" in d:
        return bool(d["enabled"])
    return True


def sched_desired(name: str, now: datetime | None = None) -> dict | None:
    """The account's current desired block, or None if missing/stale (>10 min —
    treat as 'scheduler not running', i.e. legacy always-run)."""
    return desired_from(read_schedule(name), now)


# --- CLI ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # console may be cp1252 (like run.py)
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Anti-ban scheduler (see module docstring)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("tick", help="draw-if-needed + evaluate all accounts (the watchdog's call)")
    t.add_argument("--now", default=None, help="inject a fake clock (ISO, for tests)")
    p = sub.add_parser("preview", help="print the upcoming timeline (no writes)")
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--now", default=None)
    s = sub.add_parser("simulate", help="long-run distribution stats (no writes)")
    s.add_argument("--days", type=int, default=365)
    args = ap.parse_args(argv)
    if args.cmd == "tick":
        return tick(_parse(args.now) if args.now else None)
    if args.cmd == "preview":
        preview(args.days, _parse(args.now) if args.now else None)
        return 0
    simulate(args.days)
    return 0


if __name__ == "__main__":
    sys.exit(main())
