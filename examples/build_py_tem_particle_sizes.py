"""Build "TEM Particle Sizes.ksheet" — a Python-cell materials science example.

A column of measured particle diameters (nm) drawn from a log-normal
population (seeded RNG).  The =PY cell plots a histogram, fits a
log-normal distribution (scipy.stats.lognorm), overlays the fitted PDF,
and writes back the count, mean, median, geometric mean and standard
deviation of the diameters.

Data layout:
  col 0 = A : Diameter (nm)   [literal, seeded data, header in A1]
  Parameters: C2 = target mean (nm), C3 = sigma (log-space)
  Results: written to E2:E6 by =PY via ks_set
  =PY cell: col 7 (H), row 9 — well clear of A-B data and C-F results

Run:  python examples/build_py_tem_particle_sizes.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "examples"))

from ksheet_author import Workbook, PALETTE  # noqa: E402


# ── Synthetic particle size data ──────────────────────────────────────
# Log-normal distribution: geometric mean 12 nm, sigma_log = 0.35
# n=200 particles (realistic TEM dataset)

N_PARTICLES = 200
GEOM_MEAN_NM = 12.0    # geometric mean diameter (nm)
SIGMA_LOG = 0.35       # log-space standard deviation

rng = np.random.default_rng(42)
diameters = rng.lognormal(
    mean=np.log(GEOM_MEAN_NM),
    sigma=SIGMA_LOG,
    size=N_PARTICLES,
)
diameters = np.sort(np.round(diameters, 2))


# ── =PY cell body ─────────────────────────────────────────────────────
PY_BODY = r"""import numpy as np, matplotlib.pyplot as plt
from scipy import stats

# --- read diameters from column A (header in A1, data A2:A...) ------
d_raw = ks('A2:A2000')
d_raw = np.asarray(d_raw, dtype=float)
d = d_raw[np.isfinite(d_raw)]

# --- compute statistics -------------------------------------------
n        = len(d)
mean_d   = float(np.mean(d))
median_d = float(np.median(d))
std_d    = float(np.std(d, ddof=1))
geom_mean = float(np.exp(np.mean(np.log(d[d > 0]))))

# --- fit log-normal distribution (scipy.stats.lognorm) ------------
# lognorm parameterisation: shape=sigma, loc=0, scale=exp(mu)
shape, loc, scale = stats.lognorm.fit(d, floc=0)
mu_fit    = float(np.log(scale))    # fitted log-mean
sigma_fit = float(shape)            # fitted log-sigma

# --- write statistics back to cells (E2:E6) -----------------------
ks_set('E2', n)
ks_set('E3', round(mean_d, 3))
ks_set('E4', round(median_d, 3))
ks_set('E5', round(geom_mean, 3))
ks_set('E6', round(std_d, 3))
ks_set('E7', round(sigma_fit, 4))

# --- plot: histogram + fitted PDF ---------------------------------
fig, ax = plt.subplots(figsize=(7, 4.8))

# Normalised histogram
bins = np.linspace(0, d.max() * 1.1, 30)
ax.hist(d, bins=bins, density=True, color='#4472c4', alpha=0.6,
        edgecolor='white', linewidth=0.5, label=f'Measured (n={n})')

# Fitted log-normal PDF
x_pdf = np.linspace(0.1, d.max() * 1.15, 400)
pdf = stats.lognorm.pdf(x_pdf, shape, loc=0, scale=scale)
ax.plot(x_pdf, pdf, '-', lw=2.2, color='#c00000',
        label=f'Log-normal fit\n$\\mu_{{ln}}$={mu_fit:.3f}, '
              f'$\\sigma_{{ln}}$={sigma_fit:.3f}')

# Vertical lines for mean, median, geometric mean
for val, lbl, clr in [(mean_d, 'mean', '#ed7d31'),
                       (median_d, 'median', '#2e9e44'),
                       (geom_mean, 'geom. mean', '#7030a0')]:
    ax.axvline(val, color=clr, lw=1.3, linestyle='--',
               label=f'{lbl} = {val:.1f} nm')

