# KherveSheet — undo commands for charts, annotations, sparklines
# Copyright © 2024-2026 Gwilherm Kerherve — GPL-3.0-or-later

"""QUndoCommand subclasses for chart, annotation, and sparkline operations.

Cell-level undo commands (CellEditCmd, FormatCellsCmd, etc.) live in
sheet.py.  This module covers overlay objects whose undo support was
added later.
"""

from PyQt5.QtWidgets import QUndoCommand


# ── Chart insert / delete ──────────────────────────────────────────────

class InsertChartCmd(QUndoCommand):
    """Undoable insertion of an EmbeddedChart onto a sheet."""

    def __init__(self, sheet, chart):
        super().__init__("Insert Chart")
        self.sheet = sheet
        self.chart = chart
        self._first = True

    def redo(self):
        if self._first:
            # Chart was already created and added by the caller on the
            # first pass — just mark done.
            self._first = False
            return
        self.chart.setParent(self.sheet.table.viewport())
        if self.chart not in self.sheet._charts:
            self.sheet._charts.append(self.chart)
        try:
            self.sheet.data_changed.connect(self.chart._on_data_changed)
        except (TypeError, RuntimeError):
            pass
        self.chart.show()

    def undo(self):
        self.chart.hide()
        try:
            self.sheet._charts.remove(self.chart)
        except ValueError:
            pass
        try:
            self.sheet.data_changed.disconnect(self.chart._on_data_changed)
        except (TypeError, RuntimeError):
            pass


class DeleteChartCmd(QUndoCommand):
    """Undoable deletion (close) of an EmbeddedChart."""

    def __init__(self, sheet, chart):
        super().__init__("Delete Chart")
        self.sheet = sheet
        self.chart = chart

    def redo(self):
        self.chart.hide()
        try:
            self.sheet._charts.remove(self.chart)
        except ValueError:
            pass
        try:
            self.sheet.data_changed.disconnect(self.chart._on_data_changed)
        except (TypeError, RuntimeError):
            pass
        if getattr(self.sheet, '_selected_chart', None) is self.chart:
            self.sheet._selected_chart = None

    def undo(self):
        self.chart.setParent(self.sheet.table.viewport())
        if self.chart not in self.sheet._charts:
            self.sheet._charts.append(self.chart)
        try:
            self.sheet.data_changed.connect(self.chart._on_data_changed)
        except (TypeError, RuntimeError):
            pass
        self.chart.show()


# ── Annotation add / delete / modify ──────────────────────────────────

def _snapshot_annotation(ann_dict):
    """Capture the serialisable state of an annotation dict entry.

    This mirrors the serialisation logic in EmbeddedChart.to_dict() but
    works on a single annotation.
    """
    a = ann_dict
    artist = a["artist"]
    d = {"type": a["type"]}

    if a["type"] == "text":
        d["text"] = artist.get_text()
        d["xy"] = tuple(artist.xy)
        d["fontsize"] = float(artist.get_fontsize())
        d["fontweight"] = str(artist.get_fontweight())
        d["fontstyle"] = str(artist.get_fontstyle())
        d["color"] = artist.get_color()
        d["rotation"] = float(artist.get_rotation())
        bp = artist.get_bbox_patch()
        if bp is not None:
            from matplotlib.colors import to_hex
            fc = bp.get_facecolor()
            d["bbox_fc"] = to_hex(fc[:3])
            d["bbox_alpha"] = float(fc[3]) if len(fc) > 3 else 1.0
            d["bbox_style"] = type(bp.get_boxstyle()).__name__.lower()

    elif a["type"] == "arrow":
        d["text"] = artist.get_text()
        d["xy"] = tuple(artist.xy)
        d["xytext"] = tuple(artist.get_position())
        ap = getattr(artist, "arrow_patch", None)
        if ap is not None:
            from matplotlib.colors import to_hex
            d["arrow_color"] = to_hex(ap.get_edgecolor()[:3])
            d["arrow_lw"] = float(ap.get_linewidth())
            d["arrow_ls"] = ap.get_linestyle()
            from .graph import _arrowstyle_name
            d["arrow_style"] = _arrowstyle_name(ap)

    elif a["type"] == "line":
        if hasattr(artist, 'xy') and hasattr(artist, 'get_position'):
            d["xy"] = tuple(artist.xy)
            d["xytext"] = tuple(artist.get_position())
            ap = getattr(artist, "arrow_patch", None)
            if ap is not None:
                from matplotlib.colors import to_hex
                d["arrow_color"] = to_hex(ap.get_edgecolor()[:3])
                d["arrow_lw"] = float(ap.get_linewidth())
                d["arrow_ls"] = ap.get_linestyle()
        else:
            d["direction"] = a.get("direction", "horizontal")
            if d["direction"] == "horizontal":
                d["value"] = float(artist.get_ydata()[0])
            else:
                d["value"] = float(artist.get_xdata()[0])
    return d


