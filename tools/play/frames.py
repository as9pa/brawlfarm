"""Pull training frames out of recorder sessions (with their match-N folders), raw match files and
container videos.

Every source is sampled at FPS_OUT, fitted to 1600 x 900, deduped against the whole index and
written into the dataset folder with one index line each. Read-only against the source files;
nothing here talks to adb or sends input.

    uv run python tools/play/frames.py --session <home>/calibration/recordings/Pie64/20260918-101112
    uv run python tools/play/frames.py --match match-1.h264 --source pie64-match-1
    uv run python tools/play/frames.py --video downloads/clip.mp4 --root D:/play-data
"""

from __future__ import annotations

import argparse
import itertools
import math
from collections.abc import Callable, Iterable, Iterator, Sequence
from pathlib import Path

import cv2
import numpy as np

from brawlfarm.core import vision
from brawlfarm.play import h264
from tools.play import dataset

FPS_OUT = 2.0
# How many frames the border measurement looks at before the first one is written.
TRIM_SAMPLE = 40
# The share of a video's duration the sampled frames are spread over, away from intro and credits.
SAMPLE_START, SAMPLE_END = 0.05, 0.95

_CHUNK = 64 * 1024


def _sampler(fps_out: float) -> Callable[[float], bool]:
    """Returns take(t): True for the first frame at or after each multiple of 1 / fps_out.

    The next deadline is recomputed from the frame's own time rather than stepped forward, so
    a gap in the source skips the deadlines it swallowed instead of emitting a burst.
    """
    step = 1.0 / fps_out
    state = {"next": 0.0}

    def take(t: float) -> bool:
        if t + 1e-9 < state["next"]:
            return False
        state["next"] = (math.floor((t + 1e-9) / step) + 1) * step
        return True

    return take


def iter_h264(
    path: Path, fps_in: float = 30.0, fps_out: float = FPS_OUT
) -> Iterator[tuple[float, np.ndarray]]:
    """Sample a raw H.264 elementary stream. It carries no timestamps, so frame k is k / fps_in."""
    decoder = h264.Decoder()
    take = _sampler(fps_out)
    k = 0

    def emit(frames: list[np.ndarray]) -> Iterator[tuple[float, np.ndarray]]:
        nonlocal k
        for frame in frames:
            t = k / fps_in
            k += 1
            if take(t):
                yield t, frame

    with Path(path).open("rb") as fh:
        while True:
            data = fh.read(_CHUNK)
            if not data:
                break
            yield from emit(decoder.feed(data))
    yield from emit(decoder.flush())


def _video_time(frame, index: int, rate) -> float | None:
    """A container frame's time in seconds, or None when there is no way to place it.

    Most frames carry a presentation time. A stream that does not falls back to the frame
    index over the stream's average rate; treating an untimed frame as t = 0 instead would
    drop every one of them after the first sample.
    """
    if frame.time is not None:
        return float(frame.time)
    if rate:
        return index / float(rate)
    return None


def iter_video(path: Path, fps_out: float = FPS_OUT) -> Iterator[tuple[float, np.ndarray]]:
    """Sample a container video (mp4, mkv, webm) by its own presentation times."""
    import av  # only the dataset and play groups have PyAV

    with av.open(str(path)) as container:
        stream = container.streams.video[0]
        take = _sampler(fps_out)
        untimed = 0
        for index, frame in enumerate(container.decode(stream)):
            t = _video_time(frame, index, stream.average_rate)
            if t is None:
                untimed += 1
                continue
            if take(t):
                yield t, frame.to_ndarray(format="bgr24")
        if untimed:
            print(f"{Path(path).name}: skipped {untimed} frames with no time and no rate")


def sample_video(path: Path, n: int = TRIM_SAMPLE) -> list[np.ndarray]:
    """n frames spread evenly over the middle of a container video, for the border measurement.

    The first frames of a video are the worst ones to measure: an intro, a channel card or a
    fade is often full bleed while the footage behind it is letterboxed, and the trim would then
    find no border at all. So this seeks instead of decoding from the start, one seek and one
    frame per step between SAMPLE_START and SAMPLE_END of the duration. A video that cannot say
    how long it is, or that fails any step, gives back nothing and the caller buffers instead.
    """
    import av  # only the dataset and play groups have PyAV

    try:
        with av.open(str(path)) as container:
            stream = container.streams.video[0]
            if not container.duration:
                return []
            picked = []
            for step in range(max(n, 1)):
                share = SAMPLE_START
                if n > 1:
                    share += (SAMPLE_END - SAMPLE_START) * step / (n - 1)
                container.seek(int(container.duration * share), any_frame=False, backward=True)
                frame = next(container.decode(stream), None)
                if frame is None:
                    break
                picked.append(frame.to_ndarray(format="bgr24"))
            return picked
    except Exception as exc:  # a broken container, an audio-only file, an unseekable stream
        print(f"{Path(path).name}: cannot sample it for the border trim ({exc})")
        return []


def iter_session(folder: Path) -> Iterator[tuple[float | None, np.ndarray]]:
    """The session's screenshots in name order. Sessions recorded at half size are useless for
    training, so anything that is not exactly 1600 x 900 is skipped and reported at the end."""
    folder = Path(folder)
    skipped = 0
    for path in sorted(folder.glob("*.jpg")):
        frame = cv2.imdecode(np.frombuffer(path.read_bytes(), np.uint8), cv2.IMREAD_COLOR)
        if frame is None or frame.shape[:2] != (dataset.FRAME_H, dataset.FRAME_W):
            skipped += 1
            continue
        yield None, frame
    if skipped:
        print(f"{folder.name}: skipped {skipped} frames that are not 1600 x 900")


