"""Build "News (live)" — a =PY template that fetches live headlines from
an RSS feed (BBC News by default, no key) and shows each headline WITH its
image as a news board, plus a headlines table.  Network-resilient: falls
back to labelled sample headlines when offline.

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

PY_BODY = r'''# Live news headlines with images from an RSS feed (no API key).
# Each headline is shown with its thumbnail; the titles/links are also
# written to the table. Falls back to sample headlines when offline.
import urllib.request, xml.etree.ElementTree as ET, textwrap
import datetime as dt
import numpy as np, matplotlib.pyplot as plt
from PyQt5.QtGui import QImage

feed = str(ks("B3")).strip()        # RSS feed URL
n = int(ks("B4"))                   # number of headlines

def _get(u, timeout=8):
    req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=timeout).read()

def _img(u):                        # download + decode a thumbnail (via Qt)
    if not u:
        return None
    try:
        qi = QImage()
        qi.loadFromData(_get(u))
        if qi.isNull():
            return None
        qi = qi.convertToFormat(QImage.Format_RGBA8888)
        w, h = qi.width(), qi.height()
        ptr = qi.bits(); ptr.setsize(h * w * 4)
        return np.frombuffer(ptr, np.uint8).reshape(h, w, 4).copy()
    except Exception:
        return None

NS = {"media": "http://search.yahoo.com/mrss/"}
live = True
items = []
try:
    root = ET.fromstring(_get(feed))
    for it in root.findall(".//item")[:n]:
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        img = None
        for tag in ("media:thumbnail", "media:content"):
            e = it.find(tag, NS)
            if e is not None and e.get("url"):
                img = e.get("url"); break
        if img is None:
            enc = it.find("enclosure")
            if enc is not None:
                img = enc.get("url")
        items.append((title, link, img))
except Exception:
    live = False
    items = [(f"Sample headline {i + 1}", "", None) for i in range(n)]

updated = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")   # fetch time
ks_set("B5", "live" if live else "offline (sample)")
ks_set("B6", updated)                                      # last updated
ks_set("A9", [str(i + 1) for i in range(len(items))])     # # | Headline | Link
ks_set("B9", [t for t, _, _ in items])
ks_set("C9", [lk for _, lk, _ in items])

# News board: one row per headline = thumbnail (left) + title (right).
m = max(1, len(items))
fig = plt.figure(figsize=(8.6, 1.25 * m + 0.4))
gs = fig.add_gridspec(m, 2, width_ratios=[1, 3], hspace=0.45, wspace=0.04)
for i, (title, link, img) in enumerate(items):
    ai = fig.add_subplot(gs[i, 0]); ai.axis("off")
    arr = _img(img)
    if arr is not None:
        ai.imshow(arr)
    else:
        ai.add_patch(plt.Rectangle((0, 0), 1, 1, color="#dfe3e8"))
        ai.set_xlim(0, 1); ai.set_ylim(0, 1)
        ai.text(0.5, 0.5, "no image", ha="center", va="center",
                fontsize=7, color="#888")
    at = fig.add_subplot(gs[i, 1]); at.axis("off")
    at.text(0.0, 0.5, textwrap.fill(title, 66), va="center", fontsize=9)
domain = feed.split("//")[-1].split("/")[0]
fig.suptitle(f"Live news — {domain}"
             + ("" if live else "   [offline sample]"),
             fontsize=12, fontweight="bold")
fig.text(0.5, 0.965, f"Updated {updated}", ha="center",
         fontsize=8, color="#666")
fig.subplots_adjust(top=0.92, left=0.01, right=0.99, bottom=0.02)
plt.gcf()'''


def build():
    wb = Workbook(min_rows=40, min_cols=12)
    s = wb.add_sheet("News")
    s.title_block("News (live)",
                  "Live headlines with images from an RSS feed")

    inputs = [("Feed URL", "https://feeds.bbci.co.uk/news/rss.xml"),
              ("Headlines", 5), ("Data status", ""), ("Last updated", "")]
    for i, (label, v) in enumerate(inputs):
        r = 2 + i
        s.set(r, 0, label); s.set(r, 1, v)
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="left")
    s.fmt(4, 1, bg=PALETTE["good"], align="center")   # status
    s.fmt(5, 1, bg=PALETTE["good"], align="center")   # last updated

    s.set(7, 0, "#"); s.set(7, 1, "Headline"); s.set(7, 2, "Link")
    for c in (0, 1, 2):
        s.fmt(7, c, bold=True, bg=PALETTE["header"],
              font_color=PALETTE["header_text"], align="center")

    s.set(1, 4, "Fetch ▼"); s.fmt(1, 4, bold=True, font_color=PALETTE["header"])
    s.formula(2, 4, "=PY\n" + PY_BODY)
    s.note(0, 5,
           "Press Ctrl+Enter on the =PY cell to fetch live news. Each "
           "headline is shown with its image in the plot, and listed in "
           "the table. Change the RSS feed in B3 (e.g. a Guardian or "
           "Reuters feed) or the count in B4. Right-click the cell -> "
           "Python loop to auto-refresh. Works offline with samples.")
    s.col_width(0, 60)
    s.col_width(1, 430)
    s.col_width(2, 240)

    out = os.path.join(os.path.dirname(__file__), "python", "Live Data",
                       "News (live).ksheet")
    wb.save(out)
    print("Wrote", out)


if __name__ == "__main__":
    build()
