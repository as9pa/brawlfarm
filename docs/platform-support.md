# Platform support

brawlfarm supports only Windows 11 with BlueStacks 5 today. That is down to concrete code paths, not policy. A port to another emulator or operating system would have to replace:

- Instance discovery: `brawlfarm.setup.discover` reads the instances and their adb ports from `%PROGRAMDATA%\BlueStacks_nxt\bluestacks.conf`.
- The adb binary: `brawlfarm.core.adb` wraps BlueStacks' bundled `HD-Adb.exe`, whose default path is in `brawlfarm.settings` and `brawlfarm.core.config`.
- The data folder: `brawlfarm.settings` puts it under `%LOCALAPPDATA%\brawlfarm` unless `BRAWLFARM_HOME` is set.
- The display check: `brawlfarm.core.controller` (and `brawlfarm.core.observer` in observe mode) stops the worker on any display other than 1600 x 900, and `brawlfarm.setup.checks` checks the pixel density of 240 in the setup wizard.
- The open-folder buttons: the endpoints in `brawlfarm.api.settings_routes` and `brawlfarm.api.calibration` use `os.startfile` and answer 501 off Windows.
- CI: `.github/workflows/ci.yml` runs on `windows-latest`.

Template matching and OCR are tied to that display size, so a new size is a recalibration, not a config change. Pull requests for other platforms are welcome under the safety-rail rule in [development.md](development.md#contributing).
