"""Console entry point.

`brawlfarm` with no flags serves the control panel: uvicorn and the supervisor share one
asyncio loop bound to 127.0.0.1, and the default browser opens on the panel a second later
(spec section 3). `--once` keeps the headless mode phase 2 shipped: one tick, print the
instance table, exit. Closing the process leaves workers running; the next start reattaches
to them through their status.json PIDs.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import os
import sys
import threading
import webbrowser
from logging.handlers import RotatingFileHandler
from pathlib import Path

from brawlfarm import __version__
from brawlfarm import settings as S

log = logging.getLogger("brawlfarm")


def _positive(value: str) -> float:
    """argparse type for --interval: a tick every 0 seconds is a busy loop, not a setting."""
    try:
        seconds = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be a number of seconds") from None
    if seconds <= 0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return seconds


def _port(value: str) -> int:
    """argparse type for --port: port 0 tells the OS to pick an ephemeral one, which the
    URL we print and open a browser on would then be lying about."""
    try:
        port = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("must be a port number") from None
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("must be between 1 and 65535")
    return port


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="brawlfarm", description="Brawl Stars trophy farmer")
    ap.add_argument("-V", "--version", action="store_true", help="print the version and exit")
    ap.add_argument(
        "--home",
        type=Path,
        default=None,
        help="data directory (default: BRAWLFARM_HOME or %%LOCALAPPDATA%%\\brawlfarm)",
    )
    ap.add_argument(
        "--once", action="store_true", help="run one supervisor tick, print the instances, exit"
    )
    ap.add_argument(
        "--interval", type=_positive, default=None, help="seconds between ticks (default 60)"
    )
    ap.add_argument("--no-launch", action="store_true", help="never start a worker (dry run)")
    ap.add_argument("--port", type=_port, default=None, help="panel port (default: app.port, 8765)")
    ap.add_argument(
        "--no-browser", action="store_true", help="serve the panel without opening a browser"
    )
    ap.add_argument(
        "--window",
        action="store_true",
        help="open the panel in a desktop window with a tray icon (needs uv sync --group desktop)",
    )
    return ap


def _setup_logging(home: Path) -> None:
    logs = home / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S")
    root = logging.getLogger("brawlfarm")
    root.setLevel(logging.INFO)
    root.handlers.clear()
    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(fmt)
    root.addHandler(stream)
    file = RotatingFileHandler(
        logs / "supervisor.log", maxBytes=5_000_000, backupCount=1, encoding="utf-8"
    )
    file.setFormatter(fmt)
    root.addHandler(file)


def _print_table(views) -> None:
    if not views:
        print("no instances configured; add [[instances]] entries to config.toml")
        return
    print(f"{'name':<16}{'port':<8}{'state':<18}{'health':<9}{'pid':<8}{'note'}")
    for v in views:
        until = f" (until {v.until:%H:%M})" if v.until else ""
        print(
            f"{v.name:<16}{v.adb_port:<8}{v.state:<18}{v.health:<9}{v.pid or '-':<8}{v.note}{until}"
        )


def _uvicorn_server(app, port: int):
    """A uvicorn Server, not yet started. Imported here so `brawlfarm --version` and
    `--once` do not pay for the import."""
    import uvicorn

    return uvicorn.Server(
        uvicorn.Config(
            app,
            host="127.0.0.1",  # loopback only; there is no authentication (spec section 3)
            port=port,
            log_level="warning",
            log_config=None,  # keep our handlers; uvicorn's default config replaces them
            access_log=False,
        )
    )


async def _open_later(url: str, delay_s: float, opener) -> None:
    """Give uvicorn a moment to bind before the browser asks for the page."""
    await asyncio.sleep(delay_s)
    try:
        opener(url)
    except Exception as exc:  # a machine with no browser is not an error
        log.warning("could not open a browser: %s", exc)


async def _serve(
    sup,
    app,
    port: int,
    *,
    open_browser: bool,
    make_server=_uvicorn_server,
    browser_open=webbrowser.open,
    delay_s: float = 1.0,
    stop: asyncio.Event | None = None,
) -> None:
    """Serve the panel and supervise the fleet on one loop. uvicorn owns the signal
    handling: Ctrl+C ends serve(), and only then is the supervisor asked to stop. The final
    await lets a tick already running in its worker thread finish; the workers themselves
    are left alone on purpose.

    In window mode this loop runs off the main thread, where uvicorn's signal handlers
    never fire; `stop` is the Ctrl+C the tray's Quit sends instead."""
    server = make_server(app, port)
    supervising = asyncio.create_task(sup.run_forever())
    browsing = None
    if open_browser:
        browsing = asyncio.create_task(
            _open_later(f"http://127.0.0.1:{port}/", delay_s, browser_open)
        )
    try:
        if stop is None:
            await server.serve()
        else:
            serving = asyncio.create_task(server.serve())
            waiting = asyncio.create_task(stop.wait())
            # Either the user quit or the server gave up on its own (a port already in
            # use ends serve() by itself); waiting only on the event would hang on that.
            await asyncio.wait({serving, waiting}, return_when=asyncio.FIRST_COMPLETED)
            waiting.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await waiting
            server.should_exit = True  # the shutdown uvicorn performs on Ctrl+C
            await serving
    finally:
        # uvicorn re-raises the SIGINT it swallowed the moment serve() returns, and
        # asyncio.run's own handler turns that into a cancel of this task -- which would
        # land on the first await below and skip the shutdown. The Ctrl+C is already
        # handled, so absorb exactly that one cancellation; a second Ctrl+C still gets
        # through, as a KeyboardInterrupt straight out of the handler.
        task = asyncio.current_task()
        if task is not None and task.cancelling():
            task.uncancel()
        if browsing is not None:
            browsing.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await browsing
        sup.request_shutdown()
        await supervising


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(sys.argv[1:] if argv is None else argv)
    if args.version:
        print(f"brawlfarm {__version__}")
        return 0
    home = (args.home or S.default_home()).resolve()
    os.environ["BRAWLFARM_HOME"] = str(home)  # the core reads it at import time
    try:
        home.mkdir(parents=True, exist_ok=True)
    except OSError as exc:  # a path that is a file, a read-only drive, a bad UNC share
        print(f"error: cannot use {home} as the data directory: {exc}", file=sys.stderr)
        return 2
    try:
        settings = S.load(home)
    except S.SettingsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not S.config_path(home).exists():
        S.save(settings, home)
        print(f"wrote default settings to {S.config_path(home)}")
    _setup_logging(home)
    from brawlfarm.supervisor import Supervisor  # after BRAWLFARM_HOME is set

    kwargs = {}
    if args.no_launch:
        kwargs["launcher"] = _dry_launcher
    sup = Supervisor(settings, home, interval_s=args.interval or 60.0, **kwargs)
    if args.once:
        _print_table(sup.tick())
        return 0

    from brawlfarm.api.app import create_app  # pulls in FastAPI; --once must not pay for it

    # Both modes serve the same three things, and neither of them can be built from the
    # flags alone, so the namespace carries them: _dispatch picks a mode without knowing
    # what either one has to set up.
    args.port = args.port or settings.app.port
    args.sup = sup
    args.app = create_app(sup, home)
    print(f"brawlfarm {__version__}: panel on http://127.0.0.1:{args.port}/ (loopback only)")
    print(f"supervising {len(settings.instances)} instance(s) from {home}")
    return _dispatch(args)


