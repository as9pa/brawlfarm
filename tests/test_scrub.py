"""The scrub check keeps legacy account identifiers and Discord imports out of the repo."""

from __future__ import annotations

import hashlib
from pathlib import Path

from tools import scrub_check

REPO = Path(__file__).resolve().parents[1]


def _h(token: str) -> str:
    return hashlib.sha256(token.lower().encode()).hexdigest()


def test_repo_is_clean() -> None:
    assert scrub_check.scan(REPO) == []


def test_detects_forbidden_token_in_text(tmp_path: Path) -> None:
    (tmp_path / "note.md").write_text("the account forbiddenword was here\n", encoding="utf-8")
    hits = scrub_check.scan(tmp_path, extra_hashes=frozenset({_h("forbiddenword")}))
    assert hits == ["note.md:1: forbidden identifier"]


def test_detects_forbidden_token_in_filename(tmp_path: Path) -> None:
    (tmp_path / "shot_forbiddenword_1.png").write_bytes(b"\x89PNG")
    hits = scrub_check.scan(tmp_path, extra_hashes=frozenset({_h("forbiddenword")}))
    assert hits == ["shot_forbiddenword_1.png:0: forbidden identifier in filename"]


def test_detects_discord_import(tmp_path: Path) -> None:
    (tmp_path / "x.py").write_text("import os\nfrom discord import app_commands\n", encoding="utf-8")
    assert scrub_check.scan(tmp_path) == ["x.py:2: discord import"]


def test_ignores_token_with_hash_prefix_only(tmp_path: Path) -> None:
    (tmp_path / "ok.md").write_text("forbiddenwords are longer tokens\n", encoding="utf-8")
    assert scrub_check.scan(tmp_path, extra_hashes=frozenset({_h("forbiddenword")})) == []
