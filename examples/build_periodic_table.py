"""Build a rich Periodic Table template (examples/templates/Science/).

Generates examples/templates/Science/Periodic Table.ksheet — a full
IUPAC 18-column layout with all 118 elements, colour-coded by category,
hover notes on every cell, and a colour legend.

Run:  python examples/build_periodic_table.py
Copyright (C) 2026 Gwilherm Kerherve - GPL-3.0-or-later.
"""

import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from ksheet_author import Workbook, PALETTE  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "templates", "Science")

# ── Element categories ────────────────────────────────────────────────

CATEGORIES = {
    "Alkali metal":           "#FFCCCC",   # warm pink-red
    "Alkaline earth metal":   "#FFE0B2",   # warm orange
    "Transition metal":       "#FFF9C4",   # pale yellow
    "Post-transition metal":  "#C8E6C9",   # pale green
    "Metalloid":              "#B2EBF2",   # pale cyan
    "Reactive nonmetal":      "#E1F5FE",   # pale sky blue
    "Noble gas":              "#EDE7F6",   # pale lavender
    "Lanthanide":             "#FCE4EC",   # pale rose
    "Actinide":               "#F3E5F5",   # pale purple
    "Unknown":                "#ECEFF1",   # pale grey-blue
}

# Text colours (all dark for readability on pastel backgrounds)
CAT_TEXT = {cat: "#1a1a1a" for cat in CATEGORIES}

# ── Full element data ─────────────────────────────────────────────────
# Fields: (Z, symbol, name, mass, category, electron_config, state, group, period)
# Electron configs use noble-gas notation where applicable.
# State at STP: Solid / Liquid / Gas

