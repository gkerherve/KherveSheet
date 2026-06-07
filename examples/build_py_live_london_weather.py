"""Build "London Weather (live)" — a =PY template that fetches real
hourly temperatures + weather conditions for today and a 7-day forecast
from the free Open-Meteo API (no key).  Shows condition emoji in the
cells and a plot of the conditions drawn as weather icons.  Network-
resilient: falls back to labelled sample data when offline.

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
# Today's hourly temperature + condition, and a 7-day forecast.  The
# conditions are shown as emoji in the cells and as drawn icons in the
# plot (matplotlib shapes, so they render without an emoji font).  Falls
# back to labelled sample data when offline.
import json, urllib.request
import numpy as np, matplotlib.pyplot as plt
from matplotlib.patches import Circle, Polygon

lat  = float(ks("B3"))            # latitude  (London 51.5072)
lon  = float(ks("B4"))            # longitude (London -0.1276)
days = int(ks("B6"))              # forecast days

# --- WMO weather code -> (emoji, label, icon category) ---------------
def code_info(c):
    t = {
        0: ("☀️", "Clear", "sun"),
        1: ("\U0001f324️", "Mainly clear", "sun"),
        2: ("⛅", "Partly cloudy", "partly"),
        3: ("☁️", "Overcast", "cloud"),
        45: ("\U0001f32b️", "Fog", "fog"),
        48: ("\U0001f32b️", "Rime fog", "fog"),
        51: ("\U0001f326️", "Light drizzle", "rain"),
        53: ("\U0001f326️", "Drizzle", "rain"),
        55: ("\U0001f326️", "Dense drizzle", "rain"),
        56: ("\U0001f327️", "Freezing drizzle", "rain"),
        57: ("\U0001f327️", "Freezing drizzle", "rain"),
        61: ("\U0001f327️", "Light rain", "rain"),
        63: ("\U0001f327️", "Rain", "rain"),
        65: ("\U0001f327️", "Heavy rain", "rain"),
        66: ("\U0001f327️", "Freezing rain", "rain"),
        67: ("\U0001f327️", "Freezing rain", "rain"),
        71: ("\U0001f328️", "Light snow", "snow"),
        73: ("\U0001f328️", "Snow", "snow"),
        75: ("\U0001f328️", "Heavy snow", "snow"),
        77: ("\U0001f328️", "Snow grains", "snow"),
        80: ("\U0001f326️", "Rain showers", "rain"),
        81: ("\U0001f326️", "Rain showers", "rain"),
        82: ("\U0001f326️", "Violent showers", "rain"),
        85: ("\U0001f328️", "Snow showers", "snow"),
        86: ("\U0001f328️", "Snow showers", "snow"),
        95: ("⛈️", "Thunderstorm", "thunder"),
        96: ("⛈️", "Thunderstorm, hail", "thunder"),
        99: ("⛈️", "Thunderstorm, hail", "thunder"),
    }
    return t.get(int(c), ("☁️", "Cloudy", "cloud"))

# --- draw a weather icon from primitives (no emoji font needed) ------
def draw_icon(ax, cx, cy, cat, s=0.42):
    def sun(ox, oy, sc, col="#f6b73c"):
        for k in range(8):
            a = k * np.pi / 4
            ax.plot([ox+0.55*sc*np.cos(a), ox+0.92*sc*np.cos(a)],
                    [oy+0.55*sc*np.sin(a), oy+0.92*sc*np.sin(a)],
                    color=col, lw=1.5, zorder=2, solid_capstyle="round")
        ax.add_patch(Circle((ox, oy), 0.42*sc, color=col, ec="none", zorder=3))

    def cloud(ox, oy, sc, col="#9aa3ad"):
        for dx, dy, rr in [(-0.42, 0.0, 0.30), (0.42, 0.0, 0.32),
                           (0.0, 0.20, 0.40), (0.0, -0.05, 0.50)]:
            ax.add_patch(Circle((ox+dx*sc, oy+dy*sc), rr*sc,
                                color=col, ec="none", zorder=3))

    def drops(ox, oy, sc, col="#3b82f6", n=3):
        for j in range(n):
            dx = (j-(n-1)/2)*0.30*sc
            ax.plot([ox+dx, ox+dx-0.05*sc], [oy-0.45*sc, oy-0.80*sc],
                    color=col, lw=1.8, zorder=4, solid_capstyle="round")

    def flakes(ox, oy, sc, col="#7fb2e6", n=3):
        for j in range(n):
            dx = (j-(n-1)/2)*0.30*sc
            ax.scatter([ox+dx], [oy-0.62*sc], marker="*",
                       s=70*sc, color=col, zorder=4)

    def bolt(ox, oy, sc, col="#f5c518"):
        p = np.array([(0.0, 0.45), (-0.22, -0.02), (-0.02, -0.02),
                      (-0.18, -0.5), (0.24, 0.1), (0.04, 0.1)])
        ax.add_patch(Polygon(np.column_stack([ox+p[:, 0]*sc, oy+p[:, 1]*sc]),
                             closed=True, color=col, ec="none", zorder=4))

    if cat == "sun":
        sun(cx, cy, s)
    elif cat == "partly":
        sun(cx-0.28*s, cy+0.25*s, s*0.65); cloud(cx+0.1*s, cy-0.05*s, s*0.95)
    elif cat == "fog":
        cloud(cx, cy+0.12*s, s*0.9)
        for j in range(3):
            yy = cy-0.32*s-0.18*s*j
            ax.plot([cx-0.5*s, cx+0.5*s], [yy, yy],
                    color="#9aa3ad", lw=1.6, zorder=4, solid_capstyle="round")
    elif cat == "rain":
        cloud(cx, cy+0.12*s, s); drops(cx, cy, s)
    elif cat == "snow":
        cloud(cx, cy+0.12*s, s); flakes(cx, cy, s)
    elif cat == "thunder":
        cloud(cx, cy+0.12*s, s); bolt(cx, cy, s)
    else:
        cloud(cx, cy, s)

def fetch_json(url, timeout=8):
    req = urllib.request.Request(url, headers={"User-Agent": "KherveSheet"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)

# timezone=auto -> times are in the location's local zone; "current"
# gives "now" so we can show the NEXT 24 hours, not the past ones.
url = ("https://api.open-meteo.com/v1/forecast"
       f"?latitude={lat}&longitude={lon}"
       "&hourly=temperature_2m,weathercode"
       "&daily=temperature_2m_max,temperature_2m_min,weathercode"
       "&current=temperature_2m,weathercode"
       f"&timezone=auto&forecast_days={days}")
live = True
now = None
try:
    d = fetch_json(url)
    htime = d["hourly"]["time"]; htemp = d["hourly"]["temperature_2m"]
    hcode = d["hourly"]["weathercode"]
    dday = d["daily"]["time"]
    dmax = d["daily"]["temperature_2m_max"]
    dmin = d["daily"]["temperature_2m_min"]
    dcode = d["daily"]["weathercode"]
    now = d["current"]["time"]                    # local "now", e.g. 14:15
except Exception:
    live = False                                  # offline -> sample data
    rng = np.random.default_rng(0)
    htime = [f"2025-01-01T{h:02d}:00" for h in range(48)]
    htemp = (8 + 5*np.sin((np.arange(48)-9)/24*2*np.pi)
             + rng.normal(0, 0.5, 48)).round(1).tolist()
    hcode = ([3, 3, 3, 45, 2, 1, 0, 0, 1, 2, 2, 3, 61, 63, 61, 80,
              3, 2, 1, 0, 0, 1, 2, 3]) * 2
    dday = [f"day {i+1}" for i in range(days)]
    dmax = (12 + rng.normal(0, 2, days)).round(1).tolist()
    dmin = (5 + rng.normal(0, 2, days)).round(1).tolist()
    dcode = [0, 2, 3, 61, 80, 1, 95][:days]

# Find "now" in the hourly series and take the NEXT 24 hours from there.
start = 0
if now is not None:
    for i, t in enumerate(htime):
        if t <= now:
            start = i              # last hour bucket at or before now
        else:
            break
end = start + 24
htime = htime[start:end]
htemp = htemp[start:end]
hcode = hcode[start:end]

# Reverse-geocode the latitude/longitude into a place name for B5.
location = f"{lat:.4f}, {lon:.4f}"
try:
    g = fetch_json("https://api.bigdatacloud.net/data/"
                   f"reverse-geocode-client?latitude={lat}&longitude={lon}"
                   "&localityLanguage=en")
    place = (g.get("city") or g.get("locality")
             or g.get("principalSubdivision") or "")
    cc = g.get("countryCode") or ""
    if place:
        location = place + (f", {cc}" if cc else "")
except Exception:
    pass
ks_set("B5", location)             # write the resolved location name

hours = [t[11:16] for t in htime]
temps = [float(v) for v in htemp]
hcat = [code_info(c)[2] for c in hcode]
hcond = [f"{code_info(c)[0]} {code_info(c)[1]}" for c in hcode]
dcat = [code_info(c)[2] for c in dcode[:days]]
dcond = [f"{code_info(c)[0]} {code_info(c)[1]}" for c in dcode[:days]]

ks_set("A10", hours)                 # hourly table: Hour | Temp | Condition
ks_set("B10", temps)
ks_set("C10", hcond)
ks_set("D10", [str(x) for x in dday[:days]])   # forecast: Date|Min|Max|Cond
ks_set("E10", [float(v) for v in dmin[:days]])
ks_set("F10", [float(v) for v in dmax[:days]])
ks_set("G10", dcond)
ks_set("B7", "live" if live else "offline (sample data)")

# --- plot: hourly condition icons, hourly temperature, 7-day icons ---
fig, (axc, axt, axf) = plt.subplots(
    3, 1, figsize=(7.8, 6.4),
    gridspec_kw={"height_ratios": [1.1, 2.6, 1.4]})

fig.suptitle(f"{location} — weather"
             + ("" if live else "   [offline sample]"),
             fontsize=12, fontweight="bold")
step = list(range(0, 24, 3))         # every 3 h -> 8 icons
axc.set_xlim(-0.6, len(step)-0.4); axc.set_ylim(-0.9, 1.2)
axc.set_aspect("equal"); axc.axis("off")
axc.set_title("Next 24 hours")
for j, i in enumerate(step):
    draw_icon(axc, j, 0.1, hcat[i], 0.40)
    axc.text(j, -0.7, hours[i], ha="center", fontsize=7)
    axc.text(j, 1.0, f"{temps[i]:.0f}°", ha="center", fontsize=8,
             fontweight="bold")

axt.plot(range(24), temps, "o-", ms=3, color="#ed7d31")
axt.set_xticks(range(0, 24, 3))
axt.set_xticklabels([hours[i] for i in range(0, 24, 3)])
axt.set_ylabel("°C"); axt.grid(True, alpha=0.3)
axt.set_title("Hourly temperature")

ndays = len(dday[:days])
axf.set_xlim(-0.6, ndays-0.4); axf.set_ylim(-1.0, 1.3)
axf.set_aspect("equal"); axf.axis("off")
axf.set_title("7-day forecast")
for i in range(ndays):
    draw_icon(axf, i, 0.15, dcat[i], 0.42)
    axf.text(i, 1.05, f"{dmax[i]:.0f}°/{dmin[i]:.0f}°",
             ha="center", fontsize=7, fontweight="bold")
    axf.text(i, -0.8, str(dday[i])[5:], ha="center", fontsize=7)
fig.subplots_adjust(hspace=0.55, top=0.90, bottom=0.04)
plt.gcf()'''


def build():
    wb = Workbook(min_rows=60, min_cols=14)
    s = wb.add_sheet("London Weather")
    s.title_block("London Weather (live)",
                  "Hourly temperature + conditions and a 7-day forecast "
                  "(Open-Meteo)")

    inputs = [("Latitude", 51.5072), ("Longitude", -0.1276),
              ("Location (auto)", ""), ("Forecast days", 7),
              ("Data status", "")]
    for i, (label, v) in enumerate(inputs):
        r = 2 + i
        s.set(r, 0, label); s.set(r, 1, v)
        s.fmt(r, 0, bold=True)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center")
    # Location (B5) and Data status (B7) are filled by the =PY cell.
    s.fmt(4, 1, bg=PALETTE["good"], align="center")
    s.fmt(6, 1, bg=PALETTE["good"], align="center")

    # Result-table headers (filled by the =PY cell).
    s.set(8, 0, "Hour"); s.set(8, 1, "Temp (°C)"); s.set(8, 2, "Condition")
    s.set(8, 3, "Date"); s.set(8, 4, "Min °C"); s.set(8, 5, "Max °C")
    s.set(8, 6, "Condition")
    for c in (0, 1, 2, 3, 4, 5, 6):
        s.fmt(8, c, bold=True, bg=PALETTE["header"],
              font_color=PALETTE["header_text"], align="center")

    s.set(1, 8, "Fetch ▼"); s.fmt(1, 8, bold=True, font_color=PALETTE["header"])
    s.formula(2, 8, "=PY\n" + PY_BODY)
    s.note(0, 9,
           "Press Ctrl+Enter on the =PY cell to fetch live weather. The "
           "Condition columns show emoji; the plot draws the conditions as "
           "icons. Change latitude/longitude (B3/B4) for another city. "
           "Works offline with sample data (Data status, B7). "
           "Source: Open-Meteo.")
    s.col_width(0, 90)
    s.col_width(2, 130)
    s.col_width(6, 130)

    out = os.path.join(os.path.dirname(__file__), "python", "Live Data",
                       "London Weather (live).ksheet")
    wb.save(out)
    print("Wrote", out)


if __name__ == "__main__":
    build()
