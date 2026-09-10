"""
Data logging: persist per-game results, per-menu trophy snapshots, and a session
event log — for later analysis and graphs.

- games.csv         one row per concluded match (deduped on battleTime)
- menu_trophies.csv one row each time we snapshot total trophies on the main menu
- session-<ts>.jsonl append-only event log of what the bot did (for morning review)

Match results come from the API battlelog (placement + trophy change), not OCR.
Because the battlelog lags a few minutes, call log_games_from_battlelog() repeatedly
(e.g. each menu return); dedup on battleTime makes that safe.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

from brawlfarm.core import config, notify
from brawlfarm.core.api import is_showdown, my_brawler

GAMES_CSV = config.DATA_DIR / "games.csv"
TROPHIES_CSV = config.DATA_DIR / "menu_trophies.csv"

# --- startup-narration step events -------------------------------------------------
#
# Canonical contract, appended to the session JSONL for the control panel's tailer:
#
#   {"ts": "...", "kind": "step", "step": "<id>", "label": "<human text>",
#    "status": "ok" | "error"}
#   {"ts": "...", "kind": "farming", "brawler": "<API name>" | null}
#
# Step ids, in canonical startup order (the control panel renders this order;
# unknown ids are appended as they arrive, so new steps need no bot-side change):
#
#   launch        Brawl Stars brought to the foreground
#   verify        RESERVED: sign-in/account verification (no worker emission yet —
#                 the controller has no such step)
#   dnd           in-game invite mutes
#   daily_reward  DAILY STREAK login reward claimed (opportunistic — may never fire)
#   brawler       farm brawler selected
#
# The controller (core/controller.py) already logs every milestone as a plain event
# (launch_game, dnd, select_brawler, daily_streak_claim,
# phase->queuing). DataLog.event() MIRRORS the first occurrence of each into the
# canonical "step" record — so the worker side needs zero controller changes and the
# control panel needs to understand exactly one format. A later "ok" upgrades an
# earlier "error" for the same step (e.g. planned brawler select fails -> lowest-
# trophy fallback succeeds). The first menu->queuing phase flip emits "farming".

STEP_LABELS = {
    "launch": "Brawl Stars opened",
    "dnd": "DND enabled",
    "daily_reward": "Daily reward claimed",
    "brawler": "Brawler selected",
}
STEP_ORDER = tuple(STEP_LABELS)

_EVENT_TO_STEP = {
    "launch_game": ("launch", "ok"),
    "launch_game_error": ("launch", "error"),
    "dnd": ("dnd", "ok"),
    "dnd_error": ("dnd", "error"),
    "daily_streak_claim": ("daily_reward", "ok"),
    "select_brawler": ("brawler", "ok"),
    "select_brawler_error": ("brawler", "error"),
}

GAME_FIELDS = [
    "battleTime",
    "logged_at",
    "event_mode",
    "battle_mode",
    "type",
    "rank",
    "trophyChange",
    "result",
    "duration_s",
    "map",
    "brawler",
    "is_showdown",
]
TROPHY_FIELDS = ["logged_at", "total_trophies", "highest_trophies", "expLevel"]


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _ensure_csv(path: Path, fields: list[str]) -> None:
    # parents=True: DATA_DIR is data/<acct>, so a fresh checkout/instance may be
    # missing the data/ parent too — a bare mkdir would crash the worker at boot.
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with path.open("w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=fields).writeheader()


class DataLog:
    def __init__(self):
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        _ensure_csv(GAMES_CSV, GAME_FIELDS)
        _ensure_csv(TROPHIES_CSV, TROPHY_FIELDS)
        self._seen_battles = self._load_seen()

        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.session_path = config.DATA_DIR / f"session-{ts}.jsonl"

        # Startup-narration mirror state (see the contract block above).
        self._step_status: dict[str, str] = {}  # step id -> "ok" | "error"
        self._farming_emitted = False
        self._last_brawler: str | None = None

    def _load_seen(self) -> set[str]:
        seen: set[str] = set()
        try:
            with GAMES_CSV.open("r", newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    bt = row.get("battleTime")
                    if bt:
                        seen.add(bt)
        except FileNotFoundError:
            pass
        return seen

    # --- per-game ------------------------------------------------------------

    def log_games_from_battlelog(self, items: list[dict]) -> int:
        """Append any battlelog entries we haven't logged yet. Returns # new rows."""
        new = 0
        with GAMES_CSV.open("a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=GAME_FIELDS)
            # Oldest first so the file reads chronologically.
            for e in reversed(items):
                bt = e.get("battleTime")
                if not bt or bt in self._seen_battles:
                    continue
                ev = e.get("event", {})
                b = e.get("battle", {})
                w.writerow(
                    {
                        "battleTime": bt,
                        "logged_at": _now_iso(),
                        "event_mode": ev.get("mode"),
                        "battle_mode": b.get("mode"),
                        "type": b.get("type"),
                        "rank": b.get("rank"),
                        "trophyChange": b.get("trophyChange"),
                        "result": b.get("result"),
                        "duration_s": b.get("duration"),
                        "map": ev.get("map"),
                        "brawler": my_brawler(e),
                        "is_showdown": is_showdown(e),
                    }
                )
                self._seen_battles.add(bt)
                new += 1
        if new:
            self.event("games_logged", count=new)
        return new

    # --- per-menu trophies ---------------------------------------------------

    def log_menu_trophies(self, player: dict) -> None:
        if not player:  # no account registered — api.get_player() skipped the call
            return
        with TROPHIES_CSV.open("a", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=TROPHY_FIELDS).writerow(
                {
                    "logged_at": _now_iso(),
                    "total_trophies": player.get("trophies"),
                    "highest_trophies": player.get("highestTrophies"),
                    "expLevel": player.get("expLevel"),
                }
            )

    # --- session event log ---------------------------------------------------

    def event(self, etype: str, **fields) -> None:
        """Append one structured event to the session JSONL.
        `etype` is the event kind (e.g. "phase", "tap"); **fields are extra data.
        Avoid passing a field literally named 'kind' (reserved for etype)."""
        rec = {"ts": _now_iso(), "kind": etype, **fields}
        self._append(rec)
        # Auto-alert on the events worth waking up for (stop / recover / crash /
        # wrong_mode / bad_resolution). No-op unless a backend is set in .env, and
        # never allowed to break logging.
        try:
            notify.maybe_alert(etype, fields)
        except Exception:
            pass
        # Mirror startup milestones into the canonical narration contract (the
        # control panel's checklist). Best-effort: narration must never break logging.
        try:
            self._mirror_narration(etype, fields)
        except Exception:
            pass

    def _append(self, rec: dict) -> None:
        with self.session_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def _mirror_narration(self, etype: str, fields: dict) -> None:
        """The "step"/"farming" mirror (contract block at the top of this file).
        Each step is emitted once — except that a later success upgrades an earlier
        error (planned-select fails -> fallback succeeds). The first menu->queuing
        phase flip marks the start of actual farming."""
        if fields.get("brawler"):  # remember for the terminal "farming" record
            self._last_brawler = str(fields["brawler"])
        hit = _EVENT_TO_STEP.get(etype)
        if hit is not None:
            step, status = hit
            prev = self._step_status.get(step)
            if prev == "ok" or prev == status:
                return  # already told this story
            self._step_status[step] = status
            label = STEP_LABELS[step]
            if step == "brawler" and fields.get("brawler"):
                label = f"Brawler selected: {fields['brawler']}"
            self._append(
                {
                    "ts": _now_iso(),
                    "kind": "step",
                    "step": step,
                    "label": label,
                    "status": status,
                }
            )
            return
        if etype == "phase" and fields.get("to") == "queuing" and not self._farming_emitted:
            self._farming_emitted = True
            self._append({"ts": _now_iso(), "kind": "farming", "brawler": self._last_brawler})
