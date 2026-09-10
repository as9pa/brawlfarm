"""Finding adb and the BlueStacks instances the setup wizard offers.

Parsing plus one adb call: bluestacks.conf names the instances and their ADB ports,
`adb devices` says which of them are answering. Nothing here writes anything.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from brawlfarm import settings as S
from brawlfarm.setup.checks import Runner, decode, first_line, run_adb, serial

DEFAULT_ADB = S.DEFAULT_ADB_PATH
CONF_NAME = "bluestacks.conf"

# bluestacks.conf is flat `key="value"` lines. Only the five keys the wizard shows are
# read, and the name group is already narrower than a folder name has to be.
_CONF_RE = re.compile(
    r'^bst\.instance\.([A-Za-z0-9_-]+)\.(adb_port|display_name|fb_width|fb_height|dpi)="(.*)"$'
)
_DEVICE_RE = re.compile(r"^127\.0\.0\.1:(\d+)\s+device\s*$")


@dataclass(frozen=True)
class Discovered:
    """One row in the wizard's Instances step, straight from bluestacks.conf."""

    name: str
    display_name: str
    adb_port: int | None
    width: int | None
    height: int | None
    dpi: int | None


def bluestacks_conf_path() -> Path:
    """%PROGRAMDATA%\\BlueStacks_nxt\\bluestacks.conf, where BlueStacks 5 keeps the
    instance table."""
    root = os.environ.get("PROGRAMDATA", "").strip() or r"C:\ProgramData"
    return Path(root) / "BlueStacks_nxt" / CONF_NAME


def find_adb(configured: str | None = None) -> str | None:
    """The adb to use: what the user configured if it is really there, else the one
    BlueStacks ships, else whatever is on PATH. None when nothing is installed."""
    for candidate in (configured, DEFAULT_ADB):
        if candidate and Path(candidate).exists():
            return str(candidate)
    return shutil.which("adb")


def parse_bluestacks_conf(text: str) -> list[Discovered]:
    """One Discovered per `bst.instance.<name>.*` block, sorted by name.

    A name that could not be a folder (INSTANCE_NAME_RE) is skipped: the wizard writes it
    straight into config.toml and creates <home>/instances/<name>/ from it.
    """
    fields: dict[str, dict[str, str]] = {}
    for line in (text or "").splitlines():
        m = _CONF_RE.match(line.strip())
        if not m:
            continue
        name, key, value = m.group(1), m.group(2), m.group(3)
        if not S.INSTANCE_NAME_RE.match(name):
            continue
        fields.setdefault(name, {})[key] = value
    out: list[Discovered] = []
    for name in sorted(fields):
        f = fields[name]
        out.append(
            Discovered(
                name=name,
                display_name=f.get("display_name") or name,
                adb_port=_int_or_none(f.get("adb_port")),
                width=_int_or_none(f.get("fb_width")),
                height=_int_or_none(f.get("fb_height")),
                dpi=_int_or_none(f.get("dpi")),
            )
        )
    return out


def parse_devices(text: str) -> set[int]:
    """The local ports `adb devices` reports as `device`. An `offline` or `unauthorized`
    row is not one of them."""
    ports: set[int] = set()
    for line in (text or "").splitlines():
        m = _DEVICE_RE.match(line.strip())
        if m:
            ports.add(int(m.group(1)))
    return ports


def scan(
    adb_path: str | None, conf_path: Path | None = None, *, runner: Runner | None = None
) -> dict:
    """What the wizard's Instances step shows: where adb is, whether bluestacks.conf was
    found, and a row per instance with its port, display size and whether it answers.

    Blocking (it shells out to adb), so route handlers call it through asyncio.to_thread.
    """
    path = Path(conf_path) if conf_path is not None else bluestacks_conf_path()
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        conf_found = True
    except OSError:
        text, conf_found = "", False
    online = _online_ports(adb_path, runner) if adb_path else set()
    return {
        "adb_path": str(adb_path) if adb_path else None,
        "adb_found": bool(adb_path),
        "conf_found": conf_found,
        "instances": [
            {**asdict(d), "online": d.adb_port is not None and d.adb_port in online}
            for d in parse_bluestacks_conf(text)
        ],
    }


def probe_port(
    adb_path: str, port: int, *, timeout_s: float = 15.0, runner: Runner | None = None
) -> dict:
    """Can the panel actually talk to this instance? `adb connect`, then `adb get-state`.

    Fails CLOSED, unlike supervisor.process.instance_online: the wizard is asking the user
    to trust this row, so an unanswered probe must read as "not working", not as
    "probably fine". The supervisor's probe fails open for the opposite reason -- a broken
    probe there would strand a healthy instance in backoff.
    """
    dev = serial(port)
    try:
        connected = run_adb(adb_path, ["connect", dev], timeout_s=timeout_s, runner=runner)
        state = run_adb(adb_path, ["-s", dev, "get-state"], timeout_s=timeout_s, runner=runner)
    except subprocess.TimeoutExpired:
        return {"ok": False, "detail": f"adb timed out talking to {dev}"}
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ok": False, "detail": f"adb failed for {dev}: {exc}"}
    if decode(state.stdout).strip() == "device":
        return {"ok": True, "detail": f"{dev} answered"}
    reason = (
        first_line(state.stderr)
        or first_line(state.stdout)
        or first_line(connected.stdout)
        or "no answer"
    )
    return {"ok": False, "detail": f"{dev}: {reason}"}


def _online_ports(adb_path: str, runner: Runner | None) -> set[int]:
    try:
        done = run_adb(adb_path, ["devices"], runner=runner)
    except (OSError, subprocess.SubprocessError):
        return set()
    if done.returncode != 0:
        return set()
    return parse_devices(decode(done.stdout))


def _int_or_none(value: str | None) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None
