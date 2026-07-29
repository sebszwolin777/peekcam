# Flathub submission bundle

Ready-to-submit files for [flathub/flathub](https://github.com/flathub/flathub):

- `io.github.sebszwolin777.PeekCam.yaml` — manifest with the app source pinned to `v0.1.1`.
- `python3-modules.json` — pinned blur ML wheels (cp312, matching KDE 6.9 = Python 3.12).

## Submit (Flathub `new-pr` flow)

Files go at the **root** of the branch (not a subdirectory), and the PR targets the
**`new-pr`** branch — not `master`.

```bash
# 1. Fork github.com/flathub/flathub  (UNcheck "Copy the master branch only").

# 2. Clone your fork's new-pr branch and make a submission branch off it:
git clone --branch=new-pr git@github.com:sebszwolin777/flathub.git
cd flathub
git checkout -b peekcam-submission new-pr

# 3. Copy the two files to the repo ROOT:
cp /path/to/peekcam/flathub-submission/io.github.sebszwolin777.PeekCam.yaml .
cp /path/to/peekcam/flathub-submission/python3-modules.json .

# 4. Lint before pushing:
flatpak install flathub org.flatpak.Builder
flatpak run --command=flatpak-builder-lint org.flatpak.Builder manifest \
    io.github.sebszwolin777.PeekCam.yaml

# 5. Commit + push:
git add io.github.sebszwolin777.PeekCam.yaml python3-modules.json
git commit -m "Add io.github.sebszwolin777.PeekCam"
git push origin peekcam-submission

# 6. Open a PR on GitHub with base branch **new-pr** (NOT master),
#    title "Add io.github.sebszwolin777.PeekCam".
#    Then comment "bot, build" on the PR to trigger a test build.
```

## Keeping it in sync

This manifest mirrors `../flatpak/io.github.sebszwolin777.PeekCam.yaml` except the app
source is pinned (`tag` + `commit`) instead of `branch: main`. If you change the dev
manifest or cut a new release, update this one and regenerate `python3-modules.json`:

```bash
../flatpak/gen-python-deps.sh && cp ../flatpak/python3-modules.json .
```
