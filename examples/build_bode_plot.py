"""Build the "Bode Plot" Python-cell example .ksheet.

RC low-pass filter: magnitude response |H(jω)| in dB vs log-frequency.
Inputs R and C are in cells; =PY reads them and draws the Bode plot.

Run:  python examples/build_bode_plot.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "examples"))

from ksheet_author import Workbook, PALETTE

OUTPUT = os.path.join(
    _REPO, "examples", "python", "Engineering", "Bode Plot.ksheet"
)


def build() -> str:
    wb = Workbook(min_rows=40, min_cols=14)
    s = wb.add_sheet("Bode Plot")

    # Title
    s.title_block(
        "Bode Plot — RC Low-Pass Filter",
        "Magnitude response |H(jω)| in dB vs frequency — edit R and C, press Ctrl+Enter",
    )

    # Input parameters
    s.set(3, 0, "Parameters")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    params = [
        ("Resistance  R (Ω)", 1000.0),
        ("Capacitance  C (µF)", 10.0),
    ]
    for i, (lbl, val) in enumerate(params):
        r = 4 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.##")

    s.box(4, 0, 5, 1, color=PALETTE["accent"], width=1.5)
    s.col_width(0, 220)
    s.col_width(1, 110)

    s.note(4, 1,
           "RC low-pass filter:  H(jω) = 1 / (1 + jωRC).\n"
           "C is entered in µF; −3 dB corner is at f_c = 1/(2πRC).",
           kind="note")

    # Derived: corner frequency fc
    s.set(7, 0, "Corner frequency  fc (Hz)")
    s.fmt(7, 0, bold=True)
    s.formula(
        7, 1,
        "=PY\n"
        "import numpy as np\n"
        "R = ks('B5')\n"
        "C_uF = ks('B6')\n"
        "C_F = C_uF * 1e-6\n"
        "fc = 1.0 / (2 * np.pi * R * C_F)\n"
        "round(fc, 4)\n"
    )
    s.fmt(7, 1, bg=PALETTE["good"], bold=True, align="center", number_format="0.0000")
    s.box(7, 0, 7, 1, color=PALETTE["header"], width=1.5)

    # Gain at 10× corner
    s.set(8, 0, "Gain at 10·fc (dB, expect ≈ −20)")
    s.fmt(8, 0, bold=True)
    s.formula(
        8, 1,
        "=PY\n"
        "import numpy as np\n"
        "R = ks('B5')\n"
        "C_uF = ks('B6')\n"
        "C_F = C_uF * 1e-6\n"
        "fc = 1.0 / (2 * np.pi * R * C_F)\n"
        "f_test = 10 * fc\n"
        "omega_test = 2 * np.pi * f_test\n"
        "mag_dB = 20 * np.log10(1.0 / np.sqrt(1 + (omega_test * R * C_F)**2))\n"
        "round(mag_dB, 2)\n"
    )
    s.fmt(8, 1, bg=PALETTE["band"], bold=True, align="center", number_format="0.00")
    s.box(8, 0, 8, 1, color=PALETTE["header"], width=1.5)

    # Instruction row
    s.set(10, 0, "Bode magnitude plot  (=PY cell — press Ctrl+Enter to refresh)")
    s.fmt(10, 0, bold=True, font_color=PALETTE["header"])

    # =PY plot cell
    py_code = (
        "=PY\n"
        "import numpy as np, matplotlib.pyplot as plt\n"
        "R    = ks('B5')\n"
        "C_uF = ks('B6')\n"
        "C_F  = C_uF * 1e-6\n"
        "fc   = 1.0 / (2 * np.pi * R * C_F)\n"
        "# frequency range: 3 decades either side of fc\n"
        "f    = np.logspace(np.log10(fc) - 3, np.log10(fc) + 3, 600)\n"
        "omega = 2 * np.pi * f\n"
        "H_mag = 1.0 / np.sqrt(1 + (omega * R * C_F)**2)\n"
        "H_dB  = 20 * np.log10(H_mag)\n"
        "fig, ax = plt.subplots(figsize=(7, 4))\n"
        "ax.semilogx(f, H_dB, color='#4472c4', linewidth=2.5, label='|H(jω)| dB')\n"
        "ax.axvline(fc, color='#ed7d31', linestyle='--', linewidth=1.5,\n"
        "           label=f'fc = {fc:.2f} Hz  (−3 dB)')\n"
        "ax.axhline(-3, color='#70ad47', linestyle=':', linewidth=1.2, label='−3 dB')\n"
        "ax.set_xlabel('Frequency  f (Hz)')\n"
        "ax.set_ylabel('Magnitude  (dB)')\n"
        "ax.set_title('RC Low-Pass Filter — Bode Magnitude')\n"
        "ax.legend()\n"
        "ax.grid(True, which='both', linestyle='--', alpha=0.4)\n"
        "plt.tight_layout()\n"
        "plt.gcf()"
    )
    s.formula(11, 0, py_code)
    s.fmt(11, 0, bg="#f0f4ff", font_family="Consolas", font_size=9)

    s.note(11, 0,
           "The slope above fc rolls off at −20 dB/decade (first-order filter). "
           "Increase C or R to shift fc lower.",
           kind="note")

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    wb.save(OUTPUT)
    return OUTPUT


if __name__ == "__main__":
    print("Wrote", build())
