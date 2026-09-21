"""The play dataset core: the class list, hashing, framing, dedupe, the index and frame files.

Synthetic images only. Nothing here reads the owner's data home or a real template.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import cv2
import numpy as np
import pytest

from tools.play import classes, dataset


def _gradient(h: int = 900, w: int = 1600) -> np.ndarray:
    row = np.linspace(0, 255, w, dtype=np.float32)
    img = np.repeat(row[None, :], h, axis=0).astype(np.uint8)
    return np.dstack([img, img, img])


def _checkerboard(h: int = 900, w: int = 1600, size: int = 40) -> np.ndarray:
    ys, xs = np.mgrid[0:h, 0:w]
    cells = (((ys // size + xs // size) % 2) * 255).astype(np.uint8)
    return np.dstack([cells, cells, cells])


def _spread_hashes(n: int) -> list[int]:
    """n pseudo-random 64-bit hashes, far apart from each other so only exact repeats match."""
    return [int.from_bytes(hashlib.sha256(str(i).encode()).digest()[:8], "big") for i in range(n)]


def test_category_id_is_the_one_based_position():
    assert classes.category_id("self") == 1
    assert classes.category_id(classes.CLASSES[-1]) == len(classes.CLASSES)
    with pytest.raises(KeyError):
        classes.category_id("not_a_class")


def test_template_classes_and_tap_anchors_are_classes():
    for name in classes.TEMPLATE_CLASS.values():
        assert name in classes.CLASSES
    for name in classes.TAP_ANCHORS:
        assert name in classes.CLASSES


def test_default_root_is_under_the_isolated_home(tmp_path):
    home = Path(os.environ["BRAWLFARM_HOME"]).resolve()
    assert dataset.default_root() == home / "datasets" / "play"


def test_dhash_ignores_a_uniform_brightness_shift():
    frame = _gradient()
    brighter = np.clip(frame.astype(np.int16) + 3, 0, 255).astype(np.uint8)
    assert dataset.dhash(frame) == dataset.dhash(brighter)


def test_dhash_separates_unrelated_frames():
    assert dataset.hamming(dataset.dhash(_gradient()), dataset.dhash(_checkerboard())) > 10


def test_fit_frame_leaves_a_16_9_frame_unpadded():
    out, pad = dataset.fit_frame(_gradient(1080, 1920))
    assert out.shape == (dataset.FRAME_H, dataset.FRAME_W, 3)
    assert pad == (0, 0, 0, 0)


def test_fit_frame_pads_a_wide_frame_top_and_bottom():
    out, pad = dataset.fit_frame(_gradient(1080, 2340))
    left, top, right, bottom = pad
    assert out.shape == (dataset.FRAME_H, dataset.FRAME_W, 3)
    assert (left, right) == (0, 0)
    assert top > 0 and top == bottom
    assert not out[:top].any()
    assert not out[dataset.FRAME_H - bottom :].any()


def test_fit_frame_returns_an_exact_frame_unchanged():
    frame = _gradient()
    out, pad = dataset.fit_frame(frame)
    assert pad == (0, 0, 0, 0)
    assert np.array_equal(out, frame)


def test_deduper_refuses_an_exact_repeat_beyond_the_window():
    d = dataset.Deduper(window=4)
    first = _spread_hashes(1)[0]
    assert d.is_new(first)
    for h in _spread_hashes(20)[1:]:
        assert d.is_new(h)
    assert not d.is_new(first)


def test_deduper_refuses_a_near_neighbour_and_keeps_a_far_one():
    d = dataset.Deduper()
    base = _spread_hashes(1)[0]
    assert d.is_new(base)
    near = base ^ 0b111  # distance 3
    far = base ^ 0b11111  # distance 5
    assert not d.is_new(near)
    assert d.is_new(far)


def test_deduper_takes_seed_hashes():
    seed = _spread_hashes(2)
    d = dataset.Deduper(seen=seed)
    assert not d.is_new(seed[0])
    assert not d.is_new(seed[1])


@pytest.mark.parametrize("name", ["../x", "a b", "", "x" * 65, "a/b", "a.b"])
def test_check_source_refuses_a_bad_name(name):
    with pytest.raises(ValueError):
        dataset.check_source(name)


def test_check_source_returns_a_good_name():
    assert dataset.check_source("20260918-101112-match-1") == "20260918-101112-match-1"


def test_index_appends_lines_and_reloads(tmp_path):
    index = dataset.Index(tmp_path)
    assert index.hashes() == []
    assert not index.has_source("clip")
    index.add(
        file="frames/clip/clip-000000.jpg",
        source="clip",
        kind="video",
        t=0.0,
        hash_=1,
        teams_left=0.5,
        pad=(0, 0, 0, 0),
    )
    index.add(
        file="frames/clip/clip-000001.jpg",
        source="clip",
        kind="video",
        t=None,
        hash_=0xABCDEF0123456789,
        teams_left=0.25,
        pad=(0, 10, 0, 10),
        crop=(0, 60, 1280, 600),
    )

    lines = (tmp_path / "index.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    row = json.loads(lines[1])
    assert row == {
        "file": "frames/clip/clip-000001.jpg",
        "source": "clip",
        "kind": "video",
        "t": None,
        "crop": [0, 60, 1280, 600],
        "hash": "abcdef0123456789",
        "teams_left": 0.25,
        "pad": [0, 10, 0, 10],
    }

    again = dataset.Index(tmp_path)
    assert again.hashes() == [1, 0xABCDEF0123456789]
    assert again.has_source("clip")
    assert not again.has_source("other")


def test_index_row_carries_hud_only_when_given(tmp_path):
    index = dataset.Index(tmp_path)
    index.add(
        file="frames/clip/clip-000000.jpg",
        source="clip",
        kind="video",
        t=0.0,
        hash_=1,
        teams_left=0.5,
        pad=(0, 0, 0, 0),
    )
    index.add(
        file="frames/clip/clip-000001.jpg",
        source="clip",
        kind="video",
        t=0.5,
        hash_=2,
        teams_left=0.5,
        pad=(0, 0, 0, 0),
        hud=False,
    )

    rows = dataset.index_rows(tmp_path)
    assert "hud" not in rows[0]
    assert rows[1]["hud"] is False


def test_save_frame_writes_a_relative_jpeg_path(tmp_path):
    rel = dataset.save_frame(tmp_path, "clip", 12, _gradient())
    assert rel == "frames/clip/clip-000012.jpg"
    written = tmp_path / "frames" / "clip" / "clip-000012.jpg"
    decoded = cv2.imdecode(np.frombuffer(written.read_bytes(), np.uint8), cv2.IMREAD_COLOR)
    assert decoded.shape == (dataset.FRAME_H, dataset.FRAME_W, 3)


def test_save_frame_refuses_to_overwrite(tmp_path):
    dataset.save_frame(tmp_path, "clip", 3, _gradient())
    with pytest.raises(FileExistsError):
        dataset.save_frame(tmp_path, "clip", 3, _gradient())


def _bordered(h: int = 180, w: int = 320, left: int = 100, top: int = 60, level: int = 200):
    """A bright picture inside a black border, the shape a letterboxed video has."""
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    frame[top:, left:] = level
    return frame


def test_content_box_finds_the_picture_inside_the_border():
    assert dataset.content_box([_bordered(), _bordered()]) == (100, 60, 220, 120)


def test_content_box_survives_a_dark_frame_of_the_same_source():
    # A dark moment in a minority of the frames must not widen the border.
    frames = [_bordered(level=200)] * 7 + [_bordered(level=4)] * 3

    assert dataset.content_box(frames) == (100, 60, 220, 120)


def test_content_box_survives_a_full_bleed_minority():
    # An intro or a replay overlay fills the frame; three of ten must not hide the bars.
    frames = [_bordered()] * 7 + [np.full((180, 320, 3), 200, dtype=np.uint8)] * 3

    assert dataset.content_box(frames) == (100, 60, 220, 120)


def _pillarboxed(h: int = 360, w: int = 640, left: int = 80, right: int = 560, level: int = 120):
    """A picture over the full height inside black side bars, the shape a phone capture has."""
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    frame[:, left:right] = level
    return frame


def test_content_box_ignores_an_overlay_inside_a_bar():
    # A creator's overlay reaches the frame edge: it lifts the bar's mean gray but lights well
    # under half of the bar's pixels, so the bar still reads as a bar.
    frames = []
    for _ in range(8):
        frame = _pillarboxed()
        frame[200:340, :80] = 200
        frames.append(frame)

    assert dataset.content_box(frames) == (80, 0, 480, 360)


def test_content_box_keeps_a_dark_scene_inside_the_box():
    # A dark scene lights none of its pixels, but a minority of the frames cannot move the box.
    frames = [_pillarboxed()] * 5 + [_pillarboxed(level=6)] * 3

    assert dataset.content_box(frames) == (80, 0, 480, 360)


def test_content_box_of_a_full_bleed_set_is_the_whole_frame():
    frames = [np.full((180, 320, 3), 200, dtype=np.uint8)] * 10

    assert dataset.content_box(frames) == (0, 0, 320, 180)


def test_content_box_of_a_dark_set_is_the_whole_frame():
    assert dataset.content_box([np.zeros((180, 320, 3), dtype=np.uint8)]) == (0, 0, 320, 180)


def test_content_box_refuses_a_box_smaller_than_half_the_frame():
    frame = np.zeros((180, 320, 3), dtype=np.uint8)
    frame[80:120, 140:180] = 200

    assert dataset.content_box([frame]) == (0, 0, 320, 180)


def test_content_box_of_frames_that_differ_in_size_is_the_whole_frame():
    assert dataset.content_box([_bordered(), _bordered(h=200)]) == (0, 0, 320, 180)


def test_content_box_needs_a_frame():
    with pytest.raises(ValueError):
        dataset.content_box([])


def test_a_half_written_last_line_is_skipped_not_fatal(tmp_path, capsys):
    index = dataset.Index(tmp_path)
    index.add(
        file="frames/clip/clip-000000.jpg",
        source="clip",
        kind="video",
        t=0.0,
        hash_=7,
        teams_left=0.5,
        pad=(0, 0, 0, 0),
    )
    with (tmp_path / "index.jsonl").open("a", encoding="utf-8") as fh:
        fh.write('{"file": "frames/clip/clip-0000')  # the run was interrupted here
    again = dataset.Index(tmp_path)
    assert again.hashes() == [7]
    assert [row["file"] for row in dataset.index_rows(tmp_path)] == ["frames/clip/clip-000000.jpg"]
    assert "line 2" in capsys.readouterr().out
