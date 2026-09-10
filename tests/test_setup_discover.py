"""Finding adb and the BlueStacks instances: the bluestacks.conf parser, the adb devices
parser, and the two probes the wizard runs. The fixture conf text is invented -- no real
instance names, display names or ports from anyone's machine."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from brawlfarm.setup import discover

CONF_TEXT = """[general]
bst.feature.rooting="0"
bst.instance.Pie64.adb_port="5555"
bst.instance.Pie64.display_name="BlueStacks App Player 1"
bst.instance.Pie64.fb_width="1600"
bst.instance.Pie64.fb_height="900"
bst.instance.Pie64.dpi="240"
bst.instance.Pie64_1.adb_port="5565"
bst.instance.Pie64_1.display_name="BlueStacks App Player 2"
bst.instance.Pie64_1.fb_width="1280"
bst.instance.Pie64_1.fb_height="720"
bst.instance.Pie64_1.dpi="240"
bst.instance.Nougat32.adb_port="5575"
"""

DEVICES_TEXT = "List of devices attached\n127.0.0.1:5555\tdevice\n127.0.0.1:5575\toffline\n\n"


def _done(
    argv: list[str], rc: int = 0, out: bytes = b"", err: bytes = b""
) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(argv, rc, out, err)


class RecordingRunner:
    """A checks.Runner: answers by the first key found in the joined argv, records calls."""

    def __init__(self, answers: dict[str, subprocess.CompletedProcess]) -> None:
        self.answers = answers
        self.calls: list[list[str]] = []

    def __call__(self, argv: list[str], timeout_s: float) -> subprocess.CompletedProcess:
        self.calls.append(list(argv))
        joined = " ".join(argv)
        for key, done in self.answers.items():
            if key in joined:
                return done
        return _done(argv, rc=1, err=b"unexpected argv")


def test_parse_bluestacks_conf_reads_every_instance_block() -> None:
    found = discover.parse_bluestacks_conf(CONF_TEXT)
    assert [d.name for d in found] == ["Nougat32", "Pie64", "Pie64_1"]
    pie = found[1]
    assert pie.display_name == "BlueStacks App Player 1"
    assert (pie.adb_port, pie.width, pie.height, pie.dpi) == (5555, 1600, 900, 240)
    bare = found[0]
    assert bare.display_name == "Nougat32"  # no display_name key: fall back to the name
    assert (bare.width, bare.height, bare.dpi) == (None, None, None)


def test_parse_bluestacks_conf_skips_names_that_could_not_be_folders() -> None:
    too_long = "A" * 40
    text = CONF_TEXT + f'bst.instance.{too_long}.adb_port="5585"\n'
    assert [d.name for d in discover.parse_bluestacks_conf(text)] == [
        "Nougat32",
        "Pie64",
        "Pie64_1",
    ]
    assert discover.parse_bluestacks_conf("") == []


def test_parse_devices_reads_only_the_ports_that_say_device() -> None:
    assert discover.parse_devices(DEVICES_TEXT) == {5555}
    assert discover.parse_devices("") == set()


def test_find_adb_prefers_the_configured_path_then_bluestacks_then_the_path(
    tmp_path: Path, monkeypatch
) -> None:
    configured = tmp_path / "HD-Adb.exe"
    configured.write_text("", encoding="utf-8")
    bundled = tmp_path / "bundled-adb.exe"
    monkeypatch.setattr(discover, "DEFAULT_ADB", str(bundled))
    assert discover.find_adb(str(configured)) == str(configured)
    bundled.write_text("", encoding="utf-8")
    assert discover.find_adb(str(tmp_path / "gone.exe")) == str(bundled)
    bundled.unlink()
    monkeypatch.setattr(shutil, "which", lambda _name: "C:/tools/adb.exe")
    assert discover.find_adb(None) == "C:/tools/adb.exe"
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    assert discover.find_adb(None) is None


def test_scan_marks_the_instances_adb_can_see(tmp_path: Path) -> None:
    conf = tmp_path / "bluestacks.conf"
    conf.write_text(CONF_TEXT, encoding="utf-8")
    runner = RecordingRunner({"devices": _done(["adb", "devices"], out=DEVICES_TEXT.encode())})
    out = discover.scan("C:/tools/adb.exe", conf, runner=runner)
    assert out["adb_path"] == "C:/tools/adb.exe"
    assert out["adb_found"] is True and out["conf_found"] is True
    by_name = {i["name"]: i for i in out["instances"]}
    assert by_name["Pie64"] == {
        "name": "Pie64",
        "display_name": "BlueStacks App Player 1",
        "adb_port": 5555,
        "width": 1600,
        "height": 900,
        "dpi": 240,
        "online": True,
    }
    assert by_name["Pie64_1"]["online"] is False  # not in adb devices
    assert by_name["Nougat32"]["online"] is False  # listed, but "offline"


def test_scan_without_adb_or_without_the_conf_still_answers(tmp_path: Path) -> None:
    conf = tmp_path / "bluestacks.conf"
    conf.write_text(CONF_TEXT, encoding="utf-8")
    out = discover.scan(None, conf)
    assert out["adb_found"] is False and out["adb_path"] is None
    assert all(i["online"] is False for i in out["instances"])
    missing = discover.scan(None, tmp_path / "nope.conf")
    assert missing["conf_found"] is False and missing["instances"] == []


def test_test_port_reports_a_device_that_answers() -> None:
    runner = RecordingRunner(
        {
            "connect": _done(["adb", "connect"], out=b"connected to 127.0.0.1:5555\n"),
            "get-state": _done(["adb", "get-state"], out=b"device\n"),
        }
    )
    assert discover.probe_port("C:/tools/adb.exe", 5555, runner=runner) == {
        "ok": True,
        "detail": "127.0.0.1:5555 answered",
    }
    assert runner.calls[1] == ["C:/tools/adb.exe", "-s", "127.0.0.1:5555", "get-state"]


def test_test_port_fails_closed_when_the_port_does_not_answer() -> None:
    runner = RecordingRunner(
        {
            "connect": _done(["adb", "connect"], rc=1, err=b"cannot connect to 127.0.0.1:5599\n"),
            "get-state": _done(["adb", "get-state"], rc=1, err=b"error: device offline\n"),
        }
    )
    out = discover.probe_port("C:/tools/adb.exe", 5599, runner=runner)
    assert out["ok"] is False
    assert out["detail"] == "127.0.0.1:5599: error: device offline"


def test_test_port_reports_a_timeout_instead_of_raising() -> None:
    def slow(argv: list[str], timeout_s: float) -> subprocess.CompletedProcess:
        raise subprocess.TimeoutExpired(argv, timeout_s)

    assert discover.probe_port("C:/tools/adb.exe", 5555, runner=slow) == {
        "ok": False,
        "detail": "adb timed out talking to 127.0.0.1:5555",
    }
