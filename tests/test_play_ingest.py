"""YouTube ingest: the owner's URL list into downloads and dataset frames.

Nothing here downloads. `download` takes its `run` from the caller, so the fake records the
argument list instead of starting yt-dlp, and `main`'s download and frame extraction are
monkeypatched so no video is ever opened.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

from tests.hud_draw import draw_hud
from tools.play import dataset, frames, ingest_youtube

VIDEO_ID = "AAAAAAAAAAA"
CANONICAL = f"https://www.youtube.com/watch?v={VIDEO_ID}"


def _urls_file(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "urls.txt"
    path.write_text(text, encoding="utf-8")
    return path


def test_read_urls_accepts_both_shapes_and_skips_comments(tmp_path):
    path = _urls_file(
        tmp_path,
        "\n".join(
            [
                "# good players, autumn 2026",
                "",
                "https://www.youtube.com/watch?v=AAAAAAAAAAA",
                "https://youtube.com/watch?v=BBBBBBBBBBB&t=42",
                "  https://youtu.be/ccccccccccc?t=90  ",
                "https://www.youtu.be/dd-dd_ddddd",
            ]
        ),
    )
    assert ingest_youtube.read_urls(path) == [
        ("AAAAAAAAAAA", "https://www.youtube.com/watch?v=AAAAAAAAAAA"),
        ("BBBBBBBBBBB", "https://www.youtube.com/watch?v=BBBBBBBBBBB"),
        ("ccccccccccc", "https://www.youtube.com/watch?v=ccccccccccc"),
        ("dd-dd_ddddd", "https://www.youtube.com/watch?v=dd-dd_ddddd"),
    ]


@pytest.mark.parametrize(
    "bad",
    [
        "http://www.youtube.com/watch?v=AAAAAAAAAAA",
        "https://www.youtube.com/playlist?list=PLAAAAAAAAAAA",
        "https://evil.example/watch?v=AAAAAAAAAAA",
        "https://www.youtube.com/watch?v=tooshort",
    ],
)
def test_read_urls_refuses_anything_else_and_names_the_line(tmp_path, bad):
    path = _urls_file(tmp_path, f"# header\n\n{CANONICAL}\n{bad}\n")
    with pytest.raises(ValueError) as exc:
        ingest_youtube.read_urls(path)
    assert "line 4" in str(exc.value)


def test_download_argument_list_is_exact_and_holds_nothing_from_the_owners_line(tmp_path):
    videos = tmp_path / "videos"
    calls = []

    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        Path(args[args.index("-o") + 1].replace("%(ext)s", "mp4")).write_bytes(b"video")
        return subprocess.CompletedProcess(args, 0)

    out = ingest_youtube.download(VIDEO_ID, CANONICAL, videos, run=fake_run)

    assert out == videos / f"{VIDEO_ID}.mp4"
    args, kwargs = calls[0]
    assert args == [
        sys.executable,
        "-m",
        "yt_dlp",
        "--no-playlist",
        "--no-progress",
        "-f",
        ingest_youtube.FORMAT,
        "--merge-output-format",
        "mp4",
        "-o",
        str(videos / f"{VIDEO_ID}.%(ext)s"),
        "--",
        CANONICAL,
    ]
    assert kwargs == {"check": True}
    # Only the 11 character id survives: the owner's trailing junk reaches no argument.
    raw = "https://youtu.be/AAAAAAAAAAA?t=42&list=EVIL"
    assert not any(raw in str(arg) or "EVIL" in str(arg) or "youtu.be" in str(arg) for arg in args)


def test_download_skips_a_video_it_already_has(tmp_path):
    videos = tmp_path / "videos"
    videos.mkdir()
    (videos / f"{VIDEO_ID}.mp4").write_bytes(b"video")

    def fake_run(args, **kwargs):
        raise AssertionError("yt-dlp must not run for a video we already have")

    assert ingest_youtube.download(VIDEO_ID, CANONICAL, videos, run=fake_run) == (
        videos / f"{VIDEO_ID}.mp4"
    )


def test_download_raises_when_yt_dlp_leaves_no_file(tmp_path):
    def fake_run(args, **kwargs):
        return subprocess.CompletedProcess(args, 0)

    with pytest.raises(RuntimeError) as exc:
        ingest_youtube.download(VIDEO_ID, CANONICAL, tmp_path / "videos", run=fake_run)
    assert f"{VIDEO_ID}.mp4" in str(exc.value)


def _index_line(root: Path, source: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    row = {
        "file": f"frames/{source}/{source}-000000.jpg",
        "source": source,
        "kind": "youtube",
        "t": 0.0,
        "hash": "0" * 16,
        "teams_left": 0.0,
        "pad": [0, 0, 0, 0],
    }
    (root / "index.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")


@pytest.fixture
def fake_pipeline(monkeypatch):
    """Downloads and frame extraction both faked: no video, no templates, no subprocess."""
    added = []

    def fake_download(video_id, url, videos, *, run=None):
        path = Path(videos) / f"{video_id}.mp4"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"video")
        return path

    def fake_add_source(root, source, kind, frames_in, **kwargs):
        added.append((source, kind, list(frames_in), kwargs))
        return {"seen": 4, "kept": 3, "duplicates": 1, "dropped": 0}

    monkeypatch.setattr(ingest_youtube, "download", fake_download)
    monkeypatch.setattr(frames, "iter_video", lambda path, **kw: iter([]))
    monkeypatch.setattr(frames, "sample_video", lambda path, **kw: ["sampled"])
    monkeypatch.setattr(frames, "add_source", fake_add_source)
    return added


def test_main_skips_a_source_already_in_the_index(tmp_path, capsys, fake_pipeline):
    root = tmp_path / "play"
    _index_line(root, f"yt-{VIDEO_ID}")
    urls = _urls_file(tmp_path, f"{CANONICAL}\nhttps://youtu.be/BBBBBBBBBBB?t=7\n")

    code = ingest_youtube.main([str(urls), "--root", str(root)])

    out = capsys.readouterr().out
    assert code == 0
    assert f"yt-{VIDEO_ID}" in out
    assert "already in the index" in out
    assert [source for source, _, _, _ in fake_pipeline] == ["yt-BBBBBBBBBBB"]
    assert fake_pipeline[0][1] == "youtube"
    assert fake_pipeline[0][3]["trim"] is True
    assert fake_pipeline[0][3]["sample"] == ["sampled"]
    assert "kept 3" in out


def test_main_stops_on_a_failed_download(tmp_path, capsys, monkeypatch, fake_pipeline):
    def boom(video_id, url, videos, *, run=None):
        raise RuntimeError("yt-dlp left no AAAAAAAAAAA.mp4")

    monkeypatch.setattr(ingest_youtube, "download", boom)
    urls = _urls_file(tmp_path, f"{CANONICAL}\nhttps://youtu.be/BBBBBBBBBBB\n")

    code = ingest_youtube.main([str(urls), "--root", str(tmp_path / "play")])

    assert code == 1
    assert fake_pipeline == []
    assert "yt-dlp left no" in capsys.readouterr().out


def test_main_keep_going_counts_the_failure_and_still_exits_1(
    tmp_path, capsys, monkeypatch, fake_pipeline
):
    def sometimes(video_id, url, videos, *, run=None):
        if video_id == VIDEO_ID:
            raise RuntimeError("yt-dlp left no AAAAAAAAAAA.mp4")
        path = Path(videos) / f"{video_id}.mp4"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"video")
        return path

    monkeypatch.setattr(ingest_youtube, "download", sometimes)
    urls = _urls_file(tmp_path, f"{CANONICAL}\nhttps://youtu.be/BBBBBBBBBBB\n")

    code = ingest_youtube.main([str(urls), "--root", str(tmp_path / "play"), "--keep-going"])

    out = capsys.readouterr().out
    assert code == 1
    assert [source for source, _, _, _ in fake_pipeline] == ["yt-BBBBBBBBBBB"]
    assert "1 failed" in out


def test_main_refuses_a_bad_url_file_before_anything_runs(tmp_path, capsys, fake_pipeline):
    urls = _urls_file(tmp_path, "https://evil.example/watch?v=AAAAAAAAAAA\n")

    code = ingest_youtube.main([str(urls), "--root", str(tmp_path / "play")])

    assert code == 2
    assert fake_pipeline == []
    assert "line 1" in capsys.readouterr().out


FULL = (0, 0, dataset.FRAME_W, dataset.FRAME_H)


def _blocked(frame: np.ndarray, x: int) -> np.ndarray:
    """One bright block, clear of every HUD search box, at a place of this frame's own.

    A blurred floor hashes flat, so without it the fake video's frames land within the
    deduper's distance of each other and a test about the filter would measure the dedupe.
    """
    cv2.rectangle(frame, (x, 100), (x + 500, 400), (210, 210, 210), -1)
    return frame


def _hud_frames() -> list[np.ndarray]:
    """Two frames the real detector calls a HUD, drawn full bleed so the trim finds no border
    and the pad stays zero: the filter then reads the box it reads on footage without bars.
    """
    return [
        _blocked(draw_hud(FULL, seed=0), 150),
        _blocked(
            draw_hud(FULL, seed=1, attack=(0.83, 0.47), knob=(0.26, 0.60), base=(0.25, 0.58)), 700
        ),
    ]


def _no_hud_frames() -> list[np.ndarray]:
    """Two arena floors with no touch controls on them at all."""
    return [
        _blocked(
            draw_hud(
                FULL, attack=None, super_state=None, knob=None, base=None, gadget=False, seed=seed
            ),
            x,
        )
        for seed, x in ((7, 300), (8, 1000))
    ]


@pytest.fixture
def fake_video(monkeypatch):
    """A faked download in front of the real add_source, so the HUD filter runs for real.

    The frames of the video are whatever the test appends to the returned list. Only the
    template score is faked, the way the frames tests do it: no template file is read.
    """
    made: list[np.ndarray] = []

    def fake_download(video_id, url, videos, *, run=None):
        path = Path(videos) / f"{video_id}.mp4"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"video")
        return path

    real = frames.add_source
    monkeypatch.setattr(ingest_youtube, "download", fake_download)
    monkeypatch.setattr(
        frames,
        "iter_video",
        lambda path, **kw: iter([(float(n), frame) for n, frame in enumerate(made)]),
    )
    monkeypatch.setattr(frames, "sample_video", lambda path, **kw: list(made))
    monkeypatch.setattr(
        frames,
        "add_source",
        lambda *a, **kw: real(*a, score=lambda frame, name: 0.5, **kw),
    )
    return made


def _rows(root: Path) -> list[dict]:
    return [
        json.loads(line) for line in (root / "index.jsonl").read_text(encoding="utf-8").splitlines()
    ]


def test_main_drops_the_frames_with_no_mobile_hud(tmp_path, capsys, fake_video):
    fake_video.extend(_hud_frames() + _no_hud_frames())
    root = tmp_path / "play"
    urls = _urls_file(tmp_path, f"{CANONICAL}\n")

    code = ingest_youtube.main([str(urls), "--root", str(root)])

    out = capsys.readouterr().out
    assert code == 0
    assert f"yt-{VIDEO_ID}: seen 4, kept 2, duplicates 0, no HUD 2" in out
    assert "2 frames kept, 2 dropped for no HUD" in out
    assert [row["hud"] for row in _rows(root)] == [True, True]


def test_main_keep_no_hud_keeps_every_frame(tmp_path, capsys, fake_video):
    fake_video.extend(_hud_frames() + _no_hud_frames())
    root = tmp_path / "play"
    urls = _urls_file(tmp_path, f"{CANONICAL}\n")

    code = ingest_youtube.main([str(urls), "--root", str(root), "--keep-no-hud"])

    out = capsys.readouterr().out
    assert code == 0
    assert f"yt-{VIDEO_ID}: seen 4, kept 4, duplicates 0, no HUD 0" in out
    assert "4 frames kept, 0 dropped for no HUD" in out
    rows = _rows(root)
    assert len(rows) == 4
    assert all("hud" not in row for row in rows)


def test_main_names_a_video_that_showed_no_hud_at_all(tmp_path, capsys, fake_video):
    fake_video.extend(_no_hud_frames())
    root = tmp_path / "play"
    urls = _urls_file(tmp_path, f"{CANONICAL}\n")

    code = ingest_youtube.main([str(urls), "--root", str(root)])

    out = capsys.readouterr().out
    assert code == 0
    assert f"yt-{VIDEO_ID}: seen 2, kept 0, duplicates 0, no HUD 2" in out
    assert "no frame showed a mobile HUD" in out
    assert not (root / "index.jsonl").exists()
