"""`brawlfarm` with no flags serves the panel: uvicorn and the supervisor share one loop,
the browser opens once on the right URL unless --no-browser, and the supervisor is asked to
stop -- and allowed to finish -- when the server returns, even though uvicorn re-raises the
Ctrl+C it swallowed. No socket is bound: the server object is a fake."""

from __future__ import annotations

import asyncio

import pytest

from brawlfarm.__main__ import _parser, _serve


class FakeServer:
    """Stands in for uvicorn.Server: serve() returns when the user presses Ctrl+C."""

    def __init__(self) -> None:
        self.served = False

    async def serve(self) -> None:
        self.served = True
        await asyncio.sleep(0.05)  # long enough for the browser task to get its turn


class CancellingServer:
    """uvicorn's capture_signals re-raises the SIGINT it swallowed as soon as serve()
    returns, and asyncio.run's own handler turns that into a cancel of the task awaiting
    serve(). Reproduces that state: the caller comes back from serve() already cancelled."""

    def __init__(self) -> None:
        self.served = False

    async def serve(self) -> None:
        self.served = True
        asyncio.current_task().cancel()


class FakeSup:
    def __init__(self) -> None:
        self.runs = 0
        self.stopped = False
        self._stop = asyncio.Event()

    async def run_forever(self) -> None:
        self.runs += 1
        await self._stop.wait()

    def request_shutdown(self) -> None:
        self.stopped = True
        self._stop.set()


class FinishingSup(FakeSup):
    """Records that run_forever returned normally rather than being cancelled."""

    def __init__(self) -> None:
        super().__init__()
        self.finished = False

    async def run_forever(self) -> None:
        await super().run_forever()
        self.finished = True


@pytest.mark.asyncio
async def test_serve_runs_the_supervisor_and_opens_the_browser() -> None:
    sup, server, opened = FakeSup(), FakeServer(), []
    await _serve(
        sup,
        object(),
        8765,
        open_browser=True,
        make_server=lambda app, port: server,
        browser_open=opened.append,
        delay_s=0.0,
    )
    assert server.served is True
    assert opened == ["http://127.0.0.1:8765/"]
    assert sup.runs == 1
    assert sup.stopped is True  # the supervisor loop is stopped; the workers are not


@pytest.mark.asyncio
async def test_no_browser_skips_the_browser_hook() -> None:
    sup, server, opened = FakeSup(), FakeServer(), []
    await _serve(
        sup,
        object(),
        9001,
        open_browser=False,
        make_server=lambda app, port: server,
        browser_open=opened.append,
        delay_s=0.0,
    )
    assert opened == []
    assert server.served is True
    assert sup.stopped is True


@pytest.mark.asyncio
async def test_a_browser_that_will_not_open_is_not_fatal() -> None:
    def _boom(url: str) -> None:
        raise RuntimeError("no display")

    sup, server = FakeSup(), FakeServer()
    await _serve(
        sup,
        object(),
        8765,
        open_browser=True,
        make_server=lambda app, port: server,
        browser_open=_boom,
        delay_s=0.0,
    )
    assert server.served is True and sup.stopped is True


def test_serve_flags_have_sane_defaults() -> None:
    args = _parser().parse_args([])
    assert args.port is None and args.no_browser is False and args.once is False
    args = _parser().parse_args(["--port", "9100", "--no-browser"])
    assert args.port == 9100 and args.no_browser is True


@pytest.mark.asyncio
async def test_ctrl_c_stops_the_supervisor_even_though_uvicorn_re_raises_it() -> None:
    sup, server = FinishingSup(), CancellingServer()
    await _serve(
        sup,
        object(),
        8765,
        open_browser=False,
        make_server=lambda app, port: server,
        delay_s=0.0,
    )
    assert server.served is True
    assert sup.stopped is True
    # run_forever ran to its own end instead of being cancelled part-way: that is what
    # lets a tick already in flight finish and log "supervisor loop stopped".
    assert sup.finished is True