def _recreate_annotation(ax, snap, canvas):
    """Re-create an annotation artist from a snapshot dict.

    Returns a new annotation dict entry ``{"type": ..., "artist": ...}``.
    """
    atype = snap["type"]

    if atype == "text":
        bbox_d = None
        if "bbox_fc" in snap:
            bbox_d = dict(
                boxstyle=snap.get("bbox_style", "round") + ",pad=0.3",
                facecolor=snap["bbox_fc"],
                alpha=snap.get("bbox_alpha", 0.8))
        ann = ax.annotate(
            snap.get("text", ""), xy=snap["xy"], xytext=snap["xy"],
            fontsize=snap.get("fontsize", 10),
            fontweight=snap.get("fontweight", "normal"),
            fontstyle=snap.get("fontstyle", "normal"),
            color=snap.get("color", "black"),
            rotation=snap.get("rotation", 0),
            ha='center', va='center', bbox=bbox_d)
        ann.draggable(True)
        return {"type": "text", "artist": ann}

    elif atype == "arrow":
        ac = snap.get("arrow_color", "black")
        alw = snap.get("arrow_lw", 1.5)
        als = snap.get("arrow_ls", "-")
        astyle = snap.get("arrow_style", "->")
        if astyle.startswith("<"):
            astyle = "->"
        txt = snap.get("text", "")
        ann = ax.annotate(
            txt, xy=snap["xy"],
            xytext=snap.get("xytext", snap["xy"]),
            fontsize=9,
            arrowprops=dict(arrowstyle=astyle, color=ac, lw=alw,
                            linestyle=als),
            bbox=dict(boxstyle='round,pad=0.2', fc='white', alpha=0.7)
            if txt.strip() else None)
        ann.draggable(True)
        return {"type": "arrow", "artist": ann}

    elif atype == "line":
        if "xy" in snap and "xytext" in snap:
            ac = snap.get("arrow_color", "black")
            alw = snap.get("arrow_lw", 1.5)
            als = snap.get("arrow_ls", "-")
            ann = ax.annotate(
                "", xy=snap["xy"], xytext=snap["xytext"],
                arrowprops=dict(arrowstyle='-', color=ac, lw=alw,
                                linestyle=als))
            ann.draggable(True)
            return {"type": "line", "artist": ann}
        else:
            dirn = snap.get("direction", "horizontal")
            val = snap.get("value", 0)
            if dirn == "horizontal":
                line = ax.axhline(val, color='red', ls='--', lw=1.2)
            else:
                line = ax.axvline(val, color='red', ls='--', lw=1.2)
            from .graph import _DraggableLine
            dl = _DraggableLine(line, dirn, canvas)
            return {"type": "line", "artist": line,
                    "direction": dirn, "dragger": dl}

    return None


class AddAnnotationCmd(QUndoCommand):
    """Undoable addition of an annotation to a chart."""

    def __init__(self, chart, ann_dict):
        type_label = ann_dict.get("type", "annotation").title()
        super().__init__(f"Add {type_label}")
        self.chart = chart
        # Snapshot the annotation so we can re-create it on redo.
        self._snap = _snapshot_annotation(ann_dict)
        self._ann_dict = ann_dict
        self._first = True

    def redo(self):
        if self._first:
            self._first = False
            return
        new_entry = _recreate_annotation(
            self.chart._ax, self._snap, self.chart._canvas)
        if new_entry:
            self.chart._annotations.append(new_entry)
            self._ann_dict = new_entry
        self.chart._canvas.draw_idle()

    def undo(self):
        # Remove the annotation.
        try:
            self.chart._annotations.remove(self._ann_dict)
        except ValueError:
            # Fallback: pop last if same type.
            for i in reversed(range(len(self.chart._annotations))):
                if self.chart._annotations[i]["type"] == self._snap["type"]:
                    self.chart._annotations.pop(i)
                    break
        try:
            self._ann_dict["artist"].remove()
        except Exception:
            pass
        self.chart._deselect_annotation()
        self.chart._canvas.draw_idle()


