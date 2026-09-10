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
    ap.add_argument("--port", type=int, default=None, help="panel port (default: app.port, 8765)")
    ap.add_argument(
        "--no-browser", action="store_true", help="serve the panel without opening a browser"
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
) -> None:
    """Serve the panel and supervise the fleet on one loop. uvicorn owns the signal
    handling: Ctrl+C ends serve(), and only then is the supervisor asked to stop. The final
    await lets a tick already running in its worker thread finish; the workers themselves
    are left alone on purpose."""
    server = make_server(app, port)
    supervising = asyncio.create_task(sup.run_forever())
    browsing = None
    if open_browser:
        browsing = asyncio.create_task(
            _open_later(f"http://127.0.0.1:{port}/", delay_s, browser_open)
        )
    try:
        await server.serve()
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

    port = args.port or settings.app.port
    app = create_app(sup, home)
    print(f"brawlfarm {__version__}: panel on http://127.0.0.1:{port}/ (loopback only)")
    print(f"supervising {len(settings.instances)} instance(s) from {home}")
    print("Ctrl+C stops the panel; workers keep running and are reattached on the next start.")
    try:
        asyncio.run(_serve(sup, app, port, open_browser=not args.no_browser))
    except KeyboardInterrupt:  # Ctrl+C before uvicorn installed its own handlers
        sup.request_shutdown()
    except OSError as exc:
        print(f"error: cannot serve on 127.0.0.1:{port}: {exc}", file=sys.stderr)
        return 1
    except SystemExit:
        # uvicorn logs the bind failure and calls sys.exit(1) itself rather than raising.
        print(
            f"error: cannot serve on 127.0.0.1:{port}; is brawlfarm already running?",
            file=sys.stderr,
        )
        return 1
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
