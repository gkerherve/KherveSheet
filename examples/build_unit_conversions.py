"""Build the "Unit Conversions" demo .ksheet example.

An interactive unit-conversion reference.  The user types a value into
one amber input cell per category and every equivalent updates via
formulas.  Four categories are covered, each in its own styled mini-table:

  Length      — metres  -> km, miles, feet, inches, yards
  Mass        — kg      -> g, lb, oz, stones
  Temperature — Celsius -> Fahrenheit (offset formula), Kelvin
  Speed       — m/s     -> km/h, mph, knots

Charts and equations are intentionally omitted — they would add no value
to a reference sheet whose purpose is the conversion tables themselves.

Run:  python examples/build_unit_conversions.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os

from ksheet_author import Workbook, PALETTE


# ---------------------------------------------------------------------------
# Layout constants (all 0-based)
# ---------------------------------------------------------------------------

# Two columns per "panel": col A = label, col B = value.
# We lay four tables down one sheet, separated by a blank row.
# Each table: 1 section-header row, 1 column-header row, N data rows.

COL_LABEL = 0    # A — conversion name
COL_VALUE = 1    # B — value (input amber or formula result)
COL_UNIT  = 2    # C — unit string

# Section-header colour (accent orange)
SEC_COLOR = PALETTE["accent"]   # "#ed7d31"
# Input cell colour (amber / warn)
INPUT_BG  = PALETTE["warn"]     # "#ffeb9c"
# Result banding colours
BAND_EVEN = None                # white
BAND_ODD  = PALETTE["band_alt"] # very light blue


def _section_header(s, row, label):
    """Bold accent-coloured section label spanning three columns."""
    s.set(row, COL_LABEL, label)
    s.fmt(row, COL_LABEL,
          bold=True, font_size=12, font_color="#ffffff",
          bg=SEC_COLOR, align="center")
    s.fmt(row, COL_VALUE, bg=SEC_COLOR)
    s.fmt(row, COL_UNIT,  bg=SEC_COLOR)
    s.merge(row, COL_LABEL, 1, 3)


def _col_headers(s, row):
    """"Conversion", "Value", "Unit" sub-header row."""
    for c, text in enumerate(["Conversion", "Value", "Unit"]):
        s.set(row, c, text)
        s.fmt(row, c,
              bold=True,
              bg=PALETTE["header"],
              font_color=PALETTE["header_text"],
              align="center")


def _input_row(s, row, label, value, unit):
    """Amber editable input cell."""
    s.set(row, COL_LABEL, label)
    s.set(row, COL_VALUE, value)
    s.set(row, COL_UNIT,  unit)
    s.fmt(row, COL_LABEL, align="left", bold=True)
    s.fmt(row, COL_VALUE, bg=INPUT_BG, align="right",
          number_format="0.0000", bold=True)
    s.fmt(row, COL_UNIT,  align="left", italic=True,
          font_color="#666666")


def _result_row(s, row, label, formula_expr, unit, band):
    """One formula-driven result row."""
    bg = BAND_ODD if band else BAND_EVEN
    s.set(row, COL_LABEL, label)
    s.formula(row, COL_VALUE, formula_expr)
    s.set(row, COL_UNIT,  unit)
    kw = dict(align="right", number_format="0.0000")
    if bg:
        kw["bg"] = bg
    s.fmt(row, COL_LABEL, align="left", **({"bg": bg} if bg else {}))
    s.fmt(row, COL_VALUE, **kw)
    s.fmt(row, COL_UNIT,  align="left", italic=True,
          font_color="#666666", **({"bg": bg} if bg else {}))


def _box_table(s, top_row, bottom_row):
    """Blue outer box plus inner grid lines for the whole mini-table."""
    s.box(top_row, COL_LABEL, bottom_row, COL_UNIT,
          color=PALETTE["header"], width=1.2, style="solid")
    s.box(top_row, COL_LABEL, bottom_row, COL_UNIT,
          color="#bfbfbf", width=0.6, style="solid", inner=True)


def build() -> str:
    wb = Workbook(min_rows=50, min_cols=8)
    s = wb.add_sheet("Unit Conversions")

    # Column widths
    s.col_width(COL_LABEL, 210)
    s.col_width(COL_VALUE, 130)
    s.col_width(COL_UNIT,  100)

    # ------------------------------------------------------------------ #
    # Title block                                                          #
    # ------------------------------------------------------------------ #
    s.title_block("Unit Conversions",
                  "Type a value in the amber cell — every equivalent "
                  "updates automatically",
                  row=0, col=0, span=3)
    s.fmt(1, 0, font_size=10)

    # ------------------------------------------------------------------ #
    # 1. LENGTH  (input in metres, cell B5 = sheet row index 4)           #
    # ------------------------------------------------------------------ #
    LENGTH_SEC  = 3   # section header (0-based row)
    LENGTH_HEAD = 4   # column header row
    LENGTH_INP  = 5   # input row  → sheet cell B6
    LENGTH_R0   = 6   # first result row

    _section_header(s, LENGTH_SEC,  "LENGTH")
    _col_headers(s, LENGTH_HEAD)
    _input_row(s, LENGTH_INP, "Input (metres)", 1.0, "m")
    s.note(LENGTH_INP, COL_VALUE,
           "Edit this cell to change all length conversions below.",
           kind="note")

    # B6 holds the input in metres (1-based: row 6, col B)
    length_results = [
        ("Kilometres",  "=$B$6*0.001",        "km"),
        ("Miles",       "=$B$6*0.000621371",   "mi"),
        ("Feet",        "=$B$6*3.28084",       "ft"),
        ("Inches",      "=$B$6*39.3701",       "in"),
        ("Yards",       "=$B$6*1.09361",       "yd"),
    ]
    for i, (lbl, expr, unit) in enumerate(length_results):
        _result_row(s, LENGTH_R0 + i, lbl, expr, unit, band=(i % 2 == 1))

    length_bottom = LENGTH_R0 + len(length_results) - 1
    _box_table(s, LENGTH_SEC, length_bottom)

    # ------------------------------------------------------------------ #
    # 2. MASS  (input in kilograms, cell B14 = 0-based row 13)            #
    # ------------------------------------------------------------------ #
    MASS_SEC  = length_bottom + 2
    MASS_HEAD = MASS_SEC + 1
    MASS_INP  = MASS_HEAD + 1    # sheet row = MASS_INP + 1
    MASS_R0   = MASS_INP + 1

    _section_header(s, MASS_SEC,  "MASS")
    _col_headers(s, MASS_HEAD)
    # Compute the 1-based sheet row for the input cell
    mass_input_sheet_row = MASS_INP + 1   # 1-based
    _input_row(s, MASS_INP,
               "Input (kilograms)", 1.0, "kg")
    s.note(MASS_INP, COL_VALUE,
           "Edit this cell to change all mass conversions below.",
           kind="note")

    mass_inp_ref = f"$B${mass_input_sheet_row}"
    mass_results = [
        ("Grams",   f"={mass_inp_ref}*1000",      "g"),
        ("Pounds",  f"={mass_inp_ref}*2.20462",   "lb"),
        ("Ounces",  f"={mass_inp_ref}*35.274",    "oz"),
        ("Stones",  f"={mass_inp_ref}*0.157473",  "st"),
    ]
    for i, (lbl, expr, unit) in enumerate(mass_results):
        _result_row(s, MASS_R0 + i, lbl, expr, unit, band=(i % 2 == 1))

    mass_bottom = MASS_R0 + len(mass_results) - 1
    _box_table(s, MASS_SEC, mass_bottom)

    # ------------------------------------------------------------------ #
    # 3. TEMPERATURE  (input in Celsius)                                  #
    # ------------------------------------------------------------------ #
    TEMP_SEC  = mass_bottom + 2
    TEMP_HEAD = TEMP_SEC + 1
    TEMP_INP  = TEMP_HEAD + 1
    TEMP_R0   = TEMP_INP + 1

    _section_header(s, TEMP_SEC,  "TEMPERATURE")
    _col_headers(s, TEMP_HEAD)
    temp_input_sheet_row = TEMP_INP + 1
    _input_row(s, TEMP_INP,
               "Input (Celsius)", 100.0, "°C")
    s.note(TEMP_INP, COL_VALUE,
           "Temperature uses an offset formula, not a simple ratio.\n"
           "°F = C × 9/5 + 32    |    K = C + 273.15",
           kind="note")

    temp_inp_ref = f"$B${temp_input_sheet_row}"
    temp_results = [
        ("Fahrenheit",  f"={temp_inp_ref}*9/5+32",     "°F"),
        ("Kelvin",      f"={temp_inp_ref}+273.15",      "K"),
    ]
    for i, (lbl, expr, unit) in enumerate(temp_results):
        _result_row(s, TEMP_R0 + i, lbl, expr, unit, band=(i % 2 == 1))

    temp_bottom = TEMP_R0 + len(temp_results) - 1
    _box_table(s, TEMP_SEC, temp_bottom)

    # ------------------------------------------------------------------ #
    # 4. SPEED  (input in m/s)                                            #
    # ------------------------------------------------------------------ #
    SPEED_SEC  = temp_bottom + 2
    SPEED_HEAD = SPEED_SEC + 1
    SPEED_INP  = SPEED_HEAD + 1
    SPEED_R0   = SPEED_INP + 1

    _section_header(s, SPEED_SEC,  "SPEED")
    _col_headers(s, SPEED_HEAD)
    speed_input_sheet_row = SPEED_INP + 1
    _input_row(s, SPEED_INP,
               "Input (metres/second)", 1.0, "m/s")
    s.note(SPEED_INP, COL_VALUE,
           "Edit this cell to change all speed conversions below.",
           kind="note")

    speed_inp_ref = f"$B${speed_input_sheet_row}"
    speed_results = [
        ("Kilometres/hour",  f"={speed_inp_ref}*3.6",       "km/h"),
        ("Miles/hour",       f"={speed_inp_ref}*2.23694",   "mph"),
        ("Knots",            f"={speed_inp_ref}*1.94384",   "kn"),
    ]
    for i, (lbl, expr, unit) in enumerate(speed_results):
        _result_row(s, SPEED_R0 + i, lbl, expr, unit, band=(i % 2 == 1))

    speed_bottom = SPEED_R0 + len(speed_results) - 1
    _box_table(s, SPEED_SEC, speed_bottom)

    # ------------------------------------------------------------------ #
    # Footer note                                                          #
    # ------------------------------------------------------------------ #
    footer_row = speed_bottom + 2
    s.set(footer_row, COL_LABEL,
          "All conversion factors follow NIST / SI definitions.")
    s.fmt(footer_row, COL_LABEL,
          italic=True, font_color="#888888", font_size=9)
    s.merge(footer_row, COL_LABEL, 1, 3)

    # ------------------------------------------------------------------ #
    # Save                                                                 #
    # ------------------------------------------------------------------ #
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "Unit Conversions.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
