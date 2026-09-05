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
  - `solver.py`     — `SolverDialog` (Excel-style optimisation: min/max/target via scipy);
    `solve_headless()` runs the same dialog with no window for scripted/MCP callers.
  - `trendline.py`  — `TrendlineDialog` (curve fitting: 23+ models via scipy, goodness-of-fit report);
    `fit_series()` is the Qt-free fit behind both the dialog and the tool layer.
  - `fit_models.py` — `FitFunction` registry wrapping every built-in lmfit model plus a custom-function builder (compiles an expression in `x` into an lmfit model); linear/poly/Shirley/Tougaard backgrounds.
  - `fitting.py`    — `FittingDialog` (KherveFitting-style lmfit peak fitting: add any lmfit/custom function, per-peak parameter editor with value/min/max/vary, pick background, live plot + fit report, write components back to sheet).
  - `icons.py`      — qtawesome icon factory (themed MDI + custom QPainter plot glyphs).
  - `updater.py`    — silent auto-updater: polls the `Kherve-Downloads`
    releases API (tag prefix `khervesheet-v`), downloads and checksums the
    Inno installer in the background, prompts to restart, hands over to a
    detached batch helper. Windows + frozen builds only.
  - `git_backend.py` — per-document Git repo: auto-commit, push, pull, history, branches (pygit2).
  - `history_dialog.py` — `HistoryDialog` commit browser with DAG graph, diff view, restore.
  - `mcp_server.py`  — stdio MCP server an external host (Claude Desktop,
    Claude Code, Cursor, Zed) launches. Pure stdlib, no Qt: it forwards
    JSON-RPC `tools/call` over a loopback socket. Also reachable as
    `KherveSheet.exe --mcp-server`.
  - `mcp_bridge.py`  — `McpBridge`, the in-app half: a token-authenticated
    127.0.0.1 listener that runs `AiToolExecutor` tools on the GUI thread,
    one undo macro per mutating call.
  - `mcp_dialog.py`  — `McpServerDialog` (enable the bridge, choose the
    access level, connect a host). See `docs/MCP.md`.
  - `mcp_hosts.py`   — Qt-free config-file writer: detects Claude
    Desktop / Claude Code / Cursor / Windsurf / Zed and merges
    KherveSheet's entry in, with a backup and an atomic replace.
  - `ai_charts.py`   — chart tools for both tables: `insert_chart`,
    `modify_chart`, `style_chart`, with their schemas next to the code
    that runs them (series styling, fills, legend, fonts, presets).
  - `ai_charts_extra.py` — the rest of the chart system as tools:
    `add_chart_series`, `remove_chart_series`, `add_trendline`,
    `configure_axis`, `annotate_chart`, `export_chart`.
  - `ai_tools_extra.py` — document I/O (open/save/new) and analysis
    (`run_solver`, `fit_trendline`, `fit_peaks`) tools, registered into
    `AiToolExecutor` at construction.
  - `ai_tools_schema.py` — `EXTRA_TOOLS`, the input schemas for those.
    An MCP host writes its own system prompt, so anything an agent must
    know belongs in these descriptions.
  - `peakfit.py`     — Qt-free lmfit peak-fitting core shared by
    `FittingDialog` and the tool layer.
- `requirements.txt`, `LICENSE` (GPL-3.0).
- Packaging — one PyInstaller spec, two platform tails:
  - `KherveSheet.spec` — shared Analysis; branches on `sys.platform` for
    the icon (.ico/.icns), UPX (off on macOS — it breaks Mach-O) and a
    `BUNDLE()` step that produces `KherveSheet.app`.
  - `tools/generate_icon.py` — renders the app mark into a multi-res
    `.ico` or `.icns`; the format follows the output extension.
  - `KherveSheet_setup.iss` — Windows Inno Setup installer.
  - `tools/make_dmg.sh` + `.github/workflows/macos-build.yml` — macOS
    DMG, built on GitHub runners (arm64 + x86_64). Ad-hoc signed only,
    not notarized; see `README.macos.md`.

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

## Tool layer (AI chat + MCP)

The tools in `ai_tools.py` / `ai_tools_extra.py` are reachable two
ways: the built-in chat (which supplies a system prompt) and any MCP
client (which does not — the host writes its own). **Any constraint
that matters must therefore be enforced in the executor or stated in
the tool's schema description, never only in the chat prompt.**

Two tables, one executor:

- `ai_backend.TOOLS` — what the chat is offered (the grid, charts,
  formatting, the function catalogue).
- `ai_backend.MCP_TOOLS` — `TOOLS + EXTRA_TOOLS`, what an MCP client is
  offered. The extras (document I/O, Solver, fitting) are withheld from
  the chat on purpose: in the window those are menu items the user
  drives, while an MCP client has no menus.

`AiToolExecutor` dispatches every name in either table, so a new tool
only has to be added to the right schema list.

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
