from pathlib import Path
import math
import copy
from PySide6.QtCore import QTimer, QSaveFile, QIODevice, Qt
from PySide6.QtGui import QAction, QKeySequence, QPainter
from gui.design_history import DesignHistory
from gui.dxf_item import DXFGraphicsItem
from PySide6.QtWidgets import (QMainWindow, QHBoxLayout, QVBoxLayout, QWidget, 
                               QFileDialog, QMessageBox, QLabel, QTabWidget, QTextEdit, QScrollArea, QPushButton, QSizePolicy)

from gui.canvas import ViewerCanvas
from gui.control_panel import ControlPanel
from gui.file_panel import FilePanel
from gui.gcode_panel import GCodePanel
from gui.collapsible_box import CollapsibleBox  # <--- IMPORTACIÓN NUEVA
from core.dxf_processor import DXFReader
from core.transformer import TransformManager

class StatusLabel(QLabel):
    """Single-line status that never forces the window to grow."""
    def __init__(self, text=''):
        super().__init__(text)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.setMinimumWidth(0)
        self.setToolTip(text)

    def setText(self, text):
        super().setText(' '.join(text.split()))
        self.setToolTip(text)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setPen(self.palette().color(self.foregroundRole()))
        text = self.fontMetrics().elidedText(self.text(), Qt.ElideRight, self.contentsRect().width())
        painter.drawText(self.contentsRect(), Qt.AlignLeft | Qt.AlignVCenter, text)


