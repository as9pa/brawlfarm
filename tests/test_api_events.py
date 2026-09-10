"""The event bus and GET /api/events: SSE framing, replay after Last-Event-ID, the
oldest-first drop policy on a slow subscriber, publishing from the supervisor's tick
thread, log lines mirrored onto the bus, and supervisor state changes arriving as
"instance" events. No socket is opened: the stream generator is driven directly with a
fake request whose is_disconnected() flips after N polls."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import pytest

from brawlfarm.api.events import BusLogHandler, Event, EventBus, event_stream, format_sse
from tests.apihelpers import make_client


@pytest.fixture()
def api(tmp_path: Path):
    client, sup, home = make_client(tmp_path, ("alpha",))
    try:
        yield client, sup, home
    finally:
        client.__exit__(None, None, None)


class FakeRequest:
    """Stands in for a Starlette Request: the stream only ever asks whether the client is
    still there. is_disconnected() returns True after `checks` polls, which is how a test
    ends an otherwise infinite generator."""

    def __init__(self, checks: int) -> None:
        self.checks = checks
        self.seen = 0

    async def is_disconnected(self) -> bool:
        self.seen += 1
        return self.seen > self.checks


def test_format_sse_frames_id_kind_and_json() -> None:
    frame = format_sse(Event(id=7, kind="alert", data={"title": "Bot crashed"}, ts="t"))
    assert frame == 'id: 7\nevent: alert\ndata: {"title": "Bot crashed"}\n\n'


def test_format_sse_survives_a_value_json_cannot_encode() -> None:
    frame = format_sse(Event(id=1, kind="log", data={"when": object()}, ts="t"))
    assert frame.startswith("id: 1\nevent: log\ndata: {")
    assert json.loads(frame.split("data: ", 1)[1].strip())["when"].startswith("<object")


def test_publish_numbers_events_and_keeps_history() -> None:
    bus = EventBus(history=3)
    for n in range(5):
        bus.publish("log", {"n": n})
    assert [e.id for e in bus.recent()] == [3, 4, 5]
    assert [e.data["n"] for e in bus.recent(2)] == [3, 4]
    assert bus.recent()[0].ts  # stamped on publish


@pytest.mark.asyncio
async def test_subscribe_replays_history_after_last_id() -> None:
    bus = EventBus()
    bus.publish("instance", {"name": "alpha"})
    bus.publish("instance", {"name": "bravo"})
    subscription = bus.subscribe(last_id=1)
    replayed = await anext(subscription)
    await subscription.aclose()
    assert replayed.id == 2 and replayed.data == {"name": "bravo"}


@pytest.mark.asyncio
async def test_a_full_queue_drops_the_oldest_event_for_that_subscriber() -> None:
    bus = EventBus(queue_size=3)
    subscription = bus.subscribe()
    for n in range(5):
        bus.publish("log", {"n": n})
    kept = [(await anext(subscription)).data["n"] for _ in range(3)]
    await subscription.aclose()
    assert kept == [2, 3, 4]


@pytest.mark.asyncio
async def test_publish_from_a_worker_thread_reaches_the_loop() -> None:
    bus = EventBus()
    bus.attach(asyncio.get_running_loop())
    await asyncio.to_thread(bus.publish, "instance", {"name": "alpha"})
    await asyncio.sleep(0)  # let the scheduled call_soon_threadsafe run
    assert [e.kind for e in bus.recent()] == ["instance"]


@pytest.mark.asyncio
async def test_stream_keepalives_when_idle_then_stops_on_disconnect() -> None:
    bus = EventBus()
    request = FakeRequest(checks=3)
    stream = event_stream(bus, request, keepalive_s=0.02)
    assert await anext(stream) == ": keepalive\n\n"
    bus.publish("alert", {"id": 1})
    assert await anext(stream) == 'id: 1\nevent: alert\ndata: {"id": 1}\n\n'
    bus.publish("feed", {"instance": "alpha"})
    assert (await anext(stream)).startswith("id: 2\nevent: feed\n")
    with pytest.raises(StopAsyncIteration):
        await anext(stream)
    assert bus.subscriber_count() == 0  # the subscription is released on disconnect


@pytest.mark.asyncio
async def test_a_disconnect_during_a_keepalive_still_releases_the_subscription() -> None:
    """The ordinary shape of a closed browser tab: the stream was idle, so a keepalive
    left an __anext__ pending, and the next poll finds the client gone. The pending task
    has to finish being cancelled before the subscription is closed, or the queue is
    never released and the bus grows a dead subscriber per tab."""
    bus = EventBus()
    stream = event_stream(bus, FakeRequest(checks=1), keepalive_s=0.02)
    assert await anext(stream) == ": keepalive\n\n"
    with pytest.raises(StopAsyncIteration):
        await anext(stream)
    assert bus.subscriber_count() == 0


@pytest.mark.asyncio
async def test_stream_replays_from_the_last_event_id() -> None:
    bus = EventBus()
    bus.publish("log", {"message": "one"})
    bus.publish("log", {"message": "two"})
    stream = event_stream(bus, FakeRequest(checks=1), last_id=1, keepalive_s=0.02)
    assert await anext(stream) == 'id: 2\nevent: log\ndata: {"message": "two"}\n\n'
    await stream.aclose()


def test_bus_log_handler_publishes_log_events() -> None:
    bus = EventBus()
    log = logging.getLogger("brawlfarm.test-bus")
    log.setLevel(logging.INFO)
    handler = BusLogHandler(bus)
    log.addHandler(handler)
    try:
        log.info("tick: %s", "alpha=farming")
        log.debug("too quiet for the panel")
    finally:
        log.removeHandler(handler)
    assert [e.kind for e in bus.recent()] == ["log"]
    data = bus.recent()[0].data
    assert data["level"] == "INFO"
    assert data["logger"] == "brawlfarm.test-bus"
    assert data["message"] == "tick: alpha=farming"
    assert data["ts"]


def test_the_events_route_is_registered(api) -> None:
    client, _sup, _home = api
    # fastapi 0.141 keeps an included router lazy, so app.routes holds a wrapper rather
    # than the route itself; the schema is what actually says the path is served.
    assert "/api/events" in client.app.openapi()["paths"]


def test_supervisor_state_changes_arrive_as_instance_events(api) -> None:
    client, _sup, _home = api
    client.get("/api/health")  # one request turns the loop, so the queued publish lands
    bus = client.app.state.bus
    instance = next(e for e in bus.recent(500) if e.kind == "instance")
    assert instance.data["name"] == "alpha"
    assert instance.data["state"]
    assert instance.data["adb_port"] == 5555
