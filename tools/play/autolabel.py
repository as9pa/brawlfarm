"""Auto-labels for the play detector: every frame in the index, no human step.

uv run python tools/play/autolabel.py
uv run python tools/play/autolabel.py --root D:/play-data --source yt-AAAAAAAAAAA --no-sam
"""

from __future__ import annotations

import numpy as np

from tools.play import dataset, terrain, zones

MODEL_VERSION = "autolabel-v1"
OUT_NAME = "autolabel.json"
SAM_MODEL = "facebook/sam2.1-hiera-large"


def in_match(row: dict, hsv: np.ndarray, template: list[dict]) -> bool:
    """Whether a frame is mid-match, so the brawler and terrain passes should run on it.

    Every template is a menu button or card, so any template box means a menu. Past that, the
    index's HUD flag decides when the frame has one, and the colour spread decides when it does
    not.
    """
    if template:
        return False
    if row.get("hud") is not None:
        return bool(row["hud"])
    return terrain.is_game_frame(hsv)


def merge(template: list[dict], auto: list[dict], zone: np.ndarray) -> list[dict]:
    """The frame's final boxes: the template boxes first, then the auto boxes that survive.

    Auto boxes mostly inside a zone are dropped and the rest are clipped to the frame, skipping
    any that clip to nothing. Template boxes are never zone-filtered: menu buttons sit where the
    HUD does, so the HUD zones would drop exactly the boxes the templates exist to find.
    """
    kept: list[dict] = []
    for box in zones.drop_in_zones(auto, zone):
        left = max(0, box["x"])
        top = max(0, box["y"])
        right = min(dataset.FRAME_W, box["x"] + box["w"])
        bottom = min(dataset.FRAME_H, box["y"] + box["h"])
        if right <= left or bottom <= top:
            continue
        kept.append({**box, "x": left, "y": top, "w": right - left, "h": bottom - top})
    return list(template) + kept
