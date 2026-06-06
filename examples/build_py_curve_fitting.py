"""Build the "XPS Peak Fitting (Sr 3d)" Python-cell example .ksheet.

Replicates KherveSheet's Curve Fitting dialog entirely in cells + a =PY
cell: Pseudo-Voigt peaks on a standard Shirley background, with cells for
the X/Y data ranges and the fitting X-range, plus a full parameter table
(Value / Min / Max / Vary / Expr) that supports constraints and
expression-linking between peaks (e.g. peak 2's centre = peak 1's centre
+ 1.74).  The Sr 3d data is embedded from the user's STO.ksheet so the
example is self-contained.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from ksheet_author import Workbook, PALETTE  # noqa: E402


def _load_sr3d():
    """Read the Sr3d x/y columns out of the bundled STO.ksheet, falling
    back to a synthetic Sr 3d doublet if that file is not present."""
    import h5py
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(repo, "Test", "STO.ksheet")
    if os.path.exists(path):
        with h5py.File(path, "r") as f:
            for i in range(int(f.attrs["sheet_count"])):
                g = f.get("sheet_%d" % i)
                if g is None or g.attrs.get("name") != "Sr3d":
                    continue
                rows, cols = int(g.attrs["rows"]), int(g.attrs["cols"])
                cells = [c.decode() if isinstance(c, bytes) else c
                         for c in g["cells"][:]]
                arr = np.array(cells, dtype=object).reshape(rows, cols)
                xs, ys = [], []
                for r in range(rows):
                    try:
                        xs.append(float(arr[r, 0]))
                        ys.append(float(arr[r, 1]))
                    except (TypeError, ValueError):
                        pass
                return np.array(xs), np.array(ys)
    x = np.round(np.arange(142.08, 126.0, -0.1), 2)

    def pv(x, a, c, s, fr):
        g = np.exp(-(x-c)**2/(2*s*s))
        ll = s*s/((x-c)**2+s*s)
        return a*((1-fr)*g+fr*ll)
    y = (23000 + 3000*(x > 134)
         + pv(x, 98000, 132.5, 0.5, 0.3)
         + pv(x, 65000, 134.24, 0.5, 0.3))
    rng = np.random.default_rng(0)
    return x, np.round(y + rng.normal(0, 800, x.size), 0)


# The =PY fit program (body only; the "=PY" marker is added on write).
PY_BODY = r'''# XPS curve fitting — Pseudo-Voigt peaks on a standard Shirley
# background.  The X/Y data ranges, the fitting X-range and every peak
# parameter (Value / Min / Max / Vary / Expr) all come from the cells in
# the panel above.  This cell reads them, fits with lmfit, writes the
# fitted Values back into the table, and plots the result.
import numpy as np, matplotlib.pyplot as plt
import lmfit
from scipy.integrate import cumulative_trapezoid

# --- data ranges + fitting range come from cells ---------------------
x_range = str(ks("E4")).strip()        # X data range, e.g. A1:A161
y_range = str(ks("E5")).strip()        # Y data range, e.g. B1:B161
xa = np.array(ks(x_range), dtype=float)
ya = np.array(ks(y_range), dtype=float)
ok = np.isfinite(xa) & np.isfinite(ya)
xa, ya = xa[ok], ya[ok]
order = np.argsort(xa); xa, ya = xa[order], ya[order]   # full spectrum
lo = float(ks("E7")); hi = float(ks("E8"))         # fitting X-range (eV)
keep = (xa >= min(lo, hi)) & (xa <= max(lo, hi))   # clip to the fit window
x, y = xa[keep], ya[keep]                          # data used for the fit

# --- read the parameter table (supports up to 10 peaks = 40 rows) ----
names = ks("D13:D52"); vals = ks("E13:E52")
mins  = ks("F13:F52"); maxs = ks("G13:G52")
varys = ks("H13:H52"); exprs = ks("I13:I52")
def val(v):                        # treat None / "" / NaN (blank) as empty
    if v is None or v == "":
        return None
    if isinstance(v, float) and not np.isfinite(v):
        return None
    return v

P = lmfit.Parameters()
rows = []
for i, nm in enumerate(names):
    if not val(nm):
        continue
    nm = str(nm).strip()
    kw = {"value": float(vals[i])}
    vy = val(varys[i]); ex = val(exprs[i])
    kw["vary"] = True if vy is None else bool(float(vy))
    if val(mins[i]) is not None: kw["min"] = float(mins[i])
    if val(maxs[i]) is not None: kw["max"] = float(maxs[i])
    if ex: kw["expr"] = str(ex).strip()        # link to another parameter
    P.add(nm, **kw)
    rows.append(nm)

ids = sorted({int(n[1:n.index("_")]) for n in rows
              if n.startswith("p") and "_" in n})

def pv(x, amp, cen, sig, fr):      # Pseudo-Voigt (height-normalised)
    g = np.exp(-(x-cen)**2/(2*sig*sig))
    lor = sig*sig/((x-cen)**2 + sig*sig)
    return amp*((1-fr)*g + fr*lor)

def peak_sum(p, x):                # all peaks added together
    t = np.zeros_like(x)
    for i in ids:
        t += pv(x, p["p%d_amplitude" % i], p["p%d_center" % i],
                p["p%d_sigma" % i], p["p%d_fraction" % i])
    return t

def shirley(x, y, nit=60):         # standard iterative Shirley background
    # x ascending; endpoints anchor the background. The step under each
    # peak is proportional to the spectral area still to higher BE, which
    # is what gives Shirley its characteristic S-shape.
    yl, yr = y[0], y[-1]; B = np.zeros_like(y)
    for _ in range(nit):
        inten = y - yr - B
        tot = np.trapezoid(inten, x)
        if tot <= 0:
            break
        area_right = tot - cumulative_trapezoid(inten, x, initial=0)
        Bn = (yl - yr) * (area_right / tot)
        if np.max(np.abs(Bn - B)) < 1e-5 * max(1, abs(yl - yr)):
            B = Bn; break
        B = Bn
    return yr + B

# --- standard Shirley background (from the raw data), then fit peaks --
# Computed once from the data itself (peaks included) so it keeps the
# Shirley step; the peaks are then fitted to (data - background).
bg = shirley(x, y)
out = lmfit.minimize(lambda p: peak_sum(p, x) - (y - bg), P)
P = out.params
fit = peak_sum(P, x) + bg
resid = y - fit                                    # residuals over the fit
r2 = 1 - np.sum((y - fit)**2) / np.sum((y - y.mean())**2)

# --- write fitted values back into the table + the R^2 cell ---------
ks_set("E13", [round(float(P[n].value), 4) for n in rows])
ks_set("E10", round(float(r2), 5))

# --- plot: residuals strip on top, full spectrum + fit below --------
fig, (axr, axm) = plt.subplots(
    2, 1, figsize=(7.4, 5.4), sharex=True,
    gridspec_kw={"height_ratios": [1, 4], "hspace": 0.05})

# residuals (data - fit) over the fitted window
axr.plot(x, resid, "-", lw=0.8, color="#7f7f7f")
axr.axhline(0, color="#c00000", lw=0.8)
axr.set_ylabel("resid"); axr.tick_params(labelbottom=False)
axr.set_title("Sr 3d  —  %d Pseudo-Voigt peaks, Shirley "
              "(R² = %.4f)" % (len(ids), r2))

# main panel: the WHOLE raw spectrum, with the fit on the fit window
axm.plot(xa, ya, "o", ms=2.5, color="#1f4e79", label="data (full range)")
axm.plot(x, bg, "--", lw=1, color="#7f7f7f", label="Shirley bg")
for i in ids:
    comp = pv(x, P["p%d_amplitude" % i], P["p%d_center" % i],
              P["p%d_sigma" % i], P["p%d_fraction" % i]) + bg
    axm.fill_between(x, bg, comp, alpha=0.30)
    axm.plot(x, comp, lw=1)
axm.plot(x, fit, "-", lw=1.7, color="#c00000", label="fit")
for xb in (lo, hi):                              # green fit-range markers
    axm.axvline(xb, color="#2e9e44", ls="--", lw=1)
    axr.axvline(xb, color="#2e9e44", ls="--", lw=1)
axm.set_xlabel("Binding energy (eV)"); axm.set_ylabel("Counts")
axm.legend()
plt.gcf()'''


def build():
    x, y = _load_sr3d()
    n = x.size
    wb = Workbook(min_rows=max(220, n + 5), min_cols=14)
    s = wb.add_sheet("Sr 3d Fit")

    # ── Data in columns A (x) and B (y) ──────────────────────────────
    for r in range(n):
        s.set(r, 0, round(float(x[r]), 3))
        s.set(r, 1, round(float(y[r]), 1))

    # ── Control panel (columns D..I) ─────────────────────────────────
    s.set(0, 3, "XPS Curve Fitting — Sr 3d")
    s.fmt(0, 3, bold=True, font_size=16, font_color=PALETTE["header"])
    s.merge(0, 3, 1, 6)
    s.set(1, 3, "Pseudo-Voigt peaks · standard Shirley background · "
                "fitted in Python (lmfit)")
    s.fmt(1, 3, italic=True, font_color="#555555")
    s.merge(1, 3, 1, 6)

    # Settings rows (label in D, value in E, second value in F).
    settings = [
        (3, "Data X range", "A1:A%d" % n, None),
        (4, "Data Y range", "B1:B%d" % n, None),
        (5, "Background", "Shirley", None),
        (6, "Fit X min (eV)", 128.0, None),
        (7, "Fit X max (eV)", 140.0, None),
        (8, "Number of peaks", 2, None),
        (9, "R² (after Fit)", "", None),
    ]
    for r, label, v, _ in settings:
        s.set(r, 3, label)
        s.set(r, 4, v)
        s.fmt(r, 3, bold=True)
        s.fmt(r, 4, bg=PALETTE["warn"], align="center")
    s.fmt(9, 4, bg=PALETTE["good"], align="center", number_format="0.0000")
    s.box(3, 3, 9, 4, color=PALETTE["header"], width=1.0)

    # ── Parameter table ──────────────────────────────────────────────
    headers = ["Parameter", "Value", "Min", "Max", "Vary", "Expr (link)"]
    for j, h in enumerate(headers):
        s.set(11, 3 + j, h)
        s.fmt(11, 3 + j, bold=True, bg=PALETTE["header"],
              font_color=PALETTE["header_text"], align="center")

    # (name, value, min, max, vary, expr) — peak 0 free, peak 1 linked.
    params = [
        ("p0_amplitude", 90000, 0,  "", 1, ""),
        ("p0_center",    132.5, 130, 135, 1, ""),
        ("p0_sigma",     0.7,   0.05, "", 1, ""),
        ("p0_fraction",  0.3,   0,  1,  1, ""),
        ("p1_amplitude", 60000, "", "", 0, "p0_amplitude*0.667"),
        ("p1_center",    134.2, "", "", 0, "p0_center+1.74"),
        ("p1_sigma",     0.7,   "", "", 0, "p0_sigma"),
        ("p1_fraction",  0.3,   "", "", 0, "p0_fraction"),
    ]
    for i, (nm, v, mn, mx, vy, ex) in enumerate(params):
        r = 12 + i
        s.set(r, 3, nm)
        s.set(r, 4, v)
        s.set(r, 5, mn)
        s.set(r, 6, mx)
        s.set(r, 7, vy)
        s.set(r, 8, ex)
        s.fmt(r, 3, bold=True)
        s.fmt(r, 4, bg=PALETTE["warn"], align="center")
        for c in (5, 6, 7):
            s.fmt(r, c, align="center")
        s.fmt(r, 8, font_color="#0a7", italic=True)
    s.box(11, 3, 19, 8, color=PALETTE["header"], width=1.0)
    # Rows 13..52 (D13:I52) are reserved for up to 10 peaks — keep this
    # block free of other text so it reads cleanly.

    # ── The fit program ──────────────────────────────────────────────
    # Placed in column K (well clear of the data in A/B and the parameter
    # table in D:I rows 13-52) so it never overlaps the peak cells.
    s.set(2, 10, "Fit engine ▼")
    s.fmt(2, 10, bold=True, font_color=PALETTE["header"])
    s.formula(3, 10, "=PY\n" + PY_BODY)

    s.note(
        2, 11,
        "Set the X/Y data ranges (E4/E5) and the fitting X-range "
        "(E7/E8 — shown as green lines on the plot). Edit any Value / Min "
        "/ Max / Vary, or an Expr to LINK a parameter to another (e.g. "
        "p1_center = p0_center+1.74). Add peaks with rows p2_amplitude … "
        "p2_fraction (up to 10). Press Ctrl+Enter to fit; fitted values "
        "are written back into the Value column.")

    s.col_width(3, 130)
    s.col_width(8, 170)

    out = os.path.join(os.path.dirname(__file__), "python", "Curve Fitting",
                       "XPS Peak Fitting (Sr 3d).ksheet")
    wb.save(out)
    print("Wrote", out)


if __name__ == "__main__":
    build()
