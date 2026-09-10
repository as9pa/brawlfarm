"""One atomic JSON writer, shared by the farm core and the control panel.

Every persisted-state file in this project — status.json, schedule.json,
farmplan.json, the events history, the panel's own state — is written the SAME
way: serialize to a sibling ``*.tmp`` file, then ``os.replace`` it onto the
target. ``os.replace`` is atomic on Windows and POSIX for same-directory paths,
so an out-of-process reader (the watchdog, the control panel, a dashboard)
never catches a half-written file. This module is the single home for that
pattern (it lived hand-rolled in ~10 places).

It lives under ``core/`` so both sides import it without an import cycle — the
core never imports the control panel.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


def atomic_write_json(path, obj, *, indent: int = 2) -> None:
    """Atomically write ``obj`` as JSON to ``path`` (temp file + ``os.replace``).

    Creates parent directories as needed. Encoding is UTF-8 and the default
    ``indent=2`` matches every existing call site; pass ``indent`` to override.
    Not best-effort — it raises on a real I/O error, so callers that must never
    disturb the farm (core/status.py) keep their own try/except wrapper.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, indent=indent), encoding="utf-8")
    os.replace(tmp, path)  # atomic rename on Windows + POSIX (same-dir)
