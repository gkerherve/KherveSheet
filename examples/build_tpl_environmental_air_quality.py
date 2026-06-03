"""Build the "Environmental Air / Water Quality" Analysis template .ksheet.

An hourly air-quality monitoring log for a 36-hour urban measurement
campaign.  Demonstrates:

* Editable inputs: WHO 24-hour PM2.5 limit, EPA 24-hour PM2.5 limit.
* 36 rows of realistic hourly PM2.5, NO2, O3 data (with diurnal patterns
  and two genuine exceedance episodes).
* Live formula columns:
    - 8-hour trailing rolling-average PM2.5 (AVERAGE over explicit
      shrinking window for first 7 rows; full 8-row window thereafter).
    - AQI sub-index for PM2.5 via 6-tier nested-IF piecewise-linear
      interpolation matching the US EPA 2024 breakpoints.
    - Compliance flag: "Exceeds" / "OK" referenced against the editable
      EPA daily limit cell.
* Summary panel: peak PM2.5, peak AQI, mean NO2, count of exceedances.
* Two live-bound charts:
    (a) PM2.5 raw vs 8-hour rolling average over the 36-hour campaign.
    (b) AQI index over time — colour threshold at AQI 100 visible via the
        data.
* One LaTeX equation (AQI piecewise-linear formula).
* Three instructive sticky notes.

Output: examples/templates/Analysis/Environmental Air-Water Quality.ksheet

Run:  python examples/build_tpl_environmental_air_quality.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

from __future__ import annotations

import os
import sys

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from ksheet_author import Workbook, Series, PALETTE  # noqa: E402


# ── Measurement parameters ────────────────────────────────────────────
# WHO 24-hour PM2.5 guideline: 15 µg/m³  (2021 update)
# US EPA 24-hour NAAQS PM2.5:  35 µg/m³
WHO_LIMIT  = 15.0   # µg/m³
EPA_LIMIT  = 35.0   # µg/m³
ROLL_WIN   = 8      # rolling-average window (hours)
N_ROWS     = 36     # hourly data points (1.5 days)

# ── EPA PM2.5 AQI piecewise-linear breakpoints ────────────────────────
# (C_lo, C_hi, I_lo, I_hi) for each tier — used in Python for numpy
# pre-computation only; the sheet formulas use inline constants.
_AQI_BP = [
    (0.0,   12.0,    0,   50),
    (12.1,  35.4,   51,  100),
    (35.5,  55.4,  101,  150),
    (55.5, 150.4,  151,  200),
    (150.5, 250.4, 201,  300),
    (250.5, 500.4, 301,  500),
]


def _pm25_aqi(c: float) -> int:
    """Python reference: EPA piecewise-linear AQI for PM2.5."""
    c = round(float(c), 1)
    for c_lo, c_hi, i_lo, i_hi in _AQI_BP:
        if c <= c_hi:
            return int(round(i_lo + (i_hi - i_lo) * (c - c_lo) / (c_hi - c_lo)))
    return 500


def _generate_data() -> tuple:
    """Return (pm25, no2, o3) arrays with realistic urban diurnal profile."""
    np.random.seed(42)

    # PM2.5: morning rush (h6-9), evening rush (h17-20), low overnight
    pm25_base = []
    for i in range(N_ROWS):
        h = i % 24
        if   6 <= h <= 9:    base = 35 + 10 * np.sin((h - 6) * np.pi / 3)
        elif 17 <= h <= 20:  base = 30 +  8 * np.sin((h - 17) * np.pi / 3)
        elif 0 <= h <= 5:    base = 8.0
        elif 10 <= h <= 16:  base = 12.0
        else:                base = 18.0
        pm25_base.append(base)

    pm25 = np.array(pm25_base, dtype=float) + np.random.normal(0, 3, N_ROWS)
    # Inject two exceedance episodes
    pm25[14] = 58.2
    pm25[15] = 67.4
    pm25[16] = 52.1
    pm25 = np.round(np.maximum(pm25, 2.0), 1)

    # NO2: diurnal + traffic correlation
    no2 = np.array([
        12 + 20 * np.sin((i % 24) * np.pi / 12) + np.random.normal(0, 4)
        for i in range(N_ROWS)
    ])
    no2[14] += 15.0
    no2[15] += 18.0
    no2 = np.round(np.maximum(no2, 2.0), 1)

    # O3: peaks at midday
    o3 = np.array([
        max(0.0, 30 * np.sin(((i % 24) - 6) * np.pi / 12))
        + np.random.normal(0, 5)
        for i in range(N_ROWS)
    ])
    o3 = np.round(np.maximum(o3, 0.5), 1)

    return pm25, no2, o3


def _rolling_avg(pm25: np.ndarray, win: int = 8) -> np.ndarray:
    """Trailing rolling mean — matches the sheet formula logic exactly."""
    out = []
    for i in range(len(pm25)):
        start = max(0, i - win + 1)
        out.append(round(float(pm25[start : i + 1].mean()), 2))
    return np.array(out)


def build() -> str:
    pm25, no2, o3 = _generate_data()
    ravg = _rolling_avg(pm25, ROLL_WIN)
    aqi  = np.array([_pm25_aqi(v) for v in pm25], dtype=float)

    # ── Workbook ──────────────────────────────────────────────────────
    wb = Workbook(min_rows=50, min_cols=16)
    s  = wb.add_sheet("Air Quality")

    # ── Column widths ─────────────────────────────────────────────────
    s.col_width(0,  46)   # A: Hour #
    s.col_width(1,  88)   # B: Date
    s.col_width(2,  68)   # C: Time
    s.col_width(3,  96)   # D: PM2.5
    s.col_width(4,  80)   # E: NO2
    s.col_width(5,  70)   # F: O3
    s.col_width(6, 110)   # G: 8h Rolling Avg
    s.col_width(7,  74)   # H: AQI
    s.col_width(8,  84)   # I: Compliance
    s.col_width(9,  18)   # spacer
    s.col_width(10, 200)  # J: Summary labels
    s.col_width(11, 100)  # K: Summary values

    # ── Title block ───────────────────────────────────────────────────
    s.title_block(
        "Environmental Air Quality Monitor",
        "Hourly PM2.5, NO₂ & O₃ log with AQI index and WHO/EPA compliance "
        "check — edit yellow cells to update the entire table and charts",
        span=9,
    )

    # ── Input panel (rows 3-6, cols 0-1) ──────────────────────────────
    # 0-based row 3 → sheet row 4; values in col B (1-based col 2 = B).
    # Cell addresses (1-based): B4=WHO limit, B5=EPA limit

    s.set(3, 0, "Monitoring Parameters")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"], font_size=11)

    param_inputs = [
        ("WHO 24-h PM2.5 limit (µg/m³)",  WHO_LIMIT,  "0.0"),
        ("EPA 24-h PM2.5 limit (µg/m³)",  EPA_LIMIT,  "0.0"),
        ("Rolling average window (hours)", ROLL_WIN,   "0"),
    ]
    for i, (lbl, val, nfmt) in enumerate(param_inputs):
        r = 4 + i   # 0-based rows 4,5,6
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 0, align="left")
        s.fmt(r, 1, bg=PALETTE["warn"], align="center",
              number_format=nfmt, bold=True)

    s.box(4, 0, 6, 1, color=PALETTE["accent"], width=1.5)

    # Note 1: editing inputs
    s.note(
        4, 1,
        "Edit B5 (WHO limit) or B6 (EPA limit) to change the\n"
        "compliance threshold — column I updates immediately.\n"
        "WHO 2021 guideline: 15 µg/m³.  US EPA NAAQS: 35 µg/m³.",
        kind="note",
    )

    # ── AQI tier reference block (rows 3-9, cols 3-5) ─────────────────
    # Informational only — breakpoints used inline in formulas.
    s.set(3, 3, "US EPA PM2.5 AQI Breakpoints")
    s.fmt(3, 3, bold=True, font_color=PALETTE["header"], font_size=10)
    s.merge(3, 3, 1, 3)

    bp_headers = ["PM2.5 range (µg/m³)", "AQI range", "Category"]
    bp_rows = [
        ("0.0 – 12.0",   "0 – 50",    "Good"),
        ("12.1 – 35.4",  "51 – 100",  "Moderate"),
        ("35.5 – 55.4",  "101 – 150", "Unhealthy (sensitive)"),
        ("55.5 – 150.4", "151 – 200", "Unhealthy"),
        ("150.5 – 250.4","201 – 300", "Very Unhealthy"),
        ("250.5 – 500.4","301 – 500", "Hazardous"),
    ]
    # Header row at 0-based row 4
    for j, h in enumerate(bp_headers):
        s.set(4, 3 + j, h)
        s.fmt(4, 3 + j, bold=True, bg=PALETTE["header"],
              font_color=PALETTE["header_text"], align="center")

    # Category fill colours matching AQI convention
    bp_fills = [
        PALETTE["good"],       # Good
        PALETTE["warn"],       # Moderate
        "#ff9a00",             # Unhealthy for sensitive (orange)
        PALETTE["bad"],        # Unhealthy
        "#8b3a8b",             # Very Unhealthy (purple — hex)
        "#7e0023",             # Hazardous (maroon — hex)
    ]
    bp_text_colors = [
        "#000000", "#000000", "#000000",
        "#000000", "#ffffff", "#ffffff",
    ]
    for i, (pm_rng, aqi_rng, cat) in enumerate(bp_rows):
        r = 5 + i   # 0-based rows 5..10
        s.set(r, 3, pm_rng)
        s.set(r, 4, aqi_rng)
        s.set(r, 5, cat)
        for j in range(3):
            s.fmt(r, 3 + j, bg=bp_fills[i],
                  font_color=bp_text_colors[i], align="center")

    s.box(4, 3, 10, 5, color=PALETTE["header"], width=1.0)

    # ── Data table ────────────────────────────────────────────────────
    # Table header: 0-based row TABLE_START = 12
    # First data: 0-based row TABLE_START+1 = 13 → 1-based sheet row 14
    TABLE_START = 12

    s.set(11, 0, "Hourly Monitoring Data")
    s.fmt(11, 0, bold=True, font_color=PALETTE["header"], font_size=11)
    s.merge(11, 0, 1, 9)

    # 1-based sheet row of first data row = TABLE_START + 2 = 14
    first_sr = TABLE_START + 2   # = 14

    # Generate date/time strings: start 2024-06-01 00:00
    base_hour = 0
    dates = []
    times_str = []
    for i in range(N_ROWS):
        day = i // 24
        hour = i % 24
        dates.append(f"2024-06-{1 + day:02d}")
        times_str.append(f"{hour:02d}:00")

    # Build table rows: columns A-I (9 columns)
    # A=hour index, B=date, C=time, D=PM2.5, E=NO2, F=O3,
    # G=8h rolling avg (formula), H=AQI (formula), I=compliance (formula)
    table_rows = []
    for k in range(N_ROWS):
        sr = first_sr + k    # 1-based sheet row for this data row

        # Rolling average: trailing ROLL_WIN rows
        # For row k (0-based), include rows from max(0, k-ROLL_WIN+1) to k.
        # In sheet terms: AVERAGE(D{sr_start}:D{sr})
        window_start = k - ROLL_WIN + 1
        if window_start < 0:
            window_start = 0
        roll_start_sr = first_sr + window_start  # 1-based sheet row of window start
        if window_start == k:
            # Window of 1: just this cell
            g_formula = f"=D{sr}"
        else:
            g_formula = f"=AVERAGE(D{roll_start_sr}:D{sr})"

        # AQI piecewise-linear (EPA, inline breakpoints):
        # INT(IF(D<=12, 50*D/12,
        #   IF(D<=35.4, 51+49*(D-12.1)/23.3,
        #     IF(D<=55.4, 101+49*(D-35.5)/19.9,
        #       IF(D<=150.4, 151+49*(D-55.5)/94.9,
        #         IF(D<=250.4, 201+99*(D-150.5)/99.9,
        #           301+99*(D-250.5)/149.5))))))
        d = f"D{sr}"
        h_formula = (
            f"=INT(IF({d}<=12,50*{d}/12,"
            f"IF({d}<=35.4,51+49*({d}-12.1)/23.3,"
            f"IF({d}<=55.4,101+49*({d}-35.5)/19.9,"
            f"IF({d}<=150.4,151+49*({d}-55.5)/94.9,"
            f"IF({d}<=250.4,201+99*({d}-150.5)/99.9,"
            f"301+99*({d}-250.5)/149.5))))))"
        )

        # Compliance: compare against EPA limit in $B$6 (0-based row 5, col 1)
        # $B$6 is 1-based sheet row 6 = 0-based row 5
        i_formula = f'=IF(D{sr}>$B$6,"Exceeds","OK")'

        table_rows.append([
            k,                    # col A: hour index (literal)
            dates[k],             # col B: date (literal text)
            times_str[k],         # col C: time (literal text)
            float(pm25[k]),       # col D: PM2.5 (literal — the input data)
            float(no2[k]),        # col E: NO2 (literal)
            float(o3[k]),         # col F: O3 (literal)
            g_formula,            # col G: rolling avg (formula)
            h_formula,            # col H: AQI (formula)
            i_formula,            # col I: compliance (formula)
        ])

    # Table headers with units
    headers = [
        "Hour #",
        "Date",
        "Time",
        "PM2.5 (µg/m³)",
        "NO₂ (ppb)",
        "O₃ (ppb)",
        "8-h Avg PM2.5",
        "AQI (PM2.5)",
        "Compliance",
    ]

    s.table(
        TABLE_START, 0,
        headers=headers,
        rows=table_rows,
        number_format="0.0",
        banded=True,
    )

    # Override specific column formats
    # Col A (hour index): integer
    for k in range(N_ROWS):
        r = TABLE_START + 1 + k
        s.fmt(r, 0, number_format="0", align="center")
    # Cols B, C: left-aligned text
    for k in range(N_ROWS):
        r = TABLE_START + 1 + k
        s.fmt(r, 1, align="center", number_format="@")
        s.fmt(r, 2, align="center", number_format="@")
    # Col H: integer AQI
    for k in range(N_ROWS):
        r = TABLE_START + 1 + k
        s.fmt(r, 7, number_format="0", align="center")
    # Col I: compliance — centred text; colour-code Exceeds rows
    for k in range(N_ROWS):
        r = TABLE_START + 1 + k
        s.fmt(r, 8, align="center", number_format="@")
        if float(pm25[k]) > EPA_LIMIT:
            # Pre-fill red highlight for known exceedances (static visual aid)
            s.fmt(r, 8, bg=PALETTE["bad"], font_color="#9c0006")

    # Designate X and Y columns for chart binding
    s.designate(0, "X")   # col A: hour index
    s.designate(3, "Y")   # col D: PM2.5
    s.designate(6, "Y")   # col G: 8h rolling avg
    s.designate(7, "Y")   # col H: AQI

    # Note 2: rolling average explanation
    s.note(
        TABLE_START, 6,
        "Column G: 8-hour trailing rolling average of PM2.5.\n"
        "Row 1 uses only 1 reading; row 8 onwards uses the full 8-hour window.\n"
        "Matches the US EPA 24-hour PM2.5 averaging convention.\n"
        "Edit the window size in B7 — the formula window in the sheet\n"
        "is fixed at 8 rows; rebuild the file to change N.",
        kind="note",
    )

    # Note 3: AQI calculation
    s.note(
        TABLE_START, 7,
        "Column H: US EPA Air Quality Index (AQI) for PM2.5.\n"
        "Computed via piecewise-linear interpolation:\n"
        "  0-12 µg/m³  → AQI 0-50   (Good)\n"
        " 12-35 µg/m³  → AQI 51-100 (Moderate)\n"
        " 35-55 µg/m³  → AQI 101-150 (Unhealthy sensitive)\n"
        " >55 µg/m³    → AQI 151+   (Unhealthy / worse)\n"
        "AQI >100 indicates health concern for sensitive groups.",
        kind="note",
    )

    # ── Summary panel (cols 10-11, rows 4-12) ─────────────────────────
    # 1-based data range: rows first_sr .. first_sr+N_ROWS-1
    last_sr = first_sr + N_ROWS - 1   # = 14 + 35 = 49

    s.set(3, 10, "Summary Statistics")
    s.fmt(3, 10, bold=True, font_color=PALETTE["header"], font_size=11)
    s.merge(3, 10, 1, 2)

    summary_items = [
        ("Peak PM2.5 (µg/m³)",
         f"=MAX(D{first_sr}:D{last_sr})",
         PALETTE["bad"], "0.0"),
        ("Mean PM2.5 (µg/m³)",
         f"=AVERAGE(D{first_sr}:D{last_sr})",
         PALETTE["band"], "0.0"),
        ("Min PM2.5 (µg/m³)",
         f"=MIN(D{first_sr}:D{last_sr})",
         PALETTE["good"], "0.0"),
        ("Peak 8h Avg PM2.5 (µg/m³)",
         f"=MAX(G{first_sr}:G{last_sr})",
         PALETTE["warn"], "0.0"),
        ("Peak AQI",
         f"=MAX(H{first_sr}:H{last_sr})",
         PALETTE["bad"], "0"),
        ("Mean NO₂ (ppb)",
         f"=AVERAGE(E{first_sr}:E{last_sr})",
         PALETTE["band"], "0.0"),
        ("Peak O₃ (ppb)",
         f"=MAX(F{first_sr}:F{last_sr})",
         PALETTE["band_alt"], "0.0"),
        ("WHO 24-h limit (µg/m³)",
         "=$B$5",
         PALETTE["warn"], "0.0"),
    ]

    for i, (lbl, expr, fill, nfmt) in enumerate(summary_items):
        r = 4 + i   # 0-based rows 4..11
        s.set(r, 10, lbl)
        s.formula(r, 11, expr)
        s.fmt(r, 10, align="left")
        s.fmt(r, 11, bg=fill, align="right",
              number_format=nfmt, bold=True)

    s.box(4, 10, 11, 11, color=PALETTE["header"], width=1.5)

    # ── Charts ────────────────────────────────────────────────────────
    # 0-based data rows: TABLE_START+1 .. TABLE_START+N_ROWS (inclusive)
    r0 = TABLE_START + 1       # 0-based first data row
    r1 = TABLE_START + N_ROWS  # 0-based last data row

    hour_idx = np.arange(N_ROWS, dtype=float)

    # Chart 1: PM2.5 raw + 8-hour rolling average
    s.chart(
        [
            Series(
                x=list(hour_idx),
                y=list(pm25),
                label="PM2.5 (µg/m³)",
                plot_type="Line+Symbol",
                color=PALETTE["header"],
                linewidth=1.5,
                marker="o",
                markersize=3.5,
                markerfacecolor=PALETTE["header"],
                markeredgecolor="#ffffff",
                x_col=0,
                y_col=3,
                row_start=r0,
                row_end=r1,
            ),
            Series(
                x=list(hour_idx),
                y=list(ravg),
                label="8-h Rolling Avg",
                plot_type="Line",
                color=PALETTE["accent"],
                linewidth=2.5,
                linestyle="-",
                x_col=0,
                y_col=6,
                row_start=r0,
                row_end=r1,
            ),
        ],
        at=(550, 20),
        size=(480, 300),
        title="PM2.5 Concentration — 36-Hour Campaign",
        xlabel="Hour",
        ylabel="PM2.5 (µg/m³)",
        grid=True,
        legend=True,
    )

    # Chart 2: AQI over time
    s.chart(
        [
            Series(
                x=list(hour_idx),
                y=list(aqi),
                label="AQI (PM2.5)",
                plot_type="Bar",
                color="#4472c4",
                linewidth=1.0,
                x_col=0,
                y_col=7,
                row_start=r0,
                row_end=r1,
            ),
        ],
        at=(550, 340),
        size=(480, 280),
        title="PM2.5 Air Quality Index (AQI) — 36-Hour Campaign",
        xlabel="Hour",
        ylabel="AQI",
        grid=True,
        legend=True,
    )

    # ── LaTeX equation: AQI piecewise-linear formula ──────────────────
    s.equation(
        r"I = I_{lo} + \frac{I_{hi} - I_{lo}}{C_{hi} - C_{lo}} \,(C - C_{lo})",
        at=(1050, 20),
        fontsize=17,
        color="#222222",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.2,
        size=(340, 56),
    )

    # ── Save ──────────────────────────────────────────────────────────
    out_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "templates", "Analysis",
    )
    out = os.path.join(out_dir, "Environmental Air-Water Quality.ksheet")
    wb.save(out)
    return out


if __name__ == "__main__":
    print("Wrote", build())
