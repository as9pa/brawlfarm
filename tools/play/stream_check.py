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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--seconds", type=float, default=60.0)
    ap.add_argument("--record", type=Path, default=None)
    args = ap.parse_args(argv)

    adb.connect()
    hp = _hd_player()
    idle = hp.cpu_percent(interval=3.0) if hp else float("nan")

    s = stream.Stream(record=args.record)
    s.start()
    print(f"instance on adb port {config.ADB_PORT}")
    print(f"stream up on port {s.port}; sampling {args.seconds:g} s")
    if hp:
        hp.cpu_percent(None)
    psutil.cpu_percent(None)
    gaps: list[float] = []
    last = s.frames
    last_t = time.monotonic()
    end = last_t + args.seconds
    drift_rows: list[tuple[str, float, float]] = []
    try:
        while time.monotonic() < end:
            time.sleep(0.005)
            if s.frames != last:
                now = time.monotonic()
                gaps.append((now - last_t) * 1000)
                last, last_t = s.frames, now
            if s.error:
                print("stream error:", s.error)
                return 1
            if not drift_rows and s.frames > 30:
                shot = adb.screencap()
                frame, _age = s.latest()
                if frame is not None:
                    for name in vision.TEMPLATE_NAMES:
                        drift_rows.append(
                            (
                                name,
                                float(vision.score(shot, name)),
                                float(vision.score(frame, name)),
                            )
                        )
    finally:
        busy = hp.cpu_percent(None) if hp else float("nan")
        host = psutil.cpu_percent(None)
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
