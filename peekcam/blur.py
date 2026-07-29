"""Background blur (optional feature) — parent-side client.

The actual MediaPipe segmentation runs in a separate process (blur_worker.py) because
MediaPipe's EGL/GL + X context conflicts with Qt's X connection in-process. Frames are
exchanged through shared memory; a tiny text protocol over the worker's stdin/stdout
provides synchronization.

process() takes a contiguous HxWx3 uint8 RGB numpy array and returns a new array with the
background blurred and the person kept sharp.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys

MODEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "models", "selfie_segmenter.tflite",
)

MAX_BYTES = 3840 * 2160 * 3  # up to 4K RGB

_available: bool | None = None
_import_error: str = ""


def available() -> bool:
    """True if the model file exists and the worker's deps look importable — checked
    without importing mediapipe into this (Qt) process."""
    global _available, _import_error
    if _available is None:
        missing = [m for m in ("numpy", "cv2", "mediapipe")
                   if importlib.util.find_spec(m) is None]
        if missing:
            _available = False
            _import_error = "missing modules: " + ", ".join(missing)
        elif not os.path.exists(MODEL_PATH):
            _available = False
            _import_error = f"model not found: {MODEL_PATH}"
        else:
            _available = True
    return _available


def import_error() -> str:
    return _import_error


class BackgroundBlur:
    """Drives the segmentation subprocess. Construct from the thread that will call
    process() (kept single-threaded by the pipeline). Raises if the worker fails to
    start."""

    def __init__(self, sigma: float = 13.0):
        from multiprocessing import shared_memory

        self._shm_in = shared_memory.SharedMemory(create=True, size=MAX_BYTES)
        self._shm_out = shared_memory.SharedMemory(create=True, size=MAX_BYTES)
        self._proc = subprocess.Popen(
            [sys.executable, "-m", "peekcam.blur_worker",
             self._shm_in.name, self._shm_out.name, MODEL_PATH, str(sigma)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        )
        first = self._proc.stdout.readline().decode("utf-8", "ignore").strip()
        if first != "ready":
            self.close()
            raise RuntimeError(f"blur worker failed to start: {first or 'no response'}")

    def process(self, rgb):
        h, w = rgb.shape[:2]
        n = w * h * 3
        if n > MAX_BYTES:
            return rgb  # frame larger than our buffer; skip blur for this frame
        self._shm_in.buf[:n] = rgb.tobytes()
        self._proc.stdin.write(f"{w} {h}\n".encode())
        self._proc.stdin.flush()
        reply = self._proc.stdout.readline().decode("utf-8", "ignore").strip()
        if reply != "ok":
            raise RuntimeError(f"blur worker error: {reply or 'worker exited'}")
        import numpy as np
        return np.ndarray((h, w, 3), dtype=np.uint8, buffer=self._shm_out.buf[:n]).copy()

    def close(self) -> None:
        proc = getattr(self, "_proc", None)
        if proc is not None and proc.poll() is None:
            try:
                proc.stdin.write(b"quit\n")
                proc.stdin.flush()
                proc.wait(timeout=1)
            except Exception:
                proc.kill()
        for shm in (getattr(self, "_shm_in", None), getattr(self, "_shm_out", None)):
            if shm is not None:
                try:
                    shm.close()
                    shm.unlink()
                except Exception:
                    pass
