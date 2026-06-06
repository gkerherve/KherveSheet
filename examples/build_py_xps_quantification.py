"""Build "XPS Quantification.ksheet" — a Python-cell materials-science example.

A table of Element / peak area / relative sensitivity factor (RSF) for
5 elements.  A =PY cell computes atomic % = (area/RSF)/sum(area/RSF)
for each element, writes the at% column back, and draws a composition
bar chart.

Row/column mapping: set(r, c, v) -> sheet cell letter(c) + str(r+1).

Run:  python examples/build_py_xps_quantification.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "examples"))

import numpy as np
from ksheet_author import Workbook, PALETTE


def build() -> str:
    # ── XPS data: TiO2-based sample with surface carbon contamination ──
    # Element, peak, RSF (Scofield + instrument), raw area
    elements = ["Ti", "O", "C", "N", "Si"]
    peaks    = ["Ti 2p3/2", "O 1s", "C 1s", "N 1s", "Si 2p"]
    rsf      = [7.81,        2.93,    1.00,   1.80,   0.817]
    areas    = [45230.0,    142800.0, 31500.0, 2900.0, 8750.0]

    # Pre-compute at% for reference
    norm = np.array(areas) / np.array(rsf)
    at_pct = 100.0 * norm / norm.sum()

    N = len(elements)  # 5

    # ── Workbook ──────────────────────────────────────────────────────
    wb = Workbook(min_rows=40, min_cols=14)
    s = wb.add_sheet("XPS Quant")

    # ── Title ─────────────────────────────────────────────────────────
    s.title_block(
        "XPS Elemental Quantification",
        "Atomic % from peak areas and relative sensitivity factors (RSF).  Edit areas or RSF and press Ctrl+Enter.",
    )

    # ── Note about the technique ──────────────────────────────────────
    s.note(0, 7,
           "XPS quantification: at% = (area/RSF) / Σ(area/RSF).  "
           "RSF values are instrument- and pass-energy-dependent — "
           "always use the RSF set calibrated for your spectrometer.",
           kind="note")

    # ── Data table headers (row 3 = sheet row 4) ─────────────────────
    s.set(2, 0, "Peak data")
    s.fmt(2, 0, bold=True, font_color=PALETTE["accent"])

    headers = ["Element", "Peak", "Area (cps·eV)", "RSF", "at%"]
    for j, h in enumerate(headers):
        s.set(3, j, h)
        s.fmt(3, j, bold=True, bg=PALETTE["header"],
              font_color=PALETTE["header_text"], align="center")
    s.col_width(0, 80)
    s.col_width(1, 100)
    s.col_width(2, 130)
    s.col_width(3, 80)
    s.col_width(4, 80)

    # Data rows: rows 4..8 -> sheet rows 5..9
    band_colors = [None, PALETTE["band_alt"]] * 5
    for i in range(N):
        r = 4 + i
        band = PALETTE["band_alt"] if i % 2 else None
        s.set(r, 0, elements[i])
        s.set(r, 1, peaks[i])
        s.set(r, 2, float(areas[i]))
        s.set(r, 3, float(rsf[i]))
        s.set(r, 4, "")   # at% filled by =PY
        s.fmt(r, 0, align="left")
        s.fmt(r, 1, align="left")
        s.fmt(r, 2, align="right", number_format="0.0")
        s.fmt(r, 3, align="right", number_format="0.000")
        s.fmt(r, 4, align="right", number_format="0.00",
              bg=PALETTE["good"], bold=True)
        if band:
            for c in range(5):
                s.fmt(r, c, bg=band)
            # Re-apply special formats on top of band
            s.fmt(r, 2, bg=band, align="right", number_format="0.0")
            s.fmt(r, 3, bg=band, align="right", number_format="0.000")
            s.fmt(r, 4, bg=PALETTE["good"], bold=True,
                  align="right", number_format="0.00")

    s.box(3, 0, 3 + N, 4, color=PALETTE["header"], width=1.0)

    s.note(4, 2,
           "Edit the peak areas (column C) to reflect your measured values. "
           "The at% column (E) and bar chart update when you press Ctrl+Enter on the =PY cell.",
           kind="note")
    s.note(4, 3,
           "RSF values here are for a Thermo K-Alpha with Al Kα (1486.6 eV) "
           "and a 20 eV pass energy.  Replace with your instrument's RSF table.",
           kind="note")

    # ── Summary: total at% (row 9+1 = 10, sheet row 11) ─────────────
    r_sum = 4 + N  # row 9
    s.set(r_sum, 3, "Total at%:")
    s.fmt(r_sum, 3, bold=True, align="right")
    s.set(r_sum, 4, "")   # filled by =PY
    s.fmt(r_sum, 4, bold=True, bg=PALETTE["band"], align="right",
          number_format="0.00")

    # ── =PY cell: col 6 (G), row 3 (sheet row 4) ─────────────────────
    # Data: C5:D9 (areas and RSF, rows 4..8, cols 2..3)
    # Writes: at% to E5:E9 (col 4), total to E10 (row 9)
    # NOTE: =PY cell is at (3, 6) — column G, well clear of A-E
    py_code = "\n".join([
        "=PY",
        "import numpy as np",
        "import matplotlib.pyplot as plt",
        "",
        "# Read areas and RSF",
        f"areas = ks('C5:C{4 + N}')",
        f"rsf   = ks('D5:D{4 + N}')",
        "",
        "m = np.isfinite(areas) & np.isfinite(rsf) & (rsf > 0)",
        "areas_ok = areas[m]; rsf_ok = rsf[m]",
        "n_el = int(m.sum())",
        "",
        "# Atomic %",
        "norm = areas_ok / rsf_ok",
        "total_norm = norm.sum()",
        "at_pct = 100.0 * norm / total_norm if total_norm > 0 else norm * 0",
        "",
        "# Write at% back to E5:E<4+n_el>",
        "ks_set('E5', at_pct.reshape(-1, 1))",
        f"ks_set('E{4 + N + 1}', round(float(at_pct.sum()), 3))",
        "",
        "# Read element names for labels",
        f"el_raw = ks('A5:A{4 + N}')",
        "# el_raw may be numbers (NaN) for text cells on first load;",
        "# use fallback labels in that case",
        f"fallback = {elements!r}",
        "el_labels = []",
        "for i in range(n_el):",
        "    v = el_raw[i] if i < len(el_raw) else float('nan')",
        "    if isinstance(v, str) and v.strip():",
        "        el_labels.append(v.strip())",
        "    elif v != v:  # nan",
        "        el_labels.append(fallback[i] if i < len(fallback) else str(i))",
        "    else:",
        "        el_labels.append(str(int(v)) if v == int(v) else str(v))",
        "",
        "# Bar chart",
        "bar_colors = ['#4472c4','#ed7d31','#a9d18e','#ffc000','#7030a0']",
        "fig, ax = plt.subplots(figsize=(6, 4))",
        "bars = ax.bar(el_labels[:n_el], at_pct,",
        "              color=bar_colors[:n_el], edgecolor='white',",
        "              linewidth=0.8)",
        "for bar, val in zip(bars, at_pct):",
        "    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.4,",
        "            f'{val:.1f}%', ha='center', va='bottom', fontsize=9)",
        "ax.set_xlabel('Element')",
        "ax.set_ylabel('Atomic concentration (%)')",
        "ax.set_title('XPS Elemental Composition')",
        "ax.set_ylim(0, max(at_pct) * 1.15)",
        "ax.grid(True, axis='y', alpha=0.3)",
        "plt.tight_layout()",
        "plt.gcf()",
    ])
    s.formula(3, 6, py_code)
    s.fmt(3, 6, italic=True, font_color="#555555")
    s.col_width(6, 280)
    s.set(3, 7, "Analysis cell (col G) — Ctrl+Enter to re-run")
    s.fmt(3, 7, italic=True, font_color="#888888")

    # ── Equation ──────────────────────────────────────────────────────
    s.equation(
        r"at\%_i = \frac{A_i / S_i}{\sum_j A_j / S_j} \times 100",
        at=(550, 50), fontsize=16, color="#222222",
        bg_color="#ffffff", border_color=PALETTE["header"],
        border_width=1.2, size=(310, 52),
    )

    # ── Save ──────────────────────────────────────────────────────────
    out = os.path.join(
        _REPO, "examples", "python", "Materials Science",
        "XPS Quantification.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
