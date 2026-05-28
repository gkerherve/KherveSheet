# KherveSheet — notes for Claude

KherveSheet is an Excel-inspired spreadsheet workbench built on PyQt5 +
matplotlib. The goal is to mirror the look and workflow of Microsoft
Excel without literally copying their code, icons, or branded assets,
while reusing KhervePlot's plotting engine for embedded charts.

## Build / run

- Python 3.12 / 3.13 with PyQt5 + matplotlib + numpy.
- Run via `python KherveSheet.py` or `python -m khervesheet`.
- Optional libs: openpyxl (Excel import/export), h5py (native .ksheet format).
- Crash log: `%TEMP%/khervesheet_crash.log`.
- **Version string** is derived at runtime in `_version.py` from
  `git rev-list --count HEAD` and `git rev-parse --short HEAD`,
  cached with `lru_cache`. Falls back to `_FALLBACK = "0.1.0"`
  outside a git checkout. Title bar reads `KherveSheet v0.1.N+sha`.

## File size policy

Every module in `khervesheet/` should stay near **1500 lines**. If a
change would push a file meaningfully past that, split the new code
into a new module and import.

## Project layout

- `KherveSheet.py` — entry script.
- `khervesheet/` — package; `python -m khervesheet` is the alternative entry.
  - `__init__.py`   — constants, version import.
  - `__main__.py`   — module entry point.
  - `_version.py`   — git-based version string.
  - `app.py`        — `main()`, app icon, crash log, QSS styling.
  - `sheet.py`      — `SheetWidget` (single grid tab with formula bar).
  - `workbook.py`   — `WorkbookWidget` (QTabWidget managing sheets).
  - `graph.py`      — `EmbeddedChart` (matplotlib chart overlaid on grid viewport).
  - `axis_dialog.py` — `AxisPropertiesDialog` (per-axis config: scale, title, ticks, grids).
  - `cellformat.py`  — `CellFormat`, `BorderSpec`, `CellFormatDelegate` (fill + borders).
  - `format_dialog.py` — `FormatCellsDialog` (Excel-style multi-tab cell formatting dialog).
  - `mainwindow.py` — `MainWindow` shell: menus, toolbars, status bar, I/O (CSV/Excel/HDF5).
  - `formula_engine.py` — cell formula parser & evaluator.
  - `undo_commands.py` — QUndoCommand classes.
  - `insert_ops.py`  — Insert menu ops: checkbox, dropdown, link, comment/note, emoji, transpose, spell-check.
  - `solver.py`     — `SolverDialog` (Excel-style optimisation: min/max/target via scipy).
  - `trendline.py`  — `TrendlineDialog` (curve fitting: 23+ models via scipy, goodness-of-fit report).
  - `icons.py`      — qtawesome icon factory (themed MDI + custom QPainter plot glyphs).
  - `git_backend.py` — per-document Git repo: auto-commit, push, pull, history, branches (pygit2).
  - `history_dialog.py` — `HistoryDialog` commit browser with DAG graph, diff view, restore.
- `requirements.txt`, `LICENSE` (GPL-3.0).

## UI conventions

- **Excel-style grid**: columns A, B, C, ... Z, AA, AB...; rows 1-based.
- **No meta rows** (unlike KhervePlot). Column headers are letters only.
- **Formula bar at top**: `[Cell ref] [=] [formula input]`.
- **Fill handle**: cross at bottom-right of selection for drag-fill.
- **Bottom sheet tabs**: Sheet1, Sheet2, Sheet3 — renameable by double-click.
- **Embedded charts**: movable/resizable matplotlib plots overlaid on grid.
- **Single chart layer** (unlike KhervePlot's multi-layer system).
- **Number formats**: General, Number (0.0 through 0.0000), Scientific,
  Percentage, Currency, Date, Time, Text.
- **Window style**: Fusion as default.

## Undo / redo policy

**Every user-visible change must be undoable.** Cell edits, formatting
changes (fill, font, borders, alignment, number format), paste, clear,
and drag-fill all push `QUndoCommand` instances onto the shared undo
stack.  When adding a new action that modifies cell content or
formatting, always create or reuse an undo command for it.

## Persistence policy

**All cell and chart properties must be saved and restored.** Every
field on `CellFormat` (font, fill, borders, alignment, number format,
wrap text) and every chart axis property must round-trip through the
`.ksheet` (HDF5) format.  When adding a new property, update both
`to_dict()`/`from_dict()` in the data class and the save/load code in
`mainwindow.py`.

## Commit / push policy

**Every change must land as a commit on the `dev` branch and be pushed
immediately.** No batching. No exceptions. No `Co-Authored-By:` trailer.

Commit subjects under 70 chars; body explains *why*, not what.

**Commit message prefix** — every subject line must start with one of:

- `fix:` — bug fix
- `feat:` — new feature or option
- `refactor:` — code restructuring, no behavior change
- `style:` — formatting, UI tweaks
- `docs:` — documentation only
- `perf:` — performance improvement

## Licensing

GPL-3.0. New source files must carry the short GPL notice at the top.
