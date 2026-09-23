"""The play package: importable without PyAV, ships the scrcpy server jar and its license,
and says whether the play extra is installed without importing it."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

from brawlfarm import play

REPO = Path(__file__).resolve().parents[1]
DATA = "brawlfarm/play/data/showdown_maps.json"


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


def test_the_map_data_ships_in_the_wheel() -> None:
    # hatchling's VCS-aware selection takes tracked, non-ignored files under packages=["brawlfarm"].
    assert (REPO / DATA).is_file()
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", DATA], cwd=REPO, capture_output=True
    )
    assert tracked.returncode == 0
    ignored = subprocess.run(["git", "check-ignore", "-q", DATA], cwd=REPO)
    assert ignored.returncode == 1


def test_the_maps_module_imports_only_the_standard_library() -> None:
    tree = ast.parse((REPO / "brawlfarm/play/maps.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module:
            assert node.module.split(".")[0] != "brawlfarm", node.module
    code = "import sys, brawlfarm.play.maps as m; m.load(); print(sorted(k for k in ('av', 'numpy', 'brawlfarm.play.detect', 'brawlfarm.core.adb') if k in sys.modules))"
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True, cwd=REPO
    )
    assert out.stdout.strip() == "[]"


def test_the_docs_carry_the_disclaimer_verbatim() -> None:
    from tools.play import maps as tool

    assert tool.DISCLAIMER in (REPO / "docs/play-maps.md").read_text(encoding="utf-8")
