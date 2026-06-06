"""Build "London Weather (live)" — a =PY template that fetches real
hourly temperatures for today and a 7-day forecast from the free
Open-Meteo API (no key).  Network-resilient: falls back to labelled
sample data when offline so the workbook always opens cleanly.

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

PY_BODY = r'''# Live London weather from Open-Meteo (no API key needed).
# Fetches today's hourly temperature and a 7-day forecast; if the network
# is unavailable it falls back to clearly-labelled sample data so the
# sheet still opens.
import json, urllib.request
import numpy as np, matplotlib.pyplot as plt

lat  = float(ks("B3"))            # latitude  (London 51.5072)
lon  = float(ks("B4"))            # longitude (London -0.1276)
days = int(ks("B6"))              # forecast days

def fetch_json(url, timeout=8):
    req = urllib.request.Request(url, headers={"User-Agent": "KherveSheet"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)

url = ("https://api.open-meteo.com/v1/forecast"
       f"?latitude={lat}&longitude={lon}"
       "&hourly=temperature_2m"
       "&daily=temperature_2m_max,temperature_2m_min"
       f"&timezone=Europe/London&forecast_days={days}")
live = True
try:
    d = fetch_json(url)
    htime = d["hourly"]["time"]; htemp = d["hourly"]["temperature_2m"]
    dday = d["daily"]["time"]
    dmax = d["daily"]["temperature_2m_max"]
    dmin = d["daily"]["temperature_2m_min"]
except Exception:
    live = False                                  # offline -> sample data
    rng = np.random.default_rng(0)
    htime = [f"2025-01-01T{h:02d}:00" for h in range(24)]
    htemp = (8 + 5*np.sin((np.arange(24)-9)/24*2*np.pi)
             + rng.normal(0, 0.5, 24)).round(1).tolist()
    dday = [f"day {i+1}" for i in range(days)]
    dmax = (12 + rng.normal(0, 2, days)).round(1).tolist()
    dmin = (5 + rng.normal(0, 2, days)).round(1).tolist()

# Today = the first 24 hourly samples.
hours = [t[11:16] for t in htime[:24]]
temps = [float(v) for v in htemp[:24]]
ks_set("A10", hours)               # write the hourly table (Hour, Temp)
ks_set("B10", temps)
ks_set("D10", [str(x) for x in dday[:days]])   # 7-day forecast table
ks_set("E10", [float(v) for v in dmin[:days]])
ks_set("F10", [float(v) for v in dmax[:days]])
ks_set("B7", "live" if live else "offline (sample data)")

fig, (a1, a2) = plt.subplots(2, 1, figsize=(7.2, 5.2))
a1.plot(range(24), temps, "o-", color="#ed7d31")
a1.set_xticks(range(0, 24, 3))
a1.set_xticklabels([hours[i] for i in range(0, 24, 3)])
a1.set_ylabel("°C"); a1.grid(True, alpha=0.3)
a1.set_title("London — temperature today (hourly)"
             + ("" if live else "  [offline sample]"))
xi = np.arange(len(dday[:days]))
a2.plot(xi, dmax[:days], "o-", color="#c00000", label="max")
a2.plot(xi, dmin[:days], "o-", color="#4472c4", label="min")
a2.fill_between(xi, dmin[:days], dmax[:days], alpha=0.15, color="#4472c4")
a2.set_xticks(xi); a2.set_xticklabels([str(x)[:10] for x in dday[:days]],
                                      rotation=30, ha="right", fontsize=8)
a2.set_ylabel("°C"); a2.grid(True, alpha=0.3); a2.legend()
a2.set_title("7-day forecast (min / max)")
plt.tight_layout()
plt.gcf()'''


def build():
    wb = Workbook(min_rows=60, min_cols=14)
    s = wb.add_sheet("London Weather")
    s.title_block("London Weather (live)",
                  "Hourly today + 7-day forecast via Open-Meteo")

    inputs = [("Latitude", 51.5072), ("Longitude", -0.1276),
              ("Location", "London, UK"), ("Forecast days", 7),
              ("Data status", "")]
    for i, (label, v) in enumerate(inputs):
        r = 2 + i
        s.set(r, 0, label); s.set(r, 1, v)
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center")
    s.fmt(6, 1, bg=PALETTE["good"], align="center")

    # Result-table headers (filled by the =PY cell below them).
    s.set(8, 0, "Hour"); s.set(8, 1, "Temp (°C)")
    s.set(8, 3, "Date"); s.set(8, 4, "Min °C"); s.set(8, 5, "Max °C")
    for c in (0, 1, 3, 4, 5):
        s.fmt(8, c, bold=True, bg=PALETTE["header"],
              font_color=PALETTE["header_text"], align="center")

    # =PY cell placed to the right (clear of the tables it writes).
    s.set(1, 7, "Fetch ▼"); s.fmt(1, 7, bold=True, font_color=PALETTE["header"])
    s.formula(2, 7, "=PY\n" + PY_BODY)
    s.note(0, 8,
           "Press Ctrl+Enter on the =PY cell to fetch live weather. Change "
           "the latitude/longitude (B3/B4) for another city. Works offline "
           "with sample data (see Data status in B7). Source: Open-Meteo.")
    s.col_width(0, 90)

    out = os.path.join(os.path.dirname(__file__), "python", "Live Data",
                       "London Weather (live).ksheet")
    wb.save(out)
    print("Wrote", out)


if __name__ == "__main__":
    build()
