"""Generate KherveSheet.ico from the runtime make_app_icon().

Single source of truth for the green "KS" monogram lives in
khervesheet.icons.make_app_icon() — that draws the icon via QPainter.
This script renders it at 7 sizes (16..256) into a multi-resolution
.ico and writes the result to the path supplied on the command line
(defaults to build/KherveSheet.ico).

PyInstaller's KherveSheet.spec runs this before the actual Analysis
so the bootloader .exe gets the proper Windows icon.

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

# Use the native platform plugin so system fonts are available.
os.environ.pop("QT_QPA_PLATFORM", None)

from PyQt5.QtCore import QBuffer, QByteArray      # noqa: E402
from PyQt5.QtWidgets import QApplication           # noqa: E402

SIZES = (16, 24, 32, 48, 64, 128, 256)


def _render_icon_pngs() -> dict[int, bytes]:
    """Render the app icon at each standard size via QPainter."""
    app = QApplication.instance() or QApplication([])  # noqa: F841
    from khervesheet.icons import make_app_icon
    icon = make_app_icon()
    pngs: dict[int, bytes] = {}
    for sz in SIZES:
        pm = icon.pixmap(sz, sz)
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


def main(out_path: Path) -> int:
    pngs = _render_icon_pngs()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(_compose_ico(pngs))
    print(f"Wrote {out_path} ({out_path.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    target = (Path(sys.argv[1]) if len(sys.argv) > 1
              else _PROJECT_ROOT / "build" / "KherveSheet.ico")
    raise SystemExit(main(target))
