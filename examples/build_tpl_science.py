"""Build the rich Science template set (examples/templates/Science/).

Projectile Motion, Periodic Table, Chemistry Solutions, Resistor Color
Codes, Temperature Conversion, Unit Conversions.

Run:  python examples/build_tpl_science.py
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
                   "templates", "Science")


def _save(wb, name):
    wb.save(os.path.join(OUT, name))


def projectile_motion():
    wb = Workbook(min_rows=44, min_cols=12)
    s = wb.add_sheet("Projectile")
    s.title_block("Projectile Motion",
                  "Launch speed and angle -> range, height, trajectory",
                  span=6)
    for i, (lbl, v) in enumerate([("Launch speed u (m/s)", 25.0),
                                  ("Angle θ (deg)", 40.0),
                                  ("Gravity g (m/s²)", 9.81)]):
        s.set(4 + i, 0, lbl)
        s.set(4 + i, 1, v)
        s.fmt(4 + i, 1, bg=PALETTE["warn"], align="center", number_format="0.00")
    s.box(4, 0, 6, 1, color=PALETTE["accent"], width=1.0)
    s.col_width(0, 170)
    # inputs: u=B5, theta=B6, g=B7
    res = [("vₓ = u cosθ", "=B5*COS(RADIANS(B6))"),
           ("vᵧ = u sinθ", "=B5*SIN(RADIANS(B6))"),
           ("Time of flight", "=2*B5*SIN(RADIANS(B6))/B7"),
           ("Max height", "=(B5*SIN(RADIANS(B6)))^2/(2*B7)"),
           ("Range", "=B5*B5*SIN(RADIANS(2*B6))/B7")]
    s.set(3, 3, "Results")
    s.fmt(3, 3, bold=True, font_color=PALETTE["header"])
    for i, (lbl, expr) in enumerate(res):
        s.set(4 + i, 3, lbl)
        s.formula(4 + i, 4, expr)
        s.fmt(4 + i, 4, bold=True, bg=PALETTE["band"], number_format="0.00")
    s.box(4, 3, 8, 4, color=PALETTE["header"], width=1.0)
    s.col_width(3, 140)
    # trajectory
    TS = 11
    u, th, g = 25.0, 40.0, 9.81
    T = 2 * u * np.sin(np.radians(th)) / g
    ts = np.linspace(0, T, 21)
    rows = []
    for i, t in enumerate(ts):
        sr = TS + 2 + i
        rows.append([round(float(t), 3),
                     f"=$B$5*COS(RADIANS($B$6))*A{sr}",
                     f"=$B$5*SIN(RADIANS($B$6))*A{sr}-0.5*$B$7*A{sr}*A{sr}"])
    s.set(10, 0, "Trajectory")
    s.fmt(10, 0, bold=True, font_color=PALETTE["header"])
    s.table(TS, 0, headers=["t (s)", "x (m)", "y (m)"], rows=rows,
            number_format="0.00", banded=True, align_data="center")
    r0, r1 = TS + 1, TS + len(ts)
    x = u * np.cos(np.radians(th)) * ts
    y = u * np.sin(np.radians(th)) * ts - 0.5 * g * ts ** 2
    s.chart([Series(x, y, "Trajectory", "Line+Symbol", color=PALETTE["header"],
                    marker="o", x_col=1, y_col=2, row_start=r0, row_end=r1)],
            at=(560, 40), size=(440, 300), title="Trajectory",
            xlabel="x (m)", ylabel="y (m)", legend=False)
    s.note(4, 1, "Edit u, θ, g — results and trajectory update.", kind="note")
    _save(wb, "Projectile Motion.ksheet")


_ELEMENTS = [
    (1, "H", "Hydrogen", 1.008), (2, "He", "Helium", 4.003),
    (3, "Li", "Lithium", 6.94), (4, "Be", "Beryllium", 9.012),
    (5, "B", "Boron", 10.81), (6, "C", "Carbon", 12.011),
    (7, "N", "Nitrogen", 14.007), (8, "O", "Oxygen", 15.999),
    (9, "F", "Fluorine", 18.998), (10, "Ne", "Neon", 20.180),
    (11, "Na", "Sodium", 22.990), (12, "Mg", "Magnesium", 24.305),
    (13, "Al", "Aluminium", 26.982), (14, "Si", "Silicon", 28.085),
    (15, "P", "Phosphorus", 30.974), (16, "S", "Sulfur", 32.06),
    (17, "Cl", "Chlorine", 35.45), (18, "Ar", "Argon", 39.948),
    (19, "K", "Potassium", 39.098), (20, "Ca", "Calcium", 40.078),
    (21, "Sc", "Scandium", 44.956), (22, "Ti", "Titanium", 47.867),
    (23, "V", "Vanadium", 50.942), (24, "Cr", "Chromium", 51.996),
    (25, "Mn", "Manganese", 54.938), (26, "Fe", "Iron", 55.845),
    (27, "Co", "Cobalt", 58.933), (28, "Ni", "Nickel", 58.693),
    (29, "Cu", "Copper", 63.546), (30, "Zn", "Zinc", 65.38),
    (31, "Ga", "Gallium", 69.723), (32, "Ge", "Germanium", 72.630),
    (33, "As", "Arsenic", 74.922), (34, "Se", "Selenium", 78.971),
    (35, "Br", "Bromine", 79.904), (36, "Kr", "Krypton", 83.798),
]


def periodic_table():
    wb = Workbook(min_rows=46, min_cols=10)
    s = wb.add_sheet("Elements")
    s.title_block("Periodic Table (Z = 1-36)",
                  "Atomic number, symbol, name and atomic mass", span=5)
    TS = 4
    rows = [[z, sym, nm, mass] for (z, sym, nm, mass) in _ELEMENTS]
    s.table(TS, 0, headers=["Z", "Symbol", "Name", "Atomic Mass"],
            rows=rows, number_format="0.000", banded=True, align_data="center")
    for i in range(len(_ELEMENTS)):
        s.fmt(TS + 1 + i, 2, align="left")
    r0, r1 = TS + 1, TS + len(_ELEMENTS)
    s.chart([Series(np.array([e[0] for e in _ELEMENTS], dtype=float),
                    np.array([e[3] for e in _ELEMENTS], dtype=float),
                    "Atomic mass", "Line+Symbol", color=PALETTE["header"],
                    marker="o", x_col=0, y_col=3, row_start=r0, row_end=r1)],
            at=(520, 40), size=(440, 300), title="Atomic Mass vs Z",
            xlabel="Atomic number Z", ylabel="Atomic mass", legend=False)
    s.col_width(2, 110)
    _save(wb, "Periodic Table.ksheet")


def chemistry_solutions():
    wb = Workbook(min_rows=30, min_cols=10)
    s = wb.add_sheet("Solutions")
    s.title_block("Chemistry Solutions",
                  "Molarity and dilution calculators", span=6)
    # Molarity
    s.set(3, 0, "Make a solution")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])
    for i, (lbl, v) in enumerate([("Mass of solute (g)", 5.85),
                                  ("Molar mass Mr (g/mol)", 58.44),
                                  ("Volume (L)", 0.5)]):
        s.set(4 + i, 0, lbl)
        s.set(4 + i, 1, v)
        s.fmt(4 + i, 1, bg=PALETTE["warn"], align="center", number_format="0.000")
    s.box(4, 0, 6, 1, color=PALETTE["accent"], width=1.0)
    s.set(7, 0, "Moles (mol)")
    s.formula(7, 1, "=B5/B6")
    s.set(8, 0, "Concentration (mol/L)")
    s.formula(8, 1, "=B5/B6/B7")
    for r in (7, 8):
        s.fmt(r, 1, bold=True, bg=PALETTE["band"], number_format="0.0000")
    s.col_width(0, 180)
    # Dilution C1 V1 = C2 V2
    s.set(3, 4, "Dilution  C₁V₁ = C₂V₂")
    s.fmt(3, 4, bold=True, font_color=PALETTE["accent"])
    for i, (lbl, v) in enumerate([("Stock conc C₁ (mol/L)", 2.0),
                                  ("Final conc C₂ (mol/L)", 0.25),
                                  ("Final volume V₂ (L)", 1.0)]):
        s.set(4 + i, 4, lbl)
        s.set(4 + i, 5, v)
        s.fmt(4 + i, 5, bg=PALETTE["warn"], align="center", number_format="0.000")
    s.box(4, 4, 6, 5, color=PALETTE["accent"], width=1.0)
    s.set(7, 4, "Stock volume V₁ (L)")
    s.formula(7, 5, "=F6*F7/F5")
    s.set(8, 4, "Add solvent (L)")
    s.formula(8, 5, "=F7-F6*F7/F5")
    for r in (7, 8):
        s.fmt(r, 5, bold=True, bg=PALETTE["band"], number_format="0.0000")
    s.col_width(4, 180)
    s.note(4, 1, "NaCl example: 5.85 g in 0.5 L -> 0.2 M.", kind="note")
    _save(wb, "Chemistry Solutions.ksheet")


def resistor_color():
    wb = Workbook(min_rows=30, min_cols=10)
    s = wb.add_sheet("Resistors")
    s.title_block("Resistor Color Codes",
                  "Band reference and a 3-band value calculator", span=6)
    bands = [
        ("Black", 0, "1", ""), ("Brown", 1, "10", "±1%"),
        ("Red", 2, "100", "±2%"), ("Orange", 3, "1k", ""),
        ("Yellow", 4, "10k", ""), ("Green", 5, "100k", "±0.5%"),
        ("Blue", 6, "1M", "±0.25%"), ("Violet", 7, "10M", "±0.1%"),
        ("Grey", 8, "-", "±0.05%"), ("White", 9, "-", ""),
        ("Gold", -1, "0.1", "±5%"), ("Silver", -2, "0.01", "±10%"),
    ]
    TS = 4
    rows = [[c, (d if d >= 0 else ""), mult, tol] for (c, d, mult, tol) in bands]
    s.table(TS, 0, headers=["Color", "Digit", "Multiplier", "Tolerance"],
            rows=rows, number_format="0", banded=True, align_data="center")
    for i in range(len(bands)):
        s.fmt(TS + 1 + i, 0, align="left")
    # Calculator
    s.set(3, 6, "Resistance calculator")
    s.fmt(3, 6, bold=True, font_color=PALETTE["accent"])
    for i, (lbl, v) in enumerate([("Band 1 digit", 2), ("Band 2 digit", 7),
                                  ("Multiplier (power of 10)", 3)]):
        s.set(4 + i, 6, lbl)
        s.set(4 + i, 7, v)
        s.fmt(4 + i, 7, bg=PALETTE["warn"], align="center", number_format="0")
    s.box(4, 6, 6, 7, color=PALETTE["accent"], width=1.0)
    s.set(7, 6, "Resistance (Ω)")
    s.formula(7, 7, "=(H5*10+H6)*POWER(10,H7)")
    s.fmt(7, 7, bold=True, bg=PALETTE["good"], number_format="0")
    s.col_width(6, 170)
    s.note(4, 7, "Example: 2,7,×10³ = 27 kΩ.", kind="note")
    _save(wb, "Resistor Color Codes.ksheet")


def temperature_conversion():
    wb = Workbook(min_rows=40, min_cols=10)
    s = wb.add_sheet("Temperature")
    s.title_block("Temperature Conversion",
                  "Celsius / Fahrenheit / Kelvin", span=6)
    s.set(4, 0, "Celsius input")
    s.set(4, 1, 25.0)
    s.fmt(4, 1, bg=PALETTE["warn"], align="center", number_format="0.0")
    s.set(5, 0, "Fahrenheit")
    s.formula(5, 1, "=B5*9/5+32")
    s.set(6, 0, "Kelvin")
    s.formula(6, 1, "=B5+273.15")
    for r in (5, 6):
        s.fmt(r, 1, bold=True, bg=PALETTE["band"], number_format="0.00")
    s.box(4, 0, 6, 1, color=PALETTE["accent"], width=1.0)
    s.col_width(0, 140)
    # Table
    TS = 9
    cs = list(range(-40, 121, 10))
    rows = []
    for i, c in enumerate(cs):
        sr = TS + 2 + i
        rows.append([c, f"=A{sr}*9/5+32", f"=A{sr}+273.15"])
    s.set(8, 0, "Conversion table")
    s.fmt(8, 0, bold=True, font_color=PALETTE["header"])
    s.table(TS, 0, headers=["°C", "°F", "K"], rows=rows,
            number_format="0.0", banded=True, align_data="center")
    r0, r1 = TS + 1, TS + len(cs)
    ca = np.array(cs, dtype=float)
    s.chart([Series(ca, ca * 9 / 5 + 32, "°F", "Line", color=PALETTE["accent"],
                    x_col=0, y_col=1, row_start=r0, row_end=r1),
             Series(ca, ca + 273.15, "K", "Line", color=PALETTE["header"],
                    x_col=0, y_col=2, row_start=r0, row_end=r1)],
            at=(440, 40), size=(440, 300), title="°F and K vs °C",
            xlabel="°C", ylabel="°F / K", legend=True)
    s.note(4, 1, "Edit the Celsius input to convert.", kind="note")
    _save(wb, "Temperature Conversion.ksheet")


def unit_conversions():
    wb = Workbook(min_rows=44, min_cols=8)
    s = wb.add_sheet("Units")
    s.title_block("Unit Conversions",
                  "Type a base value; conversions follow", span=5)

    def section(row, title, base_label, base_val, items):
        s.set(row, 0, title)
        s.fmt(row, 0, bold=True, font_color=PALETTE["accent"], font_size=12)
        s.set(row + 1, 0, base_label)
        s.set(row + 1, 1, base_val)
        s.fmt(row + 1, 1, bg=PALETTE["warn"], align="right",
              number_format="0.0000")
        bcell = f"B{row + 2}"      # 1-based row of the base value
        for k, (lbl, factor) in enumerate(items):
            rr = row + 2 + k
            s.set(rr, 0, lbl)
            s.formula(rr, 1, f"={bcell}*{factor}")
            s.fmt(rr, 1, align="right", number_format="0.0000",
                  bg=(PALETTE["band_alt"] if k % 2 else None))
        s.box(row + 1, 0, row + 1 + len(items), 1,
              color=PALETTE["header"], width=1.0)

    section(3, "Length", "metres", 1.0,
            [("kilometres", 0.001), ("miles", 0.000621371),
             ("feet", 3.28084), ("inches", 39.3701), ("yards", 1.09361)])
    section(11, "Mass", "kilograms", 1.0,
            [("grams", 1000), ("pounds", 2.20462), ("ounces", 35.274),
             ("stones", 0.157473)])
    section(18, "Speed", "metres/second", 1.0,
            [("km/h", 3.6), ("mph", 2.23694), ("knots", 1.94384)])
    s.col_width(0, 150)
    s.note(4, 1, "Edit the highlighted base value in each section.",
           kind="note")
    _save(wb, "Unit Conversions.ksheet")


def build():
    os.makedirs(OUT, exist_ok=True)
    projectile_motion()
    periodic_table()
    chemistry_solutions()
    resistor_color()
    temperature_conversion()
    unit_conversions()
    print("Science templates written to", OUT)


if __name__ == "__main__":
    build()
