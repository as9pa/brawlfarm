"""brawlfarm/play/maps.py against the fixture JSON and the packaged JSON."""

from __future__ import annotations

from pathlib import Path

import pytest

from brawlfarm.play import maps
from tools.play import maps as tool

FIX = Path(__file__).parent / "fixtures" / "maps"


@pytest.fixture(scope="module")
def index(tmp_path_factory) -> maps.MapIndex:
    out = tmp_path_factory.mktemp("maps") / "m.json"
    assert tool.main(["build", "--src", str(FIX), "--out", str(out)]) == 0
    return maps.load(out)


def test_packaged_json() -> None:
    idx = maps.load()
    assert len(idx.names()) == 26
    assert idx.commit == "cc307ff" and idx.version == "69.230"
    for name in idx.names():
        for m in idx.variants(name):
            assert (m.rows, m.cols) == (60, 60) and all(len(line) == 60 for line in m.grid)
    assert idx.by_name("Rockwall Brawl").map_id == "Survival_605"
    assert [m.map_id for m in idx.variants("Rockwall Brawl")] == ["Survival_605", "Survival_3"]


def test_lookup(index) -> None:
    assert index.names() == ["Test Flats", "Twin Peaks"]
    assert index.by_name("  twin   PEAKS ").map_id == "Survival_604"
    assert index.by_name("Nowhere") is None and index.variants("Nowhere") == []
    assert index.by_id("Survival_1").theme == "OldTheme" and index.by_id("x") is None


def test_tile_classifiers(index) -> None:
    m = index.by_id("Survival_7")
    assert m.tile(0, 3) == "M" and m.is_wall(0, 3) and not m.is_water(0, 3)
    assert m.is_water(1, 4) and not m.is_wall(1, 4)
    assert m.is_bush(0, 0) and not m.is_open(0, 0)
    assert m.is_open(3, 4)  # unknown code P counts as open
    assert m.is_open(2, 2)  # a spawn marker counts as open
    with pytest.raises(IndexError):
        m.tile(4, 0)
    with pytest.raises(IndexError):
        m.tile(0, -1)
    assert m.bushes() == frozenset({(0, 0), (0, 1), (1, 0)})
    assert m.walls() == frozenset({(0, 3), (1, 3)}) and m.water() == frozenset({(1, 4)})
    assert len(m.open_tiles()) == 20 - 3 - 2 - 1


def test_clusters_center_spawns(index) -> None:
    m = index.by_id("Survival_604")
    assert m.bush_clusters() == (
        frozenset({(0, 0)}),
        frozenset({(0, 4)}),
        frozenset({(3, 0)}),
        frozenset({(3, 4)}),
    )
    assert index.by_id("Survival_7").bush_clusters() == (frozenset({(0, 0), (0, 1), (1, 0)}),)
    assert m.center() == (2.0, 2.5)
    s7 = index.by_id("Survival_7")
    assert (
        s7.spawns() == ((3, 0),)
        and s7.spawns("solo_spawn") == ((2, 2),)
        and s7.boxes() == ((3, 2),)
    )


def test_broken_json_raises(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("{nope", encoding="utf-8")
    with pytest.raises(maps.MapsDataError):
        maps.load(bad)
    bad.write_text('{"schema": 2}', encoding="utf-8")
    with pytest.raises(maps.MapsDataError):
        maps.load(bad)
    with pytest.raises(maps.MapsDataError):
        maps.load(tmp_path / "missing.json")


def test_match_name_with_ocr_noise(index) -> None:
    assert maps.match_name("TWIN PEAKS", index) == "Twin Peaks"
    assert maps.match_name("Twln Peaks.", index) == "Twin Peaks"
    assert maps.match_name("Tw1n Pe", index) is None
    assert maps.match_name("", index) is None


def test_current_map_name_by_ocr(index) -> None:
    lines = ["TRIO SHOWDOWN", "Twin Peaks", "New map in: 1h 27m"]
    assert maps.current_map_name(lines, index=index) == "Twin Peaks"
    assert maps.current_map_name(["TRI0 SHOWDOWN", "Test Flat5"], index=index) == "Test Flats"


def test_current_map_name_rotation_fallback(index) -> None:
    rot = [
        {"event": {"mode": "trioShowdown", "map": "Test Flats"}},
        {"event": {"mode": "gemGrab", "map": "Hard Rock Mine"}},
    ]
    assert maps.current_map_name(["SOLO SHOWDOWN"], rot, index) == "Test Flats"
    assert maps.current_map_name(None, rot, index) == "Test Flats"
    assert maps.current_map_name(["TRIO SHOWDOWN", "??"], rot, index) == "Test Flats"


def test_current_map_name_none(index) -> None:
    two = [
        {"event": {"mode": "trioShowdown", "map": "Test Flats"}},
        {"event": {"mode": "trioShowdown", "map": "Twin Peaks"}},
    ]
    assert maps.current_map_name(None, two, index) is None
    assert maps.current_map_name([], None, index) is None
    assert maps.current_map_name(None, [{"event": None}], index) is None


def test_parse_refresh() -> None:
    assert maps.parse_refresh("New map in: 1h 27m") == 5220
    assert maps.parse_refresh("27m") == 1620
    assert maps.parse_refresh("45s") == 45
    assert maps.parse_refresh("1d 2h") == 93600
    assert maps.parse_refresh("New map in:") is None
