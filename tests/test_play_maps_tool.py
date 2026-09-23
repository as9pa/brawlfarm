"""tools/play/maps.py: parsing, trio selection, build and fetch. No network."""

from __future__ import annotations

import hashlib
import io
import json
import urllib.error
from pathlib import Path

import pytest

from tools.play import maps as tool

FIX = Path(__file__).parent / "fixtures" / "maps"


def _load(rel: str) -> list[list[str]]:
    return tool.read_rows(FIX / rel)


def test_parse_maps_joins_a_name_row_with_its_continuation_rows() -> None:
    grids = tool.parse_maps(_load("csv_logic/maps.csv"))
    assert list(grids) == ["Survival_7", "Survival_1", "Survival_604"]
    assert grids["Survival_7"] == ["FF.M.", "F..MW", "..1.2", "3.4.P"]


def test_parse_tiles_reads_the_flags() -> None:
    tiles = tool.parse_tiles(_load("csv_logic/tiles.csv"))
    assert tiles["F"] == {
        "name": "Forest",
        "blocks_movement": False,
        "blocks_projectiles": False,
        "destructible": False,
        "forest": True,
    }
    assert tiles["M"]["blocks_movement"] and tiles["M"]["blocks_projectiles"]
    assert tiles["W"]["blocks_movement"] and not tiles["W"]["blocks_projectiles"]


def _selected() -> list[dict]:
    return tool.select_trio(
        tool.records(_load("csv_logic/locations.csv")),
        tool.records(_load("localization/texts.csv")),
        tool.parse_maps(_load("csv_logic/maps.csv")),
    )


def test_disabled_and_other_modes_are_dropped() -> None:
    assert sorted(s["location"] for s in _selected()) == [
        "SurvivalTrio1",
        "SurvivalTrio604",
        "SurvivalTrio7",
    ]


def test_preferred_variant_comes_first() -> None:
    doc = tool.build_document(tool.parse_tiles(_load("csv_logic/tiles.csv")), _selected())
    assert doc["names"] == {
        "Test Flats": ["Survival_7"],
        "Twin Peaks": ["Survival_604", "Survival_1"],
    }
    assert [m["map_id"] for m in doc["maps"]] == ["Survival_7", "Survival_1", "Survival_604"]


def test_unknown_codes_are_listed_not_fatal() -> None:
    doc = tool.build_document(tool.parse_tiles(_load("csv_logic/tiles.csv")), _selected())
    by_id = {m["map_id"]: m for m in doc["maps"]}
    assert by_id["Survival_7"]["unknown_codes"] == ["P"]
    assert by_id["Survival_1"]["unknown_codes"] == []


def test_a_ragged_grid_is_a_build_error() -> None:
    maps = {"Survival_7": ["FF.M.", "F..M"]}
    locs = [
        {
            "Name": "L",
            "Disabled": "",
            "GameModeVariation": "TrioShowdown",
            "Map": "Survival_7",
            "TID": "T",
            "LocationTheme": "X",
        }
    ]
    with pytest.raises(tool.BuildError, match="ragged"):
        tool.select_trio(locs, [{"TID": "T", "EN": "Name"}], maps)


def test_missing_map_or_text_is_a_build_error() -> None:
    locs = [
        {
            "Name": "L",
            "Disabled": "",
            "GameModeVariation": "TrioShowdown",
            "Map": "Nope",
            "TID": "T",
            "LocationTheme": "X",
        }
    ]
    with pytest.raises(tool.BuildError, match="Nope"):
        tool.select_trio(locs, [{"TID": "T", "EN": "Name"}], {})
    locs[0]["Map"] = "M"
    with pytest.raises(tool.BuildError, match="T"):
        tool.select_trio(locs, [], {"M": ["."]})


def test_build_twice_gives_identical_bytes(tmp_path: Path) -> None:
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    assert tool.main(["build", "--src", str(FIX), "--out", str(a)]) == 0
    assert tool.main(["build", "--src", str(FIX), "--out", str(b)]) == 0
    assert a.read_bytes() == b.read_bytes()
    assert a.read_bytes().endswith(b"}\n") and b"\r\n" not in a.read_bytes()
    assert json.loads(a.read_text(encoding="utf-8"))["disclaimer"] == tool.DISCLAIMER


def test_build_prints_a_summary(tmp_path: Path, capsys) -> None:
    tool.main(["build", "--src", str(FIX), "--out", str(tmp_path / "o.json")])
    out = capsys.readouterr().out
    assert "maps: 3" in out and "names: 2" in out and "Twin Peaks" in out and "Survival_7: P" in out


def _copy_fixture(tmp_path: Path) -> Path:
    import shutil

    src = tmp_path / "src"
    shutil.copytree(FIX, src)
    return src


def test_build_exits_1_on_a_ragged_grid(tmp_path: Path, capsys) -> None:
    src = _copy_fixture(tmp_path)
    p = src / "csv_logic" / "maps.csv"
    p.write_text(
        p.read_text(encoding="utf-8").replace('"","F..MW",""', '"","F..M",""'), encoding="utf-8"
    )
    assert tool.main(["build", "--src", str(src), "--out", str(tmp_path / "o.json")]) == 1
    assert "ragged" in capsys.readouterr().err
    assert not (tmp_path / "o.json").exists()


def test_build_exits_1_when_source_json_disagrees(tmp_path: Path, capsys) -> None:
    src = _copy_fixture(tmp_path)
    (src / "SOURCE.json").write_text(
        '{"commit": "abc1234", "files": {}, "version": "69.230"}', encoding="utf-8"
    )
    assert tool.main(["build", "--src", str(src), "--out", str(tmp_path / "o.json")]) == 1
    assert "SOURCE.json" in capsys.readouterr().err


class LocalOpener:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, url: str, timeout: float | None = None):
        self.calls.append(url)
        rel = url.split(f"/{tool.PINNED_VERSION}/", 1)[1]
        return io.BytesIO((FIX / rel).read_bytes())


def test_fetch_writes_source_json_and_a_second_run_does_nothing(tmp_path: Path) -> None:
    opener = LocalOpener()
    assert tool.fetch(tmp_path, opener=opener) is True
    assert len(opener.calls) == 4
    assert opener.calls[0] == tool.RAW_BASE + "csv_logic/maps.csv"
    meta = json.loads((tmp_path / "SOURCE.json").read_text(encoding="utf-8"))
    assert meta["commit"] == "cc307ff" and meta["version"] == "69.230"
    for rel in tool.FILES:
        assert meta["files"][rel] == hashlib.sha256((FIX / rel).read_bytes()).hexdigest()
    assert not list(tmp_path.rglob("*.part"))
    assert tool.fetch(tmp_path, opener=opener) is False
    assert len(opener.calls) == 4
    assert tool.fetch(tmp_path, force=True, opener=opener) is True
    assert len(opener.calls) == 8


def test_fetch_refetches_a_changed_file(tmp_path: Path) -> None:
    opener = LocalOpener()
    tool.fetch(tmp_path, opener=opener)
    (tmp_path / "csv_logic" / "tiles.csv").write_text("tampered", encoding="utf-8")
    assert tool.fetch(tmp_path, opener=opener) is True


def test_a_network_error_exits_2_with_the_url(tmp_path: Path, capsys, monkeypatch) -> None:
    def offline(url, timeout=None):
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(tool, "_OPENER", offline)
    assert tool.main(["fetch", "--home", str(tmp_path)]) == 2
    assert tool.RAW_BASE in capsys.readouterr().err
    assert not list(tmp_path.rglob("*.part")) and not list(tmp_path.rglob("*.csv"))
