"""
Activate a NEW MEGA QUEST — runs at startup AND between games. This is the ONLY menu
action the bot takes between games (besides a future brawler-change).

The QUESTS button in the bottom menu bar turns GOLD when a new mega quest is available to
activate; once one is active (or none remain) it's gray. So a gold fraction over its face
is the trigger (`quests_button_has_new`). Activating one consumes the gold, so this won't
re-fire until the next becomes available — accounts with a mega quest already in progress
read gray and are skipped.

Flow (mirrors core/brawlers.py: open from menu -> act -> exit to menu via taps):
  menu (QUESTS gold) -> tap QUESTS -> tap the yellow "NEW MEGA QUEST" card on the left
  (one tap activates it directly, no confirm) -> top-left back arrow -> menu.

Safety: TAPS only, never the Android BACK key (project rule). Idempotent: gated on the
gold indicator (button + card), and if the screen/card isn't found it just exits to menu.
"""

from __future__ import annotations

import time

from brawlfarm.core import adb, config, states, vision


def quests_button_has_new(screen) -> bool:
    """True if the menu QUESTS button is GOLD — i.e. a NEW MEGA QUEST is available to
    activate. Gray (one already active / none left) reads ~0. This is the recurring trigger
    the controller checks both at startup and between games."""
    frac = vision.color_fraction(
        screen,
        config.QUESTS_NEW_REGION,
        config.QUESTS_GOLD_HSV_LO,
        config.QUESTS_GOLD_HSV_HI,
    )
    return frac >= config.QUESTS_NEW_FRAC


def _on_quests_screen(screen) -> bool:
    """True if the QUESTS screen is open (its 'QUESTS' title sits top-left)."""
    return vision.find_text(screen, "QUESTS", region=config.QUESTS_TITLE_REGION) is not None


def _has_new_mega_card(screen) -> bool:
    """True if the yellow 'NEW MEGA QUEST' card is showing in the mega-quest slot. Once a
    mega quest is active the card turns blue (gold drops), so this also stops us re-tapping
    an already-active quest."""
    frac = vision.color_fraction(
        screen,
        config.QUESTS_MEGA_CARD_REGION,
        config.QUESTS_GOLD_HSV_LO,
        config.QUESTS_GOLD_HSV_HI,
    )
    return frac >= config.QUESTS_NEW_FRAC


def _exit_to_menu() -> None:
    """Return to the main menu using TAPS only (no BACK key): tap the top-left back arrow
    until states.classify sees the MENU; close a stray popup via its red close_x."""
    for _ in range(6):
        screen = adb.screencap()
        state = states.classify(screen)
        if state is states.State.MENU:
            return
        if state is states.State.POPUP:
            x = vision.find(screen, "close_x")
            adb.tap(*(x.center if x is not None else config.CLOSE_X_BUTTON))
        else:
            adb.tap(*config.QUESTS_CLOSE_BUTTON)  # top-left back arrow
        time.sleep(1.2)


def activate_new_mega_quest(log=print) -> bool:
    """Open QUESTS and activate the available NEW MEGA QUEST, then return to the menu.
    Returns True if a mega quest was activated, False if none was available or the screen
    didn't open. Leaves the game on the main menu. Assumes we start at/near the menu (the
    caller gates on `quests_button_has_new`; re-checked here cheaply and idempotently)."""
    adb.tap(*config.QUESTS_BUTTON)
    time.sleep(2.0)
    screen = adb.screencap()
    if not _on_quests_screen(screen):
        log("[quests] QUESTS screen didn't open — leaving")
        _exit_to_menu()
        return False
    if not _has_new_mega_card(screen):
        log("[quests] no NEW MEGA QUEST card to activate")
        _exit_to_menu()
        return False
    # One tap on the yellow card activates the mega quest directly (no confirm dialog).
    adb.tap(*config.QUESTS_MEGA_CARD)
    time.sleep(1.8)
    log("[quests] activated a new mega quest")
    _exit_to_menu()
    return True
