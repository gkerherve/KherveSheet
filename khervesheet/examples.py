"""Example workbook generators — 50 templates for File ▸ Examples.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import math
import random
from typing import List, Tuple

# Each example is a tuple: (name, category, builder_function)
# The builder returns a list of (sheet_name, headers, rows) tuples.
# headers: list of str; rows: list of list of str.

Row = List[str]
Sheet = Tuple[str, List[str], List[Row]]


def _fv(v, d=4):
    """Format a float value."""
    if isinstance(v, float):
        return f"{v:.{d}f}"
    return str(v)


# ── Builders ─────────────────────────────────────────────────────

def _budget():
    cats = ["Rent", "Groceries", "Utilities", "Transport", "Insurance",
            "Dining Out", "Entertainment", "Clothing", "Healthcare",
            "Savings", "Subscriptions", "Miscellaneous"]
    h = ["Category", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
         "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Total"]
    rows = []
    for c in cats:
        vals = [round(random.uniform(50, 2000), 2) for _ in range(12)]
        rows.append([c] + [_fv(v, 2) for v in vals]
                    + [_fv(sum(vals), 2)])
    totals = ["Total"]
    for m in range(12):
        totals.append(f"=SUM({chr(66+m)}2:{chr(66+m)}{len(cats)+1})")
    totals.append(f"=SUM(N2:N{len(cats)+1})")
    rows.append(totals)
    return [("Budget", h, rows)]


def _invoice():
    h = ["Item", "Description", "Quantity", "Unit Price", "Total"]
    items = [
        ("Web Design", "Homepage redesign", 1, 2500),
        ("Hosting", "Annual hosting plan", 12, 29.99),
        ("Domain", "Domain renewal", 1, 14.99),
        ("SSL Certificate", "Wildcard SSL", 1, 89),
        ("SEO Audit", "Full site audit", 1, 750),
    ]
    rows = []
    for i, (name, desc, qty, price) in enumerate(items):
        r = i + 2
        rows.append([name, desc, str(qty), _fv(price, 2),
                     f"=C{r}*D{r}"])
    rows.append(["", "", "", "Subtotal:", f"=SUM(E2:E{len(items)+1})"])
    rows.append(["", "", "", "Tax (20%):",
                 f"=E{len(items)+2}*0.20"])
    rows.append(["", "", "", "Total:",
                 f"=E{len(items)+2}+E{len(items)+3}"])
    return [("Invoice", h, rows)]


def _grade_book():
    h = ["Student", "HW1", "HW2", "HW3", "Midterm", "Final", "Average",
         "Grade"]
    names = ["Alice", "Bob", "Charlie", "Diana", "Eve", "Frank",
             "Grace", "Hank", "Ivy", "Jack"]
    rows = []
    for i, n in enumerate(names):
        r = i + 2
        scores = [random.randint(40, 100) for _ in range(5)]
        rows.append([n] + [str(s) for s in scores]
                    + [f"=AVERAGE(B{r}:F{r})", ""])
    return [("Grades", h, rows)]


def _sine_cosine():
    h = ["Angle (deg)", "Radians", "sin(x)", "cos(x)", "tan(x)"]
    rows = []
    for deg in range(0, 361, 5):
        rad = math.radians(deg)
        s = math.sin(rad)
        c = math.cos(rad)
        t = math.tan(rad) if abs(math.cos(rad)) > 1e-10 else ""
        rows.append([str(deg), _fv(rad), _fv(s), _fv(c),
                     _fv(t) if t != "" else ""])
    return [("Trig", h, rows)]


def _fibonacci():
    h = ["n", "F(n)", "Ratio F(n)/F(n-1)"]
    rows = [["0", "0", ""], ["1", "1", ""]]
    a, b = 0, 1
    for n in range(2, 31):
        a, b = b, a + b
        rows.append([str(n), str(b), _fv(b / a)])
    return [("Fibonacci", h, rows)]


def _compound_interest():
    h = ["Year", "Principal", "Interest", "Balance"]
    principal = 10000
    rate = 0.05
    rows = []
    bal = principal
    for yr in range(1, 31):
        intr = bal * rate
        bal += intr
        rows.append([str(yr), _fv(principal, 2), _fv(intr, 2),
                     _fv(bal, 2)])
    return [("Interest", h, rows)]


def _currency_converter():
    h = ["Currency", "Code", "Rate to USD", "100 USD ="]
    pairs = [
        ("Euro", "EUR", 0.92), ("British Pound", "GBP", 0.79),
        ("Japanese Yen", "JPY", 149.5), ("Swiss Franc", "CHF", 0.88),
        ("Canadian Dollar", "CAD", 1.36), ("Aus Dollar", "AUD", 1.53),
        ("Chinese Yuan", "CNY", 7.24), ("Indian Rupee", "INR", 83.1),
        ("Mexican Peso", "MXN", 17.1), ("Brazilian Real", "BRL", 4.97),
        ("South Korean Won", "KRW", 1320),
        ("Swedish Krona", "SEK", 10.8),
    ]
    rows = []
    for i, (name, code, rate) in enumerate(pairs):
        r = i + 2
        rows.append([name, code, _fv(rate, 4), f"=100*C{r}"])
    return [("Currencies", h, rows)]


def _bmi_calculator():
    h = ["Name", "Height (m)", "Weight (kg)", "BMI", "Category"]
    people = [
        ("Alice", 1.65, 55), ("Bob", 1.80, 90),
        ("Charlie", 1.75, 72), ("Diana", 1.60, 48),
        ("Eve", 1.70, 85), ("Frank", 1.85, 105),
        ("Grace", 1.58, 62), ("Hank", 1.78, 78),
    ]
    rows = []
    for i, (n, h_m, w) in enumerate(people):
        r = i + 2
        bmi = w / (h_m ** 2)
        cat = ("Underweight" if bmi < 18.5 else "Normal"
               if bmi < 25 else "Overweight" if bmi < 30 else "Obese")
        rows.append([n, _fv(h_m, 2), _fv(w, 1),
                     f"=C{r}/(B{r}^2)", cat])
    return [("BMI", h, rows)]


def _sales_dashboard():
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    products = ["Laptop", "Phone", "Tablet", "Monitor", "Keyboard",
                "Mouse", "Headset"]
    h = ["Product"] + months + ["Total"]
    rows = []
    for p in products:
        vals = [random.randint(20, 500) for _ in range(12)]
        r = len(rows) + 2
        rows.append([p] + [str(v) for v in vals]
                    + [f"=SUM(B{r}:M{r})"])
    return [("Sales", h, rows)]


def _temperature_conversion():
    h = ["Celsius", "Fahrenheit", "Kelvin"]
    rows = []
    for c in range(-40, 101, 5):
        r = len(rows) + 2
        rows.append([str(c), f"=A{r}*9/5+32", f"=A{r}+273.15"])
    return [("Temperature", h, rows)]


def _quadratic_solver():
    h = ["a", "b", "c", "Discriminant", "x1", "x2"]
    cases = [(1, -3, 2), (1, 0, -4), (2, 5, 3), (1, 2, 1),
             (1, -5, 6), (3, -7, 2), (1, 1, -12), (2, -8, 6)]
    rows = []
    for a, b, c in cases:
        disc = b*b - 4*a*c
        if disc >= 0:
            x1 = (-b + math.sqrt(disc)) / (2*a)
            x2 = (-b - math.sqrt(disc)) / (2*a)
            rows.append([str(a), str(b), str(c), _fv(disc, 2),
                         _fv(x1), _fv(x2)])
        else:
            rows.append([str(a), str(b), str(c), _fv(disc, 2),
                         "complex", "complex"])
    return [("Quadratic", h, rows)]


def _mortgage():
    h = ["Month", "Payment", "Interest", "Principal", "Balance"]
    loan = 300000
    annual_rate = 0.065
    months = 360
    r = annual_rate / 12
    pmt = loan * r * (1+r)**months / ((1+r)**months - 1)
    bal = loan
    rows = []
    for m in range(1, min(months+1, 61)):  # first 60 months
        intr = bal * r
        princ = pmt - intr
        bal -= princ
        rows.append([str(m), _fv(pmt, 2), _fv(intr, 2),
                     _fv(princ, 2), _fv(bal, 2)])
    return [("Mortgage", h, rows)]


def _employee_directory():
    h = ["ID", "Name", "Department", "Position", "Salary", "Start Date"]
    depts = ["Engineering", "Marketing", "Sales", "HR", "Finance",
             "Operations"]
    first = ["James", "Maria", "John", "Sara", "David", "Lisa",
             "Michael", "Emma", "Robert", "Olivia"]
    last = ["Smith", "Johnson", "Williams", "Brown", "Jones",
            "Garcia", "Miller", "Davis", "Martinez", "Wilson"]
    rows = []
    for i in range(20):
        dept = random.choice(depts)
        sal = random.randint(45000, 150000)
        yr = random.randint(2015, 2024)
        mo = random.randint(1, 12)
        rows.append([str(1001+i),
                     f"{random.choice(first)} {random.choice(last)}",
                     dept, "Staff", str(sal),
                     f"{yr}-{mo:02d}-01"])
    return [("Employees", h, rows)]


def _unit_conversions():
    h = ["From", "To", "Factor", "10 units ="]
    pairs = [
        ("km", "miles", 0.6214), ("kg", "lbs", 2.2046),
        ("litre", "gallon", 0.2642), ("metre", "feet", 3.2808),
        ("hectare", "acres", 2.4711), ("cm", "inches", 0.3937),
        ("kg", "oz", 35.274), ("km/h", "mph", 0.6214),
        ("bar", "psi", 14.504), ("Celsius", "Kelvin", 1.0),
        ("MJ", "kWh", 0.2778), ("Newton", "lbf", 0.2248),
    ]
    rows = []
    for i, (f, t, fac) in enumerate(pairs):
        r = i + 2
        rows.append([f, t, _fv(fac, 4), f"=10*C{r}"])
    return [("Units", h, rows)]


def _attendance_tracker():
    h = ["Name", "Mon", "Tue", "Wed", "Thu", "Fri", "Total Present"]
    names = ["Alice", "Bob", "Charlie", "Diana", "Eve",
             "Frank", "Grace", "Hank", "Ivy", "Jack"]
    rows = []
    for i, n in enumerate(names):
        days = [random.choice(["P", "A"]) for _ in range(5)]
        present = days.count("P")
        rows.append([n] + days + [str(present)])
    return [("Attendance", h, rows)]


def _stock_portfolio():
    h = ["Ticker", "Shares", "Buy Price", "Current Price",
         "Cost", "Value", "Gain/Loss", "% Return"]
    tickers = [("AAPL", 50, 145, 178), ("MSFT", 30, 280, 420),
               ("GOOGL", 10, 125, 176), ("AMZN", 20, 130, 185),
               ("TSLA", 15, 200, 245), ("NVDA", 25, 450, 880),
               ("META", 40, 300, 510), ("JPM", 35, 140, 195)]
    rows = []
    for i, (t, sh, bp, cp) in enumerate(tickers):
        r = i + 2
        rows.append([t, str(sh), _fv(bp, 2), _fv(cp, 2),
                     f"=B{r}*C{r}", f"=B{r}*D{r}",
                     f"=F{r}-E{r}", f"=G{r}/E{r}*100"])
    return [("Portfolio", h, rows)]


def _calorie_tracker():
    h = ["Food", "Calories", "Protein (g)", "Carbs (g)", "Fat (g)"]
    foods = [
        ("Oatmeal", 150, 5, 27, 3), ("Banana", 105, 1, 27, 0.4),
        ("Chicken breast", 165, 31, 0, 3.6),
        ("Brown rice", 216, 5, 45, 1.8),
        ("Broccoli", 55, 4, 11, 0.6), ("Salmon", 208, 20, 0, 13),
        ("Apple", 95, 0.5, 25, 0.3), ("Egg", 78, 6, 0.6, 5),
        ("Greek yogurt", 100, 17, 6, 0.7),
        ("Almonds (28g)", 164, 6, 6, 14),
    ]
    rows = []
    for f, cal, p, c, fat in foods:
        rows.append([f, str(cal), _fv(p, 1), _fv(c, 1), _fv(fat, 1)])
    r = len(foods) + 2
    rows.append(["Total", f"=SUM(B2:B{r-1})", f"=SUM(C2:C{r-1})",
                 f"=SUM(D2:D{r-1})", f"=SUM(E2:E{r-1})"])
    return [("Calories", h, rows)]


def _todo_list():
    h = ["Task", "Priority", "Status", "Due Date", "Notes"]
    tasks = [
        ("Review PR #42", "High", "In Progress", "2026-05-25", ""),
        ("Update docs", "Medium", "Todo", "2026-05-28", ""),
        ("Fix login bug", "High", "Done", "2026-05-20", "v2.1"),
        ("Deploy staging", "Medium", "Todo", "2026-05-30", ""),
        ("Team meeting", "Low", "Done", "2026-05-24", "weekly"),
        ("Write tests", "High", "In Progress", "2026-05-27", "unit"),
        ("Backup database", "High", "Todo", "2026-05-26", ""),
        ("Code review", "Medium", "Todo", "2026-05-29", ""),
    ]
    rows = [list(t) for t in tasks]
    return [("Todo", h, rows)]


def _statistics_data():
    h = ["Sample", "Value", "Z-Score"]
    random.seed(42)
    vals = [round(random.gauss(100, 15), 2) for _ in range(50)]
    mean_v = sum(vals) / len(vals)
    std_v = (sum((v - mean_v)**2 for v in vals) / (len(vals)-1))**0.5
    rows = []
    for i, v in enumerate(vals):
        z = (v - mean_v) / std_v
        rows.append([str(i+1), _fv(v, 2), _fv(z)])
    rows.append(["Mean", _fv(mean_v, 2), ""])
    rows.append(["Std Dev", _fv(std_v, 2), ""])
    return [("Statistics", h, rows)]


def _multiplication_table():
    h = ["×"] + [str(i) for i in range(1, 13)]
    rows = []
    for r in range(1, 13):
        rows.append([str(r)] + [str(r*c) for c in range(1, 13)])
    return [("Multiply", h, rows)]


def _distance_matrix():
    cities = ["London", "Paris", "Berlin", "Madrid", "Rome",
              "Amsterdam", "Vienna", "Brussels"]
    dists = {
        (0,1): 341, (0,2): 930, (0,3): 1264, (0,4): 1435,
        (0,5): 358, (0,6): 1237, (0,7): 322,
        (1,2): 878, (1,3): 1054, (1,4): 1106, (1,5): 430,
        (1,6): 1034, (1,7): 264,
        (2,3): 1870, (2,4): 1181, (2,5): 577, (2,6): 524, (2,7): 651,
        (3,4): 1363, (3,5): 1480, (3,6): 1809, (3,7): 1316,
        (4,5): 1293, (4,6): 765, (4,7): 1174,
        (5,6): 938, (5,7): 171,
        (6,7): 915,
    }
    h = ["City"] + cities
    rows = []
    for i, city in enumerate(cities):
        row = [city]
        for j in range(len(cities)):
            if i == j:
                row.append("0")
            else:
                k = (min(i,j), max(i,j))
                row.append(str(dists.get(k, "")))
        rows.append(row)
    return [("Distances", h, rows)]


def _periodic_table():
    h = ["Z", "Symbol", "Name", "Mass", "Group", "Period"]
    elements = [
        (1, "H", "Hydrogen", 1.008, 1, 1),
        (2, "He", "Helium", 4.003, 18, 1),
        (3, "Li", "Lithium", 6.941, 1, 2),
        (4, "Be", "Beryllium", 9.012, 2, 2),
        (5, "B", "Boron", 10.81, 13, 2),
        (6, "C", "Carbon", 12.01, 14, 2),
        (7, "N", "Nitrogen", 14.01, 15, 2),
        (8, "O", "Oxygen", 16.00, 16, 2),
        (9, "F", "Fluorine", 19.00, 17, 2),
        (10, "Ne", "Neon", 20.18, 18, 2),
        (11, "Na", "Sodium", 22.99, 1, 3),
        (12, "Mg", "Magnesium", 24.31, 2, 3),
        (13, "Al", "Aluminium", 26.98, 13, 3),
        (14, "Si", "Silicon", 28.09, 14, 3),
        (15, "P", "Phosphorus", 30.97, 15, 3),
        (16, "S", "Sulfur", 32.07, 16, 3),
        (17, "Cl", "Chlorine", 35.45, 17, 3),
        (18, "Ar", "Argon", 39.95, 18, 3),
        (19, "K", "Potassium", 39.10, 1, 4),
        (20, "Ca", "Calcium", 40.08, 2, 4),
    ]
    rows = [[str(z), sym, name, _fv(mass, 3), str(g), str(p)]
            for z, sym, name, mass, g, p in elements]
    return [("Elements", h, rows)]


def _project_timeline():
    h = ["Task", "Start", "End", "Duration (days)", "Status"]
    tasks = [
        ("Requirements", "2026-01-06", "2026-01-17", 12, "Done"),
        ("Design", "2026-01-20", "2026-02-07", 19, "Done"),
        ("Backend Dev", "2026-02-10", "2026-03-21", 40, "Done"),
        ("Frontend Dev", "2026-02-17", "2026-03-28", 40, "In Progress"),
        ("API Integration", "2026-03-24", "2026-04-11", 19, "Todo"),
        ("Testing", "2026-04-14", "2026-05-02", 19, "Todo"),
        ("UAT", "2026-05-05", "2026-05-16", 12, "Todo"),
        ("Deployment", "2026-05-19", "2026-05-23", 5, "Todo"),
    ]
    rows = [[t, s, e, str(d), st] for t, s, e, d, st in tasks]
    return [("Timeline", h, rows)]


def _loan_comparison():
    h = ["Bank", "Rate (%)", "Term (yr)", "Loan Amount",
         "Monthly Payment", "Total Paid", "Total Interest"]
    banks = [
        ("Bank A", 3.5, 30, 400000), ("Bank B", 3.8, 25, 400000),
        ("Bank C", 3.2, 30, 400000), ("Bank D", 4.0, 20, 400000),
        ("Bank E", 3.6, 15, 400000), ("Bank F", 3.9, 30, 400000),
    ]
    rows = []
    for name, rate, term, amount in banks:
        r_m = rate / 100 / 12
        n = term * 12
        pmt = amount * r_m * (1+r_m)**n / ((1+r_m)**n - 1)
        total = pmt * n
        rows.append([name, _fv(rate, 1), str(term), str(amount),
                     _fv(pmt, 2), _fv(total, 2),
                     _fv(total - amount, 2)])
    return [("Loans", h, rows)]


def _weather_data():
    h = ["Date", "High (°C)", "Low (°C)", "Avg (°C)",
         "Humidity (%)", "Precip (mm)"]
    rows = []
    for d in range(1, 32):
        hi = round(random.uniform(18, 32), 1)
        lo = round(hi - random.uniform(5, 12), 1)
        r = len(rows) + 2
        rows.append([f"2026-07-{d:02d}", _fv(hi, 1), _fv(lo, 1),
                     f"=(B{r}+C{r})/2",
                     str(random.randint(30, 95)),
                     _fv(round(random.uniform(0, 15), 1), 1)])
    return [("Weather", h, rows)]


def _prime_numbers():
    h = ["n", "Prime?", "Value"]
    primes = []
    for n in range(2, 201):
        is_p = all(n % i != 0 for i in range(2, int(n**0.5)+1))
        if is_p:
            primes.append(n)
    rows = []
    for i, p in enumerate(primes):
        rows.append([str(i+1), "Yes", str(p)])
    return [("Primes", h, rows)]


def _color_palette():
    h = ["Name", "Hex", "R", "G", "B"]
    colors = [
        ("Red", "#FF0000", 255, 0, 0),
        ("Green", "#00FF00", 0, 255, 0),
        ("Blue", "#0000FF", 0, 0, 255),
        ("Yellow", "#FFFF00", 255, 255, 0),
        ("Cyan", "#00FFFF", 0, 255, 255),
        ("Magenta", "#FF00FF", 255, 0, 255),
        ("Orange", "#FF8000", 255, 128, 0),
        ("Purple", "#8000FF", 128, 0, 255),
        ("Pink", "#FF80C0", 255, 128, 192),
        ("Lime", "#80FF00", 128, 255, 0),
        ("Teal", "#008080", 0, 128, 128),
        ("Navy", "#000080", 0, 0, 128),
        ("Maroon", "#800000", 128, 0, 0),
        ("Olive", "#808000", 128, 128, 0),
        ("Coral", "#FF7F50", 255, 127, 80),
        ("Salmon", "#FA8072", 250, 128, 114),
        ("Gold", "#FFD700", 255, 215, 0),
        ("Silver", "#C0C0C0", 192, 192, 192),
        ("Indigo", "#4B0082", 75, 0, 130),
        ("Violet", "#EE82EE", 238, 130, 238),
    ]
    rows = [[n, hx, str(r), str(g), str(b)]
            for n, hx, r, g, b in colors]
    return [("Colors", h, rows)]


def _matrix_operations():
    h = ["", "C1", "C2", "C3"]
    a = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
    b = [[9, 8, 7], [6, 5, 4], [3, 2, 1]]
    rows = [["Matrix A"]]
    for r in a:
        rows.append([""] + [str(v) for v in r])
    rows.append([""])
    rows.append(["Matrix B"])
    for r in b:
        rows.append([""] + [str(v) for v in r])
    rows.append([""])
    rows.append(["A + B"])
    for i in range(3):
        rows.append([""] + [str(a[i][j]+b[i][j]) for j in range(3)])
    return [("Matrix", h, rows)]


def _exponential_growth():
    h = ["Day", "Population", "Growth Rate", "Daily Increase"]
    pop = 1000
    rate = 0.05
    rows = []
    for d in range(0, 61):
        r = len(rows) + 2
        p = pop * math.exp(rate * d)
        rows.append([str(d), _fv(p, 0), _fv(rate*100, 1)+"%",
                     _fv(p * rate, 0) if d > 0 else "0"])
    return [("Growth", h, rows)]


def _survey_results():
    h = ["Question", "Strongly Agree", "Agree", "Neutral",
         "Disagree", "Strongly Disagree", "Total"]
    qs = [
        "Product is easy to use",
        "Price is fair",
        "Would recommend",
        "Customer support is good",
        "Website is user-friendly",
        "Delivery was timely",
        "Quality meets expectations",
        "Will buy again",
    ]
    rows = []
    for i, q in enumerate(qs):
        vals = [random.randint(5, 50) for _ in range(5)]
        r = i + 2
        rows.append([q] + [str(v) for v in vals]
                    + [f"=SUM(B{r}:F{r})"])
    return [("Survey", h, rows)]


def _physics_projectile():
    h = ["Time (s)", "Vx (m/s)", "Vy (m/s)", "X (m)", "Y (m)"]
    v0 = 50  # m/s
    angle = 45  # degrees
    g = 9.81
    vx = v0 * math.cos(math.radians(angle))
    vy0 = v0 * math.sin(math.radians(angle))
    rows = []
    for i in range(0, 80):
        t = i * 0.1
        vy = vy0 - g * t
        x = vx * t
        y = vy0 * t - 0.5 * g * t * t
        if y < -0.01 and t > 0:
            break
        rows.append([_fv(t, 1), _fv(vx, 2), _fv(vy, 2),
                     _fv(x, 2), _fv(max(y, 0), 2)])
    return [("Projectile", h, rows)]


def _inventory():
    h = ["SKU", "Product", "Category", "Quantity", "Unit Cost",
         "Total Value", "Reorder Level", "Status"]
    items = [
        ("SKU001", "Widget A", "Hardware", 150, 4.50, 20),
        ("SKU002", "Widget B", "Hardware", 5, 7.25, 30),
        ("SKU003", "Gadget X", "Electronics", 200, 25.00, 50),
        ("SKU004", "Gadget Y", "Electronics", 15, 45.00, 20),
        ("SKU005", "Part 101", "Components", 500, 1.20, 100),
        ("SKU006", "Part 202", "Components", 80, 2.50, 100),
        ("SKU007", "Cable USB", "Accessories", 300, 3.00, 50),
        ("SKU008", "Adapter", "Accessories", 10, 8.00, 25),
        ("SKU009", "Sensor A", "Electronics", 45, 15.00, 30),
        ("SKU010", "Bolt M8", "Hardware", 1000, 0.15, 200),
    ]
    rows = []
    for i, (sku, prod, cat, qty, cost, reorder) in enumerate(items):
        r = i + 2
        status = "Low Stock" if qty < reorder else "OK"
        rows.append([sku, prod, cat, str(qty), _fv(cost, 2),
                     f"=D{r}*E{r}", str(reorder), status])
    return [("Inventory", h, rows)]


def _workout_log():
    h = ["Date", "Exercise", "Sets", "Reps", "Weight (kg)", "Volume"]
    exercises = [
        ("2026-05-19", "Squat", 4, 8, 100),
        ("2026-05-19", "Bench Press", 4, 10, 80),
        ("2026-05-19", "Deadlift", 3, 5, 140),
        ("2026-05-21", "OHP", 4, 8, 50),
        ("2026-05-21", "Barbell Row", 4, 8, 70),
        ("2026-05-21", "Pull-ups", 3, 10, 0),
        ("2026-05-23", "Squat", 5, 5, 110),
        ("2026-05-23", "Bench Press", 5, 5, 90),
        ("2026-05-23", "RDL", 3, 10, 80),
    ]
    rows = []
    for i, (d, ex, s, rp, w) in enumerate(exercises):
        r = i + 2
        rows.append([d, ex, str(s), str(rp), str(w),
                     f"=C{r}*D{r}*E{r}"])
    return [("Workout", h, rows)]


def _blood_pressure():
    h = ["Date", "Time", "Systolic", "Diastolic", "Pulse", "Notes"]
    rows = []
    for d in range(1, 15):
        for time in ["08:00", "20:00"]:
            sys = random.randint(110, 145)
            dia = random.randint(65, 90)
            pulse = random.randint(60, 85)
            rows.append([f"2026-05-{d:02d}", time,
                         str(sys), str(dia), str(pulse), ""])
    return [("BP Log", h, rows)]


def _recipe_scaler():
    h = ["Ingredient", "Original (serves 4)", "Scaled (serves N)",
         "Unit"]
    ingredients = [
        ("Flour", 250, "g"), ("Sugar", 100, "g"),
        ("Butter", 125, "g"), ("Eggs", 2, ""),
        ("Milk", 200, "ml"), ("Vanilla", 1, "tsp"),
        ("Baking powder", 2, "tsp"), ("Salt", 0.5, "tsp"),
    ]
    # N (number of servings) goes in B1
    rows_data = [["Servings:", "8"]]
    rows = []
    for i, (name, amt, unit) in enumerate(ingredients):
        r = i + 3  # offset by header + servings row
        rows.append([name, str(amt), f"=B{r}*$B$1/4", unit])
    return [("Recipe", h, rows_data + rows)]


def _electricity_bill():
    h = ["Month", "kWh Used", "Rate ($/kWh)", "Base Charge",
         "Total Bill"]
    rows = []
    for i, month in enumerate(["Jan", "Feb", "Mar", "Apr", "May",
                                "Jun", "Jul", "Aug", "Sep", "Oct",
                                "Nov", "Dec"]):
        r = i + 2
        kwh = random.randint(200, 900)
        rows.append([month, str(kwh), "0.12", "15.00",
                     f"=B{r}*C{r}+D{r}"])
    rows.append(["Total", f"=SUM(B2:B13)", "", "",
                 f"=SUM(E2:E13)"])
    return [("Electric", h, rows)]


def _periodic_payments():
    h = ["Period", "Payment", "Interest", "Principal", "Balance"]
    bal = 50000
    rate = 0.06 / 12
    n_pay = 60
    pmt = bal * rate * (1+rate)**n_pay / ((1+rate)**n_pay - 1)
    rows = []
    for p in range(1, n_pay+1):
        intr = bal * rate
        princ = pmt - intr
        bal -= princ
        rows.append([str(p), _fv(pmt, 2), _fv(intr, 2),
                     _fv(princ, 2), _fv(max(bal, 0), 2)])
    return [("Amortization", h, rows)]


def _soccer_league():
    h = ["Team", "Played", "Won", "Drawn", "Lost",
         "GF", "GA", "GD", "Points"]
    teams = ["Arsenal", "Man City", "Liverpool", "Chelsea",
             "Tottenham", "Man Utd", "Newcastle", "Brighton",
             "Aston Villa", "West Ham"]
    rows = []
    for i, t in enumerate(teams):
        played = 38
        w = random.randint(8, 28)
        d = random.randint(2, 12)
        lo = played - w - d
        gf = random.randint(40, 95)
        ga = random.randint(25, 65)
        r = i + 2
        rows.append([t, str(played), str(w), str(d), str(lo),
                     str(gf), str(ga), f"=F{r}-G{r}",
                     f"=C{r}*3+D{r}"])
    return [("League", h, rows)]


def _chemistry_solutions():
    h = ["Solute", "Molar Mass (g/mol)", "Mass (g)",
         "Volume (L)", "Molarity (M)"]
    solutes = [
        ("NaCl", 58.44, 29.22, 0.5),
        ("HCl", 36.46, 18.23, 1.0),
        ("NaOH", 40.00, 8.00, 0.5),
        ("H2SO4", 98.08, 49.04, 1.0),
        ("CaCO3", 100.09, 25.02, 0.25),
        ("KMnO4", 158.03, 15.80, 0.5),
        ("AgNO3", 169.87, 33.97, 0.2),
        ("CuSO4", 159.61, 31.92, 0.4),
    ]
    rows = []
    for i, (name, mm, mass, vol) in enumerate(solutes):
        r = i + 2
        rows.append([name, _fv(mm, 2), _fv(mass, 2), _fv(vol, 3),
                     f"=(C{r}/B{r})/D{r}"])
    return [("Solutions", h, rows)]


def _ascii_table():
    h = ["Decimal", "Hex", "Char", "Description"]
    rows = []
    for code in range(32, 127):
        ch = chr(code) if code >= 32 else ""
        desc = ""
        if code == 32:
            desc = "Space"
        elif 48 <= code <= 57:
            desc = "Digit"
        elif 65 <= code <= 90:
            desc = "Uppercase"
        elif 97 <= code <= 122:
            desc = "Lowercase"
        elif code in (33, 63):
            desc = "Punctuation"
        rows.append([str(code), f"0x{code:02X}", ch, desc])
    return [("ASCII", h, rows)]


def _regression_data():
    h = ["x", "y", "x²", "xy"]
    random.seed(99)
    rows = []
    for i in range(30):
        x = round(i * 0.5 + random.uniform(-0.5, 0.5), 2)
        y = round(2.5 * x + 10 + random.gauss(0, 3), 2)
        r = i + 2
        rows.append([_fv(x, 2), _fv(y, 2),
                     f"=A{r}^2", f"=A{r}*B{r}"])
    n = len(rows) + 1
    rows.append(["Sum", f"=SUM(B2:B{n})", f"=SUM(C2:C{n})",
                 f"=SUM(D2:D{n})"])
    return [("Regression", h, rows)]


def _time_zones():
    h = ["City", "UTC Offset", "When London 12:00",
         "When New York 12:00"]
    zones = [
        ("London", 0), ("New York", -5), ("Los Angeles", -8),
        ("Tokyo", 9), ("Sydney", 10), ("Dubai", 4),
        ("Mumbai", 5.5), ("Berlin", 1), ("São Paulo", -3),
        ("Moscow", 3), ("Shanghai", 8), ("Singapore", 8),
        ("Cairo", 2), ("Johannesburg", 2), ("Auckland", 12),
    ]
    rows = []
    for city, off in zones:
        ldn = 12 + off
        ny = 12 + off + 5
        rows.append([city, f"UTC{off:+.1f}" if off % 1 else
                     f"UTC{off:+.0f}",
                     f"{int(ldn)%24:02d}:00",
                     f"{int(ny)%24:02d}:00"])
    return [("TimeZones", h, rows)]


def _hex_dec_bin():
    h = ["Decimal", "Binary", "Octal", "Hexadecimal"]
    rows = []
    for n in range(0, 65):
        rows.append([str(n), bin(n)[2:], oct(n)[2:], hex(n)[2:].upper()])
    return [("NumBases", h, rows)]


def _book_collection():
    h = ["Title", "Author", "Year", "Pages", "Genre", "Rating"]
    books = [
        ("1984", "George Orwell", 1949, 328, "Dystopian", 4.7),
        ("Dune", "Frank Herbert", 1965, 412, "Sci-Fi", 4.6),
        ("Pride and Prejudice", "Jane Austen", 1813, 279, "Romance", 4.5),
        ("The Hobbit", "J.R.R. Tolkien", 1937, 310, "Fantasy", 4.7),
        ("Brave New World", "Aldous Huxley", 1932, 311, "Dystopian", 4.3),
        ("Crime and Punishment", "Dostoevsky", 1866, 671, "Fiction", 4.4),
        ("The Great Gatsby", "F. Scott Fitzgerald", 1925, 180,
         "Fiction", 4.2),
        ("Sapiens", "Yuval N. Harari", 2011, 443, "Non-Fiction", 4.4),
        ("To Kill a Mockingbird", "Harper Lee", 1960, 281,
         "Fiction", 4.6),
        ("The Alchemist", "Paulo Coelho", 1988, 197, "Fiction", 4.2),
    ]
    rows = [[t, a, str(y), str(p), g, _fv(r, 1)]
            for t, a, y, p, g, r in books]
    return [("Books", h, rows)]


def _resistor_color():
    h = ["Band 1", "Band 2", "Multiplier", "Value (Ω)", "Tolerance"]
    colors = ["Black", "Brown", "Red", "Orange", "Yellow",
              "Green", "Blue", "Violet", "Grey", "White"]
    combos = [(2, 2, 3), (1, 0, 2), (4, 7, 1), (5, 6, 0),
              (1, 0, 4), (3, 3, 2), (6, 8, 1), (2, 7, 3),
              (1, 5, 3), (4, 7, 2)]
    rows = []
    for b1, b2, mult in combos:
        val = (b1*10 + b2) * (10**mult)
        if val >= 1e6:
            vs = f"{val/1e6:.1f}M"
        elif val >= 1e3:
            vs = f"{val/1e3:.1f}k"
        else:
            vs = str(int(val))
        rows.append([colors[b1], colors[b2], colors[mult],
                     vs, "±5%"])
    return [("Resistors", h, rows)]


def _tip_calculator():
    h = ["Bill Amount", "Tip %", "Tip Amount", "Total",
         "Per Person (2)", "Per Person (3)", "Per Person (4)"]
    rows = []
    for bill in [15, 25, 35, 50, 75, 100, 150, 200]:
        for pct in [15, 18, 20]:
            r = len(rows) + 2
            rows.append([str(bill), str(pct),
                         f"=A{r}*B{r}/100", f"=A{r}+C{r}",
                         f"=D{r}/2", f"=D{r}/3", f"=D{r}/4"])
    return [("Tips", h, rows)]


def _password_generator():
    h = ["#", "Password (8)", "Password (12)", "Password (16)",
         "Strength"]
    chars = ("abcdefghijklmnopqrstuvwxyz"
             "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%")
    rows = []
    for i in range(20):
        p8 = "".join(random.choice(chars) for _ in range(8))
        p12 = "".join(random.choice(chars) for _ in range(12))
        p16 = "".join(random.choice(chars) for _ in range(16))
        rows.append([str(i+1), p8, p12, p16,
                     "Strong" if len(p16) >= 16 else "Medium"])
    return [("Passwords", h, rows)]


def _world_population():
    h = ["Country", "Population (M)", "Area (km²)",
         "Density (per km²)"]
    countries = [
        ("China", 1412, 9597000), ("India", 1408, 3287000),
        ("USA", 331, 9834000), ("Indonesia", 274, 1905000),
        ("Pakistan", 221, 881000), ("Brazil", 214, 8516000),
        ("Nigeria", 211, 924000), ("Bangladesh", 166, 148000),
        ("Russia", 146, 17098000), ("Mexico", 130, 1964000),
        ("Japan", 126, 378000), ("Ethiopia", 118, 1104000),
        ("Philippines", 111, 300000), ("Egypt", 102, 1002000),
        ("Germany", 84, 357000),
    ]
    rows = []
    for i, (c, pop, area) in enumerate(countries):
        r = i + 2
        rows.append([c, str(pop), str(area),
                     f"=B{r}*1000000/C{r}"])
    return [("Population", h, rows)]


def _multi_sheet_demo():
    s1 = ("Data", ["X", "Y1", "Y2"],
          [[_fv(i*0.1, 1),
            _fv(math.sin(i*0.1), 4),
            _fv(math.cos(i*0.1), 4)]
           for i in range(63)])
    s2 = ("Summary", ["Metric", "Y1", "Y2"],
          [["Min", "=MIN(Data!B:B)", "=MIN(Data!C:C)"],  # placeholder
           ["Max", "", ""],
           ["Points", "63", "63"]])
    return [s1, s2]


# ── Registry ─────────────────────────────────────────────────────

EXAMPLES = [
    # (name, category, builder)
    ("Monthly Budget",              "Finance",      _budget),
    ("Invoice Template",            "Finance",      _invoice),
    ("Compound Interest",           "Finance",      _compound_interest),
    ("Mortgage Amortization",       "Finance",      _mortgage),
    ("Loan Comparison",             "Finance",      _loan_comparison),
    ("Currency Converter",          "Finance",      _currency_converter),
    ("Stock Portfolio",             "Finance",      _stock_portfolio),
    ("Electricity Bill",            "Finance",      _electricity_bill),
    ("Periodic Payments",           "Finance",      _periodic_payments),
    ("Tip Calculator",              "Finance",      _tip_calculator),
    ("Grade Book",                  "Education",    _grade_book),
    ("Multiplication Table",        "Education",    _multiplication_table),
    ("Fibonacci Sequence",          "Education",    _fibonacci),
    ("Prime Numbers",               "Education",    _prime_numbers),
    ("Hex / Dec / Binary",          "Education",    _hex_dec_bin),
    ("ASCII Table",                 "Education",    _ascii_table),
    ("Sine / Cosine Table",         "Math",         _sine_cosine),
    ("Quadratic Solver",            "Math",         _quadratic_solver),
    ("Matrix Operations",           "Math",         _matrix_operations),
    ("Exponential Growth",          "Math",         _exponential_growth),
    ("Regression Data",             "Math",         _regression_data),
    ("Statistics Sample",           "Math",         _statistics_data),
    ("Projectile Motion",           "Science",      _physics_projectile),
    ("Periodic Table",              "Science",      _periodic_table),
    ("Chemistry Solutions",         "Science",      _chemistry_solutions),
    ("Resistor Color Codes",        "Science",      _resistor_color),
    ("Temperature Conversion",      "Science",      _temperature_conversion),
    ("Unit Conversions",            "Science",      _unit_conversions),
    ("Sales Dashboard",             "Business",     _sales_dashboard),
    ("Employee Directory",          "Business",     _employee_directory),
    ("Inventory Tracker",           "Business",     _inventory),
    ("Project Timeline",            "Business",     _project_timeline),
    ("Survey Results",              "Business",     _survey_results),
    ("Soccer League Table",         "Business",     _soccer_league),
    ("Attendance Tracker",          "Daily Life",   _attendance_tracker),
    ("BMI Calculator",              "Daily Life",   _bmi_calculator),
    ("Calorie Tracker",             "Daily Life",   _calorie_tracker),
    ("Blood Pressure Log",          "Daily Life",   _blood_pressure),
    ("Workout Log",                 "Daily Life",   _workout_log),
    ("Recipe Scaler",               "Daily Life",   _recipe_scaler),
    ("Todo List",                   "Daily Life",   _todo_list),
    ("Weather Data",                "Daily Life",   _weather_data),
    ("Book Collection",             "Daily Life",   _book_collection),
    ("Password Generator",          "Daily Life",   _password_generator),
    ("Color Palette (RGB)",         "Reference",    _color_palette),
    ("Distance Matrix",             "Reference",    _distance_matrix),
    ("Time Zones",                  "Reference",    _time_zones),
    ("World Population",            "Reference",    _world_population),
    ("Multi-Sheet Demo",            "Reference",    _multi_sheet_demo),
    ("Sine / Cos Plot Data",        "Reference",    _sine_cosine),
]
