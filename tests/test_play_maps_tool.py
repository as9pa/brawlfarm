"""tools/play/maps.py: parsing, trio selection, build and fetch. No network."""

from __future__ import annotations

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
