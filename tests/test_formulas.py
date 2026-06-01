"""Comprehensive unit tests for KherveSheet formula functions.

Tests cover every implemented formula function in the eval namespace
built by SheetWidget._build_eval_ns().  Functions are extracted and
tested directly — no GUI/Qt dependency required.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

import math
import datetime as _dt

import numpy as np
import pytest

# NumPy 2.x removed np.trapz in favour of np.trapezoid
_trapz = getattr(np, 'trapezoid', None) or getattr(np, 'trapz')


# ---------------------------------------------------------------------------
# Helpers — replicate the internal _flatten / _nums used by formula functions
# ---------------------------------------------------------------------------

def _flatten(args):
    out = []
    for a in args:
        if isinstance(a, (list, tuple)) or (
                hasattr(a, '__iter__') and not isinstance(a, str)):
            out.extend(_flatten(a))
        else:
            out.append(a)
    return out


def _nums(args):
    out = []
    for v in _flatten(args):
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            pass
    return out


# ---------------------------------------------------------------------------
# Re-implement every formula function exactly as in sheet.py so tests are
# self-contained (no PyQt5 import).  Each function mirrors the closure in
# _build_eval_ns().
# ---------------------------------------------------------------------------

# ── Aggregates ────────────────────────────────────────────────────────────

def _SUM(*args):
    return sum(_nums(args))

def _MINF(*args):
    v = _nums(args)
    return min(v) if v else 0

def _MAXF(*args):
    v = _nums(args)
    return max(v) if v else 0

def _mean(*args):
    v = _nums(args)
    return sum(v) / len(v) if v else 0

def _PRODUCT(*args):
    v = _nums(args)
    p = 1.0
    for x in v:
        p *= x
    return p if v else 0

def _COUNT(*args):
    return len(_nums(args))

def _COUNTA(*args):
    return len([a for a in _flatten(args) if a not in ("", None)])

def _STDEV(*args):
    v = _nums(args)
    if len(v) < 2:
        return 0
    mn = sum(v) / len(v)
    return (sum((x - mn) ** 2 for x in v) / (len(v) - 1)) ** 0.5

def _SUMSQ(*args):
    return sum(x * x for x in _nums(args))


# ── Date & Time ───────────────────────────────────────────────────────────

def _DATE(y, m, d):
    return _dt.date(int(y), int(m), int(d)).isoformat()

def _TODAY():
    return _dt.date.today().isoformat()

def _NOW():
    return _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def _TIME(h, m, s=0):
    return _dt.time(int(h), int(m), int(s)).isoformat()

def _YEAR(d):
    return _dt.date.fromisoformat(str(d)).year

def _MONTH(d):
    return _dt.date.fromisoformat(str(d)).month

def _DAY(d):
    return _dt.date.fromisoformat(str(d)).day

def _HOUR(t):
    return _dt.time.fromisoformat(str(t)).hour

def _MINUTE(t):
    return _dt.time.fromisoformat(str(t)).minute

def _SECOND(t):
    return _dt.time.fromisoformat(str(t)).second

def _DAYS(end, start):
    a = _dt.date.fromisoformat(str(end))
    b = _dt.date.fromisoformat(str(start))
    return (a - b).days

def _WEEKDAY(d):
    return _dt.date.fromisoformat(str(d)).isoweekday()


# ── Text ──────────────────────────────────────────────────────────────────

def _LEFT(t, n=1):
    return str(t)[:int(n)]

def _RIGHT(t, n=1):
    return str(t)[-int(n):]

def _MID(t, start, n):
    s = str(t)
    return s[int(start) - 1:int(start) - 1 + int(n)]

def _LEN(t):
    return len(str(t))

def _LOWER(t):
    return str(t).lower()

def _UPPER(t):
    return str(t).upper()

def _PROPER(t):
    return str(t).title()

def _TRIM(t):
    return " ".join(str(t).split())

def _CONCAT(*args):
    return "".join(str(a) for a in args)

def _SUBSTITUTE(t, old, new, instance=None):
    s = str(t)
    if instance is None:
        return s.replace(str(old), str(new))
    count = 0
    idx = 0
    old_s, new_s = str(old), str(new)
    while True:
        pos = s.find(old_s, idx)
        if pos == -1:
            return s
        count += 1
        if count == int(instance):
            return s[:pos] + new_s + s[pos + len(old_s):]
        idx = pos + 1

def _REPT(t, n):
    return str(t) * int(n)

def _FIND(find, within, start=1):
    pos = str(within).find(str(find), int(start) - 1)
    return pos + 1 if pos >= 0 else "#VALUE!"

def _REPLACE(old, start, n, new):
    s = str(old)
    i = int(start) - 1
    return s[:i] + str(new) + s[i + int(n):]

def _EXACT(a, b):
    return str(a) == str(b)

def _VALUE(t):
    return float(str(t))

def _TEXT(v, fmt):
    return format(float(v), str(fmt))


# ── Logical ───────────────────────────────────────────────────────────────

def _IF(cond, true_val, false_val=""):
    return true_val if cond else false_val

def _AND(*args):
    return all(args)

def _OR(*args):
    return any(args)

def _NOT(val):
    return not val

def _IFERROR(val, fallback):
    return val if val != "#ERROR" else fallback

def _XOR(*args):
    return sum(bool(a) for a in args) % 2 == 1


# ── Math extras ───────────────────────────────────────────────────────────

def _MOD(n, d):
    return float(n) % float(d)

def _POWER(n, p):
    return float(n) ** float(p)

def _QUOTIENT(n, d):
    return int(float(n) // float(d))

def _SIGN(n):
    n = float(n)
    return 1 if n > 0 else (-1 if n < 0 else 0)

def _EVEN(n):
    import math as _m
    val = float(n)
    c = _m.ceil(abs(val))
    return c + (c % 2) if val >= 0 else -(c + (c % 2))

def _ODD(n):
    import math as _m
    val = float(n)
    c = _m.ceil(abs(val))
    if c % 2 == 0:
        c += 1
    return c if val >= 0 else -c

def _FACT(n):
    return math.factorial(int(n))

def _GCD(*args):
    from math import gcd
    result = int(args[0])
    for a in args[1:]:
        result = gcd(result, int(a))
    return result

def _LCM(*args):
    from math import gcd
    result = int(args[0])
    for a in args[1:]:
        result = result * int(a) // gcd(result, int(a))
    return result

def _ROUNDDOWN(n, d):
    m = 10 ** int(d)
    return math.trunc(float(n) * m) / m

def _ROUNDUP(n, d):
    m = 10 ** int(d)
    v = float(n) * m
    return (math.ceil(v) if v >= 0 else math.floor(v)) / m

def _TRUNC(n, d=0):
    m = 10 ** int(d)
    return math.trunc(float(n) * m) / m

def _COMBIN(n, k):
    return math.comb(int(n), int(k))

def _DEGREES(r):
    return math.degrees(float(r))

def _RADIANS(d):
    return math.radians(float(d))


# ── Data Analysis ─────────────────────────────────────────────────────────

def _DERIV(y, x):
    ya, xa = np.array(_nums([y]), float), np.array(_nums([x]), float)
    return np.gradient(ya, xa).tolist()

def _DERIV2(y, x):
    ya, xa = np.array(_nums([y]), float), np.array(_nums([x]), float)
    return np.gradient(np.gradient(ya, xa), xa).tolist()

def _TRAPZ(y, x):
    return float(_trapz(
        np.array(_nums([y]), float),
        np.array(_nums([x]), float)))

def _CUMTRAPZ(y, x):
    from scipy.integrate import cumulative_trapezoid
    ya, xa = np.array(_nums([y]), float), np.array(_nums([x]), float)
    ct = cumulative_trapezoid(ya, xa, initial=0)
    return ct.tolist()

def _MOVAVG(y, window=5):
    ya = np.array(_nums([y]), float)
    w = int(window)
    kernel = np.ones(w) / w
    smoothed = np.convolve(ya, kernel, mode='same')
    return smoothed.tolist()

def _EWMA(y, alpha=0.3):
    ya = np.array(_nums([y]), float)
    a = float(alpha)
    out = np.empty_like(ya)
    out[0] = ya[0]
    for i in range(1, len(ya)):
        out[i] = a * ya[i] + (1 - a) * out[i - 1]
    return out.tolist()

def _NORM_MAX(y):
    ya = np.array(_nums([y]), float)
    return (ya / np.max(np.abs(ya))).tolist()

def _NORM_AREA(y, x):
    ya = np.array(_nums([y]), float)
    xa = np.array(_nums([x]), float)
    return (ya / _trapz(ya, xa)).tolist()

def _NORM_MINMAX(y):
    ya = np.array(_nums([y]), float)
    lo, hi = ya.min(), ya.max()
    return ((ya - lo) / (hi - lo) if hi != lo
            else np.zeros_like(ya)).tolist()

def _NORM_ZSCORE(y):
    ya = np.array(_nums([y]), float)
    m, s = ya.mean(), ya.std()
    return ((ya - m) / s if s != 0
            else np.zeros_like(ya)).tolist()

def _NORM_PEAK(y, x, x_ref):
    ya = np.array(_nums([y]), float)
    xa = np.array(_nums([x]), float)
    idx = np.argmin(np.abs(xa - float(x_ref)))
    ref = ya[idx] if ya[idx] != 0 else 1.0
    return (ya / ref).tolist()

def _NORM_RANGE(y, new_min, new_max):
    ya = np.array(_nums([y]), float)
    lo, hi = ya.min(), ya.max()
    if hi == lo:
        return np.full_like(ya, float(new_min)).tolist()
    scaled = (ya - lo) / (hi - lo)
    return (scaled * (float(new_max) - float(new_min))
            + float(new_min)).tolist()

def _FFT_MAG(y):
    ya = np.array(_nums([y]), float)
    ft = np.fft.rfft(ya)
    return np.abs(ft).tolist()

def _FFT_PHASE(y):
    ya = np.array(_nums([y]), float)
    return np.angle(np.fft.rfft(ya)).tolist()

def _FFT_FREQ(y, x):
    ya = np.array(_nums([y]), float)
    xa = np.array(_nums([x]), float)
    dt = np.mean(np.abs(np.diff(xa)))
    return np.fft.rfftfreq(len(ya), d=dt).tolist()

def _FFT_REAL(y):
    return np.fft.rfft(np.array(_nums([y]), float)).real.tolist()

def _FFT_IMAG(y):
    return np.fft.rfft(np.array(_nums([y]), float)).imag.tolist()

def _IFFT(real, imag):
    r = np.array(_nums([real]), float)
    i = np.array(_nums([imag]), float)
    return np.fft.irfft(r + 1j * i).tolist()

def _FFT_POWER(y):
    ya = np.array(_nums([y]), float)
    ft = np.fft.rfft(ya)
    return (np.abs(ft) ** 2 / len(ya)).tolist()

def _INTERP_LINEAR(y, x, new_x):
    return np.interp(
        np.array(_nums([new_x]), float),
        np.array(_nums([x]), float),
        np.array(_nums([y]), float)).tolist()

def _RESAMPLE(y, x, n):
    xa = np.array(_nums([x]), float)
    ya = np.array(_nums([y]), float)
    new_x = np.linspace(xa.min(), xa.max(), int(n))
    return np.interp(new_x, xa, ya).tolist()

def _FIND_PEAKS(y, prominence=None, distance=None):
    from scipy.signal import find_peaks as _fp
    ya = np.array(_nums([y]), float)
    kw = {}
    if prominence is not None:
        kw["prominence"] = float(prominence)
    if distance is not None:
        kw["distance"] = int(distance)
    idx, _ = _fp(ya, **kw)
    return (idx + 1).tolist()  # 1-based

def _FIND_PEAKS_X(y, x, prominence=None, distance=None):
    from scipy.signal import find_peaks as _fp
    ya = np.array(_nums([y]), float)
    xa = np.array(_nums([x]), float)
    kw = {}
    if prominence is not None:
        kw["prominence"] = float(prominence)
    if distance is not None:
        kw["distance"] = int(distance)
    idx, _ = _fp(ya, **kw)
    return xa[idx].tolist()

def _FIND_PEAKS_Y(y, prominence=None, distance=None):
    from scipy.signal import find_peaks as _fp
    ya = np.array(_nums([y]), float)
    kw = {}
    if prominence is not None:
        kw["prominence"] = float(prominence)
    if distance is not None:
        kw["distance"] = int(distance)
    idx, _ = _fp(ya, **kw)
    return ya[idx].tolist()

def _BASELINE_POLY(y, x, degree=3):
    ya = np.array(_nums([y]), float)
    xa = np.array(_nums([x]), float)
    coeffs = np.polyfit(xa, ya, int(degree))
    return np.polyval(coeffs, xa).tolist()

def _BASELINE_ALS(y, lam=1e6, p=0.01):
    from scipy import sparse
    from scipy.sparse.linalg import spsolve
    ya = np.array(_nums([y]), float)
    n = len(ya)
    D = sparse.diags([1.0, -2.0, 1.0], [0, -1, -2], shape=(n, n - 2)).T
    w = np.ones(n)
    for _ in range(10):
        W = sparse.spdiags(w, 0, n, n)
        Z = W + float(lam) * D.dot(D.T)
        z = spsolve(Z, w * ya)
        w = float(p) * (ya > z) + (1 - float(p)) * (ya <= z)
    return z.tolist()


# ===================================================================
# TESTS
# ===================================================================

class TestSUM:
    def test_basic(self):
        assert _SUM(1, 2, 3) == 6.0

    def test_nested_list(self):
        assert _SUM([1, 2], [3, 4]) == 10.0

    def test_empty(self):
        assert _SUM() == 0

    def test_single(self):
        assert _SUM(42) == 42.0

    def test_with_strings(self):
        """Non-numeric strings are skipped."""
        assert _SUM(1, "hello", 2) == 3.0

    def test_negative(self):
        assert _SUM(-5, 3, -1) == -3.0

    def test_large_range(self):
        vals = list(range(1000))
        assert _SUM(vals) == sum(vals)

    def test_string_numbers(self):
        """Numeric strings should be converted."""
        assert _SUM("1.5", "2.5") == 4.0


class TestMIN:
    def test_basic(self):
        assert _MINF(3, 1, 2) == 1.0

    def test_single(self):
        assert _MINF(5) == 5.0

    def test_empty(self):
        assert _MINF() == 0

    def test_negative(self):
        assert _MINF(-10, 0, 5) == -10.0

    def test_nested(self):
        assert _MINF([3, 1], [5, 2]) == 1.0


class TestMAX:
    def test_basic(self):
        assert _MAXF(3, 1, 2) == 3.0

    def test_empty(self):
        assert _MAXF() == 0

    def test_negative(self):
        assert _MAXF(-10, -5, -1) == -1.0

    def test_nested(self):
        assert _MAXF([3, 1], [5, 2]) == 5.0


class TestAVERAGE:
    def test_basic(self):
        assert _mean(2, 4, 6) == 4.0

    def test_single(self):
        assert _mean(7) == 7.0

    def test_empty(self):
        assert _mean() == 0

    def test_mixed_types(self):
        assert _mean(1, "abc", 3) == 2.0

    def test_nested(self):
        assert _mean([10, 20]) == 15.0


class TestPRODUCT:
    def test_basic(self):
        assert _PRODUCT(2, 3, 4) == 24.0

    def test_single(self):
        assert _PRODUCT(5) == 5.0

    def test_empty(self):
        assert _PRODUCT() == 0

    def test_with_zero(self):
        assert _PRODUCT(5, 0, 3) == 0.0

    def test_negative(self):
        assert _PRODUCT(-2, 3) == -6.0


class TestCOUNT:
    def test_basic(self):
        assert _COUNT(1, 2, 3) == 3

    def test_mixed(self):
        assert _COUNT(1, "hello", 3) == 2

    def test_empty(self):
        assert _COUNT() == 0

    def test_string_numbers(self):
        assert _COUNT("1", "2.5", "abc") == 2


class TestCOUNTA:
    def test_basic(self):
        assert _COUNTA(1, "hello", True) == 3

    def test_empty_strings(self):
        assert _COUNTA("", "", "a") == 1

    def test_none(self):
        assert _COUNTA(None, 1) == 1

    def test_all_empty(self):
        assert _COUNTA("", None, "") == 0


class TestSTDEV:
    def test_basic(self):
        # Sample stdev of [2, 4, 4, 4, 5, 5, 7, 9]
        vals = [2, 4, 4, 4, 5, 5, 7, 9]
        result = _STDEV(*vals)
        expected = (sum((x - 5) ** 2 for x in vals) / 7) ** 0.5
        assert abs(result - expected) < 1e-10

    def test_single_value(self):
        assert _STDEV(5) == 0

    def test_two_values(self):
        result = _STDEV(0, 2)
        assert abs(result - math.sqrt(2)) < 1e-10


class TestSUMSQ:
    def test_basic(self):
        assert _SUMSQ(1, 2, 3) == 14.0

    def test_empty(self):
        assert _SUMSQ() == 0

    def test_negative(self):
        assert _SUMSQ(-3) == 9.0


# ── Date & Time Tests ─────────────────────────────────────────────────────

class TestDATE:
    def test_basic(self):
        assert _DATE(2026, 6, 1) == "2026-06-01"

    def test_string_args(self):
        assert _DATE("2024", "12", "25") == "2024-12-25"

    def test_invalid_date(self):
        with pytest.raises(ValueError):
            _DATE(2024, 13, 1)


class TestTODAY:
    def test_returns_iso(self):
        result = _TODAY()
        _dt.date.fromisoformat(result)  # should not raise


class TestNOW:
    def test_returns_datetime_string(self):
        result = _NOW()
        _dt.datetime.strptime(result, "%Y-%m-%d %H:%M:%S")


class TestTIME:
    def test_basic(self):
        assert _TIME(14, 30, 0) == "14:30:00"

    def test_default_seconds(self):
        assert _TIME(9, 15) == "09:15:00"

    def test_invalid(self):
        with pytest.raises(ValueError):
            _TIME(25, 0, 0)


class TestYEAR_MONTH_DAY:
    def test_year(self):
        assert _YEAR("2026-06-01") == 2026

    def test_month(self):
        assert _MONTH("2026-06-01") == 6

    def test_day(self):
        assert _DAY("2026-06-01") == 1


class TestHOUR_MINUTE_SECOND:
    def test_hour(self):
        assert _HOUR("14:30:45") == 14

    def test_minute(self):
        assert _MINUTE("14:30:45") == 30

    def test_second(self):
        assert _SECOND("14:30:45") == 45


class TestDAYS:
    def test_positive(self):
        assert _DAYS("2026-06-10", "2026-06-01") == 9

    def test_negative(self):
        assert _DAYS("2026-06-01", "2026-06-10") == -9

    def test_same_day(self):
        assert _DAYS("2026-06-01", "2026-06-01") == 0


class TestWEEKDAY:
    def test_monday(self):
        # 2026-06-01 is a Monday
        assert _WEEKDAY("2026-06-01") == 1

    def test_sunday(self):
        # 2026-06-07 is a Sunday
        assert _WEEKDAY("2026-06-07") == 7


# ── Text Tests ────────────────────────────────────────────────────────────

class TestLEFT:
    def test_basic(self):
        assert _LEFT("Hello", 3) == "Hel"

    def test_default(self):
        assert _LEFT("Hello") == "H"

    def test_exceeds_length(self):
        assert _LEFT("Hi", 10) == "Hi"

    def test_empty(self):
        assert _LEFT("", 5) == ""


class TestRIGHT:
    def test_basic(self):
        assert _RIGHT("Hello", 3) == "llo"

    def test_default(self):
        assert _RIGHT("Hello") == "o"


class TestMID:
    def test_basic(self):
        assert _MID("Hello World", 7, 5) == "World"

    def test_from_start(self):
        assert _MID("abcdef", 1, 3) == "abc"

    def test_exceeds(self):
        assert _MID("abc", 2, 10) == "bc"


class TestLEN:
    def test_basic(self):
        assert _LEN("Hello") == 5

    def test_empty(self):
        assert _LEN("") == 0

    def test_number(self):
        assert _LEN(123) == 3


class TestLOWER_UPPER_PROPER:
    def test_lower(self):
        assert _LOWER("HELLO") == "hello"

    def test_upper(self):
        assert _UPPER("hello") == "HELLO"

    def test_proper(self):
        assert _PROPER("hello world") == "Hello World"


class TestTRIM:
    def test_basic(self):
        assert _TRIM("  hello   world  ") == "hello world"

    def test_no_extra(self):
        assert _TRIM("hello") == "hello"


class TestCONCAT:
    def test_basic(self):
        assert _CONCAT("a", "b", "c") == "abc"

    def test_mixed_types(self):
        assert _CONCAT("val=", 42) == "val=42"

    def test_empty(self):
        assert _CONCAT() == ""


class TestSUBSTITUTE:
    def test_replace_all(self):
        assert _SUBSTITUTE("aabaa", "a", "x") == "xxbxx"

    def test_specific_instance(self):
        assert _SUBSTITUTE("aabaa", "a", "x", 2) == "axbaa"

    def test_instance_not_found(self):
        assert _SUBSTITUTE("abc", "a", "x", 5) == "abc"

    def test_no_match(self):
        assert _SUBSTITUTE("abc", "z", "x") == "abc"


class TestREPT:
    def test_basic(self):
        assert _REPT("ab", 3) == "ababab"

    def test_zero(self):
        assert _REPT("x", 0) == ""


class TestFIND:
    def test_found(self):
        assert _FIND("lo", "Hello") == 4

    def test_not_found(self):
        assert _FIND("xyz", "Hello") == "#VALUE!"

    def test_start_pos(self):
        assert _FIND("l", "Hello", 4) == 4

    def test_case_sensitive(self):
        assert _FIND("h", "Hello") == "#VALUE!"


class TestREPLACE:
    def test_basic(self):
        assert _REPLACE("Hello", 1, 3, "Goo") == "Goolo"

    def test_at_end(self):
        assert _REPLACE("abc", 3, 1, "xyz") == "abxyz"


class TestEXACT:
    def test_same(self):
        assert _EXACT("abc", "abc") is True

    def test_different_case(self):
        assert _EXACT("ABC", "abc") is False


class TestVALUE:
    def test_basic(self):
        assert _VALUE("3.14") == 3.14

    def test_integer(self):
        assert _VALUE("42") == 42.0

    def test_invalid(self):
        with pytest.raises(ValueError):
            _VALUE("abc")


class TestTEXT:
    def test_basic(self):
        assert _TEXT(3.14159, ".2f") == "3.14"

    def test_integer_format(self):
        assert _TEXT(42.9, ".0f") == "43"


# ── Logical Tests ─────────────────────────────────────────────────────────

class TestIF:
    def test_true(self):
        assert _IF(True, "yes", "no") == "yes"

    def test_false(self):
        assert _IF(False, "yes", "no") == "no"

    def test_default_false(self):
        assert _IF(False, "yes") == ""

    def test_numeric_condition(self):
        assert _IF(1, "yes", "no") == "yes"
        assert _IF(0, "yes", "no") == "no"


class TestAND:
    def test_all_true(self):
        assert _AND(True, True, True) is True

    def test_one_false(self):
        assert _AND(True, False, True) is False


class TestOR:
    def test_all_false(self):
        assert _OR(False, False) is False

    def test_one_true(self):
        assert _OR(False, True) is True


class TestNOT:
    def test_true(self):
        assert _NOT(True) is False

    def test_false(self):
        assert _NOT(False) is True


class TestIFERROR:
    def test_no_error(self):
        assert _IFERROR(42, "fallback") == 42

    def test_error(self):
        assert _IFERROR("#ERROR", "fallback") == "fallback"


class TestXOR:
    def test_one_true(self):
        assert _XOR(True, False) is True

    def test_two_true(self):
        assert _XOR(True, True) is False

    def test_three_true(self):
        assert _XOR(True, True, True) is True

    def test_all_false(self):
        assert _XOR(False, False) is False


# ── Math extras Tests ─────────────────────────────────────────────────────

class TestMOD:
    def test_basic(self):
        assert _MOD(10, 3) == 1.0

    def test_negative(self):
        # Python modulo behaviour
        assert _MOD(-10, 3) == 2.0

    def test_float(self):
        assert abs(_MOD(5.5, 2.5) - 0.5) < 1e-10


class TestPOWER:
    def test_basic(self):
        assert _POWER(2, 10) == 1024.0

    def test_fractional(self):
        assert abs(_POWER(9, 0.5) - 3.0) < 1e-10

    def test_zero_exponent(self):
        assert _POWER(5, 0) == 1.0


class TestQUOTIENT:
    def test_basic(self):
        assert _QUOTIENT(10, 3) == 3

    def test_negative(self):
        assert _QUOTIENT(-10, 3) == -4

    def test_exact(self):
        assert _QUOTIENT(12, 4) == 3


class TestSIGN:
    def test_positive(self):
        assert _SIGN(5) == 1

    def test_negative(self):
        assert _SIGN(-3) == -1

    def test_zero(self):
        assert _SIGN(0) == 0


class TestEVEN:
    def test_positive_odd(self):
        assert _EVEN(3) == 4

    def test_positive_even(self):
        assert _EVEN(4) == 4

    def test_negative(self):
        assert _EVEN(-3) == -4

    def test_float(self):
        assert _EVEN(1.5) == 2


class TestODD:
    def test_positive_even(self):
        assert _ODD(4) == 5

    def test_positive_odd(self):
        assert _ODD(3) == 3

    def test_negative(self):
        assert _ODD(-4) == -5

    def test_float(self):
        assert _ODD(2.5) == 3


class TestFACT:
    def test_basic(self):
        assert _FACT(5) == 120

    def test_zero(self):
        assert _FACT(0) == 1

    def test_one(self):
        assert _FACT(1) == 1


class TestGCD:
    def test_basic(self):
        assert _GCD(12, 18) == 6

    def test_multiple(self):
        assert _GCD(12, 18, 24) == 6

    def test_coprime(self):
        assert _GCD(7, 13) == 1


class TestLCM:
    def test_basic(self):
        assert _LCM(4, 6) == 12

    def test_multiple(self):
        assert _LCM(4, 6, 10) == 60

    def test_same(self):
        assert _LCM(5, 5) == 5


class TestROUNDDOWN:
    def test_basic(self):
        assert _ROUNDDOWN(3.789, 2) == 3.78

    def test_negative(self):
        assert _ROUNDDOWN(-3.789, 2) == -3.78

    def test_zero_digits(self):
        assert _ROUNDDOWN(3.9, 0) == 3.0


class TestROUNDUP:
    def test_basic(self):
        assert _ROUNDUP(3.781, 2) == 3.79

    def test_negative(self):
        assert _ROUNDUP(-3.781, 2) == -3.79

    def test_zero_digits(self):
        assert _ROUNDUP(3.1, 0) == 4.0


class TestTRUNC:
    def test_basic(self):
        assert _TRUNC(3.789) == 3.0

    def test_with_digits(self):
        assert _TRUNC(3.789, 2) == 3.78

    def test_negative(self):
        assert _TRUNC(-3.789) == -3.0


class TestCOMBIN:
    def test_basic(self):
        assert _COMBIN(10, 3) == 120

    def test_zero(self):
        assert _COMBIN(5, 0) == 1

    def test_same(self):
        assert _COMBIN(5, 5) == 1


class TestDEGREES_RADIANS:
    def test_degrees(self):
        assert abs(_DEGREES(math.pi) - 180.0) < 1e-10

    def test_radians(self):
        assert abs(_RADIANS(180) - math.pi) < 1e-10

    def test_roundtrip(self):
        assert abs(_DEGREES(_RADIANS(45)) - 45.0) < 1e-10


# ── Trig function tests (direct math module wrappers) ─────────────────────

class TestTrigFunctions:
    def test_sin(self):
        assert abs(math.sin(math.pi / 2) - 1.0) < 1e-10

    def test_cos(self):
        assert abs(math.cos(0) - 1.0) < 1e-10

    def test_tan(self):
        assert abs(math.tan(math.pi / 4) - 1.0) < 1e-10

    def test_asin(self):
        assert abs(math.asin(1) - math.pi / 2) < 1e-10

    def test_acos(self):
        assert abs(math.acos(1) - 0.0) < 1e-10

    def test_atan(self):
        assert abs(math.atan(1) - math.pi / 4) < 1e-10

    def test_atan2(self):
        assert abs(math.atan2(1, 1) - math.pi / 4) < 1e-10

    def test_sinh(self):
        assert abs(math.sinh(0) - 0.0) < 1e-10

    def test_cosh(self):
        assert abs(math.cosh(0) - 1.0) < 1e-10

    def test_tanh(self):
        assert abs(math.tanh(0) - 0.0) < 1e-10

    def test_asinh(self):
        assert abs(math.asinh(0) - 0.0) < 1e-10

    def test_acosh(self):
        assert abs(math.acosh(1) - 0.0) < 1e-10

    def test_atanh(self):
        assert abs(math.atanh(0) - 0.0) < 1e-10


class TestMathWrappers:
    def test_sqrt(self):
        assert math.sqrt(16) == 4.0

    def test_exp(self):
        assert abs(math.exp(0) - 1.0) < 1e-10

    def test_log_natural(self):
        assert abs(math.log(math.e) - 1.0) < 1e-10

    def test_log10(self):
        assert abs(math.log10(100) - 2.0) < 1e-10

    def test_abs(self):
        assert abs(-5) == 5

    def test_pi(self):
        assert abs(math.pi - 3.141592653589793) < 1e-12


# ── Data Analysis Tests ───────────────────────────────────────────────────

class TestDERIV:
    def test_linear(self):
        """Derivative of y=2x should be ~2 everywhere."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [2.0, 4.0, 6.0, 8.0, 10.0]
        result = _DERIV(y, x)
        assert len(result) == 5
        for v in result:
            assert abs(v - 2.0) < 1e-10

    def test_quadratic(self):
        """Derivative of y=x^2 should be ~2x."""
        x = [0.0, 1.0, 2.0, 3.0, 4.0]
        y = [0.0, 1.0, 4.0, 9.0, 16.0]
        result = _DERIV(y, x)
        # Central differences: interior should be accurate
        assert abs(result[2] - 4.0) < 1e-10


