"""The atomic writer's bounded retry: Windows refuses os.replace while another process
holds the target open, so a transient PermissionError must not become a failed request.
Pins that the rename is tried again on a backing-off schedule, that the file lands when
one of those attempts wins, and that a rename which never wins raises the original error
and leaves no *.tmp behind."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from brawlfarm.core import jsonio
from brawlfarm.core.jsonio import REPLACE_BACKOFF_S, atomic_write_json


@pytest.fixture()
def slept(monkeypatch) -> list[float]:
    """Every wait the writer asked for, and none of them real."""
    waits: list[float] = []
    monkeypatch.setattr(jsonio.time, "sleep", waits.append)
    return waits


def _refusing(times: int):
    """An os.replace that raises WinError 5 the first `times` calls, then does the real
    rename. The count is what the retry is being measured against."""
    real = os.replace
    calls = {"n": 0}

    def replace(src, dst):
        calls["n"] += 1
        if calls["n"] <= times:
            raise PermissionError(13, "The file is being used by another process", str(dst), 5)
        return real(src, dst)

    return replace, calls


def test_a_rename_that_is_refused_twice_still_lands(tmp_path: Path, monkeypatch, slept) -> None:
    replace, calls = _refusing(2)
    monkeypatch.setattr(jsonio.os, "replace", replace)
    target = tmp_path / "override.json"

    atomic_write_json(target, {"mode": "run"})

    assert json.loads(target.read_text(encoding="utf-8")) == {"mode": "run"}
    assert calls["n"] == 3  # two refusals, then the attempt that won
    assert slept == [REPLACE_BACKOFF_S[0], REPLACE_BACKOFF_S[1]]
    assert list(tmp_path.glob("*.tmp")) == []


def test_a_rename_that_is_never_allowed_raises_and_leaves_no_temp_file(
    tmp_path: Path, monkeypatch, slept
) -> None:
    replace, calls = _refusing(len(REPLACE_BACKOFF_S))
    monkeypatch.setattr(jsonio.os, "replace", replace)
    target = tmp_path / "override.json"

    with pytest.raises(PermissionError):
        atomic_write_json(target, {"mode": "run"})

    # The retry is bounded: the caller hears about it rather than the write hanging on.
    assert calls["n"] == len(REPLACE_BACKOFF_S)
    assert slept == list(REPLACE_BACKOFF_S)
    assert not target.exists()
    assert list(tmp_path.glob("*.tmp")) == []


def test_an_error_that_is_not_a_permission_error_is_not_retried(
    tmp_path: Path, monkeypatch, slept
) -> None:
    """Only the Windows sharing violation is worth waiting on. A missing directory or a
    bad name is not going to fix itself, and retrying it would only delay the report."""

    def replace(_src, _dst):
        raise OSError(22, "invalid argument")

    monkeypatch.setattr(jsonio.os, "replace", replace)

    with pytest.raises(OSError):
        atomic_write_json(tmp_path / "override.json", {"mode": "run"})

    assert slept == []


def test_the_temp_file_keeps_its_name_beside_the_target(tmp_path: Path, monkeypatch) -> None:
    """The readers of these files glob for *.tmp, so the name the writer uses is part of
    the contract and the retry must not have changed it."""
    seen: list[str] = []
    real = os.replace

    def replace(src, dst):
        seen.append(Path(src).name)
        return real(src, dst)

    monkeypatch.setattr(jsonio.os, "replace", replace)
    atomic_write_json(tmp_path / "status.json", {"state": "farming"})

    assert seen == ["status.json.tmp"]
