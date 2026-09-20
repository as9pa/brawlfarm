"""The four adb helpers the play stream needs: push a file, add and remove a port forward,
and start a long-running shell process. Every call is checked as an argument list; nothing
reaches a real adb."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from brawlfarm.core import adb, config


@pytest.fixture()
def calls(monkeypatch) -> list[list[str]]:
    seen: list[list[str]] = []

    def fake_run(args, **kwargs):
        seen.append(list(args))
        return ""

    monkeypatch.setattr(adb, "_run", fake_run)
    monkeypatch.setattr(config, "ADB_SERIAL", "127.0.0.1:5555")
    return seen


def test_push_sends_the_file_to_the_device_path(calls, tmp_path: Path) -> None:
    jar = tmp_path / "scrcpy-server"
    jar.write_bytes(b"x")
    adb.push(jar, "/data/local/tmp/scrcpy-server.jar")
    assert calls == [
        ["-s", "127.0.0.1:5555", "push", str(jar), "/data/local/tmp/scrcpy-server.jar"]
    ]


def test_forward_and_remove_name_the_tcp_port(calls) -> None:
    adb.forward(27183, "localabstract:scrcpy")
    adb.forward_remove(27183)
    assert calls == [
        ["-s", "127.0.0.1:5555", "forward", "tcp:27183", "localabstract:scrcpy"],
        ["-s", "127.0.0.1:5555", "forward", "--remove", "tcp:27183"],
    ]


def test_shell_process_starts_adb_shell_with_the_arguments(monkeypatch) -> None:
    seen = {}

    class FakePopen:
        def __init__(self, cmd, **kwargs):
            seen["cmd"] = cmd
            seen["kwargs"] = kwargs

    monkeypatch.setattr(config, "ADB_PATH", "C:/fake/adb.exe")
    monkeypatch.setattr(config, "ADB_SERIAL", "127.0.0.1:5555")
    monkeypatch.setattr(adb.subprocess, "Popen", FakePopen)
    proc = adb.shell_process(["app_process", "/", "com.example.Server", "4.1"])
    assert isinstance(proc, FakePopen)
    assert seen["cmd"] == [
        "C:/fake/adb.exe",
        "-s",
        "127.0.0.1:5555",
        "shell",
        "app_process",
        "/",
        "com.example.Server",
        "4.1",
    ]
    assert seen["kwargs"]["stdin"] is subprocess.DEVNULL
    assert seen["kwargs"]["stdout"] is subprocess.PIPE
