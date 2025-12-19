from PySide6.QtWidgets import (QMainWindow, QHBoxLayout, QVBoxLayout, QWidget, 
                               QFileDialog, QMessageBox, QLabel, QFrame)
from PySide6.QtCore import Qt

# Importamos los 3 módulos
from gui.canvas import ViewerCanvas
from gui.control_panel import ControlPanel
from gui.file_panel import FilePanel  # <--- Importamos el nuevo widget
from core.dxf_processor import DXFProcessor

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("CookieCNC - Editor Modular v2")
        self.resize(1100, 750)
        
        self.processor = DXFProcessor()

        # Widget central
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        self.main_layout = QHBoxLayout(main_widget)

        # --- IZQUIERDA: LIENZO ---
        self.canvas_container = QWidget()
        canvas_layout = QVBoxLayout(self.canvas_container)
        canvas_layout.setContentsMargins(0,0,0,0)
        
        self.lbl_info = QLabel("Bienvenido. Carga un DXF.")
        self.lbl_info.setStyleSheet("padding: 5px; color: gray;")
        self.canvas = ViewerCanvas()
        
        canvas_layout.addWidget(self.lbl_info)
        canvas_layout.addWidget(self.canvas)
        
        # --- DERECHA: BARRA LATERAL (Sidebar) ---
        # Creamos un contenedor vertical para apilar los paneles
        self.sidebar = QWidget()
        self.sidebar.setFixedWidth(280)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setAlignment(Qt.AlignTop)
        
        # 1. Panel de Archivos (Arriba)
        self.file_panel = FilePanel()
        sidebar_layout.addWidget(self.file_panel)
        
        # Separador visual (Línea horizontal)
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        sidebar_layout.addWidget(line)
        
        # 2. Panel de Control (Debajo)
        self.control_panel = ControlPanel()
        sidebar_layout.addWidget(self.control_panel)
        
        # Espaciador al final para empujar todo hacia arriba
        sidebar_layout.addStretch()

        # Agregamos los contenedores al layout principal
        self.main_layout.addWidget(self.canvas_container, stretch=1)
        self.main_layout.addWidget(self.sidebar, stretch=0)

        # --- CONEXIONES (WIRING) ---
        
        # Conexiones del FilePanel
        self.file_panel.signal_load.connect(self.action_load_file)
        self.file_panel.signal_gcode.connect(self.action_generate_gcode)
        
        # Conexiones del ControlPanel
        self.control_panel.signal_move.connect(self.apply_move)
        self.control_panel.signal_scale.connect(self.apply_scale)
        self.control_panel.signal_rotate.connect(self.apply_rotate)

    # --- LÓGICA ---

    def refresh_canvas(self):
        paths = self.processor.get_paths()
        count = self.canvas.draw_geometry(paths)
        self.lbl_info.setText(f"Vista previa: {count} trazos")

    def action_load_file(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Abrir DXF", "", "DXF Files (*.dxf)")
        if filename:
            if self.processor.load_file(filename):
                self.refresh_canvas()
                self.file_panel.enable_gcode_button(True) # Activamos el botón en el otro panel
                self.lbl_info.setText(f"Archivo: {filename}")
            else:
                QMessageBox.critical(self, "Error", "No se pudo leer el archivo DXF.")

    def apply_move(self, dx, dy):
        self.processor.move(dx, dy)
        self.refresh_canvas()

    def apply_scale(self, factor):
        self.processor.scale(factor)
        self.refresh_canvas()

    def apply_rotate(self, angle):
        self.processor.rotate(angle)
        self.refresh_canvas()

    def action_generate_gcode(self):
        QMessageBox.information(self, "G-Code", "¡Generando G-Code... (Lógica pendiente)!")