from PySide6.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QGroupBox)
from PySide6.QtCore import Signal

class FilePanel(QWidget):
    # Señales para comunicar al exterior qué botón se presionó
    signal_load = Signal()
    signal_gcode = Signal()

    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        # Usamos un layout vertical para apilar los elementos
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0) # Sin márgenes externos para que encaje bien

        # Grupo "Proyecto"
        group = QGroupBox("Proyecto / Archivo")
        group_layout = QVBoxLayout()
        
        # Botón Cargar
        self.btn_load = QPushButton("📂 Cargar DXF")
        self.btn_load.setMinimumHeight(35) # Un poco más alto para que destaque
        self.btn_load.clicked.connect(self.signal_load.emit)
        
        # Botón Guardar (inicia desactivado)
        self.btn_gcode = QPushButton("💾 Guardar CGC")
        self.btn_gcode.setMinimumHeight(35)
        self.btn_gcode.setEnabled(False)
        self.btn_gcode.setStyleSheet("background-color: #e1e1e1;") # Visualmente desactivado
        self.btn_gcode.clicked.connect(self.signal_gcode.emit)
        
        group_layout.addWidget(self.btn_load)
        group_layout.addWidget(self.btn_gcode)
        group.setLayout(group_layout)
        
        layout.addWidget(group)

    def enable_gcode_button(self, enable=True):
        """Activa o desactiva el botón de guardar visualmente"""
        self.btn_gcode.setEnabled(enable)
        if enable:
            self.btn_gcode.setStyleSheet("background-color: #cfc; font-weight: bold;") # Verde suave al activar
        else:
            self.btn_gcode.setStyleSheet("background-color: #e1e1e1;")