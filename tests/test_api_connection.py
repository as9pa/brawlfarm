"""GET /api/connection/check: five statuses, one fetch per five minutes, and a log that
carries neither the token nor the player tag.

No test here opens a socket: fetch_player is replaced at every call site.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from pathlib import Path

import pytest
import requests

from brawlfarm.api import connection
from brawlfarm.core.api import ApiClient, ApiError
from tests.apihelpers import make_client

TOKEN = "test-token-not-a-real-one"
TAG = "#2P0YLQ9"
T0 = datetime(2026, 9, 12, 22, 14, 7)


class FakeResponse:
    """Enough of requests.Response for ApiClient._get: a status, a body and a json()."""

    def __init__(self, status_code: int, payload: object = None, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self) -> object:
        return self._payload


def test_api_error_carries_the_status_of_a_non_200(monkeypatch) -> None:
    client = ApiClient(token=TOKEN)
    monkeypatch.setattr(client._session, "get", lambda *a, **k: FakeResponse(403, text="nope"))
    with pytest.raises(ApiError) as caught:
        client.get_player(TAG)
    assert caught.value.status == 403
    # The message text is unchanged, so controller.py's three except ApiError blocks
    # behave exactly as they did. It carries the encoded tag, which is why nothing reads it.
    assert "HTTP 403" in str(caught.value)


def test_a_transport_failure_leaves_the_status_none(monkeypatch) -> None:
    client = ApiClient(token=TOKEN)

    def boom(*args, **kwargs):
        raise requests.RequestException("the socket went away")

    monkeypatch.setattr(client._session, "get", boom)
    with pytest.raises(ApiError) as caught:
        client.get_player(TAG)
    assert caught.value.status is None


@pytest.mark.parametrize(
    "token,tag,expected",
    [
        ("", TAG, "no_token"),
        ("   ", TAG, "no_token"),
        (TOKEN, "", "no_tag"),
        (TOKEN, "  ", "no_tag"),
        (TOKEN, TAG, None),
    ],
)
def test_credential_status(token, tag, expected) -> None:
    assert connection.credential_status(token, tag) == expected


def cache(fetch, *, clock=lambda: T0, now=None) -> connection.ConnectionCache:
    ticker = now or (lambda: 1000.0)
    return connection.ConnectionCache(now=ticker, clock=clock, fetch=fetch)


def test_a_clean_answer_is_ok() -> None:
    got = asyncio.run(cache(lambda tag, token: {"tag": tag}).get(TOKEN, TAG))
    assert got == ("ok", "2026-09-12T22:14:07")


@pytest.mark.parametrize("status", [401, 403])
def test_a_401_or_a_403_is_rejected(status) -> None:
    def boom(tag: str, token: str) -> dict:
        err = ApiError("/players/x -> HTTP %d: nope" % status)
        err.status = status
        raise err

    assert asyncio.run(cache(boom).get(TOKEN, TAG))[0] == "rejected"


def test_a_request_exception_is_unreachable() -> None:
    def boom(tag: str, token: str) -> dict:
        raise requests.RequestException("the socket went away")

    assert asyncio.run(cache(boom).get(TOKEN, TAG))[0] == "unreachable"


def test_a_500_is_unreachable() -> None:
    def boom(tag: str, token: str) -> dict:
        err = ApiError("/players/x -> HTTP 500: nope")
        err.status = 500
        raise err

    assert asyncio.run(cache(boom).get(TOKEN, TAG))[0] == "unreachable"


def test_a_second_call_inside_the_ttl_does_not_fetch_again() -> None:
    calls: list[str] = []
    ticks = [1000.0]

    def fetch(tag: str, token: str) -> dict:
        calls.append(tag)
        return {}

    cached = cache(fetch, now=lambda: ticks[0])

    async def twice() -> list[tuple[str, str]]:
        first = await cached.get(TOKEN, TAG)
        ticks[0] += connection.TTL_S - 1
        second = await cached.get(TOKEN, TAG)
        ticks[0] += 2
        third = await cached.get(TOKEN, TAG)
        return [first, second, third]

    results = asyncio.run(twice())
    assert [r[0] for r in results] == ["ok", "ok", "ok"]
    assert len(calls) == 2


def test_the_failure_log_carries_neither_the_token_nor_the_tag(caplog) -> None:
    def boom(tag: str, token: str) -> dict:
        raise ApiError(f"/players/{tag} -> HTTP 403: {token}")

    with caplog.at_level(logging.WARNING, logger="brawlfarm.api"):
        asyncio.run(cache(boom).get(TOKEN, TAG))
    text = "\n".join(record.getMessage() for record in caplog.records)
    assert TOKEN not in text
    assert "2P0YLQ9" not in text


def route_client(tmp_path: Path, *, token: str = TOKEN, tag: str = TAG):
    """A client whose one instance carries `tag`, with `token` in settings."""
    client, sup, home = make_client(tmp_path, ("Pie64",), **{"connection.brawl_api_token": token})
    sup.settings.instances[0].player_tag = tag
    return client, sup, home


def test_route_is_ok_when_the_player_endpoint_answers(tmp_path: Path) -> None:
    client, _sup, _home = route_client(tmp_path)
    try:
        client.app.state.connection = cache(lambda tag, token: {"tag": tag})
        r = client.get("/api/connection/check")
        assert r.status_code == 200
        assert r.json() == {"status": "ok", "checked_at": "2026-09-12T22:14:07"}
    finally:
        client.__exit__(None, None, None)


def test_route_is_no_token_without_a_network_call(tmp_path: Path) -> None:
    client, _sup, _home = route_client(tmp_path, token="")
    try:
        calls: list[str] = []
        client.app.state.connection = cache(lambda tag, token: calls.append(tag) or {})
        body = client.get("/api/connection/check").json()
        assert body["status"] == "no_token"
        assert body["checked_at"]
        assert calls == []
    finally:
        client.__exit__(None, None, None)


def test_route_is_no_tag_without_a_network_call(tmp_path: Path) -> None:
    client, _sup, _home = route_client(tmp_path, tag="")
    try:
        calls: list[str] = []
        client.app.state.connection = cache(lambda tag, token: calls.append(tag) or {})
        body = client.get("/api/connection/check").json()
        assert body["status"] == "no_tag"
        assert body["checked_at"]
        assert calls == []
    finally:
        client.__exit__(None, None, None)


def test_route_is_rejected_on_a_403(tmp_path: Path) -> None:
    client, _sup, _home = route_client(tmp_path)
    try:

        def boom(tag: str, token: str) -> dict:
            err = ApiError("/players/x -> HTTP 403: nope")
            err.status = 403
            raise err

        client.app.state.connection = cache(boom)
        assert client.get("/api/connection/check").json()["status"] == "rejected"
    finally:
        client.__exit__(None, None, None)


def test_route_is_unreachable_on_a_transport_failure(tmp_path: Path) -> None:
    client, _sup, _home = route_client(tmp_path)
    try:

        def boom(tag: str, token: str) -> dict:
            raise requests.RequestException("the socket went away")

        client.app.state.connection = cache(boom)
        assert client.get("/api/connection/check").json()["status"] == "unreachable"
    finally:
        client.__exit__(None, None, None)


def test_the_route_body_never_carries_the_token_or_the_tag(tmp_path: Path) -> None:
    client, _sup, _home = route_client(tmp_path)
    try:
        client.app.state.connection = cache(lambda tag, token: {"tag": tag})
        text = client.get("/api/connection/check").text
        assert TOKEN not in text
        assert "2P0YLQ9" not in text
    finally:
        client.__exit__(None, None, None)
