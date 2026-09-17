"""
In-game Do-Not-Disturb — a once-per-session startup action (not part of the per-frame
farm loop). Team/friend invites pop a modal that BLOCKS the menu and can interrupt the
farm, so before farming we set the game's own mute settings and leave them on for the
whole session.

The flow mirrors core/brawlers.py (open from menu -> act -> exit to menu via taps):

  ensure_team_invites_muted():
     menu -> translucent "+" team slot beside the brawler -> TEAM UP panel -> gear
     (top-right, LEFT of the red ✕) -> SOCIAL SETTINGS. Confirm MUTE FRIENDS = 24h and
     MUTE RECENT TEAMMATES = 30 days (selected radio = bright ORANGE fill).

(Round 6, legacy owner-instructions note, not ported: the separate "block online push
notifications" leg was removed — it was unnecessary. Team-invite mutes are the whole
DND now.)

Safety: every hop VERIFIES the expected screen via OCR before tapping anything inside
it, and bails back to the menu when the verify fails — so a stale/uncalibrated
coordinate degrades to a logged no-op, never a misfire (the "+" slot and the gear are
both probe-confirmed as of 2026-09-17). Idempotent: rows are only tapped when the
colour check says they are NOT already set; CONFIRM on an unchanged panel is a
harmless no-op and is used as the deterministic way to close it. TAPS only, never the
Android BACK key (project rule).

STOP ETIQUETTE: a USER-initiated stop hands the account back to a human, so remove_dnd()
runs the REVERSE of the mute leg — same proven navigation and verifies, toggling back:

  ensure_team_invites_unmuted(): clear the selected mute in both columns.
      Probe-verified live (2026-06-10): the panel has NO "Don't mute" row —
      tapping the SELECTED (orange) radio deselects it; CONFIRM applies the
      unmute (status line gone on reopen). Radios are colour-checked against the
      measured grid (config.DND_MUTE_RADIO_GRID); only selected ones are tapped.
"""

from __future__ import annotations

import time

import cv2

from brawlfarm.core import adb, config, states, vision


def _event_shot(screen, tag: str) -> None:
    """Save a diagnostic screenshot of a failed verify (mirrors controller.event_shot,
    which isn't importable here without a cycle) — so a skipped DND leg leaves ground
    truth in captures/events/ instead of just a log line."""
    d = config.CAPTURES_DIR / "events"
    d.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(d / f"{time.strftime('%H%M%S')}_{tag}.png"), screen)


def _wait_for_screen(needle: str, budget_s: float, poll_s: float = 0.5):
    """Poll for an OCR label after a navigation tap; return the screen that contained
    it (for follow-up colour checks), or None once the budget runs out. A single fixed-
    delay capture flaked on cold-booted clients (the panel was still animating in when
    the check ran) — polling keeps warm-client speed and tolerates the laggy case.
    The caller passes the total time the panel gets (config.DND_PANEL_WAIT_S /
    DND_SETTINGS_WAIT_S) rather than a try count: the old 4 x 1.0 s budget gave up
    before the 4.9 s the TEAM UP panel actually takes, and the whole leg skipped."""
    waited = 0.0
    while waited < budget_s:
        time.sleep(poll_s)
        waited += poll_s
        screen = adb.screencap()
        if vision.find_text(screen, needle) is not None:
            return screen
    return None


def _radio_selected(screen, center) -> bool:
    """True if the radio at `center` shows the bright ORANGE 'selected' fill (an
    unselected radio is dark blue, which the orange window ignores)."""
    cx, cy = center
    h = config.DND_RADIO_HALF
    frac = vision.color_fraction(
        screen,
        (cx - h, cy - h, cx + h, cy + h),
        config.DND_RADIO_ORANGE_LO,
        config.DND_RADIO_ORANGE_HI,
    )
    return frac >= config.DND_RADIO_ON_FRAC


