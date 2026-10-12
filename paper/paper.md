---
title: 'KherveSheet: a spreadsheet for teaching scientific data analysis, from formulas to Python, with AI assistants that show their work'
tags:
  - Python
  - spreadsheet
  - science education
  - data analysis
  - Model Context Protocol
  - X-ray photoelectron spectroscopy
authors:
  - name: Gwilherm Kerherve
    orcid: 0000-0002-6449-1828
    affiliation: 1
affiliations:
  - name: Department of Materials, Imperial College London, London SW7 2AZ, United Kingdom
    index: 1
date: 12 October 2026
bibliography: paper.bib
---

# Summary

KherveSheet is a free, open-source spreadsheet for learning and teaching
scientific data analysis. It looks and works like the spreadsheets students
already know, with a grid, formulas, charts and `.xlsx` files, and it adds a
path from there to programming: any cell can hold a complete Python program
(a `=PY` cell) that reads and writes the grid next to it. KherveSheet ships
with more than 180 ready-made workbooks, about 150 of them in science,
engineering and data processing. It also includes graded exercises for
undergraduate years one to four and an assistant interface that lets AI
tools work in the sheet only through visible, editable cells. It runs on
Windows and macOS under the GPL-3.0 licence.

# Statement of need

Science students meet data analysis twice: first in a spreadsheet during
laboratory classes, and later in Python or a notebook. The jump between the
two is large. In a spreadsheet the data is visible but the logic is hidden
in formulas, and errors are easy to make and hard to find [@ziemann2016;
@herndon2014]. In a notebook the logic is explicit, but students lose the
grid they think in and must learn a new environment at the same time as a
new language [@jupyter].

KherveSheet is designed to make that transition gradual. Students start with
ordinary formulas and charts. They then put a few lines of Python in a cell,
for example `ks("A2:A100")` to read a column and `ks_set("C2", ...)` to write a
result, and see the result appear beside their data. NumPy, SciPy, pandas and
Matplotlib are available in every cell, and a cell can return a figure that
embeds in the sheet. The code stays in the grid, next to the numbers it
produces, so the step from formula to program is small and visible.

AI assistants pose a related teaching problem: students can obtain an
answer without seeing how it was reached. KherveSheet includes a Model
Context Protocol (MCP) server [@mcp2024], so any local assistant (Claude,
Cursor, VS Code, LM Studio and others) can work in the open workbook. It can
only do so by writing cells, so every result it produces is code that the
student and the instructor can read, question and re-run. An access level
set by the user decides whether an assistant may run Python at all.

# Learning materials

The examples are organised by subject and by level:

* **Graded exercises** for undergraduate years one to four. Topics run from
  Ohm's law and projectile kinematics, through damped oscillators,
  diffraction, black-body radiation and the particle in a box, to Arrhenius
  analysis and least-squares fitting.
* **Experimental techniques** with realistic data: XPS, Auger, UV-Vis,
  FTIR, Raman, EDX, XRF and XRD spectra, BET surface area, TGA, DSC, Tauc
  band gaps and the Hall effect.
* **Fifty-nine Python-cell workbooks** covering numerical methods,
  Monte Carlo methods, signal processing, curve fitting, statistics and
  simulations such as the Ising model, predator–prey dynamics and random
  walks, including four that read live data from the web.
* **Data-processing recipes**: smoothing, baseline correction, outlier
  removal, resampling, derivatives and integrals.

Instructors can edit any workbook, save it as `.ksheet` or `.xlsx`, and
share it with students, who need nothing beyond the free application.

# Example: a research-grade analysis students can read

The repository includes a worked case study (`paper/demo/`) that fits the
Ti 2p X-ray photoelectron spectrum of a TiO$_2$ reference sample. Every step
is a short `=PY` cell. One loads the instrument file, one builds a Shirley
background [@shirley1972], and one fits a Voigt spin–orbit doublet and the
Ti$^{4+}$ satellite with SciPy [@scipy]. A results table and a Monte Carlo
error analysis follow, each in its own cell. The figure (\autoref{fig:ti2p})
is a native chart drawn in the conventions of the XPS literature
[@major2020]. The analysis gives a 2p$_{3/2}$ position of 458.10 eV and a
spin–orbit splitting of 5.70 eV, as expected for TiO$_2$ [@biesinger2010].

The example was built by an AI assistant over MCP, so it also shows
students what a transparent AI-assisted analysis looks like. The log of
every assistant action is included, and each cell can be opened, changed
and re-run. For instance, a student can change the background model and see
how the peak areas move.

![Ti 2p spectrum of TiO$_2$ analysed entirely in `=PY` cells and drawn as a
native KherveSheet chart: a Voigt spin–orbit doublet and the Ti$^{4+}$
satellite over a Shirley background.\label{fig:ti2p}](figures/tio2_ti2p_chart.png){ width=85% }

# Design and quality

KherveSheet is written in Python with PyQt5. Its calculation engine has no
Qt dependency, so the same formulas run in the desktop application and in
the browser through Pyodide. More than 450 automated tests check the formula
engine against a golden set of 245 formulas, as well as Python cells,
charts, the Solver, `.xlsx` round trips and the MCP tools. The tests run on
every change.

# AI usage disclosure

Generative AI was used in this work. Claude (Anthropic; Claude Opus and
Sonnet models, through Claude Code, 2025–2026) assisted with writing parts of
the KherveSheet source code, tests, learning materials and documentation, and
with drafting and editing this paper. In the worked example, Claude also
drove the MCP session that placed the `=PY` cells. The author designed the
software, made all core design and teaching decisions, chose the scientific
analyses, and reviewed, tested and validated all AI-assisted code, materials
and text, and takes full responsibility for them.

# References
