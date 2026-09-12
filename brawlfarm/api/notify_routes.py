"""POST /api/notifications/test: send one alert to the channels config.toml names, now.

The Settings screen's "Send a test" button. The route takes no body and reads the
supervisor's own [notifications] section instead, so what is tested is what is saved. It
calls notify.send_test, which touches none of that module's configured state and has no
cooldown, through asyncio.to_thread: three network calls on the event loop would stall the
supervisor task and the SSE stream behind them.

Always 200. A channel that did not answer is a name in `failed`, not an HTTP error, because
the panel wants to show three outcomes at once. No URL and no topic is logged or returned;
only the channel names are.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request

from brawlfarm.api.deps import get_sup
from brawlfarm.core import notify

router = APIRouter()


@router.post("/api/notifications/test")
async def test_notifications(request: Request) -> dict:
    """Fire one test alert per configured channel and say which of them answered."""
    n = get_sup(request).settings.notifications
    results = await asyncio.to_thread(
        notify.send_test,
        webhook_url=n.webhook_url,
        ntfy_server=n.ntfy_server,
        ntfy_topic=n.ntfy_topic,
        healthchecks_url=n.healthchecks_url,
    )
    return {
        "sent": [name for name, ok in results.items() if ok],
        "failed": [name for name, ok in results.items() if not ok],
    }
