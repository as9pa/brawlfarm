# Training the play mode detector

## What this kit is

Tools under `tools/play/` that turn video of Brawl Stars into a labelled training set, and
turn a labelled set into a scored detector. A **class** is one kind of thing the detector
learns to find, such as `enemy` or `play_button`. A **box** is the rectangle drawn around one
instance of a class in one frame.

## What this kit is not

No model ships with this pull request. Running every step below leaves you with a folder of
data and, if you go all the way to training, a `play.onnx` file on your own disk. The first
model the project ships arrives later, in its own calibration pull request, together with the
training set hash, the score report, and the held-out numbers.

## Where the data lives

Nothing this kit touches enters the repository: no video, no frame, no label, no model. Every
tool takes `--root`, and without it the default is `%LOCALAPPDATA%\brawlfarm\datasets\play` (or
under `BRAWLFARM_HOME` if you have that set). The layout under the root:

```
videos/<source>.mp4              downloads kept for re-extraction
frames/<source>/<source>-NNNNNN.jpg   1600 x 900 JPEG frames
index.jsonl                      one line per kept frame
labelstudio/config.xml           the labelling interface
labelstudio/tasks.json           the import file, with pre-label boxes
coco/{train,valid,test}/         the training set, split by source
runs/<YYYYmmdd-HHMMSS>/          training output
models/play.onnx, models/play.json    export output
```

## Step 1: frames from your own recordings

If you have run brawlfarm with the recorder on, you already have sessions under
`%LOCALAPPDATA%\brawlfarm\calibration\recordings\<instance>\<session>`. Only frames recorded
at full size (1600 x 900) are usable; a session recorded at half size has nothing to give here.

```
uv run python tools/play/frames.py --session %LOCALAPPDATA%\brawlfarm\calibration\recordings\Pie64\20260918-101112
```

A session's `match-N.h264` files are their own sources, worth extracting separately because
they cover in-match play that the menu frames do not:

```
uv run python tools/play/frames.py --match match-1.h264 --source pie64-match-1
```

`frames.py` also takes `--video` for any container video, `--source` to name the source
(default is the file or folder name), and `--again` to add a source that is already in the
index. Extraction samples 2 frames a second and throws away near-duplicates, so a long session
keeps far fewer frames than it has seconds: a 181 frame menu session kept 138.

## Step 2: frames from YouTube

Put one URL per line in a text file, `#` for a comment line. Only
`https://www.youtube.com/watch?v=<id>` and `https://youtu.be/<id>` are accepted, and only the
11 character video id ever reaches the downloader or a file name.

```
uv run python tools/play/ingest_youtube.py urls.txt
```

`--root` picks the dataset root and `--keep-going` carries on after a failed download instead
of stopping the whole list. The video list is your own choice: pick mobile gameplay with a
clean, uncovered HUD, because anything covering the joystick, the cards or the buttons is a bad
example for the detector and for the HUD reader that comes later. The videos are downloaded
into `videos/` and stay on your disk; two 27 minute videos gave 2677 kept frames from 877 MB of
video, in about 8 minutes. Some creators bake black borders into their video; those are
trimmed per source before frames are cut, and the trim is recorded in `index.jsonl` so it can
be reversed.

## Step 3: pre-labels

The farm's own template matcher already knows how to find a handful of screens, so it can draw
a first draft of some boxes for you instead of you drawing every one by hand.

```
uv run python tools/play/prelabel.py
```

`--root` picks the dataset root, and `--source` restricts pre-labelling to one source (repeat
the flag for more). Pre-labelling covers only `showdown_card`, `play_button`,
`play_again_button`, `proceed_button`, `exit_button` and `close_x`. Everything that happens
inside a match (`self`, `enemy`, `teammate`, `power_cube`, `box`, `bush`) and `skull_star`,
`team_up_panel`, `event_tab` have no template behind them and are labelled by hand. Pre-labelling
2815 frames took about 9.5 minutes.

## Step 4: labelling in Label Studio

