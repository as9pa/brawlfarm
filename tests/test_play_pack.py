"""The label pack: one folder, and a zip of it, that a labeller can use on a computer without
the repository."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import numpy as np

from tools.play import dataset, pack, prelabel

DOC = Path(__file__).resolve().parents[1] / "docs" / "play-training.md"


def _root(tmp_path: Path) -> Path:
    """Two sources with two frames each, and a tasks.json that references three of the four."""
    root = tmp_path / "play"
    frame = np.zeros((90, 160, 3), dtype=np.uint8)
    for source, n in (("alpha", 1), ("alpha", 2), ("beta", 1), ("beta", 2)):
        dataset.save_frame(root, source, n, frame)
    tasks = [
        prelabel.task_for("frames/alpha/alpha-000001.jpg", []),
        prelabel.task_for("frames/alpha/alpha-000002.jpg", []),
        prelabel.task_for("frames/beta/beta-000001.jpg", []),
    ]
    out = root / "labelstudio"
    out.mkdir(parents=True)
    (out / "tasks.json").write_text(json.dumps(tasks), encoding="utf-8")
    return root


def _frames(folder: Path) -> list[str]:
    return sorted(p.relative_to(folder).as_posix() for p in (folder / "frames").rglob("*.jpg"))


def test_pack_copies_only_the_frames_the_tasks_reference(tmp_path, capsys):
    root = _root(tmp_path)

    code = pack.main(["--root", str(root)])

    assert code == 0
    folder = root / "label-pack"
    assert _frames(folder) == [
        "frames/alpha/alpha-000001.jpg",
        "frames/alpha/alpha-000002.jpg",
        "frames/beta/beta-000001.jpg",
    ]
    tasks = json.loads((folder / "labelstudio" / "tasks.json").read_text(encoding="utf-8"))
    assert [task["data"]["file"] for task in tasks] == [
        "frames/alpha/alpha-000001.jpg",
        "frames/alpha/alpha-000002.jpg",
        "frames/beta/beta-000001.jpg",
    ]
    assert (folder / "labelstudio" / "config.xml").read_text(encoding="utf-8") == (
        prelabel.CONFIG_XML.read_text(encoding="utf-8")
    )
    out = capsys.readouterr().out
    assert "3 frames" in out
    assert "alpha, beta" in out


def test_source_filters_both_the_frames_and_the_tasks(tmp_path):
    root = _root(tmp_path)

    assert pack.main(["--root", str(root), "--source", "beta"]) == 0

    folder = root / "label-pack"
    assert _frames(folder) == ["frames/beta/beta-000001.jpg"]
    tasks = json.loads((folder / "labelstudio" / "tasks.json").read_text(encoding="utf-8"))
    assert [task["data"]["file"] for task in tasks] == ["frames/beta/beta-000001.jpg"]


def test_start_scripts_and_readme_name_the_local_files_variables(tmp_path):
    root = _root(tmp_path)

    assert pack.main(["--root", str(root), "--no-zip"]) == 0

    folder = root / "label-pack"
    for name in ("start.sh", "start.ps1", "README.md"):
        text = (folder / name).read_text(encoding="utf-8")
        assert "LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED" in text, name
        assert "LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT" in text, name
    start = (folder / "start.sh").read_bytes()
    assert b"\r" not in start
    assert start.startswith(b"#!/usr/bin/env bash\n")
    assert b"set -euo pipefail" in start
    readme = (folder / "README.md").read_text(encoding="utf-8")
    assert "—" not in readme


def test_readme_class_meanings_and_rules_match_the_training_doc():
    doc = DOC.read_text(encoding="utf-8")

    assert pack.CLASS_NOTES in doc
    assert "- `gas`:" in pack.CLASS_NOTES


def test_zip_marks_start_sh_executable(tmp_path, capsys):
    root = _root(tmp_path)

    assert pack.main(["--root", str(root)]) == 0

    archive = root / "label-pack.zip"
    with zipfile.ZipFile(archive) as zf:
        infos = {info.filename: info for info in zf.infolist()}
    start = infos["label-pack/start.sh"]
    assert (start.external_attr >> 16) & 0o111 == 0o111
    assert infos["label-pack/frames/alpha/alpha-000001.jpg"].compress_type == zipfile.ZIP_STORED
    assert infos["label-pack/README.md"].compress_type == zipfile.ZIP_DEFLATED
    assert "label-pack/frames/beta/beta-000002.jpg" not in infos
    assert str(archive) in capsys.readouterr().out


def test_no_zip_writes_no_zip(tmp_path):
    root = _root(tmp_path)

    assert pack.main(["--root", str(root), "--no-zip"]) == 0

    assert (root / "label-pack" / "start.sh").exists()
    assert not (root / "label-pack.zip").exists()


def test_a_rerun_replaces_the_pack_rather_than_adding_to_it(tmp_path):
    root = _root(tmp_path)
    assert pack.main(["--root", str(root), "--no-zip"]) == 0

    assert pack.main(["--root", str(root), "--no-zip", "--source", "alpha"]) == 0

    assert _frames(root / "label-pack") == [
        "frames/alpha/alpha-000001.jpg",
        "frames/alpha/alpha-000002.jpg",
    ]


def test_refuses_an_out_folder_that_is_not_a_pack(tmp_path):
    root = _root(tmp_path)
    other = tmp_path / "keep"
    other.mkdir()
    (other / "notes.txt").write_text("mine", encoding="utf-8")

    assert pack.main(["--root", str(root), "--out", str(other)]) == 1

    assert (other / "notes.txt").read_text(encoding="utf-8") == "mine"


def test_a_missing_frame_drops_its_task(tmp_path, capsys):
    root = _root(tmp_path)
    (root / "frames" / "alpha" / "alpha-000002.jpg").unlink()

    assert pack.main(["--root", str(root), "--no-zip"]) == 0

    tasks = json.loads(
        (root / "label-pack" / "labelstudio" / "tasks.json").read_text(encoding="utf-8")
    )
    assert [task["data"]["file"] for task in tasks] == [
        "frames/alpha/alpha-000001.jpg",
        "frames/beta/beta-000001.jpg",
    ]
    assert "1 missing" in capsys.readouterr().out


def test_no_tasks_file_is_an_error(tmp_path, capsys):
    root = tmp_path / "play"
    root.mkdir()

    assert pack.main(["--root", str(root)]) == 1
    assert "prelabel.py" in capsys.readouterr().out