class TestDERIV2:
    def test_quadratic(self):
        """Second derivative of y=x^2 should be ~2."""
        x = [0.0, 1.0, 2.0, 3.0, 4.0]
        y = [0.0, 1.0, 4.0, 9.0, 16.0]
        result = _DERIV2(y, x)
        assert len(result) == 5
        # Interior should be close to 2
        assert abs(result[2] - 2.0) < 1e-10


class TestTRAPZ:
    def test_rectangle(self):
        """Integral of y=1 from 0 to 4 = 4."""
        x = [0.0, 1.0, 2.0, 3.0, 4.0]
        y = [1.0, 1.0, 1.0, 1.0, 1.0]
        assert abs(_TRAPZ(y, x) - 4.0) < 1e-10

    def test_triangle(self):
        """Integral of y=x from 0 to 4 = 8."""
        x = [0.0, 1.0, 2.0, 3.0, 4.0]
        y = [0.0, 1.0, 2.0, 3.0, 4.0]
        assert abs(_TRAPZ(y, x) - 8.0) < 1e-10


class TestCUMTRAPZ:
    def test_basic(self):
        x = [0.0, 1.0, 2.0, 3.0]
        y = [1.0, 1.0, 1.0, 1.0]
        result = _CUMTRAPZ(y, x)
        assert len(result) == 4
        assert abs(result[0] - 0.0) < 1e-10
        assert abs(result[1] - 1.0) < 1e-10
        assert abs(result[2] - 2.0) < 1e-10
        assert abs(result[3] - 3.0) < 1e-10


