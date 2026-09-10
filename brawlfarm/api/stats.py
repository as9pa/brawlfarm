"""Stats for the Stats screen (spec sections 7 and 8).

core/stats.py reads one instance's games.csv; this module reads several, filters them to a
range in LOCAL time (the owner thinks in local days, the API stamps battleTime in UTC) and
shapes the numbers the screen draws: the summary row, one cumulative-trophy series per
instance, the per-brawler table, the rank distribution and the recent games list. Every
number is rounded for display and NaN is turned into None, because json.dumps would happily
write NaN and the browser's JSON.parse would then reject the whole response.

"Time farmed" is an approximation (ruling 9): games are grouped per instance into sessions
split wherever more than 30 minutes passed since the previous game, and each session counts
as first-to-last plus the last game's duration.
"""

from __future__ import annotations

import asyncio
import csv
import io
import logging
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

import pandas as pd
from fastapi import APIRouter, HTTPException, Query, Request, Response

from brawlfarm import settings as S
from brawlfarm.core import datalog
from brawlfarm.core import stats as core_stats

log = logging.getLogger("brawlfarm.api")
router = APIRouter()

RANGES = ("today", "7d", "30d", "all")
RangeName = Literal["today", "7d", "30d", "all"]
SESSION_GAP_S = 1800.0  # more than 30 min between games ends a farming session
RECENT_LIMIT = 20
_BATTLETIME_FMT = "%Y%m%dT%H%M%S.%fZ"  # the API's format, as written by core/datalog.py


def range_start(range_: str, now: datetime) -> datetime | None:
    """The oldest local moment inside `range_`, or None for "all". `today` is local midnight
    so a session that ran past midnight splits across two days, which is what the owner
    means by "today"."""
    if range_ not in RANGES:
        raise ValueError(f"unknown range {range_!r}")
    local = now.astimezone()
    if range_ == "today":
        return local.replace(hour=0, minute=0, second=0, microsecond=0)
    if range_ == "7d":
        return local - timedelta(days=7)
    if range_ == "30d":
        return local - timedelta(days=30)
    return None


def load_games_for(home: Path, names: Sequence[str], range_: str, now: datetime) -> pd.DataFrame:
    """Every selected instance's games.csv in one frame with an `instance` column, times
    converted to the local zone and filtered to the range, oldest first. An instance with no
    file contributes nothing; nothing at all gives an empty frame with the right columns so
    every caller below can assume the columns exist."""
    start = range_start(range_, now)
    frames: list[pd.DataFrame] = []
    for name in names:
        df = core_stats.load_games(S.instance_dir(home, name) / "games.csv")
        if df.empty:
            continue
        df = df.copy()
        df["instance"] = name
        frames.append(df)
    if not frames:
        return pd.DataFrame(columns=["instance", *datalog.GAME_FIELDS])
    games = pd.concat(frames, ignore_index=True)
    if "battleTime" in games:
        games = games.dropna(subset=["battleTime"])
        # One fixed offset for the whole window: a DST change inside a 30-day range shifts
        # the boundary by an hour, which no owner will notice on a daily total.
        games["battleTime"] = games["battleTime"].dt.tz_convert(now.astimezone().tzinfo)
        if start is not None:
            games = games[games["battleTime"] >= start]
        games = games.sort_values("battleTime").reset_index(drop=True)
    return games


def sessions_hours(games: pd.DataFrame) -> float:
    """Hours actually farmed (ruling 9): per instance, sum first-to-last plus the last
    game's duration over each block of games no more than SESSION_GAP_S apart."""
    if games.empty or "battleTime" not in games or "instance" not in games:
        return 0.0
    total = 0.0
    for _name, part in games.groupby("instance", sort=False):
        part = part.dropna(subset=["battleTime"]).sort_values("battleTime")
        if part.empty:
            continue
        times = list(part["battleTime"])
        if "duration_s" in part:
            durations = [_num(d, 3) or 0.0 for d in part["duration_s"]]
        else:
            durations = [0.0] * len(times)
        start = times[0]
        previous, previous_duration = times[0], durations[0]
        for moment, duration in zip(times[1:], durations[1:], strict=True):
            if (moment - previous).total_seconds() > SESSION_GAP_S:
                total += (previous - start).total_seconds() + previous_duration
                start = moment
            previous, previous_duration = moment, duration
        total += (previous - start).total_seconds() + previous_duration
    return total / 3600.0


def _num(value, digits: int = 1) -> float | None:
    """Round for display; None for anything that is not a real number. pandas hands back
    NaN for a missing cell and json.dumps would write a bare NaN, which no browser parses."""
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:  # NaN
        return None
    return round(number, digits)


def _text(value) -> str | None:
    if value is None or (isinstance(value, float) and value != value):
        return None
    return str(value)


def aggregate(home: Path, names: Sequence[str], range_: str, now: datetime) -> dict:
    """Everything the Stats screen draws for one range and one set of instances.
    Blocking (pandas); the routes run it in a thread."""
    games = load_games_for(home, names, range_, now)
    hours = sessions_hours(games)
    changes = games["trophyChange"].dropna() if "trophyChange" in games else pd.Series(dtype=float)
    ranks = games["rank"].dropna() if "rank" in games else pd.Series(dtype=float)
    net = int(changes.sum()) if len(changes) else 0
    return {
        "range": range_,
        "instances": list(names),
        "summary": {
            "games": int(len(games)),
            "trophies": net,
            "trophies_per_hour": _num(net / hours) if hours > 0 else None,
            "avg_rank": _num(ranks.mean()) if len(ranks) else None,
            "top4_rate": _num(float((ranks <= 4).mean()) * 100) if len(ranks) else None,
            "hours_farmed": _num(hours),
        },
        "series": _series(games, names),
        "brawlers": _brawlers(games),
        "ranks": _ranks(ranks),
        "recent": _recent(games),
    }


