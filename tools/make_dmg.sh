#!/usr/bin/env bash
#
# Wrap dist/KherveSheet.app into a distributable .dmg.
#
# The macOS counterpart of KherveSheet_setup.iss.  Unlike the Windows
# installer there is nothing to unregister or clean up on upgrade: a
# drag-install replaces the whole bundle atomically, so the stale
# _internal problem the .iss works around cannot happen here.
#
# Usage:  tools/make_dmg.sh [output-dir]        # default: installer/
#
# Copyright (C) 2026 Gwilherm Kerherve
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="$ROOT/dist/KherveSheet.app"
OUT_DIR="${1:-$ROOT/installer}"
STAGE="$ROOT/build/dmg"

if [[ ! -d "$APP" ]]; then
  echo "make_dmg.sh: $APP not found — run pyinstaller KherveSheet.spec first" >&2
  exit 1
fi

VERSION="0.1.0"
if [[ -f "$ROOT/khervesheet/VERSION" ]]; then
  VERSION="$(tr -d '[:space:]' < "$ROOT/khervesheet/VERSION")"
fi
ARCH="$(uname -m)"
DMG="$OUT_DIR/KherveSheet-${VERSION}-${ARCH}.dmg"

# Ad-hoc signature.  Apple Silicon refuses to launch an unsigned Mach-O
# outright, and any post-build edit to the bundle invalidates whatever
# PyInstaller signed, so re-sign the finished tree before sealing it.
# This is NOT notarization: without a Developer ID the download is still
# quarantined on the user's machine (see README.macos.md).
echo "==> ad-hoc signing $APP"
codesign --force --deep --sign - --timestamp=none "$APP"
codesign --verify --deep --strict "$APP"

echo "==> staging"
rm -rf "$STAGE"
mkdir -p "$STAGE" "$OUT_DIR"
cp -R "$APP" "$STAGE/"
# The /Applications symlink is what turns the mounted window into the
# familiar drag-to-install gesture.
ln -s /Applications "$STAGE/Applications"

echo "==> building $DMG"
rm -f "$DMG"
hdiutil create \
  -volname "KherveSheet" \
  -srcfolder "$STAGE" \
  -fs HFS+ \
  -format UDZO \
  -imagekey zlib-level=9 \
  -ov \
  "$DMG"

rm -rf "$STAGE"
echo "==> done: $DMG"
ls -lh "$DMG"
