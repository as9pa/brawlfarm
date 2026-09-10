"""The suite-wide fixture puts back the module globals a test may set: notify's settings
overrides and the scheduler's default-enabled flag (phase 2 deferral).

The two tests run in definition order, which is what makes the pin work: the first
dirties both globals, the second proves the autouse fixture's teardown cleaned them.
"""

from __future__ import annotations

from brawlfarm.core import notify, scheduler


def test_a_test_may_dirty_the_notify_and_scheduler_globals() -> None:
    notify.configure(webhook_url="https://example.invalid/hook", events=["crash"])
    notify._last_alert["crash"] = 1.0
    scheduler.set_default_enabled(False)
    assert notify._overrides["webhook_url"] == "https://example.invalid/hook"
    assert scheduler.DEFAULT_ENABLED is False


def test_the_next_test_sees_them_clean() -> None:
    assert notify._overrides == {}
    assert notify._last_alert == {}
    assert scheduler.DEFAULT_ENABLED is True
