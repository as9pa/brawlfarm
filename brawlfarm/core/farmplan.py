"""Per-instance FARM PLAN: which brawler to grind, to what trophy goal, and what's next.

Persisted as ``<DATA_DIR>/farmplan.json`` so the control panel (writer) and the farm
controller (reader) share it through the same file bridge as status.json. Shape:

    {
      "mode": "prestige" | "ladder",
      "prestige_start": "highest" | "lowest",   # which end of the <1000 pool to start
      "goal_trophies": 1000,                     # the ladder ceiling / prestige floor
      "maxed_fallback": null                     # prestige-only, opt-in (see below)
    }

"maxed_fallback" (prestige-only, opt-in; default null = today's behavior): a brawler
NAME to switch to and keep farming once prestige is EXHAUSTED — i.e. every owned
brawler is >= the goal so the normal prestige pool is empty. With it unset the
controller HOLDS the last brawler (the legacy all-maxed latch). With it set to an
OWNED brawler's name, :func:`choose_target` returns that brawler (instead of None)
when the pool is empty, so the farm keeps playing it indefinitely to gather
later-stage statistics. This DELIBERATELY grinds one brawler past 1000 — an explicit,
owner-sanctioned exception to the "never grind a brawler over 1000" rule, GATED
STRICTLY to the all-maxed state (nothing else is left to farm). Matched by uppercase;
a non-string / empty / not-owned value is treated as unset (falls back to the hold).

"prestige" completes whole brawlers to 1000 (prestige) one at a time, starting
from the highest- or lowest-trophy one still under 1000.
"ladder" (the default) raises the WHOLE roster evenly, one 100-trophy tier at a time
(everyone to 700, then 800, ...) up to goal_trophies — it farms the lowest brawler
toward the next tier above the current minimum, so no brawler races ahead into
high-trophy diminishing returns while the rest lag behind.

v5 (round 5 owner feedback, docs/owner-feedback/dc slop 5.md): the "manual" mode (what /farm set —
target + queue) and "least" (always-the-lowest, no plan smarts) are REMOVED —
ladder subsumes least, and /mode overrides made /farm pointless. Stored plans
with either mode alias to ladder at load time (:func:`load_plan`), so no data
migration is needed in either direction.

r6 (round 6 owner feedback, docs/more instructions.md): "optimal" is FOLDED INTO
ladder — there was one obvious pick between the two, so the rate-based rotation
that used to be optimal-only is now just how ladder behaves. Ladder's lowest-first
selection PLUS rate-based rotation: the controller asks :func:`rotation_decision`
(the win-rate model v2 — empirical-Bayes-shrunk recency rate over games.csv) and,
when it says rotate AND the brawler is not on a winstreak (:func:`recent_winstreak`
— the owner's "never mid-winstreak" guard), treats the brawler as exhausted for
the session and re-asks for a target with it excluded (the ``exclude`` argument
below). Rotation state lives in CONTROLLER MEMORY
(session-scoped, reset on worker restart) — deliberately not in this file, so a
transient cold streak never sticks to the plan across sessions. Stored "optimal"
plans alias to ladder at load (same v5 pattern — no data migration).

2026-06-14 (owner): the rotation's "opportunity_cost" trigger is now OFF by default
(config.WINRATE_OPPORTUNITY_COST) — on a near-maxed roster it thrashed the brawler
menu (it fired on every freshly-selected brawler). The "absolute_floor" net-losing
trigger stays on. The live accounts run prestige/lowest, which never rotates.

Ladder selection additionally carries the WIN-RATE BIAS (Q2,
docs/future-plans/winrate-aware-farming.md): candidates inside the current step
band are ordered by their trailing net trophy rate from games.csv
(:func:`rates_by_brawler`), and a clearly-hotter one (>= config.WINRATE_MARGIN
over the roster minimum's score) is promoted — picked BY NAME — instead of the
literal minimum. Margin + min-sample + neutral-prior rails mean every uncertain
case (fresh csv, under-sampled brawlers, near-ties) falls through to today's
behavior; BRAWL_WINRATE_AWARE=0 pins it off entirely.

The controller consults :func:`choose_target` at startup and at the existing
mid-session reselect points — the selection itself still happens in core/brawlers.py.
"""

