# Flathub submission bundle

Ready-to-submit files for [flathub/flathub](https://github.com/flathub/flathub):

- `io.github.sebszwolin777.PeekCam.yaml` — manifest with the app source pinned to `v0.1.1`.
- `python3-modules.json` — pinned blur ML wheels (cp312, matching KDE 6.9 = Python 3.12).

## Submit

```bash
# 1. Fork github.com/flathub/flathub, then on your fork:
git checkout -b io.github.sebszwolin777.PeekCam
mkdir io.github.sebszwolin777.PeekCam
cp /path/to/peekcam/flathub-submission/io.github.sebszwolin777.PeekCam.yaml \
   /path/to/peekcam/flathub-submission/python3-modules.json \
   io.github.sebszwolin777.PeekCam/
git add io.github.sebszwolin777.PeekCam && git commit -m "Add io.github.sebszwolin777.PeekCam"
git push origin io.github.sebszwolin777.PeekCam

# 2. Lint locally first:
flatpak install flathub org.flatpak.Builder
flatpak run --command=flatpak-builder-lint org.flatpak.Builder manifest \
    io.github.sebszwolin777.PeekCam/io.github.sebszwolin777.PeekCam.yaml

# 3. Open a PR from your branch to flathub/flathub:master.
```

## Keeping it in sync

This manifest mirrors `../flatpak/io.github.sebszwolin777.PeekCam.yaml` except the app
source is pinned (`tag` + `commit`) instead of `branch: main`. If you change the dev
manifest or cut a new release, update this one and regenerate `python3-modules.json`:

```bash
../flatpak/gen-python-deps.sh && cp ../flatpak/python3-modules.json .
```
