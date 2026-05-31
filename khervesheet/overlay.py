"""Shared selection, z-order and grouping helpers for overlay widgets.

Embedded shapes, equations and images all float as sibling child
widgets of the sheet's table viewport.  This module gives them a common
model so they can be selected together, stacked (bring to front / send
to back / forward / backward) and grouped so that moving one member
moves the whole group.

Copyright (C) 2026 Gwilherm Kerherve

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

from __future__ import annotations

from PyQt5.QtWidgets import QUndoCommand


def add_arrange_actions(menu, widget):
    """Add z-order + group/ungroup entries to a context *menu*."""
    arrange = menu.addMenu("Arrange")
    arrange.addAction("Bring to Front",
                      lambda: bring_to_front(widget))
    arrange.addAction("Bring Forward",
                      lambda: bring_forward(widget))
    arrange.addAction("Send Backward",
                      lambda: send_backward(widget))
    arrange.addAction("Send to Back",
                      lambda: send_to_back(widget))
    sheet = sheet_of(widget)
    grp = menu.addAction("Group", lambda: group_selected(widget))
    grp.setEnabled(bool(sheet) and can_group(sheet))
    ung = menu.addAction("Ungroup", lambda: ungroup(widget))
    ung.setEnabled(can_ungroup(widget))


_OVERLAY_LISTS = ("_shapes", "_equations", "_images")


# ── Sheet / overlay discovery ─────────────────────────────────────────

def sheet_of(widget):
    """Walk up from an overlay widget to the SheetWidget that owns it."""
    sw = widget.parent() if widget is not None else None
    while sw and not any(hasattr(sw, n) for n in _OVERLAY_LISTS):
        p = sw.parent()
        if p is sw:
            break
        sw = p
    if sw and any(hasattr(sw, n) for n in _OVERLAY_LISTS):
        return sw
    return None


def all_overlays(sheet):
    """Every shape, equation and image on the sheet (flat list)."""
    items = []
    for name in _OVERLAY_LISTS:
        items.extend(getattr(sheet, name, []) or [])
    return items


def selected_overlays(sheet):
    return [o for o in all_overlays(sheet)
            if getattr(o, "_selected", False)]


def deselect_all(sheet, except_widget=None):
    for o in all_overlays(sheet):
        if o is not except_widget and getattr(o, "_selected", False):
            o._selected = False
            o.update()


# ── Selection on mouse press ──────────────────────────────────────────

def handle_select_on_press(widget, ctrl):
    """Update selection when *widget* is pressed.

    ``ctrl`` toggles membership without clearing the rest.  A plain click
    selects the widget (and its whole group), clearing other selections —
    unless the widget is already part of an active multi-selection, in
    which case the selection is kept so the group can be dragged.
    """
    sheet = sheet_of(widget)
    if sheet is None:
        widget._selected = True
        widget.update()
        return
    if ctrl:
        widget._selected = not getattr(widget, "_selected", False)
        widget.update()
        return
    members = group_members(widget)
    already = getattr(widget, "_selected", False)
    if already and len(selected_overlays(sheet)) > 1:
        return  # keep the active multi-selection so it can be dragged
    deselect_all(sheet)
    for m in members:
        m._selected = True
        m.update()


# ── Grouping ──────────────────────────────────────────────────────────

def group_id(widget):
    return getattr(widget, "_group_id", None)


def group_members(widget):
    """All overlays sharing *widget*'s group, or just [widget]."""
    gid = group_id(widget)
    if gid is None:
        return [widget]
    sheet = sheet_of(widget)
    if sheet is None:
        return [widget]
    members = [o for o in all_overlays(sheet) if group_id(o) == gid]
    return members or [widget]


def _new_group_id(sheet):
    existing = [group_id(o) for o in all_overlays(sheet)]
    existing = [g for g in existing if g is not None]
    return (max(existing) + 1) if existing else 1


