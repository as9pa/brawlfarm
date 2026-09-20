# Play stream: scrcpy over adb, measured

Date: 2026-09-18. Status: adopted in pull request 1.

Before the play mode spec was written, the video path was measured on a real
instance instead of guessed at. This note records those numbers and the two
things that cost the most time, so the next person does not rediscover them.

## The layers

BlueStacks runs the game. adb is the cable into it: every tap, swipe, screenshot
and launch, and the scrcpy server itself, travel over adb. scrcpy is a small
Android program adb pushes onto the instance; it streams the screen back over
the same connection and sends nothing in. The stream replaces `adb screencap`
inside a match only. Outside a match screencap stays, because the 13 templates
were validated on screencap frames (H.264 compression shifts pixels, and
`close_x` has a 0.006 margin) and because the encoder costs BlueStacks about 60
percent of one core for as long as it runs.

## What the stream costs

Measured on Pie64 on 2026-09-18, scrcpy 4.1 server, raw H.264 into Python,
control off.

- Frames 1600 x 900 native, 30.0 fps received.
- Gap between frames: 33 ms median, 37 ms p95, 69 ms max.
- 2.2 ms per frame to convert a decoded frame to a BGR array.
- 4.3 Mbit/s over the forwarded socket.
- BlueStacks `HD-Player.exe` at 22 percent of one core idle and 81 percent while
  streaming; host 16 percent across all cores.
- Encoder `OMX.google.h264.encoder`, software, inside the guest.

Decoder threading, measured on a synthetic 30 fps clip: PyAV's default frame
threading holds back 18 packets before the first frame, which is 600 ms at 30
fps; a single-threaded decoder emits the first frame after 3 packets, at 1.2 ms
median and 3.4 ms max per packet. Frame threading is therefore never enabled.

Machine: RTX 4080 SUPER 16 GB, Ryzen 7 7800X3D, 31 GB RAM, Python 3.13.13, uv
0.12.5, PyAV 18.1.0.

## The two gotchas

adb accepts the forwarded connection before the scrcpy server is listening on
the abstract socket, then closes it silently. Connecting successfully proves
nothing. The stream peeks for the first byte and retries until an 8 s deadline,
and if the server process exited first, its output tail is the error.

PyAV's file-object demuxer does not decode this stream. `raw_stream=true` is a
bare H.264 elementary stream with no container, and the demuxer either blocks or
gives up on it. The parser path does work: `av.CodecContext.create("h264", "r")`
set to one thread, fed by `parse()` on raw socket reads.
