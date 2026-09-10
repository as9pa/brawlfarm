"""Session-data rotation (r8) — fold old per-session JSONL logs into one monthly file,
plus (r9) roll the oversized append-only ops logs.

WHY: each worker run writes a fresh ``data/<acct>/session-YYYYMMDD-HHMMSS.jsonl`` (the
startup-narration + recap event log). They accumulate fast (dozens a day across the
farms) and clutter the account dir. The owner: *"it's racking up sessions … migrate
into one organized file."* So this rotates: per account, the session files OLDER than
``KEEP_DAYS`` (7) get concatenated — in time order — into a per-month archive
``data/<acct>/archive/sessions-YYYY-MM.jsonl`` (appended), then the originals deleted.

r9 adds ``rotate_big_logs``: the project-level append-only ops logs
``data/audit.jsonl`` and ``data/events_history.jsonl`` grow without bound (no
per-session split), so once one crosses ~5 MB AND hasn't been written in 60 s it's
rolled into ``data/archive/<name>-YYYY-MM.jsonl`` (same copy-then-delete shape) and
the live file truncated for the blind-appending writer to reopen.

SAFETY (the readers must keep working):
  - The control panel's alert and feed tailers BOTH read only the *newest*
    ``session-*.jsonl`` (``sorted(glob(...))[-1]``). This janitor NEVER touches the
    newest ``KEEP_NEWEST`` (3) files, nor anything dated today — so the live tailers
    always find their file.
  - Move = copy-then-delete per file (the archive write lands fully before the source
    is removed). Idempotent on re-run: a file already archived is gone from the source
    dir, so a second pass simply finds nothing to do. A crash mid-rotation at worst
    duplicates ONE file's lines into the archive on the next run (the copy completed but
    the delete didn't) — acceptable for a log archive, and the file is then deleted, so
    it self-heals.
  - Best-effort by contract: ``rotate_all`` swallows per-account errors and returns a
    summary; a rotation hiccup must never break its caller (it runs from the
    supervisor's daily maintenance pass, which must keep going).

This is OFFLINE/pure-filesystem — no adb, no network, no game. Safe to run anytime.

CLI:
  python -m brawlfarm.core.janitor            # rotate all accounts (uses real `now`)
  python -m brawlfarm.core.janitor --dry-run  # report what WOULD move, touch nothing
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

from brawlfarm.core import config

KEEP_DAYS = 7  # only files older than this (by their timestamp) are eligible
KEEP_NEWEST = 3  # never touch the newest N session files (the live tailers' headroom)

# Append-only ops logs that grow without bound (no per-session split). Rotated by
# SIZE into the same monthly archive shape as the sessions.
BIG_LOG_NAMES = ("audit.jsonl", "events_history.jsonl")
BIG_LOG_MAX_BYTES = 5 * 1024 * 1024  # roll once a log crosses ~5 MB
BIG_LOG_QUIET_S = 60  # ...but only when it hasn't been written in the last 60 s
#   WHY the quiet window: the WRITERS (the audit log, core/events.py) append
#   blindly with no lock, so a roll racing an in-flight append could drop the
#   appended line. A file untouched for 60 s is safe to copy-then-delete.

# session-YYYYMMDD-HHMMSS.jsonl
_SESSION_RE = re.compile(r"^session-(\d{8})-(\d{6})\.jsonl$")


def _root() -> Path:
    """Env-overridable project root (BRAWL_SCHED_DATA_ROOT) so tests run against a tmp
    dir — the same knob core/scheduler.py uses."""
    return Path(os.environ.get("BRAWL_SCHED_DATA_ROOT", "") or config.HOME_DIR)


def _session_ts(path: Path) -> datetime | None:
    """Parse the timestamp encoded in a session filename, or None if it doesn't match."""
    m = _SESSION_RE.match(path.name)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")
    except ValueError:
        return None


def _archive_path(acct_dir: Path, ts: datetime) -> Path:
    """The monthly archive a given session timestamp folds into."""
    return acct_dir / "archive" / f"sessions-{ts.strftime('%Y-%m')}.jsonl"


