#!/usr/bin/env bash
# Launch PeekCam under XWayland (X11 backend) so always-on-top, free positioning,
# and click-through work on GNOME/Zorin Wayland. Passes through any CLI action flags
# (e.g. --snapshot, --toggle-record) to a running instance.
set -euo pipefail
export QT_QPA_PLATFORM=xcb
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"
# Prefer the blur venv (has mediapipe + system PyQt6/gi via --system-site-packages)
# if it exists; otherwise fall back to system python (blur just stays unavailable).
if [ -x "$DIR/.venv/bin/python" ]; then
  exec "$DIR/.venv/bin/python" -m peekcam "$@"
else
  exec python3 -m peekcam "$@"
fi
