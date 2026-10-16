from PySide6.QtWidgets import (QWidget, QVBoxLayout, QGroupBox, QComboBox, 
                               QPushButton, QFormLayout, QListWidget, QColorDialog, 
                               QHBoxLayout, QLabel, QMessageBox, QLineEdit, QDoubleSpinBox)
from PySide6.QtGui import QColor
from PySide6.QtCore import Signal
from core.gcode_generator import GCodeGenerator

class GCodePanel(QWidget):
    gcode_generated = Signal(str)
    operations_changed = Signal() # <--- NUEVA SEÑAL
    scan_edit_requested = Signal(int)
    operations_reordering = Signal()

    def __init__(self):
        super().__init__()
        self.current_item = None
        self.generator = GCodeGenerator()
        self.current_color = "#000000"
        self.editing_index = None 
        self.setup_ui()
        self.setEnabled(True) 

    def setup_ui(self):
        # (Mismo código de UI que el paso anterior...)
        layout = QVBoxLayout(self)
        self.group_config = QGroupBox("Configuración Operación")
        form = QFormLayout()
        self.txt_name = QLineEdit()
        self.txt_name.setPlaceholderText("Ej: Contorno Exterior")
        form.addRow("Operación:", self.txt_name)
        self.txt_material = QLineEdit()
        self.txt_material.setPlaceholderText("Ej: Royal icing blanco")
        form.addRow("Royal icing:", self.txt_material)
        self.combo_type = QComboBox()
        self.combo_type.addItems(["Línea (Borde)", "Relleno (Trama)"])
        form.addRow("Tipo:", self.combo_type)
        self.combo_injector = QComboBox()
        self.combo_injector.addItems(["1", "2", "3", "4"])
        form.addRow("Inyector:", self.combo_injector)
        self.spin_nozzle = QDoubleSpinBox()
        self.spin_nozzle.setRange(0.1, 5.0)
        self.spin_nozzle.setSingleStep(0.1)
        self.spin_nozzle.setValue(2.0)
        self.spin_nozzle.setSuffix(" mm")
        form.addRow("Boquilla:", self.spin_nozzle)
        color_layout = QHBoxLayout()
        self.btn_color = QPushButton()
        self.btn_color.setFixedWidth(50)
        self.btn_color.clicked.connect(self.choose_color)
        self.lbl_color_hex = QLabel(self.current_color)
        color_layout.addWidget(self.btn_color)
        color_layout.addWidget(self.lbl_color_hex)
        form.addRow("Color:", color_layout)
        self._update_color_btn()
        
        self.layout_actions = QHBoxLayout()
        self.btn_add = QPushButton("➕ Agregar")
        self.btn_add.clicked.connect(self.action_add_or_save)
        self.btn_cancel_edit = QPushButton("Cancelar")
        self.btn_cancel_edit.setVisible(False)
        self.btn_cancel_edit.clicked.connect(self.cancel_editing)
        self.layout_actions.addWidget(self.btn_add)
        self.layout_actions.addWidget(self.btn_cancel_edit)
        form.addRow(self.layout_actions)
        self.group_config.setLayout(form)
        layout.addWidget(self.group_config)
        
        layout.addWidget(QLabel("Cola de trabajo:"))
        self.list_ops = QListWidget()
        self.list_ops.setSelectionMode(QListWidget.SingleSelection)
        self.list_ops.itemClicked.connect(self.on_list_item_clicked)
        layout.addWidget(self.list_ops)
        order_layout = QHBoxLayout()
        self.btn_up = QPushButton('↑ Subir')
        self.btn_down = QPushButton('↓ Bajar')
        self.btn_up.clicked.connect(lambda: self.move_operation(-1))
        self.btn_down.clicked.connect(lambda: self.move_operation(1))
        order_layout.addWidget(self.btn_up)
        order_layout.addWidget(self.btn_down)
        layout.addLayout(order_layout)
        self.list_ops.currentRowChanged.connect(self.update_order_buttons)
        self.update_order_buttons()
        
        list_btns_layout = QHBoxLayout()
        self.btn_edit = QPushButton("✏️ Editar")
        self.btn_edit.setEnabled(False)
        self.btn_edit.clicked.connect(self.start_editing)
        self.btn_delete = QPushButton("🗑️ Borrar")
        self.btn_delete.setEnabled(False)
        self.btn_delete.clicked.connect(self.delete_selected)
        list_btns_layout.addWidget(self.btn_edit)
        list_btns_layout.addWidget(self.btn_delete)
        layout.addLayout(list_btns_layout)

        self.btn_clear = QPushButton("Limpiar Todo")
        self.btn_clear.clicked.connect(self.clear_queue)
        layout.addWidget(self.btn_clear)
        self.btn_scan = QPushButton('Editar puntos de escaneo')
        self.btn_scan.setEnabled(False)
        self.btn_scan.clicked.connect(lambda: self.scan_edit_requested.emit(self.list_ops.currentRow()))
        self.list_ops.currentRowChanged.connect(self.update_scan_button)
        layout.addWidget(self.btn_scan)
        layout.addStretch()
        self.btn_generate = QPushButton("💾 GENERAR CÓDIGO FINAL")
        self.btn_generate.setMinimumHeight(40)
        self.btn_generate.setStyleSheet("background-color: #28a745; color: white; font-weight: bold;")
        self.btn_generate.clicked.connect(self.generate_final_code)
        layout.addWidget(self.btn_generate)
        self.combo_injector.currentTextChanged.connect(self.load_injector_definition)
        self.scan_info = QLabel('FILL: selecciona una operación en la cola para editar sus puntos de escaneo. '
                               'Cada región necesita al menos un punto interior.')
        self.scan_info.setWordWrap(True)
        layout.addWidget(self.scan_info)

    def load_injector_definition(self, text):
        if self.editing_index is not None:
            return
        for op in self.generator.operations:
            if op['injector'] == int(text):
                self.current_color = op['color']
                self.txt_material.setText(op['material_name'])
                self.spin_nozzle.setValue(op['nozzle'])
                self._update_color_btn()
                return

    def update_scan_button(self, row):
        ops=self.generator.operations
        self.btn_scan.setEnabled(0<=row<len(ops) and ops[row]['type']=='fill')

    def update_order_buttons(self, *_):
        row = self.list_ops.currentRow()
        count = len(self.generator.operations)
        enabled = self.editing_index is None
        self.btn_up.setEnabled(enabled and 0 < row < count)
        self.btn_down.setEnabled(enabled and 0 <= row < count-1)

    def move_operation(self, direction):
        row = self.list_ops.currentRow()
        target = row + direction
        ops = self.generator.operations
        if self.editing_index is not None or direction not in (-1, 1) or not 0 <= row < len(ops) or not 0 <= target < len(ops):
            return
        # Stop sample editing before the index changes, even for shared geometry.
        self.operations_reordering.emit()
        ops.insert(target, ops.pop(row))
        self.refresh_list()
        self.list_ops.setCurrentRow(target)
        self.btn_edit.setEnabled(True)
        self.btn_delete.setEnabled(True)
        self.list_ops.setFocus()

    def choose_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.current_color = color.name()
            self._update_color_btn()

    def _update_color_btn(self):
        self.btn_color.setStyleSheet(f"background-color: {self.current_color}; border: 1px solid #555;")
        self.lbl_color_hex.setText(self.current_color)

    def update_selection(self, item):
        self.current_item = item

    def on_list_item_clicked(self, item):
        self.btn_edit.setEnabled(True)
        self.btn_delete.setEnabled(True)

    def refresh_list(self):
        self.list_ops.clear()
        for i, op in enumerate(self.generator.operations):
            t = "LINE" if op['type'] == 'line' else "FILL"
            name = op['name'] if op['name'] else "(Sin nombre)"
            text = f"{i+1}. {name} [{t}] - Inj:{op['injector']} - Noz:{op['nozzle']}mm"
            self.list_ops.addItem(text)
        self.btn_edit.setEnabled(False)
        self.btn_delete.setEnabled(False)
        
        # EMITIR SEÑAL DE CAMBIO
        self.operations_changed.emit()

    def action_add_or_save(self):
        op_type = "line" if self.combo_type.currentIndex() == 0 else "fill"
        inj = self.combo_injector.currentText()
        col = self.current_color
        name = self.txt_name.text()
        nozzle = self.spin_nozzle.value()

        if not name.strip() or not self.txt_material.text().strip():
            QMessageBox.warning(self, "Datos incompletos", "Escribe el nombre de operación y del royal icing.")
            return
        previous = [dict(op) for op in self.generator.operations]
        editing = self.editing_index
        if self.editing_index is None:
            if not self.current_item:
                QMessageBox.warning(self, "Atención", "Selecciona un objeto en el diseño primero.")
                return
            transform = self.current_item.sceneTransform()
            path_local = self.current_item.path()
            polygons = list(path_local.toSubpathPolygons(transform))
            self.generator.add_operation(polygons, op_type, inj, col, name, nozzle,
                                         material_name=self.txt_material.text().strip(), source_item=self.current_item)
        else:
            self.generator.update_operation(self.editing_index, op_type, inj, col, name, nozzle,
                                            material_name=self.txt_material.text().strip())

        try:
            self.generator.generate_full_code()
        except ValueError as exc:
            self.generator.operations = previous
            QMessageBox.warning(self, "Operación inválida", str(exc))
            return
        if editing is not None:
            self.cancel_editing()
        self.refresh_list()
        self.reset_operation_form()

    def reset_operation_form(self):
        """Prepare a new operation without changing the saved injector definitions."""
        self.txt_name.clear()
        self.txt_material.clear()
        self.combo_type.setCurrentIndex(0)
        # Returning to injector 1 must not refill the fields from the queue.
        blocked = self.combo_injector.blockSignals(True)
        try:
            self.combo_injector.setCurrentIndex(0)
        finally:
            self.combo_injector.blockSignals(blocked)
        self.spin_nozzle.setValue(2.0)
        self.current_color = '#000000'
        self._update_color_btn()
        self.txt_name.setFocus()

    def start_editing(self):
        row = self.list_ops.currentRow()
        if row < 0: return
        op = self.generator.operations[row]
        self.editing_index = row
        self.txt_name.setText(op['name'])
        self.txt_material.setText(op['material_name'])
        idx_type = 0 if op['type'] == 'line' else 1
        self.combo_type.setCurrentIndex(idx_type)
        combo_idx = self.combo_injector.findText(str(op['injector']))
        if combo_idx >= 0: self.combo_injector.setCurrentIndex(combo_idx)
        self.spin_nozzle.setValue(op['nozzle'])
        self.current_color = op['color']
        self._update_color_btn()
        self.group_config.setTitle(f"Editando Operación #{row+1}")
        self.btn_add.setText("💾 Guardar Cambios")
        self.btn_add.setStyleSheet("background-color: #007bff; color: white;")
        self.btn_cancel_edit.setVisible(True)
        self.list_ops.setEnabled(False)
        self.update_order_buttons()

    def cancel_editing(self):
        self.editing_index = None
        self.group_config.setTitle("Nueva Operación")
        self.btn_add.setText("➕ Agregar")
        self.btn_add.setStyleSheet("")
        self.btn_cancel_edit.setVisible(False)
        self.list_ops.setEnabled(True)
        self.update_order_buttons()
        self.txt_name.clear()

    def delete_selected(self):
        row = self.list_ops.currentRow()
        if row < 0: return
        confirm = QMessageBox.question(self, "Confirmar", "¿Borrar esta operación?", QMessageBox.Yes | QMessageBox.No)
        if confirm == QMessageBox.Yes:
            self.generator.delete_operation(row)
            if self.editing_index == row: self.cancel_editing()
            self.refresh_list()

    def clear_queue(self):
        self.generator.clear_operations()
        self.cancel_editing()
        self.refresh_list()

    def generate_final_code(self):
        if len(self.generator.operations) == 0:
            QMessageBox.warning(self, "Vacío", "No has agregado operaciones.")
            return
        try:
            full_code = self.generator.generate_full_code()
        except ValueError as exc:
            QMessageBox.warning(self, "No se puede generar el CGC", str(exc))
            return
        self.gcode_generated.emit(full_code)