class DeleteAnnotationCmd(QUndoCommand):
    """Undoable deletion of an annotation from a chart."""

    def __init__(self, chart, ann_dict, index):
        type_label = ann_dict.get("type", "annotation").title()
        super().__init__(f"Delete {type_label}")
        self.chart = chart
        self._snap = _snapshot_annotation(ann_dict)
        self._index = index
        self._ann_dict = ann_dict

    def redo(self):
        # Remove the annotation.
        try:
            self.chart._annotations.remove(self._ann_dict)
        except ValueError:
            if self._index < len(self.chart._annotations):
                self.chart._annotations.pop(self._index)
        try:
            self._ann_dict["artist"].remove()
        except Exception:
            pass
        self.chart._deselect_annotation()
        self.chart._canvas.draw_idle()

    def undo(self):
        new_entry = _recreate_annotation(
            self.chart._ax, self._snap, self.chart._canvas)
        if new_entry:
            idx = min(self._index, len(self.chart._annotations))
            self.chart._annotations.insert(idx, new_entry)
            self._ann_dict = new_entry
        self.chart._canvas.draw_idle()


class ModifyAnnotationCmd(QUndoCommand):
    """Undoable property change on an annotation."""

    def __init__(self, chart, ann_dict, old_snap, new_snap):
        type_label = ann_dict.get("type", "annotation").title()
        super().__init__(f"Modify {type_label}")
        self.chart = chart
        self._index = None
        try:
            self._index = chart._annotations.index(ann_dict)
        except ValueError:
            pass
        self._old_snap = old_snap
        self._new_snap = new_snap
        self._first = True

    def redo(self):
        if self._first:
            self._first = False
            return
        self._apply(self._new_snap)

    def undo(self):
        self._apply(self._old_snap)

    def _apply(self, snap):
        idx = self._index
        if idx is None or idx >= len(self.chart._annotations):
            return
        old_entry = self.chart._annotations[idx]
        try:
            old_entry["artist"].remove()
        except Exception:
            pass
        new_entry = _recreate_annotation(
            self.chart._ax, snap, self.chart._canvas)
        if new_entry:
            self.chart._annotations[idx] = new_entry
        self.chart._deselect_annotation()
        self.chart._canvas.draw_idle()


# ── Sparkline insert / delete ─────────────────────────────────────────

class InsertSparklineCmd(QUndoCommand):
    """Undoable insertion of sparkline(s) into cell(s)."""

    def __init__(self, sheet, entries):
        """*entries*: list of ((row, col), spark_dict) tuples."""
        n = len(entries)
        label = f"Insert Sparkline{'s' if n > 1 else ''}"
        super().__init__(label)
        self.sheet = sheet
        self.entries = entries

    def redo(self):
        if not hasattr(self.sheet, '_cell_sparklines'):
            self.sheet._cell_sparklines = {}
        for (r, c), spark in self.entries:
            self.sheet._fmt_delegate._sparklines[(r, c)] = spark
            self.sheet._cell_sparklines[(r, c)] = spark
            idx = self.sheet.table.model().index(r, c)
            self.sheet.table.update(idx)

    def undo(self):
        for (r, c), _spark in self.entries:
            self.sheet._fmt_delegate._sparklines.pop((r, c), None)
            if hasattr(self.sheet, '_cell_sparklines'):
                self.sheet._cell_sparklines.pop((r, c), None)
            idx = self.sheet.table.model().index(r, c)
            self.sheet.table.update(idx)


class DeleteSparklineCmd(QUndoCommand):
    """Undoable removal of sparkline(s) from cell(s)."""

    def __init__(self, sheet, entries):
        """*entries*: list of ((row, col), spark_dict) tuples."""
        n = len(entries)
        label = f"Delete Sparkline{'s' if n > 1 else ''}"
        super().__init__(label)
        self.sheet = sheet
        self.entries = entries

    def redo(self):
        for (r, c), _spark in self.entries:
            self.sheet._fmt_delegate._sparklines.pop((r, c), None)
            if hasattr(self.sheet, '_cell_sparklines'):
                self.sheet._cell_sparklines.pop((r, c), None)
            idx = self.sheet.table.model().index(r, c)
            self.sheet.table.update(idx)

    def undo(self):
        if not hasattr(self.sheet, '_cell_sparklines'):
            self.sheet._cell_sparklines = {}
        for (r, c), spark in self.entries:
            self.sheet._fmt_delegate._sparklines[(r, c)] = spark
            self.sheet._cell_sparklines[(r, c)] = spark
            idx = self.sheet.table.model().index(r, c)
            self.sheet.table.update(idx)


