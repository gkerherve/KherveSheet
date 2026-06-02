"""Build the rich Business template set (examples/templates/Business/).

Sales Dashboard, Employee Directory, Inventory Tracker, Project Timeline,
Survey Results, Soccer League Table.  Each is a formatted, formula-driven
.ksheet with a data-bound chart where useful.

Run:  python examples/build_tpl_business.py

Copyright (C) 2026 Gwilherm Kerherve - GPL-3.0-or-later.
"""

import os
import sys

import numpy as np

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from ksheet_author import Workbook, Series, PALETTE  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "templates", "Business")


def _save(wb, name):
    wb.save(os.path.join(OUT, name))


# ── Sales Dashboard ─────────────────────────────────────────────────

def sales_dashboard():
    wb = Workbook(min_rows=40, min_cols=12)
    s = wb.add_sheet("Sales")
    s.title_block("Sales Dashboard",
                  "Monthly revenue, cost, profit and margin", span=6)
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    rev = [42, 38, 51, 47, 55, 61, 58, 63, 60, 67, 72, 80]
    cost = [28, 26, 32, 30, 34, 37, 36, 38, 37, 40, 43, 46]
    TS = 4
    rows = []
    for i, m in enumerate(months):
        sr = TS + 2 + i
        rows.append([m, rev[i] * 1000, cost[i] * 1000,
                     f"=B{sr}-C{sr}",
                     f"=IF(B{sr}==0,0,(B{sr}-C{sr})/B{sr}*100)"])
    s.table(TS, 0, headers=["Month", "Revenue", "Cost", "Profit", "Margin %"],
            rows=rows, number_format="0", banded=True)
    last = TS + 1 + len(months)
    tot = last + 1
    s.set(tot - 1, 0, "TOTAL")
    s.fmt(tot - 1, 0, bold=True, bg=PALETTE["header"],
          font_color=PALETTE["header_text"])
    for col in (1, 2, 3):
        L = chr(ord("A") + col)
        s.formula(tot - 1, col, f"=SUM({L}{TS + 2}:{L}{last})")
        s.fmt(tot - 1, col, bold=True, bg=PALETTE["band"], number_format="0")
    s.designate(0, "X")
    s.designate(1, "Y")
    r0, r1 = TS + 1, TS + len(months)
    s.chart([Series(np.arange(12), np.array(rev) * 1000.0, "Revenue", "Bar",
                    color=PALETTE["header"], y_col=1, row_start=r0, row_end=r1),
             Series(np.arange(12), np.array(cost) * 1000.0, "Cost", "Bar",
                    color=PALETTE["accent"], y_col=2, row_start=r0, row_end=r1)],
            at=(560, 40), size=(440, 300), title="Revenue & Cost by Month",
            xlabel="Month", ylabel="GBP", legend=True)
    s.note(TS, 1, "Edit Revenue and Cost; Profit and Margin recompute.",
           kind="note")
    _save(wb, "Sales Dashboard.ksheet")


# ── Employee Directory ──────────────────────────────────────────────

def employee_directory():
    wb = Workbook(min_rows=40, min_cols=12)
    s = wb.add_sheet("Employees")
    s.title_block("Employee Directory",
                  "Staff list with payroll summary", span=7)
    data = [
        ("Alice Brown", "Engineering", "Senior Dev", "alice@co.uk", 62000),
        ("Ben Carter", "Engineering", "Developer", "ben@co.uk", 48000),
        ("Chloe Davis", "Design", "Lead Designer", "chloe@co.uk", 55000),
        ("Daniel Evans", "Sales", "Account Mgr", "dan@co.uk", 45000),
        ("Ella Foster", "Sales", "Sales Rep", "ella@co.uk", 38000),
        ("Femi Green", "Marketing", "Marketer", "femi@co.uk", 42000),
        ("Grace Hill", "HR", "HR Manager", "grace@co.uk", 50000),
        ("Henry Ives", "Finance", "Accountant", "henry@co.uk", 47000),
    ]
    TS = 4
    rows = [[n, d, role, mail, sal] for (n, d, role, mail, sal) in data]
    s.table(TS, 0, headers=["Name", "Department", "Role", "Email", "Salary"],
            rows=rows, number_format="0", banded=True, align_data="left")
    last = TS + 1 + len(data)
    s.set(4, 6, "Summary")
    s.fmt(4, 6, bold=True, font_color=PALETTE["header"])
    summ = [("Head count", f"=COUNT(E{TS + 2}:E{last})"),
            ("Total payroll", f"=SUM(E{TS + 2}:E{last})"),
            ("Average salary", f"=AVERAGE(E{TS + 2}:E{last})"),
            ("Highest salary", f"=MAX(E{TS + 2}:E{last})")]
    for i, (lbl, expr) in enumerate(summ):
        s.set(5 + i, 6, lbl)
        s.formula(5 + i, 7, expr)
        s.fmt(5 + i, 7, bold=True, bg=PALETTE["band"], number_format="0")
    s.box(5, 6, 8, 7, color=PALETTE["header"], width=1.0)
    s.col_width(0, 130)
    s.col_width(3, 150)
    s.col_width(6, 130)
    _save(wb, "Employee Directory.ksheet")


