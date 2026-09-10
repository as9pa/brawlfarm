"""Session-data rotation (brawlfarm/core/janitor.py) — offline tests with a tmp data
root + an injected `now`.

Covers: only files older than KEEP_DAYS move; the newest KEEP_NEWEST are always kept;
today's file is never touched; lines are appended to the right monthly archive in time
order; the move is idempotent on re-run; a dry run touches nothing.

Run:  uv run pytest tests/test_data_janitor.py -q
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from brawlfarm.core import config
from brawlfarm.core import janitor as J

NOW = datetime(2026, 6, 20, 12, 0, 0)

# rotate_all walks config.INSTANCES, which ships empty; register stand-ins so the
# per-account walk has something to walk.
INSTANCES = {"Pie64": {"port": "5555", "tag": "", "data": "data/Pie64"}}


@pytest.fixture(autouse=True)
def _registered():
    config.set_instances(INSTANCES)


@pytest.fixture()
def acct(tmp_path, monkeypatch):
    """A tmp data root with one real account dir; returns that account dir Path."""
    monkeypatch.setenv("BRAWL_SCHED_DATA_ROOT", str(tmp_path))
    name = next(iter(config.INSTANCES))
    d = tmp_path / config.INSTANCES[name]["data"]
    d.mkdir(parents=True)
    return d


def _write_session(acct_dir, ts: datetime, lines: list[str]) -> None:
    p = acct_dir / f"session-{ts.strftime('%Y%m%d-%H%M%S')}.jsonl"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _session_files(acct_dir):
    return sorted(p.name for p in acct_dir.glob("session-*.jsonl"))


def test_only_old_files_move_newest_and_today_kept(acct):
    # 6 old files (10-16 days back) + 2 recent (2 days back) + today.
    olds = [NOW - timedelta(days=d) for d in (16, 15, 14, 13, 12, 11)]
    recents = [NOW - timedelta(days=2, hours=h) for h in (1, 2)]
    today = NOW - timedelta(hours=3)
    for i, ts in enumerate(olds):
        _write_session(acct, ts, [f'{{"i": {i}}}'])
    for ts in recents:
        _write_session(acct, ts, ['{"r": 1}'])
    _write_session(acct, today, ['{"today": 1}'])

    summary = J.rotate_account(acct, NOW)

    # The newest 3 (today + the 2 recents) are protected outright; the 3 oldest of the
    # remaining olds move (the 4th-from-newest old is still > KEEP_NEWEST but old enough).
    remaining = _session_files(acct)
    # today + 2 recents always survive
    assert f"session-{today.strftime('%Y%m%d-%H%M%S')}.jsonl" in remaining
    for ts in recents:
        assert f"session-{ts.strftime('%Y%m%d-%H%M%S')}.jsonl" in remaining
    # at least the 3 oldest old files were archived
    assert summary["moved"] >= 3
    assert summary["kept_newest"] == J.KEEP_NEWEST
    # nothing newer than the cutoff was moved
    archive = acct / "archive"
    assert archive.is_dir()


def test_newest_three_never_touched_even_when_all_old(acct):
    # ALL files are ancient — the newest KEEP_NEWEST must STILL be kept (the live
    # tailers' headroom), so the readers always find their file.
    times = [NOW - timedelta(days=d) for d in (30, 29, 28, 27, 26)]
    for i, ts in enumerate(times):
        _write_session(acct, ts, [f'{{"i": {i}}}'])
    J.rotate_account(acct, NOW)
    remaining = _session_files(acct)
    assert len(remaining) == J.KEEP_NEWEST
    # the kept ones are the NEWEST three (largest timestamps)
    newest3 = sorted(
        f"session-{t.strftime('%Y%m%d-%H%M%S')}.jsonl" for t in times[-J.KEEP_NEWEST :]
    )
    assert remaining == newest3


def test_archive_append_preserves_lines_and_order(acct):
    # two old files in the SAME month fold into one monthly archive, in time order,
    # with every line preserved.
    a = NOW - timedelta(days=14)  # older
    b = NOW - timedelta(days=12)  # newer (still old)
    _write_session(acct, a, ['{"n": "a1"}', '{"n": "a2"}'])
    _write_session(acct, b, ['{"n": "b1"}'])
    # padding so a, b are NOT in the protected newest-3
    for d in (5, 4, 3):
        _write_session(acct, NOW - timedelta(days=d), ['{"pad": 1}'])

    J.rotate_account(acct, NOW)

    arch = acct / "archive" / f"sessions-{a.strftime('%Y-%m')}.jsonl"
    assert arch.is_file()
    lines = arch.read_text(encoding="utf-8").splitlines()
    # a's lines come before b's (oldest-first), nothing dropped
    assert lines == ['{"n": "a1"}', '{"n": "a2"}', '{"n": "b1"}']


def test_idempotent_on_rerun(acct):
    for d in (20, 19, 18, 17, 16, 15):
        _write_session(acct, NOW - timedelta(days=d), [f'{{"d": {d}}}'])
    first = J.rotate_account(acct, NOW)
    arch_files = sorted((acct / "archive").glob("*.jsonl"))
    contents = {p.name: p.read_text(encoding="utf-8") for p in arch_files}
    # a second pass finds nothing new to move and does NOT re-append anything
    second = J.rotate_account(acct, NOW)
    assert second["moved"] == 0
    contents_after = {
        p.name: p.read_text(encoding="utf-8")
        for p in sorted((acct / "archive").glob("*.jsonl"))
    }
    assert contents_after == contents  # archives unchanged on the idempotent re-run
    assert first["moved"] >= 1


def test_dry_run_changes_nothing(acct):
    for d in (20, 19, 18, 17):
        _write_session(acct, NOW - timedelta(days=d), ['{"x": 1}'])
    before = _session_files(acct)
    summary = J.rotate_account(acct, NOW, dry_run=True)
    assert _session_files(acct) == before  # no file removed
    assert not (acct / "archive").exists()  # no archive written
    assert summary["moved"] >= 1  # but it reported what WOULD move


def test_monthly_buckets_split_by_timestamp(acct):
    # files in different months land in different archive buckets
    may = datetime(2026, 5, 10, 8, 0, 0)
    apr = datetime(2026, 4, 10, 8, 0, 0)
    _write_session(acct, may, ['{"m": "may"}'])
    _write_session(acct, apr, ['{"m": "apr"}'])
    for d in (5, 4, 3):  # padding to clear the protected newest-3
        _write_session(acct, NOW - timedelta(days=d), ['{"pad": 1}'])
    J.rotate_account(acct, NOW)
    assert (acct / "archive" / "sessions-2026-05.jsonl").is_file()
    assert (acct / "archive" / "sessions-2026-04.jsonl").is_file()


def test_rotate_all_best_effort_and_summary(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAWL_SCHED_DATA_ROOT", str(tmp_path))
    # one account dir populated with old files, the others absent -> no crash
    name = next(iter(config.INSTANCES))
    d = tmp_path / config.INSTANCES[name]["data"]
    d.mkdir(parents=True)
    for day in (20, 19, 18, 17):
        _write_session(d, NOW - timedelta(days=day), ['{"x": 1}'])
    out = J.rotate_all(NOW)
    assert set(out) == set(config.INSTANCES)  # a summary per account
    assert out[name]["moved"] >= 1


def test_missing_account_dir_is_noop(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAWL_SCHED_DATA_ROOT", str(tmp_path))
    s = J.rotate_account(tmp_path / "data" / "ghost", NOW)
    assert s == {"moved": 0, "skipped_recent": 0, "kept_newest": 0, "errors": 0}


# --- r9: oversized append-only ops-log rotation -----------------------------------------


import os  # noqa: E402


def _big_log(tmp_path, name, *, size, age_s):
    """Write data/<name> at ~``size`` bytes whose mtime is ``age_s`` seconds old."""
    p = tmp_path / "data" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("x" * size, encoding="utf-8")
    stamp = NOW.timestamp() - age_s
    os.utime(p, (stamp, stamp))
    return p


def test_big_log_over_threshold_and_quiet_rolls(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAWL_SCHED_DATA_ROOT", str(tmp_path))
    p = _big_log(tmp_path, "audit.jsonl", size=J.BIG_LOG_MAX_BYTES + 10, age_s=120)
    out = J.rotate_big_logs(NOW)
    assert out["audit.jsonl"]["rolled"] == 1
    arch = tmp_path / "data" / "archive" / f"audit-{NOW.strftime('%Y-%m')}.jsonl"
    assert (
        arch.is_file() and len(arch.read_text(encoding="utf-8")) >= J.BIG_LOG_MAX_BYTES
    )
    assert p.read_text(encoding="utf-8") == ""  # live file truncated, writer reopens


def test_big_log_under_threshold_is_left_alone(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAWL_SCHED_DATA_ROOT", str(tmp_path))
    _big_log(tmp_path, "audit.jsonl", size=1000, age_s=120)  # small
    out = J.rotate_big_logs(NOW)
    assert out["audit.jsonl"]["rolled"] == 0 and out["audit.jsonl"]["skipped"] == 0
    assert not (tmp_path / "data" / "archive").exists()


def test_big_log_written_recently_is_skipped(tmp_path, monkeypatch):
    # Big enough to roll, but touched 5 s ago -> a mid-write roll could drop a line.
    monkeypatch.setenv("BRAWL_SCHED_DATA_ROOT", str(tmp_path))
    _big_log(tmp_path, "events_history.jsonl", size=J.BIG_LOG_MAX_BYTES + 10, age_s=5)
    out = J.rotate_big_logs(NOW)
    assert out["events_history.jsonl"]["rolled"] == 0
    assert out["events_history.jsonl"]["skipped"] == 1


def test_big_log_dry_run_touches_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAWL_SCHED_DATA_ROOT", str(tmp_path))
    p = _big_log(tmp_path, "audit.jsonl", size=J.BIG_LOG_MAX_BYTES + 10, age_s=120)
    out = J.rotate_big_logs(NOW, dry_run=True)
    assert out["audit.jsonl"]["rolled"] == 1  # reported...
    assert p.stat().st_size >= J.BIG_LOG_MAX_BYTES  # ...but nothing moved
    assert not (tmp_path / "data" / "archive").exists()


def test_big_log_missing_file_is_noop(tmp_path, monkeypatch):
    monkeypatch.setenv("BRAWL_SCHED_DATA_ROOT", str(tmp_path))
    out = J.rotate_big_logs(NOW)
    assert out == {n: {"rolled": 0, "skipped": 0, "errors": 0} for n in J.BIG_LOG_NAMES}
