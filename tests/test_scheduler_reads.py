"""scheduler.read_override and scheduler.is_enabled: the read-only twins of the writers
the panel already had. The panel has to show the switch and the override it is about to
change, and until now it could only write them."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from brawlfarm.core import config, scheduler

_INSTANCES = {"alpha": {"port": "5555", "tag": "", "data": "instances/alpha"}}


def _one_instance(home: Path) -> None:
    config.set_home(home)
    config.set_instances(_INSTANCES)


def test_read_override_returns_what_write_override_wrote(tmp_path: Path) -> None:
    _one_instance(tmp_path)
    assert scheduler.read_override("alpha") is None
    scheduler.write_override("alpha", "run", datetime(2026, 9, 10, 16, 0, 0))
    override = scheduler.read_override("alpha")
    assert set(override) == {"mode", "until", "set_at"}
    assert override["mode"] == "run"
    assert override["until"] == "2026-09-10T16:00:00"
    scheduler.clear_override("alpha")
    assert scheduler.read_override("alpha") is None


def test_read_override_is_none_for_junk_or_an_unknown_instance(tmp_path: Path) -> None:
    _one_instance(tmp_path)
    path = tmp_path / "instances" / "alpha" / "override.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"mode": "sideways", "until": "2026-09-10T16:00:00"}', encoding="utf-8")
    assert scheduler.read_override("alpha") is None
    path.write_text("not json at all", encoding="utf-8")
    assert scheduler.read_override("alpha") is None
    assert scheduler.read_override("ghost") is None  # not in config.INSTANCES


def test_is_enabled_is_default_on_and_honours_an_explicit_false(tmp_path: Path) -> None:
    _one_instance(tmp_path)
    assert scheduler.is_enabled("alpha") is True  # no control file at all
    scheduler.set_enabled(["alpha"], False)
    assert scheduler.is_enabled("alpha") is False
    scheduler.set_enabled(["alpha"], True)
    assert scheduler.is_enabled("alpha") is True
    scheduler.bump_nonce("alpha")  # a redraw must never silently disable an account
    assert scheduler.is_enabled("alpha") is True
