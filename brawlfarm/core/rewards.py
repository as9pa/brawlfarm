"""
Rewards: classify drop rewards into a "session recap" (trophies, skins, brawlers).

This module is pure perception + bookkeeping — it never touches ADB or the game.
The farm loop feeds it the drop-reveal OCR lines it already collects; this module
turns those into structured data and, at the end of a run, a human-readable summary
of everything gained.

  parse_drop_reward(lines)       -> {"kind": ..., "amount"/"name"/"rarity": ...} | None
  SessionRewards (dataclass)     -> a list of reward events (skins / brawlers / drops)
  format_recap(session, ...)     -> multi-line text summary (games / trophies / skins)

Currency gain-tracking (coins/PP/credits/bling/gems) was removed in round 7
(trophy-only minimalism, legacy owner note, not ported): the recap is now
trophies + skins + games only. parse_drop_reward still recognizes coin/power-point
DROP frames so the tap-through never mistakes one for an unknown popup, but the
amounts are no longer summed or surfaced anywhere.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# --- drop-reward classification ----------------------------------------------
#
# Starr Drops / Chaos Drops reveal one reward per frame. The bot OCRs the reveal and
# hands us the text lines; we classify them. Real shapes seen in reveals:
#   ["POWER POINTS FOR ANY BRAWLER", "+50", "50", "You have:", "16646"] -> power_points 50
#   ["COINS", "+100"]                                                    -> coins 100
#   ["NEW EPIC SKIN!", "NIGHT WITCH", "MORTIS"]                          -> skin, EPIC
#   ["RARE", "UPGRADE CHANCES"]                                          -> None (rarity splash)
#
# Everything is matched case-insensitively and defensively: a missing amount, an
# unexpected ordering, or an unrecognizable reward all resolve to a sensible value
# (None when we genuinely can't tell).

# Drop-rarity words — used to (a) read a skin's rarity and (b) recognize the bare
# rarity "splash" frame that precedes the real reward and is NOT itself a reward.
_RARITIES = ("COMMON", "RARE", "SUPER RARE", "EPIC", "MYTHIC", "LEGENDARY")


def _first_signed_amount(lines: list[str]) -> int | None:
    """Return the first integer that appears with a leading '+' (e.g. "+50" -> 50).
    Drop reveals show the gained amount as "+N"; the unsigned "N" beneath it and the
    "You have:" total are ignored in favour of the explicit "+N". If no signed token
    is present, fall back to a bare integer ONLY when it is the sole candidate on
    the frame — with several bare integers (the duplicate "N" + the "You have:"
    total) the pick would be a guess, and no amount beats a wrong amount."""
    joined = " ".join(lines)
    m = re.search(r"\+\s*(\d[\d,]*)", joined)
    if m:
        return int(m.group(1).replace(",", ""))
    bare = re.findall(r"\b\d[\d,]*\b", joined)
    return int(bare[0].replace(",", "")) if len(bare) == 1 else None


def parse_drop_reward(lines: list[str]) -> dict | None:
    """Classify one drop-reveal frame's OCR lines into a reward dict, or None if the
    lines aren't a recognizable reward.

    Returns one of:
      {"kind": "power_points", "amount": int}
      {"kind": "coins", "amount": int}
      {"kind": "skin", "name": str, "rarity": str}      # rarity uppercased, e.g. "EPIC"
      {"kind": "brawler", "name": str}
      None                                              # e.g. the bare rarity splash
    """
    if not lines:
        return None
    # Normalise: trim + uppercase, drop blanks. Keep an uppercased "joined" too.
    norm = [ln.strip().upper() for ln in lines if ln and ln.strip()]
    if not norm:
        return None
    joined = " ".join(norm)

    # --- skin: "NEW <RARITY> SKIN!" then the skin name on following line(s) ---------
    # The header carries the rarity between "NEW" and "SKIN"; the name is whatever
    # non-header lines follow (often split across two lines, e.g. "NIGHT WITCH" +
    # "MORTIS").
    skin_hdr = next((ln for ln in norm if "SKIN" in ln and "NEW" in ln), None)
    if skin_hdr is not None:
        m = re.search(r"NEW\s+(.*?)\s+SKIN", skin_hdr)
        rarity = None
        if m:
            candidate = m.group(1).strip()
            # Only treat it as a rarity if it's a known one; otherwise leave None.
            if candidate in _RARITIES:
                rarity = candidate
        # Name = the reveal lines that aren't the header / a stray rarity word.
        name_parts = [
            ln for ln in norm if ln is not skin_hdr and "SKIN" not in ln and ln not in _RARITIES
        ]
        name = " ".join(name_parts).strip()
        return {"kind": "skin", "name": name, "rarity": rarity}

    # --- power points: "POWER POINTS FOR ANY BRAWLER" + "+N" ------------------------
    if any("POWER POINT" in ln for ln in norm):
        return {"kind": "power_points", "amount": _first_signed_amount(norm)}

    # --- coins: a "COINS" line + "+N" -----------------------------------------------
    if any("COIN" in ln for ln in norm):
        return {"kind": "coins", "amount": _first_signed_amount(norm)}

    # --- new brawler: "NEW BRAWLER!" / "BRAWLER UNLOCKED" then the brawler name ------
    if any(("BRAWLER" in ln and ("NEW" in ln or "UNLOCK" in ln)) for ln in norm):
        name_parts = [ln for ln in norm if "BRAWLER" not in ln and "UNLOCK" not in ln]
        return {"kind": "brawler", "name": " ".join(name_parts).strip()}

    # --- the bare drop-rarity splash ("RARE" / "EPIC" + "UPGRADE CHANCES") -----------
    # This frame announces the drop's rarity tier, not a reward — explicitly NOT a hit.
    if any(ln in _RARITIES for ln in norm) and "UPGRADE" in joined:
        return None

    # Nothing matched — unknown / not a reward frame.
    return None


# --- session bookkeeping ------------------------------------------------------


@dataclass
class SessionRewards:
    """Everything gained during one automation session.

    `events` is the running list of reward dicts (from parse_drop_reward), plus
    optionally synthetic count events for trophies/games. Currency snapshots were
    removed in round 7 (trophy-only minimalism) — the recap tracks skins/brawlers.
    """

    events: list[dict] = field(default_factory=list)

    def add_event(self, event: dict | None) -> None:
        """Append a reward event (a dict from parse_drop_reward). None is ignored so
        callers can pass parse_drop_reward's result straight through."""
        if event:
            self.events.append(event)

    def skins(self) -> list[dict]:
        """All skin-unlock events recorded this session."""
        return [e for e in self.events if e.get("kind") == "skin"]

    def brawlers(self) -> list[dict]:
        """All brawler-unlock events recorded this session."""
        return [e for e in self.events if e.get("kind") == "brawler"]


