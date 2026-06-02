"""Build the "Attendance Tracker" Daily Life template .ksheet.

A polished attendance grid (names × sessions) with:
  - Title block and instructive notes
  - 10 sample participants × 10 sessions (pre-filled 1/0 flags)
  - "Days Present" column — live SUM formula per row
  - "Attendance %" column — live formula: days_present / n_sessions * 100
  - Per-session total row — live SUM per column
  - Conditional-style fill on the % column (green/amber/red bands)
  - Summary panel (class avg %, best/worst attender) — live formulas
  - Data-bound horizontal Bar chart of attendance % per person
  - LaTeX equation for the attendance rate formula
  - Sticky notes guiding the user

Layout (0-based rows):
  0   Title
  1   Subtitle
  2   blank
  3   Section label "Attendance Register"
  4   Headers (Name | Day 1 … Day 10 | Days Present | Attendance %)
  5–14 One row per participant (editable 1/0 cells)
  15  "Total Present" totals row
  16  blank
  17  Summary section header
  18–21 Summary metrics
  22+ (chart / equation overlays)

Columns (0-based):
  0   (A) Name
  1–10 (B–K) Day 1 … Day 10
  11  (L) Days Present
  12  (M) Attendance %

Run:  python examples/build_tpl_attendance.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from examples.ksheet_author import Workbook, Series, PALETTE  # noqa: E402


# ── Sample data ───────────────────────────────────────────────────────
N_SESSIONS = 10
SESSION_LABELS = [f"Day {i+1}" for i in range(N_SESSIONS)]

# Participants and their 1/0 attendance per session.
# Edit these values freely in the spreadsheet — all totals recalculate.
PARTICIPANTS = [
    ("Alice Chen",      [1, 1, 1, 1, 0, 1, 1, 1, 1, 1]),
    ("Bob Martin",     [1, 0, 1, 1, 1, 0, 1, 1, 0, 1]),
    ("Carol Singh",    [1, 1, 1, 1, 1, 1, 1, 1, 1, 1]),
    ("David Osei",     [0, 1, 1, 0, 1, 1, 0, 1, 1, 0]),
    ("Elena Rossi",    [1, 1, 0, 1, 1, 1, 1, 0, 1, 1]),
    ("Farid Aziz",     [0, 0, 1, 1, 1, 1, 0, 1, 1, 1]),
    ("Grace Kim",      [1, 1, 1, 1, 1, 0, 1, 1, 1, 1]),
    ("Hassan Diallo",  [1, 0, 0, 1, 0, 1, 1, 1, 0, 1]),
    ("Iris Novak",     [1, 1, 1, 0, 1, 1, 1, 1, 1, 0]),
    ("James Tran",     [0, 1, 1, 1, 1, 1, 0, 0, 1, 1]),
]

N_PEOPLE = len(PARTICIPANTS)

# Row / column layout constants (0-based)
ROW_TITLE    = 0
ROW_SUBTITLE = 1
ROW_SECHEAD  = 3
ROW_HEADERS  = 4
ROW_DATA_FIRST = 5
ROW_DATA_LAST  = ROW_DATA_FIRST + N_PEOPLE - 1     # = 14
ROW_TOTALS   = ROW_DATA_LAST + 1                   # = 15
ROW_SUMHEAD  = ROW_TOTALS + 2                      # = 17
ROW_SUM_FIRST = ROW_SUMHEAD + 1                    # = 18

COL_NAME   = 0   # A
COL_DAY1   = 1   # B  (first session)
COL_DAYN   = COL_DAY1 + N_SESSIONS - 1  # K  (last session = 10)
COL_DAYS   = COL_DAYN + 1               # L  Days Present
COL_PCT    = COL_DAYS + 1               # M  Attendance %


def col_letter(c: int) -> str:
    """0-based column index → spreadsheet column letter(s)."""
    letters = ""
    c += 1
    while c > 0:
        c, rem = divmod(c - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


# Pre-compute column letter strings for formula construction
L_DAY1 = col_letter(COL_DAY1)   # "B"
L_DAYN = col_letter(COL_DAYN)   # "K"
L_DAYS = col_letter(COL_DAYS)   # "L"
L_PCT  = col_letter(COL_PCT)    # "M"


def build() -> str:
    wb = Workbook(min_rows=40, min_cols=14)
    s = wb.add_sheet("Attendance")

    # ── Column widths ─────────────────────────────────────────────────
    s.col_width(COL_NAME, 140)
    for c in range(COL_DAY1, COL_DAYN + 1):
        s.col_width(c, 56)
    s.col_width(COL_DAYS, 80)
    s.col_width(COL_PCT, 90)

    # ── Title block ───────────────────────────────────────────────────
    s.title_block(
        "Attendance Tracker",
        "Class / group attendance register — enter 1 = present, 0 = absent",
        span=COL_PCT + 1,
    )

    # ── Section label ─────────────────────────────────────────────────
    s.set(ROW_SECHEAD, COL_NAME, "Attendance Register")
    s.fmt(ROW_SECHEAD, COL_NAME,
          bold=True, font_size=11, font_color=PALETTE["header"])
    s.merge(ROW_SECHEAD, COL_NAME, 1, 4)

    # ── Header row ────────────────────────────────────────────────────
    # Name header
    s.set(ROW_HEADERS, COL_NAME, "Name")
    s.fmt(ROW_HEADERS, COL_NAME,
          bold=True, bg=PALETTE["header"],
          font_color="#ffffff", align="center")

    # Session day headers
    for i, lbl in enumerate(SESSION_LABELS):
        c = COL_DAY1 + i
        s.set(ROW_HEADERS, c, lbl)
        s.fmt(ROW_HEADERS, c,
              bold=True, bg=PALETTE["header"],
              font_color="#ffffff", align="center")

    # Days Present header
    s.set(ROW_HEADERS, COL_DAYS, "Days Present")
    s.fmt(ROW_HEADERS, COL_DAYS,
          bold=True, bg=PALETTE["header"],
          font_color="#ffffff", align="center", wrap=True)

    # Attendance % header
    s.set(ROW_HEADERS, COL_PCT, "Attendance %")
    s.fmt(ROW_HEADERS, COL_PCT,
          bold=True, bg=PALETTE["header"],
          font_color="#ffffff", align="center", wrap=True)

    # ── Data rows (participants) ───────────────────────────────────────
    pct_values = []   # for chart y-data
    for i, (name, flags) in enumerate(PARTICIPANTS):
        r = ROW_DATA_FIRST + i
        sr = r + 1   # 1-based sheet row

        band = (PALETTE["band_alt"] if (i % 2) else None)

        # Name (label)
        s.set(r, COL_NAME, name)
        s.fmt(r, COL_NAME, align="left", **({"bg": band} if band else {}))

        # 1/0 flags (editable literals — the only non-formula output cells)
        for j, flag in enumerate(flags):
            c = COL_DAY1 + j
            s.set(r, c, flag)
            kw = dict(align="center", number_format="0")
            if band:
                kw["bg"] = band
            s.fmt(r, c, **kw)

        # Days Present — live SUM formula across the flag columns
        s.formula(r, COL_DAYS,
                  f"=SUM({L_DAY1}{sr}:{L_DAYN}{sr})")
        s.fmt(r, COL_DAYS,
              bold=True, align="center", number_format="0",
              bg=PALETTE["band"])

        # Attendance % — live formula: days_present / n_sessions * 100
        # N_SESSIONS is a literal integer in the formula (no sci notation)
        s.formula(r, COL_PCT,
                  f"={L_DAYS}{sr}/{N_SESSIONS}*100")

        # Conditional-look fill: >=80% green, 60–79% amber, <60% red
        # We choose colour statically by the pre-filled default, since
        # dynamic conditional formatting is not available in the author
        # API. The user can see the semantics via the note.
        pct = sum(flags) / N_SESSIONS * 100
        pct_values.append(pct)
        if pct >= 80:
            fill = PALETTE["good"]
        elif pct >= 60:
            fill = PALETTE["warn"]
        else:
            fill = PALETTE["bad"]
        s.fmt(r, COL_PCT,
              bold=True, align="center", number_format="0.0",
              bg=fill)

    # ── Totals row (per session) ──────────────────────────────────────
    r_tot = ROW_TOTALS
    sr_first = ROW_DATA_FIRST + 1   # 1-based
    sr_last  = ROW_DATA_LAST  + 1

    s.set(r_tot, COL_NAME, "Total Present")
    s.fmt(r_tot, COL_NAME,
          bold=True, bg=PALETTE["accent"],
          font_color="#ffffff", align="left")

    for i in range(N_SESSIONS):
        c = COL_DAY1 + i
        cl = col_letter(c)
        s.formula(r_tot, c,
                  f"=SUM({cl}{sr_first}:{cl}{sr_last})")
        s.fmt(r_tot, c,
              bold=True, bg=PALETTE["accent"],
              font_color="#ffffff", align="center", number_format="0")

    # Total days col — SUM of the "Days Present" column across all people
    s.formula(r_tot, COL_DAYS,
              f"=SUM({L_DAYS}{sr_first}:{L_DAYS}{sr_last})")
    s.fmt(r_tot, COL_DAYS,
          bold=True, bg=PALETTE["accent"],
          font_color="#ffffff", align="center", number_format="0")

    # Overall attendance % for the whole class
    s.formula(r_tot, COL_PCT,
              f"=IFERROR({L_DAYS}{r_tot + 1}/({N_PEOPLE}*{N_SESSIONS})*100, 0)")
    s.fmt(r_tot, COL_PCT,
          bold=True, bg=PALETTE["accent"],
          font_color="#ffffff", align="center", number_format="0.0")

    # ── Border around the main attendance table ────────────────────────
    s.box(ROW_HEADERS, COL_NAME, ROW_TOTALS, COL_PCT,
          color=PALETTE["header"], width=1.2)
    # Inner vertical line before Days Present
    for r in range(ROW_HEADERS, ROW_TOTALS + 1):
        s.fmt(r, COL_DAYS, align="center")  # (re-apply; box doesn't reset)

    # ── Sticky notes ─────────────────────────────────────────────────
    s.note(ROW_DATA_FIRST, COL_DAY1,
           "Enter 1 = present, 0 = absent for each person and session. "
           "Days Present and Attendance % recalculate automatically.",
           kind="note")
    s.note(ROW_DATA_FIRST, COL_PCT,
           "Fill colour: green ≥ 80%, amber 60–79%, red < 60%. "
           "Add/remove rows to track more participants.",
           kind="note")
    s.note(ROW_TOTALS, COL_DAY1,
           "Per-session totals — useful for spotting low-attendance days.",
           kind="note")

    # ── Summary panel ─────────────────────────────────────────────────
    COL_SUM_L = COL_PCT + 2   # two columns right of the table
    COL_SUM_V = COL_SUM_L + 1

    s.col_width(COL_SUM_L, 180)
    s.col_width(COL_SUM_V, 90)

    s.set(ROW_SUMHEAD, COL_SUM_L, "Summary")
    s.fmt(ROW_SUMHEAD, COL_SUM_L,
          bold=True, font_size=11, font_color=PALETTE["header"])
    s.merge(ROW_SUMHEAD, COL_SUM_L, 1, 2)

    # 1-based row references for the Attendance % column
    pct_sr_first = ROW_DATA_FIRST + 1
    pct_sr_last  = ROW_DATA_LAST  + 1
    tot_sr       = ROW_TOTALS + 1

    summary_items = [
        ("Class Avg Attendance %",
         f"=AVERAGE({L_PCT}{pct_sr_first}:{L_PCT}{pct_sr_last})",
         PALETTE["band"], "0.1"),
        ("Highest % (best)",
         f"=MAX({L_PCT}{pct_sr_first}:{L_PCT}{pct_sr_last})",
         PALETTE["good"], "0.1"),
        ("Lowest % (concern)",
         f"=MIN({L_PCT}{pct_sr_first}:{L_PCT}{pct_sr_last})",
         PALETTE["bad"], "0.1"),
        ("Total Person-Sessions",
         f"={L_DAYS}{tot_sr}",
         PALETTE["band_alt"], "0"),
    ]

    for i, (lbl, expr, col_bg, nf) in enumerate(summary_items):
        r = ROW_SUM_FIRST + i
        s.set(r, COL_SUM_L, lbl)
        s.fmt(r, COL_SUM_L, align="left")
        s.formula(r, COL_SUM_V, expr)
        s.fmt(r, COL_SUM_V,
              bold=True, bg=col_bg,
              align="right", number_format=nf)

    s.box(ROW_SUM_FIRST, COL_SUM_L,
          ROW_SUM_FIRST + len(summary_items) - 1, COL_SUM_V,
          color=PALETTE["header"], width=1.2)

    s.note(ROW_SUM_FIRST, COL_SUM_L,
           "Summary updates when you edit any attendance cell.",
           kind="note")

    # ── Designate columns for chart axis ──────────────────────────────
    # The chart reads attendance % from column M (COL_PCT), using row
    # index as X (one bar per person).
    s.designate(COL_PCT, "Y")

    # ── Bar chart — attendance % per person ───────────────────────────
    pct_array = np.array(pct_values, dtype=float)
    x_indices = np.arange(N_PEOPLE, dtype=float)

    r0 = ROW_DATA_FIRST   # 0-based inclusive start
    r1 = ROW_DATA_LAST    # 0-based inclusive end

    # Bar colours: mirror the conditional fill logic
    bar_colors = []
    for pct in pct_values:
        if pct >= 80:
            bar_colors.append(PALETTE["good"])
        elif pct >= 60:
            bar_colors.append(PALETTE["warn"])
        else:
            bar_colors.append(PALETTE["bad"])

    # Single series bound to the % column
    s.chart(
        [Series(
            x=x_indices,
            y=pct_array,
            label="Attendance %",
            plot_type="Bar",
            color=PALETTE["header"],
            y_col=COL_PCT,
            row_start=r0,
            row_end=r1,
        )],
        at=(820, 30),
        size=(440, 320),
        title="Attendance % per Participant",
        xlabel="Participant",
        ylabel="Attendance %",
        grid=True,
        legend=False,
    )

    # ── LaTeX equation ────────────────────────────────────────────────
    s.equation(
        r"\mathrm{Attendance\%} = \frac{\mathrm{Sessions\;Attended}}{\mathrm{Total\;Sessions}} \times 100",
        at=(820, 370),
        fontsize=16,
        color="#222222",
        bg_color="#ffffff",
        border_color=PALETTE["header"],
        border_width=1.2,
        size=(440, 52),
    )

    # ── Save ──────────────────────────────────────────────────────────
    out = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "templates", "Daily Life", "Attendance Tracker.ksheet",
    )
    wb.save(out)
    return out


if __name__ == "__main__":
    path = build()
    print(f"Saved: {path}")
