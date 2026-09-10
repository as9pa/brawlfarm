"""New-account onboarding: drive the in-game Supercell ID login on a target instance.

The intended flow (the user duplicates a BlueStacks instance manually, then drives the
login from the control panel):
  onboard start <port> <email>  -> this module navigates menu ≡ -> SUPERCELL ID ->
  (gear -> Switch account, when an ID is already connected) -> the SCID login form,
  types the EMAIL, submits; Supercell emails a 6-digit code; the user relays it with
  onboard code <port> <code>; this module types it, completing the login.

CALIBRATION STATUS — read this before trusting it:
  ✅ Calibrated LIVE (read-only taps on a farm account, 2026-06-09, see the config
     "Supercell ID / onboarding" block): menu ≡ -> side menu -> SUPERCELL ID overlay
     -> gear -> SCID SETTINGS (logged-in email line, Switch account / Log Out
     positions, ✕).
  ⚠️ NOT calibrated: everything PAST "Switch account" — the account picker, the
     email form, and the code form. Reaching them requires starting a real
     switch/login, which is forbidden on a live farm account. Those steps are
     OCR-driven best-effort and MUST be validated end-to-end on a fresh instance
     before first real use. Every step saves a screenshot to captures/onboard/ so
     the control panel can show exactly where the flow stands.

SAFETY RAILS (real accounts):
  * Every entry point takes the adb PORT explicitly and REFUSES the registered farm
    instances unless ``allow_farm_instance=True`` (only the read-only ``whoami``
    sets it). Logging a farm account out would be a serious incident.
  * "Log Out" / "Disconnect" are never tapped; the only account-changing tap this
    module makes is "Switch account", and only from ``start_login``.
  * Each hop verifies its screen via OCR and bails out (✕ back to the menu) when
    the expected text isn't there, so a stale coordinate degrades to a no-op.
"""

from __future__ import annotations

import re
import time

import cv2

from brawlfarm.core import config
from brawlfarm.core import adb, vision


# Registered farm instances — DERIVED from config.INSTANCES (not hardcoded) so every
# instance the user registers is automatically covered by the refuse-to-sign-in rail
# below.
def farm_ports() -> frozenset[str]:
    """Ports of registered farm instances, read at call time so runtime registration counts."""
    return frozenset(inst["port"] for inst in config.INSTANCES.values())


class OnboardError(RuntimeError):
    """A navigation step didn't verify; the flow bailed out safely."""


def _use_port(port: int | str, allow_farm_instance: bool) -> None:
    """Point this process's adb at the target instance (same pattern the control
    panel's screenshot action uses) and connect. Refuses farm instances unless
    explicitly allowed (read-only steps only)."""
    port = str(int(port))
    if port in farm_ports() and not allow_farm_instance:
        raise OnboardError(
            f"port {port} is a registered FARM instance — refusing to run an "
            "account-login flow on it. Onboard only fresh instances."
        )
    config.ADB_PORT = int(port)
    config.ADB_SERIAL = f"{config.ADB_HOST}:{port}"
    adb.connect()


def _shot(tag: str):
    """Screenshot the current screen to captures/onboard/ (evidence for the panel);
    returns (image, path)."""
    img = adb.screencap()
    config.ONBOARD_SHOTS_DIR.mkdir(parents=True, exist_ok=True)
    path = config.ONBOARD_SHOTS_DIR / f"{time.strftime('%H%M%S')}_{tag}.png"
    cv2.imwrite(str(path), img)
    return img, path


def _find(screen, needle: str, region=None):
    return vision.find_text(screen, needle, region=region)


def _open_scid_overlay(log) -> None:
    """Main menu -> ≡ -> SUPERCELL ID overlay. Verifies each hop, raises on failure."""
    adb.tap(*config.MENU_BURGER)
    time.sleep(1.2)
    screen, _ = _shot("side_menu")
    item = _find(screen, "SUPERCELL ID", region=config.SIDE_MENU_REGION)
    if item is None:
        adb.tap(*config.MENU_BURGER)  # toggle the side menu back closed
        raise OnboardError("side menu didn't show SUPERCELL ID (not on the menu?)")
    adb.tap(*item)
    time.sleep(2.0)


def _close_overlay() -> None:
    adb.tap(*config.SCID_CLOSE_X)
    time.sleep(1.0)


