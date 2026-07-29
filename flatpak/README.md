# Building the PeekCam Flatpak (with background blur)

This bundles PyQt6 (via the PyQt BaseApp), the MediaPipe blur stack, and the
segmentation model. It targets the **KDE 6.8 runtime**.

> Status: **builds, installs, and runs.** Verified on Zorin OS 18: the sandboxed app
> launches always-on-top, the camera works (`v4l2src` + `/dev/video*` via `--device=all`),
> snapshots save to ~/Pictures, and **background blur works** (the MediaPipe subprocess
> runs inside the sandbox using the bundled model). Two known gaps remain — see
> "Known limitations" below.

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

## Known limitations (to fix before Flathub)

- **Recording (H.264) doesn't work yet.** Neither `x264enc` nor `avenc_h264` is available
  in the KDE 6.8 runtime — the ffmpeg-full extension ships the ffmpeg libs but the GStreamer
  `gst-libav` plugin that exposes `avenc_h264` isn't present. Overlay, snapshot, and blur
  all work; only recording is affected. Fix options: bundle `gst-libav`, or use
  `openh264enc` (openh264 extension) / VAAPI hardware encode.
- **CLI actions across `flatpak run` are unreliable.** `flatpak run … --toggle-blur` starts
  a separate sandbox instance whose local socket doesn't reach the running app, so the
  single-instance IPC (used for GNOME custom-shortcut hotkeys) doesn't forward. A D-Bus
  single-instance/activation mechanism is the proper fix inside Flatpak.
- **KDE 6.8 is end-of-life** — bump `runtime-version`/`base-version` to 6.9 (and
  ffmpeg-full to 25.08) for a Flathub submission.
- **Reproducible release**: the app source uses `branch: main`; pin it to a tagged commit
  (`tag:` + `commit:`) for a release/Flathub build.

## Toward Flathub

Once it builds and runs locally: validate the metainfo (`flatpak run
org.freedesktop.appstream-glib validate flatpak/*.metainfo.xml`), pin the app source to a
tagged commit, and submit the manifest to the flathub/flathub repo. The app-id
`io.github.sebszwolin777.PeekCam` already follows the GitHub-hosted naming scheme.
