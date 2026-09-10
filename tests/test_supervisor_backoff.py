"""Offline backoff: 2, 4, 8, 16, then 30 minutes (and 30 thereafter); clear resets."""

from __future__ import annotations

from datetime import datetime, timedelta

from brawlfarm.supervisor.backoff import BACKOFF_MINUTES, OfflineBackoff

NOW = datetime(2026, 9, 10, 12, 0, 0)


def test_sequence_caps_at_thirty() -> None:
    b = OfflineBackoff()
    waits = [(b.record_miss("a", NOW) - NOW) for _ in range(7)]
    assert [w.total_seconds() / 60 for w in waits] == [2, 4, 8, 16, 30, 30, 30]
    assert BACKOFF_MINUTES == (2, 4, 8, 16, 30)
    assert b.misses("a") == 7


def test_until_and_expiry() -> None:
    b = OfflineBackoff()
    assert b.until("a", NOW) is None
    b.record_miss("a", NOW)
    assert b.until("a", NOW + timedelta(minutes=1)) == NOW + timedelta(minutes=2)
    assert b.until("a", NOW + timedelta(minutes=2)) is None  # expired: probe again
    assert b.misses("a") == 1  # expiry does not forget the miss count


def test_clear_is_per_instance_and_clear_all() -> None:
    b = OfflineBackoff()
    b.record_miss("a", NOW)
    b.record_miss("b", NOW)
    b.clear("a")
    assert b.misses("a") == 0 and b.until("a", NOW) is None
    assert b.misses("b") == 1
    b.clear_all()
    assert b.misses("b") == 0
