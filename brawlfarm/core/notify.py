"""
Push notifications for unattended runs.

Ping your phone the moment the farm bot stops, recovers, or crashes — so a 10-hour
overnight session doesn't need babysitting. Two backends; configure whichever you
use via .env (loaded by config):

  Discord webhook:  DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
  ntfy.sh:          NTFY_TOPIC=some-unique-topic   (optional NTFY_SERVER, default https://ntfy.sh)

If neither is set, every call here is a no-op, so the bot runs fine without it.
All network errors are swallowed — a failed alert must never crash or stall the
farm loop.

Entry points:
  notify(title, message, screenshot=None) -> bool
      Low-level send. `screenshot` may be a BGR numpy frame (from adb.screencap())
      or a path; it's attached as a PNG. Returns True if a backend accepted it.
  maybe_alert(kind, fields) -> None
      Convenience used by the data logger: turns a session event (kind + fields)
      into a text alert. Safe to call very often; only ALERT_KINDS actually fire.
"""

from __future__ import annotations

import json
import os
import sys
import time

from brawlfarm.core import config  # noqa: F401  (imported so config's load_dotenv runs)

# Session event kinds worth a phone alert during an unattended run.
# "recalibrate" = the season-rollover tripwire (ops-resilience.md §B): a detector
# is suspected season-blind — advisory, the farm keeps running, a human re-probes.
ALERT_KINDS = {
    "stop",
    "recover",
    "wrong_mode",
    "bad_resolution",
    "crash",
    "recalibrate",
}

# Don't re-fire the same kind within this window. Matters most for "recover",
# which a flapping session can emit many times — each one is a network call.
_COOLDOWN_S = 120.0
_last_alert: dict[str, float] = {}
_warned_send_failed = False

# Titles are kept ASCII on purpose: ntfy puts the title in an HTTP header, which
# requests encodes as latin-1, so an emoji there raises UnicodeEncodeError. The
# visual icon comes from ntfy's "Tags" header instead (see _send_ntfy).
_TITLES = {
    "stop": "Bot stopped",
    "recover": "Bot recovering",
    "wrong_mode": "Wrong mode selected",
    "bad_resolution": "Wrong resolution",
    "crash": "Bot crashed",
    "recalibrate": "Recalibration needed",
}


def _ascii(s: str) -> str:
    """Make a value safe for an HTTP header (requests encodes headers as latin-1).
    We drop to ASCII, replacing anything outside it — strictly safer than latin-1."""
    return s.encode("ascii", "replace").decode("ascii")


def _discord_url() -> str:
    return os.environ.get("DISCORD_WEBHOOK_URL", "").strip()


def _ntfy() -> tuple[str, str]:
    server = os.environ.get("NTFY_SERVER", "https://ntfy.sh").strip().rstrip("/")
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    return server, topic


def configured() -> bool:
    """True if at least one notification backend is set up in the environment."""
    return bool(_discord_url()) or bool(_ntfy()[1])


def _encode_png(screenshot) -> bytes | None:
    """Accept a BGR numpy frame or a path; return PNG bytes (or None on failure)."""
    if screenshot is None:
        return None
    try:
        if isinstance(screenshot, (str, os.PathLike)):
            with open(screenshot, "rb") as f:
                return f.read()
        import cv2  # local import: only needed when actually attaching an image

        ok, buf = cv2.imencode(".png", screenshot)
        return buf.tobytes() if ok else None
    except Exception:
        return None


def notify(title: str, message: str, screenshot=None) -> bool:
    """Send title/message (+ optional screenshot) to every configured backend.
    Returns True if any backend accepted it. Never raises."""
    if not configured():
        return False
    try:
        import requests
    except Exception:
        return False

    png = _encode_png(screenshot)
    sent = False
    url = _discord_url()
    if url:
        sent |= _send_discord(requests, url, title, message, png)
    server, topic = _ntfy()
    if topic:
        sent |= _send_ntfy(requests, server, topic, title, message, png)
    return sent


def _send_discord(requests, url, title, message, png) -> bool:
    content = f"**{title}**\n{message}"[:1900]
    try:
        if png is not None:
            r = requests.post(
                url,
                data={"payload_json": json.dumps({"content": content})},
                files={"file": ("screen.png", png, "image/png")},
                timeout=10,
            )
        else:
            r = requests.post(url, json={"content": content}, timeout=10)
        return r.status_code < 300
    except Exception:
        return False


def _send_ntfy(requests, server, topic, title, message, png) -> bool:
    url = f"{server}/{topic}"
    headers = {"Title": _ascii(title), "Priority": "high", "Tags": "warning"}
    try:
        if png is not None:
            # ntfy attaches the request body as a file when Filename is set; the
            # human text rides along in the Message header (also latin-1-only).
            headers["Filename"] = "screen.png"
            headers["Message"] = _ascii(message)
            r = requests.put(url, data=png, headers=headers, timeout=10)
        else:
            r = requests.post(
                url, data=message.encode("utf-8"), headers=headers, timeout=10
            )
        return r.status_code < 300
    except Exception:
        return False


def maybe_alert(kind: str, fields: dict) -> None:
    """Fire a text alert for an alert-worthy session event; no-op otherwise.
    Called from DataLog.event(), so it must be cheap and never raise."""
    global _warned_send_failed
    if kind not in ALERT_KINDS or not configured():
        return
    now = time.monotonic()
    last = _last_alert.get(kind)
    if last is not None and now - last < _COOLDOWN_S:
        return  # throttle repeats of the same kind (esp. recover loops)
    _last_alert[kind] = now
    detail = ", ".join(f"{k}={v}" for k, v in fields.items() if v is not None)
    title = _TITLES.get(kind, f"Bot: {kind}")
    ok = notify(title, detail or kind)
    if not ok and not _warned_send_failed:
        # A configured-but-failing backend (typo'd webhook / wrong topic) would
        # otherwise stay silent forever; surface it once.
        _warned_send_failed = True
        print(
            "[notify] alert send failed — check DISCORD_WEBHOOK_URL / NTFY_TOPIC",
            file=sys.stderr,
        )
