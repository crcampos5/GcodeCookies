"""Undoable design edits, keeping scene objects and their operation references alive."""
from PySide6.QtGui import QUndoCommand, QUndoStack
from PySide6.QtCore import Qt
from gui.dxf_item import DXFGraphicsItem


class DesignCommand(QUndoCommand):
    def __init__(self, history, before, after, label):
        super().__init__(label)
        self.history, self.before, self.after = history, before, after
        self.first = True

    def redo(self):
        if self.first:
            self.first = False
        else:
            self.history.restore(self.after)

    def undo(self):
        self.history.restore(self.before)


class DesignHistory:
    def __init__(self, window):
        self.window = window
        self.restoring = False
        self.stack = QUndoStack(window)
        self.stack.setUndoLimit(100)
        self.last = self.capture()

    def capture(self):
        w = self.window
        items = [i for i in w.canvas.scene.items(Qt.AscendingOrder) if isinstance(i, DXFGraphicsItem)]
        return dict(items=[(i, i.x(), i.y(), i.scale(), i.rotation(), i.zValue()) for i in items],
                    selected=[i for i in items if i.isSelected()],
                    operations=[dict(op) for op in w.gcode_panel.generator.operations],
                    registration=w.gcode_panel.generator.registration,
                    registration_geometry=dict(w.gcode_panel.generator.registration_geometry),
                    name=w.gcode_panel.generator.design_name)

    def commit(self, label):
        if self.restoring:
            return
        after = self.capture()
        if any(after[key] != self.last[key] for key in ('items', 'operations', 'name', 'registration')):
            self.stack.push(DesignCommand(self, self.last, after, label))
            self.last = after

    def restore(self, state):
        w = self.window
        self.restoring = True
        try:
            w.preview_timer.stop()
            scene = w.canvas.scene
            # Selection is a current UI choice, not geometry to rewind.
            selected_now = set(scene.selectedItems())
            scene.blockSignals(True)
            try:
                desired = {entry[0] for entry in state['items']}
                for item in list(scene.items()):
                    if isinstance(item, DXFGraphicsItem) and item not in desired:
                        scene.removeItem(item)
                scene.clearSelection()
                for item, x, y, scale, rotation, z in state['items']:
                    if item.scene() is not scene:
                        scene.addItem(item)
                    locked = getattr(item,'registration_locked',False)
                    item.registration_locked = False
                    try:
                        item.setPos(x,y);item.setScale(scale);item.setRotation(rotation)
                    finally:
                        item.registration_locked = locked
                    item.setZValue(z)
                    item.setSelected(item in selected_now)
                # Restore bottom-to-top order, including equal-Z siblings.
                ordered = [entry[0] for entry in state['items']]
                for lower, upper in reversed(list(zip(ordered, ordered[1:]))):
                    if lower.zValue() == upper.zValue():
                        lower.stackBefore(upper)
            finally:
                scene.blockSignals(False)
            panel = w.gcode_panel
            panel.cancel_editing()
            panel.generator.operations = [dict(op) for op in state['operations']]
            panel.generator.design_name = state['name']
            panel.generator.registration = state['registration']
            panel.generator.registration_geometry = dict(state['registration_geometry'])
            w.sync_registration_ui()
            panel.refresh_list()
            w.preview_timer.stop()
            w.on_items_selected(scene.selectedItems())
            if w.scan_editor.active:
                w.scan_editor.draft = None
                w.scan_editor.dragging = False
                w.scan_editor.selected = None
                if w.scan_editor.operation() is not None:
                    panel.list_ops.setCurrentRow(w.scan_editor.row)
                w.scan_editor.refresh()
            self.last = self.capture()
        finally:
            self.restoring = False
