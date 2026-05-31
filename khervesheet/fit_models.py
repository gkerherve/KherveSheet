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
                 factory: Callable, expr: str = "", guesser=None):
        self.key = key
        self.label = label
        self.group = group
        self._factory = factory
        self.expr = expr  # populated for user-built custom functions
        # Optional guesser(x, y) -> {param_name: value}; used for models
        # that don't ship an lmfit .guess() (our stable replacements).
        self.guesser = guesser

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
    area = float(np.trapz(yy, x)) or (height * sigma)
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
        funcs.append(FitFunction("lmfit:" + cls_name, label, group,
                                 _builtin_factory(cls_name)))
    # Voigt with both widths free (sigma = Gaussian, gamma = Lorentzian).
    funcs.insert(2, FitFunction(
        "voigt_sg", "Voigt", "Common / XRD", _voigt_factory,
        guesser=_voigt_guess))
    # Stable EMG (replaces lmfit's NaN-prone ExponentialGaussianModel).
    funcs.append(FitFunction(
        "emg_stable", "Exp.-modified Gaussian", "TGA / chromatography",
        _emg_factory, guesser=_emg_guess))
    return funcs


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

# Analytic backgrounds expose a polynomial degree (-1 = none).
BACKGROUNDS = [
    ("none", "None", -1),
    ("constant", "Constant", 0),
    ("linear", "Linear", 1),
    ("poly2", "Polynomial (2)", 2),
    ("poly3", "Polynomial (3)", 3),
    ("shirley", "Shirley (XPS)", None),
    ("tougaard", "Tougaard (XPS)", None),
]

_BG_DEGREE = {k: deg for k, _, deg in BACKGROUNDS}


def background_degree(key: str):
    """Polynomial degree for an analytic background, or None if the
    background is data-derived (Shirley/Tougaard) or absent."""
    return _BG_DEGREE.get(key, -1)


def is_data_background(key: str) -> bool:
    return key in ("shirley", "tougaard")


def shirley_background(x, y, max_iter: int = 50, tol: float = 1e-6):
    """Iterative Shirley background between the two range endpoints.

    Returns an array the same length as *y*. Robust to ascending or
    descending x (XPS binding-energy axes run high→low)."""
    y = np.asarray(y, dtype=float)
    n = len(y)
    if n < 2:
        return np.zeros_like(y)
    order = np.argsort(x)
    ys = y[order]
    y_lo, y_hi = ys[0], ys[-1]
    bg = np.linspace(y_lo, y_hi, n)
    for _ in range(max_iter):
        above = np.clip(ys - bg, 0.0, None)
        cum = np.concatenate(([0.0], np.cumsum(
            (above[:-1] + above[1:]) / 2.0)))
        total = cum[-1]
        if total <= 0:
            break
        new_bg = y_hi + (y_lo - y_hi) * (cum / total) \
            if y_lo < y_hi else y_lo + (y_hi - y_lo) * (1.0 - cum / total)
        if np.max(np.abs(new_bg - bg)) < tol * (abs(total) + 1e-12):
            bg = new_bg
            break
        bg = new_bg
    out = np.empty_like(bg)
    out[order] = bg
    return out


def tougaard_background(x, y, b: float = 2866.0, c: float = 1643.0):
    """Two-parameter universal Tougaard background (XPS).

    Uses the universal cross-section K(T) = B·T / (C + T²)² convolved
    with the spectrum above the high-kinetic-energy endpoint."""
    order = np.argsort(x)
    xs = np.asarray(x, dtype=float)[order]
    ys = np.asarray(y, dtype=float)[order]
    n = len(ys)
    if n < 2:
        return np.zeros_like(y)
    base = ys[-1]
    f = ys - base
    bg = np.zeros(n)
    for i in range(n):
        t = xs[i:] - xs[i]
        k = b * t / (c + t ** 2) ** 2
        bg[i] = np.trapz(k * f[i:], xs[i:])
    bg = bg + base
    out = np.empty(n)
    out[order] = bg
    return out
