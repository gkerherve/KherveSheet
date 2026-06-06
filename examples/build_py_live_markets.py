"""Build live market templates — "NVIDIA Stock (live)" and "Bitcoin Price
(live)" — =PY cells that fetch the last 3 months of daily prices from the
free Yahoo Finance chart API and plot the 3-month and 3-week views.
Network-resilient: falls back to labelled sample data when offline.

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

PY_BODY = r'''# Live daily prices from the Yahoo Finance chart API (no key).
# Fetches ~3 months of daily closes for the ticker in B3 and plots the
# 3-month and 3-week views; falls back to sample data when offline.
import json, urllib.request, datetime as dt
import numpy as np, matplotlib.pyplot as plt

ticker = str(ks("B3")).strip()

def fetch_json(url, timeout=8):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)

url = ("https://query1.finance.yahoo.com/v8/finance/chart/"
       f"{ticker}?range=3mo&interval=1d")
live = True
try:
    res = fetch_json(url)["chart"]["result"][0]
    ts = res["timestamp"]
    closes = res["indicators"]["quote"][0]["close"]
    dates, price = [], []
    for t, c in zip(ts, closes):
        if c is None:
            continue
        dates.append(dt.datetime.utcfromtimestamp(t).strftime("%Y-%m-%d"))
        price.append(float(c))
except Exception:
    live = False                                   # offline -> sample data
    rng = np.random.default_rng(abs(hash(ticker)) % 2**31)
    n = 63
    start = dt.date.today() - dt.timedelta(days=n)
    dates = [(start + dt.timedelta(days=i)).strftime("%Y-%m-%d")
             for i in range(n)]
    steps = rng.normal(0, 1, n)
    price = (100 * np.exp(np.cumsum(0.002 + 0.02*steps))).round(2).tolist()

price = np.array(price)
n3w = min(15, len(price))                          # ~3 weeks of trading days
ks_set("B5", "live" if live else "offline (sample data)")
ks_set("B6", round(float(price[-1]), 2))           # latest close
# Write the most recent ~3 weeks as a table.
ks_set("A10", dates[-n3w:])
ks_set("B10", price[-n3w:].round(2).tolist())

fig, (a1, a2) = plt.subplots(1, 2, figsize=(8.4, 3.8))
a1.plot(np.arange(len(price)), price, color="#4472c4")
a1.set_title(f"{ticker} — last 3 months"
             + ("" if live else "  [offline sample]"))
a1.set_ylabel("price"); a1.grid(True, alpha=0.3)
step = max(1, len(price)//5)
a1.set_xticks(np.arange(0, len(price), step))
a1.set_xticklabels([dates[i] for i in range(0, len(price), step)],
                   rotation=30, ha="right", fontsize=7)
xi = np.arange(n3w)
a2.plot(xi, price[-n3w:], "o-", color="#ed7d31")
a2.set_title(f"{ticker} — last 3 weeks"); a2.grid(True, alpha=0.3)
a2.set_xticks(xi[::3])
a2.set_xticklabels([dates[-n3w:][i] for i in range(0, n3w, 3)],
                   rotation=30, ha="right", fontsize=7)
plt.tight_layout()
plt.gcf()'''


def _make(name, subtitle, ticker, out_name):
    wb = Workbook(min_rows=60, min_cols=14)
    s = wb.add_sheet(name)
    s.title_block(name, subtitle)
    inputs = [("Ticker", ticker), ("Range", "3 months / 3 weeks"),
              ("Data status", ""), ("Latest close", "")]
    for i, (label, v) in enumerate(inputs):
        r = 2 + i
        s.set(r, 0, label); s.set(r, 1, v)
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center")
    s.fmt(4, 1, bg=PALETTE["good"], align="center")
    s.fmt(5, 1, bg=PALETTE["good"], align="center", number_format="0.00")

    s.set(8, 0, "Date"); s.set(8, 1, "Close")
    for c in (0, 1):
        s.fmt(8, c, bold=True, bg=PALETTE["header"],
              font_color=PALETTE["header_text"], align="center")

    s.set(1, 7, "Fetch ▼"); s.fmt(1, 7, bold=True, font_color=PALETTE["header"])
    s.formula(2, 7, "=PY\n" + PY_BODY)
    s.note(0, 8,
           "Press Ctrl+Enter on the =PY cell to fetch live prices. Change "
           "the ticker in B3 (Yahoo symbols, e.g. AAPL, MSFT, ETH-USD). "
           "Works offline with sample data (see Data status). "
           "Source: Yahoo Finance.")
    s.col_width(0, 95)

    out = os.path.join(os.path.dirname(__file__), "python", "Live Data",
                       out_name)
    wb.save(out)
    print("Wrote", out)


def build():
    _make("NVIDIA Stock (live)",
          "Last 3 months & 3 weeks of NVDA daily closes (Yahoo Finance)",
          "NVDA", "NVIDIA Stock (live).ksheet")
    _make("Bitcoin Price (live)",
          "Last 3 months & 3 weeks of BTC-USD daily closes (Yahoo Finance)",
          "BTC-USD", "Bitcoin Price (live).ksheet")


if __name__ == "__main__":
    build()
