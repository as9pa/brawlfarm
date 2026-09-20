"""The detector's class list, and the templates that can pre-label a box for one of them.

The order of CLASSES is the COCO category order for the whole kit: category ids are 1-based
positions in it, so a class may be appended but never reordered or removed without retraining.
"""

from __future__ import annotations

CLASSES: tuple[str, ...] = (
    "self",
    "enemy",
    "teammate",
    "power_cube",
    "box",
    "bush",
    "showdown_card",
    "skull_star",
    "team_up_panel",
    "event_tab",
    "play_button",
    "play_again_button",
    "proceed_button",
    "exit_button",
    "close_x",
)

# templates whose match is a pre-label box for a class (template name -> class name)
TEMPLATE_CLASS: dict[str, str] = {
    "trio_showdown": "showdown_card",
    "play": "play_button",
    "playagain": "play_again_button",
    "proceed": "proceed_button",
    "exit": "exit_button",
    "close_x": "close_x",
}

# anchors a controller would tap: a false positive on one of these is a never-tap failure
TAP_ANCHORS: frozenset[str] = frozenset(TEMPLATE_CLASS.values()) | {
    "skull_star",
    "team_up_panel",
    "event_tab",
}

_IDS: dict[str, int] = {name: i for i, name in enumerate(CLASSES, start=1)}


def category_id(name: str) -> int:
    """The COCO category id of a class: its 1-based position in CLASSES."""
    return _IDS[name]