def _series(games: pd.DataFrame, names: Sequence[str]) -> list[dict]:
    """One cumulative net-trophy line per instance, in battleTime order. An instance with no
    games still gets an entry so the chart legend matches the chips the user picked."""
    out: list[dict] = []
    for name in names:
        points: list[dict] = []
        if not games.empty and "instance" in games:
            running = 0
            for row in games[games["instance"] == name].to_dict("records"):
                change = _num(row.get("trophyChange"), 0)
                running += int(change) if change is not None else 0
                moment = row["battleTime"].to_pydatetime()
                points.append({"t": moment.isoformat(timespec="seconds"), "cum": running})
        out.append({"instance": name, "points": points})
    return out


def _brawlers(games: pd.DataFrame) -> list[dict]:
    if games.empty or "brawler" not in games:
        return []
    out: list[dict] = []
    for brawler, part in games.groupby("brawler", sort=False):
        ranks = part["rank"].dropna() if "rank" in part else pd.Series(dtype=float)
        changes = (
            part["trophyChange"].dropna() if "trophyChange" in part else pd.Series(dtype=float)
        )
        out.append(
            {
                "name": str(brawler),
                "games": int(len(part)),
                "net": int(changes.sum()) if len(changes) else 0,
                "avg_rank": _num(ranks.mean()) if len(ranks) else None,
                "top4_rate": _num(float((ranks <= 4).mean()) * 100) if len(ranks) else None,
            }
        )
    out.sort(key=lambda row: (-row["games"], row["name"]))  # name breaks ties, so it is stable
    return out


def _ranks(ranks: pd.Series) -> list[dict]:
    if not len(ranks):
        return []
    counts = ranks.astype(int).value_counts().sort_index()
    return [{"rank": int(rank), "games": int(n)} for rank, n in counts.items()]


def _recent(games: pd.DataFrame) -> list[dict]:
    """The newest RECENT_LIMIT games, newest first."""
    if games.empty:
        return []
    out: list[dict] = []
    for row in games.tail(RECENT_LIMIT).iloc[::-1].to_dict("records"):
        rank = _num(row.get("rank"), 0)
        change = _num(row.get("trophyChange"), 0)
        out.append(
            {
                "instance": _text(row.get("instance")),
                "t": row["battleTime"].to_pydatetime().isoformat(timespec="seconds"),
                "brawler": _text(row.get("brawler")),
                "rank": int(rank) if rank is not None else None,
                "trophy_change": int(change) if change is not None else None,
                "map": _text(row.get("map")),
                "mode": _text(row.get("event_mode")),
            }
        )
    return out


def _parse_battle_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, _BATTLETIME_FMT).replace(tzinfo=UTC)
    except (TypeError, ValueError):
        return None


def export_csv(home: Path, names: Sequence[str], range_: str, now: datetime) -> str:
    """The selected games as CSV: `instance` plus datalog.GAME_FIELDS, oldest first. Read
    with the csv module rather than pandas on purpose -- pandas turns an int column with one
    empty cell into floats, and the export must be byte-for-byte the values the worker
    logged. Blocking; the route runs it in a thread."""
    start = range_start(range_, now)
    rows: list[tuple[datetime, dict]] = []
    for name in names:
        path = S.instance_dir(home, name) / "games.csv"
        if not path.exists():
            continue
        try:
            with path.open("r", newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    moment = _parse_battle_time(row.get("battleTime"))
                    if moment is None or (start is not None and moment < start):
                        continue
                    fields = {k: row.get(k, "") for k in datalog.GAME_FIELDS}
                    rows.append((moment, {"instance": name, **fields}))
        except OSError as exc:
            log.warning("%s: cannot read games.csv: %s", name, exc)
    rows.sort(key=lambda pair: pair[0])
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=["instance", *datalog.GAME_FIELDS], lineterminator="\n")
    writer.writeheader()
    for _moment, row in rows:
        writer.writerow(row)
    return buf.getvalue()


def _selected(request: Request, instances: str | None) -> list[str]:
    """The instance filter: a comma-separated list, or every configured instance. An unknown
    name is a 404 like every other instance route, not a silently empty chart."""
    configured = [i.name for i in request.app.state.sup.settings.instances]
    if not instances:
        return configured
    names = [n.strip() for n in instances.split(",") if n.strip()]
    for name in names:
        if name not in configured:
            raise HTTPException(status_code=404, detail="unknown instance")
    return names


@router.get("/api/stats")
async def get_stats(
    request: Request,
    range_: RangeName = Query("today", alias="range"),
    instances: str | None = None,
) -> dict:
    """Summary, series, brawlers, ranks and recent games for one range. An unknown range is
    a 422 (FastAPI validates the Literal); an unknown instance is a 404."""
    names = _selected(request, instances)
    return await asyncio.to_thread(aggregate, request.app.state.home, names, range_, datetime.now())


@router.get("/api/stats/export.csv")
async def get_stats_csv(
    request: Request,
    range_: RangeName = Query("today", alias="range"),
    instances: str | None = None,
) -> Response:
    """The same selection as a CSV download, one row per game."""
    names = _selected(request, instances)
    body = await asyncio.to_thread(
        export_csv, request.app.state.home, names, range_, datetime.now()
    )
    return Response(
        content=body,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="brawlfarm-games-{range_}.csv"'},
    )
