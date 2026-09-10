"""Stats aggregation over fixture games.csv files: local-time range filtering, the
30-minute session-gap rule behind "time farmed", the summary row, the per-instance
cumulative series, the per-brawler and rank tables, the recent list, the CSV export, and
the two routes with their 404 and 422 answers. No NaN ever reaches the JSON."""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from brawlfarm import settings as S
from brawlfarm.api.stats import aggregate, export_csv, load_games_for, range_start, sessions_hours
from brawlfarm.core import datalog
from tests.apihelpers import make_client

NOW = datetime(2026, 9, 10, 18, 0, 0)  # naive local, the way the routes call datetime.now()


@pytest.fixture()
def api(tmp_path: Path):
    client, sup, home = make_client(tmp_path, ("alpha", "bravo"))
    try:
        yield client, sup, home
    finally:
        client.__exit__(None, None, None)


def _battle_time(moment: datetime) -> str:
    """A local moment as the API's UTC battleTime string (datalog's %Y%m%dT%H%M%S.%fZ)."""
    return moment.astimezone(UTC).strftime("%Y%m%dT%H%M%S.%f")[:-3] + "Z"


def _game(minutes_ago: float, brawler: str, rank: int, change: int, duration: int = 150) -> dict:
    moment = NOW - timedelta(minutes=minutes_ago)
    return {
        "battleTime": _battle_time(moment),
        "logged_at": moment.isoformat(timespec="seconds"),
        "event_mode": "soloShowdown",
        "battle_mode": "soloShowdown",
        "type": "ranked",
        "rank": rank,
        "trophyChange": change,
        "result": "",
        "duration_s": duration,
        "map": "Feast or Famine",
        "brawler": brawler,
        "is_showdown": True,
    }