# ── Inventory Tracker ───────────────────────────────────────────────

def inventory_tracker():
    wb = Workbook(min_rows=40, min_cols=12)
    s = wb.add_sheet("Inventory")
    s.title_block("Inventory Tracker",
                  "Stock value and reorder status", span=7)
    items = [
        ("Widget A", "WA-100", 120, 2.50, 50),
        ("Widget B", "WB-200", 30, 4.00, 40),
        ("Gadget C", "GC-300", 200, 1.20, 60),
        ("Gizmo D", "GD-400", 15, 9.99, 20),
        ("Module E", "ME-500", 80, 6.50, 25),
        ("Cable F", "CF-600", 500, 0.45, 100),
    ]
    TS = 4
    rows = []
    for i, (nm, sku, qty, cost, reorder) in enumerate(items):
        sr = TS + 2 + i
        rows.append([nm, sku, qty, cost, reorder,
                     f"=C{sr}*D{sr}",
                     f'=IF(C{sr}<E{sr},"REORDER","OK")'])
    s.table(TS, 0, headers=["Item", "SKU", "Qty", "Unit Cost",
                            "Reorder Lvl", "Value", "Status"],
            rows=rows, number_format="0.00", banded=True, align_data="left")
    last = TS + 1 + len(items)
    s.set(last + 1, 4, "Total value")
    s.fmt(last + 1, 4, bold=True, align="right")
    s.formula(last + 1, 5, f"=SUM(F{TS + 2}:F{last})")
    s.fmt(last + 1, 5, bold=True, bg=PALETTE["good"], number_format="0.00")
    r0, r1 = TS + 1, TS + len(items)
    s.chart([Series(np.arange(len(items)),
                    np.array([q * c for _, _, q, c, _ in items]),
                    "Stock value", "Bar", color=PALETTE["header"],
                    y_col=5, row_start=r0, row_end=r1)],
            at=(620, 40), size=(420, 300), title="Stock Value by Item",
            xlabel="Item", ylabel="Value", legend=False)
    s.note(TS, 2, "Status flags REORDER when Qty < Reorder Level.", kind="note")
    s.col_width(0, 110)
    _save(wb, "Inventory Tracker.ksheet")


# ── Project Timeline ────────────────────────────────────────────────

def project_timeline():
    wb = Workbook(min_rows=40, min_cols=12)
    s = wb.add_sheet("Timeline")
    s.title_block("Project Timeline",
                  "Tasks, durations and progress", span=7)
    tasks = [
        ("Requirements", 1, 5, "Alice", 100),
        ("Design", 6, 8, "Chloe", 100),
        ("Development", 14, 20, "Ben", 60),
        ("Testing", 34, 10, "Daniel", 20),
        ("Deployment", 44, 4, "Grace", 0),
        ("Review", 48, 3, "Henry", 0),
    ]
    TS = 4
    rows = []
    for i, (nm, start, dur, owner, pct) in enumerate(tasks):
        sr = TS + 2 + i
        rows.append([nm, start, dur, f"=B{sr}+C{sr}", owner, pct])
    s.table(TS, 0, headers=["Task", "Start (day)", "Duration",
                            "End (day)", "Owner", "% Complete"],
            rows=rows, number_format="0", banded=True, align_data="left")
    last = TS + 1 + len(tasks)
    s.set(last + 1, 0, "Project length (days)")
    s.fmt(last + 1, 0, bold=True)
    s.formula(last + 1, 3, f"=MAX(D{TS + 2}:D{last})")
    s.fmt(last + 1, 3, bold=True, bg=PALETTE["band"], number_format="0")
    r0, r1 = TS + 1, TS + len(tasks)
    s.chart([Series(np.arange(len(tasks)),
                    np.array([d for _, _, d, _, _ in tasks]),
                    "Duration", "Bar", color=PALETTE["accent"],
                    y_col=2, row_start=r0, row_end=r1),
             Series(np.arange(len(tasks)),
                    np.array([p for _, _, _, _, p in tasks]),
                    "% Complete", "Bar", color=PALETTE["header"],
                    y_col=5, row_start=r0, row_end=r1)],
            at=(620, 40), size=(420, 300), title="Duration & Progress",
            xlabel="Task", ylabel="days / %", legend=True)
    s.col_width(0, 130)
    _save(wb, "Project Timeline.ksheet")


