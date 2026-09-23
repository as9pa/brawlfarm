"""The newest finished session in one instance folder.

The API stops reporting status.json's session block the moment a worker stops, so a
stopped instance reads as zeros on a cold load. This joins the two files that survive the
stop: the session log narrates (its filename is the start, its last line is the end, its
kinds are the interrupts and the disconnects) and games.csv carries the only placement
(its `rank` column) and trophy change anyone wrote down.

It lives beside the other route-side readers rather than in the supervisor: a tick must
not grow a per-status disk walk, and instances.py is already where games.csv and
status.json are read.

Every read is wrapped. A broken session file must never break a Fleet card.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

from brawlfarm.api import feed

SESSION_GLOB = "session-*.jsonl"
SESSION_STAMP_FMT = "%Y%m%d-%H%M%S"  # core/datalog.py's filename, local time

# {resolved instance dir: (session filename, session stamp, games.csv stamp, value)}. A
# stamp is (mtime, size): mtime alone misses two writes inside one filesystem tick, which
# the Windows CI runner produces. A same-size rewrite inside one tick still slips through;
# games.csv is append-only so that does not happen in practice, and the next append fixes
# it. The work is redone only when one of those three changes, so a Fleet poll every few
# seconds costs two stat calls per instance.
_cache: dict[Path, tuple[str, tuple[float, int], tuple[float, int], dict | None]] = {}


def _newest_name(inst_dir: Path) -> str | None:
    """The newest session file by NAME. The name is session-%Y%m%d-%H%M%S.jsonl, so the
    names sort chronologically, which beats an mtime sort on a folder copied between
    machines."""
    try:
        names = sorted(p.name for p in inst_dir.glob(SESSION_GLOB) if p.is_file())
    except OSError:
        return None
    return names[-1] if names else None


def _stamp(path: Path) -> tuple[float, int]:
    """The file's (mtime, size), or (-1.0, -1) when it is not there. A missing games.csv
    is a stable cache key, not an exception."""
    try:
        st = path.stat()
    except OSError:
        return (-1.0, -1)
    return (st.st_mtime, st.st_size)


def _started_at(filename: str) -> datetime | None:
    """The session's start, parsed out of its own filename as local time."""
    stamp = filename[len("session-") : -len(".jsonl")]
    try:
        return datetime.strptime(stamp, SESSION_STAMP_FMT)
    except ValueError:
        return None


def _moment(value: object) -> datetime | None:
    """One "2026-09-12T22:14:07" as core/datalog.py writes it, or None."""
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _int_or_zero(value: object) -> int:
    """A hand-edited or half-written cell counts as zero, never as an exception."""
    try:
        return int(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def _float_or_none(value: object) -> float | None:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _games_window(path: Path, started: datetime, ended: datetime) -> tuple[int, int, float | None]:
    """(games, net trophies, mean placement) for the rows whose logged_at falls inside the
    session, ends included. An unreadable file is zeros."""
    games = 0
    trophies = 0
    ranks: list[float] = []
    try:
        with path.open("r", encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                moment = _moment(row.get("logged_at"))
                if moment is None or moment < started or moment > ended:
                    continue
                games += 1
                trophies += _int_or_zero(row.get("trophyChange"))
                rank = _float_or_none(row.get("rank"))
                if rank is not None:
                    ranks.append(rank)
    except (OSError, csv.Error, UnicodeDecodeError, ValueError):
        return 0, 0, None
    avg_placement = round(sum(ranks) / len(ranks), 1) if ranks else None
    return games, trophies, avg_placement


def _read(session_path: Path, games_path: Path, filename: str) -> dict | None:
    """The block for one session file, or None when even its name cannot be read."""
    started = _started_at(filename)
    if started is None:
        return None
    ended = started
    interrupts = 0
    disconnects = 0
    try:
        with session_path.open("r", encoding="utf-8") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    line = json.loads(raw)
                except ValueError:  # one bad line costs its line, never the session
                    continue
                if not isinstance(line, dict):
                    continue
                kind = str(line.get("kind") or "")
                if feed.classify(kind) == "interrupts":
                    interrupts += 1
                if kind == "disconnect":
                    disconnects += 1
                moment = _moment(line.get("ts"))
                if moment is not None and moment > ended:
                    ended = moment
    except (OSError, UnicodeDecodeError):
        return None
    games, trophies, avg_placement = _games_window(games_path, started, ended)
    return {
        "games": games,
        "trophies": trophies,
        "avg_placement": avg_placement,
        "disconnects": disconnects,
        "duration_s": max(0, int((ended - started).total_seconds())),
        "interrupts": interrupts,
        "ended_at": ended.isoformat(timespec="seconds"),
    }


def last_session(inst_dir: Path) -> dict | None:
    """This instance's newest finished session, or None when it has never written one."""
    inst_dir = Path(inst_dir)
    filename = _newest_name(inst_dir)
    if filename is None:
        _cache.pop(inst_dir, None)
        return None
    session_path = inst_dir / filename
    games_path = inst_dir / "games.csv"
    stamp = (filename, _stamp(session_path), _stamp(games_path))
    cached = _cache.get(inst_dir)
    if cached is not None and cached[:3] == stamp:
        return cached[3]
    value = _read(session_path, games_path, filename)
    _cache[inst_dir] = (*stamp, value)
    return value