class MainWindow(QMainWindow):
    def closeEvent(self, event):
        self.history.commit('Editar diseño')
        if not self.history.stack.isClean():
            answer = QMessageBox.question(
                self, 'Cambios sin guardar', '¿Deseas guardar los cambios del proyecto antes de cerrar?',
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Save)
            if answer not in (QMessageBox.Save, QMessageBox.Discard):
                event.ignore()
                return
            if answer == QMessageBox.Save and not self.project_actions.save():
                event.ignore()
                return
        self.preview_timer.stop()
        self.scan_editor.finish()
        event.accept()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("CookieCNC - Editor Multicapa")
        available = self.screen().availableGeometry()
        self.resize(min(1100, available.width() - 40),
                    min(750, available.height() - 60))
        
        self.dxf_reader = DXFReader()
        self.transformer = TransformManager()

        self.setup_ui()
        self.setup_connections()
        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(120)
        self.preview_timer.timeout.connect(self.update_canvas_preview)
        self.canvas.geometry_changed.connect(self.on_geometry_changed)
        self.canvas.move_registered_group = self.move_registered_group
        self.history = DesignHistory(self)
        from gui.scan_point_editor import ScanPointEditor
        self.scan_editor = ScanPointEditor(self)
        self.gcode_panel.scan_edit_requested.connect(self.toggle_scan_editor)
        self.gcode_panel.operations_reordering.connect(self.scan_editor.finish)
        self.gcode_panel.list_ops.currentRowChanged.connect(self.scan_operation_changed)
        from gui.project_actions import ProjectActions
        self.project_actions = ProjectActions(self)
        self.setup_edit_actions()
        self.configuration_action = QAction('Configuración',self)
        self.menuBar().addAction(self.configuration_action)
        self.configuration_action.triggered.connect(self.configure_worktable)
        self.canvas.drag_finished.connect(lambda: self.history.commit("Mover elementos"))
        self.gcode_panel.operations_changed.connect(lambda: self.history.commit("Editar operaciones"))

    def setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        # Layout Principal Horizontal: [ Pestañas Centrales | Barra Lateral ]
        self.main_layout = QHBoxLayout(main_widget)

        # --- A. ZONA CENTRAL (PESTAÑAS) ---
        self.tabs = QTabWidget()
        
        # 1. Pestaña Diseño
        self.tab_design = QWidget()
        self.layout_design = QVBoxLayout(self.tab_design)
        self.layout_design.setContentsMargins(0,0,0,0)
        
        self.lbl_info = StatusLabel('Listo.')
        self.canvas = ViewerCanvas()
        
        self.lbl_registration = StatusLabel()
        self.statusBar().setSizeGripEnabled(False)
        self.statusBar().addWidget(self.lbl_info, 2)
        self.statusBar().addWidget(self.lbl_registration, 1)
        self.layout_design.addWidget(self.canvas)
        
        # 2. Pestaña Visor G-Code
        self.tab_viewer = QWidget()
        self.layout_viewer = QVBoxLayout(self.tab_viewer)
        self.layout_viewer.setContentsMargins(0,0,0,0)
        
        self.gcode_display = QTextEdit()
        self.gcode_display.setPlaceholderText("Genera el código desde el panel derecho para verlo aquí.")
        self.gcode_display.setReadOnly(True)
        self.gcode_display.setStyleSheet("font-family: Consolas, monospace; font-size: 13px;")
        
        self.layout_viewer.addWidget(self.gcode_display)

        # Agregar pestañas
        self.tabs.addTab(self.tab_design, "🎨 Diseño (Canvas)")
        self.tabs.addTab(self.tab_viewer, "📝 Código Generado")

        self.viewer_3d = None
        self.tab_3d = QWidget()
        self.layout_3d = QVBoxLayout(self.tab_3d)
        self.label_3d = QLabel("Abre esta pestaña para cargar el visor 3D.")
        self.label_3d.setWordWrap(True)
        self.layout_3d.addWidget(self.label_3d)
        self.refresh_3d = QPushButton("Actualizar desde el diseño")
        self.refresh_3d.clicked.connect(self.update_3d_from_design)
        self.layout_3d.addWidget(self.refresh_3d)
        self.tabs.addTab(self.tab_3d, "Vista 3D")
        self.tabs.currentChanged.connect(self.on_tab_changed)

        # --- B. BARRA LATERAL (FIJA) ---
        self.sidebar = QWidget()
        self.sidebar.setMinimumWidth(300)
        l_sidebar = QVBoxLayout(self.sidebar)
        l_sidebar.setContentsMargins(5, 5, 5, 5)
        
        # 1. Panel de Archivo (Siempre visible)
        self.file_panel = FilePanel()
        l_sidebar.addWidget(self.file_panel)
        
        l_sidebar.addSpacing(10)

        # 2. Panel de Control (DESPLEGABLE)
        self.control_panel = ControlPanel()
        # Envolvemos el panel en nuestra caja colapsable
        self.box_control = CollapsibleBox("Transformación", self.control_panel)
        l_sidebar.addWidget(self.box_control)
        
        l_sidebar.addSpacing(5)

        # 3. Panel G-Code (DESPLEGABLE)
        self.gcode_panel = GCodePanel()
        self.box_gcode = CollapsibleBox("Configuración G-Code", self.gcode_panel)
        l_sidebar.addWidget(self.box_gcode)

        l_sidebar.addStretch() # Empuja todo hacia arriba

        # Agregar al layout principal
        self.main_layout.addWidget(self.tabs, stretch=1)
        self.sidebar_scroll = QScrollArea()
        self.sidebar_scroll.setWidgetResizable(True)
        self.sidebar_scroll.setWidget(self.sidebar)
        self.sidebar_scroll.setFixedWidth(330)
        self.main_layout.addWidget(self.sidebar_scroll, stretch=0)

    def configure_worktable(self):
        from gui.worktable_dialog import WorktableDialog
        dialog=WorktableDialog(self.gcode_panel.generator.worktable,self)
        if dialog.exec()==WorktableDialog.DialogCode.Accepted:
            self.apply_worktable(dialog.settings())

    def apply_worktable(self, settings):
        from core.worktable import validate_worktable
        settings=validate_worktable(settings)
        if settings==self.gcode_panel.generator.worktable:
            return
        self.gcode_panel.generator.worktable=settings
        self.canvas.set_worktable(settings)
        self.history.commit('Configurar topes y origen')
        self.update_canvas_preview()
        self.statusBar().showMessage('Topes y origen actualizados.',5000)

    def setup_connections(self):
        # Carga
        self.file_panel.signal_load.connect(self.action_load_file)
        self.file_panel.signal_gcode.connect(self.save_cgc)
        
        # Canvas -> Selección
        self.canvas.items_selected.connect(self.on_items_selected)
        
        # Panel Control -> Transformación
        self.control_panel.value_changed.connect(self.apply_transformations)
        
        # Panel GCode -> Visor
        self.gcode_panel.gcode_generated.connect(self.display_gcode_result)

        self.gcode_panel.operations_changed.connect(self.update_canvas_preview)

    def action_load_file(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Importar DXF", "", "DXF (*.dxf)")
        if filename:
            try:
                self.import_dxf(filename)
            except ValueError as exc:
                QMessageBox.warning(self, 'No se puede importar', str(exc))

    def import_dxf(self, filename):
        generator = self.gcode_panel.generator
        if generator.registration:
            raise ValueError('El diseño tiene una referencia ArUco. Usa Editar > Vaciar diseño antes de importar otro DXF.')
        paths = self.dxf_reader.read(filename)
        if not paths:
            raise ValueError('El DXF no contiene curvas de decoración válidas.')
        registration = self.dxf_reader.registration
        if registration and any(isinstance(i, DXFGraphicsItem) for i in self.canvas.scene.items()):
            raise ValueError('Importa el diseño con ArUco en un lienzo vacío: Editar > Vaciar diseño.')
        if not generator.operations:
            generator.design_name = Path(filename).stem
        added = self.canvas.add_dxf_object(paths)
        if registration:
            generator.registration = registration
            generator.registration_geometry = {i: generator.item_geometry(i) for i in added}
            for item in added:
                item.registration_locked = True
                item.setFlag(item.GraphicsItemFlag.ItemIsMovable, False)
                item.setToolTip('Diseño vinculado a la impresión. Modifica posición y tamaño en Corel.')
        self.sync_registration_ui()
        self.history.commit('Importar DXF')
        self.update_canvas_preview()
        self.lbl_info.setText(f'Añadido: {Path(filename).name}')
        self.tabs.setCurrentIndex(0)
        if registration:
            rect = added[0].sceneBoundingRect()
            for item in added[1:] + self.canvas.registration_items:
                rect = rect.united(item.sceneBoundingRect())
            rect = rect.adjusted(-5,-5,5,5)
            self.canvas.setSceneRect(self.canvas.sceneRect().united(rect))
            self.canvas.fitInView(rect, Qt.KeepAspectRatio)
        return added

    def sync_registration_ui(self):
        registration = self.gcode_panel.generator.registration
        self.canvas.show_registration(registration)
        self.update_registered_controls()
        if not registration:
            self.lbl_registration.setText('')
            return
        data = registration['metadata']
        a,b = data['corners_design_mm'][:2]
        angle = math.degrees(math.atan2(b[1]-a[1],b[0]-a[0]))
        text = f'ArUco {data["id"]} · {angle:.1f}°'
        try:
            warnings = self.gcode_panel.generator.alignment_warnings()
        except ValueError:
            warnings = []  # The normal preview reports invalid operations.
        self.lbl_registration.setText(text + (' · Revisar cobertura' if warnings else ''))
        self.lbl_registration.setToolTip('\n'.join(warnings) if warnings else
            f'ArUco {data["id"]} · {data["side_mm"]:g} mm. Ctrl+A para mover o girar el conjunto.')

    def registered_group_selected(self):
        items = [i for i in self.canvas.scene.items() if isinstance(i, DXFGraphicsItem)]
        return bool(self.gcode_panel.generator.registration and items and all(i.isSelected() for i in items))

    def registration_center(self):
        reg = self.gcode_panel.generator.registration
        if 'placement_center' in reg:
            return reg['placement_center']
        items = [i for i in self.canvas.scene.items() if isinstance(i, DXFGraphicsItem)]
        rect = items[0].sceneBoundingRect()
        for item in items[1:]:
            rect = rect.united(item.sceneBoundingRect())
        return [rect.center().x(), rect.center().y()]

    def update_registered_controls(self):
        panel = self.control_panel
        reg = self.gcode_panel.generator.registration
        if not reg:
            panel.update_ui_from_selection(self.canvas.scene.selectedItems())
            return
        panel.block_signals = True
        try:
            panel.setEnabled(self.registered_group_selected())
            panel.group_pos.setEnabled(True)
            panel.group_rot.setEnabled(True)
            panel.group_scale.setEnabled(False)
            x,y = self.registration_center()
            panel.spin_x.setValue(x); panel.spin_y.setValue(y)
            panel.spin_scale.setValue(1)
            panel.spin_rot.setValue(reg.get('placement_rotation',0))
            panel.lbl_info.setText('Ctrl+A: selecciona todo para mover o girar. X/Y: centro del conjunto. Escala fija.')
        finally:
            panel.block_signals = False

    def move_registered_group(self, dx, dy):
        if not self.registered_group_selected():
            return False
        x,y = self.registration_center()
        reg = self.gcode_panel.generator.registration
        self.transform_registered_group(x+dx,y+dy,reg.get('placement_rotation',0))
        return True

    def transform_registered_group(self, x, y, rotation):
        if not self.registered_group_selected():
            return
        generator = self.gcode_panel.generator
        reg = copy.deepcopy(generator.registration)
        cx,cy = self.registration_center()
        delta = rotation-reg.get('placement_rotation',0)
        if abs(x-cx)+abs(y-cy)+abs(delta)<1e-10:
            return
        angle = math.radians(delta); c,s = math.cos(angle),math.sin(angle)
        def transformed(p):
            vx,vy = p[0]-cx,p[1]-cy
            return [x+c*vx-s*vy,y+s*vx+c*vy]
        items = [i for i in self.canvas.scene.items() if isinstance(i,DXFGraphicsItem)]
        for item in items:
            item.registration_locked = False
            try:
                px,py = transformed((item.x(),item.y()))
                item.setPos(px,py)
                item.setRotation(item.rotation()+delta)
            finally:
                item.registration_locked = True
        reg['metadata']['corners_design_mm'] = [transformed(p) for p in reg['metadata']['corners_design_mm']]
        for shape in reg['shapes']:
            shape['points'] = [transformed(p) for p in shape['points']]
        reg['placement_center'] = [x,y]
        reg['placement_rotation'] = rotation
        generator.registration = reg
        generator.registration_geometry = {i:generator.item_geometry(i) for i in items}
        self.sync_registration_ui()
        self.on_geometry_changed()

    def on_items_selected(self, items):
        """
        Maneja la lógica de UI al seleccionar y pasa los datos al Transformer.
        """
        # 1. Pasar selección al gestor lógico
        self.transformer.set_selection(items)
        
        # 2. Actualizar UI (Panel Transformación)
        self.control_panel.update_ui_from_selection(items)
        if self.gcode_panel.generator.registration:
            self.update_registered_controls()
        
        # 3. Actualizar UI (Panel G-Code y Textos)
        if len(items) == 1:
            self.gcode_panel.update_selection(items[0])
            self.gcode_panel.setEnabled(True)
            self.lbl_info.setText("Objeto seleccionado.")
            if not self.box_control.toggle_button.isChecked():
                self.box_control.toggle_button.click()
        else:
            self.gcode_panel.update_selection(None)
            self.gcode_panel.setEnabled(True)
            if len(items) > 1:
                self.lbl_info.setText(f"{len(items)} objetos seleccionados.")
            else:
                self.lbl_info.setText('Listo.')

    def apply_transformations(self, x, y, scale, rotation):
        if self.scan_editor.active:
            return
        if self.gcode_panel.generator.registration:
            if scale != 1:
                self.update_registered_controls()
                return
            self.transform_registered_group(x,y,rotation)
            self.history.commit('Mover/girar conjunto ArUco')
            return
        self.transformer.apply(x, y, scale, rotation)
        self.history.commit("Transformar elementos")

    def display_gcode_result(self, text):
        if self.preview_timer.isActive():
            self.preview_timer.stop()
            self.update_canvas_preview()
        self.gcode_display.setPlainText(text)
        if self.viewer_3d is not None:
            self.viewer_3d.load_code(text)
        self.tabs.setCurrentIndex(1)
        self.file_panel.enable_gcode_button(True)

    def update_canvas_preview(self):
        """Pide al generador los caminos calculados y se los manda al canvas"""
        # 1. Obtener datos de geometría (rutas de relleno o borde)
        self.invalidate_code()
        try:
            preview_data = self.gcode_panel.generator.get_all_preview_paths()
        except ValueError as exc:
            self.canvas.draw_preview_paths([])
            self.lbl_info.setText(str(exc))
            return
        self.canvas.draw_preview_paths(preview_data)
        self.sync_registration_ui()

        if hasattr(self, 'scan_editor'):
            self.scan_editor.refresh()

    def toggle_scan_editor(self, row):
        if self.scan_editor.active:
            self.scan_editor.finish()
        else:
            self.gcode_panel.cancel_editing()
            self.scan_editor.begin(row)

    def scan_operation_changed(self, row):
        if self.scan_editor.active and not self.history.restoring and row != self.scan_editor.row:
            self.scan_editor.finish()

    def invalidate_code(self):
        if self.viewer_3d is not None:
            self.viewer_3d.clear()
        self.gcode_display.clear()
        self.gcode_display.setPlaceholderText("El diseño cambió. Genera el código para actualizarlo.")
        self.file_panel.enable_gcode_button(bool(self.gcode_panel.generator.operations))

    def on_geometry_changed(self):
        self.invalidate_code()
        self.preview_timer.start()

    def save_cgc(self):
        # Regenerar siempre desde la geometría actual, nunca guardar texto obsoleto.
        self.preview_timer.stop()
        try:
            code = self.gcode_panel.generator.generate_full_code()
        except ValueError as exc:
            QMessageBox.warning(self, "No se puede guardar", str(exc))
            return
        suggested = self.gcode_panel.generator.design_name + '.cgc'
        filename, _ = QFileDialog.getSaveFileName(self, "Guardar CGC", suggested, "Cookie G-code (*.cgc)")
        if not filename:
            return
        if not filename.lower().endswith('.cgc'):
            filename += '.cgc'
            if Path(filename).exists():
                answer = QMessageBox.question(self, "Reemplazar archivo", "El archivo CGC ya existe. ¿Reemplazarlo?",
                                              QMessageBox.Yes | QMessageBox.No)
                if answer != QMessageBox.Yes:
                    return
        target = QSaveFile(filename)
        data = code.encode('utf-8')
        if not target.open(QIODevice.WriteOnly):
            QMessageBox.critical(self, "Error al guardar", target.errorString())
            return
        if target.write(data) != len(data):
            target.cancelWriting()
            QMessageBox.critical(self, "Error al guardar", target.errorString())
            return
        if not target.commit():
            QMessageBox.critical(self, "Error al guardar", target.errorString())
            return
        self.display_gcode_result(code)
        self.statusBar().showMessage(f"CGC guardado: {filename}", 10000)
    def on_tab_changed(self, index):
        if self.tabs.widget(index) != self.tab_3d:
            return
        if self.viewer_3d is None:
            try:
                from gui.gcode_3d_viewer import Gcode3DViewer
                self.viewer_3d = Gcode3DViewer(self.tab_3d)
            except (ImportError, RuntimeError, OSError) as exc:
                self.label_3d.setText(f"No se pudo cargar el visor 3D: {exc}")
                return
            self.label_3d.hide()
            self.layout_3d.addWidget(self.viewer_3d, 1)
        if not self.gcode_display.toPlainText().strip():
            self.update_3d_from_design()
        elif self.viewer_3d.data is None:
            self.viewer_3d.load_code(self.gcode_display.toPlainText())

    def update_3d_from_design(self):
        if self.viewer_3d is None:
            self.on_tab_changed(self.tabs.currentIndex())
            return
        self.preview_timer.stop()
        self.update_canvas_preview()
        try:
            code = self.gcode_panel.generator.generate_full_code()
        except ValueError as exc:
            self.viewer_3d.clear(str(exc))
            return
        self.gcode_display.setPlainText(code)
        self.viewer_3d.load_code(code)

    def setup_edit_actions(self):
        menu = self.menuBar().addMenu("Editar")
        self.undo_action = self.history.stack.createUndoAction(self, "Deshacer")
        self.undo_action.setShortcut(QKeySequence.Undo)
        self.redo_action = self.history.stack.createRedoAction(self, "Rehacer")
        self.redo_action.setShortcuts([QKeySequence("Ctrl+Y"), QKeySequence("Ctrl+Shift+Z")])
        menu.addAction(self.undo_action); menu.addAction(self.redo_action)
        menu.addSeparator()
        self.delete_action = QAction("Eliminar seleccionados", self)
        self.delete_action.setShortcut(QKeySequence("Delete"))
        self.delete_action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        self.canvas.addAction(self.delete_action)
        self.delete_action.triggered.connect(self.delete_selected_design)
        menu.addAction(self.delete_action)
        self.select_all_action = QAction("Seleccionar todo el diseño", self)
        self.select_all_action.setShortcut(QKeySequence.SelectAll)
        self.select_all_action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        self.canvas.addAction(self.select_all_action)
        self.select_all_action.triggered.connect(self.select_all_design)
        menu.addAction(self.select_all_action)
        self.clear_design_action = QAction("Vaciar diseño", self)
        self.clear_design_action.triggered.connect(self.clear_design)
        menu.addAction(self.clear_design_action)


    def select_all_design(self):
        if self.scan_editor.active:
            return
        for item in self.canvas.scene.items():
            if isinstance(item, DXFGraphicsItem):
                item.setSelected(True)
        self.canvas.setFocus()

    def delete_selected_design(self):
        if self.scan_editor.active:
            self.scan_editor.delete_selected()
            return
        items = [item for item in self.canvas.scene.selectedItems() if isinstance(item, DXFGraphicsItem)]
        self.remove_design_items(items, "Eliminar elementos")

    def clear_design(self):
        self.scan_editor.finish()
        items = [item for item in self.canvas.scene.items() if isinstance(item, DXFGraphicsItem)]
        self.remove_design_items(items, "Vaciar diseño")

    def remove_design_items(self, items, label):
        if not items:
            return
        self.preview_timer.stop()
        # Record deletion and related operations as one command.
        self.history.restoring = True
        try:
            scene = self.canvas.scene
            scene.blockSignals(True)
            try:
                for item in items:
                    scene.removeItem(item)
            finally:
                scene.blockSignals(False)
            panel = self.gcode_panel
            panel.cancel_editing()
            panel.generator.operations = [op for op in panel.generator.operations
                                          if op.get('source_item') not in items]
            if not any(isinstance(i, DXFGraphicsItem) for i in scene.items()):
                panel.generator.registration = None
                panel.generator.registration_geometry = {}
            self.sync_registration_ui()
            panel.refresh_list()
            self.on_items_selected(scene.selectedItems())
        finally:
            self.history.restoring = False
        self.history.commit(label)
