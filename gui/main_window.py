from PySide6.QtWidgets import (QMainWindow, QVBoxLayout, QWidget, 
                               QPushButton, QFileDialog, QMessageBox, QLabel)
from PySide6.QtCore import Qt

# Importamos nuestros módulos propios
from gui.canvas import ViewerCanvas
from core.dxf_processor import DXFProcessor

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("CookieCNC - Generador de G-Code")
        self.resize(1000, 700)
        
        # Instanciar el procesador lógico
        self.processor = DXFProcessor()

        # --- Configuración UI ---
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # 1. Barra superior
        self.lbl_info = QLabel("Carga un archivo DXF para comenzar")
        self.lbl_info.setStyleSheet("font-size: 14px; padding: 5px;")
        layout.addWidget(self.lbl_info)

        # 2. El Lienzo (Nuestro widget personalizado)
        self.canvas = ViewerCanvas()
        layout.addWidget(self.canvas)

        # 3. Botones
        self.btn_load = QPushButton("Cargar DXF")
        self.btn_load.setMinimumHeight(40)
        self.btn_load.clicked.connect(self.action_load_file)
        layout.addWidget(self.btn_load)
        
        # (Futuro botón para guardar Gcode)
        self.btn_gcode = QPushButton("Generar G-Code")
        self.btn_gcode.setEnabled(False) # Desactivado hasta cargar algo
        layout.addWidget(self.btn_gcode)

    def action_load_file(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Abrir DXF", "", "DXF Files (*.dxf)")
        
        if filename:
            # 1. Usar el Core para cargar
            success = self.processor.load_file(filename)
            
            if success:
                # 2. Obtener la geometría procesada
                paths = self.processor.get_paths()
                
                # 3. Mandarla al GUI para dibujar
                count = self.canvas.draw_geometry(paths)
                
                self.lbl_info.setText(f"Archivo cargado: {filename} | Elementos: {count}")
                self.btn_gcode.setEnabled(True)
            else:
                QMessageBox.critical(self, "Error", "No se pudo leer el archivo DXF.")