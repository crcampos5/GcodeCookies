"""Mouse editing of FILL samples, stored in source-item coordinates."""
from PySide6.QtCore import QObject, QEvent, Qt, QPointF
from PySide6.QtGui import QPainterPath, QPen, QColor, QBrush, QTransform
from PySide6.QtWidgets import QGraphicsItem
from shiboken6 import isValid


class ScanPointEditor(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.w = window
        self.row = None
        self.source = None
        self.selected = None
        self.dragging = False
        self.draft = None
        self.graphics = []
        self.canvas = window.canvas
        self.canvas.viewport().installEventFilter(self)
        self.canvas.installEventFilter(self)

    @property
    def active(self):
        return self.row is not None

    def operation(self):
        ops = self.w.gcode_panel.generator.operations
        if self.row is None or not 0 <= self.row < len(ops):
            return None
        op = ops[self.row]
        if op['type']!='fill' or op.get('source_item') is not self.source:
            return None
        return op

    def begin(self, row):
        self.finish()
        ops = self.w.gcode_panel.generator.operations
        if not 0 <= row < len(ops) or ops[row]['type']!='fill':
            return
        self.row = row; self.source = ops[row].get('source_item')
        self.w.tabs.setCurrentIndex(0)
        self.w.gcode_panel.btn_scan.setText('Terminar edición de puntos')
        self.canvas.setCursor(Qt.CrossCursor)
        self.refresh()
        self.canvas.setFocus()

    def clear_graphics(self):
        for item in self.graphics:
            self.canvas.scene.removeItem(item)
        self.graphics.clear()

    def finish(self):
        self.row = None; self.source = None; self.selected = None
        self.dragging = False; self.draft = None
        self.clear_graphics()
        self.canvas.unsetCursor()
        self.w.gcode_panel.btn_scan.setText('Editar puntos de escaneo')
        self.w.gcode_panel.group_config.setEnabled(True)
        self.w.gcode_panel.btn_edit.setEnabled(self.w.gcode_panel.list_ops.currentRow()>=0)
        self.w.update_registered_controls()

    def points(self):
        _, groups = self.w.gcode_panel.generator.fill_scan_data(self.operation())
        return [p for group in groups for p in group]

    def message(self, text):
        self.w.lbl_info.setText(text)

    def add_graphic(self, item, z=50):
        item.setAcceptedMouseButtons(Qt.NoButton)
        item.setZValue(z)
        self.graphics.append(item)
        return item

    def refresh(self):
        if not self.active:
            return
        op = self.operation()
        if op is None:
            self.finish(); return
        try:
            regions, groups = self.w.gcode_panel.generator.fill_scan_data(op)
        except ValueError as exc:
            self.finish(); self.message(str(exc)); return
        self.clear_graphics()
        fill = QPainterPath(); fill.setFillRule(Qt.OddEvenFill)
        for region in regions:
            for ring in [region.exterior,*region.interiors]:
                coords=list(ring.coords);fill.moveTo(*coords[0])
                for p in coords[1:]:fill.lineTo(*p)
                fill.closeSubpath()
        self.add_graphic(self.canvas.scene.addPath(fill,QPen(QColor('#007acc'),0),QBrush(QColor(0,150,220,35))),40)
        points = self.draft if self.draft is not None else [p for group in groups for p in group]
        if self.selected is not None and self.selected>=len(points):self.selected=None
        for index,(x,y) in enumerate(points):
            color=QColor('#e87800' if index==self.selected else '#0066ff')
            cross=QPainterPath();cross.moveTo(-6,0);cross.lineTo(6,0);cross.moveTo(0,-6);cross.lineTo(0,6)
            marker=self.add_graphic(self.canvas.scene.addPath(cross,QPen(color,2)))
            marker.setFlag(QGraphicsItem.ItemIgnoresTransformations,True);marker.setPos(x,y)
            label=self.add_graphic(self.canvas.scene.addSimpleText(str(index+1)),51)
            label.setBrush(QBrush(color));label.setFlag(QGraphicsItem.ItemIgnoresTransformations,True)
            label.setPos(x,y)
            label.setTransform(QTransform().translate(8,-18))
        self.w.control_panel.setEnabled(False)
        self.w.gcode_panel.group_config.setEnabled(False)
        self.w.gcode_panel.btn_edit.setEnabled(False)
        self.w.gcode_panel.btn_scan.setEnabled(True)
        self.message(f'Escaneo: {op["name"]} · {len(points)} puntos · Esc: terminar')
        self.w.lbl_info.setToolTip('Clic: agregar · Arrastrar: mover · Suprimir: borrar · Esc: terminar')

    def commit(self, points, label):
        op=self.operation()
        if op is None:return False
        try:
            self.w.gcode_panel.generator.set_fill_scan_points(op,points)
        except ValueError as exc:
            self.draft=None;self.refresh();self.message(str(exc));return False
        self.draft=None
        self.w.history.commit(label)
        self.w.update_canvas_preview()
        return True

    def delete_selected(self):
        if self.selected is None:
            self.message('Selecciona un punto de escaneo para eliminarlo.');return
        points=self.points();points.pop(self.selected)
        if self.commit(points,'Eliminar punto de escaneo'):
            self.selected=None;self.refresh()

    def eventFilter(self, watched, event):
        if not self.active or not isValid(self.canvas):return False
        kind=event.type()
        if kind==QEvent.KeyPress:
            if event.key()==Qt.Key_Escape:
                self.finish();return True
            if event.key() in (Qt.Key_Delete,Qt.Key_Backspace):
                self.delete_selected();return True
            if event.key() in (Qt.Key_Left,Qt.Key_Right,Qt.Key_Up,Qt.Key_Down):return True
        if watched is not self.canvas.viewport():return False
        if kind==QEvent.MouseButtonDblClick and event.button()==Qt.LeftButton:return True
        if kind==QEvent.MouseButtonPress and event.button()==Qt.LeftButton:
            self.canvas.setFocus()
            points=self.points();position=event.position().toPoint()
            distances=[(self.canvas.mapFromScene(QPointF(*p))-position).manhattanLength() for p in points]
            if distances and min(distances)<=12:
                self.selected=distances.index(min(distances));self.dragging=True;self.draft=list(points)
                self.drag_origin=position;self.drag_moved=False;self.refresh()
            else:
                q=self.canvas.mapToScene(position)
                self.selected=None
                self.commit(points+[(q.x(),q.y())],'Agregar punto de escaneo')
            return True
        if kind==QEvent.MouseMove and self.dragging:
            if not self.drag_moved and (event.position().toPoint()-self.drag_origin).manhattanLength()<3:
                return True
            self.drag_moved=True
            q=self.canvas.mapToScene(event.position().toPoint())
            self.draft[self.selected]=(q.x(),q.y());self.refresh();return True
        if kind==QEvent.MouseButtonRelease and event.button()==Qt.LeftButton:
            if self.dragging:
                self.dragging=False
                if not self.drag_moved:
                    self.draft=None;self.refresh();return True
                q=self.canvas.mapToScene(event.position().toPoint())
                self.draft[self.selected]=(q.x(),q.y())
                if self.draft!=self.points():self.commit(self.draft,'Mover punto de escaneo')
                else:self.draft=None;self.refresh()
            return True
        return False
