"""Play mode: the opt-in in-match brain.

Nothing in this file imports PyAV or onnxruntime. The core loop and the API import this
package to ask ``available()`` and must keep working when the play extra is absent.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

# The scrcpy 4.1 server (Apache-2.0, license text in LICENSE.scrcpy next to it). It is pushed
# onto the instance by brawlfarm.play.stream and streams the display back over adb; it sends
# nothing in.
SERVER_JAR = Path(__file__).resolve().parent / "scrcpy-server"
SERVER_VERSION = "4.1"
SERVER_JAR_SIZE = 733706


def available() -> bool:
    """True when the play extra is installed (PyAV imports), without importing it."""
    return importlib.util.find_spec("av") is not None
