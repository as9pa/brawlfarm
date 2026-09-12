"""
Official Brawl Stars API client.

We use the API as the SOURCE OF TRUTH for results data — placement and trophy
change come from the battlelog, total trophies from the player endpoint — instead
of OCR'ing the screen. The token is read from the environment (.env), never hard-coded.

Endpoints:
  get_player()         -> /players/{tag}             (trophies, brawlers, ...)
  get_battlelog()      -> /players/{tag}/battlelog   (recent matches)
  get_brawlers()       -> /brawlers                  (full catalog; future use)
  get_event_rotation() -> /events/rotation           (live event rotation; Phase 0
                          of event-modifier awareness — see core/events.py)

Note: battlelog lags ~2-3 min after a match and keeps only ~25 entries, so callers
should poll periodically and de-duplicate on `battleTime` (see core/datalog.py).
"""

from __future__ import annotations

import requests

from brawlfarm.core import config


class ApiError(RuntimeError):
    """Raised when an API call fails (network, auth, or non-200 status).

    ``status`` is the HTTP status of a non-200 answer and None for a transport failure or
    a missing token. Callers that need to tell a rejected token from an unreachable API
    read it rather than parsing the message: the message embeds the requested path, which
    carries the player tag, so it is never logged, echoed or matched against.
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.status: int | None = None


class ApiClient:
    def __init__(self, token: str | None = None, timeout: float = 20.0):
        self.token = token if token is not None else config.API_TOKEN
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
            }
        )

    def _get(self, path: str) -> dict | list:
        if not self.token:
            raise ApiError("No API token set (check .env / BRAWL_API_TOKEN).")
        url = f"{config.API_BASE}{path}"
        try:
            resp = self._session.get(url, timeout=self.timeout)
        except requests.RequestException as e:
            raise ApiError(f"Request to {path} failed: {e}") from e
        if resp.status_code != 200:
            # 403 usually = bad token or IP not in the token's allowlist.
            body = resp.text[:300]
            err = ApiError(f"{path} -> HTTP {resp.status_code}: {body}")
            err.status = resp.status_code
            raise err
        return resp.json()

    # --- endpoints -----------------------------------------------------------

    def get_player(self, tag: str | None = None) -> dict:
        tag = tag or config.PLAYER_TAG
        if not tag:  # no account registered yet — "/players/" would just 404
            return {}
        tag_enc = tag.replace("#", "%23")
        return self._get(f"/players/{tag_enc}")

    def get_battlelog(self, tag: str | None = None) -> list[dict]:
        tag = tag or config.PLAYER_TAG
        if not tag:  # see get_player
            return []
        tag_enc = tag.replace("#", "%23")
        data = self._get(f"/players/{tag_enc}/battlelog")
        return data.get("items", [])

    def get_brawlers(self) -> list[dict]:
        return self._get("/brawlers").get("items", [])

    def get_event_rotation(self) -> list[dict]:
        """Current event rotation (each item: startTime/endTime in battleTime
        format + event {id, mode, map, modifiers?}). The endpoint returns a bare
        JSON array; tolerate an {"items": [...]} wrapper too in case the API
        changes shape like the list endpoints."""
        data = self._get("/events/rotation")
        if isinstance(data, list):
            return data
        return data.get("items", [])


# --- helpers for reading battlelog entries -----------------------------------


def is_showdown(entry: dict) -> bool:
    """True if a battlelog entry is any Showdown mode (solo/duo/trio).

    None-safe by design: the API can send "event": null or "mode": null (a
    present-but-null key skips dict.get's default), so every level falls back
    through `or` instead of trusting the defaults."""
    mode = (
        (entry.get("event") or {}).get("mode") or (entry.get("battle") or {}).get("mode") or ""
    ).lower()
    return any(k in mode for k in config.SHOWDOWN_MODE_KEYS)


def my_brawler(entry: dict, my_tag: str | None = None) -> str | None:
    """Find which brawler we used in a battlelog entry by matching our player tag.
    Showdown entries store participants under `teams` (list of teams) or `players`.
    """
    my_tag = (my_tag or config.PLAYER_TAG).upper()
    if not my_tag:  # an empty tag would match every player whose tag key is missing
        return None

    def scan(players):
        for p in players or []:
            if str(p.get("tag", "")).upper() == my_tag:
                return p.get("brawler", {}).get("name")
        return None

    battle = entry.get("battle", {})
    # Showdown: teams is a list of teams, each a list of players.
    for team in battle.get("teams", []) or []:
        found = scan(team)
        if found:
            return found
    # Some modes: flat players list.
    return scan(battle.get("players"))
