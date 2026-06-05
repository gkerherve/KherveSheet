"""Build the "Projectile With Drag" Python-cell example .ksheet.

Numerically integrates projectile motion with quadratic air drag and
compares it to the no-drag parabola. Inputs are in cells.

Run:  python examples/build_projectile_drag.py

Copyright (C) 2026 Gwilherm Kerherve — GPL-3.0-or-later.
"""

import os
import sys

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "examples"))

from ksheet_author import Workbook, PALETTE

OUTPUT = os.path.join(
    _REPO, "examples", "python", "Engineering", "Projectile With Drag.ksheet"
)


def build() -> str:
    wb = Workbook(min_rows=40, min_cols=14)
    s = wb.add_sheet("Projectile + Drag")

    # Title
    s.title_block(
        "Projectile Motion with Air Drag",
        "Numerical integration of quadratic drag vs ideal parabola — edit inputs, press Ctrl+Enter",
    )

    # Input parameters
    s.set(3, 0, "Parameters")
    s.fmt(3, 0, bold=True, font_color=PALETTE["accent"])

    params = [
        ("Launch speed  v0 (m/s)", 50.0),
        ("Launch angle  θ (°)", 45.0),
        ("Drag coefficient  Cd (dimensionless)", 0.47),
        ("Projectile mass  m (kg)", 0.145),
        ("Projectile cross-section  A (m²)", 0.00426),
        ("Air density  ρ (kg/m³)", 1.225),
    ]
    for i, (lbl, val) in enumerate(params):
        r = 4 + i
        s.set(r, 0, lbl)
        s.set(r, 1, val)
        s.fmt(r, 1, bg=PALETTE["warn"], align="center", number_format="0.####")

    s.box(4, 0, 9, 1, color=PALETTE["accent"], width=1.5)
    s.col_width(0, 260)
    s.col_width(1, 110)

    s.note(4, 1,
           "Default values are approximately a baseball (Cd=0.47, m=145 g, A=42.6 cm²). "
           "Increase Cd to see stronger drag effects.",
           kind="note")

    # Derived: no-drag range  R = v0^2 sin(2θ)/g
    s.set(11, 0, "No-drag range  R (m)")
    s.fmt(11, 0, bold=True)
    s.formula(
        11, 1,
        "=PY\n"
        "import numpy as np\n"
        "v0 = ks('B5')\n"
        "theta_deg = ks('B6')\n"
        "g = 9.81\n"
        "theta = np.radians(theta_deg)\n"
        "R = v0**2 * np.sin(2 * theta) / g\n"
        "round(R, 2)\n"
    )
    s.fmt(11, 1, bg=PALETTE["good"], bold=True, align="center", number_format="0.00")
    s.box(11, 0, 11, 1, color=PALETTE["header"], width=1.5)

    # Drag range (computed by the plot cell below; separate =PY cell)
    s.set(12, 0, "With-drag range  R_drag (m)")
    s.fmt(12, 0, bold=True)
    s.formula(
        12, 1,
        "=PY\n"
        "import numpy as np\n"
        "from scipy.integrate import solve_ivp\n"
        "v0       = ks('B5')\n"
        "theta    = np.radians(ks('B6'))\n"
        "Cd       = ks('B7')\n"
        "m        = ks('B8')\n"
        "A        = ks('B9')\n"
        "rho      = ks('B10')\n"
        "g        = 9.81\n"
        "k        = 0.5 * rho * Cd * A\n"
        "vx0      = v0 * np.cos(theta)\n"
        "vy0      = v0 * np.sin(theta)\n"
        "def deriv(t, state):\n"
        "    xp, yp, vx, vy = state\n"
        "    speed = np.sqrt(vx**2 + vy**2)\n"
        "    ax = -(k / m) * speed * vx\n"
        "    ay = -g - (k / m) * speed * vy\n"
        "    return [vx, vy, ax, ay]\n"
        "def hit_ground(t, state): return state[1]\n"
        "hit_ground.terminal = True\n"
        "hit_ground.direction = -1\n"
        "sol = solve_ivp(deriv, [0, 30], [0, 0, vx0, vy0],\n"
        "                events=hit_ground, max_step=0.01, rtol=1e-6)\n"
        "x_drag = sol.y[0]\n"
        "round(float(x_drag[-1]), 2)\n"
    )
    s.fmt(12, 1, bg=PALETTE["band"], bold=True, align="center", number_format="0.00")
    s.box(12, 0, 12, 1, color=PALETTE["header"], width=1.5)

    # Instruction row
    s.set(14, 0, "Trajectory plot  (=PY cell — press Ctrl+Enter to refresh)")
    s.fmt(14, 0, bold=True, font_color=PALETTE["header"])

    # =PY plot cell
    py_code = (
        "=PY\n"
        "import numpy as np, matplotlib.pyplot as plt\n"
        "from scipy.integrate import solve_ivp\n"
        "v0    = ks('B5')\n"
        "theta = np.radians(ks('B6'))\n"
        "Cd    = ks('B7')\n"
        "m     = ks('B8')\n"
        "A     = ks('B9')\n"
        "rho   = ks('B10')\n"
        "g     = 9.81\n"
        "k     = 0.5 * rho * Cd * A\n"
        "vx0   = v0 * np.cos(theta)\n"
        "vy0   = v0 * np.sin(theta)\n"
        "# No-drag parabola\n"
        "T_nd  = 2 * vy0 / g\n"
        "t_nd  = np.linspace(0, T_nd, 300)\n"
        "x_nd  = vx0 * t_nd\n"
        "y_nd  = vy0 * t_nd - 0.5 * g * t_nd**2\n"
        "# Drag ODE\n"
        "def deriv(t, state):\n"
        "    xp, yp, vx, vy = state\n"
        "    speed = np.sqrt(vx**2 + vy**2)\n"
        "    ax = -(k / m) * speed * vx\n"
        "    ay = -g - (k / m) * speed * vy\n"
        "    return [vx, vy, ax, ay]\n"
        "def hit_ground(t, state): return state[1]\n"
        "hit_ground.terminal = True\n"
        "hit_ground.direction = -1\n"
        "sol = solve_ivp(deriv, [0, 30], [0, 0, vx0, vy0],\n"
        "                events=hit_ground, max_step=0.02, rtol=1e-6)\n"
        "x_d = sol.y[0]\n"
        "y_d = sol.y[1]\n"
        "fig, ax = plt.subplots(figsize=(7, 4))\n"
        "ax.plot(x_nd, y_nd, color='#70ad47', linewidth=2, linestyle='--', label='No drag')\n"
        "ax.plot(x_d,  y_d,  color='#4472c4', linewidth=2.5, label=f'With drag (Cd={Cd})')\n"
        "ax.set_xlabel('Horizontal distance  x (m)')\n"
        "ax.set_ylabel('Height  y (m)')\n"
        "ax.set_title('Projectile Motion: Drag vs No Drag')\n"
        "ax.legend()\n"
        "ax.grid(True, linestyle='--', alpha=0.4)\n"
        "ax.set_ylim(bottom=0)\n"
        "plt.tight_layout()\n"
        "plt.gcf()"
    )
    s.formula(15, 0, py_code)
    s.fmt(15, 0, bg="#f0f4ff", font_family="Consolas", font_size=9)

    s.note(15, 0,
           "Drag force = ½ρCd·A·v². The ODE is solved with scipy solve_ivp "
           "(RK45); integration stops when y returns to zero.",
           kind="note")

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    wb.save(OUTPUT)
    return OUTPUT


if __name__ == "__main__":
    print("Wrote", build())
