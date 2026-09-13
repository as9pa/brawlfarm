"""api/sessions.py: the newest finished session in an instance folder.

The session log narrates and games.csv carries the numbers, so the block is a join of the
two over the session's own window. Every read is guarded: a broken session file must never
break a Fleet card.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from brawlfarm.api import sessions

GAMES_HEADER = "battleTime,logged_at,event_mode,battle_mode,type,rank,trophyChange,result,duration_s,map,brawler,is_showdown\n"


def write_session(inst_dir: Path, stamp: str, lines: list[dict]) -> Path:
    inst_dir.mkdir(parents=True, exist_ok=True)
    path = inst_dir / f"session-{stamp}.jsonl"
    path.write_text("".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")
    return path


def write_games(inst_dir: Path, rows: list[str]) -> Path:
    inst_dir.mkdir(parents=True, exist_ok=True)
    path = inst_dir / "games.csv"
    path.write_text(GAMES_HEADER + "".join(row + "\n" for row in rows), encoding="utf-8")
    return path


def game(logged_at: str, rank: str, change: str, brawler: str = "NORI") -> str:
    """One games.csv row in GAME_FIELDS order, with only the four cells this module reads
    carrying anything worth reading."""
    return f"20260912T210000.000Z,{logged_at},soloShowdown,soloShowdown,ranked,{rank},{change},victory,150,Feast or Famine,{brawler},True"


def test_a_folder_with_no_session_file_is_none(tmp_path: Path) -> None:
    (tmp_path / "Pie64").mkdir()
    assert sessions.last_session(tmp_path / "Pie64") is None


def test_a_missing_folder_is_none(tmp_path: Path) -> None:
    assert sessions.last_session(tmp_path / "never-ran") is None


def test_one_finished_session_gives_the_seven_fields(tmp_path: Path) -> None:
    inst = tmp_path / "Pie64"
    write_session(
        inst,
        "20260912-210000",
        [
            {"ts": "2026-09-12T21:00:05", "kind": "farming", "brawler": "NORI"},
            {"ts": "2026-09-12T21:31:00", "kind": "disconnect"},
            {"ts": "2026-09-12T21:40:00", "kind": "popup_close"},
            {"ts": "2026-09-12T22:14:07", "kind": "recap"},
        ],
    )
    write_games(
        inst,
        [
            game("2026-09-12T20:59:00", "3", "8"),  # before the session started
            game("2026-09-12T21:10:00", "2", "12"),
            game("2026-09-12T21:50:00", "5", "-4"),
            game("2026-09-12T22:20:00", "1", "20"),  # after the session ended
        ],
    )
    assert sessions.last_session(inst) == {
        "games": 2,
        "trophies": 8,
        "avg_rank": 3.5,
        "disconnects": 1,
        "duration_s": 4447,
        "interrupts": 2,
        "ended_at": "2026-09-12T22:14:07",
    }


def test_a_session_with_no_ranked_game_has_a_null_avg_rank(tmp_path: Path) -> None:
    inst = tmp_path / "Pie64"
    write_session(inst, "20260912-210000", [{"ts": "2026-09-12T21:30:00", "kind": "recap"}])
    write_games(inst, [game("2026-09-12T21:10:00", "", "12")])
    block = sessions.last_session(inst)
    assert block is not None
    assert block["avg_rank"] is None
    assert block["games"] == 1
    assert block["trophies"] == 12


def test_a_broken_json_line_still_counts_the_rest(tmp_path: Path) -> None:
    inst = tmp_path / "Pie64"
    inst.mkdir(parents=True)
    (inst / "session-20260912-210000.jsonl").write_text(
        '{"ts": "2026-09-12T21:05:00", "kind": "disconnect"}\n'
        "{not json at all\n"
        "\n"
        '{"ts": "2026-09-12T21:30:00", "kind": "popup_close"}\n',
        encoding="utf-8",
    )
    block = sessions.last_session(inst)
    assert block is not None
    assert block["disconnects"] == 1
    assert block["interrupts"] == 2
    assert block["ended_at"] == "2026-09-12T21:30:00"


def test_a_half_written_games_csv_gives_zeros_instead_of_raising(tmp_path: Path) -> None:
    inst = tmp_path / "Pie64"
    write_session(inst, "20260912-210000", [{"ts": "2026-09-12T21:30:00", "kind": "recap"}])
    (inst / "games.csv").write_bytes(GAMES_HEADER.encode() + b"\xff\xfe not utf-8 at all")
    block = sessions.last_session(inst)
    assert block is not None
    assert (block["games"], block["trophies"], block["avg_rank"]) == (0, 0, None)


def test_the_newest_of_three_session_files_is_the_one_read(tmp_path: Path) -> None:
    inst = tmp_path / "Pie64"
    write_session(inst, "20260910-080000", [{"ts": "2026-09-10T09:00:00", "kind": "recap"}])
    write_session(inst, "20260912-210000", [{"ts": "2026-09-12T22:14:07", "kind": "recap"}])
    write_session(inst, "20260911-190540", [{"ts": "2026-09-11T20:00:00", "kind": "recap"}])
    block = sessions.last_session(inst)
    assert block is not None
    assert block["ended_at"] == "2026-09-12T22:14:07"


def test_a_second_call_with_nothing_changed_does_not_reread(tmp_path: Path, monkeypatch) -> None:
    inst = tmp_path / "Pie64"
    write_session(inst, "20260912-210000", [{"ts": "2026-09-12T22:14:07", "kind": "recap"}])
    write_games(inst, [game("2026-09-12T21:10:00", "2", "12")])
    first = sessions.last_session(inst)
    reads: list[Path] = []
    original = sessions._read

    def counted(session_path: Path, games_path: Path, filename: str):
        reads.append(session_path)
        return original(session_path, games_path, filename)

    monkeypatch.setattr(sessions, "_read", counted)
    assert sessions.last_session(inst) == first
    assert reads == []


def test_a_new_game_row_invalidates_the_cache(tmp_path: Path) -> None:
    inst = tmp_path / "Pie64"
    write_session(inst, "20260912-210000", [{"ts": "2026-09-12T22:14:07", "kind": "recap"}])
    write_games(inst, [game("2026-09-12T21:10:00", "2", "12")])
    assert sessions.last_session(inst)["games"] == 1
    write_games(
        inst,
        [game("2026-09-12T21:10:00", "2", "12"), game("2026-09-12T21:20:00", "4", "6")],
    )
    assert sessions.last_session(inst)["games"] == 2


def test_a_rewrite_inside_one_mtime_tick_still_invalidates(tmp_path: Path) -> None:
    """Two writes can land in the same filesystem tick (the Windows CI runner does it), so
    the stamp must not be mtime alone."""
    inst = tmp_path / "Pie64"
    write_session(inst, "20260912-210000", [{"ts": "2026-09-12T22:14:07", "kind": "recap"}])
    write_games(inst, [game("2026-09-12T21:10:00", "2", "12")])
    games_path = inst / "games.csv"
    frozen = games_path.stat().st_mtime
    assert sessions.last_session(inst)["games"] == 1
    write_games(
        inst,
        [game("2026-09-12T21:10:00", "2", "12"), game("2026-09-12T21:20:00", "4", "6")],
    )
    os.utime(games_path, (frozen, frozen))
    assert sessions.last_session(inst)["games"] == 2


def test_every_instance_payload_carries_last_session(tmp_path: Path) -> None:
    from brawlfarm import settings as S
    from tests.apihelpers import make_client

    client, _sup, home = make_client(tmp_path, ("Pie64",))
    try:
        inst = S.instance_dir(home, "Pie64")
        write_session(inst, "20260912-210000", [{"ts": "2026-09-12T22:14:07", "kind": "recap"}])
        write_games(inst, [game("2026-09-12T21:10:00", "2", "12")])
        payload = client.get("/api/instances").json()["instances"][0]
        assert payload["last_session"] == {
            "games": 1,
            "trophies": 12,
            "avg_rank": 2.0,
            "disconnects": 0,
            "duration_s": 4447,
            "interrupts": 0,
            "ended_at": "2026-09-12T22:14:07",
        }
        # The blocks beside it are untouched. today_counts reads the wall clock, so only
        # its shape is asserted here: its own tests own the counting.
        assert "session" in payload
        assert sorted(payload["today"]) == ["games", "trophies"]
    finally:
        client.__exit__(None, None, None)


def test_an_instance_that_never_ran_carries_a_null_last_session(tmp_path: Path) -> None:
    from tests.apihelpers import make_client

    client, _sup, _home = make_client(tmp_path, ("Pie64",))
    try:
        payload = client.get("/api/instances").json()["instances"][0]
        assert payload["last_session"] is None
    finally:
        client.__exit__(None, None, None)
