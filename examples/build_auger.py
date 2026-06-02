"""Build the "Auger Electron Spectroscopy" demo .ksheet example.

A surface-science example illustrating AES: the Auger KLL electron kinetic
energy, a synthetic N(E) spectrum (Gaussian on a linear background) and the
derivative dN/dE spectrum conventionally used in AES analysis.

Run:  python examples/build_auger.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from ksheet_author import Workbook, Series, PALETTE  # noqa: E402


# ---------------------------------------------------------------------------
# Physical parameters (also written as literal input cells)
# ---------------------------------------------------------------------------
E_K    = 1096.0   # Cu 2p1/2 → use Cu KLL instead: K-edge ~8979 eV is too big
                  # Use Al KLL: E_K = 1559 eV, E_L1 = 117 eV, E_L23 = 73 eV
                  # Auger KE ~ 1559 - 117 - 73 - 4.5 = 1364.5 eV  (Al KLL)
E_K    = 1559.0   # Al K binding energy (eV)
E_L1   = 117.0    # Al L1 binding energy (eV)
E_L23  = 73.0     # Al L2,3 binding energy (eV)
phi    = 4.5      # work function (eV)
FWHM   = 8.0      # Auger peak FWHM (eV)
amp    = 5000.0   # peak amplitude (counts)

# Derived
E_auger = E_K - E_L1 - E_L23 - phi   # = 1364.5 eV

# Energy grid: 61 points centred on the Auger KE ±30 eV
n_pts  = 61
E_lo   = E_auger - 30.0
E_hi   = E_auger + 30.0
E_grid = np.linspace(E_lo, E_hi, n_pts)

# Background parameters (linear, falling with increasing KE)
bg_slope  = -2.0   # counts/eV (stored as literal input)
bg_offset = 800.0  # counts at E_lo (stored as literal input)

# Gaussian sigma from FWHM
sigma = FWHM / (2.0 * np.sqrt(2.0 * np.log(2.0)))   # ~ 3.397 eV

# N(E) = bg_offset + bg_slope*(E - E_lo) + amp * exp(-0.5*((E-Eaug)/sigma)^2)
def N_E(E):
    bg  = bg_offset + bg_slope * (E - E_lo)
    pk  = amp * np.exp(-0.5 * ((E - E_auger) / sigma) ** 2)
    return bg + pk

NE   = N_E(E_grid)

# dN/dE by forward finite difference (last point uses backward difference)
dE   = E_grid[1] - E_grid[0]
dNdE = np.gradient(NE, dE)


def build() -> str:
    wb = Workbook(min_rows=70, min_cols=16)
    s  = wb.add_sheet("AES")

    # ------------------------------------------------------------------ Title
    s.title_block(
        "Auger Electron Spectroscopy (AES)",
        "Al KLL transition — N(E) spectrum and derivative dN/dE",
        span=8,
    )
    s.col_width(0, 220)
    s.col_width(1, 110)
    s.col_width(2, 110)
    s.col_width(3, 55)
    s.col_width(4, 160)
    s.col_width(5, 110)
    s.col_width(6, 120)
    s.col_width(7, 120)

    # --------------------------------------------------------- Input panel
    # Row 3: section label
    s.set(3, 0, "Editable Inputs")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    input_rows = [
        # (label,            value,     number_format)
        ("E_K — K-level binding energy (eV)",   E_K,   "0.0"),
        ("E_L1 — L1 binding energy (eV)",        E_L1,  "0.0"),
        ("E_L23 — L2,3 binding energy (eV)",     E_L23, "0.0"),
        ("phi — work function (eV)",             phi,   "0.00"),
        ("Peak FWHM (eV)",                       FWHM,  "0.0"),
        ("Peak amplitude (counts)",              amp,   "0"),
        ("Background at E_lo (counts)",          bg_offset, "0"),
        ("Background slope (counts/eV)",         bg_slope,  "0.00"),
    ]

    # Rows 4..11  →  sheet rows 5..12  →  B5..B12
    for i, (lbl, val, nfmt) in enumerate(input_rows):
        r = 4 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, align="left")
        s.fmt(r, 1, bg=PALETTE["warn"], align="right", number_format=nfmt)

    s.box(4, 0, 11, 1, color=PALETTE["accent"], width=1.2)

    # Sticky notes
    s.note(4, 1,
           "Edit E_K, E_L1, E_L23 or phi — the Auger KE formula (B14) "
           "and the whole N(E)/dN/dE table recalculate instantly.",
           kind="note")
    s.note(9, 1,
           "Auger electron energies are independent of the primary beam "
           "energy — only the core-level binding energies matter.",
           kind="note")

    # --------------------------------------------------------- Derived panel
    # Row 3 col 3-5
    s.set(3, 3, "Derived Quantities")
    s.fmt(3, 3, bold=True, font_color=PALETTE["accent"])
    s.merge(3, 3, 1, 3)

    # Auger KE formula at row 4 (0-based) → sheet row 5 → B5
    # Inputs: B5=E_K, B6=E_L1, B7=E_L23, B8=phi
    s.set(4, 3, "Auger KE (eV)")
    s.formula(4, 4, "=$B$5-$B$6-$B$7-$B$8")
    s.fmt(4, 3, align="left")
    s.fmt(4, 4, bg=PALETTE["good"], align="right", number_format="0.00",
          bold=True)

    # Sigma = FWHM / 2.3548  →  B9=FWHM, so sigma at E5 (row4,col4 already used)
    # Place sigma at row 5 (0-based) → sheet row 6
    s.set(5, 3, "Sigma = FWHM / 2.3548 (eV)")
    s.formula(5, 4, "=$B$9/2.3548")
    s.fmt(5, 3, align="left")
    s.fmt(5, 4, bg=PALETTE["band"], align="right", number_format="0.000")

    # E_lo = E_Auger - 30 eV
    s.set(6, 3, "E_lo grid start (eV)")
    s.formula(6, 4, "=$E$5-30")
    s.fmt(6, 3, align="left")
    s.fmt(6, 4, bg=PALETTE["band"], align="right", number_format="0.0")

    # E_hi = E_Auger + 30 eV
    s.set(7, 3, "E_hi grid end (eV)")
    s.formula(7, 4, "=$E$5+30")
    s.fmt(7, 3, align="left")
    s.fmt(7, 4, bg=PALETTE["band"], align="right", number_format="0.0")

    s.box(4, 3, 7, 4, color=PALETTE["header"], width=1.0)

    # Summary: peak-to-peak of dN/dE  (filled after table is defined)
    # Will reference the dN/dE column range — done below after table layout.

    # --------------------------------------------------------- Data table
    # Table headers at row 13 (0-based) → sheet row 14
    # Data rows 14..74 (0-based) → sheet rows 15..75
    table_start = 13   # 0-based row of header row
    # n_pts = 61 data rows

    # Column layout (0-based):
    #   col 0 → A  : E (eV)       — literal independent variable
    #   col 1 → B  : N(E)         — formula
    #   col 2 → C  : dN/dE        — formula (finite difference)

    s.set(12, 0, "Spectrum Data  (E_lo to E_hi, 61 points)")
    s.fmt(12, 0, bold=True, font_color=PALETTE["header"])
    s.merge(12, 0, 1, 3)

    # Designate columns
    s.designate(0, "X")
    s.designate(1, "Y")
    s.designate(2, "Y")

    # Build table rows.
    # Header is at sheet row (table_start + 1) = 14.
    # First data row is sheet row (table_start + 2) = 15.
    # So for data index k (0-based), sheet row = table_start + 2 + k = 15 + k.
    #
    # N(E) formula (row rr, col A = energy cell):
    #   = $B$11 + $B$12*(A{rr} - $E$7)
    #     + $B$10 * EXP(-0.5*((A{rr}-$E$5)/$E$6)^2)
    #
    # Inputs mapping:
    #   B5  = E_K      (row 4, col 1)
    #   B6  = E_L1     (row 5, col 1)
    #   B7  = E_L23    (row 6, col 1)
    #   B8  = phi      (row 7, col 1)
    #   B9  = FWHM     (row 8, col 1)
    #   B10 = amp      (row 9, col 1)
    #   B11 = bg_offset (row 10, col 1)
    #   B12 = bg_slope  (row 11, col 1)
    #
    # Derived:
    #   E5  = Auger KE  (row 4, col 4)
    #   E6  = sigma     (row 5, col 4)
    #   E7  = E_lo      (row 6, col 4)
    #   E8  = E_hi      (row 7, col 4)
    #
    # Energy step dE = (E_hi - E_lo) / 60 — need this as a cell ref.
    # We'll compute dE as a derived cell at E9 (row 8, col 4).
    s.set(8, 3, "dE step (eV)")
    s.formula(8, 4, "=($E$8-$E$7)/60")
    s.fmt(8, 3, align="left")
    s.fmt(8, 4, bg=PALETTE["band"], align="right", number_format="0.000")
    s.box(4, 3, 8, 4, color=PALETTE["header"], width=1.0)

    # The energy grid values are: E_lo + k * dE  for k = 0..60
    # We write them as literal floats (the independent variable).
    # N(E) and dN/dE are formulas referencing the same-row energy cell (col A).
    #
    # dN/dE finite difference:
    #   interior:  (N(E_{k+1}) - N(E_{k-1})) / (2*dE)   (central)
    #   first row: (N(E_1) - N(E_0)) / dE                 (forward)
    #   last row:  (N(E_n) - N(E_{n-1})) / dE             (backward)
    #
    # In sheet terms (1-based):
    #   first data row = sheet row 15  →  A15, B15
    #   last data row  = sheet row 75  →  A75, B75
    #   interior row r : dN/dE = (B{r+1} - B{r-1}) / (2*$E$9)

    first_data_sheet_row = table_start + 2   # = 15  (1-based)
    last_data_sheet_row  = table_start + 1 + n_pts  # = 75

    rows = []
    for k in range(n_pts):
        rr = first_data_sheet_row + k   # 1-based sheet row of this data row

        # Energy literal
        E_val = round(float(E_grid[k]), 4)

        # N(E) formula
        ne_formula = (
            f"=$B$11+$B$12*(A{rr}-$E$7)"
            f"+$B$10*EXP(-0.5*((A{rr}-$E$5)/$E$6)*((A{rr}-$E$5)/$E$6))"
        )

        # dN/dE finite difference formula
        if k == 0:
            # forward: (B_next - B_this) / dE
            dnde_formula = f"=(B{rr+1}-B{rr})/$E$9"
        elif k == n_pts - 1:
            # backward: (B_this - B_prev) / dE
            dnde_formula = f"=(B{rr}-B{rr-1})/$E$9"
        else:
            # central: (B_next - B_prev) / (2*dE)
            dnde_formula = f"=(B{rr+1}-B{rr-1})/(2*$E$9)"

        rows.append([E_val, ne_formula, dnde_formula])

    s.table(
        table_start, 0,
        headers=["E (eV)", "N(E)  (counts)", "dN/dE  (counts/eV)"],
        rows=rows,
        number_format="0.0",
        banded=True,
    )

    # --------------------------------------------------------- Summary panel
    # Place at rows 4..8, cols 6-7  (right of derived panel)
    s.set(3, 6, "Spectrum Summary")
    s.fmt(3, 6, bold=True, font_color=PALETTE["accent"])
    s.merge(3, 6, 1, 2)

    first_ne_ref = f"B{first_data_sheet_row}"
    last_ne_ref  = f"B{last_data_sheet_row}"
    first_dn_ref = f"C{first_data_sheet_row}"
    last_dn_ref  = f"C{last_data_sheet_row}"

    summary_items = [
        ("Auger KE (eV)",    "=$E$5",                           PALETTE["good"]),
        ("Peak N(E) max",    f"=MAX({first_ne_ref}:{last_ne_ref})", PALETTE["band"]),
        ("Bg at grid start", f"=$B$11",                          PALETTE["band_alt"]),
        ("dN/dE peak-peak",  f"=MAX({first_dn_ref}:{last_dn_ref})-MIN({first_dn_ref}:{last_dn_ref})",
                                                                  PALETTE["warn"]),
        ("dN/dE peak (pos)", f"=MAX({first_dn_ref}:{last_dn_ref})", PALETTE["good"]),
        ("dN/dE trough",     f"=MIN({first_dn_ref}:{last_dn_ref})", PALETTE["bad"]),
    ]

    for i, (lbl, expr, col) in enumerate(summary_items):
        r = 4 + i
        s.set(r, 6, lbl)
        s.formula(r, 7, expr)
        s.fmt(r, 6, align="left")
        s.fmt(r, 7, bg=col, align="right", number_format="0.0", bold=True)

    s.box(4, 6, 9, 7, color=PALETTE["header"], width=1.2)
    s.col_width(6, 170)
    s.col_width(7, 110)

    # --------------------------------------------------------- Chart
    # dN/dE (col C = index 2) vs E (col A = index 0)
    # 0-based rows: table_start+1 .. table_start+n_pts = 14 .. 74
    r0 = table_start + 1
    r1 = table_start + n_pts

    s.chart(
        [
            Series(
                E_grid, dNdE,
                label="dN/dE",
                plot_type="Line",
                color="#4472c4",
                linewidth=1.8,
                x_col=0, y_col=2,
                row_start=r0, row_end=r1,
            ),
        ],
        at=(620, 20), size=(460, 310),
        title="AES Derivative Spectrum  dN/dE vs Kinetic Energy",
        xlabel="Kinetic Energy  E  (eV)",
        ylabel="dN/dE  (counts/eV)",
        grid=True, legend=True,
    )

    # N(E) chart (secondary, smaller, placed below)
    s.chart(
        [
            Series(
                E_grid, NE,
                label="N(E)",
                plot_type="Line",
                color="#ed7d31",
                linewidth=1.8,
                x_col=0, y_col=1,
                row_start=r0, row_end=r1,
            ),
        ],
        at=(620, 350), size=(460, 280),
        title="N(E) Direct Spectrum",
        xlabel="Kinetic Energy  E  (eV)",
        ylabel="N(E)  (counts)",
        grid=True, legend=True,
    )

    # --------------------------------------------------------- Note on surface
    s.note(11, 1,
           "AES is surface-sensitive (sampling depth ~1–3 nm) because "
           "Auger electrons have short inelastic mean free paths in solids.",
           kind="note")

    # Derivative-mode note
    s.note(12, 0,
           "Derivative mode (dN/dE) suppresses the large slowly-varying "
           "secondary-electron background, making small Auger peaks visible.",
           kind="note")

    # --------------------------------------------------------- Equation
    s.equation(
        r"E_{\mathrm{Auger}} = E_K - E_{L_1} - E_{L_{23}} - \phi",
        at=(620, 650), fontsize=20,
        color="#222222",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.4,
        size=(340, 54),
    )

    # --------------------------------------------------------- Save
    out = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "Auger Electron Spectroscopy.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
