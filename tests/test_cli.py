"""The brawlfarm command: writes a default config.toml on first run, prints the instance
table with --once, and reports settings errors plainly."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _run(args: list[str], home: Path) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("BRAWL_", "DISCORD_"))}
    env["BRAWLFARM_HOME"] = str(home)
    return subprocess.run(
        [sys.executable, "-m", "brawlfarm", *args], env=env, capture_output=True, text=True
    )


def test_version() -> None:
    r = _run(["--version"], Path.cwd())
    assert r.returncode == 0 and r.stdout.startswith("brawlfarm 0.")


def test_first_run_writes_defaults_and_once_prints_no_instances(tmp_path: Path) -> None:
    r = _run(["--once"], tmp_path)
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "config.toml").exists()
    assert "wrote default settings" in r.stdout
    assert "no instances configured" in r.stdout
    assert (tmp_path / "logs" / "supervisor.log").exists()


def test_once_prints_a_row_per_instance(tmp_path: Path) -> None:
    # The schedule is off so the tick always wants to run: with it on, whether this
    # instance is farming or on a break would depend on the wall clock.
    (tmp_path / "config.toml").write_text(
        '[connection]\nadb_path = "C:/definitely/missing/adb.exe"\n'
        "[scheduler]\ndefault_enabled = false\n"
        '[[instances]]\nname = "Pie64"\nadb_port = 5555\n',
        encoding="utf-8",
    )
    r = _run(["--once", "--no-launch"], tmp_path)
    assert r.returncode == 0, r.stderr
    assert "Pie64" in r.stdout and "5555" in r.stdout and "starting" in r.stdout


def test_settings_error_is_reported_plainly(tmp_path: Path) -> None:
    (tmp_path / "config.toml").write_text("[app]\nprot = 1\n", encoding="utf-8")
    r = _run(["--once"], tmp_path)
    assert r.returncode == 2
    assert "config.toml" in r.stderr and "prot" in r.stderr
