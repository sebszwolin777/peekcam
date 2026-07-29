"""PeekCam — a movable, always-on-top webcam overlay for Zorin/Ubuntu (Wayland via XWayland)."""

import os

__version__ = "0.1.0"
APP_NAME = "PeekCam"
APP_ID = "peekcam"


def data_dir() -> str:
    """Locate the directory that holds assets/ and models/.

    Resolves relocatably so the app works both from a source checkout and from a
    packaged install (e.g. Flatpak, which installs data under /app/share/peekcam):
      1. $PEEKCAM_DATA_DIR (if set and present)
      2. /app/share/peekcam (Flatpak)
      3. the repo root (dirname of this package) — the dev/source layout
    """
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for candidate in (os.environ.get("PEEKCAM_DATA_DIR"),
                      "/app/share/peekcam",
                      repo_root):
        if candidate and os.path.isdir(candidate):
            return candidate
    return repo_root
