"""notify reads its backends from BRAWL_WEBHOOK_URL / NTFY_* or from configure(), and
BRAWL_NOTIFY_EVENTS (or configure(events=...)) filters which alert kinds are sent."""

from __future__ import annotations

import pytest

from brawlfarm.core import notify


@pytest.fixture(autouse=True)
def _reset():
    notify.configure(webhook_url=None, ntfy_server=None, ntfy_topic=None, events=None)
    notify._overrides.clear()
    notify._last_alert.clear()
    yield
    notify._overrides.clear()
    notify._last_alert.clear()


def test_unconfigured_by_default() -> None:
    assert notify.configured() is False


def test_env_webhook_new_name_and_legacy_fallback(monkeypatch) -> None:
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://legacy.invalid/x")
    assert notify.configured() is True
    monkeypatch.setenv("BRAWL_WEBHOOK_URL", "https://new.invalid/y")
    assert notify._webhook_url() == "https://new.invalid/y"


def test_configure_wins_over_env(monkeypatch) -> None:
    monkeypatch.setenv("NTFY_TOPIC", "from-env")
    notify.configure(ntfy_topic="from-settings", ntfy_server="https://ntfy.example/")
    assert notify._ntfy() == ("https://ntfy.example", "from-settings")


def test_events_filter_from_env_and_configure(monkeypatch) -> None:
    assert notify.enabled_events() == frozenset(notify.ALERT_KINDS)
    monkeypatch.setenv("BRAWL_NOTIFY_EVENTS", "crash, offline")
    assert notify.enabled_events() == frozenset({"crash", "offline"})
    notify.configure(events=["recover"])
    assert notify.enabled_events() == frozenset({"recover"})


def test_offline_is_an_alert_kind_and_filter_applies(monkeypatch) -> None:
    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(
        notify, "notify", lambda title, msg, screenshot=None: sent.append((title, msg)) or True
    )
    notify.configure(webhook_url="https://hook.invalid/z", events=["offline"])
    notify.maybe_alert("crash", {"x": 1})
    notify.maybe_alert("offline", {"instance": "Pie64", "misses": 3})
    assert sent == [("Instance offline", "instance=Pie64, misses=3")]
