# Building the PeekCam Flatpak (with background blur)

This bundles PyQt6 (via the PyQt BaseApp), the MediaPipe blur stack, and the
segmentation model. It targets the **KDE 6.8 runtime**.

> Status: scaffold. The manifest and metadata are complete, but a blur-bundled Flatpak
> needs a real `flatpak-builder` loop to finalize (the Python-deps step in particular).
> Expect to iterate on the first build; paste any errors and we'll fix them.

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

This runs `flatpak-pip-generator` **inside `org.kde.Sdk//6.8`** so pip picks the correct
prebuilt manylinux wheels for the runtime's Python (rather than source tarballs), and
writes `flatpak/python3-modules.json`.

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

## Known things to verify on first build

- **H.264 recording**: relies on `avenc_h264` from the ffmpeg-full extension being
  available to GStreamer in the KDE runtime. If recording fails, check
  `gst-inspect-1.0 avenc_h264` inside the sandbox; overlay/snapshot/blur don't depend on it.
- **Version alignment**: `runtime-version`, `base-version`, `gen-python-deps.sh`
  `RUNTIME_VERSION`, and the ffmpeg-full `version` must stay mutually consistent (KDE 6.8
  is built on freedesktop 24.08). Change them together if you retarget.
- **Reproducible release**: the app source uses `branch: main`; pin it to a tagged commit
  (`tag:` + `commit:`) for a release/Flathub build.

## Toward Flathub

Once it builds and runs locally: validate the metainfo (`flatpak run
org.freedesktop.appstream-glib validate flatpak/*.metainfo.xml`), pin the app source to a
tagged commit, and submit the manifest to the flathub/flathub repo. The app-id
`io.github.sebszwolin777.PeekCam` already follows the GitHub-hosted naming scheme.
