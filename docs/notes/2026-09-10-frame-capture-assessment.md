# Frame capture: adb screencap versus direct window capture

Date: 2026-09-10. Status: assessed, not scheduled. Verdict: keep `adb screencap`.

A separate review of the worker's frame loop suggested replacing `adb screencap`
with direct capture of the BlueStacks window (dxcam or Windows Graphics Capture)
behind a config flag with an ADB fallback. This note records the measurements
and the reasons for not doing it, so the question is not reopened from memory.

## What the loop costs today

Measured live on the development machine with one instance (Pie64 on port 5555)
and no worker running. Single-instance numbers; adb-server contention with two
or three farming workers was not measured.

| Step | Measured |
| --- | --- |
| `adb.screencap()` (raw capture path) | median 172 ms (159 to 208) |
| `states.classify()` full chain on an unknown frame | 365 to 371 ms |
| `vision.find` per gray template | 16 to 20 ms |
| `vision.find` for `close_x` and `matchmaking` (colour only, 3 channels) | 95 ms and 121 ms |
| `PrintWindow(hwnd, hdc, PW_RENDERFULLCONTENT)` on the render child | 5.1 ms median |
| `PrintWindow` without that flag | black frame |
| BlueStacks render client area | 655 x 368 on a 1920 x 1080 desktop at 96 DPI |

The capture comment in `brawlfarm/core/config.py` cites 370 to 570 ms from the
legacy project's measurements. On this machine, today, the raw path is 172 ms.
An in-match iteration is roughly 172 ms capture, 130 ms classify and the
200 ms `LOOP_POLL_INTERVAL` sleep: capture is about a third of the loop, the
literal sleep is the largest single item, and one colour template
(`close_x`, run on every frame over the full 1600 x 900 image) is a fifth.

## Candidate APIs

- dxcam 0.3.0: Desktop Duplication over a screen region. The window must be
  on screen and unoccluded, and several BlueStacks windows cannot all be
  visible on one desktop. Wrong tool for more than one instance.
- windows-capture 2.0.1: takes a window handle, works when occluded, delivers
  frames on a background thread through a callback with a zero-copy view that
  must be copied inside the callback. Viable per window, at the cost of a
  Rust-built binary dependency and a thread inside a deliberately
  single-threaded worker.
- PrintWindow with `PW_RENDERFULLCONTENT` through ctypes: correct and 5 ms on
  this machine (the instance renders through OpenGL and is black without the
  flag). The cheapest working path with no packaging cost, if window capture
  is ever revisited.

## Multi-instance

The instance to window chain is solvable: `bluestacks.conf` maps the instance
key to its adb port (already parsed by `brawlfarm/setup/discover.py`),
`HD-Player.exe` runs with `--instance <key>`, so the pid comes from psutil and
the window handle from the pid. Matching on the window title would be wrong,
because the title is the display name, not the config key. The handle changes
on every BlueStacks restart and must be re-resolved on capture failure. A
minimized window stops rendering: Windows Graphics Capture yields nothing and
PrintWindow yields the last stale frame, and the worker cannot stop the user
minimizing or resizing the window.

## Coordinate mapping (the blocker)

Templates are cut at 1600 x 900. The render window is 655 x 368, so captured
frames would have to be upscaled 2.44 times before matching. Comparing an
upscaled window frame against the simultaneous adb frame: colour agrees (mean
absolute difference 1.67, p95 6) but resampling inflates false template scores
by up to 0.10 (`reload` +0.103, `close_x` +0.036, `trophy_brawler` +0.025).
`close_x` is documented at a 0.006 margin between its lowest true and highest
false score. Taps sent over adb stay in device coordinates and are safe, but
several taps are derived from frame matches (`green_cta`, `close_x`,
`CONTINUE`, the mode cards, `reload`, `MUTE`); a frame at the wrong scale sends
those to 0.41 of the true point, and the never-tap rail test states that it
cannot catch runtime-computed coordinates. Window capture is therefore only
acceptable with every window pinned to a 1600 x 900 client area (one fits on a
1920 x 1080 desktop; three do not) or a full re-validation of every threshold
against window-captured frames.

## Render mode and fidelity

Both capture APIs read the DWM redirection surface: the composited window,
which is BlueStacks' own scaling of the 1600 x 900 guest, not the guest
framebuffer. The process owns OpenGL pbuffer windows at exactly 1600 x 900, but
they are invisible with no DWM surface and cannot be captured. Fidelity is
fine at 1:1 and fails the existing thresholds at any other size.

## Expected real-world gain

A match is about 150 s of fixed game time. Loop latency only affects the
detect-then-tap transitions (results, trophy screens, drops, popups, menu,
queue), each already gated by `TAP_SETTLE = 0.6`. At 12 to 20 such steps per
cycle, saving 170 ms of capture per step is 2 to 3.4 s off a cycle of about
200 s: one to two percent, roughly 0.2 to 0.3 extra matches per hour. In-match
nothing improves, because `ATTACK_INTERVAL` (2.75 s), the move interval, the
ability cooldown and the modal check cadence all gate well above the 0.5 s
loop. Reaction latency to a new screen would drop from about 500 ms to about
50 ms, which is a worse human tell, not a better one.

## Verdict

Not worth it. Capture is a third of the loop, not the bulk of it; the change
adds a binary dependency or a GDI path, a background thread, a window-geometry
contract the user can break by dragging a corner, and a re-validation of every
template threshold, to move throughput by one to two percent. What would change
this: a measured `screencap` median above about 400 ms with two or three
instances actually farming, together with the user accepting a pinned
1600 x 900 window per instance.

Because the verdict is no, the per-frame timing instrumentation proposed for
the heartbeat and `/api/health` was not added.

## A cheaper direction, if loop time ever matters

Not scheduled. Recorded so the option is not lost.

1. Guard the frame shape in `adb.screencap` (raise `AdbError` when the array
   is not 900 x 1600 x 3). This is worth doing on its own as the only runtime
   guard against a mis-scaled frame reaching a frame-derived tap.
2. Add an optional search region to `vision.find`, `find_with_score` and
   `score` that crops the haystack and offsets the returned match back to
   full-frame coordinates (`Match.center` must stay in full-frame
   coordinates, because the controller taps it).
3. Pass regions for `close_x` and `matchmaking` only, from `states.classify`,
   with an env kill switch in the style of the existing feature flags.
   Gate: on a corpus of at least 200 debug frames, `classify` returns the
   identical state with and without the regions under every phase hint.
   This is the risky step: a popup whose close button renders outside the
   region would stall the bot into a match timeout, so the regions must be
   fitted from real frames, not from the tap constant.
4. Only then revisit `LOOP_POLL_INTERVAL`, with a 30 minute live run
   compared against a 30 minute baseline.

Expected effect of steps 2 and 3: per-frame matching drops from about 216 ms
to about 25 ms, more than window capture would return, contained in files the
project already owns. The vision and states modules are safety-rail files, so
this would be its own reviewed change with the never-tap tests as the gate.
