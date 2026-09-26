"""Shared input for the formula golden tests: a small workbook and ~200
formulas covering every family of functions, references and syntax.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

# Cell values by sheet: {(row, col): text}. Column A holds 1..10, B their
# squares, C text, D booleans, E mixed, F a noisy signal, G/H x-y data.
DATA = {
    "Data": {
        **{(r, 0): str(r + 1) for r in range(10)},
        **{(r, 1): str((r + 1) ** 2) for r in range(10)},
        (0, 2): "apple", (1, 2): "Banana", (2, 2): "cherry",
        (3, 2): "  spaced  ", (4, 2): "apple",
        (0, 3): "TRUE", (1, 3): "FALSE", (2, 3): "TRUE",
        (0, 4): "3.5", (1, 4): "x", (3, 4): "-2", (4, 4): "0",
        **{(r, 5): repr(round(((r * 37) % 11) / 3.0 + r * 0.5, 4))
           for r in range(20)},
        **{(r, 6): str(r * 0.5) for r in range(12)},
        **{(r, 7): repr(round(2.0 * (r * 0.5) + 1.0 + ((r % 3) - 1) * 0.1, 4))
           for r in range(12)},
    },
    # I1 holds a formula whose shown value (0.33) is rounded; I2 reads it.
    "Precision": {(0, 0): "=1/3", (1, 0): "=A1*3", (2, 0): "0.123456789"},
    "Other Sheet": {
        (0, 0): "100", (1, 0): "200", (2, 0): "300",
        (0, 1): "hello",
    },
}

FORMULAS = [
    # References and arithmetic
    "=A1", "=A1+B2", "=A10*B10-3", "=A2^3", "=(A1+A2)/A4", "=$A$3",
    "=A$3+$B4", "=-A5", "=A1/0", "=C1", "=Z99", "=D1", "=D1+D3",
    "=E1*2", "=E2", "=A1&\"x\"", "=2^10", "=7 % 3" if False else "=MOD(7,3)",
    # Aggregates, ranges and whole columns
    "=SUM(A1:A10)", "=SUM(A1:A10, B1)", "=SUM(A)", "=AVERAGE(A1:A10)",
    "=AVG(B1:B10)", "=MEAN(A)", "=MIN(B1:B10)", "=MAX(B)", "=COUNT(A)",
    "=COUNT(C1:C5)", "=COUNTA(C1:C5)", "=STDEV(A1:A10)", "=SUMSQ(A1:A3)",
    "=PRODUCT(A1:A5)", "=SUM(D1:D3)", "=MEDIAN(A1:A10)", "=MODE(1,2,2,3)",
    "=VAR(A1:A10)", "=VARP(A1:A10)", "=STDEVP(A1:A10)", "=GEOMEAN(A1:A5)",
    "=HARMEAN(A1:A5)", "=TRIMMEAN(A1:A10,0.2)", "=LARGE(B1:B10,2)",
    "=SMALL(B1:B10,3)", "=RANK(5,A1:A10)", "=PERCENTILE(A1:A10,0.9)",
    "=QUARTILE(A1:A10,1)", "=PERCENTRANK(A1:A10,4)", "=AVERAGEA(E1:E5)",
    "=MAXA(E1:E5)", "=MINA(E1:E5)", "=CORREL(A1:A10,B1:B10)",
    "=SLOPE(H1:H12,G1:G12)", "=INTERCEPT(H1:H12,G1:G12)",
    "=RSQ(H1:H12,G1:G12)", "=FORECAST(20,H1:H12,G1:G12)",
    "=COUNTIF(A1:A10,\">5\")", "=COUNTIF(C1:C5,\"apple\")",
    "=SUMIF(A1:A10,\">5\")", "=SUMIF(A1:A10,\">5\",B1:B10)",
    "=AVERAGEIF(A1:A10,\"<4\")", "=COUNTBLANK(E1:E5)",
    "=COUNTIFS(A1:A10,\">2\",B1:B10,\"<50\")",
    "=SUMIFS(B1:B10,A1:A10,\">2\",A1:A10,\"<6\")",
    "=AVERAGEIFS(B1:B10,A1:A10,\">5\")", "=SUMPRODUCT(A1:A3,B1:B3)",
    "=SUBTOTAL(9,A1:A10)", "=SUBTOTAL(1,A1:A4)",
    # Maths and trigonometry
    "=ABS(-3.2)", "=SQRT(B4)", "=POWER(2,0.5)", "=EXP(1)", "=LN(10)",
    "=LOG(100)", "=LOG(8,2)", "=LOG10(1000)", "=PI()", "=SIN(PI()/2)",
    "=COS(0)", "=TAN(PI()/4)", "=ASIN(1)", "=ACOS(0)", "=ATAN(1)",
    "=ATAN2(1,1)", "=SINH(1)", "=COSH(1)", "=TANH(0.5)", "=DEGREES(PI())",
    "=RADIANS(180)", "=ROUND(2.345,2)", "=ROUNDUP(2.341,2)",
    "=ROUNDDOWN(2.349,2)", "=TRUNC(-2.7)", "=INT(-2.5)", "=CEILING(2.1,1)",
    "=FLOOR(2.9,1)", "=MROUND(10,3)", "=SIGN(-4)", "=EVEN(3)", "=ODD(4)",
    "=FACT(6)", "=FACTDOUBLE(7)", "=COMBIN(10,3)", "=COMBINA(4,2)",
    "=GCD(24,36)", "=LCM(4,6)", "=QUOTIENT(17,5)", "=MOD(-7,3)",
    "=MULTINOMIAL(2,3)", "=ROMAN(1999)", "=BASE(255,16)",
    "=DECIMAL(\"FF\",16)", "=SQRTPI(2)", "=SEC(0.5)", "=CSC(0.5)",
    "=COT(0.5)", "=SUMX2MY2(A1:A3,B1:B3)", "=SUMX2PY2(A1:A3,B1:B3)",
    "=SUMXMY2(A1:A3,B1:B3)", "=MDETERM(A1:B2)", "=CEILING.MATH(2.5)",
    "=FLOOR.MATH(-2.5)",
    # Logic and information
    "=IF(A1>0,\"pos\",\"neg\")", "=IF(D2,1,2)", "=AND(A1>0,A2>1)",
    "=OR(A1>5,A2>5)", "=NOT(A1>5)", "=XOR(TRUE,FALSE)",
    "=IFERROR(1/0,\"div\")", "=IFS(A3>5,\"big\",A3>1,\"mid\")",
    "=SWITCH(2,1,\"one\",2,\"two\")", "=CHOOSE(2,\"a\",\"b\",\"c\")",
    "=ISNUMBER(A1)", "=ISNUMBER(C1)", "=ISTEXT(C1)", "=ISBLANK(E3)",
    "=ISBLANK(A1)", "=ISEVEN(4)", "=ISODD(4)", "=ISLOGICAL(TRUE)",
    "=ISNONTEXT(A1)", "=TYPE(\"a\")", "=TRUE()" if False else "=TRUE",
    # Text
    "=LEN(C2)", "=UPPER(C1)", "=LOWER(C2)", "=PROPER(\"hello world\")",
    "=TRIM(C4)", "=LEFT(C2,3)", "=RIGHT(C3,2)", "=MID(C2,2,3)",
    "=CONCAT(C1,\"-\",A2)", "=CONCATENATE(\"a\",\"b\")",
    "=SUBSTITUTE(C2,\"a\",\"o\")", "=REPT(\"ab\",3)", "=FIND(\"n\",C2)",
    "=SEARCH(\"N\",C2)", "=REPLACE(C1,1,1,\"A\")", "=EXACT(C1,C5)",
    "=VALUE(\"3.25\")", "=TEXT(3.14159,\"0.00\")", "=CHAR(65)",
    "=CODE(\"A\")", "=TEXTJOIN(\"-\",TRUE,C1:C3)", "=FIXED(1234.567,1)",
    "=NUMBERVALUE(\"1.5\")", "=CLEAN(\"ab\")", "=UNICHAR(9731)",
    # Dates
    "=DATE(2024,2,29)", "=YEAR(DATE(2024,2,29))", "=MONTH(DATE(2024,2,29))",
    "=DAY(DATE(2024,2,29))", "=DAYS(DATE(2024,3,1),DATE(2024,1,1))",
    "=EDATE(DATE(2024,1,31),1)", "=EOMONTH(DATE(2024,1,15),1)",
    "=WEEKDAY(DATE(2024,1,1))", "=WEEKNUM(DATE(2024,3,1))",
    "=ISOWEEKNUM(DATE(2024,3,1))", "=DAYS360(DATE(2024,1,1),DATE(2024,12,31))",
    "=YEARFRAC(DATE(2024,1,1),DATE(2024,7,1))",
    "=NETWORKDAYS(DATE(2024,1,1),DATE(2024,1,31))",
    "=WORKDAY(DATE(2024,1,1),10)", "=TIME(12,30,0)",
    "=DATEVALUE(\"2024-02-01\")",
    # Lookup and reference
    "=MATCH(5,A1:A10,0)", "=INDEX(B1:B10,4)", "=VLOOKUP(3,A1:B10,2)",
    "=VLOOKUP(3,A1:B10,2,FALSE)", "=HLOOKUP(1,A1:B3,2)",
    "=XLOOKUP(4,A1:A10,B1:B10)", "=LOOKUP(6,A1:A10,B1:B10)",
    "=ROWS(A1:B7)", "=COLUMNS(A1:C2)", "=ADDRESS(2,3)",
    # Financial
    "=PMT(0.05/12,360,200000)", "=PV(0.05,10,-100)", "=FV(0.05,10,-100)",
    "=NPER(0.05,-100,1000)", "=RATE(10,-100,800)", "=NPV(0.1,100,200,300)",
    "=IRR(A1:A3)" if False else "=IRR(-100,30,40,50)",
    "=SLN(1000,100,5)", "=SYD(1000,100,5,1)", "=DDB(1000,100,5,1)",
    "=EFFECT(0.05,12)", "=NOMINAL(0.05,12)", "=IPMT(0.05,1,10,1000)",
    "=PPMT(0.05,1,10,1000)",
    # Engineering
    "=DEC2HEX(255)", "=DEC2BIN(10)", "=HEX2DEC(\"FF\")", "=BIN2DEC(\"1010\")",
    "=OCT2DEC(\"17\")", "=DELTA(3,3)", "=GESTEP(5,4)", "=ERF(0.5)",
    "=ERFC(0.5)", "=COMPLEX(3,4)", "=IMABS(\"3+4i\")", "=IMREAL(\"3+4i\")",
    "=IMSUM(\"1+2i\",\"3-i\")", "=IMPRODUCT(\"1+2i\",\"3-i\")",
    "=CONVERT(1,\"km\",\"m\")",
    # Data analysis (dotted names)
    "=TRAPZ(H1:H12,G1:G12)", "=MOVAVG(F1:F20,3)", "=NORM.MAX(A1:A10)",
    "=NORM.MINMAX(A1:A5)", "=NORM.AREA(A1:A5)", "=FFT.MAG(F1:F8)",
    "=DERIV(H1:H12,G1:G12)", "=INTERP.LINEAR(1.25,G1:G12,H1:H12)",
    "=FIND.PEAKS(F1:F20)", "=SAVGOL(F1:F20,5,2)",
    # Cross-sheet references
    "='Other Sheet'!A1", "='Other Sheet'!A1+A2", "=SUM('Other Sheet'!A1:A3)",
    "='Other Sheet'!B1", "=Data!A5*2",
    # Excel syntax: comparisons, text joining, quotes inside text
    "=IF(A1=1,\"one\",\"other\")", "=A1=1", "=A1<>2", "=C1=\"apple\"",
    "=\"say \"\"hi\"\"\"", "=C1&\"-\"&A2", "=1+2&\"x\"", "=A1&B1",
    "=COUNTIF(C1:C5,\"A1\")",
    # Only the branch that is needed is computed
    "=IF(A1=0,0,1/A1)", "=IF(A1>0,\"ok\",1/0)", "=IFERROR(C1+1,\"text\")",
    "=IFNA(MATCH(99,A1:A10,0),\"none\")", "=IFS(A1>5,1/0,TRUE,\"else\")",
    # Text cells, lookups on tables, text made from numbers
    "=VLOOKUP(\"cherry\",C1:D3,2,FALSE)", "=INDEX(A1:B10,3,2)",
    "=HLOOKUP(1,A1:B3,3)", "=MID(A10*100,1,2)", "=LEN(E3)",
    # Full precision behind rounded cells
    "=Precision!A2", "=Precision!A3*1000000", "=Precision!A1*300",
    # More constants, rounding and units
    "=PI*2", "=CEILING(-2.1,-1)", "=FLOOR(-2.5,1)",
    "=CONVERT(100,\"C\",\"F\")", "=CONVERT(5,\"mi\",\"km\")",
    "=CONVERT(1,\"kWh\",\"J\")", "=CONVERT(1,\"m\",\"kg\")",
    "=PYTHAGORAS(3,4)", "=SQRT(-1)", "=1e300*1e300",
    # Errors and edge cases
    "=NOSUCHFUNC(1)", "=SUM(", "=\"text\"", "=1.0", "=0.1+0.2",
    "=1/3", "=1e20", "=-1e-9",
]
