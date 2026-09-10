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
    monkeypatch.setenv("BRAWL_NOTIFY_EVENTS", "")
    assert notify.enabled_events() == frozenset()
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


def test_healthchecks_url_from_settings_then_env(monkeypatch) -> None:
    assert notify.healthchecks_url() == ""
    monkeypatch.setenv("HEALTHCHECKS_URL", "https://hc.invalid/from-env")
    assert notify.healthchecks_url() == "https://hc.invalid/from-env"
    notify.configure(healthchecks_url="https://hc.invalid/from-settings")
    assert notify.healthchecks_url() == "https://hc.invalid/from-settings"


def test_ping_healthchecks_is_a_no_op_without_a_url() -> None:
    calls: list[str] = []
    assert notify.ping_healthchecks(getter=lambda url, timeout: calls.append(url)) is False
    assert calls == []


def test_ping_healthchecks_gets_the_url_and_never_raises() -> None:
    seen: list[tuple[str, int]] = []

    class _Ok:
        status_code = 200

    def _get(url, timeout):
        seen.append((url, timeout))
        return _Ok()

    notify.configure(healthchecks_url="https://hc.invalid/uuid")
    assert notify.ping_healthchecks(getter=_get) is True
    assert seen == [("https://hc.invalid/uuid", 5)]

    def _boom(url, timeout):
        raise OSError("network down")

    assert notify.ping_healthchecks(getter=_boom) is False


def test_alert_title_is_shared_with_the_panel() -> None:
    assert notify.alert_title("crash") == "Bot crashed"
    assert notify.alert_title("offline") == "Instance offline"
    assert notify.alert_title("mystery") == "Bot: mystery"
