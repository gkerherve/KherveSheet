---
title: 'KherveSheet: an Excel-like spreadsheet for scientists, with Python in every cell and AI assistants that work through the grid'
tags:
  - Python
  - spreadsheet
  - scientific data analysis
  - reproducibility
  - Model Context Protocol
  - large language models
  - X-ray photoelectron spectroscopy
authors:
  - name: Gwilherm Kerherve
    orcid: 0000-0002-6449-1828
    affiliation: 1
affiliations:
  - name: Department of Materials, Imperial College London, London SW7 2AZ, United Kingdom
    index: 1
date: 12 October 2026
bibliography: ../paper.bib
---

# Summary

KherveSheet is a desktop spreadsheet made for scientists. It looks and works
like the spreadsheets researchers already use: a grid, formulas, cell
formatting, charts and `.xlsx` import and export, with about 290 built-in
functions. Behind that familiar interface it adds what experimental work
needs:

* **Python in any cell.** A `=PY` cell holds a complete program, with imports,
  functions, loops and network access. It reads the grid with `ks("A1:B10")`,
  writes back with `ks_set(...)`, and has NumPy, SciPy, pandas and Matplotlib
  available. Its last expression becomes the cell's value: a number, a block
  of values, or an embedded Matplotlib figure. All `=PY` cells share one
  namespace, and cells can poll live data, for example instrument logs or web
  APIs.
* **Charts for publication.** Native charts have a full journal-style
  vocabulary: reversed axes, components filled down to a baseline, minor
  ticks with independent directions on each edge, annotations and export to
  PNG, SVG or PDF at any resolution. Where a native chart is not enough, a
  `=PY` cell can return any Matplotlib figure.
* **Analysis tools.** These include an Excel-style Solver, 23 trendline models
  with goodness-of-fit statistics, and lmfit-based peak fitting [@lmfit] over
  Shirley, Tougaard or polynomial backgrounds.
* **Ready-made scientific workbooks.** KherveSheet ships with more than 180
  templates and worked examples, about 150 of them in science, engineering and
  data processing, and 59 written as `=PY` programs. They cover spectroscopy
  (XPS, Auger, UV-Vis, FTIR, Raman, EDX, XRF, XRD), materials
  characterisation (BET, TGA, DSC, Tauc plots, Hall effect), kinetics and
  thermodynamics, signal processing, statistics and Monte Carlo simulation.
  A set of graded exercises supports undergraduate teaching from first to
  fourth year.
* **AI assistants that work in the grid.** A built-in Model Context Protocol
  (MCP) server [@mcp2024] lets any local MCP client, such as Claude Desktop,
  Claude Code, Cursor, VS Code or LM Studio, read and edit the open workbook
  through 36 documented tools. An assistant does its analysis by writing
  `=PY` cells, so every number it produces traces back to code a person can
  read, edit and re-run.

KherveSheet is written in Python with PyQt5 and released under GPL-3.0 for
Windows and macOS. Its calculation engine has no Qt dependency and also runs
in the browser through Pyodide.

# Statement of need

Spreadsheets remain the tool most scientists reach for first: to look at an
instrument export, tabulate results or make a quick plot. General-purpose
spreadsheets serve this work poorly. Their numerical tools are limited, their
charts need extensive manual work to reach journal conventions, and anything
beyond a formula means leaving for a programming environment. Their failure
modes are also well documented. Automatic type conversion turned gene symbols
into dates in roughly a fifth of the genomics papers that came with Excel gene
lists [@ziemann2016]. A range error in a widely cited macroeconomics
spreadsheet went unnoticed until others tried to reproduce it [@herndon2014].
In both cases the logic was hidden in formulas and manual steps.

Notebooks such as Jupyter [@jupyter] solve the transparency problem, but they
ask experimental scientists to give up the grid they think in. KherveSheet
keeps the grid and puts real code in it. Data stays visible in cells, the
analysis is readable Python next to it, and a template library means a user
starts from a working XPS quantification or BET analysis instead of a blank
sheet.

