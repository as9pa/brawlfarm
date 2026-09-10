"""Process plumbing for the supervisor: PID liveness, the worker command-line guard,
kill by PID, launching a worker with its env, and the adb online probe.

Safety rail: a worker is only ever killed by the PID read from its own status.json,
never found by name. kill_worker() additionally refuses a PID whose command line does
not run brawlfarm.worker, so a reused PID can never be killed by mistake.
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import psutil

WORKER_MODULE = "brawlfarm.worker"
_DEVICE_LINE = re.compile(r"^127\.0\.0\.1:(\d+)\s+device\s*$")

Runner = Callable[[list[str], float], str]


def pid_alive(pid: int) -> bool:
    if pid is None or pid <= 0:
        return False
    try:
        p = psutil.Process(pid)
        return p.is_running() and p.status() != psutil.STATUS_ZOMBIE
    except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError):
        return False


def is_worker(pid: int) -> bool:
    """True when the PID's command line runs brawlfarm.worker (``-m brawlfarm.worker`` or
    the module path). AccessDenied counts as "not ours"."""
    try:
        argv = psutil.Process(pid).cmdline()
    except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError):
        return False
    tail = WORKER_MODULE.replace(".", "/") + ".py"
    return any(a == WORKER_MODULE or a.replace("\\", "/").endswith(tail) for a in argv)


def kill_worker(pid: int, log: Callable[[str], None] = print) -> bool:
    """Kill by PID. Returns False (and logs why) when the PID is gone or is not a worker."""
    if not pid_alive(pid):
        log(f"kill {pid}: not running")
        return False
    if not is_worker(pid):
        log(f"kill {pid}: refused, command line is not {WORKER_MODULE}")
        return False
    try:
        p = psutil.Process(pid)
        p.kill()
        p.wait(timeout=10)
    except psutil.NoSuchProcess:
        pass
    except psutil.Error as exc:
        log(f"kill {pid}: failed: {exc}")
        return False
    return True


def launch_worker(
    args: list[str],
    env: dict[str, str],
    log_dir: Path,
    name: str,
    module: str | None = WORKER_MODULE,
) -> subprocess.Popen:
    """Start ``python -m brawlfarm.worker <args>`` with ``env``, hidden, stdout and stderr
    appended to <log_dir>/<name>.out.log and .err.log. ``module=None`` runs python with
    ``args`` directly (tests)."""
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable]
    if module:
        cmd += ["-m", module]
    cmd += list(args)
    out = open(log_dir / f"{name}.out.log", "ab")  # handed to the child, closed below
    err = open(log_dir / f"{name}.err.log", "ab")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        return subprocess.Popen(cmd, env=env, stdout=out, stderr=err, creationflags=flags)
    finally:
        out.close()
        err.close()


def _default_runner(cmd: list[str], timeout_s: float) -> str:
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout_s, check=False
    ).stdout


def _python_runner(cmd: list[str], timeout_s: float) -> str:
    """Test hook: run a .py stand-in for HD-Adb.exe through the interpreter."""
    return _default_runner([sys.executable, *cmd], timeout_s)


def instance_online(
    adb_path: str, port: int, timeout_s: float = 15.0, runner: Runner = _default_runner
) -> bool:
    """adb connect, then adb devices; online only when the row for this port says
    ``device``. Fails OPEN (True) on a missing adb, a timeout or any other probe error,
    so a broken probe never strands an instance in backoff."""
    serial = f"127.0.0.1:{int(port)}"
    if not Path(adb_path).exists():
        return True
    try:
        runner([adb_path, "connect", serial], timeout_s)
        out = runner([adb_path, "devices"], timeout_s)
    except (subprocess.TimeoutExpired, OSError, subprocess.SubprocessError):
        return True
    if not out.strip():
        return True
    for line in out.splitlines():
        m = _DEVICE_LINE.match(line.strip())
        if m and int(m.group(1)) == int(port):
            return True
    return False