def _title(text: str) -> str:
    """Title-case a SCREAMING reward name for display ("NIGHT WITCH MORTIS" ->
    "Night Witch Mortis"). Leaves already-mixed text alone-ish via str.title."""
    return text.title() if text else text


def format_recap(
    session: SessionRewards,
    trophies_gained: int | None = None,
    games_played: int | None = None,
) -> str:
    """Render a clean, human-readable session summary.

    Games played and trophies are always shown when provided. Skins/brawlers are
    listed by name. (Currency gain-tracking was removed in round 7 — trophy-only.)
    """
    lines = ["Session recap"]

    if games_played is not None:
        lines.append(f"- Games played: {games_played:,}")
    if trophies_gained is not None:
        lines.append(f"- Trophies: {trophies_gained:+,}")

    skins = session.skins()
    if skins:
        labels = []
        for s in skins:
            name = _title(s.get("name") or "Unknown")
            rarity = s.get("rarity")
            labels.append(f"{name} ({rarity.title()})" if rarity else name)
        lines.append(f"- Skins unlocked: {', '.join(labels)}")

    brawlers = session.brawlers()
    if brawlers:
        names = ", ".join(_title(b.get("name") or "Unknown") for b in brawlers)
        lines.append(f"- Brawlers unlocked: {names}")

    return "\n".join(lines)
