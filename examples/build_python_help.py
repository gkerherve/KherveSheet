# One-off generator for khervesheet/python_help.html.
# Run from the repo root:  python _gen_help.py
import html
import re

KW = set((
    "import from as def class return if elif else for while in is and or not "
    "with try except finally raise lambda yield None True False print").split())
_TOK = re.compile(
    r'(?P<comment>\#[^\n]*)'
    r"|(?P<string>\"[^\"]*\"|'[^']*')"
    r'|(?P<number>\b\d+\.?\d*(?:[eE]-?\d+)?\b)'
    r'|(?P<name>[A-Za-z_]\w*)')


def hl(code):
    out, i = [], 0
    for m in _TOK.finditer(code):
        out.append(html.escape(code[i:m.start()]))
        k = m.lastgroup
        t = html.escape(m.group())
        if k == "comment":
            out.append(f'<span class="com">{t}</span>')
        elif k == "string":
            out.append(f'<span class="str">{t}</span>')
        elif k == "number":
            out.append(f'<span class="num2">{t}</span>')
        elif k == "name" and m.group() in KW:
            out.append(f'<span class="kw">{t}</span>')
        else:
            out.append(t)
        i = m.end()
    out.append(html.escape(code[i:]))
    return "".join(out)


# Each section: (id, title, intro_html_or_None, [ (title, desc_or_None, code) ])
SECTIONS = [
 ("start", "Getting started", None, [
  ("A number", "The value of the last line becomes the cell's value.",
   "# The last expression is the cell result\n2 ** 10"),
  ("Use the math module", None,
   "# import any standard library and use it\nimport math\nmath.sqrt(2)"),
  ("Text output", None,
   '# build a string with an f-string\nname = "KherveSheet"\nf"Hello from {name}"'),
  ("A multi-step calculation", None,
   "# intermediate variables, then a final expression\n"
   "r = 5\narea = math.pi * r ** 2   # area of a circle\narea"),
  ("Define a function (shared everywhere)", None,
   "# functions defined here are visible to every other =PY cell\n"
   "def celsius_to_f(c):\n    return c * 9 / 5 + 32"),
  ("Call that function from another cell", None,
   "# uses the function defined in the cell above\ncelsius_to_f(100)   # 212.0"),
  ("Spill a list into the grid",
   "Returning a <code>list</code> fills this cell and the ones below it.",
   "# a list result spills down the column\n[x ** 2 for x in range(1, 6)]   # 1, 4, 9, 16, 25"),
  ("Conditional value", None,
   "# pick a value with an if/else expression\nn = 17\n\"even\" if n % 2 == 0 else \"odd\""),
 ]),
 ("grid", "Reading the grid — ks()",
  '<table class="ref">'
  '<tr><th><code>ks("A1")</code></th><td>value of one cell</td></tr>'
  '<tr><th><code>ks("A1:A10")</code></th><td>1-D NumPy array</td></tr>'
  '<tr><th><code>ks("A1:C5")</code></th><td>2-D NumPy array</td></tr>'
  '<tr><th><code>ks("Sheet2!B2")</code></th><td>value from another sheet</td>'
  '</tr></table>'
  '<div class="tip"><b>Writing back:</b> <code>ks_set("C1", value)</code> '
  '(alias <code>write</code>) pushes a result into the grid — a scalar fills '
  'the range, a 1-D array writes down a column, a 2-D array writes a block. '
  'The cell running the code is never overwritten, e.g. '
  '<code>ks_set("D1:D50", np.cumsum(ks("A1:A50")))</code>.</div>', [
  ("Sum a column", None,
   "# read a range and add it up\nimport numpy as np\nnp.sum(ks(\"A1:A20\"))"),
  ("Average of a range", None,
   "# mean of every value in B2:B100\nnp.mean(ks(\"B2:B100\"))"),
  ("One cell at a time", None,
   "# ks(\"A1\") returns a single number\nks(\"A1\") + ks(\"A2\")"),
  ("Element-wise arithmetic, then spill", None,
   "# transform a column and spill the result back\n(ks(\"A1:A10\") * 2 + 1).tolist()"),
  ("Cross-sheet reference", None,
   "# read from another sheet by name\nnp.max(ks(\"Data!C1:C50\"))"),
  ("Combine two columns", None,
   "# multiply paired values and sum (a dot product)\n"
   "x = ks(\"A2:A50\")\ny = ks(\"B2:B50\")\nnp.sum(x * y)"),
  ("Read a 2-D block", None,
   "# a rectangular range comes back as a 2-D array\n"
   "m = ks(\"A1:C3\")              # 3x3 array\nm.sum(axis=0).tolist()       # column totals (spills across)"),
  ("Count values above a threshold", None,
   "# boolean mask, then count the True values\nimport numpy as np\nint(np.sum(ks(\"A1:A100\") > 50))"),
  ("Write a result back to the grid", None,
   "# compute a running total and place it in D1:D50\nimport numpy as np\n"
   "ks_set(\"D1\", np.cumsum(ks(\"A1:A50\")))\n\"written\""),
 ]),
 ("numpy", "NumPy & math", None, [
  ("Evenly spaced values", "Kept as an array object; re-read with ks().",
   "# 100 points from 0 to 1\nnp.linspace(0, 1, 100)"),
  ("arange then spill", None,
   "# even numbers 0..18 spilled down a column\nnp.arange(0, 20, 2).tolist()"),
  ("Cumulative sum", None,
   "# running total of a column\nnp.cumsum(ks(\"A1:A12\")).tolist()"),
  ("Normalise to 0–1", None,
   "# rescale so min->0 and max->1\ny = ks(\"A1:A50\")\n((y - y.min()) / (y.max() - y.min())).tolist()"),
  ("Degrees to sine", None,
   "# convert degrees to radians, then take the sine\ndeg = ks(\"A1:A37\")\nnp.sin(np.radians(deg)).tolist()"),
  ("Clip values to a range", None,
   "# limit every value to lie within [0, 100]\nnp.clip(ks(\"A1:A50\"), 0, 100).tolist()"),
  ("Sort descending", None,
   "# sort ascending then reverse\nnp.sort(ks(\"A1:A20\"))[::-1].tolist()"),
  ("Random sample (reproducible)", None,
   "# a fixed seed makes the random draw repeatable\n"
   "rng = np.random.default_rng(42)\nrng.normal(100, 15, 30).round(2).tolist()"),
 ]),
 ("stats", "Statistics", None, [
  ("Mean, median, std", None,
   "# three summary statistics of a column\ny = ks(\"A1:A100\")\n[float(np.mean(y)), float(np.median(y)), float(np.std(y))]"),
  ("Z-scores", None,
   "# how many std-devs each point is from the mean\ny = ks(\"A1:A100\")\n((y - y.mean()) / y.std()).round(3).tolist()"),
  ("Percentiles", None,
   "# the 25th, 50th and 75th percentiles (quartiles)\nnp.percentile(ks(\"A1:A200\"), [25, 50, 75]).tolist()"),
  ("Correlation coefficient", None,
   "# Pearson correlation between two columns (-1..1)\nnp.corrcoef(ks(\"A1:A50\"), ks(\"B1:B50\"))[0, 1]"),
  ("Histogram counts", None,
   "# bin the data into 10 bins and return the counts\ncounts, edges = np.histogram(ks(\"A1:A200\"), bins=10)\ncounts.tolist()"),
  ("Moving average", None,
   "# smooth with a 5-point sliding window\ny = ks(\"A1:A100\")\nnp.convolve(y, np.ones(5)/5, \"valid\").tolist()"),
  ("Two-sample t-test", None,
   "# test whether two samples have different means\nfrom scipy import stats\n"
   "t, p = stats.ttest_ind(ks(\"A1:A30\"), ks(\"B1:B30\"))\n[float(t), float(p)]   # t-stat, p-value"),
  ("Describe with pandas", None,
   "# count/mean/std/min/quartiles/max in one call\nimport pandas as pd\npd.Series(ks(\"A1:A100\")).describe()"),
 ]),
 ("analysis", "Data analysis & signals", None, [
  ("Numerical derivative", None,
   "# dy/dx by finite differences\nx = ks(\"A2:A100\"); y = ks(\"B2:B100\")\nnp.gradient(y, x).tolist()"),
  ("Trapezoidal integral", None,
   "# area under the curve (use np.trapz on older NumPy)\n"
   "x = ks(\"A2:A100\"); y = ks(\"B2:B100\")\nfloat(np.trapezoid(y, x))"),
  ("Savitzky–Golay smoothing", None,
   "# smooth noisy data while keeping peak shape\n"
   "from scipy.signal import savgol_filter\nsavgol_filter(ks(\"B2:B200\"), 11, 3).tolist()"),
  ("Find peaks", None,
   "# locate local maxima above a prominence\nfrom scipy.signal import find_peaks\n"
   "idx, _ = find_peaks(ks(\"B2:B500\"), prominence=1)\n(idx + 2).tolist()       # 1-based row numbers"),
  ("FFT magnitude spectrum", None,
   "# frequency content of a signal\ny = ks(\"B2:B514\")\nnp.abs(np.fft.rfft(y)).tolist()"),
  ("FFT frequency axis", None,
   "# the frequencies matching the FFT bins\ny = ks(\"B2:B514\")\ndt = 0.001                 # sample spacing (s)\nnp.fft.rfftfreq(len(y), dt).tolist()"),
  ("Interpolate onto a new grid", None,
   "# resample y at 200 evenly spaced x-values\n"
   "x = ks(\"A2:A50\"); y = ks(\"B2:B50\")\nxn = np.linspace(x.min(), x.max(), 200)\nnp.interp(xn, x, y).tolist()"),
  ("Baseline subtraction", None,
   "# fit and remove a slow polynomial background\n"
   "x = ks(\"A2:A300\"); y = ks(\"B2:B300\")\nbase = np.polyval(np.polyfit(x, y, 3), x)\n(y - base).tolist()"),
 ]),
 ("fitting", "Curve fitting & regression", None, [
  ("Linear fit (slope & intercept)", None,
   "# fit a straight line y = m*x + b\nx = ks(\"A2:A50\"); y = ks(\"B2:B50\")\nnp.polyfit(x, y, 1).tolist()   # [slope, intercept]"),
  ("R² of a linear fit", None,
   "# coefficient of determination (fit quality)\n"
   "x = ks(\"A2:A50\"); y = ks(\"B2:B50\")\np = np.polyfit(x, y, 1); yhat = np.polyval(p, x)\n"
   "float(1 - np.sum((y-yhat)**2) / np.sum((y-y.mean())**2))"),
  ("Polynomial fit, evaluated", None,
   "# fit a cubic and evaluate it at the data x\nx = ks(\"A2:A50\"); y = ks(\"B2:B50\")\nnp.polyval(np.polyfit(x, y, 3), x).tolist()"),
  ("Nonlinear fit (exponential)", None,
   "# fit y = a*exp(b*x) by least squares\nfrom scipy.optimize import curve_fit\n"
   "def f(x, a, b): return a * np.exp(b * x)\nx = ks(\"A2:A40\"); y = ks(\"B2:B40\")\n"
   "popt, _ = curve_fit(f, x, y, p0=[1, 0.1])\npopt.tolist()   # fitted a, b"),
  ("Gaussian fit", None,
   "# fit a bell curve and return amplitude, centre, width\nfrom scipy.optimize import curve_fit\n"
   "def g(x, A, mu, s): return A*np.exp(-(x-mu)**2/(2*s*s))\nx = ks(\"A2:A100\"); y = ks(\"B2:B100\")\n"
   "popt, _ = curve_fit(g, x, y, p0=[y.max(), x.mean(), 1])\npopt.tolist()"),
  ("Predict new values from a fit", None,
   "# fit on A/B, predict for new x in D2:D10\np = np.polyfit(ks(\"A2:A50\"), ks(\"B2:B50\"), 1)\nnp.polyval(p, ks(\"D2:D10\")).tolist()"),
  ("Linear regression (full stats)", None,
   "# slope, intercept, R-squared and p-value\nfrom scipy import stats\n"
   "r = stats.linregress(ks(\"A2:A50\"), ks(\"B2:B50\"))\n[r.slope, r.intercept, r.rvalue**2, r.pvalue]"),
  ("Residuals of a fit", None,
   "# data minus fitted line (what the model misses)\nx = ks(\"A2:A50\"); y = ks(\"B2:B50\")\n(y - np.polyval(np.polyfit(x, y, 1), x)).tolist()"),
 ]),
 ("linalg", "Linear algebra", None, [
  ("Matrix multiply", None,
   "# matrix product of two 3x3 blocks\nA = ks(\"A1:C3\"); B = ks(\"E1:G3\")\n(A @ B).tolist()"),
  ("Determinant", None,
   "# determinant of a square matrix\nfloat(np.linalg.det(ks(\"A1:C3\")))"),
  ("Inverse matrix", None,
   "# matrix inverse\nnp.linalg.inv(ks(\"A1:C3\")).tolist()"),
  ("Solve a linear system Ax = b", None,
   "# solve simultaneous equations\nA = ks(\"A1:C3\"); b = ks(\"E1:E3\")\nnp.linalg.solve(A, b).tolist()"),
  ("Eigenvalues", None,
   "# eigenvalues of a matrix (real part)\nnp.linalg.eigvals(ks(\"A1:C3\")).real.tolist()"),
  ("Vector length (norm)", None,
   "# Euclidean length of a vector\nfloat(np.linalg.norm(ks(\"A1:A10\")))"),
 ]),
 ("plot-basic", "Plots — basics",
  '<div class="tip">Build a figure and return it (or just create one — '
  'KherveSheet captures the current figure). The plot is embedded next to '
  'the cell.</div>', [
  ("Line plot of a column", None,
   "# plot a single column against its index\nimport matplotlib.pyplot as plt\nplt.plot(ks(\"A1:A50\"))\nplt.gcf()"),
  ("X vs Y with labels", None,
   "# scatter+line of B against A, with axis labels\nfig, ax = plt.subplots()\n"
   "ax.plot(ks(\"A2:A50\"), ks(\"B2:B50\"), \"o-\")\nax.set_xlabel(\"Time (s)\"); ax.set_ylabel(\"Signal\")\nfig"),
  ("Scatter plot", None,
   "# points only, size 12\nplt.scatter(ks(\"A1:A80\"), ks(\"B1:B80\"), s=12)\nplt.gcf()"),
  ("Bar chart", None,
   "# category labels from A, heights from B\nlabels = [str(v) for v in ks(\"A1:A6\")]\nplt.bar(labels, ks(\"B1:B6\"))\nplt.gcf()"),
  ("Histogram", None,
   "# distribution of a column in 30 bins\nplt.hist(ks(\"A1:A200\"), bins=30, color=\"#4472c4\")\nplt.gcf()"),
  ("Two series with a legend", None,
   "# plot two columns and label them\nx = ks(\"A2:A50\")\n"
   "plt.plot(x, ks(\"B2:B50\"), label=\"trial 1\")\nplt.plot(x, ks(\"C2:C50\"), label=\"trial 2\")\nplt.legend(); plt.gcf()"),
  ("Curve from a formula", None,
   "# evaluate and plot sin(x) on a fine grid\nx = np.linspace(0, 2*np.pi, 200)\nplt.plot(x, np.sin(x)); plt.grid(True)\nplt.gcf()"),
  ("Log-scale plot", None,
   "# logarithmic y-axis\nplt.semilogy(ks(\"A1:A50\"), ks(\"B1:B50\"))\nplt.gcf()"),
  ("Title, grid and colour", None,
   "# style a single line plot\nplt.plot(ks(\"A1:A60\"), color=\"#ed7d31\", lw=2)\nplt.title(\"Measured response\"); plt.grid(True)\nplt.gcf()"),
  ("Fitted line over data", None,
   "# scatter the data and overlay a linear fit\nx = ks(\"A2:A50\"); y = ks(\"B2:B50\")\n"
   "p = np.polyfit(x, y, 1)\nplt.scatter(x, y, s=10); plt.plot(x, np.polyval(p, x), \"r-\")\nplt.gcf()"),
 ]),
 ("plot-adv", "Plots — advanced", None, [
  ("Stacked subplots", None,
   "# two charts sharing a figure\nfig, (a, b) = plt.subplots(2, 1)\na.plot(ks(\"A1:A50\")); b.plot(ks(\"B1:B50\"))\nfig"),
  ("Error bars", None,
   "# y with vertical error bars from column C\nx = ks(\"A2:A20\"); y = ks(\"B2:B20\"); e = ks(\"C2:C20\")\nplt.errorbar(x, y, yerr=e, fmt=\"o\", capsize=3)\nplt.gcf()"),
  ("Heatmap of a 2-D block", None,
   "# colour-map a rectangular range\nm = ks(\"A1:J10\")\nplt.imshow(m, cmap=\"viridis\"); plt.colorbar()\nplt.gcf()"),
  ("Contour plot", None,
   "# filled contours of a 2-D function\nx = np.linspace(-3, 3, 100); X, Y = np.meshgrid(x, x)\nZ = np.exp(-(X**2 + Y**2))\nplt.contourf(X, Y, Z, 20); plt.gcf()"),
  ("Filled area", None,
   "# shade the area under a curve\nx = np.linspace(0, 10, 100)\nplt.fill_between(x, np.sin(x), alpha=0.4)\nplt.gcf()"),
  ("Pie chart", None,
   "# proportions from column B\nplt.pie(ks(\"B1:B5\"), labels=[str(v) for v in ks(\"A1:A5\")])\nplt.gcf()"),
  ("Box plot of several columns", None,
   "# compare distributions side by side\ndata = [ks(\"A1:A50\"), ks(\"B1:B50\"), ks(\"C1:C50\")]\nplt.boxplot(data); plt.gcf()"),
  ("Stem plot", None,
   "# discrete stems (good for sequences)\nplt.stem(ks(\"A1:A20\")); plt.gcf()"),
  ("Step plot", None,
   "# step/staircase line\nplt.step(ks(\"A1:A30\"), ks(\"B1:B30\"), where=\"mid\")\nplt.gcf()"),
  ("3-D surface", None,
   "# a surface z = f(x, y)\nx = np.linspace(-3, 3, 60); X, Y = np.meshgrid(x, x)\n"
   "fig = plt.figure(); ax = fig.add_subplot(111, projection=\"3d\")\nax.plot_surface(X, Y, np.sin(np.sqrt(X**2+Y**2)))\nfig"),
  ("Annotated peak", None,
   "# mark the maximum of a curve\nx = np.linspace(0, 10, 200); y = np.exp(-(x-5)**2)\n"
   "plt.plot(x, y); i = y.argmax()\nplt.annotate(\"peak\", (x[i], y[i]))\nplt.gcf()"),
 ]),
 ("physics", "Physics", None, [
  ("Projectile trajectory", None,
   "# height vs horizontal distance for a 45 deg launch\nv, ang, g = 50, np.radians(45), 9.81\n"
   "t = np.linspace(0, 2*v*np.sin(ang)/g, 100)\ny = v*np.sin(ang)*t - 0.5*g*t*t\nplt.plot(v*np.cos(ang)*t, y); plt.gcf()"),
  ("Simple harmonic motion", None,
   "# position of an oscillator over time\nt = np.linspace(0, 10, 500)\nplt.plot(t, np.cos(2*np.pi*0.5*t)); plt.gcf()"),
  ("Damped oscillation", None,
   "# decaying oscillation A*e^(-gt)*cos(wt)\nt = np.linspace(0, 10, 500)\nplt.plot(t, np.exp(-0.3*t)*np.cos(5*t)); plt.gcf()"),
  ("Kinetic energy from a speed column", None,
   "# KE = 1/2 m v^2 for each speed\nm = 2.0                       # kg\n(0.5 * m * ks(\"A1:A50\")**2).tolist()"),
  ("Free-fall distance", None,
   "# distance fallen, d = 1/2 g t^2\nt = ks(\"A1:A30\")\n(0.5 * 9.81 * t**2).tolist()"),
  ("Ohm's law (V = I·R)", None,
   "# voltage from current x resistance\n(ks(\"A1:A20\") * ks(\"B1:B20\")).tolist()"),
  ("Planck blackbody curve", None,
   "# spectral radiance vs wavelength at 5000 K\nh, c, k = 6.626e-34, 3e8, 1.38e-23; T = 5000\n"
   "w = np.linspace(1e-7, 3e-6, 300)\nB = 2*h*c*c/w**5/(np.exp(h*c/(w*k*T))-1)\nplt.plot(w*1e9, B); plt.gcf()"),
  ("Pendulum period vs length", None,
   "# T = 2*pi*sqrt(L/g)\nL = np.linspace(0.1, 2, 50)\nplt.plot(L, 2*np.pi*np.sqrt(L/9.81)); plt.gcf()"),
 ]),
 ("chem", "Chemistry", None, [
  ("Molarity = moles / volume", None,
   "# concentration for each row\n(ks(\"A1:A10\") / ks(\"B1:B10\")).tolist()"),
  ("pH from [H+]", None,
   "# pH = -log10 of the hydrogen-ion concentration\n(-np.log10(ks(\"A1:A20\"))).tolist()"),
  ("Arrhenius plot (ln k vs 1/T)", None,
   "# linearised rate data for an activation energy\nT = ks(\"A2:A20\"); k = ks(\"B2:B20\")\nplt.plot(1/T, np.log(k), \"o\"); plt.gcf()"),
  ("First-order decay", None,
   "# concentration falling as 100*e^(-kt)\nt = np.linspace(0, 10, 200)\nplt.plot(t, 100*np.exp(-0.4*t)); plt.gcf()"),
  ("Beer–Lambert absorbance", None,
   "# A = epsilon * l * concentration\neps, l = 1.2e4, 1.0\n(eps * l * ks(\"A1:A15\")).tolist()"),
  ("Titration curve (strong acid/base)", None,
   "# pH as base is added to an acid\nV = np.linspace(0, 50, 300); Va = 25; C = 0.1\n"
   "moles = C*(Va - V)\npH = np.where(V<Va, -np.log10(np.abs(moles)/(Va+V)+1e-9), 7)\nplt.plot(V, pH); plt.gcf()"),
 ]),
 ("eng", "Engineering & signals", None, [
  ("Generate a noisy sine", None,
   "# a 5 Hz sine plus random noise\nt = np.linspace(0, 1, 500)\nrng = np.random.default_rng(0)\n"
   "(np.sin(2*np.pi*5*t) + 0.3*rng.normal(size=t.size)).tolist()"),
  ("Low-pass Butterworth filter", None,
   "# remove high-frequency noise (zero-phase)\nfrom scipy.signal import butter, filtfilt\n"
   "b, a = butter(4, 0.1)\nfiltfilt(b, a, ks(\"B2:B500\")).tolist()"),
  ("RMS value", None,
   "# root-mean-square of a signal\nfloat(np.sqrt(np.mean(ks(\"A1:A500\")**2)))"),
  ("Decibels from a ratio", None,
   "# convert amplitude ratios to dB\n(20 * np.log10(ks(\"A1:A30\"))).tolist()"),
  ("Bode-style magnitude", None,
   "# RC low-pass magnitude vs frequency\nf = np.logspace(0, 4, 200); fc = 100\n"
   "plt.semilogx(f, 20*np.log10(1/np.sqrt(1+(f/fc)**2)))\nplt.gcf()"),
  ("Cross-correlation", None,
   "# how two signals line up at different lags\nnp.correlate(ks(\"A1:A50\"), ks(\"B1:B50\"), \"full\").tolist()"),
 ]),
 ("finance", "Finance & misc", None, [
  ("Compound interest schedule", None,
   "# balance after 0..10 years at 5%\np, r = 1000, 0.05\n(p * (1+r) ** np.arange(0, 11)).round(2).tolist()"),
  ("Monthly loan payment", None,
   "# standard amortised payment formula\nP, r, n = 200000, 0.04/12, 360\nround(P*r*(1+r)**n/((1+r)**n-1), 2)"),
  ("Net present value", None,
   "# discount future cash flows to today\ncf = ks(\"A1:A10\"); r = 0.08\nfloat(np.sum(cf / (1+r) ** np.arange(len(cf))))"),
  ("Cumulative returns", None,
   "# compound a series of period returns\nnp.cumprod(1 + ks(\"A1:A60\")).tolist()"),
  ("Group & sum with pandas", None,
   "# total each category\nimport pandas as pd\n"
   "df = pd.DataFrame({\"cat\": ks(\"A1:A20\"), \"val\": ks(\"B1:B20\")})\ndf.groupby(\"cat\")[\"val\"].sum()"),
  ("Build a small table object",
   "A DataFrame is kept live in the cell; read parts of it with ks().",
   "# a 2-column table held in this cell\nimport pandas as pd\npd.DataFrame({\"x\": ks(\"A1:A10\"), \"x2\": ks(\"A1:A10\")**2})"),
 ]),
 ("sims", "Simulations & Monte Carlo",
  '<div class="tip"><b>What is Monte Carlo?</b> Instead of solving a problem '
  'with a formula, you draw many random samples and average the outcomes — '
  'the answer converges as the number of samples grows. Always seed the '
  'generator (<code>np.random.default_rng(seed)</code>) so results are '
  'reproducible. The shipped <b>Examples &rarr; Python Examples</b> menu has '
  'ready-to-open workbooks for all of these (Simulations, Finance '
  'Simulations, Physics Simulations, Materials Science).</div>', [
  ("Estimate π by random darts",
   "Throw points in a square; the fraction landing in the quarter circle is π/4.",
   "# Monte Carlo estimate of pi\nrng = np.random.default_rng(0)\n"
   "p = rng.random((100000, 2))          # random points in the unit square\n"
   "inside = (p[:, 0]**2 + p[:, 1]**2) <= 1   # inside the quarter circle?\n"
   "4 * inside.mean()                    # -> approx 3.14159"),
  ("Monte Carlo integration",
   "Average the function at random points, times the interval width.",
   "# estimate the integral of sin(x)^2 on [0, pi]\nrng = np.random.default_rng(1)\n"
   "a, b, N = 0, np.pi, 100000\nx = rng.uniform(a, b, N)             # random sample points\n"
   "(b - a) * np.mean(np.sin(x)**2)      # ~ pi/2"),
  ("Buffon's needle",
   "Drop needles on ruled lines; the crossing fraction gives π.",
   "# estimate pi from needle crossings\nrng = np.random.default_rng(2)\n"
   "N, L, d = 100000, 1.0, 2.0           # drops, needle length, line spacing\n"
   "mid = rng.uniform(0, d/2, N)         # distance of centre to nearest line\n"
   "ang = rng.uniform(0, np.pi/2, N)     # needle angle\n"
   "cross = mid <= (L/2)*np.sin(ang)     # does it cross a line?\n"
   "2*L / (d * cross.mean())             # ~ pi"),
  ("Law of large numbers (dice)",
   "The running average of many dice rolls converges to 3.5.",
   "# rolling average approaches the true mean 3.5\nrng = np.random.default_rng(3)\n"
   "rolls = rng.integers(1, 7, 5000)     # 5000 dice rolls\n"
   "avg = np.cumsum(rolls) / np.arange(1, rolls.size + 1)\n"
   "plt.plot(avg); plt.axhline(3.5, color=\"#ed7d31\", ls=\"--\")\nplt.gcf()"),
  ("1-D random walk",
   "Each step is +1 or -1; the path wanders away as sqrt(steps).",
   "# one random walk of 1000 steps\nrng = np.random.default_rng(4)\n"
   "steps = rng.choice([-1, 1], 1000)    # +/-1 each step\n"
   "plt.plot(np.cumsum(steps)); plt.gcf()"),
  ("2-D random walk",
   "Steps in x and y — a model of diffusion.",
   "# a random walker on the plane\nrng = np.random.default_rng(5)\n"
   "step = rng.choice([-1, 1], (2000, 2))   # dx, dy each step\n"
   "xy = np.cumsum(step, axis=0)\nplt.plot(xy[:, 0], xy[:, 1], lw=0.7)\nplt.gcf()"),
  ("Brownian motion",
   "Gaussian increments accumulate into a continuous random path.",
   "# a Wiener process path\nrng = np.random.default_rng(6)\n"
   "dt = 0.01; n = 1000\nincr = rng.normal(0, np.sqrt(dt), n)   # tiny random kicks\n"
   "plt.plot(np.cumsum(incr)); plt.gcf()"),
  ("Stock price paths (GBM)",
   "Geometric Brownian motion — the standard model for asset prices.",
   "# 50 simulated price paths over a year\nrng = np.random.default_rng(7)\n"
   "S0, mu, sig, days, n = 100, 0.08, 0.2, 252, 50\ndt = 1/days\n"
   "z = rng.normal(size=(n, days))\nincr = (mu - 0.5*sig*sig)*dt + sig*np.sqrt(dt)*z\n"
   "paths = S0*np.exp(np.cumsum(incr, axis=1))\nplt.plot(paths.T, lw=0.6, alpha=0.6); plt.gcf()"),
  ("Monte Carlo option price",
   "Average the discounted payoff over many simulated final prices.",
   "# price a European call by simulation\nrng = np.random.default_rng(8)\n"
   "S0, K, sig, r, T, n = 100, 105, 0.2, 0.03, 1.0, 200000\n"
   "ST = S0*np.exp((r-0.5*sig*sig)*T + sig*np.sqrt(T)*rng.normal(size=n))\n"
   "payoff = np.maximum(ST - K, 0)       # call payoff at expiry\n"
   "float(np.exp(-r*T) * payoff.mean())  # discounted average"),
  ("Value at Risk (VaR)",
   "The loss not exceeded with, say, 95% confidence.",
   "# 1-day 95% VaR from simulated returns\nrng = np.random.default_rng(9)\n"
   "value, mu, sig, n = 100000, 0.0005, 0.02, 100000\n"
   "pnl = value * rng.normal(mu, sig, n)     # simulated profit/loss\n"
   "float(-np.percentile(pnl, 5))            # 95% VaR (a positive loss)"),
  ("Galton board",
   "Balls bouncing left/right pile up into a normal distribution.",
   "# sum of +/-1 bounces over many rows -> bell curve\nrng = np.random.default_rng(10)\n"
   "rows, balls = 20, 5000\nfinal = rng.choice([-1, 1], (balls, rows)).sum(axis=1)\n"
   "plt.hist(final, bins=range(-rows, rows+2, 2)); plt.gcf()"),
  ("Birthday paradox",
   "Probability that two people in a group share a birthday.",
   "# simulate groups of 23 people\nrng = np.random.default_rng(11)\n"
   "trials, group = 20000, 23\nhit = 0\nfor _ in range(trials):\n"
   "    b = rng.integers(0, 365, group)\n    if len(np.unique(b)) < group:   # a clash?\n        hit += 1\n"
   "hit / trials                         # ~ 0.507"),
  ("Ising model (magnetism)",
   "Spins flip by the Metropolis rule; below T_c they align.",
   "# net magnetization of a small 2-D lattice\nrng = np.random.default_rng(12)\n"
   "L, T, sweeps = 20, 2.0, 200\ns = rng.choice([-1, 1], (L, L))\n"
   "for _ in range(sweeps):\n    i, j = rng.integers(0, L, 2)\n"
   "    nb = s[(i+1)%L, j] + s[(i-1)%L, j] + s[i, (j+1)%L] + s[i, (j-1)%L]\n"
   "    dE = 2 * s[i, j] * nb            # energy change if flipped\n"
   "    if dE <= 0 or rng.random() < np.exp(-dE/T):\n        s[i, j] *= -1   # accept the flip\n"
   "float(abs(s.mean()))                 # |magnetization| per spin"),
  ("Percolation",
   "Randomly occupy sites; clusters appear and eventually span the grid.",
   "# largest cluster fraction at occupation p\nfrom scipy.ndimage import label\n"
   "rng = np.random.default_rng(13)\nL, p = 80, 0.6\ngrid = rng.random((L, L)) < p     # occupied sites\n"
   "lab, n = label(grid)\nsizes = np.bincount(lab.ravel())[1:]   # cluster sizes\n"
   "float(sizes.max() / grid.sum())"),
  ("SIR epidemic",
   "Susceptible/Infected/Recovered populations over time.",
   "# integrate the SIR model with simple Euler steps\nN, beta, gamma = 1000, 0.4, 0.1\n"
   "S, I, R = N-1, 1, 0\nhist = []\nfor _ in range(1600):\n"
   "    dS = -beta*S*I/N; dI = beta*S*I/N - gamma*I; dR = gamma*I\n"
   "    S += 0.1*dS; I += 0.1*dI; R += 0.1*dR\n    hist.append((S, I, R))\n"
   "plt.plot(hist); plt.legend([\"S\", \"I\", \"R\"]); plt.gcf()"),
  ("Estimating e",
   "On average it takes e uniform(0,1) draws to sum past 1.",
   "# Monte Carlo estimate of Euler's number\nrng = np.random.default_rng(14)\n"
   "trials = 200000\ncounts = []\nfor _ in range(trials):\n    s = c = 0\n"
   "    while s <= 1:\n        s += rng.random(); c += 1   # draw until the sum exceeds 1\n"
   "    counts.append(c)\nnp.mean(counts)                  # ~ 2.71828"),
 ]),
]