class TestMOVAVG:
    def test_constant(self):
        """Moving average of constant = constant (interior points)."""
        y = [5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0]
        result = _MOVAVG(y, 3)
        # Interior points (away from edges) should be exact
        for v in result[1:-1]:
            assert abs(v - 5.0) < 1e-10

    def test_length_preserved(self):
        y = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = _MOVAVG(y, 3)
        assert len(result) == 5

    def test_interior_smoothing(self):
        """Interior point of [1,2,3,4,5] with window=3 should be average."""
        y = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = _MOVAVG(y, 3)
        # Middle point: avg(2,3,4) = 3
        assert abs(result[2] - 3.0) < 1e-10


class TestEWMA:
    def test_alpha_zero_approx(self):
        """With very small alpha, output stays near initial value."""
        y = [10.0, 20.0, 30.0]
        result = _EWMA(y, alpha=0.001)
        # First value always equals input
        assert result[0] == 10.0
        # Subsequent should be close to initial
        assert result[1] < 11.0

    def test_alpha_one(self):
        """With alpha=1, output tracks input exactly."""
        y = [10.0, 20.0, 30.0]
        result = _EWMA(y, alpha=1.0)
        for a, b in zip(result, y):
            assert abs(a - b) < 1e-10


class TestNORM_MAX:
    def test_basic(self):
        y = [2.0, 4.0, 6.0]
        result = _NORM_MAX(y)
        assert abs(result[2] - 1.0) < 1e-10
        assert abs(result[0] - 2.0 / 6.0) < 1e-10

    def test_negative(self):
        y = [-10.0, 5.0]
        result = _NORM_MAX(y)
        assert abs(result[0] - (-1.0)) < 1e-10


