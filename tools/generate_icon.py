"""Generate KherveSheet.ico / KherveSheet.icns from the runtime icon.

Single source of truth for the green "KS" monogram lives in
khervesheet.appmark — it is drawn as stroked vector paths via QPainter
and stays crisp at any size.  This script renders it at whatever sizes
the target container needs and writes the result to the path supplied
on the command line.

The output format follows the file extension:

  python tools/generate_icon.py build/KherveSheet.ico    # Windows
  python tools/generate_icon.py build/KherveSheet.icns   # macOS

PyInstaller's KherveSheet.spec runs this before the actual Analysis so
the bootloader gets the proper platform icon.

Both writers are pure Python — the .icns container is assembled here
rather than shelling out to ``iconutil`` so the file can be produced
(and inspected) off a Mac.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""
from __future__ import annotations

import os
import struct
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# The mark is drawn as vector paths and needs no system font, so render
# offscreen: this has to work on a headless CI runner with no window
# server, and forcing the plugin keeps the output byte-identical
# wherever the build happens.
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PyQt5.QtCore import QBuffer, QByteArray      # noqa: E402
from PyQt5.QtWidgets import QApplication           # noqa: E402

SIZES = (16, 24, 32, 48, 64, 128, 256)

# ICNS icon-type codes keyed by pixel size, mirroring the mapping
# ``iconutil`` applies to an .iconset folder.  Several sizes appear
# twice because Retina variants are distinct chunk types carrying the
# same pixels (e.g. icon_16x16@2x and icon_32x32 are both 32 px, stored
# as ic11 and icp5).  Every one of these types accepts a PNG payload.
ICNS_TYPES = (
    ("icp4", 16),     # 16x16
    ("icp5", 32),     # 32x32
    ("ic11", 32),     # 16x16@2x
    ("ic12", 64),     # 32x32@2x
    ("ic07", 128),    # 128x128
    ("ic13", 256),    # 128x128@2x
    ("ic08", 256),    # 256x256
    ("ic14", 512),    # 256x256@2x
    ("ic09", 512),    # 512x512
    ("ic10", 1024),   # 512x512@2x
)


def _render_pngs(sizes) -> dict[int, bytes]:
    """Render the app mark at each requested size, as PNG bytes."""
    app = QApplication.instance() or QApplication([])  # noqa: F841
    from khervesheet.icons import _draw_app_pixmap
    pngs: dict[int, bytes] = {}
    for sz in sorted(set(sizes)):
        pm = _draw_app_pixmap(sz)
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QBuffer.WriteOnly)
        pm.save(buf, "PNG")
        buf.close()
        pngs[sz] = bytes(ba)
    return pngs


def _compose_ico(pngs_by_size: dict[int, bytes]) -> bytes:
    """Build an ICO file with one PNG-encoded entry per size."""
    sizes = sorted(pngs_by_size.keys())
    n = len(sizes)
    out = bytearray()
    out += struct.pack("<HHH", 0, 1, n)
    data_offset = 6 + 16 * n
    for sz in sizes:
        data = pngs_by_size[sz]
        w = h = 0 if sz == 256 else sz
        out += struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32,
                           len(data), data_offset)
        data_offset += len(data)
    for sz in sizes:
        out += pngs_by_size[sz]
    return bytes(out)


def _compose_icns(pngs_by_size: dict[int, bytes]) -> bytes:
    """Build an ICNS file: 'icns' + total length, then typed chunks.

    Every field is big-endian, and each chunk's declared length counts
    its own 8-byte header — get that wrong and Finder silently shows the
    generic document icon instead of erroring.
    """
    chunks = bytearray()
    for code, sz in ICNS_TYPES:
        data = pngs_by_size[sz]
        chunks += code.encode("ascii")
        chunks += struct.pack(">I", len(data) + 8)
        chunks += data
    return b"icns" + struct.pack(">I", len(chunks) + 8) + bytes(chunks)


def main(out_path: Path) -> int:
    icns = out_path.suffix.lower() == ".icns"
    sizes = [sz for _c, sz in ICNS_TYPES] if icns else SIZES
    pngs = _render_pngs(sizes)
    blob = _compose_icns(pngs) if icns else _compose_ico(pngs)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(blob)
    print(f"Wrote {out_path} ({out_path.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    target = (Path(sys.argv[1]) if len(sys.argv) > 1
              else _PROJECT_ROOT / "build" / "KherveSheet.ico")
    raise SystemExit(main(target))
