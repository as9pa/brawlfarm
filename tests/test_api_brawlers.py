"""GET /api/brawlers/{name}/icon.png: the PNG with a week of Cache-Control and an ETag,
304 on a match, one 404 detail for every kind of miss, one CDN call per id however many
requests race, and no token or tag anywhere in the log.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import pytest

from brawlfarm.api import brawlers
from brawlfarm.core import icons
from tests.apihelpers import make_client

PNG = icons.PNG_MAGIC + b"the rest of a tiny png"
TOKEN = "test-token-not-a-real-one"
NORI_URL = "https://cdn.brawlify.com/brawlers/borderless/42.png"
SHELLY_URL = "https://cdn.brawlify.com/brawlers/borderless/9.png"


class FakeCdn:
    """Stands in for requests.get against the CDN.

    The route reaches the network through icons.fetch_icon_bytes, whose default argument
    is bound at definition time, so replacing that NAME would not change what ensure_icon
    calls. icons.requests is looked up on every call, which makes it the seam that works.
    """

    def __init__(self, body: bytes = PNG, status: int = 200) -> None:
        self.body = body
        self.status = status
        self.urls: list[str] = []

    def get(self, url: str, timeout: float | None = None):
        self.urls.append(url)
        return _CdnResponse(self.status, self.body)


class _CdnResponse:
    def __init__(self, status_code: int, content: bytes) -> None:
        self.status_code = status_code
        self.content = content


class FakeApiClient:
    """Stands in for icons.ApiClient, for the same reason FakeCdn stands in for requests:
    fetch_brawlers looks the class up on the module at call time."""

    items: list[dict] = []

    def __init__(self, token: str | None = None, timeout: float = 20.0) -> None:
        self.token = token

    def get_brawlers(self) -> list[dict]:
        return list(type(self).items)


@pytest.fixture(autouse=True)
def _fresh_module_state(monkeypatch):
    """The refresh stamp, the per-id locks and the once-per-process prewarm flag all live
    at module level, so every test starts as a fresh process would."""
    monkeypatch.setattr(icons, "_last_refresh_at", None)
    monkeypatch.setattr(brawlers, "_locks", {})
    monkeypatch.setattr(brawlers, "_prewarmed", False)


@pytest.fixture()
def api(tmp_path: Path):
    client, sup, home = make_client(tmp_path, ("Pie64",), **{"connection.brawl_api_token": TOKEN})
    try:
        yield client, sup, home
    finally:
        client.__exit__(None, None, None)


def write_catalog(home: Path, catalog: dict[str, int]) -> None:
    path = icons.catalog_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(catalog), encoding="utf-8")


def write_icon(home: Path, brawler_id: int, body: bytes = PNG) -> None:
    path = icons.icon_path(home, brawler_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)


def test_icon_is_served_with_a_week_of_cache_and_an_etag(api) -> None:
    client, _sup, home = api
    write_catalog(home, {"NORI": 42})
    write_icon(home, 42)
    r = client.get("/api/brawlers/Nori/icon.png")
    assert r.status_code == 200
    assert r.content == PNG
    assert r.headers["content-type"] == "image/png"
    assert r.headers["cache-control"] == "public, max-age=604800"
    assert len(r.headers["etag"]) == 18  # 16 hex chars inside quotes


def test_a_matching_if_none_match_is_304_with_the_same_headers(api) -> None:
    client, _sup, home = api
    write_catalog(home, {"NORI": 42})
    write_icon(home, 42)
    etag = client.get("/api/brawlers/Nori/icon.png").headers["etag"]
    r = client.get("/api/brawlers/Nori/icon.png", headers={"If-None-Match": etag})
    assert r.status_code == 304
    assert r.content == b""
    assert r.headers["etag"] == etag
    assert r.headers["cache-control"] == "public, max-age=604800"


def test_an_unknown_name_is_404_no_icon(api, monkeypatch) -> None:
    client, _sup, home = api
    write_catalog(home, {"NORI": 42})
    FakeApiClient.items = []
    monkeypatch.setattr(icons, "ApiClient", FakeApiClient)
    r = client.get("/api/brawlers/Ghost/icon.png")
    assert r.status_code == 404
    assert r.json() == {"detail": "no icon"}


def test_a_blank_token_is_404_no_icon(tmp_path: Path) -> None:
    client, _sup, _home = make_client(tmp_path, ("Pie64",))
    try:
        r = client.get("/api/brawlers/Nori/icon.png")
        assert r.status_code == 404
        assert r.json() == {"detail": "no icon"}
    finally:
        client.__exit__(None, None, None)


def test_a_cdn_failure_is_404_no_icon(api, monkeypatch) -> None:
    client, _sup, home = api
    write_catalog(home, {"NORI": 42})
    monkeypatch.setattr(icons, "requests", FakeCdn(body=b"<html>nope</html>"))
    r = client.get("/api/brawlers/Nori/icon.png")
    assert r.status_code == 404
    assert r.json() == {"detail": "no icon"}


@pytest.mark.parametrize("name", ["a" * 33, "Nori%00"])
def test_a_name_that_fails_the_pattern_is_404_before_any_disk_work(api, name) -> None:
    client, _sup, home = api
    r = client.get(f"/api/brawlers/{name}/icon.png")
    assert r.status_code == 404
    assert r.json() == {"detail": "no icon"}
    assert not (home / "cache").exists()


@pytest.mark.parametrize("name", ["..%2Fetc", "Nori/../.."])
def test_a_name_carrying_a_separator_never_reaches_the_route(api, name) -> None:
    """A slash, encoded or not, makes the URL a longer path that matches no route, so the
    router's own 404 answers and BRAWLER_NAME_RE is never even consulted. The detail is
    starlette's rather than this route's; what matters is that nothing touched the disk."""
    client, _sup, home = api
    r = client.get(f"/api/brawlers/{name}/icon.png")
    assert r.status_code == 404
    assert not (home / "cache").exists()


def test_two_concurrent_requests_for_a_new_id_cost_one_cdn_call(api, monkeypatch) -> None:
    client, _sup, home = api
    write_catalog(home, {"NORI": 42})
    cdn = FakeCdn()
    monkeypatch.setattr(icons, "requests", cdn)

    async def both() -> list[int]:
        return await asyncio.gather(
            asyncio.to_thread(lambda: client.get("/api/brawlers/Nori/icon.png").status_code),
            asyncio.to_thread(lambda: client.get("/api/brawlers/Nori/icon.png").status_code),
        )

    assert asyncio.run(both()) == [200, 200]
    assert cdn.urls == [NORI_URL]


def test_neither_the_token_nor_the_tag_reaches_the_log(api, monkeypatch, caplog) -> None:
    client, _sup, home = api
    write_catalog(home, {"NORI": 42})
    monkeypatch.setattr(icons, "requests", FakeCdn(status=503))
    with caplog.at_level(logging.WARNING, logger="brawlfarm.api"):
        assert client.get("/api/brawlers/Nori/icon.png").status_code == 404
    text = "\n".join(record.getMessage() for record in caplog.records)
    assert TOKEN not in text
    assert "2P0YLQ9" not in text
    assert "HTTP 503" in text


def test_prewarm_with_no_token_makes_no_call(tmp_path: Path, monkeypatch) -> None:
    cdn = FakeCdn()
    FakeApiClient.items = [{"id": 42, "name": "Nori"}]
    monkeypatch.setattr(icons, "requests", cdn)
    monkeypatch.setattr(icons, "ApiClient", FakeApiClient)
    assert brawlers.prewarm(tmp_path, "  ", ["Nori"], sleep=lambda _s: None) == 0
    assert cdn.urls == []
    assert not icons.catalog_path(tmp_path).exists()


def test_prewarm_fetches_only_the_ids_with_no_file(tmp_path: Path, monkeypatch) -> None:
    write_catalog(tmp_path, {"NORI": 42, "SHELLY": 9})
    write_icon(tmp_path, 42)
    cdn = FakeCdn()
    monkeypatch.setattr(icons, "requests", cdn)
    warmed = brawlers.prewarm(tmp_path, TOKEN, ["Nori", "Shelly", "Nori"], sleep=lambda _s: None)
    assert warmed == 1
    assert cdn.urls == [SHELLY_URL]


def test_prewarm_runs_once_per_process(tmp_path: Path, monkeypatch) -> None:
    write_catalog(tmp_path, {"SHELLY": 9})
    cdn = FakeCdn()
    monkeypatch.setattr(icons, "requests", cdn)
    assert brawlers.prewarm(tmp_path, TOKEN, ["Shelly"], sleep=lambda _s: None) == 1
    assert brawlers.prewarm(tmp_path, TOKEN, ["Shelly"], sleep=lambda _s: None) == 0
    assert cdn.urls == [SHELLY_URL]


def test_a_raising_fetch_does_not_propagate(tmp_path: Path, monkeypatch) -> None:
    write_catalog(tmp_path, {"SHELLY": 9})

    class Exploding:
        def get(self, url: str, timeout: float | None = None):
            raise OSError("the socket went away")

    monkeypatch.setattr(icons, "requests", Exploding())
    assert brawlers.prewarm(tmp_path, TOKEN, ["Shelly"], sleep=lambda _s: None) == 0
