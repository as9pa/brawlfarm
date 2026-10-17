"""The SAM stage's file contract, with a fake segmenter: torch is never imported here."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from tools.play import brawlers, dataset, segment

REPO = Path(__file__).resolve().parents[1]


def _bar():
    return brawlers.Bar(
        cls="enemy", cx=800.0, bw=100.0, bot=300, named=True, colour="red", why="bar", ammo=0.0
    )


def _body_segmenter(frame, bars):
    h, w = frame.shape[:2]
    masks = np.zeros((len(bars), 3, h, w), dtype=bool)
    masks[:, 0, 310:405, 755:845] = True
    return masks, np.full((len(bars), 3), 0.9)


def test_module_imports_without_torch():
    # a fresh interpreter, so whatever other tests imported cannot hide a top-level import
    code = "import sys; import tools.play.segment; assert 'torch' not in sys.modules"
    done = subprocess.run([sys.executable, "-c", code], cwd=REPO, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert segment.DEFAULT_MODEL == "facebook/sam2.1-hiera-large"


def test_run_writes_one_line_per_prompt(tmp_path):
    black = np.zeros((dataset.FRAME_H, dataset.FRAME_W, 3), np.uint8)
    rel = dataset.save_frame(tmp_path, "alpha", 1, black)
    gone = "frames/alpha/alpha-000099.jpg"
    prompts = tmp_path / "prompts.jsonl"
    lines = [{"file": rel, "bars": [_bar().to_json()]}, {"file": gone, "bars": [_bar().to_json()]}]
    prompts.write_text("".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")
    out = tmp_path / "boxes.jsonl"

    summary = segment.run(tmp_path, prompts, out, _body_segmenter)

    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert [r["file"] for r in rows] == [rel, gone]
    assert rows[0]["boxes"] == [
        {"class": "enemy", "x": 755, "y": 310, "w": 90, "h": 95, "score": 0.9, "fallback": False}
    ]
    assert rows[1]["boxes"] == []
    assert summary == {"frames": 2, "boxes": 1, "fallbacks": 0, "missing": 1}
