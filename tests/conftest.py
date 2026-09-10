"""Suite-wide isolation: every test gets an empty home directory and no farm env."""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    for key in list(os.environ):
        if key.startswith(("BRAWL_", "DISCORD_", "NTFY_")):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("BRAWLFARM_HOME", str(tmp_path))
    from brawlfarm.core import config

    previous_home = config.HOME_DIR
    config.set_home(tmp_path)
    config.set_instances({})
    yield
    config.set_instances({})
    config.set_home(previous_home)
