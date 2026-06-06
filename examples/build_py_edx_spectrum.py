"""Build "EDX Spectrum.ksheet" — a Python-cell materials science example.

Energy (keV) vs counts spectrum with several characteristic peaks on a
falling bremsstrahlung background + noise.  The =PY cell finds peaks,
matches each to the nearest characteristic line within a tolerance,
labels them, spills an identified-elements table, and plots the spectrum
with element labels annotated.

Column / cell layout (0-based rows and cols → 1-based sheet refs):
  col A (0): Energy (keV)  — header A1 (row 0), data A2..AN (rows 1..N)
  col B (1): Counts        — header B1 (row 0), data B2..BN (rows 1..N)
  [spacer col C]
  col D (3): Labels for params/results
  col E (4): Parameter & result values
    E2 (row 1) = tolerance (keV)          → ks('E2')
    E3 (row 2) = min peak height (counts) → ks('E3')
    E4 (row 3) = peaks found (output, written by ks_set)
  [spacer col F]
  col G (6): Result table — Energy(keV)
  col H (7): Result table — Element
  col I (8): Result table — Line
  col J (9): Result table — Counts
  =PY cell: col K (10), row 10 — well clear of data A-B and results D-J

Run:  python examples/build_py_edx_spectrum.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "examples"))

from ksheet_author import Workbook, PALETTE  # noqa: E402


# ── Characteristic line energies (keV) ───────────────────────────────
CHAR_LINES = [
    ("C",  "Ka",  0.277),
    ("O",  "Ka",  0.525),
    ("Na", "Ka",  1.041),
    ("Si", "Ka",  1.740),
    ("Ti", "Ka",  4.508),
    ("Fe", "Ka",  6.404),
    ("Cu", "Ka",  8.048),
]

# ── Synthetic spectrum ────────────────────────────────────────────────
E_MIN, E_MAX, E_STEP = 0.10, 10.0, 0.05
energies = np.arange(E_MIN, E_MAX + E_STEP * 0.5, E_STEP)
N = len(energies)

rng = np.random.default_rng(2024)

brem_A, brem_decay = 3500.0, 1.8
background = brem_A * np.exp(-energies / brem_decay)

peak_params = {
    "C":  (4500.0, 0.14),
    "O":  (6200.0, 0.15),
    "Na": (2100.0, 0.16),
    "Si": (3800.0, 0.17),
    "Ti": (1400.0, 0.20),
    "Fe": (2800.0, 0.22),
    "Cu": (1600.0, 0.24),
}

def gaussian_peak(E, E0, amp, fwhm):
    sigma = fwhm / (2.0 * np.sqrt(2.0 * np.log(2.0)))
    return amp * np.exp(-0.5 * ((E - E0) / sigma) ** 2)

counts = background.copy()
for elem, line, E0 in CHAR_LINES:
    amp, fwhm = peak_params[elem]
    counts += gaussian_peak(energies, E0, amp, fwhm)

noise = rng.normal(0, np.sqrt(np.maximum(counts, 1)) * 0.05)
counts = np.maximum(counts + noise, 0.0).round(1)


# ── =PY cell body ─────────────────────────────────────────────────────
# Reads ks('E2') = tolerance (keV), ks('E3') = min peak height (counts)
# Writes to E4 (peaks found) and G5:J11 (result table)
PY_BODY = r"""import numpy as np, matplotlib.pyplot as plt
from scipy.signal import find_peaks

# --- read data from cells -------------------------------------------
E_raw = ks('A2:A2000')
C_raw = ks('B2:B2000')
E_raw = np.asarray(E_raw, dtype=float)
C_raw = np.asarray(C_raw, dtype=float)
mask = np.isfinite(E_raw) & np.isfinite(C_raw)
E = E_raw[mask]
C = C_raw[mask]

# --- read parameters (E2 = tolerance, E3 = min peak height) ---------
tol    = float(ks('E2'))
min_ht = float(ks('E3'))

# --- characteristic lines database ----------------------------------
char_lines = [
    ('C',  'Ka',  0.277),
    ('O',  'Ka',  0.525),
    ('Na', 'Ka',  1.041),
    ('Si', 'Ka',  1.740),
    ('Ti', 'Ka',  4.508),
    ('Fe', 'Ka',  6.404),
    ('Cu', 'Ka',  8.048),
]

# --- detect peaks ---------------------------------------------------
dE = float(E[1] - E[0]) if len(E) > 1 else 0.05
min_dist = max(1, int(0.3 / dE))
peak_idx, props = find_peaks(C, height=min_ht, distance=min_dist,
                             prominence=min_ht * 0.3)

