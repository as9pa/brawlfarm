"""The scheduler tick reports through logging, never print: the headless CLI prints its
own instance table, and the panel's log stream (phase 3) only sees log records."""

from __future__ import annotations

import logging
from pathlib import Path

from brawlfarm.core import config, scheduler

_INSTANCES = {"alpha": {"port": "5555", "tag": "", "data": "instances/alpha"}}


def _one_instance(home: Path) -> None:
    config.set_home(home)
    config.set_instances(_INSTANCES)


def test_the_all_disabled_summary_is_logged_not_printed(tmp_path, caplog, capsys) -> None:
    _one_instance(tmp_path)
    scheduler.set_enabled(["alpha"], False)  # the legacy always-run path
    with caplog.at_level(logging.INFO, logger="brawlfarm.scheduler"):
        assert scheduler.tick() == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""
    messages = [r.getMessage() for r in caplog.records]
    assert any(m.startswith("tick ") and "alpha=run" in m for m in messages)
    assert {r.name for r in caplog.records} == {"brawlfarm.scheduler"}


def test_the_draw_line_is_logged_too(tmp_path, caplog, capsys) -> None:
    _one_instance(tmp_path)  # scheduling on by default: the tick draws a day
    with caplog.at_level(logging.INFO, logger="brawlfarm.scheduler"):
        assert scheduler.tick() == 0
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""
    messages = [r.getMessage() for r in caplog.records]
    assert any(m.startswith("drew alpha ") and "session(s)" in m for m in messages)
    assert any(m.startswith("tick ") for m in messages)


def test_an_internal_failure_is_logged_with_its_traceback(
    tmp_path, caplog, capsys, monkeypatch
) -> None:
    _one_instance(tmp_path)

    def boom(_now):
        raise RuntimeError("scheduler exploded")

    monkeypatch.setattr(scheduler, "_tick_inner", boom)
    with caplog.at_level(logging.ERROR, logger="brawlfarm.scheduler"):
        assert scheduler.tick() == 1  # still fails open: desired=run is written
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert errors and errors[0].exc_info is not None
    assert "scheduler exploded" in caplog.text
