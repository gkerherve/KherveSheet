"""Build the "Recipe Scaler" Daily Life template .ksheet file.

A polished, practical recipe scaler with:
  - Editable inputs (amber): Original Servings, Desired Servings.
  - Scale Factor: live formula =DesiredServings/OriginalServings.
  - Ingredients table: Ingredient | Original Qty | Unit | Scaled Qty,
    where Scaled Qty = OriginalQty * $DesiredServings / $OriginalServings
    as a live formula per row.
  - A summary panel showing the current scale factor.
  - A LaTeX equation for the scaling formula.
  - Instructive yellow sticky notes.

Save path: examples/templates/Daily Life/Recipe Scaler.ksheet

Run:  python examples/build_tpl_recipe.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

# Ensure the repo root is importable.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from examples.ksheet_author import Workbook, PALETTE  # noqa: E402


# ── Default recipe: Classic Chocolate Chip Cookies (makes 24) ─────────
ORIGINAL_SERVINGS = 24   # cookies
DESIRED_SERVINGS  = 12   # cookies (half batch by default)

# Ingredients: (name, qty, unit)
# Quantities are plain floats (literal independents); Scaled Qty are formulas.
INGREDIENTS = [
    ("All-purpose flour",    2.25, "cups"),
    ("Baking soda",          1.0,  "tsp"),
    ("Salt",                 1.0,  "tsp"),
    ("Unsalted butter",      225.0, "g"),
    ("Granulated sugar",     150.0, "g"),
    ("Brown sugar",          165.0, "g"),
    ("Eggs",                 2.0,  "whole"),
    ("Vanilla extract",      1.0,  "tsp"),
    ("Chocolate chips",      340.0, "g"),
]


def build() -> str:
    wb = Workbook(min_rows=40, min_cols=10)
    s  = wb.add_sheet("Recipe Scaler")

    # ── Column widths ─────────────────────────────────────────────────
    s.col_width(0, 30)    # A: left margin / spacer
    s.col_width(1, 200)   # B: Ingredient name
    s.col_width(2, 110)   # C: Original Qty
    s.col_width(3, 80)    # D: Unit
    s.col_width(4, 120)   # E: Scaled Qty
    s.col_width(5, 30)    # F: spacer
    s.col_width(6, 180)   # G: input labels / summary labels
    s.col_width(7, 120)   # H: input values / summary values

    # ── Title block ───────────────────────────────────────────────────
    # 0-based rows 0-1; the title_block helper merges from col 0 by default,
    # but our layout starts ingredients at col 1 — place it spanning cols 1..7.
    s.set(0, 1, "Recipe Scaler")
    s.fmt(0, 1, bold=True, font_size=20, font_color=PALETTE["header"])
    s.merge(0, 1, 1, 7)

    s.set(1, 1, "Classic Chocolate Chip Cookies — adjust servings below")
    s.fmt(1, 1, italic=True, font_color="#555555")
    s.merge(1, 1, 1, 7)

    # ── Input panel (G / H columns, rows 3..4) ────────────────────────
    # 0-based row 3 → 1-based sheet row 4  → ref $H$4
    # 0-based row 4 → 1-based sheet row 5  → ref $H$5

    s.set(2, 6, "Servings")
    s.fmt(2, 6, bold=True, font_color=PALETTE["accent"], font_size=11)

    s.set(3, 6, "Original Servings")
    s.set(3, 7, ORIGINAL_SERVINGS)
    s.fmt(3, 6, align="left")
    s.fmt(3, 7, bg=PALETTE["warn"], align="center",
          number_format="0", bold=True, font_size=12)

    s.set(4, 6, "Desired Servings")
    s.set(4, 7, DESIRED_SERVINGS)
    s.fmt(4, 6, align="left")
    s.fmt(4, 7, bg=PALETTE["warn"], align="center",
          number_format="0", bold=True, font_size=12)

    s.box(3, 6, 4, 7, color=PALETTE["accent"], width=2.0)

    # Notes on inputs.
    s.note(3, 7,
           "Edit H4: original number of servings the recipe makes.\n"
           "All scaled quantities update automatically.",
           kind="note")
    s.note(4, 7,
           "Edit H5: how many servings you want to make.\n"
           "Scale factor = Desired / Original.",
           kind="note")

    # ── Summary panel (G / H columns, rows 6..7) ──────────────────────
    # Scale Factor = DesiredServings / OriginalServings
    # $H$4 = Original (0-based row 3, col 7 → 1-based H4)
    # $H$5 = Desired  (0-based row 4, col 7 → 1-based H5)

    s.set(6, 6, "Summary")
    s.fmt(6, 6, bold=True, font_color=PALETTE["header"], font_size=11)

    s.set(7, 6, "Scale Factor")
    s.formula(7, 7, "=$H$5/$H$4")
    s.fmt(7, 6, align="left")
    s.fmt(7, 7, bg=PALETTE["good"], align="center",
          number_format="0.00", bold=True, font_size=13)

    s.set(8, 6, "Scaled Servings")
    s.formula(8, 7, "=$H$5")
    s.fmt(8, 6, align="left")
    s.fmt(8, 7, bg=PALETTE["band"], align="center",
          number_format="0", bold=True, font_size=12)

    s.box(7, 6, 8, 7, color=PALETTE["header"], width=1.5)

    s.note(7, 7,
           "Scale Factor = Desired / Original.\n"
           "A value of 0.5 halves all quantities; 2.0 doubles them.",
           kind="note")

    # ── Ingredients table ─────────────────────────────────────────────
    # Header at 0-based row 3 → sheet row 4.
    # First data row at 0-based row 4 → sheet row 5.
    # Columns (0-based): B=1 (Ingredient), C=2 (Original Qty), D=3 (Unit),
    #                    E=4 (Scaled Qty).
    # Scaled Qty formula: =C{sheet_row}*$H$5/$H$4
    # where $H$4 = Original Servings, $H$5 = Desired Servings.
    TABLE_START = 3   # 0-based header row

    # Build formula rows.
    # Header is at TABLE_START (0-based) → sheet row TABLE_START+1 = 4.
    # First data row is TABLE_START+1 (0-based) → sheet row TABLE_START+2 = 5.
    table_rows = []
    for k, (name, qty, unit) in enumerate(INGREDIENTS):
        data_sheet_row = TABLE_START + 2 + k   # 1-based ref for this row
        scaled_formula = f"=C{data_sheet_row}*$H$5/$H$4"
        table_rows.append([name, qty, unit, scaled_formula])

    s.table(TABLE_START, 1,
            headers=["Ingredient", "Original Qty", "Unit", "Scaled Qty"],
            rows=table_rows,
            number_format="0.##",
            banded=True)

    # Override column alignment: Original Qty and Scaled Qty right-aligned,
    # Unit centred, Ingredient left-aligned (table() already does first col).
    n = len(INGREDIENTS)
    for k in range(n):
        r = TABLE_START + 1 + k
        s.fmt(r, 2, align="right")    # Original Qty
        s.fmt(r, 3, align="center")   # Unit
        s.fmt(r, 4, align="right", number_format="0.##")   # Scaled Qty

    # Scaled Qty column: bold to make it stand out.
    for k in range(n):
        r = TABLE_START + 1 + k
        s.fmt(r, 4, bold=True)

    # ── Section label above table ─────────────────────────────────────
    s.set(2, 1, "Ingredients")
    s.fmt(2, 1, bold=True, font_color=PALETTE["accent"], font_size=11)

    # ── Cooking notes section ─────────────────────────────────────────
    notes_row = TABLE_START + 1 + n + 2   # two blank rows below table
    s.set(notes_row, 1, "Recipe Notes")
    s.fmt(notes_row, 1, bold=True, font_color=PALETTE["header"], font_size=11)
    s.merge(notes_row, 1, 1, 4)

    hints = [
        "Preheat oven to 190 °C (375 °F). Line baking sheets with parchment.",
        "Cream butter and sugars until light and fluffy (~3 min).",
        "Beat in eggs one at a time; add vanilla extract.",
        "Gradually mix in flour, baking soda and salt; fold in chocolate chips.",
        "Drop rounded tablespoons onto prepared sheets, 5 cm apart.",
        "Bake 9-11 minutes until edges are golden. Cool 2 min before transferring.",
    ]
    for i, hint in enumerate(hints):
        r = notes_row + 1 + i
        s.set(r, 1, f"{i+1}. {hint}")
        s.fmt(r, 1, align="left", wrap=True)
        s.merge(r, 1, 1, 4)
        if i % 2 == 1:
            s.fmt_range(r, 1, r, 4, bg=PALETTE["band_alt"])

    s.box(notes_row, 1, notes_row + len(hints), 4,
          color=PALETTE["header"], width=1.0)

    # ── LaTeX equation ────────────────────────────────────────────────
    # Scaled Qty = Original Qty * (Desired / Original)
    s.equation(
        r"\mathrm{Scaled} = \mathrm{OrigQty} \times "
        r"\frac{\mathrm{Desired}}{\mathrm{Original}}",
        at=(540, 200),
        fontsize=17,
        color="#222222",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.5,
        size=(340, 60),
    )

    # ── Save ──────────────────────────────────────────────────────────
    out = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "templates", "Daily Life", "Recipe Scaler.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
