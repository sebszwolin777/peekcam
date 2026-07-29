"""Camera enumeration and format discovery via v4l2-ctl (v4l-utils).

We probe every /dev/video* node, keep the ones that expose *capture* formats (the
paired metadata nodes report none), and parse `--list-formats-ext` into a structured
list of formats/resolutions/framerates used to populate the settings dropdowns.
"""
from __future__ import annotations

import glob
import re
import subprocess
from dataclasses import dataclass, field
from fractions import Fraction


@dataclass
class FrameSize:
    width: int
    height: int
    fps: list[float] = field(default_factory=list)  # descending


@dataclass
class PixFormat:
    fourcc: str            # e.g. "MJPG", "YUYV"
    description: str
    sizes: list[FrameSize] = field(default_factory=list)


@dataclass
class Camera:
    path: str              # /dev/videoN (a capture node)
    name: str              # human-friendly card name
    formats: list[PixFormat] = field(default_factory=list)

    @property
    def device_id(self) -> str:
        """Stable-ish id for config keying. Prefers the by-id symlink when present."""
        for link in glob.glob("/dev/v4l/by-id/*"):
            try:
                import os
                if os.path.realpath(link) == os.path.realpath(self.path):
                    return f"{self.name}::{link.split('/')[-1]}"
            except OSError:
                pass
        return f"{self.name}::{self.path}"


def _run(args: list[str]) -> str:
    try:
        return subprocess.run(
            args, capture_output=True, text=True, timeout=5
        ).stdout
    except (subprocess.SubprocessError, FileNotFoundError):
        return ""


def _card_name(path: str) -> str:
    out = _run(["v4l2-ctl", "-d", path, "--info"])
    m = re.search(r"Card type\s*:\s*(.+)", out)
    return m.group(1).strip() if m else path


_FMT_RE = re.compile(r"\[\d+\]:\s*'(\w+)'\s*\((.*?)\)")
_SIZE_RE = re.compile(r"Size:\s*Discrete\s*(\d+)x(\d+)")
_FPS_RE = re.compile(r"\(([\d.]+)\s*fps\)")


def _parse_formats(path: str) -> list[PixFormat]:
    out = _run(["v4l2-ctl", "-d", path, "--list-formats-ext"])
    formats: list[PixFormat] = []
    cur_fmt: PixFormat | None = None
    cur_size: FrameSize | None = None
    for line in out.splitlines():
        mf = _FMT_RE.search(line)
        if mf:
            cur_fmt = PixFormat(fourcc=mf.group(1), description=mf.group(2))
            formats.append(cur_fmt)
            cur_size = None
            continue
        ms = _SIZE_RE.search(line)
        if ms and cur_fmt is not None:
            cur_size = FrameSize(int(ms.group(1)), int(ms.group(2)))
            cur_fmt.sizes.append(cur_size)
            continue
        mfp = _FPS_RE.search(line)
        if mfp and cur_size is not None:
            cur_size.fps.append(float(mfp.group(1)))
    # sort sizes big->small, fps high->low
    for f in formats:
        f.sizes.sort(key=lambda s: s.width * s.height, reverse=True)
        for s in f.sizes:
            s.fps.sort(reverse=True)
    return formats


def list_cameras() -> list[Camera]:
    cams: list[Camera] = []
    for path in sorted(glob.glob("/dev/video*")):
        formats = _parse_formats(path)
        if not formats:
            continue  # metadata / non-capture node
        cams.append(Camera(path=path, name=_card_name(path), formats=formats))
    return cams


def find_by_id(cams: list[Camera], device_id: str | None) -> Camera | None:
    if device_id:
        for c in cams:
            if c.device_id == device_id:
                return c
    return cams[0] if cams else None


def fps_fraction(fps: float) -> tuple[int, int]:
    """Convert a float fps (e.g. 7.5) to a GStreamer fraction (num, den)."""
    fr = Fraction(fps).limit_denominator(1000)
    return fr.numerator, fr.denominator
