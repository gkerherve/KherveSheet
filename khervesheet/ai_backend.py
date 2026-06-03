"""AI backend — Claude API client, tool definitions, and threading.

Manages the conversation with Claude using tool-use.  The API call
runs on a background QThread while tool execution happens on the
main (GUI) thread so that Qt widgets are always accessed safely.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from PyQt5.QtCore import (
    Qt, QObject, QThread, QMutex, QWaitCondition, pyqtSignal, pyqtSlot,
)
from PyQt5.QtWidgets import QApplication

# ── Optional dependency guard ──────────────────────────────────────
try:
    import anthropic
    HAVE_ANTHROPIC = True
except ImportError:
    anthropic = None
    HAVE_ANTHROPIC = False


# ── Tool definitions ───────────────────────────────────────────────

TOOLS = [
    {
        "name": "get_sheet_info",
        "description": (
            "List all sheets in the workbook with their dimensions "
            "(row and column counts)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "read_cells",
        "description": (
            "Read cell values from a rectangular range in a sheet. "
            "Returns a 2D list of string values."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sheet_name": {
                    "type": "string",
                    "description": "Name of the sheet tab.",
                },
                "range": {
                    "type": "string",
                    "description": (
                        "A1-notation range, e.g. 'A1:C10' or 'B3' "
                        "for a single cell."
                    ),
                },
            },
            "required": ["sheet_name", "range"],
        },
    },
    {
        "name": "write_cells",
        "description": (
            "Write values to a rectangular range.  The values array is "
            "row-major: [[row1_values], [row2_values], ...]. "
            "Use '=FORMULA' syntax for formulas."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sheet_name": {
                    "type": "string",
                    "description": "Name of the sheet tab.",
                },
                "range": {
                    "type": "string",
                    "description": (
                        "Top-left cell of the write area, e.g. 'A1'. "
                        "The range expands to fit the values array."
                    ),
                },
                "values": {
                    "type": "array",
                    "items": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "description": (
                        "2D array of cell values (strings). "
                        "Use '=SUM(A1:A5)' syntax for formulas."
                    ),
                },
            },
            "required": ["sheet_name", "range", "values"],
        },
    },
    {
        "name": "set_formula",
        "description": (
            "Set a formula in a single cell. "
            "The formula must start with '='."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sheet_name": {
                    "type": "string",
                    "description": "Name of the sheet tab.",
                },
                "cell": {
                    "type": "string",
                    "description": "Cell reference, e.g. 'B5'.",
                },
                "formula": {
                    "type": "string",
                    "description": (
                        "Formula string starting with '=', "
                        "e.g. '=SUM(A1:A10)'."
                    ),
                },
            },
            "required": ["sheet_name", "cell", "formula"],
        },
    },
    {
        "name": "format_cells",
        "description": "Apply visual formatting to a range of cells.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sheet_name": {
                    "type": "string",
                    "description": "Name of the sheet tab.",
                },
                "range": {
                    "type": "string",
                    "description": "A1-notation range, e.g. 'A1:C5'.",
                },
                "format_props": {
                    "type": "object",
                    "description": "Formatting properties to apply.",
                    "properties": {
                        "bg_color": {
                            "type": "string",
                            "description": (
                                "Background colour as hex, "
                                "e.g. '#FFD700'."
                            ),
                        },
                        "font_color": {
                            "type": "string",
                            "description": "Font colour as hex.",
                        },
                        "bold": {"type": "boolean"},
                        "italic": {"type": "boolean"},
                        "underline": {"type": "boolean"},
                        "font_family": {"type": "string"},
                        "font_size": {"type": "number"},
                        "alignment": {
                            "type": "string",
                            "enum": ["left", "center", "right"],
                        },
                        "number_format": {
                            "type": "string",
                            "enum": [
                                "General", "0", "0.0", "0.00",
                                "0.000", "0.0000", "Scientific",
                                "Percentage", "Currency", "Date",
                                "Time", "Text",
                            ],
                        },
                    },
                },
            },
            "required": ["sheet_name", "range", "format_props"],
        },
    },
    {
        "name": "insert_chart",
        "description": "Create an embedded chart from data in the sheet.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sheet_name": {
                    "type": "string",
                    "description": "Sheet containing the data.",
                },
                "chart_type": {
                    "type": "string",
                    "enum": [
                        "Line", "Scatter", "Line+Symbol", "Bar",
                        "Step", "Stem", "Histogram", "Box",
                        "Heatmap", "3D Surface",
                    ],
                },
                "x_range": {
                    "type": "string",
                    "description": (
                        "A1-notation range for X data, "
                        "e.g. 'A2:A20'."
                    ),
                },
                "y_range": {
                    "type": "string",
                    "description": (
                        "A1-notation range for Y data, "
                        "e.g. 'B2:B20'."
                    ),
                },
            },
            "required": [
                "sheet_name", "chart_type", "x_range", "y_range",
            ],
        },
    },
    {
        "name": "add_sheet",
        "description": "Add a new sheet tab to the workbook.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name for the new sheet tab.",
                },
            },
            "required": ["name"],
        },
    },
    {
        "name": "read_selection",
        "description": (
            "Read the user's current cell selection "
            "(active sheet, range, and values)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "search_functions",
        "description": (
            "Search KherveSheet's capability catalogue for spreadsheet "
            "formula functions and science/analysis features. Use this "
            "BEFORE telling the user a function does or doesn't exist, or "
            "when you need the exact name/signature of a function (e.g. "
            "FFT, smoothing, peak fitting, baseline, integration). Returns "
            "lightweight matches; follow up with get_function_details for "
            "full syntax."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Search text matched against function names and "
                        "descriptions, e.g. 'fft', 'smooth', 'gaussian', "
                        "'baseline', 'lookup'."
                    ),
                },
                "category": {
                    "type": "string",
                    "description": (
                        "Optional category filter, e.g. 'Statistical', "
                        "'Science', 'Data Analysis', 'Analysis', 'Charts'."
                    ),
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results (default 25).",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_function_details",
        "description": (
            "Get full details (signature, description, how to access) for "
            "specific functions or features by exact name."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Exact names to look up, e.g. "
                        "['SAVGOL', 'FFT.MAG', 'Curve Fitting']."
                    ),
                },
            },
            "required": ["names"],
        },
    },
    {
        "name": "list_charts",
        "description": (
            "List the embedded charts on a sheet with each series' style "
            "and which columns (X and Y) feed it. Use this to understand "
            "an existing plot before recreating or modifying it."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sheet_name": {"type": "string"},
            },
            "required": ["sheet_name"],
        },
    },
    {
        "name": "get_chart_details",
        "description": (
            "Get the full spec of one chart on a sheet: title, axis labels, "
            "scales, and every series' plot type, X/Y columns, colour, line "
            "style, and markers."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sheet_name": {"type": "string"},
                "chart_index": {
                    "type": "integer",
                    "description": "0-based index (see list_charts).",
                },
            },
            "required": ["sheet_name", "chart_index"],
        },
    },
    {
        "name": "clone_chart",
        "description": (
            "Recreate a chart from one sheet onto another (or the same) "
            "sheet, preserving its exact style — colours, line styles, "
            "markers, axis labels — and the same column mapping, pulling "
            "live data from the target sheet."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source_sheet": {"type": "string"},
                "chart_index": {
                    "type": "integer",
                    "description": "0-based index on the source sheet.",
                },
                "target_sheet": {
                    "type": "string",
                    "description": (
                        "Sheet to place the clone on. Defaults to the "
                        "source sheet."
                    ),
                },
            },
            "required": ["source_sheet", "chart_index"],
        },
    },
    {
        "name": "modify_chart",
        "description": (
            "Edit an existing chart's axes and labels in place: invert "
            "(reverse) the X or Y axis, set axis scales (linear/log), set "
            "the title or axis labels, or toggle gridlines. Use this when "
            "the user asks to flip/reverse an axis, use a log scale, or "
            "rename a chart's title/axes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sheet_name": {"type": "string"},
                "chart_index": {
                    "type": "integer",
                    "description": "0-based index (see list_charts).",
                },
                "invert_x": {
                    "type": "boolean",
                    "description": "True reverses the X axis (high→low).",
                },
                "invert_y": {
                    "type": "boolean",
                    "description": "True reverses the Y axis.",
                },
                "x_scale": {
                    "type": "string",
                    "enum": ["linear", "log", "symlog", "logit"],
                },
                "y_scale": {
                    "type": "string",
                    "enum": ["linear", "log", "symlog", "logit"],
                },
                "title": {"type": "string"},
                "x_label": {"type": "string"},
                "y_label": {"type": "string"},
                "grid": {"type": "boolean"},
            },
            "required": ["sheet_name", "chart_index"],
        },
    },
]


# ── System prompt builder ──────────────────────────────────────────

def build_system_prompt(mainwindow) -> str:
    """Build the system prompt with live workbook context."""
    wb = mainwindow._workbook
    sheet_lines = []
    for s in wb.all_sheets():
        name = wb.name_of_sheet(s)
        sheet_lines.append(
            f"  - {name}: {s.row_count()} rows × {s.column_count()} cols")
    sheets_info = "\n".join(sheet_lines) or "  (none)"
    active = mainwindow._active_sheet()
    active_name = wb.name_of_sheet(active) if active else "(none)"
    # Current selection.
    sel_str = "(none)"
    if active:
        sel = active.table.selectedRanges()
        if sel:
            from .sheet import col_index_to_letter
            s = sel[0]
            tl = (f"{col_index_to_letter(s.leftColumn())}"
                  f"{s.topRow() + 1}")
            br = (f"{col_index_to_letter(s.rightColumn())}"
                  f"{s.bottomRow() + 1}")
            sel_str = tl if tl == br else f"{tl}:{br}"
    return f"""\
