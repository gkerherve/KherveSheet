"""Formulas menu — function library catalog and menu builder.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from PyQt5.QtWidgets import QMenu

# ── Function catalog ─────────────────────────────────────────────────
# Each category maps to a sorted list of function names.
# These mirror Excel's Function Library ribbon categories.

FUNCTION_CATEGORIES = {
    "Math && Trig": [
        "ABS", "ACOS", "ACOSH", "ACOT", "ACOTH",
        "ASIN", "ASINH", "ATAN", "ATAN2", "ATANH",
        "BASE", "CEILING.MATH",
        "COMBIN", "COMBINA", "COS", "COSH", "COT", "COTH",
        "CSC", "CSCH", "DECIMAL", "DEGREES",
        "EVEN", "EXP", "FACT", "FACTDOUBLE",
        "FLOOR.MATH", "GCD", "INT", "LCM",
        "LN", "LOG", "LOG10",
        "MDETERM", "MINVERSE", "MMULT",
        "MOD", "MROUND", "MULTINOMIAL",
        "ODD", "PI", "POWER", "PRODUCT",
        "QUOTIENT", "RADIANS", "RAND", "RANDBETWEEN",
        "ROMAN", "ROUND", "ROUNDDOWN", "ROUNDUP",
        "SEC", "SECH", "SIGN", "SIN", "SINH",
        "SQRT", "SQRTPI",
        "SUBTOTAL", "SUM", "SUMIF", "SUMIFS", "SUMPRODUCT",
        "SUMSQ", "SUMX2MY2", "SUMX2PY2", "SUMXMY2",
        "TAN", "TANH", "TRUNC",
    ],
    "Text": [
        "CHAR", "CLEAN", "CODE", "CONCAT", "CONCATENATE",
        "DOLLAR", "EXACT", "FIND",
        "FIXED", "LEFT", "LEN", "LOWER",
        "MID", "NUMBERVALUE", "PROPER",
        "REPLACE", "REPT", "RIGHT",
        "SEARCH", "SUBSTITUTE",
        "T", "TEXT", "TEXTJOIN",
        "TRIM", "UNICHAR", "UNICODE",
        "UPPER", "VALUE",
    ],
    "Date && Time": [
        "DATE", "DATEVALUE", "DAY", "DAYS", "DAYS360",
        "EDATE", "EOMONTH",
        "HOUR", "ISOWEEKNUM",
        "MINUTE", "MONTH",
        "NETWORKDAYS", "NETWORKDAYS.INTL",
        "NOW", "SECOND",
        "TIME", "TIMEVALUE", "TODAY",
        "WEEKDAY", "WEEKNUM",
        "WORKDAY", "WORKDAY.INTL",
        "YEAR", "YEARFRAC",
    ],
    "Logical": [
        "AND", "FALSE", "IF", "IFERROR", "IFNA",
        "IFS", "NOT", "OR",
        "SWITCH", "TRUE", "XOR",
    ],
    "Lookup && Reference": [
        "ADDRESS", "AREAS", "CHOOSE",
        "COLUMN", "COLUMNS",
        "HLOOKUP", "INDEX",
        "INDIRECT", "LOOKUP", "MATCH",
        "OFFSET", "ROW", "ROWS",
        "TRANSPOSE", "VLOOKUP", "XLOOKUP",
    ],
    "Financial": [
        "ACCRINT", "ACCRINTM",
        "DB", "DDB",
        "DISC", "DOLLARDE", "DOLLARFR",
        "DURATION", "EFFECT",
        "FV", "FVSCHEDULE",
        "INTRATE", "IPMT", "IRR",
        "ISPMT",
        "MDURATION", "MIRR",
        "NOMINAL", "NPER", "NPV",
        "PMT", "PPMT", "PRICE", "PRICEDISC", "PRICEMAT",
        "PV", "RATE", "RECEIVED",
        "SLN", "SYD",
        "XIRR", "XNPV",
        "YIELD", "YIELDDISC", "YIELDMAT",
    ],
    "Statistical": [
        "AVERAGE", "AVERAGEA", "AVERAGEIF", "AVERAGEIFS",
        "CORREL", "COUNT", "COUNTA", "COUNTBLANK",
        "COUNTIF", "COUNTIFS",
        "FORECAST", "FREQUENCY",
        "GEOMEAN", "HARMEAN",
        "INTERCEPT",
        "LARGE", "LINEST",
        "MAX", "MAXA", "MEDIAN", "MIN", "MINA", "MODE",
        "PERCENTILE", "PERCENTRANK",
        "QUARTILE", "RANK",
        "RSQ", "SLOPE", "SMALL",
        "STDEV", "STDEVA", "STDEVP", "STDEVPA",
        "TREND", "TRIMMEAN",
        "VAR", "VARA", "VARP", "VARPA",
    ],
    "Engineering": [
        "BIN2DEC", "BIN2HEX", "BIN2OCT",
        "COMPLEX", "CONVERT",
        "DEC2BIN", "DEC2HEX", "DEC2OCT", "DELTA",
        "ERF", "ERFC",
        "GESTEP",
        "HEX2BIN", "HEX2DEC", "HEX2OCT",
        "IMABS", "IMAGINARY", "IMARGUMENT",
        "IMCONJUGATE", "IMCOS", "IMDIV",
        "IMEXP", "IMLN", "IMLOG10", "IMLOG2",
        "IMPOWER", "IMPRODUCT", "IMREAL",
        "IMSIN", "IMSQRT", "IMSUB", "IMSUM",
        "OCT2BIN", "OCT2DEC", "OCT2HEX",
    ],
    "Information": [
        "ERROR.TYPE", "ISBLANK", "ISERR", "ISERROR",
        "ISEVEN", "ISLOGICAL", "ISNA",
        "ISNONTEXT", "ISNUMBER", "ISODD",
        "ISREF", "ISTEXT",
        "N", "NA", "TYPE",
    ],
}

# Order for the menu (matches Excel's ribbon left-to-right).
CATEGORY_ORDER = [
    "Math && Trig", "Text", "Date && Time",
    "Logical", "Lookup && Reference", "Financial",
    "Statistical", "Engineering", "Information",
]


def build_formulas_menu(menu_bar, insert_callback):
    """Build the Formulas top-level menu on *menu_bar*.

    *insert_callback* is called with the function name (str) when a
    user selects a function from the library.  It should insert
    ``=FUNC()`` into the formula bar.
    """
    formulas_menu = menu_bar.addMenu("F&ormulas")

    # AutoSum shortcut
    formulas_menu.addAction(
        "AutoSum", lambda: insert_callback("SUM"), "Alt+Shift+=")
    formulas_menu.addSeparator()

    # Function Library submenus
    lib_menu = formulas_menu.addMenu("Function Library")
    for cat in CATEGORY_ORDER:
        funcs = FUNCTION_CATEGORIES.get(cat, [])
        sub = lib_menu.addMenu(cat)
        for fn in funcs:
            act = sub.addAction(fn)
            act.triggered.connect(
                lambda _, f=fn: insert_callback(f))

    return formulas_menu
