"""
Push notifications for unattended runs.

Ping your phone the moment the farm bot stops, recovers, or crashes — so a 10-hour
overnight session doesn't need babysitting. Two backends; configure whichever you
use via .env (loaded by config):

  Webhook:  BRAWL_WEBHOOK_URL=https://...    (legacy DISCORD_WEBHOOK_URL still honoured)
  ntfy.sh:  NTFY_TOPIC=some-unique-topic     (optional NTFY_SERVER, default https://ntfy.sh)

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
# "offline" = the supervisor's own alert: an instance stopped answering health checks.
ALERT_KINDS = {
    "stop",
    "recover",
    "wrong_mode",
    "bad_resolution",
    "crash",
    "recalibrate",
    "offline",
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
    "offline": "Instance offline",
}


def _ascii(s: str) -> str:
    """Make a value safe for an HTTP header (requests encodes headers as latin-1).
    We drop to ASCII, replacing anything outside it — strictly safer than latin-1."""
    return s.encode("ascii", "replace").decode("ascii")


# Explicit settings from the control panel; None means "use the environment".
_overrides: dict[str, object] = {}


def configure(
    *,
    webhook_url: str | None = None,
    ntfy_server: str | None = None,
    ntfy_topic: str | None = None,
    events: list[str] | None = None,
) -> None:
    """Set the backends from settings. Workers keep reading the environment the
    supervisor hands them; the supervisor process itself calls this once."""
    for key, value in (
        ("webhook_url", webhook_url),
        ("ntfy_server", ntfy_server),
        ("ntfy_topic", ntfy_topic),
        ("events", events),
    ):
        if value is None:
            _overrides.pop(key, None)
        else:
            _overrides[key] = value


def _webhook_url() -> str:
    if "webhook_url" in _overrides:
        return str(_overrides["webhook_url"]).strip()
    return (
        os.environ.get("BRAWL_WEBHOOK_URL", "") or os.environ.get("DISCORD_WEBHOOK_URL", "")
    ).strip()


def _ntfy() -> tuple[str, str]:
    server = str(_overrides.get("ntfy_server", os.environ.get("NTFY_SERVER", "https://ntfy.sh")))
    topic = str(_overrides.get("ntfy_topic", os.environ.get("NTFY_TOPIC", "")))
    return server.strip().rstrip("/"), topic.strip()


def enabled_events() -> frozenset[str]:
    """Alert kinds that may be sent: configure(events=...), else BRAWL_NOTIFY_EVENTS, else all."""
    if "events" in _overrides:
        return frozenset(str(e).strip() for e in _overrides["events"] if str(e).strip())
    raw = os.environ.get("BRAWL_NOTIFY_EVENTS", "").strip()
    if not raw:
        return frozenset(ALERT_KINDS)
    return frozenset(e.strip() for e in raw.split(",") if e.strip())


def configured() -> bool:
    """True if at least one notification backend is set up."""
    return bool(_webhook_url()) or bool(_ntfy()[1])


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
    url = _webhook_url()
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
            r = requests.post(url, data=message.encode("utf-8"), headers=headers, timeout=10)
        return r.status_code < 300
    except Exception:
        return False


def maybe_alert(kind: str, fields: dict) -> None:
    """Fire a text alert for an alert-worthy session event; no-op otherwise.
    Called from DataLog.event(), so it must be cheap and never raise."""
    global _warned_send_failed
    if kind not in ALERT_KINDS or kind not in enabled_events() or not configured():
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
            "[notify] alert send failed — check BRAWL_WEBHOOK_URL / NTFY_TOPIC",
            file=sys.stderr,
        )