from __future__ import annotations

import csv
import json
from collections import deque
from pathlib import Path

from brawlfarm.core import config
from brawlfarm.core.jsonio import atomic_write_json

PRESTIGE_GOAL = 1000  # the per-brawler trophy milestone ("prestige")
LADDER_STEP = 100  # ladder mode raises the whole roster one 100-trophy tier at a time
VALID_MODES = ("prestige", "ladder")

# Winstreak guard (r6): never rotate a brawler that has won its last
# WINSTREAK_GUARD_GAMES showdown games — "if it's hot, leave it alone." 3 is a
# short, conservative streak: long enough to mean "genuinely on a roll", short
# enough that a brawler that's actually gone cold clears it within a window.
WINSTREAK_GUARD_GAMES = 3

# v5/r6: /farm, "least" and "optimal" are removed from the surface, but plans they
# stored are still on disk — alias them to ladder at load so they degrade
# gracefully (manual's lowest-first cousin; least was literally ladder minus tiered
# goals; optimal is now just ladder with its rate-based rotation built in).
_MODE_ALIASES = {"manual": "ladder", "least": "ladder", "optimal": "ladder"}

DEFAULT_PLAN = {
    "mode": "ladder",
    "prestige_start": "highest",
    "goal_trophies": PRESTIGE_GOAL,
    "maxed_fallback": None,  # prestige-only, opt-in: keep farming this brawler when maxed
}


def _path(data_dir: str | Path | None = None) -> Path:
    return Path(data_dir or config.DATA_DIR) / "farmplan.json"


def load_plan(data_dir: str | Path | None = None) -> dict:
    """The instance's farm plan, merged over the defaults (missing file = defaults,
    i.e. ladder). Stored "manual"/"least"/"optimal" plans alias to ladder (v5/r6 —
    /farm, least and optimal removed; stored plans degrade gracefully); unknown
    modes fall back to ladder too."""
    plan = dict(DEFAULT_PLAN)
    try:
        plan.update(json.loads(_path(data_dir).read_text(encoding="utf-8")))
    except Exception:
        pass
    plan["mode"] = _MODE_ALIASES.get(plan.get("mode"), plan.get("mode"))
    if plan.get("mode") not in VALID_MODES:
        plan["mode"] = "ladder"
    return plan


def save_plan(plan: dict, data_dir: str | Path | None = None) -> dict:
    """Atomically persist ``plan`` (merged over defaults). Returns the merged plan."""
    merged = {**DEFAULT_PLAN, **plan}
    atomic_write_json(_path(data_dir), merged)
    return merged


# --- target selection ----------------------------------------------------------


def _prestige_pool(brawlers: list[dict]) -> list[dict]:
    return [b for b in brawlers if (b.get("trophies") or 0) < PRESTIGE_GOAL]


def _prestige_pick(brawlers: list[dict], start: str) -> dict | None:
    pool = _prestige_pool(brawlers)
    if not pool:
        return None
    key = lambda b: b.get("trophies") or 0  # noqa: E731
    return max(pool, key=key) if start == "highest" else min(pool, key=key)


