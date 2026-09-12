"""Optional desktop window and tray icon (uv sync --group desktop).

Imports of pywebview, pystray and Pillow are lazy so the base install never
needs them. Quit does what Ctrl+C does: the server and supervisor stop,
worker processes keep running.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

MISSING_MESSAGE = (
    "The desktop window needs the optional extras.\n"
    "Run: uv sync --group desktop\n"
    "Opening in the browser instead."
)

ACCENT = (0xE0, 0xB8, 0x4B, 0xFF)


def available() -> bool:
    try:
        import PIL  # noqa: F401
        import pystray  # noqa: F401
        import webview  # noqa: F401
    except ImportError:
        return False
    return True


def _icon_image():
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle((6, 6, 58, 58), radius=14, fill=ACCENT)
    return img


def run(url: str, *, running: Callable[[], int], quit_cb: Callable[[], None]) -> None:
    """Open the panel in a window and hold the main thread until the user quits. Closing
    the window only hides it; the tray icon brings it back and Quit ends the run."""
    import pystray
    import webview

    window = webview.create_window("brawlfarm", url, width=1280, height=800)
    warned = {"done": False}
    icon: pystray.Icon | None = None

    def on_closing() -> bool:
        window.hide()
        if icon is not None and not warned["done"]:
            warned["done"] = True
            try:
                icon.notify("brawlfarm is still running. Open it again from the tray icon.")
            except Exception:  # notification support varies by platform
                pass
        return False  # cancel the close

    def show(icon_, item) -> None:
        window.show()

    def quit_(icon_, item) -> None:
        quit_cb()
        icon_.stop()
        window.destroy()

    def title(item) -> str:
        return f"brawlfarm, {running()} running"

    menu = pystray.Menu(
        pystray.MenuItem(title, None, enabled=False),
        pystray.MenuItem("Open panel", show, default=True),
        pystray.MenuItem("Quit", quit_),
    )
    icon = pystray.Icon("brawlfarm", _icon_image(), "brawlfarm", menu)
    window.events.closing += on_closing
    threading.Thread(target=icon.run, name="tray", daemon=True).start()
    webview.start()