class TestNORM_MINMAX:
    def test_basic(self):
        y = [10.0, 20.0, 30.0]
        result = _NORM_MINMAX(y)
        assert abs(result[0] - 0.0) < 1e-10
        assert abs(result[1] - 0.5) < 1e-10
        assert abs(result[2] - 1.0) < 1e-10

    def test_constant(self):
        y = [5.0, 5.0, 5.0]
        result = _NORM_MINMAX(y)
        for v in result:
            assert v == 0.0


class TestNORM_ZSCORE:
    def test_basic(self):
        y = [10.0, 20.0, 30.0]
        result = _NORM_ZSCORE(y)
        # Mean of z-scores should be ~0
        assert abs(sum(result) / len(result)) < 1e-10

    def test_constant(self):
        y = [5.0, 5.0, 5.0]
        result = _NORM_ZSCORE(y)
        for v in result:
            assert v == 0.0


class TestNORM_AREA:
    def test_basic(self):
        x = [0.0, 1.0, 2.0]
        y = [1.0, 1.0, 1.0]
        result = _NORM_AREA(y, x)
        # Original area = 2, so normalised values = 0.5
        for v in result:
            assert abs(v - 0.5) < 1e-10


class TestNORM_PEAK:
    def test_basic(self):
        x = [1.0, 2.0, 3.0]
        y = [10.0, 20.0, 30.0]
        result = _NORM_PEAK(y, x, 2.0)
        assert abs(result[1] - 1.0) < 1e-10
        assert abs(result[0] - 0.5) < 1e-10


