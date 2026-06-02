"""Build the "XRD Bragg Diffraction" demo .ksheet example.

Powder X-ray diffraction peak positions for a cubic crystal via Bragg's
law.  Editable inputs: X-ray wavelength lambda (Cu K-alpha default),
cubic lattice parameter a, diffraction order n.  A table of common hkl
reflections computes d-spacing and 2theta for each peak.  Reflections
whose ASIN argument exceeds 1 are suppressed with an IF guard.  A bar
chart of intensity-proxy vs 2theta is live-bound to the sheet columns.
Two mathtext equations illustrate Bragg's law and the d-spacing formula.

Run:  python examples/build_xrd.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from ksheet_author import Workbook, Series, PALETTE  # noqa: E402


# ---------------------------------------------------------------------------
# Physical / crystallographic constants for the initial render.
# ---------------------------------------------------------------------------

LAMBDA_DEFAULT = 1.5406   # Cu K-alpha (Angstrom)
A_DEFAULT      = 3.615    # Copper FCC lattice parameter (Angstrom)
N_DEFAULT      = 1        # Diffraction order

# Common cubic hkl reflections (systematic absences for FCC already excluded
# so all are in principle "allowed", but the worksheet shows all and lets the
# user interpret them).  Sorted by M = h^2+k^2+l^2.
HKL = [
    (1, 0, 0),   # M=1
    (1, 1, 0),   # M=2
    (1, 1, 1),   # M=3
    (2, 0, 0),   # M=4
    (2, 1, 0),   # M=5
    (2, 1, 1),   # M=6
    (2, 2, 0),   # M=8
    (2, 2, 1),   # M=9
    (3, 0, 0),   # M=9  (same M as 221)
    (3, 1, 0),   # M=10
    (3, 1, 1),   # M=11
    (2, 2, 2),   # M=12
    (3, 2, 0),   # M=13
    (3, 2, 1),   # M=14
    (4, 0, 0),   # M=16
]

TABLE_START = 8   # 0-based sheet row where the hkl table header sits
                  # => header at sheet row 9 (1-based), first data at row 10


def _two_theta(lam, a, n, h, k, l):
    """Return 2theta in degrees, or None if ASIN argument > 1."""
    M = h*h + k*k + l*l
    d = a / np.sqrt(M)
    arg = n * lam / (2.0 * d)
    if arg > 1.0:
        return None
    return float(2.0 * np.degrees(np.arcsin(arg)))


def build() -> str:
    wb = Workbook(min_rows=44, min_cols=14)
    s = wb.add_sheet("XRD")

    # -----------------------------------------------------------------------
    # Column layout (0-based):
    #   A(0)=hkl label, B(1)=h, C(2)=k, D(3)=l, E(4)=M,
    #   F(5)=d (A),     G(6)=2theta,    H(7)=intensity proxy (1/M)
    # -----------------------------------------------------------------------

    # -----------------------------------------------------------------------
    # Title block
    # -----------------------------------------------------------------------
    s.title_block(
        "XRD Bragg Diffraction",
        "Powder diffraction 2θ positions for a cubic crystal (Cu Kα default)",
        span=9,
    )

    # -----------------------------------------------------------------------
    # Input panel  (rows 3–5, cols 0-2)
    # -----------------------------------------------------------------------
    s.set(3, 0, "Inputs")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    inputs = [
        ("Wavelength λ (Å)",           LAMBDA_DEFAULT,  "B4"),
        ("Lattice parameter a (Å)",          A_DEFAULT,       "B5"),
        ("Diffraction order n",                   N_DEFAULT,       "B6"),
    ]
    for i, (lbl, val, _ref) in enumerate(inputs):
        r = 4 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, align="left")
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.0000")
    # order n is integer
    s.fmt(6, 1, number_format="0")

    s.box(4, 0, 6, 1, color=PALETTE["accent"], width=1.2)
    s.col_width(0, 210)   # hkl label column
    s.col_width(1, 80)
    s.col_width(2, 55)
    s.col_width(3, 55)
    s.col_width(4, 55)
    s.col_width(5, 85)
    s.col_width(6, 90)
    s.col_width(7, 90)

    s.note(4, 1,
           "Edit λ, a, or n here — d-spacing and 2θ columns "
           "recalculate automatically.",
           kind="note")

    # -----------------------------------------------------------------------
    # Section label above the table
    # -----------------------------------------------------------------------
    s.set(7, 0, "hkl Reflection Table")
    s.fmt(7, 0, bold=True, font_color=PALETTE["header"])
    s.merge(7, 0, 1, 8)

    # -----------------------------------------------------------------------
    # Table of hkl reflections
    # TABLE_START = 8 (0-based), so:
    #   header row (sheet) = TABLE_START+1 = 9 (1-based)
    #   first data row (sheet) = TABLE_START+2 = 10 (1-based)
    # -----------------------------------------------------------------------
    headers = ["hkl", "h", "k", "l", "M = h²+k²+l²",
               "d (Å)", "2θ (°)", "Rel. intensity"]

    table_rows = []
    for idx, (h, k, l) in enumerate(HKL):
        # 1-based sheet row for this data row
        sr = TABLE_START + 2 + idx   # e.g. first row: 8+2+0 = 10

        hkl_label = f"{h}{k}{l}"
        M = h*h + k*k + l*l

        # d-spacing formula: =$B$6/SQRT(E<sr>)
        # Inputs are at 0-based rows 4,5,6 => 1-based B5, B6, B7
        # $B$5 = lambda, $B$6 = a, $B$7 = n
        d_formula = f"=$B$6/SQRT(E{sr})"

        # 2theta formula with ASIN guard:
        #   =IF($B$7*$B$5/(2*F<sr>)>1,"—",2*DEGREES(ASIN($B$7*$B$5/(2*F<sr>))))
        two_theta_formula = (
            f"=IF($B$7*$B$5/(2*F{sr})>1,\"—\","
            f"2*DEGREES(ASIN($B$7*$B$5/(2*F{sr}))))"
        )

        # Intensity proxy: 1/M (simple geometric multiplicity proxy).
        # M = h²+k²+l² is always >= 1, so this never errors.  Reflections
        # with 2θ = "—" yield a non-numeric X and are dropped from the
        # chart automatically, so no ISNUMBER guard is needed (and
        # ISNUMBER(<cell ref>) is not supported by the formula engine).
        intensity_formula = f"=1/E{sr}"

        table_rows.append([
            hkl_label,
            h, k, l,
            f"={h}^2+{k}^2+{l}^2",   # M as a formula
            d_formula,
            two_theta_formula,
            intensity_formula,
        ])

    s.table(
        TABLE_START, 0,
        headers=headers,
        rows=table_rows,
        number_format="0.0000",
        banded=True,
    )

    # Left-align hkl label column (already done by table helper for col 0,
    # but also centre h, k, l columns explicitly).
    n_rows = len(HKL)
    for i in range(n_rows):
        r = TABLE_START + 1 + i
        s.fmt(r, 1, align="center")
        s.fmt(r, 2, align="center")
        s.fmt(r, 3, align="center")
        s.fmt(r, 4, align="center")

    # -----------------------------------------------------------------------
    # Designate columns for chart binding
    # col 6 = 2theta (X), col 7 = intensity proxy (Y)
    # -----------------------------------------------------------------------
    s.designate(6, "X")
    s.designate(7, "Y")

    # -----------------------------------------------------------------------
    # Summary panel  (rows TABLE_START+n_rows+2 .. +4, cols 9-11)
    # -----------------------------------------------------------------------
    first_data_sr = TABLE_START + 2          # 1-based: 10
    last_data_sr  = TABLE_START + 1 + n_rows # 1-based: 24 (for 15 reflections)

    summ_row = TABLE_START + 1  # 0-based, start alongside the table header
    s.set(summ_row - 1, 9, "Summary")
    s.fmt(summ_row - 1, 9, bold=True, font_color=PALETTE["header"])
    s.merge(summ_row - 1, 9, 1, 3)

    summary_items = [
        ("Min 2θ (°)",    f"=MIN(G{first_data_sr}:G{last_data_sr})",
         PALETTE["good"]),
        ("Max 2θ (°)",    f"=MAX(G{first_data_sr}:G{last_data_sr})",
         PALETTE["band"]),
        ("d₀ (111) (Å)", f"=F{TABLE_START + 2 + 2}",   # row index 2 = (111)
         PALETTE["band_alt"]),
        ("nλ / (2d₀)", f"=$B$7*$B$5/(2*F{TABLE_START + 2 + 2})",
         PALETTE["warn"]),
    ]
    for j, (lbl, expr, col) in enumerate(summary_items):
        r = summ_row + j
        s.set(r, 9, lbl)
        s.formula(r, 10, expr)
        s.fmt(r, 9, align="left")
        s.fmt(r, 10, bg=col, align="center", number_format="0.0000", bold=True)

    s.box(summ_row, 9, summ_row + len(summary_items) - 1, 10,
          color=PALETTE["header"], width=1.0)
    s.col_width(9, 160)
    s.col_width(10, 100)

    # -----------------------------------------------------------------------
    # Notes
    # -----------------------------------------------------------------------
    s.note(TABLE_START, 6,
           "2θ shows '—' for reflections where nλ/(2d) > 1 "
           "(physically inaccessible). For Cu Kα on copper (a=3.615 Å) "
           "the (111) peak is near 43.3°.",
           kind="note")
    s.note(TABLE_START, 7,
           "Rel. intensity here is a simple 1/M proxy (geometric term). "
           "Edit column for real structure factors.",
           kind="note")

    # -----------------------------------------------------------------------
    # Compute numpy arrays for the chart (must match formula results)
    # -----------------------------------------------------------------------
    two_thetas = []
    intensities = []
    for h, k, l in HKL:
        M = h*h + k*k + l*l
        tt = _two_theta(LAMBDA_DEFAULT, A_DEFAULT, N_DEFAULT, h, k, l)
        if tt is not None:
            two_thetas.append(tt)
            intensities.append(1.0 / M)
        else:
            # Inaccessible — use 0 placeholder (the IF formula yields "—")
            two_thetas.append(0.0)
            intensities.append(0.0)

    two_thetas  = np.array(two_thetas,  dtype=float)
    intensities = np.array(intensities, dtype=float)

    # 0-based row bounds for the data block (inclusive)
    r0 = TABLE_START + 1            # first data row (0-based)
    r1 = TABLE_START + n_rows       # last  data row (0-based)

    s.chart(
        [Series(
            two_thetas, intensities,
            label="Rel. intensity",
            plot_type="Bar",
            color=PALETTE["header"],
            x_col=6,   # 2theta column (0-based)
            y_col=7,   # intensity proxy column (0-based)
            row_start=r0,
            row_end=r1,
        )],
        at=(540, 40),
        size=(430, 300),
        title="XRD Pattern (cubic, Cu Kα)",
        xlabel="2θ (°)",
        ylabel="Relative intensity",
        grid=True,
        legend=False,
    )

    # -----------------------------------------------------------------------
    # Equations (matplotlib mathtext)
    # -----------------------------------------------------------------------
    # Bragg's law
    s.equation(
        r"n \lambda = 2 d \sin\theta",
        at=(540, 360),
        fontsize=22,
        color="#222222",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.4,
        size=(260, 56),
    )

    # d-spacing for cubic
    s.equation(
        r"d_{hkl} = \frac{a}{\sqrt{h^{2}+k^{2}+l^{2}}}",
        at=(540, 432),
        fontsize=20,
        color="#222222",
        bg_color="#ffffff",
        border_color=PALETTE["accent"],
        border_width=1.4,
        size=(300, 60),
    )

    # -----------------------------------------------------------------------
    # Save
    # -----------------------------------------------------------------------
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "XRD Bragg Diffraction.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