def _step_goal(brawlers: list[dict], cap: int) -> int:
    """The ladder step goal for a pool: the next 100-line above the pool's
    minimum, never above the cap."""
    min_tr = min((b.get("trophies") or 0) for b in brawlers)
    floor = (min_tr // LADDER_STEP) * LADDER_STEP + LADDER_STEP
    return min(floor, cap)


# --- win-rate model v2 (r8, docs/research/winrate-model.md) ----------------------
# Two statistical upgrades to the original Q2 trailing-mean bias, surface-compatible
# (same choose_target signature, same kill-switch, same callers):
#   (a) EMPIRICAL-BAYES SHRINKAGE — a brawler's score is pulled toward the account's
#       own overall mean (mu0), strength = config.WINRATE_PRIOR_K games, so a 3-game
#       hot/cold streak no longer reads as a real signal. Replaces the hard
#       min-sample/neutral-prior cliff (a 9-game stellar run scored the prior, a
#       10-game one scored its raw mean — a discontinuity).
#   (b) RECENCY-WEIGHTED MEAN — an exponentially-weighted mean (half-life
#       config.WINRATE_HALFLIFE games) instead of a hard window, so form changes
#       register smoothly with no cliff at the window edge.
# The model is the SAME math in both consumers: the proactive selection bias
# (_winrate_pick) and the reactive rotation trigger (rotation_decision). See the
# worked examples + replay in docs/research/winrate-model.md.


def _shrink(ewma: float, n: float, mu0: float, k: float) -> float:
    """Empirical-Bayes posterior mean: blend a brawler's own recency-weighted
    rate (``ewma`` over an effective ``n`` games) toward the account mean ``mu0``
    with prior strength ``k`` games:  (n*ewma + k*mu0) / (n + k).

    n == 0 -> pure prior (mu0); n >> k -> essentially the brawler's own ewma. The
    knee sits at n == k, where the estimate is the midpoint. Pure arithmetic — the
    unit tests pin it directly."""
    if n + k <= 0:  # degenerate guard (k>0 by config, n>=0) — never the prior 0/0
        return mu0
    return (n * ewma + k * mu0) / (n + k)


def _ewma(changes: list[int], halflife: float) -> tuple[float, float]:
    """Recency-weighted mean of ``changes`` (oldest-first) and its effective
    sample size, with an exponential weight decaying by half every ``halflife``
    games of age. The most recent game has age 0 (weight 1); the one before it
    age 1; etc.  Returns (weighted_mean, sum_of_weights). The weight sum is the
    "effective n" the shrinkage uses — it saturates near ``halflife / ln 2`` as
    history grows, so a long cold history can't overwhelm the prior the way a raw
    count would. Empty list -> (0.0, 0.0)."""
    if not changes:
        return 0.0, 0.0
    decay = 0.5 ** (1.0 / halflife)  # per-game multiplicative decay
    wsum = 0.0
    acc = 0.0
    w = 1.0  # weight of the MOST RECENT game; older games get w*decay, w*decay^2...
    for c in reversed(changes):  # newest first
        acc += w * c
        wsum += w
        w *= decay
    return (acc / wsum if wsum else 0.0), wsum


def _iter_showdown_changes(data_dir: str | Path | None) -> list[tuple[str, int]]:
    """The shared games.csv scan (core/datalog.py's schema): ``[(UPPER brawler,
    trophyChange), ...]`` for every SHOWDOWN row with a parseable trophyChange, in
    file order. Rows without a brawler/showdown flag, and trophyChange gaps (API
    lag), are skipped. A missing OR garbled csv degrades to ``[]`` — the whole read
    succeeds or yields nothing, so each caller's missing-file behavior is unchanged.

    Materialized (not a generator) on purpose: every caller reads the WHOLE file
    anyway, the csv is only a few hundred KB, and a materialized list keeps the
    "garbled → empty, never partial" guarantee the old per-function try/excepts had.
    Reading the whole csv each call is fine — the controller only asks on the ~60 s
    trophy-snapshot cadence."""
    out: list[tuple[str, int]] = []
    try:
        with (Path(data_dir or config.DATA_DIR) / "games.csv").open(
            "r", newline="", encoding="utf-8"
        ) as f:
            for row in csv.DictReader(f):
                name = (row.get("brawler") or "").upper()
                if not name:
                    continue
                if str(row.get("is_showdown")).lower() not in ("true", "1"):
                    continue
                try:
                    out.append((name, int(row.get("trophyChange") or "")))
                except ValueError:
                    continue
    except (OSError, UnicodeError, csv.Error):  # missing or garbled csv
        return []
    return out


def _winrate_stats_v2(
    data_dir: str | Path | None,
) -> tuple[dict[str, tuple[float, float]], float | None]:
    """ONE pass over games.csv (via :func:`_iter_showdown_changes`) -> a pair of:

      * per-brawler v2 stats: UPPER name -> (recency-weighted EWMA rate over its
        whole logged history, effective sample size = sum of EWMA weights). The
        caller shrinks these toward the account mean.
      * mu0, the account-wide MEAN trophyChange/game over ALL logged showdown
        games — the empirical-Bayes prior the shrinkage pulls toward, or None
        when the csv is missing/garbled/empty (no data at all).

    History is bounded to the last config.WINRATE_HISTORY_MAX games per brawler
    (the EWMA tail past ~5 half-lives is numerically negligible anyway)."""
    cap = config.WINRATE_HISTORY_MAX
    hl = config.WINRATE_HALFLIFE
    per: dict[str, deque] = {}
    overall_sum = 0
    overall_n = 0
    for name, change in _iter_showdown_changes(data_dir):
        per.setdefault(name, deque(maxlen=cap)).append(change)
        overall_sum += change
        overall_n += 1
    stats = {n: _ewma(list(w), hl) for n, w in per.items()}
    return stats, (overall_sum / overall_n if overall_n else None)


def shrunk_rates(
    data_dir: str | Path | None = None,
) -> tuple[dict[str, float], float | None]:
    """Public v2 view: UPPER brawler name -> empirical-Bayes-shrunk recency rate,
    plus the account mean mu0 (None if the csv is missing/garbled/empty). A
    brawler with NO logged games is absent from the dict (the caller scores it as
    mu0). Used by the replay tool and the selection/rotation logic."""
    stats, mu0 = _winrate_stats_v2(data_dir)
    if mu0 is None:
        return {}, None
    k = config.WINRATE_PRIOR_K
    return {n: _shrink(ewma, neff, mu0, k) for n, (ewma, neff) in stats.items()}, mu0


# Back-compat: the original trailing-mean view (last config.WINRATE_WINDOW games)
# is still exposed for any external caller / the v1-vs-v2 replay comparison.


def _winrate_stats(
    data_dir: str | Path | None, window: int
) -> tuple[dict[str, tuple[float, int]], float | None]:
    """v1 stat (kept for the replay comparison + back-compat): per-brawler trailing
    MEAN over the last ``window`` showdown games, plus the account-wide trailing
    mean over the last ``window`` games (the v1 neutral prior). Missing/garbled
    csv -> ({}, None). Shares the :func:`_iter_showdown_changes` scan."""
    per: dict[str, deque] = {}
    overall: deque = deque(maxlen=window)
    for name, change in _iter_showdown_changes(data_dir):
        per.setdefault(name, deque(maxlen=window)).append(change)
        overall.append(change)
    rates = {n: (sum(w) / len(w), len(w)) for n, w in per.items()}
    return rates, (sum(overall) / len(overall) if overall else None)


def rates_by_brawler(
    data_dir: str | Path | None = None, window: int | None = None
) -> dict[str, tuple[float, int]]:
    """v1 trailing per-brawler showdown rates from games.csv: UPPER name ->
    (mean trophyChange/game over the last ``window`` games, games counted).
    Kept for back-compat + the v1-vs-v2 replay. Window defaults to
    config.WINRATE_WINDOW. Missing/garbled csv -> {}."""
    per, _ = _winrate_stats(data_dir, window or config.WINRATE_WINDOW)
    return per


def _winrate_pick(
    pool: list[dict], step_goal: int, data_dir: str | Path | None
) -> str | None:
    """The proactive selection bias (model v2). Among ``pool`` (ladder: the roster
    minus the session's rotated-out brawlers — exclusion filters BEFORE scoring, so
    a proven-cold brawler can never be re-picked by a stale good score), consider
    only brawlers BELOW the current step goal, score each by its EMPIRICAL-BAYES-
    SHRUNK RECENCY RATE (shrunk_rates: EWMA pulled toward the account mean mu0 by
    config.WINRATE_PRIOR_K games), order by score desc (tie-break lowest trophies,
    preserving the ladder spirit), and promote the top one only when its shrunk
    score beats the roster-minimum brawler's shrunk score by >= config.WINRATE_MARGIN.

    Why shrinkage instead of v1's min-sample/neutral-prior cliff: a brawler with a
    handful of games is pulled toward the account mean smoothly — a 3-game hot
    streak can't promote, a well-sampled +5/game one still can — with no
    discontinuity at the 10-game line (worked examples in
    docs/research/winrate-model.md).

    Returns the promoted name, or None meaning "use today's default pick". EVERY
    uncertain or degenerate case — kill-switch off, missing/garbled/empty csv,
    fewer than two candidates, margin not met, the default pick already on top —
    returns None, so the legacy flow stays bit-identical. The bias can only ever
    re-order legal picks, never change a goal, never pick at or above the step."""
    if not config.WINRATE_AWARE:
        return None
    tr = lambda b: b.get("trophies") or 0  # noqa: E731
    candidates = [b for b in pool if tr(b) < step_goal]
    if len(candidates) < 2:
        return None  # nothing to reorder
    try:
        rates, mu0 = shrunk_rates(data_dir)
    except Exception:
        return None  # any stat trouble degrades to today's behavior
    if mu0 is None:
        return None  # cold start: no usable rows at all -> all-shrink-to-prior

    def score(b: dict) -> float:
        return rates.get((b.get("name") or "").upper(), mu0)  # unseen -> the prior

    baseline = min(candidates, key=tr)  # today's pick: the roster minimum
    top = max(candidates, key=lambda b: (score(b), -tr(b)))
    if top is baseline or score(top) < score(baseline) + config.WINRATE_MARGIN:
        return None
    return top.get("name")


def rotation_decision(
    current: str,
    pool: list[dict],
    data_dir: str | Path | None = None,
) -> tuple[bool, str | None]:
    """Reactive rotation trigger (model v2 — OPPORTUNITY COST). Should the farmed
    brawler ``current`` be rotated out this session? ``pool`` is the live roster
    (the controller's get_player() brawler list). Returns (rotate?, reason):

      * reason "opportunity_cost" — there is a clearly-better in-band alternative:
        (best alternative's shrunk rate - current's shrunk rate) > config.WINRATE_MARGIN
        AND current's shrunk rate < the account mean mu0. The alternative pool is
        the OTHER brawlers in current's 100-trophy band (so the ladder floor
        invariant is respected — same band the selection bias reorders within),
        excluding ``current``. OFF by default (config.WINRATE_OPPORTUNITY_COST,
        owner decision 2026-06-14): on a near-maxed roster it thrashed the menu
        by rotating every freshly-selected brawler. Re-enable with
        BRAWL_WINRATE_OPPORTUNITY_COST=1.
      * reason "absolute_floor" — the secondary, v1-style trigger kept verbatim in
        spirit: current's shrunk rate < config.OPTIMAL_RATE_MIN (net-losing).
      * (False, None) — keep farming.

    The WINSTREAK GUARD is applied by the CALLER (controller), verbatim, exactly
    as before — this function only does the statistics. Cold start / missing csv /
    a brawler with no shrunk rate (never seen) -> (False, None): no evidence to
    rotate on. Pure read of games.csv + the live roster; no I/O beyond the csv."""
    if not config.WINRATE_AWARE:
        return False, None
    try:
        rates, mu0 = shrunk_rates(data_dir)
    except Exception:
        return False, None
    if mu0 is None:
        return False, None
    cur = (current or "").upper()
    cur_rate = rates.get(cur)
    if cur_rate is None:
        return False, None  # never seen current -> no evidence
    # Absolute floor: net-losing on the SHRUNK rate. ALWAYS active — a genuinely
    # net-losing brawler is a real stagnation signal worth switching off.
    if cur_rate < config.OPTIMAL_RATE_MIN:
        return True, "absolute_floor"
    # Opportunity cost: a clearly-better alternative in the SAME band, and we're
    # below our own account average on current. OFF by default (owner decision
    # 2026-06-14, config.WINRATE_OPPORTUNITY_COST): on a near-maxed roster the
    # lowest brawlers have near-identical rates, so this fired on essentially
    # every selection (even pre-first-game) and thrashed the brawler menu. The
    # net-losing floor above still catches real stagnation.
    if not config.WINRATE_OPPORTUNITY_COST:
        return False, None
    tr = lambda b: b.get("trophies") or 0  # noqa: E731
    cur_b = next((b for b in pool if (b.get("name") or "").upper() == cur), None)
    if cur_b is None:
        return False, None  # current not in the live roster -> can't band it
    band_floor = (tr(cur_b) // LADDER_STEP) * LADDER_STEP
    band_ceil = band_floor + LADDER_STEP
    alts = [
        b
        for b in pool
        if (b.get("name") or "").upper() != cur
        and band_floor <= tr(b) < band_ceil
        and (b.get("name") or "").upper() in rates
    ]
    if not alts:
        return False, None
    best = max(alts, key=lambda b: rates[(b.get("name") or "").upper()])
    best_rate = rates[(best.get("name") or "").upper()]
    if best_rate - cur_rate > config.WINRATE_MARGIN and cur_rate < mu0:
        return True, "opportunity_cost"
    return False, None


def choose_target(
    plan: dict,
    brawlers: list[dict],
    exclude: set[str] | tuple = (),
    data_dir: str | Path | None = None,
) -> tuple[str | None, int]:
    """Decide (brawler_name, goal_trophies) from the plan + the account's live brawler
    list (the API's ``player["brawlers"]``). Returns (None, goal) when the existing
    lowest-trophy flow should be used instead (nothing applicable).

    ``exclude`` (ladder mode only) is the controller's session set of rotated-out
    brawler names: they are skipped when picking the next candidate. Prestige
    deliberately ignores it (rotation is a ladder concept — r6 folded optimal's
    rotation into ladder).

    ``data_dir`` is where the win-rate bias (:func:`_winrate_pick`, ladder only)
    reads games.csv from; None = config.DATA_DIR (correct in the worker process,
    whose DATA_DIR is the instance's own dir).
    """
    mode = plan.get("mode", "ladder")
    goal = int(plan.get("goal_trophies") or PRESTIGE_GOAL)

    if not brawlers:
        return None, goal

    if mode == "ladder":
        # Raise the WHOLE roster a tier at a time. Baseline: farm the lowest-trophy
        # brawler (target=None -> the in-game "Least Trophies" selection) toward the
        # next 100-line above the current minimum. Invariant: the floor only reaches
        # 800 once the minimum is >= 700 -- i.e. EVERY brawler is >= 700 before any is
        # pushed toward 800 ("everyone to 700, then 800, and so on"). goal_trophies is
        # the ceiling the ladder stops raising at (default 1000 = full prestige).
        #
        # r6: rotation (formerly optimal-only) is folded in here. ``exclude`` is the
        # controller's session set of rotated-out brawlers; they're filtered BEFORE
        # scoring. No rotations -> identical to the pre-r6 ladder (target=None keeps
        # the proven in-game "Least Trophies" selection). With rotations the next
        # candidate is picked BY NAME (the in-game lowest sort would just re-select
        # the rotated one), and the step goal is computed over the remaining pool so
        # the new target isn't instantly "above the step" (which would reselect-loop).
        # Win-rate bias (Q2): scores only the exclude-FILTERED pool (rotation always
        # wins) and may promote a statistically-hotter candidate within the step band
        # over the literal minimum (picked BY NAME); the step goal — and so the floor
        # invariant — is untouched. No promotion -> exactly the pre-Q2 pick.
        # (_step_goal(pool) == _step_goal(brawlers) when nothing is rotated out, so
        # the unrotated path's goal is unchanged too.)
        excluded = {str(x).upper() for x in exclude}
        pool = [b for b in brawlers if (b.get("name") or "").upper() not in excluded]
        if not pool:  # everything rotated out this session -> plain ladder
            return None, _step_goal(brawlers, goal)
        step = _step_goal(pool, goal)
        pick = _winrate_pick(pool, step, data_dir)
        if pick is not None:
            return pick, step
        if len(pool) == len(brawlers):
            return None, step
        low = min(pool, key=lambda b: b.get("trophies") or 0)
        return low.get("name"), step

    if mode == "prestige":
        # highest-or-lowest brawler still under 1000, farmed TO 1000
        pick = _prestige_pick(brawlers, plan.get("prestige_start", "highest"))
        if pick is not None:
            return pick.get("name"), max(goal, PRESTIGE_GOAL)
        # Pool empty: every owned brawler is >= the goal. Opt-in maxed_fallback —
        # if the plan names a brawler the account OWNS, keep farming it (deliberate
        # >goal grind, gated STRICTLY to this all-maxed state). Otherwise return
        # None exactly as before so the controller HOLDS the current brawler.
        fallback = plan.get("maxed_fallback")
        if isinstance(fallback, str) and fallback.strip():
            want = fallback.strip().upper()
            match = next(
                (b for b in brawlers if (b.get("name") or "").upper() == want), None
            )
            if match is not None:
                return match.get("name"), max(goal, PRESTIGE_GOAL)
        return None, max(goal, PRESTIGE_GOAL)

    # Unknown mode reaching here means the caller bypassed load_plan (which
    # aliases/validates) — degrade to the plain lowest-trophy in-game flow.
    return None, goal


def resolve_target(
    api, exclude: set[str] | tuple = ()
) -> tuple[str | None, int, list[str]]:
    """Controller-facing one-call resolution: load this instance's plan and return
    (target_name, goal_trophies, owned_names). target_name is None when the
    lowest-trophy in-game selection should run (ladder mode, or nothing
    applicable). ``exclude`` = the controller's session rotation set (ladder
    mode — r6 folded optimal's rotation into ladder). API errors propagate; the
    controller falls back to the plain lowest-trophy flow."""
    plan = load_plan()
    blist = api.get_player().get("brawlers") or []
    target, goal = choose_target(plan, blist, exclude=exclude)
    return target, goal, [b.get("name") for b in blist if b.get("name")]


def recent_winstreak(
    name: str, k: int = WINSTREAK_GUARD_GAMES, data_dir: str | Path | None = None
) -> bool:
    """True when the LAST ``k`` showdown games on ``name`` (games.csv, via the
    shared :func:`_iter_showdown_changes` scan) ALL had a positive trophyChange —
    the r6 "never rotate a brawler mid-winstreak" guard. Fewer than ``k`` logged
    games (or a missing/garbled csv) -> False: too little evidence to call it a
    streak, so the guard does NOT block rotation (the subnormal-rate trigger still
    gates that)."""
    want = (name or "").upper()
    changes = [c for n, c in _iter_showdown_changes(data_dir) if n == want]
    if len(changes) < k:
        return False  # not enough evidence to call it a streak
    return all(c > 0 for c in changes[-k:])


# v5: advance_after_goal (the manual-mode queue popper) is GONE with the mode —
# ladder/prestige both self-advance from the live roster.