CSS = """  :root {
    --bg: #ffffff; --fg: #1f2328; --muted: #57606a;
    --accent: #4472c4; --accent2: #ed7d31;
    --code-bg: #1e1e1e; --code-fg: #d4d4d4;
    --kw: #569cd6; --str: #ce9178; --num: #b5cea8; --com: #6a9955;
    --card: #f6f8fa; --border: #d0d7de;
  }
  * { box-sizing: border-box; }
  body { margin: 0; font-family: -apple-system, Segoe UI, Roboto, Helvetica,
    Arial, sans-serif; color: var(--fg); background: var(--bg);
    line-height: 1.55; }
  header { background: linear-gradient(120deg, #4472c4, #5b9bd5);
    color: #fff; padding: 32px 40px; }
  header h1 { margin: 0 0 6px; font-size: 30px; }
  header p { margin: 0; opacity: .92; font-size: 16px; }
  .wrap { display: flex; align-items: flex-start; }
  nav { position: sticky; top: 0; align-self: flex-start;
    width: 250px; max-height: 100vh; overflow: auto;
    padding: 20px 16px; border-right: 1px solid var(--border);
    font-size: 14px; background: var(--card); }
  nav a { display: block; color: var(--muted); text-decoration: none;
    padding: 3px 6px; border-radius: 6px; }
  nav a:hover { background: #e7edf5; color: var(--accent); }
  main { flex: 1; padding: 28px 40px; max-width: 980px; }
  h2 { margin: 38px 0 6px; padding-top: 10px; font-size: 22px;
    border-bottom: 2px solid var(--accent); display: inline-block; }
  h2:first-of-type { margin-top: 6px; }
  .intro { background: var(--card); border: 1px solid var(--border);
    border-radius: 10px; padding: 16px 20px; margin: 18px 0 8px; }
  .ex { margin: 18px 0; }
  .ex h3 { margin: 0 0 4px; font-size: 15px; }
  .ex .num { color: var(--accent2); font-weight: 700; margin-right: 6px; }
  .ex p { margin: 4px 0 6px; color: var(--muted); font-size: 14px; }
  pre { margin: 0; background: var(--code-bg); color: var(--code-fg);
    padding: 12px 14px; border-radius: 8px; overflow-x: auto;
    font-family: Consolas, "SF Mono", Menlo, monospace; font-size: 13px;
    line-height: 1.45; }
  code { font-family: Consolas, Menlo, monospace; }
  main p code, li code, td code { background: #eef1f4; padding: 1px 5px;
    border-radius: 4px; font-size: 13px; }
  .kw { color: var(--kw); } .str { color: var(--str); }
  .num2 { color: var(--num); } .com { color: var(--com); }
  table.ref { border-collapse: collapse; margin: 10px 0; }
  table.ref td, table.ref th { border: 1px solid var(--border);
    padding: 5px 10px; text-align: left; font-size: 14px; }
  table.ref th { background: var(--card); }
  footer { padding: 26px 40px; color: var(--muted); font-size: 13px;
    border-top: 1px solid var(--border); }
  .tip { background: #fff8e1; border-left: 4px solid var(--accent2);
    padding: 10px 14px; border-radius: 6px; margin: 12px 0; font-size: 14px; }"""

