"""Build the rich Reference template set (examples/templates/Reference/).

Color Palette (RGB), Distance Matrix, Time Zones, World Population,
Multi-Sheet Demo, Sine/Cos Plot Data.

Run:  python examples/build_tpl_reference.py
Copyright (C) 2026 Gwilherm Kerherve - GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from ksheet_author import Workbook, Series, PALETTE  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "templates", "Reference")


def _save(wb, name):
    wb.save(os.path.join(OUT, name))


def color_palette():
    wb = Workbook(min_rows=30, min_cols=8)
    s = wb.add_sheet("Colors")
    s.title_block("Color Palette (RGB)",
                  "Named colours with RGB, hex and a live swatch", span=6)
    colors = [
        ("Red", 255, 0, 0), ("Orange", 255, 165, 0),
        ("Yellow", 255, 215, 0), ("Green", 0, 176, 80),
        ("Teal", 0, 150, 136), ("Blue", 68, 114, 196),
        ("Navy", 27, 42, 74), ("Purple", 155, 89, 182),
        ("Pink", 255, 105, 180), ("Brown", 139, 69, 19),
        ("Grey", 128, 128, 128), ("Black", 0, 0, 0),
    ]
    TS = 4
    headers = ["Name", "R", "G", "B", "Hex", "Swatch"]
    for j, h in enumerate(headers):
        s.set(TS, j, h)
        s.fmt(TS, j, bold=True, bg=PALETTE["header"],
              font_color=PALETTE["header_text"], align="center")
    for i, (nm, r, g, b) in enumerate(colors):
        rr = TS + 1 + i
        hx = f"#{r:02X}{g:02X}{b:02X}"
        s.set(rr, 0, nm)
        s.set(rr, 1, r)
        s.set(rr, 2, g)
        s.set(rr, 3, b)
        s.set(rr, 4, hx)
        s.fmt(rr, 0, align="left")
        for c in (1, 2, 3):
            s.fmt(rr, c, align="center")
        s.fmt(rr, 4, align="center")
        s.fmt(rr, 5, bg=hx)            # the swatch cell
    s.box(TS, 0, TS + len(colors), 5, color=PALETTE["header"], width=1.0)
    s.col_width(0, 100)
    s.col_width(4, 90)
    s.col_width(5, 90)
    _save(wb, "Color Palette.ksheet")


def distance_matrix():
    wb = Workbook(min_rows=20, min_cols=12)
    s = wb.add_sheet("Distances")
    s.title_block("Distance Matrix",
                  "Approx. road distances between UK cities (miles)", span=8)
    cities = ["London", "Birmingham", "Manchester", "Leeds",
              "Glasgow", "Cardiff", "Bristol"]
    D = {
        ("London", "Birmingham"): 126, ("London", "Manchester"): 200,
        ("London", "Leeds"): 196, ("London", "Glasgow"): 414,
        ("London", "Cardiff"): 150, ("London", "Bristol"): 119,
        ("Birmingham", "Manchester"): 88, ("Birmingham", "Leeds"): 119,
        ("Birmingham", "Glasgow"): 293, ("Birmingham", "Cardiff"): 107,
        ("Birmingham", "Bristol"): 89, ("Manchester", "Leeds"): 44,
        ("Manchester", "Glasgow"): 214, ("Manchester", "Cardiff"): 181,
        ("Manchester", "Bristol"): 167, ("Leeds", "Glasgow"): 220,
        ("Leeds", "Cardiff"): 230, ("Leeds", "Bristol"): 209,
        ("Glasgow", "Cardiff"): 397, ("Glasgow", "Bristol"): 372,
        ("Cardiff", "Bristol"): 44,
    }

    def dist(a, b):
        if a == b:
            return 0
        return D.get((a, b)) or D.get((b, a)) or 0
    TS = 4
    # header row of city names
    s.set(TS, 0, "miles")
    s.fmt(TS, 0, bold=True, bg=PALETTE["header"],
          font_color=PALETTE["header_text"], align="center")
    for j, c in enumerate(cities):
        s.set(TS, 1 + j, c)
        s.fmt(TS, 1 + j, bold=True, bg=PALETTE["header"],
              font_color=PALETTE["header_text"], align="center")
        s.set(TS + 1 + j, 0, c)
        s.fmt(TS + 1 + j, 0, bold=True, bg=PALETTE["header"],
              font_color=PALETTE["header_text"], align="left")
    for i, a in enumerate(cities):
        for j, b in enumerate(cities):
            rr, cc = TS + 1 + i, 1 + j
            s.set(rr, cc, dist(a, b))
            s.fmt(rr, cc, align="center",
                  bg=(PALETTE["band"] if i == j else None))
    s.box(TS, 0, TS + len(cities), len(cities), color=PALETTE["header"],
          width=1.0)
    for c in range(len(cities) + 1):
        s.col_width(c, 90)
    _save(wb, "Distance Matrix.ksheet")


def time_zones():
    wb = Workbook(min_rows=30, min_cols=8)
    s = wb.add_sheet("Time Zones")
    s.title_block("World Time Zones",
                  "Local time for a reference UTC hour", span=6)
    s.set(3, 0, "Reference UTC hour (0-23)")
    s.set(3, 1, 12)
    s.fmt(3, 1, bg=PALETTE["warn"], align="center", number_format="0")
    s.col_width(0, 200)
    zones = [
        ("Los Angeles", -8), ("New York", -5), ("London", 0),
        ("Paris", 1), ("Cairo", 2), ("Moscow", 3), ("Dubai", 4),
        ("Mumbai", 5.5), ("Singapore", 8), ("Tokyo", 9),
        ("Sydney", 10), ("Auckland", 12),
    ]
    TS = 5
    rows = []
    for i, (city, off) in enumerate(zones):
        sr = TS + 2 + i
        rows.append([city, off, f"=MOD($B$4+{off}+24,24)"])
    s.table(TS, 0, headers=["City", "UTC offset", "Local hour"],
            rows=rows, number_format="0.0", banded=True, align_data="center")
    for i in range(len(zones)):
        s.fmt(TS + 1 + i, 0, align="left")
    s.col_width(0, 130)
    s.note(3, 1, "Edit the reference UTC hour; local hours recompute.",
           kind="note")
    _save(wb, "Time Zones.ksheet")


def world_population():
    wb = Workbook(min_rows=30, min_cols=10)
    s = wb.add_sheet("Population")
    s.title_block("World Population",
                  "Population, share of world and density", span=7)
    data = [
        ("China", 1412, 9597), ("India", 1417, 3287),
        ("USA", 333, 9834), ("Indonesia", 276, 1905),
        ("Pakistan", 240, 882), ("Nigeria", 223, 924),
        ("Brazil", 216, 8516), ("Bangladesh", 171, 148),
        ("Russia", 144, 17098), ("Japan", 125, 378),
    ]
    TS = 4
    last = TS + 1 + len(data)
    rows = []
    for i, (c, pop, area) in enumerate(data):
        sr = TS + 2 + i
        rows.append([c, pop, area,
                     f"=B{sr}/SUM($B${TS + 2}:$B${last})*100",
                     f"=B{sr}*1000/C{sr}"])
    s.table(TS, 0, headers=["Country", "Pop (millions)", "Area (1000 km²)",
                            "% of list", "Density (/km²)"],
            rows=rows, number_format="0.0", banded=True, align_data="center")
    for i in range(len(data)):
        s.fmt(TS + 1 + i, 0, align="left")
    s.set(last + 1, 0, "Total")
    s.fmt(last + 1, 0, bold=True)
    s.formula(last + 1, 1, f"=SUM(B{TS + 2}:B{last})")
    s.fmt(last + 1, 1, bold=True, bg=PALETTE["band"], number_format="0")
    r0, r1 = TS + 1, TS + len(data)
    s.chart([Series(np.arange(len(data)),
                    np.array([d[1] for d in data], dtype=float),
                    "Population", "Bar", color=PALETTE["header"],
                    y_col=1, row_start=r0, row_end=r1)],
            at=(640, 40), size=(420, 300), title="Population (millions)",
            xlabel="Country", ylabel="millions", legend=False)
    s.col_width(0, 120)
    _save(wb, "World Population.ksheet")


def multi_sheet_demo():
    wb = Workbook(min_rows=30, min_cols=10)
    # Sheet 1: overview
    s1 = wb.add_sheet("Overview")
    s1.title_block("Multi-Sheet Demo",
                   "A workbook with three linked-theme sheets", span=6)
    s1.set(4, 0, "This workbook has three tabs:")
    s1.fmt(4, 0, bold=True)
    for i, t in enumerate(["Overview — this page",
                           "Sales — a table with a chart",
                           "Targets — goals vs actual"]):
        s1.set(5 + i, 0, f"• {t}")
    s1.note(4, 2, "Use the tabs at the bottom to switch sheets.", kind="note")
    s1.col_width(0, 260)
    # Sheet 2: sales table + chart
    s2 = wb.add_sheet("Sales")
    s2.title_block("Sales", "Quarterly units and revenue", span=5)
    TS = 4
    q = [("Q1", 120, 30), ("Q2", 150, 30), ("Q3", 175, 30), ("Q4", 210, 30)]
    rows = []
    for i, (qq, units, price) in enumerate(q):
        sr = TS + 2 + i
        rows.append([qq, units, price, f"=B{sr}*C{sr}"])
    s2.table(TS, 0, headers=["Quarter", "Units", "Price", "Revenue"],
             rows=rows, number_format="0", banded=True, align_data="center")
    r0, r1 = TS + 1, TS + len(q)
    s2.chart([Series(np.arange(len(q)),
                     np.array([u * p for _, u, p in q], dtype=float),
                     "Revenue", "Bar", color=PALETTE["header"],
                     y_col=3, row_start=r0, row_end=r1)],
             at=(460, 40), size=(400, 280), title="Revenue by Quarter",
             xlabel="Quarter", ylabel="Revenue", legend=False)
    # Sheet 3: targets
    s3 = wb.add_sheet("Targets")
    s3.title_block("Targets", "Goal vs actual with variance", span=5)
    TS = 4
    t = [("Sales", 800, 655), ("New clients", 50, 61),
         ("Churn %", 5, 4), ("NPS", 60, 57)]
    rows = []
    for i, (m, goal, actual) in enumerate(t):
        sr = TS + 2 + i
        rows.append([m, goal, actual, f"=C{sr}-B{sr}"])
    s3.table(TS, 0, headers=["Metric", "Goal", "Actual", "Variance"],
             rows=rows, number_format="0", banded=True, align_data="center")
    for i in range(len(t)):
        s3.fmt(TS + 1 + i, 0, align="left")
    _save(wb, "Multi-Sheet Demo.ksheet")


def sine_cos_plot():
    wb = Workbook(min_rows=80, min_cols=8)
    s = wb.add_sheet("Plot Data")
    s.title_block("Sine / Cos Plot Data",
                  "Smooth sin and cos over 0 to 2pi", span=5)
    TS = 4
    n = 61
    xs = np.linspace(0, 2 * np.pi, n)
    rows = []
    for i, x in enumerate(xs):
        sr = TS + 2 + i
        rows.append([round(float(x), 4), f"=SIN(A{sr})", f"=COS(A{sr})"])
    s.table(TS, 0, headers=["x (rad)", "sin x", "cos x"], rows=rows,
            number_format="0.0000", banded=True, align_data="center")
    r0, r1 = TS + 1, TS + n
    s.chart([Series(xs, np.sin(xs), "sin x", "Line", color=PALETTE["header"],
                    x_col=0, y_col=1, row_start=r0, row_end=r1),
             Series(xs, np.cos(xs), "cos x", "Line", color=PALETTE["accent"],
                    x_col=0, y_col=2, row_start=r0, row_end=r1)],
            at=(440, 40), size=(460, 320), title="sin x and cos x",
            xlabel="x (rad)", ylabel="value", legend=True)
    _save(wb, "Sine Cos Plot Data.ksheet")


def build():
    os.makedirs(OUT, exist_ok=True)
    color_palette()
    distance_matrix()
    time_zones()
    world_population()
    multi_sheet_demo()
    sine_cos_plot()
    print("Reference templates written to", OUT)


if __name__ == "__main__":
    build()
