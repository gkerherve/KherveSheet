# KherveSheet — notes for Claude

KherveSheet is an Excel-inspired spreadsheet workbench built on PyQt5 +
matplotlib. The goal is to mirror the look and workflow of Microsoft
Excel without literally copying their code, icons, or branded assets,
while reusing KhervePlot's plotting engine for embedded charts.

## Build / run

- Python 3.12 / 3.13 with PyQt5 + matplotlib + numpy.
- Run via `python KherveSheet.py` or `python -m khervesheet`.
- Optional libs: openpyxl (Excel import/export).
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
  - `graph.py`      — `EmbeddedChart` (matplotlib chart embedded in grid).
  - `mainwindow.py` — `MainWindow` shell: menus, toolbars, status bar.
  - `mainwindow_io.py` — `IOMixin`: CSV / Excel import/export.
  - `mainwindow_columns.py` — `ColumnsMixin`: column operations.
  - `mainwindow_analysis.py` — `AnalysisMixin`: basic analysis ops.
  - `formula_engine.py` — cell formula parser & evaluator.
  - `undo_commands.py` — QUndoCommand classes.
  - `icons.py`      — icon factory.
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
  Date, Time, Text.
- **Window style**: Fusion as default.

## Commit / push policy

**Every change must land as a commit on the `dev` branch and be pushed
immediately.** No batching. No exceptions. No `Co-Authored-By:` trailer.

Commit subjects under 70 chars; body explains *why*, not what.

## Licensing

GPL-3.0. New source files must carry the short GPL notice at the top.
