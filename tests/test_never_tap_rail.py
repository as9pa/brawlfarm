"""The NEVER-TAP safety rail, source-enforced (r10 hardening).

Project rule (CONTRIBUTING.md, absolute — real accounts, real-money surfaces): never
tap ACCEPT on a team invite, GET/Upgrade, EQUIP NOW, shop buy buttons, the pass
VAULT, anything Gems-priced, or SCID_LOG_OUT. Until now zero tests enforced any
of it. This parses every brawlfarm/core/*.py and fails if a forbidden surface is
routed into a tap — so a future PR that taps one of these CANNOT land green.

What it catches (static analysis — scope stated honestly):
  * `adb.tap(*config.SCID_LOG_OUT)` / `tap(*SCID_LOG_OUT)` — any forbidden
    config NAME (collected from config.py: constants whose trailing comment
    says "NEVER tap...") appearing anywhere in a tap-call's arguments;
  * `adb.tap(947, 565)` / `adb.tap(*(947, 565))` — the known forbidden
    coordinate LITERALS (team-invite ACCEPT; plus the resolved values of the
    forbidden names, so inlining the tuple doesn't dodge the name check).

What it CANNOT catch (runtime is out of reach for a static rail): coordinates
computed at runtime (OCR matches, arithmetic), aliasing through intermediate
variables, or taps issued outside brawlfarm/core/*.py. The runtime defenses remain
the verify-then-act pattern and the calibrated-coordinate discipline; this rail is
the structural backstop, not the whole fence. EQUIP NOW / shop buys / VAULT
have NO coordinates in config.py (deliberately never calibrated) — for those
surfaces "the constant doesn't exist" is the rail, and this test pins the
forbidden ones that DO exist near tappable mirrors (ACCEPT sits at the fixed
mirror of REJECT; LOG OUT sits below SWITCH ACCOUNT).

Two coordinate rails ride along (phase 10a, the quest sweep): REROLL QUEST is
calibrated as a landmark only and must not be named outside config.py at all, and
every swipe lane endpoint must clear the tappable controls by a margin, because a
swipe that starts or ends on a button can register as a tap.

A self-test feeds the detector synthetic violations and asserts it fires, so
the rail can't rot into a vacuous pass.
"""

from __future__ import annotations

import ast
import math
import re
from pathlib import Path

from brawlfarm.core import config

CORE = Path(config.__file__).parent
TAP_CALL_NAMES = {"tap", "tap_hold", "long_press"}

# Known forbidden coordinate literals that exist only as comments/UI mirrors:
# the green ACCEPT on the team-invite modal (config.py: "must NEVER be tapped").
ACCEPT_TEAM_INVITE = (947, 565)


# --- collect the forbidden set from config.py itself --------------------------------


def forbidden_config_names() -> set[str]:
    """Constants config.py marks never-tapped: an assignment whose trailing
    comment contains 'NEVER tap' (case-insensitive; matches 'NEVER tapped')."""
    names: set[str] = set()
    src = Path(config.__file__).read_text(encoding="utf-8")
    for line in src.splitlines():
        m = re.match(r"^([A-Z][A-Z0-9_]*)\s*=.*#.*never\s+tap", line, re.IGNORECASE)
        if m:
            names.add(m.group(1))
    return names


def forbidden_coords(names: set[str]) -> set[tuple[int, int]]:
    coords = {ACCEPT_TEAM_INVITE}
    for n in names:
        v = getattr(config, n, None)
        if isinstance(v, tuple) and len(v) == 2:
            coords.add(v)
    return coords


# --- the detector --------------------------------------------------------------------


def _call_simple_name(call: ast.Call) -> str | None:
    f = call.func
    if isinstance(f, ast.Attribute):
        return f.attr  # adb.tap / adb.tap_hold
    if isinstance(f, ast.Name):
        return f.id  # bare tap (from-import style)
    return None


def _const_tuple(node: ast.AST) -> tuple | None:
    if isinstance(node, ast.Tuple) and all(isinstance(e, ast.Constant) for e in node.elts):
        return tuple(e.value for e in node.elts)
    return None


