"""The control panel's HTTP surface: a FastAPI app on 127.0.0.1 that drives the
supervisor, reads the instance directories and streams events to the browser.

No authentication (spec section 3): the app refuses every client that is not on the
loopback interface instead. Nothing in this package writes to core.config globals -- the
process-global adb path and player tag belong to a worker, not to the panel.
"""
