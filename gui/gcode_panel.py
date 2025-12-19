from PySide6.QtWidgets import (QWidget, QVBoxLayout, QGroupBox, QComboBox, 
                               QPushButton, QFormLayout, QListWidget, QColorDialog, 
                               QHBoxLayout, QLabel, QMessageBox)
from PySide6.QtGui import QColor
from PySide6.QtCore import Signal
from core.gcode_generator import GCodeGenerator

class GCodePanel(QWidget):
    # Señal para enviar el texto final
    gcode_generated = Signal(str)

    def __init__(self):
        super().__init__()
        self.current_item = None
        self.generator = GCodeGenerator()
        self.current_color = "#000000" # Color por defecto (Negro)
        
        self.setup_ui()
        self.setEnabled(False)

    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # --- Configuración de Operación ---
        group = QGroupBox("Nueva Operación")
        form = QFormLayout()
        
        # Tipo: Línea o Relleno
        self.combo_type = QComboBox()
        self.combo_type.addItems(["Línea (Borde)", "Relleno (Trama)"])
        form.addRow("Tipo:", self.combo_type)
        
        # Inyector
        self.combo_injector = QComboBox()
        self.combo_injector.addItems(["1", "2", "3", "4"])
        form.addRow("Inyector:", self.combo_injector)
        
        # Selector de Color
        color_layout = QHBoxLayout()
        self.btn_color = QPushButton()
        self.btn_color.setFixedWidth(50)
        self.btn_color.clicked.connect(self.choose_color)
        self.lbl_color_hex = QLabel(self.current_color)
        
        color_layout.addWidget(self.btn_color)
        color_layout.addWidget(self.lbl_color_hex)
        form.addRow("Color:", color_layout)
        self._update_color_btn() # Pintar estado inicial
        
        # Botón Agregar
        self.btn_add = QPushButton("➕ Agregar Operación")
        self.btn_add.clicked.connect(self.add_operation_to_queue)
        form.addRow(self.btn_add)
        
        group.setLayout(form)
        layout.addWidget(group)
        
        # --- Cola de Operaciones (Lista) ---
        layout.addWidget(QLabel("Cola de trabajo:"))
        self.list_ops = QListWidget()
        layout.addWidget(self.list_ops)
        
        # Botón Limpiar Cola
        self.btn_clear = QPushButton("Limpiar Todo")
        self.btn_clear.clicked.connect(self.clear_queue)
        layout.addWidget(self.btn_clear)
        
        layout.addStretch()

        # --- Botón Final ---
        self.btn_generate = QPushButton("💾 GENERAR CÓDIGO FINAL")
        self.btn_generate.setMinimumHeight(40)
        self.btn_generate.setStyleSheet("background-color: #28a745; color: white; font-weight: bold;")
        self.btn_generate.clicked.connect(self.generate_final_code)
        layout.addWidget(self.btn_generate)

    def choose_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            # Convertir a Hex formato #RRGGBB
            self.current_color = color.name()
            self._update_color_btn()

    def _update_color_btn(self):
        self.btn_color.setStyleSheet(f"background-color: {self.current_color}; border: 1px solid #555;")
        self.lbl_color_hex.setText(self.current_color)

    def update_selection(self, item):
        self.current_item = item
        # Habilitamos el panel si hay un ítem seleccionado, 
        # PERO también debe estar habilitado si ya hay operaciones en cola para poder exportar.
        self.setEnabled(True) 
        # (Podrías refinar esto para deshabilitar solo el botón de "Agregar" si no hay item)

    def add_operation_to_queue(self):
        if not self.current_item:
            QMessageBox.warning(self, "Atención", "Selecciona un objeto en el diseño primero.")
            return

        # 1. Recoger datos
        op_type = "line" if self.combo_type.currentIndex() == 0 else "fill"
        inj = self.combo_injector.currentText()
        col = self.current_color
        
        # 2. Obtener geometría
        transform = self.current_item.sceneTransform()
        path_local = self.current_item.path()
        polygons = list(path_local.toSubpathPolygons(transform)) # Convertir a lista segura
        
        # 3. Guardar en el generador
        self.generator.add_operation(polygons, op_type, inj, col)
        
        # 4. Actualizar lista visual
        item_text = f"{len(self.generator.operations)}. {op_type.upper()} - Inj {inj} - {col}"
        self.list_ops.addItem(item_text)

    def clear_queue(self):
        self.generator.clear_operations()
        self.list_ops.clear()

    def generate_final_code(self):
        if self.list_ops.count() == 0:
            QMessageBox.warning(self, "Vacío", "No has agregado ninguna operación a la cola.")
            return

        # Pedirle al core que construya el string completo
        full_code = self.generator.generate_full_code()
        
        # Emitir señal a Main Window
        self.gcode_generated.emit(full_code)