"""Build "Quantum Chemistry DFT.ksheet" template.

A molecular-orbital (MO) results workbook for a closed-shell molecule
(representative of a DFT/B3LYP calculation on a small aromatic):

  Sheet "MO Results"
  ├─ Title block
  ├─ Input panel  : HOMO index, LUMO index, E_HOMO (eV), E_LUMO (eV),
  │                  broadening σ (eV) — all editable amber cells
  ├─ MO table     : 18 MOs — Index, Label, Occupancy, Energy (eV),
  │                  plus HOMO/LUMO/occ/virt flags (live IF formula)
  ├─ Summary panel: gap, χ (electronegativity), η (hardness), S (softness),
  │                 ω (electrophilicity) — live formulas referencing inputs
  ├─ DOS grid     : fixed energy axis (cols J/K), Gaussian-broadened DOS
  │                 per row via formula summing EXP terms over frontier MOs
  ├─ Chart        : DOS vs energy (line, live data-bound)
  ├─ LaTeX        : DOS formula + descriptor definitions
  └─ Notes        : pedagogic sticky notes

Saved to:
  examples/templates/Analysis/Quantum Chemistry DFT.ksheet

Run:
  python examples/build_tpl_dft_quantum_chem.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys
import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from examples.ksheet_author import Workbook, Series, PALETTE  # noqa: E402

# ── Realistic MO data (B3LYP/6-311G*-style for a small aromatic) ──────────
# 18 MOs: 8 doubly occupied (occ=2), 10 virtual (occ=0).
# Energies in eV.  HOMO = MO 8 (1-based), LUMO = MO 9.
MO_DATA = [
    # (1-based idx, label,   energy_eV,  occupancy)
    ( 1,  "1a1g",  -285.20,  2),
    ( 2,  "1a2u",   -37.45,  2),
    ( 3,  "2a1g",   -23.80,  2),
    ( 4,  "1b1u",   -19.62,  2),
    ( 5,  "1eg",    -14.31,  2),
    ( 6,  "2a2u",   -11.74,  2),
    ( 7,  "2b1u",    -9.18,  2),
    ( 8,  "1b2g",    -6.43,  2),   # HOMO
    ( 9,  "3a1g",    -1.75,  0),   # LUMO
    (10,  "1b3g",     0.82,  0),
    (11,  "2eg",      1.94,  0),
    (12,  "3b1u",     3.15,  0),
    (13,  "2b2g",     3.87,  0),
    (14,  "4a1g",     4.62,  0),
    (15,  "3a2u",     5.41,  0),
    (16,  "3eg",      6.78,  0),
    (17,  "4b1u",     8.23,  0),
    (18,  "5a1g",    10.05,  0),
]
N_MO = len(MO_DATA)         # 18

HOMO_IDX_DEFAULT   = 8      # 1-based
LUMO_IDX_DEFAULT   = 9      # 1-based
HOMO_E_DEFAULT     = -6.43  # eV
LUMO_E_DEFAULT     = -1.75  # eV
SIGMA_DEFAULT      = 0.3    # Gaussian broadening (eV)

# Frontier MOs included in the DOS sum (1-based indices 4 through 15)
DOS_MO_FIRST = 4
DOS_MO_LAST  = 15

# DOS energy grid: fixed literals, −18 to +12 eV, 121 points
DOS_EMIN = -18.0
DOS_EMAX =  12.0
DOS_NPTS = 121
dos_e_arr = np.linspace(DOS_EMIN, DOS_EMAX, DOS_NPTS)

# Pre-compute DOS at default sigma for chart first-render
sigma_def = SIGMA_DEFAULT
dos_y_arr = np.zeros(DOS_NPTS)
for idx, lbl, e_ev, occ in MO_DATA[DOS_MO_FIRST - 1: DOS_MO_LAST]:
    w = 2.0 if occ == 2 else 1.0   # virtual MOs weight 1
    dos_y_arr += w * np.exp(-((dos_e_arr - e_ev) ** 2) / (2.0 * sigma_def ** 2))


def build() -> str:
    wb = Workbook(min_rows=60, min_cols=16)
    s = wb.add_sheet("MO Results")

    # ── Column widths ──────────────────────────────────────────────────────
    s.col_width(0, 70)    # MO index
    s.col_width(1, 80)    # MO label
    s.col_width(2, 80)    # Occupancy
    s.col_width(3, 120)   # Energy (eV)
    s.col_width(4, 80)    # Type flag
    s.col_width(5, 20)    # spacer
    s.col_width(6, 220)   # input / summary labels
    s.col_width(7, 110)   # input / summary values
    s.col_width(8, 20)    # spacer
    s.col_width(9, 110)   # DOS energy grid
    s.col_width(10, 110)  # DOS values

    # ── Title block ────────────────────────────────────────────────────────
    s.title_block(
        "Quantum Chemistry — DFT Molecular Orbital Results",
        "B3LYP/6-311G*  ·  Kohn-Sham MO energies and density of states",
        span=10,
    )

    # ── Input panel ───────────────────────────────────────────────────────
    # Layout (0-based rows):
    #   Row 3: "Inputs" heading
    #   Row 4: HOMO index       → B5  (col 1, 1-based row 5)
    #   Row 5: LUMO index       → B6
    #   Row 6: E_HOMO (eV)      → B7  ← key input for summary formulas
    #   Row 7: E_LUMO (eV)      → B8
    #   Row 8: σ broadening     → B9

    s.set(3, 0, "Inputs")
    s.fmt(3, 0, bold=True, font_size=11, font_color=PALETTE["accent"])

    input_rows = [
        (4, "HOMO index  (MO #, 1-based)",       HOMO_IDX_DEFAULT,  "0",      True),
        (5, "LUMO index  (MO #, 1-based)",        LUMO_IDX_DEFAULT,  "0",      True),
        (6, "E_HOMO  (eV)",                       HOMO_E_DEFAULT,    "0.00",   True),
        (7, "E_LUMO  (eV)",                       LUMO_E_DEFAULT,    "0.00",   True),
        (8, "DOS broadening  σ  (eV)",            SIGMA_DEFAULT,     "0.000",  True),
    ]
    for r, lbl, val, fmt, editable in input_rows:
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, align="left")
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format=fmt)

    s.box(4, 0, 8, 1, color=PALETTE["accent"], width=1.2)

    s.note(4, 1,
           "HOMO / LUMO index: 1-based MO number.  "
           "These drive the Type flag column in the MO table.",
           kind="note")
    s.note(6, 1,
           "Enter the HOMO and LUMO energies from your DFT output (in eV).  "
           "Editing these cells instantly updates gap, χ, η, S, and ω.",
           kind="note")
    s.note(8, 1,
           "σ (sigma): Gaussian peak width for the DOS plot.  "
           "Typical range 0.1–0.5 eV.  Larger σ smooths the spectrum.",
           kind="note")

    # ── MO table ──────────────────────────────────────────────────────────
    # Header at 0-based row MO_TABLE_START → sheet row MO_TABLE_START+1
    # First data row (0-based) = MO_TABLE_START+1 → sheet row MO_TABLE_START+2
    #
    # Columns (0-based from start_col=0):
    #   A (0): MO #
    #   B (1): Label
    #   C (2): Occ.
    #   D (3): Energy (eV)
    #   E (4): Type flag (HOMO/LUMO/occ/virt)
    #
    # Absolute input refs: $B$5 = HOMO index, $B$6 = LUMO index

    MO_TABLE_START = 11   # 0-based; header → sheet row 12
    # First data 1-based sheet row = MO_TABLE_START + 2 = 13

    s.set(10, 0, "Kohn-Sham Molecular Orbital Energies")
    s.fmt(10, 0, bold=True, font_size=11, font_color=PALETTE["header"])
    s.merge(10, 0, 1, 5)

    mo_rows = []
    for i, (idx, lbl, e_ev, occ) in enumerate(MO_DATA):
        rr = MO_TABLE_START + 2 + i   # 1-based sheet row for this data row = 13, 14, ...
        # Type flag formula: IF(A{rr}==$B$5, "HOMO", IF(A{rr}==$B$6, "LUMO",
        #                       IF(C{rr}==2, "occ", IF(C{rr}==1, "SOMO", "virt"))))
        flag = (
            f"=IF(A{rr}==$B$5,\"HOMO\","
            f"IF(A{rr}==$B$6,\"LUMO\","
            f"IF(C{rr}==2,\"occ\",IF(C{rr}==1,\"SOMO\",\"virt\"))))"
        )
        mo_rows.append([idx, lbl, occ, e_ev, flag])

    s.table(
        MO_TABLE_START, 0,
        headers=["MO #", "Label", "Occ.", "Energy (eV)", "Type"],
        rows=mo_rows,
        number_format="0.00",
        banded=True,
    )

    # Per-cell overrides: index/occupancy as integers, label left-aligned, type centred
    for i, (idx, lbl, e_ev, occ) in enumerate(MO_DATA):
        r = MO_TABLE_START + 1 + i
        s.fmt(r, 0, number_format="0", align="center")
        s.fmt(r, 1, align="left")
        s.fmt(r, 2, number_format="0", align="center")
        s.fmt(r, 4, align="center")

    # Colour the Type flag cell: green=HOMO, amber=LUMO, light=occ, plain=virt
    for i, (idx, lbl, e_ev, occ) in enumerate(MO_DATA):
        r = MO_TABLE_START + 1 + i
        if idx == HOMO_IDX_DEFAULT:
            s.fmt(r, 4, bg=PALETTE["good"],  bold=True, font_color="#155724")
        elif idx == LUMO_IDX_DEFAULT:
            s.fmt(r, 4, bg=PALETTE["warn"],  bold=True, font_color="#856404")
        elif occ == 2:
            s.fmt(r, 4, bg=PALETTE["band_alt"])
        # virtuals: no extra colour

    s.designate(3, "Y")   # energy column — axis hint

    # ── Summary panel ─────────────────────────────────────────────────────
    # Lives in columns 6–7 (G–H), rows 3–12 (0-based).
    # All formulas reference $B$7 (E_HOMO) and $B$8 (E_LUMO).
    #
    # Absolute refs:
    #   E_HOMO = $B$7  (row 6, col 1 → 1-based row 7, col B)
    #   E_LUMO = $B$8  (row 7, col 1 → 1-based row 8, col B)

    SUMM_LBL = 6   # col G (0-based)
    SUMM_VAL = 7   # col H (0-based)

    s.set(3, SUMM_LBL, "Summary — Frontier Orbital Descriptors")
    s.fmt(3, SUMM_LBL, bold=True, font_size=11, font_color=PALETTE["header"])
    s.merge(3, SUMM_LBL, 1, 2)

    # Row 4 — E_HOMO (mirrors input $B$7)
    s.set(4, SUMM_LBL, "E_HOMO  (eV)")
    s.formula(4, SUMM_VAL, "=$B$7")
    s.fmt(4, SUMM_LBL, align="left")
    s.fmt(4, SUMM_VAL, bg=PALETTE["good"], bold=True, align="center",
          number_format="0.00", font_color="#155724")

    # Row 5 — E_LUMO (mirrors input $B$8)
    s.set(5, SUMM_LBL, "E_LUMO  (eV)")
    s.formula(5, SUMM_VAL, "=$B$8")
    s.fmt(5, SUMM_LBL, align="left")
    s.fmt(5, SUMM_VAL, bg=PALETTE["warn"], bold=True, align="center",
          number_format="0.00", font_color="#856404")

    # Row 6 — HOMO-LUMO gap = E_LUMO - E_HOMO
    s.set(6, SUMM_LBL, "HOMO-LUMO gap  Δ  (eV)")
    s.formula(6, SUMM_VAL, "=$B$8-$B$7")
    s.fmt(6, SUMM_LBL, align="left")
    s.fmt(6, SUMM_VAL, bg=PALETTE["band"], bold=True, align="center",
          number_format="0.00")

    # Row 7 — blank spacer
    s.set(7, SUMM_LBL, "")

    # Row 8 — electronegativity  χ = −(E_HOMO + E_LUMO) / 2
    s.set(8, SUMM_LBL, "Electronegativity  χ = −(E_H+E_L)/2  (eV)")
    s.formula(8, SUMM_VAL, "=-($B$7+$B$8)/2")
    s.fmt(8, SUMM_LBL, align="left")
    s.fmt(8, SUMM_VAL, bg=PALETTE["band_alt"], bold=True, align="center",
          number_format="0.00")

    # Row 9 — chemical hardness  η = (E_LUMO - E_HOMO) / 2
    s.set(9, SUMM_LBL, "Chemical hardness  η = Δ/2  (eV)")
    s.formula(9, SUMM_VAL, "=($B$8-$B$7)/2")
    s.fmt(9, SUMM_LBL, align="left")
    s.fmt(9, SUMM_VAL, bg=PALETTE["band_alt"], bold=True, align="center",
          number_format="0.00")

    # Row 10 — chemical softness  S = 1 / (2η)
    # η is in H10 (row 9, col 7) — but reference $B$7/$B$8 directly to avoid chain
    s.set(10, SUMM_LBL, "Chemical softness  S = 1/(2η)  (eV⁻¹)")
    s.formula(10, SUMM_VAL, "=2/($B$8-$B$7)")
    s.fmt(10, SUMM_LBL, align="left")
    s.fmt(10, SUMM_VAL, bg=PALETTE["band_alt"], bold=True, align="center",
          number_format="0.000")

    # Row 11 — electrophilicity  ω = χ² / (2η)
    s.set(11, SUMM_LBL, "Electrophilicity  ω = χ²/(2η)  (eV)")
    s.formula(11, SUMM_VAL, "=(($B$7+$B$8)/2)*(($B$7+$B$8)/2)/($B$8-$B$7)")
    s.fmt(11, SUMM_LBL, align="left")
    s.fmt(11, SUMM_VAL, bg=PALETTE["band_alt"], bold=True, align="center",
          number_format="0.00")

    s.box(4, SUMM_LBL, 11, SUMM_VAL, color=PALETTE["header"], width=1.2)

    s.note(6, SUMM_VAL,
           "HOMO-LUMO gap (Δ): larger gap → kinetically more stable / less reactive.  "
           "Organic semiconductors: 1–4 eV; insulators: > 5 eV.",
           kind="note")
    s.note(8, SUMM_LBL,
           "Koopmans descriptors (Parr-Yang DFT):  "
           "χ approximates the ionisation potential.  "
           "η measures resistance to charge transfer.  "
           "ω quantifies electrophilic power.",
           kind="note")

    # ── DOS grid ──────────────────────────────────────────────────────────
    # Energy grid column J (col 9), DOS column K (col 10).
    # DOS header at row DOS_TABLE_START (0-based).
    # First data row (0-based) = DOS_TABLE_START + 1.
    # 1-based first data row = DOS_TABLE_START + 2.
    #
    # DOS formula per row:
    #   = sum over MOs DOS_MO_FIRST..DOS_MO_LAST of
    #     w_i * EXP(-((J{rr} - D{mo_row})*(J{rr} - D{mo_row})) / (2*$B$9*$B$9))
    # where:
    #   J{rr}   = grid energy (column J, this row)
    #   D{mo_row} = MO energy in column D for MO number mo_idx
    #               → sheet row = MO_TABLE_START + 1 + mo_idx (0-based data row)
    #                            = MO_TABLE_START + 2 + (mo_idx - 1) (1-based)
    #   $B$9    = σ (row 8, col 1 → sheet row 9)
    #   w_i     = 2 for occupied MOs, 1 for virtual MOs (literal in formula)
    #
    # MO_TABLE_START = 11, header at row 11 (0-based) = sheet row 12.
    # Data MO 1 at 0-based row 12 = sheet row 13.
    # Data MO k at 0-based row 11+k = sheet row 12+k.
    # e.g. MO 4 (DOS_MO_FIRST): sheet row = 12 + 4 = 16  → D16
    #      MO 15 (DOS_MO_LAST):  sheet row = 12 + 15 = 27 → D27

    DOS_TABLE_START = 11   # same row as MO table start — cols J/K are free

    # Pre-compute MO energies' 1-based sheet rows
    mo_sheet_rows_1b = {}
    for idx, lbl, e_ev, occ in MO_DATA:
        mo_sheet_rows_1b[idx] = MO_TABLE_START + 1 + idx   # = 12+idx

    mo_weights = {idx: (2 if occ == 2 else 1) for idx, lbl, e_ev, occ in MO_DATA}

    # Header
    s.set(DOS_TABLE_START, 9, "Energy (eV)")
    s.fmt(DOS_TABLE_START, 9, bold=True, bg=PALETTE["header"],
          font_color=PALETTE["header_text"], align="center")
    s.set(DOS_TABLE_START, 10, "DOS (arb. units)")
    s.fmt(DOS_TABLE_START, 10, bold=True, bg=PALETTE["header"],
          font_color=PALETTE["header_text"], align="center")
    s.box(DOS_TABLE_START, 9, DOS_TABLE_START + DOS_NPTS, 10,
          color=PALETTE["header"], width=1.0)

    # Data rows
    for k in range(DOS_NPTS):
        r0 = DOS_TABLE_START + 1 + k       # 0-based sheet row
        rr = DOS_TABLE_START + 2 + k       # 1-based sheet row
        e_grid = round(float(dos_e_arr[k]), 4)
        s.set(r0, 9, e_grid)
        band_bg = PALETTE["band_alt"] if k % 2 else None
        s.fmt(r0, 9, number_format="0.00", bg=band_bg, align="right")

        # Build the DOS formula string.
        # Sigma ref: $B$9 (row 8, col 1 → 1-based row 9).
        terms = []
        for mo_idx in range(DOS_MO_FIRST, DOS_MO_LAST + 1):
            mo_sr = mo_sheet_rows_1b[mo_idx]   # e.g. 16 for MO 4
            w = mo_weights[mo_idx]
            # Use (J{rr}-$D${mo_sr})^2 written as product to avoid ^ ambiguity
            diff = f"(J{rr}-$D${mo_sr})"
            terms.append(
                f"{w}*EXP(-{diff}*{diff}/(2*$B$9*$B$9))"
            )
        dos_formula = "=" + "+".join(terms)
        s.formula(r0, 10, dos_formula)
        s.fmt(r0, 10, number_format="0.0000", bg=band_bg, align="right")

    s.designate(9, "X")
    s.designate(10, "Y")

    s.note(DOS_TABLE_START, 10,
           "DOS = Gaussian-broadened sum over MOs 4–15.  "
           "Peak height is weighted by occupancy (occ=2 → weight 2; virtual → weight 1).  "
           "Edit σ in cell B9 to change peak width.",
           kind="note")

    # ── Chart: DOS vs Energy ───────────────────────────────────────────────
    r_start_dos = DOS_TABLE_START + 1
    r_end_dos   = DOS_TABLE_START + DOS_NPTS

    s.chart(
        [Series(
            x=dos_e_arr,
            y=dos_y_arr,
            label="DOS",
            plot_type="Line",
            color=PALETTE["header"],
            linewidth=2.0,
            x_col=9,
            y_col=10,
            row_start=r_start_dos,
            row_end=r_end_dos,
        )],
        at=(560, 20),
        size=(460, 320),
        title="Density of States (Gaussian broadening)",
        xlabel="Energy (eV)",
        ylabel="DOS (arb. units)",
        grid=True,
        legend=True,
    )

    # ── LaTeX equations ────────────────────────────────────────────────────
    # Gaussian DOS formula
    s.equation(
        r"g(E) = \sum_{i} w_i \exp\!\left(-\frac{(E - \varepsilon_i)^2}{2\sigma^2}\right)",
        at=(560, 360),
        fontsize=18,
        color="#1a1a1a",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.4,
        size=(420, 58),
    )

    # Descriptors
    s.equation(
        r"\chi = -\frac{E_{H}+E_{L}}{2}, \quad \eta = \frac{E_{L}-E_{H}}{2}",
        at=(560, 440),
        fontsize=17,
        color="#1a1a1a",
        bg_color="#ffffff",
        border_color=PALETTE["accent"],
        border_width=1.2,
        size=(420, 52),
    )

    # ── Save ──────────────────────────────────────────────────────────────
    out = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "templates", "Analysis", "Quantum Chemistry DFT.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
