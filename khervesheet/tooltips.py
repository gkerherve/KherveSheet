"""Long hover help for every ribbon button, written for people coming
from Microsoft Excel: what the button does, how to use it, and one thing
worth knowing (often how it differs from Excel).

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""
from __future__ import annotations

from html import escape

# ribbon label -> (title, what it does, good to know)
TIPS: dict[str, tuple[str, str, str]] = {
    "file": ("File",
        "New, Open, Save, Save As, recent files, import and export "
        "(Excel, CSV), Print, version control and live sharing.",
        "Excel's File tab. Ctrl+N, Ctrl+O and Ctrl+S work everywhere."),
    # ----- quick access -----
    "Save": ("Save",
        "Saves the workbook. The first time, it asks for a name and a "
        "place; after that it saves over the same file.",
        "The native .ksheet format keeps everything: formulas, formats, "
        "charts, equations, notes and Python cells. Use File ▸ Export "
        "for Excel or CSV."),
    "Undo": ("Undo",
        "Reverses your last change — a typed value, a format, a paste, "
        "a sort. Press again to keep stepping back.",
        "Changes made by Claude or another connected assistant are on "
        "the same undo list, so you can undo those too."),
    "Redo": ("Redo",
        "Puts back the change you just undid.", ""),
    "ChatBox (requires API key)": ("Chat box",
        "Opens or hides a chat panel on the right where an AI assistant "
        "can read and edit this workbook for you.",
        "It needs your own API key. To use the Claude app you already "
        "have instead, see AI ▸ Connect to Claude."),
    "Collapse the Ribbon": ("Collapse the Ribbon",
        "Hides the buttons and keeps only the tab names, giving more "
        "room to the grid. Click any tab to bring them back.",
        "Double-clicking a tab name does the same, as in Excel."),
    # ----- clipboard -----
    "Paste": ("Paste",
        "Puts what you copied into the sheet, starting at the selected "
        "cell. Formulas are adjusted to their new position, as in Excel. "
        "The arrow offers Paste Values and Transpose.",
        "Tables copied from Excel or a web page are split into cells "
        "automatically."),
    "Cut": ("Cut",
        "Removes the selected cells' contents and keeps them on the "
        "clipboard so you can paste them somewhere else.", ""),
    "Copy": ("Copy",
        "Copies the selected cells to the clipboard. Paste them here, in "
        "another sheet, or straight into Excel, Word or an e-mail.", ""),
    "Paste Values": ("Paste Values Only",
        "Pastes the results you copied, not the formulas behind them — "
        "so a pasted =A1*2 arrives as the number it showed.",
        "Use it to freeze numbers so they no longer change when the "
        "original cells change."),
    "Transpose": ("Transpose",
        "Flips the selected block: rows become columns and columns "
        "become rows.", ""),
    # ----- font -----
    "font": ("Font",
        "The typeface of the selected cells. Type a name to jump to it.",
        "Fonts are saved with the workbook; another computer without the "
        "font shows a similar one."),
    "size": ("Font Size",
        "Size of the selected cells' text, in points. Pick a size or type "
        "your own, such as 10.5.", ""),
    "Bold": ("Bold",
        "Makes the selected cells' text bold — handy for headers and "
        "totals. Click again to remove it.", ""),
    "Italic": ("Italic",
        "Slants the selected cells' text, e.g. for units, notes or Latin "
        "names.", ""),
    "Underline": ("Underline",
        "Underlines the selected cells' text.", ""),
    "borders": ("Borders",
        "Draws lines around or inside the selected cells: all borders, "
        "outside only, bottom, thick box and more. Choose No Border to "
        "remove them.",
        "Borders print and export to Excel; the grey gridlines do not."),
    "fill": ("Fill Color",
        "Colours the background of the selected cells. Click the bucket "
        "for the last colour used, or the arrow to pick another.",
        "Choose No Fill to go back to plain white cells."),
    "fcolor": ("Font Color",
        "Colours the text of the selected cells. Click the A for the last "
        "colour used, or the arrow to pick another.", ""),
    # ----- alignment -----
    "Align Left": ("Align Left",
        "Lines the text up against the left edge of its cell.",
        "Like Excel, text aligns left and numbers right until you "
        "choose otherwise."),
    "Align Center": ("Center",
        "Centres the content in its cell — common for column headers.",
        ""),
    "Align Right": ("Align Right",
        "Lines the content up against the right edge of its cell, so "
        "numbers of different lengths line up on their last digit.", ""),
    "Wrap Text": ("Wrap Text",
        "Shows long text on several lines inside the cell instead of "
        "letting it run into the next cells. The row grows to fit.", ""),
    "Merge & Center": ("Merge & Center",
        "Joins the selected cells into one large cell and centres its "
        "content — typically for a title over several columns. Click "
        "again on a merged cell to split it. The arrow has Unmerge.",
        "Only the top-left cell's content is kept when merging."),
    # ----- number -----
    "number": ("Number Format",
        "How numbers in the selected columns are shown: General, a fixed "
        "number of decimals, Scientific, Percentage, Currency, Date, "
        "Time or Text.",
        "Only the display changes — formulas still use the exact value."),
    "Percent Style": ("Percent Style",
        "Shows the numbers as percentages: 0.25 becomes 25%.",
        "Type 0.25, not 25, for 25%."),
    "Scientific": ("Scientific",
        "Shows the numbers in scientific notation, such as 6.02E+23 — "
        "best for very large or very small values.", ""),
    "Increase Decimal": ("Increase Decimal",
        "Shows one more digit after the decimal point (up to four).",
        "The stored value never changes, only how many digits are "
        "shown."),
    "Decrease Decimal": ("Decrease Decimal",
        "Shows one fewer digit after the decimal point; the display "
        "rounds, the value stays exact.", ""),
    # ----- styles / cells / editing -----
    "Format as Table": ("Format as Table",
        "Turns the selected range into a styled table: coloured header "
        "row, banded rows and borders. Pick a style from the gallery.",
        "Select the whole range, headers included, before choosing."),
    "Cell Styles": ("Format Cells",
        "Opens the Format Cells dialog with every option in one place: "
        "number, alignment, font, border and fill.",
        "Shortcut Ctrl+1, as in Excel."),
    "Insert": ("Insert Cells",
        "Inserts a new row below the selected cell. The arrow inserts a "
        "row above, a column, or a new sheet.", ""),
    "Format": ("Format",
        "Sets the row height or column width exactly, or opens Format "
        "Cells.", ""),
    "AutoSum": ("AutoSum",
        "Starts a =SUM( ) formula in the selected cell — pick the cells "
        "to add, then press Enter. The arrow offers Average, Count, Max "
        "and Min.", "Shortcut Alt+Shift+=."),
    "Clear": ("Clear",
        "Empties the selected cells, or deletes the selected chart, "
        "shape or equation.", "Shortcut Delete. Undo brings it back."),
    "Sort & Filter": ("Sort & Filter",
        "Sorts the rows of the current column from smallest to largest "
        "(A to Z) or the reverse.",
        "Click a cell in the column to sort by before choosing."),
    "Solver": ("Solver",
        "Finds the input values that make a formula reach its minimum, "
        "maximum or a target value, with optional limits on each input — "
        "Excel's Solver add-in, built in.",
        "Several methods (Powell, SLSQP, evolutionary) and multi-start "
        "for awkward problems."),
    "Curve Fitting": ("Curve Fitting",
        "Fits peaks or any model to the selected X / Y data: Gaussian, "
        "Lorentzian, Voigt, exponentials or your own function, with a "
        "background, a live plot and a fit report.",
        "The fitted components can be written back into the sheet."),
    # ----- insert -----
    "Table": ("Table",
        "Formats the selected range as a styled table (header, banded "
        "rows, borders).", ""),
    "Pivot / Transpose": ("Pivot / Transpose",
        "Flips the selected block so rows become columns and columns "
        "become rows.", "Undo restores the original layout."),
    "Pictures": ("Pictures",
        "Places an image file (PNG, JPEG, SVG…) over the sheet. Drag it to "
        "move it and its corners to resize it.",
        "The picture is stored inside the workbook file."),
    "Shapes": ("Shapes",
        "Draws a shape over the sheet — rectangles, arrows, callouts, "
        "stars, flowchart symbols. Double-click a shape to type in it.", ""),
    "Recommended Charts": ("Insert Chart",
        "Charts the selected columns with the last chart type you used. "
        "The arrow lists every type.",
        "Select X then Y columns (headers included) first. The chart "
        "stays linked: edit a cell and it redraws."),
    "Line": ("Line Chart",
        "Plots the selected Y columns against X as connected lines — for "
        "trends, spectra and time series.", ""),
    "Bar": ("Bar Chart",
        "Compares values across categories as vertical bars.", ""),
    "Pie": ("Pie Chart",
        "Shows how parts make up a whole. Best with fewer than seven "
        "slices.", ""),
    "Scatter": ("Scatter Chart",
        "Plots each X / Y pair as a marker without lines — for "
        "measurements and correlations.",
        "Right-click the chart to add a trendline."),
    "Line+Symbol": ("Line and Markers",
        "Lines through the data with a marker at each point, so you see "
        "both the trend and the measured values.", ""),
    "Histogram": ("Histogram",
        "Counts how many values fall into each range (bin) and shows the "
        "distribution of the selected column.", ""),
    "Box": ("Box Plot",
        "Shows the median, quartiles and outliers of each selected "
        "column side by side.", ""),
    "More": ("More Charts",
        "Step, stem, heatmap, 3-D surface, doughnut and 3-D pie charts, "
        "or a chart from a saved template.", ""),
    "Sparkline": ("Sparklines",
        "Draws a tiny line chart inside a cell for each selected row — a "
        "trend at a glance next to the data. The arrow has single "
        "sparklines and Remove.", ""),
    "Checkbox": ("Checkbox",
        "Puts a tick box in the selected cell. Ticked reads as 1 and "
        "unticked as 0, so formulas can count or test it.", ""),
    "Button": ("Button",
        "Turns the selected cell into a clickable button that writes a "
        "value into another cell and / or re-runs a Python cell.",
        "Modes: toggle, set a value, or pulse."),
    "Dropdown": ("Dropdown",
        "Gives the selected cell a drop-down list of allowed values to "
        "choose from — Excel's data-validation list.", ""),
    "Link": ("Link",
        "Turns the selected cell into a clickable link to a web page, a "
        "file or another cell.", "Shortcut Ctrl+K."),
    "Comment": ("Comment",
        "Adds a comment to the selected cell — a discussion note shown "
        "when you hover the cell's corner marker.",
        "Shortcut Ctrl+Alt+M."),
    "Note": ("Note",
        "Adds a yellow sticky note to the selected cell for a reminder or "
        "explanation.", "Shortcut Shift+F2."),
    "Equation": ("Equation",
        "Places a typeset equation over the sheet: choose a ready-made "
        "one (quadratic formula, Gaussian…) or write your own in the "
        "equation editor.", "Written in LaTeX, shown as real maths."),
    "Symbol": ("Symbol",
        "Inserts a Greek letter, maths sign or unit symbol (α, ±, °, Å, "
        "µ…) into the selected cell.", ""),
    "Emoji": ("Emoji",
        "Inserts an emoji into the selected cell.", ""),
    # ----- page layout / view -----
    "Themes": ("Themes",
        "Changes the colours of the whole window — light, dark and many "
        "tinted themes. The ribbon follows the theme's colour.",
        "Only the window changes; your cells keep their own colours."),
    "Print Setup": ("Print",
        "Opens the Print dialog: printer, paper, orientation, margins, "
        "scaling and a preview of the pages.", "Shortcut Ctrl+P."),
    "Gridlines": ("Gridlines",
        "Shows or hides the light grey lines between cells.",
        "Gridlines are for the screen; add Borders for lines that print."),
    "Headings": ("Headings",
        "Shows or hides the column letters and row numbers.", ""),
    "Bring Forward": ("Bring Forward",
        "Moves the selected chart, picture or shape in front of the one "
        "that covers it.", ""),
    "Send Backward": ("Send Backward",
        "Moves the selected chart, picture or shape behind the one under "
        "it.", ""),
    "Normal": ("Normal View",
        "The usual working view of the grid.", ""),
    "Page Layout": ("Page Layout View",
        "Shows the sheet as it will look on printed pages.", ""),
    "Zoom In": ("Zoom In",
        "Makes the cells bigger on screen.", "Shortcut Ctrl+=."),
    "Zoom Out": ("Zoom Out",
        "Makes the cells smaller so you see more of the sheet.",
        "Shortcut Ctrl+-."),
    "100%": ("100%",
        "Returns to the normal zoom.", "Shortcut Ctrl+0."),
    "New Window": ("New Window",
        "Opens a second KherveSheet window, for another workbook side by "
        "side.", "Shortcut Ctrl+Shift+N."),
    # ----- formulas -----
    "Insert Function": ("Insert Function",
        "Opens the function browser: search the ~290 functions by name "
        "or purpose, read what each argument means, and insert it into "
        "the cell.", "Shortcut Shift+F3. Formulas work as in Excel."),
    "Python Cell": ("Python Cell",
        "Makes the selected cell a Python cell (=PY): write a normal "
        "Python script; its last line becomes the cell's value. A list "
        "spills down the column, a matplotlib figure shows as a plot.",
        "ks(\"A1:B10\") reads cells as a NumPy array; ks_set writes "
        "back. numpy, scipy, pandas and matplotlib are ready."),
    # ----- data -----
    "Get Data": ("Get Data",
        "Imports data from a text / CSV file or an Excel workbook into "
        "the sheet.", ""),
    "From Text/CSV": ("From Text/CSV",
        "Imports a comma-, tab- or space-separated text file, as exported "
        "by most instruments.", ""),
    "From Excel": ("From Excel",
        "Opens the sheets of an Excel workbook (.xlsx) with their values, "
        "formulas and formatting.", ""),
    "Sort A to Z": ("Sort Smallest to Largest",
        "Sorts the rows by the current column, smallest (or A) first.",
        "Click a cell in the column to sort by first."),
    "Sort Z to A": ("Sort Largest to Smallest",
        "Sorts the rows by the current column, largest (or Z) first.", ""),
    "Set Column As X / Y": ("Set Column As X / Y",
        "Marks the selected columns as X (horizontal axis) or Y "
        "(plotted values) for charts and fitting.",
        "Charts and Curve Fitting read these marks to know what to plot "
        "against what."),
    "Statistics": ("Statistics",
        "Summarises the selected numbers: count, mean, median, standard "
        "deviation, minimum, maximum and more.",
        "The status bar always shows Average, Count and Sum of the "
        "selection."),
    "Science Tools": ("Science Tools",
        "Signal-processing tools for measured data: normalise, "
        "integrate, differentiate, smooth, FFT, interpolate, find peaks, "
        "subtract a baseline, filter, calibrate, deconvolve and more.",
        ""),
    # ----- review -----
    "Spelling": ("Spelling",
        "Checks the spelling of the text in the sheet and suggests "
        "corrections one by one.", "Shortcut F7."),
    "Check Spelling as You Type": ("Check Spelling as You Type",
        "Underlines misspelled words in red as you type.", ""),
    "New Comment": ("New Comment",
        "Adds a comment to the selected cell for co-authors to read.",
        "Shortcut Ctrl+Alt+M."),
    "New Note": ("New Note",
        "Adds a yellow sticky note to the selected cell.",
        "Shortcut Shift+F2."),
    "History": ("Version History",
        "Lists every saved version of this workbook with what changed, "
        "and lets you compare or restore any of them.",
        "Each save is recorded automatically; save the file once to "
        "start its history."),
    "Push": ("Push",
        "Sends this workbook's version history to its remote copy (for "
        "example a Git server), so it is backed up and shared.",
        "Set the remote first in File ▸ Version Control."),
    "Pull": ("Pull",
        "Fetches versions saved elsewhere from the remote copy.", ""),
    "Share": ("Share",
        "Edit this workbook live with other people: share it on "
        "KherveDOC or on your local network, invite people, or stop "
        "sharing.", "Everyone sees each other's cursor and edits live."),
    # ----- AI / help -----
    "Connect to Claude": ("Connect to Claude",
        "Lets Claude Desktop, Claude Code or another assistant work in "
        "this workbook — read data, write formulas, make charts, fit "
        "curves. No API key: it uses the login you already have.",
        "You choose how much it may change; every change can be undone."),
    "User Guide": ("User Guide",
        "Opens the KherveSheet user guide.", ""),
    "Python Help": ("Python in KherveSheet",
        "How Python cells work, with examples: reading and writing "
        "cells, spilling arrays, plotting with matplotlib.", ""),
    "Examples": ("Examples",
        "Ready-made workbooks and templates to open and learn from — "
        "worked science examples, Python examples and exercises.", ""),
    "Check for Updates": ("Check for Updates",
        "Looks for a newer version of KherveSheet.", ""),
    "About": ("About KherveSheet",
        "Version, licence and credits.", ""),
}

# Function-category buttons on the Formulas tab share one tip.
_CATEGORY = ("{name} functions",
             "Lists the {name} functions. Pick one to start it in the "
             "selected cell; hover a name in the list for what it does.",
             "Same names and arguments as Excel.")


def html(title: str, what: str, more: str = "", shortcut: str = "") -> str:
    head = f"<b>{escape(title)}</b>"
    if shortcut:
        head += (f"&nbsp;&nbsp;<span style='color:#777'>"
                 f"({escape(shortcut)})</span>")
    parts = [head, escape(what)]
    if more:
        parts.append(f"<span style='color:#777'>{escape(more)}</span>")
    return ("<p style='white-space:normal; width:300px'>"
            + "<br><br>".join(parts) + "</p>")


def tip_for(key: str, shortcut: str = "", category: bool = False) -> str:
    if key in TIPS:
        return html(*TIPS[key], shortcut=shortcut)
    if category:
        t, w, m = _CATEGORY
        return html(t.format(name=key), w.format(name=key), m)
    return ""


def apply(ribbon) -> None:
    """Give every button and box of the ribbon its long hover help.
    Keys are the button's label, or the `tip_key` property for widgets
    without one (the font box, colour buttons…)."""
    from PyQt5.QtWidgets import QToolButton, QWidget
    from .ribbon import short
    for w in ribbon.findChildren(QWidget):
        key = w.property("tip_key")
        shortcut = ""
        act = w.defaultAction() if isinstance(w, QToolButton) else None
        if not key and act is not None:
            key = short(act.text()).replace("\n", " ")
            shortcut = act.shortcut().toString()
        if not key:
            continue
        cat = bool(w.property("tip_category")
                   or (act is not None and act.property("tip_category")))
        text = tip_for(key, shortcut, category=cat)
        if not text:
            continue
        # A button copies its action's tooltip whenever the action
        # changes (checked, enabled), so the tip goes on the action.
        (act or w).setToolTip(text)