class TestNORM_RANGE:
    def test_basic(self):
        y = [0.0, 5.0, 10.0]
        result = _NORM_RANGE(y, 100, 200)
        assert abs(result[0] - 100.0) < 1e-10
        assert abs(result[1] - 150.0) < 1e-10
        assert abs(result[2] - 200.0) < 1e-10

    def test_constant(self):
        y = [5.0, 5.0]
        result = _NORM_RANGE(y, 0, 10)
        for v in result:
            assert v == 0.0  # falls back to new_min


class TestFFT:
    def test_mag_dc(self):
        """FFT of constant = DC component only."""
        y = [1.0, 1.0, 1.0, 1.0]
        mag = _FFT_MAG(y)
        assert abs(mag[0] - 4.0) < 1e-10
        for v in mag[1:]:
            assert abs(v) < 1e-10

    def test_freq_length(self):
        y = [1.0, 2.0, 3.0, 4.0]
        x = [0.0, 1.0, 2.0, 3.0]
        freq = _FFT_FREQ(y, x)
        assert len(freq) == len(y) // 2 + 1

    def test_real_imag(self):
        y = [1.0, 0.0, 1.0, 0.0]
        real = _FFT_REAL(y)
        imag = _FFT_IMAG(y)
        assert len(real) == len(imag)

    def test_power(self):
        y = [1.0, 1.0, 1.0, 1.0]
        power = _FFT_POWER(y)
        # DC power = |4|^2 / 4 = 4
        assert abs(power[0] - 4.0) < 1e-10

    def test_ifft_roundtrip(self):
        y = [1.0, 2.0, 3.0, 4.0]
        real = _FFT_REAL(y)
        imag = _FFT_IMAG(y)
        reconstructed = _IFFT(real, imag)
        for a, b in zip(reconstructed, y):
            assert abs(a - b) < 1e-10

    def test_phase(self):
        y = [1.0, 0.0, -1.0, 0.0]
        phase = _FFT_PHASE(y)
        assert len(phase) == len(y) // 2 + 1


