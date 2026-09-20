"""Frame extraction from recorder sessions, raw match files and container videos.

The fixture clip is the only real video here; every other frame is synthetic and the
template score is faked, so nothing depends on template content.
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from tools.play import dataset, frames

FIXTURE = Path(__file__).parent / "fixtures" / "play" / "stream-2s.h264"


def _gradient(h: int = 900, w: int = 1600) -> np.ndarray:
    row = np.linspace(0, 255, w, dtype=np.float32)
    img = np.repeat(row[None, :], h, axis=0).astype(np.uint8)
    return np.dstack([img, img, img])


def _checkerboard(h: int = 900, w: int = 1600, size: int = 40) -> np.ndarray:
    ys, xs = np.mgrid[0:h, 0:w]
    cells = (((ys // size + xs // size) % 2) * 255).astype(np.uint8)
    return np.dstack([cells, cells, cells])


def _write_jpg(path: Path, frame: np.ndarray) -> None:
    ok, buf = cv2.imencode(".jpg", frame)
    assert ok
    path.write_bytes(buf.tobytes())


def _half_score(frame: np.ndarray, name: str) -> float:
    return 0.5


def test_iter_h264_samples_the_fixture_clip():
    pytest.importorskip("av")
    out = list(frames.iter_h264(FIXTURE, fps_out=2.0))
    assert [round(t, 3) for t, _ in out] == [0.0, 0.5, 1.0, 1.5]
    for _, frame in out:
        assert frame.shape == (900, 1600, 3)


def test_iter_video_samples_a_container(tmp_path):
    av = pytest.importorskip("av")
    path = tmp_path / "clip.mp4"
    with av.open(str(path), "w") as container:
        stream = container.add_stream("mpeg4", rate=10)
        stream.width, stream.height = 320, 180
        stream.pix_fmt = "yuv420p"
        for i in range(10):
            img = np.full((180, 320, 3), i * 20, dtype=np.uint8)
            frame = av.VideoFrame.from_ndarray(img, format="bgr24")
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)

    out = list(frames.iter_video(path, fps_out=2.0))
    assert len(out) == 2
    assert [round(t, 3) for t, _ in out] == [0.0, 0.5]
    for _, frame in out:
        assert frame.shape == (180, 320, 3)


def test_iter_session_skips_frames_that_are_not_full_size(tmp_path):
    _write_jpg(tmp_path / "0001-home.jpg", _gradient())
    _write_jpg(tmp_path / "0002-home.jpg", _gradient(450, 800))
    out = list(frames.iter_session(tmp_path))
    assert len(out) == 1
    t, frame = out[0]
    assert t is None
    assert frame.shape == (900, 1600, 3)


def test_add_source_keeps_new_frames_and_counts_duplicates(tmp_path):
    first = _gradient()
    incoming = [(0.0, first), (0.5, first.copy()), (1.0, _checkerboard())]
    counts = frames.add_source(tmp_path, "clip", "video", incoming, score=_half_score)
    assert counts == {"seen": 3, "kept": 2, "duplicates": 1}

    files = sorted(p.name for p in (tmp_path / "frames" / "clip").glob("*.jpg"))
    assert files == ["clip-000000.jpg", "clip-000001.jpg"]

    lines = (tmp_path / "index.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    rows = [json.loads(line) for line in lines]
    assert [row["file"] for row in rows] == [
        "frames/clip/clip-000000.jpg",
        "frames/clip/clip-000001.jpg",
    ]
    assert [row["teams_left"] for row in rows] == [0.5, 0.5]
    assert [row["t"] for row in rows] == [0.0, 1.0]
    assert all(row["source"] == "clip" and row["kind"] == "video" for row in rows)


def test_add_source_refuses_a_bad_source_name(tmp_path):
    with pytest.raises(ValueError):
        frames.add_source(tmp_path, "../x", "video", [], score=_half_score)


def _faked_add_source(monkeypatch):
    """Run the real add_source from main() but with the template score faked."""
    real = frames.add_source
    monkeypatch.setattr(frames, "add_source", lambda *a, **kw: real(*a, score=_half_score, **kw))


def test_main_refuses_an_indexed_source_unless_again(tmp_path, monkeypatch):
    _faked_add_source(monkeypatch)
    session = tmp_path / "20260918-101112"
    session.mkdir()
    _write_jpg(session / "0001-home.jpg", _gradient())
    root = tmp_path / "root"
    argv = ["--session", str(session), "--root", str(root)]

    assert frames.main(argv) == 0
    assert frames.main(argv) == 2
    assert frames.main(argv + ["--again"]) == 0

    index = dataset.Index(root)
    assert index.has_source("20260918-101112")


def test_add_source_numbers_past_a_gap_in_the_existing_frames(tmp_path):
    folder = tmp_path / "frames" / "clip"
    folder.mkdir(parents=True)
    _write_jpg(folder / "clip-000000.jpg", _gradient())
    _write_jpg(folder / "clip-000002.jpg", _checkerboard())
    before = {p.name: p.read_bytes() for p in folder.glob("*.jpg")}

    counts = frames.add_source(tmp_path, "clip", "video", [(0.0, _gradient())], score=_half_score)

    assert counts == {"seen": 1, "kept": 1, "duplicates": 0}
    assert (folder / "clip-000003.jpg").exists()
    assert {p.name: p.read_bytes() for p in folder.glob("*.jpg") if p.name in before} == before
    row = json.loads((tmp_path / "index.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert row["file"] == "frames/clip/clip-000003.jpg"


def test_video_time_falls_back_to_the_average_rate():
    class _Untimed:
        time = None

    assert frames._video_time(_Untimed(), 3, 10) == pytest.approx(0.3)
    assert frames._video_time(_Untimed(), 3, None) is None


def _bordered_video_frame(value: int) -> np.ndarray:
    """1080p-ish frame with the game picture inside a baked-in black border."""
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    # A coarse pattern seeded by the value, so consecutive frames are not deduped away.
    small = np.random.default_rng(value).integers(20, 250, size=(8, 9), dtype=np.uint8)
    picture = cv2.resize(small, (1080, 600), interpolation=cv2.INTER_NEAREST)
    frame[60:660, 100:1180] = np.dstack([picture, picture, picture])
    return frame


def test_add_source_trims_the_border_and_indexes_the_crop(tmp_path):
    incoming = [(float(n), _bordered_video_frame(40 + n * 30)) for n in range(5)]

    counts = frames.add_source(tmp_path, "clip", "video", incoming, score=_half_score, trim=True)

    assert counts["kept"] == 5
    rows = [
        json.loads(line)
        for line in (tmp_path / "index.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert all(row["crop"] == [100, 60, 1080, 600] for row in rows)
    kept = cv2.imdecode(
        np.frombuffer((tmp_path / rows[0]["file"]).read_bytes(), np.uint8), cv2.IMREAD_COLOR
    )
    assert kept.shape == (dataset.FRAME_H, dataset.FRAME_W, 3)


def test_add_source_without_trim_indexes_the_whole_frame_as_the_crop(tmp_path):
    frames.add_source(tmp_path, "clip", "video", [(0.0, _gradient())], score=_half_score)

    row = json.loads((tmp_path / "index.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert row["crop"] == [0, 0, 1600, 900]


def test_add_source_trims_with_fewer_frames_than_the_sample(tmp_path, monkeypatch):
    monkeypatch.setattr(frames, "TRIM_SAMPLE", 40)
    incoming = iter([(0.0, _bordered_video_frame(90))])

    counts = frames.add_source(tmp_path, "clip", "video", incoming, score=_half_score, trim=True)

    assert counts["kept"] == 1
    row = json.loads((tmp_path / "index.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert row["crop"] == [100, 60, 1080, 600]


def test_main_trims_container_videos_only(tmp_path, monkeypatch):
    calls = []

    def recorder(root, name, kind, made, **kwargs):
        calls.append((kind, kwargs.get("trim")))
        return {"seen": 0, "kept": 0, "duplicates": 0}

    monkeypatch.setattr(frames, "iter_video", lambda path, **kw: iter([]))
    monkeypatch.setattr(frames, "add_source", recorder)
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"video")
    session = tmp_path / "20260918-101112"
    session.mkdir()
    _write_jpg(session / "0001-home.jpg", _gradient())
    root = tmp_path / "root"

    assert frames.main(["--video", str(video), "--root", str(root)]) == 0
    assert frames.main(["--session", str(session), "--root", str(root)]) == 0
    assert calls == [("video", True), ("session", False)]
