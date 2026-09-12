"""notify.send_test sends one alert to exactly the channels it is handed, reports each one
as a plain True or False, and leaves the module's own configured state untouched."""

from __future__ import annotations

import sys

import pytest

from brawlfarm.core import notify


class FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class FakeRequests:
    """Stands in for the requests module: records every call, answers with a status, and
    raises instead when the test handed it an exception."""

    def __init__(self, post=200, get=200) -> None:
        self._post, self._get = post, get
        self.posts: list[tuple[str, dict]] = []
        self.gets: list[str] = []

    def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        if isinstance(self._post, Exception):
            raise self._post
        return FakeResponse(self._post)

    def get(self, url, **kwargs):
        self.gets.append(url)
        if isinstance(self._get, Exception):
            raise self._get
        return FakeResponse(self._get)


def _install(monkeypatch, requests: FakeRequests) -> FakeRequests:
    """send_test imports requests lazily, so the fake only has to be in sys.modules."""
    monkeypatch.setitem(sys.modules, "requests", requests)
    return requests


@pytest.fixture()
def fake(monkeypatch) -> FakeRequests:
    return _install(monkeypatch, FakeRequests())


def test_every_configured_channel_is_reported(fake) -> None:
    result = notify.send_test(
        webhook_url="https://hook.invalid/abc",
        ntfy_server="https://ntfy.example/",
        ntfy_topic="brawlfarm-test",
        healthchecks_url="https://hc.invalid/ping",
    )
    assert result == {"webhook": True, "ntfy": True, "healthchecks": True}
    # The UI joins these names with ", " into one toast, so the order is part of the copy.
    assert list(result) == ["webhook", "ntfy", "healthchecks"]
    assert [url for url, _ in fake.posts] == [
        "https://hook.invalid/abc",
        "https://ntfy.example/brawlfarm-test",  # the trailing slash is stripped
    ]
    assert fake.gets == ["https://hc.invalid/ping"]
    assert fake.posts[0][1]["json"]["content"] == (
        "**brawlfarm test**\nThis is a test alert from brawlfarm."
    )
    assert fake.posts[1][1]["headers"]["Title"] == "brawlfarm test"
    assert fake.posts[1][1]["data"] == b"This is a test alert from brawlfarm."


def test_a_channel_that_does_not_answer_is_a_failure_not_an_exception(monkeypatch) -> None:
    _install(monkeypatch, FakeRequests(post=500, get=RuntimeError("name resolution failed")))
    result = notify.send_test(
        webhook_url="https://hook.invalid/abc",
        ntfy_server="https://ntfy.sh",
        ntfy_topic="brawlfarm-test",
        healthchecks_url="https://hc.invalid/ping",
    )
    # A test that explodes tells the user less than a test that says no.
    assert result == {"webhook": False, "ntfy": False, "healthchecks": False}


def test_an_unset_channel_gets_no_key_at_all(fake) -> None:
    assert notify.send_test(
        webhook_url="",
        ntfy_server="https://ntfy.sh",
        ntfy_topic="brawlfarm-test",
        healthchecks_url="",
    ) == {"ntfy": True}
    assert (
        notify.send_test(
            webhook_url="", ntfy_server="https://ntfy.sh", ntfy_topic="", healthchecks_url=""
        )
        == {}
    )
    # Whitespace is not a channel, so nothing is sent and nothing is claimed.
    assert (
        notify.send_test(webhook_url="   ", ntfy_server=" ", ntfy_topic="  ", healthchecks_url=" ")
        == {}
    )
    assert fake.posts == [("https://ntfy.sh/brawlfarm-test", fake.posts[0][1])]


def test_it_leaves_the_modules_own_settings_alone(fake) -> None:
    notify.configure(webhook_url="https://configured.invalid/z", events=["crash"])
    before = dict(notify._overrides)

    notify.send_test(
        webhook_url="https://typed.invalid/abc",
        ntfy_server="https://ntfy.sh",
        ntfy_topic="typed-topic",
        healthchecks_url="",
    )

    assert notify._overrides == before
    assert notify._webhook_url() == "https://configured.invalid/z"
    assert notify.enabled_events() == frozenset({"crash"})
    assert notify._last_alert == {}  # no per-kind cooldown was started
    # The test went where the screen said, not where the supervisor is configured.
    assert [url for url, _ in fake.posts] == [
        "https://typed.invalid/abc",
        "https://ntfy.sh/typed-topic",
    ]
