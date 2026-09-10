"""Suite-wide isolation: every test gets an empty home directory, no farm env, and the
module-level globals the panel and the supervisor mutate (notify's settings overrides,
the scheduler's default-enabled flag) put back afterwards."""

from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path, monkeypatch):
    for key in list(os.environ):
        if key.startswith(("BRAWL_", "DISCORD_", "NTFY_")):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("BRAWLFARM_HOME", str(tmp_path))
    from brawlfarm.core import config, notify, scheduler

    previous_home = config.HOME_DIR
    previous_default_enabled = scheduler.DEFAULT_ENABLED
    config.set_home(tmp_path)
    config.set_instances({})
    yield
    config.set_instances({})
    config.set_home(previous_home)
    # Supervisor.apply_settings() calls both of these, so any test that builds a
    # Supervisor leaves them set for the next test unless we put them back.
    notify._overrides.clear()
    notify._last_alert.clear()  # the 120 s per-kind alert cooldown is process-global too
    scheduler.set_default_enabled(previous_default_enabled)
