"""Tool schemas for the document and analysis tools.

Split out from ``ai_backend.TOOLS`` so neither file grows past the
project's 1500-line ceiling.  Descriptions here are the *only* briefing
an external MCP client's model gets — a host writes its own system
prompt, so anything an agent must know to use a tool correctly has to
live in the schema, not in KherveSheet's chat prompt.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

_SHEET = {"type": "string", "description": "Name of the sheet tab."}


EXTRA_TOOLS = [
    # ── Document ───────────────────────────────────────────────────
    {
        "name": "get_document_info",
        "description": (
            "Report which file the open workbook came from, whether it "
            "has unsaved changes, and whether it can be saved in place. "
            "Call this before save_workbook if you are unsure."
        ),
        "input_schema": {"type": "object", "properties": {},
                         "required": []},
    },
    {
        "name": "save_workbook",
        "description": (
            "Save the open workbook. With no path it overwrites the "
            "current file; that fails for a workbook that has never "
            "been saved, or one imported from Excel (overwriting the "
            "original would corrupt it), so pass an explicit path in "
            "those cases. Format follows the extension: .ksheet keeps "
            "everything (charts, Python cells, formatting), .csv keeps "
            "values only, .xlsx is an export and does not become the "
            "current file."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "Full path ending in .ksheet, .csv or .xlsx. "
                        "Omit to overwrite the current file."),
                },
            },
            "required": [],
        },
    },
    {
        "name": "open_workbook",
        "description": (
            "Open a .ksheet, .csv, .xlsx or .xlsm file, replacing the "
            "workbook currently on screen. Refuses when there are "
            "unsaved changes unless discard_unsaved_changes is true — "
            "save first rather than discarding someone's work. Opening "
            "a .ksheet that contains Python cells asks the user to "
            "confirm, so the call may wait on them."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string",
                         "description": "Full path to the file."},
                "discard_unsaved_changes": {
                    "type": "boolean",
                    "description": (
                        "Throw away unsaved changes in the open "
                        "workbook. Default false."),
                },
            },
            "required": ["path"],
        },
    },
    {
        "name": "new_workbook",
        "description": (
            "Replace the open workbook with an empty one. Refuses when "
            "there are unsaved changes unless discard_unsaved_changes "
            "is true."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "discard_unsaved_changes": {
                    "type": "boolean",
                    "description": (
                        "Throw away unsaved changes. Default false."),
                },
            },
            "required": [],
        },
    },

    # ── Analysis ───────────────────────────────────────────────────
    {
        "name": "run_solver",
        "description": (
            "Excel-style Solver: change the variable cells until the "
            "objective cell is minimised, maximised, or hits a target, "
            "subject to constraints. The objective must be a formula "
            "cell that depends on the variable cells. Writes the "
            "solution into the sheet (undoable) and reports the "
            "objective value it reached."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sheet_name": _SHEET,
                "objective_cell": {
                    "type": "string",
                    "description": "Cell to optimise, e.g. 'D5'.",
                },
                "variable_cells": {
                    "type": "string",
                    "description": (
                        "Cells the solver may change — a range, or "
                        "several comma-separated ranges, "
                        "e.g. 'B2:B4,D2'."),
                },
                "goal": {
                    "type": "string",
                    "enum": ["min", "max", "value"],
                    "description": "Default 'min'.",
                },
                "target_value": {
                    "type": "number",
                    "description": "Required when goal is 'value'.",
                },
                "constraints": {
                    "type": "array",
                    "description": (
                        "Limits the solution must respect, each on a "
                        "cell that the variables affect."),
                    "items": {
                        "type": "object",
                        "properties": {
                            "cell": {"type": "string"},
                            "op": {"type": "string",
                                   "enum": ["<=", ">=", "="]},
                            "value": {"type": "string"},
                        },
                        "required": ["cell", "op", "value"],
                    },
                },
                "method": {
                    "type": "string",
                    "enum": ["GRG Nonlinear", "LP Simplex",
                             "Evolutionary"],
                    "description": (
                        "Default 'GRG Nonlinear' — smooth problems. "
                        "'Evolutionary' for non-smooth ones."),
                },
                "non_negative": {
                    "type": "boolean",
                    "description": (
                        "Constrain every variable to >= 0. "
                        "Default false."),
                },
            },
            "required": ["sheet_name", "objective_cell",
                         "variable_cells"],
        },
    },
    {
        "name": "fit_trendline",
        "description": (
            "Fit a curve to two columns and report the fitted "
            "parameters with goodness-of-fit (R², adjusted R², RMSE, "
            "reduced chi-squared, AIC, BIC). 23 models are available — "
            "call list_fit_models for the names. Optionally writes the "
            "fitted y values into the sheet. Use this for regression "
            "over a whole series; use fit_peaks for spectra with "
            "overlapping peaks."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sheet_name": _SHEET,
                "x_range": {"type": "string",
                            "description": "Range holding x, e.g. 'A2:A80'."},
                "y_range": {"type": "string",
                            "description": "Range holding y, same length."},
                "model": {
                    "type": "string",
                    "description": (
                        "Model name, e.g. 'Linear', 'Exponential "
                        "Decay', 'Logistic (Sigmoid)', 'Polynomial'. "
                        "Default 'Linear'."),
                },
                "poly_order": {
                    "type": "integer",
                    "description": "Order when model is 'Polynomial'.",
                },
                "ma_period": {
                    "type": "integer",
                    "description": (
                        "Window when model is 'Moving Average'."),
                },
                "output_cell": {
                    "type": "string",
                    "description": (
                        "Top-left cell for a written column of fitted "
                        "y values (a header goes in this cell). Omit "
                        "to only report the numbers."),
                },
            },
            "required": ["sheet_name", "x_range", "y_range"],
        },
    },
    {
        "name": "fit_peaks",
        "description": (
            "lmfit peak fitting for spectra: fit a sum of peak shapes "
            "(Gaussian, Lorentzian, Voigt, Doniach-Sunjic, …) over a "
            "background (Shirley, ALS, polynomial). Reports every "
            "fitted parameter with its uncertainty plus chi-squared / "
            "AIC / BIC, and can write x, data, background, each "
            "component, the total fit and the residual into the sheet "
            "as columns. Call list_fit_models for the shape and "
            "background names."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sheet_name": _SHEET,
                "x_range": {"type": "string",
                            "description": "Range holding x."},
                "y_range": {"type": "string",
                            "description": "Range holding y, same length."},
                "peaks": {
                    "type": "array",
                    "description": (
                        "One entry per peak. Either a shape name, or "
                        "an object with 'model' plus starting values "
                        "for its parameters (e.g. "
                        "{'model': 'Gaussian', 'center': 285.0}). "
                        "Seeding centres matters for overlapping "
                        "peaks."),
                    "items": {"type": ["string", "object"]},
                },
                "background": {
                    "type": "string",
                    "description": (
                        "Background name, e.g. 'None', 'Linear', "
                        "'Shirley (XPS)', 'Asymmetric Least Squares'. "
                        "Default 'None'."),
                },
                "output_cell": {
                    "type": "string",
                    "description": (
                        "Top-left cell for the written result "
                        "columns. Omit to only report the fit."),
                },
            },
            "required": ["sheet_name", "x_range", "y_range", "peaks"],
        },
    },
    {
        "name": "list_fit_models",
        "description": (
            "List the curve models available to fit_trendline and the "
            "peak shapes and backgrounds available to fit_peaks, with "
            "their formulas. Call this before guessing a model name."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "kind": {
                    "type": "string",
                    "enum": ["all", "trendline", "peak"],
                    "description": "Default 'all'.",
                },
            },
            "required": [],
        },
    },
]
