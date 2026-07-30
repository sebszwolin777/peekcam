# AUR packaging

`PKGBUILD` + `.SRCINFO` to publish PeekCam on the [AUR](https://aur.archlinux.org).

> **Untested draft.** These were written on a non-Arch machine and must be built and
> validated on Arch before publishing. Don't push an unbuilt PKGBUILD to the AUR.

## 1. Test on Arch (VM or container)

Fast build-test in a container:
```bash
podman run --rm -it -v "$PWD:/pkg:ro" archlinux:latest bash
# inside the container:
pacman -Syu --noconfirm base-devel git namcap
useradd -m build && cp /pkg/PKGBUILD /home/build/ && chown -R build /home/build
su - build -c 'cd ~ && makepkg -s'      # must build cleanly (makepkg won't run as root)
```

On a full Arch VM (also lets you runtime-test the GUI + webcam):
```bash
cd packaging/aur
makepkg -si                         # build + install
namcap PKGBUILD                     # lint the recipe
namcap peekcam-*.pkg.tar.zst        # lint the built package
peekcam                             # launch (needs a desktop session + camera)
```

Fix anything the build or `namcap` flags, then regenerate the canonical metadata:
```bash
makepkg --printsrcinfo > .SRCINFO
```

## 2. Publish to the AUR

1. Create an account at aur.archlinux.org and add your **SSH public key**
   (My Account → SSH Public Key).
2. Confirm the name `peekcam` is free: https://aur.archlinux.org/packages/peekcam
3. Clone the (new) package repo and add only `PKGBUILD` + `.SRCINFO`:
   ```bash
   git clone ssh://aur@aur.archlinux.org/peekcam.git aur-peekcam
   cd aur-peekcam
   cp ../PKGBUILD ../.SRCINFO .
   git add PKGBUILD .SRCINFO
   git commit -m "Initial import: peekcam 0.1.1"
   git push                     # first push creates the AUR package
   ```

Only `PKGBUILD`, `.SRCINFO`, and any `.install`/patch files belong in the AUR repo — the
source is fetched from the pinned GitHub tag.

## Notes

- `arch=any` (pure-Python app). Blur deps are **optdepends**; `python-mediapipe` (AUR) is
  x86_64-only, but the base app runs anywhere.
- The launcher exports `QT_QPA_PLATFORM=xcb` (always-on-top needs X11/XWayland) and
  `PEEKCAM_DATA_DIR=/usr/share/peekcam` (where assets + the model are installed).
- To update on a new release: bump `pkgver`, refresh `sha256sums` (`updpkgsums`),
  regenerate `.SRCINFO`, commit, push.