def can_group(sheet):
    return len(selected_overlays(sheet)) >= 2


def can_ungroup(widget):
    return group_id(widget) is not None


# ── Z-order (stacking) ────────────────────────────────────────────────

def _in_stack_order(items):
    """Sort *items* by their back-to-front stacking order."""
    if not items:
        return []
    parent = items[0].parent()
    if parent is None:
        return list(items)
    order = {c: i for i, c in enumerate(parent.children())}
    return sorted(items, key=lambda w: order.get(w, 0))


def _overlay_siblings_in_stack_order(widget):
    sheet = sheet_of(widget)
    overlays = set(all_overlays(sheet)) if sheet else {widget}
    parent = widget.parent()
    if parent is None:
        return [widget]
    return [c for c in parent.children() if c in overlays]


def bring_to_front(widget):
    for m in _in_stack_order(group_members(widget)):
        m.raise_()


def send_to_back(widget):
    for m in reversed(_in_stack_order(group_members(widget))):
        m.lower()


def _step_forward(m):
    sibs = _overlay_siblings_in_stack_order(m)
    if m not in sibs:
        return
    i = sibs.index(m)
    if i < len(sibs) - 1:
        sibs[i + 1].stackUnder(m)


def _step_backward(m):
    sibs = _overlay_siblings_in_stack_order(m)
    if m not in sibs:
        return
    i = sibs.index(m)
    if i > 0:
        m.stackUnder(sibs[i - 1])


def bring_forward(widget):
    # Move the topmost member first so members don't leapfrog each other.
    for m in reversed(_in_stack_order(group_members(widget))):
        _step_forward(m)


def send_backward(widget):
    for m in _in_stack_order(group_members(widget)):
        _step_backward(m)


# ── Group dragging ────────────────────────────────────────────────────

def begin_group_drag(widget):
    """Snapshot start positions of everything that should move with
    *widget* (its whole current selection)."""
    sheet = sheet_of(widget)
    movers = selected_overlays(sheet) if sheet else [widget]
    if widget not in movers:
        movers.append(widget)
    return {m: m.pos() for m in movers}


def drag_group(starts, delta):
    for m, p0 in starts.items():
        m.move(p0 + delta)


# ── Undo commands ─────────────────────────────────────────────────────

class GroupCmd(QUndoCommand):
    """Undoable grouping of a set of overlays."""

    def __init__(self, members, gid):
        super().__init__("Group")
        self._members = list(members)
        self._old = {m: group_id(m) for m in members}
        self._gid = gid

    def redo(self):
        for m in self._members:
            m._group_id = self._gid

    def undo(self):
        for m in self._members:
            m._group_id = self._old[m]


class UngroupCmd(QUndoCommand):
    """Undoable ungrouping."""

    def __init__(self, members):
        super().__init__("Ungroup")
        self._members = list(members)
        self._old = {m: group_id(m) for m in members}

    def redo(self):
        for m in self._members:
            m._group_id = None

    def undo(self):
        for m in self._members:
            m._group_id = self._old[m]


def group_selected(widget):
    """Group the current selection (undoable).  Returns the group id."""
    sheet = sheet_of(widget)
    if sheet is None:
        return None
    members = selected_overlays(sheet)
    if len(members) < 2:
        return None
    gid = _new_group_id(sheet)
    stack = getattr(sheet, "_undo_stack", None)
    cmd = GroupCmd(members, gid)
    if stack is not None:
        stack.push(cmd)
    else:
        cmd.redo()
    return gid


def ungroup(widget):
    """Ungroup *widget*'s group (undoable)."""
    members = group_members(widget)
    if group_id(widget) is None:
        return
    sheet = sheet_of(widget)
    stack = getattr(sheet, "_undo_stack", None) if sheet else None
    cmd = UngroupCmd(members)
    if stack is not None:
        stack.push(cmd)
    else:
        cmd.redo()
