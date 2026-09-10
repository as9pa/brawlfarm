"""Season-rollover tripwire streak state (ops-resilience.md §B).

A surface computes a per-run "suspicion" flag — an independent coarse check
disagreed with the calibrated detector (e.g. the brawler grid screen verified but
0 owned names read). One flagged run can be OCR noise, so the controller folds each
observation through ``record()`` here, which keeps a per-surface STREAK in
``data/<acct>/recalib.json`` and says when the streak has crossed its threshold (→
emit the ``recalibrate`` event). (The brawler grid is the only live surface now —
the pass/oddities surfaces went in round 7, the shop freebie in round 8 — but this
module stays fully surface-agnostic, including the ``per_day`` path below.)

Contracts (same observability-only stance as core/status.py):
  * The WORKER is this file's only writer (one-writer-per-file rule); writes are
    atomic (temp file + ``os.replace``) so an out-of-process reader never catches
    a half-written file.
  * Cooldown: ONE alert per surface per day via ``last_alert_date`` — the event
    simply isn't re-emitted that day, but the streak KEEPS counting, so the alert
    re-fires tomorrow if the surface is still broken.
  * ``per_day=True`` surfaces (thresholds of "N consecutive DAYS") bump the streak
    at most once per calendar day, so a multi-session day can't fast-forward a
    days-based threshold. Session-based surfaces (the brawler grid) bump on every
    suspicious run. (No live surface uses ``per_day`` now — the shop dailies that
    did was removed in round 8 — but the path is retained and still tested.)
  * A corrupt/missing state file degrades to "start from zero" — never raises
    into the claim/sweep path (callers wrap us anyway, belt and braces).

File shape: ``{surface: {streak, last_inc_date, last_alert_date}}``.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from brawlfarm.core.jsonio import atomic_write_json

FILE_NAME = "recalib.json"

# Tri-state observation sentinel (review #56 MINOR): a NAV failure means the
# surface was never actually observed — neither suspicious nor healthy. Folding
# it as healthy would RESET a genuine streak (a reskin that also breaks a nav
# needle would be invisible forever). Callers pass SKIP; _note_recalib drops it.
SKIP = "__no_observation__"


def load(data_dir) -> dict:
    """The parsed state dict, or {} if missing/corrupt (never raises)."""
    try:
        data = json.loads((Path(data_dir) / FILE_NAME).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def record(
    data_dir,
    surface: str,
    suspicious: bool,
    threshold: int,
    *,
    per_day: bool = False,
    today: str | None = None,
) -> tuple[bool, int]:
    """Fold one observation for ``surface`` into its streak; persist atomically.

    Returns ``(fire, streak)`` — ``fire`` is True exactly when the caller should
    emit the ``recalibrate`` event NOW (streak >= threshold and no alert was sent
    for this surface today). A non-suspicious observation resets the streak to 0
    (the disagreement must be *consecutive* to mean a reskin, not noise).
    ``today`` is injectable for tests; defaults to the real calendar date.
    """
    d = Path(data_dir)
    d.mkdir(parents=True, exist_ok=True)
    path = d / FILE_NAME
    state = load(d)
    entry = state.get(surface)
    if not isinstance(entry, dict):
        entry = {}
    today = today or date.today().isoformat()
    streak = int(entry.get("streak") or 0)
    if suspicious:
        if not (per_day and entry.get("last_inc_date") == today):
            streak += 1
            entry["last_inc_date"] = today
    else:
        streak = 0
        entry.pop("last_inc_date", None)
    entry["streak"] = streak
    fire = streak >= threshold and entry.get("last_alert_date") != today
    if fire:
        entry["last_alert_date"] = today
    state[surface] = entry
    atomic_write_json(path, state)
    return fire, streak
