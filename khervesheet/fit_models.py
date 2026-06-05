"""Model library for the Curve Fitting tool.

Fittable functions are exposed as :class:`FitFunction` objects wrapping an
lmfit model.  Three sources feed the registry:

* **Every built-in lmfit model** (Gaussian, Lorentzian, Voigt,
  Pseudo-Voigt, Pearson IV/VII, split-Lorentzian, Doniach, skewed shapes,
  Breit–Wigner–Fano, exponential, power-law, step, …) covering
  XRD/XPS/Raman/FTIR/TGA/AFM workflows.
* **User-built custom functions** — an arbitrary expression in ``x`` and
  named parameters, compiled into an lmfit model on the fly.

Backgrounds come in two flavours:

* *Analytic* (constant, linear, polynomial): fitted simultaneously with
  the peaks as ordinary lmfit parameters.
* *Data-derived* (Shirley, Tougaard): they depend on the spectrum, so
  they are pre-computed from the data, subtracted, and the peaks are
  fitted to the remainder.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import ast
from typing import Callable, Dict, List

import numpy as np


# ── Fittable-function abstraction ───────────────────────────────────

class FitFunction:
    """One fittable shape: a label plus a factory that builds a prefixed
    lmfit model.  ``make_model(prefix)`` returns a fresh lmfit Model so
    several copies of the same shape can be summed in one composite."""

    def __init__(self, key: str, label: str, group: str,
                 factory: Callable, expr: str = "", guesser=None,
                 source: str = "", formula: str = "",
                 description: str = ""):
        self.key = key
        self.label = label
        self.group = group
        self._factory = factory
        self.expr = expr  # populated for user-built custom functions
        # Optional guesser(x, y) -> {param_name: value}; used for models
        # that don't ship an lmfit .guess() (our stable replacements).
        self.guesser = guesser
        self.source = source            # where the model comes from
        self.formula = formula          # human-readable equation
        self.description = description   # one-line explanation

    def make_model(self, prefix: str):
        return self._factory(prefix)


# ── Built-in lmfit models ───────────────────────────────────────────
#
# (lmfit class name, friendly label, technique group).  2-D and complex
# models are deliberately omitted.

_LMFIT_SPECS = [
    ("GaussianModel", "Gaussian", "Common"),
    ("LorentzianModel", "Lorentzian", "Common"),
    # Voigt is added separately so its Gaussian (sigma) and Lorentzian
    # (gamma) widths are both freely fittable (lmfit ties gamma=sigma).
    ("PseudoVoigtModel", "Pseudo-Voigt", "XRD / XPS"),
    ("Pearson7Model", "Pearson VII", "XRD"),
    ("Pearson4Model", "Pearson IV", "XRD"),
    ("SplitLorentzianModel", "Split Lorentzian", "XPS / Raman"),
    ("MoffatModel", "Moffat", "Optics / PSF"),
    ("DoniachModel", "Doniach-Sunjic", "XPS"),
    ("SkewedGaussianModel", "Skewed Gaussian", "Asymmetric"),
    ("SkewedVoigtModel", "Skewed Voigt", "Asymmetric"),
    # ExponentialGaussianModel is added separately below via a
    # numerically-stable implementation (lmfit's overflows to NaN).
    ("BreitWignerModel", "Breit-Wigner-Fano", "Raman"),
    ("LognormalModel", "Log-normal", "Particle size"),
    ("StudentsTModel", "Student's t", "Statistics"),
    ("DampedOscillatorModel", "Damped oscillator", "Spectroscopy"),
    ("DampedHarmonicOscillatorModel", "Damped harmonic osc.",
     "Spectroscopy"),
    ("ThermalDistributionModel", "Thermal distribution", "Physics"),
    ("BoseModel", "Bose-Einstein", "Physics"),
    ("FermiModel", "Fermi-Dirac", "Physics"),
    ("StepModel", "Step", "TGA / DSC"),
    ("RectangleModel", "Rectangle", "General"),
    ("ExponentialModel", "Exponential", "Decay / kinetics"),
    ("PowerLawModel", "Power law", "AFM / scaling"),
    ("SineModel", "Sine", "Oscillatory"),
    ("LinearModel", "Linear", "Polynomial"),
    ("QuadraticModel", "Quadratic", "Polynomial"),
    ("ConstantModel", "Constant", "Polynomial"),
]


# Concise formula + explanation per model, keyed by lmfit class name (or
# our own key for the stable/freed variants).  Source is filled in
# separately.  amplitude=A, center=mu, sigma=s, etc.
_MODEL_INFO = {
    "GaussianModel": (
        "A/(s·√(2π)) · exp(-(x-mu)²/(2s²))",
        "Symmetric bell curve; FWHM = 2.3548·s."),
    "LorentzianModel": (
        "A/π · s/((x-mu)² + s²)",
        "Cauchy/Lorentzian peak with heavier tails than a Gaussian."),
    "voigt_sg": (
        "Voigt = Gaussian(s) ⊗ Lorentzian(gamma)",
        "Convolution of Gaussian and Lorentzian; sigma and gamma are "
        "both fitted independently."),
    "PseudoVoigtModel": (
        "fraction·Lorentzian + (1-fraction)·Gaussian",
        "Linear Gaussian/Lorentzian mix; the standard XRD/XPS peak."),
    "Pearson7Model": (
        "A / [1 + ((x-mu)/s)²·(2^(1/m)-1)]^m",
        "Pearson VII — Gaussian (m→∞) to Lorentzian (m=1); XRD."),
    "Pearson4Model": (
        "Pearson IV (skewed Pearson VII)",
        "Asymmetric Pearson with a skew parameter; XRD."),
    "SplitLorentzianModel": (
        "Lorentzian with sigma left of centre, sigma_r right",
        "Asymmetric Lorentzian with independent half-widths."),
    "MoffatModel": (
        "A / [1 + ((x-mu)/s)²]^beta",
        "Moffat profile; optical point-spread functions."),
    "DoniachModel": (
        "A·cos[πα/2 + (1-α)·atan((x-mu)/s)] / (s²+(x-mu)²)^((1-α)/2)",
        "Doniach–Šunjić asymmetric core-level line shape (XPS)."),
    "SkewedGaussianModel": (
        "Gaussian · [1 + erf(gamma·(x-mu)/(s√2))]",
        "Gaussian skewed by gamma."),
    "SkewedVoigtModel": (
        "Voigt skewed by an error-function factor (skew)",
        "Asymmetric Voigt."),
    "emg_stable": (
        "A·gamma/2 · exp(gamma/2·(2mu+gamma·s²-2x)) · erfc(...)",
        "Exponentially-modified Gaussian (tailing peak); evaluated via "
        "erfcx so it never overflows."),
    "BreitWignerModel": (
        "A·(q·s/2 + x-mu)² / ((s/2)² + (x-mu)²)",
        "Breit–Wigner–Fano resonance; asymmetric Raman lines."),
    "LognormalModel": (
        "A/(x·s√(2π)) · exp(-(ln x-mu)²/(2s²))",
        "Log-normal distribution; particle-size data."),
    "StudentsTModel": (
        "Student's t distribution",
        "Bell curve with adjustable tail weight."),
    "DampedOscillatorModel": (
        "A / √((1-(x/mu)²)² + (2·s·x/mu)²)",
        "Amplitude of a driven damped oscillator."),
    "DampedHarmonicOscillatorModel": (
        "Damped harmonic oscillator (DHO) response",
        "DHO line shape used in inelastic scattering."),
    "ThermalDistributionModel": (
        "Bose/Maxwell/Fermi thermal distribution",
        "Thermal occupation versus energy."),
    "BoseModel": ("1/(exp((x-mu)/kt) - 1)",
                  "Bose–Einstein distribution."),
    "FermiModel": ("1/(exp((x-mu)/kt) + 1)",
                   "Fermi–Dirac distribution."),
    "StepModel": (
        "A·step((x-mu)/s)  [linear/erf/atan/logistic]",
        "Rising step; TGA mass loss / DSC transitions."),
    "RectangleModel": (
        "A·[step up at center1] · [step down at center2]",
        "Top-hat / rectangle built from two steps."),
    "ExponentialModel": ("A·exp(-x/decay)",
                         "Exponential decay; kinetics."),
    "PowerLawModel": ("A·x^exponent",
                      "Power law; scaling / AFM."),
    "SineModel": ("A·sin(frequency·x + shift)",
                  "Sinusoid."),
    "LinearModel": ("slope·x + intercept", "Straight line."),
    "QuadraticModel": ("a·x² + b·x + c", "Parabola."),
    "ConstantModel": ("c", "Constant offset."),
}


def _builtin_factory(class_name):
    def factory(prefix):
        import lmfit.models as M
        return getattr(M, class_name)(prefix=prefix)
    return factory


def _voigt_factory(prefix):
    """Voigt with an independently-fittable Lorentzian width gamma
    (lmfit ties gamma to sigma by default, hiding it)."""
    import lmfit.models as M
    m = M.VoigtModel(prefix=prefix)
    m.set_param_hint("gamma", vary=True, expr="", min=0)
    return m


def _voigt_guess(x, y):
    """Seed a free-gamma Voigt from lmfit's own guess, starting the
    Lorentzian width at the Gaussian width (otherwise the freed gamma
    has no sensible starting value and can run away)."""
    import lmfit.models as M
    try:
        g = M.VoigtModel().guess(np.asarray(y, dtype=float),
                                 x=np.asarray(x, dtype=float))
        sig = float(g["sigma"].value)
        return {"amplitude": float(g["amplitude"].value),
                "center": float(g["center"].value),
                "sigma": sig, "gamma": sig}
    except Exception:
        return {}


# ── Stable exponentially-modified Gaussian ──────────────────────────
#
# lmfit's ExponentialGaussianModel evaluates exp(…)·erfc(…) directly,
# where the exp term overflows and the erfc term underflows at extreme
# trial parameters, producing inf·0 = NaN and aborting the fit.  We
# evaluate the same function through the scaled complementary error
# function erfcx(z)=exp(z²)·erfc(z), which never overflows:
#     exp(u)·erfc(z) = exp(u − z²)·erfcx(z).

def exp_gaussian(x, amplitude, center, sigma, gamma):
    from scipy.special import erfcx
    sigma = max(float(sigma), 1e-12)
    gamma = float(gamma)
    z = (center + gamma * sigma ** 2 - x) / (np.sqrt(2.0) * sigma)
    u = (gamma / 2.0) * (2.0 * center + gamma * sigma ** 2 - 2.0 * x)
    return (amplitude * gamma / 2.0) * np.exp(u - z ** 2) * erfcx(z)


def _emg_factory(prefix):
    import lmfit
    m = lmfit.Model(exp_gaussian, prefix=prefix,
                    name="Exp.-modified Gaussian")
    m.set_param_hint("sigma", min=0)
    m.set_param_hint("gamma", min=0)
    return m


def _emg_guess(x, y):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    base = float(np.nanmin(y))
    yy = y - base
    i = int(np.nanargmax(yy))
    height = float(yy[i]) or 1.0
    above = yy >= height / 2.0
    if above.any():
        width = float(x[above].max() - x[above].min()) or 1.0
    else:
        width = (float(np.nanmax(x) - np.nanmin(x)) or 1.0) / 10.0
    sigma = max(width / 2.3548, 1e-3)
    _trapz = getattr(np, "trapezoid", np.trapz)
    area = float(_trapz(yy, x)) or (height * sigma)
    return {"amplitude": area, "center": float(x[i]),
            "sigma": sigma, "gamma": 1.0 / sigma}


def builtin_functions() -> List[FitFunction]:
    funcs = []
    for cls_name, label, group in _LMFIT_SPECS:
        try:
            import lmfit.models as M  # noqa: F401
            getattr(M, cls_name)
        except (ImportError, AttributeError):
            continue
        formula, desc = _MODEL_INFO.get(cls_name, ("", ""))
        funcs.append(FitFunction(
            "lmfit:" + cls_name, label, group,
            _builtin_factory(cls_name), source="lmfit",
            formula=formula, description=desc))
    # Voigt with both widths free (sigma = Gaussian, gamma = Lorentzian).
    vf, vd = _MODEL_INFO["voigt_sg"]
    funcs.insert(2, FitFunction(
        "voigt_sg", "Voigt", "Common / XRD", _voigt_factory,
        guesser=_voigt_guess, source="lmfit (gamma freed)",
        formula=vf, description=vd))
    # Stable EMG (replaces lmfit's NaN-prone ExponentialGaussianModel).
    ef, ed = _MODEL_INFO["emg_stable"]
    funcs.append(FitFunction(
        "emg_stable", "Exp.-modified Gaussian", "TGA / chromatography",
        _emg_factory, guesser=_emg_guess,
        source="KherveSheet (stable EMG)", formula=ef, description=ed))
    return funcs


def function_help(custom_store: Dict[str, dict]):
    """Return [{label, group, source, formula, description, params}] for
    every available function, for the Curve Fitting help dialog."""
    rows = []
    for f in all_functions(custom_store):
        try:
            pars = f.make_model("p_").make_params()
            params = [p[2:] for p in pars if not pars[p].expr]
        except Exception:
            params = []
        rows.append({
            "label": f.label, "group": f.group,
            "source": f.source or "lmfit",
            "formula": f.expr or f.formula,
            "description": f.description or "",
            "params": params,
        })
    return rows


# ── User-built custom functions ─────────────────────────────────────
#
# A custom function is an expression in ``x`` plus free parameters, e.g.
# ``a * exp(-(x - c)**2 / (2 * w**2)) + d``.  We parse the parameter
# names, build a real Python function with that exact signature (so lmfit
# can introspect it), and evaluate the body in a restricted namespace of
# numpy / scipy maths — no builtins, so it can't import or call out.

# Names available inside a custom expression (besides the parameters).
def _safe_namespace():
    import numpy as _np
    ns = {
        "exp": _np.exp, "log": _np.log, "ln": _np.log, "log10": _np.log10,
        "sqrt": _np.sqrt, "abs": _np.abs, "fabs": _np.fabs,
        "sin": _np.sin, "cos": _np.cos, "tan": _np.tan,
        "arcsin": _np.arcsin, "arccos": _np.arccos, "arctan": _np.arctan,
        "sinh": _np.sinh, "cosh": _np.cosh, "tanh": _np.tanh,
        "sign": _np.sign, "where": _np.where, "heaviside": _np.heaviside,
        "power": _np.power, "maximum": _np.maximum, "minimum": _np.minimum,
        "clip": _np.clip, "floor": _np.floor, "ceil": _np.ceil,
        "pi": _np.pi, "e": _np.e,
    }
    try:
        from scipy.special import erf, erfc, wofz, gamma
        ns.update({"erf": erf, "erfc": erfc, "wofz": wofz, "gamma": gamma})
    except ImportError:
        pass
    return ns


_RESERVED = set(_safe_namespace().keys()) | {"x"}


def custom_param_names(expr: str) -> List[str]:
    """Free parameters of *expr* (identifiers that aren't ``x`` or a
    known maths function), in order of first appearance."""
    tree = ast.parse(expr, mode="eval")
    seen, names = set(), []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id not in _RESERVED:
            if node.id not in seen:
                seen.add(node.id)
                names.append(node.id)
    return names


def make_custom_function(key: str, label: str, expr: str) -> FitFunction:
    """Compile *expr* into a :class:`FitFunction`.  Raises ValueError if
    the expression is invalid or has no free parameters."""
    expr = expr.strip()
    try:
        params = custom_param_names(expr)
    except SyntaxError as exc:
        raise ValueError(f"Invalid expression: {exc}")
    if not params:
        raise ValueError("Expression has no free parameters to fit.")

    ns = _safe_namespace()
    src = f"def _custom(x, {', '.join(params)}):\n    return ({expr})\n"
    glb = {"__builtins__": {}}
    glb.update(ns)
    try:
        exec(src, glb)  # noqa: S102 — restricted namespace, user formula
    except SyntaxError as exc:
        raise ValueError(f"Invalid expression: {exc}")
    fn = glb["_custom"]

    # Sanity-check it evaluates on a small array.
    try:
        fn(np.linspace(1.0, 2.0, 5), *[1.0] * len(params))
    except Exception as exc:
        raise ValueError(f"Expression failed to evaluate: {exc}")

    def factory(prefix):
        import lmfit
        return lmfit.Model(fn, prefix=prefix, name=label)

    return FitFunction(key, label, "Custom", factory, expr=expr)


def all_functions(custom_store: Dict[str, dict]) -> List[FitFunction]:
    """Built-in functions followed by any user-built custom functions in
    *custom_store* (``{key: {'label':.., 'expr':..}}``)."""
    funcs = builtin_functions()
    for key, spec in (custom_store or {}).items():
        try:
            funcs.append(make_custom_function(
                key, spec["label"], spec["expr"]))
        except ValueError:
            continue
    return funcs


# ── Background models ───────────────────────────────────────────────

# Analytic backgrounds expose a polynomial degree (-1 = none); the
# data-derived ones use None.
BACKGROUNDS = [
    ("none", "None", -1),
    ("constant", "Constant", 0),
    ("linear", "Linear", 1),
    ("poly2", "Polynomial (2)", 2),
    ("poly3", "Polynomial (3)", 3),
    ("shirley", "Shirley (XPS)", None),
    ("shirley_rev", "Shirley (reversed)", None),
    ("active_shirley", "Active Shirley (XPS)", None),
    ("active_shirley_rev", "Active Shirley (reversed)", None),
    ("als", "Asymmetric Least Squares", None),
]

_BG_DEGREE = {k: deg for k, _, deg in BACKGROUNDS}
_DATA_BG = {"shirley", "shirley_rev", "active_shirley",
            "active_shirley_rev", "als"}
_ACTIVE_BG = {"active_shirley", "active_shirley_rev"}


def background_degree(key: str):
    """Polynomial degree for an analytic background, or None if the
    background is data-derived (Shirley/ALS) or absent."""
    return _BG_DEGREE.get(key, -1)


def is_data_background(key: str) -> bool:
    return key in _DATA_BG


def is_active_background(key: str) -> bool:
    """Active backgrounds are recomputed from the fitted peak model each
    iteration (handled by the fitting dialog's outer loop)."""
    return key in _ACTIVE_BG


def data_background(key: str, x, y):
    """Compute a data-derived background array, or None if *key* is not
    one.  Active Shirley is seeded here from the data; the dialog then
    refines it from the peak model."""
    if key in ("shirley", "active_shirley"):
        return shirley_background(x, y, reverse=False)
    if key in ("shirley_rev", "active_shirley_rev"):
        return shirley_background(x, y, reverse=True)
    if key == "als":
        return als_background(x, y)
    return None


def active_shirley_background(x, y, peaks, reverse: bool = False):
    """Active Shirley: the step is proportional to the integrated area of
    the *fitted peak model* (smooth, noise-free) rather than the raw
    data, anchored at the data endpoints.  Recomputed each fit iteration
    as the peaks change."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    p = np.asarray(peaks, dtype=float)
    n = len(y)
    if n < 2:
        return np.zeros_like(y)
    order = np.argsort(x)
    ys, ps = y[order], p[order]
    if reverse:
        ys, ps = ys[::-1], ps[::-1]
    y_lo, y_hi = ys[0], ys[-1]
    above = np.clip(ps, 0.0, None)
    cum = np.concatenate(([0.0], np.cumsum((above[:-1] + above[1:]) / 2.0)))
    total = cum[-1]
    if total <= 0:
        bg = np.linspace(y_lo, y_hi, n)
    else:
        bg = y_lo + (y_hi - y_lo) * (cum / total)
    if reverse:
        bg = bg[::-1]
    out = np.empty(n)
    out[order] = bg
    return out


def shirley_background(x, y, max_iter: int = 50, tol: float = 1e-6,
                       reverse: bool = False):
    """Iterative Shirley background between the two range endpoints.

    The background equals the data at both endpoints and steps up under
    each peak in proportion to the integrated peak area, so it sits low
    on the low-intensity side and high on the elevated (inelastic) side.

    By convention the step accumulates from the low-x endpoint; for data
    whose inelastic tail is on the *low-x* side (binding energy plotted
    high→low), pass ``reverse=True``.  Output matches the input order.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    n = len(y)
    if n < 2:
        return np.zeros_like(y)
    order = np.argsort(x)
    ys = y[order]
    if reverse:
        ys = ys[::-1]
    y_lo, y_hi = ys[0], ys[-1]
    bg = np.linspace(y_lo, y_hi, n)
    for _ in range(max_iter):
        above = np.clip(ys - bg, 0.0, None)
        cum = np.concatenate(([0.0], np.cumsum(
            (above[:-1] + above[1:]) / 2.0)))
        total = cum[-1]
        if total <= 0:
            break
        # Background rises from the first endpoint to the last as the
        # cumulative peak area accumulates.
        new_bg = y_lo + (y_hi - y_lo) * (cum / total)
        if np.max(np.abs(new_bg - bg)) < tol * (abs(total) + 1e-12):
            bg = new_bg
            break
        bg = new_bg
    if reverse:
        bg = bg[::-1]
    out = np.empty(n)
    out[order] = bg
    return out


def als_background(x, y, lam: float = 1e5, p: float = 0.01,
                   n_iter: int = 10):
    """Asymmetric Least Squares baseline (Eilers & Boelens 2005).

    A smooth baseline that hugs the troughs of the data — popular for
    Raman / FTIR / XRD.  *lam* controls smoothness (larger = stiffer),
    *p* the asymmetry (small = baseline stays below peaks).  Independent
    of x spacing (assumes roughly uniform sampling)."""
    from scipy import sparse
    from scipy.sparse.linalg import spsolve
    y = np.asarray(y, dtype=float)
    n = len(y)
    if n < 3:
        return np.zeros_like(y)
    # Second-difference penalty matrix.
    D = sparse.diags([1.0, -2.0, 1.0], [0, 1, 2], shape=(n - 2, n))
    DtD = lam * (D.transpose() @ D)
    w = np.ones(n)
    z = y.copy()
    for _ in range(n_iter):
        W = sparse.spdiags(w, 0, n, n)
        z = spsolve((W + DtD).tocsc(), w * y)
        w = p * (y > z) + (1.0 - p) * (y < z)
    return z
