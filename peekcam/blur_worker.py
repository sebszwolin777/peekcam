"""Subprocess worker that runs MediaPipe selfie segmentation in isolation.

MediaPipe initializes its own EGL/GL + X context, which conflicts (deadlock/segfault)
with Qt's X connection when run in the same process. Running it in a separate process
sidesteps all shared GL/X/native state.

Protocol (driven by the parent in blur.py):
  - argv: shm_in_name shm_out_name model_path sigma
  - shared memory: shm_in holds the incoming RGB frame, shm_out the composited result.
  - control over stdin/stdout (text lines):
        parent -> worker:  "<w> <h>\n"   (frame is in shm_in, w*h*3 bytes)
        worker -> parent:  "ok\n"        (result is in shm_out, w*h*3 bytes)
    On startup the worker prints "ready\n", or "err <message>\n" then exits.
"""
from __future__ import annotations

import sys
from multiprocessing import shared_memory


def _log(*a):
    print(*a, file=sys.stderr, flush=True)


def main() -> int:
    shm_in_name, shm_out_name, model_path, sigma_s = sys.argv[1:5]
    sigma = float(sigma_s)
    try:
        import numpy as np
        import cv2
        import mediapipe as mp
        from mediapipe.tasks import python as mpp
        from mediapipe.tasks.python import vision

        options = vision.ImageSegmenterOptions(
            base_options=mpp.BaseOptions(model_asset_path=model_path,
                                         delegate=mpp.BaseOptions.Delegate.CPU),
            running_mode=vision.RunningMode.IMAGE,
            output_category_mask=False,
            output_confidence_masks=True,
        )
        seg = vision.ImageSegmenter.create_from_options(options)
        shm_in = shared_memory.SharedMemory(name=shm_in_name)
        shm_out = shared_memory.SharedMemory(name=shm_out_name)
    except Exception as e:
        sys.stdout.write(f"err {type(e).__name__}: {e}\n")
        sys.stdout.flush()
        return 1

    sys.stdout.write("ready\n")
    sys.stdout.flush()

    for line in sys.stdin:
        line = line.strip()
        if not line or line == "quit":
            break
        try:
            w, h = (int(x) for x in line.split())
            n = w * h * 3
            rgb = np.ndarray((h, w, 3), dtype=np.uint8, buffer=shm_in.buf[:n]).copy()
            out = _composite(np, cv2, mp, seg, rgb, sigma)
            shm_out.buf[:n] = out.tobytes()
            sys.stdout.write("ok\n")
            sys.stdout.flush()
        except Exception as e:
            sys.stdout.write(f"err {type(e).__name__}: {e}\n")
            sys.stdout.flush()

    try:
        seg.close()
    except Exception:
        pass
    return 0


SEG_H = 256  # segment on a small copy; the selfie model works at ~256px internally


def _composite(np, cv2, mp, seg, rgb, sigma):
    h, w = rgb.shape[:2]
    # 1) Segment on a downscaled copy (much cheaper), then upscale the mask.
    seg_w = max(1, int(round(w * SEG_H / h)))
    small_rgb = cv2.resize(rgb, (seg_w, SEG_H), interpolation=cv2.INTER_AREA)
    image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(small_rgb))
    result = seg.segment(image)
    mask = result.confidence_masks[0].numpy_view()
    if mask.ndim == 3:
        mask = mask[:, :, 0]
    mask = cv2.GaussianBlur(mask, (0, 0), 1.5)  # feather cheaply at small res
    mask = cv2.resize(mask, (w, h), interpolation=cv2.INTER_LINEAR)
    mask3 = cv2.merge([mask, mask, mask])  # HxWx3 float32
    # 2) Fast, resolution-independent background blur: downscale -> blur -> upscale.
    blur_small = cv2.resize(rgb, (max(1, w // 4), max(1, h // 4)), interpolation=cv2.INTER_LINEAR)
    blur_small = cv2.GaussianBlur(blur_small, (0, 0), max(1.0, sigma / 4.0))
    blurred = cv2.resize(blur_small, (w, h), interpolation=cv2.INTER_LINEAR).astype(np.float32)
    # 3) Composite: blurred + (rgb - blurred) * mask, using cv2's SIMD ops.
    rgbf = rgb.astype(np.float32)
    out = cv2.add(blurred, cv2.multiply(cv2.subtract(rgbf, blurred), mask3))
    return out.astype(np.uint8)


if __name__ == "__main__":
    raise SystemExit(main())
