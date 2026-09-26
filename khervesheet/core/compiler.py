"""Formula compiler: '=SUM(A1:B3)*2' → a cached Python code object.

Cell refs and ranges become calls (_C, _RANGE, _COL, _XC…) that read live
values at evaluation time, so compiled code is reusable for any values.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import re

from .refs import (
    XREF_PATTERN, col_index_to_letter, compile_xref, letter_to_col_index,
)

# Names that look like cell refs but are functions/constants and so
# must not be rewritten into _C(...) calls.
CELLREF_SKIP = frozenset({
    "log", "exp", "sin", "cos", "tan", "sqrt", "abs", "int", "sum",
    "min", "max", "len", "avg", "mean", "count", "stdev", "round",
    "float", "math", "pi", "np", "asin", "acos", "atan", "sinh",
    "cosh", "tanh", "asinh", "acosh", "atanh", "date", "today",
    "now", "time", "year", "month", "day", "hour", "minute",
    "second", "days", "weekday", "left", "right", "mid", "len",
    "lower", "upper", "proper", "trim", "concat", "concatenate",
    "substitute", "rept", "find", "replace", "exact", "value",
    "text", "if", "and", "or", "not", "iferror", "xor", "true",
    "false", "mod", "power", "quotient", "sign", "even", "odd",
    "fact", "gcd", "lcm", "rand", "randbetween", "rounddown",
    "roundup", "trunc", "combin", "degrees", "radians", "ln",
    "product", "counta", "sumsq",
    # Logical extras
    "ifna", "ifs",
    # Information — N and NA omitted: they look like cell-ref
    # column letters (N1, NA1) and the function normaliser already
    # handles N(...) and NA() via the word-followed-by-paren regex.
    "isblank", "iserror", "iserr", "isna", "isnumber", "istext",
    "isnontext", "islogical", "iseven", "isodd", "isref",
    "type", "error_type",
    "countblank", "countif", "countifs", "sumif",
    # Engineering
    "dec2hex", "dec2bin", "dec2oct",
    "hex2dec", "hex2bin", "hex2oct",
    "bin2dec", "bin2hex", "bin2oct",
    "oct2dec", "oct2bin", "oct2hex",
    "delta", "gestep", "erf", "erfc",
    # Data Analysis (underscore forms after dot rewrite).
    "deriv", "deriv2", "deriv_smooth",
    "trapz", "cumtrapz", "simps",
    "savgol", "movavg", "ewma",
    "lowpass", "highpass", "bandpass", "median_filter",
    "norm_max", "norm_area", "norm_minmax", "norm_zscore",
    "norm_peak", "norm_range",
    "fft_mag", "fft_phase", "fft_freq", "fft_real", "fft_imag",
    "ifft", "fft_power",
    "interp_linear", "interp_spline", "interp_akima", "resample",
    "find_peaks", "find_peaks_x", "find_peaks_y",
    "baseline_poly", "baseline_als",
    # Lookup & Reference
    "row", "column", "rows", "columns", "choose", "address",
    "match", "index", "switch",
    "vlookup", "hlookup", "xlookup", "lookup",
    "transpose", "areas", "indirect", "offset",
    # Statistical
    "median", "var", "varp", "stdevp",
    "vara", "varpa", "stdeva", "stdevpa",
    "correl", "slope", "intercept", "rsq", "forecast",
    "large", "small", "rank",
    "percentile", "percentrank", "quartile",
    "mode", "geomean", "harmean", "trimmean",
    "averageif", "averageifs", "averagea",
    "maxa", "mina",
    "frequency", "linest", "trend",
    # Financial
    "pv", "fv", "pmt", "nper", "rate", "ipmt", "ppmt",
    "npv", "irr", "mirr", "xnpv", "xirr",
    "sln", "syd", "db", "ddb",
    "effect", "nominal", "ispmt", "fvschedule",
    "dollarde", "dollarfr",
    "accrint", "accrintm", "disc", "duration", "mduration",
    "intrate", "price", "pricedisc", "pricemat",
    "received", "yield", "yielddisc", "yieldmat",
    # Text (new)
    "char", "code", "clean", "dollar", "fixed",
    "numbervalue", "search", "textjoin",
    "unichar", "unicode",
    # Date & Time (new)
    "datevalue", "timevalue", "edate", "eomonth",
    "weeknum", "isoweeknum", "yearfrac", "days360",
    "networkdays", "workday",
    "networkdays_intl", "workday_intl",
    # Math & Trig (new)
    "acot", "acoth", "cot", "coth", "csc", "csch",
    "sec", "sech", "sqrtpi",
    "base", "decimal", "factdouble",
    "ceiling_math", "floor_math",
    "mround", "multinomial", "combina", "roman",
    "sumproduct", "sumifs",
    "sumx2my2", "sumx2py2", "sumxmy2",
    "subtotal",
    "mdeterm", "minverse", "mmult",
    # Engineering — complex numbers (new)
    "complex", "imreal", "imaginary",
    "imabs", "imargument", "imconjugate",
    "imcos", "imsin", "imexp", "imln",
    "imlog10", "imlog2", "impower", "imsqrt",
    "imsum", "imsub", "improduct", "imdiv",
    "convert"})


def compile_formula(formula, ns, ns_lower):
    """Parse a formula and compile it to a reusable code object.

    Cell refs and aggregate ranges are rewritten into _C/_AGG/_COL
    calls that read live grid values at eval time, so the compiled
    object is value-independent and safe to cache by formula text.
    Returns False if the expression cannot be compiled.
    """
    expr = formula[1:]  # strip leading =

    # Mask cross-sheet refs (Sheet1!B5, 'My Sheet'!A1:B10) with
    # letters-only placeholders so the local cell-ref/range regexes
    # below don't corrupt the embedded sheet-name string literals.
    # Restore them to _XC/_XRANGE calls after the local rewrites.
    xref_subs = {}

    def _mask_xref(m):
        name = m.group(1) if m.group(1) is not None else m.group(2)
        ref = m.group(3)
        # Token has no digits (so the cell-ref regex can't match it)
        # and an underscore (so the whole-column SUM(A) pass, which
        # matches a run of letters, can't match it either).
        token = "XSHEETREF_" + col_index_to_letter(len(xref_subs))
        xref_subs[token] = compile_xref(name, ref)
        return token

    expr = XREF_PATTERN.sub(_mask_xref, expr)

    # Rewrite dotted function names (NORM.MINMAX, FFT.MAG, …) into
    # underscore equivalents that are valid Python identifiers.
    expr = re.sub(
        r'\b([A-Za-z]+(?:\.[A-Za-z]+)+)\s*\(',
        lambda m: m.group(1).replace(".", "_") + "("
        if m.group(1).replace(".", "_").upper() in ns
        or ns_lower.get(m.group(1).replace(".", "_").lower())
        else m.group(0),
        expr)

    def _normalise_func(m):
        word = m.group(1)
        if word in ns:
            return m.group(0)
        canon = ns_lower.get(word.lower())
        return canon + "(" if canon else m.group(0)

    expr = re.sub(r'\b([A-Za-z_]\w*)\s*\(', _normalise_func, expr)
    expr = _compile_range_functions(expr)
    expr = _compile_column_functions(expr)
    expr = re.sub(r'(\$?)([A-Za-z]{1,3})(\$?)(\d+)\b',
                  _compile_cell_ref, expr)
    # IS* functions need the raw cell value (string or number),
    # not the numeric-coerced _C() result.
    expr = re.sub(
        r'\b(ISNUMBER|ISTEXT|ISNONTEXT|ISBLANK|ISLOGICAL)\(_C\(',
        r'\1(_CR(', expr)
    for token, call in xref_subs.items():
        expr = expr.replace(token, call)
    expr = expr.replace("^", "**")
    try:
        return compile(expr, "<formula>", "eval")
    except Exception:
        return False

def _compile_cell_ref(m):
    name = m.group(2)
    if name.lower() in CELLREF_SKIP:
        return m.group(0)
    c = letter_to_col_index(m.group(2))
    r = int(m.group(4)) - 1
    return f"_C({r},{c})"

def _compile_range_functions(expr: str) -> str:
    import re

    # Rewrite any A1:B10 range into a _RANGE(...) call that yields a
    # list of values.  Works regardless of surrounding context, so
    # ranges can be mixed with commas/expressions inside aggregates,
    # e.g. SUM(A1:A10, B1) or AVERAGE(A1:A3).
    def _expand(m):
        c1 = letter_to_col_index(m.group(1).upper())
        r1 = int(m.group(2)) - 1
        c2 = letter_to_col_index(m.group(3).upper())
        r2 = int(m.group(4)) - 1
        return f"_RANGE({c1},{r1},{c2},{r2})"

    pattern = (r'\$?([A-Za-z]+)\$?(\d+)\s*:\s*'
               r'\$?([A-Za-z]+)\$?(\d+)')
    return re.sub(pattern, _expand, expr)

def _compile_column_functions(expr: str) -> str:
    import re

    def _expand(m):
        func = m.group(1).lower()
        c = letter_to_col_index(m.group(2).upper())
        return f"_COL('{func}',{c})"

    pattern = (r'(SUM|AVERAGE|AVG|MEAN|MIN|MAX|COUNT|STDEV)'
               r'\s*\(\s*([A-Z]+)\s*\)')
    return re.sub(pattern, _expand, expr, flags=re.IGNORECASE)