ax.set_xlabel('Particle diameter (nm)')
ax.set_ylabel('Probability density')
ax.set_title('TEM Particle Size Distribution — Log-normal Fit')
ax.legend(fontsize=8.5)
ax.grid(True, alpha=0.28)
plt.tight_layout()
plt.gcf()"""


def build() -> str:
    wb = Workbook(min_rows=max(N_PARTICLES + 10, 60), min_cols=14)
    s = wb.add_sheet("TEM Sizes")

    # ── Column widths ─────────────────────────────────────────────────
    s.col_width(0, 120)   # A: Diameter
    s.col_width(1, 20)    # B: spacer
    s.col_width(2, 180)   # C: param labels
    s.col_width(3, 20)    # D: spacer
    s.col_width(4, 120)   # E: results
    s.col_width(5, 20)    # F: spacer
    s.col_width(6, 20)    # G: spacer
    s.col_width(7, 20)    # H: =PY cell col

    # ── Title (rows 0 = title row; data header at row 0 col 0) ────────
    # Put title in cols 2-7, data header in A1/B1
    s.set(0, 2, "TEM Particle Sizes — Log-normal Analysis")
    s.fmt(0, 2, bold=True, font_size=16, font_color=PALETTE["header"])
    s.merge(0, 2, 1, 5)
    s.set(1, 2, "Measured diameters from TEM images fitted with scipy.stats.lognorm")
    s.fmt(1, 2, italic=True, font_color="#555555")
    s.merge(1, 2, 1, 5)

    # ── Data column header (row 0 col 0 = A1) ────────────────────────
    # =PY reads A2:A2000 so header at A1 (row 0 col 0), data from A2 (row 1 col 0)
    s.set(0, 0, "Diameter (nm)")
    s.fmt(0, 0, bold=True, bg=PALETTE["header"],
          font_color=PALETTE["header_text"], align="center")

    # ── Write particle diameter data (rows 1..N_PARTICLES) ────────────
    for i, d in enumerate(diameters):
        r = i + 1   # sheet row = r+1 = i+2
        s.set(r, 0, float(d))
        s.fmt(r, 0, align="right", number_format="0.00")
        if i % 2 == 1:
            s.fmt(r, 0, bg=PALETTE["band_alt"])

    s.box(0, 0, N_PARTICLES, 0, color=PALETTE["header"], width=1.0)

    # ── Parameter panel (rows 2-3, cols 2-4) ─────────────────────────
    # These are informational (the fit uses the data directly)
    s.set(2, 2, "Parameters")
    s.fmt(2, 2, bold=True, font_color=PALETTE["accent"], font_size=11)

    s.set(3, 2, "Seeded RNG seed")
    s.set(3, 4, 42)
    s.fmt(3, 2, bold=True)
    s.fmt(3, 4, bg=PALETTE["warn"], align="center", number_format="0")

    s.set(4, 2, "True log-mean ln(d) (nm)")
    s.set(4, 4, round(float(np.log(GEOM_MEAN_NM)), 4))
    s.fmt(4, 2, bold=True)
    s.fmt(4, 4, bg=PALETTE["band"], align="center", number_format="0.0000")

    s.set(5, 2, "True log-sigma")
    s.set(5, 4, SIGMA_LOG)
    s.fmt(5, 2, bold=True)
    s.fmt(5, 4, bg=PALETTE["band"], align="center", number_format="0.00")

    s.box(3, 2, 5, 4, color=PALETTE["accent"], width=1.2)

    # ── Results panel (rows 2-8, cols 2/4) labelled ───────────────────
    # Labels in col 2 (C), values in col 4 (E) — filled by ks_set
    result_labels = [
        (2, 2, "Statistics (output)"),  # header
        (2, 4, "Count"),
        (3, 4, "Mean diameter (nm)"),
        (4, 4, "Median diameter (nm)"),
        (5, 4, "Geometric mean (nm)"),
        (6, 4, "Std dev (nm)"),
        (7, 4, "Fitted log-sigma"),
    ]

    # Use row 7+ for results to avoid overwriting params
    RESULTS_START = 7
    stat_labels = [
        "Count (n)",
        "Mean (nm)",
        "Median (nm)",
        "Geometric mean (nm)",
        "Std dev (nm)",
        "Fitted log-sigma",
    ]
    # Sheet rows for ks_set targets: E2=n, E3=mean, E4=median, E5=geom, E6=std, E7=sigma_fit
    # 0-based rows: row 1=E2, row 2=E3, row 3=E4, row 4=E5, row 5=E6, row 6=E7
    # So we write results labels at rows 1-6, col 2 (C) for label, col 4 (E) for value

    s.set(1, 2, "Results")
    s.fmt(1, 2, bold=True, font_color=PALETTE["accent"], font_size=11)

    # rows 1..6 for the 6 statistics — these map to sheet rows E2..E7
    for k, lbl in enumerate(stat_labels):
        r_label = k + 1   # 0-based row; row 1 = E2 in col E (4)
        s.set(r_label, 2, lbl)
        s.fmt(r_label, 2, bold=True)
        s.fmt(r_label, 4, bg=PALETTE["good"], bold=True,
              align="center", number_format="0.000")

    s.box(1, 2, 6, 4, color=PALETTE["header"], width=1.2)

    s.note(
        1, 4,
        "These statistics are written by the =PY cell (H10) after fitting. "
        "n = number of particles; geometric mean = exp(mean(ln(d))).",
        kind="note",
    )

    # ── =PY cell (row 9 = sheet row 10, col 7 = H) ────────────────────
    s.set(8, 2, "Analysis cell (H10) ▼")
    s.fmt(8, 2, bold=True, font_color=PALETTE["header"])
    s.formula(9, 7, "=PY\n" + PY_BODY)

    s.note(
        9, 7,
        "=PY cell: reads diameters from A2 downward, fits a log-normal "
        "distribution using scipy.stats.lognorm, writes statistics to E2:E7, "
        "and plots histogram + fitted PDF.",
        kind="note",
    )

    # ── Additional sticky note on data column ─────────────────────────
    s.note(
        0, 0,
        f"Column A: {N_PARTICLES} particle diameters (nm) drawn from a "
        "log-normal distribution (geometric mean 12 nm, sigma_log=0.35). "
        "Seed: np.random.default_rng(42). Sorted ascending.",
        kind="note",
    )

    # ── LaTeX equation ────────────────────────────────────────────────
    s.equation(
        r"f(d) = \frac{1}{d\,\sigma\sqrt{2\pi}}"
        r"\exp\!\left(-\frac{(\ln d - \mu)^2}{2\sigma^2}\right)",
        at=(560, 40), fontsize=16, color="#1a1a2e",
        bg_color="#f8f8ff", border_color=PALETTE["header"],
        border_width=1.2, size=(360, 56),
    )

    # ── Save ──────────────────────────────────────────────────────────
    out = os.path.join(
        _REPO, "examples", "python", "Materials Science",
        "TEM Particle Sizes.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
