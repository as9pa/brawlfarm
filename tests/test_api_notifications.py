"""POST /api/notifications/test: what is tested is what is saved, the answer is two lists of
channel names in a fixed order, and no URL or topic ever appears in it."""

from __future__ import annotations

from pathlib import Path

import pytest

from brawlfarm.core import notify
from tests.apihelpers import make_client


@pytest.fixture()
def api(tmp_path: Path):
    client, sup, home = make_client(tmp_path, ("alpha", "bravo"))
    try:
        yield client, sup, home
    finally:
        client.__exit__(None, None, None)


def test_it_splits_the_channels_into_sent_and_failed(api, monkeypatch) -> None:
    client, sup, _home = api
    sup.settings.notifications.webhook_url = "https://hook.invalid/abc"
    sup.settings.notifications.ntfy_topic = "brawlfarm-test"
    seen: dict[str, str] = {}

    def fake_send_test(*, webhook_url, ntfy_server, ntfy_topic, healthchecks_url):
        seen.update(
            webhook_url=webhook_url,
            ntfy_server=ntfy_server,
            ntfy_topic=ntfy_topic,
            healthchecks_url=healthchecks_url,
        )
        return {"webhook": False, "ntfy": True}

    monkeypatch.setattr(notify, "send_test", fake_send_test)
    r = client.post("/api/notifications/test")
    assert r.status_code == 200
    assert r.json() == {"sent": ["ntfy"], "failed": ["webhook"]}
    # The route reads the supervisor's own section, so the screen tests what is on disk.
    assert seen["webhook_url"] == "https://hook.invalid/abc"
    assert seen["ntfy_topic"] == "brawlfarm-test"
    assert seen["ntfy_server"] == "https://ntfy.sh"
    assert seen["healthchecks_url"] == ""


def test_no_channel_configured_is_two_empty_lists_and_still_a_200(api, monkeypatch) -> None:
    client, _sup, _home = api
    monkeypatch.setattr(notify, "send_test", lambda **kwargs: {})
    r = client.post("/api/notifications/test")
    assert r.status_code == 200
    assert r.json() == {"sent": [], "failed": []}


def test_it_keeps_the_channel_order_send_test_returned(api, monkeypatch) -> None:
    client, _sup, _home = api
    monkeypatch.setattr(
        notify,
        "send_test",
        lambda **kwargs: {"webhook": True, "ntfy": True, "healthchecks": True},
    )
    body = client.post("/api/notifications/test").json()
    assert body["sent"] == ["webhook", "ntfy", "healthchecks"]
    assert body["failed"] == []


def test_the_answer_never_carries_a_url_or_a_topic(api, monkeypatch) -> None:
    client, sup, _home = api
    sup.settings.notifications.webhook_url = "https://hook.invalid/not-in-the-answer"
    sup.settings.notifications.ntfy_topic = "not-in-the-answer-either"
    monkeypatch.setattr(notify, "send_test", lambda **kwargs: {"webhook": True, "ntfy": False})
    text = client.post("/api/notifications/test").text
    assert "not-in-the-answer" not in text
    assert text == '{"sent":["webhook"],"failed":["ntfy"]}'
