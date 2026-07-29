"""Snapshot + recording output helpers (paths, timestamps, saving snapshots).

The heavy lifting for video recording lives in pipeline.CameraPipeline (tee branch);
this module just decides *where* files go and saves still frames.
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path

from PyQt6.QtGui import QPixmap


def _timestamp() -> str:
    return _dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def snapshot_path(directory: str) -> Path:
    d = Path(directory).expanduser()
    d.mkdir(parents=True, exist_ok=True)
    return d / f"peekcam-{_timestamp()}.png"


def video_path(directory: str) -> Path:
    d = Path(directory).expanduser()
    d.mkdir(parents=True, exist_ok=True)
    return d / f"peekcam-{_timestamp()}.mp4"


def save_snapshot(pixmap: QPixmap, directory: str) -> Path | None:
    if pixmap is None or pixmap.isNull():
        return None
    path = snapshot_path(directory)
    return path if pixmap.save(str(path), "PNG") else None