INTRO = """<div class="intro">
  <p><b>How it works.</b> Type <code>=PY</code> in a cell (or
  <b>Insert&nbsp;&rarr;&nbsp;Python&nbsp;Cell</b>); the formula bar becomes a
  code editor. Press <b>Ctrl+Enter</b> to run. The cell's value is the value
  of the <b>last line</b> (if it's an expression). All Python cells share one
  workbook namespace, so a function defined in one cell is callable from any
  other. Every example below has comments explaining what each line does.</p>
  <p><b>Read the grid</b> with <code>ks("A1")</code> (one cell) or
  <code>ks("A1:B10")</code> (a range &rarr; NumPy array). <b>Output:</b> a
  number/text shows in the cell; a <code>list</code> spills into neighbouring
  cells; a NumPy array / DataFrame is held live in the cell; a matplotlib
  figure is embedded as a picture. <code>np</code>, <code>plt</code> and (if
  installed) <code>pd</code> / <code>scipy</code> are ready to use.</p>
</div>
<div class="tip"><b>Python functions as formulas (UDFs).</b> A function you
<code>def</code> in a <code>=PY</code> cell can be called from an ordinary
formula: define <code>def discount(p, r): return p * (1 - r)</code>, then
write <code>=DISCOUNT(A2, 0.1)</code> anywhere — case-insensitive, and
built-in functions are never overridden.</div>
<div class="tip"><b>Pop-out editor.</b> Click the button next to the green PY
strip for a larger editor with line numbers, autocomplete (Ctrl+Space),
comment toggle (Ctrl+/), a <b>Pick cell</b> button to click-insert a
<code>ks("…")</code> reference, and an output pane. <b>Run</b> keeps the
window open so you can iterate.</div>
<div class="tip"><b>Images &amp; plots.</b> Return a matplotlib figure to
embed a plot. Return an image to embed a picture — or use
<code>ks_image(src)</code> where <i>src</i> is a URL, file path, raw bytes,
a PIL image or a NumPy H&times;W&times;3 array, e.g.
<code>ks_image("https://example.com/photo.jpg")</code>.</div>
<div class="tip"><b>Auto-refresh.</b> Right-click a <code>=PY</code> cell
&rarr; <b>Python loop</b> to re-run it on an interval (5&nbsp;s, 30&nbsp;s,
&hellip;) — handy for the live weather / stock / image cells. The PY badge
shows the period.</div>"""