# ── Survey Results ──────────────────────────────────────────────────

def survey_results():
    wb = Workbook(min_rows=36, min_cols=10)
    s = wb.add_sheet("Survey")
    s.title_block("Survey Results",
                  "Response counts and percentages", span=5)
    opts = [("Very satisfied", 48), ("Satisfied", 71),
            ("Neutral", 33), ("Dissatisfied", 18),
            ("Very dissatisfied", 9)]
    TS = 4
    last = TS + 1 + len(opts)
    rows = []
    for i, (lbl, n) in enumerate(opts):
        sr = TS + 2 + i
        rows.append([lbl, n, f"=B{sr}/SUM($B${TS + 2}:$B${last})*100"])
    s.table(TS, 0, headers=["Response", "Count", "Percent %"],
            rows=rows, number_format="0.0", banded=True, align_data="left")
    s.set(last + 1, 0, "Total")
    s.fmt(last + 1, 0, bold=True)
    s.formula(last + 1, 1, f"=SUM(B{TS + 2}:B{last})")
    s.fmt(last + 1, 1, bold=True, bg=PALETTE["band"], number_format="0")
    r0, r1 = TS + 1, TS + len(opts)
    s.chart([Series(np.arange(len(opts)),
                    np.array([n for _, n in opts], dtype=float),
                    "Responses", "Bar", color=PALETTE["header"],
                    y_col=1, row_start=r0, row_end=r1)],
            at=(440, 40), size=(440, 300), title="Responses by Option",
            xlabel="Option", ylabel="Count", legend=False)
    s.col_width(0, 150)
    _save(wb, "Survey Results.ksheet")


# ── Soccer League Table ─────────────────────────────────────────────

def soccer_league():
    wb = Workbook(min_rows=36, min_cols=14)
    s = wb.add_sheet("League")
    s.title_block("Soccer League Table",
                  "Standings with goal difference and points", span=9)
    teams = [
        ("Arsenal FC", 10, 8, 1, 1, 24, 8),
        ("City United", 10, 7, 2, 1, 22, 10),
        ("Rovers", 10, 6, 2, 2, 18, 12),
        ("Athletic", 10, 5, 3, 2, 16, 13),
        ("Wanderers", 10, 4, 3, 3, 14, 14),
        ("Town FC", 10, 3, 2, 5, 11, 17),
        ("County", 10, 2, 3, 5, 9, 18),
        ("Albion", 10, 1, 1, 8, 6, 24),
    ]
    TS = 4
    rows = []
    for i, (nm, p, w, d, l, gf, ga) in enumerate(teams):
        sr = TS + 2 + i
        rows.append([nm, p, w, d, l, gf, ga,
                     f"=F{sr}-G{sr}", f"=C{sr}*3+D{sr}"])
    s.table(TS, 0, headers=["Team", "P", "W", "D", "L", "GF", "GA",
                            "GD", "Pts"],
            rows=rows, number_format="0", banded=True, align_data="center")
    # left-align team names
    for i in range(len(teams)):
        s.fmt(TS + 1 + i, 0, align="left")
    r0, r1 = TS + 1, TS + len(teams)
    s.chart([Series(np.arange(len(teams)),
                    np.array([w * 3 + d for _, _, w, d, _, _, _ in teams],
                             dtype=float),
                    "Points", "Bar", color=PALETTE["header"],
                    y_col=8, row_start=r0, row_end=r1)],
            at=(640, 40), size=(420, 300), title="Points by Team",
            xlabel="Team", ylabel="Pts", legend=False)
    s.col_width(0, 130)
    _save(wb, "Soccer League Table.ksheet")


def build():
    os.makedirs(OUT, exist_ok=True)
    sales_dashboard()
    employee_directory()
    inventory_tracker()
    project_timeline()
    survey_results()
    soccer_league()
    print("Business templates written to", OUT)


if __name__ == "__main__":
    build()