ELEMENTS = [
    # Period 1
    (1,  "H",  "Hydrogen",      1.008,   "Reactive nonmetal",   "1s1",                          "Gas",    1,  1),
    (2,  "He", "Helium",        4.003,   "Noble gas",           "1s2",                          "Gas",    18, 1),
    # Period 2
    (3,  "Li", "Lithium",       6.941,   "Alkali metal",        "[He] 2s1",                     "Solid",  1,  2),
    (4,  "Be", "Beryllium",     9.012,   "Alkaline earth metal","[He] 2s2",                     "Solid",  2,  2),
    (5,  "B",  "Boron",        10.811,   "Metalloid",           "[He] 2s2 2p1",                 "Solid",  13, 2),
    (6,  "C",  "Carbon",       12.011,   "Reactive nonmetal",   "[He] 2s2 2p2",                 "Solid",  14, 2),
    (7,  "N",  "Nitrogen",     14.007,   "Reactive nonmetal",   "[He] 2s2 2p3",                 "Gas",    15, 2),
    (8,  "O",  "Oxygen",       15.999,   "Reactive nonmetal",   "[He] 2s2 2p4",                 "Gas",    16, 2),
    (9,  "F",  "Fluorine",     18.998,   "Reactive nonmetal",   "[He] 2s2 2p5",                 "Gas",    17, 2),
    (10, "Ne", "Neon",         20.180,   "Noble gas",           "[He] 2s2 2p6",                 "Gas",    18, 2),
    # Period 3
    (11, "Na", "Sodium",       22.990,   "Alkali metal",        "[Ne] 3s1",                     "Solid",  1,  3),
    (12, "Mg", "Magnesium",    24.305,   "Alkaline earth metal","[Ne] 3s2",                     "Solid",  2,  3),
    (13, "Al", "Aluminium",    26.982,   "Post-transition metal","[Ne] 3s2 3p1",                "Solid",  13, 3),
    (14, "Si", "Silicon",      28.086,   "Metalloid",           "[Ne] 3s2 3p2",                 "Solid",  14, 3),
    (15, "P",  "Phosphorus",   30.974,   "Reactive nonmetal",   "[Ne] 3s2 3p3",                 "Solid",  15, 3),
    (16, "S",  "Sulfur",       32.060,   "Reactive nonmetal",   "[Ne] 3s2 3p4",                 "Solid",  16, 3),
    (17, "Cl", "Chlorine",     35.450,   "Reactive nonmetal",   "[Ne] 3s2 3p5",                 "Gas",    17, 3),
    (18, "Ar", "Argon",        39.948,   "Noble gas",           "[Ne] 3s2 3p6",                 "Gas",    18, 3),
    # Period 4
    (19, "K",  "Potassium",    39.098,   "Alkali metal",        "[Ar] 4s1",                     "Solid",  1,  4),
    (20, "Ca", "Calcium",      40.078,   "Alkaline earth metal","[Ar] 4s2",                     "Solid",  2,  4),
    (21, "Sc", "Scandium",     44.956,   "Transition metal",    "[Ar] 3d1 4s2",                 "Solid",  3,  4),
    (22, "Ti", "Titanium",     47.867,   "Transition metal",    "[Ar] 3d2 4s2",                 "Solid",  4,  4),
    (23, "V",  "Vanadium",     50.942,   "Transition metal",    "[Ar] 3d3 4s2",                 "Solid",  5,  4),
    (24, "Cr", "Chromium",     51.996,   "Transition metal",    "[Ar] 3d5 4s1",                 "Solid",  6,  4),
    (25, "Mn", "Manganese",    54.938,   "Transition metal",    "[Ar] 3d5 4s2",                 "Solid",  7,  4),
    (26, "Fe", "Iron",         55.845,   "Transition metal",    "[Ar] 3d6 4s2",                 "Solid",  8,  4),
    (27, "Co", "Cobalt",       58.933,   "Transition metal",    "[Ar] 3d7 4s2",                 "Solid",  9,  4),
    (28, "Ni", "Nickel",       58.693,   "Transition metal",    "[Ar] 3d8 4s2",                 "Solid",  10, 4),
    (29, "Cu", "Copper",       63.546,   "Transition metal",    "[Ar] 3d10 4s1",                "Solid",  11, 4),
    (30, "Zn", "Zinc",         65.380,   "Transition metal",    "[Ar] 3d10 4s2",                "Solid",  12, 4),
    (31, "Ga", "Gallium",      69.723,   "Post-transition metal","[Ar] 3d10 4s2 4p1",           "Solid",  13, 4),
    (32, "Ge", "Germanium",    72.630,   "Metalloid",           "[Ar] 3d10 4s2 4p2",            "Solid",  14, 4),
    (33, "As", "Arsenic",      74.922,   "Metalloid",           "[Ar] 3d10 4s2 4p3",            "Solid",  15, 4),
    (34, "Se", "Selenium",     78.971,   "Reactive nonmetal",   "[Ar] 3d10 4s2 4p4",            "Solid",  16, 4),
    (35, "Br", "Bromine",      79.904,   "Reactive nonmetal",   "[Ar] 3d10 4s2 4p5",            "Liquid", 17, 4),
    (36, "Kr", "Krypton",      83.798,   "Noble gas",           "[Ar] 3d10 4s2 4p6",            "Gas",    18, 4),
    # Period 5
    (37, "Rb", "Rubidium",     85.468,   "Alkali metal",        "[Kr] 5s1",                     "Solid",  1,  5),
    (38, "Sr", "Strontium",    87.620,   "Alkaline earth metal","[Kr] 5s2",                     "Solid",  2,  5),
    (39, "Y",  "Yttrium",      88.906,   "Transition metal",    "[Kr] 4d1 5s2",                 "Solid",  3,  5),
    (40, "Zr", "Zirconium",    91.224,   "Transition metal",    "[Kr] 4d2 5s2",                 "Solid",  4,  5),
    (41, "Nb", "Niobium",      92.906,   "Transition metal",    "[Kr] 4d4 5s1",                 "Solid",  5,  5),
    (42, "Mo", "Molybdenum",   95.950,   "Transition metal",    "[Kr] 4d5 5s1",                 "Solid",  6,  5),
    (43, "Tc", "Technetium",   98.000,   "Transition metal",    "[Kr] 4d5 5s2",                 "Solid",  7,  5),
    (44, "Ru", "Ruthenium",   101.070,   "Transition metal",    "[Kr] 4d7 5s1",                 "Solid",  8,  5),
    (45, "Rh", "Rhodium",     102.906,   "Transition metal",    "[Kr] 4d8 5s1",                 "Solid",  9,  5),
    (46, "Pd", "Palladium",   106.420,   "Transition metal",    "[Kr] 4d10",                    "Solid",  10, 5),
    (47, "Ag", "Silver",      107.868,   "Transition metal",    "[Kr] 4d10 5s1",                "Solid",  11, 5),
    (48, "Cd", "Cadmium",     112.411,   "Transition metal",    "[Kr] 4d10 5s2",                "Solid",  12, 5),
    (49, "In", "Indium",      114.818,   "Post-transition metal","[Kr] 4d10 5s2 5p1",           "Solid",  13, 5),
    (50, "Sn", "Tin",         118.710,   "Post-transition metal","[Kr] 4d10 5s2 5p2",           "Solid",  14, 5),
    (51, "Sb", "Antimony",    121.760,   "Metalloid",           "[Kr] 4d10 5s2 5p3",            "Solid",  15, 5),
    (52, "Te", "Tellurium",   127.600,   "Metalloid",           "[Kr] 4d10 5s2 5p4",            "Solid",  16, 5),
    (53, "I",  "Iodine",      126.904,   "Reactive nonmetal",   "[Kr] 4d10 5s2 5p5",            "Solid",  17, 5),
    (54, "Xe", "Xenon",       131.293,   "Noble gas",           "[Kr] 4d10 5s2 5p6",            "Gas",    18, 5),
    # Period 6
    (55, "Cs", "Caesium",     132.905,   "Alkali metal",        "[Xe] 6s1",                     "Solid",  1,  6),
    (56, "Ba", "Barium",      137.327,   "Alkaline earth metal","[Xe] 6s2",                     "Solid",  2,  6),
    # 57-71 = lanthanides; placeholder in group 3
    (57, "La", "Lanthanum",   138.905,   "Lanthanide",          "[Xe] 5d1 6s2",                 "Solid",  3,  6),
    (58, "Ce", "Cerium",      140.116,   "Lanthanide",          "[Xe] 4f1 5d1 6s2",             "Solid",  4,  6),
    (59, "Pr", "Praseodymium",140.908,   "Lanthanide",          "[Xe] 4f3 6s2",                 "Solid",  5,  6),
    (60, "Nd", "Neodymium",   144.242,   "Lanthanide",          "[Xe] 4f4 6s2",                 "Solid",  6,  6),
    (61, "Pm", "Promethium",  145.000,   "Lanthanide",          "[Xe] 4f5 6s2",                 "Solid",  7,  6),
    (62, "Sm", "Samarium",    150.360,   "Lanthanide",          "[Xe] 4f6 6s2",                 "Solid",  8,  6),
    (63, "Eu", "Europium",    151.964,   "Lanthanide",          "[Xe] 4f7 6s2",                 "Solid",  9,  6),
    (64, "Gd", "Gadolinium",  157.250,   "Lanthanide",          "[Xe] 4f7 5d1 6s2",             "Solid",  10, 6),
    (65, "Tb", "Terbium",     158.925,   "Lanthanide",          "[Xe] 4f9 6s2",                 "Solid",  11, 6),
    (66, "Dy", "Dysprosium",  162.500,   "Lanthanide",          "[Xe] 4f10 6s2",                "Solid",  12, 6),
    (67, "Ho", "Holmium",     164.930,   "Lanthanide",          "[Xe] 4f11 6s2",                "Solid",  13, 6),
    (68, "Er", "Erbium",      167.259,   "Lanthanide",          "[Xe] 4f12 6s2",                "Solid",  14, 6),
    (69, "Tm", "Thulium",     168.934,   "Lanthanide",          "[Xe] 4f13 6s2",                "Solid",  15, 6),
    (70, "Yb", "Ytterbium",   173.045,   "Lanthanide",          "[Xe] 4f14 6s2",                "Solid",  16, 6),
    (71, "Lu", "Lutetium",    174.967,   "Lanthanide",          "[Xe] 4f14 5d1 6s2",            "Solid",  17, 6),
    (72, "Hf", "Hafnium",     178.490,   "Transition metal",    "[Xe] 4f14 5d2 6s2",            "Solid",  4,  6),
    (73, "Ta", "Tantalum",    180.948,   "Transition metal",    "[Xe] 4f14 5d3 6s2",            "Solid",  5,  6),
    (74, "W",  "Tungsten",    183.840,   "Transition metal",    "[Xe] 4f14 5d4 6s2",            "Solid",  6,  6),
    (75, "Re", "Rhenium",     186.207,   "Transition metal",    "[Xe] 4f14 5d5 6s2",            "Solid",  7,  6),
    (76, "Os", "Osmium",      190.230,   "Transition metal",    "[Xe] 4f14 5d6 6s2",            "Solid",  8,  6),
    (77, "Ir", "Iridium",     192.217,   "Transition metal",    "[Xe] 4f14 5d7 6s2",            "Solid",  9,  6),
    (78, "Pt", "Platinum",    195.084,   "Transition metal",    "[Xe] 4f14 5d9 6s1",            "Solid",  10, 6),
    (79, "Au", "Gold",        196.967,   "Transition metal",    "[Xe] 4f14 5d10 6s1",           "Solid",  11, 6),
    (80, "Hg", "Mercury",     200.592,   "Transition metal",    "[Xe] 4f14 5d10 6s2",           "Liquid", 12, 6),
    (81, "Tl", "Thallium",    204.383,   "Post-transition metal","[Xe] 4f14 5d10 6s2 6p1",      "Solid",  13, 6),
    (82, "Pb", "Lead",        207.200,   "Post-transition metal","[Xe] 4f14 5d10 6s2 6p2",      "Solid",  14, 6),
    (83, "Bi", "Bismuth",     208.980,   "Post-transition metal","[Xe] 4f14 5d10 6s2 6p3",      "Solid",  15, 6),
    (84, "Po", "Polonium",    209.000,   "Post-transition metal","[Xe] 4f14 5d10 6s2 6p4",      "Solid",  16, 6),
    (85, "At", "Astatine",    210.000,   "Metalloid",           "[Xe] 4f14 5d10 6s2 6p5",       "Solid",  17, 6),
    (86, "Rn", "Radon",       222.000,   "Noble gas",           "[Xe] 4f14 5d10 6s2 6p6",       "Gas",    18, 6),
    # Period 7
    (87, "Fr", "Francium",    223.000,   "Alkali metal",        "[Rn] 7s1",                     "Solid",  1,  7),
    (88, "Ra", "Radium",      226.000,   "Alkaline earth metal","[Rn] 7s2",                     "Solid",  2,  7),
    # 89-103 = actinides; placeholder in group 3
    (89, "Ac", "Actinium",    227.000,   "Actinide",            "[Rn] 6d1 7s2",                 "Solid",  3,  7),
    (90, "Th", "Thorium",     232.038,   "Actinide",            "[Rn] 6d2 7s2",                 "Solid",  4,  7),
    (91, "Pa", "Protactinium",231.036,   "Actinide",            "[Rn] 5f2 6d1 7s2",             "Solid",  5,  7),
    (92, "U",  "Uranium",     238.029,   "Actinide",            "[Rn] 5f3 6d1 7s2",             "Solid",  6,  7),
    (93, "Np", "Neptunium",   237.000,   "Actinide",            "[Rn] 5f4 6d1 7s2",             "Solid",  7,  7),
    (94, "Pu", "Plutonium",   244.000,   "Actinide",            "[Rn] 5f6 7s2",                 "Solid",  8,  7),
    (95, "Am", "Americium",   243.000,   "Actinide",            "[Rn] 5f7 7s2",                 "Solid",  9,  7),
    (96, "Cm", "Curium",      247.000,   "Actinide",            "[Rn] 5f7 6d1 7s2",             "Solid",  10, 7),
    (97, "Bk", "Berkelium",   247.000,   "Actinide",            "[Rn] 5f9 7s2",                 "Solid",  11, 7),
    (98, "Cf", "Californium", 251.000,   "Actinide",            "[Rn] 5f10 7s2",                "Solid",  12, 7),
    (99, "Es", "Einsteinium", 252.000,   "Actinide",            "[Rn] 5f11 7s2",                "Solid",  13, 7),
    (100,"Fm", "Fermium",     257.000,   "Actinide",            "[Rn] 5f12 7s2",                "Solid",  14, 7),
    (101,"Md", "Mendelevium", 258.000,   "Actinide",            "[Rn] 5f13 7s2",                "Solid",  15, 7),
    (102,"No", "Nobelium",    259.000,   "Actinide",            "[Rn] 5f14 7s2",                "Solid",  16, 7),
    (103,"Lr", "Lawrencium",  266.000,   "Actinide",            "[Rn] 5f14 7s2 7p1",            "Solid",  17, 7),
    (104,"Rf", "Rutherfordium",267.000,  "Transition metal",    "[Rn] 5f14 6d2 7s2",            "Solid",  4,  7),
    (105,"Db", "Dubnium",     268.000,   "Transition metal",    "[Rn] 5f14 6d3 7s2",            "Solid",  5,  7),
    (106,"Sg", "Seaborgium",  271.000,   "Transition metal",    "[Rn] 5f14 6d4 7s2",            "Solid",  6,  7),
    (107,"Bh", "Bohrium",     270.000,   "Transition metal",    "[Rn] 5f14 6d5 7s2",            "Solid",  7,  7),
    (108,"Hs", "Hassium",     277.000,   "Transition metal",    "[Rn] 5f14 6d6 7s2",            "Solid",  8,  7),
    (109,"Mt", "Meitnerium",  278.000,   "Unknown",             "[Rn] 5f14 6d7 7s2",            "Solid",  9,  7),
    (110,"Ds", "Darmstadtium",281.000,   "Unknown",             "[Rn] 5f14 6d8 7s2",            "Solid",  10, 7),
    (111,"Rg", "Roentgenium", 282.000,   "Unknown",             "[Rn] 5f14 6d9 7s2",            "Solid",  11, 7),
    (112,"Cn", "Copernicium", 285.000,   "Transition metal",    "[Rn] 5f14 6d10 7s2",           "Gas",    12, 7),
    (113,"Nh", "Nihonium",    286.000,   "Post-transition metal","[Rn] 5f14 6d10 7s2 7p1",      "Solid",  13, 7),
    (114,"Fl", "Flerovium",   289.000,   "Post-transition metal","[Rn] 5f14 6d10 7s2 7p2",      "Solid",  14, 7),
    (115,"Mc", "Moscovium",   290.000,   "Post-transition metal","[Rn] 5f14 6d10 7s2 7p3",      "Solid",  15, 7),
    (116,"Lv", "Livermorium", 293.000,   "Post-transition metal","[Rn] 5f14 6d10 7s2 7p4",      "Solid",  16, 7),
    (117,"Ts", "Tennessine",  294.000,   "Metalloid",           "[Rn] 5f14 6d10 7s2 7p5",       "Solid",  17, 7),
    (118,"Og", "Oganesson",   294.000,   "Noble gas",           "[Rn] 5f14 6d10 7s2 7p6",       "Gas",    18, 7),
]