def _append_file(src: Path, dst: Path) -> None:
    """Append src's full contents to dst (preserving line order), ensuring a trailing
    newline so concatenated sessions never glue two records onto one line."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    data = src.read_text(encoding="utf-8")
    if data and not data.endswith("\n"):
        data += "\n"
    with dst.open("a", encoding="utf-8") as f:
        f.write(data)


def rotate_account(acct_dir: Path, now: datetime, *, dry_run: bool = False) -> dict:
    """Rotate one account's old session files into monthly archives. Returns a summary
    ``{moved, skipped_recent, kept_newest, errors}``. Pure-filesystem; never raises for
    a per-file problem (counts it under ``errors`` and moves on)."""
    summary = {"moved": 0, "skipped_recent": 0, "kept_newest": 0, "errors": 0}
    if not acct_dir.is_dir():
        return summary

    # All session files with a parseable timestamp, sorted oldest -> newest by that
    # timestamp (the filename sorts the same way, but we sort on the parsed value to be
    # explicit and robust). The newest KEEP_NEWEST are always protected.
    dated = sorted(
        ((p, ts) for p in acct_dir.glob("session-*.jsonl") if (ts := _session_ts(p))),
        key=lambda pt: pt[1],
    )
    if not dated:
        return summary
    cutoff = now - timedelta(days=KEEP_DAYS)
    today = now.date()
    protected_newest = {p for p, _ in dated[-KEEP_NEWEST:]}

    for path, ts in dated:
        if path in protected_newest:  # never touch the live tailers' headroom
            summary["kept_newest"] += 1
            continue
        if ts.date() == today or ts >= cutoff:  # too new to archive yet
            summary["skipped_recent"] += 1
            continue
        try:
            dst = _archive_path(acct_dir, ts)
            if dry_run:
                summary["moved"] += 1
                continue
            _append_file(path, dst)  # copy first ...
            path.unlink()  # ... then delete (so a crash never loses the source content)
            summary["moved"] += 1
        except OSError as e:
            print(f"  WARN: {path.name}: {e!r}", file=sys.stderr)
            summary["errors"] += 1
    return summary


def rotate_all(now: datetime | None = None, *, dry_run: bool = False) -> dict:
    """Rotate every account dir in config.INSTANCES. Best-effort: a failure on one
    account is caught and recorded, never propagated (this runs from the supervisor's
    daily maintenance pass, which must keep running). Returns ``{<acct>: summary}``."""
    now = now or datetime.now()
    root = _root()
    out: dict = {}
    for name, inst in config.INSTANCES.items():
        acct_dir = root / inst["data"]
        try:
            out[name] = rotate_account(acct_dir, now, dry_run=dry_run)
        except Exception as e:  # noqa: BLE001 — one bad account must not abort the rest
            print(f"WARN: data_janitor failed for {name}: {e!r}", file=sys.stderr)
            out[name] = {"moved": 0, "skipped_recent": 0, "kept_newest": 0, "errors": 1}
    return out


def rotate_big_logs(now: datetime | None = None, *, dry_run: bool = False) -> dict:
    """Roll the append-only ops logs (``data/audit.jsonl``,
    ``data/events_history.jsonl``) into a monthly archive once they cross
    BIG_LOG_MAX_BYTES — copy-then-delete (the rotate_account pattern) to
    ``data/archive/<name>-YYYY-MM.jsonl``, then truncate the live file to empty so
    the blind-appending writer keeps working uninterrupted.

    Skips a file that has been written within the last BIG_LOG_QUIET_S (a roll
    racing an in-flight append could drop the line). Best-effort + summary —
    ``{<name>: {rolled, skipped, errors}}`` — so the daily janitor loop never dies."""
    now = now or datetime.now()
    data_dir = _root() / "data"
    out: dict = {}
    for name in BIG_LOG_NAMES:
        summary = {"rolled": 0, "skipped": 0, "errors": 0}
        out[name] = summary
        src = data_dir / name
        try:
            if not src.is_file() or src.stat().st_size < BIG_LOG_MAX_BYTES:
                continue
            if now.timestamp() - src.stat().st_mtime < BIG_LOG_QUIET_S:
                summary["skipped"] += 1  # written too recently — wait for it to settle
                continue
            if dry_run:
                summary["rolled"] += 1
                continue
            stem = name[:-6] if name.endswith(".jsonl") else name  # drop ".jsonl"
            dst = data_dir / "archive" / f"{stem}-{now.strftime('%Y-%m')}.jsonl"
            _append_file(src, dst)  # copy first ...
            src.write_text("", encoding="utf-8")  # ... then truncate (writer reopens)
            summary["rolled"] += 1
        except OSError as e:
            print(f"  WARN: {name}: {e!r}", file=sys.stderr)
            summary["errors"] += 1
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Rotate old session JSONL into monthly archives")
    ap.add_argument("--dry-run", action="store_true", help="report what would move, change nothing")
    args = ap.parse_args(argv)
    results = rotate_all(dry_run=args.dry_run)
    tag = "[dry-run] " if args.dry_run else ""
    for name, s in results.items():
        print(
            f"{tag}{name}: moved={s['moved']} skipped_recent={s['skipped_recent']} "
            f"kept_newest={s['kept_newest']} errors={s['errors']}"
        )
    for name, s in rotate_big_logs(dry_run=args.dry_run).items():
        print(f"{tag}{name}: rolled={s['rolled']} skipped={s['skipped']} errors={s['errors']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
