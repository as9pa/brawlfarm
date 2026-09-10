"""Event-rotation snapshotter — Phase 0 of event-modifier awareness.

WHY (docs/future-plans/event-modifier-awareness.md): some event rotations carry
trophy-affecting modifiers, but we do NOT yet know which ones actually appear on
trioShowdown rotations. Phase 0 is measure-first: fetch the official rotation,
cache it, and append every snapshot to a history log. After ~2 weeks of history
the research doc records what shows up; only then does anything change behavior.
This module NEVER touches the scheduler — it is pure fetch + file plumbing.

Files (both under data/, anchored on the PROJECT ROOT — deliberately NOT
config.DATA_DIR, which is per-account env-overridable and the watchdog process
carries leftover BRAWL_DATA_DIR from farm launches):
  data/events.json          {fetched_at, rotation: [...]} — atomic write
  data/events_history.jsonl one {ts, rotation} line per real fetch (append-only)

Runner: tools/watchdog.ps1 calls ``python -m brawlfarm.core.events refresh`` each loop right
after the scheduler tick. The 30-min self-throttle makes that ~one real HTTP
fetch per half hour; every other call exits immediately. This module is the only
one in the fetch path that imports requests (via brawlfarm.core.api) — the scheduler tick
only ever *reads* data/events.json with stdlib json (in Phase 1+).

FAIL-OPEN CONTRACT: refresh() never raises and always exits 0 — an API outage,
a bad token, or a full disk must never propagate into the watchdog loop. On any
failure the last events.json is kept as-is.

CLI:
  python -m brawlfarm.core.events refresh
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from brawlfarm.core import config
from brawlfarm.core.jsonio import atomic_write_json

THROTTLE_MIN = 30  # exit immediately if events.json is younger than this
FETCH_TIMEOUT_S = 10.0  # HTTP timeout — the watchdog calls this in-loop, keep it short
TIME_FMT = "%Y-%m-%dT%H:%M:%S"  # same local-time format as core/scheduler.py


# --- paths (env-overridable root so tests run against a tmp dir) ---------------


def _root() -> Path:
    return Path(os.environ.get("BRAWL_EVENTS_DATA_ROOT", "") or config.HOME_DIR)


def _events_path() -> Path:
    return _root() / "data" / "events.json"


def _history_path() -> Path:
    return _root() / "data" / "events_history.jsonl"


# --- plumbing -------------------------------------------------------------------


def _write_json(path: Path, payload: dict) -> None:
    """Atomic write so a reader never catches a half-written file (core/jsonio.py)."""
    atomic_write_json(path, payload)


def _fetch_rotation() -> list[dict]:
    """The one HTTP call. Local import keeps ``import brawlfarm.core.events`` cheap and makes
    this the single seam tests fake (no real network in the suite)."""
    from brawlfarm.core.api import ApiClient

    return ApiClient(timeout=FETCH_TIMEOUT_S).get_event_rotation()


def _is_fresh(now: datetime) -> bool:
    """True if events.json exists and was fetched < THROTTLE_MIN ago. Any problem
    (missing, corrupt, bad timestamp) counts as stale — worst case we just fetch."""
    try:
        j = json.loads(_events_path().read_text(encoding="utf-8"))
        fetched = datetime.strptime(j["fetched_at"], TIME_FMT)
        return 0 <= (now - fetched).total_seconds() < THROTTLE_MIN * 60
    except Exception:
        return False


# --- the refresh ------------------------------------------------------------------


def refresh(now: datetime | None = None) -> int:
    """Fetch the rotation, atomically rewrite data/events.json and append one
    history line. Self-throttled; never raises; always returns 0 (the watchdog
    swallows our output — a nonzero exit would just be noise it has to ignore)."""
    try:
        now = now or datetime.now()
        if _is_fresh(now):
            print(f"fresh — skipped (throttle {THROTTLE_MIN} min)")
            return 0
        try:
            rotation = _fetch_rotation()
        except Exception as e:  # ApiError, network, bad token — keep the last file
            print(f"refresh failed (keeping last events.json): {e}")
            return 0
        ts = now.strftime(TIME_FMT)
        _write_json(_events_path(), {"fetched_at": ts, "rotation": rotation})
        try:
            with _history_path().open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"ts": ts, "rotation": rotation}) + "\n")
        except OSError as e:
            # events.json is already updated — a history hiccup is log-worthy only.
            print(f"history append failed: {e}")
        print(f"refreshed — {len(rotation)} rotation entries")
        return 0
    except Exception as e:  # absolute backstop: never raise to the caller
        print(f"refresh failed: {e}")
        return 0


# --- CLI ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # console may be cp1252 (like run.py)
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Event-rotation snapshotter (see module docstring)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("refresh", help="fetch + cache the rotation (30-min self-throttle)")
    args = ap.parse_args(argv)
    if args.cmd == "refresh":
        return refresh()
    return 0


if __name__ == "__main__":
    sys.exit(main())