You are a helpful AI assistant embedded in KherveSheet, a scientific \
spreadsheet application.  You can directly manipulate the spreadsheet \
using the tools provided.

Current workbook state:
- Sheets:
{sheets_info}
- Active sheet: {active_name}
- Current selection: {sel_str}

Guidelines:
- Do NOT redo work already completed earlier in this conversation. \
Only make the specific change the user just asked for, and leave \
existing data, formatting, and charts untouched unless asked.
- If you are unsure of the current contents of a cell or range \
(for example at the start of a new conversation), use read_cells to \
check before writing — do not blindly recreate data.
- Use set_formula for calculated cells (formulas start with =).
- Always read_cells first if you need to understand existing data \
before modifying.
- TEMPLATES MUST BE POLISHED, matching KherveSheet's shipped example \
workbooks — never a bare grid of numbers. When you build a template:
  1. Put a bold, larger title in row 1 (e.g. A1, font_size ~14, bold).
  2. Make a proper header row: bold white text (font_color "#FFFFFF") \
on a coloured fill (bg_color e.g. "#4472C4"), centered, and ALWAYS \
include units in the header text, e.g. "Retention Time (min)".
  3. Fill 10-20 rows of realistic example data with write_cells.
  4. Add calculated columns using set_formula with CORRECT cell \
