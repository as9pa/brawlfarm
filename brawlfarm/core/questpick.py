"""Quest lines in, a farm brawler name out. Pure, and deliberately so.

``parse`` turns the OCR of the quests screen into quests; ``resolve`` turns those plus the
owned roster into one brawler name. Neither touches adb, a screen, a coordinate or
config.py, so both are tested today against hand-typed lines and wired to a real screen
read later, once an observe recording of the quests screen exists.

Three shapes matter:

    "Win 5 battles with Shelly"          -> KIND_BRAWLER, SHELLY, 5
    "Deal 20,000 damage with Tanks"      -> KIND_CLASS,   TANKS, 20000
    "Play 8 battles in Gem Grab"         -> KIND_MODE,    GEMGRAB, 8

Whether a quest is about a brawler or about a class is decided by the target, not by the
verb, because the game writes both "win with" and "deal damage with" for either one.

The class-to-brawler table is deferred until the captures exist (phase 9 spec, feature 2),
so ``resolve`` answers None for a class quest rather than naming a brawler the account may
not own. Mode quests answer None too: the bot only plays Trio Showdown. None is always the
safe answer, because the caller falls back to the farm plan or the lowest-trophy pick.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

KIND_BRAWLER = "brawler"
KIND_CLASS = "class"
KIND_MODE = "mode"

# The classes as the quests screen spells them, normalized. Game vocabulary, not
# calibration: there is no coordinate and no threshold here, so it does not belong in
# config.py and does not need an owner-approved calibration pull request to change.
CLASSES = frozenset(
    {
        "DAMAGEDEALERS",
        "TANKS",
        "MARKSMEN",
        "ARTILLERIES",
        "CONTROLLERS",
        "ASSASSINS",
        "SUPPORTS",
    }
)

# A row whose reward is already taken must never steer the session: farming it buys
# nothing. Anything that looks like a finished row is dropped rather than parsed.
_CLAIMED = re.compile(r"\b(CLAIMED|COLLECTED|COMPLETE|COMPLETED)\b")

_WIN_RE = re.compile(r"\bWIN (\d+) BATTLES? WITH (.+)$")
_DAMAGE_RE = re.compile(r"\bDEAL (\d+) DAMAGE WITH (.+)$")
_MODE_RE = re.compile(r"\bPLAY (\d+) BATTLES? IN (.+)$")

# The game's styled font reads letters as digits, the way config.py's SELET note records:
# "W1TH", "BATTLE5", "8ITE". Folded back only in words that are not a bare number, so a
# count stays a count.
_LOOKALIKE = str.maketrans({"0": "O", "1": "I", "5": "S", "|": "I"})


@dataclass(frozen=True)
class Quest:
    """One understood quest row."""

    kind: str  # KIND_BRAWLER | KIND_CLASS | KIND_MODE
    target: str  # normalized: "SHELLY", "TANKS", "GEMGRAB"
    count: int  # battles to win or play, or damage to deal
    line: str  # the normalized line it came from, for the log and the feed


def norm_name(name: str | None) -> str:
    """Collapse a name for comparison: uppercase, alphanumerics only ("EL PRIMO" ->
    "ELPRIMO", "8-BIT" -> "8BIT").

    The same rule as ``brawlers._norm``, kept here rather than imported so this module
    pulls in nothing that can touch the screen. tests/test_questpick.py asserts the two
    agree, so they cannot drift apart quietly.
    """
    return "".join(c for c in (name or "").upper() if c.isalnum())


def _fold(word: str) -> str:
    return word if word.isdigit() else word.translate(_LOOKALIKE)


def normalize(line: str) -> str:
    """One OCR line as the matchers want it: uppercase, punctuation gone, thousands
    separators gone, digit look-alikes folded back to letters, single spaces."""
    upper = (line or "").upper().replace(",", "").replace(".", "")
    cleaned = "".join(c if c.isalnum() else " " for c in upper)
    return " ".join(_fold(word) for word in cleaned.split())


def parse(lines: Iterable[str]) -> list[Quest]:
    """Every quest this OCR pass understood, in screen order.

    Lines it does not understand are dropped, and so are rows that read as already
    claimed: a quest the parser is not sure of must not steer a session.
    """
    out: list[Quest] = []
    for raw in lines:
        line = normalize(raw)
        if not line or _CLAIMED.search(line):
            continue
        quest = _parse_line(line)
        if quest is not None:
            out.append(quest)
    return out


def _parse_line(line: str) -> Quest | None:
    match = _WIN_RE.search(line) or _DAMAGE_RE.search(line)
    if match is not None:
        target = norm_name(match.group(2))
        if not target:
            return None
        kind = KIND_CLASS if target in CLASSES else KIND_BRAWLER
        return Quest(kind, target, int(match.group(1)), line)
    match = _MODE_RE.search(line)
    if match is not None:
        target = norm_name(match.group(2))
        return None if not target else Quest(KIND_MODE, target, int(match.group(1)), line)
    return None


def resolve(quests: Sequence[Quest], owned: Sequence[str]) -> str | None:
    """The owned brawler that clears the first quest it can, or None.

    The roster's own spelling comes back, never the quest's, so the name that leaves here
    is one ``brawlers.select_brawler_by_name_checked`` can verify on the detail screen.
    """
    by_norm = {norm_name(name): name for name in owned}
    for quest in quests:
        if quest.kind != KIND_BRAWLER:
            continue
        owned_name = by_norm.get(quest.target)
        if owned_name is not None:
            return owned_name
    return None
