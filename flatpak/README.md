# Building the PeekCam Flatpak (with background blur)

This bundles PyQt6 (via the PyQt BaseApp), the MediaPipe blur stack, and the
segmentation model. It targets the **KDE 6.8 runtime**.

> Status: **builds, installs, and fully runs.** Verified on Zorin OS 18: always-on-top
> overlay, camera, snapshot, recording, background blur, and CLI actions all work in the
> sandbox. See "Verified working" and "Before a Flathub submission" below.

## Prerequisites

```bash
sudo apt install flatpak-builder
flatpak install flathub \
    org.kde.Platform//6.8 org.kde.Sdk//6.8 \
    com.riverbankcomputing.PyQt.BaseApp//6.8 \
    org.freedesktop.Platform.ffmpeg-full//24.08
# gen-python-deps.sh needs the 'requirements-parser' python module:
python3 -m pip install --user requirements-parser   # or use the blur .venv's python
```

## 1. Generate the Python dependency list (once)

```bash
./flatpak/gen-python-deps.sh
```

This resolves a **binary-only** wheel tree (via pip's install report) and writes
`flatpak/python3-modules.json` — all wheels, installed offline at build time. Run it on a
host whose Python major.minor and glibc match the runtime (freedesktop 24.08 / KDE 6.8 =
Python 3.12), so the selected wheels are compatible.

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

## Before a Flathub submission

- **Bump off KDE 6.8** (end-of-life) to 6.9, and `ffmpeg-full` to 25.08. Re-run
  `gen-python-deps.sh` on a matching-Python host if the runtime's Python changes.
- **Pin the app source** to a tagged commit (`tag:` + `commit:`) instead of `branch: main`
  for a reproducible build.
- Validate the metainfo and ensure the screenshots resolve.

## Toward Flathub

Once it builds and runs locally: validate the metainfo (`flatpak run
org.freedesktop.appstream-glib validate flatpak/*.metainfo.xml`), pin the app source to a
tagged commit, and submit the manifest to the flathub/flathub repo. The app-id
`io.github.sebszwolin777.PeekCam` already follows the GitHub-hosted naming scheme.
