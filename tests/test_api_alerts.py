"""Alerts: the worker's alert-worthy session events kept in memory for the Fleet drawer,
published on the bus as they arrive, listed newest first and dismissed one at a time."""

from __future__ import annotations

import sys
import threading
from pathlib import Path

import pytest

from brawlfarm.api.alerts import MAX_ALERTS, Alert, AlertStore
from brawlfarm.api.events import EventBus
from tests.apihelpers import make_client


@pytest.fixture()
def api(tmp_path: Path):
    client, sup, home = make_client(tmp_path, ("alpha",))
    try:
        yield client, sup, home
    finally:
        client.__exit__(None, None, None)


def test_add_titles_the_kind_and_joins_the_detail() -> None:
    bus = EventBus()
    store = AlertStore(bus)
    alert = store.add("alpha", "crash", {"err": "adb gone", "streak": 3, "note": None})
    assert alert == Alert(
        id=1,
        ts=alert.ts,
        instance="alpha",
        kind="crash",
        title="Bot crashed",
        detail="err=adb gone, streak=3",
        dismissed=False,
    )
    assert [(e.kind, e.data["title"]) for e in bus.recent()] == [("alert", "Bot crashed")]


def test_ingest_only_reacts_to_alert_kinds() -> None:
    store = AlertStore()
    assert store.ingest("alpha", {"ts": "2026-09-10T18:00:00", "kind": "tap", "x": 1}) is None
    assert store.ingest("alpha", {"ts": "2026-09-10T18:00:00", "kind": "phase"}) is None
    # a graceful stop pushes a notification (notify.ALERT_KINDS) but is not a panel alert
    assert store.ingest("alpha", {"ts": "2026-09-10T18:00:00", "kind": "stop", "games": 2}) is None
    alert = store.ingest(
        "alpha", {"ts": "2026-09-10T18:00:00", "kind": "recover", "reason": "stuck", "attempt": 1}
    )
    assert alert is not None
    assert alert.ts == "2026-09-10T18:00:00"
    assert alert.title == "Bot recovering"
    assert alert.detail == "reason=stuck, attempt=1"


def test_list_is_newest_first_and_hides_dismissed() -> None:
    store = AlertStore()
    first = store.add("alpha", "crash", {})
    second = store.add("bravo", "offline", {"misses": 3})
    assert [a.id for a in store.list()] == [second.id, first.id]
    assert store.unread_count() == 2
    assert store.dismiss(first.id) is True
    assert store.dismiss(999) is False
    assert [a.id for a in store.list()] == [second.id]
    assert [a.id for a in store.list(include_dismissed=True)] == [second.id, first.id]
    assert store.unread_count() == 1


def test_dismiss_all_clears_every_unread_alert() -> None:
    store = AlertStore()
    first = store.add("alpha", "crash", {"err": "adb gone"})
    store.add("bravo", "offline", {"misses": 3})
    assert store.dismiss(first.id) is True
    assert store.dismiss_all() == 1  # only the one that was still unread
    assert store.list() == []
    assert store.unread_count() == 0
    assert len(store.list(include_dismissed=True)) == 2
    assert store.dismiss_all() == 0  # a second call is a no-op, not an error


def test_the_store_is_bounded() -> None:
    store = AlertStore(maxlen=3)
    for n in range(5):
        store.add("alpha", "crash", {"n": n})
    assert [a.detail for a in store.list()] == ["n=4", "n=3", "n=2"]


def test_add_and_read_are_safe_from_two_threads() -> None:
    """The tailer adds on the loop thread while the supervisor's offline hook adds from the
    tick's worker thread, so the id counter, the deque and every reader are contended. The
    interpreter's switch interval is squeezed for the duration: at the default 5 ms each
    thread runs its whole loop inside one quantum and the race never gets a chance to show.
    """
    store = AlertStore()
    barrier = threading.Barrier(2)
    minted: list[list[Alert]] = [[], []]
    failures: list[Exception] = []

    def spam(slot: int) -> None:
        barrier.wait()  # both threads race the counter from the same instant
        try:
            for n in range(200):
                minted[slot].append(store.add("alpha", "crash", {"n": n}))
                if n % 10 == 0:  # reading while the other thread appends must not raise
                    store.list(include_dismissed=True)
                    store.unread_count()
                    store.dismiss(n)
        except Exception as exc:  # a thread that dies would otherwise just print and pass
            failures.append(exc)

    previous_interval = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        threads = [threading.Thread(target=spam, args=(slot,)) for slot in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
    finally:
        sys.setswitchinterval(previous_interval)

    assert failures == []
    ids = [alert.id for batch in minted for alert in batch]
    assert len(ids) == 400
    assert len(set(ids)) == 400  # no two alerts ever share an id
    assert len(store.list(include_dismissed=True)) == MAX_ALERTS  # the deque cap holds


def test_alert_routes_list_and_dismiss(api) -> None:
    client, _sup, _home = api
    store: AlertStore = client.app.state.alerts
    crash = store.add("alpha", "crash", {"err": "adb gone"})
    store.add("alpha", "offline", {"misses": 3})
    body = client.get("/api/alerts").json()
    assert body["unread"] == 2
    assert [a["kind"] for a in body["alerts"]] == ["offline", "crash"]
    assert body["alerts"][1]["title"] == "Bot crashed"
    assert body["alerts"][1]["instance"] == "alpha"

    assert client.post(f"/api/alerts/{crash.id}/dismiss").status_code == 204
    after = client.get("/api/alerts").json()
    assert after["unread"] == 1
    assert [a["kind"] for a in after["alerts"]] == ["offline"]
    assert len(client.get("/api/alerts?include_dismissed=true").json()["alerts"]) == 2
    assert client.post("/api/alerts/999/dismiss").status_code == 404


def test_the_dismiss_all_route_empties_the_drawer(api) -> None:
    client, _sup, _home = api
    store: AlertStore = client.app.state.alerts
    store.add("alpha", "crash", {"err": "adb gone"})
    store.add("alpha", "offline", {"misses": 3})

    assert client.post("/api/alerts/dismiss-all").status_code == 204
    assert client.get("/api/alerts").json() == {"alerts": [], "unread": 0}
    # Dismissed is read, not deleted: the drawer can still show them on request.
    assert len(client.get("/api/alerts?include_dismissed=true").json()["alerts"]) == 2
    # Clearing an already-clear drawer is still a 204, so the button never shows an error.
    assert client.post("/api/alerts/dismiss-all").status_code == 204


def test_the_app_wires_the_store_to_the_tailer_and_the_supervisor(api) -> None:
    client, _sup, _home = api
    store = client.app.state.alerts
    assert isinstance(store, AlertStore)
    assert client.app.state.tailer._alerts is store