The same design addresses a newer problem. Large language model (LLM)
assistants can process a dataset in seconds, but their intermediate steps
usually stay inside a conversation, which makes the result hard to check or
reproduce. In fields such as X-ray photoelectron spectroscopy (XPS),
inconsistent peak fitting is already a recognised source of error in the
literature [@major2020], so an opaque assistant is a risk. In KherveSheet the
assistant has no private workspace. The grid is the shared interface, and
everything the assistant computes is a cell the scientist can audit. Every
remote change is one undo step. An access level (read only, edit or full)
decides whether a client may run Python at all, and the MCP server listens only
on the local machine, so unpublished data never leaves the user's computer.

The intended users are experimental scientists, such as surface scientists,
chemists, materials scientists and physicists, together with their students.

# State of the field

Python inside a spreadsheet has been explored before. Pyspread [@pyspread]
makes every cell a Python expression. Microsoft's Python in Excel
[@pythoninexcel] adds a `=PY` function that runs in Microsoft's cloud. Reactive
notebooks such as marimo [@marimo] offer Python with live outputs, but they are
not spreadsheets. KherveSheet differs in four ways. Its cells hold full
multi-line programs that run locally. Its interface, tools and template library
are aimed at laboratory science rather than general office work. Its native
charts follow scientific plotting conventions. And it is designed for AI
assistants that have to work through visible cells, a model that MCP has only
recently made possible.

# Example: fitting the Ti 2p spectrum of TiO$_2$ through MCP

As a worked example, we fit the Ti 2p core-level spectrum of a TiO$_2$
reference sample. The spectrum was recorded with monochromatic Al K$\alpha$
radiation. An MCP client placed five `=PY` cells in an empty workbook. Apart
from formatting and saving, the client did nothing except call
`set_python_cell`. Every step of the analysis is code in the grid
(\autoref{fig:window}):

* **A1** loads the instrument export with pandas and writes binding energy
  and counts into columns A and B.
* **C1** defines an iterative Shirley background [@shirley1972] and uses it
  to seed the fit.
* **D1** fits the spectrum over the full 448–475 eV range with SciPy
  [@scipy]. The model has a Ti$^{4+}$ 2p$_{3/2}$/2p$_{1/2}$ Voigt doublet in
  which the 2p$_{1/2}$ line has its own widths, to allow for Coster–Kronig
  broadening. It adds a Gaussian for the Ti$^{4+}$ charge-transfer satellite,
  and an *active* Shirley background [@herreragomez2014] that is built from
  the fitted peaks and refined with them. The components, envelope and
  residual are written into columns D–H.
* **I1** writes a results table with positions, FWHM (Olivero–Longbothum
  approximation [@olivero1977]), heights, areas, the spin–orbit splitting
  with its uncertainty, and the reduced $\chi^2$.
* **T1** runs a Monte Carlo error analysis. It draws 300 synthetic spectra
  from the fitted model with Poisson counting noise, refits each one, and
  writes every refit (T12 onwards) and a summary table (T3:X9) into the grid.
* **I40** returns a Matplotlib figure with normalised residuals, embedded in
  the grid as a quick visual check of the fit.

The publication figure (\autoref{fig:ti2p}) is a native KherveSheet chart,
not Python code. The client built it with `insert_chart` over columns A–F and
filled each component down to the Shirley background with `style_chart`. It
drew the spin–orbit splitting and the satellite offset with `annotate_chart`.
With `configure_axis` it reversed the binding-energy axis, following XPS
conventions [@major2020], and set a full frame with minor ticks. It then
exported the chart with `export_chart` at 300 dpi. The chart stays linked to
the cells, so re-running a `=PY` cell redraws it.

![KherveSheet after the MCP session. Every number comes from `=PY` cells
in row 1: the envelope and residual (columns G–H), the results table (I3:M9),
and the Monte Carlo summary (T3:X9) with its 300 refits below it. The Ti 2p
spectrum and the Monte Carlo histogram are native KherveSheet charts over
those cells.\label{fig:window}](../figures/khervesheet_window.png)

