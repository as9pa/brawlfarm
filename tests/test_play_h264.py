"""The parser-fed H.264 decoder: raw bytes in any chunking, BGR frames out, single-threaded
so the first frame is not held back. The clip is a synthetic test pattern, not a capture."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("av")

from brawlfarm.play import h264  # noqa: E402

CLIP = Path(__file__).parent / "fixtures" / "play" / "stream-2s.h264"


def test_the_clip_decodes_to_full_size_bgr_frames() -> None:
    dec = h264.Decoder()
    frames = []
    data = CLIP.read_bytes()
    for i in range(0, len(data), 4096):
        frames.extend(dec.feed(data[i : i + 4096]))
    frames.extend(dec.flush())
    assert dec.packets == 59
    assert len(frames) == 59
    assert frames[0].shape == (900, 1600, 3)
    assert frames[0].dtype == np.uint8
    assert dec.frames == len(frames)


def test_the_first_frame_is_not_held_back_by_threading() -> None:
    dec = h264.Decoder()
    data = CLIP.read_bytes()
    fed = 0
    for i in range(0, len(data), 4096):
        out = dec.feed(data[i : i + 4096])
        fed = dec.packets
        if out:
            break
    assert fed <= 4, "a single-threaded decoder emits within the first few packets"


def test_feeding_nothing_is_harmless() -> None:
    dec = h264.Decoder()
    assert dec.feed(b"") == []
    assert dec.flush() == []