def find_violations(
    tree: ast.AST, names: set[str], coords: set[tuple[int, int]]
) -> list[tuple[int, str]]:
    """(lineno, what) for every tap/tap_hold/long_press call that references a
    forbidden config name or a forbidden coordinate literal in its arguments."""
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _call_simple_name(node) not in TAP_CALL_NAMES:
            continue
        args = [a.value if isinstance(a, ast.Starred) else a for a in node.args]
        # forbidden NAME anywhere in any argument (config.X, bare X, nested)
        for a in args:
            for sub in ast.walk(a):
                if isinstance(sub, ast.Attribute) and sub.attr in names:
                    out.append((node.lineno, sub.attr))
                elif isinstance(sub, ast.Name) and sub.id in names:
                    out.append((node.lineno, sub.id))
                else:
                    t = _const_tuple(sub)
                    if t in coords:
                        out.append((node.lineno, str(t)))
        # forbidden coordinate as two positional number literals: tap(947, 565)
        consts = [a.value for a in args if isinstance(a, ast.Constant)]
        for pair in zip(consts, consts[1:]):
            if pair in coords:
                out.append((node.lineno, str(pair)))
    return out


# --- the rail itself ------------------------------------------------------------------


def test_config_marks_the_known_forbidden_constants():
    # collection self-check: if the comment convention drifts, fail loudly here
    names = forbidden_config_names()
    assert "SCID_LOG_OUT" in names, (
        "config.py no longer marks SCID_LOG_OUT 'NEVER tapped' — restore the "
        "marker comment; the never-tap rail keys off it"
    )
    assert config.SCID_LOG_OUT in forbidden_coords(names)


def test_no_core_code_taps_a_forbidden_surface():
    names = forbidden_config_names()
    coords = forbidden_coords(names)
    offenders: list[str] = []
    sources = sorted(CORE.glob("*.py"))
    assert sources, f"no core modules under {CORE} — the rail would pass vacuously"
    for py in sources:
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        for lineno, what in find_violations(tree, names, coords):
            offenders.append(f"{py.name}:{lineno}: taps forbidden surface {what}")
    assert not offenders, (
        "NEVER-TAP rail violated (CONTRIBUTING.md safety rails — real-money surfaces):\n"
        + "\n".join(offenders)
    )


# --- self-test: the detector actually fires (no vacuous pass) -------------------------


SYNTHETIC_VIOLATIONS = [
    "from brawlfarm.core import adb, config\nadb.tap(*config.SCID_LOG_OUT)\n",
    "from brawlfarm.core.config import SCID_LOG_OUT\nfrom brawlfarm.core.adb import tap\ntap(*SCID_LOG_OUT)\n",
    "from brawlfarm.core import adb\nadb.tap(947, 565)\n",  # inlined ACCEPT coords
    "from brawlfarm.core import adb\nadb.tap(*(947, 565))\n",  # starred literal tuple
    "from brawlfarm.core import adb, config\nadb.tap_hold(*config.SCID_LOG_OUT, 500)\n",
    f"from brawlfarm.core import adb\nadb.tap{config.SCID_LOG_OUT}\n",  # inlined LOG OUT coords
]

SYNTHETIC_OK = [
    # the calibrated REJECT (shares ACCEPT's y) and a config'd allowed surface
    "from brawlfarm.core import adb, config\nadb.tap(*config.INVITE_REJECT_BUTTON)\n",
    "from brawlfarm.core import adb\nadb.tap(653, 565)\n",
    "from brawlfarm.core import adb, config\nadb.tap(*config.HOME_BUTTON)\n",
    # the forbidden name OUTSIDE a tap call is fine (config.py documents it)
    "from brawlfarm.core import config\nx = config.SCID_LOG_OUT\nprint(x)\n",
]


def test_detector_fires_on_synthetic_violations():
    names = forbidden_config_names()
    coords = forbidden_coords(names)
    for snippet in SYNTHETIC_VIOLATIONS:
        hits = find_violations(ast.parse(snippet), names, coords)
        assert hits, f"detector MISSED a forbidden tap:\n{snippet}"