def main():
    n = 0
    nav, body = [], []
    for sid, title, intro, items in SECTIONS:
        nav.append(f'  <a href="#{sid}">{html.escape(title)}</a>')
        body.append(
            "\n<!-- ============================================ -->\n"
            f'<h2 id="{sid}">{html.escape(title)}</h2>')
        if intro:
            body.append(intro)
        for t, desc, code in items:
            n += 1
            block = [f'<div class="ex"><h3><span class="num">{n}</span>'
                     f'{html.escape(t)}</h3>']
            if desc:
                block.append(f"<p>{desc}</p>")
            block.append(f"<pre>{hl(code)}</pre></div>")
            body.append("\n".join(block))
    doc = f"""<!DOCTYPE html>
<!--
  Python in KherveSheet — {n} commented examples.
  Copyright (C) 2026 Gwilherm Kerherve. GPL-3.0-or-later.
  Generated by _gen_help.py — do not edit by hand.
-->
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Python in KherveSheet — {n} Examples</title>
<style>
{CSS}
</style>
</head>
<body>
<header>
  <h1>Python in KherveSheet</h1>
  <p>Write real Python inside a cell — {n} commented examples.</p>
</header>
<div class="wrap">
<nav>
{chr(10).join(nav)}
</nav>
<main>

{INTRO}
{chr(10).join(body)}

</main>
</div>
<footer>
  KherveSheet — Python cells run real Python on your computer. Code saved in a
  <code>.ksheet</code> file prompts for permission before running when the file
  is reopened. &nbsp;·&nbsp; GPL-3.0-or-later.
</footer>
</body>
</html>
"""
    with open("khervesheet/python_help.html", "w", encoding="utf-8") as f:
        f.write(doc)
    print(f"wrote khervesheet/python_help.html with {n} examples")


if __name__ == "__main__":
    main()
