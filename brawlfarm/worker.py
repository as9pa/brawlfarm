"""
Per-instance farm worker: ONE process drives ONE BlueStacks instance.

Normally started by the supervisor (never two workers on the same instance), but it
runs standalone too:
    uv run python -m brawlfarm.worker --max-games 2 --debug-shots  # short supervised run
    uv run python -m brawlfarm.worker                    # farm until stopped (Ctrl-C)
    uv run python -m brawlfarm.worker --max-minutes 480  # farm for 8 hours then stop

The worker farms whatever mode is selected in the menu, but refuses to play and stops
if the menu is not on Trio Showdown (so it never grinds the wrong mode).
"""

import argparse
import sys

from brawlfarm.core.controller import Controller


def main() -> int:
    ap = argparse.ArgumentParser(description="Brawl Stars Trio Showdown auto-farm bot")
    ap.add_argument("--max-games", type=int, default=None, help="stop after N matches")
    ap.add_argument(
        "--max-minutes", type=float, default=None, help="stop after N minutes"
    )
    ap.add_argument(
        "--debug-shots",
        action="store_true",
        help="save a screenshot on each phase change to captures/run/",
    )
    ap.add_argument(
        "--select-brawler",
        action="store_true",
        help="at startup, select the lowest-trophy brawler (sort Least Trophies, "
        "filters off), then farm",
    )
    ap.add_argument(
        "--dnd",
        action="store_true",
        help="at startup, set the in-game team-invite mutes (DND) so invites "
        "can't pop a farm-blocking modal, then farm",
    )
    ap.add_argument(
        "--startup-all",
        action="store_true",
        help="run ALL startup tasks at once (DND + brawler select); same as passing "
        "those two flags. Mega-quest activation is always on regardless.",
    )
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8")  # player names contain unicode
    except Exception:
        pass

    # --startup-all is a convenience that turns on every startup task at once.
    startup = args.startup_all
    Controller(
        max_games=args.max_games,
        max_minutes=args.max_minutes,
        debug_shots=args.debug_shots,
        select_brawler=args.select_brawler or startup,
        dnd=args.dnd or startup,
    ).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
