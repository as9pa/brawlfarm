from pathlib import Path

from brawlfarm.core import calibration


def _ns() -> dict[str, object]:
    return {
        "PLAY_BUTTON": (1434, 830),
        "MATCH_THRESHOLD": 0.85,
        "ATTACK_INTERVAL": 0.5,
        "SCREEN_W": 1600,
        "GRAY_MATCH": True,
        "MAX_GAMES": 40,
        "NAME": "x",
        "COLOR_ONLY_TEMPLATES": frozenset({"close_x"}),
        "REGION": (1, 2, 3, 4),
        "_PRIVATE": 1.0,
        "lower": 2.0,
    }


def test_overridable_picks_floats_and_two_int_tuples_only():
    picked = calibration.overridable(_ns())
    assert set(picked) == {"PLAY_BUTTON", "MATCH_THRESHOLD", "ATTACK_INTERVAL"}


def test_group_of():
    assert calibration.group_of("PLAY_BUTTON", (1, 2)) == "tap"
    assert calibration.group_of("MATCH_THRESHOLD", 0.85) == "threshold"
    assert calibration.group_of("ATTACK_INTERVAL", 0.5) == "timing"


def test_apply_missing_file_changes_nothing(tmp_path: Path):
    ns = _ns()
    report = calibration.apply(ns, tmp_path / "calibration.toml")
    assert report.present is False
    assert report.applied == {}
    assert report.problems == ()
    assert ns["PLAY_BUTTON"] == (1434, 830)
    assert report.defaults["PLAY_BUTTON"] == (1434, 830)


def test_apply_overrides_and_converts(tmp_path: Path):
    f = tmp_path / "calibration.toml"
    f.write_text("PLAY_BUTTON = [1434, 826]\nMATCH_THRESHOLD = 1\n", encoding="utf-8")
    ns = _ns()
    report = calibration.apply(ns, f)
    assert ns["PLAY_BUTTON"] == (1434, 826)
    assert ns["MATCH_THRESHOLD"] == 1.0 and isinstance(ns["MATCH_THRESHOLD"], float)
    assert report.applied == {"PLAY_BUTTON": (1434, 826), "MATCH_THRESHOLD": 1.0}
    assert report.present is True and report.mtime_ns is not None


def test_apply_reports_unknown_and_wrong_shape(tmp_path: Path):
    f = tmp_path / "calibration.toml"
    f.write_text(
        'PLAY_BUTON = [1, 2]\nPLAY_BUTTON = "no"\nMATCH_THRESHOLD = [1, 2]\nSCREEN_W = 1\n',
        encoding="utf-8",
    )
    ns = _ns()
    report = calibration.apply(ns, f)
    assert ns["PLAY_BUTTON"] == (1434, 830)
    assert ns["MATCH_THRESHOLD"] == 0.85
    assert ns["SCREEN_W"] == 1600
    assert report.problems == (
        "MATCH_THRESHOLD must be a number.",
        "PLAY_BUTON is not a calibration constant. The line is ignored.",
        "PLAY_BUTTON must be two integers.",
        "SCREEN_W is not a calibration constant. The line is ignored.",
    )


def test_apply_bad_toml_changes_nothing(tmp_path: Path):
    f = tmp_path / "calibration.toml"
    f.write_text("PLAY_BUTTON = [1,", encoding="utf-8")
    ns = _ns()
    report = calibration.apply(ns, f)
    assert ns["PLAY_BUTTON"] == (1434, 830)
    assert len(report.problems) == 1
    assert report.problems[0].startswith("calibration.toml could not be read: ")


def test_apply_twice_restores_defaults_when_key_removed(tmp_path: Path):
    f = tmp_path / "calibration.toml"
    ns = _ns()
    f.write_text("PLAY_BUTTON = [1, 2]\n", encoding="utf-8")
    calibration.apply(ns, f)
    assert ns["PLAY_BUTTON"] == (1, 2)
    f.write_text("MATCH_THRESHOLD = 0.5\n", encoding="utf-8")
    report = calibration.apply(ns, f)
    assert ns["PLAY_BUTTON"] == (1434, 830)
    assert ns["MATCH_THRESHOLD"] == 0.5
    assert report.applied == {"MATCH_THRESHOLD": 0.5}


def test_changed_since(tmp_path: Path):
    f = tmp_path / "calibration.toml"
    ns = _ns()
    report = calibration.apply(ns, f)
    assert calibration.changed_since(report) is False
    f.write_text("MATCH_THRESHOLD = 0.5\n", encoding="utf-8")
    assert calibration.changed_since(report) is True


def test_config_applies_file_from_home(tmp_path: Path):
    from brawlfarm.core import config

    (tmp_path / "calibration").mkdir()
    (tmp_path / "calibration" / "calibration.toml").write_text(
        "MATCH_THRESHOLD = 0.77\n", encoding="utf-8"
    )
    config.set_home(tmp_path)
    try:
        assert config.MATCH_THRESHOLD == 0.77
        assert config.CALIBRATION.applied == {"MATCH_THRESHOLD": 0.77}
        assert config.CALIBRATION_FILE == tmp_path / "calibration" / "calibration.toml"
    finally:
        (tmp_path / "calibration" / "calibration.toml").unlink()
        config.set_home(tmp_path)
    assert config.MATCH_THRESHOLD == 0.85
