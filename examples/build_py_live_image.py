"""Build "Image from URL (live)" — a =PY template that fetches a picture
from the web with ks_image() and embeds it in the sheet.  Network-
resilient: shows a generated placeholder image when offline.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from ksheet_author import Workbook, PALETTE  # noqa: E402

PY_BODY = r'''# Fetch a picture from the web and embed it. ks_image() accepts
# a URL, a local file path, raw image bytes, a PIL image, or a NumPy
# H x W x 3 array. Returning an image from a =PY cell embeds it next to
# the cell. Falls back to a generated placeholder when offline.
import numpy as np
url = str(ks("B3")).strip()
try:
    pic = ks_image(url)                 # download + decode the image
    ks_set("B4", "live")
except Exception:
    ks_set("B4", "offline (placeholder)")
    g = np.linspace(40, 220, 240).astype(np.uint8)
    pic = np.dstack([np.tile(g, (140, 1))] * 3)   # grey placeholder
pic                                     # last line: embeds the picture'''


def build():
    wb = Workbook(min_rows=30, min_cols=12)
    s = wb.add_sheet("Image")
    s.title_block("Image from URL (live)",
                  "Fetch and embed a picture with ks_image()")

    inputs = [("Image URL",
               "https://upload.wikimedia.org/wikipedia/commons/thumb/"
               "c/c3/Python-logo-notext.svg/120px-Python-logo-notext.svg.png"),
              ("Data status", "")]
    for i, (label, v) in enumerate(inputs):
        r = 2 + i
        s.set(r, 0, label); s.set(r, 1, v)
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="left")
    s.fmt(3, 1, bg=PALETTE["good"], align="center")

    s.set(1, 5, "Fetch ▼"); s.fmt(1, 5, bold=True, font_color=PALETTE["header"])
    s.formula(2, 5, "=PY\n" + PY_BODY)
    s.note(0, 6,
           "Press Ctrl+Enter on the =PY cell to fetch the image in B3. "
           "ks_image() also accepts a local file path, raw bytes, a PIL "
           "image or a NumPy array. Paste any image URL into B3. Works "
           "offline with a placeholder (see Data status).")
    s.col_width(0, 100)
    s.col_width(1, 360)

    out = os.path.join(os.path.dirname(__file__), "python", "Live Data",
                       "Image from URL (live).ksheet")
    wb.save(out)
    print("Wrote", out)


if __name__ == "__main__":
    build()