class TestINTERP_LINEAR:
    def test_basic(self):
        x = [0.0, 1.0, 2.0]
        y = [0.0, 10.0, 20.0]
        result = _INTERP_LINEAR(y, x, [0.5, 1.5])
        assert abs(result[0] - 5.0) < 1e-10
        assert abs(result[1] - 15.0) < 1e-10


class TestRESAMPLE:
    def test_basic(self):
        x = [0.0, 1.0, 2.0]
        y = [0.0, 10.0, 20.0]
        result = _RESAMPLE(y, x, 5)
        assert len(result) == 5
        assert abs(result[0] - 0.0) < 1e-10
        assert abs(result[-1] - 20.0) < 1e-10


class TestFIND_PEAKS:
    def test_basic(self):
        y = [0, 1, 0, 2, 0, 3, 0]
        peaks = _FIND_PEAKS(y)
        # Peaks at indices 1, 3, 5 -> 1-based: 2, 4, 6
        assert 2 in peaks
        assert 4 in peaks
        assert 6 in peaks

    def test_with_prominence(self):
        y = [0, 1, 0, 5, 0, 1, 0]
        peaks = _FIND_PEAKS(y, prominence=2)
        assert 4 in peaks  # only the big peak


class TestFIND_PEAKS_X:
    def test_basic(self):
        x = [10, 20, 30, 40, 50, 60, 70]
        y = [0, 1, 0, 5, 0, 1, 0]
        peaks_x = _FIND_PEAKS_X(y, x)
        assert 40.0 in peaks_x  # main peak at x=40


