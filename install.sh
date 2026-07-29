#!/usr/bin/env bash
# One-time installer: system deps + application-menu entry.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Installing system dependencies (needs sudo)…"
sudo apt update
sudo apt install -y \
    python3-pyqt6 python3-pyqt6.sip python3-gi \
    gir1.2-gstreamer-1.0 gir1.2-gst-plugins-base-1.0 \
    gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-libav \
    v4l-utils

chmod +x "$DIR/run.sh"

echo "==> Installing application icon…"
for sz in 48 64 128 256; do
    install -Dm644 "$DIR/assets/peekcam-$sz.png" \
        "$HOME/.local/share/icons/hicolor/${sz}x${sz}/apps/peekcam.png"
done
gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

echo "==> Installing application-menu entry…"
install -Dm644 "$DIR/peekcam.desktop" \
    "$HOME/.local/share/applications/peekcam.desktop"
# point Exec at the real location
sed -i "s#^Exec=.*#Exec=$DIR/run.sh#" "$HOME/.local/share/applications/peekcam.desktop"
update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true

echo "==> Done. Launch 'PeekCam' from your applications menu, or run: $DIR/run.sh"
