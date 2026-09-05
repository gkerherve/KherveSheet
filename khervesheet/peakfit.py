"""Headless peak fitting — the numerical core behind Curve Fitting.

``FittingDialog`` used to hold this logic inline, which meant the only
way to fit peaks was to open the dialog and click.  It lives here now,
free of Qt, so the dialog, a script, and the AI / MCP tool layer all
run the *same* fit rather than three that drift apart.

The peak structure is deliberately the dialog's own: a list of
``{"func": FitFunction, "prefix": "p0_", "params": {name: spec}}``,
where each spec carries ``value``, ``min``, ``max``, ``vary`` and an
optional lmfit ``expr`` tying it to another peak.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

import numpy as np

from . import fit_models as fm

#: Passes allowed when refining an Active Shirley background against
#: the fitted peak model.
_ACTIVE_MAX_PASSES = 12


def expand_expr(expr: str, param_name: str) -> str:
    """Expand a bare peak reference in a constraint expression to the
    parameter on the same row.  In the 'center' row, ``p0`` means
    ``p0_center``; ``0.5*p1`` on the amplitude row means
    ``0.5*p1_amplitude``.  Fully-qualified names (``p0_sigma``) are left
    untouched."""
    return re.sub(r"\bp(\d+)(?!\w)",
                  lambda m: f"p{m.group(1)}_{param_name}", expr)


# ── Function lookup ────────────────────────────────────────────────

def available_functions(custom_store: Optional[dict] = None):
    """Every fittable shape, built-ins plus any custom expressions."""
    if custom_store:
        return fm.all_functions(custom_store)
    return fm.builtin_functions()


def function_by_name(name: str,
                     custom_store: Optional[dict] = None):
    """Resolve a peak shape by key or label, case-insensitively."""
    wanted = str(name).strip().lower()
    funcs = available_functions(custom_store)
    for f in funcs:
        if f.key.lower() == wanted or f.label.lower() == wanted:
            return f
    return None


def background_by_name(name: str) -> Optional[str]:
    """Resolve a background by key or label; '' and None mean 'none'."""
    if not name:
        return "none"
    wanted = str(name).strip().lower()
    for key, label, _deg in fm.BACKGROUNDS:
        if key.lower() == wanted or label.lower() == wanted:
            return key
    return None


# ── Initial parameters ─────────────────────────────────────────────

def initial_params(func, prefix: str, x=None, y=None) -> Dict[str, dict]:
    """Editable parameter dict for a new peak, seeded from the data.

    Derived parameters (a Gaussian's fwhm/height, say) are dropped:
    lmfit computes them from the free ones through an expression, and
    setting a value on one silently discards that expression.
    """
    model = func.make_model(prefix)
    pars = model.make_params()
    if x is not None and y is not None:
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)
        mask = np.isfinite(x) & np.isfinite(y)
        if mask.sum() >= 3:
            if func.guesser is not None:
                try:
                    for k, v in func.guesser(x[mask], y[mask]).items():
                        full = prefix + k
                        if full in pars and not pars[full].expr:
                            pars[full].set(value=v)
                except Exception:
                    pass
            else:
                try:
                    g = model.guess(y[mask], x=x[mask])
                    for k in pars:
                        if k in g and not pars[k].expr:
                            pars[k].set(value=g[k].value)
                except Exception:
                    pass
    out: Dict[str, dict] = {}
    for full, par in pars.items():
        if par.expr:
            continue
        name = full[len(prefix):]
        val = par.value
        if val is None or not np.isfinite(val):
            val = 1.0
        out[name] = {"value": float(val), "min": par.min,
                     "max": par.max, "vary": bool(par.vary),
                     "expr": ""}
    return out


def make_peaks(model_names: List[str], x=None, y=None,
               seeds: Optional[List[dict]] = None,
               custom_store: Optional[dict] = None) -> List[dict]:
    """Build the peak list for *model_names*, seeded from the data.

    *seeds* optionally overrides individual parameters per peak, e.g.
    ``[{"center": 285.0}, {"center": 288.5, "sigma": 0.8}]``.
    """
    peaks = []
    for i, name in enumerate(model_names):
        func = function_by_name(name, custom_store)
        if func is None:
            raise ValueError(
                f"Unknown peak shape {name!r}. "
                f"Call list_fit_models for the available shapes.")
        prefix = f"p{i}_"
        params = initial_params(func, prefix, x, y)
        for key, val in (seeds[i] if seeds and i < len(seeds) else
                         {}).items():
            if key in params and val is not None:
                params[key]["value"] = float(val)
        peaks.append({"func": func, "prefix": prefix, "params": params})
    return peaks


# ── The fit ────────────────────────────────────────────────────────

def build_model(peaks: List[dict], bg_key: str):
    """Compose the summed peak model (plus polynomial background)."""
    comp = None
    for pk in peaks:
        m = pk["func"].make_model(pk["prefix"])
        comp = m if comp is None else comp + m
    if comp is None:
        raise ValueError("Add at least one function to fit.")
    deg = fm.background_degree(bg_key)
    if deg is not None and deg >= 0:
        from lmfit.models import PolynomialModel
        comp = comp + PolynomialModel(degree=deg, prefix="bg_")
    return comp


def build_params(comp, peaks: List[dict], bg_key: str, y):
    """Apply every peak's value/bounds/expr to the composite params."""
    params = comp.make_params()
    for pk in peaks:
        for name, spec in pk["params"].items():
            full = pk["prefix"] + name
            if full not in params:
                continue
            expr = str(spec.get("expr", "")).strip()
            if expr:
                params[full].set(value=spec["value"],
                                 expr=expand_expr(expr, name))
            else:
                params[full].set(value=spec["value"], min=spec["min"],
                                 max=spec["max"], vary=spec["vary"],
                                 expr="")
    deg = fm.background_degree(bg_key)
    if deg is not None and deg >= 0:
        params["bg_c0"].set(value=float(np.nanmin(y)))
        for d in range(1, deg + 1):
            params[f"bg_c{d}"].set(value=0.0)
    return params


def run_fit(x, y, peaks: List[dict], bg_key: str = "none") -> dict:
    """Fit *peaks* to (x, y).  Raises on failure.

    Returns ``{"result": lmfit ModelResult, "background": array|None}``
    where the background array, when present, is the data-derived
    baseline that was subtracted before fitting — aligned with *x*.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    comp = build_model(peaks, bg_key)
    params = build_params(comp, peaks, bg_key, y)

    if not fm.is_data_background(bg_key):
        return {"result": comp.fit(y, params, x=x), "background": None}

    bg = fm.data_background(bg_key, x, y)
    if fm.is_active_background(bg_key):
        # Refine the Shirley against the fitted peak model until the
        # background stops moving (or we run out of passes).
        reverse = bg_key.endswith("_rev")
        tol = 1e-4 * (float(np.ptp(y)) + 1e-9)
        for _ in range(_ACTIVE_MAX_PASSES):
            result = comp.fit(y - bg, params, x=x)
            params = result.params
            new_bg = fm.active_shirley_background(
                x, y, result.best_fit, reverse=reverse)
            done = np.max(np.abs(new_bg - bg)) <= tol
            bg = new_bg
            if done:
                break
    return {"result": comp.fit(y - bg, params, x=x), "background": bg}


# ── Reporting ──────────────────────────────────────────────────────

def summarise(result, peaks: List[dict]) -> dict:
    """A JSON-friendly digest of an lmfit result, grouped by peak."""
    out = {
        "success": bool(getattr(result, "success", True)),
        "n_points": int(getattr(result, "ndata", 0)),
        "n_varys": int(getattr(result, "nvarys", 0)),
        "statistics": {},
        "peaks": [],
    }
    for key in ("chisqr", "redchi", "aic", "bic", "rsquared"):
        val = getattr(result, key, None)
        if val is not None and np.isfinite(val):
            out["statistics"][key] = float(val)
    for pk in peaks:
        entry = {"model": pk["func"].label,
                 "prefix": pk["prefix"].rstrip("_"),
                 "params": {}}
        for full, par in result.params.items():
            if not full.startswith(pk["prefix"]):
                continue
            name = full[len(pk["prefix"]):]
            entry["params"][name] = {
                "value": float(par.value),
                "stderr": (float(par.stderr)
                           if par.stderr is not None else None),
                "vary": bool(par.vary),
            }
        out["peaks"].append(entry)
    return out