def _write_games(home: Path, name: str, rows: list[dict]) -> None:
    inst_dir = S.instance_dir(home, name)
    inst_dir.mkdir(parents=True, exist_ok=True)
    with (inst_dir / "games.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=datalog.GAME_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _fixture(home: Path) -> None:
    """alpha: one game yesterday, a three-game block, then one game after a 90 min gap.
    bravo: a single game. Numbers are chosen so every summary field is checkable by hand."""
    _write_games(
        home,
        "alpha",
        [
            _game(1500, "SHELLY", 9, -4),  # 25 h ago: outside "today", inside "7d"
            _game(120, "SHELLY", 2, 7),
            _game(115, "COLT", 4, 3),
            _game(110, "SHELLY", 1, 9),
            _game(20, "COLT", 8, -3),  # after a 90 min gap: a second session
        ],
    )
    _write_games(home, "bravo", [_game(60, "NITA", 3, 5)])


def test_range_start_is_local_and_midnight_for_today() -> None:
    assert range_start("today", NOW) == NOW.astimezone().replace(hour=0, minute=0, second=0)
    assert range_start("7d", NOW) == NOW.astimezone() - timedelta(days=7)
    assert range_start("30d", NOW) == NOW.astimezone() - timedelta(days=30)
    assert range_start("all", NOW) is None


def test_today_summary_across_two_instances(tmp_path: Path) -> None:
    _fixture(tmp_path)
    out = aggregate(tmp_path, ["alpha", "bravo"], "today", NOW)
    assert out["range"] == "today"
    assert out["instances"] == ["alpha", "bravo"]
    # 5 games today (yesterday's is excluded); 7+3+9-3+5 = 21 trophies; ranks 2,4,1,8,3;
    # sessions 16:00-16:10 (+150 s), 17:40 alone, bravo 17:00 alone = 17.5 min = 0.29 h.
    assert out["summary"] == {
        "games": 5,
        "trophies": 21,
        "trophies_per_hour": 72.0,
        "avg_rank": 3.6,
        "top4_rate": 80.0,
        "hours_farmed": 0.3,
    }


def test_seven_days_reaches_back_past_midnight(tmp_path: Path) -> None:
    _fixture(tmp_path)
    summary = aggregate(tmp_path, ["alpha"], "7d", NOW)["summary"]
    assert summary["games"] == 5
    assert summary["trophies"] == 12
    assert summary["avg_rank"] == 4.8
    assert summary["top4_rate"] == 60.0


def test_series_brawlers_ranks_and_recent(tmp_path: Path) -> None:
    _fixture(tmp_path)
    out = aggregate(tmp_path, ["alpha", "bravo"], "today", NOW)
    series = {s["instance"]: [p["cum"] for p in s["points"]] for s in out["series"]}
    assert series["alpha"] == [7, 10, 19, 16]
    assert series["bravo"] == [5]
    assert out["series"][0]["points"][0]["t"].startswith("2026-09-10T")
    assert out["brawlers"] == [
        {"name": "COLT", "games": 2, "net": 0, "avg_rank": 6.0, "top4_rate": 50.0},
        {"name": "SHELLY", "games": 2, "net": 16, "avg_rank": 1.5, "top4_rate": 100.0},
        {"name": "NITA", "games": 1, "net": 5, "avg_rank": 3.0, "top4_rate": 100.0},
    ]
    assert out["ranks"] == [
        {"rank": 1, "games": 1},
        {"rank": 2, "games": 1},
        {"rank": 3, "games": 1},
        {"rank": 4, "games": 1},
        {"rank": 8, "games": 1},
    ]
    assert len(out["recent"]) == 5
    assert out["recent"][0]["instance"] == "alpha"
    assert out["recent"][0]["brawler"] == "COLT"
    assert out["recent"][0]["rank"] == 8
    assert out["recent"][0]["trophy_change"] == -3
    assert out["recent"][0]["map"] == "Feast or Famine"
    assert out["recent"][0]["mode"] == "soloShowdown"


def test_empty_data_is_zeroed_and_json_safe(tmp_path: Path) -> None:
    out = aggregate(tmp_path, ["charlie"], "all", NOW)
    assert out["summary"] == {
        "games": 0,
        "trophies": 0,
        "trophies_per_hour": None,
        "avg_rank": None,
        "top4_rate": None,
        "hours_farmed": 0.0,
    }
    assert out["series"] == [{"instance": "charlie", "points": []}]
    assert out["brawlers"] == [] and out["ranks"] == [] and out["recent"] == []
    json.dumps(out, allow_nan=False)  # NaN would make the browser's JSON.parse fail


def test_sessions_hours_splits_on_a_thirty_minute_gap(tmp_path: Path) -> None:
    _write_games(
        tmp_path,
        "alpha",
        [_game(200, "SHELLY", 1, 9, duration=0), _game(180, "SHELLY", 1, 9, duration=0)],
    )
    together = load_games_for(tmp_path, ["alpha"], "all", NOW)
    assert round(sessions_hours(together), 3) == round(20 / 60, 3)

    _write_games(
        tmp_path,
        "alpha",
        [_game(200, "SHELLY", 1, 9, duration=0), _game(120, "SHELLY", 1, 9, duration=0)],
    )
    apart = load_games_for(tmp_path, ["alpha"], "all", NOW)
    assert sessions_hours(apart) == 0.0  # two one-game sessions, no duration to add


def test_export_csv_is_the_raw_rows_in_time_order(tmp_path: Path) -> None:
    _fixture(tmp_path)
    body = export_csv(tmp_path, ["alpha", "bravo"], "today", NOW)
    rows = list(csv.DictReader(body.splitlines()))
    assert list(rows[0]) == ["instance", *datalog.GAME_FIELDS]
    assert [r["instance"] for r in rows] == ["alpha", "alpha", "alpha", "bravo", "alpha"]
    assert [r["rank"] for r in rows] == ["2", "4", "1", "3", "8"]  # ints, not 2.0
    assert rows[0]["battleTime"] == _battle_time(NOW - timedelta(minutes=120))


def test_stats_routes(api) -> None:
    client, _sup, home = api
    _fixture(home)
    body = client.get("/api/stats?range=all").json()
    assert body["range"] == "all"
    assert body["instances"] == ["alpha", "bravo"]
    assert body["summary"]["games"] == 6
    assert client.get("/api/stats").json()["range"] == "today"
    assert client.get("/api/stats?range=all&instances=bravo").json()["instances"] == ["bravo"]
    assert client.get("/api/stats?range=year").status_code == 422
    assert client.get("/api/stats?instances=ghost").status_code == 404

    export = client.get("/api/stats/export.csv?range=all")
    assert export.status_code == 200
    assert export.headers["content-type"].startswith("text/csv")
    assert export.headers["content-disposition"] == 'attachment; filename="brawlfarm-games-all.csv"'
    assert export.text.splitlines()[0] == ",".join(["instance", *datalog.GAME_FIELDS])
    assert len(export.text.splitlines()) == 7  # header + 6 games
