#!/usr/bin/env bash
# Optional: install the background-blur ML stack (MediaPipe) into a local venv that
# also sees the system PyQt6 + GStreamer (via --system-site-packages).
#
# Prereqs (one-time, needs sudo):
#     sudo apt install -y python3.12-venv python3-pip
# Then run this script (no sudo needed):
#     ./setup_blur.sh
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$DIR/.venv"

if ! python3 -c "import ensurepip" 2>/dev/null; then
  echo "ERROR: python venv/pip support missing." >&2
  echo "Run first:  sudo apt install -y python3.12-venv python3-pip" >&2
  exit 1
fi

echo "==> Creating venv (with access to system PyQt6 + GStreamer)…"
python3 -m venv --system-site-packages "$VENV"

echo "==> Installing mediapipe (this pulls numpy + opencv; ~100MB+)…"
"$VENV/bin/pip" install --upgrade pip
"$VENV/bin/pip" install mediapipe

echo "==> Fetching the selfie-segmenter model…"
mkdir -p "$DIR/models"
MODEL_URL="https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_segmenter/float16/latest/selfie_segmenter.tflite"
if [ ! -f "$DIR/models/selfie_segmenter.tflite" ]; then
  curl -fsSL -o "$DIR/models/selfie_segmenter.tflite" "$MODEL_URL"
fi
ls -la "$DIR/models/selfie_segmenter.tflite"

echo "==> Verifying…"
"$VENV/bin/python" - <<'PY'
import mediapipe, numpy, cv2
print("mediapipe", mediapipe.__version__, "| numpy", numpy.__version__, "| cv2", cv2.__version__)
from mediapipe.tasks.python import vision  # noqa
print("Tasks ImageSegmenter: OK")
PY

echo "==> Done. Launch PeekCam normally (run.sh auto-uses this venv);"
echo "    toggle 'Background blur' from the right-click / tray menu."
