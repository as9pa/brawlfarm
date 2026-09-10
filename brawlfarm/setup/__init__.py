"""The setup wizard's probes: find adb, list the BlueStacks instances and their ports,
test one, and check that its display is 1600 x 900 at DPI 240.

Deliberately separate from core/adb.py. The core's adb module reads the process-global
config (one instance per worker process); these run in the panel's process against any
port the user points at, so they take the adb path as an argument and build their own
`-s 127.0.0.1:<port>` serial. Nothing here mutates core.config.
"""