# --- match to characteristic lines ----------------------------------
results = []
for i in peak_idx:
    E_pk = float(E[i])
    C_pk = float(C[i])
    best_dist, best_elem, best_line = 1e9, 'Unknown', '?'
    for el, ln, E0 in char_lines:
        d = abs(E_pk - E0)
        if d < best_dist:
            best_dist, best_elem, best_line = d, el, ln
    if best_dist <= tol:
        results.append((round(E_pk, 3), best_elem, best_line,
                        round(C_pk, 0)))

# --- write count of peaks to E4 (row 3, col E) ----------------------
n_found = len(results)
ks_set('E4', n_found)

# --- write results table to G5:J.. (starts at sheet row 5) ----------
# G5:J5 is the header row (written by the build script).
# Data goes from G6 (row 5, 0-based) onward.
if n_found:
    table_data = [[r[0], r[1], r[2], r[3]] for r in results]
    ks_set('G6', table_data)

# --- plot -----------------------------------------------------------
fig, ax = plt.subplots(figsize=(7.5, 4.8))
ax.plot(E, C, lw=1.4, color='#1f4e79', label='EDX spectrum')

for E_pk, elem, line, C_pk in results:
    ax.annotate(
        f'{elem} {line}',
        xy=(E_pk, C_pk),
        xytext=(0, 14), textcoords='offset points',
        ha='center', fontsize=8, color='#c00000',
        arrowprops=dict(arrowstyle='->', color='#c00000', lw=0.8),
    )
    ax.axvline(E_pk, color='#ed7d31', lw=0.7, alpha=0.45)

