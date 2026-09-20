"""Parser-fed H.264 decoding for the play stream.

The scrcpy server sends a raw H.264 elementary stream (Annex B). PyAV's file-object demuxer
does not decode it from a live socket; a codec context fed through ``parse()`` does. The
decoder runs on one thread on purpose: frame threading holds back about 18 packets before
the first frame comes out, 600 ms at 30 fps, measured on 2026-09-18.
"""

from __future__ import annotations

import numpy as np


class Decoder:
    """Bytes in, BGR frames out. Chunking does not matter; the parser reassembles packets."""

    def __init__(self) -> None:
        import av  # the play extra; imported here so the package loads without it

        self._ctx = av.CodecContext.create("h264", "r")
        self._ctx.thread_count = 1
        self.packets = 0
        self.frames = 0

    def feed(self, data: bytes) -> list[np.ndarray]:
        """Decode whatever complete packets ``data`` completes. Returns zero or more frames."""
        out: list[np.ndarray] = []
        if not data:
            return out
        for packet in self._ctx.parse(data):
            self.packets += 1
            for frame in self._ctx.decode(packet):
                self.frames += 1
                out.append(frame.to_ndarray(format="bgr24"))
        return out

    def flush(self) -> list[np.ndarray]:
        """Drain the frames the decoder still holds. Only needed at end of stream."""
        out: list[np.ndarray] = []
        try:
            frames = self._ctx.decode()
        except Exception:  # a drained or closed context has nothing more to give
            return out
        for frame in frames:
            self.frames += 1
            out.append(frame.to_ndarray(format="bgr24"))
        return out