def _exit_to_menu(log) -> None:
    """Return to the main menu using TAPS only (no BACK key). Each cycle taps ONLY what
    the screen proves is on it: a stray popup's detected red close_x, else SOCIAL
    SETTINGS' ✕ (that panel sits ON TOP of TEAM UP, so it is checked first), else the
    TEAM UP panel's own red ✕ — it closes from the TOP-RIGHT, unlike the pass/brawlers
    screens' top-left arrow. Nothing readable means nothing is tapped this cycle: a
    panel still animating in reads on the next one. The old version rotated blind taps
    through HOME_BUTTON (1525, 47), which ON THE MENU is the hamburger (MENU_BURGER):
    it opened the side menu and the taps after it walked the game out of the app
    (2026-09-17 worker sessions, once ending behind the Android launcher)."""
    for _ in range(8):
        screen = adb.screencap()
        state = states.classify(screen)
        if state is states.State.MENU:
            return
        if state is states.State.POPUP:
            x = vision.find(screen, "close_x")
            adb.tap(*(x.center if x is not None else config.CLOSE_X_BUTTON))
        elif vision.find_text(screen, "SOCIAL SETTINGS") is not None:
            adb.tap(*config.CLOSE_X_BUTTON)
        elif vision.find_text(screen, "TEAM UP") is not None:
            adb.tap(*config.DND_TEAMUP_CLOSE_X)
        time.sleep(1.2)
    log("[dnd] could not confirm the menu after closing — continuing anyway")


def ensure_team_invites_muted(log=print) -> bool:
    """Setting A: open the TEAM UP panel's SOCIAL SETTINGS and make sure MUTE FRIENDS =
    24h and MUTE RECENT TEAMMATES = 30 days. Returns True iff the panel was reached (the
    mutes are then known-set); False on a safe bail. Leaves the game on the main menu."""
    # DND_TEAM_SLOT is probe-confirmed (2026-09-17) to open this panel; the verify below
    # still makes a miss a harmless no-op (whatever a stray tap opened gets closed by
    # _exit_to_menu). The panel takes ~4.9 s to become readable, hence the budget.
    adb.tap(*config.DND_TEAM_SLOT)
    if _wait_for_screen("TEAM UP", config.DND_PANEL_WAIT_S) is None:
        log("[dnd] TEAM UP panel didn't open ('+' slot mis-tapped?) — skipping")
        _exit_to_menu(log)
        return False

    # Gear sits only ~65 px left of the panel's red ✕ — if we hit the ✕ instead, the
    # panel closes and the verify below fails (safe bail), it never mis-taps settings.
    # Settle first, then up to 2 attempts: a gear tap fired while the panel is still
    # animating in lands where the gear isn't yet (the recurring leg-skip cause).
    # Verify needle is bare "MUTE": OCR sometimes collapses spaces ("MUTEFRIENDS"),
    # which a two-word needle would miss; "MUTE" still substring-matches either column
    # header, mangled or not. (Same OCR quirk that broke leg B's "BLOCK ONLINE".)
    time.sleep(1.0)
    screen = None
    for _ in range(2):
        adb.tap(*config.DND_TEAMUP_GEAR)
        screen = _wait_for_screen("MUTE", config.DND_SETTINGS_WAIT_S)
        if screen is not None:
            break
    if screen is None:
        _event_shot(adb.screencap(), "dnd_no_mute_settings")
        log("[dnd] SOCIAL SETTINGS (team invites) didn't open — skipping")
        _exit_to_menu(log)
        return False

    changed = []
    if not _radio_selected(screen, config.DND_MUTE_FRIENDS_24H_RADIO):
        adb.tap(*config.DND_MUTE_FRIENDS_24H)  # whole row is tappable
        changed.append("friends=24h")
        time.sleep(0.8)
        screen = adb.screencap()  # re-capture so the next radio check is fresh
    if not _radio_selected(screen, config.DND_MUTE_RECENT_30D_RADIO):
        adb.tap(*config.DND_MUTE_RECENT_30D)
        changed.append("recent=30d")
        time.sleep(0.8)

    # CONFIRM applies + closes the panel. We tap it even when nothing changed — it's the
    # one deterministic way OFF this panel, and confirming already-set values is a no-op.
    adb.tap(*config.DND_MUTES_CONFIRM)
    time.sleep(1.0)
    log(
        f"[dnd] team-invite mutes set ({', '.join(changed)})"
        if changed
        else "[dnd] team-invite mutes already set"
    )
    _exit_to_menu(log)  # close the TEAM UP panel (red ✕) back to the menu
    return True


