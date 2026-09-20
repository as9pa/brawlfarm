"""Live pass for the play stream. Read-only against the configured instance: streams for N
seconds, reports fps, frame gaps and CPU, and scores every template on one screencap and on
the stream frame taken at the same moment so the drift between the two capture paths is a
number in the pull request body.

    uv run python tools/play/stream_check.py --seconds 60
    uv run python tools/play/stream_check.py --seconds 20 --record out.h264
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

import psutil

from brawlfarm.core import adb, config, vision
from brawlfarm.play import stream


def _hd_player() -> psutil.Process | None:
    for p in psutil.process_iter(["name"]):
        if p.info["name"] == "HD-Player.exe":
            return p
    return None


def _cpu(hp: psutil.Process | None, interval: float | None = None) -> float:
    """HD-Player's CPU percent, or nan when it is gone. It can exit mid-run, and a reading
    that raises must never cost us the stream teardown."""
    if hp is None:
        return float("nan")
    try:
        return hp.cpu_percent(interval=interval)
    except psutil.Error:
        return float("nan")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--seconds", type=float, default=60.0)
    ap.add_argument("--record", type=Path, default=None)
    args = ap.parse_args(argv)

    adb.connect()
    hp = _hd_player()
    idle = _cpu(hp, interval=3.0)

    s = stream.Stream(record=args.record)
    gaps: list[float] = []
    drift_rows: list[tuple[str, float, float]] = []
    drift_tried = False
    s.start()
    # Everything past here runs under the try: once the stream is up, no failure may skip
    # stop(), or the encoder keeps costing the instance a core.
    try:
        print(f"instance on adb port {config.ADB_PORT}")
        print(f"stream up on port {s.port}; sampling {args.seconds:g} s")
        _cpu(hp)
        psutil.cpu_percent(None)
        last = s.frames
        last_t = time.monotonic()
        end = last_t + args.seconds
        while time.monotonic() < end:
            time.sleep(0.005)
            if s.frames != last:
                now = time.monotonic()
                gaps.append((now - last_t) * 1000)
                last, last_t = s.frames, now
            if s.error:
                print("stream error:", s.error)
                return 1
            if not drift_tried and s.frames > 30:
                # One attempt only, even when it yields no rows: a screen that goes static
                # stops the encoder, so latest() stays stale and retrying would screencap
                # every 5 ms.
                drift_tried = True
                shot = adb.screencap()
                frame, _age = s.latest()
                if frame is None:
                    print("no fresh stream frame for the drift table (static screen)")
                else:
                    for name in vision.TEMPLATE_NAMES:
                        drift_rows.append(
                            (
                                name,
                                float(vision.score(shot, name)),
                                float(vision.score(frame, name)),
                            )
                        )
                # The screencap and the scoring stall this loop for most of a second; start
                # the gap clock again so the stall does not read as a stream gap.
                last, last_t = s.frames, time.monotonic()
    finally:
        # Read the CPU while the encoder still runs, so the number is the stream's cost; the
        # inner finally keeps the teardown unconditional.
        try:
            busy = _cpu(hp)
            host = psutil.cpu_percent(None)
        finally:
            s.stop()

    span = max(1e-6, (last_t - (s.started_at or last_t)))
    print(f"frames {s.frames} in {span:.1f} s: {s.frames / span:.1f} fps")
    if gaps:
        gaps.sort()
        p95 = gaps[int(len(gaps) * 0.95)]
        print(f"gap ms p50 {statistics.median(gaps):.1f} p95 {p95:.1f} max {gaps[-1]:.0f}")
    print(
        f"HD-Player cpu % of one core: idle {idle:.0f}, streaming {busy:.0f}; "
        f"host all cores {host:.0f}"
    )
    if drift_rows:
        print("template score, screencap vs stream frame (same moment):")
        worst = 0.0
        for name, a, b in drift_rows:
            worst = max(worst, abs(a - b))
            print(f"  {name:16s} {a:.4f} {b:.4f} {b - a:+.4f}")
        print(f"largest drift {worst:.4f}")
    if args.record is not None:
        print(f"recorded {args.record} ({args.record.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
