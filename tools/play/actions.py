"""Per-frame action labels for one dataset source: where the stick is pushed and where the shot
points, plus the button states, as `frames/<source>/actions.jsonl`.

A source is learned before it is read. The joystick floats, so there is no rest position: a push
is the knob measured from the small dark dot at the centre of its ring, found per frame, over the
ring radius, which is learned once over the whole source from the knob the source draws. A HUD
frame with no move vector is usually a stick sitting still, its own knob covering the dot; that
is what the label not being there means, and it is not the same as no joystick at all. The attack
disc has no rest position on paper either, so its home is the fullest bin of where it actually
sat.

What cannot be read honestly is rejected per channel rather than guessed at: footage whose
joystick a creator's webcam covers keeps its aim labels and loses its move labels, and the reason
is printed and written into the meta file. There is no "attack pressed" label at all: a tap is
invisible at 2 frames per second, only aiming is.

    uv run python tools/play/actions.py
    uv run python tools/play/actions.py --root D:/play-data --source yt-AAAAAAAAAAA
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from tools.play import dataset, hud

LEARN_SAMPLE = 200  # frames read to learn a source, spread evenly over it
MIN_HUD_FRAMES = 100  # fewer HUD frames than this and nothing about the source is trusted
HOME_BIN = 6  # px, the attack home is the fullest bin of this size
HOME_SHARE = 0.30  # the fullest bin must hold this share of the attack discs
ATTACK_RATE = 0.60  # attack discs per HUD frame, below this the aim channel is rejected
KNOB_RATE = 0.80  # knobs per HUD frame, below this the move channel is rejected
ORIGIN_RATE = 0.30  # origins per knob frame; a clean source measures about 0.8, and the knob
# hides the dot whenever the stick is near its centre
AIM_RADIUS = 0.198  # share of the box height; the p95 drag distance measured in the spike
AIMING_MIN = 0.2  # share of AIM_RADIUS past which the disc counts as dragged
BOX_SAMPLE = 24  # frames measured for the content box, spread evenly over the source


@dataclass(frozen=True)
class Clip:
    """What one source taught about itself, and what of it may be labelled."""

    box: tuple[int, int, int, int]
    hud_frames: int
    home: tuple[float, float] | None  # attack home, frame pixels
    ring_radius: float | None  # the ring the stick is clamped to, frame pixels
    channels: dict[str, str]  # "move" and "aim": "ok" or the reason it was rejected


def spread(items: Sequence, n: int) -> list:
    """n items evenly over the sequence, the first and the last among them; all if there are
    fewer. A sample of a source has to reach its end: the HUD of the last match is as much the
    source's HUD as the first one's."""
    if n <= 0 or not items:
        return []
    if len(items) <= n:
        return list(items)
    if n == 1:
        return [items[0]]
    last = len(items) - 1
    return [items[round(i * last / (n - 1))] for i in range(n)]


def _home(discs: Sequence[tuple[float, float]]) -> tuple[float, float] | None:
    """The mean of the fullest HOME_BIN bin of attack centres, or None when none of them holds
    HOME_SHARE of the discs: a disc that is never in the same place twice has no home to
    measure a drag from."""
    bins: dict[tuple[int, int], list[tuple[float, float]]] = {}
    for x, y in discs:
        bins.setdefault((int(x // HOME_BIN), int(y // HOME_BIN)), []).append((x, y))
    fullest = max(bins.values(), key=len)
    if len(fullest) < HOME_SHARE * len(discs):
        return None
    return statistics.fmean(x for x, _y in fullest), statistics.fmean(y for _x, y in fullest)


def learn(
    frames: Sequence[np.ndarray],
    box: tuple[int, int, int, int],
    *,
    min_frames: int = MIN_HUD_FRAMES,
) -> Clip:
    """Read a sample of one source and decide what may be labelled on it.

    One pass, because the frames arrive one at a time: the origin dot of a knob frame is looked
    for while that frame is still in hand, not on a second walk over frames nobody kept.
    """
    hud_frames = 0
    discs: list[tuple[float, float]] = []
    knobs: list[float] = []
    origins = 0
    for frame in frames:
        if frame is None:  # a frame the index outlived teaches the source nothing
            continue
        found = hud.find(frame, box)
        if not hud.visible(found):
            continue
        hud_frames += 1
        if "attack" in found:
            discs.append((found["attack"].x, found["attack"].y))
        if "knob" in found:
            knobs.append(found["knob"].r)
            if hud.origin(frame, box, found["knob"]) is not None:
                origins += 1

    if hud_frames < min_frames:
        reason = f"too few HUD frames ({hud_frames})"
        return Clip(box, hud_frames, None, None, {"move": reason, "aim": reason})

    home = None
    attack_rate = len(discs) / hud_frames
    if attack_rate < ATTACK_RATE:
        aim = f"attack disc in {attack_rate:.2f} of HUD frames"
    else:
        home = _home(discs)
        aim = "ok" if home is not None else "no stable attack home"

    ring_radius = None
    knob_rate = len(knobs) / hud_frames
    if knob_rate < KNOB_RATE:
        # the covered joystick: a creator's webcam or overlay sits where the stick is
        move = f"joystick knob in {knob_rate:.2f} of HUD frames"
    else:
        origin_rate = origins / len(knobs)
        if origin_rate < ORIGIN_RATE:
            move = f"joystick origin in {origin_rate:.2f} of knob frames"
        else:
            # The HUD scales as one piece, so the ring follows the knob the source draws.
            ring_radius = hud.RING_RATIO * statistics.median(knobs)
            move = "ok"
    return Clip(box, hud_frames, home, ring_radius, {"move": move, "aim": aim})


def _row(seen: bool) -> dict:
    """An action row with nothing read off it yet."""
    return {
        "hud": seen,
        "move": None,
        "aim": None,
        "aiming": None,
        "super": None,
        "gadget": None,
        "hyper": None,
    }


def _vector(dx: float, dy: float, scale: float) -> list[float]:
    """A pixel offset as a -1 to 1 pair, per axis. y grows downward, as it does in the image."""
    return [round(max(-1.0, min(1.0, value / scale)), 3) for value in (dx, dy)]


def read(frame: np.ndarray, clip: Clip) -> dict:
    """One frame's actions, as far as the clip's channels allow them to be read.

    There is no "attack pressed" key. A plain tap lasts less than the half second between two
    frames, so a still cannot tell a pressed attack from a resting one; what is observable is
    aiming, the disc dragged away from its home, and that is what `aim` carries.
    """
    found = hud.find(frame, clip.box)
    row = _row(hud.visible(found))
    if not row["hud"]:
        return row
    for cls in ("super", "gadget", "hyper"):
        if cls in found:
            row[cls] = found[cls].state
    if clip.channels.get("aim") == "ok" and clip.home is not None and "attack" in found:
        disc = found["attack"]
        row["aim"] = _vector(disc.x - clip.home[0], disc.y - clip.home[1], AIM_RADIUS * clip.box[3])
        row["aiming"] = math.hypot(*row["aim"]) >= AIMING_MIN
    if clip.channels.get("move") == "ok" and clip.ring_radius is not None and "knob" in found:
        knob = found["knob"]
        dot = hud.origin(frame, clip.box, knob)
        if dot is not None:
            row["move"] = _vector(knob.x - dot.x, knob.y - dot.y, clip.ring_radius)
    return row


def _read_frame(path: Path) -> np.ndarray | None:
    """imdecode, not imread: OpenCV cannot read a non-ASCII path on Windows."""
    if not path.exists():
        return None
    return cv2.imdecode(np.frombuffer(path.read_bytes(), np.uint8), cv2.IMREAD_COLOR)


class _Decoded(Sequence):
    """The frames behind a list of paths, decoded one at a time as they are walked over.

    A frame is 4.3 MB, so a learning sample handed over as a list would cost most of a gigabyte
    for nothing: learn keeps what it measured, never the picture.
    """

    def __init__(self, paths: Sequence[Path]) -> None:
        self._paths = list(paths)

    def __len__(self) -> int:
        return len(self._paths)

    def __getitem__(self, index):
        return _read_frame(self._paths[index])


def run(root: Path, source: str, *, min_frames: int = MIN_HUD_FRAMES) -> dict:
    """Label every frame of one source. Returns the counts and the channel verdicts.

    Writes `frames/<source>/actions.jsonl`, one row per index row and in index order, and
    `frames/<source>/actions.meta.json` beside it with what the source was learned to be. The
    rows go to a `.tmp` first and are renamed over the old file, so a run interrupted halfway
    leaves the previous labels rather than half of the new ones.
    """
    dataset.check_source(source)
    root = Path(root)
    rows = [row for row in dataset.index_rows(root) if row["source"] == source]
    if not rows:
        raise ValueError(f"{source} is not in the index")

    paths = [root / row["file"] for row in rows]
    sample = [frame for frame in _Decoded(spread(paths, BOX_SAMPLE)) if frame is not None]
    if not sample:
        raise ValueError(f"{source} has no readable frames")
    box = dataset.content_box(sample)
    clip = learn(_Decoded(spread(paths, LEARN_SAMPLE)), box, min_frames=min_frames)

    counts = {"frames": 0, "hud": 0, "move": 0, "aim": 0, "aiming": 0, "unreadable": 0}
    folder = root / "frames" / source
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / "actions.jsonl"
    tmp = out.with_name(out.name + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as handle:
        for row, path in zip(rows, paths):
            frame = _read_frame(path)
            if frame is None:
                # The index outlives the files, so a deleted frame is a row of nothing, not fatal.
                counts["unreadable"] += 1
                action = _row(False)
            else:
                action = read(frame, clip)
            counts["frames"] += 1
            counts["hud"] += int(action["hud"])
            counts["move"] += int(action["move"] is not None)
            counts["aim"] += int(action["aim"] is not None)
            counts["aiming"] += int(bool(action["aiming"]))
            handle.write(json.dumps({"file": row["file"], "t": row.get("t"), **action}) + "\n")
    tmp.replace(out)

    meta = {
        "box": list(box),
        "hud_frames": clip.hud_frames,
        "home": None if clip.home is None else [round(value, 3) for value in clip.home],
        "ring_radius": None if clip.ring_radius is None else round(clip.ring_radius, 3),
        "channels": clip.channels,
        "learn_sample": LEARN_SAMPLE,
        "min_hud_frames": min_frames,
        "home_bin": HOME_BIN,
        "home_share": HOME_SHARE,
        "attack_rate": ATTACK_RATE,
        "knob_rate": KNOB_RATE,
        "origin_rate": ORIGIN_RATE,
        "aim_radius": AIM_RADIUS,
        "aiming_min": AIMING_MIN,
        "counts": counts,
    }
    (folder / "actions.meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return {**counts, "channels": clip.channels}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--root", type=Path, default=None, help="dataset root")
    ap.add_argument(
        "--source",
        action="append",
        default=None,
        metavar="NAME",
        help="label only this source; repeat for more",
    )
    args = ap.parse_args(argv)

    root = args.root if args.root is not None else dataset.default_root()
    if args.source:
        wanted = list(args.source)
    else:
        wanted = sorted(
            {row["source"] for row in dataset.index_rows(root) if row.get("kind") == "youtube"}
        )

    whole = 0
    rejected = 0
    for name in wanted:
        try:
            counts = run(root, name, min_frames=MIN_HUD_FRAMES)
        except ValueError as error:
            print(error)
            return 2
        line = (
            f"{name}: {counts['frames']} frames, HUD on {counts['hud']}, "
            f"move on {counts['move']}, aim on {counts['aim']} (aiming {counts['aiming']})"
        )
        if counts["unreadable"]:
            line += f", {counts['unreadable']} unreadable"
        print(line)
        bad = {channel: why for channel, why in counts["channels"].items() if why != "ok"}
        for channel, why in bad.items():
            print(f"{name}: {channel} rejected, {why}")
        if bad:
            rejected += 1
        else:
            whole += 1
    print(f"{len(wanted)} sources: {whole} with every channel, {rejected} with a rejected channel")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
