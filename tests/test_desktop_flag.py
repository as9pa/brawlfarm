"""`--window` opens the panel in a desktop window when the optional extras are installed,
and falls back to the browser with a hint when they are not. The extras are never imported
at module import time, so this file runs on a base install."""

from __future__ import annotations

import argparse
import asyncio

import pytest

from brawlfarm import __main__ as main_mod
from brawlfarm import desktop


def test_parser_has_window_flag():
    ns = main_mod._parser().parse_args(["--window"])
    assert ns.window is True
    assert main_mod._parser().parse_args([]).window is False


def test_available_false_without_extras(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name in {"webview", "pystray", "PIL"}:
            raise ImportError(name)
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert desktop.available() is False


def test_missing_message_names_the_group():
    assert "uv sync --group desktop" in desktop.MISSING_MESSAGE
    assert "browser" in desktop.MISSING_MESSAGE


def test_window_falls_back_to_browser(monkeypatch, capsys):
    monkeypatch.setattr(desktop, "available", lambda: False)
    calls: list[str] = []
    monkeypatch.setattr(main_mod, "_run_browser_mode", lambda args: calls.append("browser"))
    monkeypatch.setattr(main_mod, "_run_window_mode", lambda args: calls.append("window"))
    main_mod._dispatch(argparse.Namespace(window=True))
    assert calls == ["browser"]
    assert desktop.MISSING_MESSAGE.splitlines()[0] in capsys.readouterr().err


def test_window_mode_used_when_available(monkeypatch):
    monkeypatch.setattr(desktop, "available", lambda: True)
    calls: list[str] = []
    monkeypatch.setattr(main_mod, "_run_browser_mode", lambda args: calls.append("browser"))
    monkeypatch.setattr(main_mod, "_run_window_mode", lambda args: calls.append("window"))
    main_mod._dispatch(argparse.Namespace(window=True))
    assert calls == ["window"]


def test_no_window_never_asks_about_the_extras(monkeypatch, capsys):
    def explode() -> bool:
        raise AssertionError("available() must not be called without --window")

    monkeypatch.setattr(desktop, "available", explode)
    calls: list[str] = []
    monkeypatch.setattr(main_mod, "_run_browser_mode", lambda args: calls.append("browser"))
    main_mod._dispatch(argparse.Namespace(window=False))
    assert calls == ["browser"]
    assert capsys.readouterr().err == ""


class StoppableServer:
    """Stands in for uvicorn.Server in window mode: serve() returns once should_exit is set,
    which is what the quit callback ends up asking for."""

    def __init__(self) -> None:
        self.should_exit = False

    async def serve(self) -> None:
        while not self.should_exit:
            await asyncio.sleep(0.01)


class FakeSup:
    def __init__(self) -> None:
        self.stopped = False
        self._stop = asyncio.Event()

    async def run_forever(self) -> None:
        await self._stop.wait()

    def request_shutdown(self) -> None:
        self.stopped = True
        self._stop.set()


@pytest.mark.asyncio
async def test_stop_event_ends_the_server_and_the_supervisor() -> None:
    # Quit from the tray leaves nothing behind: the server exits and the supervisor is
    # asked to stop, exactly as the Ctrl+C path does.
    sup, server, stop = FakeSup(), StoppableServer(), asyncio.Event()
    serving = asyncio.create_task(
        main_mod._serve(
            sup,
            object(),
            8765,
            open_browser=False,
            make_server=lambda app, port: server,
            stop=stop,
        )
    )
    await asyncio.sleep(0.02)
    assert not serving.done()
    stop.set()
    await asyncio.wait_for(serving, timeout=2)
    assert server.should_exit is True
    assert sup.stopped is True
