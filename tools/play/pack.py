"""The label pack: everything Label Studio needs, in one folder, for a computer with no checkout.

The labeller may be on a Mac with nothing of this repository on it, so the pack carries the
frames the import file points at, the interface config, the import file itself, a start script
for macOS and Linux and one for Windows, and a README written for someone who has never opened
Label Studio. The task paths stay relative (`frames/...`), and the start scripts point Label
Studio's local file server at the pack's own folder, so they resolve wherever it is unzipped.

    uv run python tools/play/pack.py
    uv run python tools/play/pack.py --root D:/play-data --source yt-AAAAAAAAAAA --no-zip
"""

from __future__ import annotations

import argparse
import json
import shutil
import zipfile
from pathlib import Path, PurePosixPath

from tools.play import dataset, prelabel

# Copied verbatim from docs/play-training.md, Step 5; a test keeps the two the same.
CLASS_NOTES = """\
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
- `gas`: the Showdown poison cloud. Box the visible cloud area, edge to edge, one box per
  connected area; the policy uses the box's near edge to know where the safe ground ends.

Labelling rules:

- Box the whole sprite, not just the part that is easiest to see.
- Skip frames with no game in them (loading screens, black frames): leave them with no boxes.
- Never label names or tags. A player's name or club tag showing in a screenshot is not a
  class this kit tracks, and it should never be typed into a label.
"""

START_SH = """\
#!/usr/bin/env bash
# Starts Label Studio with its local file server pointed at this folder.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if ! command -v uv >/dev/null 2>&1; then
  echo "uv is not installed; follow step 1 of README.md, then open a new terminal." >&2
  exit 1
fi
export LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED=true
export LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT="$here"
echo "Frames folder for the Local files storage: $here/frames"
exec uvx --python 3.12 label-studio start
"""

START_PS1 = """\
# Starts Label Studio with its local file server pointed at this folder.
$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Error "uv is not installed; follow step 1 of README.md, then open a new window."
    exit 1
}
$env:LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED = "true"
$env:LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT = $here
Write-Host "Frames folder for the Local files storage: $(Join-Path $here 'frames')"
uvx --python 3.12 label-studio start
"""

README = """\
# Label pack

This folder holds {frames} frames to label, from {sources}, and everything Label Studio needs
to show them. Label Studio is a free program that runs in your web browser; you draw a box
around each thing in a picture and pick what it is. Nothing here needs the brawlfarm
repository.

Below, `<pack>` means the full path of this folder, the one this README is in, for example
`/Users/you/Downloads/label-pack` on a Mac or `C:\\Users\\you\\Downloads\\label-pack` on
Windows.

## Start Label Studio

1. Install `uv`, the tool that downloads and runs Label Studio for you. On a Mac, open the
   Terminal app and run:

   ```
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

   On Windows, open PowerShell and run:

   ```
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

   Then close that window and open a new one, so it can find `uv`.

2. Go to this folder and run the start script. On a Mac or Linux:

   ```
   cd <pack>
   ./start.sh
   ```

   If it says permission denied, run `bash start.sh` instead. On Windows:

   ```
   cd <pack>
   powershell -ExecutionPolicy ByPass -File .\\start.ps1
   ```

   The first start downloads Label Studio and takes a few minutes. The script sets
   `LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED` to `true` and
   `LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT` to this folder, which is what lets Label Studio
   show the pictures from here. It also prints the frames folder path you need in step 6.
   Leave the window open while you label; closing it stops Label Studio.

3. Label Studio opens in your browser (if it does not, go to http://localhost:8080). Sign up
   with any email and password; the account only exists on this computer.

## Set up the project

4. Create a project. Give it any name.
5. Open the project's Settings, then Labeling Interface, then Code. Replace what is there with
   the contents of `labelstudio/config.xml` from this folder, and save.
6. In Settings, open Cloud Storage, choose Add Source Storage, and pick Local files. Set the
   absolute local path to `<pack>/frames` (on Windows `<pack>\\frames`), with `<pack>`
   replaced by the folder you unzipped to; the start script printed this path. Save it. Do not
   press Sync: the tasks come from the import in the next step, and this storage only lets
   Label Studio show the pictures.
7. Go back to the project and press Import. Choose `labelstudio/tasks.json` from this folder.
   Some frames already have draft boxes drawn on them; check them and fix what is wrong.

## Label

8. Open a task, pick a class, and drag a box around the thing. Submit when the frame is done,
   and move on to the next one. Your work is saved as you go; you can stop the start script
   and run it again later to carry on.

{notes}
## Send the labels back

9. On the project page press Export and choose **JSON**. Not JSON-MIN and not COCO: only the
   plain JSON export carries what the training tools need.
10. Send the exported file back to the computer this pack came from.
"""


