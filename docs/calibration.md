# Calibration

brawlfarm taps fixed coordinates on a 1600 x 900 screen at 240 DPI and matches thirteen templates against the frame it just captured. A game update that moves a button, or a skin that repaints one, breaks that without breaking anything else. The Calibration page shows you what the workers see, and the calibration folder is where you correct it without touching the code.

## What the page shows

The page lives at `http://127.0.0.1:8765/calibration`, behind Calibration in the left rail. Pick the instance you want along the top; everything below follows that choice.

The frame is the instance's own live capture with the calibration drawn over it, in the worker's 1600 x 900 coordinates, so a tap written at 1434, 830 is drawn at 1434, 830. A toggle draws the tap points, the anchor boxes, or both. It is a picture and nothing else: no click anywhere on it moves a coordinate.

The anchor table has one row per template, with the threshold it has to beat, the score it got on this frame, a status and when it was last seen. Found means the score reached the threshold. Drift means the phase the worker is in expects this anchor and the frame did not produce it, which is the row worth investigating. Absent means the anchor is simply not on this screen, which is the normal answer for most rows.

The overrides table lists every constant `calibration.toml` may override, grouped into tap, threshold and timing, each with its current value, the packaged default, and whether that value came from the package or from the file. The templates are listed the same way, each with its size and its source. Anything wrong in the file is reported here as a problem, and if the file has changed since the process started, the table says so.

Open folder opens the calibration folder in Explorer, creating it if this is the first time. That button is Windows only.

## Where the folder is

By default the folder is `%LOCALAPPDATA%\brawlfarm\calibration\`. Under `--home <path>` it follows the data directory, at `<home>/calibration`. It holds `calibration.toml`, the `templates` folder and the `recordings` folder, and nothing there is required: an empty or missing folder means the packaged values are used.

## calibration.toml

The file is flat TOML, one key per line, and the keys are constant names from `brawlfarm/core/config.py`. Two kinds of value can be overridden: a tap coordinate, written as an array of two integers, and a float, which covers the match thresholds and the timings.

```toml
PLAY_BUTTON = [1434, 830]
MATCHMAKING_THRESHOLD = 0.85
```

Only uppercase constants whose packaged value is already a float or a two-integer tuple are overridable. `SCREEN_W`, `SCREEN_H` and `SCREEN_DPI` are locked, because a different screen size does not move one button, it invalidates every template and every coordinate at once.

A bad line is skipped and reported, and the rest of the file still applies. A key that is not a constant, a misspelled `PLAY_BUTON` for instance, gives `PLAY_BUTON is not a calibration constant. The line is ignored.`, a float key given something that is not a number gives `MATCHMAKING_THRESHOLD must be a number.`, and a tap key given anything other than two integers gives `PLAY_BUTTON must be two integers.` A file that will not parse at all applies nothing and reports `calibration.toml could not be read:` with the parser's own complaint.

The file is read once, when the process starts. Editing it while brawlfarm is running changes nothing until you restart brawlfarm and the workers, and the page tells you when the file on disk has moved on from what the running process read.

## Template overrides

To replace a packaged template, drop a PNG at `<home>/calibration/templates/<name>.png`. The thirteen names are `close_x`, `exit`, `matchmaking`, `other_device`, `play`, `playagain`, `proceed`, `reload`, `skin_popup`, `teams_left`, `trio_showdown`, `trophy_brawler` and `trophy_screen`. The name has to match one of those exactly; a file under any other name is ignored, because an override replaces a template and never adds one.

The crop does not have to be the same size as the file it replaces, but it does have to come from a 1600 x 900 frame at 240 DPI, like the packaged ones. Cut it tight around the thing you want matched and leave the background out of it.

An override is picked up on the next capture, by its modified time, with no restart. Deleting the file goes back to the packaged template just as quickly.

## Recording frames

The Record frames switch on the page starts a labeled recording for the chosen instance. It writes an empty `record.flag` in that instance's data folder, at `instances/<name>/record.flag`, and the worker notices within a few ticks and answers in `recorder.json`. Turning the switch off closes the session; turning it on again starts a new one.

A session is a folder under the calibration folder at `recordings/<instance>/<yyyymmdd-hhmmss>/`. Each frame is a JPEG named `NNNN-state.jpg`, where `NNNN` is a four-digit counter and `state` is the worker's state at the moment of the capture. Beside them, `labels.jsonl` carries one JSON line per frame with `seq`, `ts`, `file`, `state`, `phase` and `scores`, where `scores` is every template's score against that frame. That is the corpus you can rescore a candidate threshold or a re-cut template against afterwards.

The cadence is at most one frame per second, so a long sit on a menu costs a frame a second rather than a frame a tick, and a state change is always recorded whatever the clock says.

Two caps stop a recording from filling the disk. A session closes at 2000 frames, and no new session opens once the instance's recordings reach 512 MiB. The page names the reason either way, `frame_cap` or `disk_cap`, and reports `error` if a frame could not be written, which also closes the session.

The recorder never deletes anything. Clearing space is your job: delete the session folders you are done with from the calibration folder.

## Record while I play

Recording frames captures what the bot sees, which is only the handful of screens the bot
visits. Record while I play captures what you see. Stop the instance, turn the switch on,
and the supervisor launches a worker in observe mode: it connects, checks the display is
1600x900, and from then on it screencaps about twice a second, labels each frame with the
state its anchors prove and writes it to the same session folder the recorder uses. Then
you play the game by hand and walk it through whatever screens the next calibration needs.

Observe mode never taps. It is a separate module from the farm controller and it imports
nothing that can send an input event, which two tests enforce: one reads its source and
fails on any adb input call, and one imports it in a fresh interpreter and fails if the
controller, the brawler screen, the quests screen, the reward paths or the core settings
came along with it.

It is one worker per instance either way, so observe mode takes the same slot a farming
worker would. That is why the switch refuses to start on a running instance: stop it
first. Turning the switch off is an ordinary stop.

The session ends at the same 2000 frame cap a farm recording has, which is roughly half an
hour of distinct screens. When it stops, turn the switch on again for a new folder.

## Safety

The page reads and the files write. Nothing on the page moves a tap point, and no route behind it writes a coordinate: the calibration routes serve the constants, the templates, the anchor scores and the recorder switch, and the only one that writes at all creates the calibration folder or flips `record.flag`. Changing a value means editing `calibration.toml` or dropping a PNG in `templates`, by hand, on purpose.

That holds for the repository too. As `CONTRIBUTING.md` puts it, the calibration block of `brawlfarm/core/config.py`, and the tap coordinates and OCR needles in `brawlfarm/core/controller.py`, `brawlfarm/core/states.py` and `brawlfarm/core/vision.py`, change only in a dedicated calibration PR that carries live evidence: the frames you matched against and the scores you measured. Do not fold a coordinate change into a feature PR. The calibration folder is how you try a value out before it ever gets that far.