def test_detector_stays_quiet_on_allowed_taps():
    names = forbidden_config_names()
    coords = forbidden_coords(names)
    for snippet in SYNTHETIC_OK:
        hits = find_violations(ast.parse(snippet), names, coords)
        assert not hits, f"false positive on an allowed tap:\n{snippet}"


# --- the quest sweep rails (phase 10a) ------------------------------------------------

PACKAGE = CORE.parent
REROLL_NAME = "QUEST_REROLL_BUTTON"
SWIPE_CLEARANCE_PX = 120

# Every tappable surface a swipe lane must stay clear of: the reroll button and the
# exits on QUESTS, the mega-quest card it sits above, and the BRAWLERS top-bar controls
# (the roster lane pages the grid under them).
CLEARANCE_TARGETS = (
    "QUEST_REROLL_BUTTON",
    "HOME_BUTTON",
    "QUESTS_CLOSE_BUTTON",
    "QUESTS_MEGA_CARD",
    "BRAWLER_SEARCH_FIELD",
    "BRAWLER_QUEST_TOGGLE",
    "BRAWLER_HEART_TOGGLE",
)


def swipe_endpoints() -> list[tuple[str, tuple[int, int]]]:
    """Both endpoints of both swipe lanes, built from config, never hardcoded, so a
    recalibration of any lane is re-checked against the clearance rule."""
    return [
        ("QUEST_SWIPE start", (config.QUEST_SWIPE_X_START, config.QUEST_SWIPE_Y)),
        ("QUEST_SWIPE end", (config.QUEST_SWIPE_X_END, config.QUEST_SWIPE_Y)),
        ("BRAWLER_SCROLL left", (config.BRAWLER_SCROLL_X_LEFT, config.BRAWLER_SCROLL_Y)),
        ("BRAWLER_SCROLL right", (config.BRAWLER_SCROLL_X_RIGHT, config.BRAWLER_SCROLL_Y)),
    ]


def test_reroll_button_is_named_only_in_config():
    """REROLL QUEST is calibrated so the quest swipe lane can be measured against it,
    and for nothing else. No module may even name it, so it cannot reach a tap by any
    route the AST detector can't see (an alias, a helper, a computed argument)."""
    assert hasattr(config, REROLL_NAME), (
        f"config.py no longer defines {REROLL_NAME}: the quest sweep rails key off it"
    )
    sources = sorted(PACKAGE.rglob("*.py"))
    assert sources, f"no modules under {PACKAGE}: the rail would pass vacuously"
    config_py = Path(config.__file__).resolve()
    offenders: list[str] = []
    for py in sources:
        if py.resolve() == config_py:
            continue
        for lineno, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
            if REROLL_NAME in line:
                offenders.append(f"{py.relative_to(PACKAGE)}:{lineno}: {line.strip()}")
    assert not offenders, (
        f"{REROLL_NAME} is a landmark only (a reroll throws a quest away): it may "
        "appear in config.py and nowhere else in the package:\n" + "\n".join(offenders)
    )


def test_swipe_lanes_clear_every_tappable_control():
    endpoints = swipe_endpoints()
    targets = {name: getattr(config, name) for name in CLEARANCE_TARGETS}
    for name, coord in targets.items():
        assert isinstance(coord, tuple) and len(coord) == 2, (
            f"config.{name} is no longer an (x, y) pair: the clearance rail can't "
            "measure against it"
        )
    offenders: list[str] = []
    for label, (x, y) in endpoints:
        for name, (tx, ty) in targets.items():
            gap = math.hypot(x - tx, y - ty)
            if gap <= SWIPE_CLEARANCE_PX:
                offenders.append(f"{label} {(x, y)} sits {gap:.0f} px from {name} {(tx, ty)}")
    assert not offenders, (
        f"a swipe endpoint is within {SWIPE_CLEARANCE_PX} px of a tappable control "
        "(a swipe that starts or ends on a button can register as a tap):\n" + "\n".join(offenders)
    )