def _source_of(rel: object) -> str | None:
    """The source of a task's frame path, or None if the path is not `frames/<source>/<x>.jpg`.

    The path decides where a file is copied to inside the pack, so anything that could climb
    out of it, or name a folder that is not a plain source name, is rejected.
    """
    if not isinstance(rel, str):
        return None
    parts = PurePosixPath(rel).parts
    if len(parts) != 3 or parts[0] != "frames" or not parts[2].endswith(".jpg"):
        return None
    if parts[2] in {".", ".."} or "\\" in rel:
        return None
    try:
        return dataset.check_source(parts[1])
    except ValueError:
        return None


def _is_pack(folder: Path) -> bool:
    return (folder / "start.sh").is_file() and (folder / "labelstudio" / "tasks.json").is_file()


def _write_zip(folder: Path, archive: Path) -> None:
    """Every file under `folder`, stored under its name so it unzips into one folder.

    JPEGs are already compressed, so they are stored as they are; the rest is deflated. The
    scripts get a Unix mode so an unzip on a Mac keeps `start.sh` executable.
    """
    tmp = archive.with_name(archive.name + ".part")
    with zipfile.ZipFile(tmp, "w") as zf:
        for path in sorted(folder.rglob("*")):
            if not path.is_file():
                continue
            name = f"{folder.name}/{path.relative_to(folder).as_posix()}"
            info = zipfile.ZipInfo.from_file(path, name)
            info.create_system = 3
            mode = 0o755 if path.suffix in {".sh", ".ps1"} else 0o644
            info.external_attr = (0o100000 | mode) << 16
            info.compress_type = (
                zipfile.ZIP_STORED if path.suffix == ".jpg" else zipfile.ZIP_DEFLATED
            )
            with path.open("rb") as src, zf.open(info, "w") as dst:
                shutil.copyfileobj(src, dst)
    tmp.replace(archive)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--root", type=Path, default=None, help="dataset root")
    ap.add_argument(
        "--out", type=Path, default=None, help="pack folder (default <root>/label-pack)"
    )
    ap.add_argument(
        "--source",
        action="append",
        default=None,
        metavar="NAME",
        help="pack only this source; repeat for more",
    )
    ap.add_argument("--no-zip", action="store_true", help="write the folder only")
    args = ap.parse_args(argv)

    root = args.root if args.root is not None else dataset.default_root()
    out = args.out if args.out is not None else root / "label-pack"
    wanted = {dataset.check_source(name) for name in args.source} if args.source else None
    tasks_path = root / "labelstudio" / "tasks.json"
    if not tasks_path.exists():
        print(f"no import file at {tasks_path}; run tools/play/prelabel.py first")
        return 1
    if out.exists() and any(out.iterdir()) and not _is_pack(out):
        # A rerun replaces the old pack; anything else in the way is someone's folder.
        print(f"{out} is not empty and is not a label pack; pick another --out")
        return 1

    tasks = json.loads(tasks_path.read_text(encoding="utf-8"))
    kept = []
    sources: set[str] = set()
    missing = 0
    bad = 0
    for task in tasks:
        rel = task.get("data", {}).get("file") if isinstance(task, dict) else None
        source = _source_of(rel)
        if source is None:
            bad += 1
            continue
        if wanted is not None and source not in wanted:
            continue
        if not (root / rel).is_file():
            # The pack must match its import file, so a task without its frame is dropped.
            missing += 1
            continue
        kept.append(task)
        sources.add(source)

    if out.exists():
        shutil.rmtree(out)
    (out / "labelstudio").mkdir(parents=True)
    for task in kept:
        rel = task["data"]["file"]
        dest = out / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / rel, dest)
    (out / "labelstudio" / "tasks.json").write_text(json.dumps(kept, indent=1), encoding="utf-8")
    shutil.copyfile(prelabel.CONFIG_XML, out / "labelstudio" / "config.xml")
    # Bytes, not text: a text write on Windows would give start.sh CRLF endings, and bash on a
    # Mac cannot run a script whose first line ends in a carriage return.
    (out / "start.sh").write_bytes(START_SH.encode("utf-8"))
    (out / "start.ps1").write_bytes(START_PS1.replace("\n", "\r\n").encode("utf-8"))
    names = ", ".join(sorted(sources)) or "no sources"
    readme = README.format(frames=len(kept), sources=names, notes=CLASS_NOTES)
    (out / "README.md").write_bytes(readme.encode("utf-8"))
    (out / "start.sh").chmod(0o755)

    print(f"{len(kept)} frames, {missing} missing, {bad} with a bad path")
    print(f"sources: {names}")
    print(f"folder: {out}")
    if not args.no_zip:
        archive = out.with_name(out.name + ".zip")
        _write_zip(out, archive)
        print(f"zip: {archive} ({archive.stat().st_size / 1_000_000:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
