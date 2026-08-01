# Building and running KherveSheet on macOS

PyInstaller cannot cross-compile, so a macOS build has to happen on a
Mac. Either run the steps below locally or let
`.github/workflows/macos-build.yml` do it on a GitHub runner and download
the DMG artifact.

## Build

```bash
pip install -r requirements.txt
pip install pyinstaller
printf '0.1.%s+%s' "$(git rev-list --count HEAD)" "$(git rev-parse --short HEAD)" \
  > khervesheet/VERSION
pyinstaller KherveSheet.spec --noconfirm
tools/make_dmg.sh
```

Output: `installer/KherveSheet-<version>-<arch>.dmg`.

The `khervesheet/VERSION` step is not optional. A frozen bundle ships no
`.git`, so without that file the title bar reports the `0.1.0`
placeholder instead of the real build.

## Architectures

`arm64` and `x86_64` are separate builds. There is no universal2 DMG,
because a universal bundle would need universal wheels for numpy, scipy,
h5py and pygit2 all the way down and those are not consistently
published. The Intel DMG runs on Apple Silicon through Rosetta, so it is
the safe one to hand to someone whose hardware you do not know; the arm64
DMG is the faster one for a Mac you know is Apple Silicon.

## Gatekeeper

The DMG is **ad-hoc signed, not notarized.** The ad-hoc signature is what
lets the binary execute at all on Apple Silicon; it does nothing for
Gatekeeper. macOS quarantines anything downloaded from a browser, so on
first launch users will see *"KherveSheet is damaged and can't be
opened"* — which is misleading. Nothing is damaged; the app simply has no
Developer ID.

Either:

```bash
xattr -dr com.apple.quarantine /Applications/KherveSheet.app
```

or right-click the app → **Open** → **Open** in the dialog. A DMG copied
over by AirDrop or a USB stick is not quarantined and just opens.

Removing this friction requires an Apple Developer Program membership
(99 USD/yr) to sign with a Developer ID and notarize through Apple. Once
you have one, add `codesign --options runtime` with the identity plus a
`xcrun notarytool submit --wait` and `xcrun stapler staple` step to
`tools/make_dmg.sh`.

## Known gaps

- **No auto-update.** `khervesheet/updater.py` gates every entry point on
  `sys.platform.startswith("win")`, so macOS builds never check for
  updates. Users update by downloading a new DMG.
- **File associations** are declared in the bundle's `Info.plist`, but
  macOS only honours them once the app has been moved to `/Applications`
  and registered by LaunchServices — which can take a login cycle, or a
  manual `lsregister -f /Applications/KherveSheet.app`.
