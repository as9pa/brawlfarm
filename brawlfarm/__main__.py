"""Console entry point. The control panel arrives in phase 3; for now this reports the version."""

from __future__ import annotations

import sys

from brawlfarm import __version__


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args and args[0] in {"-V", "--version"}:
        print(f"brawlfarm {__version__}")
        return 0
    print(f"brawlfarm {__version__}: the control panel is not built yet. Run the worker with:")
    print("  uv run python -m brawlfarm.worker --help")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