# Build a lookup dictionary by atomic number
_ELEM_BY_Z = {e[0]: e for e in ELEMENTS}

# ── IUPAC grid positions ──────────────────────────────────────────────
# Row offset = 2 (title rows) + 1 (blank) = row 3 is period-1 row (0-based)
# Col = group - 1  (0-based)
# Lanthanides (Z=57-71) and actinides (Z=89-103) get placed in separate rows.

_TITLE_ROWS = 2          # rows 0-1 = title block
_PERIOD_ROW_START = 3    # 0-based row for period 1

# Elements that go in main grid: all except lanthanides 58-71 and actinides 90-103
# La(57) stays in period 6 group 3 — but we replace it with "57-71" placeholder
# Ac(89) stays in period 7 group 3 — but we replace it with "89-103" placeholder
# Actually: for the 2-row f-block scheme, remove La and Ac from the main grid too,
# and place 57-71 in lanthanide row, 89-103 in actinide row.

# Main grid elements: Z not in 57-71, not in 89-103
_LANTHANIDE_Z = set(range(57, 72))   # 57-71
_ACTINIDE_Z   = set(range(89, 104))  # 89-103

# Lanthanide row (below main grid + 2-row gap):
#   row = _PERIOD_ROW_START + 7 + 2   (7 periods + 1 spacer + 1 label row)
# Actinide row: lanthanide row + 1

