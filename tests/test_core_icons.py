"""core/icons.py: the brawler catalog and the disk icon cache.

Every test here stubs both fetches. Nothing in this file opens a socket, and the only
paths it writes are under the tmp_path home that conftest.py hands out.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from brawlfarm.core import icons

PNG = icons.PNG_MAGIC + b"the rest of a tiny png"


@pytest.fixture(autouse=True)
def _forget_refresh_stamp(monkeypatch):
    """The refresh rate limit is a module-level monotonic stamp, so it outlives a test
    unless it is put back. Every case starts as a fresh process would."""
    monkeypatch.setattr(icons, "_last_refresh_at", None)
    monkeypatch.setattr(icons, "_last_refresh_token", None)


def write_catalog(home: Path, catalog: dict[str, int]) -> None:
    path = icons.catalog_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(catalog), encoding="utf-8")


def test_resolve_id_answers_from_the_cached_catalog_without_fetching(tmp_path: Path) -> None:
    write_catalog(tmp_path, {"NORI": 42})
    calls: list[str] = []

    def fetch(token: str) -> list[dict]:
        calls.append(token)
        return []

    assert icons.resolve_id(tmp_path, "Nori", "tok", fetch=fetch) == 42
    assert calls == []


def test_resolve_id_matches_upper_cased_and_stripped(tmp_path: Path) -> None:
    write_catalog(tmp_path, {"MR. P": 7})
    assert icons.resolve_id(tmp_path, "  mr. p ", "tok", fetch=lambda _t: []) == 7


def test_a_miss_refreshes_once_and_writes_the_catalog(tmp_path: Path) -> None:
    write_catalog(tmp_path, {"NORI": 42})
    calls: list[str] = []

    def fetch(token: str) -> list[dict]:
        calls.append(token)
        return [{"id": 9, "name": "Shelly"}, {"id": 42, "name": "Nori"}]

    assert icons.resolve_id(tmp_path, "Shelly", "tok", fetch=fetch) == 9
    assert len(calls) == 1
    assert json.loads(icons.catalog_path(tmp_path).read_text(encoding="utf-8")) == {
        "SHELLY": 9,
        "NORI": 42,
    }


def test_a_second_miss_inside_the_hour_does_not_refresh(tmp_path: Path) -> None:
    calls: list[str] = []
    clock = [1000.0]

    def fetch(token: str) -> list[dict]:
        calls.append(token)
        # The first refresh does not carry Shelly, so the call after the hour is up has a
        # real miss to refresh for rather than an answer the first refresh already cached.
        return [{"id": 42, "name": "Nori"}] if len(calls) == 1 else [{"id": 9, "name": "Shelly"}]

    assert icons.resolve_id(tmp_path, "Ghost", "tok", now=lambda: clock[0], fetch=fetch) is None
    clock[0] += icons.REFRESH_S - 1
    assert icons.resolve_id(tmp_path, "Other", "tok", now=lambda: clock[0], fetch=fetch) is None
    assert len(calls) == 1
    clock[0] += 2
    assert icons.resolve_id(tmp_path, "Shelly", "tok", now=lambda: clock[0], fetch=fetch) == 9
    assert len(calls) == 2


def test_a_blank_token_is_a_miss_and_leaves_the_catalog_alone(tmp_path: Path) -> None:
    write_catalog(tmp_path, {"NORI": 42})
    calls: list[str] = []

    def fetch(token: str) -> list[dict]:
        calls.append(token)
        return [{"id": 9, "name": "Shelly"}]

    assert icons.resolve_id(tmp_path, "Shelly", "", fetch=fetch) is None
    assert calls == []
    assert json.loads(icons.catalog_path(tmp_path).read_text(encoding="utf-8")) == {"NORI": 42}


def test_a_refresh_that_raises_leaves_the_catalog_alone(tmp_path: Path) -> None:
    write_catalog(tmp_path, {"NORI": 42})

    def boom(token: str) -> list[dict]:
        raise RuntimeError("the CDN said no")

    assert icons.resolve_id(tmp_path, "Shelly", "tok", fetch=boom) is None
    assert json.loads(icons.catalog_path(tmp_path).read_text(encoding="utf-8")) == {"NORI": 42}


def test_a_refresh_that_raises_does_not_arm_the_hour(tmp_path: Path) -> None:
    """A rejected token or a dropped connection must not lock the catalog out for an hour:
    the next miss after the token is corrected has to reach the API again."""
    calls: list[str] = []
    clock = [1000.0]

    def fetch(token: str) -> list[dict]:
        calls.append(token)
        raise RuntimeError("the API said no")

    assert icons.resolve_id(tmp_path, "Shelly", "tok", now=lambda: clock[0], fetch=fetch) is None

    def ok(token: str) -> list[dict]:
        calls.append(token)
        return [{"id": 9, "name": "Shelly"}]

    clock[0] += 1
    assert icons.resolve_id(tmp_path, "Shelly", "tok", now=lambda: clock[0], fetch=ok) == 9
    assert len(calls) == 2


def test_a_changed_token_inside_the_hour_refreshes(tmp_path: Path) -> None:
    """The stamp is tied to the token that earned it, so correcting the token in settings
    clears the throttle without a restart."""
    calls: list[str] = []
    clock = [1000.0]

    def fetch(token: str) -> list[dict]:
        calls.append(token)
        return [{"id": 9, "name": "Shelly"}] if token == "good" else [{"id": 42, "name": "Nori"}]

    assert icons.resolve_id(tmp_path, "Shelly", "bad", now=lambda: clock[0], fetch=fetch) is None
    clock[0] += 1
    assert icons.resolve_id(tmp_path, "Shelly", "bad", now=lambda: clock[0], fetch=fetch) is None
    assert len(calls) == 1
    assert icons.resolve_id(tmp_path, "Shelly", "good", now=lambda: clock[0], fetch=fetch) == 9
    assert calls == ["bad", "good"]


def test_load_catalog_of_a_broken_file_is_empty(tmp_path: Path) -> None:
    path = icons.catalog_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")
    assert icons.load_catalog(tmp_path) == {}


def test_ensure_icon_serves_an_existing_file_without_fetching(tmp_path: Path) -> None:
    path = icons.icon_path(tmp_path, 42)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(PNG)
    calls: list[str] = []

    def fetch(url: str) -> bytes:
        calls.append(url)
        return b""

    assert icons.ensure_icon(tmp_path, 42, fetch=fetch) == PNG
    assert calls == []


def test_ensure_icon_fetches_and_writes_on_a_miss(tmp_path: Path) -> None:
    calls: list[str] = []

    def fetch(url: str) -> bytes:
        calls.append(url)
        return PNG

    assert icons.ensure_icon(tmp_path, 42, fetch=fetch) == PNG
    assert calls == ["https://cdn.brawlify.com/brawlers/borderless/42.png"]
    assert icons.icon_path(tmp_path, 42).read_bytes() == PNG
    assert list(icons.icon_path(tmp_path, 42).parent.glob("*.tmp")) == []


def test_ensure_icon_rejects_a_body_that_is_not_a_png(tmp_path: Path) -> None:
    assert icons.ensure_icon(tmp_path, 42, fetch=lambda _u: b"<html>nope</html>") is None
    assert not icons.icon_path(tmp_path, 42).exists()


def test_ensure_icon_rejects_an_oversized_body(tmp_path: Path) -> None:
    huge = icons.PNG_MAGIC + b"x" * icons.MAX_ICON_BYTES
    assert icons.ensure_icon(tmp_path, 42, fetch=lambda _u: huge) is None
    assert not icons.icon_path(tmp_path, 42).exists()


def test_ensure_icon_rejects_a_non_200(tmp_path: Path) -> None:
    def fetch(url: str) -> bytes:
        raise icons.IconUnavailable("the CDN did not serve an icon", 404)

    assert icons.ensure_icon(tmp_path, 42, fetch=fetch) is None
    assert not icons.icon_path(tmp_path, 42).exists()


def test_ensure_icon_writes_only_under_the_home_cache(tmp_path: Path) -> None:
    icons.ensure_icon(tmp_path, 42, fetch=lambda _u: PNG)
    written = [p for p in tmp_path.rglob("*") if p.is_file()]
    assert written == [tmp_path / "cache" / "brawlers" / "42.png"]
