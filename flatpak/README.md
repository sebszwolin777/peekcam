# Building the PeekCam Flatpak (with background blur)

This bundles PyQt6 (via the PyQt BaseApp), the MediaPipe blur stack, and the
segmentation model. It targets the **KDE 6.9 runtime** (Python 3.12).

> Status: **builds, installs, and fully runs.** Verified on Zorin OS 18: always-on-top
> overlay, camera, snapshot, recording, background blur, and CLI actions all work in the
> sandbox. See "Verified working" and "Before a Flathub submission" below.

## Prerequisites

```bash
sudo apt install flatpak-builder
flatpak install flathub \
    org.kde.Platform//6.9 org.kde.Sdk//6.9 \
    com.riverbankcomputing.PyQt.BaseApp//6.9
# gen-python-deps.sh needs a python3 with pip >= 22.2 (system python3 or the blur .venv).
```

## 1. Generate the Python dependency list (once)

```bash
./flatpak/gen-python-deps.sh
```

This resolves a **binary-only** wheel tree (via pip's install report) and writes
`flatpak/python3-modules.json` — all wheels, installed offline at build time. It resolves
wheels cross-version for the runtime's Python via `TARGET_PYVER` (default `312`; KDE 6.9 =
Python 3.12), so the host's own Python need not match.

## 2. Build & install

```bash
flatpak-builder --user --install --force-clean build-dir \
    flatpak/io.github.sebszwolin777.PeekCam.yaml
```

## 3. Run

```bash
flatpak run io.github.sebszwolin777.PeekCam
# CLI actions (e.g. for GNOME custom shortcuts):
flatpak run io.github.sebszwolin777.PeekCam --toggle-blur
flatpak run io.github.sebszwolin777.PeekCam --snapshot
```

## Sandbox permissions (see the manifest `finish-args`)

- `--socket=fallback-x11` + `QT_QPA_PLATFORM=xcb` — required for always-on-top / free
  positioning / click-through (X11 under XWayland).
- `--device=all` — cameras (`/dev/video*`) and GPU; we use `v4l2src` + `v4l2-ctl`
  directly, which need raw device access rather than the camera portal.
- `--filesystem=xdg-pictures:create`, `xdg-videos:create` — snapshots / recordings.
- tray + notifications talk-names.

## Verified working in the sandbox

Overlay (always-on-top), camera capture, snapshot, **recording** (H.264 via
`openh264enc` — `gst-libav` omits `avenc_h264`, and the recorder falls back
x264enc → openh264enc → vah264enc), **background blur** (MediaPipe subprocess), and
**CLI actions** (`flatpak run … --snapshot` / `--toggle-blur` reach the running instance —
Flatpak shares the per-app runtime dir, so the single-instance socket works for hotkeys).

## Toward Flathub

The in-repo manifest builds from `branch: main` for local dev. To submit to
[flathub/flathub](https://github.com/flathub/flathub):

1. Fork flathub/flathub, create a branch named `io.github.sebszwolin777.PeekCam`.
2. Add the manifest with the app source **pinned** to the release (reproducible builds):
   ```yaml
   sources:
     - type: git
       url: https://github.com/sebszwolin777/peekcam.git
       tag: v0.1.1
       commit: 06872a6f48cfbd394483932a719b198f1c8eaeeb
   ```
3. Also commit `python3-modules.json` (the pinned wheel list — it carries the offline
   sources Flathub's no-network build needs). Generate it with `./gen-python-deps.sh`.
4. Lint before opening the PR:
   `flatpak install flathub org.flatpak.Builder && \`
   `flatpak run --command=flatpak-builder-lint org.flatpak.Builder manifest <manifest>`
5. Open a PR. The app-id already follows the GitHub-hosted naming scheme.

Note: KDE 6.9 is the current stable at time of writing; check it's still supported when you
submit (Flathub rejects end-of-life runtimes).
