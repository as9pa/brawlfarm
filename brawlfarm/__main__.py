"""Console entry point: `brawlfarm` runs the supervisor headless (the API and the browser
panel arrive in phase 3). `--once` runs one tick and prints the instance table, which is
the phase 2 live evidence."""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from brawlfarm import __version__
from brawlfarm import settings as S


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
        "--interval", type=float, default=None, help="seconds between ticks (default 60)"
    )
    ap.add_argument(
        "--no-launch", action="store_true", help="with --once: never start a worker (dry run)"
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


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(sys.argv[1:] if argv is None else argv)
    if args.version:
        print(f"brawlfarm {__version__}")
        return 0
    home = (args.home or S.default_home()).resolve()
    os.environ["BRAWLFARM_HOME"] = str(home)  # the core reads it at import time
    home.mkdir(parents=True, exist_ok=True)
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
    print(f"brawlfarm {__version__}: supervising {len(settings.instances)} instance(s) from {home}")
    print("Ctrl+C stops the supervisor; workers keep running and are reattached on the next start.")
    try:
        asyncio.run(sup.run_forever())
    except KeyboardInterrupt:
        sup.request_shutdown()
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