[Label Studio](https://labelstud.io/) is the tool you draw boxes in. Version 1.23.0 is what
this kit was checked against, on Python 3.12 (Python 3.13 has not been tried). Start it with
the local file server turned on and pointed at the dataset root, PowerShell:

```
$env:LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED = "true"
$env:LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT = "$env:LOCALAPPDATA\brawlfarm\datasets\play"
uvx --python 3.12 label-studio start
```

Then, in the browser window Label Studio opens:

1. Create a project.
2. Settings, Labeling Interface, Code: paste the contents of `labelstudio/config.xml`.
3. Settings, Cloud Storage, Add Source Storage, Local files: set the absolute local path to
   the dataset root's `frames` folder. Do not press Sync; the tasks come from the import file
   in the next step, and this storage only lets Label Studio serve the images.
4. Import: `labelstudio/tasks.json`. The import screen shows how many predictions it found;
   opening a task shows a frame with its pre-label boxes already drawn, where it has any.

What each class means:

- `self`: your own brawler.
- `enemy`: an opposing brawler.
- `teammate`: a brawler on your team, not yourself.
- `power_cube`: a power cube on the ground.
- `box`: a breakable box.
- `bush`: a bush a brawler can hide in.
- `showdown_card`: the card shown at the start or end of a Showdown match.
- `skull_star`: the star marking the last standing player in Showdown.
- `team_up_panel`: the panel offering a team-up in Showdown.
- `event_tab`: the tab for the current event on the home screen.
- `play_button`: the main Play button.
- `play_again_button`: the Play Again button on a results screen.
- `proceed_button`: the Proceed button, such as after a reward screen.
- `exit_button`: an Exit button.
- `close_x`: a close (X) control on a dialog or banner.

Labelling rules:

- Box the whole sprite, not just the part that is easiest to see.
- Skip frames with no game in them (loading screens, black frames): leave them with no boxes.
- Never label names or tags. A player's name or club tag showing in a screenshot is not a
  class this kit tracks, and it should never be typed into a label.

## Step 5: export and build the COCO set

Export the project as **JSON**, not JSON-MIN and not COCO. Label Studio's own COCO export does
not carry the split rule this kit needs, so `coco.py` does the conversion:

```
uv run python tools/play/coco.py export.json
```

`--root` picks the dataset root. `--from-predictions` builds the set from the template
pre-labels instead of the hand-labelled boxes, which is only useful for a smoke run before any
labelling has happened.

The split is by source video, never by frame: consecutive frames of one video look almost
identical, so splitting by frame would put near-copies of the same picture on both sides of the
split and make the score look better than the model really is. A source is assigned to a
**split** (`train`, `valid` or `test`) by hashing its name, and train always keeps the largest
split. With fewer than three sources there are not enough videos to split at all, so `coco.py`
writes the same frames into all three splits and marks the layout as a smoke set; every later
tool in this kit warns when it sees that mark.

## Step 6: train

`train.py` is a self-contained script: `uv run tools/play/train.py` builds its own environment
on first run, including torch from the CUDA 12.8 index, about 3 GB. It never touches the
project's own `pyproject.toml` or lock file.

```
uv run tools/play/train.py --epochs 8
```

`--root` picks the dataset root, `--epochs` the number of passes over the training set (an
**epoch** is one full pass over the training data; the default is 60, a real run needs many
more than the 8 used for a smoke test), `--batch` the number of images per training step, and
`--accum` the number of steps to accumulate gradients over before updating the model, which
lets a small GPU behave like a bigger one. On an RTX 4080 SUPER, 8 epochs on a tiny set took
about 50 seconds; a real run takes much longer. Output goes to `runs/<YYYYmmdd-HHMMSS>/`.

## Step 7: export

```
uv run tools/play/export.py --run runs/20260918-101112
```

`--root` picks the dataset root, `--run` the training run to export (a folder path, or a name
under `runs/`; without it the most recent run is used). Export converts the trained model to
**ONNX**, a portable model file format, then runs the ONNX model over the validation images and
checks its output against the training library's own output on the same images, so a broken
conversion is caught here rather than later. On the same RTX 4080 SUPER, export took about 25
seconds and produced a `play.onnx` file of about 119 MB.

Export also picks a **threshold** for every class: the score above which a detection counts.
For each class, it is the lowest threshold between 0.30 and 0.95 that still keeps
**precision** (the fraction of the model's detections of that class that are actually correct)
at or above 0.98 on the validation images. A class with no validation images gets 0.95, the
most cautious threshold available. Thresholds and the run they came from are written to
`play.json` next to `play.onnx`.

## Step 8: score

```
uv run python tools/play/score.py
```

`--root` picks the dataset root, `--models` the folder holding `play.onnx` (default
`models/`), `--frames` adds a folder of pictures to score besides the dataset root's own frames
(repeat the flag for more), and `--cuda` asks for the CUDA execution provider.

`score.py` compares the exported model against the farm's own templates on every 1600 x 900
frame it can find. The bar is not an average score: it is that the model never produces a
**false positive** (a detection that should not be there) on a tap anchor, a class the farm
would act on, because a tap on the wrong pixel can spend gems or leave a match queue. A single
extra detection next to a correct one still fails the whole report. Missing a control the
template found is only logged, not failed, because a miss just means a slower loop rather than
a wrong tap. A run that scores no frames at all also fails, since a silent zero is not a pass.
Three tap anchors have no template behind them (`skull_star`, `team_up_panel`, `event_tab`);
those are listed separately as unverified and do not count toward the bar either way.

## How the first model ships

No `play.onnx` or `play.json` is committed by this kit. Once a run passes `score.py`, the
model and its thresholds move into a calibration pull request of their own, one that also
carries the training set hash from `coco/split.json`, the score report, and the held-out
numbers the model was judged on. That is the pull request an owner reviews before the detector
is allowed anywhere near a live instance.
