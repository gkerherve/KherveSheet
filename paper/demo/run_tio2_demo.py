"""TiO2 Ti 2p worked example for the JOSS paper.

All the science happens in =PY cells: loading the spectrum, the Shirley
background, the Voigt doublet fit, the results table and the figure. The
cells are placed over MCP (`set_python_cell` through khervesheet.mcp_server),
and every call is logged to mcp_calls.jsonl.
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from mcp_client import MCP

S = "Ti 2p"
SRC = os.path.expanduser(
    "~/Documents/KherveFitting/Data-Examples/2p Al ... Zn/22 - Ti - Titanium/TiO2.xlsx")
FIG = os.path.abspath(os.path.join(HERE, "..", "figures"))
LOG = os.path.join(HERE, "mcp_calls.jsonl")
if os.path.exists(LOG):
    os.remove(LOG)
m = MCP(LOG)
say = lambda *a: print(str(a[0])[:300], flush=True)

say(m.call("new_workbook", discard_unsaved_changes=True))
say(m.call("add_sheet", name=S))

CELLS = {
# A1 - load the measured spectrum straight from the instrument export
"A1": f'''import pandas as pd, numpy as np
raw = pd.read_excel({SRC!r}, sheet_name="Ti2p").iloc[:, :2].dropna()
be  = raw.iloc[:, 0].to_numpy(float)    # binding energy, eV
cps = raw.iloc[:, 1].to_numpy(float)    # counts
ks_set("A3", [["Binding Energy (eV)", "Counts"]] + np.column_stack([be, cps]).tolist())
"Ti 2p: %d points, %.1f-%.1f eV" % (len(be), be.min(), be.max())''',

# C1 - iterative Shirley background
"C1": '''def shirley(x, y, n_avg=5, tol=1e-6, max_iter=100):
    """Iterative Shirley (1972) background, any x order."""
    o = np.argsort(x); xs, ys = x[o], y[o]
    lo, hi = ys[:n_avg].mean(), ys[-n_avg:].mean()
    b = np.full_like(ys, lo)
    for _ in range(max_iter):
        s = ys - b
        cum = np.concatenate([[0], np.cumsum(0.5*(s[1:] + s[:-1])*np.diff(xs))])
        new = lo + (hi - lo)*cum/cum[-1]
        done = np.max(np.abs(new - b)) < tol*hi
        b = new
        if done: break
    out = np.empty_like(b); out[o] = b
    return out
bkg = shirley(be, cps)
ks_set("C3", ["Shirley"] + bkg.tolist())
"Shirley %.0f-%.0f cps" % (bkg.min(), bkg.max())''',

# D1 - Voigt spin-orbit doublet over the background
"D1": '''from scipy.optimize import curve_fit
from scipy.special import voigt_profile as V
def peaks(x, A, E0, sg1, gm1, split, ratio, sg2, gm2, As, Es, ss):
    # 2p1/2 keeps its own widths (Coster-Kronig broadening);
    # the Ti4+ charge-transfer satellite is a broad Gaussian ~13 eV above 2p3/2
    return (A*V(x - E0, sg1, gm1) + ratio*A*V(x - E0 - split, sg2, gm2)
            + As*V(x - Es, ss, 0))
o = np.argsort(be)
def active_shirley(x, pk, b0, k):
    """Shirley step built from the fitted peaks themselves (active Shirley)."""
    xs, ps = x[o], pk[o]
    cum = np.concatenate([[0], np.cumsum(0.5*(ps[1:] + ps[:-1])*np.diff(xs))])
    out = np.empty_like(cum); out[o] = b0 + k*cum
    return out
def model(x, b0, k, *pp):
    pk = peaks(x, *pp)
    return active_shirley(x, pk, b0, k) + pk
y0 = cps - bkg                          # C1's static Shirley only seeds the fit
p0 = [cps.min(), 0.05, 2*y0.max(), be[np.argmax(y0)], 0.5, 0.3, 5.7, 0.5, 0.8, 0.6, 0.1*y0.max(), 471.5, 1.2]
lo = [0, 0, 0, 455, 0.05, 0, 5.3, 0.3, 0.05, 0, 0, 469, 0.3]
hi = [cps.max(), 1, np.inf, 461, 2, 2, 6.1, 0.7, 3, 3, np.inf, 474, 3]
p, cov = curve_fit(model, be, cps, p0=p0, bounds=(lo, hi), maxfev=40000)
b0, k, A, E0, sg1, gm1, split, ratio, sg2, gm2, As, Es, ss = p
bkg = active_shirley(be, peaks(be, *p[2:]), b0, k)
ks_set("C4", bkg.tolist())             # C1's seed replaced by the fitted background
err = np.sqrt(np.diag(cov))
c1 = A*V(be - E0, sg1, gm1)
c2 = ratio*A*V(be - E0 - split, sg2, gm2)
c3 = As*V(be - Es, ss, 0)
env = bkg + c1 + c2 + c3
ks_set("D3", [["Ti 2p3/2", "Ti 2p1/2", "Satellite", "Envelope", "Residual"]]
             + np.column_stack([bkg + c1, bkg + c2, bkg + c3, env, cps - env]).tolist())
"2p3/2 %.2f eV, split %.2f eV" % (E0, split)''',

# I1 - results table, as in KherveFitting
"I1": '''def fwhm(sg, gm):   # Olivero & Longbothum (1977)
    fg, fl = 2*np.sqrt(2*np.log(2))*sg, 2*gm
    return 0.5346*fl + np.sqrt(0.2166*fl**2 + fg**2)
chi2r = np.sum((cps - env)**2/np.maximum(cps, 1))/(len(be) - len(p))
ks_set("I3", [["Peak", "Position (eV)", "FWHM (eV)", "Height (cps)", "Area (cps eV)"],
              ["Ti 2p3/2 Ti4+", round(E0, 2), round(fwhm(sg1, gm1), 2), round(c1.max()), round(A)],
              ["Ti 2p1/2 Ti4+", round(E0 + split, 2), round(fwhm(sg2, gm2), 2), round(c2.max()), round(ratio*A)],
              ["Sat. Ti4+", round(Es, 2), round(2.3548*ss, 2), round(c3.max()), round(As)],
              ["Splitting (eV)", round(split, 3), "+/-", round(err[6], 3), ""],
              ["Area ratio", round(ratio, 3), "+/-", round(err[7], 3), ""],
              ["Reduced chi2", round(chi2r, 2), "", "", ""]])
"Results table"''',

# T1 - Monte Carlo error analysis: Poisson-resampled spectra, each one refitted
"T1": '''import time
rng = np.random.default_rng(1)
truth = model(be, *p)
names = ["2p3/2 pos (eV)", "2p3/2 FWHM (eV)", "Splitting (eV)", "Area ratio", "2p3/2 area", "Sat. offset (eV)"]
draws, t0 = [], time.time()
while len(draws) < 300 and time.time() - t0 < 20:
    sim = rng.poisson(truth).astype(float)
    try:
        q, _ = curve_fit(model, be, sim, p0=p, bounds=(lo, hi), maxfev=4000)
    except RuntimeError:
        continue
    _, _, a, e0, s1, g1, sp, r, _, _, _, es, _ = q
    draws.append([e0, fwhm(s1, g1), sp, r, a, es - e0])
mc = np.array(draws)
ks_set("T3", [["Monte Carlo (N=%d)" % len(mc), "Fit value", "MC mean", "MC std", "Cov. std"]]
             + [[n, float("%.6g" % v), float("%.6g" % m_), float("%.2g" % sd), c]
                for n, v, m_, sd, c in zip(names,
                    [E0, fwhm(sg1, gm1), split, ratio, A, Es - E0],
                    mc.mean(0), mc.std(0, ddof=1),
                    [round(err[3], 4), "", round(err[6], 4), round(err[7], 4), round(err[2]), ""])])
ks_set("T12", [names] + mc.tolist())
"MC: %d refits" % len(mc)''',

# I40 - quick-look figure with residuals, in XPS publication conventions
"I40": f'''import matplotlib.pyplot as plt
plt.rcParams.update({{"font.family": "DejaVu Sans", "font.size": 10}})
fig, (ax, axr) = plt.subplots(2, 1, figsize=(6.4, 5.2), sharex=True,
                              gridspec_kw={{"height_ratios": [4, 1], "hspace": 0.05}})
k = 1e3
ax.fill_between(be, bkg/k, (bkg + c1)/k, color="#4a90d9", alpha=0.45, lw=0)
ax.fill_between(be, bkg/k, (bkg + c2)/k, color="#5cbf8a", alpha=0.45, lw=0)
ax.plot(be, (bkg + c1)/k, color="#1f5fa8", lw=1, label="Ti 2p$_{{3/2}}$ (Ti$^{{4+}}$)")
ax.plot(be, (bkg + c2)/k, color="#2e8b57", lw=1, label="Ti 2p$_{{1/2}}$ (Ti$^{{4+}}$)")
ax.fill_between(be, bkg/k, (bkg + c3)/k, color="#f0a35e", alpha=0.45, lw=0)
ax.plot(be, (bkg + c3)/k, color="#d97a1e", lw=1, label="Satellite")
ax.annotate("+%.1f eV" % (Es - E0), (Es, (bkg + c3).max()/k), xytext=(0, 8),
            textcoords="offset points", ha="center", fontsize=9)
ax.plot(be, bkg/k, "--", color="#7f7f7f", lw=1, label="Shirley")
ax.plot(be, env/k, color="#c0392b", lw=1.5, label="Envelope")
ax.plot(be, cps/k, "o", ms=2.5, mfc="none", mec="#222", mew=0.6, label="Data")
ax.annotate("%.2f eV" % E0, (E0, (bkg + c1).max()/k), xytext=(8, -4),
            textcoords="offset points", fontsize=9)
ax.annotate(r"$\\Delta$ = %.2f eV" % split, (E0 + split, (bkg + c2).max()/k),
            xytext=(8, 4), textcoords="offset points", fontsize=9)
ax.set_ylabel("Intensity (10$^3$ counts)"); ax.set_title("TiO$_2$  Ti 2p")
ax.legend(frameon=False, fontsize=9)
axr.plot(be, (cps - env)/np.sqrt(np.maximum(cps, 1)), color="#222", lw=0.8)
axr.axhline(0, color="#c0392b", lw=0.8)
axr.set_ylabel("Res./$\\\\sigma$"); axr.set_xlabel("Binding Energy (eV)")
axr.set_xlim(be.max(), be.min())          # XPS: binding energy decreases to the right
for a in (ax, axr):
    a.tick_params(direction="in", top=True, right=True)
fig.savefig({os.path.join(FIG, "tio2_ti2p.png")!r}, dpi=300, bbox_inches="tight")
fig.savefig({os.path.join(FIG, "tio2_ti2p.svg")!r}, bbox_inches="tight")
fig''',
}

for cell, code in CELLS.items():
    say(m.call("set_python_cell", sheet_name=S, cell=cell, code=code))
    say(m.call("read_cells", sheet_name=S, range=cell))

say(m.call("format_cells", sheet_name=S, range="A3:H3", format_props={"bold": True, "bg_color": "#DDEBF7"}))
say(m.call("format_cells", sheet_name=S, range="I3:M3", format_props={"bold": True, "bg_color": "#DDEBF7"}))
say(m.call("format_cells", sheet_name=S, range="A1:I1", format_props={"italic": True, "font_color": "#1f5fa8"}))
say(m.call("read_cells", sheet_name=S, range="I3:M9"))

# Native KherveSheet chart over the spilled columns (no matplotlib code),
# styled like a journal XPS figure: frame all round, no intensity numbers,
# components shaded to the background, spin-orbit splitting drawn as an arrow
import json as _json
cols = _json.loads(m.call("read_cells", sheet_name=S, range="A4:F274"))["values"]
num = [[float(v) for v in r] for r in cols]
peak = lambda j: max(num, key=lambda r: r[j] - r[2])          # row at component j's maximum
r32, r12, rsat = peak(3), peak(4), peak(5)
E32, E12, Esat = r32[0], r12[0], rsat[0]
top = max(r[1] for r in num)
rng = lambda c: "%s4:%s274" % (c, c)
say(m.call("insert_chart", sheet_name=S, chart_type="Line", x_range=rng("A"),
           y_range=",".join(rng(c) for c in "BCDEF"),
           title="", x_label="Binding Energy / eV", y_label="Intensity / cps",
           series_labels=["Experimental", "Background", "Ti 2p$_{3/2}$",
                          "Ti 2p$_{1/2}$", "Ti$^{4+}$ satellite"],
           preset="default", width=760, height=520, position="I11"))
RED, RED_E, BLUE, BLUE_E = "#e8a0a0", "#c0504d", "#8fb0dc", "#3f6fb5"
say(m.call("style_chart", sheet_name=S, chart_index=0, series=[
    {"index": 0, "color": "#333333", "linewidth": 1.0},
    {"index": 1, "color": "#9a9a9a", "linewidth": 0.8},
    {"index": 2, "color": RED_E, "linewidth": 0.9, "fill_mode": "series", "fill_target": 1,
     "fill_color": RED, "fill_alpha": 0.75},
    {"index": 3, "color": BLUE_E, "linewidth": 0.9, "fill_mode": "series", "fill_target": 1,
     "fill_color": BLUE, "fill_alpha": 0.75},
    {"index": 4, "color": RED_E, "linewidth": 0.9, "fill_mode": "series", "fill_target": 1,
     "fill_color": RED, "fill_alpha": 0.45}],
    legend={"loc": "center right", "frame": False, "fontsize": 11}))
frame = dict(spine_show=True, spine_color="#000000", spine_width=1.0,
             sec_spine_show=True, major_dir="in")
say(m.call("configure_axis", sheet_name=S, chart_index=0, axis="x", invert=True,
           limit_auto=False, limit_min=450, limit_max=476, sec_tick_show=True, sec_tick_dir="in",
           minor_show=True, minor_count=4, minor_dir="out", major_count=6,
           title_size=13, tl_size=11, **{**frame, "major_dir": "out"}))
say(m.call("configure_axis", sheet_name=S, chart_index=0, axis="y", tl_show=False,
           major_show=False, limit_auto=False, limit_min=0, limit_max=top*1.24,
           title_size=13, **frame))
# Spin-orbit splitting and satellite offset, drawn as in the journals:
# a dotted guide up from each peak and an arrow from the main line
ya, ys = top*1.05, top*1.16              # arrow heights: splitting, satellite
gc = RED_E
dot = dict(linestyle=":", linewidth=0.9)
say(m.call("annotate_chart", sheet_name=S, chart_index=0, replace=True, annotations=[
    {"type": "line", "x": E32, "y": r32[1]*1.01, "x2": E32, "y2": ys, "color": gc, **dot},
    {"type": "line", "x": E12, "y": r12[1]*1.04, "x2": E12, "y2": ya, "color": BLUE_E, **dot},
    {"type": "line", "x": Esat, "y": rsat[1]*1.06, "x2": Esat, "y2": ys, "color": gc, **dot},
    {"type": "arrow", "x": E12, "y": ya, "x2": E32, "y2": ya, "color": gc, "linewidth": 1.0},
    {"type": "arrow", "x": Esat, "y": ys, "x2": E32, "y2": ys, "color": gc, "linewidth": 1.0},
    {"type": "text", "x": (E32 + E12)/2, "y": ya + top*0.03, "text": "$\\Delta$ = %.2f eV" % (E12 - E32),
     "color": gc, "fontsize": 11, "box": False},
    {"type": "text", "x": (E32 + Esat)/2, "y": ys + top*0.03, "text": "+%.1f eV" % (Esat - E32),
     "color": gc, "fontsize": 11, "box": False}]))
say(m.call("export_chart", sheet_name=S, chart_index=0,
           path=os.path.join(FIG, "tio2_ti2p_chart.png"), dpi=300))
say(m.call("export_chart", sheet_name=S, chart_index=0,
           path=os.path.join(FIG, "tio2_ti2p_chart.svg")))
say(m.call("format_cells", sheet_name=S, range="T3:X3", format_props={"bold": True, "bg_color": "#DDEBF7"}))
say(m.call("read_cells", sheet_name=S, range="T3:X9"))
# Native histogram of the Monte Carlo area ratios
say(m.call("insert_chart", sheet_name=S, chart_type="Histogram", x_range="W13:W%d" % (12 + 300), y_range="W13:W%d" % (12 + 300),
           title="Monte Carlo: Ti 2p area ratio", x_label="Area ratio (2p$_{1/2}$ / 2p$_{3/2}$)",
           y_label="Number of refits", series_labels=["Area ratio"], colors=["#4a90d9"],
           preset="default", width=520, height=360, position="Z3"))
say(m.call("style_chart", sheet_name=S, chart_index=1, series=[
    {"index": 0, "color": "#8fb0dc", "edgecolor": "#000000", "edgewidth": 0.8}],
    legend={"visible": False}))
say(m.call("configure_axis", sheet_name=S, chart_index=1, axis="x",
           minor_show=True, minor_count=5, minor_dir="out", major_dir="out",
           sec_tick_show=True, sec_tick_dir="in", **{k: v for k, v in frame.items() if k != "major_dir"}))
say(m.call("configure_axis", sheet_name=S, chart_index=1, axis="y", **frame))
say(m.call("export_chart", sheet_name=S, chart_index=1,
           path=os.path.join(FIG, "tio2_mc_ratio.png"), dpi=300))
say(m.call("save_workbook", path=os.path.join(HERE, "TiO2_Ti2p.ksheet")))