def read_logged_in_email(port: int | str, log=print, allow_farm_instance: bool = True):
    """READ-ONLY: which Supercell ID email is connected on this instance (or None if
    it doesn't show one). Path: ≡ -> SUPERCELL ID -> gear -> OCR the 'Logged in
    with' line -> ✕ out. Safe on farm instances (taps verified live)."""
    _use_port(port, allow_farm_instance)
    _open_scid_overlay(log)
    adb.tap(*config.SCID_GEAR)
    time.sleep(1.5)
    screen, path = _shot("scid_settings")
    email = None
    for text, _conf in vision.read_lines(screen, region=config.SCID_EMAIL_REGION):
        if "@" in text:
            email = text.strip()
            break
    _close_overlay()  # the settings panel's ✕ (also clears the overlay)
    log(f"[onboard] logged-in email on :{port} -> {email or 'not found'}")
    return email, path


def start_login(port: int | str, email: str, log=print) -> tuple[str, object]:
    """Drive the login up to (and including) typing the EMAIL. Returns
    (status, screenshot_path) where status explains how far it got. Statuses:
    'email_submitted' (code now expected) or an OnboardError is raised.

    ⚠️ The post-"Switch account" steps are UNCALIBRATED (see module docstring) —
    OCR-driven, screenshot at every step, bail on anything unexpected."""
    # Validate BEFORE any navigation: the email is user-supplied (via the panel) and is
    # eventually typed through `adb shell input text`, which re-evaluates through the
    # device-side shell — this whitelist also guarantees shell-safety (see
    # docs/future-plans/multi-user-security.md and adb.input_text's gate).
    email = str(email).strip()
    if not re.fullmatch(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", email):
        raise OnboardError(f"not a valid email address: {email!r}")
    _use_port(port, allow_farm_instance=False)
    _open_scid_overlay(log)
    screen, _ = _shot("scid_overlay")

    if _find(screen, "REWARDS", region=config.SCID_PANEL_REGION) is not None:
        # An ID is already connected (the overlay shows ID REWARDS/FRIENDS/MY GAMES):
        # go through gear -> Switch account.
        log("[onboard] an ID is connected — opening gear -> Switch account")
        adb.tap(*config.SCID_GEAR)
        time.sleep(1.5)
        screen, _ = _shot("scid_settings")
        item = _find(screen, "Switch account", region=config.SCID_PANEL_REGION)
        if item is None:
            _close_overlay()
            raise OnboardError("SCID settings didn't show 'Switch account' — bailed")
        adb.tap(*item)
        time.sleep(2.0)
        screen, _ = _shot("switch_account")
        # Account picker (uncalibrated): look for a "log in with another ID"-style
        # entry. Try several label fragments seen across SCID versions.
        for needle in ("another", "Log in", "LOG IN", "Add account"):
            item = _find(screen, needle)
            if item is not None:
                adb.tap(*item)
                time.sleep(2.0)
                break
        else:
            _close_overlay()
            raise OnboardError(
                "couldn't find a 'log in with another ID' entry on the account "
                "picker — see captures/onboard/switch_account.png"
            )
        screen, _ = _shot("login_entry")

    # Email form (uncalibrated): find the email field by its placeholder / label,
    # tap to focus, type, then submit via a Continue/Log in-style button.
    field = None
    for needle in ("email", "E-mail", "Email address"):
        field = _find(screen, needle)
        if field is not None:
            break
    if field is None:
        _close_overlay()
        raise OnboardError(
            "couldn't find the email field — see the captures/onboard/ screenshots"
        )
    adb.tap(*field)
    time.sleep(1.0)
    adb.input_text(email)
    time.sleep(0.8)
    screen, _ = _shot("email_typed")
    for needle in ("Continue", "Log in", "LOG IN", "Next"):
        btn = _find(screen, needle)
        if btn is not None:
            adb.tap(*btn)
            time.sleep(2.0)
            break
    else:
        raise OnboardError("typed the email but found no submit button — left as-is")
    _, path = _shot("email_submitted")
    log(f"[onboard] email submitted on :{port} — waiting for the 6-digit code")
    return "email_submitted", path


def enter_code(port: int | str, code: str, log=print) -> tuple[str, object]:
    """Type the 6-digit verification code (relayed by the user via the panel) into the
    code form. UNCALIBRATED: assumes the code field is focused (SCID focuses it after
    the email submit); screenshots before/after so the result is verifiable."""
    code = "".join(c for c in str(code) if c.isdigit())
    if len(code) != 6:
        raise OnboardError(f"expected a 6-digit code, got {code!r}")
    _use_port(port, allow_farm_instance=False)
    screen, _ = _shot("before_code")
    field = _find(screen, "code")
    if field is not None:
        adb.tap(*field)  # focus the field if a label/placeholder is visible
        time.sleep(0.8)
    adb.input_text(code)
    time.sleep(2.5)
    _, path = _shot("after_code")
    log(f"[onboard] code typed on :{port} — check the screenshot for the result")
    return "code_typed", path