![Ti 2p spectrum of TiO$_2$ as a native KherveSheet chart built over MCP.
The fit was computed in `=PY` cells: a Voigt spin–orbit doublet (red, blue)
and the Ti$^{4+}$ charge-transfer satellite over an active Shirley background.
Arrows mark the spin–orbit splitting and the satellite offset.\label{fig:ti2p}](../figures/tio2_ti2p_chart.png)

The fit gives the Ti 2p$_{3/2}$ line at 458.10 eV with an FWHM of 1.07 eV,
a spin–orbit splitting of 5.705 ± 0.005 eV, and a satellite 13.6 eV above
the main line. These values agree with the established Ti$^{4+}$ signature of
TiO$_2$ [@biesinger2010]. As a cross-check, we compared the same spectrum
fitted independently in KherveFitting. Both programs give the same 2p$_{3/2}$
FWHM (1.07 eV) and splitting (5.70 eV), and their 2p$_{3/2}$ areas differ by
1.3%. The 0.14 eV difference in position comes from the charge correction
applied in the KherveFitting file and is not a difference between the fits.

### Monte Carlo uncertainties

Standard errors from the covariance matrix assume the model is exact. With a
reduced $\chi^2$ of 20 here, that assumption clearly fails. The `=PY` cell in
T1 therefore estimates the counting-statistics contribution directly: it
generates 300 Poisson realisations of the fitted spectrum and refits each one
from the same starting point (\autoref{tab:mc}). The client then built a
native histogram of the 300 area ratios with one `insert_chart` call
(\autoref{fig:mc}).

: Monte Carlo (N = 300, Poisson noise) versus covariance standard deviations.\label{tab:mc}

| Parameter               | Fit value | MC std  | Covariance std |
|:------------------------|----------:|--------:|---------------:|
| Ti 2p$_{3/2}$ position (eV) | 458.098 | < 0.001 | 0.001 |
| Ti 2p$_{3/2}$ FWHM (eV)     | 1.073   | 0.002   | —     |
| Spin–orbit splitting (eV)   | 5.705   | 0.002   | 0.005 |
| Area ratio 2p$_{1/2}$/2p$_{3/2}$ | 0.466 | 0.003 | 0.014 |
| Ti 2p$_{3/2}$ area (cps eV) | 267 793 | 290     | 1 071 |
| Satellite offset (eV)       | 13.556  | 0.005   | —     |

![Distribution of the Ti 2p area ratio over 300 Monte Carlo refits, as a
native KherveSheet histogram over the T-column refits.\label{fig:mc}](../figures/tio2_mc_ratio.png){ width=70% }

The Monte Carlo spread is three to five times smaller than the covariance
estimate. On data with this many counts, Poisson noise is therefore not the
limiting factor. The uncertainty in quantities such as the area ratio comes
mainly from the model: background, line shape and the satellite. The
covariance errors, which are scaled by the reduced $\chi^2$, partly reflect
that misfit, and the Monte Carlo errors do not. Because both analyses sit
side by side in the grid as readable code, a reader can see this distinction
directly and test alternative models by editing a single cell.

The script that places these cells, the full log of MCP calls
(`mcp_calls.jsonl`) and the resulting workbook are in the repository under
`paper/demo/`. Re-running the script rebuilds the workbook and the figure.

# AI usage disclosure

Generative AI was used in this work. Claude (Anthropic; Claude Opus and
Sonnet models, through Claude Code, 2025–2026) assisted with writing parts of
the KherveSheet source code, tests and documentation, and with drafting and
editing this manuscript. In the worked example, Claude also drove the MCP
session that placed the `=PY` cells. The author designed the software and its
architecture, made all core design decisions, chose the scientific analysis
and models, and reviewed, tested and validated all AI-assisted code, results
and text, and takes full responsibility for them.

# Acknowledgements

We thank the users of the Kherve tools at Imperial College London for
feedback.

# References
