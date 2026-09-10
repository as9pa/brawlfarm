"""config.set_home re-points every derived core path, and the suite-wide isolation
fixture reaches the CSV paths in datalog and stats (phase 1 deferral)."""

from __future__ import annotations

from pathlib import Path

from brawlfarm.core import config, datalog, stats


def test_set_home_repoints_every_derived_path(tmp_path: Path) -> None:
    home = tmp_path / "elsewhere"
    config.set_home(home)
    assert config.HOME_DIR == home.resolve()
    assert config.DATA_DIR == home.resolve() / "data"
    assert config.CAPTURES_DIR == home.resolve() / "captures"
    assert config.ONBOARD_SHOTS_DIR == home.resolve() / "captures" / "onboard"
    assert datalog.games_csv() == config.DATA_DIR / "games.csv"
    assert datalog.trophies_csv() == config.DATA_DIR / "menu_trophies.csv"
    assert stats.games_csv() == config.DATA_DIR / "games.csv"
    assert stats.trophies_csv() == config.DATA_DIR / "menu_trophies.csv"


def test_set_home_honours_brawl_data_dir(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("BRAWL_DATA_DIR", "instances/Pie64")
    config.set_home(tmp_path)
    assert config.DATA_DIR == tmp_path.resolve() / "instances" / "Pie64"


def test_datalog_writes_under_the_isolated_home(tmp_path: Path) -> None:
    dl = datalog.DataLog()
    assert datalog.games_csv().exists()
    assert datalog.games_csv().is_relative_to(tmp_path)
    assert datalog.trophies_csv().is_relative_to(tmp_path)
    assert dl.session_path.is_relative_to(tmp_path)


def test_no_module_level_csv_constants_remain() -> None:
    for mod in (datalog, stats):
        assert not hasattr(mod, "GAMES_CSV")
        assert not hasattr(mod, "TROPHIES_CSV")
