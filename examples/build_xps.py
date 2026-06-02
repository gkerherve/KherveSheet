"""Build the "XPS Spectrum" demo .ksheet example.

X-ray Photoelectron Spectroscopy (XPS) — synthetic high-resolution spectrum
showing the photoemission relation (KE = hν − BE − φ) and Gaussian core-level
peaks on a linear background.  Demonstrates live-bound charts, LaTeX equations,
an inputs panel, a banded data table with absolute cell references, and sticky
notes teaching the user what to edit.

Run:  python examples/build_xps.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import numpy as np
from ksheet_author import Workbook, Series, PALETTE

# ── Physical / experimental parameters ───────────────────────────────────────
HV       = 1486.6   # photon energy Al Kα (eV)
PHI      = 4.5      # analyser work function (eV)

# Background (linear): intensity = bg0 + bg_slope * BE
BG0      = 800.0    # intercept (counts)
BG_SLOPE = 0.3      # slope (counts/eV) — rises gently at high BE

# Peaks: (label, BE_i eV, FWHM_i eV, Amplitude counts)
PEAKS = [
    ("C 1s",      284.8, 1.2, 12000.0),
    ("C-O (sh.)", 286.5, 1.5,  2800.0),
    ("O 1s",      531.5, 1.8,  7500.0),
]

# BE grid: 280 – 540 eV in 0.5 eV steps
BE_MIN, BE_MAX, BE_STEP = 280.0, 540.0, 0.5
be = np.arange(BE_MIN, BE_MAX + BE_STEP * 0.5, BE_STEP)
N = len(be)   # 521 data rows


def gauss(be_arr, be_i, fwhm_i, amp_i):
    """Gaussian: A * exp(-4*ln2*((BE - BE_i)/FWHM_i)^2)."""
    return amp_i * np.exp(-4.0 * np.log(2.0) * ((be_arr - be_i) / fwhm_i) ** 2)


# Numpy arrays for chart initial render (must match what the formulas produce)
bg    = BG0 + BG_SLOPE * be
c1s   = gauss(be, *PEAKS[0][1:])
co    = gauss(be, *PEAKS[1][1:])
o1s   = gauss(be, *PEAKS[2][1:])
total = bg + c1s + co + o1s
ke    = HV - be - PHI

# ── Sheet layout (all row indices 0-based) ────────────────────────────────────
#
# Row 0:  Title
# Row 1:  Subtitle
# Row 3:  "Source & Analyser" label
# Row 4:  "Photon energy hν (eV)"  |  B5=1486.6   ← $B$5 in formulas
# Row 5:  "Work function φ (eV)"   |  B6=4.5       ← $B$6 in formulas
# Row 7:  "Background parameters" label
# Row 8:  "bg₀ offset (counts)"    |  B9=800       ← $B$9 in formulas
# Row 9:  "bg slope (counts/eV)"   |  B10=0.3      ← $B$10 in formulas
# Row 11: "Core-Level Peaks" label
# Row 12: Peak table header
# Row 13: C 1s       | B14=284.8 | C14=1.2 | D14=12000  ← $B$14,$C$14,$D$14
# Row 14: C-O (sh.)  | B15=286.5 | C15=1.5 | D15=2800   ← $B$15,$C$15,$D$15
# Row 15: O 1s       | B16=531.5 | C16=1.8 | D16=7500   ← $B$16,$C$16,$D$16
# Row 17: Section label "Spectrum data…"
# Row 18: Table header  (DATA_START = 18)
# Row 19: First data row (DATA_ROW0 = 19, 1-based = 20)
# ...
# Row 19+N-1 = 539: Last data row

DATA_START    = 18          # 0-based row of table header
DATA_ROW0     = DATA_START + 1   # 0-based first data row = 19
DATA_ROW0_1   = DATA_ROW0 + 1   # 1-based first data row = 20

# ── 1-based cell refs used in formulas ───────────────────────────────────────
REF_HV    = "$B$5"
REF_PHI   = "$B$6"
REF_BG0   = "$B$9"
REF_BGS   = "$B$10"
# Peak params: BE at col B (1), FWHM at col C (2), Amp at col D (3)
# Peak rows (1-based): C 1s=14, C-O=15, O 1s=16
PEAK_REF = [
    ("$B$14", "$C$14", "$D$14"),
    ("$B$15", "$C$15", "$D$15"),
    ("$B$16", "$C$16", "$D$16"),
]


def build() -> str:
    wb = Workbook(min_rows=max(N + DATA_START + 6, 60), min_cols=14)
    s = wb.add_sheet("XPS Spectrum")

    # ── Column widths ─────────────────────────────────────────────────────
    s.col_width(0, 130)   # labels / BE values
    s.col_width(1, 95)    # values / Background
    s.col_width(2, 90)    # C 1s
    s.col_width(3, 90)    # C-O (sh.)
    s.col_width(4, 90)    # O 1s
    s.col_width(5, 110)   # Total Intensity
    s.col_width(6, 90)    # KE (eV)
    s.col_width(7, 20)    # spacer
    s.col_width(8, 185)   # summary labels
    s.col_width(9, 115)   # summary values

    # ── Title block ───────────────────────────────────────────────────────
    s.title_block(
        "XPS Spectrum",
        "Synthetic high-resolution X-ray Photoelectron Spectroscopy "
        "(Al Kα source, hν = 1486.6 eV)",
        span=9,
    )

    # ── Input panel: photon energy & work function ─────────────────────
    # Rows 3-5 (0-based); values land at B5 = row 4 col 1, B6 = row 5 col 1
    s.set(3, 0, "Source & Analyser")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])
    s.merge(3, 0, 1, 3)

    src_inputs = [
        ("Photon energy hν (eV)", HV),    # row 4 → sheet row 5 → B5
        ("Work function φ (eV)",  PHI),   # row 5 → sheet row 6 → B6
    ]
    for i, (lbl, val) in enumerate(src_inputs):
        r = 4 + i
        s.set(r, 0, lbl);  s.fmt(r, 0, align="left")
        s.set(r, 1, val);  s.fmt(r, 1, bg=PALETTE["warn"], align="center",
                                  number_format="0.0")
    s.box(4, 0, 5, 1, color=PALETTE["accent"], width=1.2)

    # ── Input panel: background ───────────────────────────────────────────
    # Rows 7-9 (0-based); bg0 at row 8 col 1 → B9, slope at row 9 col 1 → B10
    s.set(7, 0, "Background (linear)")
    s.fmt(7, 0, bold=True, font_color=PALETTE["accent"])
    s.merge(7, 0, 1, 3)

    bg_inputs = [
        ("bg₀  offset (counts)",     BG0),     # row 8 → B9
        ("bg slope (counts / eV)",        BG_SLOPE),# row 9 → B10
    ]
    for i, (lbl, val) in enumerate(bg_inputs):
        r = 8 + i
        s.set(r, 0, lbl);  s.fmt(r, 0, align="left")
        s.set(r, 1, val);  s.fmt(r, 1, bg=PALETTE["warn"], align="center",
                                  number_format="0.00")
    s.box(8, 0, 9, 1, color=PALETTE["accent"], width=1.2)

    # ── Peak parameters table ─────────────────────────────────────────────
    # Header at row 12 (0-based) → sheet row 13
    # Peak data rows 13-15 (0-based) → sheet rows 14-16 → B14/C14/D14 etc.
    s.set(11, 0, "Core-Level Peaks  (edit BE, FWHM, Amplitude)")
    s.fmt(11, 0, bold=True, font_color=PALETTE["accent"])
    s.merge(11, 0, 1, 5)

    peak_hdr_row = 12   # 0-based
    peak_hdrs = ["Peak", "BEᵢ (eV)", "FWHMᵢ (eV)",
                 "Amplitude (counts)", "Data col."]
    for j, h in enumerate(peak_hdrs):
        s.set(peak_hdr_row, j, h)
        s.fmt(peak_hdr_row, j, bold=True, bg=PALETTE["header"],
              font_color=PALETTE["header_text"], align="center")

    data_col_labels = ["C (col 3)", "D (col 4)", "E (col 5)"]
    for i, ((lbl, be_i, fwhm_i, amp_i), dcol) in enumerate(
            zip(PEAKS, data_col_labels)):
        r = 13 + i   # 0-based rows 13, 14, 15 → 1-based 14, 15, 16
        band = PALETTE["band_alt"] if i % 2 else None
        bg_kw = {"bg": band} if band else {}
        s.set(r, 0, lbl);     s.fmt(r, 0, align="left", **bg_kw)
        s.set(r, 1, be_i);    s.fmt(r, 1, bg=PALETTE["warn"], align="center",
                                     number_format="0.0")
        s.set(r, 2, fwhm_i);  s.fmt(r, 2, bg=PALETTE["warn"], align="center",
                                     number_format="0.0")
        s.set(r, 3, amp_i);   s.fmt(r, 3, bg=PALETTE["warn"], align="center",
                                     number_format="0")
        s.set(r, 4, dcol);    s.fmt(r, 4, align="center", **bg_kw)
    s.box(peak_hdr_row, 0, 15, 4, color=PALETTE["header"], width=1.0)

    # ── Section divider ───────────────────────────────────────────────────
    s.set(DATA_START - 1, 0,
          "Spectrum data  (280 – 540 eV, 0.5 eV steps — edit inputs above)")
    s.fmt(DATA_START - 1, 0, bold=True, font_color=PALETTE["header"])
    s.merge(DATA_START - 1, 0, 1, 6)

    # ── Data table ────────────────────────────────────────────────────────
    # DATA_START=18 (0-based) → header at sheet row 19 (1-based)
    # DATA_ROW0=19 (0-based)  → first data row at sheet row 20 (1-based)
    # DATA_ROW0_1=20 = 1-based first data row
    #
    # Columns (0-based index → 1-based letter):
    #   0=A BE, 1=B Background, 2=C C1s, 3=D C-O, 4=E O1s, 5=F Total, 6=G KE
    #
    # Refs used:
    #   hν  = $B$5   (row 4 col 1)
    #   φ   = $B$6   (row 5 col 1)
    #   bg0 = $B$9   (row 8 col 1)
    #   bgs = $B$10  (row 9 col 1)
    #   C1s: BE=$B$14, FWHM=$C$14, Amp=$D$14
    #   CO:  BE=$B$15, FWHM=$C$15, Amp=$D$15
    #   O1s: BE=$B$16, FWHM=$C$16, Amp=$D$16

    table_rows = []
    for k in range(N):
        rr = DATA_ROW0_1 + k    # 1-based sheet row of this data row
        A = f"A{rr}"            # BE cell in this row

        bg_f   = f"=$B$9+$B$10*{A}"
        c1s_f  = f"=$D$14*EXP(-4*LN(2)*POWER(({A}-$B$14)/MAX($C$14,1E-9),2))"
        co_f   = f"=$D$15*EXP(-4*LN(2)*POWER(({A}-$B$15)/MAX($C$15,1E-9),2))"
        o1s_f  = f"=$D$16*EXP(-4*LN(2)*POWER(({A}-$B$16)/MAX($C$16,1E-9),2))"
        tot_f  = f"=B{rr}+C{rr}+D{rr}+E{rr}"
        ke_f   = f"=$B$5-{A}-$B$6"

        table_rows.append([
            round(float(be[k]), 1),  # BE literal
            bg_f,
            c1s_f,
            co_f,
            o1s_f,
            tot_f,
            ke_f,
        ])

    s.table(
        DATA_START, 0,
        headers=["BE (eV)", "Background", "C 1s", "C-O (sh.)", "O 1s",
                 "Total Intensity", "KE (eV)"],
        rows=table_rows,
        number_format="0.0",
        banded=True,
    )

    # Designate axes: column 0 = X (BE), column 5 = primary Y (Total),
    # column 1 = secondary Y (Background)
    s.designate(0, "X")
    s.designate(5, "Y")
    s.designate(1, "Y")

    # ── Summary panel ────────────────────────────────────────────────────
    # Placed at cols 8-9 (I-J), rows 3-11
    s.set(3, 8, "Summary")
    s.fmt(3, 8, bold=True, font_color=PALETTE["header"], font_size=12)
    s.merge(3, 8, 1, 2)

    # KE = hν − BE_peak − φ  using the editable peak cells
    summary_items = [
        ("KE  C 1s  (eV)",       "=$B$5-$B$14-$B$6",  PALETTE["good"]),
        ("KE  C-O sh. (eV)",     "=$B$5-$B$15-$B$6",  PALETTE["good"]),
        ("KE  O 1s  (eV)",       "=$B$5-$B$16-$B$6",  PALETTE["good"]),
        ("Amp  C 1s (counts)",   "=$D$14",             PALETTE["band"]),
        ("Amp  C-O  (counts)",   "=$D$15",             PALETTE["band"]),
        ("Amp  O 1s (counts)",   "=$D$16",             PALETTE["band"]),
        ("C 1s charge ref (eV)", "=$B$14",             PALETTE["warn"]),
    ]
    for i, (lbl, expr, col) in enumerate(summary_items):
        r = 4 + i
        s.set(r, 8, lbl);  s.fmt(r, 8, align="left")
        s.formula(r, 9, expr)
        s.fmt(r, 9, bg=col, align="center", number_format="0.0", bold=True)
    s.box(4, 8, 4 + len(summary_items) - 1, 9,
          color=PALETTE["header"], width=1.2)

    # ── Yellow sticky notes ───────────────────────────────────────────────
    s.note(
        DATA_START, 5,
        "XPS convention: binding energy INCREASES right-to-left on "
        "published spectra. This chart plots BE ascending (left-to-right). "
        "Reverse the X axis when preparing figures for publication.",
        kind="note",
    )
    s.note(
        13, 1,
        "C 1s at 284.8 eV is the universal charge reference for XPS. "
        "If the measured position shifts from 284.8 eV, apply an "
        "electrostatic correction to all other peak positions.",
        kind="note",
    )
    s.note(
        13, 3,
        "Chemical state shifts: oxidised C (C-O, C=O, O-C=O) shifts to "
        "higher BE by ~1.5 – 4 eV relative to the hydrocarbon C 1s. "
        "Edit the C-O shoulder BE and Amplitude to model surface oxidation.",
        kind="note",
    )

    # ── Live-bound chart ──────────────────────────────────────────────────
    # Data rows: 0-based DATA_ROW0 (19) .. DATA_ROW0+N-1 (539)
    # X = column 0 (BE), Y = column 5 (Total Intensity), Y2 = column 1 (BG)
    r0 = DATA_ROW0
    r1 = DATA_ROW0 + N - 1

    s.chart(
        [
            Series(
                be, total, "Total Intensity", "Line",
                color="#4472c4", linewidth=1.8,
                x_col=0, y_col=5, row_start=r0, row_end=r1,
            ),
            Series(
                be, bg, "Background", "Line",
                color="#ed7d31", linewidth=1.2, linestyle="--",
                x_col=0, y_col=1, row_start=r0, row_end=r1,
            ),
        ],
        at=(740, 30), size=(510, 340),
        title="XPS Spectrum — Al Kα (1486.6 eV)",
        xlabel="Binding Energy (eV)",
        ylabel="Intensity (counts)",
        grid=True, legend=True,
    )

    # ── LaTeX equations ───────────────────────────────────────────────────
    # Equation 1: photoemission relation
    s.equation(
        r"KE = h\nu - BE - \phi",
        at=(740, 390), fontsize=20,
        color="#1a1a1a",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.5,
        size=(240, 50),
    )

    # Equation 2: Gaussian peak lineshape
    s.equation(
        r"G_i(BE) = A_i \exp\!\left(-\frac{4\ln 2\,(BE-BE_i)^2}{FWHM_i^2}\right)",
        at=(740, 458), fontsize=16,
        color="#1a1a1a",
        bg_color="#ffffff",
        border_color=PALETTE["accent"],
        border_width=1.5,
        size=(490, 60),
    )

    # ── Save ──────────────────────────────────────────────────────────────
    out = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "XPS Spectrum.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
