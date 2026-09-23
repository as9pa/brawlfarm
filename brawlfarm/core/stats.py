"""
Read the bot's logged data into pandas frames and compute summary stats.

This is the data layer behind tools/dashboard.py, kept separate so it stays
importable and testable without Streamlit installed.

Sources (written by core/datalog.py):
  data/games.csv          one row per match (from the API battlelog)
  data/menu_trophies.csv  total-trophy snapshots over time
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from brawlfarm.core import config


def games_csv() -> Path:
    """Per-instance games log; resolved at call time so config.set_home() is honoured."""
    return config.DATA_DIR / "games.csv"


def trophies_csv() -> Path:
    return config.DATA_DIR / "menu_trophies.csv"


# battleTime from the API looks like "20260607T170728.000Z".
_BATTLETIME_FMT = "%Y%m%dT%H%M%S.%fZ"


def load_games(path: str | Path | None = None) -> pd.DataFrame:
    """Load games.csv with times parsed and numeric columns coerced, sorted oldest
    first. Returns an empty frame if the file doesn't exist yet."""
    path = Path(path) if path else games_csv()
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    if "battleTime" in df:
        df["battleTime"] = pd.to_datetime(
            df["battleTime"], format=_BATTLETIME_FMT, errors="coerce", utc=True
        )
    if "logged_at" in df:
        df["logged_at"] = pd.to_datetime(df["logged_at"], errors="coerce")
    for col in ("rank", "trophyChange", "duration_s"):
        if col in df:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "battleTime" in df:
        df = df.sort_values("battleTime").reset_index(drop=True)
    return df


def load_trophies(path: str | Path | None = None) -> pd.DataFrame:
    """Load menu_trophies.csv with time parsed and counts coerced, sorted oldest
    first. Returns an empty frame if the file doesn't exist yet."""
    path = Path(path) if path else trophies_csv()
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    if "logged_at" in df:
        df["logged_at"] = pd.to_datetime(df["logged_at"], errors="coerce")
    for col in ("total_trophies", "highest_trophies", "expLevel"):
        if col in df:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "logged_at" in df:
        df = df.sort_values("logged_at").reset_index(drop=True)
    return df


def summarize(games: pd.DataFrame, trophies: pd.DataFrame) -> dict:
    """Headline numbers for the dashboard's metric row. Every key is optional —
    callers should use .get() — so partial/empty data never raises."""
    s: dict = {"n_games": int(len(games))}

    if not games.empty and "trophyChange" in games:
        tc = games["trophyChange"].dropna()
        if len(tc):
            s["net_trophies_games"] = int(tc.sum())
            s["avg_trophy_change"] = round(float(tc.mean()), 2)
        rank = games["rank"].dropna() if "rank" in games else pd.Series(dtype=float)
        if len(rank):  # placed games only: other modes log no placement
            s["avg_placement"] = round(float(rank.mean()), 2)
            s["wins"] = int((rank == 1).sum())  # showdown: first place
            s["win_rate"] = round(float((rank == 1).mean()) * 100, 1)
        dur = games["duration_s"].dropna() if "duration_s" in games else pd.Series(dtype=float)
        if len(dur):
            s["avg_duration_s"] = round(float(dur.mean()), 1)
        bt = (
            games["battleTime"].dropna()
            if "battleTime" in games
            else pd.Series(dtype="datetime64[ns]")
        )
        if len(bt) >= 2:
            span_h = (bt.max() - bt.min()).total_seconds() / 3600
            s["span_hours"] = round(span_h, 2)
            if span_h > 0:
                s["games_per_hour"] = round(len(games) / span_h, 1)

    if not trophies.empty and "total_trophies" in trophies:
        tt = trophies["total_trophies"].dropna()
        if len(tt):
            s["trophies_start"] = int(tt.iloc[0])
            s["trophies_latest"] = int(tt.iloc[-1])
            s["trophies_gained"] = int(tt.iloc[-1] - tt.iloc[0])
        la = (
            trophies["logged_at"].dropna()
            if "logged_at" in trophies
            else pd.Series(dtype="datetime64[ns]")
        )
        if len(la) >= 2 and len(tt) >= 2:
            span_h = (la.max() - la.min()).total_seconds() / 3600
            if span_h > 0:
                s["trophies_per_hour"] = round((tt.iloc[-1] - tt.iloc[0]) / span_h, 1)

    return s


def per_brawler(games: pd.DataFrame) -> pd.DataFrame:
    """Games played, net trophy change, and average placement per brawler. Only
    aggregates columns that are actually present, so partial data never raises."""
    if games.empty or "brawler" not in games:
        return pd.DataFrame()
    aggs = {"games": ("brawler", "size")}
    if "trophyChange" in games:
        aggs["net_trophies"] = ("trophyChange", "sum")
    if "rank" in games:
        aggs["avg_placement"] = ("rank", "mean")
    return games.groupby("brawler").agg(**aggs).round(2).sort_values("games", ascending=False)


def placement_distribution(games: pd.DataFrame) -> pd.Series:
    """Count of finishes by showdown placement (1..10), read from the `rank` column."""
    if games.empty or "rank" not in games:
        return pd.Series(dtype=int)
    return games["rank"].dropna().astype(int).value_counts().sort_index()


def cumulative_trophy_change(games: pd.DataFrame) -> pd.DataFrame:
    """Per-game trophy change accumulated over time — a match-level view of
    progress that complements the menu_trophies snapshots."""
    if games.empty or "battleTime" not in games or "trophyChange" not in games:
        return pd.DataFrame()
    df = games[["battleTime", "trophyChange"]].dropna().copy()
    df["cumulative"] = df["trophyChange"].cumsum()
    return df.set_index("battleTime")