def _next_index(root: Path, source: str) -> int:
    """One past the highest number this source has already written, so --again adds frames
    instead of overwriting them. A count would not do: delete one frame in the middle and the
    count lands on a name the index still points at."""
    highest = -1
    for path in (root / "frames" / source).glob(f"{source}-*.jpg"):
        suffix = path.stem[len(source) + 1 :]
        if suffix.isdigit():
            highest = max(highest, int(suffix))
    return highest + 1


def add_source(
    root: Path,
    source: str,
    kind: str,
    frames: Iterable[tuple[float | None, np.ndarray]],
    *,
    score=vision.score,
    trim: bool = False,
    sample: Sequence[np.ndarray] | None = None,
    keep: Callable[[np.ndarray, tuple[int, int, int, int]], bool] | None = None,
) -> dict[str, int]:
    """Fit, hash, dedupe, save and index every frame of one source. Returns the counts.

    `trim` is for footage that arrives inside baked-in black bars: the border is measured once
    and then every frame of the source is cropped to the same box before it is fitted. The
    measurement reads `sample` when it is given one, which is how a caller with the file in
    hand hands over frames from the whole video instead of its opening seconds; without one the
    first TRIM_SAMPLE frames are buffered and measured. Emulator frames never need any of it,
    and asking for it on them costs a measurement that finds nothing.

    `keep` is the frame filter the YouTube ingest hands over to drop footage with no mobile
    HUD on it. It reads the fitted frame and its pad, because that is the picture the index
    will hold and the pad is where the HUD coordinates come from. It runs before the hash, so
    a refused frame teaches the deduper nothing and a frame kept later cannot be lost to it;
    what it let through is recorded as `hud` on the row, and without a filter no row says
    anything about a HUD at all.
    """
    dataset.check_source(source)
    root = Path(root)
    index = dataset.Index(root)
    deduper = dataset.Deduper(seen=index.hashes())
    n = _next_index(root, source)
    counts = {"seen": 0, "kept": 0, "duplicates": 0, "dropped": 0}
    incoming = iter(frames)
    box: tuple[int, int, int, int] | None = None
    if trim and sample:
        box = dataset.content_box(list(sample))
    elif trim:
        buffered = list(itertools.islice(incoming, TRIM_SAMPLE))
        if buffered:
            box = dataset.content_box([frame for _t, frame in buffered])
        # The buffered frames go through the same crop as the rest, not around it.
        incoming = itertools.chain(buffered, incoming)
    for t, frame in incoming:
        counts["seen"] += 1
        crop = box if box is not None else (0, 0, frame.shape[1], frame.shape[0])
        x, y, w, h = crop
        fitted, pad = dataset.fit_frame(frame[y : y + h, x : x + w])
        if keep is not None and not keep(fitted, pad):
            counts["dropped"] += 1
            continue
        hash_ = dataset.dhash(fitted)
        if not deduper.is_new(hash_):
            counts["duplicates"] += 1
            continue
        rel = dataset.save_frame(root, source, n, fitted)
        index.add(
            file=rel,
            source=source,
            kind=kind,
            t=None if t is None else float(t),
            hash_=hash_,
            teams_left=round(float(score(fitted, "teams_left")), 4),
            pad=pad,
            crop=crop,
            hud=None if keep is None else True,
        )
        n += 1
        counts["kept"] += 1
    return counts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    what = ap.add_mutually_exclusive_group(required=True)
    what.add_argument("--session", type=Path, help="a recorder session folder")
    what.add_argument("--match", type=Path, help="a raw match-N.h264 file")
    what.add_argument("--video", type=Path, help="a container video")
    ap.add_argument("--source", default=None, help="source name, default the file or folder stem")
    ap.add_argument("--root", type=Path, default=None, help="dataset root")
    ap.add_argument("--again", action="store_true", help="add a source that is already indexed")
    args = ap.parse_args(argv)

    root = args.root if args.root is not None else dataset.default_root()
    target = args.session or args.match or args.video
    jobs: list[tuple[str, str, Callable[[], Iterable[tuple[float | None, np.ndarray]]]]] = []
    try:
        source = dataset.check_source(args.source or target.stem)
        if args.session:
            jobs.append((source, "session", lambda: iter_session(target)))
            # A session keeps its match recordings beside its screenshots; they are the only
            # in-game footage it has, so take them too rather than asking for a second run.
            # A match is a match-N/ folder of JPEGs now; older sessions hold match-N.h264 clips.
            for match in sorted(target.glob("match-*")):
                if match.is_dir():
                    name = dataset.check_source(f"{source}-{match.name}")
                    jobs.append((name, "match", lambda match=match: iter_session(match)))
                elif match.suffix == ".h264":
                    name = dataset.check_source(f"{source}-{match.stem}")
                    jobs.append((name, "match", lambda match=match: iter_h264(match)))
        elif args.match:
            jobs.append((source, "match", lambda: iter_h264(target)))
        else:
            jobs.append((source, "video", lambda: iter_video(target)))
    except ValueError as exc:
        print(exc)
        return 2

    index = dataset.Index(root)
    if not args.again:
        for name, _, _ in jobs:
            if index.has_source(name):
                print(f"{name} is already in the index; pass --again to add it a second time")
                return 2

    for name, kind, make in jobs:
        # Only a container video can carry baked-in bars; sessions and match files are
        # emulator frames, already the right shape. The bars are measured on frames taken from
        # the whole video rather than on its opening seconds, which may be an intro.
        trim = kind == "video"
        counts = add_source(
            root,
            name,
            kind,
            make(),
            trim=trim,
            sample=sample_video(target) if trim else None,
        )
        print(
            f"{name}: seen {counts['seen']}, kept {counts['kept']}, "
            f"duplicates {counts['duplicates']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
