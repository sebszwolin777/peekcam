#!/usr/bin/env bash
# Generate python3-modules.json (pinned, offline pip wheels for the blur ML stack)
# for the Flatpak build.
#
# It runs flatpak-pip-generator INSIDE the target runtime (--runtime) so pip resolves
# the correct prebuilt manylinux wheels for the runtime's exact Python/ABI — this is
# what avoids OpenCV/NumPy coming through as source tarballs.
#
# Prereqs:
#   flatpak install flathub org.kde.Sdk//$RUNTIME_VERSION
#   (python3 with the 'requirements-parser' module, e.g. in a venv or pipx)
#
# Usage:  ./gen-python-deps.sh
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME_VERSION="${RUNTIME_VERSION:-6.8}"   # keep in sync with the manifest's runtime-version

GEN="$DIR/flatpak-pip-generator.py"
if [ ! -f "$GEN" ]; then
  echo "==> Fetching flatpak-pip-generator…"
  curl -fsSL -o "$GEN" \
    https://raw.githubusercontent.com/flatpak/flatpak-builder-tools/master/pip/flatpak-pip-generator.py
fi

echo "==> Generating python3-modules.json against org.kde.Sdk//$RUNTIME_VERSION…"
python3 "$GEN" \
    --runtime "org.kde.Sdk//$RUNTIME_VERSION" \
    --requirements-file "$DIR/requirements-ml.txt" \
    --output "$DIR/python3-modules" \
    --checker-data

echo "==> Wrote $DIR/python3-modules.json"
