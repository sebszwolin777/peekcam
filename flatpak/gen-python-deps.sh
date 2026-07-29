#!/usr/bin/env bash
# Generate flatpak/python3-modules.json — a "wheelhouse" module that bundles the blur
# ML stack (mediapipe + opencv + numpy + deps) as BINARY wheels for offline install.
#
# Why not flatpak-pip-generator? It records compiled packages (numpy/opencv/…) as source
# tarballs, which would try to build OpenCV from source in the sandbox. Instead we resolve
# a binary-only wheel tree with pip's install report and emit those URLs + hashes.
#
# Requirements: python3 with pip >= 22.2 (for --report). Resolves wheels cross-version for
# the target runtime's Python (TARGET_PYVER), so the host's own Python need not match.
# KDE 6.9 / freedesktop 25.08 -> Python 3.13; KDE 6.8 / 24.08 -> 3.12.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-python3}"
TARGET_PYVER="${TARGET_PYVER:-313}"      # cp tag of the runtime Python, e.g. 313 or 312
REPORT="$(mktemp)"

echo "==> Resolving binary-only wheel tree for cp${TARGET_PYVER}…"
"$PYTHON" -m pip install --dry-run --ignore-installed --only-binary=:all: \
    --python-version "$TARGET_PYVER" --implementation cp \
    --abi "cp${TARGET_PYVER}" --abi abi3 --abi none \
    --platform manylinux_2_28_x86_64 --platform manylinux_2_17_x86_64 \
    --platform manylinux2014_x86_64 \
    --report "$REPORT" -r "$DIR/requirements-ml.txt"

echo "==> Writing python3-modules.json…"
"$PYTHON" - "$REPORT" "$DIR/python3-modules.json" <<'PY'
import json, sys
report, out = sys.argv[1], sys.argv[2]
r = json.load(open(report))
sources, pkgs = [], []
for p in r["install"]:
    di = p["download_info"]; ai = di.get("archive_info", {})
    sha = (ai.get("hashes", {}) or {}).get("sha256") \
          or (ai.get("hash", "").split("=", 1)[1] if ai.get("hash", "").startswith("sha256=") else None)
    assert sha and di["url"].endswith(".whl"), f"expected a wheel with sha256: {di['url']}"
    sources.append({"type": "file", "url": di["url"], "sha256": sha})
    md = p["metadata"]; pkgs.append(f'{md["name"]}=={md["version"]}')
module = {
    "name": "python3-blur-deps",
    "buildsystem": "simple",
    "build-commands": [
        'pip3 install --ignore-installed --no-index --no-build-isolation '
        '--find-links="file://${PWD}" --prefix=${FLATPAK_DEST} ' + " ".join(sorted(pkgs))
    ],
    "sources": sources,
}
json.dump(module, open(out, "w"), indent=2)
print(f"   {len(sources)} wheels")
PY
rm -f "$REPORT"
echo "==> Done: $DIR/python3-modules.json"
