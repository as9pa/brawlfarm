"""Turn an owner-supplied list of YouTube URLs into dataset frames.

Each line is validated against one fixed pattern and only the 11 character video id survives it:
the URL handed to yt-dlp is rebuilt from that id and the download is named after it, so nothing
the owner typed reaches the subprocess or a path. Downloads are kept under the dataset root so a
video can be re-extracted later without fetching it again.

    uv run python tools/play/ingest_youtube.py urls.txt
    uv run python tools/play/ingest_youtube.py urls.txt --root D:/play-data --keep-going
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

from tools.play import dataset, frames

URL_RE = re.compile(
    r"^https://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([A-Za-z0-9_-]{11})(?:[&?].*)?$"
)
FORMAT = "bv*[height<=1080][ext=mp4]/bv*[height<=1080]/b[height<=1080]"


def read_urls(path: Path) -> list[tuple[str, str]]:
    """Read the URL list into (video id, canonical url) pairs.

    Blank lines and lines starting with # are skipped. Anything else that is not a YouTube
    video URL stops the whole run: a typo that silently downloaded nothing would be worse
    than a refusal naming the line.
    """
    out: list[tuple[str, str]] = []
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = URL_RE.match(line)
        if match is None:
            raise ValueError(f"line {number} is not a YouTube video URL: {line!r}")
        video_id = match.group(1)
        out.append((video_id, f"https://www.youtube.com/watch?v={video_id}"))
    return out


def download(video_id: str, url: str, videos: Path, *, run=subprocess.run) -> Path:
    """Fetch one video at up to 1080p into `videos/<id>.mp4` and return its path.

    `run` is a parameter so the tests can record the argument list without starting yt-dlp.
    """
    videos = Path(videos)
    out = videos / f"{video_id}.mp4"
    if out.exists():
        print(f"{out.name} is already downloaded")
        return out
    videos.mkdir(parents=True, exist_ok=True)
    run(
        [
            sys.executable,
            "-m",
            "yt_dlp",
            "--no-playlist",
            "--no-progress",
            "-f",
            FORMAT,
            "--merge-output-format",
            "mp4",
            "-o",
            str(videos / f"{video_id}.%(ext)s"),
            # An id may start with "-", which yt-dlp would read as an option, so the URL is
            # last and behind the end-of-options marker.
            "--",
            url,
        ],
        check=True,
    )
    if not out.exists():
        raise RuntimeError(f"yt-dlp left no {out.name} in {videos}")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("urls", type=Path, help="a text file of YouTube URLs, one per line")
    ap.add_argument("--root", type=Path, default=None, help="dataset root")
    ap.add_argument("--keep-going", action="store_true", help="carry on after a failed download")
    args = ap.parse_args(argv)

    root = args.root if args.root is not None else dataset.default_root()
    try:
        urls = read_urls(args.urls)
    except (OSError, ValueError) as exc:
        print(exc)
        return 2

    videos = root / "videos"
    kept = skipped = failed = 0
    for video_id, url in urls:
        source = dataset.check_source(f"yt-{video_id}")
        # Re-read per video: add_source appends to the same index, so a repeated id in the
        # list is caught on its second turn as well.
        if dataset.Index(root).has_source(source):
            print(f"{source} is already in the index; skipping")
            skipped += 1
            continue
        try:
            path = download(video_id, url, videos)
        except (RuntimeError, subprocess.CalledProcessError) as exc:
            print(f"{source}: {exc}")
            failed += 1
            if not args.keep_going:
                return 1
            continue
        # Downloads are the footage with baked-in black bars, so they are measured and cropped.
        # The measurement reads frames from the whole video, never just past the intro.
        counts = frames.add_source(
            root,
            source,
            "youtube",
            frames.iter_video(path),
            trim=True,
            sample=frames.sample_video(path),
        )
        print(
            f"{source}: seen {counts['seen']}, kept {counts['kept']}, "
            f"duplicates {counts['duplicates']}"
        )
        kept += counts["kept"]
    print(f"{len(urls)} videos: {kept} frames kept, {skipped} already indexed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
