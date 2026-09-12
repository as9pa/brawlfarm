from pathlib import Path

import cv2
import numpy as np

from brawlfarm.core import config, vision


def test_template_names_match_folder():
    names = sorted(p.stem for p in config.TEMPLATES_DIR.glob("*.png"))
    assert list(vision.TEMPLATE_NAMES) == names
    assert "play" in vision.TEMPLATE_NAMES


def test_template_path_prefers_override(tmp_path: Path):
    config.set_home(tmp_path)
    assert vision.template_source("play") == "package"
    assert vision.template_path("play") == config.TEMPLATES_DIR / "play.png"
    override = tmp_path / "calibration" / "templates"
    override.mkdir(parents=True)
    img = np.zeros((10, 20, 3), dtype=np.uint8)
    cv2.imwrite(str(override / "play.png"), img)
    assert vision.template_source("play") == "override"
    assert vision.template_path("play") == override / "play.png"


def test_loader_picks_up_override_without_restart(tmp_path: Path):
    config.set_home(tmp_path)
    packaged = vision._load_template("play")
    override = tmp_path / "calibration" / "templates"
    override.mkdir(parents=True)
    img = np.full((10, 20, 3), 7, dtype=np.uint8)
    cv2.imwrite(str(override / "play.png"), img)
    loaded = vision._load_template("play")
    assert loaded.shape == (10, 20, 3)
    assert loaded.shape != packaged.shape
    (override / "play.png").unlink()
    assert vision._load_template("play").shape == packaged.shape


def test_threshold_for_matches_find_defaults():
    assert vision.threshold_for("play") == config.MATCH_THRESHOLD
    assert vision.threshold_for("teams_left") == config.IN_MATCH_THRESHOLD
    assert vision.threshold_for("matchmaking") == config.MATCHMAKING_THRESHOLD
