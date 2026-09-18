"""The play package: importable without PyAV, ships the scrcpy server jar and its license,
and says whether the play extra is installed without importing it."""

from __future__ import annotations

import subprocess
import sys

from brawlfarm import play


def test_available_is_a_bool() -> None:
    assert isinstance(play.available(), bool)


def test_the_server_jar_ships_with_its_license() -> None:
    assert play.SERVER_JAR.is_file()
    assert play.SERVER_JAR.stat().st_size == play.SERVER_JAR_SIZE == 733706
    assert play.SERVER_VERSION == "4.1"
    license_text = (play.SERVER_JAR.parent / "LICENSE.scrcpy").read_text(encoding="utf-8")
    assert "Apache License" in license_text


def test_importing_the_package_does_not_import_pyav() -> None:
    code = "import sys, brawlfarm.play as p; p.available(); print('av' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False"
