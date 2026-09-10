"""Suite-wide isolation: every test gets an empty home directory and no farm env."""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    for key in list(os.environ):
        if key.startswith(("BRAWL_", "DISCORD_")):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("BRAWLFARM_HOME", str(tmp_path))
    from brawlfarm.core import config

    monkeypatch.setattr(config, "HOME_DIR", tmp_path)
    monkeypatch.setattr(config, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(config, "CAPTURES_DIR", tmp_path / "captures")
    config.set_instances({})
    yield
    config.set_instances({})
