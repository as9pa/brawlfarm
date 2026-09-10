"""Per-instance status heartbeat.

Each farm process writes a small ``status.json`` into its data dir (``BRAWL_DATA_DIR``,
e.g. ``data/<account>/``) so an OUT-OF-PROCESS reader — the control panel, a watchdog,
a dashboard — can see what every instance is doing without touching the process.

Written ATOMICALLY (temp file + ``os.replace``) so a reader never catches a half-written
file, and entirely best-effort: a status-write failure must never disturb the farm, so
everything is wrapped and swallowed.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from brawlfarm.core.jsonio import atomic_write_json


def write_status(data_dir, fields: dict) -> None:
    """Atomically write ``status.json`` into ``data_dir`` with ``fields`` (plus a ``ts``).
    Best-effort: any error is swallowed (status is observability, never load-bearing)."""
    try:
        payload = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), **fields}
        atomic_write_json(Path(data_dir) / "status.json", payload)
    except Exception:
        pass


def read_status(data_dir) -> dict | None:
    """Read a farm's ``status.json`` (for the control panel / watchdog). Returns the parsed
    dict, or None if it's missing/unreadable. Adds ``age_s`` = seconds since its ``ts`` so a
    reader can tell a live heartbeat from a stale one (a dead/hung farm stops updating it)."""
    try:
        path = Path(data_dir) / "status.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        try:
            stamped = time.mktime(time.strptime(data["ts"], "%Y-%m-%dT%H:%M:%S"))
            data["age_s"] = round(time.time() - stamped, 1)
        except Exception:
            data["age_s"] = None
        return data
    except Exception:
        return None