_LAN_ROW_OFFSET = _PERIOD_ROW_START + 7 + 2   # 0-based row for lanthanides
_ACT_ROW_OFFSET = _LAN_ROW_OFFSET + 1          # 0-based row for actinides

# Lanthanide columns: La is group 3 (col 2, 0-based), spans cols 2-16
# We align them starting at col 2 matching the main-grid group-3 position
_LAN_COL_START = 2   # 0-based column for Z=57 (La)
_ACT_COL_START = 2   # 0-based column for Z=89 (Ac)

# Legend rows start after actinides + 2
_LEGEND_ROW = _ACT_ROW_OFFSET + 3


def _make_note(z, sym, name, mass, cat, econfig, state, grp, per):
    """Build the hover-note text for one element."""
    return (
        f"{name} ({sym})\n"
        f"Atomic number: {z}\n"
        f"Atomic mass: {mass:.3f}\n"
        f"Category: {cat}\n"
        f"Electron config: {econfig}\n"
        f"State (STP): {state}\n"
        f"Group {grp} · Period {per}"
    )


def periodic_table():
    # We need 18 columns for groups + some extra. Use min_cols=19
    # Rows: 2 title + 1 blank + 7 periods + 2 gap + 2 f-block + 2 gap + legend rows
    total_rows = _LEGEND_ROW + len(CATEGORIES) + 4
    wb = Workbook(min_rows=total_rows, min_cols=19)
    s = wb.add_sheet("Periodic Table")

    # ── Title ─────────────────────────────────────────────────────────
    s.set(0, 0, "Periodic Table of the Elements")
    s.fmt(0, 0, bold=True, font_size=16, font_color="#1a237e", align="center")
    s.merge(0, 0, 1, 19)

    s.set(1, 0, "Hover over any element cell to see its properties · "
               "118 elements · IUPAC layout")
    s.fmt(1, 0, italic=True, font_color="#555555", align="center", font_size=9)
    s.merge(1, 0, 1, 19)

    # ── Column widths: all 18 group columns narrow and equal ──────────
    for c in range(18):
        s.col_width(c, 46)

    # ── Place each element in the main grid ──────────────────────────
    for elem in ELEMENTS:
        z, sym, name, mass, cat, econfig, state, grp, per = elem

        # Determine grid position
        is_lan = z in _LANTHANIDE_Z
        is_act = z in _ACTINIDE_Z

        if is_lan:
            row = _LAN_ROW_OFFSET
            col = _LAN_COL_START + (z - 57)
        elif is_act:
            row = _ACT_ROW_OFFSET
            col = _ACT_COL_START + (z - 89)
        else:
            row = _PERIOD_ROW_START + (per - 1)
            col = grp - 1   # 0-based

        # Cell text: atomic number on first line, symbol on second
        # We write symbol as value and put atomic number as a small prefix
        cell_text = f"{z}\n{sym}"
        s.set(row, col, cell_text)

        # Formatting
        bg = CATEGORIES[cat]
        s.fmt(row, col,
              bold=True,
              font_size=8,
              bg=bg,
              font_color=CAT_TEXT[cat],
              align="center",
              wrap=True)

        # Hover note with full properties
        note_text = _make_note(z, sym, name, mass, cat, econfig, state, grp, per)
        s.note(row, col, note_text, kind="note")

    # ── Placeholders for lanthanides/actinides in main grid ──────────
    # Period 6, group 3 (row=_PERIOD_ROW_START+5, col=2)
    lan_ph_row = _PERIOD_ROW_START + 5
    act_ph_row = _PERIOD_ROW_START + 6

    s.set(lan_ph_row, 2, "57-71")
    s.fmt(lan_ph_row, 2,
          bold=True, font_size=7,
          bg=CATEGORIES["Lanthanide"],
          font_color="#880e4f",
          align="center")
    s.note(lan_ph_row, 2,
           "Lanthanides (Z = 57-71)\nLa through Lu\n"
           "See the row below the main table for details.",
           kind="note")

    s.set(act_ph_row, 2, "89-103")
    s.fmt(act_ph_row, 2,
          bold=True, font_size=7,
          bg=CATEGORIES["Actinide"],
          font_color="#4a148c",
          align="center")
    s.note(act_ph_row, 2,
           "Actinides (Z = 89-103)\nAc through Lr\n"
           "See the row below the main table for details.",
           kind="note")

    # ── Period and group labels ───────────────────────────────────────
    # Group numbers across the top (row 2, cols 0-17)
    for g in range(1, 19):
        s.set(_PERIOD_ROW_START - 1, g - 1, str(g))
        s.fmt(_PERIOD_ROW_START - 1, g - 1,
              bold=True, font_size=7, font_color="#455a64", align="center")

    # Period numbers down the left (col -1 is outside grid, so use col 0 area)
    # We can't put them before col 0, so skip—labels are implicit from layout.

    # ── Thin borders around every occupied cell ───────────────────────
    # Apply a thin grey box to each element cell
    border_color = "#9e9e9e"
    for elem in ELEMENTS:
        z, sym, name, mass, cat, econfig, state, grp, per = elem
        is_lan = z in _LANTHANIDE_Z
        is_act = z in _ACTINIDE_Z
        if is_lan:
            row = _LAN_ROW_OFFSET
            col = _LAN_COL_START + (z - 57)
        elif is_act:
            row = _ACT_ROW_OFFSET
            col = _ACT_COL_START + (z - 89)
        else:
            row = _PERIOD_ROW_START + (per - 1)
            col = grp - 1
        s.box(row, col, row, col, color=border_color, width=0.5, style="solid")

    # Also border the placeholders
    s.box(lan_ph_row, 2, lan_ph_row, 2, color=border_color, width=0.5)
    s.box(act_ph_row, 2, act_ph_row, 2, color=border_color, width=0.5)

    # ── Lanthanide / Actinide row label ───────────────────────────────
    # Label in col 0-1 of those rows
    s.set(_LAN_ROW_OFFSET, 0, "Lanthanides")
    s.fmt(_LAN_ROW_OFFSET, 0, bold=True, font_size=7,
          font_color="#880e4f", align="right")
    s.merge(_LAN_ROW_OFFSET, 0, 1, 2)

    s.set(_ACT_ROW_OFFSET, 0, "Actinides")
    s.fmt(_ACT_ROW_OFFSET, 0, bold=True, font_size=7,
          font_color="#4a148c", align="right")
    s.merge(_ACT_ROW_OFFSET, 0, 1, 2)

    # Connector line label between main grid and f-block
    connector_row = _PERIOD_ROW_START + 7
    s.set(connector_row, 2, "Lanthanides (57-71) and Actinides (89-103) below")
    s.fmt(connector_row, 2, italic=True, font_size=7,
          font_color="#78909c", align="left")
    s.merge(connector_row, 2, 1, 14)

    # ── Colour legend ─────────────────────────────────────────────────
    s.set(_LEGEND_ROW - 1, 0, "Category legend")
    s.fmt(_LEGEND_ROW - 1, 0, bold=True, font_size=9,
          font_color="#1a237e", align="left")
    s.merge(_LEGEND_ROW - 1, 0, 1, 4)

    legend_order = [
        "Alkali metal", "Alkaline earth metal", "Transition metal",
        "Post-transition metal", "Metalloid", "Reactive nonmetal",
        "Noble gas", "Lanthanide", "Actinide", "Unknown",
    ]

    for i, cat in enumerate(legend_order):
        r = _LEGEND_ROW + i
        # Colour swatch
        s.set(r, 0, "")
        s.fmt(r, 0, bg=CATEGORIES[cat], align="center")
        s.box(r, 0, r, 0, color="#9e9e9e", width=0.5)
        # Label
        s.set(r, 1, cat)
        s.fmt(r, 1, font_size=8, font_color="#212121", align="left")

    s.merge(_LEGEND_ROW - 1, 0, 1, 2)

    # ── Save ──────────────────────────────────────────────────────────
    path = os.path.join(OUT, "Periodic Table.ksheet")
    os.makedirs(OUT, exist_ok=True)
    wb.save(path)
    print(f"Written: {path}")
    return path


if __name__ == "__main__":
    periodic_table()