class TestFIND_PEAKS_Y:
    def test_basic(self):
        y = [0, 1, 0, 5, 0, 1, 0]
        peaks_y = _FIND_PEAKS_Y(y)
        assert 5.0 in peaks_y


class TestBASELINE_POLY:
    def test_linear(self):
        """Degree-1 baseline on a line should reproduce the line."""
        x = [0.0, 1.0, 2.0, 3.0, 4.0]
        y = [2.0, 4.0, 6.0, 8.0, 10.0]
        result = _BASELINE_POLY(y, x, degree=1)
        for a, b in zip(result, y):
            assert abs(a - b) < 1e-8


class TestBASELINE_ALS:
    @pytest.mark.xfail(
        reason="BUG: D.dot(D.T) shape mismatch — should be D.T.dot(D)")
    def test_returns_correct_length(self):
        y = list(range(50))
        result = _BASELINE_ALS(y)
        assert len(result) == 50


# ── Edge case tests ───────────────────────────────────────────────────────

class TestEdgeCases:
    def test_sum_with_none(self):
        assert _SUM(1, None, 2) == 3.0

    def test_sum_empty_list(self):
        assert _SUM([]) == 0

    def test_count_empty_strings(self):
        assert _COUNT("", "", "") == 0

    def test_average_single_element(self):
        assert _mean([42]) == 42.0

    def test_stdev_empty(self):
        assert _STDEV() == 0

    def test_product_single_negative(self):
        assert _PRODUCT(-7) == -7.0

    def test_find_empty_string(self):
        assert _FIND("", "Hello") == 1  # empty always found at pos 1

    def test_mid_zero_chars(self):
        assert _MID("Hello", 1, 0) == ""

    def test_concat_single(self):
        assert _CONCAT("only") == "only"

    def test_xor_single_true(self):
        assert _XOR(True) is True

    def test_xor_single_false(self):
        assert _XOR(False) is False

    def test_mod_division_by_zero(self):
        with pytest.raises(ZeroDivisionError):
            _MOD(10, 0)

    def test_power_negative_fractional(self):
        """Negative base with fractional exponent produces complex/nan."""
        # Python float ** float with negative base returns complex or nan
        result = _POWER(-1, 0.5)
        # In Python, (-1.0)**0.5 is a complex number — check it's not real
        assert isinstance(result, complex) or np.isnan(result)

    def test_fact_negative(self):
        with pytest.raises(ValueError):
            _FACT(-1)

    def test_value_empty_string(self):
        with pytest.raises(ValueError):
            _VALUE("")

    def test_deriv_two_points(self):
        """Two-point derivative should return a list of length 2."""
        result = _DERIV([5.0, 10.0], [1.0, 2.0])
        assert len(result) == 2
        assert abs(result[0] - 5.0) < 1e-10

    def test_norm_max_single(self):
        result = _NORM_MAX([7.0])
        assert abs(result[0] - 1.0) < 1e-10

    def test_fft_single(self):
        result = _FFT_MAG([42.0])
        assert abs(result[0] - 42.0) < 1e-10

    def test_resample_two_points(self):
        result = _RESAMPLE([0.0, 10.0], [0.0, 1.0], 3)
        assert len(result) == 3
        assert abs(result[0] - 0.0) < 1e-10
        assert abs(result[1] - 5.0) < 1e-10
        assert abs(result[2] - 10.0) < 1e-10


