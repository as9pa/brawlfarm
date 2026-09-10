"""The in-process event bus and the SSE stream behind GET /api/events (spec section 7).

Everything the panel updates from live goes through one bus: supervisor state changes
(kind "instance"), session narration lines (kind "feed", task 7), alerts (kind "alert",
task 8) and the supervisor's own log lines (kind "log"). Publishers may be on any thread
-- the supervisor's tick runs in a worker thread, so its listeners do too -- so publish()
hops back onto the event loop with call_soon_threadsafe. Every subscriber gets its own
bounded queue: a browser tab that stops reading loses its oldest events instead of
stalling the farm.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import deque
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

router = APIRouter()

KEEPALIVE_S = 15.0  # an idle stream still writes a comment frame this often


@dataclass(frozen=True)
class Event:
    """One thing that happened, as the stream sends it. `id` is monotonic per process so a
    reconnecting browser can ask for everything after the last one it saw."""

    id: int
    kind: str
    data: dict
    ts: str


def _running_loop() -> asyncio.AbstractEventLoop | None:
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        return None


class EventBus:
    def __init__(self, *, history: int = 500, queue_size: int = 200) -> None:
        self._history: deque[Event] = deque(maxlen=history)
        self._queue_size = queue_size
        self._subscribers: list[asyncio.Queue[Event]] = []
        self._loop: asyncio.AbstractEventLoop | None = None
        self._next_id = 1

    def attach(self, loop: asyncio.AbstractEventLoop) -> None:
        """Remember the loop the app runs on; publishers on other threads hand their events
        to it. Called once from the lifespan."""
        self._loop = loop

    def publish(self, kind: str, data: dict) -> None:
        """Thread-safe. Never logs anything: BusLogHandler publishes INTO this bus, so a log
        call here would recurse."""
        loop = self._loop
        if loop is not None and loop is not _running_loop():
            loop.call_soon_threadsafe(self._push, kind, data)
            return
        self._push(kind, data)

    def _push(self, kind: str, data: dict) -> None:
        """Always runs on the loop thread, so the id counter and the queues need no lock."""
        event = Event(
            id=self._next_id,
            kind=kind,
            data=data,
            ts=datetime.now().isoformat(timespec="seconds"),
        )
        self._next_id += 1
        self._history.append(event)
        for queue in self._subscribers:
            if queue.full():
                # Drop this subscriber's oldest event rather than blocking the publisher:
                # a stalled tab must never slow the supervisor down.
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

    def subscribe(self, last_id: int | None = None) -> AsyncIterator[Event]:
        """History after `last_id` (if given), then live events. NOT an async generator on
        purpose: a generator body does not run until its first __anext__, and every event
        published in that window would be lost. Registering the queue here closes the gap.
        The caller must iterate the result (the SSE route always does) -- the queue is
        released in the iterator's finally block."""
        queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=self._queue_size)
        self._subscribers.append(queue)
        replay = [e for e in self._history if e.id > last_id] if last_id is not None else []
        return self._iterate(queue, replay)

    async def _iterate(
        self, queue: asyncio.Queue[Event], replay: list[Event]
    ) -> AsyncIterator[Event]:
        try:
            for event in replay:
                yield event
            while True:
                yield await queue.get()
        finally:
            self._subscribers.remove(queue)

    def recent(self, n: int = 50) -> list[Event]:
        """The newest `n` events, oldest first."""
        return list(self._history)[-n:]

    def subscriber_count(self) -> int:
        """Open streams; the tests assert a disconnect actually releases the queue."""
        return len(self._subscribers)


def format_sse(event: Event) -> str:
    """One SSE frame. default=str so an odd value in a payload degrades to its repr instead
    of breaking the whole stream."""
    payload = json.dumps(event.data, ensure_ascii=False, default=str)
    return f"id: {event.id}\nevent: {event.kind}\ndata: {payload}\n\n"


class BusLogHandler(logging.Handler):
    """Mirrors the `brawlfarm` logger onto the bus as kind "log" so the panel can show what
    the supervisor is doing. Attached in the lifespan, removed on shutdown."""

    def __init__(self, bus: EventBus, level: int = logging.INFO) -> None:
        super().__init__(level)
        self._bus = bus

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._bus.publish(
                "log",
                {
                    "ts": datetime.fromtimestamp(record.created).isoformat(timespec="seconds"),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                },
            )
        except Exception:  # a bad format string must never take the process down
            pass


async def event_stream(
    bus: EventBus,
    request,
    last_id: int | None = None,
    keepalive_s: float = KEEPALIVE_S,
) -> AsyncIterator[str]:
    """The SSE body: replay after `last_id`, then live events, with a comment frame every
    `keepalive_s` while idle so proxies keep the connection and a dead client is noticed.

    The pending __anext__ is kept across a timeout instead of being cancelled: cancelling
    it would close the async generator (its finally runs and the next __anext__ raises
    StopAsyncIteration), which would end the stream at the first keepalive.
    """
    subscription = bus.subscribe(last_id)
    pending: asyncio.Task[Event] | None = None
    try:
        while not await request.is_disconnected():
            if pending is None:
                pending = asyncio.ensure_future(anext(subscription))
            done, _ = await asyncio.wait({pending}, timeout=keepalive_s)
            if not done:
                yield ": keepalive\n\n"
                continue
            try:
                event = pending.result()
            except StopAsyncIteration:
                return
            finally:
                pending = None
            yield format_sse(event)
    finally:
        if pending is not None:
            # Wait for the cancellation to land before closing. Until it does the
            # subscription is still mid-__anext__, and aclose() on a running async
            # generator raises RuntimeError instead of releasing the queue -- which is
            # the common path, because an idle stream disconnects with a pending anext.
            pending.cancel()
            try:
                await pending
            except asyncio.CancelledError:
                pass
        await subscription.aclose()


def _parse_last_id(header: str | None) -> int | None:
    """The browser's Last-Event-ID on a reconnect. Junk is ignored (start from live)."""
    try:
        return int(header) if header else None
    except (TypeError, ValueError):
        return None


@router.get("/api/events")
async def get_events(request: Request) -> StreamingResponse:
    """Server-sent events: instance state changes, feed lines, alerts and supervisor log
    lines. Send Last-Event-ID to resume; the bus keeps the newest 500 events."""
    bus: EventBus = request.app.state.bus
    last_id = _parse_last_id(request.headers.get("Last-Event-ID"))
    return StreamingResponse(
        event_stream(bus, request, last_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
