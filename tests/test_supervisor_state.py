"""Heartbeat classification (healthy / stale / dead) and the derived instance state the
spec shows everywhere (farming, stopped, scheduled break, reconnecting, offline, plus
the transitional starting and stopping)."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta

import pytest

from brawlfarm.supervisor import state as st

NOW = datetime(2026, 9, 10, 12, 0, 0)


def _status(age_s: float, **fields) -> dict:
    """A status.json stamped ``age_s`` seconds before NOW. status.json keeps WHOLE seconds,
    so round the stamp toward NOW instead of truncating away from it: truncating 239.9s
    would land the heartbeat exactly ON the 240s stale line and pin the wrong side of it."""
    stamped = NOW - timedelta(seconds=age_s)
    if stamped.microsecond:
        stamped = stamped.replace(microsecond=0) + timedelta(seconds=1)
    ts = stamped.strftime("%Y-%m-%dT%H:%M:%S")
    return {"ts": ts, "pid": 4242, "phase": "playing", **fields}


def test_heartbeat_age() -> None:
    assert st.heartbeat_age_s(_status(12), NOW) == pytest.approx(12.0)
    assert st.heartbeat_age_s(None, NOW) is None
    assert st.heartbeat_age_s({"pid": 1}, NOW) is None
    assert st.heartbeat_age_s({"ts": "garbage"}, NOW) is None


@pytest.mark.parametrize(
    "status, alive, expected",
    [
        (_status(10), True, st.Health.HEALTHY),
        (_status(239.9), True, st.Health.HEALTHY),
        (_status(240), True, st.Health.STALE),
        (_status(9999), True, st.Health.STALE),
        (None, True, st.Health.STALE),
        (_status(10), False, st.Health.DEAD),
        (None, False, st.Health.DEAD),
    ],
)
def test_classify(status, alive, expected) -> None:
    assert st.classify(status, alive, NOW) == expected


def _derive(**kw):
    base = dict(
        health=st.Health.DEAD,
        desired="run",
        desired_reason="session",
        desired_until=None,
        stop_pending=False,
        booting=False,
        offline_until=None,
        status=None,
    )
    base.update(kw)
    return st.derive_state(**base)


def test_farming_when_alive_and_wanted() -> None:
    until = NOW + timedelta(minutes=30)
    assert _derive(health=st.Health.HEALTHY, desired_until=until, status=_status(5)) == (
        st.InstanceState.FARMING,
        until,
    )
    assert _derive(health=st.Health.STALE, status=_status(300))[0] == st.InstanceState.FARMING


def test_stopping_beats_everything_while_alive() -> None:
    deadline = NOW + timedelta(seconds=110)
    assert _derive(
        health=st.Health.HEALTHY, stop_pending=deadline, status=_status(5, recovery_attempts=2)
    ) == (st.InstanceState.STOPPING, deadline)


def test_reconnecting_when_alive_and_recovering() -> None:
    assert _derive(health=st.Health.HEALTHY, status=_status(5, recovery_attempts=1))[0] == (
        st.InstanceState.RECONNECTING
    )
    assert _derive(health=st.Health.HEALTHY, status=_status(5, disconnect_count=3))[0] == (
        st.InstanceState.RECONNECTING
    )
    assert _derive(health=st.Health.HEALTHY, status=_status(5, recovery_attempts=0))[0] == (
        st.InstanceState.FARMING
    )


def test_offline_wins_over_break_and_run_when_dead() -> None:
    retry = NOW + timedelta(minutes=4)
    assert _derive(offline_until=retry) == (st.InstanceState.OFFLINE, retry)
    assert _derive(offline_until=retry, desired="stop", desired_reason="gap") == (
        st.InstanceState.OFFLINE,
        retry,
    )


def test_starting_while_booting_or_awaiting_launch() -> None:
    assert _derive(booting=True) == (st.InstanceState.STARTING, None)
    assert _derive(desired="run") == (st.InstanceState.STARTING, None)


def test_scheduled_break_and_stopped() -> None:
    resume = NOW + timedelta(hours=1)
    assert _derive(desired="stop", desired_reason="gap", desired_until=resume) == (
        st.InstanceState.SCHEDULED_BREAK,
        resume,
    )
    assert _derive(desired="stop", desired_reason="override_stop", desired_until=resume) == (
        st.InstanceState.STOPPED,
        None,
    )


def test_instance_view_is_frozen() -> None:
    view = st.InstanceView(
        name="Pie64",
        adb_port=5555,
        state=st.InstanceState.STOPPED,
        health=st.Health.DEAD,
        pid=None,
        heartbeat_age_s=None,
        phase=None,
        desired="stop",
        desired_reason="override_stop",
        until=None,
        games_played=None,
        farm_brawler=None,
        note="",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        view.name = "x"  # type: ignore[misc]