# ── Chart property changes ────────────────────────────────────────────

class ChartPropertyCmd(QUndoCommand):
    """Undoable general-properties change on an EmbeddedChart."""

    def __init__(self, chart, old_state, new_state, label="Chart Properties"):
        super().__init__(label)
        self.chart = chart
        self.old_state = old_state
        self.new_state = new_state
        self._first = True

    def redo(self):
        if self._first:
            self._first = False
            return
        from .general_properties import apply_general_state
        apply_general_state(self.chart, self.new_state)
        self.chart._canvas.draw_idle()

    def undo(self):
        from .general_properties import apply_general_state
        apply_general_state(self.chart, self.old_state)
        self.chart._canvas.draw_idle()


# ── Note / comment add, edit, delete ──────────────────────────────────

class NoteCmd(QUndoCommand):
    """Undoable add/edit/delete of a cell note or comment."""

    def __init__(self, sheet, row, col, old_note, new_note):
        """*old_note* / *new_note*: dict ``{"text": ..., "kind": ...}``
        or ``None`` (meaning no note exists).
        """
        if new_note is None:
            label = "Delete Note"
        elif old_note is None:
            label = "Add Note"
        else:
            label = "Edit Note"
        super().__init__(label)
        self.sheet = sheet
        self.row = row
        self.col = col
        self.old_note = old_note
        self.new_note = new_note

    def redo(self):
        self._apply(self.new_note)

    def undo(self):
        self._apply(self.old_note)

    def _apply(self, note):
        if note is not None:
            self.sheet._cell_notes[(self.row, self.col)] = note
        else:
            self.sheet._cell_notes.pop((self.row, self.col), None)
        self.sheet._hide_note_popup()
        idx = self.sheet.table.model().index(self.row, self.col)
        self.sheet.table.update(idx)


# ── Clear cell format ─────────────────────────────────────────────────

class ClearFormatCmd(QUndoCommand):
    """Undoable clear of cell formatting from one or more cells."""

    def __init__(self, sheet, old_formats, label="Clear Formatting"):
        """*old_formats*: dict mapping (row, col) → CellFormat snapshot."""
        super().__init__(label)
        self.sheet = sheet
        self.old_formats = old_formats

    def redo(self):
        from PyQt5.QtGui import QBrush
        self.sheet.table.blockSignals(True)
        for (r, c) in self.old_formats:
            self.sheet._cell_formats.pop((r, c), None)
            it = self.sheet.table.item(r, c)
            if it:
                it.setBackground(QBrush())
        self.sheet.table.blockSignals(False)
        self.sheet.table.viewport().update()

    def undo(self):
        for (r, c), fmt in self.old_formats.items():
            if fmt is not None:
                self.sheet._cell_formats[(r, c)] = fmt
        self.sheet.table.viewport().update()


class InsertButtonCmd(QUndoCommand):
    """Undoable creation of a cell button."""

    def __init__(self, sheet, row, col, old_text, spec):
        super().__init__(f"Insert Button {spec.get('label', '')}".strip())
        self.sheet = sheet
        self.row = row
        self.col = col
        self._old_text = old_text
        self._spec = dict(spec)
        self._first = True

    def redo(self):
        if self._first:
            self._first = False    # already applied by the caller
            return
        from .cell_buttons import insert_button
        # Push nothing: this command *is* the undo entry.
        stack, self.sheet._undo_stack = self.sheet._undo_stack, None
        try:
            insert_button(self.sheet, self.row, self.col, self._spec)
        finally:
            self.sheet._undo_stack = stack

    def undo(self):
        from .cell_buttons import remove_button
        remove_button(self.sheet, self.row, self.col)
        it = self.sheet.table.item(self.row, self.col)
        if it is not None:
            it.setText(self._old_text)
        self.sheet._shadow[(self.row, self.col)] = self._old_text
        self.sheet.table.viewport().update()
