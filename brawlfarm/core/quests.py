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

The same visit also READS the quest grid on the way out (`visit`): the cards it comes
back with pick today's farm brawler. That read only OCRs each page and drags the grid
sideways, so the taps below stay the only taps the quests screen ever gets.

Safety: TAPS only, never the Android BACK key (project rule). Idempotent: gated on the
gold indicator (button + card), and if the screen/card isn't found it just exits to menu.
"""

from __future__ import annotations

import time

from brawlfarm.core import adb, config, questpick, states, vision


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


def _open_quests(log):
    """Tap the menu QUESTS button and return the quests screen once it's up, or None if it
    didn't open (the caller still has to exit to the menu). Assumes we start at/near the
    menu, like both entry points below do."""
    adb.tap(*config.QUESTS_BUTTON)
    time.sleep(2.0)
    screen = adb.screencap()
    if not _on_quests_screen(screen):
        log("[quests] QUESTS screen didn't open — leaving")
        return None
    return screen


def _activate_mega(screen, log) -> bool:
    """Activate the NEW MEGA QUEST if `screen` (the just-opened quests screen) still shows
    the yellow card. Returns whether one was activated, and leaves the quests screen open
    for whatever the caller does next."""
    if not _has_new_mega_card(screen):
        log("[quests] no NEW MEGA QUEST card to activate")
        return False
    # One tap on the yellow card activates the mega quest directly (no confirm dialog).
    adb.tap(*config.QUESTS_MEGA_CARD)
    time.sleep(1.8)
    log("[quests] activated a new mega quest")
    return True


def activate_new_mega_quest(log=print) -> bool:
    """Open QUESTS and activate the available NEW MEGA QUEST, then return to the menu.
    Returns True if a mega quest was activated, False if none was available or the screen
    didn't open. Leaves the game on the main menu. Assumes we start at/near the menu (the
    caller gates on `quests_button_has_new`; re-checked here cheaply and idempotently)."""
    screen = _open_quests(log)
    if screen is None:
        _exit_to_menu()
        return False
    activated = _activate_mega(screen, log)
    _exit_to_menu()
    return activated


def read_quest_lines(log=print) -> list[str]:
    """Every quest card the grid holds, each a joined title string, in first-seen order.

    Assumes the QUESTS screen is open and still at its LEFT edge (nothing here scrolls
    back). One page at a time: OCR the grid region, group the lines into cards, then drag
    the grid sideways along the calibrated lane and read the next page. The sweep stops as
    soon as a page repeats the one before it (the scroll has hit its right end) and gives
    up after QUEST_SWEEP_MAX pages. A page that groups into no cards is still a page: the
    placeholder "?" cards carry no text.

    Reads and swipes ONLY: it never taps, so the worst a misread costs is a wasted page.
    An empty sweep logs a tripwire line and returns [] rather than raising, because a quest
    read that found nothing must degrade to the plain lowest-trophy pick, not stop a run.
    """
    cards: list[str] = []
    seen: set[str] = set()
    previous: set[str] | None = None
    pages = 0
    for _ in range(config.QUEST_SWEEP_MAX):
        screen = adb.screencap()
        lines = vision.read_lines_boxes(screen, region=config.QUEST_LIST_REGION)
        page = questpick.group_cards(lines)
        pages += 1
        for card in page:
            if card not in seen:
                seen.add(card)
                cards.append(card)
        if previous is not None and set(page) == previous:
            break  # the same cards twice: the grid has stopped moving
        previous = set(page)
        adb.swipe(
            config.QUEST_SWIPE_X_START,
            config.QUEST_SWIPE_Y,
            config.QUEST_SWIPE_X_END,
            config.QUEST_SWIPE_Y,
            config.QUEST_SWIPE_MS,
        )
        time.sleep(1.0)  # let the fling settle before re-reading the grid
    if not cards:
        log(f"[quests] read 0 quest cards over {pages} pages")
    return cards


def visit(log=print) -> tuple[list[str], bool]:
    """The one quests visit a session makes: open QUESTS, activate a NEW MEGA QUEST if one
    is offered, read the quest cards, and return to the menu. Returns the cards read (empty
    if the screen didn't open or nothing OCR'd) and whether a mega quest was activated --
    this visit consumes the gold badge, so its caller owes the feed the row the recurring
    trigger would have logged. Leaves the game on the main menu."""
    screen = _open_quests(log)
    if screen is None:
        _exit_to_menu()
        return [], False
    activated = _activate_mega(screen, log)
    cards = read_quest_lines(log)
    _exit_to_menu()
    return cards, activated