def _dispatch(args: argparse.Namespace) -> int:
    """Window mode when it was asked for and the extras are there, the browser otherwise."""
    if getattr(args, "window", False):
        from brawlfarm import desktop  # never imported unless --window was passed

        if desktop.available():
            return _run_window_mode(args)
        print(desktop.MISSING_MESSAGE, file=sys.stderr)
    return _run_browser_mode(args)


def _run_browser_mode(args: argparse.Namespace) -> int:
    """Serve on this thread and let uvicorn's own signal handling end the run."""
    print("Ctrl+C stops the panel; workers keep running and are reattached on the next start.")
    try:
        asyncio.run(_serve(args.sup, args.app, args.port, open_browser=not args.no_browser))
    except KeyboardInterrupt:  # Ctrl+C before uvicorn installed its own handlers
        args.sup.request_shutdown()
    except OSError as exc:
        print(f"error: cannot serve on 127.0.0.1:{args.port}: {exc}", file=sys.stderr)
        return 1
    except SystemExit:
        # uvicorn logs the bind failure and calls sys.exit(1) itself rather than raising.
        print(
            f"error: cannot serve on 127.0.0.1:{args.port}; is brawlfarm already running?",
            file=sys.stderr,
        )
        return 1
    return 0


def _run_window_mode(args: argparse.Namespace) -> int:
    """Serve on a second thread and give the main thread to the window and the tray icon,
    which both insist on owning it. Quit from the tray sets the stop event, which ends the
    server and the supervisor exactly as Ctrl+C does in browser mode."""
    from brawlfarm import desktop

    print("Quit from the tray icon stops the panel; workers keep running and are reattached")
    print("on the next start. Closing the window only hides it.")
    ready = threading.Event()
    holder: dict[str, object] = {}
    failure: list[BaseException] = []

    async def _serve_until_quit() -> None:
        holder["loop"] = asyncio.get_running_loop()
        holder["stop"] = stop = asyncio.Event()
        ready.set()
        await _serve(args.sup, args.app, args.port, open_browser=False, stop=stop)

    def _thread() -> None:
        try:
            asyncio.run(_serve_until_quit())
        except BaseException as exc:  # including the SystemExit uvicorn raises on a bad bind
            failure.append(exc)
        finally:
            ready.set()  # a failure before the loop started must not leave the wait hanging

    serving = threading.Thread(target=_thread, name="serve", daemon=True)
    serving.start()
    ready.wait(timeout=10)
    serving.join(timeout=1.0)  # uvicorn reports a port it cannot bind within moments
    if not serving.is_alive():
        exc = failure[0] if failure else None
        if exc is None or isinstance(exc, SystemExit):
            # uvicorn logs the bind failure and calls sys.exit(1) itself rather than raising.
            print(
                f"error: cannot serve on 127.0.0.1:{args.port}; is brawlfarm already running?",
                file=sys.stderr,
            )
        else:
            print(f"error: cannot serve on 127.0.0.1:{args.port}: {exc}", file=sys.stderr)
        return 1

    def quit_cb() -> None:
        loop, stop = holder.get("loop"), holder.get("stop")
        if loop is not None and stop is not None:
            loop.call_soon_threadsafe(stop.set)

    desktop.run(
        f"http://127.0.0.1:{args.port}/",
        running=lambda: sum(1 for v in args.sup.views() if v.pid),
        quit_cb=quit_cb,
    )
    quit_cb()  # a window closed by any other route still takes the server down with it
    serving.join(timeout=10)
    if serving.is_alive():
        log.warning("the panel did not stop within 10 seconds; exiting anyway")
    return 0


class _DryProc:
    pid = 0

    def poll(self):
        return None


def _dry_launcher(args, env, log_dir, name, module=None):
    logging.getLogger("brawlfarm.supervisor").info("%s: dry run, would launch %s", name, args)
    return _DryProc()


if __name__ == "__main__":
    raise SystemExit(main())