def apply_dnd(log=print) -> dict:
    """Set the in-game team-invite mutes (the whole of DND since round 6 dropped the
    push-notification leg), guarded so a hiccup is logged but never kills the farm.
    Returns {"invites_muted": bool} for the session log."""
    result = {"invites_muted": False}
    try:
        result["invites_muted"] = ensure_team_invites_muted(log)
    except Exception as e:  # noqa: BLE001 — startup nicety must never kill the farm
        log(f"[dnd] team-invite mutes error: {e!r}")
        _exit_to_menu(log)
    return result


# --- DND OFF (stop etiquette — reverse of the startup flow) ------------------------


def ensure_team_invites_unmuted(log=print) -> bool:
    """Setting A reversed: open the TEAM UP panel's SOCIAL SETTINGS (the exact nav +
    verifies proven by ensure_team_invites_muted) and CLEAR the selected mute in
    BOTH columns (MUTE FRIENDS left, MUTE RECENT TEAMMATES right).

    Mechanism (probe-verified live, 2026-06-10): the panel has no "Don't mute"
    row — only the three timed options — and tapping the currently-SELECTED
    (orange) radio deselects it, which after CONFIRM means unmuted. Every radio
    in the measured grid is colour-checked; only selected ones are tapped, each
    verified to have cleared. Returns True iff the panel was reached AND every
    selected radio cleared; leaves the game on the main menu."""
    adb.tap(*config.DND_TEAM_SLOT)
    if _wait_for_screen("TEAM UP", config.DND_PANEL_WAIT_S) is None:
        log("[dnd-off] TEAM UP panel didn't open — skipping")
        _exit_to_menu(log)
        return False

    time.sleep(1.0)  # same settle + retry rationale as the ON flow
    screen = None
    for _ in range(2):
        adb.tap(*config.DND_TEAMUP_GEAR)
        screen = _wait_for_screen("MUTE", config.DND_SETTINGS_WAIT_S)
        if screen is not None:
            break
    if screen is None:
        _event_shot(adb.screencap(), "dndoff_no_mute_settings")
        log("[dnd-off] SOCIAL SETTINGS (team invites) didn't open — skipping")
        _exit_to_menu(log)
        return False

    # There is NO "Don't mute" row in the current UI (probe 2026-06-10): the panel
    # offers only the three timed mutes per column, and tapping the SELECTED
    # (orange) radio CLEARS it — verified live (the "Muted friends for…" status
    # line is gone after CONFIRM + reopen). So: scan the probe-measured radio
    # grid, tap every selected radio once, verify it cleared, CONFIRM.
    changed = []
    stuck = []
    for col, radios in config.DND_MUTE_RADIO_GRID.items():
        for xy in radios:
            if not _radio_selected(screen, xy):
                continue
            adb.tap(*xy)  # tapping a selected radio DESELECTS it
            time.sleep(0.8)
            screen = adb.screencap()
            if _radio_selected(screen, xy):
                stuck.append(f"{col}@{xy}")  # didn't clear — report, never loop
            else:
                changed.append(col)

    if stuck:
        _event_shot(screen, "dndoff_radio_stuck")
        log(f"[dnd-off] radio(s) would not clear: {', '.join(stuck)}")
    adb.tap(*config.DND_MUTES_CONFIRM)  # applies + closes; no-op when unchanged
    time.sleep(1.0)
    log(
        f"[dnd-off] invite mutes turned OFF ({', '.join(changed)})"
        if changed
        else "[dnd-off] invite mutes already off"
    )
    _exit_to_menu(log)
    return not stuck


def remove_dnd(log=print) -> dict:
    """Reverse the DND mutes (stop etiquette), guarded — and the CALLER
    (Controller.stop) guards the whole thing too, so a DND-off hiccup can never block
    the stop itself. Returns {"invites_unmuted": bool} for the session log."""
    result = {"invites_unmuted": False}
    try:
        result["invites_unmuted"] = ensure_team_invites_unmuted(log)
    except Exception as e:  # noqa: BLE001 — stop etiquette must never block the stop
        log(f"[dnd-off] team-invite unmute error: {e!r}")
        _exit_to_menu(log)
    return result
