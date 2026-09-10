"""PID liveness, the worker command-line guard, kill by PID, and launching a worker
subprocess with the env it needs. Uses real short-lived subprocesses."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from brawlfarm.supervisor import process as P

SLEEPER = "import time; time.sleep(60)"


@pytest.fixture()
def sleeper():
    proc = subprocess.Popen([sys.executable, "-c", SLEEPER, P.WORKER_MODULE])
    yield proc
    if proc.poll() is None:
        proc.kill()
        proc.wait(5)


@pytest.fixture()
def bystander():
    proc = subprocess.Popen([sys.executable, "-c", SLEEPER])
    yield proc
    if proc.poll() is None:
        proc.kill()
        proc.wait(5)


def test_pid_alive(sleeper) -> None:
    assert P.pid_alive(sleeper.pid) is True
    sleeper.kill()
    sleeper.wait(5)
    assert P.pid_alive(sleeper.pid) is False
    assert P.pid_alive(0) is False
    assert P.pid_alive(-5) is False


def test_is_worker_guard(sleeper, bystander) -> None:
    assert P.is_worker(sleeper.pid) is True
    assert P.is_worker(bystander.pid) is False
    assert P.is_worker(os.getpid()) is False


def test_kill_worker_refuses_non_workers(sleeper, bystander) -> None:
    lines: list[str] = []
    assert P.kill_worker(bystander.pid, log=lines.append) is False
    assert bystander.poll() is None
    assert any("refus" in line for line in lines)
    assert P.kill_worker(sleeper.pid, log=lines.append) is True
    sleeper.wait(5)
    assert sleeper.poll() is not None
    assert P.kill_worker(sleeper.pid, log=lines.append) is False  # already gone


def test_launch_worker_passes_env_and_logs(tmp_path: Path) -> None:
    env = {**os.environ, "BRAWL_TEST_MARK": "hello"}
    log_dir = tmp_path / "logs"
    proc = P.launch_worker(
        [
            "-c",
            "import os,sys; print(os.environ['BRAWL_TEST_MARK']); print('err', file=sys.stderr)",
        ],
        env,
        log_dir,
        "Pie64",
        module=None,
    )
    proc.wait(30)
    assert proc.returncode == 0
    assert (log_dir / "Pie64.out.log").read_text(encoding="utf-8").strip() == "hello"
    assert (log_dir / "Pie64.err.log").read_text(encoding="utf-8").strip() == "err"


def test_launch_worker_default_module_is_the_worker(tmp_path: Path) -> None:
    env = {**os.environ, "BRAWLFARM_HOME": str(tmp_path)}
    proc = P.launch_worker(["--help"], env, tmp_path / "logs", "Pie64")
    proc.wait(60)
    assert proc.returncode == 0
    assert "--max-minutes" in (tmp_path / "logs" / "Pie64.out.log").read_text(encoding="utf-8")


def test_instance_online_parses_adb_output(tmp_path: Path) -> None:
    fake = tmp_path / "adb.py"
    fake.write_text(
        "import sys\n"
        "if sys.argv[1] == 'connect': print('connected to 127.0.0.1:5555')\n"
        "else: print('List of devices attached\\n127.0.0.1:5555\\tdevice\\n127.0.0.1:5565\\toffline\\n')\n",
        encoding="utf-8",
    )
    assert P.instance_online(str(fake), 5555, runner=P._python_runner) is True
    assert P.instance_online(str(fake), 5565, runner=P._python_runner) is False
    assert P.instance_online(str(fake), 5575, runner=P._python_runner) is False


def test_instance_online_fails_open_on_probe_errors(tmp_path: Path) -> None:
    assert P.instance_online(str(tmp_path / "missing-adb.exe"), 5555) is True
    slow = tmp_path / "slow.py"
    slow.write_text("import time; time.sleep(5)", encoding="utf-8")
    t0 = time.monotonic()
    assert P.instance_online(str(slow), 5555, timeout_s=0.5, runner=P._python_runner) is True
    assert time.monotonic() - t0 < 4
