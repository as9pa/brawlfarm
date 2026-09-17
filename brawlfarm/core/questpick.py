"""Quest lines in, a farm brawler name out. Pure, and deliberately so.

``group_cards`` turns one OCR pass over the quests screen into card strings, ``parse``
turns those into quests, and ``resolve`` turns those plus the owned roster into one
brawler name. Nothing here touches adb or a screen; group_cards reads the quest-grid
geometry out of config.py and nothing else, so all three are tested against hand-typed
lines and hand-typed centres.

Three shapes matter:

    "Win 5 battles with Shelly"          -> KIND_BRAWLER, SHELLY, 5
    "Deal 20,000 damage with Tanks"      -> KIND_CLASS,   TANKS, 20000
    "Play 8 battles in Gem Grab"         -> KIND_MODE,    GEMGRAB, 8

Whether a quest is about a brawler or about a class is decided by the target, not by the
verb, because the game writes both "win with" and "deal damage with" for either one.

A quest often names several brawlers, "Win 5 battles with Nita, Pam or Mina": any one of
them clears it. Every name is kept, in screen order, as ``candidates``; ``target`` is the
first of them, so callers written when a quest named one brawler still read.

The class-to-brawler table is deferred until the captures exist (phase 9 spec, feature 2),
so ``resolve`` answers None for a class quest rather than naming a brawler the account may
not own. Mode quests answer None too: the bot only plays Trio Showdown. None is always the
safe answer, because the caller falls back to the farm plan or the lowest-trophy pick.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from brawlfarm.core import config

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
# The season rows say "DEAL 100000 POINTS OF DAMAGE WITH ...", the daily ones leave the
# three words out. A damage line with no WITH names nobody and is dropped.
_DAMAGE_RE = re.compile(r"\bDEAL (\d+)(?: POINTS OF)? DAMAGE WITH (.+)$")
_MODE_RE = re.compile(r"\bPLAY (\d+) BATTLES? IN (.+)$")

# "NITA, PAM OR MINA" is three brawlers, not one name: the game lists them with commas and
# a final OR. OR is matched as a whole word so MORTIS keeps its own.
_CANDIDATE_SPLIT = re.compile(r",|\bOR\b")

# The game's styled font reads letters as digits, the way config.py's SELET note records:
# "W1TH", "BATTLE5", "8ITE". Folded back only in words that are not a bare number, so a
# count stays a count.
_LOOKALIKE = str.maketrans({"0": "O", "1": "I", "5": "S", "|": "I"})

# A comma between two digits is a thousands separator and goes; every other comma sits
# between two names, so normalize keeps it for _CANDIDATE_SPLIT.
_THOUSANDS = re.compile(r"(?<=\d),(?=\d)")

# The quests screen shows three rows of cards at once. Row k's bands are row 0's shifted
# down by k pitches, and a line whose cy lands in no band belongs to no card.
_ROWS = 3

# A card's progress reads "3/8", and the OCR puts spaces either side of the slash as often
# as not. It is the card's state, never part of its title.
_PROGRESS_RE = re.compile(r"\s*(\d+)\s*/\s*(\d+)\s*")


@dataclass(frozen=True)
class Quest:
    """One understood quest row."""

    kind: str  # KIND_BRAWLER | KIND_CLASS | KIND_MODE
    candidates: tuple[str, ...]  # normalized, in screen order: ("NITA", "PAM", "MINA")
    count: int  # battles to win or play, or damage to deal
    line: str  # the normalized line it came from, for the log and the feed

    @property
    def target(self) -> str:
        """The first name the quest lists. ``parse`` never builds a quest without one."""
        return self.candidates[0]


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
    """One OCR line as the matchers want it: uppercase, punctuation gone bar the commas
    that separate names, thousands separators gone, digit look-alikes folded back to
    letters, single spaces."""
    upper = _THOUSANDS.sub("", (line or "").upper()).replace(".", "")
    cleaned = "".join(c if c.isalnum() or c == "," else " " for c in upper)
    return " ".join(_fold(word) for word in cleaned.split())


def group_cards(lines: Iterable[tuple[str, float, tuple[int, int]]]) -> list[str]:
    """The quest cards one ``vision.read_lines_boxes`` pass saw, joined, in screen order.

    Takes exactly what that call returns, (text, confidence, (cx, cy)) with CENTRES ONLY
    and never a rectangle, so every rule here works on centres: a line's cy picks its row
    band, its cx picks its card inside the row. Cards come back row by row and, within a
    row, left to right, each a title joined with single spaces and ready for ``parse``.

    Two kinds of card never come back. One cut off by a region edge is truncated, so it
    would parse into a quest the screen never showed, and one whose progress reads N/N is
    already finished, so farming it buys nothing.
    """
    entries = [(text.strip(), cx, cy) for text, _conf, (cx, cy) in lines if text.strip()]
    cards: list[str] = []
    for row in range(_ROWS):
        shift = row * config.QUEST_ROW_PITCH
        titles: list[tuple[int, int, str]] = []
        tokens: list[tuple[int, int, int]] = []
        for text, cx, cy in entries:
            progress = _PROGRESS_RE.fullmatch(text)
            if progress is not None:
                if _in_band(cy, config.QUEST_PROGRESS_BAND0, shift):
                    tokens.append((cx, int(progress.group(1)), int(progress.group(2))))
            elif _in_band(cy, config.QUEST_TITLE_BAND0, shift):
                titles.append((cx, cy, text))
        # The clusters come out left to right because _clusters sorts its input by cx.
        for cluster in _clusters(titles):
            mean_cx = _mean_cx(cluster)
            if _near_edge(mean_cx):
                continue
            progress = _nearest_token(tokens, mean_cx)
            if progress is not None and progress[0] == progress[1]:
                continue
            in_cy_order = sorted(cluster, key=lambda line: line[1])
            cards.append(" ".join(text for _cx, _cy, text in in_cy_order))
    return cards


def _in_band(cy: int, band: tuple[int, int], shift: int) -> bool:
    """Whether a line's cy sits in row 0's ``band`` moved down by ``shift``."""
    lo, hi = band
    return lo + shift <= cy <= hi + shift


def _clusters(titles: list[tuple[int, int, str]]) -> list[list[tuple[int, int, str]]]:
    """One row's title lines split into cards, left to right.

    Sorted by cx, a line joins the running card while it is within QUEST_CARD_X_TOL of
    that card's mean cx, else it starts the next one: a card's own lines wander by a few
    dozen pixels, the next card's begin half a pitch away.
    """
    out: list[list[tuple[int, int, str]]] = []
    for line in sorted(titles):
        if out and abs(line[0] - _mean_cx(out[-1])) <= config.QUEST_CARD_X_TOL:
            out[-1].append(line)
        else:
            out.append([line])
    return out


def _mean_cx(cluster: list[tuple[int, int, str]]) -> float:
    return sum(cx for cx, _cy, _text in cluster) / len(cluster)


def _near_edge(mean_cx: float) -> bool:
    """Whether a card sits close enough to a region edge to have been cut off by it."""
    x1, _y1, x2, _y2 = config.QUEST_LIST_REGION
    return mean_cx - x1 < config.QUEST_EDGE_MARGIN_X or x2 - mean_cx < config.QUEST_EDGE_MARGIN_X


def _nearest_token(tokens: list[tuple[int, int, int]], mean_cx: float) -> tuple[int, int] | None:
    """The done and the total of the progress token nearest this card in cx, or None when
    the nearest one is further off than half a card pitch and so belongs to a neighbouring
    card or to no card at all."""
    if not tokens:
        return None
    cx, done, total = min(tokens, key=lambda token: abs(token[0] - mean_cx))
    return (done, total) if abs(cx - mean_cx) <= config.QUEST_CARD_PITCH_X / 2 else None


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
        candidates = _candidates(match.group(2))
        if not candidates:
            return None
        kind = KIND_CLASS if any(name in CLASSES for name in candidates) else KIND_BRAWLER
        return Quest(kind, candidates, int(match.group(1)), line)
    match = _MODE_RE.search(line)
    if match is not None:
        target = norm_name(match.group(2))
        return None if not target else Quest(KIND_MODE, (target,), int(match.group(1)), line)
    return None


def _candidates(names: str) -> tuple[str, ...]:
    """Every name that part of the line lists, normalized, in screen order.

    A piece that normalizes to nothing is dropped, so a trailing comma or a stray OR does
    not become an empty candidate no roster can match.
    """
    found = (norm_name(part) for part in _CANDIDATE_SPLIT.split(names))
    return tuple(name for name in found if name)


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