ax.set_xlabel('Energy (keV)')
ax.set_ylabel('Counts')
ax.set_title(f'EDX Spectrum  —  {n_found} peaks identified')
ax.set_xlim(E.min(), E.max())
ax.set_ylim(bottom=0)
ax.grid(True, alpha=0.28)
ax.legend(fontsize=9)
plt.tight_layout()
plt.gcf()"""


def build() -> str:
    wb = Workbook(min_rows=max(220, N + 10), min_cols=14)
    s = wb.add_sheet("EDX Spectrum")

    # ── Column widths ─────────────────────────────────────────────────
    s.col_width(0, 95)    # A: Energy (keV)
    s.col_width(1, 90)    # B: Counts
    s.col_width(2, 20)    # C: spacer
    s.col_width(3, 180)   # D: labels
    s.col_width(4, 110)   # E: param/result values
    s.col_width(5, 20)    # F: spacer
    s.col_width(6, 105)   # G: result table col 1 (Energy keV)
    s.col_width(7, 80)    # H: result table col 2 (Element)
    s.col_width(8, 60)    # I: result table col 3 (Line)
    s.col_width(9, 90)    # J: result table col 4 (Counts)
    s.col_width(10, 20)   # K: =PY cell col (spacer width)

    # ── Data column headers at row 0 (= A1, B1 in sheet notation) ─────
    # =PY reads A2:A2000 so header at row 0, data from row 1 (sheet A2)
    s.set(0, 0, "Energy (keV)")
    s.fmt(0, 0, bold=True, bg=PALETTE["header"],
          font_color=PALETTE["header_text"], align="center")
    s.set(0, 1, "Counts")
    s.fmt(0, 1, bold=True, bg=PALETTE["header"],
          font_color=PALETTE["header_text"], align="center")
    s.box(0, 0, N, 1, color=PALETTE["header"], width=1.0)

    # ── Title in cols D-J (rows 0-1, not overlapping data cols A-B) ───
    # Use row -1 is not possible; put title at rows 0-1 cols 3-9
    s.set(0, 3, "EDX Spectrum Analysis")
    s.fmt(0, 3, bold=True, font_size=16, font_color=PALETTE["header"])
    s.merge(0, 3, 1, 6)
    s.set(1, 3, "Energy-dispersive X-ray: automatic peak detection & element identification")
    s.fmt(1, 3, italic=True, font_color="#555555")
    s.merge(1, 3, 1, 6)

    # ── Write spectrum data (rows 1..N = sheet A2..A(N+1)) ────────────
    for i, (E, C) in enumerate(zip(energies, counts)):
        r = i + 1   # 0-based row 1 → sheet row 2 (A2)
        s.set(r, 0, round(float(E), 2))
        s.set(r, 1, round(float(C), 1))
        s.fmt(r, 0, align="right", number_format="0.00")
        s.fmt(r, 1, align="right", number_format="0.0")
        if i % 2 == 1:
            s.fmt(r, 0, bg=PALETTE["band_alt"])
            s.fmt(r, 1, bg=PALETTE["band_alt"])

    # ── Parameter panel (rows 1-3, cols D-E) ─────────────────────────
    # 0-based row 1 = sheet row 2; col E (4) is the value column
    # ks('E2') reads row 1 col 4  → s.set(1, 4, value)
    # ks('E3') reads row 2 col 4  → s.set(2, 4, value)
    # ks_set('E4', n) writes row 3 col 4 → s.set(3, 4, "") placeholder

    s.set(1, 3, "Matching tolerance (keV)")
    s.set(1, 4, 0.15)
    s.fmt(1, 3, bold=True)
    s.fmt(1, 4, bg=PALETTE["warn"], align="center", number_format="0.000")

    s.set(2, 3, "Min peak height (counts)")
    s.set(2, 4, 400.0)
    s.fmt(2, 3, bold=True)
    s.fmt(2, 4, bg=PALETTE["warn"], align="center", number_format="0.0")

    s.set(3, 3, "Peaks identified (output)")
    s.set(3, 4, "")   # filled by ks_set('E4', ...)
    s.fmt(3, 3, bold=True)
    s.fmt(3, 4, bg=PALETTE["good"], bold=True, align="center",
          number_format="0")

    s.box(1, 3, 3, 4, color=PALETTE["accent"], width=1.2)

    s.note(
        1, 4,
        "Edit matching tolerance (keV) or min peak height, then press "
        "Ctrl+Enter on the =PY cell (K11) to re-run the analysis.",
        kind="note",
    )

    # ── Results table header (row 4, cols G-J) ────────────────────────
    # Header at 0-based row 4 → sheet row 5 (G5:J5)
    # =PY writes data starting at ks_set('G6', ...) = row 5 (0-based), col 6
    result_headers = ["Energy (keV)", "Element", "Line", "Counts"]
    for j, h in enumerate(result_headers):
        s.set(4, 6 + j, h)
        s.fmt(4, 6 + j, bold=True, bg=PALETTE["header"],
              font_color=PALETTE["header_text"], align="center")

    # Pre-format the result rows (up to 7 peaks)
    for k in range(len(CHAR_LINES)):
        r = 5 + k  # 0-based row 5..11 → sheet rows 6..12
        s.fmt(r, 6, align="right", number_format="0.000")
        s.fmt(r, 7, align="center")
        s.fmt(r, 8, align="center")
        s.fmt(r, 9, align="right", number_format="0.0")
        if k % 2 == 1:
            s.fmt_range(r, 6, r, 9, bg=PALETTE["band_alt"])

    s.box(4, 6, 4 + len(CHAR_LINES), 9,
          color=PALETTE["header"], width=1.0)

    s.note(
        4, 6,
        "This table is filled by the =PY analysis cell. "
        "Each row shows one identified peak with its matched element line.",
        kind="note",
    )

    # ── =PY cell (row 10 = sheet row 11, col 10 = K) ─────────────────
    # K column (index 10) is well clear of data (A-B) and results (D-J)
    s.set(9, 3, "Analysis cell (K11) ▼")
    s.fmt(9, 3, bold=True, font_color=PALETTE["header"])
    s.formula(10, 10, "=PY\n" + PY_BODY)

    s.note(
        10, 10,
        "=PY cell: reads A/B columns (energy+counts), finds peaks with "
        "scipy.signal.find_peaks, matches to characteristic lines, writes "
        "the identified-elements table (G6:J12) and plots the spectrum.",
        kind="note",
    )

    # ── Sticky note on data column ────────────────────────────────────
    s.note(
        0, 0,
        f"Column A: energy grid {E_MIN}-{E_MAX} keV, step {E_STEP} keV. "
        "Column B: synthetic counts = bremsstrahlung (A·exp(-E/B)) + "
        "Gaussian peaks for C, O, Na, Si, Ti, Fe, Cu + 5% Poisson noise. "
        "Seed: np.random.default_rng(2024).",
        kind="note",
    )

    # ── LaTeX equation (Gaussian peak shape) ─────────────────────────
    s.equation(
        r"I(E) = A \exp\!\left(-\frac{(E-E_0)^2}{2\sigma^2}\right)",
        at=(560, 40), fontsize=17, color="#1a1a2e",
        bg_color="#f8f8ff", border_color=PALETTE["header"],
        border_width=1.2, size=(310, 54),
    )

    # ── Save ──────────────────────────────────────────────────────────
    out = os.path.join(
        _REPO, "examples", "python", "Materials Science",
        "EDX Spectrum.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