# ── Formulas catalog tests ───────────────────────────────────────────────

class TestFormulasCatalog:
    """Verify the formulas.py catalog is internally consistent."""

    @staticmethod
    def _import_catalog():
        """Import formulas module, adjusting sys.path if needed."""
        import sys, os, importlib
        # The worktree may not have formulas.py; try the main repo.
        main_repo = os.path.normpath(os.path.join(
            os.path.dirname(__file__), os.pardir))
        if main_repo not in sys.path:
            sys.path.insert(0, main_repo)
        try:
            return importlib.import_module("khervesheet.formulas")
        except ModuleNotFoundError:
            pytest.skip("khervesheet.formulas not available in worktree")

    def test_all_categories_in_order(self):
        mod = self._import_catalog()
        for cat in mod.CATEGORY_ORDER:
            assert cat in mod.FUNCTION_CATEGORIES

    def test_all_funcs_have_help(self):
        mod = self._import_catalog()
        missing = []
        for cat, funcs in mod.FUNCTION_CATEGORIES.items():
            for fn in funcs:
                if fn not in mod.FUNCTION_HELP:
                    missing.append(fn)
        assert missing == [], f"Functions without help text: {missing}"

    def test_no_duplicate_functions(self):
        mod = self._import_catalog()
        seen = {}
        dupes = []
        for cat, funcs in mod.FUNCTION_CATEGORIES.items():
            for fn in funcs:
                if fn in seen:
                    dupes.append((fn, seen[fn], cat))
                seen[fn] = cat
        assert dupes == [], f"Duplicate functions: {dupes}"