references — every argument that should be a cell must be a real \
reference (e.g. E2), never a literal like "W0.05" or a column letter \
with a value glued on.
  5. Apply number formats to numeric columns via format_cells \
(number_format), and light borders/zebra fills for readability.
  6. Create chart(s) with insert_chart, then use modify_chart to give \
each a descriptive title and x_label/y_label (with units).
  7. Optionally add a short note explaining how to use the template.
- After writing formulas, READ BACK the calculated cells with \
read_cells; if any show #ERROR, #N/A or look wrong, diagnose and fix \
the formula before telling the user you are done. A template with \
#ERROR cells is not acceptable.
- Look up exact function names and syntax with search_functions / \
get_function_details when unsure — do not guess formula syntax.
- KherveSheet has 150+ formula functions and many science/analysis \
features (FFT, smoothing, peak fitting, baselines, solver, trendlines, \
etc.). You do NOT know them all from memory — use search_functions to \
look them up on demand, then get_function_details for exact syntax. \
Do this before claiming a capability is missing.
- To copy or understand an existing plot, use list_charts and \
get_chart_details to see each series' style and X/Y columns, and \
clone_chart to reproduce a chart (with identical style) on another sheet.
- To change an existing chart's axes — reverse/invert an axis, switch \
to a log scale, or rename the title/axis labels — use modify_chart. \
Reversing the X axis is invert_x=true.
- Available chart types: Line, Scatter, Line+Symbol, Bar, Step, Stem, \
Histogram, Box, Heatmap, 3D Surface.
- format_cells accepts: bg_color (hex), bold, italic, underline, \
font_family, font_size, font_color (hex), alignment \
("left"/"center"/"right"), number_format ("General"/"0.00"/ \
"Scientific"/"Percentage"/"Currency"/"Date"/"Time"/"Text").
- Cell references use A1 notation.  Ranges use A1:C5 format.
- Row numbers are 1-based, columns are letters (A, B, … Z, AA, AB, …).
- All your changes are undoable (Ctrl+Z).
- Be concise in your replies.  Focus on actions, not explanations."""


# ── Sliding-window conversation management ─────────────────────────

_MAX_TURNS = 60  # keep at most this many neutral-history turns


def _trim_messages(messages: List[dict]) -> List[dict]:
    """Keep only the last *_MAX_TURNS* neutral-history turns.

    After truncating, drop any leading turns that are not a plain user
    turn so the history never starts mid-exchange (a dangling
    tool_results or assistant turn would be rejected by the APIs).
    """
    if len(messages) > _MAX_TURNS:
        messages = messages[-_MAX_TURNS:]
    while messages and messages[0].get("role") != "user":
        messages = messages[1:]
    return messages


# ── Worker (runs on QThread) ───────────────────────────────────────

class AiWorker(QObject):
    """Drives a provider's agentic loop on a background thread.

    Signals are used for all communication with the main thread:
    - *chunk_ready*: incremental assistant text.
    - *tool_call*: emitted when the model wants to call a tool;
      the worker then **blocks** on a QWaitCondition until the main
      thread posts the result via *post_tool_result()*.
    - *turn_done*: all tool calls resolved, carries the updated history.
    - *error*: something went wrong.
    """

    chunk_ready = pyqtSignal(str)        # partial text
    tool_call = pyqtSignal(str, str)     # name, input_json
    turn_done = pyqtSignal(list)         # updated neutral history
    error = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._cancel = False
        # Mutex + condition for blocking while main thread runs a tool.
        self._tool_mutex = QMutex()
        self._tool_cond = QWaitCondition()
        self._tool_result: Optional[str] = None  # JSON string

    # Called from main thread to wake the worker after tool execution.
    def post_tool_result(self, result_json: str):
        self._tool_mutex.lock()
        self._tool_result = result_json
        self._tool_cond.wakeAll()
        self._tool_mutex.unlock()

    def cancel(self):
        self._cancel = True

    def _invoke_tool(self, name: str, input_dict: dict) -> dict:
        """Emit a tool-call request and block until the main thread
        posts the result."""
        self.tool_call.emit(name, json.dumps(input_dict))
        self._tool_mutex.lock()
        self._tool_result = None
        self._tool_cond.wait(self._tool_mutex)
        result_json = self._tool_result or '{"error":"cancelled"}'
        self._tool_mutex.unlock()
        try:
            return json.loads(result_json)
        except Exception:
            return {"error": "malformed tool result"}

    @pyqtSlot(str, str, str, str, str, list)
    def run_turn(self, provider_name: str, api_key: str, model: str,
                 host: str, system_prompt: str, history: list):
        """Run the full agentic turn (may loop over tool calls)."""
        self._cancel = False
        from .ai_providers import make_provider
        provider = make_provider(provider_name, {
            "api_key": api_key,
            "model": model,
            "host": host,
        })
        try:
            provider.run_turn(
                system_prompt,
                TOOLS,
                history,
                emit_text=self.chunk_ready.emit,
                run_tool=self._invoke_tool,
                cancelled=lambda: self._cancel,
            )
            self.turn_done.emit(history)
        except Exception as exc:
            self.error.emit(provider.humanize(exc))


# ── Backend coordinator (lives on main thread) ─────────────────────

class AiBackend(QObject):
    """Coordinates between the chat UI and the AiWorker thread.

    Public API (called from the chat dock on the main thread):
    - ``send(text)`` — start a new user turn.
    - ``cancel()`` — abort the current turn.
    """

    # Forwarded from worker to UI.
    chunk_ready = pyqtSignal(str)
    tool_performed = pyqtSignal(str, str)  # tool_name, summary
    turn_done = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, mainwindow):
        super().__init__(mainwindow)
        self._mw = mainwindow
        self._messages: List[dict] = []
        self._macro_open = False

        # Tool executor.
        from .ai_tools import AiToolExecutor
        self._executor = AiToolExecutor(mainwindow)

        # Worker + thread.
        self._thread = QThread(self)
        self._worker = AiWorker()
        self._worker.moveToThread(self._thread)
        # Connect worker signals.
        self._worker.chunk_ready.connect(self.chunk_ready)
        self._worker.tool_call.connect(self._on_tool_call)
        self._worker.turn_done.connect(self._on_turn_done)
        self._worker.error.connect(self._on_error)
        self._thread.start()

    def send(self, text: str, images: list = None):
        """Initiate a new user turn, optionally with pasted images."""
        from PyQt5.QtCore import QSettings
        from .ai_providers import PROVIDERS, DEFAULT_HOST
        settings = QSettings("KherveSheet", "KherveSheet")
        provider = settings.value("ai/provider", "anthropic")
        if provider not in PROVIDERS:
            provider = "anthropic"
        spec = PROVIDERS[provider]
        model = settings.value(
            f"ai/model_{provider}", spec["default_model"])
        api_key = settings.value(f"ai/key_{provider}", "")
        host = settings.value(
            "ai/ollama_host", spec.get("default_host", DEFAULT_HOST))
        if spec["needs_key"] and not api_key:
            self.error.emit(
                f"No API key configured for {spec['label']}. "
                "Click the gear icon to set one.")
            return
        user_turn = {"role": "user", "text": text}
        if images:
            user_turn["images"] = images
        self._messages.append(user_turn)
        self._messages = _trim_messages(self._messages)
        system = build_system_prompt(self._mw)
        # Invoke worker on its thread (queued connection).
        from PyQt5.QtCore import QMetaObject, Q_ARG
        QMetaObject.invokeMethod(
            self._worker, "run_turn",
            Qt.QueuedConnection,
            Q_ARG(str, provider),
            Q_ARG(str, api_key),
            Q_ARG(str, model),
            Q_ARG(str, host),
            Q_ARG(str, system),
            Q_ARG(list, list(self._messages)),
        )

    def cancel(self):
        self._worker.cancel()

    # ── Slots ───────────────────────────────────────────────────

    @pyqtSlot(str, str)
    def _on_tool_call(self, name: str, input_json: str):
        """Execute a tool on the main thread, then wake the worker."""
        inp = json.loads(input_json)
        # Open undo macro on first tool call of the turn.
        if not self._macro_open:
            self._mw._undo_stack.beginMacro("AI Assistant")
            self._macro_open = True
        result = self._executor.execute(name, inp)
        # Build a short summary for the UI.
        summary = self._summarise(name, inp, result)
        self.tool_performed.emit(name, summary)
        result_json = json.dumps(result)
        self._worker.post_tool_result(result_json)

    def _on_turn_done(self, history: list):
        # Adopt the history the worker built (assistant + tool turns).
        if history:
            self._messages = list(history)
        if self._macro_open:
            self._mw._undo_stack.endMacro()
            self._macro_open = False
        self.turn_done.emit()

    def _on_error(self, msg: str):
        if self._macro_open:
            self._mw._undo_stack.endMacro()
            self._macro_open = False
        self.error.emit(msg)

    def _summarise(self, name: str, inp: dict, result: dict) -> str:
        """One-line summary of a tool call for the chat UI."""
        if "error" in result:
            return f"Error: {result['error']}"
        if name == "write_cells":
            n = result.get("cells_written", 0)
            return f"Wrote {n} cell{'s' if n != 1 else ''}"
        if name == "set_formula":
            return f"Set {inp.get('cell', '?')} = {inp.get('formula', '?')}"
        if name == "format_cells":
            n = result.get("cells_formatted", 0)
            return f"Formatted {n} cell{'s' if n != 1 else ''}"
        if name == "insert_chart":
            return f"Created {result.get('chart_type', '')} chart"
        if name == "add_sheet":
            return f"Added sheet '{result.get('sheet_name', '')}'"
        if name == "get_sheet_info":
            n = len(result.get("sheets", []))
            return f"Listed {n} sheet{'s' if n != 1 else ''}"
        if name in ("read_cells", "read_selection"):
            return "Read data"
        if name == "search_functions":
            n = result.get("count", 0)
            return f"Searched functions ({n} match{'es' if n != 1 else ''})"
        if name == "get_function_details":
            return "Looked up function details"
        if name == "list_charts":
            n = result.get("count", 0)
            return f"Listed {n} chart{'s' if n != 1 else ''}"
        if name == "get_chart_details":
            return "Read chart details"
        if name == "clone_chart":
            return f"Cloned chart to '{result.get('target_sheet', '')}'"
        if name == "modify_chart":
            keys = ", ".join((result.get("applied") or {}).keys())
            return f"Modified chart ({keys})" if keys else "Modified chart"
        return name

    def shutdown(self):
        """Clean up the worker thread."""
        self._worker.cancel()
        self._thread.quit()
        self._thread.wait(3000)
